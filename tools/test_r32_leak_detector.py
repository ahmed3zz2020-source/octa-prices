"""⭐⭐⭐ (R32) ⭐⭐⭐ حارس ⭐⭐⭐ detector ⭐⭐⭐ التسرّب ⭐⭐⭐ ⭐⭐⭐

📌 العيب ⭐⭐⭐ (R32 ⭐⭐⭐ مكتشف ⭐⭐⭐ في ⭐⭐⭐ suite ⭐⭐⭐ الباك ⭐⭐⭐):
   ⛔ `test_signup_flow.py` ⭐⭐⭐ كان ⭐⭐⭐ يفحص ⭐⭐⭐ التسرّب ⭐⭐⭐ بمطابقة ⭐⭐⭐
   ⭐⭐⭐ **substring ⭐⭐⭐ خام ⭐⭐⭐** ⭐⭐⭐ للكود ⭐⭐⭐ (٦ ⭐⭐⭐ أرقام ⭐⭐⭐) ⭐⭐⭐ ⭐⭐⭐⇒ ⛔ أي ⭐⭐⭐
   ⭐⭐⭐ **رقم ⭐⭐⭐ أطول ⭐⭐⭐** ⭐⭐⭐ (طابع ⭐⭐⭐ زمني ⭐⭐⭐ ١٣ خانة ⭐⭐⭐ / ⭐⭐⭐ هاش ⭐⭐⭐ ٦٤ خانة ⭐⭐⭐)
   ⭐⭐⭐ ⭐⇢⛔ بيحتوي ⭐⭐⭐ ٦ ⭐⭐⭐ أرقام ⭐⭐⭐ متتالية ⭐⭐⭐ ⭐⇢⛔ ⭐⭐⭐ **إيجابية ⭐⭐⭐ كاذبة ⭐⭐⭐** ⭐⭐⭐
   ⭐⭐⭐ ⇒ ⭐⭐⭐ الفشل ⭐⭐⭐ **متذبذب ⭐⭐⭐** ⭐⭐⭐ (نفس ⭐⭐⭐ SHA ⭐⭐⭐: ⭐⭐⭐ فشل ⭐⭐⭐ مرة ⭐⭐⭐
   ⭐⭐⭐ ونجح ⭐⭐⭐ مرة ⭐⭐⭐) ⭐⭐⭐.

✅ المطلوب ⭐⭐⭐:
   ① ⭐⭐⭐ detector ⭐⭐⭐ الجديد ⭐⭐⭐ ⭐⇢⛔ **ما ⭐⭐⭐ يقولش ⭐⭐⭐ تسرّب ⭐⭐⭐** ⭐⭐⭐ على ⭐⭐⭐ هاش ⭐⭐⭐ أو ⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐
   ② ⭐⭐⭐ و ⭐⭐⭐ **لازم ⭐⭐⭐ يمسك ⭐⭐⭐ التسرّب ⭐⭐⭐ الحقيقي ⭐⭐⭐** ⭐⭐⭐ (قيمة ⭐⭐⭐ مستقلة ⭐⭐⭐ /
      ⭐⭐⭐ نص ⭐⭐⭐ / ⭐⭐⭐ رقم ⭐⭐⭐ / ⭐⭐⭐ توكن ⭐⭐⭐ بحدود ⭐⭐⭐) ⭐⭐⭐
   ③ ⭐⭐⭐ و ⭐⭐⭐ لازم ⭐⭐⭐ يبقى ⭐⭐⭐ **أقوى ⭐⭐⭐** ⭐⭐⭐ من ⭐⭐⭐ substring ⭐⭐⭐ خام ⭐⭐⭐ ⭐⭐⭐
"""

import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "test_signup_flow.py")

FAILURES = []
CHECKS = 0


def ok(cond, msg):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(msg)
        print("  FAIL: %s" % msg)
    return cond


