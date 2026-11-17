#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٦ — حداثة **السعر** + فصل **التغطية** عن **الحداثة**.

📌 **العيب ١ (خطورة 4/5) — وصف السعر كاذب**:
   وجود `price_ts` كان كافي عشان مصدر الوقت يبقى "source" ⇒ «سعر التداول
   الآن» ممكن يظهر وسوق مفتوح **حتى لو توقيت السعر قديم** و`stale=False`.
   ⛔ الحل: `price_age_seconds = now - price_ts` (عمر السعر نفسه مش عمر
   آخر جلب) + «الآن» مسموحة بس لو: السوق مفتوح **و** السعر من **نفس
   الجلسة الحالية** **و** عمره ≤ ١٥ دقيقة.

📌 **العيب ٢ (خطورة 4/5) — خلط التغطية بالحداثة**:
   تغطية < ٩٠٪ كانت بتنتج `partial` و`age_seconds=None` **قبل** ما نفحص
   عمر آخر جلب ناجح ⇒ المستخدم مش بعرف البيانات قديمة ولا التغطية جزئية
   في نفس الوقت.
   ⛔ الحل: `coverage_status` (كامل/جزئي/غير متاح) منفصل عن `freshness`
   (حديث/قديم/غير متاح) + `age_seconds` بيتحسب **دايماً**.

📌 **الاختبارات السالبة الإلزامية (negative proof)**:
   ① سوق مفتوح + سعر من **جلسة سابقة** + `stale=False`
      ⇒ ممنوع «سعر التداول الآن».
   ② تغطية 89.9٪ + آخر جلب من **عدة أيام**
      ⇒ لازم يبان **معًا**: (أ) البيانات قديمة (ب) التغطية جزئية.
   ⛔ الاختباران دول **بيفشلوا** على كود الجولة ١٥ (السلوك القديم).

📌 **ثوابت ما تتغيّرش** (الجولة ١٦ ما لمستهاش):
   · «المحور الناقص = الأسوأ» (المحور الناقص بيزوّل الدرجة والتغطية).
   · «نفس الدرجة بين Free وPro» (مافيش اختلاف في دقة الحساب).

📌 التشغيل: python test_round16_price_freshness.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r16_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R16-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R16-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402

NOW_ISO = "2026-11-17T10:00:00Z"
SESSION = "2026-11-17"
PREV_SESSION = "2026-11-16"

# ⛔ المعاملات الجديدة في الجولة ١٦ (عمر السعر + تاريخ الجلسة)
NEW_KWARGS = ("price_age_seconds", "price_session_date", "session_date",
              "price_ts", "now", "max_price_age_open", "max_price_age_closed")


def _epoch(iso):
    """⛔ تحويل ISO ⇒ epoch (توقيت ثابت للاختبارات)."""
    import datetime
    return datetime.datetime.fromisoformat(
        iso.replace("Z", "+00:00")).timestamp()


def _price_age(price_ts, now=None):
    """⛔ عمر السعر — متوافق مع الكود القديم (لو الدالة مش موجودة ⇒ None).

    📌 الهدف: يبقى **الاختبار السالب** فشل *سلوكي* على الكود القديم
       (مش TypeError).
    """
    fn = getattr(oe, "price_age_seconds_from", None)
    if fn is None:
        return None
    return fn(price_ts, now)


def _label(phase="open", **kw):
    """Calling helper — متوافق مع توقيع الجولة ١٥ (fallback للسلوك القديم)."""
    try:
        return oe.price_label_for(phase, **kw)
    except TypeError:
        old = dict(kw)
        old.pop("price_time_source", None)
        for _k in NEW_KWARGS:
            old.pop(_k, None)
        return oe.price_label_for(phase, **old)


