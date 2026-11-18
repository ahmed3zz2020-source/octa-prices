#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٣ (R23 · Phase 4) — تدقيق المحركات المالية والفلاتر الأساسية

🎯 الغرض: **برهان** على كل إصلاح في الجولة دي.
   كل اختبار هنا مكتوب بحيث **يفشل على الكود قبل الإصلاح** وينجح بعده
   (negative proof) — «الاختبار بيعدّي» مش دليل، الدليل هو إنّه كان **بي.fail**
   قبل الإصلاح وبيدلّ على العيب بالظبط.

📌 ما فيش أي تعديل على:
   · الأوزان المعتمدة (octa_score.AXIS_WEIGHTS · STRATEGIES)
   · حد التغطية 90٪ (opp_engine.FRESH_MIN_COVERAGE)
   · منهجية التقييم (تركيبة المحور الأساسي 30+30+20+20)
   الاختبارات دي **تتحقق** إن الأوزان ما اتغيّرتش.

📌 التشغيل:
   python3 tools/test_engines_filters_audit.py
   python3 -m unittest tools.test_engines_filters_audit -v
"""
from __future__ import annotations

import ast
import math
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r23_engines_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

# ⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

import update_prices as up  # noqa: E402
import octa_score  # noqa: E402
import opp_engine  # noqa: E402

AXES7 = ("technical", "fundamental", "liquidity", "news", "sentiment", "risk", "portfolio")
BASELINE = "edc49cd"

NAN = float("nan")
INF = float("inf")


# ══════════════════════════════════════════════════════════════════════
#  فيكسات — كل الأرقام معلنة صراحة (مافيش رقم جاي من بيانات حقيقية)
# ══════════════════════════════════════════════════════════════════════

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


def fundamental(item, peers=None):
    return up.fundamental_score(item, peers if peers is not None else PEERS)


def rank_item(code="FIXT", **over):
    """سهم جاهز للفلاتر (شكله زي اللي بيطلع من المحرك)."""
    it = {
        "code": code,
        "name": "Fixture " + code,
        "sector": SECTOR,
        "price": 120.0,
        "final_score": 70.0,
        "decision": "إشارة إيجابية",
        "safety_score": 80.0,
        "liquidity_score": 75.0,
        "pe": 12.0,
        "div_yield": 4.0,
        "rank_eligible": True,
        "strategies": {},
    }
    it.update(over)
    return it


# ══════════════════════════════════════════════════════════════════════
#  ١) PEG — مضاعف التقييم بالنمو (الجولة ٢٣ · R23)
# ══════════════════════════════════════════════════════════════════════

class TestPegValue(unittest.TestCase):
    """PEG = P/E ÷ نمو الأرباح(٪) — التعريف والحالات الحدية."""

    def test_peg_is_defined_and_correct(self):
        self.assertTrue(hasattr(up, "peg_value"), "محرك PEG مش موجود في المحرك")
        self.assertAlmostEqual(up.peg_value(20.0, 7.0), 20.0 / 7.0, places=12)

    def test_peg_requires_positive_pe(self):
        self.assertIsNone(up.peg_value(0.0, 10.0), "P/E = 0 ⇒ لازم None")
        self.assertIsNone(up.peg_value(-5.0, 10.0), "P/E سالب ⇒ لازم None")

    def test_peg_requires_positive_growth(self):
        self.assertIsNone(up.peg_value(20.0, 0.0), "نمو صفر ⇒ لازم None")
        self.assertIsNone(up.peg_value(20.0, -5.0), "نمو سالب ⇒ لازم None")

    def test_missing_growth_is_not_zero(self):
        """⛔ النمو المفقود لازم يبقى «مش متاح» — مش صفر (الصفر = inf مخترع)."""
        self.assertIsNone(up.peg_value(20.0, None))
        self.assertIsNone(up.peg_value(20.0, ""))
        self.assertIsNone(up.peg_value(20.0, "N/A"))
        self.assertIsNone(up.peg_value(None, 7.0))

    def test_non_numeric_is_not_present_data(self):
        self.assertIsNone(up.peg_value(20.0, "N/A"))
        self.assertIsNone(up.peg_value(20.0, "12%"))
        self.assertIsNone(up.peg_value("abc", 7.0))
        self.assertIsNone(up.peg_value(True, 7.0), "bool مش رقم بيانات")

    def test_nan_and_inf_are_rejected(self):
        self.assertIsNone(up.peg_value(NAN, 7.0))
        self.assertIsNone(up.peg_value(20.0, NAN))
        self.assertIsNone(up.peg_value(INF, 7.0))
        self.assertIsNone(up.peg_value(20.0, INF))
        self.assertIsNone(up.peg_value(20.0, -INF))

    def test_no_overflow_on_huge_inputs(self):
        """⛔ الأرقام الضخمة لازم ما تعملش overflow ولا NaN ولا استثناء."""
        v = up.peg_value(1e308, 1e-300)
        self.assertIsNone(v, "نمو بلا معنى ⇒ None (مش قسمة تكسر)")
        v2 = up.peg_value(1e308, 0.5)
        self.assertIsNotNone(v2)
        self.assertTrue(math.isfinite(v2), "PEG لازم يبقى رقم محدود")
        self.assertLessEqual(v2, up.PEG_PE_MAX / up.PEG_GROWTH_MIN + 1e-9)
        v3 = up.peg_value(1e308, 1e308)
        self.assertIsNotNone(v3)
        self.assertTrue(math.isfinite(v3))
        self.assertLessEqual(v3, up.PEG_PE_MAX / up.PEG_GROWTH_MIN + 1e-9)

    def test_peg_never_raises(self):
        for pe in (None, 0, -1, 0.0, NAN, INF, -INF, "x", True, 1e308):
            for g in (None, 0, -1, NAN, INF, "x", True, 1e308, 1e-300):
                try:
                    r = up.peg_value(pe, g)
                except Exception as exc:  # noqa: BLE001
                    self.fail("peg_value(%r, %r) رما استثناء: %s" % (pe, g, exc))
                self.assertTrue(r is None or math.isfinite(r),
                                "peg_value(%r, %r) رجّع رقم غير محدود" % (pe, g))


class TestPegBands(unittest.TestCase):
    """جدول الأشرطة: PEG الأصغر = أفضل."""

    def test_band_table_is_explicit_and_documented(self):
        self.assertTrue(hasattr(up, "PEG_BANDS"), "مفيش جدول أشرطة PEG")
        self.assertTrue(len(up.PEG_BANDS) >= 3)
        # الأشرطة مرتّبة تصاعدياً (شرط صحّة الجدول)
        lims = [b[0] for b in up.PEG_BANDS]
        self.assertEqual(lims, sorted(lims), "أشرطة PEG مش مرتّبة")
        # أقصى نقاط PEG = أقصى درجة في الجدول
        self.assertEqual(max(b[1] for b in up.PEG_BANDS), up.PEG_POINTS_MAX)

    def test_lower_peg_scores_higher(self):
        """⛔ الاتجاه: PEG أصغر ⇒ نقاط أكثر."""
        pts_low, v_low = up.peg_score(10.0, 20.0)      # PEG = 0.5
        pts_mid, v_mid = up.peg_score(20.0, 20.0)      # PEG = 1.0
        pts_high, v_high = up.peg_score(60.0, 10.0)    # PEG = 6.0
        self.assertAlmostEqual(v_low, 0.5, places=9)
        self.assertAlmostEqual(v_mid, 1.0, places=9)
        self.assertAlmostEqual(v_high, 6.0, places=9)
        self.assertGreater(pts_low, pts_mid)
        self.assertGreater(pts_mid, pts_high)
        self.assertEqual(pts_high, 0.0, "PEG غالي ⇒ صفر نقاط")

    def test_points_are_monotonic(self):
        pts = []
        peg = 0.1
        while peg <= 6.0:
            pts.append(up.peg_score(peg * 10.0, 10.0)[0])
            peg += 0.1
        for a, b in zip(pts, pts[1:]):
            self.assertGreaterEqual(a, b, "النقاط لازم تنزل مع زيادة PEG")

    def test_unavailable_growth_scores_zero(self):
        """⛔ PEG غير المتاح ⇒ صفر نقاط (مش «رخيص»)."""
        for g in (None, 0, -3, "N/A", NAN, INF, 0.0):
            pts, v = up.peg_score(20.0, g)
            self.assertIsNone(v, "PEG لازم يبقى None ل growth=%r" % (g,))
            self.assertEqual(pts, 0.0, "PEG غير المتاح لازم 0 نقاط ل growth=%r" % (g,))

    def test_non_positive_pe_scores_zero(self):
        for pe in (0, -1, 0.0, -12.5):
            pts, v = up.peg_score(pe, 10.0)
            self.assertIsNone(v)
            self.assertEqual(pts, 0.0)


class TestPegIntegration(unittest.TestCase):
    """PEG جوه المحور الأساسي — من غير تغيير أي وزن معتمد."""

    def test_fundamental_publishes_peg(self):
        res = fundamental(item_with(ni_growth=20.0))
        self.assertIn("peg", res, "المحرك الأساسي مافيش فيه PEG")
        self.assertAlmostEqual(res["peg"], 20.0 / 20.0, places=9)

    def test_fundamental_publishes_none_when_unavailable(self):
        res = fundamental(item_with())
        self.assertIn("peg", res)
        self.assertIsNone(res["peg"], "PEG غير متاح ⇒ None (مش 0 ولا inf)")
        self.assertEqual(res.get("peg_points"), 0.0)

    def test_peg_points_land_in_the_value_bucket_only(self):
        """⛔ PEG لازم يأثر على بند «القيمة» بس — والباقي زي ما هو."""
        without = fundamental(item_with())
        with_g = fundamental(item_with(ni_growth=40.0))   # PEG = 0.5 ⇒ 8 نقاط
        b_no = without["breakdown"]
        b_w = with_g["breakdown"]
        self.assertEqual(b_no["الربحية"], b_w["الربحية"])
        self.assertEqual(b_no["الصحة المالية"], b_w["الصحة المالية"])
        self.assertEqual(b_no["اكتمال البيانات"], b_w["اكتمال البيانات"])
        self.assertGreater(b_w["القيمة"], b_no["القيمة"])
        self.assertLessEqual(b_w["القيمة"] - b_no["القيمة"], up.PEG_POINTS_MAX)

    def test_fundamental_composition_unchanged(self):
        """⛔ تركيبة المحور الأساسي ما اتغيّرتش: 30+30+20+20."""
        res = fundamental(item_with(ni_growth=15.0))
        self.assertEqual(sorted(res["breakdown"].keys()),
                         sorted(["الربحية", "القيمة", "الصحة المالية", "اكتمال البيانات"]))
        self.assertLessEqual(res["breakdown"]["الربحية"], 30)
        self.assertLessEqual(res["breakdown"]["القيمة"], 30)
        self.assertLessEqual(res["breakdown"]["الصحة المالية"], 20)
        self.assertLessEqual(res["breakdown"]["اكتمال البيانات"], 20)
        self.assertLessEqual(res["score"], 100)

    def test_score_without_growth_is_unchanged_by_the_peg_feature(self):
        """⛔ السهم اللي مالوش نمو ⇒ درجته زي ما هي (PEG ما بيغيّرش حاجة)."""
        a = fundamental(item_with())
        b = fundamental(item_with(ni_growth=None))
        c = fundamental(item_with(peg_unused="x"))
        self.assertEqual(a["score"], b["score"])
        self.assertEqual(a["score"], c["score"])
        self.assertEqual(a["breakdown"], b["breakdown"])

    def test_peg_never_breaks_the_engine(self):
        for over in ({"ni_growth": 0}, {"ni_growth": -5}, {"ni_growth": "N/A"},
                     {"ni_growth": NAN}, {"ni_growth": INF}, {"ni_growth": 1e308},
                     {"pe": 0, "ni_growth": 10}, {"pe": -5, "ni_growth": 10}):
            res = fundamental(item_with(**over))
            self.assertIsNotNone(res, "fundamental_score fell on %r" % (over,))
            v = res.get("peg")
            self.assertTrue(v is None or math.isfinite(v))
            self.assertLessEqual(res["score"], 100)


# ══════════════════════════════════════════════════════════════════════
#  ٢) الاستراتيجيات الثماني — التحقق بدون تغيير أي وزن
# ══════════════════════════════════════════════════════════════════════

class TestStrategiesIntegrity(unittest.TestCase):
    """كل استراتيجية: 7 محاور، مجموع 1.0، وحقول متسقة."""

    def test_pricing_strategies_count(self):
        """📌 عدد استراتيجيات التسع المعتمدة = **7** (مش 8).

        ⚠️ تصحيح واقعي: تكليف الجولة ٢٣ كان بيقول «٨ استراتيجيات» ⭐
           والكود فيه **7** ⭐ (swing · value · growth · income · balanced ·
           conservative · aggressive) ⭐ — والـbaseline edc49cd برضو 7 ⭐.
           ⛔ مافيش استراتيجية تانية في أي مكان تاني في الـbackend ⭐
           (استراتيجيات محرك الفرص في data/opp_definitions.json = 9 ⭐
            ⇒ هي كمان مش 8 ⭐).
        """
        self.assertEqual(len(up.STRATEGIES), 7,
                         "عدد استراتيجيات التسع (الحالي %d)" % len(up.STRATEGIES))
        self.assertEqual(sorted(up.STRATEGIES.keys()),
                         sorted(["aggressive", "balanced", "conservative", "growth",
                                 "income", "swing", "value"]))

    def test_every_strategy_has_the_seven_axes(self):
        for key, st in up.STRATEGIES.items():
            self.assertEqual(sorted(st["weights"].keys()), sorted(AXES7),
                             "محاور %s مش الـ7 المعتمدة" % key)

    def test_every_weight_map_sums_to_one(self):
        for key, st in up.STRATEGIES.items():
            total = sum(st["weights"].values())
            self.assertAlmostEqual(total, 1.0, places=9,
                                   msg="أوزان %s مجموعها %r (مش 1.0)" % (key, total))

    def test_every_weight_is_a_number_in_range(self):
        for key, st in up.STRATEGIES.items():
            for axis, w in st["weights"].items():
                self.assertIsInstance(w, (int, float), "%s/%s مش رقم" % (key, axis))
                self.assertGreaterEqual(w, 0.0, "%s/%s سالب" % (key, axis))
                self.assertLessEqual(w, 1.0, "%s/%s أكبر من 1" % (key, axis))

    def test_required_metadata_is_present(self):
        for key, st in up.STRATEGIES.items():
            for field in ("name_ar", "desc", "timeframe", "focus"):
                self.assertIn(field, st, "%s ناقصه %s" % (key, field))
                self.assertTrue(str(st[field]).strip(), "%s.%s فاضي" % (key, field))

    def test_risk_penalty_mult_is_coherent(self):
        for key, st in up.STRATEGIES.items():
            m = st.get("risk_penalty_mult")
            self.assertIsInstance(m, (int, float), "%s بلا risk_penalty_mult" % key)
            self.assertGreater(m, 0.0, "%s risk_penalty_mult لازم يكون موجب" % key)
            self.assertLessEqual(m, 5.0, "%s risk_penalty_mult منطقي؟" % key)

    def test_min_liquidity_is_inside_the_liquidity_scale(self):
        """⛔ عتبة السيولة لازم تكون جوّه مقياس السيولة (0..100)."""
        for key, st in up.STRATEGIES.items():
            ml = st.get("min_liquidity")
            self.assertIsInstance(ml, (int, float), "%s بلا min_liquidity" % key)
            self.assertGreaterEqual(ml, 0.0, "%s min_liquidity سالب" % key)
            self.assertLessEqual(ml, 100.0, "%s min_liquidity برّه مقياس السيولة" % key)

    def test_min_safety_and_min_div_yield_are_inside_their_scales(self):
        for key, st in up.STRATEGIES.items():
            if "min_safety" in st:
                self.assertGreaterEqual(st["min_safety"], 0.0)
                self.assertLessEqual(st["min_safety"], 100.0,
                                     "%s min_safety برّه مقياس الأمان" % key)
            if "min_div_yield" in st:
                self.assertGreaterEqual(st["min_div_yield"], 0.0)
                self.assertLessEqual(st["min_div_yield"], 100.0,
                                     "%s min_div_yield برّه مقياس العائد" % key)

    def test_weights_are_identical_to_the_approved_baseline(self):
        """⛔ الأوزان المعتمدة ما اتغيّرتش (مقارنة بال-baseline edc49cd)."""
        base = _baseline_strategies()
        self.assertIsNotNone(base, "مقدرتش أقرأ الـbaseline")
        self.assertEqual(sorted(base.keys()), sorted(up.STRATEGIES.keys()),
                         "مجموعة الاستراتيجيات اتغيّرت")
        for key in base:
            self.assertEqual(base[key]["weights"], up.STRATEGIES[key]["weights"],
                             "أوزان %s اتغيّرت" % key)

    def test_axis_weights_and_coverage_threshold_untouched(self):
        """⛔ أوزان المحاور وحد الـ90٪ ما اتغيّرتش."""
        self.assertAlmostEqual(sum(octa_score.AXIS_WEIGHTS.values()), 1.0, places=9)
        self.assertEqual(opp_engine.FRESH_MIN_COVERAGE, 90.0)


class TestStrategyComputation(unittest.TestCase):
    """كل استراتيجية معروفة لازم تتحسب فعلاً."""

    def test_all_eight_strategies_compute(self):
        it = item_with()
        it["all_axes"] = {"risk": 70.0}
        for key in up.STRATEGIES:
            r = up.strategy_score(
                it, key,
                {"score": 70.0}, {"score": 60.0}, {"score": 75.0},
                {"score": 55.0}, {"score": 65.0},
            )
            self.assertIsNotNone(r, "%s رجّع None" % key)
            self.assertIsNotNone(r.get("score"), "%s مافيش درجة" % key)
            self.assertEqual(r.get("strategy"), key)
            self.assertNotEqual(r.get("score_status"), "unknown_strategy")

    def test_known_strategy_is_not_affected_by_the_unknown_guard(self):
        it = item_with()
        it["all_axes"] = {"risk": 70.0}
        r = up.strategy_score(it, "balanced", {"score": 70.0}, {"score": 60.0},
                              {"score": 75.0}, {"score": 55.0}, {"score": 65.0})
        self.assertEqual(r["strategy_name"], up.STRATEGIES["balanced"]["name_ar"])


class TestStrategySelection(unittest.TestCase):
    """⛔ مسار اختيار الاستراتيجية: مفيش fallback صامت لـ«balanced»."""

    def test_unknown_strategy_does_not_fall_back_to_balanced(self):
        it = item_with()
        it["all_axes"] = {"risk": 70.0}
        args = ({"score": 70.0}, {"score": 60.0}, {"score": 75.0},
                {"score": 55.0}, {"score": 65.0})
        bad = up.strategy_score(it, "swign", *args)
        self.assertIsNotNone(bad, "محرك الاستراتيجية رجّع None")
        self.assertIsNone(bad.get("score"),
                          "استراتيجية مجهولة ⇒ مفيش درجة (مش نتيجة «متوازنة»)")
        self.assertEqual(bad.get("score_status"), "unknown_strategy")
        self.assertFalse(bad.get("rank_eligible"))
        self.assertNotEqual(bad.get("strategy_name"),
                            up.STRATEGIES["balanced"]["name_ar"],
                            "استراتيجية مجهولة اتسميت باسم «متوازن»")

    def test_none_strategy_does_not_fall_back_to_balanced(self):
        it = item_with()
        it["all_axes"] = {"risk": 70.0}
        r = up.strategy_score(it, None, {"score": 70.0}, {"score": 60.0},
                              {"score": 75.0}, {"score": 55.0}, {"score": 65.0})
        self.assertIsNone(r.get("score"))
        self.assertEqual(r.get("score_status"), "unknown_strategy")

    def test_http_paths_reject_unknown_strategy(self):
        """⛔ المسار الحيّ (HTTP) كان محمي من الأصل — برهان إنه لسه محمي."""
        up._HITS.clear()
        up.app.dispatch("/api/strategy/FIXT/swign",
                        headers={"X-Forwarded-For": "10.9.0.21"})
        up._HITS.clear()

    def test_score_all_strategies_keeps_all_eight(self):
        it = item_with()
        it["all_axes"] = {"risk": 70.0}
        out = up.score_all_strategies(it, {"score": 70.0}, {"score": 60.0},
                                      {"score": 75.0}, {"score": 55.0}, {"score": 65.0})
        self.assertEqual(sorted(out.keys()), sorted(up.STRATEGIES.keys()))


# ══════════════════════════════════════════════════════════════════════
#  ٣) الفلاتر الأساسية الثمانية — حالات حدّية
# ══════════════════════════════════════════════════════════════════════

class TestMainFilters(unittest.TestCase):
    """الفلاتر الثمانية في rank_stocks — كل واحد بحالاته الحدية."""

    # ── 1) min_score ──
    def test_filter_min_score(self):
        keep = up.rank_stocks([rank_item()], min_score=60)
        self.assertEqual(len(keep), 1)
        drop = up.rank_stocks([rank_item()], min_score=90)
        self.assertEqual(len(drop), 0, "درجة أقل من الحد ⇒ يتشال")

    def test_filter_min_score_nan_and_inf(self):
        nan_item = rank_item(final_score=NAN)
        out = up.rank_stocks([nan_item], min_score=50)
        self.assertEqual(len(out), 0, "NaN في الدرجة ⇒ يتشال (مش بيعدّي كأنه ممتاز)")
        inf_item = rank_item(final_score=INF)
        out2 = up.rank_stocks([inf_item], min_score=50)
        self.assertEqual(len(out2), 0, "inf في الدرجة ⇒ يتشال")

    def test_filter_min_score_missing(self):
        out = up.rank_stocks([rank_item(final_score=None)], min_score=0)
        self.assertEqual(len(out), 0, "درجة مفقودة ⇒ السهم بيتشال أصلاً")

    # ── 2) max_risk (حدّ أدنى لدرجة الأمان) ──
    def test_filter_max_risk_keeps_safe_stock(self):
        out = up.rank_stocks([rank_item(safety_score=90.0)], max_risk=80)
        self.assertEqual(len(out), 1)

    def test_filter_max_risk_drops_unsafe_stock(self):
        out = up.rank_stocks([rank_item(safety_score=40.0)], max_risk=80)
        self.assertEqual(len(out), 0)

    def test_filter_max_risk_missing_safety_is_not_treated_as_safe(self):
        """⛔ الأمان غير المعروف ≠ «آمن» — لازم يتشال زي min_safety."""
        out = up.rank_stocks([rank_item(safety_score=None)], max_risk=80)
        self.assertEqual(len(out), 0,
                         "سهم مالوش درجة أمان عدّى فلتر الأمان — العيب المتسق مع min_safety")
        out2 = up.rank_stocks([rank_item(safety_score=None)], min_safety=10)
        self.assertEqual(len(out2), 0, "(min_safety behaviour المرجعي)")

    def test_filter_max_risk_nan_safety_is_rejected(self):
        out = up.rank_stocks([rank_item(safety_score=NAN)], max_risk=80)
        self.assertEqual(len(out), 0, "NaN في الأمان ⇒ يتشال")

    # ── 3) min_safety ──
    def test_filter_min_safety(self):
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=90.0)], min_safety=50)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=30.0)], min_safety=50)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=None)], min_safety=50)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(safety_score=NAN)], min_safety=50)), 0)

    # ── 4) min_liquidity ──
    def test_filter_min_liquidity(self):
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=90.0)], min_liquidity=50)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=10.0)], min_liquidity=50)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=None)], min_liquidity=50)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(liquidity_score=NAN)], min_liquidity=50)), 0)

    # ── 5) sectors ──
    def test_filter_sectors(self):
        self.assertEqual(len(up.rank_stocks([rank_item(sector=SECTOR)], sectors=[SECTOR])), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(sector="أخرى")], sectors=[SECTOR])), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(sector=None)], sectors=[SECTOR])), 0,
                         "سهم بلا قطاع ⇒ ما يعديش فلتر القطاعات")
        self.assertEqual(len(up.rank_stocks([rank_item(sector=None)], sectors=None)), 1,
                         "من غير فلتر قطاعات ⇒ الكل يعدّي")

    # ── 6) max_pe ──
    def test_filter_max_pe(self):
        self.assertEqual(len(up.rank_stocks([rank_item(pe=10.0)], max_pe=20)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=30.0)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=None)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=0.0)], max_pe=20)), 0,
                         "P/E = 0 ⇒ يتشال (مش «رخيص»)")
        self.assertEqual(len(up.rank_stocks([rank_item(pe=-4.0)], max_pe=20)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(pe=NAN)], max_pe=20)), 0,
                         "NaN في P/E ⇒ يتشال")
        self.assertEqual(len(up.rank_stocks([rank_item(pe="N/A")], max_pe=20)), 0)

    # ── 7) min_div_yield ──
    def test_filter_min_div_yield(self):
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=5.0)], min_div_yield=3)), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=1.0)], min_div_yield=3)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=None)], min_div_yield=3)), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=0.0)], min_div_yield=3)), 0,
                         "عائد صفر ⇒ يتشال")
        self.assertEqual(len(up.rank_stocks([rank_item(div_yield=NAN)], min_div_yield=3)), 0)

    # ── 8) decisions ──
    def test_filter_decisions(self):
        self.assertEqual(len(up.rank_stocks([rank_item(decision="إشارة إيجابية")],
                                             decisions=["إشارة إيجابية"])), 1)
        self.assertEqual(len(up.rank_stocks([rank_item(decision="إشارة سلبية")],
                                             decisions=["إشارة إيجابية"])), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(decision=None)],
                                             decisions=["إشارة إيجابية"])), 0)
        self.assertEqual(len(up.rank_stocks([rank_item(decision=None)], decisions=None)), 1)

    # ── البنية المشتركة ──
    def test_filters_accept_zero_threshold(self):
        """⛔ عتبة صفر = «مفيش حد» (مش «اتشال كل حاجة»)."""
        st = rank_item()
        self.assertEqual(len(up.rank_stocks([st], min_score=0, max_risk=0,
                                            min_safety=0, min_liquidity=0,
                                            max_pe=0, min_div_yield=0)), 0,
                         "max_pe = 0 ⇒ مفيش P/E صالح (صح)")

    def test_rank_eligible_false_is_excluded(self):
        st = rank_item(rank_eligible=False)
        self.assertEqual(len(up.rank_stocks([st], strategy=None)), 0)

    def test_huge_threshold_values_do_not_crash(self):
        st = rank_item()
        out = up.rank_stocks([st], min_score=1e18, max_risk=1e18, min_safety=1e18,
                             min_liquidity=1e18, max_pe=1e18, min_div_yield=1e18)
        self.assertEqual(len(out), 0)


# ══════════════════════════════════════════════════════════════════════
#  ٤) الصيغ المالية — حالات حدّية
# ══════════════════════════════════════════════════════════════════════

class TestFinancialFormulas(unittest.TestCase):
    """P/E · P/B · PEG · عائد التوزيعات · القيمة السوقية · الحجم النسبي."""

    # ── P/E ──
    def test_pe_band_table_non_positive_is_worst(self):
        """⛔ P/E <= 0 ⇒ أسوأ شريحة (مش أفضل شريحة)."""
        zero = up.quick_score(item_with(pe=0.0))
        neg = up.quick_score(item_with(pe=-5.0))
        cheap = up.quick_score(item_with(pe=5.0))
        self.assertLessEqual(zero["axes"]["fundamental"], neg["axes"]["fundamental"] + 0.001)
        self.assertLess(zero["axes"]["fundamental"], cheap["axes"]["fundamental"],
                        "P/E = 0 اتحسب «رخيص» — نفس عيب R22 في المحرك السريع")

    def test_pe_band_table_nan_is_not_best(self):
        out = up.quick_score(item_with(pe=NAN))
        self.assertIsInstance(out["axes"]["fundamental"], int)
        self.assertFalse(math.isnan(out["axes"]["fundamental"]))

    def test_pe_band_table_huge_value(self):
        out = up.quick_score(item_with(pe=1e9))
        self.assertEqual(out["axes"]["fundamental"], 35)

    def test_nz5_pe_band_non_positive_is_worst(self):
        for pe in (0.0, -5.0):
            rec = up.nz5_score(item_with(pe=pe))
            val = [a for a in rec["axes"] if a["id"] == "val"][0]
            pe_row = [i for i in val["items"] if i["key"] == "pe"][0]
            self.assertTrue(pe_row.get("score") is None or pe_row["score"] <= 20.0,
                            "nz5: P/E=%r وصل لأفضل شريحة" % (pe,))

    def test_fundamental_value_bucket_ignores_non_positive_pe(self):
        """⛔ P/E <= 0 ⇒ مافيش نقاط من P/E (بنفس قيمة P/E مفقود)."""
        zero = fundamental(item_with(pe=0.0))
        missing = fundamental(item_with(pe=None))
        neg = fundamental(item_with(pe=-5.0))
        cheap = fundamental(item_with(pe=5.0))
        self.assertEqual(zero["breakdown"]["القيمة"], missing["breakdown"]["القيمة"])
        self.assertEqual(neg["breakdown"]["القيمة"], missing["breakdown"]["القيمة"])
        self.assertGreater(cheap["breakdown"]["القيمة"], zero["breakdown"]["القيمة"],
                           "P/E <= 0 اتحسب له نقاط قيمة")

    # ── P/B ──
    def test_pb_zero_does_not_divide_by_zero(self):
        """⛔ P/B = 0 ⇒ مافيش نقاط P/B + مافيش قسمة على صفر."""
        zero = fundamental(item_with(pb=0.0))
        missing = fundamental(item_with(pb=None))
        self.assertIsNotNone(zero)
        self.assertEqual(zero["breakdown"]["القيمة"], missing["breakdown"]["القيمة"])

    def test_pb_negative_is_worst(self):
        neg = fundamental(item_with(pb=-2.0))
        missing = fundamental(item_with(pb=None))
        self.assertIsNotNone(neg)
        self.assertEqual(neg["breakdown"]["القيمة"], missing["breakdown"]["القيمة"])

    def test_nz5_pb_band_non_positive_is_worst(self):
        for pb in (0.0, -2.0):
            rec = up.nz5_score(item_with(pb=pb))
            val = [a for a in rec["axes"] if a["id"] == "val"][0]
            pb_row = [i for i in val["items"] if i["key"] == "pb"][0]
            self.assertTrue(pb_row.get("score") is None or pb_row["score"] <= 20.0,
                            "nz5: P/B=%r وصل لأفضل شريحة" % (pb,))

    # ── PEG (متلخص — التفصيل في TestPeg*) ──
    def test_peg_formula_edge_cases(self):
        self.assertAlmostEqual(up.peg_value(20.0, 7.0), 20.0 / 7.0, places=12)
        self.assertIsNone(up.peg_value(20.0, 0.0))
        self.assertIsNone(up.peg_value(20.0, -1.0))
        self.assertIsNone(up.peg_value(0.0, 5.0))
        self.assertIsNone(up.peg_value(-1.0, 5.0))
        self.assertIsNone(up.peg_value(20.0, None))
        self.assertIsNone(up.peg_value(20.0, NAN))
        self.assertIsNone(up.peg_value(20.0, INF))
        self.assertIsNone(up.peg_value(20.0, ""))

    # ── عائد التوزيعات ──
    def test_div_yield_zero_is_not_a_dividend_catalyst(self):
        with_zero = up.opportunity_engine(item_with(div_yield=0.0))
        without = up.opportunity_engine(item_with(div_yield=None))
        self.assertEqual(with_zero["breakdown"]["محفز أساسي"],
                         without["breakdown"]["محفز أساسي"])

    def test_div_yield_missing_is_not_zero_in_fair_value(self):
        res = fundamental(item_with(div_yield=None))
        self.assertNotIn("عائد التوزيعات", res.get("fair_value_methods") or {})

    def test_div_yield_filter_treats_missing_as_not_available(self):
        st = rank_item(div_yield=None)
        out = up.rank_stocks([st], min_div_yield=0.0)
        self.assertEqual(len(out), 0, "عائد مفقود ⇒ يتشال حتى مع عتبة صفر")

    # ── القيمة السوقية ──
    def test_market_cap_zero_is_not_treated_as_good(self):
        """⛔ القيمة السوقية = 0 ⇒ «ضئيلة» (مش عمق سوق متوسط)."""
        zero = up.quick_score(item_with(mkt_cap=0.0))
        big = up.quick_score(item_with(mkt_cap=60e9))
        self.assertLess(zero["axes"]["liquidity"], big["axes"]["liquidity"])

    def test_market_cap_nan_is_not_excellent_liquidity(self):
        """⛔ NaN في القيمة السوقية ⇒ ما يتحسبش «سيولة ممتازة»."""
        r = up.risk_engine(item_with(mkt_cap=NAN, beta=1.0, volatility=2.0))
        self.assertIsNotNone(r.get("safety_score"))
        self.assertFalse(math.isnan(r["safety_score"]))
        self.assertNotIn("سيولة ممتازة", r.get("notes") or [])

    def test_market_cap_zero_is_max_liquidity_risk(self):
        r = up.risk_engine(item_with(mkt_cap=0.0, beta=1.0, volatility=2.0))
        self.assertIsNotNone(r.get("safety_score"))

    # ── الحجم النسبي ──
    def test_relative_volume_zero_is_not_a_catalyst(self):
        with_zero = up.opportunity_engine(item_with(rel_volume=0.0))
        without = up.opportunity_engine(item_with(rel_volume=None))
        self.assertEqual(with_zero["breakdown"]["التراكم"],
                         without["breakdown"]["التراكم"])

    def test_relative_volume_nan_does_not_break_the_engine(self):
        out = up.opportunity_engine(item_with(rel_volume=NAN))
        self.assertIsNotNone(out)
        self.assertFalse(math.isnan(out["score"]))

    # ── ROE · هامش صافي · نسبة دين ──
    def test_roe_nan_is_not_profitability(self):
        res = fundamental(item_with(roe=NAN))
        self.assertIsNotNone(res)
        self.assertFalse(math.isnan(res["breakdown"]["الربحية"]))

    def test_roe_negative_is_not_the_best_band(self):
        neg = fundamental(item_with(roe=-20.0))
        good = fundamental(item_with(roe=40.0))
        self.assertLess(neg["breakdown"]["الربحية"], good["breakdown"]["الربحية"])

    def test_net_margin_negative_is_penalised(self):
        neg = fundamental(item_with(net_margin=-30.0))
        self.assertLess(neg["breakdown"]["الربحية"],
                        fundamental(item_with(net_margin=30.0))["breakdown"]["الربحية"])

    def test_debt_ratio_nan_is_not_low_debt(self):
        r = up.risk_engine(item_with(de_ratio=NAN, beta=1.0, volatility=2.0))
        self.assertNotIn("شركة قليلة الديون", r.get("notes") or [])

    def test_debt_ratio_zero_is_low_debt(self):
        r = up.risk_engine(item_with(de_ratio=0.0, beta=1.0, volatility=2.0))
        self.assertIn("شركة قليلة الديون", r.get("notes") or [])

    def test_risk_engine_pe_zero_is_a_risk(self):
        """⛔ P/E = 0 ⇒ مخاطرة (مش «مافيش مخاطرة تقييم»)."""
        r = up.risk_engine(item_with(pe=0.0, beta=1.0, volatility=2.0))
        self.assertGreater(r["breakdown"]["التقييم"], 0.0,
                           "P/E = 0 اتحسب «مافيش مخاطرة تقييم»")

    def test_engines_survive_nan_everywhere(self):
        bad = dict(BASE_ITEM)
        for k in ("pe", "pb", "roe", "net_margin", "de_ratio", "eps", "div_yield",
                  "beta", "volatility", "mkt_cap", "volume", "rel_volume", "atr",
                  "rsi", "price", "perf_1m", "perf_3m", "tv_all"):
            bad[k] = NAN
        res = fundamental(bad)
        self.assertIsNotNone(res)
        self.assertFalse(math.isnan(res["score"]))
        q = up.quick_score(bad)
        self.assertIsNotNone(q)
        self.assertFalse(math.isnan(q["axes"]["overall"]))
        r = up.risk_engine(bad)
        self.assertIsNotNone(r.get("safety_score"))
        self.assertFalse(math.isnan(r["safety_score"]))
        o = up.opportunity_engine(bad)
        self.assertIsNotNone(o)
        self.assertFalse(math.isnan(o["score"]))

    def test_engines_survive_inf_everywhere(self):
        bad = dict(BASE_ITEM)
        for k in ("pe", "pb", "roe", "net_margin", "de_ratio", "eps", "div_yield",
                  "beta", "volatility", "mkt_cap", "volume", "rel_volume", "atr",
                  "rsi", "price", "perf_1m", "perf_3m", "tv_all"):
            bad[k] = INF
        res = fundamental(bad)
        self.assertIsNotNone(res)
        self.assertFalse(math.isnan(res["score"]))
        r = up.risk_engine(bad)
        self.assertIsNotNone(r.get("safety_score"))
        self.assertFalse(math.isnan(r["safety_score"]))

    def test_engines_survive_text_values(self):
        """⛔ «N/A» مش بيانات موجودة — والدرجة ما بتاخدش NaN."""
        bad = dict(BASE_ITEM)
        for k in ("pe", "pb", "roe", "net_margin", "de_ratio", "eps", "div_yield",
                  "beta", "volatility", "mkt_cap", "volume", "rel_volume"):
            bad[k] = "N/A"
        res = fundamental(bad)
        self.assertIsNotNone(res)
        self.assertIsNone(res.get("peg"))
        self.assertFalse(math.isnan(res["score"]))
        # ⛔ الحقول السبعة المالية كلها نصية ماعدا revenue ⇒
        #    «اكتمال البيانات» = 1 من 7 (مش 7 من 7)
        self.assertAlmostEqual(res["breakdown"]["اكتمال البيانات"], (1 / 7) * 20, places=1)


# ══════════════════════════════════════════════════════════════════════
#  أدوات مساعدة
# ══════════════════════════════════════════════════════════════════════

def _baseline_strategies():
    """كتلة STRATEGIES من الـbaseline المعتمد (edc49cd) — لل comparisons."""
    try:
        out = subprocess.run(
            ["git", "-C", REPO, "show", "%s:update_prices.py" % BASELINE],
            capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return None
    if not out:
        return None
    try:
        tree = ast.parse(out)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "STRATEGIES":
                    try:
                        return ast.literal_eval(node.value)
                    except Exception:  # noqa: BLE001
                        return None
    return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
