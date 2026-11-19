# -*- coding: utf-8 -*-
"""
🧪 اختبار السعر الحيّ للذهب — **منفصل** عن مجموعة الاختبارات الحتمية

⛔ ليه الاختبار ده منفصل؟
   الجولة ٢٣ (R23 · Phase 4) — صاحب المشروع طلب فصل اختبارات **السعر الحيّ**
   عن اختبارات **الحتمية** ⭐:
   · الاختبار الحيّ بيقارن **السجل المسجَّل** بـ **السعر الحيّ** ⭐
     (سعر جرام الذهب في السوق دلوقتي) ⭐ ⇒ بيتغيّر كل يوم ⭐
     ⇒ أي انحراف بينه وبين السجل = **حركة سوق** ⭐ مش عيب في الكود ⭐.
   ⛔ الاختبار **مش محذوف** ⭐ — بينتقل هنا ⭐ وبيفضل **قابل للتشغيل** ⭐.

📌 الجولة ٢٥ (المرحلة ٧ · R24-I14) — تفسير الانحراف بقى **بمصادر مستقلة**:
   ① ذهب عالمي (دولار/أونصة) من مزوّد مستقل
   ② صرف (جنيه/دولار) من مصدر **عملة** — مش مشتقّ من الذهب
   ③ سعر محلي مصري (جنيه/جرام · ٢٤ و٢١) من مرجع سوق
   وبنتقارن الثلاثة في **نفس اللحظة** (بفارق مقاس) وبنفكّك الانحراف إلى:
   **أثر السعر** · **أثر العملة** · **فرق التسعير المحلي** · **قدم البيانات**.
   ⛔ الحد المسموح **١٫٥٪** ما اتغيّرش (المالك منع رفعه) — ولو الانحراف
      عداه ⇒ الاختبار **بيقول** إن ده انحراف **بنيوي** في طبقة التسعير
      (مش خطأ في السلسلة) وبيفشل برضه.

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
T = 31.1035
# ⛔⛔⛔ الحد المقبول للانحراف = ١٫٥٪ — **ما ينفعش يترفع**.
#    (المالك رفض صراحةً رفعه لـ٥٪ · الجولة ٢٥) ⇒ المتغير البيئي يقدر
#    **يشدّ** الحد بس ما يقدرش يوسّعه.
MAX_TOLERANCE_PCT = 1.5
_env_tol = float(os.environ.get("OCTA_LIVE_GOLD_TOLERANCE_PCT", "1.5"))
TOLERANCE_PCT = min(_env_tol, MAX_TOLERANCE_PCT)
# 📌 فرق التوقيت المقبول بين القراءات (دقّة نشر سعر الصرف المرجعي)
MAX_READING_SPREAD_MIN = 180

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


def _show(label, r):
    """توثيق كل قراءة: المزوّد · الرابط · الحقل · الوحدة · العيار · الوقت."""
    if not r:
        print("   %-12s ⛔ مفيش قراءة" % label)
        return
    print("   %-12s %s %s" % (label, r.get("value"), r.get("unit") or ""))
    print("       المصدر   : %s" % (r.get("name") or "-"))
    print("       الرابط   : %s" % (r.get("url") or "-"))
    print("       الحقل    : %s" % (r.get("field") or "-"))
    print("       العيار   : %s" % (r.get("karat") or "-"))
    print("       وقت المصدر: %s" % (r.get("source_timestamp") or "غير متاح"))
    if r.get("error"):
        print("       ⛔ %s" % r.get("error"))


def main():
    # ── ⛔ الحارس: بدون موافقة صريحة ⇒ تخطّي برسالة واضحة ──
    if os.environ.get(LIVE_ENV, "").strip().lower() not in ("1", "true", "yes", "on"):
        return _skip("اختبار السعر الحيّ محتاج %s=1 — السعر بيتغيّر كل يوم، "
                     "فمش جزء من مجموعة الاختبارات الحتمية" % LIVE_ENV)

    import gold_history as gh
    import gold_local as gl
    import gold_parity as gpar

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
    print("   آخر نقطة مسجَّلة: %s ⇒ %.2f ج.م/جرام (ذهب %.4f دولار/أونصة · "
          "صرف %.4f جنيه/دولار)"
          % (last["d"], last["gram"], last["xau"], last["egp_per_usd"]))

    section("السعر الحيّ المرصود (السوق المحلي)")
    loc = gl.get(force=True) or {}
    obs = loc.get("gram_24_reference")
    if not obs:
        print("   ⏭️  السعر المرصود غير متاح دلوقتي (%s) — مافيش مقارنة"
              % str(loc.get("error"))[:90])
        return 0
    print("   السعر المرصود: %.2f ج.م/جرام (مصدر: %s · %s)"
          % (obs, loc.get("source") or "isagha",
             loc.get("updated_iso") or ""))

    # ── ⭐ القياسات المستقلة (الجولة ٢٥) ──
    section("القراءات المستقلة (نفس اللحظة)")
    gold = gpar.world_gold(force=True)
    fx = gpar.fx_official(force=True)
    fx_mkt = gpar.local_fx_market(force=True)
    gold_spot = gpar.world_gold_spot_crosscheck()
    _show("الذهب العالمي", gold)
    _show("الصرف (مستقل)", fx)
    _show("السعر المحلي", gpar.local_gold(force=True))
    if gold_spot.get("ok"):
        print("   تقاطع        : الذهب الفوري %s دولار/أونصة (وقت %s) — "
              "أساس العقد الآجل عن الفوري"
              % (gold_spot.get("value"), gold_spot.get("source_timestamp")))
    if fx_mkt.get("ok"):
        print("   تقاطع        : الدولار في سوق الصياغة %s جنيه/دولار "
              "(وقت %s)" % (fx_mkt.get("value"),
                            fx_mkt.get("source_timestamp") or "وقت السحب"))
    if fx.get("cross_checks"):
        print("   تقاطع        : مصادر الصرف الأخرى: %s"
              % " · ".join("%s = %s (وقت %s)"
                           % (c.get("id"), c.get("value"),
                              c.get("source_timestamp"))
                           for c in fx["cross_checks"]))
        print("   تشتّت بين مصادر الصرف: %.4f%%" % (fx.get("dispersion_pct") or 0))

    if not (gold.get("ok") and fx.get("ok")):
        print("   ⛔ مفيش قراءات مستقلة كاملة ⇒ مافيش تفكيك (مش صفر كاذب)")
        check(False, "القراءات المستقلة متاحة (ذهب + صرف مستقل)")
        print("\n" + "=" * 62)
        print("❌ فشل %d اختبار حيّ" % len(fails))
        return 1

    # ── ⭐ التفكيك الصادق ──
    section("التفكيك (مصدر مستقل لكل رجل)")
    dec = gpar.decompose_drift(last, gold.get("value"), fx.get("value"),
                               obs,
                               fx_market_egp_per_usd=(fx_mkt.get("value")
                                                      if fx_mkt.get("ok") else None))
    drift = dec.get("drift_pct")
    print("   الانحراف (السجل ⇦ المرصود): %+.4f%% (الحد المسموح ±%.2f%%)"
          % (drift or 0, TOLERANCE_PCT))
    print("   أثر السعر (الذهب العالمي)  : %+.4f%%" % (dec.get("gold_leg_pct") or 0))
    print("   أثر العملة (الصرف المستقل)  : %+.4f%%" % (dec.get("fx_leg_pct") or 0))
    print("   فرق التسعير المحلي (علاوة) : %s%%"
          % ("%.4f" % dec["local_premium_pct"]
             if dec.get("local_premium_pct") is not None else "غير قابل للقياس"))
    print("   التوازي عند الصرف المستقل   : %.2f ج.م/جرام (عيار ٢٤)"
          % (dec.get("parity_egp_per_gram") or 0))
    print("   سعر الصرف المضمّن في السعر المحلي (مشتقّ — ليس مستقلاً): %s جنيه/دولار"
          % (dec.get("implied_egp_per_usd_from_local_price") or "-"))
    if dec.get("fx_market_egp_per_usd"):
        print("   ≡ مقارنة بنفس المطابقة بسعر الصرف المحلي المنشور (%s): "
              "فرق التسعير %.4f%%"
              % (dec.get("fx_market_egp_per_usd"),
                 dec.get("local_premium_vs_market_fx_pct") or 0))

    # ① الاتساق الداخلي للسلسلة (وحدة الجرام)
    live_gram = last["xau"] * last["egp_per_usd"] / T
    self_drift = (last["gram"] / live_gram - 1) * 100
    check(abs(self_drift) <= 0.5,
          "الاتساق الداخلي للسلسلة سليم (≤ 0.5%%) — %.4f%%" % self_drift)

    # ② ⛔ الصرف المستخدم لازم يكون مستقل (مش مشتقّ من سعر الذهب)
    circ = gpar.detect_circular_fx(fx.get("value"), obs, gold.get("value"))
    check(circ.get("circular") is False,
          "⛔ سعر الصرف المستقل مش مشتقّ من سعر الذهب (فرق %.4f%% مع الرقم "
          "المشتقّ)" % (circ.get("diff_pct") or 0))
    check(dec.get("local_premium_pct") is not None,
          "فرق التسعير المحلي **مقاس** (مش صفر بالبناء)")

    # ③ الهوية
    check(dec.get("identity_holds") is True,
          "الهوية اللوغاريتمية قاعدة (خطأ %.2e)" % (dec.get("identity_error_ratio") or 0))

    # ④ ⛔ الحد (١٫٥٪) — ما اترفعش · والانحراف لو عداه لازم يتفسّر
    check(abs(drift) <= TOLERANCE_PCT,
          "انحراف السعر الحيّ داخل الحد (%.2f%% ≤ %.2f%%)"
          % (abs(drift or 0), TOLERANCE_PCT))
    if abs(drift or 0) > TOLERANCE_PCT:
        cls = gpar.classify_drift(dec, TOLERANCE_PCT)
        print("   ⓘ التفسير (بيسند، مش بيبرهن): %s" % (cls.get("statement") or "-"))
        if cls.get("structural"):
            print("      ⭐ ده انحراف **بنيوي** في طبقة التسعير/العملة ⭐ — "
                  "مش خطأ في كود السلسلة (الاتساق الداخلي %.4f%% ⭐)."
                  % self_drift)
            print("      ⛔ الحد المقبول **١٫٥٪** ما اتغيّرش ⭐ — "
                  "المالك رفض رفعه ⭐.")
        else:
            print("      ⛔ الانحراف ده **مش مفسّر** بالقراءات المستقلة "
                  "المعروضة ⭐ — مش هنخترع له تفسير ⭐.")

    # ⑤ تزامن القياسات: القراءة في نفس اللحظة
    st = gpar.staleness_report({
        "gold": gold.get("source_timestamp"),
        "fx": fx.get("source_timestamp"),
        "local": loc.get("updated_iso"),
    })
    print("   فرق التوقيت بين القراءات: %s دقيقة (عمر الذهب %s · الصرف %s · "
          "المحلي %s)"
          % (st.get("spread_minutes"), st.get("ages_minutes", {}).get("gold"),
             st.get("ages_minutes", {}).get("fx"),
             st.get("ages_minutes", {}).get("local")))
    check(st.get("spread_minutes") is not None
          and st["spread_minutes"] <= MAX_READING_SPREAD_MIN,
          "القراءات اتقريت في نفس اللحظة تقريباً (≤ %d دقيقة)"
          % MAX_READING_SPREAD_MIN)

    # ⑥ قدم بيانات السلسلة
    chain_st = gpar.chain_staleness(last)
    if chain_st.get("ok"):
        print("   ⏱️  نقطة السلسلة (%s) ⇒ الإقفال الفعلي %s (عمرها %s دقيقة "
              "وقت القياس)"
              % (chain_st.get("series_date"), chain_st.get("close_utc"),
                 chain_st.get("age_minutes")))

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
