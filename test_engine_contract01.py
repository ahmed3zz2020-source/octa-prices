#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ ENGINE-SAFETY-01 — اختبار العقد وسلامة الاستراتيجيات (١٥ نوفمبر ٢٠٢٦).

⛔ العزل: كل الملفات في مجلد مؤقت · مافيش شبكة · مافيش بيانات حقيقية.
📌 التشغيل:  python3 test_engine_contract01.py
"""
import os
import sys
import json
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_eng01_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-eng01-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-eng01-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"


def _item(code="TEST", **kw):
    d = {"code": code, "name": "سهم اختبار", "price": 10.0,
         "beta": 0.9, "de_ratio": 30.0, "volatility": 25.0,
         "volume": 100000, "mkt_cap": 5e9, "rel_volume": 1.1,
         "vol_5": 100000, "vol_60": 100000}
    d.update(kw)
    return d


# ⛔ مستخدم اختبار في البيئة المعزولة (مافيش بيانات حقيقية)
DEV = "c" * 64
PIN = "9876"
EMAIL = "eng01.user@example.test"


def mk_user():
    uid = "eng01-uid"
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
    return uid


def auth_headers(client):
    r = client.post("/api/auth/pin/login",
                    json={"pin": PIN, "device": DEV},
                    headers={"X-Forwarded-For": "10.0.0.1"})
    body = r.get_json() or {}
    tok = body.get("token") or body.get("access_token")
    if not tok:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    return {"Authorization": "Bearer " + tok}


class TestStrategyNoCrash(unittest.TestCase):
    """F-20-05 — محور None ما يعملش استثناء"""

    def test_none_axis_does_not_throw(self):
        item = _item()
        r = up.strategy_score(item, "balanced",
                              {"score": None}, {"score": 80},
                              {"score": 70}, {"score": 50}, None)
        self.assertIsNotNone(r, "لازم نرجّع نتيجة منظمة مش None")
        self.assertIsNone(r["score"], "الدرجة لازم تكون None (مش رقم مخترع)")
        self.assertEqual(r["decision"], "بيانات غير كافية")
        self.assertFalse(r["filters_passed"])

    def test_unavailable_strategy_has_explicit_status(self):
        item = _item()
        r = up.strategy_score(item, "balanced",
                              {"score": None}, {"score": 80},
                              {"score": 70}, {"score": 50}, None)
        self.assertIn(r["score_status"], ("insufficient_data", "insufficient_risk"))
        self.assertFalse(r["rank_eligible"])
        self.assertTrue(r["missing_axes"])

    def test_all_strategies_keeps_shape(self):
        """⛔ القاموس لازم يفضل موجود بكل الاستراتيجيات"""
        item = _item()
        out = up.score_all_strategies(item, {"score": None}, {"score": 80},
                                      {"score": 70}, {"score": 50}, None)
        self.assertEqual(set(out.keys()), set(up.STRATEGIES.keys()))
        for k, v in out.items():
            self.assertIn("score", v)
            self.assertIn("decision", v)
            self.assertIn("score_status", v)
            self.assertIn("rank_eligible", v)

    def test_missing_risk_not_assigned_default_60(self):
        """⛔ غياب المخاطرة ⇒ مش 60"""
        item = _item()
        item.pop("all_axes", None)
        r = up.strategy_score(item, "balanced", {"score": 80}, {"score": 80},
                              {"score": 70}, {"score": 50}, None)
        self.assertIsNone(r["axes"].get("risk"), "المحور رجع رقم مخترع")
        self.assertEqual(r["score_status"], "insufficient_risk")
        self.assertFalse(r["rank_eligible"])
        self.assertEqual(r["decision"], "بيانات غير كافية")

    def test_valid_strategy_is_eligible(self):
        item = _item()
        item["all_axes"] = {"risk": 70}
        r = up.strategy_score(item, "balanced", {"score": 80}, {"score": 80},
                              {"score": 70}, {"score": 50}, None)
        self.assertIsNotNone(r["score"])
        self.assertEqual(r["score_status"], "ok")
        self.assertTrue(r["rank_eligible"])


class TestRankingEligibility(unittest.TestCase):
    """F-20-04 — الترتيب ما بيقبلش سهم غير مؤهل"""

    @classmethod
    def setUpClass(cls):
        mk_user()

    def setUp(self):
        self._old = list(up.LIVE_DATA.get("egx30", []))

    def tearDown(self):
        up.LIVE_DATA["egx30"] = self._old

    def test_ranking_excludes_ineligible(self):
        up.LIVE_DATA["egx30"] = [
            {"code": "GOOD", "name": "كامل", "final_score": 60.0,
             "decision": "إشارة محايدة", "rank_eligible": True, "score_status": "ok"},
            {"code": "NODATA", "name": "ناقص", "final_score": 90.0,
             "decision": "بيانات غير كافية", "rank_eligible": False,
             "score_status": "insufficient_risk"},
        ]
        client = up.app.test_client()
        hdr = auth_headers(client)
        rv = client.get("/api/ranking", headers=hdr)
        body = rv.get_json() or {}
        codes = [r["code"] for r in body.get("top20", [])]
        self.assertIn("GOOD", codes)
        self.assertNotIn("NODATA", codes,
                         "سهم غير مؤهل دخل قائمة أفضل الأسهم")

    def test_opportunities_excludes_ineligible(self):
        up.LIVE_DATA["egx30"] = [
            {"code": "GOOD", "opportunity_score": 70.0, "opportunity_stage": "مبكرة",
             "rank_eligible": True},
            {"code": "NODATA", "opportunity_score": 95.0, "opportunity_stage": "مبكرة",
             "rank_eligible": False},
        ]
        client = up.app.test_client()
        hdr = auth_headers(client)
        body = (client.get("/api/opportunities", headers=hdr).get_json() or {})
        codes = [r["code"] for r in (body.get("early_opportunities") or [])]
        self.assertNotIn("NODATA", codes, "سهم غير مؤهل دخل قائمة الفرص")
        self.assertIn("GOOD", codes)

    def test_rank_stocks_skips_ineligible(self):
        """⛔ السهم غير المؤهل (بيانات ناقصة) ما يدخلش ترتيب الاستراتيجية.

        📌 الجولة ١٤ (١٧ نوفمبر ٢٠٢٦): مسار الاستراتيجية **بلا fallback**
           ⇒ لازم كل سهم يكون عنده نتيجة في الاستراتيجية.
           ⇒ الاختبار اتحدّث يعكس العقد الجديد (مش سلوك جديد).
        """
        stocks = [
            {"code": "GOOD", "final_score": 50.0, "decision": "إشارة محايدة",
             "rank_eligible": True,
             "strategies": {"balanced": {"name": "متوازن", "score": 50.0,
                                         "decision": "إشارة محايدة",
                                         "filters_passed": True,
                                         "score_status": "ok",
                                         "rank_eligible": True}}},
            {"code": "NODATA", "final_score": 95.0, "decision": "بيانات غير كافية",
             "rank_eligible": False,
             "strategies": {"balanced": {"name": "متوازن", "score": 95.0,
                                         "decision": "بيانات غير كافية",
                                         "filters_passed": True,
                                         "score_status": "ok",
                                         "rank_eligible": False}}},
        ]
        out = up.rank_stocks(stocks, strategy="balanced", limit=10)
        codes = [r["code"] for r in out]
        self.assertIn("GOOD", codes)
        self.assertNotIn("NODATA", codes)

    def test_general_rank_stocks_skips_ineligible(self):
        """⛔ نفس العقد في المسار العام (strategy=None)."""
        stocks = [
            {"code": "GOOD", "final_score": 50.0, "decision": "إشارة محايدة",
             "rank_eligible": True},
            {"code": "NODATA", "final_score": 95.0, "decision": "بيانات غير كافية",
             "rank_eligible": False},
        ]
        out = up.rank_stocks(stocks, strategy=None, limit=10)
        codes = [r["code"] for r in out]
        self.assertIn("GOOD", codes)
        self.assertNotIn("NODATA", codes)


class TestEngineOutputPolicy(unittest.TestCase):
    """الحقول الجديدة ما تسرّبش للزائر"""

    def test_new_fields_are_hidden_for_visitor(self):
        self.assertIn("score_status", up._HIDDEN_KEYS_OUTPUT)
        self.assertIn("rank_eligible", up._HIDDEN_KEYS_OUTPUT)

    def test_hidden_policy_strips_new_fields(self):
        data = {"code": "X", "score_status": "ok", "rank_eligible": True,
                "final_score": 70}
        out = up._hide_outputs(data)
        self.assertNotIn("score_status", out)
        self.assertNotIn("rank_eligible", out)
        self.assertNotIn("final_score", out)
        self.assertIn("code", out)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
