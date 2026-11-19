#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 الجولة ٢٥ (R25 · المرحلة ٩) — لوحة القياس + خطة التنبيه + حالات degraded

📌 بنود القبول المستهدفة ⭐:
   · **AC-34-3** ⭐: «حقن تعطل تخزين/مصدر/رسائل واختبار تنبيه صناعي
     وحالات degraded واعتماد حدودها» ⭐
   · **AC-34-4** ⭐: «أرفق لوحة قياس وسجلات منقحة وخطة تنبيه واستجابة؛
     لا تفعيل خارجي تلقائي» ⭐

📌 الأجزاء المقيسة ⭐:
   ① **لوحة قياس قابلة للتشغيل والاختبار** ⭐
     (`tools/staging/metrics_board.py` ⭐ — شغّالة لوحدها ⭐).
   ② **سطح قياس مدمج في السيرفر المعزول** ⭐ ⇒ يقيس **الطلبات الحقيقية** ⭐.
   ③ **خطة تنبيه بحدود معتمدة** ⭐ + تنبيه **صناعي** ⭐ (مافيش تفعيل ⭐).
   ④ **حالات degraded** ⭐: تخزين تالف · مصدر متعطّل · إرسال واقع ⭐.
   ⑤ **سجلات منقّحة** ⭐ — مافيش سر ولا بريد ولا توكن ⭐.

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ سيرفر staging معزول ⭐ · مافيش شبكة ⭐ · مافيش بريد ⭐
   ⛔ مافيش أي تفعيل خارجي ⭐ (التنبيهات محلية ⭐ بس ⭐)

📌 التشغيل: python3 tools/test_r25_metrics_board.py
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
from metrics_board import (AlertPlan, DEGRADED_CASES, MetricsBoard,  # noqa: E402
                           filter_log, redact_line)

_CLEANUP = []
RESULTS = []
REPORT = {}

# ⛔ حقول **داخلية** ⭐ ممنوعة في الرد العام ⭐
LEAK_KEYS = ("users_n", "users_io", "app_writable", "mail_configured",
             "mail_last_ok", "tickers", "stocks", "gemini", "snapshot_id",
             "pin_users", "data_full_loaded", "auth")


def _launch(tag, stage_dir=None, **kw):
    stage = Path(stage_dir or ("/tmp/octa_r25_board_%s" % tag))
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


def _client(srv, ip="198.51.100.20"):
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


# ══════════════════════════════════════════════════════════════════
#  ① لوحة القياس ⭐ (قابلة للتشغيل لوحدها ⭐)
# ══════════════════════════════════════════════════════════════════
@_case
def test_metrics_board_library_is_runnable():
    """① لوحة القياس شغّالة لوحدها ⭐ وبتعطي أرقام ⭐."""
    section("① لوحة القياس (شغّالة لوحدها)")
    board = MetricsBoard(service="octa-prices (اختبار)")
    for i in range(50):
        board.record("/api/health", 1.0 + i * 0.1, 200)
    for i in range(10):
        board.record("/api/ready", 2.0 + i * 0.2, 200 if i else 503)
    board.record("/api/ranking", 250.0, 200)
    snap = board.snapshot()
    ok(snap["totals"]["requests"] == 61,
       "①a عدد الطلبات متسجل ⭐", snap["totals"])
    ok(snap["totals"]["p50_ms"] is not None,
       "①b p50 متقاس ⭐", snap["totals"]["p50_ms"])
    ok(snap["totals"]["p95_ms"] is not None,
       "①c p95 متقاس ⭐", snap["totals"]["p95_ms"])
    ok(snap["routes"]["/api/health"]["n"] == 50,
       "①d لكل مسار عدده ⭐", snap["routes"]["/api/health"]["n"])
    ok(snap["routes"]["/api/ready"]["errors"] == 1,
       "①e الأخطاء متسجلة ⭐", snap["routes"]["/api/ready"]["errors"])
    ok(snap["totals"]["error_rate"] > 0,
       "①f نسبة الأخطاء محسوبة ⭐", snap["totals"]["error_rate"])
    text = board.render()
    ok("لوحة القياس" in text, "①g اللوحة بتترسم نصّي ⭐", text[:60])
    ok(len(snap["limits"]) >= 6, "①h الحدود موثّقة ⭐", len(snap["limits"]))
    REPORT["board"] = snap["totals"]
    return snap


