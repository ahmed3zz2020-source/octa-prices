#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٣ — عقد الحداثة + حدود الباقة + أهلية الترتيب (١٦ نوفمبر ٢٠٢٦).

⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
📌 التشغيل:  python3 test_opp_freshness13.py
📌 يُشغَّل كـnegative proof على الكود القديم: لازم يفشل (يكشف العيب).
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_oppfresh_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-oppfresh-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-oppfresh-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

from pathlib import Path  # noqa: E402

import opp_engine as oe  # noqa: E402
import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"

DEV_FREE = "d" * 64
DEV_PRO = "e" * 64
PIN_FREE = "1122"
PIN_PRO = "3333"


def mk_user(uid, email, dev, pin, plan=None):
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(dev)
    with up.USERS_LOCK:
        users = up._load_users()
        rec = {
            "id": uid, "name": "مستخدم اختبار", "email": email,
            "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
            "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
            "token_epoch": 0, "created": 0,
            "bio_hash": dev_hash, "bio_hashes": [dev_hash],
            "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
        }
        if plan:
            rec["plan"] = plan
            rec["plan_until"] = int(time.time()) + 86400
        users[uid] = rec
        up._save_users(users)


def auth_headers(client, pin, dev):
    r = client.post("/api/auth/pin/login",
                    json={"pin": pin, "device": dev},
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
        "ts": "2026-11-16T10:00:00Z",
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


def _many(n=8):
    out = []
    for i in range(n):
        out.append(_stock("S%02d" % i, all_axes={
            "technical": 70.0 + i, "fundamental": 60.0 + i, "liquidity": 65.0 + i,
            "risk": 60.0 + i, "news": 50.0 + i, "sentiment": 50.0 + i}))
    return out


class TestFreshnessContract(unittest.TestCase):
    """⛔ عقد الحداثة: «السوق مغلق» ⇏ «البيانات حديثة»."""

    def test_no_successful_fetch_is_unavailable(self):
        st = oe.freshness_state(None, "open")
        self.assertEqual(st["freshness"], "unavailable")
        self.assertIsNone(st["age_seconds"])

    def test_recent_fetch_is_fresh(self):
        now = time.time()
        st = oe.freshness_state(now - 60, "open", now)
        self.assertEqual(st["freshness"], "fresh")
        self.assertEqual(st["age_seconds"], 60)

    def test_old_fetch_during_open_is_stale(self):
        now = time.time()
        st = oe.freshness_state(now - 3600, "open", now)
        self.assertEqual(st["freshness"], "stale")

    def test_market_closed_is_not_the_same_as_stale(self):
        """⛔ السوق مغلق + بيانات من ٣ ساعات ⇒ fresh (مش stale)."""
        now = time.time()
        st = oe.freshness_state(now - 3600, "closed", now)
        self.assertEqual(st["freshness"], "fresh")
        self.assertEqual(st["market_phase"], "closed")

    def test_market_closed_but_very_old_is_stale(self):
        now = time.time()
        st = oe.freshness_state(now - 5 * 86400, "closed", now)
        self.assertEqual(st["freshness"], "stale")

    def test_last_success_does_not_advance_on_failed_fetch(self):
        """⛔⛔⛔ آخر جلب ناجح ما بيتحدّثش إلا بعد نجاح حقيقي."""
        old = up._LAST_SCAN_OK_AT
        up._LAST_SCAN_OK_AT = None
        real_post = up.requests.post

        def boom(*a, **k):
            raise RuntimeError("network down")

        up.requests.post = boom
        try:
            up.tv_scan_all(["EGX:COMI"])
        except Exception:
            pass
        finally:
            up.requests.post = real_post
        self.assertIsNone(up._LAST_SCAN_OK_AT,
                          "التوقيت اتحدّث رغم فشل الجلب")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"s": "EGX:COMI", "d": [10.0]}]}

        def ok_post(*a, **k):
            return _Resp()

        up.requests.post = ok_post
        try:
            out = up.tv_scan_all(["EGX:COMI"])
        finally:
            up.requests.post = real_post
        self.assertTrue(out, "الجلب الناجح رجّع فاضي")
        self.assertIsNotNone(up._LAST_SCAN_OK_AT,
                             "آخر جلب ناجح ما اتسجّلش")
        up._LAST_SCAN_OK_AT = old

    def test_payload_carries_freshness_contract(self):
        now = time.time()
        meta = {
            "generated_at": "2026-11-16T10:00:00Z", "source": "live",
            "market_phase": "open", "source_as_of": "2026-11-16T09:59:00Z",
            "last_success_at": now - 30,
            "data_freshness": oe.freshness_state(now - 30, "open", now),
            "sources": [{"source": "TradingView Scanner", "as_of": "2026-11-16T09:59:00Z"}],
        }
        p = oe.build_payload([_stock()], None, meta)
        self.assertEqual(p["market_phase"], "open")
        self.assertEqual(p["freshness"], "fresh")
        self.assertEqual(p["age_seconds"], 30)
        self.assertIsNotNone(p["last_success_at"])
        self.assertTrue(p["sources"], "مافيش مصادر في الـpayload")

    def test_cached_stock_is_not_presented_as_live(self):
        """⛔⛔⛔ آخر سعر معروف (من الكاش) ما يتعرضش كأنه لحظي."""
        st = _stock("CACHE1")
        st["stale"] = True
        st["stale_ts"] = "2026-11-15T22:00:00Z"
        st["price"] = 41.0
        meta = {"generated_at": "2026-11-16T10:00:00Z", "source": "cache",
                "market_phase": "closed"}
        p = oe.build_payload([st], None, meta)
        item = None
        for lst in (p.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                if it.get("code") == "CACHE1":
                    item = it
        self.assertIsNotNone(item, "السهم المخزّن ما ظهرش")
        self.assertEqual(item.get("data_state"), "stale")
        self.assertEqual(item.get("source_as_of"), "2026-11-15T22:00:00Z")
        self.assertNotEqual(item.get("price_label"), "سعر إغلاق")


class TestTierContract(unittest.TestCase):
    """⛔ باقات Free/Pro: نفس الحساب · حد مختلف في العدد."""

    @classmethod
    def setUpClass(cls):
        mk_user("fresh-free", "fresh.free@example.test", DEV_FREE, PIN_FREE, plan=None)
        mk_user("fresh-pro", "fresh.pro@example.test", DEV_PRO, PIN_PRO, plan="pro")

    def setUp(self):
        self.old = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["opp"] = oe.build_payload(
            _many(8), None,
            {"generated_at": "2026-11-16T10:00:00Z", "source": "live",
             "market_phase": "open", "freshness": "fresh"})

    def tearDown(self):
        up.LIVE_DATA["opp"] = self.old

    def _login_as(self, which):
        c = up.app.test_client()
        if which == "pro":
            h = auth_headers(c, PIN_PRO, DEV_PRO)
        else:
            h = auth_headers(c, PIN_FREE, DEV_FREE)
        return c, h

    def test_free_gets_limited_items(self):
        c, h = self._login_as("free")
        body = c.get("/api/opp/list/swing", headers=h).get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("plan"), "free")
        self.assertLessEqual(len(body.get("items") or []),
                             oe.OPP_FREE_LIMIT_PER_STRATEGY)

    def test_pro_gets_full_list_with_details(self):
        c, h = self._login_as("pro")
        body = c.get("/api/opp/list/swing", headers=h).get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("plan"), "pro")
        self.assertGreater(len(body.get("items") or []),
                           oe.OPP_FREE_LIMIT_PER_STRATEGY)

    def test_same_calculation_for_both_plans(self):
        """⛔⛔⛔ مافيش اختلاف في دقة الحساب بين الباقتين."""
        cf, hf = self._login_as("free")
        cp, hp = self._login_as("pro")
        f = (cf.get("/api/opp/list/swing", headers=hf).get_json() or {})
        p = (cp.get("/api/opp/list/swing", headers=hp).get_json() or {})
        fmap = {i["code"]: i for i in (f.get("items") or [])}
        pmap = {i["code"]: i for i in (p.get("items") or [])}
        self.assertTrue(fmap, "Free مالهوش فرص")
        for code, it in fmap.items():
            self.assertIn(code, pmap, "سهم لـFree مش موجود عند Pro")
            self.assertEqual(it.get("score"), pmap[code].get("score"),
                             "الدرجة مختلفة بين الباقتين")
            self.assertEqual(it.get("decision"), pmap[code].get("decision"))

    def test_free_items_are_brief_but_pro_have_details(self):
        cf, hf = self._login_as("free")
        cp, hp = self._login_as("pro")
        f = (cf.get("/api/opp/list/swing", headers=hf).get_json() or {})
        p = (cp.get("/api/opp/list/swing", headers=hp).get_json() or {})
        fi = (f.get("items") or [{}])[0]
        pi = (p.get("items") or [{}])[0]
        self.assertNotIn("criteria", fi, "Free شاف تفاصيل تحليلية كاملة")
        self.assertIn("criteria", pi, "Pro مافيش تفاصيل تحليلية")
        for k in ("score", "reasons", "state", "coverage", "grade_ar",
                  "risk_level_ar", "risk_score", "data_state"):
            self.assertIn(k, fi, "تفاصيل مختصرة ناقصة: " + k)
        self.assertNotIn("criteria", fi,
                         "Free شاف تفاصيل تحليلية كاملة")

    def test_summary_and_strategies_carry_plan(self):
        cp, hp = self._login_as("pro")
        cf, hf = self._login_as("free")
        for path in ("/api/opp/summary", "/api/opp/strategies"):
            pb = cp.get(path, headers=hp).get_json() or {}
            fb = cf.get(path, headers=hf).get_json() or {}
            self.assertEqual(pb.get("plan"), "pro", path)
            self.assertEqual(fb.get("plan"), "free", path)

    def test_all_nine_strategies_visible_for_free(self):
        """⛔ كل الاستراتيجيات التسع ظاهرة لـFree (قرار المالك)."""
        cf, hf = self._login_as("free")
        body = cf.get("/api/opp/strategies", headers=hf).get_json() or {}
        self.assertEqual(len(body.get("strategies") or []), 9)