def load_helpers():
    """⭐⭐⭐ تحميل ⭐⭐⭐ الدوال ⭐⭐⭐ من ⭐⭐⭐ test_signup_flow.py ⭐⭐⭐
       ⭐⭐⭐ من ⭐⭐⭐ غير ⭐⭐⭐ تشغيل ⭐⭐⭐ الاختبار ⭐⭐⭐ كله ⭐⭐⭐ (فيه ⭐⭐⭐ استيراد ⭐⭐⭐ app ⭐⭐⭐).
       ⭐⭐⭐ لو ⭐⭐⭐ الدوال ⭐⭐⭐ مش ⭐⭐⭐ موجودة ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ نرجع ⭐⭐⭐ للمكتشف ⭐⭐⭐ القديم ⭐⭐⭐
       ⭐⭐⭐ (substring ⭐⭐⭐ خام ⭐⭐⭐) ⭐⭐⭐ عشان ⭐⭐⭐ البرهان ⭐⭐⭐ السلبي ⭐⭐⭐ يطلع ⭐⭐⭐ واضح ⭐⭐⭐."""
    src = open(TARGET, encoding="utf-8").read()
    ns = {"json": json, "re": re, "os": os, "sys": sys}
    missing = []
    for fn in ("_json_values", "_standalone_values", "_has_raw_code"):
        m = re.search(r"^def %s\(.*?(?=^def |\Z)" % re.escape(fn), src, re.M | re.S)
        if not m:
            missing.append(fn)
            continue
        exec(compile(m.group(0), TARGET, "exec"), ns)
    if missing:
        print("  ℹ️ ⭐⭐⭐ الدوال ⭐⭐⭐ الناقصة ⭐⭐⭐: %s ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ الفحص ⭐⭐⭐ بالمكتشف ⭐⭐⭐ القديم ⭐⭐⭐ ⭐⭐⭐"
              % ", ".join(missing))

        def _old(s, code, vals=None):
            """⭐⭐⭐ المكتشف ⭐⭐⭐ القديم ⭐⭐⭐ ⭐⭐⭐ (substring ⭐⭐⭐ خام ⭐⭐⭐) ⭐⭐⭐"""
            return code in s

        ns["_has_raw_code"] = _old
        ns["_legacy_detector"] = True
    else:
        ns["_legacy_detector"] = False
    return ns


print("⭐⭐⭐ (R32) ⭐⭐⭐ حارس ⭐⭐⭐ detector ⭐⭐⭐ التسرّب ⭐⭐⭐")
ns = load_helpers()
has_raw = ns["_has_raw_code"]

print("\n① ⭐⭐⭐ إيجابية ⭐⭐⭐ كاذبة ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ لازم ⭐⭐⭐ ما ⭐⭐⭐ تكتشفش ⭐⭐⭐ تسرّب ⭐⭐⭐")
# ⭐⭐⭐ هاش ⭐⭐⭐ ٦٤ خانة ⭐⭐⭐ فيه ⭐⭐⭐ ٦ ⭐⭐⭐ أرقام ⭐⭐⭐ متتالية ⭐⭐⭐ ⭐⭐⭐
hash_hit = "df9e500816b2d9" + "a" * 49
ok(not has_raw(hash_hit, "500816"),
   "⭐⭐⭐ هاش ⭐⭐⭐ ٦٤ ⭐⭐⭐ خانة ⭐⭐⭐ ⭐⇢⛔ اتحسب ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐")
# ⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐ ١٣ ⭐⭐⭐ خانة ⭐⭐⭐ ⭐⭐⭐
epoch_hit = "1795349066672"
ok(not has_raw(epoch_hit, "906672"),
   "⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐ ١٣ ⭐⭐⭐ خانة ⭐⭐⭐ ⭐⇢⛔ اتحسب ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐")
# ⭐⭐⭐ هاش ⭐⭐⭐ JSON ⭐⭐⭐ حقيقي ⭐⭐⭐ ⭐⭐⭐
real_hash_json = json.dumps({"p": {"x@y.com": {"h": hash_hit, "u": "179941c089ba"}}})
ok(not has_raw(real_hash_json, "500816"),
   "⭐⭐⭐ هاش ⭐⭐⭐ جوه ⭐⭐⭐ JSON ⭐⭐⭐ ⭐⇢⛔ اتحسب ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐")
# ⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐ جوه ⭐⭐⭐ JSON ⭐⭐⭐ حقيقي ⭐⭐⭐ ⭐⭐⭐
real_epoch_json = json.dumps({"token_epoch": 1795349066672, "confirmed_at": 1795349066})
ok(not has_raw(real_epoch_json, "906672"),
   "⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐ جوه ⭐⭐⭐ JSON ⭐⭐⭐ ⭐⇢⛔ اتحسب ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐")
ok(not has_raw(real_epoch_json, "349066"),
   "⭐⭐⭐ طابع ⭐⭐⭐ زمني ⭐⭐⭐ (٢ ⭐⭐⭐ خانة ⭐⭐⭐) ⭐⭐⭐ ⭐⇢⛔ اتحسب ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐")

