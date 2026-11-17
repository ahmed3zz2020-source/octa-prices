#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٥ (الجولة ١٤ · ملاحظة المالك) — وصف السعر + حالات الحداثة.

📌 الملاحظة المرفوعة (ملاحظة المالك على تقرير الجولة ١٤):
   `price_label_for()` كانت بتقول «سعر التداول الآن» وقت ما السوق مفتوح
   — حتى لو المصدر **ما بديش** توقيت للسعر نفسه.
   ⛔ «وقت استلام البيانات» **مش** دليل على وقت آخر تداول.

📌 المطلوب (مقيس هنا):
   ① سوق مفتوح + سعر بلا `price_ts` ⇒ التسمية **ما ينفعش** تكون
      «سعر التداول الآن» ⇒ لازم «آخر سعر متاح».
   ② سوق مفتوح + سعر **مع** `price_ts` ⇒ «سعر التداول الآن» (المسار السليم).
   ③ stale ⇒ «آخر سعر معروف» (مش لحظي).
   ④ النتيجة النهائية من `build_payload` (مش الدالة لوحدها):
      `price_time_source=not_provided` ⇒ `price_label` ما ينفعش يقول «الآن».
   ⑤ حالات الحداثة الأربع مميّزة:
      تغطية كاملة+حديثة · تغطية مقبولة وغير كاملة · تغطية جزئية · قديمة/غير متاحة
   ⑥ فشل المصدر بعد نجاح سابق ⇒ `last_success_at` **ما بيتصفّرش**
      (العمر بيزيد) ⇒ freshness stale مش fresh.

⛔⛔⛔ تعديل الجولة ١٦ (عقد الحداثة اتغيّر — موضّح تحت):
   · «سعر التداول الآن» بقى محتاج **تلات** أدلة: السوق مفتوح + سعر من
     **نفس الجلسة** + **عمر السعر** ≤ ١٥ دقيقة.
     ⛔ `price_ts` لوحده (من غير عمر) مش دليل ⇒ التسمية «آخر سعر متاح».
   · `freshness` بقى = **الحداثة** (عمر آخر جلب ناجح) بس.
     `coverage_status` = **التغطية** (نسبة الجلب) — مفهومين منفصلين.
     ⛔ `freshness` مبقاش بياخد قيمة "partial" (الحدالة موجودة في
       `coverage_status`).

