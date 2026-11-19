#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⏱️ الجولة ٢٥ (R25 · المرحلة ٩) — ساعة صناعية محقونة عبر المسارات الخمسة

📌 بند القبول المستهدف ⭐:
   **AC-11-3** ⭐: «ساعة صناعية عبر المسارات الخمسة ثم توقف التحديث؛
   طابق الصف مع حالة الدفعة» ⭐

📌 الفكرة ⭐:
   · الحقن هنا **في الوقت** ⭐ (مش في الكود ⭐) ⭐:
     ساعة النظام بتتحقن ⭐ + وقت القاهرة بيتحقن ⭐ (فحالة السوق بتتحكم ⭐).
   · المسارات الخمسة ⭐ هي اللي بتنشر **عقد الحداثة/التغطية** ⭐
     (نفس الحقول · نفس الدلالات ⭐) ⭐:
       `/api/opp/summary` · `/api/opp/strategies` · `/api/opp/list/<key>` ·
       `/api/opp/detail/<key>/<code>` · `/api/opp/explain/<key>/<code>` ⭐
   · المرجع الوحيد للحقيقة ⭐ = **منطق إعادة التقييم وقت الرد** ⭐
     (`opp_engine.revalidate_payload` ⭐) ⭐ — مافيش حساب ولا تقدير ⭐.

📌 ليش الساعة مهمة ⭐:
   لو التحديث وقف ⭐ ⇒ النسخة المخزّنة لو فضلت تقول «fresh» ⭐
   ⇒ ادعاء كاذب للمستخدم ⭐. الساعة الصناعية بتثبت إن الاعتماد
   بيحصل **وقت الرد** ⭐ مش وقت الإنشاء ⭐.

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ سيرفر staging معزول ⭐ في مجلد مؤقّت ⭐
   ⛔ مافيش أي اتصال خارجي ⭐ · مافيش أي سر إنتاج ⭐ · مافيش نشر ⭐

📌 التشغيل: python3 tools/test_r25_clock_routes.py
   📌 وكل ملف اختبار كمان بيشتغل تحت `pytest` ⭐.
"""
import atexit
import functools
import datetime as dt
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "staging"))

import iso_env as iso  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  ⏱️ المسارات الخمسة ⭐
# ══════════════════════════════════════════════════════════════════
FIVE_ROUTES = [
    "/api/opp/summary",
    "/api/opp/strategies",
    "/api/opp/list/{key}",
    "/api/opp/detail/{key}/{code}",
    "/api/opp/explain/{key}/{code}",
]

# ⛔ ساعة القاهرة الصناعية ⭐ — الأربعاء ١١:٠٠ ⇒ السوق مفتوح ⭐
# 📌 (٣٠٠ ثواني حدّ الحداثة وقت السوق ⭐ ⇒ ساعة واحدة بتكفي للاختبار ⭐)
CAIRO_OPEN = dt.datetime(2026, 11, 18, 8, 0, tzinfo=dt.timezone.utc).timestamp()
ONE_HOUR = 3600

_SERVERS = {}
_CLEANUP = []
RESULTS = []


def _launch(name, **kw):
    if name in _SERVERS:
        return _SERVERS[name]
    stage = Path("/tmp/octa_r25_clock_%s" % name)
    srv = iso.launch(stage_dir=str(stage), **kw)
    ok, elapsed = srv.wait_ready(timeout=240)
    if not ok:
        tail = "\n".join(srv.log_tail(30))
        srv.stop()
        raise RuntimeError("السيرفر المعزول ماقومش:\n" + tail)
    _SERVERS[name] = srv
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
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip="198.51.100.40")
    cfg = iso.read_stage_cfg(srv.stage_dir)
    tok, st, _j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s)" % st)
    return c


def _wait_capture(c, timeout=60):
    """⏳ مستني أول نسخة حقيقية من محرّك الفرص ⭐."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        st, _h, b, _ms = c.get("/__harness__/opp")
        try:
            j = json.loads(b.decode("utf-8"))
        except Exception:
            j = {}
        if j.get("captured"):
            return j
        time.sleep(0.5)
    return {}