def _stock(code, **kw):
    st = {
        "code": code, "name": "سهم " + code, "sector": "صناعة",
        "price": 100.0, "change": 1.0, "close": 100.0,
        "ts": NOW_ISO,
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


def _payload(stocks, phase="open", now=None, session=SESSION):
    meta = {"market_phase": phase, "source": "live",
            "generated_at": NOW_ISO, "now": now if now is not None
            else _epoch(NOW_ISO), "session_date": session,
            # ⛔⛔⛔ مراجعة الجولة يا (R17-P1) — الدلة لازم تعلن إن الدفاتة حديثة
            # — مفيش دليل ⇒ الصف يكون «unknown» (من عيشه ليقول «سعر التداول الآن»).
            "data_freshness": {"freshness": "fresh", "data_state": "fresh"}}
    p = oe.build_payload(stocks, None, meta)
    items = {}
    for lst in (p.get("lists") or {}).values():
        for it in (lst.get("items") or []):
            items[it.get("code")] = it
    return p, items


class TestPriceAgeTruth(unittest.TestCase):
    """⛔ العيب ١ — عمر السعر نفسه + منع الوصف الكاذب."""

    def test_price_age_is_measured_from_price_ts(self):
        """📌 `price_age_seconds = now - price_ts` (مش عمر آخر جلب)."""
        now = _epoch(NOW_ISO)
        self.assertEqual(_price_age("2026-11-17T09:58:00Z", now), 120)
        self.assertIsNone(_price_age(None, now),
                          "مافيش price_ts ⇒ العمر مجهول (مش صفر)")

    def test_negative_open_market_previous_session_is_not_now(self):
        """⛔⛔⛔ الاختبار السالب الإلزامي ① — سعر من جلسة سابقة.

        📌 الحالة: سوق مفتوح + `stale=False` + سعر مصدره من **جلسة سابقة**
           ⇒ ممنوع «سعر التداول الآن».
        """
        lab = _label("open", stale=False, price_time_source="source",
                     price_age_seconds=45,
                     price_session_date=PREV_SESSION,
                     session_date=SESSION)
        self.assertNotEqual(lab, "سعر التداول الآن",
                            "وصف كاذب: سعر من جلسة سابقة اتسمّى «الآن»")
        self.assertNotIn("الآن", lab)
        self.assertEqual(lab, "آخر سعر معروف")

    def test_negative_stale_false_alone_is_not_live(self):
        """⛔⛔⛔ `stale=False` لوحده ما بيخليش السعر لحظي."""
        lab = _label("open", stale=False, price_time_source="source")
        self.assertNotEqual(lab, "سعر التداول الآن",
                            "ادّعاء لحظية بلا دليل على حداثة السعر")
        self.assertNotIn("الآن", lab)

    def test_negative_old_price_in_open_market_is_not_now(self):
        """⛔ سعر قديم (ساعتين) وسوق مفتوح ⇒ ممنوع «الآن»."""
        lab = _label("open", stale=False, price_time_source="source",
                     price_age_seconds=7200,
                     price_session_date=SESSION, session_date=SESSION)
        self.assertNotEqual(lab, "سعر التداول الآن")
        self.assertEqual(lab, "آخر سعر معروف")

    def test_open_market_current_session_recent_price_is_now(self):
        """✅ المسار السليم: نفس الجلسة + عمر ٤٥ ثانية ⇒ «الآن»."""
        lab = _label("open", stale=False, price_time_source="source",
                     price_age_seconds=45,
                     price_session_date=SESSION, session_date=SESSION)
        self.assertEqual(lab, "سعر التداول الآن")

    def test_payload_previous_session_price_is_not_now(self):
        """⛔⛔⛔ نفس الاختبار السالب على مستوى الـpayload (الصف)."""
        st = _stock("OLD1", price_ts="2026-11-16T14:20:00Z")
        _p, items = _payload([st])
        it = items.get("OLD1")
        self.assertIsNotNone(it, "مافيش الصنف OLD1")
        self.assertNotEqual(it.get("price_label"), "سعر التداول الآن",
                            "وصف كاذب على مستوى الصف")
        self.assertEqual(it.get("price_label"), "آخر سعر معروف")

    def test_payload_current_session_price_is_now_with_age(self):
        """✅ نفس الجلسة + عمر معروف ⇒ «الآن» + العمر يبان في الصف."""
        st = _stock("NEW1", price_ts="2026-11-17T09:59:00Z")
        _p, items = _payload([st])
        it = items.get("NEW1")
        self.assertIsNotNone(it, "مافيش الصنف NEW1")
        self.assertEqual(it.get("price_label"), "سعر التداول الآن")
        self.assertEqual(it.get("price_age_seconds"), 60)
        self.assertEqual(it.get("price_age_minutes"), 1.0)
        self.assertTrue(it.get("price_age_label_ar"))

    def test_row_shows_price_age_even_when_price_ts_exists(self):
        """⛔ الجولة ١٦ — عمر السعر لازم يبان في الصف (ثواني/دقائق)."""
        st = _stock("AGE1", price_ts="2026-11-17T09:40:00Z")
        _p, items = _payload([st])
        it = items.get("AGE1")
        self.assertIsNotNone(it)
        self.assertEqual(it.get("price_age_seconds"), 1200)
        self.assertEqual(it.get("price_age_minutes"), 20.0)
        self.assertIn("دقيقة", it.get("price_age_label_ar") or "")
        self.assertEqual(it.get("price_session_date"), SESSION)
        self.assertEqual(it.get("current_session_date"), SESSION)

    def test_row_without_price_ts_has_no_fake_age(self):
        """⛔ مافيش price_ts ⇒ العمر مجهول (مش صفر) والوصف مش لحظي."""
        st = _stock("NOAGE")
        _p, items = _payload([st])
        it = items.get("NOAGE")
        self.assertIsNotNone(it)
        self.assertIsNone(it.get("price_age_seconds"))
        self.assertNotEqual(it.get("price_label"), "سعر التداول الآن")

    def test_price_age_is_not_the_fetch_time(self):
        """⛔ عمر السعر ≠ وقت استلام البيانات (Fetch ≠ Price)."""
        fresh = _stock("P1", price_ts="2026-11-17T09:59:30Z")
        old = _stock("P2", price_ts="2026-11-16T14:20:00Z")
        _p, items = _payload([fresh, old])
        a = items.get("P1")
        b = items.get("P2")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(a.get("data_received_at"), NOW_ISO)
        self.assertEqual(b.get("data_received_at"), NOW_ISO)
        self.assertIsNotNone(a.get("price_age_seconds"))
        self.assertIsNotNone(b.get("price_age_seconds"))
        self.assertLess(a.get("price_age_seconds"), b.get("price_age_seconds"))

    def test_free_tier_keeps_price_age(self):
        """⛔ باقة Free بتعرض عمر السعر كمان (مش مخفي)."""
        stocks = [_stock("F%02d" % i, price_ts="2026-11-17T09:59:00Z")
                  for i in range(8)]
        payload, _items = _payload(stocks)
        free = oe.apply_tier(payload, "free")
        pro = oe.apply_tier(payload, "pro")
        for plan, out in (("free", free), ("pro", pro)):
            for lst in (out.get("lists") or {}).values():
                for it in (lst.get("items") or []):
                    self.assertIsNotNone(it.get("price_age_seconds"), plan)
                    self.assertTrue(it.get("price_age_label_ar"), plan)


class TestCoverageVsFreshness(unittest.TestCase):
    """⛔ العيب ٢ — التغطية مفهوم **منفصل** عن الحداثة."""

    def test_negative_partial_coverage_and_old_fetch_shows_both(self):
        """⛔⛔⛔ الاختبار السالب الإلزامي ② — ٨٩.٩٪ + جلب من ٣ أيام.

        📌 لازم يبان **معًا**:
           (أ) البيانات قديمة (الحداثة)
           (ب) التغطية جزئية
        """
        now = _epoch(NOW_ISO)
        st = oe.freshness_state(now - 3 * 86400, "open", now,
                                 coverage=89.9, requested=286, updated=257)
        # (أ) البيانات قديمة
        self.assertEqual(st["freshness"], "stale",
                         "العيب: البيانات القديمة اتغطت التغطية")
        self.assertIsNotNone(st["age_seconds"],
                             "العمر لازم يتحسب حتى مع تغطية جزئية")
        # (ب) التغطية جزئية
        self.assertEqual(st.get("coverage_status"), "partial")
        # ⛔ مافيش خلط بين المفهومين
        self.assertNotEqual(st["freshness"], "partial")

    def test_partial_coverage_still_computes_age(self):
        """⛔ التغطية الجزئية ما بتلغيش حساب العمر."""
        now = _epoch(NOW_ISO)
        st = oe.freshness_state(now - 30, "open", now,
                                 coverage=89.9, requested=286, updated=257)
        self.assertEqual(st.get("coverage_status"), "partial")
        self.assertEqual(st["freshness"], "fresh")
        self.assertEqual(st["age_seconds"], 30)

    def test_freshness_values_never_carry_coverage(self):
        """⛔ `freshness` = حديث/قديم/غير متاح بس (مافيش partial)."""
        now = _epoch(NOW_ISO)
        for cov, age in ((100.0, 30), (89.9, 30), (10.0, 30),
                         (100.0, 5 * 86400), (10.0, 5 * 86400)):
            st = oe.freshness_state(now - age, "open", now, coverage=cov,
                                     requested=100, updated=50)
            self.assertIn(st["freshness"], ("fresh", "stale", "unavailable"))
            self.assertIn(st.get("coverage_status"),
                          ("complete", "partial", "unavailable"))

    def test_no_successful_fetch_is_unavailable(self):
        """⛔ مافيش جلب ناجح ⇒ غير متاح (مش جزئي ومش قديم)."""
        st = oe.freshness_state(None, "open", _epoch(NOW_ISO),
                                 coverage=89.9, requested=286, updated=257)
        self.assertEqual(st["freshness"], "unavailable")
        self.assertIsNone(st["age_seconds"])
        self.assertEqual(st.get("coverage_status"), "partial")

    def test_data_state_reflects_freshness_not_coverage(self):
        """⛔ `data_state` = الحداثة (مش التغطية)."""
        now = _epoch(NOW_ISO)
        st = oe.freshness_state(now - 3 * 86400, "open", now,
                                 coverage=89.9, requested=286, updated=257)
        self.assertEqual(st.get("data_state"), "stale")
        self.assertEqual(st.get("data_state"), st["freshness"])
        self.assertNotEqual(st.get("data_state"), "partial")

    def test_payload_surfaces_both_facts_together(self):
        """⛔⛔⛔ الـpayload لازم يوصّل **(أ) قديمة** و**(ب) تغطية جزئية**."""
        now = _epoch(NOW_ISO)
        fresh_state = oe.freshness_state(now - 3 * 86400, "open", now,
                                         coverage=89.9, requested=286,
                                         updated=257)
        meta = {"market_phase": "open", "source": "live", "now": now,
                "session_date": SESSION,
                "data_freshness": fresh_state,
                "freshness": fresh_state.get("freshness"),
                "coverage_status": fresh_state.get("coverage_status")}
        payload = oe.build_payload([_stock("BOTH")], None, meta)
        self.assertEqual(payload.get("freshness"), "stale")
        self.assertEqual(payload.get("coverage_status"), "partial")
        self.assertEqual(payload.get("data_state"), "stale")
        self.assertIsNotNone(payload.get("age_seconds"))
        summary = payload.get("freshness_summary_ar") or ""
        self.assertIn("قديمة", summary, "المستخدم لازم يعرف البيانات قديمة")
        self.assertIn("جزئية", summary, "المستخدم لازم يعرف التغطية جزئية")
        for lst in (payload.get("lists") or {}).values():
            self.assertEqual(lst.get("coverage_status"), "partial")
            self.assertEqual(lst.get("data_state"), "stale")

    def test_fresh_with_partial_coverage_is_reported_as_both(self):
        """⛔ حداثة + تغطية ناقصة ⇒ الاتنين يبانوا (مش «fresh» وحده)."""
        now = _epoch(NOW_ISO)
        fresh_state = oe.freshness_state(now - 30, "open", now,
                                         coverage=89.9, requested=286,
                                         updated=257)
        meta = {"market_phase": "open", "source": "live", "now": now,
                "data_freshness": fresh_state,
                "freshness": fresh_state.get("freshness")}
        payload = oe.build_payload([_stock("BOTH2")], None, meta)
        self.assertEqual(payload.get("freshness"), "fresh")
        self.assertEqual(payload.get("coverage_status"), "partial")
        summary = payload.get("freshness_summary_ar") or ""
        self.assertIn("حديثة", summary)
        self.assertIn("جزئية", summary)


class TestInvariantsUnchanged(unittest.TestCase):
    """⛔ ثوابت الجولة ١٦ ما لمستهاش."""

    def test_missing_axis_is_worst(self):
        """⛔ «المحور الناقص = الأسوأ» — الدرجة والتغطية بينزلوا."""
        full = _stock("FULL")
        missing = _stock("MISS")
        missing["all_axes"] = {"fundamental": 60.0, "liquidity": 65.0,
                               "risk": 55.0}     # ⛔ محور الفني ناقص
        defs = oe.load_definitions()
        st_full = oe.evaluate_strategy(full, defs["strategies"][0],
                                       oe.evaluate_item(full))
        st_miss = oe.evaluate_strategy(missing, defs["strategies"][0],
                                       oe.evaluate_item(missing))
        self.assertLess(st_miss["coverage"], st_full["coverage"],
                        "المحور الناقص ماخفّش التغطية")
        self.assertLess(st_miss["score"], st_full["score"],
                        "المحور الناقص ماخفّش الدرجة")

    def test_free_and_pro_have_same_scores(self):
        """⛔ «نفس الدرجة بين Free وPro» — مافيش اختلاف في دقة الحساب."""
        stocks = [_stock("S%02d" % i) for i in range(30)]
        payload, items = _payload(stocks)
        free = oe.apply_tier(payload, "free")
        pro = oe.apply_tier(payload, "pro")
        free_scores = {}
        for lst in (free.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                free_scores.setdefault(it.get("code"), it.get("score"))
        pro_scores = {}
        for lst in (pro.get("lists") or {}).values():
            for it in (lst.get("items") or []):
                pro_scores.setdefault(it.get("code"), it.get("score"))
        self.assertTrue(free_scores)
        for code, sc in free_scores.items():
            self.assertEqual(pro_scores.get(code), sc,
                             "الدرجة اختلفت بين Free وPro")
        self.assertEqual(free.get("limit_per_strategy"), 5)
        self.assertEqual(pro.get("limit_per_strategy"), 20)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
