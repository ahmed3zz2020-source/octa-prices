#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٠ — اختبارات AZ34 / AZ35-DELETE / AZ36 / AZ32 (باك)

⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع ولا في /app.
⛔ مافيش أي معاملة مالية حقيقية — التفعيل **محاكاة** كاملة.
⛔ مافيش أي طلب على الإنتاج.

التغطية:
   AZ34-01 · /api/health ما يكشفش أي بيانات داخلية
   AZ34-02 · /api/health لسه متوافق (market_phase موجود)
   AZ34-03 · /api/ready بيفرّق بين جاهز ومش جاهز
   AZ34-04 · /api/diagnostics محمي (401 من غير توكن أدمن)
   AZ35-01 · مفيش بريد ولا اسم في سجل القفل بعد الحذف
   AZ35-02 · الرد **مش** بيقول «اتمسح بالكامل» (ادعاء كاذب)
   AZ36-01 · تفعيل بنفس مفتاح التفرّد ⇒ من غير تمديد تاني
   AZ36-02 · فشل التخزين ⇒ 503 مش 404 + مافيش نجاح وهمي
   AZ36-03 · تفعيل من غير توكن أدمن ⇒ 401
   AZ32-01 · مفاتيح الـrate limit بتنضف بالعمر (TTL)
   AZ32-02 · سقف الذاكرة للـrate limit محفوظ

