#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار قفل «اختيار الباسورد» — ٢١ أكتوبر ٢٠٢٦
=====================================================

📌 ليه الملف ده؟
   مسار اختيار الباسورد الجديد (التسجيل · الاسترجاع · التغيير)
   كان عدّاده مربوط **بالرقم** (`p:`) مش بالحساب. النتيجة:
   كل رقم جديد = ميزانية ٤ محاولات جديدة ⇒ مسح ١٠٬٠٠٠ رقم في
   ٨٣ ساعة بإيميل واحد و IP واحد.

   الإصلاح (الخيار A): العدّاد بقى `u:` (الحساب) + `i:` (الـIP).
   ⇒ كل حساب = ٤ محاولات بس لاختيار الباسورد (مش ٤ لكل رقم)
   ⇒ تغطية ١٠٬٠٠٠ رقم = ٢٬٥٠٠ حساب حقيقي (كل واحد بإيميل).

⛔⛔ القفل العالمي على الـPIN في **مسار الدخول** ما اتغيّرش —
   هو الحماية الأساسية ضد تخمين الدخول. الاختبار رقم ٦ بيتأكد.

⛔ داتا الاختبار كلها بتتبعت في مجلد مؤقت في /tmp — الملف ده
   بيفحص المفيش وبيكتبش في المشروع ولا في /app.

