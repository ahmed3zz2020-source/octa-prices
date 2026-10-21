#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار بوابة الـAPI + داتا السوق — ٢١ أكتوبر ٢٠٢٦
=====================================================

📌 ليه الملف ده؟
   ٧٠ من ٩١ مسار في الـAPI كانوا مفتوحين للزائر المجهول:
   أي حد كان بينزّل الداتا كاملة ويسحب تحليل /api/chat من غير حساب.
   و`data/data_markets.js` (٣٫٤ ميجا) كان ملف عام على الـCDN.

   الاختبارات دي بتأكد إن:
     ① المسارات المفتوحة فاضية مفتوحة (الـhealth · التتبع · الدخول)
     ② كل مسار بيانات بيرجع 401 من غير توكن
     ③ نفس المسارات بتفتح بتوكن صالح
     ④ /api/markets محمي ومقسّم بالسوق ومفيش «الكل»
     ⑤ أحداث التتبع الجديدة (signup_start · pin_reset) بتتقبل
     ⑥ داتا السوق مطابقة **حرفياً** للملف القديم

⛔ داتا الاختبار كلها بتتبعت في مجلد مؤقت في /tmp.

شغّله:  python3 test_api_gate.py
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
TMP = tempfile.mkdtemp(prefix="gtest_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

up.USERS_FILE = pathlib.Path(TMP) / "users.json"
up.PINLOCK_FILE = pathlib.Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = pathlib.Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = pathlib.Path(TMP) / "otp.json"
up.SIGNUP_FILE = pathlib.Path(TMP) / "signup.json"
up.TRACK_FILE = pathlib.Path(TMP) / "track.json"
up.MAIL_ON = False

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


def call(path, method="GET", body=None, ip="10.0.0.1", token=None,
         headers=None):
    up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    h.update(headers or {})
    if token:
        h["Authorization"] = "Bearer " + token
    # ⛌ الـstub ما بيعرفش الـquery string جوّه الـpath —
    #    فنفصلها ونبعتها صح (زي Flask).
    query = None
    if "?" in path:
        path, _, qs = path.partition("?")
        query = {}
        for part in qs.split("&"):
            if not part:
                continue
            k, _, v = part.partition("=")
            query[k] = v
    return app.dispatch(path, method=method, body=body, headers=h,
                        query=query)


def raw_of(r):
    """الرد الخام (بايت) — المسار بيرجّع Response مش jsonify"""
    b = getattr(r, "body", None)
    if isinstance(b, (bytes, bytearray)):
        return bytes(b)
    if isinstance(b, str):
        return b.encode("utf-8")
    return json.dumps(b, ensure_ascii=False).encode("utf-8")


def canon(r):
    return json.dumps(r.get_json() or {}, ensure_ascii=False, sort_keys=True)


def make_user(name, email):
    """مستخدم بتوكن صالح — من غير ما يمرّ على الإيميل"""
    uid = "t" + str(abs(hash(email)) % 10 ** 12)
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = {"id": uid, "name": name, "email": email,
                      "created": int(time.time()), "pin_hash": "x",
                      "pin_salt": "y", "pin_idx": up._pin_index("1111")}
        up._save_users(users)
    return uid, up._make_token(uid)


UID, TOKEN = make_user("مستخدم", "gate@example.com")


# ══════════════════════════════════════════════════════════════════
#  ①  المسارات المفتوحة — لازم تفضل مفتوحة
# ══════════════════════════════════════════════════════════════════
print("\n▸ ①  المسارات المفتوحة (اللي لازم تفضل مفتوحة)")


def t_open_paths():
    cases = [
        ("/api/health", "GET", None),
        ("/api/track", "POST", {"event": "page_view", "page": "screener"}),
        ("/api/logos", "GET", None),
    ]
    for path, method, body in cases:
        r = call(path, method=method, body=body)
        ok(r.status_code != 401,
           "%s رجّع 401 — المفروض يفضل مفتوح" % path)
    # ⛔ الـauth كله مفتوح (تسجيل · دخول · استرجاع)
    # ⛌ مهم: نقيس **رد البوابة** مش الـstatus — لأن مسار الدخول
    #    بيرجّع 401 برضه لما الباسورد يكون غلط (وده صح).
    for path in ("/api/auth/pin/login", "/api/auth/signup/start",
                 "/api/auth/signup/verify", "/api/auth/signup/newpin",
                 "/api/auth/pin/challenge/send",
                 "/api/auth/pin/challenge/verify",
                 "/api/auth/pin/challenge/newpin"):
        r = call(path, method="POST", body={"pin": "0000", "email": "a@b.co",
                                            "code": "000000", "new_pin": "0000"})
        b = r.get_json() or {}
        gated = (b.get("why") == "unauthorized"
                 and b.get("error") == "المسار ده محمي"
                 and b.get("hint") == "سجّل دخول الأول")
        ok(not gated, "%s اتقفل بالبوابة — مسار الدخول لازم يكون مفتوح"
           % path)


t("المسارات المفتوحة فاضية مفتوحة", t_open_paths)


# ══════════════════════════════════════════════════════════════════
#  ②  كل مسار بيانات → 401 من غير توكن
# ══════════════════════════════════════════════════════════════════
print("\n▸ ②  البوابة — 401 من غير توكن")

PROTECTED = [
    ("/api/prices", "GET"),
    ("/api/ticker", "GET"),
    ("/api/stocks", "GET"),
    ("/api/rank", "GET"),
    ("/api/ranking", "GET"),
    ("/api/quotes", "GET"),
    ("/api/market_tech", "GET"),
    ("/api/sector-stats", "GET"),
    ("/api/gold", "GET"),
    ("/api/dividends", "GET"),
    ("/api/news/COMI", "GET"),
    ("/api/technical/COMI", "GET"),
    ("/api/fundamental/COMI", "GET"),
    ("/api/intelligence/COMI", "GET"),
    ("/api/explain/COMI", "GET"),
    ("/api/opportunity/COMI", "GET"),
    ("/api/opportunities", "GET"),
    ("/api/sentiment/COMI", "GET"),
    ("/api/risk/COMI", "GET"),
    ("/api/strategies", "GET"),
    ("/api/dashboard", "GET"),
    ("/api/filters", "GET"),
    ("/api/backtest", "GET"),
    ("/api/stress", "GET"),
    ("/api/calibration", "GET"),
    ("/api/portfolio", "GET"),
    ("/api/egx_full", "GET"),
    ("/api/data_full", "GET"),
    ("/api/ipo", "GET"),
    ("/api/obdepth/COMI", "GET"),
    ("/api/candles/COMI", "GET"),
    ("/api/charts", "GET"),
    ("/api/charts/list", "GET"),
    ("/api/top-movers", "GET"),
    ("/api/heat", "GET"),
    ("/api/sector/Finance", "GET"),
    ("/api/search/COMI", "GET"),
    ("/api/markets", "GET"),
    ("/api/portfolio/fit/COMI", "GET"),
    ("/api/strategy/COMI/swing", "GET"),
    ("/api/analyze", "POST"),
    ("/api/chat", "POST"),
]


def t_gate_401():
    bad = []
    for path, method in PROTECTED:
        r = call(path, method=method, body={} if method == "POST" else None)
        if r.status_code != 401:
            bad.append("%s → %s" % (path, r.status_code))
    ok(not bad, "⛔⛔ المسارات دي فتحت من غير توكن:\n     %s" % "\n     ".join(bad))


t("٤٠ مسار بيانات → 401 من غير توكن", t_gate_401)


def t_gate_401_body():
    r = call("/api/prices")
    b = r.get_json() or {}
    ok(b.get("ok") is False, "مش ok=false")
    ok(b.get("why") == "unauthorized", "السبب %s" % b.get("why"))
    ok("error" in b, "مافيش رسالة")


t("رد البوابة = 401 + why=unauthorized", t_gate_401_body)


def t_preflight_not_blocked():
    r = call("/api/prices", method="OPTIONS")
    ok(r.status_code != 401,
       "⛔⛔ الـpreflight اتقفل — الـCORS هيكسر")
    ok(r.status_code < 500, "حالة غريبة %s" % r.status_code)


t("الـpreflight (OPTIONS) مش متقفل", t_preflight_not_blocked)


# ══════════════════════════════════════════════════════════════════
#  ③  نفس المسارات بتفتح بتوكن صالح
# ══════════════════════════════════════════════════════════════════
print("\n▸ ③  نفس المسارات بتتوكن")


def t_gate_200():
    bad = []
    for path, method in PROTECTED:
        r = call(path, method=method, body={} if method == "POST" else None,
                 token=TOKEN)
        if r.status_code == 401:
            bad.append("%s → 401" % path)
    ok(not bad, "⛔⛔ المسارات دي اتقفلت رغم توكن صالح:\n     %s"
       % "\n     ".join(bad))


t("٤٠ مسار بيانات → تفتح بتوكن صالح", t_gate_200)


def t_gate_bad_token():
    for tok in ("abc.def", "x" * 300, "eyJ9.zzz"):
        r = call("/api/prices", token=tok)
        ok(r.status_code == 401, "توكن %r → %s" % (tok, r.status_code))


t("توكن فاسد → 401", t_gate_bad_token)


# ══════════════════════════════════════════════════════════════════
#  ④  /api/markets — محمي ومقسّم
# ══════════════════════════════════════════════════════════════════
print("\n▸ ④  /api/markets")


def t_markets_split():
    for mk in ("egypt", "us", "saudi", "uae"):
        r = call("/api/markets?market=" + mk, token=TOKEN)
        ok(r.status_code == 200,
           "%s → %s %s" % (mk, r.status_code, str(r.get_json())[:200]))
        raw = raw_of(r)
        ok(raw, "مافيش بيانات")
        d = json.loads(raw.decode("utf-8"))
        ok(mk in d, "مافيش مفتاح %s" % mk)
        ok(len(d[mk]) > 100, "%s فيها %d سطر بس" % (mk, len(d[mk])))


t("كل سوق بيرجّع داتا بتوكن", t_markets_split)


def t_markets_no_all():
    r = call("/api/markets?market=all", token=TOKEN)
    ok(r.status_code == 400, "'all' → %s (المفروض 400)" % r.status_code)
    r2 = call("/api/markets", token=TOKEN)
    ok(r2.status_code == 400, "من غير market → %s" % r2.status_code)
    r3 = call("/api/markets?market=zzz", token=TOKEN)
    ok(r3.status_code == 400, "سوق مجهول → %s" % r3.status_code)


t("مافيش «الكل» — 400 (مش ٣٫٤ ميجا في طلب واحد)", t_markets_no_all)


def t_markets_alias():
    for alias, want in (("egx", "egypt"), ("ksa", "saudi"),
                        ("america", "us"), ("dfm", "uae")):
        r = call("/api/markets?market=" + alias, token=TOKEN)
        ok(r.status_code == 200, "%s → %s" % (alias, r.status_code))
        raw = raw_of(r)
        d = json.loads(raw.decode("utf-8"))
        ok(want in d, "%s رجّع %s" % (alias, list(d.keys())))


t("الأسماء المستعارة شغالة (egx · ksa · america · dfm)", t_markets_alias)


def t_markets_no_token():
    r = call("/api/markets?market=egypt")
    ok(r.status_code == 401, "→ %s" % r.status_code)
    # ⛔⛔ مافيش leak في الرد
    b = canon(r)
    for leak in ("COMI", "البنك", "price", "volume"):
        ok(leak not in b, "⛔⛔ الرد فيه %s" % leak)


t("/api/markets من غير توكن → 401 ومافيش بيانات", t_markets_no_token)


def t_markets_data_identical():
    """⛔⛔ الداتا الجديدة لازم تكون **حرفياً** زي الملف القديم.
       مافيش إعادة حساب ولا تقريب ولا حقل ناقص."""
    old = "/workspace/octa/data/data_markets.js"
    if not os.path.isfile(old):
        print("     (الملف القديم مش موجود — اتخطّى)")
        return
    src = open(old, encoding="utf-8").read()
    m = re.match(r"window\.OCTA_MK\s*=\s*", src)
    legacy = json.loads(src[m.end():].rstrip().rstrip(";"))
    for mk in ("egypt", "us", "saudi", "uae"):
        p = up.MARKETS_DIR / (mk + ".json")
        ok(p.is_file(), "مافيش ملف %s" % p)
        new = json.loads(p.read_text(encoding="utf-8"))
        ok(mk in new, "مافيش %s في الملف الجديد" % mk)
        ok(new[mk] == legacy[mk],
           "⛔⛔ داتا %s مختلفة عن الملف القديم!" % mk)


t("⛔ داتا السوق مطابقة حرفياً للملف القديم", t_markets_data_identical)


# ══════════════════════════════════════════════════════════════════
#  ⑤  أحداث التتبع الجديدة
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑤  أحداث التتبع")


def t_track_events():
    for ev in ("signup_start", "pin_reset", "signup", "login",
               "page_view", "action"):
        r = call("/api/track", method="POST",
                 body={"event": ev, "page": "gate", "label": "x"})
        ok(r.status_code == 200,
           "⛔⛔ الحدث %s اترفض (%s) — الـfunnel فيه ثقب" % (ev, r.status_code))
    # ⛔ وحدث مجهول لسه يترفض
    r = call("/api/track", method="POST",
             body={"event": "hack_the_planet", "page": "x"})
    ok(r.status_code == 400, "حدث مجهول → %s (المفروض 400)" % r.status_code)


t("signup_start + pin_reset بيتقبلوا (كانوا 400)", t_track_events)


# ══════════════════════════════════════════════════════════════════
#  ⑥  الكوكي
# ══════════════════════════════════════════════════════════════════
print("\n▸ ⑥  كوكي الجلسة")


def t_cookie_flags():
    r = call("/api/auth/pin/login", method="POST", body={"pin": "0000"})
    ck = r.headers.get("Set-Cookie") or ""
    # ⛔ مش مهم نقدر نسجّل دخول هنا — المهم بنية الكوكي
    ok("HttpOnly" in ck or "octa_token" not in ck,
       "الكوكي مش HttpOnly: %s" % ck)
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    seg = src.split("def _json_auth")[1].split("\ndef ")[0]
    ok("httponly=True" in seg, "الكوكي مش HttpOnly في الكود")
    ok("samesite=" in seg.lower(), "مافيش SameSite")
    ok("secure=" in seg.lower(), "مافيش Secure")
    ok("octa_token" in seg, "مافيش اسم الكوكي")


t("الكوكي: HttpOnly + Secure + SameSite", t_cookie_flags)


def t_logout_clears_cookie():
    r = call("/api/auth/logout", method="POST")
    ck = r.headers.get("Set-Cookie") or ""
    ok("octa_token" in ck, "الخروج مابيمسحش الكوكي: %s" % ck)
    ok("Max-Age=0" in ck or "Expires" in ck, "الكوكي مش متمسح: %s" % ck)


t("الخروج بيمسح الكوكي", t_logout_clears_cookie)


# ══════════════════════════════════════════════════════════════════
print("\n" + "═" * 62)
print("  %d نجح · %d فشل" % (_pass, _fail))
print("═" * 62)
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if _fail else 0)
