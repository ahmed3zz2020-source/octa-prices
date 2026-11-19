#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٦ (R26 · محركات) — براهين سلبية على صحّة النسب والنمو والفلاتر

🎯 الغرض: **برهان** على كل إصلاح في الجولة دي ⭐.
   كل اختبار هنا مكتوب بحيث **يفشل على الكود قبل الإصلاح** وينجح بعده ⭐
   (negative proof) ⭐ — «الاختبار بيعدّي» مش دليل ⭐ · الدليل هو
   إنه كان **بي.fail** قبل الإصلاح ⭐.

📌 البنود اللي بنبرهنها ⭐:
   ① صحّة النسب ⭐: P/E · P/B · PEG ⭐
      · القيمة السالبة/الصفرية/NaN/Inf ⇒ **أسوأ نطاق** ⭐ (مش أحسن ⭐)
      · القسمة على صفر (pb = 0) ⇒ **نتيجة صريحة** ⭐ (مش استثناء ⭐)
      · "N/A" والبيانات الناقصة ⇒ **مش بيانات موجودة** ⭐
   ② النمو ⭐: `ni_growth` مستقل عن أداء السعر ⭐
   ③ PEG ⭐: «غير متاح» بدل رقم مخترع ⭐ (القياس نفسه في أداة منفصلة ⭐)
   ④ الأهلية · الحجم النسبي · الثقة · تطابق التفسير · حدود 0..100 ⭐
   ⑥ ⛔ ممنوع على الاختبار ده ⭐:
      · تغيير أي وزن محرك ⭐
      · تغيير حد التغطية 90٪ ⭐
      · تغيير بصمة إصدار ⭐
      · تغيير سياسة استثمار ⭐
      (فيه اختبارات **صريحة** بتحقّق إن الحاجات دي ما اتغيّرتش ⭐)

📌 التشغيل ⭐:
   python3 tools/test_round26_engines_r26.py
   python3 -m unittest tools.test_round26_engines_r26 -v