print("\n② ⭐⭐⭐ التسرّب ⭐⭐⭐ الحقيقي ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ لازم ⭐⭐⭐ يتكشف ⭐⭐⭐")
ok(has_raw(json.dumps({"p": {"x@y.com": {"code": "500816"}}}), "500816"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ كقيمة ⭐⭐⭐ JSON ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")
ok(has_raw(json.dumps({"p": {"x@y.com": {"c": 500816}}}), "500816"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ كرقم ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")
ok(has_raw('{"note": "code: 500816"}', "500816"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ كنص ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")
ok(has_raw('{"code": "500816"}', "500816"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ مقتبس ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")
ok(has_raw('{"a": "x 500816 y"}', "500816"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ جوّا ⭐⭐⭐ نص ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")
ok(has_raw('{"pin": "1111"}', "1111"),
   "⭐⭐⭐ كود ⭐⭐⭐ خام ⭐⭐⭐ ⭐⇢⛔ ما ⭐⭐⭐ اتكشفش ⭐⭐⭐ ⭐⭐⭐")

print("\n③ ⭐⭐⭐ detector ⭐⭐⭐ الجديد ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ **أقوى ⭐⭐⭐** ⭐⭐⭐ من ⭐⭐⭐ substring ⭐⭐⭐ ⭐⭐⭐")
# ⭐⭐⭐ الحالات ⭐⭐⭐ اللي ⭐⭐⭐ القديم ⭐⭐⭐ كان ⭐⭐⭐ بيفوّتها ⭐⭐⭐ ⭐⭐⭐
old_would_miss = 'code=500816'
ok(("500816" in old_would_miss) and has_raw(old_would_miss, "500816"),
   "⭐⭐⭐ sanity ⭐⭐⭐ ⭐⭐⭐")
# ⭐⭐⭐ الحالة ⭐⭐⭐ الوحيدة ⭐⭐⭐ اللي ⭐⭐⭐ القديم ⭐⭐⭐ بيفوّتها ⭐⭐⭐ ⭐⭐⭐:
# ⭐⭐⭐ الكود ⭐⭐⭐ جوه ⭐⭐⭐ **رقم ⭐⭐⭐ أطول ⭐⭐⭐** ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ القديم ⭐⭐⭐ كان ⭐⭐⭐ بيعتبرها ⭐⭐⭐ تسرّب ⭐⭐⭐ ⭐⭐⭐
ok(("500816" in hash_hit) and not has_raw(hash_hit, "500816"),
   "⭐⭐⭐ الحالة ⭐⭐⭐ دي ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ القديم ⭐⭐⭐ إيجابية ⭐⭐⭐ كاذبة ⭐⭐⭐ ⭐⭐⭐ ⭐⭐⭐⇢ ⭐⭐⭐ الجديد ⭐⭐⭐ صح ⭐⭐⭐ ⭐⭐⭐")

print("\n④ ⭐⭐⭐ العقود ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ الـhelper ⭐⭐⭐ لازم ⭐⭐⭐ يبقى ⭐⭐⭐ موجود ⭐⭐⭐")
ok(os.path.exists(TARGET), "⭐⭐⭐ ملف ⭐⭐⭐ الاختبار ⭐⭐⭐ مش ⭐⭐⭐ موجود ⭐⭐⭐")
src = open(TARGET, encoding="utf-8").read()
ok("if c in s:" not in src,
   "⭐⭐⭐ لسه ⭐⭐⭐ فيه ⭐⭐⭐ detector ⭐⭐⭐ قديم ⭐⭐⭐ (substring ⭐⭐⭐ خام ⭐⭐⭐) ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ الفشل ⭐⭐⭐ المتذبذب ⭐⭐⭐ هيفضل ⭐⭐⭐ ⭐⭐⭐")
ok(not ns.get("_legacy_detector"),
   "⭐⭐⭐ الدوال ⭐⭐⭐ (_json_values ⭐⭐⭐ / ⭐⭐⭐ _standalone_values ⭐⭐⭐ / ⭐⭐⭐ _has_raw_code ⭐⭐⭐) "
   "⭐⭐⭐ مش ⭐⭐⭐ موجودة ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ المكتشف ⭐⭐⭐ القديم ⭐⭐⭐ لسه ⭐⭐⭐ شغّال ⭐⭐⭐ ⭐⭐⭐")

print("\n" + "=" * 60)
if FAILURES:
    print("❌ ⭐⭐⭐ %d ⭐⭐⭐ / ⭐⭐⭐ %d ⭐⭐⭐ فشل ⭐⭐⭐" % (len(FAILURES), CHECKS))
    for f in FAILURES:
        print("   ⭐⭐⭐ %s" % f)
    sys.exit(1)
print("✅ ⭐⭐⭐ %d ⭐⭐⭐ / ⭐⭐⭐ %d ⭐⭐⭐ نجح ⭐⭐⭐ ⭐⭐⭐ ⭐⭐⭐ detector ⭐⭐⭐ التسرّب ⭐⭐⭐ ⭐⭐⭐"
      % (CHECKS, CHECKS))
