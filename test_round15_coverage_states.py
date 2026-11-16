#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٥ — التغطية المختلطة: ٩٠٪ محدّث + ١٠٪ قديم (البند ٥).

📌 ملاحظة المالك: «تغطية مقبولة لكنها غير كاملة» لازم تكون **مميّزة**
   عن «تغطية جزئية» وعن «بيانات قديمة/غير متاحة» — والواجهة **ما
   تعرضش كل الأسهم باعتبارها محدثة**.

📌 المطلوب مقيس هنا:
   ① ٩٠٪ من الأسهم اتحدّثوا + ١٠٪ أسعارهم قديمة:
      - حالة الحداثة = مقبولة (مش partial)
      - الأسهم القديمة `data_state='stale'` و `data_received_at=None`
      - الأسهم المحدّثة `data_state='live'`
   ② التغطية الجزئية (١٪) ⇒ `partial` (وليس «مقبولة»).
   ③ مافيش جلب ناجح ⇒ `unavailable` (أولوية على partial).
   ④ **مافيش** مسار يخلّيOld سعراً appears كأنه محدّث (negative proof على الحزمة).

📌 التشغيل: python test_round15_coverage_states.py
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r15c_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R15-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R15-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402


def _stock(code, **kw):
    st = {
        "code": code, "name": "سهم " + code, "sector": "صناعة",
        "price": 100.0, "change": 1.0,
        "ts": "2026-11-17T10:00:00Z",
        "data_quality": 0.8, "volatility": 1.2, "rel_volume": 0.9,
        "tv_rating": 0.2, "beta": 0.6, "div_yield": 0.01,
        "mkt_cap": 1e9, "pe": 12.0, "pb": 1.4,
        "roe": 0.18, "de_ratio": 0.4, "net_margin": 0.2,
        "op_margin": 0.25, "eps": 3.0, "revenue": 5e8,
        "perf_w": 1.0, "perf_1m": 2.0, "perf_3m": 3.0,
        "perf_6m": 4.0, "perf_y": 5.0,
        "all_axes": {"technical": 70.0, "fundamental": 60.0,
                     "liquidity": 65.0, "risk": 55.0},
        "technical_signal": "صاعد",
        "volume": 5_000_000.0,
    }
    st.update(kw)
    return st


def _payload(stocks, phase="open"):
    p = oe.build_payload(stocks, None, {"market_phase": phase, "source": "live"})
    items = {}
    for k, lst in (p.get("lists") or {}).items():
        for it in (lst.get("items") or []):
            items[it.get("code")] = it
    return p, items


class TestMixedCoverage(unittest.TestCase):
    """① ٩٠٪ محدّث + ١٠٪ قديم."""

    def test_mixed_coverage_states(self):
        stocks = [_stock("F%02d" % i) for i in range(9)]
        stocks += [_stock("S%02d" % i, stale=True,
                          stale_ts="2026-11-15T09:00:00Z",
                          ts="2026-11-15T09:00:00Z") for i in range(1)]
        _p, items = _payload(stocks)
        fresh = [i for i in items.values() if i.get("data_state") == "live"]
        stale = [i for i in items.values() if i.get("data_state") == "stale"]
        self.assertTrue(fresh, "مافيش أسهم محدّثة")
        self.assertTrue(stale, "مافيش أسهم قديمة (العلامة اتقفلت!)")
        for it in stale:
            self.assertIsNone(it.get("data_received_at"),
                              "ال-old سعر- اتسجلله وقت تحديث ⇒ ادعاء تحديث")
            self.assertEqual(it.get("price_label"), "آخر سعر معروف")
        for it in fresh:
            self.assertTrue(it.get("data_received_at"))

    def test_coverage_90_is_acceptable_not_partial(self):
        """⛔ ٩٠٪ = مقبولة (مش partial)."""
        st = oe.freshness_state(last_success_at=1700000000, market_phase="open",
                                coverage=90.0, requested=10, updated=9)
        self.assertNotEqual(st["freshness"], "partial")
        self.assertEqual(st["updated"], 9)
        self.assertEqual(st["missing"], 1)

    def test_partial_coverage_is_partial(self):
        st = oe.freshness_state(last_success_at=1700000000, market_phase="open",
                                coverage=10.0, requested=10, updated=1)
        self.assertEqual(st["freshness"], "partial")
        self.assertEqual(st["missing"], 9)

    def test_unavailable_wins_over_partial(self):
        st = oe.freshness_state(last_success_at=None, market_phase="open",
                                coverage=1.0, requested=10, updated=1)
        self.assertEqual(st["freshness"], "unavailable")

    def test_stale_source_timestamp_not_misused(self):
        """⛔ stocks القديمة ما بتاخدش «وقت تحديث» من وقت جلبها."""
        _p, items = _payload([_stock("OLD", stale=True,
                                     stale_ts="2026-11-15T09:00:00Z",
                                     ts="2026-11-16T09:00:00Z")])
        it = items.get("OLD")
        self.assertIsNotNone(it, "مافيش الصنف OLD")
        self.assertIsNone(it.get("data_received_at"))
        self.assertEqual(it.get("source_as_of"), "2026-11-15T09:00:00Z")
        self.assertNotEqual(it.get("price_label"), "سعر التداول الآن")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
