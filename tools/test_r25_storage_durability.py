#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💾 الجولة ٢٥ (R25 · المرحلة ٩) — التخزين الدائم + النسخ والاسترجاع + الكتابة الذرّية

📌 البند المستهدف ⭐:
   **AC-10-1/2** ⭐ + **AC-11-4** ⭐ (الحالات fresh/stale/unavailable ⭐)
   + **AC-13-1/2** ⭐ (فشل المصدر ⭐)

📌 الأجزاء المقيسة ⭐:
   ① **تخزين دائم** ⭐ — الحالة بتفضل بعد إعادة تشغيل السيرفر ⭐.
   ② **نسخ احتياطي + استرجاع** ⭐ (رحلة كاملة ⭐) ⭐
      — بنستخدم أداة المشروع نفسها ⭐ (`tools/backup_data.py` ⭐) ⭐
      ⇒ الدليل مستقل ⭐ مش lógica جديدة ⭐.
   ③ **كتابة ذرّية** ⭐ — الملف مايتقريش نصّه ⭐ أبداً ⭐.
   ④ **بيانات قديمة** ⭐ ⇒ ما تتوصفش «حديثة» ⭐.
   ⑤ **بيانات ناقصة** ⭐ ⇒ readiness بيفشل ⭐.
   ⑥ **فشل المصدر** ⭐ ⇒ تدهور صريح ⭐ (مش نجاح كاذب ⭐) + تعافي ⭐.

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ كل الملفات في مجلد مؤقّت ⭐ · مافيش أي ملف إنتاجي اتمس ⭐
   ⛔ مافيش شبكة ⭐ · مافيش سر إنتاج ⭐ · مافيش نشر ⭐

📌 التشغيل: python3 tools/test_r25_storage_durability.py
   📌 وكل ملف اختبار كمان بيشتغل تحت `pytest` ⭐.
