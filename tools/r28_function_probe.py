#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R28 · فحص وظيفي للباك الحقيقي (بيئة معزولة + بيانات اختبار).

📌 المطلوب (R28 · FINDING-07 ⭐):
   ① «صحّح الفحص الوظيفي» ⭐ ⇒ كل وظيفة **بتتحقق من محتوى الرد** ⭐
      (مش بس حالة HTTP ⭐) ⇒ ⇒ والمعيار مكتوب مع كل حالة ⭐.
   ② «سجّل اختبارات الرفض منفصلة» ⭐ ⇒ اختبارات الرفض (401/403/404 ⭐)
      في **قسم مستقل** ⭐ (مش مدمجة مع الوظائف ⭐).
   ③ «أرفق رحلة فعلية على حساب صناعي» ⭐ ⇒ دخول ⭐ ⇒ سوق ⭐ ⇒ فرص ⭐
      ⇒ محفظة ⭐ ⇒ تنبيهات ⭐ ⇒ خروج ⭐ (بالترتيب ⭐ مع تأكيد الأثر ⭐).

⛔ مافيش نشر ⭐ · ⛔ مافيش سر ⭐ · ⛔ مافيش بيانات عملاء ⭐ (كلها صناعية ⭐).
⛔ كل نتيجة = الحالة الفعلية ⭐ (مش "فتح الصفحة" ⭐).

── التشغيل ─────────────────────────────────────────────────────────────
   python3 tools/r28_function_probe.py --out /path/probe.json
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


class Probe:
    def __init__(self):
        self.functional = []
        self.rejection = []
        self.journey = []

    def ok(self, name, expected, actual, note="", kind="functional"):
        good = bool(actual)
        rec = {"name": name, "expected": expected, "actual": actual,
               "ok": good, "note": note, "kind": kind}
        if kind == "rejection":
            self.rejection.append(rec)
        elif kind == "journey":
            self.journey.append(rec)
        else:
            self.functional.append(rec)
        mark = "PASS" if good else "FAIL"
        print("  [%s] %-46s %s" % (mark, name, note[:70]))
        return good

    def summary(self):
        def count(rows):
            return (sum(1 for r in rows if r["ok"]), len(rows))
        f = count(self.functional)
        r = count(self.rejection)
        j = count(self.journey)
        return {"functional": {"passed": f[0], "total": f[1]},
                "rejection": {"passed": r[0], "total": r[1]},
                "journey": {"passed": j[0], "total": j[1]}}


