#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٥ (المرحلة ٧) — عقد قياس تكافؤ الذهب بمصادر **مستقلة**

🎯 الغرض: عقد **حتمي** (من غير شبكة) يثبت:
   ① البوابة الحتمية (سلامة السلسلة) **مفصولة** عن السعر الحيّ
   ② الاختبار الحيّ **متخطّى افتراضياً** وكود خروجه صفر
   ③ حدود البوابة الحتمية **صارمة** (اتساق داخلي ≤ 0.5٪ · حداثة ≤ 10 أيام)
   ④ ⭐ سبب انحراف السعر الحيّ **مفصول بالقياس** بمصادر مستقلة:
      ذهب عالمي مستقل · صرف مستقل · سعر محلي مرصود — **وكل واحد
      بتوقيته ووحدته وعياره موثّق**، والقياسات في نفس اللحظة تقريباً.
   ⑤ ⛔ الحد المقبول للانحراف **١٫٥٪** — ما اترفعش (المالك رفض ٥٪)،
      والانحراف اللي يعدّاه لازم يتوصف كـ**انحراف بنيوي** في طبقة
      التسعير (مش سببية مخترعة).

📌 📌 تصحيح مهم (الجولة ٢٥ · R24-I14):
   القياس بتاع الجولة ٢٤ كان فيه **دورية**: «سعر الدولار الضمني» كان
   بيتحسب من السعر المحلي نفسه، وبعدين **نفس** الرقم ده كان بيُستخدم
   لإثبات إن «الهامش المحلي = صفر» ⇒ النتيجة كانت **بالضرورة** صفر
   مهما كان السعر المرصود (برهان: ٦٠٠٠ أو ٩٠٠٠ ج.م/جرام ⇒ ٠٫٠٠٠٠٪).
   ⛔ سجل الجولة ٢٤ محفوظ زي ما هو (تاريخ) · بس الحقل اتسم صراحةً إنه
      **دائري بالبناء** · والقياس الجديد هو **المصدر المعتمد**.

📌 القياس المسجَّل تحت (مرجع حقيقي — وقت ومصدر كل رقم):
   · الذهب العالمي: `Yahoo Finance` (GC=F) — دولار/أونصة تروي
   · الصرف: `fxratesapi` (تقاطع: `exchangerate-api` · `Yahoo EGP=X`)
   · السعر المحلي: `iSagha` (٢٤/٢١) + تقاطع `goldbullioneg`
   القياس الكامل (مع البرهان السالب) بتتولّاه الأداة:
       python3 tools/r24_gold_drift_isolation.py

📌 التشغيل:
   python3 tools/test_round24_gold_gate_contract.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

T = 31.1035

# ══════════════════════════════════════════════════════════════════════
#  ① القياس المسجَّل (مرجع حقيقي — كل رقم بمصدره ووقته)
#  التاريخ: 2026-11-19 · سلسلة الذهب: TradingView · الحيّ: iSagha
# ══════════════════════════════════════════════════════════════════════
MEASUREMENT = {
    "measured_at_utc": "2026-11-18T17:58:53Z",
    "source_updated_iso": "2026-11-18T19:58:27+02:00",
    "live_source": "iSagha — مرجع سوق ذهب مصري",
    "series": {"date": "2026-11-17",
               "xau_usd_per_oz": 3734.64,
               "egp_per_usd": 53.70,
               "gram_egp": 6447.8328},
    "live": {"gram_24_reference_egp": 6617.25,
             "ounce_usd": 3734.04},
    "measured": {"drift_pct": -2.5602,
                 "gold_leg_pct": -0.0161,
                 "tv_xau_same_bar_pct": 0.0035,
                 "fx_leg_pct": 2.644,
                 # ⛔⛔⛔ الحقل ده كان **دائري بالبناء**: سعر الصرف الضمني
                 #    اتحسب من السعر المحلي نفسه ⇒ الهامش = ٠ «بالبناء»
                 #    مش بالقياس. محفوظ كسجل تاريخي + موسوم بوضوح.
                 "local_margin_pct_circular_by_construction": 0.0,
                 "internal_consistency_pct": 0.0,
                 "implied_egp_per_usd_from_market": 55.1198},
    "karats": {"14": {"sell_egp": 3860.0, "purity_over_24": 14 / 24.0},
               "18": {"sell_egp": 4962.75, "purity_over_24": 18 / 24.0},
               "21": {"sell_egp": 5790.0, "purity_over_24": 21 / 24.0}},
}

