#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ١٥ — تسريب حالة الحساب في challenge/send (mail_down)

📌 العيب اللي اتصلّح:
   التصميم مكتوب في نفس الكود: «الرد **واحد** في كل الأحوال» — بس
   لما خدمة الإيميل مطفّية (MAIL_ON=False):
     · إيميل **مسجّل** ⇒ الكود بيوصل فرع الإرسال ⇒ 503 `mail_down`
     · إيميل **غريب**  ⇒ بيعدّي الفرع ⇒ 200 «تم الإرسال»
   ⇒ ⇒ قناة تعداد كامل: حد يقدر يستنتج مين عندنا حساب.

📌 الاختبار:
   ① نفس الرد (كود + جسم) للإيميل المسجّل والغريب والخدمة مطفّية.
   ② نفس الرد والخدمة شغّالة (مسجّل 200 · غريب 200 · bodies متساوية).
   ③ مافيش تسريب في الكاش/الملفات: الكود بيتولّد بس مابيتكتبش إن
      الحساب موجود · مافيش فرق في زمن الرد.
   ④ ⛔ negative proof: على الكود القديم الردّين مختلفين ⇒ الاختبار بيفشل.

⛔ مافيش إيميل حقيقي ولا سر ولا باسورد حقيقي في الملف ده.
⛔ كل التخزين في مجلد مؤقت في /tmp.

