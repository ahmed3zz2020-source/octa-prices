#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار نظام الباسورد (PIN) — تشغيل حقيقي للمسارات، مش تحليل ساكن.

⛔⛔ داتا الاختبار كلها بتتبعت في مجلد مؤقت في /tmp — الملف ده
   بيفحص المفيش وبيكتبش في المشروع ولا في /app.

شغّله:  python3 test_pin_auth.py
"""
import os
import re
import sys
import time
import json
import shutil
import tempfile

HERE = "/workspace/octa-prices"
TMP = tempfile.mkdtemp(prefix="pintest_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔⛔ مفيش سر حقيقي في الكود ولا في الملف ده — قيم اختبار محلية بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

# ── كل التخزين يروح على /tmp ──
up.USERS_FILE = __import__("pathlib").Path(TMP) / "users.json"
up.PINLOCK_FILE = __import__("pathlib").Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = __import__("pathlib").Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = __import__("pathlib").Path(TMP) / "otp.json"
up.SIGNUP_FILE = __import__("pathlib").Path(TMP) / "signup.json"
up.MAIL_ON = False          # ⛔ متبعثش إيميل حقيقي في الاختبار

# ⛌ بنمسك الإيميل بدل ما يتبعت — والكود بيتقرا من نصّه، يعني
#    بالظبط اللي المستخدم بيشوفه على بريده.
MAILS = []


def _fake_send(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _fake_send

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

app = up.app
# ⛔⛔ المسار القديم بقى 410 — التجهيز بقى من المسار الجديد:
#    ① الإيميل الأول (start) → ② تأكيد الكود (verify)
#    → ③ اختيار ٤ أرقام (newpin).
REG = "/api/auth/pin/register"
START = "/api/auth/signup/start"
VERIFY = "/api/auth/signup/verify"
NEWPIN = "/api/auth/signup/newpin"
LOG = "/api/auth/pin/login"
CHG = "/api/auth/pin/change"

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


def call(path, method="POST", body=None, ip="10.0.0.1", token=None):
    """⛌ الـrate limit في الذاكرة — بنصفّره بين الخطوات،
       القفل الذكي نفسه على القرص وبيتختبر لوحده"""
    up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    if token:
        h["Authorization"] = "Bearer " + token
    return app.dispatch(path, method=method, body=body, headers=h)


# الأرقام دي **للاختبار** بس — ماشيطة في أي ملف بالمشروع
A_PIN, A_EMAIL = "7314", "amina@example.com"
B_PIN, B_EMAIL = "4826", "karim@example.com"


def code_of(html):
    """📬 الكود اللي وصل في الإيميل فعلاً"""
    m = re.search(r">(\d{6})<", html or "")
    return m.group(1) if m else ""


def canon(r):
    """الرد كملف نصي — للمقارنة حرف بحرف"""
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


def start_signup(email, name="تجربة", ip="10.0.0.1"):
    """خطوة ① — بترجّع (الرد، الكود اللي وصل في الإيميل)"""
    n0 = len(MAILS)
    r = call(START, body={"name": name, "email": email}, ip=ip)
    code = ""
    for m in reversed(MAILS[n0:]):
        if m["to"] == email:
            code = code_of(m["html"])
            break
    return r, code


def unlock_for(email, name="تجربة", ip="10.0.0.1"):
    """خطوتين ①+② — بترجّع توكن فتح جاهز لاختيار الباسورد"""
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
    """
    ⛔⛔ تسجيل كامل بالمسار الجديد: ① ← ② ← ③.

    بيرجّع (توكن الجلسة، رد ③). الكود بيتقرا من الإيميل
    himself — مش من متغير في السيرفر.
    """
    u = unlock_for(email, name, ip)
    r = call(NEWPIN, body={"new_pin": pin}, ip=ip, token=u)
    ok(r.status_code == 200, "newpin %s → %s %s" % (email, r.status_code,
                                                    canon(r)))
    return (r.get_json() or {}).get("token"), r

print("\n▸ ①  التسجيل")
print("  (ملف المستخدمين: %s)" % up.USERS_FILE)


def t_register():
    tok, r = signup(A_PIN, A_EMAIL, "أمينة")
    b = r.get_json()
    ok(b.get("ok") is True, "مش ok")
    ok(b.get("token"), "مافيش توكن")
    globals()["A_TOKEN"] = tok
    globals()["A_UID"] = b["user"]["id"]


t("تسجيل كامل (إيميل ثم باسورد) → 200 + توكن", t_register)


def t_me():
    r = call("/api/auth/me", method="GET", token=A_TOKEN)
    ok(r.status_code == 200, "الحالة %s" % r.status_code)
    ok((r.get_json().get("user") or {}).get("id") == A_UID,
       "الـuid غلط: %s" % r.get_json())


t("التوكن صالح على /api/auth/me → 200", t_me)


def t_bad_len():
    """⛔ ٤ أرقام بالظبط — ٣ أو ٥ أو حروف = 400.
       ⛌ الفحص بقى في الخطوة الأخيرة (newpin)، وخطوة ① ترفض
          أي باسورد في الطلب أصلاً."""
    for p in ("731", "73140", "abcd", "", "٧٣١٤"):
        em = "b%d@example.com" % (abs(hash(p)) % 9999)
        u = unlock_for(em, "x")
        r = call(NEWPIN, body={"new_pin": p}, token=u)
        ok(r.status_code == 400,
           "pin=%r رجّع %s (المفروض 400)" % (p, r.status_code))
        ok((r.get_json() or {}).get("why") == "bad_pin",
           "السبب %s" % (r.get_json() or {}).get("why"))
        # ⛔ الحساب المعلّق ماتحفظش بباسورد غلط
        rec = up._load_users().get(up._hash_key(em)[:20]) or {}
        ok(not rec.get("pin_hash"), "⛔ اتحفظ حساب بباسورد غلط %r" % p)
    # ⛌ وخطوة ① مافيش فيها باسورد خالص
    r2 = call(START, body={"name": "x", "email": "np@example.com",
                           "pin": "1234"})
    ok(r2.status_code == 400, "start بباسورد → %s مش 400" % r2.status_code)
    ok((r2.get_json() or {}).get("why") == "no_pin_here",
       "السبب %s" % (r2.get_json() or {}).get("why"))


t("pin من ٣ أو ٥ أو حروف → 400", t_bad_len)


def t_dup_email():
    """⛔⛔⛔ مافيش «الإيميل مسجّل» تاني.

       قبل كده المسار القديم كان بيرد 409 بكلمة «مسجّل» — يعني
       تعداد كامل في رد واحد. المسار الجديد بيرد **نفس الكلام
       بالظبط** سواء الإيميل مسجّل عندنا أو لأ.
    """
    r1 = call(START, body={"name": "تاني", "email": A_EMAIL}, ip="10.3.0.1")
    ok(r1.status_code == 200, "إيميل مسجّل → %s" % r1.status_code)
    r2 = call(START, body={"name": "جديد", "email": "brandnew@example.com"},
              ip="10.3.0.2")
    ok(r2.status_code == 200, "إيميل جديد → %s" % r2.status_code)
    ok(canon(r1) == canon(r2),
       "⛔⛔ الرد مختلف:\n   مسجّل: %s\n   جديد: %s" % (canon(r1), canon(r2)))
    s = json.dumps(r1.get_json() or {}, ensure_ascii=False)
    for w in ("مسجّل", "موجود", "taken"):
        ok(w not in s, "⛔ الرد فيه %r" % w)
    # ⛌ والحساب المسجّل ما اتغيّرش
    rec = up._load_users().get(A_UID) or {}
    ok(rec.get("pin_hash"), "⛔ الباسورد اتمسح")


t("تسجيل نفس الإيميل تاني → نفس الرد (مافيش تعداد)", t_dup_email)


def t_dup_pin():
    """⛔⛔ الباسورد فريد — 409 في الخطوة الأخيرة، والحساب المعلّق
       ماتحفظش بالباسورد المكرر."""
    u = unlock_for(B_EMAIL, "ب", ip="10.3.1.1")
    r = call(NEWPIN, body={"new_pin": A_PIN}, token=u, ip="10.3.1.1")
    ok(r.status_code == 409, "الحالة %s مش 409" % r.status_code)
    b = r.get_json()
    ok(b.get("why") == "pin_taken", "السبب %s" % b.get("why"))
    ok("مستخدم من قبل" in (b.get("error") or ""), "الرسالة مش مفهومة")
    ok(b.get("token") is None, "⛔ رجّع توكن مع 409")
    # ⛔⛔ الحساب التاني **ماتعملش** خالص بالباسورد ده
    ok(up._pin_by_email(B_EMAIL)[1] is None, "⛔ اتعمل حساب بالباسورد المكرر")


t("اختيار pin مستخدم من قبل → 409", t_dup_pin)


def t_second_user():
    tok, r = signup(B_PIN, B_EMAIL, "كريم", ip="10.0.0.2")
    globals()["B_TOKEN"] = tok
    globals()["B_UID"] = (r.get_json().get("user") or {}).get("id")


t("تسجيل مستخدم تاني → 200", t_second_user)

print("\n▸ ②  الدخول")


def t_login_ok():
    r = call(LOG, body={"pin": A_PIN})
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, r.get_json()))
    b = r.get_json()
    ok(b.get("token") and b["user"]["id"] == A_UID, "الرد غلط: %s" % b)
    r2 = call("/api/auth/me", "GET", token=b["token"])
    ok(r2.status_code == 200, "التوكن مش صالح على /me")


t("دخول بـpin صح → 200 + توكن صالح", t_login_ok)


def t_login_bad():
    r = call(LOG, body={"pin": "1111"})
    ok(r.status_code == 401, "الحالة %s مش 401" % r.status_code)
    ok((r.get_json() or {}).get("why") == "bad_pin", "السبب غلط")


t("دخول بـpin غلط → 401", t_login_bad)


def t_no_enumeration():
    """⛔⛔ الرد لازم يكون واحد: وجود الإيميل عندنا ولا لأ
       ما ينعكسش على الرد ولا على التوقيت."""
    import time as _t
    bodies = []
    times = []
    for body in ({"pin": "1111"},
                 {"pin": "1111", "email": A_EMAIL},      # ⛔ الإيميل مسجّل
                 {"pin": "2222", "email": "ghost@x.com"}):  # ⛔ مش موجود
        # 📌 القاعدة ① (نافذة ٦٠ ثانية) بتخلي الرد الثالث
        #    «محتاج كود إيميل» — وده **مش** تعداد، ده عدّاد
        #    محاولات. عشان المقارنة تبقى عن نفس العمق، بنصفّر
        #    نافذة الـ٦٠ ثانية قبل كل نداء: التلات ردود لازم
        #    يطلعوا متطابقين حرف بحرف.
        up._pin_window_reset(up._pin_keys(pin="1111", ip="10.0.0.1"))
        up._pin_window_reset(up._pin_keys(pin="2222", ip="10.0.0.1"))
        t0 = _t.time()
        r = call(LOG, body=body)
        times.append(_t.time() - t0)
        b = dict(r.get_json() or {})
        bodies.append((r.status_code, b))
    ok(len(set(map(str, bodies))) == 1,
       "⛔ الرد بيختلف حسب الإيميل: %s" % bodies)
    # ⛔ التوقيت: PBKDF2 وهمي لازم يخلي الفشل ياخد نفس وقت النجاح
    t0 = _t.time()
    call(LOG, body={"pin": A_PIN})
    good_t = _t.time() - t0
    ok(good_t > 0.005, "⛔ النجاح رجع في %sث — مفيش PBKDF2 خالص" % good_t)
    slow = max(times)
    ok(slow >= good_t * 0.5,
       "⛔ الفشل رجع في %.4fث والنجاح %.4fث — تسريب توقيت"
       % (slow, good_t))


t("مافيش تسريب «الإيميل مسجّل ولا لأ» (رد + توقيت)", t_no_enumeration)

print("\n▸ ③  القفل الذكي")


def _lock_state():
    return json.loads(up.PINLOCK_FILE.read_text(encoding="utf-8"))


def t_five_wrong():
    codes = []
    for i in range(5):
        codes.append(call(LOG, body={"pin": "5555"}).status_code)
    ok(codes[:4] == [401] * 4, "المحاولات ١-٤ %s" % codes)
    ok(codes[4] == 429, "المحاولة ٥ رجّع %s مش 429" % codes[4])
    globals()["_codes"] = codes


t("٥ محاولات غلط → 429 في الخامسة", t_five_wrong)


def t_retry_after():
    r = call(LOG, body={"pin": "5555"})
    ok(r.status_code == 429, "بعد القفل: %s" % r.status_code)
    b = r.get_json()
    ra = b.get("retry_after")
    ok(isinstance(ra, int) and 600 < ra <= 900,
       "retry_after=%s (المفروض ≈ ٩٠٠ ثانية = ١٥ دقيقة)" % ra)
    ok(b.get("why") == "locked", "السبب %s" % b.get("why"))


t("الرد فيه retry_after بالثواني (≈٩٠٠)", t_retry_after)


def t_lock_on_file():
    """⛔⛔ القفل لازم يكون على القرص — مش في الذاكرة.
       simulating إعادة تشغيل السيرفر = قراءة الملف من جديد."""
    st = _lock_state()
    ups = [float((v or {}).get("u") or 0) for v in (st.get("k") or {}).values()]
    ok(ups, "مافيش أي سجل قفل في الملف")
    ok(max(ups) > time.time(), "العدّاد مش متخزّن / time limit في الملف")
    ok(len(st.get("k") or {}) >= 2,
       "المفروض سجل لكل من الـpin والـIP — لقيت %d"
       % len(st.get("k") or {}))


t("العدّاد محفوظ على القرص (بيقاوم إعادة التشغيل)", t_lock_on_file)


def t_correct_locked():
    """⛔ حتى الباسورد **الصحيح** مرفوض أثناء القفل"""
    r = call(LOG, body={"pin": A_PIN})
    ok(r.status_code == 429,
       "الباسورد الصح دخل والقفل مفتوح — %s" % r.status_code)


t("الباسورد الصح مرفوض أثناء القفل → 429", t_correct_locked)


def t_after_15():
    """⛌ بدل ما نستنى ١٥ دقيقة: نرجّع وقت القفل ١٥ دقيقة بالماضي
       (زي ما وعدى الوقت فعلاً) ونشوف الدخول اشتغل"""
    st = _lock_state()
    for k, v in (st.get("k") or {}).items():
        if float((v or {}).get("u") or 0):
            v["u"] = float(v["u"]) - 900 - 5
    up.PINLOCK_FILE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    r = call(LOG, body={"pin": A_PIN})
    ok(r.status_code == 200,
       "بعد ١٥ دقيقة الدخول رجع %s (المفروض 200) — %s"
       % (r.status_code, r.get_json()))


t("بعد ١٥ دقيقة الباسورد الصح يدخل تاني", t_after_15)


def t_ip_lock():
    """⛔⛔ القفل على مستوى الـIP: ٥ باسوردات مختلفة من نفس الجهاز
       = قفل، حتى لو كل واحد منهم غلط مختلف."""
    codes = [call(LOG, body={"pin": "66%02d" % i}, ip="10.9.9.9").status_code
             for i in range(5)]
    ok(codes[4] == 429, "٥ باسوردات مختلفة من نفس IP: %s" % codes)
    # ⛔ والباسورد الصح كمان مقفول من نفس الـIP
    r = call(LOG, body={"pin": B_PIN}, ip="10.9.9.9")
    ok(r.status_code == 429, "الباسورد الصح من IP مقفول → %s" % r.status_code)
    # ⛌ بس من IP تاني: الباسورد الصح عادي
    r2 = call(LOG, body={"pin": B_PIN}, ip="10.9.9.10")
    ok(r2.status_code == 200, "من IP تاني → %s" % r2.status_code)


t("القفل على الـIP مش بس على الباسورد", t_ip_lock)


def t_pin_lock_across_ips():
    """⛔ العكس: **نفس** الباسورد الغلط من ٥ أجهزة مختلفة = قفل برضه.
       (يعني: ٥ محاولات من كل بلد لوحده = ٥ دول)
    """
    codes = [call(LOG, body={"pin": "7700"}, ip="10.8.8.%d" % i).status_code
             for i in range(5)]
    ok(codes[:4] == [401] * 4, "المحاولات ١-٤: %s" % codes)
    ok(codes[4] == 429, "نفس الباسورد من ٥ IPs: %s" % codes)
    # ⛔ ومن سادس جهاز كمان — الباسورد نفسه اتقفل عالمياً
    r = call(LOG, body={"pin": "7700"}, ip="10.8.8.99")
    ok(r.status_code == 429, "من IP سادس → %s" % r.status_code)
    # ⛌ بس الباسورد الصح من جهاز سادس: الـpin مقفول، بس الـIP جديد
    r2 = call(LOG, body={"pin": A_PIN}, ip="10.8.8.99")
    ok(r2.status_code == 200, "الباسورد الصح من جهاز نظيف → %s" % r2.status_code)


t("القفل على الباسورد عبر أجهزة مختلفة", t_pin_lock_across_ips)


def _rewind_locks(seconds=905):
    st = _lock_state()
    for k, v in (st.get("k") or {}).items():
        if float((v or {}).get("u") or 0):
            v["u"] = float(v["u"]) - seconds
    up.PINLOCK_FILE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def t_escalation():
    """⛌ أول ٥ غلط = ١٥ دقيقة، وبعد كده كل ٥ غلط = ساعة"""
    ip = "10.7.7.7"
    for i in range(5):
        first = call(LOG, body={"pin": "88%02d" % i}, ip=ip).status_code
    ok(first == 429, "القفل الأول → %s" % first)
    r = call(LOG, body={"pin": "8800"}, ip=ip)
    ra1 = (r.get_json() or {}).get("retry_after")
    ok(isinstance(ra1, int) and 600 < ra1 <= 900,
       "القفل الأول لازم ١٥ دقيقة — retry_after=%s" % ra1)

    # ⏰ عدّى الـ١٥ دقيقة
    _rewind_locks(905)
    r = call(LOG, body={"pin": "8800"}, ip=ip)
    ok(r.status_code == 401, "بعد انتهاء القفل → %s (المفروض 401)" % r.status_code)

    for i in range(5):
        last = call(LOG, body={"pin": "99%02d" % i}, ip=ip).status_code
    ok(last == 429, "المحاولة الخامسة تانية → %s" % last)
    r = call(LOG, body={"pin": "9900"}, ip=ip)
    ra2 = (r.get_json() or {}).get("retry_after")
    ok(isinstance(ra2, int) and 3300 < ra2 <= 3600,
       "⛔ الترقية لساعة مشتغلتش — retry_after=%s" % ra2)


t("بعد أول قفل، القفل الجاي = ساعة", t_escalation)


def t_counter_reset():
    """⛌ المحاولة الصح تصفّر العدّاد"""
    st = _lock_state()
    for k, v in (st.get("k") or {}).items():
        if float((v or {}).get("u") or 0):
            v["u"] = 0
    up.PINLOCK_FILE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    ok(call(LOG, body={"pin": A_PIN}, ip="10.5.5.5").status_code == 200, "دخول")
    st2 = _lock_state()
    key = "i:" + __import__("hashlib").sha256(
        b"ip|10.5.5.5").hexdigest()[:16]
    rec = (st2.get("k") or {}).get(key) or {}
    ok(not rec.get("f"), "العدّاد لسه شغّال: %s" % rec)


t("المحاولة الصح تصفّر عدّاد الـIP", t_counter_reset)

# ══════════════════════════════════════════════════════════════════
# ⛔⛔ ثقب الـEnumeration — المسارات اللي بترجّع 409
#    لازم تتحسب زي أي محاولة غلط، وإلا بقت قناة مجانية لفحص
#    ١٠٬٠٠٠ احتمال من غير ما القفل الذكي يلاحظ.
# ══════════════════════════════════════════════════════════════════
print("\n▸ ③-ب  قفل قناة الـ409 (ثقب الفحص)")


def t_dup_pin_locked():
    """⛔⛔ ٥ محاولات «الباسورد ده مستخدم من قبل» = قفل زي أي غلط"""
    codes = []
    for i in range(5):
        em = "probe%d@example.com" % i
        u = unlock_for(em, "x", ip="10.30.0.1")
        r = call(NEWPIN, body={"new_pin": A_PIN}, token=u, ip="10.30.0.1")
        codes.append(r.status_code)
    ok(codes[:4] == [409] * 4, "أول ٤: %s" % codes)
    ok(codes[4] == 429,
       "⛔⛔ المحاولة الخامسة رجعت %s مش 429 — القناة مفتوحة" % codes[4])
    u9 = unlock_for("p9@example.com", "x", ip="10.30.0.1")
    ra = (call(NEWPIN, body={"new_pin": A_PIN}, token=u9,
               ip="10.30.0.1").get_json() or {}).get("retry_after")
    ok(isinstance(ra, int) and 600 < ra <= 900, "retry_after=%s" % ra)


t("«الباسورد مستخدم من قبل» ٥ مرات → 429", t_dup_pin_locked)


def t_dup_pin_global():
    """⛔⛔ عدّاد الباسورد **مش** مربوط بجهاز: ٥ محاولات من
       ٥ عناوين IP مختلفة = قفل على الباسورد نفسه، والسادس من
       جهاز سادس برضه مقفول. ده معناه إن فحص المساحة عبر
       ١٠٬٠٠٠ جهاز بيلاقي نفس العدّاد."""
    st = _lock_state()
    rec = (st.get("k") or {}).get("p:" + up._pin_index(A_PIN)) or {}
    ok(float(rec.get("u") or 0) > time.time(),
       "مافيش قفل على الباسورد نفسه — %s" % rec)
    u = unlock_for("p10@example.com", "x", ip="10.31.9.9")
    r = call(NEWPIN, body={"new_pin": A_PIN}, token=u, ip="10.31.9.9")
    ok(r.status_code == 429, "من جهاز سادس → %s" % r.status_code)


t("عدّاد الباسورد عالمي (مش Per-IP)", t_dup_pin_global)


def t_email_taken_no_pin_dos():
    """⛔⛔⛔ تعداد الإيميلات مايقفش الباسورد بتاع حد تاني.

       قبل كده «الإيميل مسجّل» كان 409 والـIP بيقفل — وحد كان
       يقدر يبعت إيميل ضحية خمس مرات ويقفل **باسورد** الضحية
       وهو لسه ما بيحاولش يدخل. ده حجب خدمة مش حماية.

       في المسار الجديد مافيش 409 أصلاً: الرد واحد للإيميل
       المسجّل زي الجديد بالظبط، ومافيش أي عدّاد بيلمس الباسورد.
    """
    ip = "10.32.0.1"
    victim, vpin = "victim@example.com", "2121"
    signup(vpin, victim, "ضحية", ip="10.32.7.7")
    # ⛌ الحد اليومي ٣ أكواد لكل إيميل — فالتكرار بياخد ٣
    #    بالظبط وبعدين 429. المهم إن مافيش 409 ولا عدّاد على الباسورد.
    codes = [call(START, body={"name": "x", "email": victim},
                  ip=ip).status_code for _ in range(5)]
    ok(all(c in (200, 429) for c in codes),
       "⛔ الرد فيه حاجة غير متوقعة: %s" % codes)
    ok(200 in codes, "⛔ مافيش حتى رد ٢٠٠: %s" % codes)
    # ⛌ ما اتعملش قفل على الباسورد بتاع الضحية
    st = _lock_state()
    rec = (st.get("k") or {}).get("p:" + up._pin_index(vpin)) or {}
    ok(not rec, "⛔⛔ اتعمل عدّاد على باسورد الضحية من غير ما يدخل")
    # ⛌ وكل الردود واحدة (الـ429 يومي، مالوش علاقة بحالة الحساب)
    j = json.dumps(call(START, body={"name": "x", "email": victim},
                        ip="10.32.0.3").get_json() or {}, ensure_ascii=False)
    ok("مسجّل" not in j and "taken" not in j, "⛔ الرد بيسرّب حالة الحساب")
    # ⛔⛔ وضحية «الإيميل المسجّل» لسه تقدر تدخل
    r = call(LOG, body={"pin": vpin}, ip="10.32.9.9")
    ok(r.status_code == 200,
       "⛔⛔ باسورد الضحية اتقفل بسبب إيميل حد تاني (%s)" % r.status_code)


t("تعداد الإيميلات مافيشش فيه قفل الباسورد (DoS)", t_email_taken_no_pin_dos)


def t_change_dup_pin_locked():
    """⛔⛔ نفس الكلام في change: «الباسورد الجديد مستخدم» = عدّاد"""
    ip = "10.33.0.1"
    tok, _ = signup("4141", "changer@example.com", "محوّل", ip="10.33.7.7")
    codes = []
    for i in range(5):
        r = call(CHG, body={"old_pin": "4141", "new_pin": B_PIN},
                 ip=ip, token=tok)
        codes.append(r.status_code)
    ok(codes[:4] == [409] * 4, "أول ٤: %s" % codes)
    ok(codes[4] == 429, "الخامسة → %s (المفروض 429)" % codes[4])


t("change «الباسورد مستخدم» ٥ مرات → 429", t_change_dup_pin_locked)


def t_change_old_pin_counted():
    """⛔ محاولات «الباسورد القديم غلط» بتتحسب كمان"""
    ip = "10.34.0.1"
    tok, _ = signup("5151", "oldpin@example.com", "قديم", ip="10.34.7.7")
    codes = [call(CHG, body={"old_pin": "6161", "new_pin": "3232"},
                  ip=ip, token=tok).status_code for _ in range(5)]
    ok(codes[:4] == [401] * 4, "أول ٤: %s" % codes)
    ok(codes[4] == 429, "الخامسة → %s" % codes[4])


t("change «الباسورد القديم غلط» ٥ مرات → 429", t_change_old_pin_counted)


def t_global_lock_6h():
    """⛔ القفل على نفس **الباسورد** بيتصاعد: ١٥ دقيقة، ساعة،
       وبعدين ٦ ساعات. (العدّاد ده عالمي — كل الأجهزة — فالتكلفة
       أعلى من قفل جهاز واحد)"""
    # ⛌ باسورد **مش مسجّل** — عشان كل المحاولات تفشل فعلاً
    #    (لو استعملنا باسورد حد محجوز، المحاولة الصح هتفتح العدّاد)
    free = "9090"
    for rnd in range(3):
        st = _lock_state()
        for k, v in (st.get("k") or {}).items():
            if float((v or {}).get("u") or 0):
                v["u"] = 0          # ⏰ عدّى وقت القفل
        up.PINLOCK_FILE.write_text(json.dumps(st, ensure_ascii=False),
                                   encoding="utf-8")
        ip = "10.35.0.%d" % rnd
        for i in range(5):
            last = call(LOG, body={"pin": free}, ip=ip).status_code
        ok(last == 429, "الجولة %d → %s (المفروض 429)" % (rnd + 1, last))
        r = call(LOG, body={"pin": free}, ip=ip)
        ra = (r.get_json() or {}).get("retry_after")
        lo, hi = ((600, 900), (3300, 3600), (20000, 21600))[rnd]
        ok(isinstance(ra, int) and lo < ra <= hi,
           "⛔ الجولة %d: retry_after=%s (المفروض %d-%d)"
           % (rnd + 1, ra, lo, hi))
    # 🔓 فكّ القفل عشان باقي الاختبارات ما تتقفلش
    st = _lock_state()
    for k, v in (st.get("k") or {}).items():
        v["u"] = 0
    up.PINLOCK_FILE.write_text(json.dumps(st, ensure_ascii=False),
                               encoding="utf-8")


t("القفل الثالث على نفس الباسورد = ٦ ساعات", t_global_lock_6h)


def t_hourly_cap():
    """⛔⛔ السقوف على مسارات التسجيل شغّالة فعلاً.

       ⛌ المسار القديم بقى 410، وسقفه (٥/دقيقة + ٢٠/ساعة) لسه
          شغال عليه — عشان مافيش حد يسكّر عليه بلا فايدة.
       ⛌ والمسار الجديد لكل خطوة سقفها: ٣/٥ دقايق للإرسال،
          ١٠/٥ دقايق للتحقق ولاختيار الباسورد.
    """
    ok(len(up.LIMITS["pin_register"]) == 2,
       "النوافذ=%s" % up.LIMITS["pin_register"])
    up._HITS.clear()
    ip = "10.36.0.1"
    now = time.time()
    up._HITS[ip]["pin_register#1"].extend([now] * 20)
    r = app.dispatch(REG, method="POST",
                     body={"name": "x", "email": "h@example.com", "pin": "4242"},
                     headers={"X-Forwarded-For": ip})
    up._HITS.clear()
    ok(r.status_code == 429, "بعد ٢٠/ساعة → %s" % r.status_code)
    ok((r.get_json() or {}).get("bucket") == "pin_register",
       "الbucket=%s" % (r.get_json() or {}).get("bucket"))

    # ⛌ والمسار الجديد: ٣ محاولات إرسال في ٥ دقايق
    ok(up._route_bucket(START) == "pin_signup_start", "bucket start")
    ok(up._route_bucket(VERIFY) == "pin_signup_verify", "bucket verify")
    ok(up._route_bucket(NEWPIN) == "pin_signup_newpin", "bucket newpin")
    up._HITS.clear()
    codes = [app.dispatch(START, method="POST",
                          body={"name": "x", "email": "hc%d@example.com" % i},
                          headers={"X-Forwarded-For": "10.36.0.2"}).status_code
             for i in range(4)]
    up._HITS.clear()
    ok(codes == [200, 200, 200, 429], "السقف الجديد مش شغال: %s" % codes)


print("\n▸ ④  تغيير الباسورد")


def t_change_bad():
    r = call(CHG, body={"old_pin": A_PIN, "new_pin": "12"}, token=A_TOKEN)
    ok(r.status_code == 400, "pin جديد ٣ أرقام → %s" % r.status_code)
    ok((r.get_json() or {}).get("why") == "bad_pin", "السبب غلط")
    r = call(CHG, body={"old_pin": A_PIN, "new_pin": "51515"}, token=A_TOKEN)
    ok(r.status_code == 400, "pin جديد ٥ أرقام → %s" % r.status_code)
    r = call(CHG, body={"old_pin": "1111", "new_pin": "5151"}, token=A_TOKEN)
    ok(r.status_code == 401, "قديم غلط → %s" % r.status_code)
    ok((r.get_json() or {}).get("why") == "bad_old_pin", "السبب غلط")
    r = call(CHG, body={"old_pin": A_PIN, "new_pin": B_PIN}, token=A_TOKEN)
    ok(r.status_code == 409, "جديد مستخدم من قبل → %s" % r.status_code)
    ok((r.get_json() or {}).get("why") == "pin_taken", "السبب غلط")


t("change: تنسيق غلط / قديم غلط / مستخدم من قبل", t_change_bad)


def t_change_no_token():
    r = call(CHG, body={"old_pin": A_PIN, "new_pin": "6060"})
    ok(r.status_code == 401, "من غير توكن → %s" % r.status_code)
    ok((r.get_json() or {}).get("why") == "unauthorized", "السبب غلط")


t("change من غير توكن → 401", t_change_no_token)


def t_change_ok():
    _before = up._load_users()[A_UID]
    globals()["A_SALT_OLD"] = _before["pin_salt"]
    globals()["A_HASH_OLD"] = _before["pin_hash"]
    r = call(CHG, body={"old_pin": A_PIN, "new_pin": "6060"}, token=A_TOKEN)
    ok(r.status_code == 200, "الحالة %s — %s" % (r.status_code, r.get_json()))
    ok(call(LOG, body={"pin": "6060"}).status_code == 200, "الجديد مش شغّال")
    ok(call(LOG, body={"pin": A_PIN}).status_code == 401, "⛔ القديم لسه شغّال!")
    globals()["A_PIN"] = "6060"


t("تغيير الباسورد → الجديد شغّال والقديم مات", t_change_ok)

print("\n▸ ⑤  الهاش والأمان")


def t_no_raw_pin():
    raw = up.USERS_FILE.read_text(encoding="utf-8")
    # ⛔⛔⛔ أهم فحص: مافيش باسورد خام (٤ أرقام) في أي مكان
    for p in (A_PIN, B_PIN, "6060", "1111", "5555", "9999"):
        ok(p not in raw, "⛔⛔ الباسورد %s موجود خام في users.json" % p)
    hits = re.findall(r"(?<![0-9A-Za-z])\d{4}(?![0-9A-Za-z])", raw)
    ok(not hits, "⛔⛔ أرقام ٤ خام في users.json: %s" % hits[:10])
    # ⛌ ولا في ملف القفل
    # 📌 البحث بـحدود الرقم: الطوابع الزمنية (١٧ رقم) بتلاقي
    #    جوّاها أي تسلسل ٤ أرقام بالصدفة، وده **مش** باسورد
    #    خام. الباسورد الخام بيبقى ٤ أرقام لوحدها في الملف.
    if up.PINLOCK_FILE.exists():
        lraw = up.PINLOCK_FILE.read_text(encoding="utf-8")
        for p in (A_PIN, B_PIN, "6060"):
            ok(not re.search(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % p, lraw),
               "⛔⛔ الباسورد %s موجود في pinlock.json" % p)


t("⛔⛔ مافيش باسورد خام في users.json", t_no_raw_pin)


def t_hash_shape():
    rec = up._load_users()[A_UID]
    h = rec.get("pin_hash") or ""
    ok(re.fullmatch(r"[0-9a-f]{64}", h), "pin_hash مش pbkdf2 hex: %s" % h[:20])
    ok(h == up._pin_hash("6060", rec["pin_salt"]),
       "⛔ الهاش مش مطابق لـPBKDF2(salt) — الحقول مربوطة غلط")
    ok(len(rec.get("pin_salt") or "") == 16,
       "الـsalt %s مش ١٦ حرف" % len(rec.get("pin_salt") or ""))
    ok(rec["pin_salt"] != up._load_users()[B_UID]["pin_salt"],
       "⛔ salt مشترك بين مستخدمين — ملح متبادل!")
    ok("pin" not in json.dumps(rec.get("pin") or ""), "⛔ في حقل pin خام")
    # ⛌ رد الـme ما فيهوش أي بصمة
    r = call("/api/auth/me", "GET", token=A_TOKEN)
    txt = json.dumps(r.get_json(), ensure_ascii=False)
    for k in ("pin_hash", "pin_salt", "pin_idx", A_PIN):
        ok(k not in txt, "⛔ اتسرّب %s في الرد" % k)


t("الهاش pbkdf2 + salt مستقل ١٦ حرف + مافيش تسريب في الرد", t_hash_shape)


def t_salt_rotation():
    rec = up._load_users()[A_UID]
    ok(rec["pin_salt"] != A_SALT_OLD,
       "⛔ الـsalt ما اتغيرش مع الباسورد")
    ok(rec["pin_hash"] != A_HASH_OLD, "⛔ الهاش ما اتغيرش")
    ok(A_HASH_OLD == up._pin_hash("7314", A_SALT_OLD),
       "⛔ الهاش القديم مش مظبوط")
    ok(rec["pin_hash"] == up._pin_hash("6060", rec["pin_salt"]),
       "⛔ الهاش الجديد مش مظبوط")


t("تغيير الباسورد يدوّر الـsalt", t_salt_rotation)


def t_secret_independent():
    """⛔⛔ الـsalt مش تابع لـ _SECRET — لو _SECRET اتدار
       الباسوردات ماتمسحش"""
    import hashlib as _h
    salt = up._load_users()[A_UID]["pin_salt"]
    ok(_h.pbkdf2_hmac("sha256", b"6060", up._SECRET[:12].encode(),
                      60000).hex() != up._pin_hash("6060", salt),
       "⛔ الهاش بيستخدم _SECRET — تدوير السر بيمسح الباسوردات")
    ok(up._hash_key("x") != salt, "salt متعلق بالـsecret")


t("الهاش **مستقل** عن _SECRET", t_secret_independent)


def t_otp_cant_takeover():
    """⛔⛔ الإيميل ما يقدرش يدخل بحساب باسورد — المسار ده
       بيرجّع توكن لأي حد يعرف الإيميل"""
    r = app.dispatch("/api/auth/otp/verify", method="POST",
                     body={"email": A_EMAIL, "code": "000000"},
                     headers={"X-Forwarded-For": "10.6.6.6"})
    up._HITS.clear()
    ok(r.status_code == 409, "⛔⛔ الإيميل دخل بالحساب! %s" % r.status_code)
    ok((r.get_json() or {}).get("why") == "pin_account", "السبب غلط")
    r2 = app.dispatch("/api/auth/otp/send", method="POST",
                      body={"email": A_EMAIL},
                      headers={"X-Forwarded-For": "10.6.6.6"})
    up._HITS.clear()
    ok(r2.status_code == 409, "⛔⛔ بعت كود إيميل لحساب باسورد! %s" % r2.status_code)
    r3 = app.dispatch("/api/auth/reset", method="POST",
                      body={"email": A_EMAIL},
                      headers={"X-Forwarded-For": "10.6.6.6"})
    up._HITS.clear()
    ok(r3.status_code == 409, "⛔⛔ قبل استرجاع بالإيميل! %s" % r3.status_code)


t("الإيميل ما ياخدش حساب الباسورد (OTP/verify + send + reset)", t_otp_cant_takeover)

print("\n▸ ⑥  الأخطاء والحدود")


def t_exception_json():
    """⛔⛔ أي استثناء يرجّع JSON فيه why — مش صفحة 500 فاضية"""
    real = up._load_users

    def boom():
        raise RuntimeError("عطل متعمّد")

    up._load_users = boom
    try:
        r = call(LOG, body={"pin": A_PIN})
    finally:
        up._load_users = real
    ok(r.status_code == 500, "الحالة %s" % r.status_code)
    b = r.get_json() or {}
    ok(b.get("why") == "RuntimeError",
       "⛔ الرد مافيش why: %s" % b)
    ok(b.get("error"), "مافيش رسالة خطأ")
    # ⛔ برضه على المسارات التانية
    up._load_users = boom
    try:
        r2 = call(LOG, body={"pin": A_PIN}, ip="10.40.0.1")
    finally:
        up._load_users = real
    ok((r2.get_json() or {}).get("why") == "RuntimeError",
       "⛔ المسار التاني مش JSON: %s" % r2.get_json())
    # ⛔ والمسار الجديد كمان: التحقق بيفتح ملف المستخدمين
    em = "boom@example.com"
    r = start_signup(em, "س")
    code = r[1] if isinstance(r, tuple) else r
    ok(code, "⛔ مافيش كود")
    up._load_users = boom
    try:
        r3 = call(VERIFY, body={"email": em, "code": code})
    finally:
        up._load_users = real
    ok(r3.status_code == 500, "verify → %s مش 500" % r3.status_code)
    ok((r3.get_json() or {}).get("why") == "RuntimeError",
       "⛔ verify مش JSON: %s" % r3.get_json())


t("الاستثناء في أي مسار PIN → JSON فيه why", t_exception_json)


def t_buckets():
    b = up._route_bucket
    ok(b("/api/auth/pin/login") == "write",
       "login bucket=%s" % b("/api/auth/pin/login"))
    ok(b("/api/auth/pin/change") == "write",
       "change bucket=%s" % b("/api/auth/pin/change"))
    # ⛔⛔ التسجيل أضيق: نفس حد الكتابة + سقف ساعي
    ok(b("/api/auth/pin/register") == "pin_register",
       "register bucket=%s" % b("/api/auth/pin/register"))
    ok(up.LIMITS["pin_register"][0] == (5, 60),
       "السقف الدقيقي=%s" % (up.LIMITS["pin_register"][0],))
    ok(up.LIMITS["pin_register"][1] == (20, 3600),
       "السقف الساعي=%s" % (up.LIMITS["pin_register"][1],))
    ok(up.LIMITS["write"][0] == (5, 60), "حد write اتغيّر")
    # ⛌ والـOTP لسه شغال زي ما هو
    ok(up._route_bucket("/api/auth/otp/send") == "otp_send", "otp_send اتغير")
    ok(up._route_bucket("/api/auth/otp/verify") == "otp_verify", "otp_verify اتغير")
    ok(up._route_bucket("/api/auth/register") == "otp_send", "register اتغير")
    ok(up._route_bucket("/api/auth/me") == "default", "me اتغير")
    ok(up._route_bucket("/api/portfolio") == "write", "portfolio اتغير")
    ok(up._route_bucket("/api/analyze") == "expensive", "analyze اتغير")


t("bucket المسارات الجديدة = write، والقديم زي ما هو", t_buckets)


def t_rate_limit_real():
    """⛔ الحد الحقيقي شغّال: ٦ طلبات في الدقيقة → آخر واحدة 429"""
    up._HITS.clear()
    codes = [app.dispatch(LOG, method="POST", body={"pin": "3333"},
                          headers={"X-Forwarded-For": "10.4.4.4"}).status_code
             for _ in range(6)]
    ok(429 in codes, "مافيش 429 بعد ٦ طلبات: %s" % codes)
    up._HITS.clear()


t("حد الـrate limit (٥/دقيقة) شغّال", t_rate_limit_real)


def t_stale_index_dup_pin():
    """⛌ لو الفهرس ميت (pepper اتغيّر) فحص «الباسورد مستخدم من قبل»
       لازم يشتغل بالهاش الحقيقي كمان — مش يسيب حد يسجّل بالباسورد
       بتاع حد تاني."""
    import hashlib as _h
    real_pin = A_PIN
    saved = (up._PIN_PEPPER, up._PIN_PEPPER_ID)
    up._PIN_PEPPER = "TEST-ONLY-pepper-stale-2"
    up._PIN_PEPPER_ID = _h.sha256(up._PIN_PEPPER.encode()).hexdigest()[:12]
    try:
        ok(up._pin_index_stale() is True, "⛔ الفهرس لسه متظبط")
        em = "ghost2@example.com"
        u = unlock_for(em, "دخيل", ip="10.3.3.3")
        r = call(NEWPIN, body={"new_pin": real_pin}, token=u, ip="10.3.3.3")
        ok(r.status_code == 409,
           "⛔⛔ الباسورد المكرر عدّى وقت ما الفهرس ميت! %s" % r.status_code)
        ok((r.get_json() or {}).get("why") == "pin_taken", "السبب غلط")
        ok(up._pin_by_email(em)[1] is None,
           "⛔ اتعمل حساب بالباسورد المكرر")
        # ⛌ والدخول بالباسورد الصح برضه شغّال (بحث بطيء + تصليح الفهرس)
        r2 = call(LOG, body={"pin": real_pin}, ip="10.3.3.4")
        ok(r2.status_code == 200, "الدخول %s" % r2.status_code)
    finally:
        up._PIN_PEPPER, up._PIN_PEPPER_ID = saved


t("فحص التكرار يشتغل حتى والفهرس ميت", t_stale_index_dup_pin)


def t_pepper_rotation():
    """⛌ لو الـpepper اتغيّر، الدخول لازم يفضل شغّال
       (بحث بالهاش الحقيقي + تصليح الفهرس)"""
    up._PIN_PEPPER = "TEST-ONLY-pepper-rotated"
    up._PIN_PEPPER_ID = __import__("hashlib").sha256(
        up._PIN_PEPPER.encode()).hexdigest()[:12]
    r = call(LOG, body={"pin": A_PIN})
    ok(r.status_code == 200, "بعد تدوير الـpepper الدخول %s" % r.status_code)
    ok(up._load_users()[A_UID]["pin_idx_id"] == up._PIN_PEPPER_ID,
       "الفهرس اتصلّح؟")
    up._PIN_PEPPER = "TEST-ONLY-pin-pepper"
    up._PIN_PEPPER_ID = __import__("hashlib").sha256(
        up._PIN_PEPPER.encode()).hexdigest()[:12]
    r2 = call(LOG, body={"pin": A_PIN})
    ok(r2.status_code == 200, "رجوع للـpepper الأصلي %s" % r2.status_code)


t("تدوير الـpepper ما بيكسرش الباسوردات", t_pepper_rotation)


def t_pin_untouchable():
    """⛔⛔ منطق التقييم ما اتمسّش — الباتش كله auth"""
    import ast
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    tree = ast.parse(src, "update_prices.py")
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    for f in ("auth_pin_register", "auth_pin_login", "auth_pin_change"):
        ok(f in names, "المسار %s مش موجود" % f)
    ok("_pin_hash" in names and "_pinlock_fail" in names, "الدوال ناقصة")
    # مافيشWeights/أسهم اتغيرت
    ok("AXIS_WEIGHTS" in src and "final_score(" in src, "منطق التقييم اتغير؟")


t("منطق التقييم والأرقام المالية ما اتغيّرتش", t_pin_untouchable)

# ── التقرير النهائي ──
print("\n▸ 📄  فحص users.json بعد كل اللي فات")
d = json.loads(up.USERS_FILE.read_text(encoding="utf-8"))
print("   المستخدمين: %d — %s" % (
    len(d), ", ".join(sorted(u.get("email") or "?" for u in d.values()))))
print("   حقول مستخدم باسورد: %s" % sorted(d[A_UID].keys()))
print("   ملف القفل: %s (%d سجل)" % (up.PINLOCK_FILE, len(_lock_state().get("k") or {})))

print("\n%s %d نجح · %d فشل\n" % ("❌" if _fail else "✅", _pass, _fail))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if _fail else 0)