# ══════════════════════════════════════════════════════════════════════
#  ② القياس الجديد (الجولة ٢٥) — بمصادر مستقلة وتوقيت موثّق
#  التاريخ: 2026-11-19T00:16Z
# ══════════════════════════════════════════════════════════════════════
R25_MEASUREMENT = {
    "measured_at_utc": "2026-11-19T00:16:30Z",
    "sources": {
        "world_gold": {
            "provider": "Yahoo Finance / CME (COMEX)",
            "url": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
            "field": "chart.result[0].meta.regularMarketPrice",
            "value": 3738.8, "unit": "دولار لكل أونصة تروي (31.1035 جرام)",
            "karat": None, "source_timestamp": "2026-11-19T00:06:29+00:00",
            "independent_of_local_gold_price": True,
        },
        "fx": {
            "provider": "fxratesapi.com",
            "url": "https://api.fxratesapi.com/latest?base=USD&currencies=EGP",
            "field": "rates.EGP", "value": 53.7510072931,
            "unit": "جنيه مصري لكل دولار أمريكي", "karat": None,
            "source_timestamp": "2026-11-19T00:16:00+00:00",
            "independent_of_gold_price": True,
            "cross_checks": [
                {"provider": "exchangerate-api.com",
                 "url": "https://open.er-api.com/v6/latest/USD",
                 "field": "rates.EGP", "value": 53.794909,
                 "source_timestamp": "2026-11-19T00:02:31+00:00"},
                {"provider": "Yahoo Finance (EGP=X)",
                 "url": "https://query1.finance.yahoo.com/v8/finance/chart/EGP=X",
                 "field": "chart.result[0].meta.regularMarketPrice",
                 "value": 53.7,
                 "source_timestamp": "2026-11-18T21:26:09+00:00"},
            ],
            "dispersion_pct": 0.1767,
        },
        "local_gold": {
            "provider": "iSagha — مرجع سوق ذهب مصري",
            "url": "https://market.isagha.com/prices",
            "field": "سعر الجرام عيار ٢٤ (الكارت الرئيسي) + أسعار العيارات",
            "value_egp_per_gram": 6582.75,
            "unit": "جنيه مصري لكل جرام",
            "karat": "24 (مرجع) · 21/18/14 (بيع وشراء)",
            "source_timestamp": "2026-11-19T02:15:43+02:00",
            "independent_of_gold_price": True,
        },
        "local_fx_market": {
            "provider": "goldbullioneg — سوق الصياغة",
            "url": "https://goldbullioneg.com/",
            "field": "بطاقة «الدولار» (الرقم الظاهر + سعر البيع المذكور)",
            "value": 53.85, "sell_labeled": 53.75,
            "unit": "جنيه مصري لكل دولار أمريكي", "karat": None,
            "source_timestamp": None,
            "independent_of_gold_price": True,
        },
    },
    "series": {"date": "2026-11-17",
               "effective_close_utc": "2026-11-18T23:00:00+00:00",
               "age_minutes_at_measurement": 76.6,
               "xau_usd_per_oz": 3725.1,
               "egp_per_usd": 53.7,
               "gram_egp": 6431.3621},
    "measured": {
        "drift_pct": -2.2998,
        "gold_leg_pct": 0.3678,
        "fx_leg_pct": 0.0950,
        "local_premium_pct": 1.8821,
        "identity_error_ratio": 5.51e-09,
        "implied_egp_per_usd_from_local_price": 54.7626,
        "implied_fx_vs_official_pct": 1.8821,
        "local_premium_vs_market_fx_pct": 1.6948,
        "reading_spread_minutes": 9.52,
    },
}

