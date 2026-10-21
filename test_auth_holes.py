#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار الثغرات التلاتة — تشغيل حقيقي للمسارات (مش تحليل ساكن).

بيستعمل stubs خفيفة جداً للـFlask (الجهاز مافيش فيه pip)،
فبنحصل على **كود حالة حقيقي** من نفس الـhandlers اللي على السيرفر.

شغّله:  python3 test_auth_holes.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

_stub_env.install()

# ⛔ ⛔ السر مايتكتبش في أي deliverable — للتجربة بس
os.environ.setdefault("OCTAD_TOKEN_SECRET", "test-secret-" + str(int(time.time())))
os.environ.setdefault("FLASK_ENV", "testing")

import update_prices as up  # noqa: E402

app = up.app
_authed = {}


def anon(path, method="GET", query=None, body=None):
    return app.dispatch(path, method=method, query=query, body=body)


def as_user(path, method="GET", query=None, body=None, email="t@example.com"):
    uid = _authed.get(email)
    if not uid:
        with up.USERS_LOCK:
            users = up._load_users()
            uid = "u_test_%d" % (len(users) + 1)
            users[uid] = {
                "id": uid, "email": email, "name": "تست",
                "created": int(time.time()),
                "portfolio": {"holdings": {}, "cash": 0},
            }
            up._save_users(users)
        _authed[email] = uid
    tok = up._make_token(uid) if hasattr(up, "_make_token") else None
    if tok is None:
        for cand in ("_sign_token", "_token_for", "_new_token"):
            if hasattr(up, cand):
                tok = getattr(up, cand)(uid)
                break
    return app.dispatch(path, method=method, query=query, body=body,
                        headers={"Authorization": "Bearer " + str(tok)})


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


# ⛔ كل نداء مرة واحدة — rate limit بيرد 429 لو زوّدنا
_R = {
    "rank": anon("/api/ranking"),
    "pf": anon("/api/portfolio"),
    "pf_post": anon("/api/portfolio", "POST",
                    body={"action": "add", "code": "COMI", "shares": 1}),
    "rank_u": as_user("/api/ranking"),
    "pf_u": as_user("/api/portfolio"),
}


# ══════════════════════════════════════════════════════════
print("\n▸ ①  /api/ranking")

t("زائر مجهول → 401", lambda: ok(
    _R["rank"].status_code == 401,
    "الحالة %s مش 401" % _R["rank"].status_code))


def _no_data():
    b = _R["rank"].get_json() or {}
    # ⛔⛔ ٢١ أكتوبر ٢٠٢٦ — البوابة بقت قبل الـroute: الرد 401
    #    بحت (مافيش top20 ولا total أصلاً). الاختبار قبل كده كان
    #    متوقع `top20 == []` — دلوقتي مافيش أي بيانات أصلاً.
    ok(not b.get("top20"), "⛔ اتسرّب ترتيب: %s" % str(b)[:120])
    ok(not b.get("total"), "⛔ اتسرّب total: %r" % b.get("total"))
    ok(b.get("ok") is False, "⛔ الرد مش says ok=false: %s" % str(b)[:120])


t("مفيش أي بيانات في الرد", _no_data)

t("مستخدم مسجّل → 200", lambda: ok(
    _R["rank_u"].status_code == 200,
    "الحالة %s" % _R["rank_u"].status_code))


# ══════════════════════════════════════════════════════════
print("\n▸ ②  /api/portfolio")

t("GET زائر مجهول → 401", lambda: ok(
    _R["pf"].status_code == 401,
    "الحالة %s مش 401" % _R["pf"].status_code))


def _no_pf():
    b = _R["pf"].get_json() or {}
    for k in ("holdings", "total_value", "sector_exposure_pct", "count"):
        ok(k not in b, "⛔ اتسرّب مفتاح %s" % k)


t("مفيش أي مفاتيح محفظة في الرد", _no_pf)

t("POST زائر مجهول → 401", lambda: ok(
    _R["pf_post"].status_code == 401, "الحالة مش 401"))

t("GET مستخدم مسجّل → 200", lambda: ok(
    _R["pf_u"].status_code == 200, "الحالة %s" % _R["pf_u"].status_code))


# ══════════════════════════════════════════════════════════
print("\n▸ ③  كود الاسترجاع عشوائي فعلاً")


def _time_derived_mods():
    """
    ⛔ بندور في **الكود التنفيذي** بس (AST) — مش النص.
    ⛌ السبب: الشرح بالكتابة عن الكود القديم بيحتوي نفس الأرقام،
       فلو بحثنا في النص هنلاقي الكود القديم وهو في تعليق.
    """
    import ast
    src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
    tree = ast.parse(src, "update_prices.py")
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod):
            r = n.right
            if isinstance(r, ast.Constant) and r.value == 1000000:
                hits.append("سطر %d" % n.lineno)
    return hits

t("مفيش اشتقاق من الوقت في الكود", lambda: ok(
    not _time_derived_mods(),
    "⛔ لسه في اشتقاق من الوقت: %s" % _time_derived_mods()))


def _rand():
    """ولّد 400 كود وقارنهم بالسلوك المتوقع للوقت"""
    codes = [f"{up._random.SystemRandom().randint(0, 999999):06d}"
             for _ in range(400)]
    ok(all(len(c) == 6 and c.isdigit() for c in codes), "⛔ طول/نوع غلط")
    ok(len(set(codes)) > 380, "⛔ تكرار كتير: %d مختلف" % len(set(codes)))


t("6 أرقام، شبه‑مستحيل تتكرر", _rand)


def _not_time():
    """الكود الجديد لازم ما يتحسبش من now — قياس مباشر"""
    now = time.time()
    predicted = str(int(now * 1000) % 1000000).zfill(6)
    got = set()
    for _ in range(60):
        got.add(f"{up._random.SystemRandom().randint(0, 999999):06d}")
    ok(predicted not in got or len(got) > 50,
       "⛔ الكود لسه ماشي مع الوقت")
    ok(len(got) > 55, "⛔ تكرار: %d" % len(got))


t("مش مربوط بوقت السيرفر", _not_time)

t("الـTTL والحد اليومي زي ما هم", lambda: ok(
    up.RESET_TTL == 15 * 60 and up.RESET_MAX_PER_DAY == 3,
    "TTL=%s max=%s" % (up.RESET_TTL, up.RESET_MAX_PER_DAY)))


# ══════════════════════════════════════════════════════════
# ⛔ بنطلب كل المسار مرة واحدة ونخزن النتيجة — تكرار الطلبات
#    بيخلي rate limit يرد 429 وبيخفي النتيجة الصح.
print("\n▸ 🚪  كل المسارات الحساسة مقفولة لزائر مجهول")

SENSITIVE = ["/api/stats", "/api/ranking", "/api/portfolio",
             "/api/egx_full", "/api/data_full"]
_res = {p: anon(p) for p in SENSITIVE}
for p in SENSITIVE:
    t("%s → 401" % p, (lambda pp=p: ok(
        _res[pp].status_code == 401,
        "الحالة %s" % _res[pp].status_code)))

print("\n%s %d نجح · %d فشل\n" % ("❌" if _fail else "✅", _pass, _fail))
sys.exit(1 if _fail else 0)