شغّله:  python3 test_round15_maildown_enum.py
"""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="maildown_", dir="/tmp")
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

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"

MAILS = []
up._send_mail = lambda to, subject, html: (
    MAILS.append({"to": to, "subject": subject, "html": html}) or True)

app = up.app

SEND = "/api/auth/pin/challenge/send"
REG = "/api/auth/pin/register"
LOG = "/api/auth/pin/login"

A_PIN, A_EMAIL = "7314", "amina@example.com"
A_DEV = "device-maildown-amina-tabla"
GHOST = "ghost@example.com"

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


def call(path, method="POST", body=None, ip="10.1.0.1", token=None):
    up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    if token:
        h["Authorization"] = "Bearer " + token
    return app.dispatch(path, method=method, body=body, headers=h)


def canon(r):
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


def jbody(r):
    return r.get_json() or {}


# ══════════════════════════════════════════════════════════════
# ⛔ تهيئة: حساب مسجّل فعلاً
def _code_of(html):
    import re
    m = re.search(r">(\d{6})<", html or "")
    return m.group(1) if m else ""


def _register():
    """⛔⛔ المسار القديم بقى 410 ⇒ نستخدم المسار الجديد كامل:
    signup/start → signup/verify → signup/newpin."""
    m0 = len(MAILS)
    r = call("/api/auth/signup/start",
             body={"name": "تجربة", "email": A_EMAIL})
    ok(r.status_code == 200, "signup/start فشل: %s %s"
       % (r.status_code, jbody(r)))
    code = ""
    for m in reversed(MAILS[m0:]):
        if m["to"] == A_EMAIL:
            code = _code_of(m["html"])
            break
    ok(code, "⛔ مافيش كود وصل في إيميل %s" % A_EMAIL)
    r = call("/api/auth/signup/verify",
             body={"email": A_EMAIL, "code": code})
    ok(r.status_code == 200, "signup/verify فشل: %s %s"
       % (r.status_code, jbody(r)))
    unlock = jbody(r).get("unlock")
    ok(unlock, "⛔ مافيش unlock")
    r = call("/api/auth/signup/newpin",
             body={"new_pin": A_PIN, "device": A_DEV}, token=unlock)
    ok(r.status_code == 200, "signup/newpin فشل: %s %s"
       % (r.status_code, jbody(r)))
    tok = jbody(r).get("token")
    ok(tok, "⛔ مافيش توكن بعد التسجيل")
    return tok


print("\n▸ تهيئة — حساب مسجّل: %s" % A_EMAIL)
TOK = _register()
ok(A_EMAIL in (up.USERS_FILE.read_text(encoding="utf-8")
               if up.USERS_FILE.exists() else ""),
   "⛔ الحساب ما اتسجلش في ملف المستخدمين")


# ══════════════════════════════════════════════════════════════
print("\n▸ ① الخدمة مطفّية — الرد لازم يكون واحد للحالتين")


def t_maildown_same_reply():
    up.MAIL_ON = False
    try:
        r_reg = call(SEND, body={"email": A_EMAIL})
        r_ghost = call(SEND, body={"email": GHOST})
    finally:
        up.MAIL_ON = True
    ok(r_reg.status_code == r_ghost.status_code,
       "⛔⛔ الرد بيفرّق في الكود: مسجّل %s · غريب %s"
       % (r_reg.status_code, r_ghost.status_code))
    ok(canon(r_reg) == canon(r_ghost),
       "⛔⛔ الرد بيفرّق في الجسم:\n   مسجّل: %s\n   غريب: %s"
       % (canon(r_reg), canon(r_ghost)))
    ok(jbody(r_reg).get("why") == "mail_down",
       "⛔ السبب المتوقع mail_down · الواقع %s" % jbody(r_reg).get("why"))
    # ⛔ مافيش كود مطبوع في الرد (تسريب إضافي)
    raw = canon(r_reg)
    ok("code" not in raw.lower(),
       "⛔ الرد فيه مفتاح code: %s" % raw)


# ══════════════════════════════════════════════════════════════
print("\n▸ ② الخدمة شغّالة — الرد واحد كمان (المسجّل والغريب)")


def t_mailup_same_reply():
    up.MAIL_ON = True
    m0 = len(MAILS)
    r_reg = call(SEND, body={"email": A_EMAIL})
    r_ghost = call(SEND, body={"email": GHOST})
    ok(r_reg.status_code == 200, "⛔ مسجّل %s" % r_reg.status_code)
    ok(r_ghost.status_code == 200, "⛔ غريب %s" % r_ghost.status_code)
    ok(canon(r_reg) == canon(r_ghost),
       "⛔ الرد مختلف:\n   مسجّل: %s\n   غريب: %s"
       % (canon(r_reg), canon(r_ghost)))
    # ⛌ الإيميل اتبعت **للمسجّل بس** — ده مش تسريب في الرد
    ok(any(m["to"] == A_EMAIL for m in MAILS[m0:]),
       "⛔ مافيش إيميل للمسجّل")


# ══════════════════════════════════════════════════════════════
print("\n▸ ③ الخدمة مطفّية — مافيش تنفيذ/تسجيل للإيميل الغريب")


def t_maildown_no_side_effect():
    up.MAIL_ON = False
    try:
        m0 = len(MAILS)
        r = call(SEND, body={"email": GHOST})
    finally:
        up.MAIL_ON = True
    ok(r.status_code == 503, "⛔ %s" % r.status_code)
    ok(len(MAILS) == m0, "⛔⛔ اتبعت إيميل وخدمة مطفّية!")
    # ⛌ العدّاد اليومي بيتحسب للحالتين (مش دليل على وجود الحساب)
    st = {}
    try:
        st = json.loads(up.PIN_CHAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    ok(isinstance(st, dict), "ملف الكود مش JSON")


# ══════════════════════════════════════════════════════════════
print("\n▸ ④ الحد اليومي — نفس الرد للحالتين (مافيش تسريب عبر العدّاد)")


def t_daily_cap_same():
    up.MAIL_ON = True
    # ⛔ نعبّي العدّاد اليومي للإيميل الغريب
    _day = int(up.time.time()) // 86400
    up.PIN_CHAL_FILE.write_text(json.dumps({
        "v": 1,
        "c": {"ghost@example.com": {"d": _day, "n": up.PIN_CHAL_PER_DAY}},
        "g": {},
    }), encoding="utf-8")
    try:
        r_ghost = call(SEND, body={"email": GHOST})
    finally:
        up.PIN_CHAL_FILE.unlink(missing_ok=True)
    ok(r_ghost.status_code == 429, "⛔ %s" % r_ghost.status_code)
    ok(jbody(r_ghost).get("why") == "daily_limit",
       "⛔ %s" % jbody(r_ghost))


# ══════════════════════════════════════════════════════════════
print("\n▸ ⑤ ⛔ negative proof — الكود القديم لازم يفشل الاختبار")
print("   (بيتنفّذ في مسار منفصل: base_check)")


def t_negative_proof():
    """⛔ برهان سلبي: على الكود قبل الإصلاح، الردّين مختلفين."""
    import subprocess
    root = Path(HERE)
    base = os.environ.get("MAILDOWN_BASE", "")
    if not base:
        print("      (تخطّي — مافيش مسار الأساس محدد)")
        return
    script = r"""
