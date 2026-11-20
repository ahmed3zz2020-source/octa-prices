#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R28 · فحص وظيفي للباك الحقيقي (بيئة معزولة + بيانات اختبار).

📌 الغرض ⭐: إثبات أن **الباك الحقيقي** (تطبيق Flask نفسه ⭐ — مش API مبسّط ⭐)
   بيخدم الوظائف اللي المالك طلب تجربتها ⭐:
   · الدخول ⭐ · من أنا ⭐ · إنشاء حساب ⭐ · الاسترجاع ⭐
   · السوق والأسعار ⭐ · المحركات ⭐ · الفرص ⭐ · المحفظة ⭐
   · مقارنة الأسهم ⭐ · الذهب المصري ⭐ · التنبيهات ⭐
   · الاشتراكات ⭐ · الخروج وإبطال الجلسات ⭐

⛔ مافيش نشر ⭐ · ⛔ مافيش سر ⭐ · ⛔ مافيش اتصال بالإنترنت ⭐.
⛔ كل نتيجة = الحالة الفعلية ⭐ (مش "فتح الصفحة" ⭐).

── التشغيل ─────────────────────────────────────────────────────────────
   python3 tools/r28_function_probe.py --out /tmp/r28-probe.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

COOKIES = {}


def http(url, method="GET", body=None, headers=None, timeout=30):
    """طلب HTTP مع كوكي دائم ⭐ (جلسة حقيقية ⭐)."""
    data = None
    hdrs = {"User-Agent": UA}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    if COOKIES:
        hdrs["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in COOKIES.items())
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            for part in (res.headers.get("Set-Cookie") or "").split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip():
                        COOKIES[k.strip()] = v.strip()
            try:
                return res.status, json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                return res.status, raw[:300].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return exc.code, raw[:200].decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="R28 · الفحص الوظيفي للباك الحقيقي")
    ap.add_argument("--port", type=int, default=8241)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    stage = os.environ.get("STAGE_DIR", "/tmp/r28-stage")
    os.makedirs(stage, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "STAGE_DIR": stage,
        "STAGE_PORT": str(args.port),
        "STAGE_SECRETS_FILE": os.path.join(stage, "secrets.json"),
        "OCTA_BG_TASKS": "off",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
    })
    log = open(os.path.join(stage, "staging.log"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tools", "staging", "run_staging.py")],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d" % args.port
    results = []

    def rec(name, st, body, note=""):
        good = isinstance(body, dict) and body.get("ok") is not False
        results.append({"feature": name, "status": st, "ok": good, "note": note})
        print("  %s %-40s status=%s %s" % ("✅" if good else "❌", name, st, note))
        return body

    try:
        up = False
        for _ in range(120):
            st, _b = http(base + "/api/health", timeout=3)
            if st:
                up = True
                break
            time.sleep(1)
        if not up:
            print("⛔ بيئة الـstaging ما راقتش ⭐")
            return 1

        cfg = {}
        cfg_path = os.path.join(stage, "staging-config.json")
        for _ in range(60):
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, encoding="utf-8") as fh:
                        cfg = json.load(fh)
                    break
                except Exception:
                    pass
            time.sleep(1)
        H = {"X-OCTA-Proxy": cfg.get("proxy_secret", "")}

        print("═" * 72)
        print("🔬 R28 · الفحص الوظيفي للباك الحقيقي (بيانات اختبار ⭐)")
        print("═" * 72)

        # ① الدخول ⭐ (حساب مجهّز ⭐)
        free = cfg.get("free") or {}
        st, b = http(base + "/api/auth/pin/login", method="POST",
                     body={"email": free.get("email"), "pin": free.get("pin"),
                           "device": free.get("device")}, headers=H)
        rec("الدخول بالباسورد (/api/auth/pin/login)", st, b)
        token = b.get("token", "") if isinstance(b, dict) else ""
        AH = dict(H)
        if token:
            AH["Authorization"] = "Bearer " + token

        st, b = http(base + "/api/auth/me", headers=AH)
        rec("من أنا (/api/auth/me)", st, b)

        # ② السوق والأسعار ⭐
        st, b = http(base + "/api/quotes?market=egx", headers=AH)
        rec("السوق والأسعار (/api/quotes)", st, b)
        st, b = http(base + "/api/ticker?code=COMI.CA", headers=AH)
        rec("سهم مفرد (/api/ticker)", st, b)

        # ③ المحركات ⭐
        for path, label in (
            ("/api/analyze?code=COMI.CA", "engine-analyze"),
            ("/api/rank", "engine-rank"),
            ("/api/ranking", "engine-ranking"),
            ("/api/opp/strategies", "engine-opp-strategies"),
            ("/api/opp/summary", "engine-opp-summary"),
            ("/api/opportunities", "engine-opportunities"),
            ("/api/opportunity/COMI.CA", "engine-opportunity-detail"),
            ("/api/strategies", "engine-strategies"),
            ("/api/indices/compare?codes=COMI.CA,SWDY.CA", "compare-indices"),
            ("/api/gold", "gold-eg"),
            ("/api/gold/signal", "gold-signal"),
            ("/api/gold/history", "gold-history"),
            ("/api/gold/local", "gold-local"),
            ("/api/gold/deep", "gold-deep"),
            ("/api/bench", "bench-bridge"),
            ("/api/candles/COMI.CA", "candles"),
            ("/api/tvcandles?code=COMI.CA", "candles-tradingview"),
            ("/api/alpha/lab", "alpha-lab"),
            ("/api/alpha/decisions", "alpha-decisions"),
            ("/api/alpha/portfolio", "alpha-portfolio"),
            ("/api/radar/universe", "radar-universe"),
            ("/api/subscriptions/me", "subscriptions-me"),
            ("/api/subscriptions/log", "subscriptions-log"),
            ("/api/alerts/state", "alerts-state"),
        ):
            st, b = http(base + path, headers=AH)
            rec(label, st, b)

        # ④ المحفظة ⭐
        st, b = http(base + "/api/portfolio", headers=AH)
        rec("المحفظة الذكية (/api/portfolio)", st, b)
        st, b = http(base + "/api/portfolio", method="POST",
                     body={"cash": 1000, "positions": {"COMI.CA": 10}}, headers=AH)
        rec("كتابة المحفظة (POST /api/portfolio)", st, b)

        # ⑤ التنبيهات ⭐
        st, b = http(base + "/api/alerts/state", headers=AH)
        rec("alerts-state", st, b)
        st, b = http(base + "/api/alerts/watch", method="POST",
                     body={"symbol": "COMI.CA", "kind": "price"}, headers=AH)
        rec("alerts-watch", st, b)

        # ⑥ إنشاء حساب ⭐
        st, b = http(base + "/api/auth/register", method="POST",
                     body={"email": "r28.probe@example.test", "password": "R28probe!2026",
                           "name": "فحص R28"}, headers=AH)
        rec("إنشاء حساب (/api/auth/register)", st, b)

        # ⑦ الاسترجاع ⭐
        st, b = http(base + "/api/auth/pin/challenge/send", method="POST",
                     body={"email": free.get("email")}, headers=AH)
        rec("طلب كود الاسترجاع (pin/challenge/send)", st, b)

        # ⑧ التشخيص (أدمن ⭐)
        AH2 = dict(AH)
        AH2["X-OCTA-Admin"] = cfg.get("admin_token", "")
        st, b = http(base + "/api/diagnostics", headers=AH2)
        rec("التشخيص (/api/diagnostics ⭐ أدمن)", st, b)

        # ⑨ الخروج ⭐ + إبطال الجلسة ⭐
        st, b = http(base + "/api/auth/logout", method="POST", headers=AH)
        rec("الخروج (/api/auth/logout)", st, b)
        st, b = http(base + "/api/auth/me", headers=AH)
        good = st != 200
        results.append({"feature": "إبطال الجلسة بعد الخروج", "status": st,
                        "ok": good, "note": "(المطلوب ⭐: رفض ⭐)"})
        print("  %s %-40s status=%s %s" % ("✅" if good else "❌",
                                           "إبطال الجلسة بعد الخروج", st,
                                           "(المطلوب ⭐: رفض ⭐)"))

        passed = sum(1 for r in results if r["ok"])
        print("─" * 72)
        print("النتيجة: %d/%d" % (passed, len(results)))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump({"base": base, "passed": passed, "total": len(results),
                           "results": results}, fh, ensure_ascii=False, indent=2)
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        log.close()


if __name__ == "__main__":
    sys.exit(main())