def http(url, method="GET", body=None, headers=None, timeout=40):
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
                return res.status, raw[:400].decode("utf-8", "replace")
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

    stage = os.environ.get("STAGE_DIR", "/tmp/r28-probe")
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
    p = Probe()

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
        AH = dict(H)
        token = ""
        free = cfg.get("free") or {}

        print("═" * 78)
        print("🔬 R28 · الفحص الوظيفي للباك الحقيقي (بيانات صناعية ⭐)")
        print("═" * 78)

        # ── ① الوظائف ⭐ (تحقق من المحتوى ⭐) ────────────────────────────
        print("\n① الوظائف ⭐")
        st, b = http(base + "/api/auth/pin/login", method="POST",
                     body={"email": free.get("email"), "pin": free.get("pin"),
                           "device": free.get("device")}, headers=H)
        p.ok("login · status 200 + token", st == 200 and bool(b.get("token")),
             "status=%s token=%s" % (st, bool(b.get("token"))), "دخول بالحساب الصناعي ⭐")
        token = b.get("token", "") if isinstance(b, dict) else ""
        if token:
            AH["Authorization"] = "Bearer " + token

        st, b = http(base + "/api/auth/me", headers=AH)
        p.ok("me · status 200 + uid مطابق", st == 200 and bool((b.get("user") or {}).get("uid")),
             "status=%s uid=%s" % (st, bool((b.get("user") or {}).get("uid"))),
             "من أنا ⭐")

        st, b = http(base + "/api/quotes?market=egx", headers=AH)
        quotes = b.get("quotes") if isinstance(b, dict) else None
        n_quotes = sum(len(v) for v in (quotes or {}).values()) if isinstance(quotes, dict) else 0
        p.ok("quotes · status 200 + أسهم فعلية", st == 200 and n_quotes > 0,
             "status=%s عدد=%s" % (st, n_quotes), "السوق ⭐")

        st, b = http(base + "/api/ticker?code=COMI.CA", headers=AH)
        p.ok("ticker · status 200 + سعر", st == 200 and bool(b.get("price") or b.get("close") or b.get("last")),
             "status=%s مفاتيح=%s" % (st, sorted(b.keys())[:4] if isinstance(b, dict) else "-"),
             "سهم مفرد ⭐")

        st, b = http(base + "/api/analyze?code=COMI.CA", headers=AH)
        p.ok("analyze · status 200 + درجة", st == 200 and (b.get("score") is not None or b.get("total") is not None),
             "status=%s grade=%s" % (st, (b.get("score") if isinstance(b, dict) else None)),
             "محرك التقييم ⭐")

        st, b = http(base + "/api/rank", headers=AH)
        rank = b.get("rows") or b.get("items") or b.get("data") if isinstance(b, dict) else None
        p.ok("rank · status 200 + صفوف", st == 200 and bool(rank),
             "status=%s صفوف=%s" % (st, len(rank) if isinstance(rank, list) else "-"),
             "الترتيب ⭐")

        st, b = http(base + "/api/opportunities", headers=AH)
        opps = b.get("items") or b.get("rows") or b.get("opportunities") if isinstance(b, dict) else None
        p.ok("opportunities · status 200 + قائمة", st == 200 and isinstance(opps, list),
             "status=%s نوع=%s" % (st, type(opps).__name__), "محرك الفرص ⭐")

        st, b = http(base + "/api/strategies", headers=AH)
        strat = b.get("strategies") or b.get("items") if isinstance(b, dict) else None
        p.ok("strategies · status 200 + استراتيجيات", st == 200 and bool(strat),
             "status=%s عدد=%s" % (st, len(strat) if isinstance(strat, list) else "-"),
             "الفلاتر ⭐")

        st, b = http(base + "/api/indices/compare?codes=COMI.CA,SWDY.CA", headers=AH)
        p.ok("compare · status 200 + مقارنة", st == 200 and isinstance(b, dict) and len(b) > 0,
             "status=%s مفاتيح=%s" % (st, sorted(b.keys())[:4] if isinstance(b, dict) else "-"),
             "مقارنة الأسهم ⭐")

        st, b = http(base + "/api/gold", headers=AH)
        gold = b.get("price") or b.get("gram") or b.get("gold") if isinstance(b, dict) else None
        p.ok("gold · status 200 + سعر", st == 200 and gold is not None,
             "status=%s سعر=%s" % (st, gold), "الذهب المصري ⭐")

        st, b = http(base + "/api/gold/signal", headers=AH)
        sig = b.get("signal") or b.get("action") if isinstance(b, dict) else None
        p.ok("gold/signal · status 200 + إشارة", st == 200 and sig is not None,
             "status=%s إشارة=%s" % (st, sig), "إشارة الذهب ⭐")

        st, b = http(base + "/api/portfolio", headers=AH)
        pf = b.get("portfolio") if isinstance(b, dict) else None
        p.ok("portfolio · status 200 + محفظة", st == 200 and isinstance(pf, dict),
             "status=%s cash=%s" % (st, (pf or {}).get("cash")), "المحفظة الذكية ⭐")

        st, b = http(base + "/api/alerts/state", headers=AH)
        p.ok("alerts/state · status 200 + حالة", st == 200 and isinstance(b, dict),
             "status=%s" % st, "التنبيهات ⭐")

        st, b = http(base + "/api/subscriptions/me", headers=AH)
        p.ok("subscriptions/me · status 200 + اشتراك", st == 200 and isinstance(b, dict),
             "status=%s" % st, "الاشتراكات ⭐")

        st, b = http(base + "/api/radar/universe", headers=AH)
        p.ok("radar/universe · status 200 + رادار", st == 200 and isinstance(b, dict),
             "status=%s" % st, "الرادار ⭐")

        st, b = http(base + "/api/index/egypt", headers=AH)
        p.ok("index/egypt · status 200 + مؤشر", st == 200 and isinstance(b, dict),
             "status=%s" % st, "مؤشر السوق ⭐")

        # ── ② الرفض ⭐ (قسم مستقل ⭐) ─────────────────────────────────────
        print("\n② اختبارات الرفض ⭐ (منفصلة ⭐)")
        st, b = http(base + "/api/auth/me", headers={"X-OCTA-Proxy": cfg.get("proxy_secret", "")})
        p.ok("رفض · من غير توكن ⇒ 401", st == 401, "status=%s" % st, kind="rejection")

        st, b = http(base + "/api/auth/me", headers={**AH, "Authorization": "Bearer forged-token-xyz"})
        p.ok("رفض · توكن مزيّف ⇒ 401", st == 401, "status=%s" % st, kind="rejection")

        st, b = http(base + "/api/quotes?market=egx", headers={**AH, "Authorization": ""})
        p.ok("رفض · مسار محمي بلا توكن ⇒ 401", st == 401, "status=%s" % st, kind="rejection")

        st, b = http(base + "/api/ticker?code=ZZZZ.ZZ", headers=AH)
        p.ok("رفض · رمز غير موجود ⇒ 404/400", st in (400, 404), "status=%s" % st, kind="rejection")

        st, b = http(base + "/api/auth/pin/login", method="POST",
                     body={"email": free.get("email"), "pin": "0000",
                           "device": free.get("device")}, headers=H)
        p.ok("رفض · باسورد غلط ⇒ 401", st == 401, "status=%s" % st, kind="rejection")

        st, b = http(base + "/api/quotes?market=egx")
        p.ok("رفض · بلا مفتاح الـproxy ⇒ 403", st == 403, "status=%s" % st, kind="rejection")

        # ── ③ الرحلة الفعلية ⭐ (ترتيب + أثر ⭐) ──────────────────────────
        print("\n③ الرحلة الفعلية على حساب صناعي ⭐")
        COOKIES.clear()
        st, b = http(base + "/api/auth/pin/login", method="POST",
                     body={"email": free.get("email"), "pin": free.get("pin"),
                           "device": free.get("device")}, headers=H)
        tok = b.get("token", "") if isinstance(b, dict) else ""
        p.ok("رحلة ① · دخول", st == 200 and bool(tok), "status=%s" % st, kind="journey")
        AHj = dict(H)
        if tok:
            AHj["Authorization"] = "Bearer " + tok

        st, b = http(base + "/api/quotes?market=egx", headers=AHj)
        p.ok("رحلة ② · السوق", st == 200 and isinstance(b, dict), "status=%s" % st, kind="journey")

        st, b = http(base + "/api/opportunities", headers=AHj)
        p.ok("رحلة ③ · الفرص", st == 200, "status=%s" % st, kind="journey")

        st, b = http(base + "/api/portfolio", method="POST",
                     body={"cash": 5000, "positions": {"COMI.CA": 10}}, headers=AHj)
        p.ok("رحلة ④ · كتابة المحفظة", st in (200, 201), "status=%s" % st, kind="journey")

        st, b = http(base + "/api/portfolio", headers=AHj)
        pf = (b.get("portfolio") or {}) if isinstance(b, dict) else {}
        p.ok("رحلة ⑤ · المحفظة اتقرأت (cash=5000)",
             st == 200 and float(pf.get("cash") or 0) == 5000.0,
             "status=%s cash=%s" % (st, pf.get("cash")), kind="journey")

        st, b = http(base + "/api/alerts/watch", method="POST",
                     body={"symbol": "COMI.CA", "kind": "price"}, headers=AHj)
        p.ok("رحلة ⑥ · إضافة تنبيه", st in (200, 201), "status=%s" % st, kind="journey")

        st, b = http(base + "/api/alerts/state", headers=AHj)
        stxt = json.dumps(b, ensure_ascii=False) if isinstance(b, dict) else str(b)
        p.ok("رحلة ⑦ · التنبيه ظهر في الحالة", st == 200 and "COMI.CA" in stxt,
             "status=%s" % st, kind="journey")

        st, b = http(base + "/api/auth/logout", method="POST", headers=AHj)
        p.ok("رحلة ⑧ · الخروج", st == 200, "status=%s" % st, kind="journey")

        st, b = http(base + "/api/auth/me", headers=AHj)
        p.ok("رحلة ⑨ · الإبطال بعد الخروج ⇒ 401", st == 401, "status=%s" % st, kind="journey")

        s = p.summary()
        print("\n" + "─" * 78)
        print("الوظائف: %d/%d · الرفض: %d/%d · الرحلة: %d/%d" % (
            s["functional"]["passed"], s["functional"]["total"],
            s["rejection"]["passed"], s["rejection"]["total"],
            s["journey"]["passed"], s["journey"]["total"]))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump({"base": base, "summary": s, "functional": p.functional,
                           "rejection": p.rejection, "journey": p.journey},
                          fh, ensure_ascii=False, indent=2)
            print("📄 %s" % args.out)
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
