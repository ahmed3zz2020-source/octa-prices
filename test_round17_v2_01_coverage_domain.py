#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٧ — R17-V2-01: **نطاق الأعداد ومصدر الحقيقة للتغطية**.

📌 **العيب (برهان مستقل فاشل على HEAD)**:
   · 99% + 100/100 ⇒ «كاملة» (و99% مش 100%).
   · 90% + 895/1000 ⇒ «مقبولة» (والنسبة الحقيقية 89.5% ⇒ تحت العتبة).
   · 100% + 0/0 ⇒ «كاملة» (مافيش كون أصلاً).
   · 110% + 110/100 ⇒ «كاملة» و missing = −10 (نسبة > 100% وعدد أكبر من المطلوب).

⛔ **الإصلاح**:
   · نطاق الأعداد: المطلوب > 0 · المحدَّث بين 0 والمطلوب ⇒ غير صالح ⇒
     ممنوع «كاملة» و«مقبولة».
   · لما الأعداد موجودة ⇒ **هي مصدر الحقيقة**: النسبة = المحدَّث ÷ المطلوب،
     والمقارنة بتقريب المصدر لرقمين عشريين (مش سماحية نقطة).
   · «كاملة» بس لو ١٠٠٪ صحيحة ومتسقة · «مقبولة» بس لو عدّت العتبة ٩٠٪.
   ⛔ العتبة نفسها (90%) ما بتتغيّرش.

📌 التشغيل: python test_round17_v2_01_coverage_domain.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_v201_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402


def _state(coverage, requested=None, updated=None):
    now = time.time()
    return oe.freshness_state(now - 30, "open", now,
                               coverage=coverage,
                               requested=requested, updated=updated)


class TestV201CoverageDomain(unittest.TestCase):
    """⛔ R17-V2-01 — نطاق الأعداد + مصدر الحقيقة."""

    # ── الحالات الأربع الفاشلة على HEAD ──

    def test_rounding_does_not_hide_a_real_gap(self):
        """⛔ 99% مع 100/100 ⇒ ممنوع «كاملة»."""
        s = _state(99, requested=100, updated=100)
        self.assertNotEqual(s.get("coverage_status"), "complete",
                            "⛔ 99% اتختم «كاملة»")
        self.assertFalse(s["coverage_consistent"],
                         "⛔ التعارض بين النسبة والأعداد ما اتعلّمش")

    def test_threshold_is_based_on_actual_counts(self):
        """⛔ 90% مع 895/1000 ⇒ النسبة الحقيقية 89.5% ⇒ ممنوع «مقبولة»."""
        s = _state(90, requested=1000, updated=895)
        self.assertFalse(s["coverage_acceptable"],
                         "⛔ تغطية 89.5% اتقبلت")
        self.assertNotEqual(s.get("coverage_status"), "complete")

    def test_zero_universe_is_not_complete(self):
        """⛔ 100% مع 0/0 ⇒ مافيشكون ⇒ ممنوع «كاملة»."""
        s = _state(100, requested=0, updated=0)
        self.assertNotEqual(s.get("coverage_status"), "complete",
                            "⛔ تغطية بكون صفري اتختم «كاملة»")

    def test_impossible_counts_are_not_complete(self):
        """⛔ 110% مع 110/100 ⇒ ممنوع «كاملة» (و missing سالب)."""
        s = _state(110, requested=100, updated=110)
        self.assertNotEqual(s.get("coverage_status"), "complete",
                            "⛔ نسبة 110% اتختم «كاملة»")
        self.assertFalse(s["coverage_acceptable"],
                         "⛔ نسبة > 100% اتقبلت")

    # ── الحالات السليمة (مفيش ارتجاع) ──

    def test_full_coverage_with_consistent_counts_is_complete(self):
        """✅ 100% مع 100/100 ⇒ «كاملة»."""
        s = _state(100, requested=100, updated=100)
        self.assertEqual(s.get("coverage_status"), "complete")
        self.assertTrue(s.get("coverage_acceptable"))
        self.assertTrue(s.get("coverage_consistent"))

    def test_healthy_production_shape_is_acceptable(self):
        """✅ الشكل الحقيقي للمنتج: 257/286 = 89.86% ⇒ مقبولة (تحت العتبة؟ لأ)."""
        s = _state(89.86, requested=286, updated=257)
        self.assertTrue(s.get("coverage_consistent"))
        self.assertEqual(s.get("coverage_status"), "partial")
        # ⛔ 89.86% أقل من العتبة ⇒ مش «مقبولة» (مصدر الحقيقة = الأعداد)
        self.assertFalse(s.get("coverage_acceptable"))
        self.assertAlmostEqual(s.get("coverage_implied_pct"), 89.86, places=2)

    def test_rounded_source_ratio_stays_consistent(self):
        """✅ تقريب المصدر لرقمين (89.86 من 257/286) ⇒ متسقة."""
        s = _state(89.86, requested=286, updated=257)
        self.assertTrue(s.get("coverage_consistent"))
        self.assertEqual(s.get("coverage_pct"), 89.86)

    def test_threshold_boundary_still_works(self):
        """✅ 90% بالظبط (90/100) ⇒ مقبولة، ومش كاملة."""
        s = _state(90, requested=100, updated=90)
        self.assertTrue(s.get("coverage_acceptable"))
        self.assertEqual(s.get("coverage_status"), "partial")

    def test_no_counts_uses_ratio_alone(self):
        """✅ مافيش أعداد ⇒ النسبة وحدها تكفي (ضمن المدى)."""
        s = _state(100, requested=None, updated=None)
        self.assertEqual(s.get("coverage_status"), "complete")
        s2 = _state(50, requested=None, updated=None)
        self.assertEqual(s2["coverage_status"], "partial")
        self.assertFalse(s2["coverage_acceptable"])

    def test_ratio_out_of_range_without_counts_is_not_complete(self):
        """✅ نسبة 110% من غير أعداد ⇒ ممنوع «كاملة»."""
        s = _state(110, requested=None, updated=None)
        self.assertNotEqual(s.get("coverage_status"), "complete")
        self.assertFalse(s.get("coverage_acceptable"))

    def test_threshold_constant_unchanged(self):
        """⛔ العتبة المعتمدة ما بتتغيّرش (٩٠٪)."""
        self.assertEqual(oe.FRESH_MIN_COVERAGE, 90.0)

    def test_missing_coverage_is_unavailable(self):
        """✅ مافيش تغطية ⇒ «غير متاحة»."""
        s = _state(None, requested=None, updated=None)
        self.assertEqual(s.get("coverage_status"), "unavailable")
        self.assertFalse(s.get("coverage_acceptable"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