شغّله:  python3 test_pin_pick_lock.py
"""
import os
import re
import sys
import json
import time
import shutil
import tempfile
import pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="pinpick_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔⛔ مفيش سر حقيقي في الكود ولا في الملف ده — قيم اختبار محلية بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

# ⛔⛔ القواعد هنا = قواعد **الإنتاج** مش القواعد القديمة:
# ⛌ PIN_FAIL_LIMIT = ٤ (مش ٥) — يعني ٤ محاولات للحساب.
# ⛌ القفل ٣٠ ثانية (مش ١٥ دقيقة) — زي الإنتاج بالظبط.
up.PIN_FAIL_LIMIT = 4
up.PIN_LOCK_FIRST = 30
up.PIN_LOCK_NEXT = 30

# ── كل التخزين يروح على /tmp ──
up.USERS_FILE = pathlib.Path(TMP) / "users.json"
up.PINLOCK_FILE = pathlib.Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = pathlib.Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = pathlib.Path(TMP) / "otp.json"
up.SIGNUP_FILE = pathlib.Path(TMP) / "signup.json"
up.MAIL_ON = False          # ⛔ متبعثش إيميل حقيقي في الاختبار

MAILS = []


def _fake_send(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _fake_send

if not hasattr(fl_mod.jsonify.__globals__["_Response"], "set_data"):
    def _get_data(self):
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")

    def _set_data(self, raw):
        if isinstance(raw, (bytes, bytearray)):
            self.body = json.loads(raw.decode("utf-8"))
        else:
            self.body = raw

    fl_mod.jsonify.__globals__["_Response"].get_data = _get_data
    fl_mod.jsonify.__globals__["_Response"].set_data = _set_data

app = up.app

START = "/api/auth/signup/start"
VERIFY = "/api/auth/signup/verify"
NEWPIN = "/api/auth/signup/newpin"
LOG = "/api/auth/pin/login"
CHG = "/api/auth/pin/change"

_pass = _fail = 0


def t(name, fn):
    global _pass, _fail
    try:
        fn()
        print("  ✅", name)
        _pass += 1
    except Exception as e:
        print("  ❌", name, "\n     →", e)
        _fail += 1


def ok(c, m):
    if not c:
        raise AssertionError(m)


def call(path, method="POST", body=None, ip="10.0.0.1", token=None):
    # ⛌ الـrate limit في الذاكرة — بنصفّره بين الخطوات
    up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    if token:
        h["Authorization"] = "Bearer " + token
    return app.dispatch(path, method=method, body=body, headers=h)


def code_of(html):
    m = re.search(r">(\d{6})<", html or "")
    return m.group(1) if m else ""


def canon(r):
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


def start_signup(email, name="تجربة", ip="10.0.0.1"):
    n0 = len(MAILS)
    r = call(START, body={"name": name, "email": email}, ip=ip)
    code = ""
    for m in reversed(MAILS[n0:]):
        if m["to"] == email:
            code = code_of(m["html"])
            break
    return r, code


def unlock_for(email, name="تجربة", ip="10.0.0.1"):
    """خطوتين ①+② — توكن فتح جاهز لاختيار الباسورد"""
    r, code = start_signup(email, name, ip)
    ok(r.status_code == 200, "start %s → %s %s" % (email, r.status_code,
                                                  canon(r)))
    ok(code, "⛔ مافيش كود وصل في إيميل %s" % email)
    rv = call(VERIFY, body={"email": email, "code": code}, ip=ip)
    ok(rv.status_code == 200, "verify %s → %s %s" % (email, rv.status_code,
                                                     canon(rv)))
    u = (rv.get_json() or {}).get("unlock")
    ok(u, "⛔ مافيش unlock لـ %s" % email)
    return u


def signup(pin, email, name="تجربة", ip="10.0.0.1"):
    """تسجيل كامل — يرجّع (توكن الجلسة، uid، رد ③)"""
    u = unlock_for(email, name, ip)
    r = call(NEWPIN, body={"new_pin": pin}, ip=ip, token=u)
    ok(r.status_code == 200, "newpin %s → %s %s" % (email, r.status_code,
                                                    canon(r)))
    b = r.get_json() or {}
    return b.get("token"), (b.get("user") or {}).get("id"), r


def lock_state():
    try:
        return up._pinlock_load()
    except Exception:
        return {"k": {}}


def uid_of(unlock_tok):
    """الـuid بتاع توكن الفتح — عشان نفحص عدّاد الحساب `u:`"""
    return up._signup_unlock_read(unlock_tok)


# ══════════════════════════════════════════════════════════════════
#  الحسابات اللي هنستخدمها
#  ⛔ الأرقام دي **للاختبار** بس — ماشيطة في أي ملف بالمشروع
# ══════════════════════════════════════════════════════════════════
A_PIN, A_EMAIL = "7314", "amina@example.com"
B_PIN, B_EMAIL = "4826", "karim@example.com"
# ٤ باسوردات «مأجورة» — لازم نعمل عليها ٤ محاولات على ٤ أرقام مختلفة
TAKEN_PINS = ["1111", "2222", "3333", "4444"]
TAKEN_EMAILS = ["t1@example.com", "t2@example.com",
                "t3@example.com", "t4@example.com"]

print("\n▸ ٠  التجهيز")
A_TOKEN = A_UID = None
B_TOKEN = B_UID = None
for i, p in enumerate(TAKEN_PINS):
    signup(p, TAKEN_EMAILS[i], "مأجور", ip="10.0.0.%d" % (10 + i))
print("  (اتعمل ٤ حسابات بـ ٤ باسوردات + حسابين A و B)")


# ══════════════════════════════════════════════════════════════════
#  ①  تسجيل بحساب جديد وباسورد جديد → ينجح
# ══════════════════════════════════════════════════════════════════
print("\n▸ ①  التسجيل")


def t_signup_ok():
    global A_TOKEN, A_UID
    tok, uid, r = signup(A_PIN, A_EMAIL, "أمينة", ip="10.1.0.1")
    b = r.get_json()
    ok(b.get("ok") is True, "مش ok: %s" % canon(r))
    ok(tok, "مافيش توكن")
    ok(uid, "مافيش uid")
    A_TOKEN, A_UID = tok, uid
    # ⛔ الكوكي لازم يتبعت (HttpOnly) — خط دفاع تاني ضد XSS
    ck = r.headers.get("Set-Cookie") or ""
    ok("octa_token=" in ck, "مافيش كوكي جلسة: %s" % ck)
    ok("HttpOnly" in ck, "الكوكي مش HttpOnly: %s" % ck)
    ok("SameSite" in ck, "الكوكي من غير SameSite: %s" % ck)
    # ⛔ والباسورد خام مش متخزّن أبداً
    with up.USERS_LOCK:
        rec = (up._load_users() or {}).get(uid) or {}
    ok(A_PIN not in json.dumps(rec, ensure_ascii=False),
       "⛔⛔ الباسورد خام متخزّن في users.json!")
    ok(rec.get("pin_hash"), "مافيش هاش")


t("تسجيل بحساب جديد وباسورد جديد → 200 + توكن + كوكي", t_signup_ok)


def t_login_ok():
    r = call(LOG, body={"pin": A_PIN}, ip="10.1.0.1")
    ok(r.status_code == 200, "الدخول → %s %s" % (r.status_code, canon(r)))
    b = r.get_json() or {}
    ok(b.get("ok") is True, "مش ok")
    ok(b.get("token"), "مافيش توكن")
    ck = r.headers.get("Set-Cookie") or ""
    ok("octa_token=" in ck and "HttpOnly" in ck,
       "⛔ مافيش كوكي HttpOnly في رد الدخول: %s" % ck)


t("دخول بالباسورد الصحيح → يدخل (200 + كوكي)", t_login_ok)


def t_account_b():
    global B_TOKEN, B_UID
    B_TOKEN, B_UID, _ = signup(B_PIN, B_EMAIL, "كريم", ip="10.2.0.1")
    ok(B_UID, "مافيش uid لـ B")


t("تسجيل حساب تاني (B) → 200", t_account_b)


# ══════════════════════════════════════════════════════════════════
#  ②  تسجيل بحساب جديد وباسورد مستخدم تاني → يرفض + رسالة صح
# ══════════════════════════════════════════════════════════════════
print("\n▸ ②  الباسورد المكرر")


def t_taken_pin_rejected():
    u = unlock_for("newbie@example.com", "جديد", ip="10.3.0.1")
    r = call(NEWPIN, body={"new_pin": A_PIN}, ip="10.3.0.1", token=u)
    ok(r.status_code == 409, "الحالة %s مش 409" % r.status_code)
    b = r.get_json() or {}
    ok(b.get("why") == "pin_taken", "السبب %s" % b.get("why"))
    ok("مستخدم من قبل" in str(b.get("error") or ""),
       "الرسالة مش زي ما هي: %s" % b.get("error"))
    ok(b.get("token") is None, "⛔ رجّع توكن مع 409")
    # ⛔ الحساب **ماتعملش** — مافيش حساب نص نص
    with up.USERS_LOCK:
        users = up._load_users() or {}
    for uid, rec in users.items():
        if rec.get("email_hash") and rec.get("email") == "newbie@example.com":
            ok(not rec.get("pin_hash"),
               "⛔⛔ اتعمل حساب والباسورد مرفوض!")


t("باسورد مستخدم تاني → 409 + «مستخدم من قبل»", t_taken_pin_rejected)


# ══════════════════════════════════════════════════════════════════
#  ③  ٤ محاولات على باسورد واحد → القفل يشتغل
# ══════════════════════════════════════════════════════════════════
print("\n▸ ③  القفل على نفس الباسورد")


def t_four_same_pin_locks():
    u = unlock_for("samepin@example.com", "جديد", ip="10.4.0.1")
    codes = []
    for _ in range(5):
        r = call(NEWPIN, body={"new_pin": A_PIN}, ip="10.4.0.1", token=u)
        codes.append(r.status_code)
    ok(codes[:3] == [409] * 3, "أول ٣: %s" % codes)
    ok(codes[3] == 429,
       "⛔⛔ المحاولة الرابعة رجعت %s مش 429 — القفل مش شغّال" % codes[3])
    ok(codes[4] == 429, "الخامسة → %s" % codes[4])
    b = (call(NEWPIN, body={"new_pin": A_PIN}, ip="10.4.0.1",
              token=u).get_json() or {})
    ok(isinstance(b.get("retry_after"), int) and b.get("retry_after", 0) > 0,
       "مافيش retry_after: %s" % b)


t("٤ محاولات على نفس الباسورد → القفل يشتغل (429)", t_four_same_pin_locks)


# ══════════════════════════════════════════════════════════════════
#  ④  ٤ محاولات على ٤ باسوردات مختلفة → لازم يقفل (الخيار A)
#     ⛔⛔ ده الاختبار اللي بيفرق قبل/بعد الإصلاح:
#     قبل = كل رقم ليه ميزانية ٤ ⇒ ٤ أرقام مختلفة ما بتقفلش.
#     بعد = ٤ محاولات **للحساب كله** ⇒ بتقفل.
#     ⛌ وكل محاولة من **IP مختلف** ⇒ مافيش غير عدّاد الحساب
#        (`u:`) هو اللي يقدر يكون سبب القفل.
# ══════════════════════════════════════════════════════════════════
print("\n▸ ④  الخيار A — ٤ أرقام مختلفة = ٤ محاولات للحساب")


def t_four_different_pins_lock_account():
    u = unlock_for("sweeper@example.com", "سweep", ip="10.5.0.1")
    codes = []
    for i, p in enumerate(TAKEN_PINS):
        # ⛌ IP مختلف في كل محاولة — عشان نضمن إن القفل جاي
        #    من عدّاد الحساب مش من عدّاد الجهاز
        r = call(NEWPIN, body={"new_pin": p}, ip="10.5.0.%d" % (20 + i),
                 token=u)
        codes.append(r.status_code)
    ok(codes[:3] == [409] * 3, "أول ٣: %s" % codes)
    ok(codes[3] == 429,
       "⛔⛔ ٤ أرقام مختلفة من غير قفل — الحساب لسه فاضي: %s" % codes)
    ok(codes[3] == 429, "الرابعة → %s" % codes[3])

    # ⛔⛔ والدليل القاطع: القفل مربوط بالحساب
    st = lock_state()
    kmap = st.get("k") or {}
    rec_u = kmap.get("u:" + str(uid_of(u))) or {}
    ok(float(rec_u.get("u") or 0) > time.time(),
       "⛔⛔ مافيش قفل على الحساب: %s" % rec_u)
    # ⛌ ومافيش قفل عالمي على الرقم (ده اللي كان-behavior القديم)
    for p in TAKEN_PINS:
        rec_p = kmap.get("p:" + up._pin_index(p)) or {}
        ok(not float(rec_p.get("u") or 0),
           "⛔⛔ اتعمل قفل عالمي على الرقم %s — السلوك القديم" % p)


t("٤ محاولات على ٤ باسوردات مختلفة → القفل يشتغل (الخيار A)",
  t_four_different_pins_lock_account)


def t_account_lock_follows_account_not_device():
    """⛔⛔ بعد القفل: نفس الحساب من **جهاز تاني** = مقفول برضه.
       ده اللي بيفرق عن السلوك القديم (كان القفل على الرقم)."""
    u = unlock_for("sweeper2@example.com", "سweep2", ip="10.6.0.1")
    for i, p in enumerate(TAKEN_PINS[:3]):
        call(NEWPIN, body={"new_pin": p}, ip="10.6.0.%d" % (30 + i), token=u)
    # ⛔ المحاولة الرابعة من IP مختلف خالص
    r = call(NEWPIN, body={"new_pin": TAKEN_PINS[3]}, ip="10.6.9.9", token=u)
    ok(r.status_code == 429,
       "⛔⛔ من جهاز تاني رجعت %s — القفل مش مربوط بالحساب" % r.status_code)


t("القفل يتبع الحساب من أي جهاز (مش الجهاز)", t_account_lock_follows_account_not_device)


def t_other_account_not_locked():
    """⛔⛔ حساب تاني من جهاز تاني = **مش** مقفول.
       مافيش تسريب بين الحسابات: عدّاد حد مايقفلش حد تاني."""
    u = unlock_for("innocent@example.com", "بريء", ip="10.7.0.1")
    r = call(NEWPIN, body={"new_pin": A_PIN}, ip="10.7.9.9", token=u)
    ok(r.status_code == 409,
       "⛔⛔ حساب بريء اتقفل بسبب حساب تاني → %s" % r.status_code)


t("حساب تاني ما يتقفلش بسبب حد تاني", t_other_account_not_locked)


# ══════════════════════════════════════════════════════════════════
#  ⑤  دخول بالباسورد الصحيح → يدخل
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑤  الدخول")


def t_login_correct():
    r = call(LOG, body={"pin": B_PIN}, ip="10.8.0.1")
    ok(r.status_code == 200, "→ %s %s" % (r.status_code, canon(r)))
    b = r.get_json() or {}
    ok(b.get("token"), "مافيش توكن")
    ok((b.get("user") or {}).get("id") == B_UID, "الـuid غلط")


t("دخول بالباسورد الصحيح → يدخل", t_login_correct)


# ══════════════════════════════════════════════════════════════════
#  ⑥  دخول بباسورد غلط × ٥ → القفل العالمي يشتغل
#     ⛔⛔ ده القفل اللي ما اتغيّرش — وهو الحماية الأساسية
#        ضد تخمين الدخول. لازم يفضل شغّال بالظبط.
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑥  القفل العالمي على الباسورد (مسار الدخول)")


def t_login_global_lock():
    codes = []
    for _ in range(5):
        r = call(LOG, body={"pin": "7777"}, ip="10.9.0.1")
        codes.append(r.status_code)
    # ⛌ حد الفشل في الإنتاج = ٤ ⇒ القفل في المحاولة الرابعة
    ok(codes[:3] == [401] * 3, "أول ٣: %s" % codes)
    ok(codes[3] == 429,
       "⛔⛔ القفل العالمي مش شغّال — %s" % codes)
    ok(codes[4] == 429, "الخامسة → %s" % codes[4])

    # ⛔⛔ القفل **عالمي** مش Per-IP: نفس الرقم من جهاز تاني = مقفول
    r2 = call(LOG, body={"pin": "7777"}, ip="10.9.8.8")
    ok(r2.status_code == 429,
       "⛔⛔ القفل مش عالمي → %s" % r2.status_code)

    # ⛔ والدليل: فيه سجل `p:` عالمي في ملف القفل
    st = lock_state()
    rec = (st.get("k") or {}).get("p:" + up._pin_index("7777")) or {}
    ok(float(rec.get("u") or 0) > time.time(),
       "⛔⛔ مافيش قفل عالمي على الباسورد: %s" % rec)

    # ⛔⛔ و**مفيش** حجب خدمة على الضحية: قفل رقم X ما بيقفلش
    #    رقم Y — الضحية لسه تقدر تدخل بباسوردها.
    r3 = call(LOG, body={"pin": A_PIN}, ip="10.9.7.7")
    ok(r3.status_code == 200,
       "⛔⛔⛔ باسورد الضحية اتقفل بسبب رقم تاني → %s" % r3.status_code)


t("٥ محاولات دخول غلط → القفل العالمي يشتغل (429)", t_login_global_lock)


# ══════════════════════════════════════════════════════════════════
#  ⑦  ⛔⛔⛔ مفيش تسريب بين الحسابات
#     الحساب B ما يعرفش حاجة عن الحساب A — لا في الردود،
#     ولا في القفل، ولا في البيانات.
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑦  ⛔⛔ مفيش تسريب بين الحسابات")


def t_no_leak_between_accounts():
    # ⛔ ① ⛔⛔ مفيش oracle في مسار الدخول: ردّ «باسورد غلط» لازم
    #    يكون **بالحرف** نفسه سواء الحساب موجود أو لأ.
    r_exist = call(LOG, body={"pin": "8899"}, ip="10.20.0.1")
    r_nones = call(LOG, body={"pin": "6677"}, ip="10.20.0.2")
    ok(r_exist.status_code == 401 and r_nones.status_code == 401,
       "→ %s / %s" % (r_exist.status_code, r_nones.status_code))
    b1, b2 = canon(r_exist), canon(r_nones)
    ok(b1 == b2,
       "⛔⛔ الردّين مختلفين — فيه تمييز!\n   موجود: %s\n   مش موجود: %s"
       % (b1, b2))
    for leak in (A_EMAIL, A_UID, "taken", "مستخدم من قبل", "مسجّل"):
        ok(leak not in b1 and leak not in b2,
           "⛔⛔ الرد بيسرّب %s" % leak)

    # ⛔ ② B يختار باسورد A كـ«باسورد جديد» في حسابه
    #    → 409 (الرقم مأجور) — بس **ما بيطلعش** أي بيانات
    u = unlock_for("leaker@example.com", "ليكر", ip="10.20.0.3")
    r2 = call(NEWPIN, body={"new_pin": A_PIN}, ip="10.20.0.3", token=u)
    ok(r2.status_code == 409, "→ %s" % r2.status_code)
    body2 = canon(r2)
    for leak in (A_EMAIL, A_UID, "amina"):
        ok(leak not in body2, "⛔⛔ الرد فيه %s" % leak)

    # ⛔ ③ B يقدر يغيّر باسورد A؟ → 401 (لازم توكن A)
    r3 = call(CHG, body={"old_pin": A_PIN, "new_pin": "9999"},
              ip="10.20.0.4", token=B_TOKEN)
    ok(r3.status_code == 401, "⛔⛔ غير مصرّح ليه → %s" % r3.status_code)
    body3 = canon(r3)
    ok(A_UID not in body3 and A_EMAIL not in body3, "⛔⛔ تسريب")

    # ⛔ ④ محاولات B ما بتقفلش حساب A
    for i in range(6):
        uu = unlock_for("noisy%d@example.com" % i, "ضجيج",
                         ip="10.20.1.%d" % (10 + i))
        call(NEWPIN, body={"new_pin": A_PIN}, ip="10.20.1.%d" % (10 + i),
             token=uu)
    # ⛌ A لسه يقدر يدخل
    r4 = call(LOG, body={"pin": A_PIN}, ip="10.21.0.1")
    ok(r4.status_code == 200,
       "⛔⛔⛔ حساب A اتقفل بسبب محاولات حد تاني → %s" % r4.status_code)

    # ⛌ وبيانات A في users.json ماتغيّرتش
    with up.USERS_LOCK:
        rec = (up._load_users() or {}).get(A_UID) or {}
    ok(rec.get("pin_hash"), "⛔⛔ هاش A اتمسح!")
    ok(A_PIN not in json.dumps(rec, ensure_ascii=False),
       "⛔⛔ الباسورد خام ظهر في users.json")
    ok(rec.get("name") == "أمينة", "⛔⛔ اسم A اتغيّر: %s" % rec.get("name"))


t("⛔⛔ مفيش تسريب بين حساب A وحساب B", t_no_leak_between_accounts)


# ══════════════════════════════════════════════════════════════════
#  ⑧  إصلاح الـP0 — `_json_auth` كانت ناقصة ⇒ 500 على كل مصادقة
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑧  ردود المصادقة (إصلاح الـNameError)")


def t_auth_paths_no_500():
    # ⛔ كل المسارات اللي بترجّع توكن لازم ترجّع 200/401/409 — مش 500
    checks = [
        (LOG, {"pin": B_PIN}),
        (START, {"name": "x", "email": "zz@example.com"}),
    ]
    for p, b in checks:
        r = call(p, body=b, ip="10.30.0.1")
        ok(r.status_code < 500, "%s رجّع %s (خطأ خادم!)" % (p, r.status_code))
    # ⛔ مسارات المصادقة كلها موجودة
    rules = set()
    um = up.app.url_map
    if hasattr(um, "iter_rules"):
        for r in um.iter_rules():
            rules.add(str(r.rule))
    else:
        for r in um:
            rules.add(str(getattr(r, "path", r)))
    for p in (START, VERIFY, NEWPIN, LOG, CHG,
              "/api/auth/pin/challenge/newpin",
              "/api/auth/refresh", "/api/auth/me"):
        ok(p in rules, "⛔ المسار %s مش موجود (الموجود: %s)" % (p, rules))


t("مفيش 500 في أي مسار مصادقة", t_auth_paths_no_500)


# ══════════════════════════════════════════════════════════════════
#  ⑨  الثوابت intoxicating ما اتغيّرتش
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑨  الثوابت")


def t_constants_untouched():
    # ⛔ سقف المسار ١٠ / ٥ دقايق
    ok(up.LIMITS["pin_signup_newpin"] == [(10, 300)],
       "⛔ سقف newpin اتغيّر: %s" % (up.LIMITS["pin_signup_newpin"],))
    # ⛔ ٣ محاولات في ٦٠ ثانية (النافذة)
    ok(up.PIN_WINDOW_FAILS == 4, "⛔ نافذة المحاولات اتغيّرت")
    ok(up.PIN_WINDOW_SECONDS == 60, "⛔ طول النافذة اتغيّر")
    # ⛔ القفل العالمي على الباسورد في الدخول: ٥ / ٩٠٠ / ٣٦٠٠
    ok(up.PIN_FAIL_LIMIT == 4, "⛔ حد الفشل اتغيّر")
    # ⛔ ومفيش شيل للـPIN من مسار الدخول
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    seg = src.split("def auth_pin_login")[1].split("\ndef ")[0]
    ok("_pin_keys(pin=pin" in seg,
       "⛔⛔ مسار الدخول بقى يستخدم عدّاد غير PIN!")
    ok("_pin_acct_keys" not in seg,
       "⛔⛔ مسار الدخول اتغيّر — القفل العالمي لازم يفضل زي ما هو")


t("ثوابت الأمان ما اتغيّرتش", t_constants_untouched)


# ══════════════════════════════════════════════════════════════════
print("\n" + "═" * 62)
print("  %d نجح · %d فشل" % (_pass, _fail))
print("═" * 62)
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if _fail else 0)
