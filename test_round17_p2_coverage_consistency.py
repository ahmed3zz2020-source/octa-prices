#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٧ — R17-P2: **اتساق مدخلات التغطية قبل التصنيف**.

📌 **العيب (من المراجعة النهائية)**:
   `coverage=90` و`requested=100` و`updated=100` ⇒ `missing = 0`
   ⇒ `coverage_status="complete"` ⇒ **ادعاء كاذب**: النسبة ٩٠٪ بتقول
   إن ١٠ صفوف ناقصة، والأعداد بتقول إن مفيش ناقص.

⛔ **الإصلاح**:
   · قبل التصنيف: نتأكد إن النسبة **متسقة** مع (المطلوب · المحدَّث).
   · تناقض ⇒ ممنوع «كاملة» في أي حال + `coverage_consistent=False`.
   · حقول جديدة: `coverage_consistent` · `coverage_implied_pct`.

📌 **الاختبار السالب الإلزامي**: أعداد متعارضة + ٠٪ + ٩٠٪ + ١٠٠٪ + تقريب النسب.

📌 التشغيل: python test_round17_p2_coverage_consistency.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_p2_tmp_%d" % os.getpid())
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


class TestP2CoverageConsistency(unittest.TestCase):
    """⛔ R17-P2 — التصنيف لازم يكون متسق مع الأرقام."""

    def test_contradictory_counts_are_not_complete(self):
        """⛔ السالب: ٩٠٪ مع ١٠٠/١٠٠ ⇒ ممنوع «كاملة»."""
        st = _state(90, requested=100, updated=100)
        self.assertNotEqual(st.get("coverage_status"), "complete",
                            "⛔ تناقض الأرقام اتختم «كاملة»")
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertFalse(st.get("coverage_consistent"),
                         "⛔ التناقض ما اتعلّمش")
        self.assertFalse(st.get("coverage_acceptable"),
                         "⛔ تغطية متناقضة ما ينفعش تتقبل")

    def test_contradictory_counts_visible_in_text(self):
        """⛔ النصّ لازم Says التناقض."""
        st = _state(90, requested=100, updated=100)
        text = oe.freshness_summary_ar(st)
        self.assertIn("غير متسقة", text,
                      "⛔ النصّ ماقالاش إن الأرقام غير متسقة: " + text)
        self.assertNotIn("كاملة", text)

    def test_zero_percent_is_partial(self):
        """⛔ ٠٪ ⇒ جزئية (ومفيش «كاملة»)."""
        st = _state(0, requested=100, updated=0)
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertFalse(st.get("coverage_acceptable"))
        self.assertEqual(st.get("missing"), 100)

    def test_90_percent_consistent_is_acceptable_not_complete(self):
        """⛔ ٩٠٪ متسقة (١٠٠/٩٠) ⇒ مقبولة مش كاملة."""
        st = _state(90, requested=100, updated=90)
        self.assertTrue(st.get("coverage_consistent"))
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertTrue(st.get("coverage_acceptable"))
        text = oe.freshness_summary_ar(st)
        self.assertIn("مقبولة", text)
        self.assertNotIn("كاملة", text)

    def test_100_percent_consistent_is_complete(self):
        """⛔ ١٠٠٪ متسقة ⇒ كاملة."""
        st = _state(100, requested=100, updated=100)
        self.assertTrue(st.get("coverage_consistent"))
        self.assertEqual(st.get("coverage_status"), "complete")
        self.assertTrue(st.get("coverage_acceptable"))

    def test_rounded_percentages_are_tolerated(self):
        """⛔ تقريب النسب (33.33% من 3/1 · 89.86% من 257/286) ⇒ متسقة."""
        cases = [
            (33.33, 3, 1),
            (89.86, 286, 257),
            (1.05, 286, 3),
            (32.33, 300, 97),
        ]
        for cov, req, upd in cases:
            st = _state(cov, requested=req, updated=upd)
            self.assertTrue(st.get("coverage_consistent"),
                            "⛔ تقريب النسبة اتحسب متناقض: %s" % (cov,))
            self.assertNotEqual(st.get("coverage_status"), "complete",
                                "⛔ نسبة أقل من ١٠٠ اتختم «كاملة»: %s" % (cov,))

    def test_no_counts_uses_percentage_only(self):
        """⛔ مافيش أعداد ⇒ النسبة وحدها تكفي."""
        st = _state(100, requested=None, updated=None)
        self.assertEqual(st.get("coverage_status"), "complete")
        st2 = _state(50, requested=None, updated=None)
        self.assertEqual(st2.get("coverage_status"), "partial")

    def test_implied_percentage_is_published(self):
        """⛔ العقد ينشر النسبة المستنتجة من الأعداد."""
        st = _state(90, requested=100, updated=90)
        self.assertEqual(st.get("coverage_implied_pct"), 90.0)
        st2 = _state(89.86, requested=286, updated=257)
        self.assertAlmostEqual(st2.get("coverage_implied_pct"), 89.86, places=2)

    def test_unavailable_when_no_coverage(self):
        """⛔ مافيش تغطية ⇒ غير متاحة."""
        st = _state(None, requested=None, updated=None)
        self.assertEqual(st.get("coverage_status"), "unavailable")
        self.assertFalse(st.get("coverage_acceptable"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
