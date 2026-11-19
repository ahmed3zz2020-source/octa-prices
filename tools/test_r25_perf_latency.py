#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📈 الجولة ٢٥ (R25 · المرحلة ٩) — قياس الأداء: p50/p95 + اختبار حمل + حدود الطلبات

📌 بنود القبول المستهدفة ⭐:
   · **AC-32-1** ⭐: «قياس p95 وطلبات الصفحة والذاكرة والتكلفة
     بالنسبة للأهداف المقترحة المعتمدة» ⭐
   · **AC-32-3** ⭐: «اختبار حمل صناعي محلي بعد اعتماد ملف الحمل والسقف؛
     اختبر عدة عمال دون موارد مدفوعة» ⭐

📌 وشmeasuring بالظبط ⭐:
   ① **p50/p95 حقيقي** ⭐ فوق **مسارات حقيقية** ⭐ في التطبيق ⭐
      (مشEstimates · مش أرقام مخترعة ⭐) ⭐.
   ② **اختبار حمل صناعي** ⭐ — عدة عمال على السيرفر المعزول ⭐
      (بلا أي مورد مدفوع ⭐ · كله على `127.0.0.1` ⭐).
   ③ **استهلاك الذاكرة** ⭐ — مقيس من عملية السيرفر نفسها ⭐.
   ④ **حدود الطلبات** ⭐ — بالحدود الحقيقية (مضاعف = 1 ⭐) ⭐.

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ سيرفر **staging معزول** ⭐ في مجلد مؤقّت ⭐
   ⛔ مافيش أي اتصال خارجي ⭐ (الشبكة مقفولة جوه العملية ⭐)
   ⛔ مافيش أي سر إنتاج ⭐ (أسرار اصطناعية تتولّد لكل تشغيل ⭐)
   ⛔ مافيش أي نشر ⭐

📌 التشغيل: python3 tools/test_r25_perf_latency.py
   📌 وكل ملف اختبار كمان بيشتغل تحت `pytest` ⭐.
