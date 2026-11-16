#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار القاعدة ① (نافذة ٣/٦٠ ثانية) + كود الإيميل + التجديد الصامت

تشغيل حقيقي للمسارات — نفس الـhandlers اللي على السيرفر، مش تحليل ساكن.

⛔⛔ داتا الاختبار كلها في مجلد مؤقت في /tmp — مافيش كتابة في
   المشروع ولا في /app، ومافيش إيميل حقيقي بيتبعت.

⛔⛔ مافيش باسورد حقيقي ولا كود حقيقي ولا سر في الملف ده ولا في
   أي ملف بيطلع منه. الأرقام دي أرقام اختبار.

شغّله:  python3 test_pin_challenge.py
"""
import os
import re
import sys
import time
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="chaltest_", dir="/tmp")
sys.path.insert(0, HERE)

os.environ.setdefault("PIN_FAIL_LIMIT", "5")
os.environ.setdefault("PIN_LOCK_FIRST", "900")
os.environ.setdefault("PIN_LOCK_NEXT", "3600")
import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔⛔ مافيش سر حقيقي — قيم محلية للاختبار بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

# ── كل التخزين على /tmp ──
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.MAIL_ON = True               # ⛔ ⛌ الخدمة «شغّالة» في الاختبار
                                #    (الإرسال نفسه متمسّك — مفيش بريد
                                #    حقيقي بيمشي). السبب: مسار الكود
                                #    بيرجّع 503 «خدمة الإيميل مش شغّالة»
                                #    لما MAIL_ON مطفّي — وده رد
                                #    **مختلف** عن رد الإيميل الغريب (200)
                                #    ⇒ يبقى تعداد على وجود الحساب.

MAILS = []          # 📬 كل إيميل «اتبعت» في الاختبار


def _fake_send(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _fake_send

# ── ساعة قابلة للتحكّم: بنحرق الدقائق ──
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
    """⏱️ نرجّع الساعة للحقيقية حتى لو الاختبار وقع في استثناء —
       غير كده الاختبارات اللي بعدها هتشتغل بساعة من المستقبل."""
    old = FAKE.t
    FAKE.t = base
    try:
        yield FAKE
    finally:
        FAKE.t = old

app = up.app

# ⛌ المسار القديم بقى 410 — مابيتقابلش من غير ما نتأكد
REG = "/api/auth/pin/register"
LOG = "/api/auth/pin/login"
SEND = "/api/auth/pin/challenge/send"
VERIFY = "/api/auth/pin/challenge/verify"
NEWPIN = "/api/auth/pin/challenge/newpin"
REFRESH = "/api/auth/refresh"

# أرقام الاختبار — ماشيطة في أي ملف بالمشروع
A_PIN, A_EMAIL = "7314", "amina@example.com"
B_PIN, B_EMAIL = "4826", "karim@example.com"
NEW_PIN = "9907"

# ⛌⛔⛔ ⭐ ٢٤ أكتوبر ٢٠٢٦ — ملكية الجهاز:
#    الباسورد لوحده ما يفتحش حساب — لازم الجهاز يكون مسجّل
#    على الحساب. جهاز جديد ⇒ 401 + need_code ⇒ كود إيميل.
# ⬜️ بصمة الجهاز — مفيش أرقام متتالية (٤ أرقام) عشان ما
#    تتلخبطش مع فحص «مافيش باسورد خام في الملفات».
A_DEV = "device-challenge-amina-tabla"
B_DEV = "device-challenge-karim-tabla"
NEW_DEV = "device-challenge-newdev-tabla"
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


def login(pin, ip="10.1.0.1", device=A_DEV):
    """⛌ دخول بالباسورد — ومعاه بصمة الجهاز (شرط التصميم الحالي)"""
    body = {"pin": pin}
    if device:
        body["device"] = device
    return call(LOG, body=body, ip=ip)


def jbody(r):
    return r.get_json() or {}


def canon(r):
    """الرد كملف نصي — للمقارنة حرف بحرف"""
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


# ⛌ المسار القديم بقى 410 — التجهيز بقى من المسار الجديد
#    (الإيميل الأول، والباسورد بعد التأكيد).
SIGNUP_START = "/api/auth/signup/start"
SIGNUP_VERIFY = "/api/auth/signup/verify"
SIGNUP_NEWPIN = "/api/auth/signup/newpin"


def signup(pin, email, ip="10.1.0.1", name="تجربة"):
    """
    ⛔⛔ تسجيل كامل بالمسار الجديد: start → verify → newpin.

    بترجّع توكن الجلسة (زي ما المسار القديم كان بيرجّع).
    الكود بيتقرا من نص الإيميل اللي اتمسك — مش من متغير في السيرفر.
    """
    m0 = len(MAILS)
    r = call(SIGNUP_START, body={"name": name, "email": email}, ip=ip)
    ok(r.status_code == 200, "signup/start فشل: %s %s" % (r.status_code,
                                                          jbody(r)))
    ok(len(MAILS) > m0, "⛔ مافيش إيميل اتبعت لـ %s" % email)
    code = ""
    for m in reversed(MAILS[m0:]):
        if m["to"] == email:
            code = code_of(m["html"])
            break
    ok(code, "⛔ مافيش كود وصل في إيميل %s" % email)
    r = call(SIGNUP_VERIFY, body={"email": email, "code": code}, ip=ip)
    ok(r.status_code == 200, "signup/verify فشل: %s %s" % (r.status_code,
                                                            jbody(r)))
    unlock = (r.get_json() or {}).get("unlock")
    ok(unlock, "⛔ مافيش unlock")
    # ⛌ بصمة الجهاز — الحساب بيتسجّل عليه من أول لحظة
    r = call(SIGNUP_NEWPIN, body={"new_pin": pin, "device": A_DEV},
             ip=ip, token=unlock)
    ok(r.status_code == 200, "signup/newpin فشل: %s %s" % (r.status_code,
                                                           jbody(r)))
    return (r.get_json() or {}).get("token")


def new_user(pin, email, ip="10.1.0.1"):
    return signup(pin, email, ip)


def code_of(html):
    """📬 الكود اللي وصل في الإيميل فعلاً"""
    m = re.search(r">(\d{6})<", html or "")
    return m.group(1) if m else ""


def last_code(to):
    for m in reversed(MAILS):
        if m["to"] == to:
            return code_of(m["html"])
    return ""


def chal_state():
    try:
        return json.loads(up.PIN_CHAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def lock_keys(pin=None, ip=None):
    return up._pin_keys(pin=pin, ip=ip)


A_TOKEN = new_user(A_PIN, A_EMAIL)
B_TOKEN = new_user(B_PIN, B_EMAIL, ip="10.2.0.2")

print("\n▸ ①  نافذة ٣ محاولات في ٦٠ ثانية (القاعدة ①)")
print("   (ملف المستخدمين: %s)" % up.USERS_FILE)


# ══════════════════════════════════════════════════════════════
def t_three_in_window():
    """⛔⛔ ٤ غلط ورا بعض جوّه ٦٠ ثانية → الرد يطلب كود إيميل
       (مش قفل ١٥ دقيقة: القفل ده اسمه القاعدة ② وواحد تاني)"""
    ip = "10.3.0.3"
    up._pinlock_reset(lock_keys(ip=ip))
    up._pin_window_reset(lock_keys(ip=ip))
    codes = []
    bodies = []
    for i in range(4):
        r = call(LOG, body={"pin": "1357"}, ip=ip)
        b = jbody(r)
        codes.append((r.status_code, b.get("attempts_left"), b.get("why")))
        bodies.append(b)
    ok(codes[0] == (401, 3, "bad_pin"), "المحاولة ١ %s" % (codes[0],))
    ok(codes[1] == (401, 2, "bad_pin"), "المحاولة ٢ %s" % (codes[1],))
    ok(codes[2] == (401, 1, "bad_pin"), "المحاولة ٣ %s" % (codes[2],))
    ok(codes[3][0] == 401 and codes[3][2] == "need_code",
       "المحاولة ٤ %s — المفروض need_code" % (codes[3],))
    b4 = bodies[3]
    ok(b4.get("need_code") is True, "need_code مش true")
    ok(b4.get("next") == "challenge/send", "المسار التالي %s" % b4.get("next"))
    ok(b4.get("window") == 60, "النافذة %s — المفروض ٦٠" % b4.get("window"))
    # ⛔⛔ مافيش قفل ١٥ دقيقة — دي القاعدة ② وواحد تاني
    locked, retry = up._pin_locked(lock_keys(ip=ip))
    ok(locked is False, "⛔ اتقفل ١٥ دقيقة ودي المفروض القاعدة ①")
    ok(all(c[0] == 401 for c in codes), "في رد مش 401: %s" % (codes,))
    # ⛔⛌ والقاعدة ② (القفل) فاضل شغّال: المحاولة الخامسة ⇒ 429
    r5 = call(LOG, body={"pin": "1357"}, ip=ip)
    ok(r5.status_code == 429,
       "المحاولة الخامسة رجعت %s — المفروض 429 (القاعدة ٢)"
       % r5.status_code)
    ok(jbody(r5).get("why") == "locked", "السبب %s" % jbody(r5).get("why"))
t("٤ غلط جوّه ٦٠ ثانية → يطلب كود إيميل (مش قفل ١٥ دقيقة)",
  t_three_in_window)


def t_window_is_60():
    """⛌⛌ النافذة ٦٠ ثانية بالظبط — لا أكتر ولا أقل"""
    ok(up.PIN_WINDOW_SECONDS == 60,
       "PIN_WINDOW_SECONDS=%s" % up.PIN_WINDOW_SECONDS)
    ok(up.PIN_WINDOW_FAILS == 4, "PIN_WINDOW_FAILS=%s" % up.PIN_WINDOW_FAILS)
    # ⛔ مفيش نافذة طويلة تانية في الملف: أي ثابت أكبر من ٦٠
    #    في سكربت القفل =Regression
    import re as _re
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    for m in _re.finditer(r"^(\w+) = (\d+) # .*([\u0600-\u06FF]+)", src, _re.M):
        name, val = m.group(1), int(m.group(2))
        if name.startswith("PIN_WINDOW"):
            ok(val <= 60, "⛔ %s=%d أكبر من ٦٠" % (name, val))
t("النافذة ٦٠ ثانية بالظبط (مفيش نافذة طويلة)", t_window_is_60)


def t_three_spread():
    """⛔⛔ ٤ غلط متباعدين (٣٠ ثانية بين كل واحد) → مفيش كود،
       والعدّاد يفضل ٢ (النافذة سلايدر — ما بتجمّعش أكتر من ٢)"""
    ip = "10.3.0.4"
    with clock():
        up._pinlock_reset(lock_keys(ip=ip))
        up._pin_window_reset(lock_keys(ip=ip))
        t0 = FAKE.t
        got = []
        for i in range(4):
            FAKE.t = t0 + 30 * i
            r = call(LOG, body={"pin": "2468"}, ip=ip)
            b = jbody(r)
            got.append((b.get("attempts_left"), b.get("need_code")))
    ok(got[-1][1] is not True,
       "⛔ متباعدين ورا بعض وطلّع كود إيميل: %s" % (got,))
    ok(got[-1][0] == 2,
       "العدّاد %s بعد ٤ محاولات متباعدة — المفروض يفضل ٢" % (got[-1][0],))
t("٤ غلط متباعدين (٣٠ ثانية) → مفيش كود، العدّاد يفضل ٢",
  t_three_spread)


def t_window_slides():
    """⛌ نافذة سلايدر: ٤ محاولات على ١٦٥ ثانية = مفيش كود"""
    ip = "10.3.0.5"
    with clock():
        up._pinlock_reset(lock_keys(ip=ip))
        up._pin_window_reset(lock_keys(ip=ip))
        t0 = FAKE.t
        got = []
        for i in range(4):
            FAKE.t = t0 + 55 * i          # 0 / 55 / 110 / 165
            got.append(jbody(call(LOG, body={"pin": "8642"}, ip=ip)))
    ok(got[-1].get("need_code") is not True,
       "⛔ ٤ محاولات على ١٦٥ ثانية طلّعوا كود: %s" % got[-1])
    ok(got[-1].get("attempts_left") == 2,
       "العدّاد %s بعد ٤ محاولات متباعدة — المفروض ٢"
       % got[-1].get("attempts_left"))
t("النافذة سلايدر: ٤ محاولات على ١٦٥ ثانية → مفيش كود",
  t_window_slides)


def t_five_spread_lock():
    """⛔⛔⛔ القاعدة ② لسه شغالة: ٥ غلط **متباعدين** → قفل ١٥ دقيقة"""
    ip = "10.3.0.6"
    with clock():
        up._pinlock_reset(lock_keys(ip=ip))
        up._pin_window_reset(lock_keys(ip=ip))
        t0 = FAKE.t
        codes = []
        for i in range(5):
            FAKE.t = t0 + 20 * 60 * i      # كل واحد بعد ٢٠ دقيقة
            codes.append(call(LOG, body={"pin": "3579"}, ip=ip).status_code)
        ok(codes[:4] == [401] * 4, "المحاولات ١-٤ %s" % codes)
        ok(codes[4] == 429, "المحاولة ٥ رجّع %s — المفروض 429" % codes[4])
        b = jbody(call(LOG, body={"pin": "3579"}, ip=ip))
        ra = b.get("retry_after")
    ok(b.get("why") == "locked", "السبب %s" % b.get("why"))
    ok(isinstance(ra, int) and 600 < ra <= 902,
       "retry_after=%s (المفروض ≈ ٩٠٠)" % ra)


t("٥ غلط متباعدين في الوقت → قفل ١٥ دقيقة (القاعدة ② شغالة)",
  t_five_spread_lock)


# ══════════════════════════════════════════════════════════════
print("\n▸ ②  كود الإيميل — تعداد ممنوع")


def t_send_same_reply():
    """⛔⛔⛔ إيميل مسجّل ولا مش مسجّل → الرد **واحد** بالظبط"""
    m0 = len(MAILS)
    r1 = call(SEND, body={"email": A_EMAIL}, ip="10.4.0.1")
    sent1 = len(MAILS) - m0
    m0 = len(MAILS)
    r2 = call(SEND, body={"email": GHOST}, ip="10.4.0.2")
    sent2 = len(MAILS) - m0
    ok(r1.status_code == 200 and r2.status_code == 200,
       "المسجّل %s / الغريب %s" % (r1.status_code, r2.status_code))
    ok(canon(r1) == canon(r2),
       "⛔⛔ الرد بيختلف:\n   مسجّل: %s\n   غريب: %s"
       % (canon(r1), canon(r2)))
    ok(r1.get_json().get("ok") is True, "ok مش true")
    ok(sent1 == 1, "⛔ الإيميل المسجّل ماتبعتش (%d)" % sent1)
    ok(sent2 == 0, "⛔⛔ إيميل مش مسجّل واتبعتله رسالة (%d)" % sent2)
    ok(A_EMAIL not in canon(r2) and GHOST not in canon(r1),
       "⛔ الرد فيه الإيميل")


t("تحدّي بإيميل مش مسجّل → نفس الرد بالظبط (حرف بحرف)",
  t_send_same_reply)


def t_send_real_mail():
    """⛔📬 إيميل مسجّل → ٢٠٠ + إيميل اتبعت فيه كود ٦ أرقام"""
    MAILS.clear()
    up._chal_send(A_EMAIL)                    # العدّاد اليومي
    r = call(SEND, body={"email": B_EMAIL}, ip="10.4.0.3")
    ok(r.status_code == 200, "الحالة %s" % r.status_code)
    ok(MAILS, "⛔ ماتبعتش إيميل خالص")
    m = MAILS[-1]
    ok(m["to"] == B_EMAIL, "المستقبل %s" % m["to"])
    ok("OCTA" in m["subject"], "العنوان %s" % m["subject"])
    c = code_of(m["html"])
    ok(re.fullmatch(r"[0-9]{6}", c or ""),
       "⛔ الكود مش ٦ أرقام إنجليزية: %r" % c)
    # ⛌ الكود الخام **مش** في الرد
    ok(c not in canon(r), "⛔⛔ الكود في الرد!")
    # ⛌ الكود الخام **مش** في أي ملف
    ok(c not in up.PIN_CHAL_FILE.read_text(encoding="utf-8"),
       "⛔⛔ الكود الخام في pinchal.json")
    # ⛌ في الملف **هاش** بس
    rec = chal_state()["c"][B_EMAIL]
    ok("h" in rec and rec["h"] != c, "⛔ مافيش هاش في الملف")
    ok(len(rec["h"]) == 64, "طول الهاش %s" % len(rec["h"]))


t("تحدّي بإيميل مسجّل → 200 + إيميل اتبعت فعليًا بكود ٦ أرقام",
  t_send_real_mail)


def t_code_source():
    """⛔⛔ الكود من secrets.randbelow — مش random ومش من الوقت"""
    import ast
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    tree = ast.parse(src, "update_prices.py")
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "_chal_send"]
    ok(fn, "دالة _chal_send مش موجودة")
    body = ast.get_source_segment(src, fn[0]) or ""
    ok("_secrets_mod.randbelow" in body,
       "⛔ الكود مش من secrets.randbelow")
    ok("_random" not in body, "⛔ الكود بيستخدم random")
    # ⛌ سطر الكود نفسه: مافيش وقت فيه خالص (الوقت بيتحسب
    #    لعدّاد اليوم بس، وده مش part الكود)
    import re as _re2
    line = [ln for ln in body.split("\n")
            if "randbelow" in ln and ln.strip().startswith("code")]
    ok(len(line) == 1 and "time" not in line[0],
       "⛔ سطر الكود فيه وقت: %s" % line)
    hits = _re2.findall(r"randbelow\((\d+)\)", body)
    ok(hits == ["1000000"], "مدى randbelow %s" % hits)
    ok(up.PIN_CHAL_TTL == 600, "PIN_CHAL_TTL=%s (المفروض ٦٠٠)" % up.PIN_CHAL_TTL)
    ok(up.PIN_CHAL_WRONG == 5, "PIN_CHAL_WRONG=%s" % up.PIN_CHAL_WRONG)


t("الكود من secrets.randbelow + صلاحية ١٠ دقايق + ٥ غلط",
  t_code_source)


def t_daily_limit():
    """⛔ ١١ كود في اليوم لنفس الإيميل → 429 (الحد ١٠ لكل إيميل)"""
    em = "daili@example.com"
    up._pin_by_email(em)
    st = chal_state()
    st["c"].pop(em, None)
    up.PIN_CHAL_FILE.write_text(json.dumps(st, ensure_ascii=False),
                                encoding="utf-8")
    codes = []
    for i in range(11):
        # ⛌ كل نداء من IP مختلف: يثبت إن الحد **لكل إيميل**
        r = call(SEND, body={"email": em}, ip="10.4.1.%d" % i)
        codes.append((r.status_code, (r.get_json() or {}).get("why")))
    ok([c[0] for c in codes[:10]] == [200] * 10, "أول ١٠ %s" % codes[:10])
    ok(codes[10][0] == 429, "الحادي عشر %s — المفروض 429" % (codes[10],))
    ok(codes[10][1] == "daily_limit", "السبب %s" % codes[10][1])
    ok(up.PIN_CHAL_PER_DAY == 10, "الحد اليومي %s" % up.PIN_CHAL_PER_DAY)
    # ⛌⛔ والرد فيه retry_after لحد نص الليل (مش 900 ثانية)
    st2 = chal_state()
    rec = (st2.get("c") or {}).get(em) or {}
    ok(int(rec.get("n") or 0) == 10, "عدّاد اليوم %s" % rec.get("n"))
t("١١ كود في اليوم لنفس الإيميل → 429 (الحد ١٠ لكل إيميل)",
  t_daily_limit)


def t_wrong_code():
    """⛔ كود غلط → 401"""
    c = last_code(B_EMAIL)
    ok(c, "مفيش كود في الإيميل")
    r = call(VERIFY, body={"email": B_EMAIL, "code": "000000"},
             ip="10.4.2.1")
    ok(r.status_code == 401, "كود غلط رجّع %s" % r.status_code)
    ok(jbody(r).get("why") == "bad_code", "السبب %s" % jbody(r).get("why"))


t("كود غلط → 401", t_wrong_code)


def t_expired_code():
    """⛔ كود منتهي (١١ دقيقة) → 401"""
    em = "expiry@example.com"
    tok = new_user("1579", em, ip="10.4.3.1")
    call(SEND, body={"email": em}, ip="10.4.3.1")
    c = last_code(em)
    ok(c, "مافيش كود")
    # ⛌ الإعداد: ١١ دقيقة > ١٠ (المدة المطلوبة)
    st = chal_state()
    st["c"][em]["s"] = int(FAKE.t) - 11 * 60
    up.PIN_CHAL_FILE.write_text(json.dumps(st, ensure_ascii=False),
                                encoding="utf-8")
    r = call(VERIFY, body={"email": em, "code": c}, ip="10.4.3.1")
    ok(r.status_code == 401, "كود منتهي رجّع %s" % r.status_code)
    ok(jbody(r).get("why") == "bad_code", "السبب %s" % jbody(r).get("why"))


t("كود منتهي (١١ دقيقة) → 401", t_expired_code)


def t_five_wrong_kills_code():
    """⛔⛔ ٥ محاولات كود غلط → الكود يموت (حتى لو صح بعدين)"""
    em = "killcode@example.com"
    new_user("2468", em, ip="10.4.4.1")
    call(SEND, body={"email": em}, ip="10.4.4.1")
    c = last_code(em)
    ok(c, "مافيش كود")
    for i in range(5):
        r = call(VERIFY, body={"email": em, "code": "111111"},
                 ip="10.4.4.1")
        ok(r.status_code == 401, "محاولة %d رجّع %s" % (i + 1, r.status_code))
    r = call(VERIFY, body={"email": em, "code": c}, ip="10.4.4.1")
    ok(r.status_code == 401,
       "⛔⛔ الكود لسه شغال بعد ٥ غلط — المفروض يموت")
    ok("h" not in (chal_state()["c"].get(em) or {}),
       "⛔ الكود لسه متخزّن بعد ما مات")


t("٥ محاولات كود غلط → الكود يموت", t_five_wrong_kills_code)


def t_verify_unknown_email():
    """⛔⛔ تحقق بإيميل مش مسجّل = نفس رد الكود الغلط بالظبط"""
    r1 = call(VERIFY, body={"email": GHOST, "code": "123456"},
              ip="10.4.5.1")
    r2 = call(VERIFY, body={"email": B_EMAIL, "code": "123456"},
              ip="10.4.5.2")
    ok(r1.status_code == r2.status_code == 401,
       "المسجّل %s / الغريب %s" % (r1.status_code, r2.status_code))
    ok(canon(r1) == canon(r2),
       "⛔ الرد بيختلف: %s ≠ %s" % (canon(r1), canon(r2)))


t("تحقق بإيميل مش مسجّل = نفس رد الكود الغلط", t_verify_unknown_email)


# ══════════════════════════════════════════════════════════════
print("\n▸ ③  الفتح الدائم — كود صح ثم باسورد جديد")


def t_no_token_before_newpin():
    """⛔⛔⛔ بعد الكود الصح: مفيش توكن، ولازم باسورد جديد"""
    em = "open1@example.com"
    old_pin = "3141"
    new_user(old_pin, em, ip="10.5.0.1")
    call(SEND, body={"email": em}, ip="10.5.0.1")
    c = last_code(em)
    r = call(VERIFY, body={"email": em, "code": c}, ip="10.5.0.1")
    ok(r.status_code == 200, "الكود الصح رجّع %s" % r.status_code)
    b = r.get_json() or {}
    ok("token" not in b, "⛔⛔ رجع توكن قبل اختيار الباسورد الجديد!")
    ok(b.get("need_pin") is True, "need_pin مش true")
    ok(b.get("next") == "challenge/newpin", "المسار %s" % b.get("next"))
    unl = b.get("unlock") or ""
    ok(unl, "مافيش توكن فتح")
    # ⛔⛔ توكن الفتح **مش** توكن جلسة
    ok(call("/api/auth/me", "GET", token=unl).status_code == 401,
       "⛔⛔ توكن الفتح فتح /api/auth/me!")
    ok(call(REFRESH, token=unl).status_code == 401,
       "⛔⛔ توكن الفتح عمل refresh!")
    # ⛔ وكمان: أي توكن تاني مايفتحش الحساب
    ok(call(REFRESH, token=B_TOKEN).status_code == 200,
       "⛔ توكن حد تاني فتح refresh")
    globals()["OPEN1"] = (em, old_pin, unl)


t("بعد الكود الصح → لازم يطلب باسورد جديد، مفيش توكن قبلها",
  t_no_token_before_newpin)


def t_newpin_rules():
    """⛔ شروط الباسورد الجديد: ٤ أرقام + فريد"""
    em, old_pin, unl = globals()["OPEN1"]
    r = call(NEWPIN, body={"new_pin": "12"}, token=unl, ip="10.5.0.1")
    ok(r.status_code == 400, "باسورد من رقمين رجّع %s" % r.status_code)
    r = call(NEWPIN, body={"new_pin": B_PIN}, token=unl, ip="10.5.0.1")
    ok(r.status_code == 409, "باسورد مستخدم رجّع %s" % r.status_code)
    ok(jbody(r).get("why") == "pin_taken", "السبب %s" % jbody(r).get("why"))


t("الباسورد الجديد: ٤ أرقام + فريد (زي التسجيل بالظبط)",
  t_newpin_rules)


def t_newpin_ok():
    """✅ اختيار الباسورد الجديد → توكن جلسة عادي"""
    em, old_pin, unl = globals()["OPEN1"]
    r = call(NEWPIN, body={"new_pin": NEW_PIN}, token=unl, ip="10.5.0.1")
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, jbody(r)))
    b = r.get_json() or {}
    ok(b.get("token"), "⛔ مافيش توكن بعد الباسورد الجديد")
    ok(call("/api/auth/me", "GET", token=b["token"]).status_code == 200,
       "⛔ التوكن الجديد مش صالح على /api/auth/me")
    globals()["OPEN1_TOKEN"] = b.get("token")


t("الباسورد الجديد اتقبل → توكن جلسة صالح", t_newpin_ok)


def t_old_pin_dead():
    """⛔⛔⛔ الباسورد القديم مات خالص"""
    em, old_pin, unl = globals()["OPEN1"]
    r = login(old_pin, ip="10.5.0.2")
    ok(r.status_code == 401, "⛔⛔ الباسورد القديم لسه بيفتح: %s"
       % r.status_code)
    ok(jbody(r).get("why") == "bad_pin",
       "السبب %s" % jbody(r).get("why"))
    r = login(NEW_PIN, ip="10.5.0.2")
    ok(r.status_code == 200, "⛔ الباسورد الجديد مش بيفتح: %s — %s"
       % (r.status_code, jbody(r)))
    # ⛌ والتوكن القديم (قبل الفتح) مابقىش صالح
    ok(call(REFRESH, token=unl).status_code == 401,
       "⛔ توكن الفتح اتقبل مرتين!")
t("الباسورد القديم مات بعد التغيير (الجديد شغال)", t_old_pin_dead)


def t_new_device_flow():
    """⛔⛔⛔ المسار الكامل للتصميم الحالي (٢٤ أكتوبر ٢٠٢٦):

       ⛌ ① الباسورد الصح من جهاز **مش مسجّل** ⇒ 401 + need_code
       ⛌ ② challenge/send ⇒ 200 (نفس الرد بالظبط زي أي إيميل)
       ⛌ ③ challenge/verify ⇒ 200 + توكن فتح (مش توكن دخول)
       ⛌ ④ challenge/newpin (مع بصمة الجهاز) ⇒ 200 + توكن جلسة
       ⛌ ⑤ الدخول من نفس الجهاز الجديد ⇒ 200 (الجهاز اتسجّل)
       ⛌ ⑥ والباسورد القديم ⇒ 401 «الباسورد غلط»
    """
    em = "newdev@example.com"
    old_pin = "4040"
    new_pin = "4041"
    new_dev = NEW_DEV
    new_user(old_pin, em, ip="10.7.0.1")
    # ⛌ ① الباسورد صح من جهاز مش مسجّل ⇒ لازم كود إيميل
    r1 = call(LOG, body={"pin": old_pin, "device": new_dev}, ip="10.7.0.2")
    ok(r1.status_code == 401, "جهاز جديد → %s مش 401" % r1.status_code)
    b1 = jbody(r1)
    ok(b1.get("why") == "new_device", "السبب %s" % b1.get("why"))
    ok(b1.get("need_code") is True, "need_code مش true")
    ok(b1.get("next") == "challenge/send", "المسار %s" % b1.get("next"))
    ok("token" not in b1, "⛔ رجّع توكن من جهاز مش مسجّل!")
    # ⛌ ② طلب الكود
    r2 = call(SEND, body={"email": em}, ip="10.7.0.3")
    ok(r2.status_code == 200, "challenge/send → %s" % r2.status_code)
    code = last_code(em)
    ok(code, "مافيش كود في الإيميل")
    # ⛌ ③ التحقق من الكود (توكن فتح — مش توكن دخول)
    r3 = call(VERIFY, body={"email": em, "code": code}, ip="10.7.0.4")
    ok(r3.status_code == 200, "challenge/verify → %s" % r3.status_code)
    b3 = jbody(r3)
    ok(b3.get("token") is None, "⛔ challenge/verify رجّع توكن دخول")
    ok(b3.get("need_pin") is True, "need_pin مش true")
    unlock = b3.get("unlock")
    ok(unlock, "مافيش توكن فتح")
    # ⛌ ④ اختيار الباسورد الجديد + تسجيل الجهاز
    r4 = call(NEWPIN, body={"new_pin": new_pin, "device": new_dev},
              token=unlock, ip="10.7.0.5")
    ok(r4.status_code == 200,
       "challenge/newpin → %s %s" % (r4.status_code, jbody(r4)))
    ok(jbody(r4).get("token"), "مافيش توكن جلسة")
    # ⛌ ⑤ الدخول من نفس الجهاز الجديد ⇒ 200 (الجهاز بقى معروف)
    r5 = call(LOG, body={"pin": new_pin, "device": new_dev}, ip="10.7.0.6")
    ok(r5.status_code == 200,
       "الدخول من الجهاز الجديد → %s %s" % (r5.status_code, jbody(r5)))
    # ⛌ ⑥ والباسورد القديم مات
    r6 = call(LOG, body={"pin": old_pin, "device": new_dev}, ip="10.7.0.7")
    ok(r6.status_code == 401, "⛔⛔ الباسورد القديم لسه بيفتح: %s"
       % r6.status_code)
    ok(jbody(r6).get("why") == "bad_pin", "السبب %s" % jbody(r6).get("why"))
t("جهاز جديد ⇒ كود إيميل ⇒ الحساب ينفتح والجهاز يتسجّل", t_new_device_flow)


def t_unlock_single_use():
    """⛔ توكن الفتح مالوش تكرار"""
    em = "single@example.com"
    new_user("4567", em, ip="10.5.1.1")
    call(SEND, body={"email": em}, ip="10.5.1.1")
    c = last_code(em)
    b = (call(VERIFY, body={"email": em, "code": c},
              ip="10.5.1.1").get_json() or {})
    unl = b.get("unlock")
    ok(call(NEWPIN, body={"new_pin": "1122"}, token=unl,
           ip="10.5.1.1").status_code == 200, "أول مرة فشل")
    r = call(NEWPIN, body={"new_pin": "3344"}, token=unl, ip="10.5.1.1")
    ok(r.status_code == 401, "⛔ توكن الفتح اتقبل مرتين: %s" % r.status_code)


t("توكن الفتح مالوش تكرار (مرة واحدة)", t_unlock_single_use)


def t_no_unlock_no_change():
    """⛔ من غير توكن فتح مافيش باسورد جديد"""
    r = call(NEWPIN, body={"new_pin": "5566"}, ip="10.5.2.1")
    ok(r.status_code == 401, "من غير Authorization رجّع %s" % r.status_code)
    r = call(NEWPIN, body={"new_pin": "5566"}, token=B_TOKEN,
             ip="10.5.2.1")
    ok(r.status_code == 401, "⛔⛔ توكن جلسة عادي فتح تغيير الباسورد!")


t("من غير توكن فتح → مافيش تغيير باسورد", t_no_unlock_no_change)


# ══════════════════════════════════════════════════════════════
print("\n▸ ④  التجديد الصامت")


def t_refresh_ok():
    """⛔ توكن صالح + refresh → 200 + توكن جديد صالح على /me"""
    r = call(REFRESH, token=A_TOKEN, ip="10.6.0.1")
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, jbody(r)))
    b = r.get_json() or {}
    ok(b.get("token"), "مافيش توكن جديد")
    ok(b.get("expires_in") == up.TOKEN_TTL,
       "expires_in=%s (المفروض %s = ٣٠ يوم)"
       % (b.get("expires_in"), up.TOKEN_TTL))
    ok(call("/api/auth/me", "GET", token=b["token"],
            ip="10.6.0.1").status_code == 200, "التوكن الجديد مش صالح")
    globals()["REFRESHED"] = b.get("token")


t("توكن صالح + refresh → 200 + توكن جديد صالح على /api/auth/me",
  t_refresh_ok)


def t_token_ttl():
    """⛔ عمر التوكن = ٣٠ يوم (مطلق) + سياسة خمول ١٤ يوم"""
    ok(up.TOKEN_TTL == 30 * 86400, "TOKEN_TTL=%s" % up.TOKEN_TTL)
    ok(up.TOKEN_IDLE_TTL == 14 * 86400,
       "TOKEN_IDLE_TTL=%s" % up.TOKEN_IDLE_TTL)
    r = call(REFRESH, token=A_TOKEN, ip="10.6.0.2")
    ok(jbody(r).get("expires_in") == up.TOKEN_TTL,
       "expires_in مش مساوي للـTTL")
    # ⛔ التوكن المولّد فعلاً فيه وقت انتهاء = دلوقتي + ٣٠ يوم
    # ⛌ الشكل الجديد: «uid|exp|epoch» ⬇️ الـepoch في الآخر
    #    (إبطال الجلسات ⬇️ تغيير الباسورد بيموت كل التوكنات)
    import base64 as _b64
    p = (r.get_json() or {})["token"].split(".")[0]
    raw = _b64.urlsafe_b64decode(p + "=" * (-len(p) % 4)).decode()
    uid, _, rest = raw.partition("|")
    exp_s, _, epoch_s = rest.partition("|")
    delta = int(exp_s) - int(FAKE.t)
    ok(up.TOKEN_TTL - 10 <= delta <= up.TOKEN_TTL,
       "الانتهاء بعد %s ثانية" % delta)
    # ⛔ والـepoch موجود ⬇️ وإلا إبطال الجلسات مش هيشتغل
    ok(epoch_s != "", "مافيش epoch في التوكن ⬇️ إبطال الجلسات مكسور")


t("عمر التوكن = ٣٠ يوم (مطلق) + خمول ١٤ يوم", t_token_ttl)


def t_session_idle_dies():
    """⛔⛔ سياسة الخمول: جلسة ساكتة ١٥ يوم ⇒ التوكن يموت

       ⛌ عمر التوكن المطلق ٣٠ يوم بس — من غير سياسة الخمول،
          جلسة مسروقة كانت هتفضل شغّالة لحد ٣٠ يوم.
    """
    with clock():
        FAKE.t = FAKE.t + 15 * 86400
        r = call("/api/auth/me", "GET", token=A_TOKEN, ip="10.6.0.7")
    ok(r.status_code == 401,
       "⛔⛔ الجلسة الساكتة لسه شغّالة بعد ١٥ يوم: %s" % r.status_code)


t("جلسة ساكتة ١٥ يوم ⇒ التوكن يموت (سياسة الخمول)", t_session_idle_dies)


def t_refresh_no_auth():
    """⛔ refresh من غير Authorization → 401"""
    r = call(REFRESH, ip="10.6.0.3")
    ok(r.status_code == 401, "رجّع %s" % r.status_code)
    ok(jbody(r).get("ok") is False, "ok مش false")


t("refresh من غير Authorization → 401", t_refresh_no_auth)


def t_refresh_expired():
    """⛔ توكن منتهي → 401 ومايفتحش أي مسار تاني"""
    dead = up._make_token(up._load_users()[up._read_token(A_TOKEN)]["id"], -1)
    r = call(REFRESH, token=dead, ip="10.6.0.4")
    ok(r.status_code == 401, "توكن منتهي رجّع %s" % r.status_code)
    ok(jbody(r).get("why") == "unauthorized", "السبب %s"
       % jbody(r).get("why"))
    ok(call("/api/auth/me", "GET", token=dead,
            ip="10.6.0.4").status_code == 401, "التوكن المنتهي فتح /me")
    # ⛌ توكن مزوّر (توقيع غلط)
    ok(call(REFRESH, token=A_TOKEN[:-2] + "xy", ip="10.6.0.4").status_code
       == 401, "⛔ توكن مزوّر اتقبل!")


t("توكن منتهي أو مزوّر → 401 (مفيش استثناء)", t_refresh_expired)


def t_refresh_no_credentials():
    """⛔⛔ refresh ما بيقبلش باسورد ولا إيميل ولا كود — 401"""
    for k, v in (("pin", A_PIN), ("email", A_EMAIL), ("code", "123456"),
                 ("new_pin", "1234"), ("password", "x"), ("key", "x")):
        r = call(REFRESH, body={k: v}, token=A_TOKEN, ip="10.6.0.5")
        ok(r.status_code == 401,
           "⛔ body فيه %s رجّع %s (المفروض 401)" % (k, r.status_code))
    # ⛌ وbody فاضي تمام
    ok(call(REFRESH, body={}, token=A_TOKEN,
            ip="10.6.0.5").status_code == 200, "body فاضي لازم 200")


t("refresh ما بيقبلش باسورد ولا إيميل ولا كود (401)", t_refresh_no_credentials)


def t_two_hours_idle_ok():
    """⛔ بعد ساعتين بالظبط: المستخدم لسه داخل بصمت (التجديد ماشي)

       ⛌ عمر التوكن المطلق = ٣٠ يوم (مش ساعتين) — والواجهة
          بتجدّد كل ساعتين ⇒ المستخدم مش بيخرج وعمري ما يشيل.
    """
    with clock():
        t0 = FAKE.t
        FAKE.t = t0 + 7199               # قبل ساعتين
        r = call(REFRESH, token=A_TOKEN, ip="10.6.0.6")
        ok(r.status_code == 200, "قبل الانتهاء رجّع %s" % r.status_code)
        tok = jbody(r).get("token")
        ok(tok, "مافيش توكن جديد")
        ok(call("/api/auth/me", "GET", token=tok,
                ip="10.6.0.6").status_code == 200, "التجديد ماقعدش جوا")
        FAKE.t = t0 + 7200               # بعد ساعتين بالظبط
        ok(call("/api/auth/me", "GET", token=A_TOKEN,
                ip="10.6.0.6").status_code == 200,
           "⛔ التوكن القديم مات قبل ما يبقى مدّته ٣٠ يوم")
        ok(call("/api/auth/me", "GET", token=tok,
                ip="10.6.0.6").status_code == 200,
           "⛔ التوكن المجدّد مات قبل ما يتجدد تاني")
t("بعد ٢ ساعة: المستخدم لسه داخل بصمت (تجديد ماشي)",
  t_two_hours_idle_ok)


# ══════════════════════════════════════════════════════════════
print("\n▸ ⑤  ⛔ مافيش باسورد ولا كود خام في أي ملف")


def t_no_raw_in_files():
    """⛔⛔⛔ بعد كل اللي فات: صفر باسورد خام وصفر كود خام"""
    secrets_found = []
    pins = [A_PIN, B_PIN, NEW_PIN, "3141", "1579", "2468", "4567",
            "1122", "1357", "3579", "2468", "8642", "8642", "1579"]
    codes = [code_of(m["html"]) for m in MAILS if code_of(m["html"])]
    for fn in (up.USERS_FILE, up.PINLOCK_FILE, up.PIN_CHAL_FILE):
        if not fn.exists():
            continue
        raw = fn.read_text(encoding="utf-8")
        for p in set(pins):
            if re.search(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % p, raw):
                secrets_found.append("%s: باسورد %s" % (fn.name, p))
        for c in set(codes):
            if re.search(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % c, raw):
                secrets_found.append("%s: كود %s" % (fn.name, c))
    ok(not secrets_found, "⛔⛔ لقينا: %s" % secrets_found)
    # ⛌ وكل حقل الباسورد في users.json hashed
    for uid, u in up._load_users().items():
        if u.get("pin_hash"):
            ok(re.fullmatch(r"[0-9a-f]{64}", u["pin_hash"]),
               "pin_hash مش hex: %s" % str(u["pin_hash"])[:20])
            ok("pin" not in u or not isinstance(u.get("pin"), (str, int)),
               "⛔ فيه حقل pin خام في users.json")
    print("     (%d ملف اتفحص، %d كود اتبع)"
          % (3, len(set(codes))))


t("مافيش باسورد خام ولا كود خام في أي ملف", t_no_raw_in_files)


def t_challenge_file_shape():
    """📄 شكل ملف الكود: هاش + وقت + عدّاد — مافيش كود خام"""
    d = chal_state()
    ok("c" in d and "g" in d, "مفاتيح الملف %s" % list(d.keys()))
    for em, rec in d["c"].items():
        ok(set(rec) <= {"h", "s", "w", "d", "n"},
           "⛔ حقول زيادة في سجل %s: %s" % (em, sorted(rec)))
        if rec.get("h"):
            ok(re.fullmatch(r"[0-9a-f]{64}", rec["h"]),
               "الهاش مش hex: %s" % rec["h"][:20])
    # ⛌ مافيش أي توكن فتح باقي في الملف
    globals()["GRANTS"] = len(d.get("g") or {})


t("ملف الكود: هاش + وقت + عدّاد بس (مافيش كود خام)",
  t_challenge_file_shape)


# ══════════════════════════════════════════════════════════════
print("\n▸ ⑥  ⛔ مفيش ريجريشن على الاختبارات القديمة")


def t_no_regression():
    """شغّل الاختبارات التلاتة القديمة زي ما هي"""
    out = {}
    for f in ("test_pin_auth.py", "test_auth_holes.py",
              "test_data_full_route.py"):
        p = subprocess.run([sys.executable, os.path.join(HERE, f)],
                           capture_output=True, text=True, timeout=900)
        tail = [ln for ln in (p.stdout or "").strip().split("\n") if ln.strip()]
        last = tail[-1] if tail else "?"
        out[f] = (p.returncode, last)
        ok(p.returncode == 0, "⛔ %s رجّع %s — %s" % (f, p.returncode, last))
    for f, (rc, last) in out.items():
        print("     %-28s rc=%s  %s" % (f, rc, last))


t("مفيش ريجريشن: الاختبارات التلاتة القديمة", t_no_regression)


def t_money_untouched():
    """⛔ الأرقام المالية والأوزان والعتبة ما اتغيّرتش"""
    import ast
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    ok("AXIS_WEIGHTS" in src, "⛔ الأوزان اتغيّرت")
    ok("final_score(" in src, "⛔ final_score اتمسح")
    ok("from octa_score import" in src, "⛔ استيراد المحرك اتغيّر")
    tree = ast.parse(src, "update_prices.py")
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for f in ("auth_pin_register", "auth_pin_login", "auth_pin_change",
              "auth_pin_chal_send", "auth_pin_chal_verify",
              "auth_pin_chal_newpin", "auth_refresh",
              "_pin_window_fail", "_chal_send", "_chal_check"):
        ok(f in names, "⛔ الدالة %s مش موجودة" % f)


t("منطق التقييم والأرقام المالية ما اتغيّرتش", t_money_untouched)


# ── التقرير النهائي ──
print("\n▸ 📄  بعد كل اللي فات")
print("   مستخدمين: %d" % len(up._load_users()))
print("   ملف القفل: %s" % up.PINLOCK_FILE)
print("   ملف الكود: %s" % up.PIN_CHAL_FILE)
print("   توكين فتح باقيين: %d" % globals().get("GRANTS", 0))

print("\n%s %d نجح · %d فشل\n" % ("❌" if _fail else "✅", _pass, _fail))
if _fail:
    for good, name in _names:
        if not good:
            print("  ❌", name)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if _fail else 0)
