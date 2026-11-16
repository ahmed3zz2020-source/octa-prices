#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ الجولة ١٦ — ربط العقد: حدود الـquery + نشر حداثة/تغطية جديدة.

📌 بيغطي:
   ① حدود الـquery **قبل** المصادقة (حماية DoS قبل أي شغل).
   ② المسارات بتنشر `coverage_status` + `data_state` + `freshness_summary_ar`
      ⇒ من غيرها الواجهة مش هتعرف «تغطية جزئية».
   ③ المسارات القديمة مقفولة على الزائر ومافيش أوزان في الرد.
   ④ صف الفرصة فيه `price_age_seconds` + `price_age_label_ar`.

⛔ بيانات صناعية · مافيش شبكة · مافيش إنتاج.
📌 التشغيل: python3 test_round16_contract_wiring.py
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# ⛔ بيئة معزولة — أسرار صناعية (مافيش سر حقيقي · مافيش إنتاج)
TMP = tempfile.mkdtemp(prefix="r16wiring_")
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "R16-WIRING-SECRET"
os.environ["OCTA_PIN_PEPPER"] = "R16-WIRING-PEPPER"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["OCTA_RATE_MULT"] = "300"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"

import update_prices as up  # noqa: E402
import opp_engine as oe  # noqa: E402


def _stock(code="R16A", **kw):
    """سهم صناعي كامل (مفيش بيانات حيّة)."""
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
        "ts": "2026-11-16T10:00:00Z",
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


def _payload():
    """⛔ payload صناعي (مافيش بيانات حيّة · مافيش شبكة)."""
    import time
    now = time.time()
    meta = {
        "generated_at": "2026-11-16T10:00:00Z", "source": "live",
        "market_phase": "open", "source_as_of": "2026-11-16T09:59:00Z",
        "last_success_at": now - 30,
        "data_freshness": oe.freshness_state(now - 30, "open", now),
        "sources": [{"source": "Test", "as_of": "2026-11-16T09:59:00Z"}],
    }
    return oe.build_payload([_stock()], None, meta)

CLIENT = None


def _setUp():
    global CLIENT
    if CLIENT is None:
        up.app.config["TESTING"] = True
        CLIENT = up.app.test_client()


def _all_keys(obj, acc=None, depth=0):
    if acc is None:
        acc = set()
    if depth > 12:
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(str(k))
            _all_keys(v, acc, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:60]:
            _all_keys(v, acc, depth + 1)
    return acc


class TestQueryLimitsBeforeAuth(unittest.TestCase):
    """⛔ حدود الـquery تتفحص **قبل** المصادقة."""

    def setUp(self):
        _setUp()
        self._orig = up.require_user
        up.require_user = lambda: None      # ⛔ مافيش جلسة

    def tearDown(self):
        up.require_user = self._orig

    def test_long_query_is_400_not_401_when_anonymous(self):
        """⛔ الطلب الكبير يترفض بـ400 (حدّ) مش 401 (جلسة) ⇒
        ⛔ الفحص الرخيص بيحصل قبل بحث التوكن."""
        r = CLIENT.get("/api/rank?note=" + "A" * 20000)
        self.assertEqual(r.status_code, 400, r.status_code)
        body = r.get_json() or {}
        self.assertEqual(body.get("why"), "query_too_long", body.get("why"))
        self.assertNotIn("A" * 200, r.get_data(as_text=True))

    def test_too_many_params_is_400_before_auth(self):
        q = "&".join("k%d=v" % i for i in range(200))
        r = CLIENT.get("/api/rank?" + q)
        self.assertEqual(r.status_code, 400, r.status_code)
        self.assertEqual((r.get_json() or {}).get("why"), "too_many_params")

    def test_long_param_name_is_400_before_auth(self):
        r = CLIENT.get("/api/rank?" + ("n" * 500) + "=1")
        self.assertEqual(r.status_code, 400, r.status_code)
        self.assertEqual((r.get_json() or {}).get("why"), "param_name_too_long")

    def test_normal_query_still_reaches_auth(self):
        """⛔ الحد مش بيقصّ الطلبات العادية ⇒ 401 (مافيش جلسة) زي ما كان."""
        r = CLIENT.get("/api/rank?code=S00")
        self.assertEqual(r.status_code, 401, r.status_code)


