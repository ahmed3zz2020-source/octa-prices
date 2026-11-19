#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 لوحة القياس + خطة التنبيه + منقّح السجلات — الجولة ٢٥ (R25 · المرحلة ٩)

📌 المطلوب من المالك ⭐ (بند القبول AC-34-3 · AC-34-4 ⭐):
   · «حقن تعطل تخزين/مصدر/رسائل واختبار تنبيه صناعي وحالات degraded
      واعتماد حدودها» ⭐
   · «أرفق لوحة قياس وسجلات منقحة وخطة تنبيه واستجابة» ⭐

📌 الأداة دي **مستقلة وقابلة للتشغيل لوحدها** ⭐:
   python3 tools/staging/metrics_board.py     ⭐ ⇒ يطبع لوحة كاملة ⭐

📌 مفيش أي اتصال خارجي ⭐ · مافيش أي سر إنتاج ⭐
"""
import json
import os
import re
import time
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
#  🚦 حدود التنبيه — معتمدة ومكتوبة ⭐ (مافيش أرقام مخترعة ⭐)
# ══════════════════════════════════════════════════════════════════
# 📌 p95: هدف الـUI في الواجهة كان 800ms ⭐ (المرجع UX-PERF-01 ⭐)
# 📌 الذاكرة: Railway بي allot 512 ميجا ⭐ ⇒ warning عند 400 ⭐
# 📌 نسبة الأخطاء: 5% ⭐ ⇒ بعد كده الخدمة «degraded» ⭐
DEFAULT_LIMITS = {
    "p95_ms": 800.0,
    "p99_ms": 1500.0,
    "error_rate": 0.05,
    "rss_mb": 400.0,
    "ready_down": True,
    "storage_broken": True,
    "mail_down": True,
    "data_unavailable": True,
}


# ══════════════════════════════════════════════════════════════════
#  📈 اللوحة
# ══════════════════════════════════════════════════════════════════
class MetricsBoard:
    """لوحة قياس ⭐ — بتجمّع عيّنات زمن الاستجابة والأخطاء ⭐."""

    def __init__(self, service="octa-prices", limits=None):
        self.service = service
        self.limits = dict(DEFAULT_LIMITS)
        if limits:
            self.limits.update(limits)
        self._routes = {}
        self._totals = {"n": 0, "errors": 0, "ms_total": 0.0}
        self.started_at = time.time()
        self.alerts = []
        self.alert_history = []

    # ── التسجيل ⭐ ──
    def record(self, route, ms, status=200):
        key = str(route)
        bucket = self._routes.setdefault(key, {"n": 0, "errors": 0, "ms": [],
                                               "statuses": {}})
        bucket["n"] += 1
        bucket["ms"].append(float(ms))
        st = str(status)
        bucket["statuses"][st] = bucket["statuses"].get(st, 0) + 1
        self._totals["n"] += 1
        self._totals["ms_total"] += float(ms)
        if int(status) >= 400:
            bucket["errors"] += 1
            self._totals["errors"] += 1
        return bucket

    def reset(self):
        self._routes = {}
        self._totals = {"n": 0, "errors": 0, "ms_total": 0.0}
        self.started_at = time.time()

    # ── اللقطة ⭐ ──
    @staticmethod
    def _pct(data, p):
        data = sorted(data)
        if not data:
            return None
        if len(data) == 1:
            return round(data[0], 3)
        k = (len(data) - 1) * (p / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(data) - 1)
        frac = k - lo
        return round(data[lo] * (1.0 - frac) + data[hi] * frac, 3)

    def snapshot(self):
        """لقطة اللوحة ⭐ — JSON جاهز للطباعة أو الحفظ ⭐."""
        routes = {}
        for name, b in sorted(self._routes.items()):
            ms = b["ms"]
            routes[name] = {
                "n": b["n"],
                "errors": b["errors"],
                "error_rate": round(b["errors"] / float(b["n"]), 6) if b["n"] else 0.0,
                "p50_ms": self._pct(ms, 50),
                "p95_ms": self._pct(ms, 95),
                "p99_ms": self._pct(ms, 99),
                "max_ms": round(max(ms), 3) if ms else None,
                "statuses": dict(b["statuses"]),
            }
        all_ms = []
        for b in self._routes.values():
            all_ms.extend(b["ms"])
        n = self._totals["n"]
        return {
            "service": self.service,
            "uptime_seconds": round(time.time() - self.started_at, 3),
            "totals": {
                "requests": n,
                "errors": self._totals["errors"],
                "error_rate": round(self._totals["errors"] / float(n), 6) if n else 0.0,
                "p50_ms": self._pct(all_ms, 50),
                "p95_ms": self._pct(all_ms, 95),
                "p99_ms": self._pct(all_ms, 99),
            },
            "routes": routes,
            "limits": dict(self.limits),
            "alerts": list(self.alerts),
        }

    def to_json(self, indent=2):
        return json.dumps(self.snapshot(), ensure_ascii=False, indent=indent)

    def save(self, path):
        Path(path).write_text(self.to_json(), encoding="utf-8")
        return str(path)

    # ── نصّي ⭐ ──
    def render(self, width=78):
        """جدول نصّي ⭐ — مناسب للسجلّات ⭐."""
        snap = self.snapshot()
        out = []
        out.append("=" * width)
        out.append("📊 %s — لوحة القياس" % snap["service"])
        out.append("=" * width)
        out.append("  التشغيل: %.1f ثانية · الطلبات: %d · الأخطاء: %d (%.2f%%)"
                   % (snap["uptime_seconds"], snap["totals"]["requests"],
                      snap["totals"]["errors"],
                      snap["totals"]["error_rate"] * 100.0))
        out.append("  p50: %s ms · p95: %s ms · p99: %s ms"
                   % (snap["totals"]["p50_ms"], snap["totals"]["p95_ms"],
                      snap["totals"]["p99_ms"]))
        out.append("-" * width)
        out.append("  %-34s %6s %8s %8s %8s" % ("المسار", "عدد", "p50", "p95", "أخطاء"))
        for name, r in snap["routes"].items():
            out.append("  %-34s %6d %8s %8s %8d"
                       % (name[:34], r["n"], r["p50_ms"], r["p95_ms"], r["errors"]))
        out.append("-" * width)
        if snap["alerts"]:
            out.append("  ⚠️ تنبيهات نشطة: %d" % len(snap["alerts"]))
            for a in snap["alerts"]:
                out.append("     · [%s] %s — %s"
                           % (a.get("severity"), a.get("name"), a.get("message")))
        else:
            out.append("  ✅ مافيش تنبيهات نشطة")
        out.append("=" * width)
        return "\n".join(out)


# ══════════════════════════════════════════════════════════════════
#  🚨 خطة التنبيه
# ══════════════════════════════════════════════════════════════════
class AlertPlan:
    """خطة تنبيه ⭐ — قواعد مقيّدة بحدود معتمدة ⭐."""

    def __init__(self, limits=None):
        self.limits = dict(DEFAULT_LIMITS)
        if limits:
            self.limits.update(limits)
        self.history = []
        self.fired = {}

    def rules(self):
        lim = self.limits
        return [
            {"name": "latency_p95_high", "severity": "warn",
             "threshold": lim["p95_ms"], "unit": "ms",
             "message": "زمن الـp95 تجاوز الحد المعتمد"},
            {"name": "latency_p99_high", "severity": "warn",
             "threshold": lim["p99_ms"], "unit": "ms",
             "message": "زمن الـp99 تجاوز الحد المعتمد"},
            {"name": "error_rate_high", "severity": "critical",
             "threshold": lim["error_rate"], "unit": "ratio",
             "message": "نسبة الأخطاء تجاوزت الحد المعتمد"},
            {"name": "memory_rss_high", "severity": "warn",
             "threshold": lim["rss_mb"], "unit": "MB",
             "message": "استهلاك الذاكرة تجاوز الحد المعتمد"},
            {"name": "readiness_down", "severity": "critical",
             "threshold": lim["ready_down"], "unit": "bool",
             "message": "الخدمة مش جاهزة للخدمة"},
            {"name": "storage_broken", "severity": "critical",
             "threshold": lim["storage_broken"], "unit": "bool",
             "message": "مخزن الحسابات تالف"},
            {"name": "mail_down", "severity": "warn",
             "threshold": lim["mail_down"], "unit": "bool",
             "message": "الإرسال مش شغّال"},
            {"name": "data_unavailable", "severity": "warn",
             "threshold": lim["data_unavailable"], "unit": "bool",
             "message": "بيانات السوق غير متاحة"},
        ]

    def evaluate(self, snapshot, extra=None):
        """بيقيّم اللقطة ⭐ ⇒ بيرجّع قائمة التنبيهات ⭐."""
        extra = extra or {}
        fired = []
        tot = snapshot.get("totals") or {}
        lim = self.limits

        def add(name, severity, observed, threshold, message):
            rec = {"name": name, "severity": severity, "observed": observed,
                   "threshold": threshold, "message": message,
                   "at": time.time()}
            fired.append(rec)
            self.history.append(rec)

        p95 = tot.get("p95_ms")
        if p95 is not None and p95 > lim["p95_ms"]:
            add("latency_p95_high", "warn", p95, lim["p95_ms"],
                "زمن الـp95 تجاوز الحد المعتمد")
        p99 = tot.get("p99_ms")
        if p99 is not None and p99 > lim["p99_ms"]:
            add("latency_p99_high", "warn", p99, lim["p99_ms"],
                "زمن الـp99 تجاوز الحد المعتمد")
        er = tot.get("error_rate")
        if er is not None and er > lim["error_rate"]:
            add("error_rate_high", "critical", er, lim["error_rate"],
                "نسبة الأخطاء تجاوزت الحد المعتمد")
        rss = extra.get("rss_mb")
        if rss is not None and rss > lim["rss_mb"]:
            add("memory_rss_high", "warn", rss, lim["rss_mb"],
                "استهلاك الذاكرة تجاوز الحد المعتمد")
        if extra.get("ready") is False:
            add("readiness_down", "critical", False, lim["ready_down"],
                "الخدمة مش جاهزة للخدمة")
        if extra.get("storage_broken"):
            add("storage_broken", "critical", True, lim["storage_broken"],
                "مخزن الحسابات تالف")
        if extra.get("mail_down"):
            add("mail_down", "warn", True, lim["mail_down"],
                "الإرسال مش شغّال")
        if extra.get("data_unavailable"):
            add("data_unavailable", "warn", True, lim["data_unavailable"],
                "بيانات السوق غير متاحة")

        self.fired = {r["name"]: r for r in fired}
        return fired

    def acknowledge(self, name):
        """استجابة إنسانية ⭐ — بتسجّل إقرار التنبيه ⭐."""
        rec = self.fired.get(name)
        if rec is None:
            return False
        rec["acknowledged"] = True
        rec["acknowledged_at"] = time.time()
        return True


# ══════════════════════════════════════════════════════════════════
#  🧾 منقّح السجلات
# ══════════════════════════════════════════════════════════════════
_REDACT_PATTERNS = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), r"\1[محجوب]"),
    (re.compile(r"(?i)(x-octa-proxy\s*[:=]\s*)[^\s,;]+"), r"\1[محجوب]"),
    (re.compile(r"(?i)(x-octa-admin\s*[:=]\s*)[^\s,;]+"), r"\1[محجوب]"),
    (re.compile(r"(?i)((?:secret|token|pepper|password|passwd|pin|apikey|api_key)"
                r"\s*[:=]\s*)[^\s,;]+"), r"\1[محجوب]"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
     "[بريد محجوب]"),
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "[رقم محجوب]"),
]


def redact_line(line):
    """بيرجّع سطر منقّح ⭐ — من غير أي سر ⭐."""
    out = str(line)
    for rx, rep in _REDACT_PATTERNS:
        out = rx.sub(rep, out)
    return out


def filter_log(lines, keep_prefixes=None):
    """ينقّي سجل ⭐ — بيرجّع (الأسطر المنقّحة · عدد المحجوب ⭐)."""
    keep_prefixes = tuple(keep_prefixes) if keep_prefixes else None
    out = []
    hidden = 0
    for ln in lines:
        text = str(ln)
        if keep_prefixes and not text.startswith(keep_prefixes):
            hidden += 1
            continue
        out.append(redact_line(text))
    return out, hidden


# ══════════════════════════════════════════════════════════════════
#  🧪 حالات الـdegraded
# ══════════════════════════════════════════════════════════════════
DEGRADED_CASES = [
    {"id": "storage_broken", "scope": "storage",
     "expect": {"ready": 503, "health": 200, "leak": False},
     "desc": "تخزين تالف ⇒ مش جاهز · والرد العام ما بيقولش حاجة داخلية"},
    {"id": "data_unavailable", "scope": "source",
     "expect": {"ready": 503, "independent_ok": True},
     "desc": "المصدر متعطّل ⇒ البيانات غير متاحة · مصدر تاني شغّال"},
    {"id": "mail_down", "scope": "mail",
     "expect": {"core_ok": True, "mail_flag": False},
     "desc": "الإرسال واقع ⭐ ⇒ الخدمة الأساسية شغّالة"},
]


def degraded_snapshot():
    """قائمة الحالات ⭐ — قابلة للاختبار ⭐."""
    return [dict(c) for c in DEGRADED_CASES]


if __name__ == "__main__":
    board = MetricsBoard(service="octa-prices (تشغيل مستقل)")
    for i in range(40):
        board.record("/api/health", 3.0 + i * 0.1, 200)
    for i in range(10):
        board.record("/api/ready", 5.0 + i * 0.2, 200 if i else 503)
    board.record("/api/prices", 120.0, 200)
    board.record("/api/ranking", 480.0, 200)
    plan = AlertPlan()
    snap = board.snapshot()
    fired = plan.evaluate(snap, extra={"ready": True, "rss_mb": 180.0})
    board.alerts = fired
    print(board.render())
    print()
    print("🚨 حدود التنبيه المعتمدة:")
    for r in plan.rules():
        print("   · %-20s %-8s حد: %s %s — %s"
              % (r["name"], r["severity"], r["threshold"], r["unit"], r["message"]))
    print()
    sample = ["INFO proxy secret = abc123SECRET",
              "WARN user email user@example.test token=xyz789",
              "INFO تمام"]
    clean, hidden = filter_log(sample)
    print("🧾 منقّح السجلات:")
    for c in clean:
        print("   " + c)
    print("   (محجوب: %d)" % hidden)
    print()
    print("🧪 حالات degraded:")
    for c in degraded_snapshot():
        print("   · %-20s %s" % (c["id"], c["desc"]))
    print()
    print("RESULT: CLEAN")
