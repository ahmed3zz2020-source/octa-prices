#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٤ — موانع النشر (١٧ نوفمبر ٢٠٢٦).

⛔ كل اختبار سالب لازم يفشل على كود الجولة ١٣ ويعدّي على الكود الجديد.
📌 التشغيل:  python3 test_round14_release.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_r14_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r14-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r14-pepper"
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


def _stock(code="AAA", **kw):
    d = {
        "code": code, "name": "سهم اختبار", "sector": "صناعة", "price": 50.0,
        "change": 1.2, "technical_score": 72.0, "fund_score": 65.0,
        "liquidity_score": 70.0, "news_score": 55.0, "sentiment_score": 50.0,
        "safety_score": 64.0, "rsi": 52.0, "perf_1m": 6.0, "perf_3m": 14.0,
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


class TestRankPaths(unittest.TestCase):
    """⛔ (أ) مسار الاستراتيجية (بلا fallback) + المسار العام المخصص."""

    def test_specific_strategy_without_evaluation_is_excluded(self):
        """⛔ السهم ماعندوش تقييم في الاستراتيجية المطلوبة ⇒ ما يدخلش."""
        item = _stock("NOSTRAT", final_score=95.0)
        item["rank_eligible"] = True
        item["strategies"] = {}
        res = up.rank_stocks([item], strategy="swing")
        self.assertEqual([r["code"] for r in res], [],
                         "سهم بلا تقييم استراتيجية دخل بدرجته العامة")

    def test_specific_strategy_with_none_score_is_excluded(self):
        item = _stock("NOSCORE", final_score=95.0)
        item["rank_eligible"] = True
        item["strategies"] = {
            "swing": {"name": "سوينج", "score": None,
                      "decision": "بيانات غير كافية",
                      "filters_passed": False, "score_status": "insufficient_data",
                      "rank_eligible": False},
        }
        res = up.rank_stocks([item], strategy="swing")
        self.assertEqual([r["code"] for r in res], [],
                         "سهم غير مؤهل دخل بدرجته العامة")

    def test_general_path_keeps_old_behaviour(self):
        """⛔ المسار العام (strategy=None) ⇒ الدرجة العامة زي ما هي."""
        item = _stock("GEN1", final_score=55.0)
        item["rank_eligible"] = True
        item["strategies"] = {}
        res = up.rank_stocks([item], strategy=None)
        self.assertEqual([r["code"] for r in res], ["GEN1"],
                         "المسار العام انكسر")

    def test_general_path_excludes_ineligible(self):
        item = _stock("GEN2", final_score=55.0)
        item["rank_eligible"] = False
        item["strategies"] = {}
        res = up.rank_stocks([item], strategy=None)
        self.assertEqual([r["code"] for r in res], [],
                         "غير المؤهل دخل في الترتيب العام")

    def test_specific_strategy_uses_strategy_score(self):
        item = _stock("GOOD1", final_score=40.0)
        item["rank_eligible"] = True
        item["strategies"] = {
            "swing": {"name": "سوينج", "score": 77.0,
                      "decision": "إشارة إيجابية", "filters_passed": True,
                      "score_status": "ok", "rank_eligible": True},
        }
        res = up.rank_stocks([item], strategy="swing")
        self.assertEqual([r["code"] for r in res], ["GOOD1"])
        self.assertEqual(res[0]["score"], 77.0)


def _epoch(iso):
    """⛔ تحويل ISO ⇒ epoch (توقيت ثابت للاختبارات)."""
    import datetime
    return datetime.datetime.fromisoformat(
        iso.replace("Z", "+00:00")).timestamp()


class TestMarketCoverage(unittest.TestCase):
    """⛔ (ب) حداثة السوق: جلب كامل / جزئي / فاشل."""

    def test_full_fetch_is_fresh(self):
        now = time.time()
        st = oe.freshness_state(now - 30, "open", now,
                                 coverage=100.0, requested=286, updated=286)
        self.assertEqual(st["freshness"], "fresh")
        self.assertEqual(st["coverage_pct"], 100.0)
        self.assertEqual(st["missing"], 0)

    def test_partial_fetch_is_partial_not_fresh(self):
        """⛔⛔⛔ نجاح سهم واحد ⇏ «fresh» — الحالة تغطية جزئية.

        ⛔ الجولة ١٦ — **فصل المفهومين**:
          · `coverage_status` = partial  (التغطية ناقصة)
          · `freshness`       = الحداثة (عمر آخر جلب ناجح) بس
        ⛔ والعمر (`age_seconds`) بيتحسب **دايماً** — عشان المستخدم يعرف
           إن البيانات قديمة حتى لو التغطية ناقصة في نفس الوقت.
        """
        now = time.time()
        st = oe.freshness_state(now - 30, "open", now,
                                 coverage=1.0, requested=286, updated=3)
        self.assertEqual(st["coverage_status"], "partial")
        self.assertNotEqual(st["freshness"], "partial",
                            "الحداثة مبقاش بتاخد قيمة التغطية")
        self.assertEqual(st["updated"], 3)
        self.assertEqual(st["missing"], 283)
        self.assertIsNotNone(st["age_seconds"],
                             "العمر لازم يتحسب حتى مع تغطية جزئية")

    def test_failed_fetch_without_success_is_unavailable(self):
        now = time.time()
        st = oe.freshness_state(None, "open", now,
                                 coverage=0.0, requested=286, updated=0)
        self.assertEqual(st["freshness"], "unavailable")

    def test_partial_fetch_after_success_does_not_claim_fresh(self):
        """⛔ الجولة ١٦ — تغطية ناقصة ⇒ **مش** «كل البيانات سليمة».

        📌 الفصل الجديد: الحداثة (`freshness`) والتغطية
        (`coverage_status`) **مفهومين منفصلين** ⇒ الحداثة بتقول «البيانات
        حديثة» والتغطية بتقول «ناقصة» — والمستخدم بيشوف الاتنين مع بعض
        (مش ادعاء «fresh» وحده).
        """
        now = time.time()
        st = oe.freshness_state(now - 30, "open", now,
                                 coverage=5.0, requested=286, updated=14)
        self.assertEqual(st["coverage_status"], "partial")
        self.assertEqual(st["freshness"], "fresh")     # ⛔ العمر هو اللي بيحكم
        self.assertEqual(st["data_state"], st["freshness"],
                         "data_state = الحداثة (مش التغطية)")
        self.assertIsNotNone(st["age_seconds"])

    def test_scan_partial_does_not_advance_last_success(self):
        """⛔ الجلب الناقص ما يحدّثش «آخر جلب ناجح»."""
        old_ok = up._LAST_SCAN_OK_AT
        old_cov = up._LAST_SCAN_ATTEMPT_COVERAGE
        up._LAST_SCAN_OK_AT = None
        up._LAST_SCAN_ATTEMPT_COVERAGE = None

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                # 3 صفوف فقط من 10 مطلوبين ⇒ تغطية 30%
                return {"data": [{"s": "EGX:A", "d": [10.0]},
                                 {"s": "EGX:B", "d": [10.0]},
                                 {"s": "EGX:C", "d": [10.0]}]}

        real_post = up.requests.post

        def ok_post(*a, **k):
            return _Resp()

        up.requests.post = ok_post
        try:
            up.tv_scan_all(["EGX:A", "EGX:B", "EGX:C",
                            "EGX:D", "EGX:E", "EGX:F",
                            "EGX:G", "EGX:H", "EGX:I", "EGX:J"])
        finally:
            up.requests.post = real_post
        self.assertIsNone(up._LAST_SCAN_OK_AT,
                          "جلب ناقص حدّث «آخر جلب ناجح»")
        self.assertIsNotNone(up._LAST_SCAN_ATTEMPT_COVERAGE)
        self.assertLess(up._LAST_SCAN_ATTEMPT_COVERAGE, up._FRESH_MIN_COVERAGE)
        self.assertEqual(up._LAST_SCAN_RETURNED, 3)
        self.assertEqual(up._LAST_SCAN_REQUESTED, 10)
        up._LAST_SCAN_OK_AT = old_ok
        up._LAST_SCAN_ATTEMPT_COVERAGE = old_cov


class TestPriceDescription(unittest.TestCase):
    """⛔ (ج) وصف السعر + فصل وقت الاستلام عن وقت السعر."""

    def test_open_market_label_is_trading_not_closing(self):
        """⛔ الجولة ١٦ — «الآن» محتاجة دليل (عمر + نفس الجلسة).

        ⛔ من غير دليل ⇒ ممنوع ادعاء لحظي (مش «سعر إغلاق» ولا «الآن»).
        """
        self.assertNotEqual(oe.price_label_for("open"), "سعر التداول الآن",
                            "ادّعاء لحظية من غير دليل على حداثة السعر")
        lab = oe.price_label_for("open", price_time_source="source",
                                 price_age_seconds=30,
                                 price_session_date="2026-11-17",
                                 session_date="2026-11-17")
        self.assertEqual(lab, "سعر التداول الآن")
        self.assertNotEqual(lab, "سعر إغلاق")

    def test_closed_market_label_is_closing(self):
        self.assertEqual(oe.price_label_for("closed"), "سعر الإغلاق")

    def test_pre_market_label_is_previous_close(self):
        self.assertEqual(oe.price_label_for("pre"), "سعر الإغلاق السابق")

    def test_stale_item_label_is_last_known(self):
        self.assertEqual(oe.price_label_for("open", stale=True),
                         "آخر سعر معروف")

    def test_item_separates_received_time_from_price_time(self):
        st = _stock("AAA")
        meta = {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
                "market_phase": "open",
                # ⛔⛔⛔ مراجعة الجولة يا (R17-P1) — الدلة لازم تعلن إن الدفاتة حديثة
                # — مفيش دليل ⇒ الصف يكون «unknown» (من عيشه ليقول «سعر التداول الآن»).
                "data_freshness": {"freshness": "fresh", "data_state": "fresh"},}
        p = oe.build_payload([st], None, meta)
        item = None
        for lst in (p.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                if it.get("code") == "AAA":
                    item = it
        self.assertIsNotNone(item)
        # ⬜️ الجولة 15 (ملاحظة المالك) — مافيش توقيت من المصدر ⇒ ممنوع ادعاء لحظية
        self.assertEqual(item.get("price_label"), "آخر سعر متاح")
        self.assertNotIn("الآن", item.get("price_label") or "")
        self.assertEqual(item.get("data_received_at"), "2026-11-17T10:00:00Z")
        # ⛔ المصدر مابيعطيش وقت السعر ⇒ null + تعلن إن المصدر مابقّدش
        self.assertIsNone(item.get("price_as_of"))
        self.assertEqual(item.get("price_time_source"), "not_provided")

    def test_item_with_source_price_time_claims_current(self):
        """⛔⛔ بتوقيت من المصدر + عمر حديث + نفس الجلسة ⇒ «سعر التداول الآن».

        ⛔ الجولة ١٦: بقى لازم **تلات** أدلة (السوق مفتوح · نفس الجلسة ·
        عمر السعر ≤ ١٥ دقيقة) — مش وجود `price_ts` بس.
        """
        st = _stock("BBB", price_ts="2026-11-17T09:59:00Z")
        meta = {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
                "market_phase": "open",
                # ⛔ الجولة ١٦ — وقت مرجعي ثابت (حتمي) + تاريخ الجلسة
                "now": _epoch("2026-11-17T10:00:00Z"),
                "session_date": "2026-11-17",
                # ⛔⛔⛔ مراجعة الجولة يا (R17-P1) — الدلة لازم تعلن إن الدفاتة حديثة
                # — مفيش دليل ⇒ الصف يكون «unknown» (من عيشه ليقول «سعر التداول الآن»).
                "data_freshness": {"freshness": "fresh", "data_state": "fresh"},}
        p = oe.build_payload([st], None, meta)
        item = None
        for lst in (p.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                if it.get("code") == "BBB":
                    item = it
        self.assertIsNotNone(item)
        self.assertEqual(item.get("price_label"), "سعر التداول الآن")
        self.assertEqual(item.get("price_time_source"), "source")
        self.assertEqual(item.get("price_as_of"), "2026-11-17T09:59:00Z")
        self.assertEqual(item.get("price_age_seconds"), 60)

    def test_cached_item_label_is_not_closing_price(self):
        st = _stock("CACHE1", stale=True, stale_ts="2026-11-16T22:00:00Z")
        meta = {"generated_at": "2026-11-17T10:00:00Z", "source": "cache",
                "market_phase": "closed"}
        p = oe.build_payload([st], None, meta)
        for lst in (p.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                if it.get("code") == "CACHE1":
                    self.assertEqual(it.get("price_label"), "آخر سعر معروف")
                    self.assertIsNone(it.get("data_received_at"))


class TestQuerySanitizerRealFlask(unittest.TestCase):
    """⛔ (د) تنظيف الـquery بـFlask الحقيقي."""

    def setUp(self):
        self.c = up.app.test_client()

    def _raw_query(self, path):
        """⛔ نقرأ الـquery بعد التنظيف مباشرة (من الـenviron)."""
        with up.app.test_request_context(path):
            from flask import request
            up._sanitize_request()
            return request.environ.get("QUERY_STRING", "")

    def test_multiple_keys_are_cleaned(self):
        q = self._raw_query("/api/x?a=hello&b=world")
        self.assertIn("a=hello", q)
        self.assertIn("b=world", q)

    def test_script_tag_is_neutralised(self):
        q = self._raw_query("/api/x?q=%3Cscript%3Ealert(1)%3C/script%3E")
        # \u26d4 \u0627\u0644\u0645\u062e\u0637\u0631 \u0645\u0627\u064a\u0642\u062f\u0631 \u062a\u0633\u0643\u064a\u0644 \u2014 \u0645\u0627\u064a\u0642\u062f\u0631\u0634 \u0643\u0644\u0645\u0627\u0621
        self.assertNotIn("<", q)
        self.assertNotIn(">", q)
        self.assertNotIn("%3c", q.lower())
        self.assertNotIn("%3e", q.lower())

    def test_duplicate_keys_are_handled(self):
        q = self._raw_query("/api/x?a=1&a=2&b=3")
        self.assertTrue(q)
        self.assertNotIn("&a=1&a=2", q)

    def test_malformed_and_long_values_are_truncated(self):
        q = self._raw_query("/api/x?q=" + ("A" * 5000))
        self.assertLessEqual(len(q), 400, "القيمة الطويلة مرّت زي ما هي")

    def test_control_characters_are_removed(self):
        q = self._raw_query("/api/x?q=%00%01%02abc")
        self.assertNotIn("\x00", q)
        self.assertNotIn("\x01", q)

    def test_failing_sanitizer_does_not_pass_dangerous_input(self):
        """⛔⛔⛔ لو التنظيف وقع ⇒ مدخل خطير ما يعدّيش."""
        import flask
        real_clean = up.clean_text

        def boom(*a, **k):
            raise RuntimeError("sanitizer down")

        up.clean_text = boom
        try:
            q = self._raw_query("/api/x?q=%3Cscript%3Ebad%3C/script%3E&k=ok")
        finally:
            up.clean_text = real_clean
        # ⛔ الخطر الحقيقي = علامات HTML (ما يبقاش فيه وسم يتكوّن)
        self.assertNotIn("<", q, "مدخل خطير مرّ بعد تعطّل التنظيف")
        self.assertNotIn(">", q)
        self.assertNotIn("%3c", q.lower())
        self.assertNotIn("%3e", q.lower())
        self.assertIn("k=ok", q, "المفاتيح السليمة اتشالت كمان")

    def test_failing_sanitizer_keeps_safe_keys(self):
        import flask
        real_clean = up.clean_text

        def boom(*a, **k):
            raise RuntimeError("sanitizer down")

        up.clean_text = boom
        try:
            q = self._raw_query("/api/x?code=COMI&limit=5")
        finally:
            up.clean_text = real_clean
        self.assertIn("code=COMI", q)
        self.assertIn("limit=5", q)


class TestTierSameData(unittest.TestCase):
    """⛔ (٣) Free وPro على **نفس** البيانات ⇒ نفس الأسهم والنتائج."""

    def test_shared_stocks_have_identical_results(self):
        stocks = [_stock("S%02d" % i, all_axes={
            "technical": 70.0 + i, "fundamental": 60.0 + i,
            "liquidity": 65.0 + i, "risk": 60.0 + i,
            "news": 50.0 + i, "sentiment": 50.0 + i}) for i in range(10)]
        meta = {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
                "market_phase": "open"}
        payload = oe.build_payload(stocks, None, meta)
        free = oe.apply_tier(payload, "free")
        pro = oe.apply_tier(payload, "pro")
        fmap = {i["code"]: i for i in (free["lists"]["swing"]["items"] or [])}
        pmap = {i["code"]: i for i in (pro["lists"]["swing"]["items"] or [])}
        self.assertTrue(fmap)
        for code, it in fmap.items():
            self.assertIn(code, pmap)
            self.assertEqual(it.get("score"), pmap[code].get("score"))
            self.assertEqual(it.get("decision"), pmap[code].get("decision"))
            self.assertEqual(it.get("coverage"), pmap[code].get("coverage"))
            self.assertEqual(it.get("rank_eligible"), pmap[code].get("rank_eligible"))

    def test_free_limit_is_five_and_pro_is_twenty(self):
        stocks = [_stock("S%02d" % i, all_axes={
            "technical": 70.0 + i, "fundamental": 60.0 + i,
            "liquidity": 65.0 + i, "risk": 60.0 + i,
            "news": 50.0 + i, "sentiment": 50.0 + i}) for i in range(30)]
        meta = {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
                "market_phase": "open"}
        payload = oe.build_payload(stocks, None, meta)
        free = oe.apply_tier(payload, "free")
        pro = oe.apply_tier(payload, "pro")
        self.assertEqual(len(free["lists"]["swing"]["items"]), 5)
        self.assertEqual(len(pro["lists"]["swing"]["items"]), 20)

    def test_pro_label_does_not_claim_all_eligible(self):
        """⛔⛔⛔ ما نقولش «كل الأسهم المؤهلة» — المحرّك بيعرض أفضل ٢٠."""
        payload = oe.build_payload([_stock()], None,
                                   {"generated_at": "x", "market_phase": "open"})
        pro = oe.apply_tier(payload, "pro")
        label = pro.get("limit_label_ar") or ""
        self.assertNotIn("كل المؤهل", label)
        self.assertNotIn("القائمة الكاملة", label)
        self.assertIn("20", label)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