def _discover_pair(c):
    """🔎 بيدوّر على (استراتيجية · كود) حقيقيين ⭐."""
    st, _h, b, _ms = c.get("/__harness__/opp")
    try:
        keys = json.loads(b.decode("utf-8")).get("lists") or []
    except Exception:
        keys = []
    for key in keys:
        st, _h, b, _ms = c.get("/api/opp/list/%s" % key)
        try:
            j = json.loads(b.decode("utf-8"))
        except Exception:
            continue
        for item in (j.get("items") or []):
            code = str(item.get("code") or "").strip()
            if code:
                return key, code
    return (keys[0] if keys else "value"), ""


def _clock(c, offset, cairo_epoch=CAIRO_OPEN):
    st, _h, b, _ms = c.post("/__harness__/clock",
                            {"offset": offset, "cairo_epoch": cairo_epoch})
    try:
        return st, json.loads(b.decode("utf-8"))
    except Exception:
        return st, {}


def _seed(c, age_seconds):
    st, _h, b, _ms = c.post("/__harness__/opp", {"age_seconds": age_seconds})
    try:
        return st, json.loads(b.decode("utf-8"))
    except Exception:
        return st, {}


def _routes_state(c, key, code):
    """📖 حالة المسارات الخمسة ⭐ (من ردود التطبيق الحقيقية ⭐)."""
    out = {}
    for tmpl in FIVE_ROUTES:
        path = tmpl.replace("{key}", key).replace("{code}", code or "XXXX")
        st, _h, b, _ms = c.get(path)
        try:
            j = json.loads(b.decode("utf-8"))
        except Exception:
            j = {}
        out[tmpl] = {"path": path, "status": st, "body": j}
    return out


# ══════════════════════════════════════════════════════════════════
#  ⛔ فحص الحماية ⭐ — بيتنفّذ في كل الحالات ⭐
# ══════════════════════════════════════════════════════════════════
def _freshness_failures(states, expect_state, expect_age, label, tol=0):
    """⛔ بيرجّع قائمة الإخفاقات ⭐ — نفس الفحص في كل الحالات ⭐."""
    fails = []
    for tmpl, rec in states.items():
        j = rec["body"]
        if rec["status"] != 200:
            fails.append("%s: الحالة %s بدل 200 ⭐ (%s)"
                         % (label, rec["status"], tmpl))
            continue
        if str(j.get("freshness")) != expect_state:
            fails.append("%s: %sfreshness=%s بدل %s ⭐"
                         % (label, tmpl, j.get("freshness"), expect_state))
        age = j.get("age_seconds")
        if age is not None and abs(int(age) - int(expect_age)) > int(tol):
            fails.append("%s: %sage_seconds=%s بدل %s ⭐"
                         % (label, tmpl, age, expect_age))
    return fails


# ══════════════════════════════════════════════════════════════════
#  ① الساعة الصناعية ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_clock_injected_hour_across_five_routes():
    """① ساعة صناعية + ساعة ⇒ المسارات الخمسة بتبلّغ الحالة الصح ⭐."""
    section("① ساعة صناعية محقونة عبر المسارات الخمسة")
    srv = _launch("main", source_mode="ok")
    c = _client(srv)
    cap = _wait_capture(c)
    ok(bool(cap.get("captured")),
       "①a اتقفلت نسخة حقيقية من محرّك الفرص ⭐", cap)
    ok(len(cap.get("lists") or []) >= 1,
       "①b النسخة فيها استراتيجيات ⭐", cap.get("lists"))

    st, clk = _clock(c, 0)
    ok(st == 200, "①c الساعة اتحقنت ⭐", st)
    phase = str((clk or {}).get("market_phase"))
    ok(phase == "open",
       "①d وقت القاهرة المحقون ⇒ حالة السوق «open» ⭐", phase)
    limits = (clk or {}).get("fresh_limits") or {}
    ok(int(limits.get("open") or 0) == 900,
       "①e حدّ الحداثة وقت السوق اتقاس من التطبيق (900 ثانية) ⭐", limits)

    key, code = _discover_pair(c)
    ok(bool(code), "①f اتلقى كود حقيقي في القوائم ⭐", "%s/%s" % (key, code))

    st, seed = _seed(c, 0)
    ok(st == 200 and seed.get("freshness") == "fresh",
       "①g اتبذرت نسخة حديثة (age=0) ⭐", seed.get("freshness"))

    states0 = _routes_state(c, key, code)
    fails0 = _freshness_failures(states0, "fresh", 0, "T0")
    ok(not fails0, "①h المسارات الخمسة بتقول «fresh» وage=0 ⭐", fails0)

    # ⛔ ساعة صناعية ⭐ — ساعة واحدة ⭐
    st, _b = _clock(c, ONE_HOUR)
    ok(st == 200, "①i اتقدّمت الساعة ساعة ⭐", st)
    states1 = _routes_state(c, key, code)
    fails1 = _freshness_failures(states1, "stale", ONE_HOUR, "T+1h")
    ok(not fails1,
       "①j بعد ساعة: المسارات الخمسة بتقول «stale» وage=3600 ⭐", fails1)
    _CLOCK["states0"] = states0
    _CLOCK["states1"] = states1
    _CLOCK["key"] = key
    _CLOCK["code"] = code
    return states1


