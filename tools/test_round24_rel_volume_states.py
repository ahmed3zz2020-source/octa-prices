#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٤ (R24 · المرحلة ٥) — حالات الحجم النسبي الأربعة في `octa_score.py`

🎯 الغرض: **إثبات السلوك بدقة** لكل حالة من حالات `rel_volume`:
   · صفر حقيقي (`0.0`) · `None` (ناقص) · `NaN` · `Inf`
   في المحرك الفني (`tech_score`) ومحرك السيولة (`liquidity_score`).

📌 أي تغيّر في السلوك ده = تغيّر سياسة ⇒ لازمه إذن المالك.
   الاختبارات دي **تثبّت** السلوك المعتمد (وزنه + عتباته) وتمنع تغيّر سري.

⛔ مافيش أي تعديل على:
   · الأوزان المعتمدة (`octa_score.AXIS_WEIGHTS`)
   · حد التغطية 90٪ (`opp_engine.FRESH_MIN_COVERAGE`)
   · منهجية التقييم (تركيبة المحور الأساسي 30+30+20+20)
   · أي وزن داخل بند الحجم أو بند النشاط

📌 التشغيل:
   python3 tools/test_round24_rel_volume_states.py
   python3 -m unittest tools.test_round24_rel_volume_states -v
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r24_relvol_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

# ⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"

NAN = float("nan")
INF = float("inf")


# ══════════════════════════════════════════════════════════════════════
#  فيكسات — كل الأرقام معلنة صراحة (مافيش رقم جاي من بيانات حقيقية)
# ══════════════════════════════════════════════════════════════════════
BASE_ITEM = {
    "code": "TEST", "name": "سهم اختبار", "price": 100.0,
    "ema20": 98.0, "ema50": 96.0, "ema200": 90.0, "sma50": 97.0,
    "rsi": 55.0, "rsi_prev": 52.0, "macd": 1.0, "macd_signal": 0.8,
    "adx": 25.0, "di_plus": 20.0, "di_minus": 18.0,
    "atr": 2.5, "bb_upper": 105.0, "bb_lower": 95.0,
    "stoch_k": 60.0, "stoch_d": 55.0, "tv_all": 0.2,
    "perf_1m": 5.0, "perf_3m": 8.0,
    "volume": 500000, "vol_5": 490000, "vol_60": 480000,
    "mkt_cap": 5e9, "beta": 0.9, "de_ratio": 30.0, "volatility": 25.0,
    "data_confidence": 80,
}


def item_with(rel_volume=None, present=True, **over):
    """سهم كامل technical + سيولة — غير حقل الحجم النسبي."""
    it = dict(BASE_ITEM)
    if present:
        it["rel_volume"] = rel_volume
    it.update(over)
    return it