"""
import atexit
import functools
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "staging"))

import iso_env as iso  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  🧰بيئة الاختبار — سيرفر واحد مشترك لكل الحالات ⭐
# ══════════════════════════════════════════════════════════════════
_SERVERS = {}
_CLEANUP = []


def _launch(name, **kw):
    """بيرجّع سيرفر معزول بالاسم ⭐ (بيتشغّل مرة واحدة ⭐)."""
    if name in _SERVERS:
        return _SERVERS[name]
    stage = Path("/tmp/octa_r25_perf_%s" % name)
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


def _client(srv, ip="198.51.100.10"):
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip=ip)
    return c


def _login(srv, c):
    cfg = iso.read_stage_cfg(srv.stage_dir)
    tok, st, _j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s)" % st)
    return tok


# ══════════════════════════════════════════════════════════════════
#  📋 المسارات المقاسة ⭐ (كلها من التطبيق الحقيقي ⭐)
# ══════════════════════════════════════════════════════════════════
PUBLIC_ROUTES = [
    "/api/health",
    "/api/ready",
    "/api/prices",
    "/api/quotes",
    "/api/logos",
]
AUTH_ROUTES = [
    "/api/data_full",
    "/api/indices",
    "/api/ranking",
    "/api/opportunities",
    "/api/dashboard",
    "/api/strategies",
    "/api/heat",
    "/api/top-movers",
]

REPEATS = 20
LOAD_WORKERS = 4
LOAD_EACH = 25
# ⛔ سقف منطقي (مش هدف أداء معتمد ⭐) — بيكشف تعليق السيرفر ⭐
SANITY_CEILING_MS = 5000.0

RESULTS = []


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


# ══════════════════════════════════════════════════════════════════
#  ① p50/p95 فوق المسارات الحقيقية ⭐
# ══════════════════════════════════════════════════════════════════
def _measure_route(c, path, auth, repeats=REPEATS):
    samples = []
    statuses = {}
    for _ in range(repeats):
        st, _h, _b, ms = c.get(path, auth=auth)
        samples.append(ms)
        statuses[st] = statuses.get(st, 0) + 1
    return iso.summarize(samples), statuses


@_case
def test_perf_routes_have_measured_p50_and_p95():
    """① لكل مسار حقيقي: p50 وp95 **مقيسان فعلاً** ⭐."""
    section("① p50/p95 فوق المسارات الحقيقية")
    srv = _launch("main")
    c = _client(srv)
    _login(srv, c)
    report = {}
    for path in PUBLIC_ROUTES:
        summ, statuses = _measure_route(c, path, auth=False)
        summ = dict(summ)
        summ["statuses"] = statuses
        report[path] = summ
        print("   %-24s n=%d p50=%.2fms p95=%.2fms p99=%.2fms %s"
              % (path, summ["n"], summ["p50_ms"], summ["p95_ms"],
                 summ["p99_ms"], statuses), flush=True)
    for path in AUTH_ROUTES:
        summ, statuses = _measure_route(c, path, auth=True)
        summ = dict(summ)
        summ["statuses"] = statuses
        report[path] = summ
        print("   %-24s n=%d p50=%.2fms p95=%.2fms p99=%.2fms %s"
              % (path, summ["n"], summ["p50_ms"], summ["p95_ms"],
                 summ["p99_ms"], statuses), flush=True)
    ok(len(report) == len(PUBLIC_ROUTES) + len(AUTH_ROUTES),
       "①a كل المسارات المقاسة اتقاست",
       len(report))
    ok(all(r["n"] == REPEATS for r in report.values()),
       "①b كل مسار اتقاس %d مرة ⭐" % REPEATS,
       {k: v["n"] for k, v in report.items()})
    ok(all(r["p50_ms"] is not None and r["p95_ms"] is not None
           for r in report.values()),
       "①c p50 وp95 موجودين لكل مسار ⭐")
    ok(all(r["p95_ms"] >= r["p50_ms"] for r in report.values()),
       "①d p95 أكبر من أو يساوي p50 ⭐ (ترتيب صح ⭐)")
    ok(all(r["max_ms"] < SANITY_CEILING_MS for r in report.values()),
       "①e مفيش مسار عدّى السقف المنطقي (%.0fms) ⭐" % SANITY_CEILING_MS,
       {k: v["max_ms"] for k, v in report.items()
        if v["max_ms"] >= SANITY_CEILING_MS})
    # ⭐ المسارات الخفيفة لازم تكون تحت حد التنبيه المعتمد (800ms ⭐)
    light = [report[p]["p95_ms"] for p in PUBLIC_ROUTES]
    ok(max(light) < 800.0,
       "①f المسارات العامة: p95 تحت حد التنبيه المعتمد (800ms) ⭐",
       "max p95 = %.2fms" % max(light))
    # ⛔ كل المسارات لازم ترد 200 ⭐ (غير الـ401 ⭐ ⇒ الجلسة شغّالة ⭐)
    bad = {k: v.get("statuses") for k, v in report.items()
           if set(v.get("statuses") or {}) - {200}}
    ok(not bad, "①g كل المسارات ردت 200 ⭐ (الجلسة شغّالة ⭐)", bad)
    _REPORT["routes"] = report
    return report


# ══════════════════════════════════════════════════════════════════
#  ② اختبار الحمل الصناعي ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_perf_synthetic_load_test():
    """② حمل صناعي: عدة عمال ⭐ على السيرفر المعزول ⭐."""
    section("② اختبار حمل صناعي (محلي · عدة عمال)")
    srv = _launch("main")
    results = {}
    errors = []
    lock = threading.Lock()

    def worker(idx):
        c = _client(srv, ip="198.51.100.%d" % (20 + idx))
        _login(srv, c)
        local = []
        for i in range(LOAD_EACH):
            path = AUTH_ROUTES[i % len(AUTH_ROUTES)]
            try:
                st, _h, _b, ms = c.get(path)
            except Exception as exc:
                with lock:
                    errors.append("%s: %s" % (path, type(exc).__name__))
                continue
            local.append((path, ms, st))
        with lock:
            results[idx] = local

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(LOAD_WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)
    wall = time.perf_counter() - t0

    all_ms = []
    by_status = {}
    for rows in results.values():
        for path, ms, st in rows:
            all_ms.append(ms)
            by_status[st] = by_status.get(st, 0) + 1
    summ = iso.summarize(all_ms)
    total = LOAD_WORKERS * LOAD_EACH
    print("   workers=%d each=%d total=%d wall=%.2fs rps=%.1f"
          % (LOAD_WORKERS, LOAD_EACH, len(all_ms), wall,
             (len(all_ms) / wall) if wall > 0 else 0.0), flush=True)
    print("   p50=%.2fms p95=%.2fms p99=%.2fms max=%.2fms statuses=%s"
          % (summ["p50_ms"], summ["p95_ms"], summ["p99_ms"], summ["max_ms"],
             by_status), flush=True)
    ok(not errors, "②a مفيش استثناء في الشبكة ⭐", errors[:5])
    ok(len(all_ms) == total,
       "②b كل الطلبات اتجاوبت (%d/%d) ⭐" % (len(all_ms), total))
    ok(sum(v for k, v in by_status.items() if int(k) >= 500) == 0,
       "②c مفيش خطأ خادم (5xx) في الحمل ⭐", by_status)
    ok(summ["p95_ms"] is not None and summ["p95_ms"] > 0,
       "②d p95 اتقاس في الحمل ⭐", summ)
    ok(wall > 0, "②e زمن الحمل اتقاس ⭐", wall)
    _REPORT["load"] = {"summary": summ, "wall_seconds": round(wall, 3),
                        "statuses": by_status, "workers": LOAD_WORKERS,
                        "each": LOAD_EACH}
    return summ


# ══════════════════════════════════════════════════════════════════
#  ③ استهلاك الذاكرة ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_perf_memory_consumption_measured():
    """③ استهلاك الذاكرة: مقيس من عملية السيرفر ⭐."""
    section("③ استهلاك الذاكرة (RSS) في عملية السيرفر")
    srv = _launch("main")
    c = _client(srv)

    def _rss():
        st, _h, body, _ms = c.get("/__harness__/state")
        j = body and __import__("json").loads(body.decode("utf-8"))
        return float((j or {}).get("rss_mb") or 0.0)

    before = _rss()
    # ⛔ حمل إضافي ⭐ عشان نشوف أثر الضغط على الذاكرة ⭐
    for _ in range(30):
        c.get("/api/data_full")
        c.get("/api/indices")
    after = _rss()
    delta = after - before
    print("   RSS before=%.2fMB after=%.2fMB delta=%.2fMB" % (before, after, delta),
          flush=True)
    ok(before > 0, "③a الذاكرة قبل الحمل اتقاست ⭐", before)
    ok(after > 0, "③b الذاكرة بعد الحمل اتقاست ⭐", after)
    ok(delta < 200.0,
       "③c فرق الذاكرة تحت 200MB ⭐ (مافيش تسريب واضح ⭐)", delta)
    ok(after < 512.0,
       "③d الذاكرة الكلية تحت سقف Railway (512MB) ⭐", after)
    _REPORT["memory"] = {"before_mb": before, "after_mb": after,
                         "delta_mb": delta}
    return {"before": before, "after": after, "delta": delta}


# ══════════════════════════════════════════════════════════════════
#  ④ حدود الطلبات بالحدود الحقيقية ⭐
# ══════════════════════════════════════════════════════════════════
def _burst(srv, ip, count):
    """بيرجّع (عدد 429 · أول حالة 429 · ترويسة Retry-After ⭐)."""
    c = _client(srv, ip=ip)
    blocked = 0
    first_status = None
    retry_after = None
    for _ in range(count):
        st, h, _b, _ms = c.get("/api/prices", auth=False)
        if st == 429:
            blocked += 1
            if first_status is None:
                first_status = st
                retry_after = h.get("Retry-After")
    c.close()
    return blocked, first_status, retry_after


def _rate_limit_protection_failures(srv, ip):
    """⛔ فحص واحد للحماية ⭐ — بيتنفّذ في الحالتين ⭐ (مع/بدون حماية ⭐).

    ⛔ نفس الفحص بالظبط ⭐ ⇒ لو الحماية اتشالت ⭐
       لازم الإخفاقات تبقى **موجودة** ⭐ (ده البرهان السالب ⭐).
    """
    fails = []
    blocked, first_status, retry_after = _burst(srv, ip, 140)
    if blocked <= 0:
        fails.append("مافيش 429 ⭐ ⇒ حد الطلبات مش شغّال ⭐")
    if first_status != 429:
        fails.append("أول رفض مش 429 ⭐ (الحالة %s)" % first_status)
    if retry_after is None:
        fails.append("مافيش ترويسة Retry-After ⭐")
    return fails, blocked


@_case
def test_perf_rate_limit_enforced_with_real_limits():
    """④ حد الطلبات الحقيقي (مضاعف=1) لازم يرد 429 ⭐."""
    section("④ حدود الطلبات بالحدود الحقيقية (مضاعف = 1)")
    srv = _launch("ratelimit", rate_mult="1")
    fails, blocked = _rate_limit_protection_failures(srv, "203.0.113.5")
    ok(not fails, "④a حد الطلبات الحقيقي شغال ⭐", fails)
    # ⛔ الخادم لازم يفضل شغّال بعد الرفض ⭐
    c = _client(srv, ip="203.0.113.6")
    st, _h, _b, _ms = c.get("/api/health", auth=False)
    ok(st == 200, "④b الخادم فضل شغّال بعد الرفض ⭐", st)
    _REPORT["rate_limit"] = {"blocked": blocked}
    return blocked


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐ — شيل الحماية وشوف السلوك يتغيّر ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_perf_negative_proof_rate_limit_removed():
    """🧨 البرهان السالب: بعد تعطيل حد الطلبات ⇒ نفس الفحص **يفشل** ⭐."""
    section("🧨 البرهان السالب — تعطيل حد الطلبات")
    srv = _launch("ratelimit", rate_mult="1")
    c = _client(srv, ip="203.0.113.7")

    # ① مع الحماية ⭐ ⇒ مافيش إخفاقات ⭐
    fails_on, blocked_on = _rate_limit_protection_failures(srv, "203.0.113.11")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: الفحص بيعدّي ⭐ (0 إخفاقات ⭐)", fails_on)

    # ② شيل الحماية ⭐
    st, _h, _b, _ms = c.post("/__harness__/fault",
                             {"kind": "rate_limit", "value": "off"})
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off, blocked_off = _rate_limit_protection_failures(srv, "203.0.113.12")
    print("   مع الحماية: 429=%d · بدونها: 429=%d ⭐"
          % (blocked_on, blocked_off), flush=True)
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))
    ok(blocked_off < blocked_on,
       "🧨d سلوك الحماية اتغيّر فعلاً ⭐ (%d → %d) ⭐"
       % (blocked_on, blocked_off))

    # ③ رجّع الحماية ⭐
    c.post("/__harness__/fault", {"kind": "rate_limit", "value": "on"})
    fails_back, _blocked_back = _rate_limit_protection_failures(srv,
                                                                 "203.0.113.13")
    ok(len(fails_back) == 0,
       "🧨e بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    _REPORT["negative_rate_limit"] = {
        "blocked_when_on": blocked_on, "blocked_when_off": blocked_off,
        "failures_before": len(fails_off), "failures_after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


# ══════════════════════════════════════════════════════════════════
_REPORT = {}


def main():
    print("=" * 70)
    print("  📈 R25 · قياس الأداء (p50/p95 + حمل + ذاكرة + حدود الطلبات)")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_perf_routes_have_measured_p50_and_p95()
    test_perf_synthetic_load_test()
    test_perf_memory_consumption_measured()
    test_perf_rate_limit_enforced_with_real_limits()
    test_perf_negative_proof_rate_limit_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 القياسات الحقيقية:")
    for path, r in sorted(_REPORT.get("routes", {}).items()):
        print("     %-24s p50=%8.2fms p95=%8.2fms p99=%8.2fms"
              % (path, r["p50_ms"], r["p95_ms"], r["p99_ms"]))
    load = _REPORT.get("load")
    if load:
        s = load["summary"]
        print("     %-24s p50=%8.2fms p95=%8.2fms p99=%8.2fms (%d عمال · %.2fs)"
              % ("الحمل الصناعي", s["p50_ms"], s["p95_ms"], s["p99_ms"],
                 load["workers"], load["wall_seconds"]))
    mem = _REPORT.get("memory")
    if mem:
        print("     %-24s قبل=%.2fMB بعد=%.2fMB فرق=%.2fMB"
              % ("الذاكرة", mem["before_mb"], mem["after_mb"], mem["delta_mb"]))
    neg = _REPORT.get("negative_rate_limit")
    if neg:
        print("     %-24s 429 مع الحماية=%d · بدونها=%d ⭐ (البرهان السالب ⭐)"
              % ("حد الطلبات", neg["blocked_when_on"],
                 neg["blocked_when_off"]))
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
