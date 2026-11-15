#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ F-20-17 — سقف خصومات الاستراتيجيات (١٥ نوفمبر ٢٠٢٦).

⛔ العيب المقاس: `strategy_score` كان يطرح خصم المخاطر�� **الخام** من
   الدرجة، وبعدين بيصغّر المتغيّرات عند تجاوز السقف 22 ⇒ السقف كان
   بيغيّر التقرير بس مش الدرجة.
   📌 العيّنة المرجعية: conservative · risk=0 · techno 80 · fund 80 ·
      liq 90 · news 45 (افتراضي) · sent 50 · pfit 70
      ⇒ قبل: base=55.6 · final=19.6 · خصم معلن 22 · خصم مؤثر 36
      ⇒ بعد: final=33.6 · خصم مؤثر = معلن = 22

📌 التشغيل:  python3 test_strategy_cap01.py
"""
import ast
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from octa_score import liquidity_score  # noqa: E402,F401


def _isolated_funcs():
    """يستخرج STRATEGIES + strategy_score من AST (بلا استيراد الباك)."""
    src = (HERE / "update_prices.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    picked = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "STRATEGIES":
                    picked.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "strategy_score":
            picked.append(node)
    ns = {}
    exec(compile(ast.Module(body=picked, type_ignores=[]), "<isolated>", "exec"), ns)
    return ns


NS = _isolated_funcs()
SS = NS["STRATEGIES"]
strategy_score = NS["strategy_score"]

ITEM = {"code": "CAP", "name": "سهم", "price": 10.0, "div_yield": 5.0,
        "safety_score": 90, "all_axes": {"risk": 0}}


def _call(strategy="conservative", item=None, tech=80, fund=80, liq=90,
          sent=50, pfit=70):
    it = dict(ITEM if item is None else item)
    return strategy_score(it, strategy, {"score": tech}, {"score": fund},
                          {"score": liq}, {"score": sent}, {"score": pfit})


class TestCapEffective(unittest.TestCase):
    def test_reference_sample(self):
        r = _call()
        self.assertEqual(r["base"], 55.6)
        self.assertEqual(r["score"], 33.6,
                         "الدرجة بعد الإصلاح لازم تكون 33.6 (مش 19.6)")
        self.assertEqual(r["risk_penalty"], -22.0)
        self.assertTrue(r["filters_passed"])

    def test_declared_penalty_matches_effect(self):
        r = _call()
        applied = round(r["base"] - r["score"], 1)
        declared = round(-r["risk_penalty"] - r["liquidity_penalty"], 1)
        self.assertEqual(applied, declared,
                         "الخصم المعلن لازم يساوي الخصم المطبَّق")
        self.assertLessEqual(applied, 22.0)

    def test_cap_boundary(self):
        """خصم خام = 22 بالظبط ⇒ مافيش تحجيم"""
        st = SS["conservative"]
        mult = st["risk_penalty_mult"]
        # مخاطرة = 100 - (22 / (0.18 * mult))
        risk = 100 - (22 / (0.18 * mult))
        item = dict(ITEM)
        item["all_axes"] = {"risk": risk}
        r = _call(item=item)
        self.assertLessEqual(round(r["base"] - r["score"], 1), 22.01)

    def test_below_cap_unchanged(self):
        """خصم تحت السقف ⇒ الدرجة زي ما هي من غير تحجيم"""
        r = _call(strategy="balanced")
        raw = (100 - 0) * 0.18 * SS["balanced"]["risk_penalty_mult"]
        if raw <= 22:
            self.assertAlmostEqual(round(r["base"] - r["score"], 1),
                                   round(raw, 1), places=1)

    def test_filter_penalties_are_separate(self):
        """⛔ عقوبة الفلتر بره سقف الـ22"""
        item = dict(ITEM)
        item["div_yield"] = 0.0          # ⛔ بيكسر شرط عائد التوزيعات
        item["safety_score"] = 10        # ⛔ وكسر شرط الأمان
        r = _call(item=item)
        self.assertIn("filter_penalty", r)
        self.assertLess(r["filter_penalty"], 0)
        declared = round(-r["risk_penalty"] - r["liquidity_penalty"], 1)
        self.assertLessEqual(declared, 22.0,
                             "سقف 22 لازم يخص المخاطرة والسيولة بس")

    def test_score_range(self):
        r = _call()
        self.assertGreaterEqual(r["score"], 0)
        self.assertLessEqual(r["score"], 100)

    def test_weights_unchanged(self):
        """⛔ الأوزان والعتبات ما اتغيّرتش"""
        for k, st in SS.items():
            self.assertEqual(r_sum(st["weights"]), 1.0,
                             "أوزان الاستراتيجية اتغيّرت: " + k)
            self.assertIn("risk_penalty_mult", st)
            self.assertIn("min_liquidity", st)


def r_sum(d):
    return round(sum(d.values()), 3)


class TestSourceGuard(unittest.TestCase):
    """⛔ حارس البنية — يمنع تكرار نفس النمط (الخصم قبل التحجيم)"""

    def _function(self):
        src = (HERE / "update_prices.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "strategy_score":
                return node
        self.fail("strategy_score مش موجودة")

    def test_no_penalty_subtracted_before_cap(self):
        fn = self._function()
        cap_seen = False
        for node in fn.body:
            # الخاصية: مافيش طرح خصم من الدرجة قبل كتلة السقف
            for sub in ast.walk(node):
                if isinstance(sub, ast.AugAssign) and isinstance(sub.op, ast.Sub):
                    tgt = sub.target
                    if isinstance(tgt, ast.Name) and tgt.id == "adj":
                        self.fail("⛔ فيه طرح خصم (adj -=) — السقف لازم يسبق الطرح")
            if isinstance(node, ast.If):
                test_src = ast.dump(node.test)
                if "total_penalty" in test_src:
                    cap_seen = True
        self.assertTrue(cap_seen, "مافيش كتلة سقف (total_penalty) في strategy_score")

    def test_final_is_computed_after_cap(self):
        fn = self._function()
        cap_idx = None
        final_idx = None
        for i, node in enumerate(fn.body):
            if isinstance(node, ast.If) and "total_penalty" in ast.dump(node.test):
                cap_idx = i
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "final":
                        final_idx = i
        self.assertIsNotNone(cap_idx)
        self.assertIsNotNone(final_idx)
        self.assertLess(cap_idx, final_idx,
                        "⛔ الدرجة بتتحسب قبل السقف — السقف مش مطبَّق فعلياً")


if __name__ == "__main__":
    unittest.main(verbosity=2)