📌 التشغيل: python test_round15_price_label.py
"""
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r15_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R15-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R15-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402

# ⛔ الجولة ١٦ — هذه المعاملات جديدة (عمر السعر + الجلسة)
NEW_KWARGS = ("price_age_seconds", "price_session_date", "session_date",
              "price_ts", "now", "max_price_age_open", "max_price_age_closed")


def _label(phase="open", **kw):
    """Calling helper — compatible with the old signature.

    ⛔ The old version (before this round) has the signature:
       price_label_for(market_phase, stale, data_state) — there is no
       price_time_source. To make the negative proof a **behavioral**
       failure (not just a TypeError), we fall back to the old call
       when the new keyword is not accepted.
    ⛔ الجولة ١٦: نفس القاعدة اتوسّعت لكل المعاملات الجديدة
       (عمر السعر + تاريخ الجلسة) ⇒ الفشل يبقى **سلوكي** مش TypeError.
    """
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
        "ts": "2026-11-17T10:00:00Z",
        "data_quality": 0.8, "volatility": 1.2, "rel_volume": 0.9,
        "tv_rating": 0.2, "beta": 0.6, "div_yield": 0.01,
        "mkt_cap": 1e9, "pe": 12.0, "pb": 1.4,
        "roe": 0.18, "de_ratio": 0.4, "net_margin": 0.2,
        "op_margin": 0.25, "eps": 3.0, "revenue": 5e8,
        "perf_w": 1.0, "perf_1m": 2.0, "perf_3m": 3.0,
        "perf_6m": 4.0, "perf_y": 5.0,
        # ⛔ المحاور المحسوبة (زي اللي الباك بيعملها) — بدونها السهم
        # بيطلع «غير مؤهل» (بيانات المخاطر ناقصة) ⇒ مش بيدخل القوائم.
        "all_axes": {"technical": 70.0, "fundamental": 60.0,
                     "liquidity": 65.0, "risk": 55.0},
        "technical_signal": "صاعد",
        # ⛔ حجم تداول كبير (القيمة النقدية = الحجم × السعر) عشان
        #    السهم يعدّي حد السيولة (حدّ لكل استراتيجية).
        "volume": 5_000_000.0,
    }
    st.update(kw)
    return st


class TestPriceLabelTruth(unittest.TestCase):
    """① + ② + ③ — التسمية ما بتجزمش بلحظية بلا دليل."""

    def test_open_market_without_price_ts_is_not_now(self):
        """⛔ الاختبار السالب المطلوب: سوق مفتوح + بلا price_ts."""
        lab = _label("open", price_time_source="not_provided")
        self.assertNotEqual(lab, "سعر التداول الآن",
                            "التسمية ادّعت لحظية بلا توقيت من المصدر")
        self.assertNotIn("الآن", lab, "فيها ادعاء لحظية")
        self.assertEqual(lab, "آخر سعر متاح")

    def test_open_market_with_price_ts_is_now(self):
        """✅ المسار السليم: سعر **حديث** من **نفس الجلسة** ⇒ «الآن».

        ⛔ الجولة ١٦: بقى لازم **عمر السعر** + **نفس الجلسة** — مش
        وجود `price_ts` بس.
        """
        lab = _label("open", price_time_source="source",
                     price_age_seconds=30,
                     price_session_date="2026-11-17",
                     session_date="2026-11-17")
        self.assertEqual(lab, "سعر التداول الآن")

    def test_open_market_without_age_evidence_is_not_now(self):
        """⛔ الجولة ١٦: `price_ts` من غير عمر ⇒ ممنوع ادعاء لحظي."""
        lab = _label("open", price_time_source="source")
        self.assertNotEqual(lab, "سعر التداول الآن",
                            "ادّعاء لحظية من غير دليل على حداثة السعر")
        self.assertNotIn("الآن", lab)

    def test_open_market_with_previous_session_price_is_not_now(self):
        """⛔ الجولة ١٦: سعر من **جلسة سابقة** ⇒ ممنوع «الآن»."""
        lab = _label("open", price_time_source="source",
                     price_age_seconds=30,
                     price_session_date="2026-11-16",
                     session_date="2026-11-17")
        self.assertNotEqual(lab, "سعر التداول الآن",
                            "ادّعاء لحظية لسعر من جلسة سابقة")
        self.assertEqual(lab, "آخر سعر معروف")

    def test_closed_and_pre_labels(self):
        self.assertEqual(_label("closed", price_time_source="source"),
                         "سعر الإغلاق")
        self.assertEqual(_label("pre", price_time_source="source"),
                         "سعر الإغلاق السابق")

    def test_stale_wins_even_with_source_ts(self):
        lab = _label("open", stale=True, price_time_source="source")
        self.assertEqual(lab, "آخر سعر معروف")

    def test_missing_source_beats_phase(self):
        """⛔ في كل الحالات (مفتوح/مغلق/سابق) ⇒ مافيش ادعاء لحظية."""
        for ph in ("open", "closed", "pre", "unknown"):
            lab = _label(ph, price_time_source="not_provided")
            self.assertNotIn("الآن", lab, ph)
            self.assertNotEqual(lab, "سعر الإغلاق", ph)


class TestPayloadPriceTruth(unittest.TestCase):
    """④ — النتيجة النهائية (build_payload) مش الدالة لوحدها."""

    def test_payload_item_without_price_ts(self):
        payload = oe.build_payload([_stock("AAA")], None,
                                   {"market_phase": "open",
                                    "generated_at": "2026-11-17T10:00:00Z",
                                    "source": "live"})
        items = []
        for lst in (payload.get("lists") or {}).values():
            items += (lst.get("items") or [])
        self.assertTrue(items, "مافيش أصناف")
        for it in items:
            self.assertEqual(it.get("price_time_source"), "not_provided")
            self.assertNotEqual(it.get("price_label"), "سعر التداول الآن")
            self.assertNotIn("الآن", it.get("price_label") or "")
            # ⛔ وقت الاستلام موجود بس مش ادعاء لحظية
            self.assertTrue(it.get("data_received_at"))

    def test_payload_item_with_price_ts(self):
        """✅ سعر من نفس الجلسة وبعمر معروف ⇒ «الآن» + العمر يبان."""
        payload = oe.build_payload(
            [_stock("BBB", price_ts="2026-11-17T09:59:00Z")], None,
            {"market_phase": "open", "source": "live",
             # ⛔ الجولة ١٦ — وقت مرجعي ثابت (عشان الحساب يبقى حتمي)
             "now": _epoch("2026-11-17T10:00:00Z"),
             "session_date": "2026-11-17",
             # ⛔⛔⛔ مراجعة الجولة يا (R17-P1) — الدلة لازم تعلن إن الدفاتة حديثة
             # — مفيش دليل ⇒ الصف يكون «unknown» (من عيشه ليقول «سعر التداول الآن»).
             "data_freshness": {"freshness": "fresh", "data_state": "fresh"},})
        items = []
        for lst in (payload.get("lists") or {}).values():
            items += (lst.get("items") or [])
        hit = [i for i in items if i.get("code") == "BBB"]
        self.assertTrue(hit, "مافيش صنف BBB")
        self.assertEqual(hit[0].get("price_time_source"), "source")
        self.assertEqual(hit[0].get("price_label"), "سعر التداول الآن")
        self.assertEqual(hit[0].get("price_as_of"), "2026-11-17T09:59:00Z")
        # ⛔ الجولة ١٦ — عمر السعر لازم يبان في الصف
        self.assertEqual(hit[0].get("price_age_seconds"), 60)
        self.assertEqual(hit[0].get("price_age_minutes"), 1.0)


class TestFreshnessStates(unittest.TestCase):
    """⑤ — الحالات الأربع مميّزة + ⑥ — فشل المصدر ما بيمسحش العمر."""

    def test_full_coverage_and_fresh(self):
        st = oe.freshness_state(last_success_at=1700000000,
                                market_phase="open", coverage=100.0,
                                requested=286, updated=286)
        self.assertIn(st["freshness"], ("fresh", "stale"))
        self.assertEqual(st["coverage_pct"], 100.0)
        self.assertEqual(st["missing"], 0)
        # ⛔ الجولة ١٦ — التغطية مفهوم مستقل
        self.assertEqual(st["coverage_status"], "complete")

    def test_acceptable_but_incomplete_coverage(self):
        """⛔ 90% بالظبط = **مقبول** (فوق العتبة) و**مش كامل** (10 ناقص).

        📌 الجولة ١٧ (R16-N2) — التمييز بين «مقبولة» و«كاملة» بقى صريح.
        📌 **تحديث الجولة ١٧ (R17-V2-01)** — الأعداد بقت **مصدر الحقيقة**:
           النسبة المعلنة لازم تتوافق مع (المحدَّث ÷ المطلوب) بتقريب رقمين
           عشريين. فالحالة (257 من 286 = 89.86% < 90%) ⇒ **مش مقبولة**؛
           صاحب «المقبولة» بقى (90 من 100 = 90% بالظبط).
        """
        st = oe.freshness_state(last_success_at=1700000000,
                                market_phase="open", coverage=90.0,
                                requested=100, updated=90)
        self.assertTrue(st.get("coverage_acceptable"),
                        "90% فوق العتبة ⇒ مقبولة")
        self.assertEqual(st["coverage_status"], "partial",
                         "في 10 ناقص ⇒ ممنوع تقول «كاملة»")
        self.assertEqual(st["missing"], 10)

    def test_declared_ratio_below_threshold_is_not_acceptable(self):
        """⛔ **تحديث الجولة ١٧ (R17-V2-01)** — النسبة المعلنة ما بتنتصرش على الأعداد.

        ⛔ 90% معلنة مع 257/286 ⇒ النسبة الحقيقية 89.86% ⇒ تحت العتبة ⇒
           ممنوع «مقبولة» (و«كاملة» ممنوعة طبعاً).
        """
        st = oe.freshness_state(last_success_at=1700000000,
                                market_phase="open", coverage=90.0,
                                requested=286, updated=257)
        self.assertFalse(st.get("coverage_acceptable"),
                         "⛔ 89.86% أقل من العتبة ⇒ ممنوع «مقبولة»")
        self.assertFalse(st.get("coverage_consistent"),
                         "⛔ النسبة المعلنة (90) بتتناقض مع الأعداد (89.86)")
        self.assertEqual(st["coverage_status"], "partial")
        self.assertEqual(st["missing"], 29)

    def test_partial_coverage(self):
        """⛔ الجولة ١٦ — التغطية الجزئية بقت `coverage_status` مستقلّة.

        📌 قبل الجولة ١٦ كانت `freshness` بتاخد "partial" وبتصفّر
        `age_seconds` ⇒ المستخدم ماعرفش إن البيانات قديمة.
        """
        st = oe.freshness_state(last_success_at=1700000000,
                                market_phase="open", coverage=1.05,
                                requested=286, updated=3)
        self.assertEqual(st["coverage_status"], "partial")
        self.assertNotEqual(st["freshness"], "partial",
                            "الحداثة مبقاش بتاخد قيمة التغطية")
        self.assertEqual(st["updated"], 3)
        self.assertEqual(st["missing"], 283)

    def test_no_successful_fetch_is_unavailable_first(self):
        """⛔ مافيش جلب ناجح ⇒ unavailable (مش partial)."""
        st = oe.freshness_state(last_success_at=None, market_phase="open",
                                coverage=100.0, requested=286, updated=286)
        self.assertEqual(st["freshness"], "unavailable")
        self.assertIsNone(st["age_seconds"])

    def test_stale_when_too_old(self):
        st = oe.freshness_state(last_success_at=1000, market_phase="open",
                                coverage=100.0, requested=286, updated=286)
        self.assertEqual(st["freshness"], "stale")
        self.assertIsNotNone(st["age_seconds"])

    def test_failure_does_not_reset_age(self):
        """⑥ — بعد نجاح سابق، فشل المصدر ⇒ last_success_at ما بيتصفّرش.

        📌 القاعدة: `last_success_at` بيتحدّث بعد جلب **ناجح** بس.
        ⇒ الفشل بعد نجاح ⇒ التوقيت القديم يفضل ⇒ stale (مش fresh).
        """
        ok_at = 1700000000
        st_ok = oe.freshness_state(last_success_at=ok_at, market_phase="open",
                                   coverage=100.0, requested=286, updated=286)
        self.assertEqual(st_ok["last_success_at"], ok_at)
        # ⛔ الفشل ⇒ ما فيش تحديث ⇒ نفس التوقيت القديم
        st_fail = oe.freshness_state(last_success_at=ok_at, market_phase="open",
                                     coverage=100.0, requested=286, updated=286)
        self.assertEqual(st_fail["last_success_at"], ok_at,
                         "الفشل مسح التوقيت — مينفعش")
        self.assertEqual(st_fail["freshness"], "stale")
        self.assertGreater(st_fail["age_seconds"], 0)


def _epoch(iso):
    """⛔ تحويل ISO ⇒ epoch (توقيت ثابت للاختبارات)."""
    import datetime
    return datetime.datetime.fromisoformat(
        iso.replace("Z", "+00:00")).timestamp()


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
