#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ الجولة ١٨ — P2-A — فحص أمني + إصلاح «fail-open» (٧ بنود)

البنود (من سجل التدقيق A–Z):
  · SEC-011 — خدمات الأنماط/الباقات ترجع plan الخام عند تعذّر plan_checker
  · SEC-012 — تفعيل الاشتراك بيغيّر الخطة قبل ما يسجّل العملية
  · SEC-002 — المسارات الإدارية/التشخيصية لازم إدارية صريحة (fail-closed)
  · SEC-032 — نافذة CSRF (كوكي/Bearer)
  · SEC-004 — تخزين أكواد استرجاع PIN الخام على القرص
  · SEC-010 — مسار الأدمن mint_session (مدة الكوكي ٦٠٠ ثانية)
  · SEC-019 — /api/chat و /api/analyze (صلاحيات + سقف تكلفة)

⛔ العزل — كل حاجة في مجلد مؤقت:
  · ⛔ مافيش بيانات مستخدمين حقيقية
  · ⛔ مافيش أسرار إنتاج (أسرار اختبار محلية فقط)
  · ⛔ مافيش أي طلب على الشبكة (الاستدعاءات الخارجية متعملة بـmock)
  · ⛔ مافيش أي تكلفة

شغّله:
    /workspace/.venv-sec/bin/python test_round18_sec_failopen.py
أو مع pytest:
    /workspace/.venv-sec/bin/python -m pytest -q test_round18_sec_failopen.py