شغّله:  python3 test_r20_az31_36.py
"""
import os
import sys
import json
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="r20az_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔ مافيش سر حقيقي — قيم اختبار محلية بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"

import update_prices as up  # noqa: E402

from pathlib import Path  # noqa: E402

# ── كل التخزين يروح على /tmp ──
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.MAIL_ON = True

MAILS = []


def _grab_mail(to, subject, html):
    MAILS.append({"to": to, "subject": subject, "html": html})
    return True


up._send_mail = _grab_mail

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


def call(path, method="GET", body=None, ip="10.9.0.1", token=None,
         admin=False, clear=True):
    # ⛔ بيكمل على حالة الـrate limit إلا لو اتقفل التنضيف ⭐
    #    (اختبار AZ32-03 محتاج العدّاد accumulates ⭐)
    if clear:
        up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    if token:
        h["Authorization"] = "Bearer " + token
    if admin:
        h["X-OCTA-Admin"] = "TEST-ONLY-admin-token"
    return up.app.dispatch(path, method=method, body=body, headers=h)


def jb(r):
    try:
        return r.get_json() or {}
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════
#  AZ34 — liveness / readiness / diagnostics
# ══════════════════════════════════════════════════════════════════
section("AZ34 — فصل liveness عن readiness")

r = call("/api/health")
h = jb(r)
FORBIDDEN = ["users_n", "pin_users", "snapshot_id", "data_full_n",
             "data_full_loaded", "mail_configured", "mail_last_ok",
             "mail_last_why", "gemini", "token_secret_configured",
             "app_writable", "users_io", "lastUpdate", "tickers", "stocks"]
leaked = [k for k in FORBIDDEN if k in h]
ok(r.status_code == 200, "AZ34-01a · /api/health بيرد 200")
ok(not leaked, "AZ34-01b · /api/health ما بيكشفش أي حقل داخلي",
   "تسريب: %s" % leaked)
ok("status" in h and "service" in h,
   "AZ34-01c · /api/health لسه فيه الحقول الأساسية")
ok(h.get("market_phase") in ("open", "closed", "pre", "after", "unknown",
                             "holiday") or isinstance(h.get("market_phase"),
                                                    str),
   "AZ34-02 · market_phase موجود (توافق مع الواجهة)",
   h.get("market_phase"))

r = call("/api/ready")
rd = jb(r)
ok(r.status_code in (200, 503), "AZ34-03a · /api/ready بيرد 200 أو 503",
   r.status_code)
ok("ready" in rd, "AZ34-03b · /api/ready فيه حقل ready")
ok(isinstance(rd.get("checks"), dict) and "data" in rd.get("checks", {}),
   "AZ34-03c · /api/ready فيه الشيكات")
ok(r.status_code == (200 if rd.get("ready") else 503),
   "AZ34-03d · الكود يطابق حالة الجاهزية", r.status_code)

r = call("/api/diagnostics")
ok(r.status_code in (401, 503),
   "AZ34-04a · /api/diagnostics محمي من غير توكن أدمن", r.status_code)
r = call("/api/diagnostics", admin=True)
ok(r.status_code == 200, "AZ34-04b · /api/diagnostics بيفتح بتوكن الأدمن",
   r.status_code)
d = jb(r)
ok("users_n" in d and "snapshot_id" in d,
   "AZ34-04c · التشخيص الكامل موجود في /api/diagnostics بس")


# ══════════════════════════════════════════════════════════════════
#  AZ35-DELETE-CLAIM — ادعاء الحذف
# ══════════════════════════════════════════════════════════════════
section("AZ35-DELETE-CLAIM — honesty عند حذف الحساب")

EMAIL = "az35delete@example.test"
UID = up._hash_key(EMAIL)[:20]
_SALT = "testsalt-az35"
up._save_users({UID: {
    "id": UID, "email": EMAIL, "name": "اسم تجريبي",
    "pin_salt": _SALT,
    "pin_hash": up._pin_hash("1234", _SALT),
    "pin_set": True, "pin_idx": 0,
    "email_hash": up._hash_key(EMAIL),
    "token_epoch": 1, "watch": [{"s": "COMI"}], "portfolio": [{"s": "COMI"}],
}})

tok = up._make_token(UID)

r = call("/api/auth/delete", method="POST",
         body={"confirm": "DELETE", "pin": "1234"}, token=tok)
ok(r.status_code in (200, 400, 401), "AZ35-00 · مسار الحذف بيرد",
   r.status_code)

if r.status_code == 200:
    b = jb(r)
    msg = str(b.get("msg") or "")
    ok("اتمسح الحساب بالكامل" not in msg,
       "AZ35-02a · الرد مش بيقول «اتمسح الحساب بالكامل»", msg)
    ok(b.get("retention", {}).get("personal_data_removed") is True,
       "AZ35-02b · الرد بيقول إن البيانات الشخصية اتشالت")
    kept = b.get("retention", {}).get("kept") or []
    ok("deleted_email" not in kept and "email" not in kept,
       "AZ35-02c · الرد مش بيقول إنه بيسيب الإيميل", kept)
    rec = up._load_users().get(UID) or {}
    ok("deleted_email" not in rec,
       "AZ35-01a · مفيش بريد عادي في سجل القفل", list(rec.keys()))
    ok("email" not in rec,
       "AZ35-01b · مفيش حقل email في سجل القفل", list(rec.keys()))
    ok("name" not in rec,
       "AZ35-01c · مفيش اسم في سجل القفل", list(rec.keys()))
    ok(rec.get("email_hash") and rec.get("deleted_at"),
       "AZ35-01d · سجل القفل فيه الهاش + وقت القفل")
    ok(not rec.get("watch") and not rec.get("portfolio"),
       "AZ35-01e · المحفظة والمتابعات اتمسحت")
else:
    ok(False, "AZ35-02a · الرد مش بيقول «اتمسح الحساب بالكامل»",
       "الحذف رجع %s — الاختبار مش قدر يوصل" % r.status_code)

# ⛔ الإيميل المرسل لازم ما يبقاش فيه ادعاء «اتمسح بالكامل»
bad_mail = [m for m in MAILS if "اتمسح" in str(m.get("html") or "")
            and "بالكامل" in str(m.get("html") or "")]
ok(not bad_mail, "AZ35-03 · إيميل التأكيد مش بيقول «اتمسح بالكامل»")


# ══════════════════════════════════════════════════════════════════
#  AZ36 — الاشتراكات (محاكاة كاملة)
# ══════════════════════════════════════════════════════════════════
section("AZ36 — ذرّية التفعيل ومنع التكرار")

SUB_UID = "az36user"
up._save_users({SUB_UID: {
    "id": SUB_UID, "email": "az36@example.test", "name": "sub",
    "pin_hash": "", "pin_salt": "", "pin_set": False, "pin_idx": -1,
    "token_epoch": 1, "plan": "free", "plan_until": 0,
}})

r = call("/api/subscriptions/activate", method="POST",
         body={"email": "az36@example.test", "plan": "pro", "days": 30,
               "price": 100, "method": "sim", "idempotency_key": "K1"},
         admin=True)
ok(r.status_code == 200, "AZ36-00 · أول تفعيل نجح", r.status_code)
b1 = jb(r)
until1 = int((b1.get("subscription") or {}).get("until") or 0)

r2 = call("/api/subscriptions/activate", method="POST",
          body={"email": "az36@example.test", "plan": "pro", "days": 30,
                "price": 100, "method": "sim", "idempotency_key": "K1"},
          admin=True)
b2 = jb(r2)
until2 = int((b2.get("subscription") or {}).get("until") or 0)
ok(r2.status_code == 200, "AZ36-01a · إعادة نفس المفتاح بترد 200 (نفس النتيجة)",
   r2.status_code)
ok(until1 == until2,
   "AZ36-01b · نفس مفتاح التفرّد ⇒ مفيش تمديد تاني",
   "%s != %s" % (until1, until2))
rec_sub = up._load_users().get(SUB_UID) or {}
ok(int(rec_sub.get("plan_until") or 0) == until1,
   "AZ36-01c · تاريخ الانتهاء في الحساب واحد",
   "%s != %s" % (rec_sub.get("plan_until"), until1))

# ⛔ مفتاح مختلف ⇒ تمديد جديد (تجديد شرعي) ⭐
r3 = call("/api/subscriptions/activate", method="POST",
          body={"email": "az36@example.test", "plan": "pro", "days": 30,
                "price": 100, "method": "sim", "idempotency_key": "K2"},
          admin=True)
until3 = int((jb(r3).get("subscription") or {}).get("until") or 0)
ok(until3 > until2, "AZ36-01d · مفتاح مختلف ⇒ تجديد شرعي اتقبل", until3)

# ⛔ من غير توكن أدمن
r4 = call("/api/subscriptions/activate", method="POST",
          body={"email": "az36@example.test", "plan": "pro", "days": 30})
ok(r4.status_code == 401, "AZ36-03 · التفعيل من غير توكن أدمن ⇒ 401",
   r4.status_code)

# ⛔ فشل التخزين ⇒ 503 مش 404 + مافيش نجاح وهمي ⭐
_old_save = up._save_users


def _broken_save(_users):
    return False


up._save_users = _broken_save
try:
    r5 = call("/api/subscriptions/activate", method="POST",
              body={"email": "az36@example.test", "plan": "pro", "days": 30,
                    "price": 100, "method": "sim", "idempotency_key": "K3"},
              admin=True)
finally:
    up._save_users = _old_save
ok(r5.status_code == 503,
   "AZ36-02a · فشل التخزين ⇒ 503 (مش 404)", r5.status_code)
ok(jb(r5).get("ok") is False, "AZ36-02b · مافيش نجاح وهمي")
rec_after = up._load_users().get(SUB_UID) or {}
ok(int(rec_after.get("plan_until") or 0) == until3,
   "AZ36-02c · الحساب ما اتغيّرش بعد فشل الحفظ",
   "%s != %s" % (rec_after.get("plan_until"), until3))


# ══════════════════════════════════════════════════════════════════
#  AZ32 — تراكم مفاتيح الـrate limit
# ══════════════════════════════════════════════════════════════════
section("AZ32 — تراكم مفاتيح الـrate limit")

up._HITS.clear()
before = len(up._HITS)
for i in range(50):
    up._HITS["10.0.0.%d" % i]["default#0"].append(0.0)   # ⛔ قديم جداً
ok(len(up._HITS) == 50, "AZ32-00 · اتحقن 50 مفتاح قديم")

# ⛔ لازم الطلب الحقيقي ينضّف المفاتيح المنتهية ⬇️
call("/api/health")
after = len(up._HITS)
ok(after < 50, "AZ32-01 · المفاتيح المنتهية اتنضفت بالعمر (TTL)", after)

# ⛔ سقف الذاكرة محفوظ ⬇️
ok(isinstance(getattr(up, "RATE_MAX_KEYS", 0), int)
   and up.RATE_MAX_KEYS >= 100,
   "AZ32-02a · سقف المفاتيح موجود ومضبوط", getattr(up, "RATE_MAX_KEYS", None))
ok(isinstance(getattr(up, "RATE_SWEEP_EVERY", 0), int)
   and up.RATE_SWEEP_EVERY >= 5,
   "AZ32-02b · period التنضيف مضبوط", getattr(up, "RATE_SWEEP_EVERY", None))

# ⛔ والحل ما كسرش الحد نفسه ⬇️
up._HITS.clear()
codes = []
for i in range(130):
    rr = call("/api/prices", ip="10.7.0.1", clear=False)
    codes.append(rr.status_code)
ok(429 in codes, "AZ32-03 · حد الـrate limit لسه شغّال بعد التنظيف",
   sorted(set(codes)))


# ── النتيجة ──
print("\n" + "=" * 64)
passed = sum(1 for c, _ in RESULTS if c)
total = len(RESULTS)
print("  النتيجة: %d/%d" % (passed, total))
print("=" * 64)
for c, label in RESULTS:
    if not c:
        print("  ❌ فشل: " + label)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if passed == total else 1)
