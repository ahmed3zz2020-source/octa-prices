#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار مسار /api/data_full — بدون تشغيل السيرفر.

السبب: الجهاز المحلي مافيش فيه Flask ولا requests، فبنتحقق
بالتحليل الساكن (ast) + مقارنة الداتا الفعلية على القرص.

شغّله:  python3 test_data_full_route.py
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "update_prices.py")
# \u2b1c\ufe0f 17 \u0646\u0648\u0641\u0645\u0628\u0631 2026 (\u0627\u0644\u062c\u0648\u0644\u0629 15) \u2014 \u0645\u0633\u0627\u0631 \u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u0642\u062f\u064a\u0645:
# \u0643\u0627\u0646 \u0627\u0644\u0631\u064a\u0628\u0648 \u0627\u0644\u0645\u062c\u0627\u0648\u0631 \u0628\u0627\u0633\u0645 \u00abocta5\u00bb (\u0627\u0644\u0623\u0633\u0645 \u0627\u0644\u0642\u062f\u064a\u0645)
# \u2b1c\ufe0f \u0627\u0644\u0628\u0646\u0627 \u0627\u0644\u0645\u0631\u0634\u062d\u0627\u062a \u0627\u0644\u0645\u0639\u0642\u0648\u0644\u0629 \u0648\u0628\u0645\u0639\u0631\u0641 \u0627\u0644\u0645\u0633\u0627\u0631 \u0627\u0644\u0642\u062f\u064a\u0645.
def _find_fe():
    parent = os.path.dirname(HERE)
    cands = [
        os.path.join(parent, "octa", "data_full.json"),
        os.path.join(parent, "octa5", "data_full.json"),
        os.path.join(HERE, "data_full.json"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return cands[0]


FE = _find_fe()

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


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


tree = ast.parse(open(SRC, encoding="utf-8").read(), SRC)

# ── جمع المسارات ──
routes = {}          # path -> handler name
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef):
        for d in n.decorator_list:
            if (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "route"
                    and d.args and isinstance(d.args[0], ast.Constant)):
                routes.setdefault(d.args[0].value, []).append(n.name)

funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

print("\n▸ المسار محمي ومكتوب صح")

t("/api/data_full مسجّل", lambda: ok("/api/data_full" in routes,
                                     "المسار مش موجود: " + str(sorted(routes)[:5])))
t("المسار مالهوش تعارض مع مسار تاني",
  lambda: ok(len(routes.get("/api/data_full", [])) == 1, "متسجل أكتر من مرة"))


def _guard():
    fn = funcs.get("api_data_full")
    ok(fn is not None, "api_data_full مش موجود")
    src = ast.get_source_segment(open(SRC, encoding="utf-8").read(), fn)
    ok("require_user()" in src, "⛔ مفيش require_user — المسار مفتوح!")
    # لازم الـguard قبل الإرسال
    ok(src.index("require_user()") < src.index("jsonify(d)"),
       "⛔ jsonify(d) قبل الحارس")
    ok("401" in src, "مفيش 401")


t("require_user() قبل أي إرسال (401 بدون توكن)", _guard)


def _loader():
    fn = funcs.get("_data_full_payload")
    ok(fn is not None, "_data_full_payload مش موجود")
    src = ast.get_source_segment(open(SRC, encoding="utf-8").read(), fn)
    ok('startswith("EGS")' in src, "⛔ فلتر السندات EGS اتشال")
    ok('_shape' in src and '"full"' in src, "مفيش _shape marker")
    ok("/app/data_full.json" in src, "مفيش مسار Railway /app")


t("اللودر: فلتر EGS + _shape marker + مسار /app", _loader)


def _no_leak():
    """مفيش مسار تاني في السيرفر بيرجّع data_full.json من غير حماية"""
    for path, names in routes.items():
        if path in ("/api/data_full", "/api/egx_full", "/api/egx_full/"):
            continue
        for nm in names:
            fn = funcs.get(nm)
            if fn is None:
                continue
            s = ast.get_source_segment(open(SRC, encoding="utf-8").read(), fn) or ""
            if "data_full.json" in s:
                raise AssertionError("⛔ %s (%s) بيقرا data_full.json" % (path, nm))


t("مفيش مسار مفتوح بيقرا data_full.json", _no_leak)

# ── الداتا الفعلية ──
print("\n▸ الداتا (مقارنة مع الملف اللي كانت الواجهة بتجيبه)")

from pathlib import Path  # noqa: E402

ns = {"Path": Path, "__file__": SRC}
_lo = open(SRC, encoding="utf-8").read()
exec(_lo[_lo.index('_DATA_FULL = {"mtime"'):_lo.index('@app.route("/api/data_full")')], ns)
pay = ns["_data_full_payload"]()

if not os.path.isfile(FE):
    print("\u2b1c\ufe0f 2b1c\ufe0f file data_full.json not found in candidates: %s" % FE)
    print("   \u0627\u0644\u062a\u062d\u0642\u064a\u0642 \u0645\u0633\u062a\u0637\u0644\u0628 \u0627\u0644\u0645\u0644\u0641 \u2014 \u0647\u0630\u0647 \u0627\u062e\u062a\u0628\u0627\u0631 \u0628\u064a\u0626\u064a\u0629 \u0648\u0644\u0627 \u0639\u064a\u0628 \u0645\u0646 \u0627\u0644\u0643\u0648\u062f")
    sys.exit(1)
ref = json.load(open(FE, encoding="utf-8"))
rs, ps = ref["stocks"], pay["stocks"]

t("285 سهم", lambda: ok(len(ps) == 285, "العدد %d" % len(ps)))
t("نفس الكودز بالظبط", lambda: ok(set(rs) == set(ps),
                                   "sym diff: %s" % (set(rs) ^ set(ps))))
t("صفر فرق في أي قيمة", lambda: ok(
    [c for c in rs if rs[c] != ps.get(c)] == [],
    "فرق في %d سهم" % len([c for c in rs if rs[c] != ps.get(c)])))
t("نفس الحقول لكل سهم", lambda: ok(
    all(sorted(rs[c]) == sorted(ps[c]) for c in rs), "اختلاف حقول"))
t("_shape marker موجود", lambda: ok(pay.get("_shape") == "full", repr(pay.get("_shape"))))
t("مفيش سند حكومي", lambda: ok(
    [c for c in ps if c.upper().startswith("EGS")] == [], "في EGS"))

print("\n%s %d نجح · %d فشل\n" % ("❌" if _fail else "✅", _pass, _fail))
sys.exit(1 if _fail else 0)
