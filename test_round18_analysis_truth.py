#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٨ — R18-P4: **صدق محرّك التحليل** (٧ بنود).

البنود (كل واحد اختبار سالب لازم يفشل على الأساس 235cc1b ويعدّي بعد الإصلاح):
 ① MD-049  / AZ21-RISK-UNKNOWN  (P1) — مخاطرة بلا مدخلات ⇒ «أمان 95 / منخفض»
 ② MD-050  / AZ21-SENT-PCT      (P2) — متوسط قطاع +2٪ ⇒ «200% مقابل 5%»
 ③ MD-054  / AZ24-WATCH-DUP     (P1) — 3 منبهات ⇒ 9 صفوف + كتابة في مسار القراءة
 ④ MD-054b / AZ24-WATCH-PERSIST (P1) — فشل الحفظ ⇒ رد «نجاح» كاذب
 ⑤ AZ24-PORTFOLIO-SHARED / SEC-015 (P1+أمني) — ملاءمة محفظة عامة لزائر
 ⑥ MD-052  / AZ22-EXPLAIN-DIVERGES (P1) — الشرح بيقول 75 والمجموع 50.9
 ⑦ MD-034  / AZ25-BACKTEST-DAYS  (P1) — days_back=3 بيرجّع لقطة عمرها 50 يوم

📌 التشغيل:  python test_round18_analysis_truth.py
📌 أو:       pytest -q test_round18_analysis_truth.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر · مافيش تكلفة.
⛔ ممنوع: تغيير أوزان المحرك أو عتباته (الاختبارات بتتحقق إن الأرقام
   المحسوبة ما اتغيرتش — غير في البند ٦ اللي إصلاحه بالظبط في إعادة التركيب).
