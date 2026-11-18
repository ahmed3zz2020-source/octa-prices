# -*- coding: utf-8 -*-
"""
🧪 اختبار السعر الحيّ للذهب — **منفصل** عن مجموعة الاختبارات الحتمية

⛔ ليه الاختبار ده منفصل؟
   الجولة ٢٣ (R23 · Phase 4) — صاحب المشروع طلب فصل اختبارات **السعر الحيّ**
   عن اختبارات **الحتمية** ⭐:
   · الاختبار الحيّ بيقارن **السجل المسجَّل** بـ **السعر الحيّ** ⭐
     (سعر جرام الذهب في السوق دلوقتي) ⭐ ⇒ بيتغيّر كل يوم ⭐
     ⇒ أي انحراف بينه وبين السجل = **حركة سوق** ⭐ مش عيب في الكود ⭐.
   · تاريخياً الفشل ده كان **موجود قبل** الجولة دي ⭐:
     −2.13٪ على الـbase غير المعدَّل (edc49cd) ⭐
     −2.57٪ على الفرع وقت الفحص ⭐ ⇒ انحراف سوق حيّ ⭐ مش عيب ⭐.
   ⛔ الاختبار **مش محذوف** ⭐ — بينتقل هنا ⭐ وبيفضل **قابل للتشغيل** ⭐.

📌 التشغيل:
   ⏭️  افتراضياً: متخطّى برسالة واضحة
       python3 test_gold_live_price.py
   ▶️  تشغيل صريح (بجلب السعر الحيّ من الشبكة):
       OCTA_RUN_LIVE_TESTS=1 python3 test_gold_live_price.py
   ⛔ مافيش أي كتابة خارج /tmp · مافيش معاملة مالية.
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("GOLD_HISTORY_PATH", "/tmp/_gh_live_price.json")

LIVE_ENV = "OCTA_RUN_LIVE_TESTS"
TOLERANCE_PCT = float(os.environ.get("OCTA_LIVE_GOLD_TOLERANCE_PCT", "1.5"))
T = 31.1035

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def section(t):
    print("\n── %s ──" % t)


def _skip(reason):
    print("⏭️  متخطّى: %s" % reason)
    print("   (شغّله صريحاً بـ: %s=1 python3 %s)"
          % (LIVE_ENV, os.path.basename(os.path.abspath(__file__))))
    return 0


def main():
    # ── ⛔ الحارس: بدون موافقة صريحة ⇒ تخطّي برسالة واضحة ──
    if os.environ.get(LIVE_ENV, "").strip().lower() not in ("1", "true", "yes", "on"):
        return _skip("اختبار السعر الحيّ محتاج %s=1 — السعر بيتغيّر كل يوم، "
                     "فمش جزء من مجموعة الاختبارات الحتمية" % LIVE_ENV)

    import gold_history as gh
    import gold_local as gl

    section("السلسلة المسجَّلة (TradingView / Yahoo)")
    d = gh.build(force=True)
    if not d.get("ok"):
        print("   ❌ السلسلة ما اتبنتش: %s" % d.get("error"))
        return 1
    s = d["series"]
    if not s:
        print("   ❌ السلسلة فاضية")
        return 1
    last = s[-1]
    print("   آخر نقطة مسجَّلة: %s ⇒ %.2f ج.م/جرام" % (last["d"], last["gram"]))

    section("السعر الحيّ المرصود (السوق المحلي)")
    loc = gl.get(force=True) or {}
    obs = loc.get("gram_24_reference")
    if not obs:
        print("   ⏭️  السعر المرصود غير متاح دلوقتي (%s) — مافيش مقارنة"
              % str(loc.get("error"))[:90])
        return 0
    print("   السعر المرصود: %.2f ج.م/جرام (مصدر: %s · %s)"
          % (obs, loc.get("source") or "isagha",
             loc.get("fetched_at") or ""))

    # ── ⭐ القياس: انحراف السجل عن السعر الحيّ ──
    section("الانحراف المقاس (السجل ⇦ السعر الحيّ)")
    drift = (last["gram"] / obs - 1) * 100
    live_gram = last["xau"] * last["egp_per_usd"] / T
    self_drift = (last["gram"] / live_gram - 1) * 100
    print("   السجل (%.2f) ⇦ الحيّ (%.2f) ⇒ الانحراف %+.2f%% (الحد المسموح ±%.2f%%)"
          % (last["gram"], obs, drift, TOLERANCE_PCT))
    print("   الاتساق الداخلي: %.2f ⇦ %.2f ⇒ %+.4f%% (مفروض 0)"
          % (last["gram"], live_gram, self_drift))
    check(abs(self_drift) <= 0.5,
          "الاتساق الداخلي للسلسلة سليم (≤ 0.5%%) — %.4f%%" % self_drift)
    check(abs(drift) <= TOLERANCE_PCT,
          "انحراف السعر الحيّ داخل الحد (%.2f%% ≤ %.2f%%)"
          % (abs(drift), TOLERANCE_PCT))
    if abs(drift) > TOLERANCE_PCT:
        print("   ⓘ التفسير: انحراف أكبر من الحد = الفرق بين **سعر السوق المحلي**"
              " و (الذهب × الدولار) — فرق تسعير/عمولة/توقيت ⭐")
        print("      ⭐ ده **انحراف سوق حيّ** ⭐ — مش عيب في كود السلسلة ⭐"
              " (الاتساق الداخلي %.4f%% ⭐ ⇒ السلسلة سليمة ⭐)." % self_drift)

    section("نِسب العيّارات (من نفس المصدر الحيّ)")
    kar = loc.get("karats") or {}
    if kar:
        for k, purity in (("14", 14), ("18", 18), ("21", 21)):
            row = kar.get(k) or kar.get(k + "k") or kar.get("gold" + k) or {}
            sell = row.get("sell_gram") or row.get("sell")
            if not sell:
                continue
            ratio = sell / obs
            check(abs(ratio - purity / 24.0) < 0.002,
                  "عيار %s: %s ÷ %.0f = %.4f (المتوقع %.4f)"
                  % (k, sell, obs, ratio, purity / 24.0))
    else:
        print("   ⏭️  نسب العيّارات غير متاحة في المصدر الحيّ")

    print("\n" + "=" * 62)
    if fails:
        print("❌ فشل %d اختبار حيّ" % len(fails))
        for f in fails:
            print("   -", f)
        return 1
    print("✅ كل اختبارات السعر الحيّ عدّت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
