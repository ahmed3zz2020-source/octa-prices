#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٧ — R16-N4: **شرط الجلسة** في وصف السعر.

📌 **العيب (من مراجعة مستقلة)**:
   `price_label_for()` كانت بتختم «سعر التداول الآن» لو:
      · السوق مفتوح · عمر السعر حديث · و**جلسة السعر مختلفة** أو **ناقصة**
   ⇒ ولو تاريخ الجلسة الحالية مش موجود ⇒ مفيش دليل على ان السعر من
   الجلسة الحالية ⇒ **ادعاء لحظي بدون دليل**.

⛔ **الإصلاح**: «الآن» محتاج **تلات** أدلة:
   ① السوق مفتوح · ② عمر السعر معروف وحديث · ③ تاريخ الجلسة الحالية
   **موجود** + تاريخ جلسة السعر **موجود** + **متساويين**.

📌 **الاختبار السالب الإلزامي**: نفس المدخلات بالظبط بس من غير تاريخ
   الجلسة الحالية ⇒ الفشل على الكود القديم لازم يكون على الـassertion.

📌 التشغيل: python test_round17_n4_session_match.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_n4_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402

NOW = "2026-11-17T10:00:00Z"
SESSION = "2026-11-17"
PREV = "2026-11-16"
NOW_LABEL = "سعر التداول الآن"
KNOWN_LABEL = "آخر سعر معروف"


class TestN4SessionRequired(unittest.TestCase):
    """⛔ R16-N4 — «الآن» لازم يكون فيها دليل جلسات."""

    def _label(self, **kw):
        args = {
            "market_phase": "open",
            "stale": False,
            "price_time_source": "source",
            "price_age_seconds": 120,      # عمر حديث (دقيقتين)
            "price_session_date": SESSION,
            "session_date": SESSION,
        }
        args.update(kw)
        return oe.price_label_for(**args)

    def test_missing_current_session_is_not_now(self):
        """⛔ السالب: مافيش تاريخ الجلسة الحالية ⇒ ممنوع «الآن»."""
        out = self._label(session_date=None)
        self.assertNotEqual(out, NOW_LABEL,
                            "⛔ اتسم «الآن» من غير دليل على الجلسة الحالية")
        self.assertEqual(out, KNOWN_LABEL)

    def test_missing_price_session_is_not_now(self):
        """⛔ السالب: مافيش تاريخ جلسة السعر ⇒ ممنوع «الآن»."""
        out = self._label(price_session_date=None)
        self.assertNotEqual(out, NOW_LABEL,
                            "⛔ اتسم «الآن» من غير دليل على جلسة السعر")
        self.assertEqual(out, KNOWN_LABEL)

    def test_both_sessions_missing_is_not_now(self):
        """⛔ السالب: مافيش أي تاريخ ⇒ ممنوع «الآن»."""
        out = self._label(price_session_date=None, session_date=None)
        self.assertNotEqual(out, NOW_LABEL)
        self.assertEqual(out, KNOWN_LABEL)

    def test_same_session_still_now(self):
        """⛔ مفيش ارتجاع: نفس الجلسة + عمر حديث ⇒ «الآن»."""
        out = self._label()
        self.assertEqual(out, NOW_LABEL,
                         "⛔ نفس الجلسة اتمنعت ⇒ ارتجاع في السلوك الصحيح")

    def test_different_session_is_known_price(self):
        """⛔ مفيش ارتجاع: جلسة مختلفة ⇒ «آخر سعر معروف»."""
        out = self._label(price_session_date=PREV)
        self.assertEqual(out, KNOWN_LABEL)
        self.assertNotEqual(out, NOW_LABEL)

    def test_old_price_with_same_session_is_known_price(self):
        """⛔ مفيش ارتجاع: عمر قديم ⇒ «آخر سعر معروف»."""
        out = self._label(price_age_seconds=3600)
        self.assertEqual(out, KNOWN_LABEL)

    def test_no_timestamp_is_last_available(self):
        """⛔ مفيش ارتجاع: مافيش توقيت ⇒ «آخر سعر متاح»."""
        out = self._label(price_age_seconds=None)
        self.assertEqual(out, "آخر سعر متاح")
        self.assertNotEqual(out, NOW_LABEL)

    def test_stale_wins_over_everything(self):
        """⛔ مفيش ارتجاع: الكاش يسبق كل حاجة."""
        out = self._label(stale=True)
        self.assertEqual(out, KNOWN_LABEL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
