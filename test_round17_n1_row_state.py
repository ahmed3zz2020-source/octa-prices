#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٧ — R16-N1: **اتساق حداثة الصف** مع الحداثة العامة.

📌 **العيب (من مراجعة مستقلة)**:
   `build_payload()` كان بيختم حالة كل صف بـ `item.stale` **وحدها** ⇒
   آخر جلب ناجح من يومين (الحداثة العامة = stale) + سهم مش من الكاش
   ⇒ الصف بيطلع `data_state="live"` ⇒ المستخدم بيشوف «بيانات حديثة»
   وسعر وسمه «سعر التداول الآن» مع إن البيانات قديمة ⇒ **ادعاء كاذب**.

⛔ **الإصلاح**: الصف ما يقدرش يقول «live» إلا لو الحداثة العامة fresh
   **و** السهم نفسه مش من الكاش. غير كده ⇒ `data_state="stale"`
   + `stale_reason` بيقول السبب (item_cache / dataset_stale /
   dataset_unavailable).

📌 **الاختبار السالب الإلزامي**: نفس البيانات بالظبط بس
   `data_freshness.freshness` = stale ⇒ الفشل على الكود القديم.

📌 التشغيل: python test_round17_n1_row_state.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_n1_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402

NOW = "2026-11-17T10:00:00Z"
SESSION = "2026-11-17"


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


def _rows(payload):
    """كل صفوف الاستراتيجيات في الـpayload."""
    out = []
    for lst in (payload.get("lists") or {}).values():
        out.extend(lst.get("items") or [])
    return out


def _meta(freshness, market_phase="closed", age=30, price_ts=None):
    now = time.time()
    fresh = oe.freshness_state(now - age, market_phase, now)
    fresh = dict(fresh)
    fresh["freshness"] = freshness
    fresh["data_state"] = freshness
    if freshness == "unavailable":
        fresh["age_seconds"] = None
    return {
        "generated_at": NOW, "source": "live",
        "market_phase": market_phase,
        "session_date": SESSION,
        "data_freshness": fresh,
        "sources": [{"source": "TradingView Scanner", "as_of": NOW}],
    }


class TestN1RowStateConsistency(unittest.TestCase):
    """⛔ R16-N1 — صف «live» يتagree مع الحداثة العامة."""

    def test_row_not_live_when_dataset_stale(self):
        """⛔ السالب: الدفعة كلها قديمة ⇒ مفيش صف «live»."""
        st = _stock("STALE1")
        p = oe.build_payload([st], None, _meta("stale", age=2 * 86400))
        rows = _rows(p)
        self.assertTrue(rows, "مفيش صفوف في الـpayload")
        for r in rows:
            self.assertNotEqual(
                r.get("data_state"), "live",
                "⛔ صف اتختم live مع إن الحداثة العامة = stale")

    def test_price_label_not_now_when_dataset_stale(self):
        """⛔ السالب: سعر «الآن» ممنوع مع دفعة قديمة."""
        st = _stock("STALE2", price_ts=NOW, price_session_date=SESSION)
        p = oe.build_payload([st], None,
                             _meta("stale", market_phase="open", age=2 * 86400))
        for r in _rows(p):
            self.assertNotEqual(
                r.get("price_label"), "سعر التداول الآن",
                "⛔ سعر اتسم «الآن» مع إن آخر جلب ناجح من يومين")

    def test_row_not_live_when_dataset_unavailable(self):
        """⛔ مافيش جلب ناجح أصلاً ⇒ مفيش صف «live»."""
        st = _stock("UNAV1")
        p = oe.build_payload([st], None, _meta("unavailable"))
        for r in _rows(p):
            self.assertNotEqual(r.get("data_state"), "live",
                                "⛔ صف اتختم live مع إن مافيش جلب ناجح")

    def test_row_live_when_dataset_fresh(self):
        """⛔ مفيش ارتجاع: دفعة حديثة + سهم مش من الكاش ⇒ «live»."""
        st = _stock("FRESH1")
        p = oe.build_payload([st], None, _meta("fresh"))
        rows = _rows(p)
        self.assertTrue(rows, "مفيش صفوف في الـpayload")
        for r in rows:
            self.assertEqual(r.get("data_state"), "live",
                             "صف اتختم stale مع إن الحداثة العامة = fresh")
            self.assertIsNone(r.get("stale_reason"),
                              "سبب قديم اتسجل مع صف حيّ")

    def test_item_cache_stays_stale_with_fresh_dataset(self):
        """⛔ مفيش ارتجاع: سهم من الكاش يفضل قديم."""
        st = _stock("CACHE1", stale=True, stale_ts="2026-11-16T22:00:00Z")
        p = oe.build_payload([st], None, _meta("fresh"))
        for r in _rows(p):
            self.assertEqual(r.get("data_state"), "stale",
                             "⛔ سهم من الكاش اتختم live")
            self.assertEqual(r.get("stale_reason"), "item_cache")

    def test_stale_reason_tells_the_truth(self):
        """⛔ السبب لازم يفرّق: كاش السهم / قدومة الدفعة / مافيش جلب."""
        cases = [
            (_stock("R1", stale=True, stale_ts="2026-11-16T22:00:00Z"),
             "fresh", "item_cache"),
            (_stock("R2"), "stale", "dataset_stale"),
            (_stock("R3"), "unavailable", "dataset_unavailable"),
        ]
        for st, fr, expected in cases:
            p = oe.build_payload([st], None, _meta(fr))
            for r in _rows(p):
                self.assertEqual(r.get("stale_reason"), expected,
                                 "⛔ سبب مختلف عن المتوقع")

    def test_payload_level_state_still_published(self):
        """⛔ مفيش ارتجاع: مستوى الـpayload لسه بينشر الحداثة."""
        p = oe.build_payload([_stock("P1")], None, _meta("fresh"))
        self.assertIn("coverage_status", p)
        self.assertIn("data_state", p)
        self.assertIn("freshness_summary_ar", p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