class TestFreshnessContractWiring(unittest.TestCase):
    """⛔ المسارات بتنشر عقد الحداثة الجديد."""

    def setUp(self):
        _setUp()
        self._orig = up.require_user
        up.require_user = lambda: {"uid": "r16", "email": "r16@test.local"}
        self._orig_payload = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["opp"] = _payload()

    def tearDown(self):
        up.require_user = self._orig
        if self._orig_payload is None:
            up.LIVE_DATA.pop("opp", None)
        else:
            up.LIVE_DATA["opp"] = self._orig_payload

    def test_opp_strategies_publishes_coverage_and_data_state(self):
        r = CLIENT.get("/api/opp/strategies")
        self.assertEqual(r.status_code, 200, r.status_code)
        d = r.get_json() or {}
        self.assertIn("coverage_status", d, "مافيش coverage_status")
        self.assertIn("data_state", d, "مافيش data_state")
        self.assertNotEqual(d.get("freshness"), "partial",
                            "freshness رجع partial ⇒ خلط مع التغطية")

    def test_opp_list_publishes_coverage_and_data_state(self):
        """⛔ المسار اللي بتقراه الواجهة (list) هو اللي لازم ينشر العقد."""
        payload = up._opp_payload()
        self.assertIsNotNone(payload, "مافيش payload")
        key = None
        for lst in (payload.get("lists") or {}).values():
            key = lst.get("strategy")
            break
        if not key:
            self.skipTest("مافيش استراتيجية في الـpayload")
        r = CLIENT.get("/api/opp/list/" + key)
        self.assertEqual(r.status_code, 200, r.status_code)
        d = r.get_json() or {}
        self.assertIn("coverage_status", d,
                      "مافيش coverage_status في /api/opp/list ⇒ الواجهة مش هتعرف التغطية")
        self.assertIn("data_state", d, "مافيش data_state في /api/opp/list")
        self.assertNotEqual(d.get("freshness"), "partial")

    def test_rows_carry_price_age(self):
        payload = up._opp_payload()
        self.assertIsNotNone(payload, "مافيش payload")
        rows = []
        for lst in (payload.get("lists") or {}).values():
            rows.extend((lst.get("items") or []))
        if not rows:
            self.skipTest("مافيش صفوف")
        for r0 in rows[:20]:
            self.assertIn("price_age_seconds", r0, "مافيش price_age_seconds")
            self.assertIn("price_age_label_ar", r0, "مافيش price_age_label_ar")
            self.assertIn("price_session_date", r0, "مافيش price_session_date")


class TestLegacyRoutesLocked(unittest.TestCase):
    """⛔ المسارات القديمة: مقفولة على الزائر + مافيش أوزان."""

    def setUp(self):
        _setUp()
        self._orig = up.require_user
        up.require_user = lambda: None

    def tearDown(self):
        up.require_user = self._orig

    def test_strategies_list_is_401_anonymous(self):
        r = CLIENT.get("/api/strategies")
        self.assertEqual(r.status_code, 401, r.status_code)
        self.assertNotIn("weights", r.get_data(as_text=True).lower())

    def test_strategy_detail_is_401_anonymous(self):
        r = CLIENT.get("/api/strategy/S00/balanced")
        self.assertEqual(r.status_code, 401, r.status_code)
        self.assertNotIn("weights", r.get_data(as_text=True).lower())


class TestLoggedInLegacyRoutes(unittest.TestCase):
    """⛔ المستخدم المسجّل: مافيش أوزان في أي عمق."""

    def setUp(self):
        _setUp()
        self._orig = up.require_user
        up.require_user = lambda: {"uid": "r16", "email": "r16@test.local"}

    def tearDown(self):
        up.require_user = self._orig

    def test_no_weights_at_any_depth(self):
        for path in ("/api/strategies", "/api/strategy/S00/balanced"):
            r = CLIENT.get(path)
            self.assertIn(r.status_code, (200, 404), "%s => %s" % (path, r.status_code))
            keys = _all_keys(r.get_json() or {})
            bad = sorted(k for k in keys if "weight" in k.lower())
            self.assertEqual(bad, [], "%s كشف أوزان: %s" % (path, bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