# ══════════════════════════════════════════════════════════════════
#  ② الصف يطابق حالة الدفعة ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_clock_row_matches_batch_state():
    """② صف السهم يطابق حالة الدفعة ⭐ (مش «حديث» و dissenting ⭐)."""
    section("② الصف يطابق حالة الدفعة")
    srv = _launch("main", source_mode="ok")
    c = _client(srv)
    _wait_capture(c)
    key = _CLOCK.get("key") or _discover_pair(c)[0]
    code = _CLOCK.get("code") or ""
    _clock(c, 0)
    st, seed = _seed(c, 0)
    states = _routes_state(c, key, code)

    lst = states["/api/opp/list/{key}"]["body"] or {}
    items = lst.get("items") or []
    ok(bool(items), "②a فيه صفوف في القائمة ⭐", len(items))
    row = items[0] if items else {}
    batch_state = str(lst.get("freshness") or "")
    ok(batch_state in ("fresh", "stale", "unavailable"),
       "②b حالة الدفعة معروفة ⭐", batch_state)
    row_state = str(row.get("data_state") or "")
    want_row = {"fresh": "live", "stale": "stale",
                "unavailable": "unavailable"}.get(batch_state, batch_state)
    ok(row_state == want_row,
       "②c حالة الصف (%s) = حالة الدفعة (%s ⇒ %s) ⭐"
       % (row_state, batch_state, want_row))

    # ⛔ بعد ساعة ⭐ ⇒ الصف لازم يتحوّل لـstale ⭐
    _clock(c, ONE_HOUR)
    states2 = _routes_state(c, key, code)
    lst2 = states2["/api/opp/list/{key}"]["body"] or {}
    items2 = lst2.get("items") or []
    row2 = items2[0] if items2 else {}
    batch2 = str(lst2.get("freshness") or "")
    ok(batch2 == "stale",
       "②d بعد ساعة: حالة الدفعة «stale» ⭐", batch2)
    want_row2 = {"fresh": "live", "stale": "stale",
                 "unavailable": "unavailable"}.get(batch2, batch2)
    ok(str(row2.get("data_state") or "") == want_row2,
       "②e بعد ساعة: حالة الصف (%s) = حالة الدفعة (%s ⇒ %s) ⭐"
       % (row2.get("data_state"), batch2, want_row2))
    ok(bool(row2.get("stale_reason")),
       "②f الصف القديم عليه سبب واضح ⭐", row2.get("stale_reason"))
    _CLOCK["row2"] = row2
    return row2


