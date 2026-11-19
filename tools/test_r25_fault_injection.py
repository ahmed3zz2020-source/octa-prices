#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💥 الجولة ٢٥ (R25 · المرحلة ٩) — حقن أعطال متدرّج + خط زمني للتعافي

📌 بند القبول المستهدف ⭐:
   **AC-13-3** ⭐: «حقن أعطال متدرجة ثم عودة المصدر؛ تحقق من عدم مسح
   الحالة الصحيحة» ⭐

📌 التدرّج المستخدم ⭐ (من الأخف للأثقل ⭐):
   ① المصدر **مهل** (timeout) ⭐
   ② المصدر **5xx** ⭐
   ③ المصدر **رد تالف** (مش JSON/مش HTML صالح ⭐) ⭐
   ④ **عودة المصدر** ⭐ ⇒ الخدمة رجعت ⭐

📌 المسار المستهدف ⭐ = `/api/ipo` ⭐:
   · بينادي مصدر خارجي **وقت الطلب** ⭐ ⭐
   · عنده كاش ساعة ⭐ ⇒ في حالة «المصدر وقع» بيرجّع آخر نسخة ⭐
     (مفيش downtime ⭐) ⭐ — وده بالظبط «عدم مسح الحالة الصحيحة» ⭐.

📌 القياس ⭐:
   · خط زمني (timeline) ⭐ لكل مرحلة ⭐ بوقت وحالة ⭐
   · زمن التعافي ⭐ (من لحظة الحقن لحد رجوع الخدمة ⭐)
   · مصدر **مستقل** لازم يفضل شغّال ⭐ أثناء العطل ⭐

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ كل الأعطال **اصطناعية** ⭐ (مفيش أي شبكة ⭐)
   ⛔ سيرفر staging معزول ⭐ في مجلد مؤقّت ⭐ · مافيش نشر ⭐

📌 التشغيل: python3 tools/test_r25_fault_injection.py
   📌 وكل ملف اختبار كمان بيشتغل تحت `pytest` ⭐.
"""
import atexit
import functools
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "staging"))

import iso_env as iso  # noqa: E402

_CLEANUP = []
RESULTS = []
REPORT = {}

# ⛔ درجات العطل ⭐ (من الأخف للأثقل ⭐)
GRADES = [
    ("timeout", "مهلة"),
    ("http_500", "خطأ خادم ٥xx"),
    ("garbage", "رد تالف"),
]


def _launch(tag, stage_dir=None, **kw):
    stage = Path(stage_dir or ("/tmp/octa_r25_fault_%s" % tag))
    srv = iso.launch(stage_dir=str(stage), **kw)
    ok, elapsed = srv.wait_ready(timeout=240)
    if not ok:
        tail = "\n".join(srv.log_tail(30))
        srv.stop()
        raise RuntimeError("السيرفر المعزول ماقومش:\n" + tail)
    _CLEANUP.append(srv)
    return srv


def _cleanup():
    for srv in list(_CLEANUP):
        try:
            srv.stop()
        except Exception:
            pass


atexit.register(_cleanup)


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra else ""), flush=True)
    return bool(cond)


def _case(fn):
    """⛔ غلاف يتوافق مع `pytest` ⭐.

    📌 السبب ⭐: تحت `pytest` ⭐ لازم الاختبار **يفشل** ⭐
    📌 لو فيه أي assertion مش عدى ⭐ ⇒ عشان `pytest` يبلّغ ⭐.
    📌 والاسترجاع (standalone ⭐) بيفضل يطبع كل الإخفاقات ⭐
    📌 لأن الاستثناء بيترمي **بعد** ما الدالة تخلص ⭐.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        before = len(RESULTS)
        completed = False
        try:
            fn(*args, **kwargs)
            completed = True
        finally:
            if completed:
                bad = [r[1] for r in RESULTS[before:] if not r[0]]
                if bad:
                    raise AssertionError(
                        "%d إخفاق ⭐: %s" % (len(bad), " · ".join(bad[:3])))
    return wrapper


def section(title):
    print("\n" + "─" * 70)
    print("  " + title)
    print("─" * 70, flush=True)


def _client(srv):
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip="198.51.100.30")
    cfg = iso.read_stage_cfg(srv.stage_dir)
    tok, st, j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s · %s)"
                           % (st, str(j)[:120]))
    return c


def _fault(c, kind, value):
    st, _h, b, _ms = c.post("/__harness__/fault",
                            {"kind": kind, "value": value})
    try:
        return st, json.loads(b.decode("utf-8"))
    except Exception:
        return st, {}


def _users_file(srv):
    return Path(srv.stage_dir) / "users.json"


