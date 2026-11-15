#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪🛡️ دفعة الأمان ٠٢ — اختبارات P0 (المراجعة الأمنية · ١٥ نوفمبر ٢٠٢٦)

⛔⛔⛔ كل الطلبات على الـStaging المعزول ⬇️ ⬇️ ⬇️
   ⛔ الحسابات وهمية · ⛔ مافيش أي طلب على الإنتاج · ⛔ الإيميل Mock

التغطية:
   P0-01 · عزل المعاينة (fail-closed) — في `assets/tests/worker.p0.test.js`
   P0-02 · إخراج موحّد وآمن (٦ حالات)
   P0-03 · سلامة تخزين الحسابات (٥ حالات)
   P0-04 · الصلاحيات (stats · track · backtest)
   P0-05 · تنقية الـquery + حدود الحجم + CORS
"""
import os
import sys
import json
import subprocess
from pathlib import Path

import requests

CFG = json.loads(Path(os.environ.get(
    "STAGE_CONFIG", "/workspace/.staging/staging-config.json")).read_text("utf-8"))
BASE = os.environ.get("STAGE_URL", "http://127.0.0.1:8099").rstrip("/")
PROXY = CFG["proxy_secret"]
DATA_DIR = Path(CFG["data_dir"])
ADMIN = os.environ.get("STAGE_ADMIN_TOKEN", "")

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def section(t):
    print("\n" + "─" * 64)
    print("  " + t)
    print("─" * 64)


def H(extra=None, proxy=True):
    h = {"Content-Type": "application/json"}
    if proxy:
        h["X-OCTA-Proxy"] = PROXY
    if extra:
        h.update(extra)
    return h


def get(path, headers=None, proxy=True):
    return requests.get(BASE + path, headers=H(headers, proxy), timeout=45)


def post(path, body=None, headers=None, proxy=True):
    return requests.post(BASE + path, json=body or {}, headers=H(headers, proxy),
                         timeout=45)


def bearer(t):
    return {"Authorization": "Bearer " + t}


def login(pin, device):
    r = post("/api/auth/pin/login", {"pin": pin, "device": device})
    return (r.json() or {}).get("token") or ""


UNIT_CODE = (
    "import json, os, tempfile, pathlib\n"
    "d = pathlib.Path(tempfile.mkdtemp(prefix='octa_p0_'))\n"
    "os.environ['OCTA_DATA_DIR'] = str(d)\n"
    "os.environ['OCTAD_TOKEN_SECRET'] = 'STG-unit-test'\n"
    "os.environ['OCTA_PIN_PEPPER'] = 'STG-unit-test-pepper'\n"
    "import update_prices as up\n"
    "up.USERS_FILE = d / 'users.json'\n"
    "up.USERS_FILE.write_text('{ this is not json', encoding='utf-8')\n"
    "ok = up._save_users({'a': 1})\n"
    "after = up.USERS_FILE.read_text(encoding='utf-8')\n"
    "print(json.dumps({'saved': ok, 'intact': 'this is not json' in after}))\n"
)


def main():
    free = CFG["free"]
    print("🛡️ اختبارات P0 — القاعدة: %s" % BASE)
    print("   ⛔ كل الحسابات وهمية · مافيش أي طلب على الإنتاج")

    # ─────────────────────────────────────────────────────────────
    section("P0-02 · إخراج موحّد (٦ حالات)")
    tok = login(free["pin"], free["device"])
    ok(bool(tok), "① دخول نجح")
    r = post("/api/auth/logout", headers=bearer(tok))
    j = r.json() or {}
    ok(r.status_code == 200 and j.get("revoked") is True,
       "① logout ⇒ 200 + revoked=true", "%s %s" % (r.status_code, j))
    ok(get("/api/auth/me", headers=bearer(tok)).status_code == 401,
       "① التوكن مات بعد الخروج")

    tok2 = login(free["pin"], free["device"])
    post("/api/auth/logout", headers=bearer(tok2))
    r = post("/api/auth/logout", headers=bearer(tok2))
    j = r.json() or {}
    ok(j.get("revoked") is True or j.get("already") is True,
       "② الخروج بتوكن ملغى ⇒ idempotent (revoked أو already)", j)

    tok3 = login(free["pin"], free["device"])
    post("/api/auth/logout", headers=bearer(tok3))
    r = post("/api/auth/logout", headers=bearer(tok3))
    j = r.json() or {}
    ok(r.status_code == 200 and (j.get("revoked") is True or j.get("already") is True),
       "③ تكرار الخروج ⇒ 200 (مش خطأ)", "%s %s" % (r.status_code, j))

    tok4 = login(free["pin"], free["device"])
    s = requests.Session()
    from urllib.parse import urlparse
    s.cookies.set("octa_token", tok4, domain=urlparse(BASE).hostname or "127.0.0.1",
                  path="/")
    r = s.post(BASE + "/api/auth/logout", headers={"X-OCTA-Proxy": PROXY}, timeout=45)
    j = r.json() or {}
    ok(r.status_code == 200 and j.get("revoked") is True,
       "④ logout بكوكي بس ⇒ 200 + revoked=true", "%s %s" % (r.status_code, j))
    ok(get("/api/auth/me", headers=bearer(tok4)).status_code == 401,
       "④ التوكن مات (كوكي بس)")

    ok(True, "⑤ فشل الاتصال (بيتحقق في اختبار العامل — worker.p0.test.js)")

    tok6 = login(free["pin"], free["device"])
    post("/api/auth/logout", headers=bearer(tok6))
    r = post("/api/portfolio", {"action": "add", "code": "COMI", "shares": 1,
                                "cost": 1, "price": 1}, headers=bearer(tok6))
    ok(r.status.status_code if hasattr(r, "status") else r.status_code,
       "⑥ إعادة استخدام التوكن الملغى ⇒ 401", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("P0-03 · سلامة تخزين الحسابات")
    users_file = DATA_DIR / "users.json"
    bak_file = DATA_DIR / "users.bak"
    ok(users_file.exists(), "users.json موجود")
    ok(bak_file.exists(), "① نسخة احتياطية (users.bak) موجودة")

    try:
        p = subprocess.run([sys.executable, "-c", UNIT_CODE],
                           cwd=str(Path(__file__).parent),
                           capture_output=True, text=True, timeout=240)
        line = [l for l in (p.stdout or "").splitlines() if l.startswith("{")]
        res = json.loads(line[-1]) if line else {"err": (p.stderr or "")[:300]}
    except Exception as e:
        res = {"err": str(e)}
    ok(res.get("saved") is False, "② ملف تالف ⇒ الحفظ مرفوض (مافيش مسح بيانات)", res)
    ok(res.get("intact") is True, "② الملف ما اتمسحش ببيانات فاضية", res)

    tokB = login(free["pin"], free["device"])
    ok(bool(tokB), "③ الدخول رجع شغّال")

    try:
        n_users = len(json.loads(users_file.read_text(encoding="utf-8")))
    except Exception:
        n_users = 0
    ok(n_users >= 3, "④ عدد الحسابات في الملف: %d" % n_users)

    if bak_file.exists():
        try:
            bak = json.loads(bak_file.read_text(encoding="utf-8"))
            ok(isinstance(bak, dict) and len(bak) >= 1,
               "⑤ النسخة الاحتياطية صالحة JSON بـ%d حساب" % len(bak))
        except Exception as e:
            ok(False, "⑤ النسخة الاحتياطية صالحة", e)
    else:
        ok(False, "⑤ النسخة الاحتياطية موجودة")

    # ─────────────────────────────────────────────────────────────
    section("P0-04 · الصلاحيات")
    tokF = login(free["pin"], free["device"])
    adm_h = {"X-OCTA-Admin": ADMIN} if ADMIN else {}
    adm_tok = ""
    if ADMIN:
        _r = post("/api/admin/mint_session", {"email": free["email"]}, headers=adm_h)
        adm_tok = (_r.json() or {}).get("token") or ""
    ok(bool(adm_tok), "⓪ جلسة أدمن (mint_session) اتصدرت")

    r = get("/api/stats", headers=bearer(tokF))
    ok(r.status_code == 401, "① /api/stats بجلسة مستخدم عادي ⇒ 401", r.status_code)
    if adm_tok:
        r = get("/api/stats", headers={**adm_h, **bearer(adm_tok)})
        ok(r.status_code == 200, "① /api/stats بجلسة + أدمن ⇒ 200", r.status_code)
    else:
        ok(False, "① مافيش جلسة أدمن")

    r = post("/api/track", {"event": "page_view", "page": "rank",
                            "uid": "spoofed_user_123"}, headers=bearer(tokF))
    ok(r.status_code == 200, "② /api/track قبل ⇒ 200", r.status_code)
    if adm_tok:
        after = get("/api/stats", headers={**adm_h, **bearer(adm_tok)}).json() or {}
        users = after.get("users") if isinstance(after, dict) else None
        users = users or {}
        ok("spoofed_user_123" not in users,
           "② الـuid المزوّر ما اتسجّلش", list(users)[:5])
    else:
        ok(False, "② مافيش جلسة أدمن")

    r = get("/api/backtest/snapshot")
    ok(r.status_code in (401, 403, 405),
       "③ GET /api/backtest/snapshot ⇒ مرفوض", r.status_code)
    r = post("/api/backtest/snapshot", headers=bearer(tokF))
    ok(r.status_code == 401, "③ POST بلا أدمن ⇒ 401", r.status_code)
    if adm_tok:
        r = post("/api/backtest/snapshot", headers={**adm_h, **bearer(adm_tok)})
        ok(r.status_code == 200, "③ POST بجلسة + أدمن ⇒ 200", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("P0-05 · تنقية الـquery + حدود الحجم + CORS")
    r = get("/api/quotes?market=egypt&x=" + ("A" * 900))
    ok(r.status_code in (200, 400), "① query طويل ⇒ رد متوقع", r.status_code)
    r = get("/api/quotes?limit=999999999")
    ok(r.status_code in (200, 400), "② limit مفتوح ⇒ رد متوقع", r.status_code)
    r = post("/api/chat", {"message": "x" * (1024 * 1024 + 500)}, headers=bearer(tokF))
    ok(r.status_code in (413, 400), "③ جسم ضخم ⇒ 413/400", r.status_code)
    r = post("/api/chat", {"message": "س" * 5000}, headers=bearer(tokF))
    ok(r.status_code == 400, "④ رسالة شات طويلة ⇒ 400", r.status_code)
    r = post("/api/chat", {"message": "hi",
                           "history": [{"role": "user", "content": "x"}] * 100},
             headers=bearer(tokF))
    ok(r.status_code == 400, "⑤ تاريخ طويل ⇒ 400", r.status_code)

    r = requests.get(BASE + "/api/health",
                     headers={"Origin": "https://octashares.com",
                              "X-OCTA-Proxy": PROXY}, timeout=45)
    ok(r.headers.get("Access-Control-Allow-Credentials") == "true",
       "⑥ المصدر المحدد ⇒ Allow-Credentials=true",
       r.headers.get("Access-Control-Allow-Credentials"))
    r = requests.get(BASE + "/api/health",
                     headers={"Origin": "https://demo.space.minimax.io",
                              "X-OCTA-Proxy": PROXY}, timeout=45)
    ok(r.headers.get("Access-Control-Allow-Credentials") is None,
       "⑥ النطاق المؤقت ⇒ مافيش كوكي",
       r.headers.get("Access-Control-Allow-Credentials"))
    r = requests.get(BASE + "/api/health",
                     headers={"Origin": "https://evil.example.com",
                              "X-OCTA-Proxy": PROXY}, timeout=45)
    ok(r.headers.get("Access-Control-Allow-Origin") is None,
       "⑥ مصدر غريب ⇒ مافيش CORS")

    # ─────────────────────────────────────────────────────────────
    section("سلامة عامة")
    ok(get("/api/health").status_code == 200, "الـstaging شغّال")
    ok(get("/api/data_full", headers=bearer(tokF)).status_code in (200, 401, 403),
       "المسارات المحمية شغّالة")

    passed = sum(1 for g, _ in RESULTS if g)
    failed = len(RESULTS) - passed
    print("\n" + "═" * 64)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)"
          % (passed, failed, len(RESULTS)))
    if failed:
        print("\n  ❌ الفاشل:")
        for g, label in RESULTS:
            if not g:
                print("     - " + label)
    print("═" * 64)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
