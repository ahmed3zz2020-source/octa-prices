#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ عقود محرّك الفرص الحي عبر الـAPI (١٥ نوفمبر ٢٠٢٦).

⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
📌 التشغيل:  python3 test_opp_api01.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_oppapi_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-oppapi-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-oppapi-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

from pathlib import Path  # noqa: E402

import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"

DEV = "d" * 64
PIN = "1122"
EMAIL = "oppapi.user@example.test"


def mk_user():
    uid = "oppapi-uid"
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(DEV)
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = {
            "id": uid, "name": "مستخدم اختبار", "email": EMAIL,
            "pin_hash": up._pin_hash(PIN, salt), "pin_salt": salt,
            "pin_idx": up._pin_index(PIN), "pin_idx_id": up._PIN_PEPPER_ID,
            "token_epoch": 0, "created": 0,
            "bio_hash": dev_hash, "bio_hashes": [dev_hash],
            "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
        }
        up._save_users(users)


def auth_headers(client):
    r = client.post("/api/auth/pin/login",
                    json={"pin": PIN, "device": DEV},
                    headers={"X-Forwarded-For": "10.0.0.1"})
    body = r.get_json() or {}
    tok = body.get("token") or body.get("access_token")
    if not tok:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    return {"Authorization": "Bearer " + tok}


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


class TestOppApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mk_user()

    def setUp(self):
        import opp_engine as oe
        self.old = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["opp"] = oe.build_payload(
            [_stock(), _stock("BBB", all_axes={"technical": 72.0, "fundamental": 65.0,
                                               "liquidity": 70.0})],
            None, {"generated_at": "2026-11-15T10:00:00Z", "source": "live",
                   "freshness": "closed"})

    def tearDown(self):
        up.LIVE_DATA["opp"] = self.old

    def _c(self):
        c = up.app.test_client()
        return c, auth_headers(c)

    def test_anonymous_is_blocked(self):
        c = up.app.test_client()
        for path in ("/api/opp/strategies", "/api/opp/summary",
                     "/api/opp/list/swing"):
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path + " مش محمي")

    def test_strategies_returns_nine_without_secrets(self):
        c, h = self._c()
        r = c.get("/api/opp/strategies", headers=h)
        self.assertEqual(r.status_code, 200)
        body = r.get_json() or {}
        self.assertEqual(len(body.get("strategies") or []), 9)
        blob = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("points_max", blob)
        self.assertNotIn("min_coverage", blob)
        self.assertNotIn("min_liquidity_value", blob)

    def test_list_returns_items(self):
        c, h = self._c()
        body = c.get("/api/opp/list/swing", headers=h).get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertIn("items", body)
        self.assertEqual(body.get("source"), "live")
        self.assertEqual(body.get("generated_at"), "2026-11-15T10:00:00Z")

    def test_list_unknown_strategy_404(self):
        c, h = self._c()
        r = c.get("/api/opp/list/nope", headers=h)
        self.assertEqual(r.status_code, 404)

    def test_detail_and_explain(self):
        c, h = self._c()
        d = c.get("/api/opp/detail/swing/AAA", headers=h).get_json() or {}
        self.assertTrue(d.get("ok"))
        self.assertEqual(d["code"], "AAA")
        e = c.get("/api/opp/explain/swing/AAA", headers=h).get_json() or {}
        self.assertTrue(e.get("ok"))
        self.assertIn("criteria", e)
        blob = json.dumps(e, ensure_ascii=False)
        self.assertNotIn("points_max", blob)

    def test_summary(self):
        c, h = self._c()
        body = c.get("/api/opp/summary", headers=h).get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(len(body.get("strategies") or []), 9)

    def test_missing_risk_stock_is_not_a_confirmed_opportunity(self):
        c, h = self._c()
        body = c.get("/api/opp/list/swing", headers=h).get_json() or {}
        codes = [i["code"] for i in body.get("items") or []]
        self.assertNotIn("BBB", codes, "سهم بمخاطرة ناقصة ظهر كفرصة مؤكدة")
        self.assertIn("BBB", (body.get("summary") or {}).get("excluded_codes") or [])


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
