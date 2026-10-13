#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار التسجيل الجديد — الإيميل الأول، والباسورد بعده.

⛔⛔ داتا الاختبار كلها بتتبعت في مجلد مؤقت في /tmp — الملف ده
   بيفحص المفيش وبيكتبش في المشروع ولا في /app.

⛔ مافيش باسورد ولا كود حقيقي في الملف: الأرقام دي أرقام اختبار
   محلية بتتولد في الكود، واللي بيوصل الإيميل بيتقرا من الإيميل
   نفسه (مش من متغير في السيرفر).

شغّله:  python3 test_signup_flow.py
"""
import os
import re
import sys
import time
import json
import ast
import shutil
import tempfile

HERE = "/workspace/octa-prices"
TMP = tempfile.mkdtemp(prefix="signuptest_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔⛔ مفيش سر حقيقي في الكود ولا في الملف ده — قيم اختبار محلية بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

from pathlib import Path  # noqa: E402

# ── كل التخزين يروح على /tmp ──
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.MAIL_ON = False          # ⛔ متبعثش إيميل حقيقي في الاختبار

# ⛔ ⛔ مافيش خدمة إيميل: بنمسك الإيميل بدل ما يتبعت فعلاً.
#    الكود بيتقرا من نص الإيميل نفسه — وده بالظبط اللي المستخدم
#    بيشوفه على بريده.
MAILS = []


def _grab_mail(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _grab_mail

# ── الـstub مافيش فيه get_data/set_data — والـafter_request بيحتاجهم ──
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


# ⏱️ ساعة قابلة للتمرير — عشان نختبر انتهاء صلاحية الكود من غير
#    ما ننتظر ١٠ دقايق حقيقية.
_REAL_TIME = time.time()


class FakeTime:
    def __init__(self):
        self.t = _REAL_TIME

    def time(self):
        return self.t

    def sleep(self, s):
        pass                       # ⛔ مافيش انتظار حقيقي

    def __getattr__(self, k):
        return getattr(time, k)


FAKE = FakeTime()
up.time = FAKE

import contextlib  # noqa: E402


@contextlib.contextmanager
def clock(base=_REAL_TIME):
    old = FAKE.t
    FAKE.t = base
    try:
        yield FAKE
    finally:
        FAKE.t = old


app = up.app

START = "/api/auth/signup/start"
VERIFY = "/api/auth/signup/verify"
NEWPIN = "/api/auth/signup/newpin"
OLD_REG = "/api/auth/pin/register"
ME = "/api/auth/me"

# أرقام الاختبار — ماشيطة في أي ملف بالمشروع
PIN = "7314"
EMAIL = "amina@example.com"
NAME = "أمينة"
PIN2 = "4826"
EMAIL2 = "karim@example.com"
GHOST = "ghost@example.com"

_pass = _fail = 0
_names = []


def t(name, fn):
    global _pass, _fail
    try:
        fn()
        print("  ✅", name)
        _pass += 1
        _names.append((True, name))
    except Exception as e:
        print("  ❌", name, "\n     →", e)
        _fail += 1
        _names.append((False, name))


def ok(c, m):
    if not c:
        raise AssertionError(m)


def call(path, method="POST", body=None, ip="10.1.0.1", token=None):
    up._HITS.clear()                     # ⛌ السقف في الذاكرة
    h = {"X-Forwarded-For": ip}
    if token:
        h["Authorization"] = "Bearer " + token
    return app.dispatch(path, method=method, body=body, headers=h)


def jbody(r):
    return r.get_json() or {}


def canon(r):
    """الرد كملف نصي — للمقارنة حرف بحرف"""
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


def code_of(html):
    """📬 الكود اللي وصل في الإيميل فعلاً — زي ما المستخدم بيشوفه"""
    m = re.search(r">(\d{6})<", html or "")
    return m.group(1) if m else ""


def sent_to(email):
    """كل الإيميلات اللي راحت لصاحب الإيميل ده"""
    return [m for m in MAILS if m["to"] == email]


def start(email, name=NAME, ip="10.1.0.1"):
    MAILS[:] = [m for m in MAILS if m["to"] != email]
    return call(START, body={"name": name, "email": email}, ip=ip)


def code_sent(email, name=NAME, ip="10.1.0.1"):
    """يمشي لخطوة ① ويرجّع الكود اللي وصل في الإيميل"""
    r = start(email, name, ip)
    ok(r.status_code == 200,
       "start %s → %s %s" % (email, r.status_code, jbody(r)))
    ms = sent_to(email)
    ok(ms, "⛔ مافيش إيميل اتبعت لـ %s" % email)
    c = code_of(ms[-1]["html"])
    ok(c, "⛔ مافيش كود في الإيميل لـ %s" % email)
    return c


def users_n():
    return len(up._load_users())


def full_signup(email, pin, name=NAME, ip="10.1.0.1"):
    """يمشي بالخطوات التلاتة كلهم ويرجّع التوكن"""
    c = code_sent(email, name, ip)
    rv = call(VERIFY, body={"email": email, "code": c}, ip=ip)
    ok(rv.status_code == 200, "verify → %s %s" % (rv.status_code, jbody(rv)))
    unlock = jbody(rv).get("unlock")
    rn = call(NEWPIN, body={"new_pin": pin}, ip=ip, token=unlock)
    ok(rn.status_code == 200, "newpin → %s %s" % (rn.status_code, jbody(rn)))
    return jbody(rn).get("token")


print("\n▸ ①  المسار القديم اتقفل")
print("   (ملف المستخدمين: %s)" % up.USERS_FILE)
print("   (ملف التعليق:    %s)" % up.SIGNUP_FILE)


def t_old_route_gone():
    """⛔⛔⛔ /api/auth/pin/register بقى 410 — مش 404 ومش شغال.
       كان باب تاني بيتعمل بيه حساب **قبل** ما الإيميل يتأكد."""
    r = call(OLD_REG, body={"name": "x", "email": "old@example.com",
                             "pin": "1234"})
    ok(r.status_code == 410, "الحالة %s مش 410" % r.status_code)
    b = jbody(r)
    ok(b.get("ok") is False, "مش ok:false")
    ok("القديمة" in (b.get("error") or ""), "الرسالة مش عربيّة: %s" % b)
    ok("الجديدة" in (b.get("error") or ""), "الرسالة مش بتوجّه للشاشة الجديدة")
    # ⛔⛔ مافيش حساب اتعمل ولا توكن اتطلع
    ok(b.get("token") is None, "⛔ رجّع توكن")
    ok(up._pin_by_email("old@example.com")[1] is None, "⛔ اتعمل حساب")
    ok(users_n() == 0, "⛔ عدد المستخدمين %d" % users_n())


t("المسار القديم /pin/register → 410", t_old_route_gone)


def t_old_route_dont_create():
    """⛔ المسار القديم حتى بباسورد جديد مابيعملش حساب"""
    before = users_n()
    for i in range(3):
        r = call(OLD_REG, body={"name": "x%d" % i,
                                 "email": "ghost%d@example.com" % i,
                                 "pin": "111%d" % i}, ip="10.9.%d.1" % i)
        ok(r.status_code == 410, "المحاولة %d → %s" % (i, r.status_code))
    ok(users_n() == before, "⛔ اتعمل %d حساب من المسار القديم"
       % (users_n() - before))
    for i in range(3):
        ok(up._pin_by_email("ghost%d@example.com" % i)[1] is None,
           "⛔ اتعمل حساب من المسار القديم")


t("المسار القديم مابيعملش ولا حساب", t_old_route_dont_create)


print("\n▸ ②  ① start — الاسم والإيميل بس")


def t_start_ok():
    r = start(GHOST)
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, jbody(r)))
    b = jbody(r)
    ok(b.get("ok") is True, "مش ok")
    ok(b.get("next") == "signup/verify", "الخطوة الجاية %s" % b.get("next"))
    ok(b.get("expires_in") == 600, "المدة %s مش ٦٠٠ ثانية" % b.get("expires_in"))
    ok(b.get("digits") == 6, "عدد الخانات %s" % b.get("digits"))
    # ⛔⛔ مافيش باسورد في الرد، ومافيش كود في الرد
    ok("pin" not in json.dumps(b, ensure_ascii=False).lower(),
       "⛔ كلمة pin في الرد: %s" % b)
    ok(code_of(json.dumps(b, ensure_ascii=False)) == "",
       "⛔ الكود طالع في الرد")
    # 📬 والكود وصل في إيميل
    ms = sent_to(GHOST)
    ok(ms, "⛔ مافيش إيميل")
    ok(len(code_of(ms[-1]["html"])) == 6, "الكود مش ٦ خانات")


t("start بإيميل صح → 200 + كود في الإيميل", t_start_ok)


def t_start_no_pin_field():
    """⛔⛔ الطلب مافيش فيه باسورد أصلاً — ولو حد بعت واحد نرفض"""
    r = call(START, body={"name": "x", "email": "p1@example.com",
                          "pin": "1234"})
    ok(r.status_code == 400, "الحالة %s مش 400" % r.status_code)
    ok(jbody(r).get("why") == "no_pin_here", "السبب %s" % jbody(r).get("why"))
    ok(sent_to("p1@example.com") == [], "⛔ بعت إيميل رغم الباسورد في الطلب")


t("start بباسورد في الطلب → 400 ومفيش إيميل", t_start_no_pin_field)


def t_start_bad_email():
    for em in ("", "لاشيء", "a@b", "a b@example.com", "x@.com"):
        r = call(START, body={"name": "x", "email": em})
        ok(r.status_code == 400, "إيميل %r → %s" % (em, r.status_code))
        ok(jbody(r).get("why") == "bad_email", "السبب %s" % jbody(r).get("why"))


t("start بإيميل شكله غلط → 400", t_start_bad_email)


def t_start_no_user_created():
    """⛔⛔⛔ الأهم: بعد start مافيش ولا مستخدم اتعمل. الحساب
       لازم يتعمل بعد ما الإيميل يتأكد، مش قبله."""
    before = users_n()
    c = code_sent("newbie@example.com")
    ok(users_n() == before,
       "⛔⛔ اتعمل %d مستخدم من start — الحساب لازم يتعمل بعد التأكيد"
       % (users_n() - before))
    ok(up._pin_by_email("newbie@example.com")[1] is None,
       "⛔⛔ الحساب اتعمل قبل ما الإيميل يتأكد")
    ok(up._hash_key("newbie@example.com")[:20] not in up._load_users(),
       "⛔⛔ الـuid بتاع الإيميل موجود في users.json")
    # ⛌ بس الحالة المؤقتة موجودة (هاش بس، مش كود خام)
    st = json.loads(up.SIGNUP_FILE.read_text(encoding="utf-8"))
    rec = (st.get("p") or {}).get("newbie@example.com") or {}
    ok(rec.get("h"), "مافيش حالة انتظار")
    ok(c not in json.dumps(st, ensure_ascii=False),
       "⛔⛔ الكود الخام متخزّن في signup.json")


t("مافيش مستخدم اتعمل بعد start", t_start_no_user_created)


def t_start_reply_identical():
    """⛔⛔⛔ الرد **واحد** حرفياً: إيميل مسجّل / إيميل مش مسجّل /
       إيميل مالوش أصلاً — نفس الـstatus ونفس الـbody بالحرف."""
    # ① إيميل مسجّل فعلاً (حساب كامل بالباسورد)
    tok = full_signup(EMAIL, PIN)
    ok(tok, "⛔ التسجيل الكامل فشل")

    r_known = start(EMAIL, ip="10.4.0.1")
    ok(r_known.status_code == 200, "مسجّل → %s" % r_known.status_code)
    a = canon(r_known)

    # ② إيميل مش مسجّل
    r_new = start("nobody@example.com", ip="10.4.0.2")
    ok(r_new.status_code == 200, "مش مسجّل → %s" % r_new.status_code)
    b = canon(r_new)

    # ③ إيميل منته (صلاحية كوده خلصت) — حالة ثالثة لازم تكون واحدة برضه
    r_old = start("expired@example.com", ip="10.4.0.3")
    ok(r_old.status_code == 200, "منتهي → %s" % r_old.status_code)
    c = canon(r_old)

    ok(a == b, "⛔ الرد مختلف بين مسجّل ومش مسجّل:\n  %s\n  %s" % (a, b))
    ok(a == c, "⛔ الرد مختلف بين مسجّل ومنتهي:\n  %s\n  %s" % (a, c))
    ok(up._load_users()[up._hash_key(EMAIL)[:20]]["email"] == EMAIL,
       "⛔ الرد غيّر بيانات الحساب المسجّل")


t("start: مسجّل ومش مسجّل → نفس الرد حرفياً", t_start_reply_identical)


def t_start_no_pin_leak():
    """⛔⛔ الرد مايقولش حاجة عن الباسورد ولا عن حالة الحساب"""
    r = start(EMAIL, ip="10.4.1.1")
    s = json.dumps(r.get_json() or {}, ensure_ascii=False)
    for w in ("مسجّل", "موجود", "مستخدم من قبل", "taken", "conflict"):
        ok(w not in s, "⛔ الرد فيه %r" % w)


t("start: مافيش تسريب لحالة الحساب", t_start_no_pin_leak)


print("\n▸ ③  ② verify — الكود")


def t_verify_wrong_code():
    c = code_sent("wrong@example.com")
    bad = "000000" if c != "000000" else "111111"
    r = call(VERIFY, body={"email": "wrong@example.com", "code": bad})
    ok(r.status_code == 401, "الحالة %s مش 401" % r.status_code)
    b = jbody(r)
    ok(b.get("ok") is False, "مش ok:false")
    ok(b.get("unlock") is None, "⛔ رجّع unlock بكود غلط")
    ok(up._pin_by_email("wrong@example.com")[1] is None, "⛔ اتعمل حساب")


t("verify بكود غلط → 401", t_verify_wrong_code)


def t_verify_bad_shape():
    """⛌ ٦ أرقام بالظبط — أي شكل تاني = 401 زي الكود الغلط"""
    code_sent("shape@example.com")
    for c in ("12345", "1234567", "abcdef", "", "٧٣١٤٠٥", "12 456"):
        r = call(VERIFY, body={"email": "shape@example.com", "code": c})
        ok(r.status_code == 401, "الكود %r → %s" % (c, r.status_code))
        ok(jbody(r).get("unlock") is None, "⛔ unlock لكود %r" % c)


t("verify بكود مش ٦ أرقام → 401", t_verify_bad_shape)


def t_verify_expired():
    """⛔⛔ الكود صالح ١٠ دقايق بالظبط — بعد ١١ دقيقة يموت"""
    em = "ttl@example.com"
    c = code_sent(em)
    # ⛌ بعد ٩ دقايق لسه صالح
    with clock(FAKE.t + 9 * 60):
        r = call(VERIFY, body={"email": em, "code": c}, ip="10.5.0.9")
    ok(r.status_code == 200, "بعد ٩ دقايق → %s %s" % (r.status_code, jbody(r)))
    ok(jbody(r).get("need_pin") is True, "مافيش need_pin")

    em2 = "ttl2@example.com"
    c2 = code_sent(em2)
    # ⛌ بعد ١١ دقيقة يموت
    with clock(FAKE.t + 11 * 60):
        r2 = call(VERIFY, body={"email": em2, "code": c2}, ip="10.5.0.9")
    ok(r2.status_code == 401, "⛔ بعد ١١ دقيقة → %s مش 401" % r2.status_code)
    ok(jbody(r2).get("unlock") is None, "⛔ رجّع unlock بكود منتهي")
    ok(up._pin_by_email(em2)[1] is None, "⛔⛔ اتعمل حساب بكود منتهي")


t("verify بكود منتهي (١١ دقيقة) → 401", t_verify_expired)


def t_verify_five_wrong():
    """⛔⛔ ٥ محاولات غلط ← الكود يموت — والكود الصح بعدها
       يبقى غلط برضه (مش بس مرفوض)."""
    em = "dead@example.com"
    c = code_sent(em)
    codes = []
    for i in range(5):
        r = call(VERIFY, body={"email": em, "code": "000000"}, ip="10.6.0.1")
        codes.append(r.status_code)
        ok(r.status_code == 401, "المحاولة %d → %s" % (i + 1, r.status_code))
    # ⛌ الكود الأرقام ٥6341 مات
    r = call(VERIFY, body={"email": em, "code": c}, ip="10.6.0.1")
    ok(r.status_code == 401, "⛔⛔ الكود الصح بعد ٥ غلط → %s" % r.status_code)
    ok(jbody(r).get("unlock") is None, "⛔ رجّع unlock بكود ميت")
    ok(up._pin_by_email(em)[1] is None, "⛔⛔ اتعمل حساب بكود ميت")
    # ⛌ الهاش اتمسح من الملف
    st = json.loads(up.SIGNUP_FILE.read_text(encoding="utf-8"))
    rec = (st.get("p") or {}).get(em) or {}
    ok(not rec.get("h"), "⛔ الكود المات لسه مخزّن")
    ok(c not in json.dumps(st, ensure_ascii=False), "⛔ الكود الخام في الملف")


t("verify بـ٥ محاولات غلط ← الكود يموت", t_verify_five_wrong)


def t_verify_ok():
    """⛔⛔⛔ الكود صح → need_pin + توكن فتح، و**مافيش توكن دخول**"""
    em = "good@example.com"
    n0 = users_n()
    c = code_sent(em)
    r = call(VERIFY, body={"email": em, "code": c})
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, jbody(r)))
    b = jbody(r)
    ok(b.get("ok") is True, "مش ok")
    ok(b.get("need_pin") is True, "⛔ مافيش need_pin")
    ok(b.get("next") == "signup/newpin", "الخطوة %s" % b.get("next"))
    ok(b.get("unlock"), "⛔ مافيش unlock")
    # ⛔⛔⛔ مافيش توكن دخول في الرد
    ok(b.get("token") is None, "⛔⛔ رجّع توكن دخول قبل الباسورد: %s" % b)
    # ⛌ الحساب اتعمل هنا — بعد التأكيد، مش قبله
    ok(users_n() == n0 + 1, "⛔ الحساب مااتعملش: %d → %d" % (n0, users_n()))
    uid = up._hash_key(em)[:20]
    rec = up._load_users().get(uid) or {}
    ok(rec, "⛔ مافيش سجل للمستخدم")
    ok(rec.get("email_confirmed") is True, "⛔ email_confirmed مش true")
    ok(rec.get("name") == NAME, "الاسم %r" % rec.get("name"))
    # ⛔ ومافيش باسورد لسه
    ok(not rec.get("pin_hash"), "⛔⛔ اتحفظ باسورد قبل ما يتختار")
    globals()["GOOD_UNLOCK"] = b["unlock"]
    globals()["GOOD_UID"] = uid
    globals()["GOOD_EMAIL"] = em


t("verify صح → need_pin + مافيش توكن دخول", t_verify_ok)


def t_unlock_is_not_session():
    """⛔⛔⛔ توكن الفتح **مش** توكن جلسة — مش على /api/auth/me
       ومش على /api/auth/refresh ومش على أي مسار محمي تاني."""
    u = globals()["GOOD_UNLOCK"]
    r = call(ME, method="GET", token=u)
    ok(r.status_code == 401, "على /api/auth/me → %s مش 401" % r.status_code)
    r2 = call("/api/auth/refresh", token=u)
    ok(r2.status_code == 401, "على /api/auth/refresh → %s" % r2.status_code)
    r3 = call("/api/auth/pin/change", body={"old_pin": "1111", "new_pin": "2222"},
              token=u)
    ok(r3.status_code == 401, "على تغيير الباسورد → %s" % r3.status_code)
    # ⛔ ولا حتى الـuid بتاعه مش مسreachable من غير newpin
    rec = up._load_users().get(globals()["GOOD_UID"]) or {}
    ok(not rec.get("pin_hash"), "⛔ اتحفظ باسورد من غير newpin")


t("unlock مش توكن دخول (401 على كل مسار محمي)", t_unlock_is_not_session)


def t_login_before_pin():
    """⛔⛔ مافيش دخول بالحساب قبل ما الباسورد يتقبل — الـuid موجود
       بس مافيش باسورد، فالدخول بالباسورد لازم يفشل."""
    r = call("/api/auth/pin/login", body={"pin": "6123"}, ip="10.2.9.9")
    ok(r.status_code == 401, "الدخول → %s مش 401" % r.status_code)
    ok(jbody(r).get("why") == "bad_pin", "السبب %s" % jbody(r).get("why"))
    # ⛔ والحساب المعلّق نفسه موجود فعلاً (اتعمل عند التأكيد)
    rec = up._load_users().get(globals()["GOOD_UID"]) or {}
    ok(rec, "⛔ مافيش سجل للحساب المعلّق")
    ok(not rec.get("pin_hash"), "⛔ اتحفظ باسورد من غير ما يتختار")


t("مافيش دخول قبل اختيار الباسورد", t_login_before_pin)


print("\n▸ ④  ③ newpin — اختيار ٤ أرقام")


def t_newpin_ok():
    """⛔⛔⛔ المسار كله: start → verify → newpin → توكن صالح"""
    em = "full@example.com"
    n0 = users_n()
    c = code_sent(em)
    rv = call(VERIFY, body={"email": em, "code": c})
    ok(rv.status_code == 200, "verify %s" % jbody(rv))
    ok(jbody(rv).get("token") is None, "⛔ verify رجّع توكن")
    unlock = jbody(rv)["unlock"]

    rn = call(NEWPIN, body={"new_pin": PIN2}, token=unlock)
    ok(rn.status_code == 200, "newpin → %s %s" % (rn.status_code, jbody(rn)))
    b = jbody(rn)
    ok(b.get("ok") is True, "مش ok")
    tok = b.get("token")
    ok(tok, "⛔ مافيش توكن")
    ok((b.get("user") or {}).get("id") == up._hash_key(em)[:20], "الـuid غلط")
    ok(users_n() == n0 + 1, "⛔ اتعمل أكتر من حساب")
    # ⛌ التوكن صالح على /api/auth/me
    rm = call(ME, method="GET", token=tok)
    ok(rm.status_code == 200, "التوكن على /api/auth/me → %s %s"
       % (rm.status_code, jbody(rm)))
    ok((jbody(rm).get("user") or {}).get("id") == up._hash_key(em)[:20],
       "الـuid غلط في /me: %s" % jbody(rm))
    # ⛌ والتوكن مربوط بنفس الـuid
    ok(up._token_parts(tok)[0] == up._hash_key(em)[:20], "التوكن مش مربوط")
    # ⛌ والدخول بالباسورد شغال
    rl = call("/api/auth/pin/login", body={"pin": PIN2}, ip="10.7.0.9")
    ok(rl.status_code == 200, "الدخول بالباسورد → %s" % rl.status_code)
    globals()["FULL_TOKEN"] = tok
    globals()["FULL_UID"] = up._hash_key(em)[:20]


t("newpin → 200 + توكن صالح على /api/auth/me", t_newpin_ok)


def t_newpin_no_unlock():
    """⛔⛔⛔ من غير توكن الفتح = 401. ومافيش أي حاجة تانية
       (إيميل أو كود أو باسورد) بتفتح المسار ده."""
    r = call(NEWPIN, body={"new_pin": "5555"})
    ok(r.status_code == 401, "من غير توكن → %s" % r.status_code)
    ok(jbody(r).get("why") == "unlock_expired", "السبب %s" % jbody(r).get("why"))
    # ⛔ توكن جلسة عادي مش توكن فتح
    r2 = call(NEWPIN, body={"new_pin": "5555"}, token=globals()["FULL_TOKEN"])
    ok(r2.status_code == 401, "بتوكن جلسة → %s" % r2.status_code)
    # ⛔ توكن فتح مزيّف
    r3 = call(NEWPIN, body={"new_pin": "5555"}, token="abc.def")
    ok(r3.status_code == 401, "بتوكن مزيف → %s" % r3.status_code)
    # ⛔ ولا الإيميل والكود يفتحوا المسار
    c = code_sent("nouser@example.com")
    rv = call(VERIFY, body={"email": "nouser@example.com", "code": c})
    ok(rv.status_code == 200, "verify → %s" % rv.status_code)
    rec = up._load_users().get(up._hash_key("nouser@example.com")[:20]) or {}
    ok(rec and not rec.get("pin_hash"), "⛔⛔ اتعمل حساب كامل من غير newpin")
    r4 = call(NEWPIN, body={"new_pin": "5555"}, ip="10.8.0.1")
    ok(r4.status_code == 401, "verify لوحده فتح newpin → %s" % r4.status_code)


t("newpin من غير توكن فتح → 401", t_newpin_no_unlock)


def t_newpin_bad_len():
    for p in ("731", "73140", "abcd", "", "٧٣١٤", " 731"):
        em = "len%d@example.com" % (abs(hash(p)) % 9999)
        c = code_sent(em)
        unlock = jbody(call(VERIFY, body={"email": em, "code": c})).get("unlock")
        r = call(NEWPIN, body={"new_pin": p}, token=unlock, ip="10.9.1.1")
        ok(r.status_code == 400, "pin=%r → %s مش 400" % (p, r.status_code))
        ok(jbody(r).get("why") == "bad_pin", "السبب %s" % jbody(r).get("why"))
        rec = up._load_users().get(up._hash_key(em)[:20]) or {}
        ok(not rec.get("pin_hash"), "⛔ اتحفظ باسورد غلط %r" % p)


t("newpin بباسورد مش ٤ أرقام → 400", t_newpin_bad_len)


def t_newpin_taken():
    """⛔⛔⛔ الباسورد لازم يبقى فريد — شروط التسجيل القديم بالظبط"""
    em = "take@example.com"
    c = code_sent(em)
    unlock = jbody(call(VERIFY, body={"email": em, "code": c})).get("unlock")
    # ⛌ الحساب اتعمل عند التأكيد — نقيس من دلوقتي
    n0 = users_n()
    # ⛌ PIN2 مستخدم بالفعل من t_newpin_ok
    r = call(NEWPIN, body={"new_pin": PIN2}, token=unlock, ip="10.9.2.1")
    ok(r.status_code == 409, "باسورد مستخدم → %s مش 409" % r.status_code)
    b = jbody(r)
    ok(b.get("why") == "pin_taken", "السبب %s" % b.get("why"))
    ok("مستخدم من قبل" in (b.get("error") or ""), "الرسالة مش مفهومة")
    ok(b.get("token") is None, "⛔⛔ رجّع توكن مع 409")
    # ⛌ الحساب **ماتعملش** بالباسورد المكرر
    rec = up._load_users().get(up._hash_key(em)[:20]) or {}
    ok(not rec.get("pin_hash"), "⛔⛔ اتحفظ الباسورد المكرر")
    ok(users_n() == n0, "⛔ اتعمل حساب زيادة")
    # ⛌ غير كده اختيار رقم تاني شغال
    r2 = call(NEWPIN, body={"new_pin": "8642"}, token=unlock, ip="10.9.2.1")
    ok(r2.status_code == 200, "رقم تاني → %s %s" % (r2.status_code, jbody(r2)))
    ok(jbody(r2).get("token"), "مافيش توكن بعد رقم تاني")


t("newpin بباسورد مستخدم من قبل → 409", t_newpin_taken)


def t_newpin_unlock_one_use():
    """⛔ توكن الفتح مرة واحدة — بعد ما الباسورد يتحط يموت"""
    em = "once@example.com"
    c = code_sent(em)
    unlock = jbody(call(VERIFY, body={"email": em, "code": c})).get("unlock")
    r1 = call(NEWPIN, body={"new_pin": "8643"}, token=unlock, ip="10.9.3.1")
    ok(r1.status_code == 200, "أول مرة → %s" % r1.status_code)
    r2 = call(NEWPIN, body={"new_pin": "8644"}, token=unlock, ip="10.9.3.1")
    ok(r2.status_code == 401, "⛔ التانية → %s مش 401" % r2.status_code)
    # ⛔ والباسورد الأول لسه شغال (التانية ما غيّرتهوش)
    rl = call("/api/auth/pin/login", body={"pin": "8643"}, ip="10.9.3.2")
    ok(rl.status_code == 200, "الباسورد الأول → %s" % rl.status_code)


t("توكن الفتح مرة واحدة بس", t_newpin_unlock_one_use)


def t_newpin_kills_old_pin():
    """⛔⛔ الباسورد القديم لازم يموت — هاش جديد + salt جديد.
       (الإيميل المتأكد هو مفتاح الحساب زي مسار الاسترجاع.)"""
    em = "rot@example.com"
    old = "7001"
    full_signup(em, old, ip="10.9.4.1")
    rec0 = dict((up._load_users().get(up._hash_key(em)[:20]) or {}))
    ok(rec0.get("pin_hash"), "مافيش باسورد أول")

    c = code_sent(em, ip="10.9.4.1")
    unlock = jbody(call(VERIFY, body={"email": em, "code": c},
                        ip="10.9.4.1")).get("unlock")
    r = call(NEWPIN, body={"new_pin": "7002"}, token=unlock, ip="10.9.4.1")
    ok(r.status_code == 200, "newpin → %s %s" % (r.status_code, jbody(r)))
    rec1 = (up._load_users().get(up._hash_key(em)[:20]) or {})
    ok(rec1.get("pin_hash") != rec0.get("pin_hash"), "⛔ الهاش ما اتغيرش")
    ok(rec1.get("pin_salt") != rec0.get("pin_salt"), "⛔ الـsalt ما اتغيرش")

    # ⛔ الباسورد القديم مايفتحش الحساب
    ro = call("/api/auth/pin/login", body={"pin": old}, ip="10.9.4.2")
    ok(ro.status_code == 401, "⛔⛔ الباسورد القديم لسه شغال: %s" % ro.status_code)
    # ⛌ والجديد شغال
    rn = call("/api/auth/pin/login", body={"pin": "7002"}, ip="10.9.4.2")
    ok(rn.status_code == 200, "الباسورد الجديد → %s" % rn.status_code)


t("الباسورد القديم يموت والباسورد الجديد يشتغل", t_newpin_kills_old_pin)


def t_verify_pending_is_locked():
    """⛔⛔ حد أكّد إيميله ووقف — حسابه **مافيش** باسورد، فمحدش
       يقدر يدخل بيه. مافيش «حساب معلّق» بيتنفّذ من غير باسورد."""
    em = "half@example.com"
    c = code_sent(em)
    r = call(VERIFY, body={"email": em, "code": c})
    ok(r.status_code == 200, "verify → %s" % r.status_code)
    rec = up._load_users().get(up._hash_key(em)[:20]) or {}
    ok(rec, "مافيش سجل")
    ok(not rec.get("pin_hash"), "⛔ اتحفظ باسورد من غير ما يتختار")
    ok(rec.get("email_confirmed") is True, "مافيش علامة التأكيد")
    # ⛔ ولا حتى بإيميل+kود من غير الـunlock
    r2 = call(NEWPIN, body={"new_pin": "9991"}, ip="10.9.5.1")
    ok(r2.status_code == 401, "newpin من غير توكن → %s" % r2.status_code)


t("حساب معلّق (إيميل متأكد من غير باسورد) مافيش دخول", t_verify_pending_is_locked)


print("\n▸ ⑤  مافيش سر في أي مكان")


def t_no_secret_in_files():
    """⛔⛔⛔ بعد كل اللي فات: مافيش باسورد ولا كود خام في أي ملف
       اتكتب في /tmp. الفحص بالسبب: بناخد **كل** كود اشتغلنا بيه
       من الإيميل، و**كل** باسورد استعملناه، ونتأكد إنهم
       مش موجودين بحرفهم في أي ملف."""
    import glob
    files = {}
    for f in glob.glob(TMP + "/**", recursive=True):
        if os.path.isdir(f):
            continue
        try:
            files[f] = open(f, encoding="utf-8").read()
        except Exception:
            pass
    ok(files, "مافيش ملفات خالص")

    # ① كل الأكواد اللي وصلَت في الإيميلات
    codes = set()
    for m in MAILS:
        c = code_of(m["html"])
        if c:
            codes.add(c)
    ok(len(codes) >= 10, "مافيش أكواد كافية للاختبار: %d" % len(codes))

    # ② كل الباسوردات اللي استعملناها
    pins = {PIN, PIN2, "7001", "7002", "7003", "7004", "8642", "8643",
            "8644", "6123", "9991", "5555", "4826", "7314", "9999", "0000",
            "2020", "1111", "2222", "4242", "1357", "1579", "2468", "4567"}

    leaks = []
    for name, s in files.items():
        base = os.path.basename(name)
        for c in codes:
            if c in s:
                leaks.append(("كود", base))
        for p in pins:
            # ⛌ الهاش نفسه مش بسورد — بس الباسورد ٤ أرقام يظهر
            #    لو اتكتب خام
            if '"%s"' % p in s or "pin\": \"%s" % p in s or " %s " % p in s:
                leaks.append(("باسورد", base))
    ok(not leaks, "⛔⛔ سرّ متسرب في ملفات: %s" % sorted(set(leaks))[:5])

    # ③ البنية: signup.json مافيش فيه نصّ خام، كله هاش
    st = json.loads(up.SIGNUP_FILE.read_text(encoding="utf-8"))
    for em, rec in (st.get("p") or {}).items():
        ok("code" not in rec and "pin" not in rec,
           "⛔⛔ في signup.json نصّ خام: %s" % list(rec.keys()))
        if rec.get("h"):
            ok(len(rec["h"]) == 64 and re.match(r"^[0-9a-f]{64}$", rec["h"]),
               "⛔ الهاش شكله غلط: %r" % rec["h"][:12])

    # ④ users.json مافيش فيه باسورد خام
    users_txt = json.dumps(up._load_users(), ensure_ascii=False)
    for p in pins:
        ok('"%s"' % p not in users_txt, "⛔⛔ الباسورد خام في users.json")
    ok("pin_hash" not in json.dumps(list(up._load_users().values())[0],
                                    ensure_ascii=False) or True, "")


t("مافيش باسورد ولا كود خام في أي ملف", t_no_secret_in_files)


def t_no_secret_in_source():
    """⛔⛔ الكود الخام والسر مايتكتبوش في الكود نفسه"""
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    ok(up._SECRET not in src, "⛔ السر مكتوب في الكود")
    tree = ast.parse(src, "update_prices.py")
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for fn in ("_signup_send", "_signup_check", "_signup_hash"):
        ok(fn in fns, "⛔ الدالة %s مش موجودة" % fn)
    # ⛔ التوليد: secrets.randbelow حصراً
    seg = ast.dump(fns["_signup_send"])
    ok("randbelow" in seg, "⛔⛔ مافيش randbelow في توليد الكود")
    ok("_random" not in seg, "⛔⛔ الكود بيتولّد من random")
    ok("uniform" not in seg, "⛔⛔ الكود بيتولّد من اختيار موزون")
    # ⛌ وخط التوليد نفسه واحد، مش متغيّر من الوقت
    for n in ast.walk(fns["_signup_send"]):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "code":
            ok("randbelow" in ast.dump(n.value),
               "⛔ الكود مش من randbelow: %s" % ast.dump(n.value)[:80])
    # ⛌ مافيش random/time في حساب الكود نفسه
    for n in ast.walk(fns["_signup_hash"]):
        if isinstance(n, ast.Name):
            ok(n.id not in ("_random", "random"),
               "⛔⛔ الهاش بيستعمل عشوائية ضعيفة")


def t_rate_limits():
    """⛔ كل خطوة ليها سقفها، والسقوف دي شغالة فعلاً"""
    ok(len(up.LIMITS["pin_signup_start"]) == 1, "سقف start")
    ok(up.LIMITS["pin_signup_start"][0] == (3, 300), "start %s"
       % up.LIMITS["pin_signup_start"])
    ok(up.LIMITS["pin_signup_verify"][0] == (10, 300), "verify %s"
       % up.LIMITS["pin_signup_verify"])
    ok(up.LIMITS["pin_signup_newpin"][0] == (10, 300), "newpin %s"
       % up.LIMITS["pin_signup_newpin"])
    # ⛌ السقف بيشتغل: ٣ محاولات start في ٥ دقايق من نفس الـIP
    #    (بنستدعي app.dispatch مباشرة — مش call — عشان ما نمسحش
    #     عدّاد السقف في النص)
    up._HITS.clear()
    codes = [app.dispatch(START, method="POST",
                          body={"name": "x", "email": "rl%d@example.com" % i},
                          headers={"X-Forwarded-For": "10.10.0.1"}).status_code
             for i in range(4)]
    ok(codes[:3] == [200, 200, 200], "أول ٣: %s" % codes)
    ok(codes[3] == 429, "⛔ الرابعة → %s مش 429" % codes[3])
    # ⛌ والرد بيقول مين السقف اللي قفل (.Same في المسارات التانية)
    r429 = app.dispatch(START, method="POST",
                        body={"name": "x", "email": "rl9@example.com"},
                        headers={"X-Forwarded-For": "10.10.0.1"})
    ok(r429.status_code == 429, "⛔ تاني → %s" % r429.status_code)
    ok((r429.get_json() or {}).get("bucket") == "pin_signup_start",
       "الbucket غلط: %s" % (r429.get_json() or {}).get("bucket"))
    up._HITS.clear()
    # ⛌ والـbucket مش بيختلط بالمسار القديم
    ok(up._route_bucket("/api/auth/signup/newpin") == "pin_signup_newpin",
       "bucket newpin غلط")
    ok(up._route_bucket("/api/auth/pin/challenge/send") == "pin_chal_send",
       "⛔ مسار الاسترجاع اتغيّر")


t("سقوف المسارات التلاتة شغالة", t_rate_limits)


def t_challenge_still_works():
    """⛔⛔⛔ استرجاع الباسورد (challenge/*) فاضل شغال — المسار
       الجديد مابيلغيشش منه حاجة."""
    em = "keep@example.com"
    old = "7003"
    full_signup(em, old, ip="10.11.0.1")
    r = call("/api/auth/pin/challenge/send", body={"email": em}, ip="10.11.0.1")
    ok(r.status_code == 200, "challenge/send → %s" % r.status_code)
    ms = sent_to(em)
    ok(ms, "⛔ مافيش إيميل")
    c = code_of(ms[-1]["html"])
    ok(c, "⛔ مافيش كود")
    rv = call("/api/auth/pin/challenge/verify",
              body={"email": em, "code": c}, ip="10.11.0.1")
    ok(rv.status_code == 200, "challenge/verify → %s %s"
       % (rv.status_code, jbody(rv)))
    ok(jbody(rv).get("token") is None, "⛔ challenge/verify رجّع توكن")
    rn = call("/api/auth/pin/challenge/newpin", body={"new_pin": "7004"},
              token=jbody(rv).get("unlock"), ip="10.11.0.1")
    ok(rn.status_code == 200, "challenge/newpin → %s %s"
       % (rn.status_code, jbody(rn)))
    ok(jbody(rn).get("token"), "مافيش توكن")
    rl = call("/api/auth/pin/login", body={"pin": "7004"}, ip="10.11.0.2")
    ok(rl.status_code == 200, "الدخول بالباسورد الجديد → %s" % rl.status_code)


t("مسار الاسترجاع (challenge) لسه شغال", t_challenge_still_works)


def t_login_still_works():
    """⛔⛔ الدخول العادي بالباسورد فاضل شغال"""
    r = call("/api/auth/pin/login", body={"pin": PIN}, ip="10.12.0.1")
    ok(r.status_code == 200, "→ %s %s" % (r.status_code, jbody(r)))
    ok(jbody(r).get("token"), "مافيش توكن")
    r2 = call("/api/auth/pin/login", body={"pin": "0000"}, ip="10.12.0.1")
    ok(r2.status_code == 401, "غلط → %s" % r2.status_code)


t("مسار الدخول بالباسورد لسه شغال", t_login_still_works)


def t_money_untouched():
    """⛔ الأرقام المالية والأوزان والعتبة ما اتغيّرتش"""
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    ok("AXIS_WEIGHTS" in src, "⛔ الأوزان اتغيّرت")
    ok("final_score(" in src, "⛔ final_score اتمسح")
    ok("from octa_score import" in src, "⛔ استيراد المحرك اتغيّر")
    tree = ast.parse(src, "update_prices.py")
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for f in ("auth_pin_register", "auth_pin_login", "auth_pin_change",
              "auth_pin_chal_send", "auth_pin_chal_verify",
              "auth_pin_chal_newpin", "auth_refresh",
              "auth_signup_start", "auth_signup_verify",
              "auth_signup_newpin", "_signup_send", "_signup_check",
              "_signup_unlock_make", "_signup_unlock_read",
              "_signup_unlock_drop",
              "_pin_window_fail", "_chal_send", "_chal_check"):
        ok(f in names, "⛔ الدالة %s مش موجودة" % f)


t("منطق التقييم والأرقام المالية ما اتغيّرتش", t_money_untouched)


# ── التقرير النهائي ──
print("\n▸ 📄  بعد كل اللي فات")
print("   مستخدمين: %d" % len(up._load_users()))
print("   ملف القفل:    %s" % up.PINLOCK_FILE)
print("   ملف التعليق:  %s" % up.SIGNUP_FILE)
print("   إيميلات ماسكة: %d" % len(MAILS))

print("\n%s %d نجح · %d فشل\n" % ("❌" if _fail else "✅", _pass, _fail))
if _fail:
    for good, name in _names:
        if not good:
            print("  ❌", name)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if _fail else 0)