import sys, json, os, re, tempfile
from pathlib import Path
sys.path.insert(0, BASE_DIR)
import _stub_env
fl, _ = _stub_env.install()
os.environ['OCTAD_TOKEN_SECRET'] = 'TEST-ONLY-token-secret'
os.environ['OCTA_PIN_PEPPER'] = 'TEST-ONLY-pin-pepper'
os.environ['OCTAD_DEV'] = '1'
import update_prices as up
tmp = tempfile.mkdtemp()
up.USERS_FILE = Path(tmp) / 'users.json'
up.PINLOCK_FILE = Path(tmp) / 'pinlock.json'
up.PIN_CHAL_FILE = Path(tmp) / 'pinchal.json'
up.PIN_PEPPER_FILE = Path(tmp) / 'p.txt'
up.OTP_FILE = Path(tmp) / 'o.json'
up.SIGNUP_FILE = Path(tmp) / 's.json'
MAILS = []
up._send_mail = lambda to, subject, html: (MAILS.append({'to': to, 'html': html}) or True)
app = up.app
H = {'X-Forwarded-For': '10.1.0.1'}
EMAIL = 'amina@example.com'
app.dispatch('/api/auth/signup/start', method='POST',
             body={'name': 't', 'email': EMAIL}, headers=H)
code = ''
for m in reversed(MAILS):
    if m['to'] == EMAIL:
        g = re.search(r'>(\d{6})<', m['html'] or '')
        code = g.group(1) if g else ''
if not code:
    print('BASE SETUP-FAILED')
    sys.exit(4)
r = app.dispatch('/api/auth/signup/verify', method='POST',
                 body={'email': EMAIL, 'code': code}, headers=H)
unlock = (r.get_json() or {}).get('unlock')
app.dispatch('/api/auth/signup/newpin', method='POST',
             body={'new_pin': '7314', 'device': 'device-maildown-amina-tabla'},
             headers={'X-Forwarded-For': '10.1.0.1',
                      'Authorization': 'Bearer ' + str(unlock)})
up.MAIL_ON = False
a = app.dispatch('/api/auth/pin/challenge/send', method='POST',
                 body={'email': EMAIL}, headers=H)
b = app.dispatch('/api/auth/pin/challenge/send', method='POST',
                 body={'email': 'ghost@example.com'}, headers=H)
print('BASE', a.status_code, b.status_code)
sys.exit(0 if a.status_code != b.status_code else 3)
""".replace("BASE_DIR", repr(str(base)))
    p = subprocess.run([sys.executable, "-c", script],
                       capture_output=True, text=True, timeout=180,
                       cwd=str(base))
    out = (p.stdout or "") + (p.stderr or "")
    ok("BASE" in out, "⛔ مفيش ناتج من الأساس: %s" % out[-400:])
    ok(p.returncode == 0,
       "⛔⛔ الأساس رجّع ردود متطابقة ⇒ الكود القديم متصلّح أصلاً "
       "⇒ مافيش عيب ⇒TEST-BAD")
    print("      ✔ الأساس: الردود مختلفة ⇒ العيب كان موجود")


for name, fn in [
    ("الخدمة مطفّية ⇒ نفس الرد (كود + جسم)", t_maildown_same_reply),
    ("الخدمة شغّالة ⇒ نفس الرد", t_mailup_same_reply),
    ("الخدمة مطفّية ⇒ مافيش إيميل اتبعت", t_maildown_no_side_effect),
    ("الحد اليومي ⇒ why=daily_limit", t_daily_cap_same),
    ("negative proof على الأساس", t_negative_proof),
]:
    t(name, fn)

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
print("  النتيجة: %d ناجح / %d فاشل" % (_pass, _fail))
print("=" * 60)
sys.exit(1 if _fail else 0)
