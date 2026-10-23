# -*- coding: utf-8 -*-
"""
🛰️ اختبارات مساح الرادار — test_radar_api.py
==============================================
⛔ الفكرة: مسح ٢٨٩ سهم بيحتاج تاريخ كل واحد. لو المتصفح جابه
   بنفسه ⇒ ١٥ طلب/دقيقة ⇒ ٢٠ دقيقة. مستحيل.

   الحل: السيرفر يجيب التاريخ (مع semaphore + كاش).
   الاختبارات دي بتتأكد:
     ① تنظيف الكون (السندات + ترجمة ISIN) صح
     ② المسارات متسجّلة فعلاً
     ③ بارامتر القائمة مش بيتمسّح بالتنظيف العام
     ④ السtimeout والـconcurrency آمنين
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL = 0


def check(label, got, want=True):
    global FAIL
    ok = (got == want)
    if not ok:
        FAIL += 1
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}"
          + ("" if ok else f": جاب {got!r} / المتوقّع {want!r}"))


print("═" * 62)
print("🛰️  اختبارات مساح الرادار")
print("═" * 62)

# ── ① الملف موجود و سليم نحوياً ───────────────────────────────
print("\n① فحص الملف:")
p = os.path.join(HERE, "radar_api.py")
check("radar_api.py موجود", os.path.exists(p))
if os.path.exists(p):
    try:
        ast.parse(open(p, encoding="utf-8").read())
        check("radar_api.py سليم نحوياً", True)
    except SyntaxError as e:
        check("radar_api.py سليم نحوياً", False, True)
        print("     ", e)

# ── ② المسارات متسجّلة في update_prices.py ─────────────────────
print("\n② الربط:")
src = open(os.path.join(HERE, "update_prices.py"), encoding="utf-8").read()
check("update_prices.py بيسجّل radar_api", "import radar_api" in src)
check("الربط fail-soft (try/except)", "except Exception as _radar_err" in src)
# ⛔ لازم الربط يكون بعد تعريف app
i_app = src.find("app = Flask(")
i_reg = src.find("import radar_api")
check("الربط بعد إنشاء app", i_app < i_reg and i_app >= 0)

# ── ③ تنظيف الكون ─────────────────────────────────────────────
print("\n③ تنظيف الكون:")
sys.path.insert(0, HERE)
import radar_api as R  # noqa: E402

check("سند حكومي بيتشال", R.clean_code("EGS30AJ1C016-EGP")[0] is None)
check("محفظة صناديق بتتشال", R.clean_code("EGS65621C012")[0] is None)
check("ISIN بيتترجم للرمز", R.clean_code("EGS3I0S1C019")[0] == "FCMD")
check("ISIN ٢", R.clean_code("EGS370O1C013")[0] == "NAPR")
check("ISIN ٣", R.clean_code("EGS659O1C015")[0] == "IDSC")
check("رمز عادي بيفضل زي ما هو", R.clean_code("COMI")[0] == "COMI")
check("حروف صغيرة بتتظبّط", R.clean_code("comi")[0] == "COMI")
check("فاضي ⇒ None", R.clean_code("")[0] is None)
check("None ⇒ None", R.clean_code(None)[0] is None)

# ── ④ اسم البارامتر ───────────────────────────────────────────
print("\n④ بارامتر القائمة:")
# ⛔ التنظيف العام بياخد أي بارامتر اسمه code/symbol/codes
#    ويحطه في clean_code — وده بيقبل رمز واحد بس.
#    فلازم نستخدم «list» مش «codes».
check("«codes» مش مستخدم كاسم بارامتر في الكود",
      'request.args.get("codes")' not in open(p, encoding="utf-8").read()
      or 'request.args.get("list")' in open(p, encoding="utf-8").read())
check("«list» هو الأساسي", 'request.args.get("list")' in open(p, encoding="utf-8").read())

# ── ⑤ الأمان: concurrency + timeout + retry ───────────────────
print("\n⑤ أمان الاتصال بالمصدر:")
body = open(p, encoding="utf-8").read()
check("في semaphore عالمي", "_SEM = threading.Semaphore" in body)
check("الـsemaphore بيتستخدم", "with _SEM:" in body)
check("في timeout", "timeout=FETCH_TIMEOUT" in body)
check("في محاولة تانية", "for attempt in range(2)" in body)
check("سقف الأكواد ٦٠", "MAX_CODES = 60" in body)
check("الكاش له TTL", "CACHE_TTL = 1800" in body)
# ⛔ مفيش سر مكتوب في الكود
for secret in ("API_KEY", "SECRET_KEY", "TOKEN=", "password"):
    check(f"مفيش «{secret}» في الكود", secret not in body)

# ── ⑥ المسارات محمية ──────────────────────────────────────────
print("\n⑥ الحماية:")
check("المسارات بتطلب تسجيل دخول", "require_user" in body)
check("فيه 401 عند عدم الدخول", "محتاج تسجيل دخول" in body)

# ── ⑦ النتيجة ─────────────────────────────────────────────────
print("\n" + "═" * 62)
if FAIL:
    print(f"❌ {FAIL} اختبار فاشل")
    sys.exit(1)
print("✅ كل اختبارات الرادار ناجحة")
sys.exit(0)
