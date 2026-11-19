#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 اختبارات ENGINE-SAFETY-01 — سلامة محرك التقييم (١٥ نوفمبر ٢٠٢٦).

⛔ العيوب المقاسة:
   F-20-05 ·Values None بتتكسّر في ضرب الأوزان ⇒ السهم بيضيع من
            التقييم كله (strategies + valuation + fair_value + upside).
   F-20-13 ·الثقة 0 بتتحوّل لـ60 ⇒ ثقة مزيفة + خصم متفرق.
   F-20-12 ·سيولة غير معروفة بتطلع 50 (نص الدرجة) + «مرتفع» + 0% ثقة.
   F-20-04 ·محور مخاطرة ناقص ⇒ +28.1 نقطة + «إشارة إيجابية» + ترتيب.

📌 التشغيل:  python3 test_engine_safety01.py
📌 مافيش شبكة · مافيش فلاس · استيراد آمن لـocta_score.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from octa_score import (  # noqa: E402
    final_score, liquidity_score, _compose_score, _confidence_value,
    build_sector_stats,
)


def _tech(score):
    return {"score": score, "signal": "اختبار"}


def _fund(score, **kw):
    d = {"score": score, "valuation_status": "مُسعَّر", "fair_value": 10.0,
         "upside_pct": 5.0}
    d.update(kw)
    return d


def _liq(score, risk_level="متوسط"):
    return {"score": score, "risk_level": risk_level, "confidence": 80.0}


class TestConfidence(unittest.TestCase):
    """F-20-13 — الثقة الحقيقية"""

    def test_zero_confidence_stays_zero(self):
        self.assertEqual(_confidence_value(0, 60.0), 0.0)
        self.assertEqual(_confidence_value(0.0, 60.0), 0.0)

    def test_missing_uses_documented_default(self):
        self.assertEqual(_confidence_value(None, 60.0), 60.0)
        self.assertEqual(_confidence_value("", 60.0), 60.0)

    def test_invalid_uses_default(self):
        self.assertEqual(_confidence_value("abc", 60.0), 60.0)

    def test_out_of_range_is_clamped(self):
        self.assertEqual(_confidence_value(150, 60.0), 100.0)
        self.assertEqual(_confidence_value(-20, 60.0), 0.0)

    def test_zero_confidence_reduces_score(self):
        """ثقة 0 لازم تأثر على الرقم (مش 60)"""
        item = {"code": "TEST", "price": 10.0, "beta": 0.9, "de_ratio": 40.0,
                "data_confidence": 0, "volatility": 30.0}
        ss = build_sector_stats([item])
        r60 = final_score(item, _tech(70), _fund(70), _liq(70), ss)
        item2 = dict(item)
        item2["data_confidence"] = 60
        r60b = final_score(item2, _tech(70), _fund(70), _liq(70), ss)
        self.assertIsNotNone(r60.get("final_score"))
        self.assertLess(r60["final_score"], r60b["final_score"],
                        "ثقة 0 لازم تنقص الدرجة أكتر من ثقة 60")


class TestLiquidityUnknown(unittest.TestCase):
    """F-20-12 — السيولة المجهولة ≠ السيولة الضعيفة"""

    def test_no_liquidity_metrics_returns_unknown(self):
        r = liquidity_score({"code": "X", "price": 10.0})
        self.assertIsNotNone(r, "المفروض نرجّع حالة «غير متاح» مش None")
        self.assertIsNone(r["score"], "درجة السيولة لازم تكون None مش رقم")
        self.assertEqual(r["score_status"], "insufficient_liquidity_data")
        self.assertEqual(r["risk_level"], "غير متاح")
        self.assertEqual(r["confidence"], 0.0)

    def test_zero_volume_is_real_low_liquidity(self):
        """صفر حجم = سيولة ضعيفة حقيقية (مش «ناقصة»)"""
        r = liquidity_score({"code": "X", "price": 10.0, "volume": 0,
                             "mkt_cap": 5e9, "rel_volume": 0.1,
                             "vol_5": 0, "vol_60": 0})
        self.assertIsNotNone(r["score"], "صفر الحجم لازم يطلع درجة ضعيفة")
        self.assertLess(r["score"], 40)
        self.assertNotEqual(r.get("score_status"), "insufficient_liquidity_data")

    def test_missing_liquidity_does_not_break_final_score(self):
        item = {"code": "X", "price": 10.0, "beta": 0.9, "de_ratio": 30.0,
                "volatility": 25.0}
        ss = build_sector_stats([item])
        r = final_score(item, _tech(70), _fund(70), None, ss)
        self.assertIsNotNone(r.get("final_score"))
        self.assertIsNone(r["axes"].get("liquidity"))


class TestRiskMissingPolicy(unittest.TestCase):
    """F-20-04 — سياسة نقص البيانات (الخيار A)"""

    def _item(self, risk_data=True):
        it = {"code": "X", "price": 10.0}
        if risk_data:
            it.update({"beta": 0.9, "de_ratio": 30.0, "volatility": 25.0})
        return it

    def test_missing_risk_has_no_positive_decision(self):
        ss = build_sector_stats([self._item(True)])
        r = final_score(self._item(False), _tech(80), _fund(80), _liq(80), ss)
        self.assertNotEqual(r["decision"], "إشارة إيجابية")
        self.assertEqual(r["decision"], "بيانات غير كافية")
        self.assertEqual(r["score_status"], "insufficient_risk")
        self.assertFalse(r["rank_eligible"])
        self.assertEqual(r["risk_level"], "غير متاح")

    def test_missing_risk_cannot_outrank_real_data(self):
        """نفس البيانات + محور مخاطرة ناقص ⇒ لازم يطلع أسوأ أو مساوي"""
        ss = build_sector_stats([self._item(True), self._item(False)])
        with_risk = final_score(self._item(True), _tech(80), _fund(80), _liq(80), ss)
        without = final_score(self._item(False), _tech(80), _fund(80), _liq(80), ss)
        self.assertLessEqual(without["final_score"], with_risk["final_score"],
                             "السهم الناقص، ما ينفعش ياخد نتيجة أعلى من السهم الكامل")

    def test_zero_risk_is_real_value_not_missing(self):
        """⛔ مخاطرة 0 = مخاطرة شديدة (مش نقص بيانات)"""
        it = self._item(True)
        ss = build_sector_stats([it])
        r = final_score(it, _tech(80), _fund(80), _liq(80), ss)
        self.assertEqual(r["score_status"], "ok")
        self.assertTrue(r["rank_eligible"])
        self.assertEqual(r["decision"], "إشارة سلبية")

    def test_valid_data_is_eligible(self):
        ss = build_sector_stats([self._item(True)])
        r = final_score(self._item(True), _tech(80), _fund(80), _liq(80), ss)
        self.assertEqual(r["score_status"], "ok")
        self.assertTrue(r["rank_eligible"])


class TestComposeScore(unittest.TestCase):
    def test_confidence_zero_penalty_applied(self):
        r0 = _compose_score({"technical": 70, "fundamental": 70, "liquidity": 70},
                            None, [], 0)
        r60 = _compose_score({"technical": 70, "fundamental": 70, "liquidity": 70},
                             None, [], 60)
        self.assertGreater(r0["conf_pen"], r60["conf_pen"])
        self.assertLess(r0["final"], r60["final"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
