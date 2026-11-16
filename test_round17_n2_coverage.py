#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٧ — R16-N2: **«تغطية مقبولة» ≠ «تغطية كاملة»**.

📌 **العيب (من مراجعة مستقلة)**:
   `coverage=90` و`requested=100` و`updated=90` ⇒ `missing=10`
   ⇒ بس الكود كان بيرجّع `coverage_status="complete"` والنصّ
   «التغطية كاملة» ⇒ **ادعاء كاذب** (في ١٠ صفوف ناقصة!).

⛔ **الإصلاح**:
   · `coverage_status` = complete ⇔ **مفيش سطر ناقص أصلاً** (١٠٠٪)
   · `coverage_acceptable` = التغطية فوق عتبة القبول (٩٠٪) — العتبة اتفضلت
   · النصّ: «التغطية كاملة» / «التغطية مقبولة (X٪)» / «التغطية جزئية (X٪)»

📌 **الاختبار السالب الإلزامي**: نفس الأرقام بالظبط على الكود القديم
   (٩٠٪ ⇒ complete + «التغطية كاملة») ⇒ الفشل لازم يكون على الـassertion.

📌 التشغيل: python test_round17_n2_coverage.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_n2_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402

NOW = "2026-11-17T10:00:00Z"
SESSION = "2026-11-17"


def _state(coverage, requested=100, updated=None, now=None):
    """حالة حداثة بتغطية محددة (آخر جلب ناجح = دلوقتي ⇒ fresh)."""
    now = now if now is not None else time.time()
    if updated is None and requested is not None and coverage is not None:
        updated = int(round(requested * float(coverage) / 100.0))
    return oe.freshness_state(now - 30, "open", now,
                              coverage=coverage,
                              requested=requested, updated=updated)


def _stock(code="AAA", **kw):
    d = {
        "code": code, "name": "سهم اختبار", "sector": "صناعة", "price": 50.0,
        "change": 1.2, "technical_score": 72.0, "technical_signal": "صاعد",
        "fund_score": 65.0, "liquidity_score": 70.0, "news_score": 55.0,
        "sentiment_score": 50.0, "safety_score": 64.0,
        "rsi": 52.0, "perf_1m": 6.0, "perf_3m": 14.0,
        "roe": 18.0, "net_margin": 12.0, "de_ratio": 35.0,
        "pe": 12.0, "pb": 1.4, "eps": 4.2, "div_yield": 6.0,
        "mkt_cap": 12e9, "rel_volume": 1.3, "volume": 900000,
        "vol_5": 880000, "vol_60": 850000,
        "beta": 0.9, "volatility": 28.0, "vol1y": 30.0, "mdd1y": -18.0,
        "cfo": 900.0, "ni": 700.0, "upside": 18.0, "fair_value": 59.0,
        "ts": NOW,
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


class TestN2CoverageHonesty(unittest.TestCase):
    """⛔ R16-N2 — التغطية المقبولة ماتتاخدش «كاملة»."""

    def test_90_percent_is_acceptable_not_complete(self):
        """⛔ السالب: ٩٠٪ من ١٠٠ ⇒ مقبولة، مش كاملة."""
        st = _state(90, requested=100, updated=90)
        self.assertEqual(st.get("missing"), 10)
        self.assertNotEqual(st.get("coverage_status"), "complete",
                            "⛔ ٩٠٪ اتسمّت كاملة مع وجود ١٠ صفوف ناقصة")
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertTrue(st.get("coverage_acceptable"),
                        "⛔ ٩٠٪ فوق عتبة القبول ⇒ لازم تكون مقبولة")

    def test_90_percent_text_is_not_complete(self):
        """⛔ النصّ الظاهر لازم يكون «مقبولة» مش «كاملة»."""
        st = _state(90, requested=100, updated=90)
        text = oe.freshness_summary_ar(st)
        self.assertIn("مقبولة", text, "⛔ النصّ ماقالش «مقبولة»: " + text)
        self.assertNotIn("كاملة", text, "⛔ النصّ قال «كاملة» وهي ناقصة: " + text)

    def test_89_9_percent_is_partial(self):
        """⛔ تحت العتبة ⇒ جزئية (مش مقبولة)."""
        st = _state(89.9, requested=1000, updated=899)
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertFalse(st.get("coverage_acceptable"),
                         "⛔ ٨٩.٩٪ اتقبلت مع إنها تحت العتبة")
        text = oe.freshness_summary_ar(st)
        self.assertIn("جزئية", text, "⛔ النصّ ماقالش «جزئية»: " + text)

    def test_99_9_percent_is_acceptable_not_complete(self):
        """⛔ ٩٩.٩٪ ⇒ مقبولة بس **مش كاملة**."""
        st = _state(99.9, requested=1000, updated=999)
        self.assertEqual(st.get("coverage_status"), "partial",
                         "⛔ ٩٩.٩٪ اتسمّت كاملة")
        self.assertTrue(st.get("coverage_acceptable"))
        text = oe.freshness_summary_ar(st)
        self.assertIn("مقبولة", text)
        self.assertNotIn("كاملة", text)

    def test_100_percent_is_complete(self):
        """⛔ مفيش ارتجاع: ١٠٠٪ ⇒ كاملة."""
        st = _state(100, requested=100, updated=100)
        self.assertEqual(st.get("coverage_status"), "complete")
        self.assertTrue(st.get("coverage_acceptable"))
        text = oe.freshness_summary_ar(st)
        self.assertIn("كاملة", text)

    def test_unavailable_when_no_coverage(self):
        """⛔ مافيش تغطية ⇒ غير متاحة (ومش «مقبولة»)."""
        st = _state(None, requested=None, updated=None)
        self.assertEqual(st.get("coverage_status"), "unavailable")
        self.assertFalse(st.get("coverage_acceptable"))

    def test_payload_publishes_coverage_acceptable(self):
        """⛔ العقد لازم ينشر «مقبولة» (المحرك + كل قائمة)."""
        now = time.time()
        fresh = oe.freshness_state(now - 30, "open", now,
                                   coverage=90, requested=100, updated=90)
        meta = {"generated_at": NOW, "source": "live", "market_phase": "open",
                "session_date": SESSION, "data_freshness": fresh}
        p = oe.build_payload([_stock()], None, meta)
        self.assertIn("coverage_acceptable", p,
                      "⛔ الـpayload م|Published «coverage_acceptable»")
        self.assertTrue(p.get("coverage_acceptable"))
        self.assertEqual(p.get("coverage_status"), "partial")
        for lst in (p.get("lists") or {}).values():
            self.assertIn("coverage_acceptable", lst,
                          "⛔ القائمة م|Published «coverage_acceptable»")
            self.assertTrue(lst.get("coverage_acceptable"))
        self.assertIn("مقبولة", p.get("freshness_summary_ar") or "")

    def test_source_label_distinguishes_complete(self):
        """⛔ مصدر البيانات: fresh+كاملة ⇒ live · fresh+مقبولة ⇒ partial."""
        self.assertEqual(oe.freshness_source(_state(100, 100, 100)), "live")
        self.assertEqual(oe.freshness_source(_state(90, 100, 90)), "partial")


if __name__ == "__main__":
    unittest.main(verbosity=2)