"""
import atexit
import functools
import json
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "staging"))
sys.path.insert(0, str(HERE))

import backup_data  # noqa: E402  (أداة المشروع الأصلية ⭐)
import iso_env as iso  # noqa: E402

# ⛔ ساعة القاهرة الصناعية ⭐ — الأربعاء ١١:٠٠ ⇒ السوق مفتوح ⭐
import datetime as _dt  # noqa: E402
CAIRO_OPEN = _dt.datetime(2026, 11, 18, 8, 0,
                           tzinfo=_dt.timezone.utc).timestamp()

_CLEANUP = []
RESULTS = []
REPORT = {}

WRITE_THREADS = 6
WRITE_EACH = 4


def _launch(tag, stage_dir=None, **kw):
    stage = Path(stage_dir or ("/tmp/octa_r25_store_%s" % tag))
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


def _client(srv, ip="198.51.100.10"):
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip=ip)
    cfg = iso.read_stage_cfg(srv.stage_dir)
    tok, st, j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s · %s)"
                           % (st, str(j)[:120]))
    return c


def _j(body):
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _fault(c, kind, value):
    st, _h, b, _ms = c.post("/__harness__/fault",
                            {"kind": kind, "value": value})
    return st, _j(b)


def _sha_map(root):
    """🔐 بصمة كل ملف ⭐ (مقارنة الحالة المرجعية ⭐)."""
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = backup_data.sha256_file(p)
    return out


# ══════════════════════════════════════════════════════════════════
#  ① تخزين دائم ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_durable_storage_survives_restart():
    """① الحالة بتفضل بعد إعادة تشغيل السيرفر ⭐."""
    section("① التخزين الدائم — الحالة بعد إعادة التشغيل")
    stage = "/tmp/octa_r25_store_restart"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("restart", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    # ⛔ حساب **جديد** ⭐ (مش الحساب الوهمي ⭐)
    # 📌 السبب ⭐: أداة الـstaging بتعيد بذر الحسابات الوهمية ⭐
    # 📌 عند كل إقلاع ⭐ ⇒ لو استخدمناه ⭐ كانت محفظته هتتمسح ⭐
    # 📌 وده سلوك أداة الاختبار ⭐ مش سلوك التطبيق ⭐.
    reg = iso.Client(srv.base_url, srv.proxy_secret,
                     client_ip="198.51.100.44")
    st, _h, b, _ms = reg.post("/api/auth/register", {
        "name": "تخزين", "key": "482913", "email": "durable@example.test"})
    tok = _j(b).get("token")
    ok(st == 200 and bool(tok),
       "①a اتسجّل حساب جديد ⭐", st)
    c.token = tok

    st, _h, b, _ms = c.post("/api/portfolio", {
        "action": "add", "code": "DURA", "shares": 7,
        "cost": 11.0, "price": 13.0, "sector": "اختبار"})
    ok(st == 200, "①a2 الكتابة نجحت ⭐", st)
    time.sleep(1.0)
    users_file = Path(srv.stage_dir) / "users.json"
    before = _sha_map(srv.stage_dir)

    # ⛔ إعادة تشغيل حقيقية ⭐ على نفس المجلد ⭐
    new, ready, elapsed = iso.restart(srv, timeout=240)
    ok(ready, "①b السيرفر قام تاني ⭐", round(elapsed, 2))
    c2 = iso.Client(new.base_url, new.proxy_secret, client_ip="198.51.100.44")
    c2.token = tok
    st, _h, b, _ms = c2.get("/api/portfolio")
    pf = _j(b)
    holdings = (pf.get("holdings") or {})
    ok("DURA" in holdings,
       "①c السهم اتحفظ وفضل موجود بعد إعادة التشغيل ⭐", list(holdings))
    after = _sha_map(srv.stage_dir)
    common = set(before) & set(after)
    diff = sorted(k for k in common if before[k] != after[k])
    ok("users.json" in diff,
       "①d ملف الحسابات اتغيّر (التوكن الجديد ⭐) ⭐", diff[:5])
    ok("users.bak" in after,
       "①e نسخة احتياطية موجودة ⭐", list(after)[:6])
    REPORT["restart"] = {"ready_seconds": round(elapsed, 2),
                         "changed": diff[:5]}
    return new


# ══════════════════════════════════════════════════════════════════
#  ② نسخ احتياطي + استرجاع ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_backup_restore_round_trip():
    """② رحلة نسخ ⇒ تعديل ⇒ استرجاع ⇒ مطابقة ⭐."""
    section("② النسخ الاحتياطي والاسترجاع — رحلة كاملة")
    stage = "/tmp/octa_r25_store_backup"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("backup", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    c.post("/api/portfolio", {"action": "add", "code": "BACK",
                              "shares": 3, "cost": 5.0, "price": 6.0})
    time.sleep(1.0)

    src = Path(srv.stage_dir)
    seed = Path("/tmp/octa_r25_store_seed")
    shutil.rmtree(seed, ignore_errors=True)
    shutil.copytree(src, seed)
    before = _sha_map(seed)
    ok(len(before) > 0, "②a فيه ملفات للنسخ ⭐", len(before))

    archive, mpath, manifest = backup_data.do_backup(seed, Path("/tmp/octa_r25_store_arch"))
    ok(archive.exists(), "②b اتعملت نسخة ⭐", archive.name)
    ok(manifest["count"] == len(before),
       "②c عدد ملفات النسخة مطابق ⭐",
       "%s vs %s" % (manifest["count"], len(before)))

    problems, _m = backup_data.do_verify(archive)
    ok(not problems, "②d فحص النسخة: سليم ⭐", problems[:3])

    # ⛔ تعديل متعمّد ⭐
    victim = seed / "users.json"
    victim.write_text('{"__mutated__": true}\n', encoding="utf-8")
    ok(victim.read_text(encoding="utf-8").find("__mutated__") >= 0,
       "②e التعديل المتعمّد اتعمل ⭐")

    # ⛔ استرجاع ⭐
    dst = Path("/tmp/octa_r25_store_restored")
    shutil.rmtree(dst, ignore_errors=True)
    backup_data.do_restore(archive, dst, force=True)
    after = _sha_map(dst)
    missing = sorted(set(before) - set(after))
    extra = sorted(set(after) - set(before))
    diff = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    ok(not missing, "②f مافيش ملف ناقص بعد الاسترجاع ⭐", missing[:5])
    ok(not extra, "②g مافيش ملف زيادة ⭐", extra[:5])
    ok(not diff, "②h كل البصمات مطابقة ⭐", diff[:5])
    REPORT["backup"] = {"files": len(before), "archive_bytes": archive.stat().st_size}
    return after


# ══════════════════════════════════════════════════════════════════
#  ③ الكتابة الذرّية ⭐
# ══════════════════════════════════════════════════════════════════
def _atomicity_failures(srv, codes, tag):
    """⛔ فحص واحد ⭐ — نفس الفحص في كل الحالات ⭐."""
    fails = []
    reads = {"n": 0, "bad": 0}
    stop = threading.Event()
    errors = []
    lock = threading.Lock()
    users_file = Path(srv.stage_dir) / "users.json"

    def reader():
        while not stop.is_set():
            try:
                raw = users_file.read_bytes()
            except Exception:
                raw = b""
            reads["n"] += 1
            try:
                json.loads(raw.decode("utf-8"))
            except Exception:
                reads["bad"] += 1
            time.sleep(0.001)

    def writer(idx):
        cc = iso.Client(srv.base_url, srv.proxy_secret,
                        client_ip="198.51.100.%d" % (120 + idx))
        cc.token = TOKEN["tok"]
        for j in range(WRITE_EACH):
            code = codes[idx * WRITE_EACH + j]
            try:
                st, _h, _b, _ms = cc.post("/api/portfolio", {
                    "action": "add", "code": code, "shares": 1 + j,
                    "cost": 7.0 + j, "price": 9.0 + j, "sector": "اختبار"})
                if st >= 400:
                    with lock:
                        errors.append("%s: %s" % (code, st))
            except Exception as exc:
                with lock:
                    errors.append("%s: %s" % (code, type(exc).__name__))
        cc.close()

    rt = threading.Thread(target=reader)
    rt.start()
    threads = [threading.Thread(target=writer, args=(i,))
               for i in range(WRITE_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)
    stop.set()
    rt.join(timeout=30)

    if errors:
        fails.append("%s: %d كتابة فشلت ⭐" % (tag, len(errors)))
    if reads["bad"] > 0:
        fails.append("%s: الملف اتقري ناقص %d مرة من %d ⭐"
                     % (tag, reads["bad"], reads["n"]))
    tmp = Path(srv.stage_dir) / "users.tmp"
    if tmp.exists():
        fails.append("%s: ملف مؤقّت معلّق (users.tmp) ⭐" % tag)
    return fails, reads


TOKEN = {"tok": None}


@_case
def test_atomic_write_never_leaves_partial_file():
    """③ الكتابة الذرّية ⭐ — الملف مايتقريش نصّه ⭐."""
    section("③ الكتابة الذرّية")
    stage = "/tmp/octa_r25_store_atomic"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("atomic", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    TOKEN["tok"] = c.token
    st, _h, b, _ms = c.get("/api/data_full")
    stocks = (_j(b).get("stocks") or {})
    codes = sorted(stocks.keys())[:WRITE_THREADS * WRITE_EACH]
    ok(len(codes) >= WRITE_THREADS * WRITE_EACH,
       "③a اتجمعت الأكواد ⭐", len(codes))

    fails, reads = _atomicity_failures(srv, codes, "مع الحماية")
    ok(not fails, "③b الملف ما اتلخبطش أبداً ⭐", fails)
    ok(reads["n"] > 0, "③c القارئ المتزامن قرأ الملف ⭐", reads)
    bak = Path(srv.stage_dir) / "users.bak"
    ok(bak.exists(), "③d فيه نسخة احتياطية (.bak) ⭐", bak.name)
    REPORT["atomic"] = {"reads": reads["n"], "bad": reads["bad"]}
    return reads


# ══════════════════════════════════════════════════════════════════
#  ④ بيانات قديمة ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_stale_data_is_never_claimed_fresh():
    """④ بيانات قديمة ⭐ ⇒ المسارات ما تقولش «fresh» ⭐."""
    section("④ بيانات قديمة — مافيش ادعاء «حديث»")
    stage = "/tmp/octa_r25_store_stale"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("stale", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    for _ in range(60):
        st, _h, b, _ms = c.get("/__harness__/opp")
        if _j(b).get("captured"):
            break
        time.sleep(0.5)
    # ⛔ وقت القاهرة المحقون ⭐ ⇒ حالة السوق «open» ⭐
    # 📌 ⇒ حدّ الحداثة وقت السوق (900 ثانية ⭐) ⭐
    # 📌 ⇒ ساعة كاملة ⭐ = stale ⭐ متيقن ⭐
    st, _h, b, _ms = c.post("/__harness__/clock", {
        "offset": 0, "cairo_epoch": CAIRO_OPEN})
    ok(st == 200, "④a0 الساعة اتحقنت ⭐", st)
    st, _h, b, _ms = c.post("/__harness__/opp", {"age_seconds": 3600})
    ok(st == 200, "④a اتبذرت نسخة قديمة (ساعة ⭐) ⭐", st)
    st, _h, b, _ms = c.get("/api/opp/summary")
    j = _j(b)
    print("   freshness=%s age=%s ⭐" % (j.get("freshness"),
                                         j.get("age_seconds")), flush=True)
    ok(str(j.get("freshness")) in ("stale", "fresh"),
       "④b المسار بيبلّغ حالة الحداثة ⭐", j.get("freshness"))
    ok(int(j.get("age_seconds") or 0) >= 3600,
       "④c عمر البيانات معلن صح ⭐", j.get("age_seconds"))
    # ⛔ الحدّ وقت السوق = 900 ثانية ⭐ ⇒ ساعة ⇒ stale ⭐
    ok(str(j.get("freshness")) == "stale",
       "④d بعد ساعة: الحالة «stale» ⭐ (مش «fresh» ⭐)", j.get("freshness"))
    REPORT["stale"] = {"freshness": j.get("freshness"),
                        "age": j.get("age_seconds")}
    return j


# ══════════════════════════════════════════════════════════════════
#  ⑤ بيانات ناقصة ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_missing_data_handling():
    """⑤ بيانات ناقصة ⭐ ⇒ readiness بيفشل ⭐ والرد العام نظيف ⭐."""
    section("⑤ بيانات ناقصة — readiness بيفشل")
    stage = "/tmp/octa_r25_store_missing"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("missing", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    st, _h, b, _ms = c.get("/api/ready", auth=False)
    ok(st == 200, "⑤a قبل التعطيل: readiness 200 ⭐", st)
    st, _fj = _fault(c, "data", "unavailable")
    ok(st == 200, "⑤b العطل اتحقن ⭐", st)
    st, _h, b, _ms = c.get("/api/ready", auth=False)
    r = _j(b)
    ok(st == 503, "⑤c بيانات ناقصة ⇒ readiness 503 ⭐", st)
    ok((r.get("checks") or {}).get("data") is False,
       "⑤d فحص البيانات بيقول «مش متاح» ⭐", r.get("checks"))
    st, _h, b, _ms = c.get("/api/health", auth=False)
    ok(st == 200, "⑤e liveness فضل 200 ⭐", st)
    ok(len(b) < 1024, "⑤f الرد العام بيفضل خفيف ⭐", len(b))
    _fault(c, "data", "restore")
    st, _h, b, _ms = c.get("/api/ready", auth=False)
    ok(st == 200, "⑤g بعد رجوع البيانات: readiness 200 ⭐", st)
    return r


# ══════════════════════════════════════════════════════════════════
#  ⑥ فشل المصدر ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_data_source_failure_handling():
    """⑥ فشل المصدر ⭐ ⇒ تدهور صريح ⭐ + تعافي ⭐."""
    section("⑥ فشل المصدر — تدهور صريح ثم تعافي")
    stage = "/tmp/octa_r25_store_source"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("source", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    _fault(c, "ipo_cache", "clear")
    _fault(c, "source_mode", "ok")
    st, _h, b, _ms = c.get("/api/ipo")
    ok(st == 200, "⑥a قبل العطل: المسار شغّال ⭐", st)

    _fault(c, "ipo_cache", "clear")
    _fault(c, "source_mode", "timeout")
    st, _h, b, ms = c.get("/api/ipo")
    ok(st == 503, "⑥b فشل المصدر ⇒ 503 صريح ⭐", st)
    j = _j(b)
    ok(j.get("error") == "unavailable",
       "⑥c السبب معلن بصراحة ⭐", j)
    ok(not isinstance(j, list),
       "⑥d مافيش بيانات مخترعة ⭐", str(j)[:80])

    _fault(c, "ipo_cache", "clear")
    t0 = time.perf_counter()
    _fault(c, "source_mode", "ok")
    st, _h, b, ms = c.get("/api/ipo")
    recov = (time.perf_counter() - t0) * 1000.0
    ok(st == 200, "⑥e بعد رجوع المصدر: 200 ⭐", st)
    print("   زمن التعافي: %.2fms ⭐" % recov, flush=True)
    REPORT["source"] = {"recovery_ms": round(recov, 2)}
    return st


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_storage_negative_proof_atomic_write_removed():
    """🧨 شيل الكتابة الذرّية ⇒ الملف بيتقري ناقص ⭐."""
    section("🧨 البرهان السالب — تعطيل الكتابة الذرّية")
    stage = "/tmp/octa_r25_store_neg"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("neg", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    TOKEN["tok"] = c.token
    st, _h, b, _ms = c.get("/api/data_full")
    stocks = (_j(b).get("stocks") or {})
    codes = sorted(stocks.keys())[:WRITE_THREADS * WRITE_EACH]

    fails_on, reads_on = _atomicity_failures(srv, codes, "مع الحماية")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: الفحص بيعدّي ⭐ (0 إخفاقات ⭐)", fails_on)

    st, _fj = _fault(c, "atomic_off", "off")
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off, reads_off = _atomicity_failures(srv, codes, "بدون حماية")
    print("   مع الحماية: قراءات=%d تالفة=%d ⭐"
          % (reads_on["n"], reads_on["bad"]), flush=True)
    print("   بدونها: قراءات=%d تالفة=%d ⭐"
          % (reads_off["n"], reads_off["bad"]), flush=True)
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))

    _fault(c, "atomic_off", "on")
    fails_back, _reads_back = _atomicity_failures(srv, codes, "رجوع")
    ok(len(fails_back) == 0,
       "🧨d بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    REPORT["negative_atomic"] = {"before": len(fails_off),
                                  "after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


def main():
    print("=" * 70)
    print("  💾 R25 · تخزين دائم + نسخ/استرجاع + كتابة ذرّية")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_durable_storage_survives_restart()
    test_backup_restore_round_trip()
    test_atomic_write_never_leaves_partial_file()
    test_stale_data_is_never_claimed_fresh()
    test_missing_data_handling()
    test_data_source_failure_handling()
    test_storage_negative_proof_atomic_write_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 نتائج التخزين (قياسات حقيقية):")
    rst = REPORT.get("restart")
    if rst:
        print("     %-30s إعادة التشغيل في %.2fs ⭐"
              % ("التخزين الدائم", rst["ready_seconds"]))
    bk = REPORT.get("backup")
    if bk:
        print("     %-30s %d ملف · أرشيف %d بايت ⭐"
              % ("النسخ والاسترجاع", bk["files"], bk["archive_bytes"]))
    at = REPORT.get("atomic")
    if at:
        print("     %-30s قراءات=%d · تالفة=%d ⭐"
              % ("الكتابة الذرّية", at["reads"], at["bad"]))
    stl = REPORT.get("stale")
    if stl:
        print("     %-30s freshness=%s · age=%s ⭐"
              % ("بيانات قديمة", stl["freshness"], stl["age"]))
    src = REPORT.get("source")
    if src:
        print("     %-30s تعافي %.2fms ⭐"
              % ("فشل المصدر", src["recovery_ms"]))
    neg = REPORT.get("negative_atomic")
    if neg:
        print("     %-30s الإخفاقات قبل=%d · بعد=%d ⭐"
              % ("البرهان السالب", neg["before"], neg["after"]))
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