class TestStrategyRankEligibility(unittest.TestCase):
    """⛔ ومنع fallback إلى final_score في ترتيب الاستراتيجية."""

    def test_ineligible_stock_does_not_enter_strategy_ranking(self):
        item = _stock("BAD1", final_score=91.0)
        item["rank_eligible"] = True
        item["strategies"] = {
            "swing": {"name": "سوينج", "score": None,
                      "decision": "بيانات غير كافية",
                      "filters_passed": False,
                      "score_status": "insufficient_risk",
                      "rank_eligible": False},
        }
        res = up.rank_stocks([item], strategy="swing")
        codes = [r["code"] for r in res]
        self.assertNotIn("BAD1", codes,
                         "سهم غير مؤهل دخل ترتيب الاستراتيجية بـfinal_score")

    def test_eligible_stock_uses_strategy_score(self):
        item = _stock("GOOD1", final_score=40.0)
        item["rank_eligible"] = True
        item["strategies"] = {
            "swing": {"name": "سوينج", "score": 77.0,
                      "decision": "إشارة إيجابية",
                      "filters_passed": True,
                      "score_status": "ok",
                      "rank_eligible": True},
        }
        res = up.rank_stocks([item], strategy="swing")
        codes = [r["code"] for r in res]
        self.assertIn("GOOD1", codes)
        self.assertEqual(res[0]["score"], 77.0,
                         "الدرجة اتحسبت من final_score مش من الاستراتيجية")

    def test_ineligible_with_score_does_not_fall_back(self):
        """⛔⛔⛔ السهم له نتيجة في الاستراتيجية بس مش مؤهل
        ⇒ مايدخلش بالدرجة العامة (الـfallback)."""
        item = _stock("BAD2", final_score=95.0)
        item["rank_eligible"] = True
        item["strategies"] = {
            "swing": {"name": "سوينج", "score": 64.4,
                      "decision": "بيانات شائعة",
                      "filters_passed": True, "score_status": "ok",
                      "rank_eligible": False},
        }
        res = up.rank_stocks([item], strategy="swing")
        self.assertEqual([r["code"] for r in res], [],
                         "سهم غير مؤهل دخل بالـfallback")

    def test_legacy_general_ranking_still_works(self):
        """⛔⛔⛔ المسار العام (من غير نتائج استراتيجيات) ما انكسرش."""
        item = _stock("GEN1", final_score=55.0)
        item["rank_eligible"] = True
        item["strategies"] = {}
        res = up.rank_stocks([item], strategy="balanced")
        self.assertEqual([r["code"] for r in res], ["GEN1"],
                         "الترتيب العام انكسر")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