"""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_r18p4_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r18p4-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r18p4-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"
up.BT_FILE = Path(TMP) / "backtest_snapshots.json"


# ════════════════════════════════════════════════════════════════
#  أدوات
# ════════════════════════════════════════════════════════════════
def _tech(score):
    return {"score": score, "signal": "اختبار"}


def _fund(score):
    return {"score": score, "valuation_status": "مُسعَّر",
            "fair_value": 10.0, "upside_pct": 5.0}


def _liq(score, level="متوسط"):
    return {"score": score, "risk_level": level, "confidence": 80.0}


def _risk_item(**kw):
    """سهم بكل مؤشرات المخاطرة (بيانات كافية)."""
    d = {"code": "TST", "name": "سهم اختبار", "sector": "صناعة", "price": 10.0,
         "beta": 0.9, "de_ratio": 30.0, "volatility": 25.0, "mkt_cap": 12e9,
         "net_margin": 12.0, "pe": 12.0, "tv_all": 0.3, "perf_3m": 14.0,
         "atr": 0.4, "rsi": 52.0, "roe": 18.0, "eps": 4.2, "pb": 1.4,
         "data_confidence": 60}
    d.update(kw)
    return d


class _FakeRequest(object):
    def __init__(self, payload):
        self._payload = payload

    def get_json(self, silent=True):
        return self._payload


# ════════════════════════════════════════════════════════════════
#  ① MD-049 / AZ21-RISK-UNKNOWN
# ════════════════════════════════════════════════════════════════
class TestRiskEngineTruth(unittest.TestCase):
    """سهم صناعي بلا مدخلات مخاطرة ⇒ ممنوع «أمان 95 / منخفض»."""

    def test_no_risk_inputs_is_insufficient_data(self):
        r = up.risk_engine({"code": "IND", "name": "سهم صناعي", "price": 100.0})
        self.assertIsNotNone(r, "المفروض نرجّع حالة صريحة مش None")
        self.assertEqual(r.get("risk_status"), "insufficient_data",
                         "بلا مدخلات مخاطرة ⇒ لازم risk_status=insufficient_data")
        self.assertNotEqual(r.get("risk_level"), "منخفض",
                            "ممنوع وصف أمان عالي بلا دليل (risk_level منخفض)")

    def test_no_high_safety_number_without_evidence(self):
        r = up.risk_engine({"code": "IND", "name": "سهم صناعي", "price": 100.0})
        safety = r.get("safety_score")
        self.assertTrue(
            safety is None or safety < 90,
            "ممنوع نشر رقم أمان عالي (90+) من غير أي مؤشر مخاطرة — got %r" % (safety,))

    def test_missing_inputs_are_disclosed(self):
        r = up.risk_engine({"code": "IND", "price": 100.0})
        self.assertEqual(r.get("risk_inputs_count"), 0)
        self.assertTrue(r.get("missing_inputs"),
                        "لازم ن disclose المدخلات الناقصة")
        self.assertTrue(any("غير معروف" in n or "ناقصة" in n for n in (r.get("notes") or [])),
                        "لازم ملاحظة صريحة إن درجة الأمان مش معروفة")

    def test_real_risk_data_still_produces_numbers(self):
        """الإصلاح ما بيلمسش الأرقام لما البيانات موجودة."""
        r = up.risk_engine(_risk_item())
        self.assertEqual(r.get("risk_status"), "ok")
        self.assertIsInstance(r.get("safety_score"), (int, float))
        self.assertIsInstance(r.get("risk_score"), (int, float))
        self.assertIn(r.get("risk_level"), ("منخفض", "متوسط", "مرتفع", "مرتفع جداً"))

    def test_weights_and_thresholds_unchanged(self):
        """⛔ الأوزان/العتبات ما اتغيرتش: نفس الأرقام المرجعية."""
        r = up.risk_engine(_risk_item())
        # volatility 25 (>5 ⇒ 20) + beta 0.9 (>0.5 ⇒ 2) + de 30 (>2 ⇒ 20) +
        # mkt_cap 12e9 (<20e9 ⇒ 2) + events (5) = 49 ⇒ أمان 51
        self.assertEqual(r["breakdown"]["التقلب"], 20.0)
        self.assertEqual(r["breakdown"]["حساسية السوق"], 2.0)
        self.assertEqual(r["breakdown"]["مالية"], 20.0)
        self.assertEqual(r["breakdown"]["السيولة"], 2.0)
        self.assertEqual(r["breakdown"]["الأحداث"], 5)
        self.assertEqual(r["risk_score"], 49.0)
        self.assertEqual(r["safety_score"], 51.0)


# ════════════════════════════════════════════════════════════════
#  ② MD-050 / AZ21-SENT-PCT
# ════════════════════════════════════════════════════════════════
class TestSentimentPercentUnit(unittest.TestCase):
    """متوسط القطاع +2٪ ما ينفعش يطلع «200%»."""

    def _sector_message(self, peers_perf3m, item_perf3m):
        peers = [{"sector": "s", "code": "S%d" % i, "perf_3m": p, "perf_1m": 2}
                 for i, p in enumerate(peers_perf3m)]
        item = {"sector": "s", "code": "TST", "perf_1m": 5, "perf_3m": item_perf3m}
        res = up.sentiment_engine(item, peers)
        return next((x for x in (res.get("positives") or []) if "متوسط" in x), "")

    def test_sector_average_is_not_multiplied_by_100(self):
        msg = self._sector_message([2, 2, 2], 5)
        self.assertTrue(msg, "المفروض تطلع رسالة المقارنة مع متوسط القطاع")
        self.assertNotIn("200%", msg,
                         "⛔ متوسط قطاع +2٪ طالع «200%» — وحدة النسبة غلط: " + msg)
        self.assertIn("2%", msg, "المفروض الرقم يبقى 2% (مش 200%): " + msg)

    def test_sector_average_numbers_are_the_real_percentages(self):
        msg = self._sector_message([2, 2, 2], 5)
        nums = msg.replace("(", " ").replace(")", " ").replace("%", " ").split()
        shown = [float(x) for x in nums if x.replace(".", "", 1).isdigit()]
        self.assertTrue(shown, "مفيش أرقام في الرسالة: " + msg)
        self.assertAlmostEqual(shown[0], 2.0, delta=0.6,
                               msg="متوسط القطاع المعروض لازم يكون 2% — " + msg)
        self.assertAlmostEqual(shown[1], 5.0, delta=0.6,
                               msg="أداء السهم المعروض لازم يكون 5% — " + msg)

    def test_other_sector_message_keeps_percent_unit(self):
        """رسالة القطاع نفسه (مش رسالة المقارنة) ما اتغيّرتش."""
        peers = [{"sector": "s", "code": "S%d" % i, "perf_3m": 2, "perf_1m": 9}
                 for i in range(3)]
        item = {"sector": "s", "code": "TST", "perf_1m": 9, "perf_3m": 5}
        res = up.sentiment_engine(item, peers)
        joined = " | ".join((res.get("positives") or []) + (res.get("negatives") or []))
        self.assertNotIn("900%", joined,
                         "⛔ متوسط قطاع +9٪ طالع «900%»: " + joined)


# ════════════════════════════════════════════════════════════════
#  ③ MD-054 / AZ24-WATCH-DUP
# ════════════════════════════════════════════════════════════════
class TestWatchListNoDuplicates(unittest.TestCase):
    """n منبهات ⇒ n صفوف (مش n²) · ومافيش كتابة في مسار القراءة."""

    def _get(self, n):
        watch = {"C%d" % i: {"hi": 110, "lo": 90, "at": 100 + i} for i in range(n)}
        live = {"egx30": [{"code": "C%d" % i} for i in range(n)]}
        with mock.patch.object(up, "require_user",
                               lambda: {"id": "T", "watch": watch}), \
             mock.patch.object(up, "LIVE_DATA", live), \
             mock.patch.object(up, "jsonify", lambda v, **k: v):
            return up._octa_watch_get()

    def test_counts_are_unique(self):
        for n in (0, 1, 3, 20):
            res = self._get(n)
            items = res.get("items") or []
            self.assertEqual(len(items), n,
                             "%d منبهات ⇒ %d صفوف (المتوقع %d)" % (n, len(items), n))
            codes = [i.get("code") for i in items]
            self.assertEqual(len(codes), len(set(codes)),
                             "مافيش تكرار في صفوف المنبهات: %r" % (codes,))

    def test_read_path_does_not_write(self):
        calls = []
        watch = {"C%d" % i: {"hi": 110, "lo": 90} for i in range(3)}
        live = {"egx30": [{"code": "C%d" % i} for i in range(3)]}
        with mock.patch.object(up, "require_user",
                               lambda: {"id": "T", "watch": watch}), \
             mock.patch.object(up, "LIVE_DATA", live), \
             mock.patch.object(up, "jsonify", lambda v, **k: v), \
             mock.patch.object(up, "w_add",
                               lambda *a, **k: calls.append(a)):
            up._octa_watch_get()
        self.assertEqual(calls, [],
                         "⛔ مسار القراءة لازم ما يكتبش (w_add اتنادى %d مرة)" % len(calls))

    def test_watch_rows_keep_their_own_data(self):
        res = self._get(3)
        ats = sorted(i.get("at") for i in (res.get("items") or []))
        self.assertEqual(ats, [100, 101, 102],
                         "كل صف لازم يحمل بياناته (at) بتاعته — مش وقت القراءة: %r" % (ats,))


# ════════════════════════════════════════════════════════════════
#  ④ MD-054b / AZ24-WATCH-PERSIST
# ════════════════════════════════════════════════════════════════
class TestWatchWriteTruth(unittest.TestCase):
    """«النجاح» = دليل على الكتابة."""

    def _post(self, patch_result):
        with mock.patch.object(up, "require_user",
                               lambda: {"id": "T", "watch": {}}), \
             mock.patch.object(up, "LIVE_DATA", {"egx30": [{"code": "AAA"}]}), \
             mock.patch.object(up, "jsonify", lambda v, **k: v), \
             mock.patch.object(up, "request",
                               _FakeRequest({"action": "add", "code": "AAA", "hi": 110})), \
             mock.patch.object(up, "_patch_user", lambda *a, **k: patch_result):
            res = up._octa_watch_post()
        if isinstance(res, tuple):
            res = res[0]
        return res

    def test_failed_write_is_not_success(self):
        res = self._post(None)          # ⛔ _patch_user رجّع None ⇒ الحفظ فشل
        self.assertFalse(res.get("ok"),
                         "⛔ فشل الحفظ ⇒ ممنوع «ok: true» (نجاح كاذب): %r" % (res,))
        self.assertFalse(res.get("saved", True),
                         "لازم نعلن إن الحفظ ما حصلش")
        self.assertTrue(res.get("error"),
                        "لازم سبب صريح للفشل: %r" % (res,))

    def test_successful_write_reports_success(self):
        res = self._post({"id": "T"})
        self.assertTrue(res.get("ok"), "الحفظ الناجح ⇒ ok=true: %r" % (res,))
        self.assertTrue(res.get("saved", True))


# ════════════════════════════════════════════════════════════════
#  ⑤ AZ24-PORTFOLIO-SHARED / SEC-015
# ════════════════════════════════════════════════════════════════
class TestPortfolioFitAuth(unittest.TestCase):
    """ملاءمة المحفظة: مصادقة إلزامية + محفظة المستخدم (مش العامة).

    📌 ملاحظة: البوابة العامة (before_request) كانت بتحجب المسار على
       مستوى HTTP للزائر — لكن **الدالة نفسها** كانت مفتوحة (وراجع
       برهان المراجع AZ24-PORTFOLIO-SHARED) وكانت بتستخدم **المحفظة
       العامة** حتى للمستخدم المسجّل. الاختبارات هنا على مستوى الدالة
       (سلوك حقيقي) + مستوى المسار.
    """

    def _call(self, user):
        live = {"egx30": [{"code": "AAA", "name": "سهم", "sector": "صناعة",
                            "price": 100.0}]}
        with mock.patch.object(up, "require_user", lambda: user), \
             mock.patch.object(up, "LIVE_DATA", live), \
             mock.patch.object(up, "jsonify", lambda v, **k: v):
            res = up.portfolio_fit_api("AAA")
        if isinstance(res, tuple):
            res = res[0]
        return res

    def test_anonymous_call_at_function_level_gets_no_fit(self):
        res = self._call(None)          # ⛔ زائر مجهول (من غير جلسة)
        self.assertFalse(res.get("portfolio_fit"),
                         "⛔ ممنوع ترجّع ملاءمة محفظة لزائر: " + repr(res))
        self.assertTrue(res.get("auth_required"),
                        "لازم نعلن إن المصادقة مطلوبة: " + repr(res))
        self.assertFalse(res.get("ok"))

    def test_http_anonymous_request_rejected(self):
        client = up.app.test_client()
        live = {"egx30": [{"code": "AAA", "name": "سهم", "sector": "صناعة",
                            "price": 100.0}]}
        with mock.patch.object(up, "LIVE_DATA", live):
            r = client.get("/api/portfolio/fit/AAA")
        self.assertIn(r.status_code, (401, 403),
                      "⛔ لازم مصادقة إلزامية — status=" + str(r.status_code))

    def test_user_portfolio_is_used_not_the_global_one(self):
        global_pf = {"holdings": {"ZZZ": {"shares": 100, "price": 10, "sector": "أخرى"},
                                  "YYY": {"shares": 5, "price": 20, "sector": "سلعة"}},
                     "cash": 0}
        user_pf = {"holdings": {"BBB": {"shares": 10, "price": 50, "sector": "بنوك"}},
                   "cash": 100}
        with mock.patch.object(up, "PORTFOLIO", global_pf):
            res = self._call({"id": "U1", "portfolio": user_pf})
        fit = res.get("portfolio_fit") or {}
        self.assertEqual(fit.get("holdings_count"), 1,
                         "لازم نحسب على محفظة المستخدم (1 سهم) مش العامة (2)")
        self.assertEqual((res.get("portfolio") or {}).get("portfolio_kind"), "user",
                         "لازم نصف طبيعة المحفظة صراحة")
        self.assertNotEqual((res.get("portfolio") or {}).get("portfolio_kind"), "global")
        self.assertEqual(fit.get("portfolio_kind"), "user")
        self.assertEqual((res.get("portfolio") or {}).get("source"), "user_portfolio")

    def test_user_without_portfolio_gets_explicit_answer(self):
        global_pf = {"holdings": {"ZZZ": {"shares": 100, "price": 10, "sector": "أخرى"}},
                     "cash": 0}
        with mock.patch.object(up, "PORTFOLIO", global_pf):
            res = self._call({"id": "U2", "portfolio": {}})
        self.assertTrue(res.get("ok"))
        self.assertIsNone(res.get("portfolio_fit"),
                          "⛔ مافيش محفظة ⇒ ممنوع رقم ملاءمة (مش المحفظة العامة)")
        self.assertTrue(res.get("note"), "لازم رد صريح: " + repr(res))
        self.assertEqual((res.get("portfolio") or {}).get("status"), "empty")
        self.assertEqual((res.get("portfolio") or {}).get("portfolio_kind"), "user")
        self.assertEqual((res.get("portfolio") or {}).get("holdings_count"), 0)


# ════════════════════════════════════════════════════════════════
#  ⑥ MD-052 / AZ22-EXPLAIN-DIVERGES
# ════════════════════════════════════════════════════════════════
class TestExplainRecomposition(unittest.TestCase):
    """إعادة تركيب النتيجة = الرقم المنشور (في كل حالة)."""

    def _case(self, item, tech=None, fund=None, liq=None):
        t = tech if tech is not None else _tech(70)
        f = fund if fund is not None else _fund(70)
        l = liq if liq is not None else _liq(70)
        ss = up.build_sector_stats([item])
        fin = up.final_score(item, t, f, l, ss)
        ex = up.explain_score(item, t, f, l, None, None, None, None, fin)
        return fin, ex

    def test_recomposition_matches_published_score(self):
        cases = [
            ("بيانات كاملة", _risk_item(), None, None, None),
            ("ثقة ضعيفة (خصم)", _risk_item(data_confidence=40), None, None, None),
            ("ثقة ممتازة (مكافأة)", _risk_item(data_confidence=95), None, None, None),
            ("سيولة ضعيفة (خصم)", _risk_item(), None, None, _liq(30, "مرتفع")),
            ("مخاطرة ناقصة", {"code": "X", "price": 10.0, "data_confidence": 60},
             None, None, None),
        ]
        for label, item, t, f, l in cases:
            fin, ex = self._case(item, t, f, l)
            self.assertIsNotNone(fin.get("final_score"), label)
            self.assertAlmostEqual(
                ex["final_score"], fin["final_score"], delta=0.15,
                msg="⛔ [%s] رقم الشرح (%s) ≠ الرقم المنشور (%s)" % (
                    label, ex["final_score"], fin["final_score"]))
            self.assertAlmostEqual(
                ex["base_score"] + ex["adjustment_total"], ex["final_score"], delta=0.05,
                msg="⛔ [%s] إعادة تركيب المساهمات (%s + %s) ≠ الرقم (%s)" % (
                    label, ex["base_score"], ex["adjustment_total"], ex["final_score"]))
            self.assertTrue(ex.get("score_consistent"),
                            "[%s] الشرف لازم يعلن إنّه متسق مع الرقم المنشور" % label)

    def test_contributions_sum_to_base(self):
        fin, ex = self._case(_risk_item())
        total = round(sum(c["contribution"] for c in ex["contributions"]), 1)
        self.assertAlmostEqual(total, ex["base_score"], delta=0.1,
                               msg="مجموع المساهمات (%s) ≠ الأساس (%s)" % (
                                   total, ex["base_score"]))

    def test_adjustments_sum_to_total(self):
        fin, ex = self._case(_risk_item(data_confidence=40))
        total = round(sum(a["value"] for a in ex["adjustments"]), 2)
        self.assertAlmostEqual(total, ex["adjustment_total"], delta=0.01,
                               msg="مجموع التعديلات (%s) ≠ الإجمالي (%s)" % (
                                   total, ex["adjustment_total"]))

    def test_bonus_case_is_shown_as_bonus(self):
        """المكافأة (ثقة عالية) لازم تظهر موجبة في الشرح."""
        fin, ex = self._case(_risk_item(data_confidence=95))
        types = {a["type"]: a["value"] for a in ex["adjustments"]}
        self.assertTrue(any(v > 0 for v in types.values()),
                        "لازم تظهر مكافأة الثقة كرقم موجب: %r" % (types,))

    def test_missing_axis_is_not_filled_with_50(self):
        """⛔ المحور الناقص = صفر (أسوأ حالة) مش 50 مخترع."""
        item = {"code": "X", "price": 10.0, "data_confidence": 60}
        fin, ex = self._case(item)
        axes = {c["axis"]: c for c in ex["contributions"]}
        # ⛔ سياسة octa_score: محور ناقص = 0 (الأسوأ) + خصم كامل
        self.assertEqual(axes["risk"]["score"], 0.0,
                         "محور المخاطرة الناقص لازم يبقى 0 (مش 50): " + repr(axes))
        self.assertEqual(axes["risk"]["contribution"], 0.0)
        # ⛔ مافيش محور مخترع: اللي في الشرح = محاور المحرك المتاحة
        #    (+ محور المخاطرة بسياسة octa_score: ناقص ⇒ 0).
        expected = {k for k, v in (fin.get("axes") or {}).items() if v is not None} | {"risk"}
        self.assertEqual(set(axes.keys()), expected,
                         "الشرح لازم يفكّك محاور المحرك بس — مافيش محور مخترع")

    def test_api_explain_matches_published_number(self):
        """اختبار حقيقي على المسار: الشرح المعلن = الرقم المنشور.

        📌 «final_score» بيتشال من ردود الزائرين بفلتر المخرجات
           (سلوك موجود من قبل) — فبنتحقق من إعادة التركيب بالرقمين
           الظاهرين: الأساس + التعديلات = الرقم المنشور.
        """
        item = _risk_item()
        live = {"egx30": [item]}
        ss = up.build_sector_stats([item])
        with mock.patch.object(up, "LIVE_DATA", live), \
             mock.patch.object(up, "SECTOR_STATS", ss), \
             mock.patch.object(up, "require_user",
                               lambda: {"id": "U1", "watch": {}, "portfolio": {}}):
            client = up.app.test_client()
            r = client.get("/api/explain/TST")
        body = r.get_json() or {}
        ex = body.get("explanation") or {}
        self.assertTrue(ex, "المفروض الشرح يتبعت: " + repr(body))
        self.assertAlmostEqual(ex.get("base_score", 0) + ex.get("adjustment_total", 0),
                               ex.get("published_score"), delta=0.05,
                               msg="⛔ إعادة تركيب المساهمات ≠ الرقم المنشور")
        total = round(sum(c["contribution"] for c in ex.get("contributions") or []), 1)
        self.assertAlmostEqual(total, ex.get("base_score"), delta=0.1,
                               msg="⛔ مجموع المساهمات ≠ الأساس: " + repr(ex))


# ════════════════════════════════════════════════════════════════
#  ⑦ MD-034 / AZ25-BACKTEST-DAYS
# ════════════════════════════════════════════════════════════════
class TestBacktestWindow(unittest.TestCase):
    """days_back لازم يبقى حدّ عمر حقيقي في الاختيار."""

    def _run(self, days_back, ages):
        snaps = {}
        for age, px in ages:
            d = (datetime.datetime.utcnow() - datetime.timedelta(days=age)).date().isoformat()
            snaps[d] = {"picks": [{"code": "TST", "price": px, "score": 70,
                                   "decision": "neutral", "sector": "Test"}]}
        with mock.patch.object(up, "BACKTEST",
                               {"snapshots": snaps, "results": [], "stats": {}}), \
             mock.patch.object(up, "LIVE_DATA", {"egx30": [{"code": "TST", "price": 120}]}), \
             mock.patch.object(up, "_bt_save", lambda: None):
            return up.bt_evaluate(days_back=days_back)

    def test_days_back_3_excludes_old_snapshot(self):
        r = self._run(3, [(50, 100), (1, 119)])
        ages = [w["age_days"] for w in r.get("windows") or []]
        self.assertTrue(all(a <= 3 for a in ages),
                        "⛔ days_back=3 رجّع نافذة عمرها %s يوم: %r" % (ages, ages))

    def test_days_back_30(self):
        r = self._run(30, [(50, 100), (20, 110), (1, 119)])
        ages = sorted(w["age_days"] for w in r.get("windows") or [])
        self.assertTrue(all(a <= 30 for a in ages),
                        "⛔ days_back=30 رجّع نافذة أقدم: %r" % (ages,))
        self.assertNotIn(50, ages, "⛔ لقطة الـ50 يوم ما ينفعش ترجع في نافذة 30 يوم")
        self.assertIn(20, ages, "لقطة الـ20 يوم لازم تتقاس")

    def test_days_back_90(self):
        r = self._run(90, [(50, 100), (20, 110), (1, 119)])
        ages = sorted(w["age_days"] for w in r.get("windows") or [])
        self.assertTrue(all(a <= 90 for a in ages))
        self.assertIn(50, ages, "نافذة 90 يوم لازم تقيس لقطة الـ50 يوم")

    def test_no_window_means_no_stats(self):
        """مفيش نافذة ⇒ ممنوع إحصائيات قديمة (رقم «مقاس» وهو مش مقاس)."""
        r = self._run(3, [(50, 100), (1, 119)])
        self.assertEqual(r.get("windows") or [], [])
        stats = r.get("stats") or {}
        self.assertEqual(stats.get("windows_measured"), 0,
                         "⛔ ممنوع ترجّع إحصائيات قديمة: %r" % (stats,))
        self.assertTrue(r.get("note") or r.get("status"),
                        "لازم سبب صريح: %r" % (r,))


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