# ══════════════════════════════════════════════════════════════════
#  ② السطح المدمج ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_metrics_surface_records_real_requests():
    """② سطح القياس المدمج بيسجّل الطلبات الحقيقية ⭐."""
    section("② سطح القياس المدمج في السيرفر المعزول")
    stage = "/tmp/octa_r25_board_surface"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("surface", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    st, _h, b, _ms = c.get("/__harness__/reset")
    ok(st == 200, "②a اللوحة اتصفّرت ⭐", st)

    n_health = 12
    n_prices = 7
    for _ in range(n_health):
        c.get("/api/health", auth=False)
    for _ in range(n_prices):
        c.get("/api/prices", auth=False)

    st, _h, b, _ms = c.get("/__harness__/metrics")
    snap = _j(b)
    routes = snap.get("routes") or {}
    ok(st == 200, "②b السطح بيرد ⭐", st)
    ok(int((routes.get("/api/health") or {}).get("n") or 0) == n_health,
       "②c عدد طلبات /api/health متطابق ⭐",
       (routes.get("/api/health") or {}).get("n"))
    ok(int((routes.get("/api/prices") or {}).get("n") or 0) == n_prices,
       "②d عدد طلبات /api/prices متطابق ⭐",
       (routes.get("/api/prices") or {}).get("n"))
    ok((routes.get("/api/health") or {}).get("p95_ms") is not None,
       "②e p95 متقاس على السيرفر ⭐",
       (routes.get("/api/health") or {}).get("p95_ms"))
    ok((routes.get("/api/health") or {}).get("p50_ms") is not None,
       "②f p50 متقاس على السيرفر ⭐",
       (routes.get("/api/health") or {}).get("p50_ms"))
    ok("app" in snap, "②g حالة التطبيق مرفقة ⭐", list(snap.keys()))
    REPORT["surface"] = {"health": routes.get("/api/health"),
                          "prices": routes.get("/api/prices")}
    return snap


# ══════════════════════════════════════════════════════════════════
#  ③ الصحة + مافيش تسريب ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_health_surface_is_light_and_leak_free():
    """③ liveness خفيف + readiness + مافيش تسريب داخلي ⭐."""
    section("③ سطح الصحة — خفيف ومافيش تسريب")
    stage = "/tmp/octa_r25_board_health"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("health", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    st, _h, b, ms = c.get("/api/health", auth=False)
    j = _j(b)
    ok(st == 200, "③a liveness بيرد 200 ⭐", st)
    leaked = [k for k in LEAK_KEYS if k in j]
    ok(not leaked, "③b مافيش بيانات داخلية في الرد العام ⭐", leaked)
    ok(len(b) < 1024, "③c الرد العام خفيف ⭐", len(b))

    st, _h, b, ms = c.get("/api/ready", auth=False)
    r = _j(b)
    ok(st == 200, "③d readiness بيرد 200 والخدمة جاهزة ⭐", st)
    checks = r.get("checks") or {}
    ok(set(checks.keys()) == {"data", "store", "writable", "secret"},
       "③e readiness بيكشف الاعتماديات الحرجة ⭐", list(checks.keys()))
    ok(all(v is True for v in checks.values()),
       "③f كل الاعتماديات الحرجة سليمة ⭐", checks)
    REPORT["health"] = {"bytes": len(b), "checks": checks}
    return j


# ══════════════════════════════════════════════════════════════════
#  ④ خطة التنبيه ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_alert_plan_fires_on_injected_faults():
    """④ تنبيه صناعي ⭐ على أعطال حقيقية ⭐ + حدود معتمدة ⭐."""
    section("④ خطة التنبيه — تنبيهات صناعية")
    stage = "/tmp/octa_r25_board_alerts"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("alerts", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    plan = AlertPlan()
    ok(len(plan.rules()) >= 6,
       "④a في خطة تنبيه بقواعد موثّقة ⭐", len(plan.rules()))
    ok(all(r.get("threshold") is not None for r in plan.rules()),
       "④b كل قاعدة ليها حدّ معتمد ⭐")

    # ⛔ خراب التخزين ⭐
    uf = Path(srv.stage_dir) / "users.json"
    good = uf.read_bytes()
    try:
        uf.write_bytes(b"{ broken")
        c.get("/api/auth/me")          # ⭐ يخلّي التطبيق يقرأ الملف ⭐
        st, _h, b, _ms = c.get("/__harness__/metrics")
        snap = _j(b)
        fired = {a.get("name"): a for a in (snap.get("alerts") or [])}
        ok("storage_broken" in fired,
           "④c عطل التخزين ⇒ تنبيه storage_broken ⭐", list(fired))
        if "storage_broken" in fired:
            ok(fired["storage_broken"]["severity"] == "critical",
               "④d التنبيه critical ⭐", fired["storage_broken"]["severity"])
            ok(fired["storage_broken"]["threshold"] is True,
               "④e حد التنبيه موثّق ⭐", fired["storage_broken"]["threshold"])
    finally:
        uf.write_bytes(good)

    # ⛔ البيانات غير متاحة ⭐
    st, _fj = _fault(c, "data", "unavailable")
    st, _h, b, _ms = c.get("/__harness__/metrics")
    fired = {a.get("name"): a for a in (_j(b).get("alerts") or [])}
    ok("data_unavailable" in fired,
       "④f البيانات غير متاحة ⇒ تنبيه data_unavailable ⭐", list(fired))
    _fault(c, "data", "restore")

    # ⛔ الإرسال واقع ⭐
    st, _fj = _fault(c, "mail", "off")
    st, _h, b, _ms = c.get("/__harness__/metrics")
    fired = {a.get("name"): a for a in (_j(b).get("alerts") or [])}
    ok("mail_down" in fired,
       "④g الإرسال واقع ⇒ تنبيه mail_down ⭐", list(fired))
    _fault(c, "mail", "on")

    # ⛔ لازم مافيش تفعيل خارجي ⭐
    st, _h, b, _ms = c.get("/__harness__/alerts")
    a = _j(b)
    ok("rules" in a and "limits" in a,
       "④h خطة التنبيه معروضة ومحدودها موثّقة ⭐", list(a.keys()))
    REPORT["alerts"] = {"rules": len(plan.rules()),
                        "limits": a.get("limits")}
    return a


# ══════════════════════════════════════════════════════════════════
#  ⑤ حالات degraded ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_degraded_mode_cases():
    """⑤ حالات degraded ⭐ — تخزين · مصدر · إرسال ⭐."""
    section("⑤ حالات degraded")
    stage = "/tmp/octa_r25_board_degraded"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("degraded", stage_dir=stage, source_mode="ok")
    c = _client(srv)
    ok(len(DEGRADED_CASES) >= 3,
       "⑤a في حالات degraded معرّفة ⭐", len(DEGRADED_CASES))

    # ⛔ (١) تخزين تالف ⭐
    uf = Path(srv.stage_dir) / "users.json"
    good = uf.read_bytes()
    try:
        uf.write_bytes(b"{ broken")
        c.get("/api/auth/me")
        st, _h, b, _ms = c.get("/api/ready", auth=False)
        ready = _j(b)
        st2, _h2, b2, _ms2 = c.get("/api/health", auth=False)
        health = _j(b2)
        ok(st == 503, "⑤b تخزين تالف ⇒ readiness 503 ⭐", st)
        ok(st2 == 200, "⑤c liveness فضل 200 ⭐", st2)
        leaked = [k for k in LEAK_KEYS if k in health]
        ok(not leaked, "⑤d الرد العام ما بيقولش حاجة داخلية ⭐", leaked)
    finally:
        uf.write_bytes(good)

    # ⛔ (٢) المصدر متعطّل ⭐
    _fault(c, "source_mode", "timeout")
    st, _h, b, _ms = c.get("/api/health", auth=False)
    ok(st == 200, "⑤e مصدر متعطّل ⇒ liveness 200 ⭐", st)
    st, _h, b, _ms = c.get("/api/prices", auth=False)
    ok(st == 200, "⑤f مصدر متعطّل ⇒ مسار عام شغّال ⭐", st)
    _fault(c, "source_mode", "ok")

    # ⛔ (٣) الإرسال واقع ⭐
    _fault(c, "mail", "off")
    st, _h, b, _ms = c.get("/api/health", auth=False)
    ok(st == 200, "⑤g الإرسال واقع ⇒ الخدمة الأساسية شغّالة ⭐", st)
    st, _h, b, _ms = c.get("/__harness__/state")
    ok(st == 200, "⑤h تشخيص الحالة متاح ⭐", st)
    _fault(c, "mail", "on")
    return True


# ══════════════════════════════════════════════════════════════════
#  ⑥ السجلات المنقّحة ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_logs_are_filtered_and_redacted():
    """⑥ السجلات منقّحة ⭐ — مافيش سر ولا بريد ولا توكن ⭐."""
    section("⑥ السجلات المنقّحة")
    stage = "/tmp/octa_r25_board_logs"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("logs", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    sample = [
        "INFO proxy_secret = SUPERSECRETVALUE123",
        "WARN user email someone@example.test token=abcdefgh",
        "INFO Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc",
        "INFO X-OCTA-Proxy: PRX-abcdefghijklmnop",
        "INFO طلب عادي بدون أي سر",
    ]
    clean, hidden = filter_log(sample)
    joined = "\n".join(clean)
    ok("SUPERSECRETVALUE123" not in joined,
       "⑥a سر البروبزي متحجوب ⭐", joined[:120])
    ok("someone@example.test" not in joined,
       "⑥b البريد متحجوب ⭐", joined[:120])
    ok("eyJhbGciOiJIUzI1NiJ9.abc" not in joined,
       "⑥c التوكن متحجوب ⭐", joined[:120])
    ok("PRX-abcdefghijklmnop" not in joined,
       "⑥d ترويسة البروبزي متحجوبة ⭐", joined[:120])
    ok(any("طلب عادي" in c2 for c2 in clean),
       "⑥e السطور المفيدة بتفضل ⭐", len(clean))

    st, _h, b, _ms = c.get("/__harness__/log")
    j = _j(b)
    ok(st == 200, "⑥f مسار السجلات المنقّحة شغّال ⭐", st)
    ok("lines" in j, "⑥g السجلات مرجّعة ⭐", list(j.keys()))
    server_log = "\n".join(j.get("lines") or [])
    ok(srv.proxy_secret not in server_log,
       "⑥h مافيش سر البروبزي في السجل ⭐", server_log[:120])
    REPORT["logs"] = {"sample_lines": len(clean), "hidden": hidden}
    return j


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐
# ══════════════════════════════════════════════════════════════════
def _readiness_failures(srv, c):
    """⛔ فحص واحد ⭐ — نفس الفحص في كل الحالات ⭐."""
    fails = []
    uf = Path(srv.stage_dir) / "users.json"
    good = uf.read_bytes()
    try:
        uf.write_bytes(b"{ broken")
        c.get("/api/auth/me")
        st, _h, b, _ms = c.get("/api/ready", auth=False)
        if st != 503:
            fails.append("readiness رجّع %s بدل 503 ⭐ (التخزين تالف ⭐)"
                         % st)
        st2, _h2, b2, _ms2 = c.get("/api/health", auth=False)
        if st2 != 200:
            fails.append("liveness رجّع %s بدل 200 ⭐" % st2)
        health = _j(b2)
        leaked = [k for k in LEAK_KEYS if k in health]
        if leaked:
            fails.append("تسريب داخلي في الرد العام ⭐ (%s)" % leaked)
    finally:
        uf.write_bytes(good)
    return fails


@_case
def test_metrics_negative_proof_store_detection_removed():
    """🧨 شيل كشف تلف المخزن ⇒ readiness مش بيفشل ⭐."""
    section("🧨 البرهان السالب — تعطيل كشف تلف المخزن")
    stage = "/tmp/octa_r25_board_neg"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("neg", stage_dir=stage, source_mode="ok")
    c = _client(srv)

    fails_on = _readiness_failures(srv, c)
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: readiness بيفشل مع تخزين تالف ⭐", fails_on)

    st, _fj = _fault(c, "store_detect_off", "off")
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off = _readiness_failures(srv, c)
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))

    _fault(c, "store_detect_off", "on")
    fails_back = _readiness_failures(srv, c)
    ok(len(fails_back) == 0,
       "🧨d بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    REPORT["negative_readiness"] = {"before": len(fails_off),
                                    "after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


def main():
    print("=" * 70)
    print("  📊 R25 · لوحة القياس + خطة التنبيه + حالات degraded")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_metrics_board_library_is_runnable()
    test_metrics_surface_records_real_requests()
    test_health_surface_is_light_and_leak_free()
    test_alert_plan_fires_on_injected_faults()
    test_degraded_mode_cases()
    test_logs_are_filtered_and_redacted()
    test_metrics_negative_proof_store_detection_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 لوحة القياس الحقيقية (من السيرفر المعزول ⭐):")
    surf = REPORT.get("surface") or {}
    for name, rec in surf.items():
        if rec:
            print("     %-24s n=%s p50=%sms p95=%sms ⭐"
                  % (name, rec.get("n"), rec.get("p50_ms"),
                     rec.get("p95_ms")))
    alerts = REPORT.get("alerts") or {}
    if alerts:
        print("     %-24s %d قاعدة · حدود موثّقة ⭐"
              % ("قواعد التنبيه", alerts.get("rules", 0)))
    neg = REPORT.get("negative_readiness")
    if neg:
        print("     %-24s الإخفاقات قبل=%d · بعد=%d ⭐"
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