def _state_hash(srv):
    """🧷 بصمة **الحقول الثابتة** من الحسابات ⭐.

    📌 ليه الحقول الثابتة ⭐: جلسة الدخول بتحدّث توكنات داخلية ⭐
    📌 (token_epoch · session_seen ⭐) ⇒ البصمة الكاملة بتتغيّر ⭐
    📌 من غير سبب ⭐ ⇒ المقارنة لازم تكون على البيانات نفسها ⭐.
    """
    import hashlib
    try:
        users = json.loads(_users_file(srv).read_text(encoding="utf-8"))
    except Exception:
        return ""
    stable = {}
    for uid, rec in (users or {}).items():
        stable[str(uid)] = [rec.get("email"), rec.get("plan"),
                            rec.get("id"), rec.get("name")]
    blob = json.dumps(stable, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════
#  ① تدرّج الأعطال ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_fault_graduated_injection_timeline():
    """① حقن متدرّج ⭐ ⇒ الخدمة بتتصرّف صح ⭐ + خط زمني ⭐."""
    section("① حقن أعطال متدرّج + خط زمني")
    stage = "/tmp/octa_r25_fault_main"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("main", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    state_before = _state_hash(srv)
    timeline = []

    # ⛔ الحالة الطبيعية ⭐
    _fault(c, "ipo_cache", "clear")
    _fault(c, "source_mode", "ok")
    st, _h, b, ms = c.get("/api/ipo")
    timeline.append({"stage": "طبيعي", "status": st, "ms": round(ms, 2),
                     "at": round(time.time(), 3)})
    ok(st == 200, "①a الحالة الطبيعية: المسار بيرد 200 ⭐", st)

    # ⛔ درجات العطل ⭐
    for mode, name in GRADES:
        _fault(c, "ipo_cache", "clear")
        st_f, _fj = _fault(c, "source_mode", mode)
        ok(st_f == 200, "①x حقن «%s» اتقبل ⭐" % name, st_f)
        st, _h, b, ms = c.get("/api/ipo")
        timeline.append({"stage": name, "status": st, "ms": round(ms, 2),
                         "at": round(time.time(), 3)})
        print("   %-14s → %s (%0.1fms) ⭐" % (name, st, ms), flush=True)
        ok(st == 503,
           "①b «%s»: المسار رجّع 503 صريح ⭐ (مش نجاح كاذب ⭐)" % name, st)
        try:
            j = json.loads(b.decode("utf-8"))
        except Exception:
            j = {}
        ok(not isinstance(j, list),
           "①c «%s»: مافيش قائمة مخترعة ⭐" % name, str(j)[:80])
        # ⛔ مصدر مستقل ⭐ لازم يفضل شغّال ⭐
        st2, _h2, _b2, _ms2 = c.get("/api/health", auth=False)
        ok(st2 == 200,
           "①d «%s»: مصدر/مسار مستقل فضل شغّال ⭐" % name, st2)

    # ⛔ عودة المصدر ⭐
    _fault(c, "ipo_cache", "clear")
    t_recover = time.perf_counter()
    _fault(c, "source_mode", "ok")
    st, _h, b, ms = c.get("/api/ipo")
    recovery_ms = (time.perf_counter() - t_recover) * 1000.0
    timeline.append({"stage": "عودة المصدر", "status": st,
                     "ms": round(ms, 2), "recovery_ms": round(recovery_ms, 2),
                     "at": round(time.time(), 3)})
    print("   عودة المصدر → %s (%0.1fms · تعافي %0.1fms) ⭐"
          % (st, ms, recovery_ms), flush=True)
    ok(st == 200, "①e بعد عودة المصدر: المسار رجّع 200 ⭐", st)
    try:
        j = json.loads(b.decode("utf-8"))
    except Exception:
        j = {}
    ok(isinstance(j, list) and bool(j),
       "①f بعد العودة: رجعت قائمة حقيقية من المصدر ⭐", str(j)[:120])
    ok(recovery_ms >= 0, "①g زمن التعافي اتقاس ⭐", round(recovery_ms, 2))

    # ⛔ الحالة الصحيحة ما اتمسحتش ⭐
    state_after = _state_hash(srv)
    ok(state_before == state_after,
       "①h الحالة الصحيحة (الحسابات) ما اتمسحتش أثناء الأعطال ⭐",
       "%s → %s" % (state_before[:12], state_after[:12]))
    REPORT["timeline"] = timeline
    REPORT["recovery_ms"] = round(recovery_ms, 2)
    REPORT["state_kept"] = state_before == state_after
    return timeline


# ══════════════════════════════════════════════════════════════════
#  ② الكاش: مفيش downtime ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_fault_cached_state_survives_source_failure():
    """② المصدر وقع بعد نجاح ⇒ الخدمة بترجّع آخر حالة صحيحة ⭐."""
    section("② الكاش — مافيش downtime و مافيش بيانات مخترعة")
    stage = "/tmp/octa_r25_fault_cache"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("cache", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    _fault(c, "ipo_cache", "clear")
    _fault(c, "source_mode", "ok")
    st, _h, b, ms = c.get("/api/ipo")
    ok(st == 200, "②a جلب أول ⭐", st)
    try:
        first = json.loads(b.decode("utf-8"))
    except Exception:
        first = []

    # ⛔ المصدر يقع ⭐ (والكاش لسه موجود ⭐)
    _fault(c, "source_mode", "http_500")
    st, _h, b, ms = c.get("/api/ipo")
    try:
        second = json.loads(b.decode("utf-8"))
    except Exception:
        second = {}
    print("   بعد سقوط المصدر: %s (%0.1fms) ⭐" % (st, ms), flush=True)
    ok(st == 200,
       "②b المصدر وقع ⇒ الخدمة رجّعت آخر حالة صحيحة ⭐ (مافيش downtime ⭐)",
       st)
    ok(second == first,
       "②c آخر حالة سليمة (مش مخترعة ⭐) ⭐",
       "مقارنة: %s" % (second == first))
    REPORT["cache"] = {"first_n": len(first) if isinstance(first, list) else 0,
                       "second_status": st}
    return second


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐
# ══════════════════════════════════════════════════════════════════
def _storage_guard_failures(srv, c, tag):
    """⛔ فحص واحد للحماية ⭐ — نفس الفحص في كل الحالات ⭐.

    ⛔ الفحص ⭐: لو ملف الحسابات تالف ⭐
       ⇒ (①) التطبيق **يرفض** الكتابة فوقه ⭐
       ⇒ (②) مافيش «نجاح كاذب» ⭐
       ⇒ (③) الملف ما يتغيرش ⭐
    """
    fails = []
    uf = _users_file(srv)
    good = uf.read_bytes()
    corrupt = b"{ this is not json"
    # ⛔ عنوان IP مختلف ⭐ ⇒ سلة حدود الطلبات منفصلة ⭐
    reg = iso.Client(srv.base_url, srv.proxy_secret,
                     client_ip="198.51.100.%d" % (150 + (len(tag) % 40)))
    try:
        uf.write_bytes(corrupt)
        st, _h, b, _ms = reg.post("/api/auth/register", {
            "name": "اختبار", "key": "482913",
            "email": "guard%s@example.test" % tag})
        after = uf.read_bytes()
        if st < 400:
            fails.append("%s: التسجيل نجح فوق ملف تالف ⭐ (نجاح كاذب ⭐) (%s)"
                         % (tag, st))
        if after != corrupt:
            fails.append("%s: الملف اتكتب فوقه ⭐ (فقد البيانات ⭐)" % tag)
    finally:
        reg.close()
        uf.write_bytes(good)
    return fails


@_case
def test_fault_negative_proof_storage_guard_removed():
    """🧨 شيل حماية «مافيش كتابة فوق ملف تالف» ⭐ ⇒ نفس الفحص يفشل ⭐."""
    section("🧨 البرهان السالب — تعطيل حماية تخزين الحسابات")
    stage = "/tmp/octa_r25_fault_neg"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("neg", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    fails_on = _storage_guard_failures(srv, c, "on")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: التطبيق رفض الكتابة فوق ملف تالف ⭐", fails_on)

    st, _h, _b, _ms = c.post("/__harness__/fault",
                             {"kind": "storage_guard_off", "value": "off"})
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off = _storage_guard_failures(srv, c, "off")
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))

    c.post("/__harness__/fault", {"kind": "storage_guard_off", "value": "on"})
    fails_back = _storage_guard_failures(srv, c, "back")
    ok(len(fails_back) == 0,
       "🧨d بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    REPORT["negative_storage"] = {"before": len(fails_off),
                                  "after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


def main():
    print("=" * 70)
    print("  💥 R25 · حقن أعطال متدرّج + خط زمني للتعافي")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_fault_graduated_injection_timeline()
    test_fault_cached_state_survives_source_failure()
    test_fault_negative_proof_storage_guard_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 الخط الزمني الحقيقي لعودة المصدر:")
    for rec in REPORT.get("timeline", []):
        print("     %-16s status=%s · %8.2fms ⭐"
              % (rec.get("stage"), rec.get("status"), rec.get("ms") or 0.0))
    if REPORT.get("recovery_ms") is not None:
        print("     زمن التعافي بعد عودة المصدر: %.2fms ⭐"
              % REPORT["recovery_ms"])
    neg = REPORT.get("negative_storage")
    if neg:
        print("     البرهان السالب: الإخفاقات قبل=%d · بعد=%d ⭐"
              % (neg["before"], neg["after"]))
    print("=" * 70)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)"
          % (passed, failed, len(RESULTS)))
    if failed:
        for cond, label in RESULTS:
            if not cond:
                print("   ❌ " + label)
        return 1
    print("  RESULT: CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
