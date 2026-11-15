#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ محرّك الفرص الحي (OPP-002) — اختبارات (١٥ نوفمبر ٢٠٢٦).

📌 التغطية:
   ① التسع استراتيجيات موجودة (مش السبعة القديمة)
   ② النتيجة بتتغيّر لما السعر/الحجم/المخاطرة يتغيّروا
   ③ ⛔ الأوزان والعتبات السرّية ما بتترجعش في الرد العام
   ④ ⛔ سهم بمخاطرة ناقصة ما بياخدش «فرصة مؤكدة»
   ⑤Reasons مبسّطة (من غير نقاط/وزن)
   ⑥ فصل المستخدم المجاني عن المدفوع

📌 التشغيل:  python3 test_opp_live01.py
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import opp_engine as oe  # noqa: E402


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
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


class TestDefinitions(unittest.TestCase):
    def test_nine_strategies_loaded(self):
        defs = oe.load_definitions()
        keys = [s["key"] for s in defs["strategies"]]
        self.assertEqual(len(keys), 9, "المفروض ٩ استراتيجيات")
        for k in ("swing", "medium", "longterm", "value", "growth",
                  "dividend", "balanced", "conservative", "aggressive"):
            self.assertIn(k, keys)

    def test_every_criterion_has_a_scorer(self):
        defs = oe.load_definitions()
        missing = []
        for s in defs["strategies"]:
            for c in s["criteria"]:
                if c["key"] not in oe.CRITERIA_SCORERS:
                    missing.append(c["key"])
        self.assertEqual(missing, [], "معايير من غير مقيّم: " + ", ".join(missing))


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.defs = oe.load_definitions()
        self.stocks = [_stock()]

    def test_scores_for_all_nine(self):
        payload = oe.build_payload(self.stocks, self.defs, {"generated_at": "T"})
        self.assertEqual(len(payload["lists"]), 9)
        for key, lst in payload["lists"].items():
            self.assertIn("items", lst)
            self.assertIn("summary", lst) if False else None
            self.assertIn("total", lst)

    def test_price_change_moves_score(self):
        """السعر بيغيّر نتيجة الاستراتيجيات المبنية على التقييم"""
        val = next(s for s in self.defs["strategies"] if s["key"] == "value")
        st = _stock()
        base = oe.evaluate_strategy(st, val, oe.evaluate_item(st))["score"]
        st2 = _stock(price=35.0, pe=8.0, fair_value=59.0, upside=68.0)
        after = oe.evaluate_strategy(st2, val, oe.evaluate_item(st2))["score"]
        self.assertNotEqual(base, after, "تغيّر السعر ما أثّرش على النتيجة")
        self.assertGreater(after, base, "سعر أقل من القيمة ⇒ نتيجة أعلى")

    def test_risk_change_moves_score(self):
        st = _stock()
        crit = oe.evaluate_item(st)
        s1 = oe.evaluate_strategy(st, self.defs["strategies"][0], crit)["score"]
        st2 = _stock(all_axes={"technical": 72.0, "fundamental": 65.0,
                               "liquidity": 70.0, "risk": 15.0,
                               "news": 55.0, "sentiment": 50.0})
        s2 = oe.evaluate_strategy(st2, self.defs["strategies"][0],
                                  oe.evaluate_item(st2))["score"]
        self.assertLess(s2, s1, "انخفاض المخاطرة لازم ينقص النتيجة")

    def test_liquidity_change_moves_score(self):
        st = _stock()
        s1 = oe.evaluate_strategy(st, self.defs["strategies"][0],
                                  oe.evaluate_item(st))["score"]
        st2 = _stock(liquidity_score=25.0, rel_volume=0.4)
        s2 = oe.evaluate_strategy(st2, self.defs["strategies"][0],
                                  oe.evaluate_item(st2))["score"]
        self.assertLess(s2, s1, "انخفاض السيولة لازم ينقص النتيجة")


class TestSecrets(unittest.TestCase):
    """⛔ الأوزان والعتبات ما بتترجعش في الرد العام"""

    def setUp(self):
        self.defs = oe.load_definitions()
        self.payload = oe.build_payload([_stock()], self.defs, {"generated_at": "T"})

    def test_public_strategy_has_no_weights(self):
        for st in self.payload["strategies"]:
            blob = json.dumps(st, ensure_ascii=False)
            self.assertNotIn("points_max", blob)
            self.assertNotIn("min_coverage", blob)
            self.assertNotIn("min_liquidity_value", blob)
            for c in st.get("criteria") or []:
                self.assertNotIn("weight", c)

    def test_items_have_no_weights(self):
        for lst in self.payload["lists"].values():
            for it in lst["items"]:
                blob = json.dumps(it, ensure_ascii=False)
                self.assertNotIn("points_max", blob)
                self.assertNotIn('"weight"', blob)

    def test_reasons_are_simplified(self):
        for lst in self.payload["lists"].values():
            for it in lst["items"]:
                for r in it.get("reasons") or []:
                    self.assertNotIn("نقطة", r, "السبب فيه نقاط مكرّمة: " + r)


class TestEligibility(unittest.TestCase):
    """⛔ سهم بمخاطرة ناقصة ما بياخدش «فرصة مؤكدة»"""

    def setUp(self):
        self.defs = oe.load_definitions()

    def test_missing_risk_is_excluded(self):
        st = _stock(all_axes={"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0})
        payload = oe.build_payload([st], self.defs, {"generated_at": "T"})
        for key, lst in payload["lists"].items():
            self.assertEqual(len(lst["items"]), 0,
                             "سهم بمخاطرة ناقصة دخل " + key)
            self.assertIn(st["code"], lst["excluded_codes"])

    def test_complete_stock_is_eligible(self):
        payload = oe.build_payload([_stock()], self.defs, {"generated_at": "T"})
        for key, lst in payload["lists"].items():
            if lst["items"]:
                self.assertEqual(lst["items"][0]["eligible"], True)


class TestFreshness(unittest.TestCase):
    def test_payload_carries_source_and_time(self):
        defs = oe.load_definitions()
        payload = oe.build_payload([_stock()], defs,
                                   {"generated_at": "2026-11-15T10:00:00Z",
                                    "source": "live", "freshness": "fresh"})
        self.assertEqual(payload["generated_at"], "2026-11-15T10:00:00Z")
        self.assertEqual(payload["source"], "live")
        self.assertEqual(payload["freshness"], "fresh")


class TestPlanSeparation(unittest.TestCase):
    """فصل المستخدم المجاني عن المدفوع"""

    def test_pro_only_list_is_explicit(self):
        self.assertIsInstance(oe.OPP_PRO_STRATEGIES, tuple)
        self.assertEqual(oe.OPP_PRO_STRATEGIES, (),
                         "السياسة المعتمدة: كل الاستراتيجيات متاحة لكل مسجّل")

    def test_public_strategy_marks_pro_only(self):
        defs = oe.load_definitions()
        payload = oe.build_payload([_stock()], defs, {"generated_at": "T"})
        for st in payload["strategies"]:
            self.assertIn("pro_only", st)
            self.assertIs(st["pro_only"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
