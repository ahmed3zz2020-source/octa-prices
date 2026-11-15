#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️🧪 دفعة الأمان ٠١ — اختبارات تلقائية قابلة للتكرار (OCTA)

⛔⛔⛔ العزل — كل حاجة في الملف ده في مجلد مؤقت ⬇️
   ⛔ ⬇️ مافيش بيانات مستخدمين حقيقية ⬇️ ⬇️
   ⛔ ⬇️ مافيش أسرار إنتاج ⬇️ ⬇️ (أسرار اختبار محلية فقط) ⬇️ ⬇️
   ⛔ ⬇️ مافيش أي طلب على الإنتاج ⬇️ ⬇️
   ⛔ ⬇️ Flask حقيقي (test_client) ⬇️ ⬇️

شغّله:
    python3 test_security_batch01.py
أو مع pytest:
    pytest -q test_security_batch01.py
"""
import os
import sys
import json
import time
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_sec01_")
sys.path.insert(0, HERE)

# ══════════════════════════════════════════════════════════════════
#  ⛔⛔⛔ العزل — قبل استيراد الباك ⬇️ ⬇️ ⬇️
# ══════════════════════════════════════════════════════════════════
os.environ["OCTA_DATA_DIR"] = TMP                  # ⛔ كل الملفات في tmp
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-sec01-secret"   # ⛔ اختبار بس
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-sec01-pepper"     # ⛔ اختبار بس
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"   # ⛔ سياسة deny-by-default شغّالة
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"  # ⛔ البصمة مقفولة (الوضع الآمن)
os.environ["MAIL_ON"] = "0"

import update_prices as up  # noqa: E402

# ⛔ كل ملفات التخزين على القرص ⇒ جوه المجلد المؤقت ⬇️
from pathlib import Path  # noqa: E402
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"
up.MAIL_ON = True             # ⛔ خدمة الإيميل "شغالة" ⬇️ (المُمسك sends)

# ⛔ الإيميل: بنمسكه بدل ما يتبعت ⬇️ (مش إيميل حقيقي)
MAILS = []


def _fake_send(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _fake_send

# ⛔ قواعد القفل في الاختبار (مش Production)
up.PIN_FAIL_LIMIT = 4
up.PIN_LOCK_FIRST = 900
up.PIN_LOCK_NEXT = 3600

# ══════════════════════════════════════════════════════════════════
#  🧰 أدوات
# ══════════════════════════════════════════════════════════════════
RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label, extra))
    print(("  ✅ " if cond else "  ❌ ") + label + (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def section(name):
    print("\n" + "═" * 66)
    print("  " + name)
    print("═" * 66)


DEV1 = "a" * 64      # ⛔ مفتاح جهاز (نسخته = ٦٤ حرف hex)
DEV2 = "b" * 64
PIN1 = "1234"
PIN2 = "4321"
MAIL1 = "sec01.user.one@example.test"
MAIL2 = "sec01.user.two@example.test"


def mk_user(uid, email, pin, dev, name="مستخدم اختبار"):
    """ينشئ مستخدم بحساب/رقم/جهاز جاهزين (في البيئة المعزولة)."""
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(dev)
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = {
            "id": uid, "name": name, "email": email,
            "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
            "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
            "token_epoch": 0, "created": int(time.time()),
            "bio_hash": dev_hash, "bio_hashes": [dev_hash],
            "portfolio": {"holdings": {}, "cash": 0},
            "watch": {},
        }
        up._save_users(users)
    return uid


def login(client, pin, dev):
    r = client.post("/api/auth/pin/login",
                    json={"pin": pin, "device": dev},
                    headers={"X-Forwarded-For": "10.0.0.1"})
    return r


def auth(tok):
    return {"Authorization": "Bearer " + tok}


def code_from_mail():
    """يستخرج الكود من نص الإيميل المرسول (للاختبار فقط)."""
    if not MAILS:
        return ""
    html = MAILS[-1]["html"]
    import re
    m = re.findall(r"letter-spacing:10px[^>]*>([0-9]{6})<", html)
    return m[0] if m else ""


# ══════════════════════════════════════════════════════════════════
#  ٠١ — رفض الوصول بدون جلسة / بكوكي مزيفة / بتوكن منتهية
# ══════════════════════════════════════════════════════════════════
section("٠١ — رفض الوصول بدون جلسة / كوكي مزيفة / توكن منتهية")
client = up.app.test_client()

uid1 = mk_user("u_sec01_one", MAIL1, PIN1, DEV1)
uid2 = mk_user("u_sec01_two", MAIL2, PIN2, DEV2)

r = client.get("/api/data_full")
ok(r.status_code == 401, "بدون أي جلسة ⇒ 401 على مسار محمي",
   "status=%s" % r.status_code)

r = client.get("/api/data_full", headers={"Cookie": "octa_token=forged.token"})
ok(r.status_code == 401, "كوكي مزيف ⇒ 401",
   "status=%s" % r.status_code)

r = client.get("/api/data_full",
               headers={"Authorization": "Bearer forged.forged"})
ok(r.status_code == 401, "توكن مزيف ⇒ 401",
   "status=%s" % r.status_code)

exp_tok = up._make_token(uid1, ttl=-60)
r = client.get("/api/auth/me", headers=auth(exp_tok))
ok(r.status_code == 401, "توكن منتهي ⇒ 401",
   "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ٠٢ — المسارات العامة لازم تفضل شغالة بلا جلسة
# ══════════════════════════════════════════════════════════════════
section("٠٢ — صفحة السوق العامة شغالة بلا جلسة (منع تراجع)")
for p in ("/api/quotes", "/api/health", "/api/prices"):
    r = client.get(p)
    ok(r.status_code == 200, "%s ⇒ 200 بلا جلسة" % p,
       "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ٠٣ — إبطال التوكنات بعد تغيير الـPIN
# ══════════════════════════════════════════════════════════════════
section("٠٣ — تغيير الـPIN ⇒ إبطال كل الجلسات القديمة")
r = login(client, PIN1, DEV1)
ok(r.status_code == 200, "دخول بالرقم نجح", "status=%s" % r.status_code)
tok1 = (r.get_json() or {}).get("token") or ""
ok(bool(tok1), "رجع توكن جلسة")

r = client.get("/api/auth/me", headers=auth(tok1))
ok(r.status_code == 200, "التوكن القديم شغّال قبل التغيير",
   "status=%s" % r.status_code)

r = client.post("/api/auth/pin/change",
                json={"old_pin": PIN1, "new_pin": "9999"},
                headers=auth(tok1))
ok(r.status_code == 200, "تغيير الـPIN نجح", "status=%s" % r.status_code)
body = r.get_json() or {}
ok(body.get("sessions_revoked") is True,
   "الرد فيه sessions_revoked=true")
new_tok = body.get("token") or ""
ok(bool(new_tok), "الرد فيه توكن جديد")

r = client.get("/api/auth/me", headers=auth(tok1))
ok(r.status_code == 401, "⛔ التوكن القديم **مات** بعد تغيير الـPIN",
   "status=%s" % r.status_code)

if new_tok:
    r = client.get("/api/auth/me", headers=auth(new_tok))
    ok(r.status_code == 200, "التوكن الجديد شغّال",
       "status=%s" % r.status_code)

# ⛔ نرجّع الرقم للوضع الأصلي عشان باقي الاختبارات
with up.USERS_LOCK:
    _u = up._load_users()
    _s = up._pin_salt_new()
    _u[uid1]["pin_salt"] = _s
    _u[uid1]["pin_hash"] = up._pin_hash(PIN1, _s)
    _u[uid1]["pin_idx"] = up._pin_index(PIN1)
    _u[uid1]["pin_idx_id"] = up._PIN_PEPPER_ID
    _u[uid1]["token_epoch"] = 0
    up._save_users(_u)

# ══════════════════════════════════════════════════════════════════
#  ٠٤ — تسجيل الخروج ⇒ إبطال على السيرفر (مش مسح كوكي بس)
# ══════════════════════════════════════════════════════════════════
section("٠٤ — تسجيل الخروج بيبطّل الجلسة على السيرفر")
r = login(client, PIN1, DEV1)
tok_logout = (r.get_json() or {}).get("token") or ""
r = client.get("/api/auth/me", headers=auth(tok_logout))
ok(r.status_code == 200, "الجلسة شغّالة قبل الخروج")

r = client.post("/api/auth/logout", headers=auth(tok_logout))
ok(r.status_code == 200, "الخروج رجّع 200", "status=%s" % r.status_code)
ok((r.get_json() or {}).get("revoked") is True,
   "الرد فيه revoked=true (إبطال فعلي على السيرفر)")

r = client.get("/api/auth/me", headers=auth(tok_logout))
ok(r.status_code == 401, "⛔ التوكن **مات** بعد الخروج",
   "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ٠٥ — البصمة: مستحيل تفتح جلسة بمفتاح جهاز منسوخ
# ══════════════════════════════════════════════════════════════════
section("٠٥ — دخول البصمة بمفتاح جهاز منسوخ")
r = client.post("/api/auth/pin/fingerprint", json={"device": DEV1})
ok(r.status_code == 410, "البصمة مقفولة افتراضياً ⇒ 410",
   "status=%s" % r.status_code)
ok((r.get_json() or {}).get("why") == "fingerprint_disabled",
   "السبب: fingerprint_disabled")

# ⛔ لو اتفتحت ⇒ لازم توثيق حديث بالرقم ⬇️ (مستخدم لسه ما دخلش بالرقم)
up.FINGERPRINT_LOGIN_ON = True
uid_fresh = "u_sec01_fresh"
with up.USERS_LOCK:
    _uu = up._load_users()
    _uu[uid_fresh] = {"id": uid_fresh, "name": "طازج",
                       "email": "fresh@example.test", "token_epoch": 0,
                       "bio_hash": up._device_key_hash(DEV2),
                       "bio_hashes": [up._device_key_hash(DEV2)]}
    up._save_users(_uu)
r = client.post("/api/auth/pin/fingerprint", json={"device": DEV2})
ok(r.status_code == 401, "بصمة من غير توثيق بالرقم ⇒ 401",
   "status=%s" % r.status_code)
ok((r.get_json() or {}).get("why") == "need_pin",
   "السبب: need_pin (لازم رقم أول)")
up.FINGERPRINT_LOGIN_ON = False

# ══════════════════════════════════════════════════════════════════
#  ٠٦ — مفيش أكواد خام على القرص
# ══════════════════════════════════════════════════════════════════
section("٠٦ — أكواد الاسترجاع: مفيش نسخة خام على القرص")
r = client.post("/api/auth/pin/challenge/send", json={"email": MAIL1})
ok(r.status_code == 200, "طلب كود استرجاع اتقبل", "status=%s" % r.status_code)
code = code_from_mail()
ok(bool(code), "الكود وصل (من الإيميل المسكوك)")

raw = ""
if up.PIN_CHAL_FILE.exists():
    raw = up.PIN_CHAL_FILE.read_text(encoding="utf-8")
ok("code_plain" not in raw, "⛔ مافيش مفتاح code_plain في pinchal.json")
ok(code not in raw and code != "" , "⛔ الكود الخام نفسه مش مكتوب في الملف")

d = json.loads(raw) if raw else {}
ok("c" in d, "ملف الكود موجود وشكله متوقع")

# ══════════════════════════════════════════════════════════════════
#  ٠٧ — منع تجاوز حدود المحاولات بتغيير ترويسات IP
# ══════════════════════════════════════════════════════════════════
section("٠٧ — ترويسات IP مزوّرة ⇒ العدّاد ما يتخطّاش")
r = login(client, PIN1, DEV1)
tok_ok = (r.get_json() or {}).get("token") or ""
ok(r.status_code == 200, "تسجيل دخول بالرقم شغّال", "status=%s" % r.status_code)

# ⛔ (أ) نفس الـPIN الغلط من ٥ عناوين مختلفة ⬇️ (محاولة تخطّي العدّاد)
locked_seen = False
for i in range(8):
    r = client.post("/api/auth/pin/login",
                    json={"pin": "0000", "device": DEV1},
                    headers={"X-Forwarded-For": "203.0.113.%d" % (i + 1)})
    if r.status_code == 429:
        locked_seen = True
        break
ok(locked_seen, "⛔ العدّاد اشتغل رغم تغيير ترويسة IP كل مرة")

# ⛔ (ب) الـIP الموثوق (من الـWorker) هو اللي بيتحسب ⬇️
#      ⛔ الترويسة المزوّرة من العميل ما بتغيّرش العدّاد ⬇️
up.PROXY_SECRET = "TEST-ONLY-proxy-secret"
up.PROXY_SECRET_CONFIGURED = True
try:
    lock2 = False
    for i in range(8):
        r = client.post("/api/auth/pin/login",
                        json={"pin": "5555", "device": DEV1},
                        headers={"X-OCTA-Proxy": "TEST-ONLY-proxy-secret",
                                 "X-OCTA-Client-IP": "5.5.5.5",
                                 "X-Forwarded-For": "198.51.100.%d" % (i + 1)})
        if r.status_code == 429:
            lock2 = True
            break
    ok(lock2, "⛔ العدّاد اشتغل بالـIP الموثوق رغم تزوير XFF كل مرة")
finally:
    up.PROXY_SECRET = ""
    up.PROXY_SECRET_CONFIGURED = False

# ⛔ (ج) كل رقم له عدّاد عالمي مستقل ⬇️ (رقم حد تاني ما يتقفلش)
r = client.post("/api/auth/pin/login",
                json={"pin": PIN1, "device": DEV1},
                headers={"X-Forwarded-For": "198.51.100.9"})
ok(r.status_code == 200, "الرقم الصح لسه شغّال (القفل على الرقم الغلط بس)",
   "status=%s" % r.status_code)

# نرجّع القفلHCRنل dla الاختبارات الجاية
try:
    up._pinlock_clear_pins([up._pin_keys(pin="0000")[0]])
    up._pinlock_clear_pins([up._pin_keys(pin=PIN1)[0]])
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════
#  ٠٨ — CSRF: كوكي لوحده ما يعملش كتابة
# ══════════════════════════════════════════════════════════════════
section("٠٨ — CSRF: الكتابة محتاجة Bearer (الكوكي لوحده مرفوض)")
r = client.post("/api/portfolio",
                json={"action": "add", "code": "COMI", "shares": 1,
                      "cost": 10, "price": 10},
                headers={"Cookie": "octa_token=%s" % tok_ok,
                         "X-Forwarded-For": "10.0.0.5"})
ok(r.status_code == 401, "⛔ POST بكوكي بس ⇒ 401 (CSRF مقفول)",
   "status=%s" % r.status_code)

r = client.post("/api/portfolio",
                json={"action": "add", "code": "COMI", "shares": 1,
                      "cost": 10, "price": 10},
                headers=dict(auth(tok_ok), **{"X-Forwarded-For": "10.0.0.5"}))
ok(r.status_code == 200, "✅ POST بـBearer شغّال (مافيش كسر)",
   "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ٠٩ — عزل حسابين: مفيش تسريب محفظة ولا منبهات
# ══════════════════════════════════════════════════════════════════
section("٠٩ — عزل بيانات كل مستخدم")
r = login(client, PIN2, DEV2)
tok2 = (r.get_json() or {}).get("token") or ""
ok(r.status_code == 200, "دخول الحساب التاني", "status=%s" % r.status_code)

r = client.get("/api/portfolio", headers=auth(tok2))
ok(r.status_code == 200, "الحساب التاني يقدر يقرأ محفظته")
pf2 = (r.get_json() or {}) or {}
ok(not (pf2.get("holdings") or {}).get("COMI"),
   "⛔ المحفظة ماعندهاش حصة المستخدم الأول")

r = client.get("/api/portfolio", headers=auth(tok_ok))
pf1 = (r.get_json() or {}) or {}
ok((pf1.get("holdings") or {}).get("COMI"),
   "محفظة المستخدم الأول فيها الحصة", "holdings=%s" % (pf1.get("holdings") or {}))

# ⛔ منبهات: المستخدم التاني ما يشوفش منبهات الأول
up._patch_user(uid1, watch={"COMI": {"hi": 99, "lo": 1}})
r = client.get("/api/alerts/watch", headers=auth(tok2))
items = (r.get_json() or {}).get("items") or []
ok(not items, "⛔ المستخدم التاني مايشوفش منبهات المستخدم الأول",
   "items=%s" % len(items))

# ══════════════════════════════════════════════════════════════════
#  ١٠ — مسارات الأدمن محمية
# ══════════════════════════════════════════════════════════════════
section("١٠ — مسارات الأدمن/التشخيص محمية")
for p in ("/api/admin/users", "/api/admin/monthly", "/api/admin/logins"):
    r = client.get(p)
    ok(r.status_code in (401, 403, 503),
       "%s ⇒ مرفوض بلا مفتاح أدمن" % p, "status=%s" % r.status_code)

r = client.get("/api/diagnostic")
ok(r.status_code in (401, 403), "التشخيص ⇒ مرفوض بلا جلسة",
   "status=%s" % r.status_code)

# ⛔ عميل نظيف (من غير كوكي) ⬇️ (العميل العادي بيحفظ الكوكي)
anon = up.app.test_client()
r = anon.get("/api/diagnostic")
ok(r.status_code in (401, 403), "التشخيص ⇒ مرفوض لعميل بلا كوكي",
   "status=%s" % r.status_code)
r = anon.get("/api/portfolio")
ok(r.status_code == 401, "المحفظة ⇒ 401 لعميل بلا كوكي",
   "status=%s" % r.status_code)

# ⛔⛔ ١٥ نوفمبر ٢٠٢٦ — التشخيص بقى للأدمن بس (مش أي مستخدم مسجّل)
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"
r = client.get("/api/diagnostic")
ok(r.status_code == 403,
   "⛔ مستخدم عادي (مسجّل) ⇒ 403 على التشخيص (مش 200)",
   "status=%s" % r.status_code)
r = client.get("/api/diagnostic",
               headers={"X-OCTA-Admin": "TEST-ONLY-admin-token"})
ok(r.status_code == 200, "الأدمن بالمفتاح ⇒ 200 على التشخيص",
   "status=%s" % r.status_code)
r = client.get("/api/diagnostic",
               headers={"X-OCTA-Admin": "wrong"})
ok(r.status_code == 403, "مفتاح أدمن غلط ⇒ 403",
   "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ١١ — الوصول المباشر لـRailway (السر بين الـEdge والـOrigin)
# ══════════════════════════════════════════════════════════════════
section("١١ — الوصول المباشر مرفوض لما السر مضبوط")
old_secret = up.PROXY_SECRET
old_flag = up.PROXY_SECRET_CONFIGURED
up.PROXY_SECRET = "TEST-ONLY-proxy-secret"
up.PROXY_SECRET_CONFIGURED = True
try:
    r = client.get("/api/quotes")
    ok(r.status_code == 403, "طلب بلا X-OCTA-Proxy ⇒ 403",
       "status=%s" % r.status_code)
    r = client.get("/api/quotes",
                   headers={"X-OCTA-Proxy": "TEST-ONLY-proxy-secret"})
    ok(r.status_code == 200, "طلب من الـWorker (بالسر) ⇒ 200",
       "status=%s" % r.status_code)
finally:
    up.PROXY_SECRET = old_secret
    up.PROXY_SECRET_CONFIGURED = old_flag

# ══════════════════════════════════════════════════════════════════
#  ١٢ — سياسة الخمول: جلسة ساكتة ⇒ توكن ميت
# ══════════════════════════════════════════════════════════════════
section("١٢ — انتهاء الجلسة بالخمول")
r = login(client, PIN1, DEV1)
tok_idle = (r.get_json() or {}).get("token") or ""
r = client.get("/api/auth/me", headers=auth(tok_idle))
ok(r.status_code == 200, "الجلسة شغّالة بعد الدخول")

old_idle = up.TOKEN_IDLE_TTL
up.TOKEN_IDLE_TTL = 1
try:
    up._patch_user(uid1, session_seen=int(time.time()) - 600)
    r = client.get("/api/auth/me", headers=auth(tok_idle))
    ok(r.status_code == 401, "⛔ جلسة ساكتة ⇒ 401 (الخمول بيقتلها)",
       "status=%s" % r.status_code)
finally:
    up.TOKEN_IDLE_TTL = old_idle
    up._patch_user(uid1, session_seen=int(time.time()))

# ══════════════════════════════════════════════════════════════════
#  ١٣ — مسار الاسترجاع (نسيت الرقم) بيبطّل الجلسات القديمة
# ══════════════════════════════════════════════════════════════════
section("١٣ — استرجاع الحساب ⇒ الإبطال + الجلسة الجديدة شغّالة")
r = login(client, PIN1, DEV1)
tok_old = (r.get_json() or {}).get("token") or ""
ok(r.status_code == 200, "تسجيل دخول قبل الاسترجاع")

MAILS.clear()
r = client.post("/api/auth/pin/challenge/send", json={"email": MAIL1})
code = code_from_mail()
ok(bool(code), "كود الاسترجاع وصل")
r = client.post("/api/auth/pin/challenge/verify",
                json={"email": MAIL1, "code": code})
ok(r.status_code == 200, "الكود اتقبل", "status=%s" % r.status_code)
unlock = (r.get_json() or {}).get("unlock") or \
    (r.get_json() or {}).get("unlock_token") or ""
ok(bool(unlock), "رجع توكن فتح")

r = client.post("/api/auth/pin/challenge/newpin",
                json={"new_pin": "7777"},
                headers=auth(unlock))
ok(r.status_code == 200, "اتغيّر الرقم بعد الاسترجاع",
   "status=%s" % r.status_code)
new_sess = (r.get_json() or {}).get("token") or ""

r = client.get("/api/auth/me", headers=auth(tok_old))
ok(r.status_code == 401, "⛔ الجلسة القديمة ماتت بعد الاسترجاع",
   "status=%s" % r.status_code)
if new_sess:
    r = client.get("/api/auth/me", headers=auth(new_sess))
    ok(r.status_code == 200, "الجلسة الجديدة شغّالة")

# ══════════════════════════════════════════════════════════════════
#  ١٤ — المسارات القديمة مقفولة
# ══════════════════════════════════════════════════════════════════
section("١٤ — مسارات قديمة مقفولة (410)")
for p in ("/api/auth/otp/send", "/api/auth/otp/verify",
          "/api/auth/reset", "/api/auth/reset/verify"):
    r = client.post(p, json={"email": MAIL1})
    ok(r.status_code == 410, "%s ⇒ 410" % p, "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  ١٥ — حساب قديم من غير token_epoch (الترحيل)
# ══════════════════════════════════════════════════════════════════
section("١٥ — ترحيل الحسابات القديمة (من غير token_epoch)")
uid_legacy = "u_sec01_legacy"
with up.USERS_LOCK:
    users = up._load_users()
    users[uid_legacy] = {"id": uid_legacy, "name": "قديم",
                          "email": "legacy@example.test",
                          "token_epoch": None}
    up._save_users(users)
try:
    ep = up._user_epoch(uid_legacy)
    ok(ep == 0, "الـepoch الحتمي = 0 (من غير خطأ)", "got=%r" % ep)
    tok_legacy = up._make_token(uid_legacy)
    r = client.get("/api/auth/me", headers=auth(tok_legacy))
    ok(r.status_code == 200, "الحساب القديم يقدر يدخل (من غير كسر)",
       "status=%s" % r.status_code)
except Exception as e:
    ok(False, "الترحيل مابايقعش استثناء", "%s: %s" % (type(e).__name__, e))

# ══════════════════════════════════════════════════════════════════
#  ١٦ — deadlock: _make_token جوّه USERS_LOCK (عيب تشغيلي كان حيّ)
# ══════════════════════════════════════════════════════════════════
section("١٦ — ⛔ deadlock: توليد توكن جوّه قفل المستخدمين")
import threading  # noqa: E402

uid_lock = "u_sec01_lock"
with up.USERS_LOCK:
    _ul = up._load_users()
    _ul[uid_lock] = {"id": uid_lock, "name": "قديم", "token_epoch": None}
    up._save_users(_ul)

_state = []


def _lock_worker():
    try:
        with up.USERS_LOCK:          # ⛔ القفل ماسك ⬇️
            up._make_token(uid_lock)  # ⛔ توليد توكن **جوه** القفل ⬇️
        _state.append("ok")
    except Exception as e:
        _state.append("err:%s" % type(e).__name__)


_t = threading.Thread(target=_lock_worker, daemon=True)
_t.start()
_t.join(timeout=8)
ok((not _t.is_alive()) and _state and _state[0] == "ok",
   "⛔ مافيش deadlock (التوكن اتولد جوّه القفل)",
   "alive=%s state=%s" % (_t.is_alive(), _state))

# ══════════════════════════════════════════════════════════════════
#  النتيجة
# ══════════════════════════════════════════════════════════════════
passed = sum(1 for r_ in RESULTS if r_[0])
failed = len(RESULTS) - passed
print("\n" + "═" * 66)
print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)" % (passed, failed, len(RESULTS)))
if failed:
    print("\n  ❌ الفاشل:")
    for good, label, extra in RESULTS:
        if not good:
            print("     - " + label + ("  [" + str(extra) + "]" if extra else ""))
print("═" * 66)

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if failed else 0)