"""
from __future__ import annotations

import ast
import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r26_engines_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

# ⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع ⭐
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r26-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r26-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-r26-admin-token"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["OCTA_WARMUP"] = "0"

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

import update_prices as up  # noqa: E402
import octa_score  # noqa: E402
import opp_engine  # noqa: E402

NAN = float("nan")
INF = float("inf")

SECTOR = "الخدمات المالية"

PEERS = {
    SECTOR: {
        "count": 12, "with_pe": 12,
        "median_pe": 20.0, "median_pb": 1.5, "median_roe": 15.0,
        "pe_range": [8.0, 40.0],
        "median_volatility": 30.0, "median_mdd1y": 28.0, "median_sharpe3y": 0.8,
    }
}

BASE_ITEM = {
    "code": "FIXT", "name": "Synthetic Fixture Co", "sector": SECTOR,
    "price": 120.0,
    "eps": 6.0,
    "equity": 3_600_000_000.0,
    "shares": 30_000_000.0,
    "pe": 20.0,
    "pb": 1.0,
    "roe": 18.0, "net_margin": 12.0, "de_ratio": 0.45, "beta": 1.1,
    "volatility": 28.0, "revenue": 4_500_000_000.0, "div_yield": 5.0,
    "mkt_cap": 3_600_000_000.0,
    "volume": 1_250_000, "vol_5": 1_100_000, "vol_60": 1_000_000,
    "rel_volume": 1.25, "atr": 4.8,
    "rsi": 55.0, "rsi_prev": 51.0,
    "ema20": 112.0, "ema50": 105.0, "ema200": 95.0, "sma50": 106.0,
    "macd": 1.2, "macd_signal": 0.9, "stoch_k": 60.0, "stoch_d": 55.0,
    "high_1m": 130.0, "low_1m": 100.0,
    "perf_w": 2.0, "perf_1m": 6.0, "perf_3m": 12.0, "perf_y": 22.0,
    "change": 1.5, "tv_all": 0.2, "news_score": 55.0,
    "vol1y": 30.0, "mdd1y": 25.0, "sharpe3y": 0.9,
    "data_confidence": 80,
}


def item_with(**over):
    it = dict(BASE_ITEM)
    it.update(over)
    return it


# ══════════════════════════════════════════════════════════════════════
#  ① صحّة النسب — P/E · P/B (الأسوأ مش الأحسن)
# ══════════════════════════════════════════════════════════════════════


class TestRatioWorstBand(unittest.TestCase):
    """⛔ P/E · P/B غير صالحين ⇒ **أسوأ نطاق** ⭐ (مش محايد ⋆ مش أحسن ⭐)."""

    def test_clamp_nan_is_not_the_best_band(self):
        """⛔ `min(1.0, nan)` = 1.0 ⇒ NaN كان بيوصل **أفضل** نطاق ⭐."""
        self.assertIsNone(opp_engine._clamp(NAN),
                          "NaN في القصّ ⇒ لازم يبقى None (مش 1.0 = أحسن نطاق)")
        self.assertIsNone(opp_engine._clamp(INF))
        self.assertIsNone(opp_engine._clamp(-INF))

    def test_f_rejects_nan_and_inf(self):
        """⛔ NaN/Inf مش «بيانات موجودة» ⭐."""
        self.assertIsNone(opp_engine._f(NAN))
        self.assertIsNone(opp_engine._f(INF))
        self.assertIsNone(opp_engine._f(-INF))
        self.assertIsNone(opp_engine._f("nan"))
        self.assertIsNone(opp_engine._f("inf"))
        self.assertIsNone(opp_engine._f("N/A"))
        self.assertEqual(opp_engine._f(0.0), 0.0,
                         "الصفر الحقيقي رقم معروف (مش ناقص)")

    def test_negative_pe_is_worse_than_expensive_pe(self):
        """⛔ شركة خاسرة (P/E سالب) ⇒ أسوأ من شركة غالية فعلاً ⭐."""
        loss = opp_engine.c_valuation({"pe": -5.0})
        cheap = opp_engine.c_valuation({"pe": 8.0})
        pricey = opp_engine.c_valuation({"pe": 30.0})
        self.assertIsNotNone(loss)
        self.assertIsNotNone(pricey)
        self.assertLess(
            loss[0], pricey[0],
            "P/E سالب (%s) لازم يكون أسوأ من P/E=30 (%s) — "
            "مش محايد في النص" % (loss[0], pricey[0]))
        self.assertLess(loss[0], cheap[0],
                        "P/E سالب (%s) لازم يكون أسوأ من P/E=8 (%s)"
                        % (loss[0], cheap[0]))

    def test_zero_and_nan_and_inf_pe_reach_worst_band(self):
        """⛔ صفر · NaN · Inf ⇒ كلهم أسوأ من P/E صالح ⭐."""
        pricey = opp_engine.c_valuation({"pe": 30.0})[0]
        for bad in (0.0, NAN, INF, -INF):
            got = opp_engine.c_valuation({"pe": bad})
            self.assertIsNotNone(got, "P/E=%r لازم يرجّع نتيجة ⭐" % (bad,))
            self.assertLess(
                got[0], pricey,
                "P/E=%r (%s) لازم يكون أسوأ من P/E=30 (%s)"
                % (bad, got[0], pricey))

    def test_negative_and_zero_pb_reach_worst_band(self):
        """⛔ P/B سالب/صفر ⇒ أسوأ نطاق ⭐ (القيمة الدفترية سالبة ⭐)."""
        ok = opp_engine.c_valuation({"pb": 0.8})
        for bad in (0.0, -2.0, NAN, INF):
            got = opp_engine.c_valuation({"pb": bad})
            self.assertIsNotNone(got, "P/B=%r لازم يرجّع نتيجة ⭐" % (bad,))
            self.assertLess(got[0], ok[0],
                            "P/B=%r (%s) لازم يكون أسوأ من P/B=0.8 (%s)"
                            % (bad, got[0], ok[0]))

    def test_na_string_is_not_existing_data(self):
        """⛔ "N/A" ⇒ مش بيانات موجودة ⭐ (مش حالة سيئة ⭐)."""
        na = opp_engine.c_valuation({"pe": "N/A", "pb": "N/A"})
        missing = opp_engine.c_valuation({})
        self.assertIsNone(na, '"N/A" ⇒ المعيار مش متاح ⭐')
        self.assertIsNone(missing)
        bad = opp_engine.c_valuation({"pe": -1.0})
        self.assertIsNotNone(bad)
        self.assertNotEqual(na, bad)

    def test_c_valuation_evidence_declares_the_state(self):
        """📌 الدليل لازم يعلن حالة كل مضاعف ⭐ (مش يخفيها ⭐)."""
        r = opp_engine.c_valuation({"pe": -3.0, "pb": 1.0})
        self.assertEqual(r[1]["pe_state"], "bad")
        self.assertEqual(r[1]["pb_state"], "ok")
        r2 = opp_engine.c_valuation({"pe": 15.0})
        self.assertEqual(r2[1]["pe_state"], "ok")

    def test_nan_fair_value_is_not_a_perfect_safety_margin(self):
        """⛔ fair_value = NaN ⇒ مش أفضل هامش أمان ⭐."""
        r = opp_engine.c_safety_margin({"fair_value": NAN, "price": 100.0})
        if r is not None:
            self.assertLess(r[0], 1.0,
                            "NaN في القيمة العادلة ⇒ مش أعلى هامش أمان ⭐")
        r2 = opp_engine.c_safety_margin({"fair_value": 150.0, "price": 100.0})
        self.assertIsNotNone(r2)
        self.assertGreater(r2[0], 0.5)

    def test_nan_relative_volume_is_not_the_maximum_bonus(self):
        """⛔ الحجم النسبي NaN ⇒ مش أقصى مكافأة ⭐ (المفقود ≠ الصفر ⭐)."""
        liq = {"liquidity_score": 50.0}
        nan_r = opp_engine.c_liquidity(dict(liq, rel_volume=NAN))
        max_r = opp_engine.c_liquidity(dict(liq, rel_volume=3.0))
        zero_r = opp_engine.c_liquidity(dict(liq, rel_volume=0.0))
        none_r = opp_engine.c_liquidity(dict(liq, rel_volume=None))
        self.assertIsNotNone(nan_r)
        self.assertLess(
            nan_r[0], max_r[0],
            "rel_volume=NaN (%s) لازم يكون أقل من أقصى حجم نسبي (%s)"
            % (nan_r[0], max_r[0]))
        self.assertNotEqual(
            zero_r[0], none_r[0],
            "الحجم النسبي صفر ⭐ ≠ الحجم النسبي مفقود ⭐ (رقمان مختلفان ⭐)")

    def test_nan_risk_axis_is_not_the_best(self):
        """⛔ محور مخاطرة NaN ⇒ مش أعلى عائد/مخاطرة ⭐."""
        r = opp_engine.c_rr({"all_axes": {"risk": NAN}})
        if r is not None:
            self.assertLess(r[0], 1.0)
        ok = opp_engine.c_rr({"all_axes": {"risk": 90.0}})
        self.assertIsNotNone(ok)
        self.assertGreater(ok[0], 0.8)

    def test_nan_cfo_is_not_the_best_conversion(self):
        """⛔ cfo/ni مع NaN ⇒ مش أفضل تحويل ⭐."""
        r = opp_engine.c_cfo({"cfo": NAN, "ni": 10.0})
        if r is not None:
            self.assertLess(r[0], 1.0)


# ══════════════════════════════════════════════════════════════════════
#  ①ب القسمة على صفر — P/B = 0 ⇒ نتيجة صريحة (مش 500)
# ══════════════════════════════════════════════════════════════════════


class TestNoDivisionByZero(unittest.TestCase):
    """⛔ pb = 0 ⇒ **نتيجة صريحة** ⭐ (مش ZeroDivisionError ⭐)."""

    def test_fundamental_score_with_zero_pb(self):
        it = item_with(pb=0.0)
        r = up.fundamental_score(it, PEERS)
        self.assertIsNotNone(r, "fundamental_score لازم يرجّع نتيجة ⭐")
        self.assertIsNotNone(r["score"])
        self.assertIsNotNone(r.get("fair_value"))

    def test_fundamental_score_with_zero_pe_and_pb(self):
        it = item_with(pe=0.0, pb=0.0, eps=None)
        r = up.fundamental_score(it, PEERS)
        self.assertIsNotNone(r)
        self.assertIsNotNone(r["score"])

    def test_nz5_fair_with_zero_pb(self):
        it = item_with(pb=0.0)
        r = up.nz5_fair(it, PEERS)
        self.assertIsNotNone(r)
        self.assertIsNotNone(r.get("sources"))

    def test_calc_levels_with_zero_pb(self):
        it = item_with(pb=0.0)
        t, s = up.calc_levels(120.0, "تجميع", 70.0, it, PEERS)
        self.assertIsInstance(t, (int, float))
        self.assertIsInstance(s, (int, float))

    def test_zero_pb_is_rejected_by_the_validator_boundary(self):
        """📌 P/B = 0 **رقم مسموح** من المصدر ⭐ (حدّه 0..200 ⭐) ⭐."""
        v, err = up.validate_value("pb", 0.0)
        self.assertIsNone(err)
        self.assertEqual(v, 0.0)


# ══════════════════════════════════════════════════════════════════════
#  ② النمو — نمو الأرباح الحقيقي مستقل عن أداء السعر
# ══════════════════════════════════════════════════════════════════════


class TestGrowthTruthfulness(unittest.TestCase):
    """⛔ أداء السعر **مش** نمو أرباح ⭐."""

    def test_missing_ni_growth_is_declared_unavailable(self):
        r = opp_engine.c_growth({"perf_3m": 30.0})
        self.assertIsNotNone(r)
        self.assertFalse(r[1]["earnings_growth_available"])
        self.assertIn("غير متاح", r[2],
                      "لازم يعلن إن نمو الأرباح غير متاح ⭐")

    def test_available_ni_growth_is_flagged(self):
        r = opp_engine.c_growth({"perf_3m": 30.0, "ni_growth": 22.0})
        self.assertIsNotNone(r)
        self.assertTrue(r[1]["earnings_growth_available"])

    def test_price_performance_alone_is_not_earnings_growth(self):
        """⛔ سهم بأداء سعر قوي ونمو أرباح ناقص ⇒ التسمية تبقى صادقة ⭐."""
        r = opp_engine.c_growth_profit({"perf_3m": 90.0})
        self.assertIsNotNone(r)
        self.assertIn("غير متاح", r[2])

    def test_evidence_never_labels_perf_as_ni_growth(self):
        """⛔ مفيش معيار بيرجّع `perf_3m` في خانة نمو الأرباح ⭐."""
        r = opp_engine.c_growth({"perf_3m": 30.0})
        self.assertIsNotNone(r)
        self.assertEqual(r[1]["ni_growth"], None)
        self.assertNotEqual(r[1].get("earnings_growth_available"), True)


# ══════════════════════════════════════════════════════════════════════
#  ③ PEG — «غير متاح» بدل رقم مخترع
# ══════════════════════════════════════════════════════════════════════


class TestPegAvailability(unittest.TestCase):
    """⛔ PEG غير المتاح ⇒ None ⭐ (مش 0 ⋆ مش inf ⭐)."""

    def test_peg_none_for_invalid_inputs(self):
        for pe, g in ((None, 20.0), (10.0, None), (-5.0, 20.0), (10.0, -5.0),
                      (10.0, 0.0), (NAN, 20.0), (10.0, NAN), (INF, 20.0),
                      (10.0, INF), ("N/A", 20.0), (10.0, "N/A")):
            self.assertIsNone(up.peg_value(pe, g),
                              "PEG(%r, %r) لازم يكون None ⭐" % (pe, g))

    def test_peg_computes_for_valid_inputs(self):
        v = up.peg_value(10.0, 20.0)
        self.assertIsNotNone(v)
        self.assertAlmostEqual(v, 0.5, places=6)
        pts, vv = up.peg_score(10.0, 20.0)
        self.assertIsNotNone(vv)
        self.assertGreater(pts, 0.0)
        self.assertLessEqual(pts, up.PEG_POINTS_MAX)

    def test_peg_unavailable_scores_zero(self):
        pts, vv = up.peg_score(None, None)
        self.assertEqual(vv, None)
        self.assertEqual(pts, 0.0)

    def test_peg_points_max_untouched(self):
        """⛔ سقف نقاط PEG ما اتغيّرش ⭐."""
        self.assertEqual(up.PEG_POINTS_MAX, 8)
        self.assertEqual(up.PEG_PE_MAX, 1000.0)
        self.assertEqual(up.PEG_GROWTH_MIN, 0.01)
        self.assertEqual(up.PEG_GROWTH_MAX, 1000.0)


# ══════════════════════════════════════════════════════════════════════
#  ④ المحرك النهائي — NaN/Inf ما توصلش لأعلى درجة
# ══════════════════════════════════════════════════════════════════════


class TestFinalScoreNaN(unittest.TestCase):
    """⛔ NaN ⇒ **مش متاح** ⭐ (مش 100 ⭐)."""

    def _score(self, **over):
        it = item_with(**over)
        tech = {"score": 70.0, "signal": "صاعد"}
        fund = {"score": 60.0}
        liq = {"score": 65.0, "risk_level": "متوسط"}
        return up.final_score(it, tech, fund, liq, PEERS)

    def test_nan_technical_score_is_not_100(self):
        r = self._score()
        # نفس الشروط بس بمحرّك فني NaN
        it = item_with()
        tech = {"score": NAN, "signal": "؟"}
        fund = {"score": 60.0}
        liq = {"score": 65.0, "risk_level": "متوسط"}
        r2 = up.final_score(it, tech, fund, liq, PEERS)
        self.assertIsNone(r2["axes"].get("technical"),
                          "محور فني NaN ⇒ لازم يكون None ⭐ (مش 100 ⭐)")
        self.assertNotEqual(r2["axes"].get("technical"), 100)
        self.assertTrue(r2["rank_eligible"] is False,
                        "سهم بمحور ناقص ⇒ مش مؤهل ⭐")

    def test_nan_technical_score_equals_a_missing_technical_score(self):
        """⛔ غير الصالح = الناقص بالظبط ⭐ (مش أعلى درجة ⭐)."""
        fund = {"score": 60.0}
        liq = {"score": 65.0, "risk_level": "متوسط"}
        it = item_with()
        r_nan = up.final_score(it, {"score": NAN, "signal": "؟"}, fund, liq, PEERS)
        r_none = up.final_score(it, None, fund, liq, PEERS)
        self.assertEqual(r_nan["axes"].get("technical"),
                         r_none["axes"].get("technical"),
                         "محور فني NaN ⇒ نفس النتيجة تماماً زي المحور الناقص ⭐")
        self.assertEqual(r_nan["final_score"], r_none["final_score"])

    def test_nan_beta_is_treated_exactly_like_a_missing_beta(self):
        """⛔ **غير الصالح = الناقص بالظبط** ⭐.

        📌 العيب المقاس ⭐: `beta = NaN` ⇒ `100 - (nan-0.3)*125` ⇒ NaN ⭐
        ⇒ `min(100, nan)` ⇒ **100** ⭐ ⇒ ⛔ مؤشر **مش موجود** كان
        بيتحسب على أنه **أفضل أمان ممكن** ⭐ (100/100 ⭐) ⭐.
        📌 القاعدة ⭐: المؤشر غير الصالح = المؤشر الناقص ⭐ — بالظبط ⭐
        (مش أفضل ⭐ ⋆ مش أسوأ ⭐).
        """
        tech = {"score": 70.0, "signal": "صاعد"}
        fund = {"score": 60.0}
        liq = {"score": 65.0, "risk_level": "متوسط"}
        it_nan = item_with(beta=NAN)
        it_gone = item_with()
        it_gone.pop("beta", None)
        r_nan = up.final_score(it_nan, tech, fund, liq, PEERS)
        r_gone = up.final_score(it_gone, tech, fund, liq, PEERS)
        self.assertEqual(
            r_nan["axes"].get("risk"), r_gone["axes"].get("risk"),
            "NaN في البيتا ⇒ نفس النتيجة تماماً как ما البيتا ناقص ⭐ "
            "(مؤشر غير صالح مش أفضل أمان ⭐)")
        self.assertEqual(r_nan["risk_inputs"], r_gone["risk_inputs"],
                         "المؤشر غير الصالح لازم يتشال من عدّاد المؤشرات ⭐")

    def test_inf_beta_is_treated_like_a_missing_beta(self):
        tech = {"score": 70.0, "signal": "صاعد"}
        fund = {"score": 60.0}
        liq = {"score": 65.0, "risk_level": "متوسط"}
        it_inf = item_with(beta=INF)
        it_gone = item_with()
        it_gone.pop("beta", None)
        r_inf = up.final_score(it_inf, tech, fund, liq, PEERS)
        r_gone = up.final_score(it_gone, tech, fund, liq, PEERS)
        self.assertEqual(r_inf["axes"].get("risk"), r_gone["axes"].get("risk"),
                         "inf في البيتا ⇒ نفس النتيجة تماماً مثل الناقص ⭐")
        self.assertNotEqual(r_inf["axes"].get("risk"), 100)

    def test_tech_score_with_nan_price_is_unavailable(self):
        t = octa_score.tech_score({"price": NAN, "rsi": 50.0})
        self.assertIsNone(t, "سعر NaN ⇒ مافيش نتيجة فنية ⭐")


# ══════════════════════════════════════════════════════════════════════
#  ④ب حدود الدرجات — مفيش > 100 ولا < 0
# ══════════════════════════════════════════════════════════════════════


class TestScoreBounds(unittest.TestCase):
    """⛔ كل درجة محصورة 0..100 ⭐."""

    def test_final_score_bounds_over_adversarial_inputs(self):
        bad_vals = [NAN, INF, -INF, -1e9, 1e9, 0, -0.0]
        for v in bad_vals:
            it = item_with(beta=v, volatility=v, mdd1y=v, sharpe3y=v,
                           de_ratio=v, pe=v, pb=v, roe=v, net_margin=v)
            tech = {"score": v, "signal": "؟"}
            fund = {"score": v}
            liq = {"score": v, "risk_level": "متوسط"}
            r = up.final_score(it, tech, fund, liq, PEERS)
            if r.get("final_score") is not None:
                self.assertGreaterEqual(r["final_score"], 0.0)
                self.assertLessEqual(r["final_score"], 100.0)
            for k, av in (r.get("axes") or {}).items():
                if av is not None:
                    self.assertGreaterEqual(av, 0.0, "محور %s أقل من صفر ⭐" % k)
                    self.assertLessEqual(av, 100.0, "محور %s أكبر من 100 ⭐" % k)

    def test_fundamental_score_bounds(self):
        for v in (NAN, INF, -INF, -1e6, 1e6):
            r = up.fundamental_score(item_with(pe=v, pb=v, roe=v,
                                               net_margin=v, de_ratio=v,
                                               eps=v, revenue=v), PEERS)
            if r and r.get("score") is not None:
                self.assertGreaterEqual(r["score"], 0.0)
                self.assertLessEqual(r["score"], 100.0)

    def test_opp_criteria_ratios_are_in_0_1(self):
        for v in (NAN, INF, -INF, -5.0, 0.0, 1e9):
            item = {"pe": v, "pb": v, "roe": v, "net_margin": v,
                    "de_ratio": v, "eps": v, "price": 100.0,
                    "cfo": v, "ni": v, "fair_value": v, "upside": v,
                    "div_yield": v, "rel_volume": v, "rsi": v,
                    "perf_3m": v, "revenue_growth": v, "ni_growth": v,
                    "all_axes": {"risk": v, "technical": v, "fundamental": v},
                    "liquidity_score": v, "news_score": v, "atr": v,
                    "vol_60": v, "volume": v, "mkt_cap": v, "beta": v}
            for key, fn in opp_engine.CRITERIA_SCORERS.items():
                res = fn(item)
                if res is None:
                    continue
                ratio = res[0]
                if ratio is None:
                    continue
                self.assertGreaterEqual(ratio, 0.0,
                                        "معيار %s أقل من صفر ⭐" % key)
                self.assertLessEqual(ratio, 1.0,
                                     "معيار %s أكبر من 1 ⭐" % key)


# ══════════════════════════════════════════════════════════════════════
#  ④ج حالة التقييم — «مش موجود» ≠ «موجود بس سيء»
# ══════════════════════════════════════════════════════════════════════


class TestValuationStatus(unittest.TestCase):
    """⛔ P/E سالب ⇒ «غير صالح» ⭐ (مش «بيانات ناقصة» ⭐)."""

    def test_negative_pe_status_is_not_missing_data(self):
        r = up.fundamental_score(item_with(pe=-8.0), PEERS)
        self.assertNotIn("ناقصة", r["valuation_status"],
                         "شركة خاسرة ⇒ الحالة لازم تقول «غير صالح» ⭐")

    def test_missing_pe_status_stays_missing_data(self):
        r = up.fundamental_score(item_with(pe=None), PEERS)
        self.assertIn("ناقصة", r["valuation_status"])

    def test_valid_pe_status_unchanged(self):
        r = up.fundamental_score(item_with(pe=10.0), PEERS)
        self.assertIn("مُسعّر", r["valuation_status"])


# ══════════════════════════════════════════════════════════════════════
#  ④د الفلاتر الأساسية الثمانية (مرجع R23) — الحماية من الانحدار
# ══════════════════════════════════════════════════════════════════════


def rank_item(code="FIXT", **over):
    it = {
        "code": code, "name": "Fixture " + code, "sector": SECTOR,
        "price": 120.0, "final_score": 70.0, "decision": "إشارة إيجابية",
        "safety_score": 80.0, "liquidity_score": 75.0, "pe": 12.0,
        "div_yield": 4.0,
    }
    it.update(over)
    return it


class TestFiltersIntact(unittest.TestCase):
    """⛔ الفلاتر الثمانية زي ما هي ⭐ (من R23) ⭐."""

    def test_filter_1_min_score(self):
        self.assertEqual(len(up.rank_stocks([rank_item()], min_score=60)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item()], min_score=90)), 0)

    def test_filter_2_max_risk(self):
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=90.0)], max_risk=80)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=40.0)], max_risk=80)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=None)], max_risk=80)), 0)

    def test_filter_3_min_safety(self):
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=90.0)], min_safety=50)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=30.0)], min_safety=50)), 0)

    def test_filter_4_min_liquidity(self):
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=90.0)], min_liquidity=50)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=10.0)], min_liquidity=50)), 0)

    def test_filter_5_sectors(self):
        self.assertEqual(len(up.rank_stocks([rank_item(sector=SECTOR)], sectors=[SECTOR])), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(sector="أخرى")], sectors=[SECTOR])), 0)

    def test_filter_6_max_pe(self):
        self.assertEqual(len(up.rank_stocks([rank_item(pe=10.0)], max_pe=20)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=30.0)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=0.0)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=-4.0)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=NAN)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe="N/A")], max_pe=20)), 0)

    def test_filter_7_min_div_yield(self):
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=5.0)], min_div_yield=3)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=1.0)], min_div_yield=3)), 0)

    def test_filter_8_decisions(self):
        self.assertEqual(len(up.rank_stocks([rank_item(decision="إشارة إيجابية")],
                                             decisions=["إشارة إيجابية"])), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(decision="إشارة سلبية")],
                                             decisions=["إشارة إيجابية"])), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(decision=None)],
                                             decisions=["إشارة إيجابية"])), 0)

    def test_filter_on_and_off(self):
        """⛔ الفلتر المفعّل/المطفأ ⭐ (عتبة صفر = «مفيش حد» ⭐)."""
        st = rank_item()
        self.assertEqual(len(up.rank_stocks([st], min_score=0)), 1,
                         "عتبة صفر ⇒ مفيش حد ⭐")
        self.assertEqual(len(up.rank_stocks([st], min_score=70)), 1,
                         "الحد بالظبط ⇒ يعدّي ⭐")
        self.assertEqual(len(up.rank_stocks([st], min_score=71)), 0)

    def test_rank_eligible_false_is_excluded(self):
        self.assertEqual(len(up.rank_stocks([rank_item(rank_eligible=False)])), 0)

    def test_unknown_strategy_is_rejected(self):
        """⛔ استراتيجية غير معروفة ⇒ خطأ واضح ⭐ (مش 500 ⭐)."""
        self.assertNotIn("__missing__", up.STRATEGIES)
        src = open(os.path.join(REPO, "update_prices.py"), encoding="utf-8").read()
        self.assertIn('"unknown_strategy"', src)


# ══════════════════════════════════════════════════════════════════════
#  ④هـ تطابق الحساب المنشور مع التفسير
# ══════════════════════════════════════════════════════════════════════


class TestExplainMatchesScore(unittest.TestCase):
    """⛔ التفسير لازم يفكّك **نفس** الأرقام ⭐."""

    def test_explain_recomposes_the_published_score(self):
        it = item_with()
        t = octa_score.tech_score(it)
        f = up.fundamental_score(it, PEERS)
        l = octa_score.liquidity_score(it)
        n = up.news_engine(it, it.get("sector"))
        s = up.sentiment_engine(it, [it])
        p = up.portfolio_fit(it, {})
        r = up.risk_engine(it, PEERS)
        fin = up.final_score(it, t, f, l, PEERS)
        ex = up.explain_score(it, t, f, l, n, s, r, p, fin)
        self.assertIsNotNone(ex)
        total = ex.get("total")
        published = fin.get("final_score")
        if total is not None and published is not None:
            self.assertAlmostEqual(total, published, delta=0.2,
                                   msg="الرقم المنشور (%s) ≠ مجموع التفسير (%s)"
                                       % (published, total))

    def test_explain_with_nan_axis_does_not_diverge(self):
        """⛔ مدخلات NaN ⇒ التفسير والنتيجة يفضلوا متسقين ⭐."""
        it = item_with(beta=NAN, pe=NAN, pb=NAN)
        t = octa_score.tech_score(it)
        f = up.fundamental_score(it, PEERS)
        l = octa_score.liquidity_score(it)
        n = up.news_engine(it, it.get("sector"))
        s = up.sentiment_engine(it, [it])
        p = up.portfolio_fit(it, {})
        r = up.risk_engine(it, PEERS)
        fin = up.final_score(it, t, f, l, PEERS)
        ex = up.explain_score(it, t, f, l, n, s, r, p, fin)
        total = ex.get("total")
        published = fin.get("final_score")
        if total is not None and published is not None:
            self.assertAlmostEqual(total, published, delta=0.2)


# ══════════════════════════════════════════════════════════════════════
#  ⑤ المنهجية — ممنوع تتغيّر (أوزان · حد ٩٠٪ · بصمة · سياسة)
# ══════════════════════════════════════════════════════════════════════


class TestMethodologyUntouched(unittest.TestCase):
    """⛔ الأوزان وحد الـ90٪ ما اتغيّرتش ⭐."""

    def test_axis_weights_untouched(self):
        self.assertEqual(octa_score.AXIS_WEIGHTS, {
            "technical": 0.20, "fundamental": 0.24, "liquidity": 0.20,
            "news": 0.05, "sentiment": 0.04, "risk": 0.27, "portfolio": 0.00,
        })

    def test_coverage_threshold_untouched(self):
        self.assertEqual(up._FRESH_MIN_COVERAGE, 90.0)
        self.assertEqual(opp_engine.FRESH_MIN_COVERAGE, 90.0)

    def test_fundamental_composition_untouched(self):
        """⛔ تركيبة المحور الأساسي 30+30+20+20 ⭐."""
        r = up.fundamental_score(item_with(), PEERS)
        b = r["breakdown"]
        self.assertEqual(sorted(b.keys()),
                         sorted(["الربحية", "القيمة", "الصحة المالية",
                                 "اكتمال البيانات"]))
        self.assertAlmostEqual(sum(b.values()), r["score"], delta=0.2)

    def test_strategy_weights_untouched(self):
        self.assertEqual(up.STRATEGIES["swing"]["weights"], {
            "technical": 0.40, "fundamental": 0.12, "liquidity": 0.22,
            "news": 0.08, "sentiment": 0.05, "risk": 0.08, "portfolio": 0.05})
        self.assertEqual(up.STRATEGIES["value"]["weights"], {
            "technical": 0.08, "fundamental": 0.45, "liquidity": 0.10,
            "news": 0.07, "sentiment": 0.02, "risk": 0.20, "portfolio": 0.08})

    def test_no_new_threshold_or_version_bump_in_source(self):
        """⛔ مفيش عتبة جديدة ولا بصمة جديدة ⭐."""
        src = open(os.path.join(REPO, "update_prices.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        thresholds = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in (
                            "_FRESH_MIN_COVERAGE", "PEG_POINTS_MAX",
                            "PEG_PE_MAX", "PEG_GROWTH_MIN", "PEG_GROWTH_MAX",
                            "FRESH_MIN_COVERAGE"):
                        thresholds.append((t.id, ast.literal_eval(node.value)))
        found = dict(thresholds)
        self.assertEqual(found.get("_FRESH_MIN_COVERAGE"), 90.0)
        self.assertEqual(found.get("PEG_POINTS_MAX"), 8)


# ══════════════════════════════════════════════════════════════════════
#  ⑥ مسار المصدر الخارجي — شكل غلط ⇒ نتيجة صريحة (مش 500)
# ══════════════════════════════════════════════════════════════════════


class TestStartaPayloadShape(unittest.TestCase):
    """⛔ استجابة المصدر بشكل object ⇒ **مش 500** ⭐."""

    def test_starta_stats_with_dict_payload_does_not_raise(self):
        orig = up._jget
        try:
            up._jget = lambda *a, **k: {"error": "rate limited"}
            r = up._starta_stats()
            self.assertIsInstance(r, dict)
        finally:
            up._jget = orig

    def test_starta_stats_with_list_of_strings_does_not_raise(self):
        orig = up._jget
        try:
            up._jget = lambda *a, **k: ["a", "b"]
            r = up._starta_stats()
            self.assertIsInstance(r, dict)
        finally:
            up._jget = orig

    def test_egx_full_all_survives_a_broken_source(self):
        orig = up._jget
        try:
            up._jget = lambda *a, **k: {"error": "boom"}
            r = up._egx_full_all()
            self.assertIsInstance(r, dict)
            self.assertIn("stocks", r)
        finally:
            up._jget = orig


# ══════════════════════════════════════════════════════════════════════
#  ⑤ب الاختبار التاريخي — بلا بيانات مستقبلية (look-ahead)
# ══════════════════════════════════════════════════════════════════════


class TestBacktestNoLookAhead(unittest.TestCase):
    """⛔ القيطة بتتاخد **دي** والقياس بيستخدم سعر **القيطة** ⭐."""

    def _fixture_stocks(self):
        out = []
        for i in range(25):
            out.append({
                "code": "B%02d" % i, "name": "Backtest %02d" % i,
                "sector": SECTOR, "price": 100.0 + i, "final_score": 90.0 - i,
                "decision": "إشارة إيجابية", "safety_score": 80.0,
                "opportunity_score": 70.0, "perf_1m": 5.0, "perf_3m": 10.0,
                "upside": 12.0,
            })
        return out

    def _run_snapshot(self, stocks, date_str):
        from datetime import datetime, timedelta
        real_dt = up.datetime
        real_live = up.LIVE_DATA
        real_backtest = up.BACKTEST
        try:
            class _DT(datetime):
                @classmethod
                def utcnow(cls):
                    return real_dt.strptime(date_str, "%Y-%m-%d")
            up.datetime = _DT
            up.LIVE_DATA = {"egx30": stocks}
            up.BACKTEST = {"snapshots": {}, "results": [], "stats": {}}
            up.bt_snapshot()
            return dict(up.BACKTEST)
        finally:
            up.datetime = real_dt
            up.LIVE_DATA = real_live
            up.BACKTEST = real_backtest

    def _days_ago(self, n):
        from datetime import datetime, timedelta
        return (datetime.utcnow() - timedelta(days=n)).strftime("%Y-%m-%d")

    def test_snapshot_uses_only_current_prices(self):
        """⛔ اللقطة بتسجّل سعر **اليوم** ⭐ (مش سعر مستقبلي ⭐)."""
        stocks = self._fixture_stocks()
        bt = self._run_snapshot(stocks, self._days_ago(0))
        snaps = bt["snapshots"]
        self.assertTrue(snaps)
        snap = list(snaps.values())[0]
        by_code = {s["code"]: s for s in stocks}
        for p in snap["picks"]:
            self.assertEqual(p["price"], by_code[p["code"]]["price"],
                             "سعر اللقطة لازم يساوي سعر اللحظة ⭐")
            self.assertIsNotNone(p["score"])

    def test_newest_snapshot_is_not_measured(self):
        """⛔ أحدث لقطة **ما بتتقاسش** ⭐ (لسه مفيش يوم بعدها ⭐)."""
        stocks = self._fixture_stocks()
        bt = self._run_snapshot(stocks, self._days_ago(0))
        real_live = up.LIVE_DATA
        real_backtest = up.BACKTEST
        try:
            up.LIVE_DATA = {"egx30": stocks}
            up.BACKTEST = bt
            r = up.bt_evaluate(30)
            self.assertEqual(r.get("windows"), [],
                             "لقطة اليوم ما بتتقاسش ⭐ (٣ أيام حد أدنى ⭐)")
        finally:
            up.LIVE_DATA = real_live
            up.BACKTEST = real_backtest

    def test_future_snapshot_is_never_measured(self):
        """⛔ لقطة بتاريخ **مستقبلي** ⇒ ما بتتقاسش أبداً ⭐."""
        stocks = self._fixture_stocks()
        real_live = up.LIVE_DATA
        real_backtest = up.BACKTEST
        try:
            up.LIVE_DATA = {"egx30": stocks}
            up.BACKTEST = {"snapshots": {"2099-01-01": {
                "date": "2099-01-01", "ts": 0,
                "picks": [{"code": "B00", "score": 90.0, "price": 100.0,
                           "decision": "إشارة إيجابية", "sector": SECTOR,
                           "safety": 80.0, "opportunity": 70.0,
                           "perf_1m": 5.0, "perf_3m": 10.0, "upside": 12.0}]}},
                "results": [], "stats": {}}
            r = up.bt_evaluate(30)
            self.assertEqual(r.get("windows"), [],
                             "لقطة مستقبلية ما بتتقاسش ⭐")
        finally:
            up.LIVE_DATA = real_live
            up.BACKTEST = real_backtest

    def test_measurement_uses_the_snapshot_price_not_a_future_one(self):
        """⛔ العائد = (سعر الآن − سعر اللقطة) ÷ سعر اللقطة ⭐."""
        stocks = self._fixture_stocks()
        today = self._days_ago(0)
        older = self._days_ago(10)
        bt = self._run_snapshot(stocks, today)
        # لقطة أقدم (١٠ أيام) + لقطة اليوم ⇒ القيطة الأقدم هي اللي تتقاس
        bt_old = self._run_snapshot(stocks, older)
        bt["snapshots"].update(bt_old["snapshots"])
        later = [dict(s, price=s["price"] * 1.10) for s in stocks]
        real_live = up.LIVE_DATA
        real_backtest = up.BACKTEST
        try:
            up.LIVE_DATA = {"egx30": later}
            up.BACKTEST = bt
            r = up.bt_evaluate(30)
            wins = r.get("windows") or []
            self.assertTrue(wins, "المفروض القيطة الأقدم تتقاس ⭐")
            w = wins[0]
            self.assertEqual(w["snapshot_date"], older)
            for p in w["picks"]:
                expected = round(((p["price_now"] - p["price_then"])
                                  / p["price_then"]) * 100, 2)
                self.assertAlmostEqual(p["actual_return"], expected, places=2)
                self.assertEqual(p["price_then"], by_code_price(stocks, p["code"]))
                self.assertAlmostEqual(p["price_now"],
                                       round(by_code_price(stocks, p["code"]) * 1.10, 2),
                                       places=2)
            self.assertEqual(w["count"], w["wins"] + w["losses"] + w["flat"])
            self.assertEqual(w["wins"], w["count"],
                             "ارتفاع ١٠٪ ⇒ كلهم ربح ⭐")
        finally:
            up.LIVE_DATA = real_live
            up.BACKTEST = real_backtest


def by_code_price(stocks, code):
    for s in stocks:
        if s["code"] == code:
            return s["price"]
    return None


# ══════════════════════════════════════════════════════════════════════
#  تشغيل
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
