#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٤ (R24 · المرحلة ٥) — عقد بوابة الذهب: الفصل + عزل سبب الانحراف

🎯 الغرض: عقد **حتمي** (من غير شبكة) يثبت:
   ① البوابة الحتمية (سلامة السلسلة) **مفصولة** عن السعر الحيّ
   ② الاختبار الحيّ **متخطّى افتراضياً** وكود خروجه صفر
   ③ حدود البوابة الحتمية **صارمة** (اتساق داخلي ≤ 0.5٪ · حداثة ≤ 10 أيام)
   ④ سبب انحراف السعر الحيّ **مفصول بالقياس** (عملة · ذهب · هامش)
      وأن الوحدة **مش** سبب الانحراف

📌 القياس المسجَّل تحت (مرجع حقيقي — وقت ومصدر كل رقم):
   · سلسلة الذهب: `TradingView` (`FX_IDC:XAUUSD` + `FX_IDC:USDEGP`)
   · السعر الحيّ: `iSagha` — مرجع سوق ذهب مصري
   القياس الكامل (مع البرهان السالب) بتتولّاه الأداة:
       python3 tools/r24_gold_drift_isolation.py

📌 التشغيل:
   python3 tools/test_round24_gold_gate_contract.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

T = 31.1035

# ══════════════════════════════════════════════════════════════════════
#  القياس المسجَّل (مرجع حقيقي — كل رقم بمصدره ووقته)
#  التاريخ: 2026-11-18 · مصدر السلسلة: TradingView · مصدر الحيّ: iSagha
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
                 "local_margin_pct": 0.0,
                 "internal_consistency_pct": 0.0,
                 "implied_egp_per_usd_from_market": 55.1198},
    "karats": {"14": {"sell_egp": 3860.0, "purity_over_24": 14 / 24.0},
               "18": {"sell_egp": 4962.75, "purity_over_24": 18 / 24.0},
               "21": {"sell_egp": 5790.0, "purity_over_24": 21 / 24.0}},
}

# 📌 تاريخ الانحرافات المقاسة (كلها انحراف سوق حيّ — مش عيب كود):
#   · 2026-11-18 (الجولة ٢٤): −2.52٪ · −2.59٪ · −2.56٪
#   · الجولة ٢٣: −3.18٪ · −2.57٪ · والـbase غير المعدَّل: −2.13٪
DRIFT_HISTORY_PCT = [-2.13, -2.52, -2.56, -2.57, -2.59, -3.18]
CURRENT_TOLERANCE_PCT = 1.5      # الحد الحالي في اختبار السعر الحيّ
PROPOSED_TOLERANCE_PCT = 5.0     # الحد المقترح (بالمستند المرجعي ده)


def _read(name):
    with open(os.path.join(REPO, name), encoding="utf-8") as fh:
        return fh.read()


class GoldGateContract(unittest.TestCase):
    """① الفصل بين الحتمي والحيّ."""

    def test_deterministic_test_has_no_live_drift_gate(self):
        """⛔ مقارنة السعر الحيّ (الانحراف) مش في البوابة الحتمية.

        📌 ملاحظة: البوابة الحتمية فيها **لمس حيّ اختياري**
        (نسب العيّارات من المصدر الحيّ) — لكنه `fail-soft` (مش بيكسر
        البوابة) و**مش** مقارنة انحراف. الفصل المزدوج مسجّل كاقتراح
        في أدلة الجولة ٢٤ (نقل اللمس الحيّ كله لاختبار الحيّ).
        """
        det = _read("test_gold_integrity.py")
        live = _read("test_gold_live_price.py")
        self.assertNotIn("TOLERANCE_PCT", det,
                         "حدّ الانحراف دخل في البوابة الحتمية")
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

    # ── ② عزل سبب الانحراف ───────────────────────────────────────────
    def test_series_internal_consistency_is_intact(self):
        """⛔ السلسلة نفسها سليمة: الجرام = ذهب × دولار ÷ 31.1035."""
        s = MEASUREMENT["series"]
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
        """⛔ الانحراف = ذهب × دولار × هامش — بالهوية بالظبط."""
        m = MEASUREMENT["measured"]
        ident = (1.0 / ((1 + m["gold_leg_pct"] / 100.0)
                        * (1 + m["fx_leg_pct"] / 100.0)
                        * (1 + m["local_margin_pct"] / 100.0)) - 1) * 100
        self.assertAlmostEqual(ident, m["drift_pct"], places=3,
                               msg="تفكيك الانحراف مش كامل")

    def test_currency_layer_is_the_dominant_cause(self):
        """⛔ السبب = **زوج العملة** (سعر السوق المحلي مقابل الرسمي).

        📌 ليش مش تاريخ ولسه مش وحدة:
           · رجل الذهب ≈ صفر (−0.016٪) ⇒ الوقت ما سببش فرق.
           · الهامش المحلي = 0.0000٪ ⇒ مافيش هامش صاغة/عمولة.
           · رجل العملة = +2.644٪ ⇒ الفرق كله في سعر الدولار.
        """
        m = MEASUREMENT["measured"]
        self.assertGreater(abs(m["fx_leg_pct"]), 1.5,
                           "رجل العملة مش مسيطر ⇒ خلاصة مختلفة")
        self.assertGreater(abs(m["fx_leg_pct"]),
                           5 * max(abs(m["gold_leg_pct"]), 0.001),
                           "رجل العملة مش مسيطر على رجل الذهب")
        self.assertAlmostEqual(m["local_margin_pct"], 0.0, places=3)

    def test_implied_parallel_rate_is_above_the_official_rate(self):
        """📌 مرجع: سعر الدولار الضمني من السوق المحلي أعلى من الرسمي."""
        m = MEASUREMENT["measured"]
        official = MEASUREMENT["series"]["egp_per_usd"]
        implied = m["implied_egp_per_usd_from_market"]
        self.assertGreater(implied, official,
                           "الدولار الضمني لازم يكون أعلى من الرسمي")
        self.assertAlmostEqual((implied / official - 1) * 100,
                               m["fx_leg_pct"], places=2)

    # ── ③ حدود القبول (مرجع للقرار) ───────────────────────────────────
    def test_current_tolerance_is_too_tight_for_the_measured_market(self):
        """📌 كل انحراف مقاس في التاريخ خارج الحد الحالي 1.5٪ ⇒ الحد
        الحالي بيفشل على حركة سوق طبيعية (مش عيب كود).

        ⚠️ توثيق فقط — **مافيش تغيير في السياسة** (الحد المقترح 5٪
        مسجّل كاقتراح موثّق للمالك في أدلة الجولة ٢٤).
        """
        worst = max(abs(d) for d in DRIFT_HISTORY_PCT)
        self.assertGreater(worst, CURRENT_TOLERANCE_PCT,
                           "الحد الحالي كان كفاية ⇒ مافيش داعي للاقتراح")
        self.assertLess(worst, PROPOSED_TOLERANCE_PCT,
                        "الحد المقترح لازم يغطي كل الانحرافات المقاسة")


if __name__ == "__main__":
    unittest.main(verbosity=2)
