#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٧ — R17-V2-04: **صلاحية وقت الرد** (مش وقت الإنشاء).

📌 **العيب (برهان مستقل فاشل على HEAD)**:
   `update_prices._opp_payload()` كانت ترجّع النسخة المخزّنة كما هي ⇒
   لو دورة التحديث توقفت، النسخة كانت لسه بتقول «fresh» وسعر
   «سعر التداول الآن» وبتار ساعات ⇒ **ادعاء كاذب للمستخدم**.

⛔ **الإصلاح**:
   · `opp_engine.revalidate_payload()` — إعادة تقييم الحداثة **وقت تقديم
     النسخة** (العمر من `last_success_at` مقابل الوقت الحالي).
   · «stale»/«unavailable» ⇒ **نسخة مشتقة**: `freshness` · `data_state` ·
     `age_seconds` · وسم كل صف (`data_state`+`stale_reason`) · وصف السعر ·
     ملخّص الحداثة.
   · ⛔ النسخة المشتركة (LIVE_DATA) ما بتتعدّلش أبداً.
   · ⛔ فشل إعادة التقييم ⇒ `None` ⇒ 503 (fail-closed، مش «حديثة»).

📌 التشغيل: python test_round17_v2_04_payload_ttl.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_v204_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402
import _stub_env  # noqa: E402

_stub_env.install()
import update_prices as up  # noqa: E402


def _stock(code="AAA", **kw):
    """سهم اصطناعي مأهّل (الشريح مستعمل من الجولة المراجعة)."""
    d = {
        "code": code, "name": "سهم اختبار", "sector": "صناعة",
        "price": 50.0, "change": 1.2, "technical_score": 72.0,
        "technical_signal": "صاعد", "fund_score": 65.0,
        "liquidity_score": 70.0, "news_score": 55.0,
        "sentiment_score": 50.0, "safety_score": 64.0,
        "rsi": 52.0, "perf_1m": 6.0, "perf_3m": 14.0,
        "roe": 18.0, "net_margin": 12.0, "de_ratio": 35.0,
        "pe": 12.0, "pb": 1.4, "eps": 4.2, "div_yield": 6.0,
        "mkt_cap": 12e9, "rel_volume": 1.3, "volume": 900000,
        "vol_5": 880000, "vol_60": 850000,
        "beta": 0.9, "volatility": 28.0, "vol1y": 30.0, "mdd1y": -18.0,
        "cfo": 900.0, "ni": 700.0, "upside": 18.0, "fair_value": 59.0,
        "ts": "2026-11-17T10:00:00Z",
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


def _iso(ts):
    """تحويل epoch → ISO بتوقت محدد."""
    import datetime
    return (datetime.datetime.utcfromtimestamp(ts)
            .strftime("%Y-%m-%dT%H:%M:%SZ"))


def _payload(now_ts):
    fresh = oe.freshness_state(now_ts, "open", now_ts + 1,
                               coverage=100, requested=1, updated=1)
    return oe.build_payload(
        [_stock(price_ts=_iso(now_ts), session_date=_iso(now_ts)[:10])], None,
        {"market_phase": "open", "now": now_ts + 1, "freshness": "fresh",
         "data_freshness": fresh, "last_success_at": now_ts,
         "generated_at": _iso(now_ts),
         "session_date": _iso(now_ts)[:10]})


class TestV204PayloadTTL(unittest.TestCase):
    """⛔ R17-V2-04 — النسخة المخزّنة ما تقدّمش «fresh» بعد انتهاء صلاحيتها."""

    def test_expired_payload_is_not_served_as_fresh(self):
        """⛔ بعد انتهاء العمر ⇒ ممنوع «fresh» (البرهان الأصلي للمراجع)."""
        t = 1794909600.0
        payload = _payload(t)
        self.assertEqual(payload.get("freshness"), "fresh")
        self.assertTrue(any(x.get("data_state") == "live"
                            for v in payload["lists"].values()
                            for x in v["items"]))
        self.assertTrue(any("الآن" in str(x.get("price_label") or "")
                            for v in payload["lists"].values()
                            for x in v["items"]),
                        "⛔ الوصف لم يكن لحظي في البناء")
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + oe.FRESH_MAX_AGE_OPEN + 10):
            served = up._opp_payload()
        self.assertIsNotNone(served)
        self.assertNotEqual(served.get("freshness"), "fresh",
                            "⛔ نسخة منتهية الصلاحية اتقدّمت كـ«fresh»")

    def test_fresh_payload_is_served_unchanged(self):
        """✅ لسه داخل العمر ⇒ النسخة كما هي."""
        t = 1794909600.0
        payload = _payload(t)
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + 10):
            served = up._opp_payload()
        self.assertEqual(served.get("freshness"), "fresh")

    def test_expired_rows_are_marked_stale(self):
        """⛔ الصفوف ما تبقىش «live» بعد انتهاء الصلاحية."""
        t = 1794909600.0
        payload = _payload(t)
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + oe.FRESH_MAX_AGE_OPEN + 10):
            served = up._opp_payload()
        for _k, _v in (served.get("lists") or {}).items():
            for _row in _v.get("items") or []:
                self.assertNotEqual(_row.get("data_state"), "live",
                                    "⛔ صف قديم اتقدّم كـ«live»")
                self.assertEqual(_row.get("stale_reason"), "dataset_stale")

    def test_expired_price_label_is_not_live(self):
        """⛔ وصف السعر ما يبقاش ادعاء لحظي بعد انتهاء الصلاحية."""
        t = 1794909600.0
        payload = _payload(t)
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + oe.FRESH_MAX_AGE_OPEN + 10):
            served = up._opp_payload()
        for _k, _v in (served.get("lists") or {}).items():
            for _row in _v.get("items") or []:
                self.assertNotIn("الآن", str(_row.get("price_label") or ""),
                                 "⛔ وصف سعر لحظي لنسخة منتهية")

    def test_shared_payload_is_not_mutated(self):
        """⛔ النسخة المشتركة في الذاكرة ما بتتعدّلش."""
        t = 1794909600.0
        payload = _payload(t)
        before = payload.get("freshness")
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + oe.FRESH_MAX_AGE_OPEN + 10):
            up._opp_payload()
        self.assertEqual(payload.get("freshness"), before,
                         "⛔ النسخة المشتركة اتعدّلت ⇒ ارتجاع")

    def test_missing_last_success_is_unavailable(self):
        """✅ مافيش دليل حداثة ⇒ «غير متاحة» (مش «fresh»)."""
        payload = _payload(1794909600.0)
        payload.pop("last_success_at", None)
        payload.get("data_freshness", {}).pop("last_success_at", None)
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=1794909700.0):
            served = up._opp_payload()
        self.assertNotEqual(served.get("freshness"), "fresh")

    def test_revalidate_reports_age(self):
        """✅ العمر بيتحسب وقت الرد."""
        t = 1794909600.0
        payload = _payload(t)
        with patch.dict(up.LIVE_DATA, {"opp": payload}), \
                patch("time.time", return_value=t + oe.FRESH_MAX_AGE_OPEN + 10):
            served = up._opp_payload()
        self.assertIsNotNone(served.get("age_seconds"))
        self.assertGreaterEqual(served.get("age_seconds"),
                                oe.FRESH_MAX_AGE_OPEN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