# ══════════════════════════════════════════════════════════════════
#  ③ توقف التحديث ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_clock_stopped_update_does_not_claim_fresh():
    """③ التحديث وقف ⇒ المسارات مفروض ما تقولش «fresh» ⭐."""
    section("③ توقف التحديث — مافيش ادعاء «حديث»")
    srv = _launch("main", source_mode="ok")
    c = _client(srv)
    _wait_capture(c)
    key = _CLOCK.get("key") or _discover_pair(c)[0]
    code = _CLOCK.get("code") or ""
    _clock(c, 0)
    st, seed = _seed(c, 0)
    _clock(c, ONE_HOUR)
    before = _routes_state(c, key, code)
    ts_before = str((before["/api/opp/summary"]["body"] or {})
                    .get("generated_at") or "")
    # ⛔ التحديث «وقف» ⭐ ⇒ ما فيش أي تحديث جديد ⭐
    time.sleep(2.0)
    after = _routes_state(c, key, code)
    ts_after = str((after["/api/opp/summary"]["body"] or {})
                   .get("generated_at") or "")
    ok(ts_before == ts_after,
       "③a النسخة لم تتجدد (توقّف التحديث) ⭐", "%s → %s" % (ts_before, ts_after))
    fails = _freshness_failures(after, "stale", ONE_HOUR, "مقفول", tol=60)
    ok(not fails,
       "③b بعد توقف التحديث: مافيش مسار بيقول «fresh» ⭐", fails)
    return after


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_clock_negative_proof_revalidation_removed():
    """🧨 شيل إعادة التقييم وقت الرد ⇒ نفس الفحص **يفشل** ⭐."""
    section("🧨 البرهان السالب — تعطيل إعادة التقييم وقت الرد")
    srv = _launch("main", source_mode="ok")
    c = _client(srv)
    _wait_capture(c)
    key = _CLOCK.get("key") or _discover_pair(c)[0]
    code = _CLOCK.get("code") or ""

    # ① مع الحماية ⭐
    _clock(c, 0)
    _seed(c, 0)
    _clock(c, ONE_HOUR)
    fails_on = _freshness_failures(_routes_state(c, key, code),
                                   "stale", ONE_HOUR, "مع الحماية")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: الفحص بيعدّي ⭐ (0 إخفاقات ⭐)", fails_on)

    # ② شيل الحماية ⭐
    st, _h, _b, _ms = c.post("/__harness__/fault",
                             {"kind": "revalidate", "value": "off"})
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off = _freshness_failures(_routes_state(c, key, code),
                                    "stale", ONE_HOUR, "بدون حماية")
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))

    # ③ رجّع الحماية ⭐
    c.post("/__harness__/fault", {"kind": "revalidate", "value": "on"})
    _clock(c, 0)
    _seed(c, 0)
    _clock(c, ONE_HOUR)
    fails_back = _freshness_failures(_routes_state(c, key, code),
                                     "stale", ONE_HOUR, "رجوع")
    ok(len(fails_back) == 0,
       "🧨d بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    _NEG["before"] = len(fails_off)
    _NEG["after"] = len(fails_on)
    return _NEG


_CLOCK = {}
_NEG = {}


def main():
    print("=" * 70)
    print("  ⏱️ R25 · ساعة صناعية محقونة عبر المسارات الخمسة")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_clock_injected_hour_across_five_routes()
    test_clock_row_matches_batch_state()
    test_clock_stopped_update_does_not_claim_fresh()
    test_clock_negative_proof_revalidation_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 نتائج الساعة الصناعية (قياسات حقيقية):")
    s0 = _CLOCK.get("states0") or {}
    s1 = _CLOCK.get("states1") or {}
    for tmpl in FIVE_ROUTES:
        a = (s0.get(tmpl) or {}).get("body") or {}
        b = (s1.get(tmpl) or {}).get("body") or {}
        print("     %-32s T0: %s (age=%s) · T+1h: %s (age=%s) ⭐"
              % (tmpl, a.get("freshness"), a.get("age_seconds"),
                 b.get("freshness"), b.get("age_seconds")))
    if _NEG:
        print("     البرهان السالب: الإخفاقات قبل=%d · بعد=%d ⭐"
              % (_NEG.get("before", 0), _NEG.get("after", 0)))
    print("=" * 70)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)" % (passed, failed, len(RESULTS)))
    if failed:
        for cond, label in RESULTS:
            if not cond:
                print("   ❌ " + label)
        return 1
    print("  RESULT: CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