def _non_finite_paths(obj, path=""):
    """كل المسارات اللي فيها NaN أو Inf (تشويش في الردود)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_non_finite_paths(v, "%s.%s" % (path, k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(_non_finite_paths(v, "%s[%d]" % (path, i)))
    elif isinstance(obj, float):
        if obj != obj or obj in (INF, -INF):
            out.append(path)
    return out


class RelVolumeStates(unittest.TestCase):
    """الحالات الأربعة — سلوك مثبّت بالرقم."""

    # ── ① الصفر الحقيقي ──────────────────────────────────────────────
    def test_zero_is_published_as_zero_not_missing(self):
        """⛔ الصفر الحقيقي = معلوم كصفر (0.0) — مش None."""
        import octa_score
        liq = octa_score.liquidity_score(item_with(0.0))
        self.assertEqual(liq["metrics"]["الحجم النسبي"], 0.0,
                         "الصفر الحقيقي لازم ينزل 0.0 (مش None)")

    def test_missing_is_published_as_none(self):
        """⛔ الناقص = None (مش صفر)."""
        import octa_score
        for rv, present in ((None, True), (None, False)):
            liq = octa_score.liquidity_score(item_with(rv, present=present))
            self.assertIsNone(liq["metrics"]["الحجم النسبي"],
                              "الناقص لازم ينزل None (مش 0.0)")

    def test_zero_and_missing_are_distinguishable(self):
        """⛔ الصفر والناقص **مختلفين** في المحركين (مش نفس الرقم)."""
        import octa_score
        zero = octa_score.tech_score(item_with(0.0))
        miss = octa_score.tech_score(item_with(None))
        self.assertNotEqual(zero["breakdown"]["الحجم"], miss["breakdown"]["الحجم"],
                            "الصفر والناقص لازم يختلفوا في بند الحجم الفني")
        self.assertEqual(zero["breakdown"]["الحجم"], 3)
        self.assertEqual(miss["breakdown"]["الحجم"], 5.0)

    # ── ② القيم غير الصالحة (NaN / Inf) ──────────────────────────────
    def test_nan_is_treated_as_missing(self):
        """⛔ `NaN` مش بيانات ⇒ ناقص (مش «ضعيف» بالصدفة)."""
        import octa_score
        liq = octa_score.liquidity_score(item_with(NAN))
        self.assertIsNone(liq["metrics"]["الحجم النسبي"])
        self.assertEqual(liq["breakdown"]["النشاط"], 15,
                         "NaN لازم behaves زي الناقص (15) مش أضعف شريحة (5)")

    def test_inf_is_treated_as_missing(self):
        """⛔ `Inf` مش بيانات ⇒ ناقص (مش أعلى شريحة)."""
        import octa_score
        liq = octa_score.liquidity_score(item_with(INF))
        self.assertIsNone(liq["metrics"]["الحجم النسبي"])
        self.assertEqual(liq["breakdown"]["النشاط"], 15,
                         "Inf لازم behaves زي الناقص (15) مش أعلى شريحة (28)")
        tech = octa_score.tech_score(item_with(INF))
        self.assertEqual(tech["breakdown"]["الحجم"], 5.0,
                         "Inf في المحرك الفني = ناقص (5.0) مش أعلى شريحة (10)")

    def test_no_nan_or_inf_in_published_payload(self):
        """⛔ مافيش NaN ولا Inf في أي ردّ بينتجه المحرّكان."""
        import octa_score
        for rv in (0.0, None, NAN, INF):
            for fn in (octa_score.tech_score, octa_score.liquidity_score):
                out = fn(item_with(rv))
                bad = _non_finite_paths(out)
                self.assertEqual(bad, [],
                                 "ردّ فيه NaN/Inf عند %r: %s" % (rv, bad))

    # ── ③ سياسة الدرجة (مثبّتة — تغيّرها = تغيّر سياسة) ──────────────
    def test_zero_keeps_the_neutral_policy_in_the_liquidity_band(self):
        """⛔ سياسة الدرجة ما اتغيّرتش: الصفر = محايد (15) زي الناقص.

        📌 توثيق: تحويل الصفر من محايد إلى «ضعيف جداً» (5) = **تغيير
        سياسة** ⇒ محتاج إذن المالك ⇒ مسجّل كاقتراح في أدلة الجولة ٢٤
        (قبل/بعد بالبرهان) ومش مطبَّق هنا.
        """
        import octa_score
        zero = octa_score.liquidity_score(item_with(0.0))
        miss = octa_score.liquidity_score(item_with(None))
        self.assertEqual(zero["breakdown"]["النشاط"], 15)
        self.assertEqual(miss["breakdown"]["النشاط"], 15)

    def test_sensitivity_of_the_published_score_is_zero_for_the_identity_fix(self):
        """📌 حساسية: إصلاح «هوية الصفر» ما حرّكش أي درجة منشورة."""
        import octa_score
        zero = octa_score.liquidity_score(item_with(0.0))
        miss = octa_score.liquidity_score(item_with(None))
        self.assertEqual(zero["score"], miss["score"],
                         "إصلاح الهوية لازم ما يغيّرش الدرجة المنشورة")
        t_zero = octa_score.tech_score(item_with(0.0))
        t_miss = octa_score.tech_score(item_with(None))
        fin_zero = octa_score.final_score(item_with(0.0), t_zero, None, zero, {})
        fin_miss = octa_score.final_score(item_with(None), t_miss, None, miss, {})
        self.assertAlmostEqual(fin_zero["final_score"], 34.9, places=1)
        self.assertAlmostEqual(fin_miss["final_score"], 35.4, places=1)

    # ── ④ «الناقص» ما بياخدش أي درجة على مستوى المحور ─────────────────
    def test_missing_axis_gets_no_score_and_no_weight(self):
        """⛔ محور ناقص = لا درجة ولا وزن (مش رقم محايد)."""
        import octa_score
        it = item_with(0.0)
        tech = octa_score.tech_score(it)
        fin = octa_score.final_score(it, tech, None, None, {})
        self.assertIsNone(fin["axes"]["liquidity"],
                          "محور السيولة الناقص لازم يبقى None")
        axes_used = [c["axis"] for c in fin.get("contributions") or []]
        self.assertNotIn("liquidity", axes_used,
                         "المحور الناقص ما بياخدش وزن في المحصلة")

    def test_item_without_any_liquidity_data_has_no_score_at_all(self):
        """⛔ مافيش بيانات سيولة خالص ⇒ درجة None (مش 50)."""
        import octa_score
        bare = {"code": "TEST", "price": 10.0}
        liq = octa_score.liquidity_score(bare)
        self.assertIsNone(liq["score"])
        self.assertEqual(liq["score_status"], "insufficient_liquidity_data")

    # ── ⑤ مصدر البيانات الحقيقي ───────────────────────────────────────
    def test_runtime_validator_rejects_nan_and_inf(self):
        """⛔ مدخل الـscanner ما بيقدرش يدي NaN ولا Inf ⇒ الدرجات المنشورة
        للأسهم الحقيقية ما بتتغيّرش بإصلاح التطبيع."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        for bad in (NAN, INF, -INF):
            value, reason = up.validate_value("rel_volume", bad)
            self.assertIsNone(value, "rel_volume=%r لازم يترفض" % (bad,))
            self.assertTrue(reason, "لازم يكون فيه سبب رفض مكتوب")

    def test_snapshot_has_no_non_finite_relative_volume(self):
        """⛔ لقطة البيانات المنشورة: مافيش NaN/Inf في الحجم النسبي."""
        path = os.path.join(REPO, "data_full.json")
        if not os.path.isfile(path):
            self.skipTest("لقطة البيانات غير موجودة")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        stocks = data.get("stocks") or {}
        values = [s.get("relvol") for s in stocks.values() if isinstance(s, dict)]
        values = [v for v in values if v is not None]
        bad = [v for v in values if isinstance(v, float) and (v != v or v in (INF, -INF))]
        self.assertEqual(bad, [], "لقطة البيانات فيها قيم غير صالحة")


if __name__ == "__main__":
    unittest.main(verbosity=2)