# 📌 تاريخ الانحرافات المقاسة (كلها انحراف سوق حيّ — مش عيب كود):
#   · 2026-11-19 (الجولة ٢٥): −2.30٪
#   · 2026-11-18 (الجولة ٢٤): −2.52٪ · −2.59٪ · −2.56٪
#   · الجولة ٢٣: −3.18٪ · −2.57٪ · والـbase غير المعدَّل: −2.13٪
DRIFT_HISTORY_PCT = [-2.13, -2.30, -2.52, -2.56, -2.57, -2.59, -3.18]
CURRENT_TOLERANCE_PCT = 1.5      # ⛔ الحد المقبول — **ثابت** (المالك رفض رفعه)
FORBIDDEN_LIMIT_PCT = 5.0        # ⛔ الحد المرفوض صراحةً من المالك
# 📌 الحارس بيستخدم تعبير نمطي (مش نص حرفي) عشان ما يقعش في مرجع ذاتي
FIVE_PCT_RE = re.compile(r"\b[A-Z_]*TOLERANCE[A-Z_]*\s*=\s*5(\.0+)?\b")


def _read(name):
    with open(os.path.join(REPO, name), encoding="utf-8") as fh:
        return fh.read()


class GoldGateContract(unittest.TestCase):
    """① الفصل بين الحتمي والحيّ."""

    def test_deterministic_test_has_no_live_drift_gate(self):
        """⛔ مقارنة السعر الحيّ (الانحراف) مش في البوابة الحتمية.

        📌 البوابة الحتمية فيها **لمس حيّ اختياري**
        (نسب العيّارات من المصدر الحيّ) — لكنه `fail-soft` (مش بيكسر
        البوابة) و**مش** مقارنة انحراف.
        """
        det = _read("test_gold_integrity.py")
        live = _read("test_gold_live_price.py")
        # ⛔ حارس: مافيش **تعيين** حدّ انحراف ولا **مقارنة** انحراف في
        #    البوابة الحتمية (البوابة بتقرأ ملف الاختبار الحيّ بس عشان
        #    تتأكد إن السياسة نفسها ما اتغيّرتش — دي حارس سياسة مش بوابة).
        self.assertNotIn("TOLERANCE_PCT =", det,
                         "حدّ الانحراف دخل في البوابة الحتمية")
        self.assertNotIn("abs(drift)", det,
                         "مقارنة انحراف دخلت البوابة الحتمية")
        self.assertIn("TOLERANCE_PCT", live,
                      "حدّ الانحراف لازم يبقى في الاختبار الحيّ")
        # اللمس الحيّ الاختياري لازم يكون `fail-soft` (مش بيكسر البوابة)
        if "import gold_local as gl" in det:
            idx = det.index("import gold_local as gl")
            line_start = det.rfind("\n", 0, idx) + 1
            line_end = det.find("\n", idx)
            line = det[line_start:line_end if line_end > 0 else len(det)]
            self.assertTrue(line.startswith("    "),
                            "اللمس الحيّ في البوابة الحتمية لازم يكون جوّه try")
            self.assertIn("except Exception", det[idx:idx + 1200],
                          "اللمس الحيّ لازم يكون fail-soft")
            self.assertIn("import gold_local as gl", live,
                          "اللمس الحيّ لازم ينتقل لاختبار الحيّ")

    def test_live_test_is_gated_and_skips_with_zero_exit(self):
        """⛔ الاختبار الحيّ متخطّى افتراضياً وكود خروجه صفر (مش فشل)."""
        src = _read("test_gold_live_price.py")
        self.assertIn("OCTA_RUN_LIVE_TESTS", src,
                      "الاختبار الحيّ مش متحكم في البيئة")
        env = dict(os.environ)
        env.pop("OCTA_RUN_LIVE_TESTS", None)
        env["GOLD_HISTORY_PATH"] = "/tmp/_r24_gold_gate_contract.json"
        proc = subprocess.run([sys.executable, "test_gold_live_price.py"],
                              capture_output=True, text=True, timeout=120,
                              cwd=REPO, env=env)
        self.assertEqual(proc.returncode, 0,
                         "الاختبار الحيّ لازم يتخطّى بكود خروج 0")
        self.assertIn("متخطّى", proc.stdout or "",
                      "الاختبار الحيّ لازم يوضّح إنه متخطّى")

    def test_deterministic_tolerances_are_strict(self):
        """⛔ حدود البوابة الحتمية ما اترفعتش."""
        src = _read("test_gold_integrity.py")
        self.assertIn("abs(gap_pct) <= 0.5", src,
                      "حد الاتساق الداخلي للسلسلة اتغيّر")
        self.assertIn("-1 <= age_days <= 10", src,
                      "نافذة حداثة السلسلة اتغيّرت")

    # ── ② عزل سبب الانحراف (مصادر مستقلة) ───────────────────────────
    def test_series_internal_consistency_is_intact(self):
        """⛔ السلسلة نفسها سليمة: الجرام = ذهب × دولار ÷ 31.1035."""
        s = R25_MEASUREMENT["series"]
        recomputed = s["xau_usd_per_oz"] * s["egp_per_usd"] / T
        gap = abs(s["gram_egp"] / recomputed - 1) * 100
        self.assertLessEqual(gap, 0.5,
                             "الاتساق الداخلي للسلسلة اتكسر")

    def test_gram_unit_is_the_same_on_both_sides(self):
        """⛔ الوحدة مش سبب الانحراف: نسب العيّارات = النقاء ÷ 24 بالظبط."""
        gram = MEASUREMENT["live"]["gram_24_reference_egp"]
        for karat, row in MEASUREMENT["karats"].items():
            ratio = row["sell_egp"] / gram
            self.assertAlmostEqual(ratio, row["purity_over_24"], places=3,
                                   msg="عيار %s: نسبة غلط ⇒ اختلاف وحدة"
                                       % karat)

    def test_drift_decomposition_identity_holds(self):
        """⛔ الانحراف = ذهب × عملة × فرق تسعير محلي — بالهوية بالظبط."""
        m = R25_MEASUREMENT["measured"]
        ident = (1.0 / ((1 + m["gold_leg_pct"] / 100.0)
                        * (1 + m["fx_leg_pct"] / 100.0)
                        * (1 + m["local_premium_pct"] / 100.0)) - 1) * 100
        self.assertAlmostEqual(ident, m["drift_pct"], places=3,
                               msg="تفكيك الانحراف مش كامل")

    def test_local_pricing_gap_is_the_dominant_measured_leg(self):
        """⛔ الرجل الغالب في القياس المستقل = **فرق التسعير المحلي**.

        📌 ليش: رجل الذهب +٠٫٣٧٪ · رجل سعر الصرف **المنشور** +٠٫١٠٪
           ⇒ الفرق مش حركة ذهب ومش حركة سعر صرف منشور؛
           ده فرق **أساس التسعير** بين مرجع السلسلة (توازي رسمي)
           وسعر السوق المحلي.
        """
        m = R25_MEASUREMENT["measured"]
        self.assertGreater(abs(m["local_premium_pct"]), abs(m["gold_leg_pct"]),
                           "فرق التسعير المحلي مش هو الرجل الغالب")
        self.assertGreater(abs(m["local_premium_pct"]), abs(m["fx_leg_pct"]),
                           "فرق التسعير المحلي مش هو الرجل الغالب")
        self.assertLess(abs(m["fx_leg_pct"]), 0.5,
                        "سعر الصرف المنشور ما اتحركش ⇒ الوتر ده مش منه")

    def test_local_price_embeds_a_different_dollar_rate(self):
        """📌 توثيق: السعر المحلي فيه سعر دولار **مضمّن** مختلف.

        ⛔ وده **مش** تفسير مُثبت: يا إما هامش الصاغة/الدمغة/العمولة،
           يا إما سعر دولار موازٍ **غير مرصود** في قراءتنا.
           ⛔ المعلن هنا إن الفرق **موجود ومقاس**، لا إن سببه معروف.
        """
        m = R25_MEASUREMENT["measured"]
        implied = m["implied_egp_per_usd_from_local_price"]
        official = R25_MEASUREMENT["sources"]["fx"]["value"]
        self.assertGreater(implied, official,
                           "سعر الدولار المضمّن لازم يكون أعلى من المرجع")
        self.assertAlmostEqual((implied / official - 1) * 100,
                               m["implied_fx_vs_official_pct"], places=2)
        # ⛔ سعر الصرف المنشور في سوق الصياغة **أقل** بكتير من المضمّن
        #    ⇒ الفرق مش من سعر الصرف المنشور.
        self.assertLess(abs(m["local_premium_vs_market_fx_pct"]),
                        abs(m["local_premium_pct"]))

    def test_readings_are_independent_and_roughly_simultaneous(self):
        """⛔ القراءات التلاتة: مستقلة · موثّقة التوقيت · في نفس اللحظة."""
        src = R25_MEASUREMENT["sources"]
        self.assertTrue(src["world_gold"]["independent_of_local_gold_price"])
        self.assertTrue(src["fx"]["independent_of_gold_price"])
        self.assertTrue(src["local_gold"]["independent_of_gold_price"])
        for key in ("world_gold", "fx", "local_gold"):
            row = src[key]
            self.assertTrue(row.get("url"), "%s: لازم رابط" % key)
            self.assertTrue(row.get("field"), "%s: لازم حقل" % key)
            self.assertTrue(row.get("unit"), "%s: لازم وحدة" % key)
            self.assertTrue(row.get("source_timestamp"),
                            "%s: لازم وقت المصدر" % key)
        self.assertLessEqual(R25_MEASUREMENT["measured"]["reading_spread_minutes"],
                             180, "القراءات لازم تكون في نفس اللحظة تقريباً")

    def test_r24_circular_margin_is_marked_as_such(self):
        """⛔ سجل الجولة ٢٤: الهامش «صفر» كان **دائري بالبناء**."""
        self.assertIn("local_margin_pct_circular_by_construction",
                      MEASUREMENT["measured"])
        self.assertNotIn("local_margin_pct", MEASUREMENT["measured"])

    # ── ③ حدود القبول (سياسة المالك — الحد ما يتغيّرش) ───────────────
    def test_drift_limit_stays_at_one_and_half_percent(self):
        """⛔ الحد المقبول = ١٫٥٪ — والمالك رفض صراحةً رفعه لـ٥٪."""
        live = _read("test_gold_live_price.py")
        self.assertIn('MAX_TOLERANCE_PCT = 1.5', live,
                      "الحد الأعلى المسموح في الاختبار الحيّ اتغيّر")
        self.assertIn('TOLERANCE_PCT = min(_env_tol, MAX_TOLERANCE_PCT)', live,
                      "المتغير البيئي لازم يقدر يشدّ الحد بس ما يوسّعهوش")
        self.assertIsNone(FIVE_PCT_RE.search(live),
                          "مافيش حد ٥٪ في الاختبار الحيّ")
        det = _read("test_gold_integrity.py")
        self.assertIn("_five_pct_re", det,
                      "البوابة الحتمية لازم تحرس سياسة الحد (الحد ١٫٥٪)")
        self.assertIsNone(FIVE_PCT_RE.search(det),
                          "البوابة الحتمية ما فيهاش حد ٥٪ مطبَّق")

    def test_drift_history_exceeds_the_limit_and_is_structural(self):
        """📌 كل انحراف مقاس في التاريخ خارج الحد الحالي ١٫٥٪.

        ⛔ التفسير المسموح: انحراف **بنيوي** في طبقة التسعير (أساس
           التسعير مختلف بين مرجع السلسلة وسعر السوق المحلي) — مش عيب
           كود ومش حركة سعر منشور.
        ⚠️ توثيق فقط — **مافيش تغيير في السياسة** (الحد يفضل ١٫٥٪).
        """
        worst = max(abs(d) for d in DRIFT_HISTORY_PCT)
        self.assertGreater(worst, CURRENT_TOLERANCE_PCT,
                           "الحد الحالي كان كفاية ⇒ مفيش داعي للقرار")
        m = R25_MEASUREMENT["measured"]
        self.assertGreater(abs(m["local_premium_pct"]), CURRENT_TOLERANCE_PCT,
                           "فرق التسعير المحلي لوحده بيعدّي الحد ⇒ بنيوي")

    def test_forbidden_tolerance_is_not_used_anywhere(self):
        """⛔ مافيش حد ٥٪ مطبَّق في أي ملف ذهب."""
        for name in ("test_gold_live_price.py", "test_gold_integrity.py",
                     "gold_parity.py", "gold_premium.py"):
            src = _read(name)
            self.assertIsNone(FIVE_PCT_RE.search(src),
                              "مافيش حد ٥٪ في %s" % name)
        self.assertIsNone(FIVE_PCT_RE.search(
            _read("tools/test_round24_gold_gate_contract.py")),
            "مافيش حد ٥٪ في العقد")


if __name__ == "__main__":
    unittest.main(verbosity=2)