"""
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_r18_p2a_")
sys.path.insert(0, HERE)

# ══════════════════════════════════════════════════════════════════
#  ⛔⛔⛔ العزل — قبل استيراد الباك ⬇️ ⬇️
# ══════════════════════════════════════════════════════════════════
os.environ["OCTA_DATA_DIR"] = TMP                 # ⛔ كل الملفات في tmp
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r18-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r18-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_BG_TASKS"] = "off"                # ⛔ مافيش مهام خلفية ⇒ مافيش شبكة
os.environ["OCTA_RATE_MULT"] = "100"               # ⛔ اختبار بس: حدود الطلبات أوسع
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_API_DENY_DEFAULT"] = "off"
os.environ.pop("OCTA_ADMIN_TOKEN", None)           # ⛔ الأدمن: بنتحكم فيه في كل اختبار
os.environ.pop("OCTA_ADMIN_KEY", None)             # ⛔ مافيش مفتاح أدمن تاني
# ⛔⛔⛔ مافيش شبكة ⬇️ ⬇️ (تلجرام/بريد/خدمات خارجية) ⬇️ ⬇️
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_CHAT_ID", None)
os.environ.pop("TELEGRAM_TOKEN", None)
os.environ.pop("RESEND_API_KEY", None)

import update_prices as up  # noqa: E402
import plan_gate  # noqa: E402
from pathlib import Path  # noqa: E402

# ⛔ كل ملفات التخزين على القرص ⇒ جوه المجلد المؤقت ⬇️
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"
up.MAIL_ON = False

ADMIN = "TEST-ONLY-r18-admin-token"
ADMIN_HEADERS = {"X-OCTA-Admin": ADMIN}

client = up.app.test_client()
cookie_client = up.app.test_client()      # ⛔ عميل منفصل للكوكي (CSRF)
os.environ["OCTA_ADMIN_TOKEN"] = ADMIN    # ⛔ مفتاح إدارة اختباري (مش إنتاج)


# ══════════════════════════════════════════════════════════════════
#  🧰 أدوات
# ══════════════════════════════════════════════════════════════════
def bearer(tok):
    return {"Authorization": "Bearer %s" % tok}


def mk_user(uid, email, plan=None, plan_until=0, name="مستخدم اختبار"):
    """ينشئ مستخدم في users.json المعزول."""
    salt = up._pin_salt_new()
    rec = {
        "id": uid, "name": name, "email": email,
        "pin_hash": up._pin_hash("1234", salt), "pin_salt": salt,
        "pin_idx": up._pin_index("1234"), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": int(time.time()),
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
    }
    if plan:
        rec["plan"] = plan
        rec["plan_until"] = int(plan_until or 0)
    with up.USERS_LOCK:
        users = up._load_users()
        users[str(uid)] = rec
        assert up._save_users(users), "فشل إنشاء المستخدم في العزل"
    return uid


def read_user(uid):
    """سجل المستخدم من القرص (الحقيقة بعد العملية)."""
    try:
        with up.USERS_LOCK:
            users = up._load_users()
        return users.get(str(uid)) or {}
    except Exception:
        return {}


def user_token(uid):
    return up._make_token(str(uid))


def plan_of_user(uid):
    return plan_gate.plan_of(read_user(uid))


class FakeResponse(object):
    """رد وهمي من الخدمة الخارجية (مافيش شبكة ولا تكلفة)."""

    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


# ══════════════════════════════════════════════════════════════════
#  ① SEC-011 — الباقة: أي تعذّر ⇒ free (مش plan الخام)
# ══════════════════════════════════════════════════════════════════
def test_sec011_plan_checker_failure_is_free_not_pro():
    """plan_checker بيكسر ⇒ الخدمات لازم ترجّع free (مش pro)."""
    uid = mk_user("r18_u_011", "r18_011@example.test",
                  plan="pro", plan_until=int(time.time()) + 86400)
    tok = user_token(uid)
    original = plan_gate.plan_of

    def broken(*a, **k):
        raise RuntimeError("تعطّر سجل الاشتراكات / plan_checker")

    plan_gate.plan_of = broken
    try:
        # ① دوال التسجيل في الباك (٤ wrappers) ⇒ لازم free
        for name in ("_pattern_plan_checker", "_zones_plan",
                     "_ch_plan", "_studio_plan"):
            fn = getattr(up, name, None)
            assert fn is not None, "الدالة %s مش موجودة" % name
            got = fn({"id": uid, "plan": "pro", "plan_until": 0})
            assert got == "free", \
                "%s رجّع %r بدل 'free' وقت التعطّر (fail-open)" % (name, got)

        # ② المسارات نفسها ⇒ مقفولة (403) والباقة free
        for path in ("/api/studio/list", "/api/zones", "/api/challenges/today"):
            r = client.get(path, headers=bearer(tok))
            body = r.get_json() or {}
            assert r.status_code == 403, \
                "%s رجّع %s بدل 403 (الباقة اتفتحت وقت التعطّر)" % (path, r.status_code)
            assert body.get("plan") == "free", \
                "%s رجّع plan=%r بدل 'free'" % (path, body.get("plan"))
    finally:
        plan_gate.plan_of = original


def test_sec011_pattern_module_fallback_is_free():
    """وحدات الأنماط نفسها (pattern_*) ⇒ لا ترجع plan الخام عند التعطّر."""
    from flask import Flask
    import pattern_studio
    import pattern_zones

    user = {"id": "r18_pattern_user", "plan": "pro", "plan_until": 0}

    def broken(u):
        raise RuntimeError("plan_checker واقع")

    for mod, path in ((pattern_studio, "/api/studio/list"),
                      (pattern_zones, "/api/zones")):
        app = Flask("r18_pattern_probe")
        mod.register(app, require_user=lambda: user, plan_checker=broken)
        c = app.test_client()
        r = c.get(path)
        body = r.get_json() or {}
        assert r.status_code == 403, \
            "%s: %s رجّع %s بدل 403 (fail-open)" % (mod.__name__, path, r.status_code)
        assert body.get("plan") == "free", \
            "%s: %s رجّع plan=%r بدل 'free'" % (mod.__name__, path, body.get("plan"))


def test_sec011_expired_pro_is_free():
    """Pro منتهي ⇒ free (قاعدة plan_gate الأصلية — لازم تفضل شغالة)."""
    uid = mk_user("r18_u_011_exp", "r18_011_exp@example.test",
                  plan="pro", plan_until=int(time.time()) - 60)
    tok = user_token(uid)
    assert plan_of_user(uid) == "free", "Pro منتهي اتحسب pro"
    assert up._pattern_plan_checker(read_user(uid)) == "free", \
        "plan_checker رجّع pro لمستخدم منتهي"
    r = client.get("/api/studio/list", headers=bearer(tok))
    assert r.status_code == 403, \
        "المستخدم المنتهي وصل لمسار Pro (status=%s)" % r.status_code


# ══════════════════════════════════════════════════════════════════
#  ② SEC-012 — تفعيل الاشتراك: ترتيب ذرّي + تراجع
# ══════════════════════════════════════════════════════════════════
def test_sec012_log_failure_leaves_state_unchanged():
    """فشل تسجيل العملية ⇒ الباقي زي ما كان (مافيش pro)."""
    uid = mk_user("r18_u_012", "r18_012@example.test")
    before = read_user(uid)
    original = plan_gate._write_log

    def unwritable(items):
        # ⛔ السجل مش قابل للكتابة (فشل تخزين)
        return False

    plan_gate._write_log = unwritable
    try:
        ok_, msg, rec = up._subs_activate("r18_012@example.test", "pro",
                                          30, 350, "admin", "r18")
    finally:
        plan_gate._write_log = original

    assert not ok_, "التفعيل رجّع نجاح رغم فشل السجل"
    after = read_user(uid)
    assert after.get("plan") != "pro", \
        "⛔ اتكتب plan=pro من غير سجل (حالة غير متسقة): %r" % after.get("plan")
    assert int(after.get("plan_until") or 0) == int(before.get("plan_until") or 0), \
        "plan_until اتغيّر رغم فشل التسجيل"


def test_sec012_user_patch_failure_rolls_back_log():
    """فشل تعديل الحساب ⇒ السجل يتراجع (مافيش عملية بلا باقة)."""
    uid = mk_user("r18_u_012b", "r18_012b@example.test")
    n_before = len(plan_gate.subscription_log(2000))
    original = up._patch_user

    def failing_patch(uid_, **fields):
        return None      # ⛔ فشل الحفظ على القرص

    up._patch_user = failing_patch
    try:
        ok_, msg, rec = up._subs_activate("r18_012b@example.test", "pro",
                                          30, 350, "admin", "r18")
    finally:
        up._patch_user = original

    assert not ok_, "التفعيل رجّع نجاح رغم فشل تحديث الحساب"
    items = plan_gate.subscription_log(2000)
    assert len(items) == n_before, \
        "⛔ السجل فيه عملية بلا باقة (مافيش تراجع): %d ⇒ %d" % (n_before, len(items))
    after = read_user(uid)
    assert after.get("plan") != "pro", "⛔ اتكتب plan=pro رغم فشل التحديث"


def test_sec012_activate_route_log_failure_is_consistent():
    """نفس البند على مستوى المسار (HTTP): فشل السجل ⇒ مافيش pro."""
    uid = mk_user("r18_u_012c", "r18_012c@example.test")
    original = plan_gate._write_log
    plan_gate._write_log = lambda items: False
    try:
        r = client.post("/api/subscriptions/activate",
                        json={"email": "r18_012c@example.test", "plan": "pro",
                              "days": 30, "price": 350, "method": "admin"},
                        headers=ADMIN_HEADERS)
    finally:
        plan_gate._write_log = original
    body = r.get_json() or {}
    assert r.status_code != 200 or not body.get("ok"), \
        "المسار رجّع نجاح رغم فشل السجل"
    after = read_user(uid)
    assert after.get("plan") != "pro", \
        "⛔ المسار wrote plan=pro من غير سجل: %r" % after.get("plan")


# ══════════════════════════════════════════════════════════════════
#  ③ SEC-002 — المسارات الإدارية: إدارة صريحة (fail-closed)
# ══════════════════════════════════════════════════════════════════
ADMIN_ROUTES = [
    ("GET", "/api/diagnostic", None),
    ("GET", "/api/audit/redundancy", None),
    ("GET", "/api/ai-status", None),
    ("GET", "/api/admin/users", None),
    ("GET", "/api/admin/logins", None),
    ("GET", "/api/admin/monthly", None),
    ("POST", "/api/admin/telegram_test", {}),
    ("POST", "/api/admin/reset_chal", {}),
    ("POST", "/api/admin/mint_session", {}),
    ("POST", "/api/admin/set_device", {}),
    ("POST", "/api/admin/trust_device", {}),
    ("GET", "/api/subscriptions/log", None),
    ("POST", "/api/subscriptions/activate", {}),
]


def test_sec002_admin_routes_fail_closed_without_key():
    """بدون مفتاح إدارة ⇒ مافيش 200 على أي مسار إداري."""
    os.environ.pop("OCTA_ADMIN_TOKEN", None)
    try:
        for method, path, body in ADMIN_ROUTES:
            r = client.open(path, method=method, json=body)
            assert r.status_code != 200, \
                "%s %s رجّع 200 بدون مفتاح إدارة" % (method, path)
            assert r.status_code in (401, 403, 503), \
                "%s %s رجّع %s (المتوقع 401/403/503)" % (method, path, r.status_code)
    finally:
        os.environ["OCTA_ADMIN_TOKEN"] = ADMIN


def test_sec002_admin_routes_reject_wrong_key():
    """مفتاح إدارة غلط ⇒ مرفوض (401/403)."""
    os.environ["OCTA_ADMIN_TOKEN"] = ADMIN
    for method, path, body in ADMIN_ROUTES:
        r = client.open(path, method=method, json=body,
                        headers={"X-OCTA-Admin": "wrong-key"})
        assert r.status_code in (401, 403), \
            "%s %s رجّع %s بمفتاح غلط" % (method, path, r.status_code)


def test_sec002_admin_routes_accept_right_key():
    """مفتاح إدارة صح ⇒ المرور (مش 401/403)."""
    os.environ["OCTA_ADMIN_TOKEN"] = ADMIN
    uid = mk_user("r18_u_002", "r18_002@example.test")
    tok = user_token(uid)
    for method, path, body in ADMIN_ROUTES:
        headers = dict(ADMIN_HEADERS)
        headers.update(bearer(tok))
        r = client.open(path, method=method, json=body, headers=headers)
        assert r.status_code not in (401, 403), \
            "%s %s رجّع %s بمفتاح صحيح" % (method, path, r.status_code)
    # ⛔ المسارات اللي ليها قراءة ⇒ 200 فعلي
    for path in ("/api/diagnostic", "/api/ai-status", "/api/audit/redundancy",
                 "/api/admin/users", "/api/admin/logins", "/api/admin/monthly",
                 "/api/subscriptions/log"):
        headers = dict(ADMIN_HEADERS)
        headers.update(bearer(tok))
        r = client.get(path, headers=headers)
        assert r.status_code == 200, \
            "%s رجّع %s بمفتاح صحيح (المتوقع 200)" % (path, r.status_code)


# ══════════════════════════════════════════════════════════════════
#  ④ SEC-032 — نافذة CSRF (كوكي/Bearer)
# ══════════════════════════════════════════════════════════════════
def test_sec032_cookie_only_write_is_rejected():
    """الكتابة (POST/PUT/PATCH/DELETE) لازم Bearer — الكوكي لوحده مرفوض."""
    uid = mk_user("r18_u_032", "r18_032@example.test")
    tok = user_token(uid)
    cookie_client.set_cookie("octa_token", tok)
    payload = {"action": "add", "code": "COMI", "shares": 1,
               "cost": 10, "price": 10}

    # ① POST بكوكي بس ⇒ 401
    r = cookie_client.post("/api/portfolio", json=payload)
    assert r.status_code == 401, \
        "POST بكوكي بس رجّع %s (CSRF مفتوح)" % r.status_code

    # ② DELETE بكوكي بس ⇒ 401
    r = cookie_client.delete("/api/charts/r18-chart-1")
    assert r.status_code == 401, \
        "DELETE بكوكي بس رجّع %s (CSRF مفتوح)" % r.status_code

    # ③ POST بـBearer ⇒ 200 (مافيش كسر)
    r = client.post("/api/portfolio", json=payload, headers=bearer(tok))
    assert r.status_code == 200, \
        "POST بـBearer رجّع %s (المتوقع 200)" % r.status_code

    # ④ ⛔ PUT/PATCH على مسار كتابة ⇒ مافيش 2xx بالكوكي بس
    for method in ("PUT", "PATCH"):
        r = cookie_client.open("/api/portfolio", method=method, json=payload)
        assert not (200 <= r.status_code < 300), \
            "%s بكوكي بس رجّع %s (CSRF مفتوح)" % (method, r.status_code)


def test_sec032_unsigned_token_is_rejected():
    """توكن من غير توقيع صحيح ⇒ مرفوض."""
    uid = mk_user("r18_u_032b", "r18_032b@example.test")
    tok = user_token(uid)
    head, _, sig = tok.partition(".")
    bad_sig = ("bb" if sig[-2:] != "bb" else "cc")
    forged = "%s.%s" % (head, bad_sig)
    r = client.get("/api/auth/me", headers=bearer(forged))
    assert r.status_code == 401, \
        "توكن بتوقيع غلط رجّع %s (المتوقع 401)" % r.status_code
    # ⛔ والقراءة بالكوكي مسموحة (الكوكي للقراءة بس)
    cookie_client.set_cookie("octa_token", tok)
    r = cookie_client.get("/api/auth/me")
    assert r.status_code == 200, \
        "GET بكوكي رجّع %s (المتوقع 200 — الكوكي للقراءة)" % r.status_code
    cookie_client.delete_cookie("octa_token")


# ══════════════════════════════════════════════════════════════════
#  ⑤ SEC-004 — مافيش كود استرجاع خام على القرص
# ══════════════════════════════════════════════════════════════════
def test_sec004_no_raw_recovery_code_on_disk():
    """كود فتح الحساب وكود الـOTP ⇒ هاش بس على القرص."""
    email = "r18_004@example.test"
    code = up._chal_send(email)
    assert code and len(code) == 6, "كود الفتح ميتولّدش"
    raw = up.PIN_CHAL_FILE.read_text(encoding="utf-8")
    assert code not in raw, "⛔ الكود الخام مكتوب على القرص (pinchal.json)"
    assert "code_plain" not in raw, "⛔ الحقل code_plain موجود على القرص"
    ok_, why = up._chal_check(email, code)
    assert ok_, "الكود الصح مرفوض (الهاش غلط) — %s" % why

    email2 = "r18_004b@example.test"
    otp = up._otp_new(email2)
    assert otp and len(otp) == 6, "كود الـOTP ميتولّدش"
    raw2 = up.OTP_FILE.read_text(encoding="utf-8")
    assert otp not in raw2, "⛔ كود الـOTP الخام على القرص"
    assert "code_hash" in raw2, "مافيش هاش للـOTP على القرص"


def test_sec004_user_pin_is_hashed_only():
    """الباسورد (PIN) نفسه ⇒ هاش + ملح، مش خام."""
    uid = mk_user("r18_u_004", "r18_004c@example.test")
    rec = read_user(uid)
    blob = json.dumps(rec, ensure_ascii=False)
    assert "1234" not in blob, "⛔ الباسورد الخام مكتوب في سجل المستخدم"
    assert rec.get("pin_hash"), "مافيش هاش للباسورد"
    assert "pin" not in rec or not str(rec.get("pin") or "").strip(), \
        "⛔ الحقل pin فيه الباسورد الخام"


# ══════════════════════════════════════════════════════════════════
#  ⑥ SEC-010 — mint_session: عمر الكوكي ٦٠٠ ثانية
# ══════════════════════════════════════════════════════════════════
def test_sec010_mint_session_cookie_max_age_is_600():
    """كوكي mint_session ⇒ ٦٠٠ ثانية (مش ٣٠ يوم)."""
    os.environ["OCTA_ADMIN_TOKEN"] = ADMIN
    mk_user("r18_u_010", "r18_010@example.test")
    r = client.post("/api/admin/mint_session",
                    json={"email": "r18_010@example.test"},
                    headers=ADMIN_HEADERS)
    assert r.status_code == 200, "mint_session رجّع %s" % r.status_code
    body = r.get_json() or {}
    assert int(body.get("ttl") or 0) == 600, \
        "ttl رجّع %r بدل 600" % body.get("ttl")
    sc = r.headers.get("Set-Cookie", "")
    assert "octa_token=" in sc, "مافيش كوكي في الرد"
    assert "Max-Age=600" in sc, "⛔ عمر الكوكي مش 600: %s" % sc
    assert "Max-Age=2592000" not in sc, "⛔ الكوكي ٣٠ يوم"


# ══════════════════════════════════════════════════════════════════
#  ⑦ SEC-019 — /api/chat و /api/analyze: صلاحيات + سقف تكلفة
# ══════════════════════════════════════════════════════════════════
def test_sec019_chat_requires_login():
    """⛔ /api/chat لازم جلسة — زائر مجهول ⇒ 401."""
    r = client.post("/api/chat", json={"message": "مرحبا"})
    assert r.status_code == 401, \
        "/api/chat رجّع %s لزائر مجهول (المتوقع 401)" % r.status_code


def test_sec019_analyze_requires_login():
    """⛔ /api/analyze لازم جلسة — زائر مجهول ⇒ 401."""
    r = client.post("/api/analyze", json={"code": "COMI"})
    assert r.status_code == 401, \
        "/api/analyze رجّع %s لزائر مجهول (المتوقع 401)" % r.status_code


def test_sec019_ai_cost_ceiling_is_enforced():
    """⛔ سقف تكلفة واضح (متغيّر بيئة) — بعد الحد ⇒ 429 من غير نداء خارجي."""
    os.environ["OCTA_AI_MAX_CALLS_PER_HOUR"] = "2"
    uid = mk_user("r18_u_019", "r18_019@example.test")
    tok = user_token(uid)
    calls = []
    real_post = up.requests.post
    real_key = up.GEMINI_KEY

    def fake_post(url, **kw):
        calls.append(url)
        return FakeResponse({"candidates": [
            {"content": {"parts": [{"text": "رد تجريبي"}]}}]})

    up.requests.post = fake_post
    up.GEMINI_KEY = "TEST-ONLY-r18-key"
    try:
        try:
            up._AI_COST.clear()
        except Exception:
            pass
        codes = []
        for _ in range(3):
            r = client.post("/api/chat", json={"message": "مرحبا"},
                            headers=bearer(tok))
            codes.append(r.status_code)
        assert codes[0] == 200, "الطلب الأول رجّع %s" % codes[0]
        assert codes[1] == 200, "الطلب التاني رجّع %s" % codes[1]
        assert codes[2] == 429, \
            "⛔ الطلب التالت رجّع %s بدل 429 (مافيش سقف تكلفة)" % codes[2]
        assert len(calls) == 2, \
            "⛔ اتعمل %d نداء خارجي والسقف 2" % len(calls)
    finally:
        up.requests.post = real_post
        up.GEMINI_KEY = real_key
        os.environ.pop("OCTA_AI_MAX_CALLS_PER_HOUR", None)


def test_sec019_ai_cost_limit_default_is_fail_closed():
    """⛔ الافتراضي مغلق: من غير ضبط ⇒ سقف محافظ (مش مفتوح)."""
    os.environ.pop("OCTA_AI_MAX_CALLS_PER_HOUR", None)
    limit = up._ai_cost_limit()
    assert isinstance(limit, int) and limit > 0, \
        "السقف الافتراضي مش محافظ: %r" % limit
    os.environ["OCTA_AI_MAX_CALLS_PER_HOUR"] = "0"
    assert up._ai_cost_limit() > 0, "⛔ سقف 0 ⇒ مفتوح (fail-open)"
    os.environ["OCTA_AI_MAX_CALLS_PER_HOUR"] = "abc"
    assert up._ai_cost_limit() > 0, "⛔ قيمة غلط ⇒ مفتوح (fail-open)"
    os.environ.pop("OCTA_AI_MAX_CALLS_PER_HOUR", None)


def test_sec019_chat_length_limits_still_enforced():
    """⛔ حدود الطول في /api/chat لسه شغالة (رجوع=False)."""
    uid = mk_user("r18_u_019b", "r18_019b@example.test")
    tok = user_token(uid)
    r = client.post("/api/chat", json={"message": "س" * 5000},
                    headers=bearer(tok))
    assert r.status_code == 400, "رسالة طويلة رجّع %s" % r.status_code
    r = client.post("/api/chat", json={"message": "hi",
                                        "history": [{"role": "user",
                                                     "content": "x"}] * 100},
                    headers=bearer(tok))
    assert r.status_code == 400, "تاريخ طويل رجّع %s" % r.status_code


# ══════════════════════════════════════════════════════════════════
#  🏃 المُشغّل (script) — نفس الملف يعمل مع pytest كمان
# ══════════════════════════════════════════════════════════════════
TESTS = [
    ("SEC-011", "test_sec011_plan_checker_failure_is_free_not_pro"),
    ("SEC-011", "test_sec011_pattern_module_fallback_is_free"),
    ("SEC-011", "test_sec011_expired_pro_is_free"),
    ("SEC-012", "test_sec012_log_failure_leaves_state_unchanged"),
    ("SEC-012", "test_sec012_user_patch_failure_rolls_back_log"),
    ("SEC-012", "test_sec012_activate_route_log_failure_is_consistent"),
    ("SEC-002", "test_sec002_admin_routes_fail_closed_without_key"),
    ("SEC-002", "test_sec002_admin_routes_reject_wrong_key"),
    ("SEC-002", "test_sec002_admin_routes_accept_right_key"),
    ("SEC-032", "test_sec032_cookie_only_write_is_rejected"),
    ("SEC-032", "test_sec032_unsigned_token_is_rejected"),
    ("SEC-004", "test_sec004_no_raw_recovery_code_on_disk"),
    ("SEC-004", "test_sec004_user_pin_is_hashed_only"),
    ("SEC-010", "test_sec010_mint_session_cookie_max_age_is_600"),
    ("SEC-019", "test_sec019_chat_requires_login"),
    ("SEC-019", "test_sec019_analyze_requires_login"),
    ("SEC-019", "test_sec019_ai_cost_ceiling_is_enforced"),
    ("SEC-019", "test_sec019_ai_cost_limit_default_is_fail_closed"),
    ("SEC-019", "test_sec019_chat_length_limits_still_enforced"),
]


def main():
    passed = 0
    failed = 0
    rows = []
    for item, name in TESTS:
        fn = globals().get(name)
        try:
            fn()
            passed += 1
            rows.append((item, name, "PASS", ""))
            print("  ✅ %-8s %s" % (item, name))
        except Exception as e:
            failed += 1
            msg = ("%s: %s" % (type(e).__name__, e))[:300]
            rows.append((item, name, "FAIL", msg))
            print("  ❌ %-8s %s\n      ⇒ %s" % (item, name, msg))
    print("\n" + "=" * 66)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)"
          % (passed, failed, passed + failed))
    print("=" * 66)
    try:
        shutil.rmtree(TMP, ignore_errors=True)
    except Exception:
        pass
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
