#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٧ — R17-P1: **«live» لازم دليل صريح**.

📌 **العيب (من المراجعة النهائية)**:
   `build_payload()` كان بيعمل `_dataset_stale` من
   `("stale", "unavailable")` ⇒ لو حداثة الدفعة **unknown** (مافيش دليل)
   ⇒ `_row_stale = False` ⇒ الصف بيتختم **`data_state="live"`**
   ⇒ ادعاء «بيانات حديثة» من غير أي دليل.

⛔ **الإصلاح**:
   · «live» ⇔ الحداثة العامة **fresh صراحةً** + السهم مش من الكاش.
   · غير كده ⇒ «stale» (قديم/مافيش جلب) أو **«unknown»** (مافيش دليل).
   · وصف السعر كمان بيمنع «سعر التداول الآن» في حالة «unknown».

📌 **الاختبار السالب الإلزامي**: دفعة بحالة «unknown» + سهم مؤهل غير مخزّن
   ⇒ الصف ما يقولش «live».

📌 التشغيل: python test_round17_p1_unknown_state.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_p1_tmp_%d" % os.getpid())
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


def _epoch(iso):
    """⛔ تحويل ISO ⇒ epoch (توقيت ثابت للاختبارات)."""
    import datetime
    return datetime.datetime.fromisoformat(
        iso.replace("Z", "+00:00")).timestamp()


def _meta(dataset_state, market_phase="open", price_ts=None):
    now = time.time()
    fresh = {"freshness": dataset_state, "data_state": dataset_state,
             "coverage_status": "complete", "coverage_acceptable": True,
             "age_seconds": 30}
    return {
        "generated_at": NOW, "source": "live",
        # ⛔ وقت مرجعي ثابت ⇒ عمر السعر محسوب صح (مش حسب ساعة الجهاز)
        "now": _epoch(NOW),
        "market_phase": market_phase,
        "session_date": SESSION,
        "data_freshness": fresh,
        "sources": [{"source": "TradingView Scanner", "as_of": NOW}],
    }


def _rows(payload):
    out = []
    for lst in (payload.get("lists") or {}).values():
        out.extend(lst.get("items") or [])
    return out


class TestP1ExplicitFreshness(unittest.TestCase):
    """⛔ R17-P1 — «live» بس مع دليل صريح."""

    def test_unknown_dataset_is_not_live(self):
        """⛔ السالب: حداثة الدفعة unknown ⇒ ممنوع «live»."""
        st = _stock("UNK1")
        p = oe.build_payload([st], None, _meta("unknown"))
        rows = _rows(p)
        self.assertTrue(rows, "مفيش صفوف في الـpayload")
        for r in rows:
            self.assertNotEqual(r.get("data_state"), "live",
                                "⛔ صف اتختم live مع مافيش دليل حداثة")
            self.assertEqual(r.get("data_state"), "unknown",
                             "⛔ الحالة الآمنة المفقودة")
            self.assertEqual(r.get("stale_reason"), "dataset_unknown")

    def test_unknown_dataset_has_no_now_price_claim(self):
        """⛔ مافيش دليل ⇒ ممنوع «سعر التداول الآن»."""
        st = _stock("UNK2", price_ts=NOW, price_session_date=SESSION)
        p = oe.build_payload([st], None, _meta("unknown"))
        for r in _rows(p):
            self.assertNotEqual(r.get("price_label"), "سعر التداول الآن",
                                "⛔ سعر اتسم «الآن» من غير دليل حداثة")

    def test_missing_freshness_evidence_is_unknown(self):
        """⛔ مافيش meta للحداثة خالص ⇒ safe state (مش live)."""
        st = _stock("UNK3")
        p = oe.build_payload([st], None, {"generated_at": NOW, "source": "live"})
        for r in _rows(p):
            self.assertNotEqual(r.get("data_state"), "live",
                                "⛔ صف اتختم live من غير أي دليل")

    def test_fresh_dataset_is_live(self):
        """⛔ مفيش ارتجاع: حداثة fresh + سهم مش مخزّن ⇒ «live»."""
        st = _stock("FR1")
        p = oe.build_payload([st], None, _meta("fresh"))
        rows = _rows(p)
        self.assertTrue(rows, "مفيش صفوف في الـpayload")
        for r in rows:
            self.assertEqual(r.get("data_state"), "live",
                             "⛔ صف اتختم مش live مع حداثة واضحة")
            self.assertIsNone(r.get("stale_reason"))

    def test_stale_dataset_is_stale(self):
        """⛔ مفيش ارتجاع: دفعة قديمة ⇒ «stale»."""
        st = _stock("ST1")
        p = oe.build_payload([st], None, _meta("stale"))
        for r in _rows(p):
            self.assertEqual(r.get("data_state"), "stale")
            self.assertEqual(r.get("stale_reason"), "dataset_stale")

    def test_unavailable_dataset_is_stale(self):
        """⛔ مفيش ارتجاع: مافيش جلب ناجح ⇒ «stale»."""
        st = _stock("UN1")
        p = oe.build_payload([st], None, _meta("unavailable"))
        for r in _rows(p):
            self.assertEqual(r.get("data_state"), "stale")
            self.assertEqual(r.get("stale_reason"), "dataset_unavailable")

    def test_cached_item_in_fresh_dataset_is_stale(self):
        """⛔ مفيش ارتجاع: سهم من الكاش يفضل قديم."""
        st = _stock("CA1", stale=True, stale_ts="2026-11-16T22:00:00Z")
        p = oe.build_payload([st], None, _meta("fresh"))
        for r in _rows(p):
            self.assertEqual(r.get("data_state"), "stale")
            self.assertEqual(r.get("stale_reason"), "item_cache")

    def test_price_label_blocks_now_for_unknown_state(self):
        """⛔ الدالة نفسها: data_state=unknown ⇒ ممنوع «الآن»."""
        out = oe.price_label_for(
            "open", False, data_state="unknown",
            price_time_source="source", price_age_seconds=60,
            price_session_date=SESSION, session_date=SESSION)
        self.assertNotEqual(out, "سعر التداول الآن",
                            "⛔ «الآن» من غير دليل حداثة")
        self.assertEqual(out, "آخر سعر معروف")


if __name__ == "__main__":
    unittest.main(verbosity=2)
