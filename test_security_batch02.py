#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️🧪 دفعة الأمان ٠٢ — اختبارات على بيئة Staging المعزولة (١٥ نوفمبر ٢٠٢٦)

⛔⛔⛔ الفصل التام عن الإنتاج ⬇️ ⬇️
   ⛔ ⬇️ كل الطلبات على الـstaging (المتغيّر STAGE_URL) ⬇️ ⬇️
   ⛔ ⬇️ كل الحسابات وهمية (example.test) ⬇️ ⬇️
   ⛔ ⬇️ مافيش أي طلب على الإنتاج ⬇️ ⬇️
   ⛔ ⬇️ الإيميل = Mock (file outbox) ⬇️ ⬇️

شغّله:
   python3 test_security_batch02.py
"""
import os
import re
import sys
import json
import time
from pathlib import Path

import requests

# ══════════════════════════════════════════════════════════════════
#  ⛔ إعداد البيئة (مافيش أي production)
# ══════════════════════════════════════════════════════════════════
CFG = json.loads(Path(os.environ.get(
    "STAGE_CONFIG", "/workspace/.staging/staging-config.json")).read_text("utf-8"))
BASE = os.environ.get("STAGE_URL", "http://127.0.0.1:8099").rstrip("/")
PROXY = CFG["proxy_secret"]
OUTBOX = Path(CFG["data_dir"]) / "outbox.jsonl"

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


def post(path, body=None, headers=None, proxy=True):
    return requests.post(BASE + path, json=body or {}, headers=H(headers, proxy),
                          timeout=45)


def get(path, headers=None, proxy=True):
    return requests.get(BASE + path, headers=H(headers, proxy), timeout=45)


def mail_code(email, kind=None):
    """يستخرج الكود من صندوق الإيميل (Mock) — آخر رسالة."""
    try:
        lines = OUTBOX.read_text(encoding="utf-8").strip().split("\n")
    except Exception:
        return ""
    for ln in reversed(lines):
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("to") != email:
            continue
        if kind and kind not in (rec.get("subject") or ""):
            continue
        m = re.findall(r"([0-9]{6})", rec.get("html") or "")
        if m:
            return m[0]
    return ""


def bearer(tok):
    return {"Authorization": "Bearer " + tok}


# ══════════════════════════════════════════════════════════════════
def main():
    print("🛡️ دفعة الأمان ٠٢ — اختبارات Staging")
    print("   القاعدة: %s" % BASE)
    print("   ⛔ كل الحسابات وهمية · مافيش أي طلب على الإنتاج")

    # ─────────────────────────────────────────────────────────────
    section("١) إنشاء حساب وتأكيد البريد التجريبي")
    new_mail = "staging.new.%d@example.test" % int(time.time())
    r = post("/api/auth/signup/start", {"name": "حساب جديد", "email": new_mail})
    ok(r.status_code == 200, "signup/start رجّع 200", r.status_code)
    code = mail_code(new_mail, "كود تأكيد")
    ok(bool(code), "كود التأكيد وصل (من صندوق الإيميل Mock)")

    r = post("/api/auth/signup/verify", {"email": new_mail, "code": "000000"})
    ok(r.status_code == 401, "كود غلط ⇒ 401 (مش قبول)", r.status_code)

    r = post("/api/auth/signup/verify", {"email": new_mail, "code": code})
    ok(r.status_code == 200, "كود صح ⇒ 200", r.status_code)
    unlock = (r.json() or {}).get("unlock") or ""
    ok(bool(unlock), "رجع توكن فتح")

    # ⛔ PIN عشوائي كل مرة ⬇️ (الـstaging بيحفظ الحسابات ⬇️
    # ⛔ ⇒ PIN ثابت ⇒ «الباسورد ده مستخدم من قبل» ⇒ 409 ⬇️)
    import random as _rnd
    new_pin = "".join(str(_rnd.randint(0, 9)) for _ in range(4))
    r = post("/api/auth/signup/newpin", {"new_pin": new_pin},
             headers=bearer(unlock))
    ok(r.status_code == 200, "حساب جديد اتعمل بـPIN",
       "%s %s" % (r.status_code, (r.text or "")[:140]))
    new_tok = (r.json() or {}).get("token") or ""
    ok(bool(new_tok), "رجع توكن جلسة للحساب الجديد")

    # ─────────────────────────────────────────────────────────────
    section("٢) تسجيل الدخول الصحيح والخاطئ")
    free = CFG["free"]
    r = post("/api/auth/pin/login", {"pin": free["pin"], "device": free["device"]})
    ok(r.status_code == 200, "دخول Free بالرقم ⇒ 200", r.status_code)
    free_tok = (r.json() or {}).get("token") or ""
    ok(bool(free_tok), "رجع توكن Free")

    r = post("/api/auth/pin/login", {"pin": "9999", "device": free["device"]})
    ok(r.status_code in (401, 429), "رقم غلط ⇒ 401/429 (مش 200)", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٣) تغيير PIN ⇒ إبطال التوكنات القديمة")
    r = post("/api/auth/pin/change", {"old_pin": free["pin"], "new_pin": "1357"},
             headers=bearer(free_tok))
    ok(r.status_code == 200, "تغيير PIN نجح", r.status_code)
    body = r.json() or {}
    ok(body.get("sessions_revoked") is True, "sessions_revoked=true")
    new_free_tok = body.get("token") or ""
    r = get("/api/auth/me", headers=bearer(free_tok))
    ok(r.status_code == 401, "⛔ التوكن القديم مات", r.status_code)
    r = get("/api/auth/me", headers=bearer(new_free_tok))
    ok(r.status_code == 200, "التوكن الجديد شغّال", r.status_code)
    # رجّع الرقم
    post("/api/auth/pin/change", {"old_pin": "1357", "new_pin": free["pin"]},
         headers=bearer(new_free_tok))

    # ─────────────────────────────────────────────────────────────
    section("٤) ⛔ تسجيل الخروج — الاختبار الإلزامي (كوكي بس)")
    # ⛔ تسجيل الخروج بكوكي بس (زي reset.html لما الـlocalStorage ضاع)
    r = post("/api/auth/pin/login", {"pin": free["pin"], "device": free["device"]})
    tok_cookie = (r.json() or {}).get("token") or ""
    # ⛔ نرسل الطلب **من غير** Bearer — كوكي بس (بـcookies من المتصفح)
    # ⛔ نطاق الكوكي لازم يطابق **المضيف الفعلي** ⬇️
    # ⛔ (127.0.0.1 محلياً · والنطاق الحقيقي عبر النفق) ⬇️
    from urllib.parse import urlparse
    _host = urlparse(BASE).hostname or "127.0.0.1"
    s = requests.Session()
    s.cookies.set("octa_token", tok_cookie, domain=_host, path="/")
    r = s.post(BASE + "/api/auth/logout", headers={"X-OCTA-Proxy": PROXY},
               timeout=45)
    ok(r.status_code == 200, "الخروج بكوكي بس ⇒ 200 (مش 401)",
       "%s %s" % (r.status_code, r.text[:120]))
    ok((r.json() or {}).get("revoked") is True, "revoked=true ⇒ إبطال فعلي")
    r = get("/api/auth/me", headers=bearer(tok_cookie))
    ok(r.status_code == 401, "⛔ الجلسة القديمة صارت غير صالحة على السيرفر",
       r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٤أ) ⛔ ارتداد: دخول وخروج في نفس الثانية")
    # 🐞 🐞 🐞 السبب: الإبطال كان `int(time.time())*1000` (دقّة ثانية)
    # ⇒ لو الدخول والخروج في نفس الثانية ⇒ الـepoch ما بيتغيّرش
    # ⇒ ⇒ التوكن_old فضل صالح ⇒ «خرج» وهو داخل.
    race_bad = 0
    for _i in range(3):
        rr = post("/api/auth/pin/login", {"pin": free["pin"],
                                          "device": free["device"]})
        tk = (rr.json() or {}).get("token") or ""
        post("/api/auth/logout", headers=bearer(tk))
        chk = get("/api/auth/me", headers=bearer(tk))
        if chk.status_code != 401:
            race_bad += 1
    ok(race_bad == 0, "⛔ دخول/خروج سريع ⇒ التوكن بيموت دايماً",
       "%d من 3 فضلوا صالحين" % race_bad)

    # ─────────────────────────────────────────────────────────────
    section("٤ب) الخروج بتوكن منتهى ⇒ لازم يبطّل برضه")
    r = post("/api/auth/pin/login", {"pin": free["pin"], "device": free["device"]})
    tok_x = (r.json() or {}).get("token") or ""
    r = post("/api/auth/logout", headers=bearer(tok_x))
    ok(r.status_code == 200, "خروج بتوكن صالح ⇒ 200", r.status_code)
    r = get("/api/auth/me", headers=bearer(tok_x))
    ok(r.status_code == 401, "⛔ التوكن مات بعد الخروج", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٥) انتهاء الجلسة (الخمول) + التجديد")
    r = post("/api/auth/pin/login", {"pin": free["pin"], "device": free["device"]})
    tok_idle = (r.json() or {}).get("token") or ""
    r = get("/api/auth/me", headers=bearer(tok_idle))
    ok(r.status_code == 200, "الجلسة شغّالة")
    r = post("/api/auth/refresh", headers=bearer(tok_idle))
    ok(r.status_code in (200, 401), "التجديد رجّع حالة متوقعة", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٦) ⛔ البصمة بمفتاح جهاز منسوخ ⇒ مش دخول مستقل")
    r = post("/api/auth/pin/fingerprint", {"device": free["device"]})
    ok(r.status_code == 410, "البصمة مقفولة ⇒ 410", r.status_code)
    ok((r.json() or {}).get("why") == "fingerprint_disabled",
       "السبب fingerprint_disabled")
    r = post("/api/auth/pin/fingerprint", {"device": CFG["pro"]["device"]})
    ok(r.status_code == 410, "مفتاح جهاز حساب تاني ⇒ 410 برضه", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٧) ⛔ تخمين كود الاسترجاع + حدود المحاولات")
    # ⛔ ملاحظة: الكود **مش** بيتبعت لعنوان غير مسجّل (تصميم ضد
    # ⛔ كشف الحسابات) ⇒ لازم نستخدم عنوان الحساب نفسه
    chal_mail = free["email"]
    r = post("/api/auth/pin/challenge/send", {"email": chal_mail})
    ok(r.status_code == 200, "طلب كود استرجاع اتقبل", r.status_code)
    ccode = mail_code(chal_mail)
    ok(bool(ccode), "كود الاسترجاع وصل")
    seen = []
    for i in range(8):
        rr = post("/api/auth/pin/challenge/verify",
                  {"email": chal_mail, "code": "000000"})
        seen.append(rr.status_code)
        if rr.status_code == 429:
            break
    ok(429 in seen or seen.count(401) >= 5,
       "⛔ التخمين اتوقف (حد المحاولات)", seen)

    # ─────────────────────────────────────────────────────────────
    section("٨) ⛔ الوصول المباشر للـBackend بدون سر ⇒ مرفوض")
    r = requests.get(BASE + "/api/quotes", timeout=45)
    ok(r.status_code == 403, "بدون X-OCTA-Proxy ⇒ 403", r.status_code)
    r = requests.get(BASE + "/api/health", timeout=45)
    ok(r.status_code == 403, "حتى الـhealth بدون سر ⇒ 403", r.status_code)
    r = get("/api/quotes")
    ok(r.status_code == 200, "بالسر ⇒ 200", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("٩) ⛔ عزل البيانات بين الحسابات")
    r = post("/api/auth/pin/login", {"pin": free["pin"], "device": free["device"]})
    tok_free = (r.json() or {}).get("token") or ""
    r = post("/api/auth/pin/login", {"pin": CFG["pro"]["pin"],
                                     "device": CFG["pro"]["device"]})
    tok_pro = (r.json() or {}).get("token") or ""
    ok(bool(tok_free) and bool(tok_pro), "دخول Free و Pro")

    r = post("/api/portfolio", {"action": "add", "code": "COMI", "shares": 5,
                                "cost": 100, "price": 100},
             headers=bearer(tok_free))
    ok(r.status_code == 200, "إضافة حصة لـFree", r.status_code)
    r = get("/api/portfolio", headers=bearer(tok_pro))
    holdings = (r.json() or {}).get("holdings") or {}
    ok(not holdings.get("COMI"), "⛔ Pro ماشوفش حصة Free", holdings)

    r = get("/api/alerts/watch", headers=bearer(tok_free))
    ok(r.status_code == 200, "منبهات Free بتترجّع", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("١٠) ⛔ مستخدم Free ⇒ واجهات Pro مقفولة")
    pro_paths = ["/api/studio/list", "/api/setups", "/api/challenges/today",
                 "/api/zones"]
    blocked = 0
    for p in pro_paths:
        rr = get(p, headers=bearer(tok_free))
        if rr.status_code in (403, 401):
            blocked += 1
    ok(blocked >= 2, "⛔ Free مرفوض من مسارات Pro",
       "%d/%d" % (blocked, len(pro_paths)))

    # ─────────────────────────────────────────────────────────────
    section("١١) ⛔ مسارات الإدارة والتشخيص ⇒ للأدمن بس")
    for p in ["/api/admin/users", "/api/admin/monthly", "/api/diagnostic",
              "/api/ai-status", "/api/audit/redundancy"]:
        rr = get(p, headers=bearer(tok_free))
        ok(rr.status_code in (401, 403, 503),
           "%s ⇒ مرفوض للمستخدم العادي" % p, rr.status_code)

    # ─────────────────────────────────────────────────────────────
    section("١٢) ⛔ CSRF — الكتابة بال��وكي بس ⇒ مرفوض")
    r = requests.post(BASE + "/api/portfolio",
                      json={"action": "add", "code": "COMI", "shares": 1,
                            "cost": 1, "price": 1},
                      headers={"X-OCTA-Proxy": PROXY,
                               "Cookie": "octa_token=" + tok_free},
                      timeout=45)
    ok(r.status_code == 401, "⛔ POST بكوكي بس ⇒ 401 (CSRF مقفول)", r.status_code)
    r = post("/api/portfolio", {"action": "add", "code": "COMI", "shares": 1,
                                "cost": 1, "price": 1},
             headers=bearer(tok_free))
    ok(r.status_code == 200, "✅ POST بـBearer شغّال", r.status_code)

    # ─────────────────────────────────────────────────────────────
    section("١٣) صفحة السوق العامة شغالة")
    for p in ["/api/quotes", "/api/prices", "/api/health"]:
        rr = get(p)
        ok(rr.status_code == 200, "%s ⇒ 200" % p, rr.status_code)

    # ─────────────────────────────────────────────────────────────
    section("١٤) بيانات الأسهم والشارت والذهب")
    rr = get("/api/quotes?market=egypt")
    ok(rr.status_code == 200, "الأسعار سليمة", rr.status_code)
    q = (rr.json() or {}).get("markets") or {}
    ok(bool(q), "في أسواق في الرد")
    # ⛔ المسار محتاج ?date=YYYY-MM-DD ⬇️ (من غيرها ⇒ 400 ⬇️)
    rr = get("/api/gold/gram", headers=bearer(tok_free))
    ok(rr.status_code == 400, "⛔ الذهب من غير تاريخ ⇒ 400 (المطلوب تاريخ)",
       rr.status_code)
    rr = get("/api/gold/gram?date=2026-11-10", headers=bearer(tok_free))
    ok(rr.status_code in (200, 404, 502),
       "الذهب بتاريخ ⇒ حالة متوقعة (بيانات حيّة/سلسلة)", rr.status_code)
    rr = get("/api/gold/gram")
    ok(rr.status_code in (401, 403), "⛔ الذهب من غير جلسة ⇒ مرفوض",
       rr.status_code)
    rr = get("/api/charts/list", headers=bearer(tok_free))
    ok(rr.status_code in (200, 401, 403), "الشارت بيرد بحالة متوقعة",
       rr.status_code)

    # ─────────────────────────────────────────────────────────────
    section("١٥) ⛔ مافيش بيانات إنتاج حقيقية في الـstaging")
    ddir = Path(CFG["data_dir"])
    users_file = ddir / "users.json"
    raw = users_file.read_text(encoding="utf-8") if users_file.exists() else "{}"
    try:
        users = json.loads(raw)
    except Exception:
        users = {}
    mails = [str((u or {}).get("email") or "") for u in users.values()]
    bad = [m for m in mails if m and not m.endswith("example.test")]
    ok(not bad, "⛔ مافيش إيميل حقيقي في users.json", bad)
    ok(len(users) <= 10, "عدد الحسابات صغير (وهمي)", len(users))
    subs = ddir / "subscriptions.json"
    if subs.exists():
        sraw = subs.read_text(encoding="utf-8")
        ok("octashares.com" not in sraw and "@gmail" not in sraw,
           "مافيش بريد حقيقي في سجل الاشتراكات")
    else:
        ok(True, "مافيش سجل اشتراكات (السجل فاضي)")

    # ─────────────────────────────────────────────────────────────
    section("§٧ إضافيات — جلسة الأدمن + انتهاء Pro + مسارات الاختبار")
    # ⛔ جلسة الأدمن ١٠ دقايق ⇒ ما تنتجش كوكي ٣٠ يوم
    admin_tok = os.environ.get("STAGE_ADMIN_TOKEN", "")
    if admin_tok:
        r = post("/api/admin/mint_session", {"email": CFG["pro"]["email"]},
                 headers={"X-OCTA-Admin": admin_tok})
        ok(r.status_code == 200, "mint_session اشتغل", r.status_code)
        setc = r.headers.get("Set-Cookie") or ""
        mt = re.search(r"Max-Age=(\d+)", setc)
        ok(bool(mt) and int(mt.group(1)) <= 900,
           "⛔ كوكي الأدمن مدته ≤ ١٥ دقيقة (مش ٣٠ يوم)", setc[:120])
        bt = (r.json() or {}).get("token") or ""
        ok(bool(bt), "رجع توكن تشخيص")
    else:
        ok(False, "STAGE_ADMIN_TOKEN مش متظبطلosh ⇒ تعذّر فحص جلسة الأدمن")

    # ⛔ Pro منتهي ⇒ مافيش تفعيل
    exp = CFG["expired_pro"]
    r = post("/api/auth/pin/login", {"pin": exp["pin"], "device": exp["device"]})
    exp_tok = (r.json() or {}).get("token") or ""
    ok(bool(exp_tok), "دخول الحساب المنتهي (Pro منتهي)")
    if exp_tok:
        blocked2 = 0
        for p in ["/api/studio/list", "/api/setups"]:
            rr = get(p, headers=bearer(exp_tok))
            if rr.status_code in (403, 401):
                blocked2 += 1
        ok(blocked2 >= 1, "⛔ Pro منتهي مابيفتحش واجهات Pro", blocked2)

    # ⛔ مسارات الاختبار التاريخي اللي بتغيّر بيانات
    for p in ["/api/alerts/test", "/api/backtest/snapshot"]:
        rr = get(p)
        ok(rr.status_code in (401, 403, 503),
           "%s ⇒ مرفوض بلا صلاحية" % p, rr.status_code)

    # ─────────────────────────────────────────────────────────────
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
