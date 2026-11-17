#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ مراجعة الجولة ١٧ — R17-P3: **العقد يحترم القيم الصريحة**.

📌 **العيب (من المراجعة النهائية)**:
   `_opp_contract()` كانت تختار أول قيمة **truthy** ⇒ القيمة `False`
   (مثل `coverage_acceptable=False`) كانت بتتن-discard ⇒ الرد بيرجع
   قيمة الـpayload (`True`) ⇒ **العقد غلط**.

⛔ **الإصلاح**: التمييز بين «الحقل موجود» و«الحقل مش موجود» —
   `False` و`0` قيم مشروعة وبتتاحترم.

📌 **الاختبار السالب الإلزامي**:
   `list.coverage_acceptable=False` + `payload.coverage_acceptable=True`
   ⇒ الرد لازم يقول `False` (قيمة القائمة).

📌 التشغيل: python test_round17_p3_contract_pick.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
TMP = REPO / (".r17_p3_tmp_%d" % os.getpid())
TMP.mkdir(exist_ok=True)
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R17-ONLY"
os.environ["OCTA_PIN_PEPPER"] = "R17-ONLY"
os.environ["OCTA_BG_TASKS"] = "off"

import update_prices as up  # noqa: E402


class TestP3ContractPick(unittest.TestCase):
    """⛔ R17-P3 — قيم صريحة (False/0) لازم تتاحترم."""

    def test_list_false_beats_payload_true(self):
        """⛔ السالب: قيمة القائمة `False` لازم تغلب `True` من الباك."""
        out = up._opp_contract({"coverage_acceptable": True},
                               {"coverage_acceptable": False})
        self.assertIs(out.get("coverage_acceptable"), False,
                      "⛔ قيمة القائمة اتDiscarded والقيمة من الباك رجعت")

    def test_list_zero_is_not_treated_as_missing(self):
        """⛔ الصفر = قيمة موجودة (مش «مفيش»).

        📌 القيمة نفسها (صفر) مش دلالة في حقول العقد — الاختبار هنا
        بيفحص **قاعدة الحضور** (presence) مش دلالة القيمة.
        """
        out = up._opp_contract({"coverage_status": "complete"},
                               {"coverage_status": 0})
        self.assertEqual(out.get("coverage_status"), 0,
                         "⛔ الصفر اتDiscarded ⇒ القاعدة مشPresence")

    def test_list_value_wins_when_both_present(self):
        """⛔ مفيش ارتجاع: أولوية القائمة على الباك."""
        out = up._opp_contract({"coverage_status": "complete"},
                               {"coverage_status": "partial"})
        self.assertEqual(out.get("coverage_status"), "partial")

    def test_falls_back_to_payload_when_list_lacks_field(self):
        """⛔ مفيش ارتجاع: حقل مش موجود في القائمة ⇒ من الباك."""
        out = up._opp_contract({"coverage_status": "complete"},
                               {"data_state": "stale"})
        self.assertEqual(out.get("coverage_status"), "complete")
        self.assertEqual(out.get("data_state"), "stale")

    def test_none_in_list_falls_back_to_payload(self):
        """⛔ `None` = مش معطى ⇒ الباك."""
        out = up._opp_contract({"coverage_status": "complete"},
                               {"coverage_status": None})
        self.assertEqual(out.get("coverage_status"), "complete")

    def test_missing_everywhere_is_none(self):
        """⛔ مافيش أي مصدر ⇒ None (مش '' ولا 0)."""
        out = up._opp_contract({}, {})
        self.assertIsNone(out.get("coverage_status"))
        self.assertIsNone(out.get("coverage_acceptable"))

    def test_all_contract_fields_present(self):
        """⛔ مفيش ارتجاع: العقد بينشر كل الحقول."""
        out = up._opp_contract({"coverage_status": "partial",
                                "coverage_acceptable": True,
                                "data_state": "stale",
                                "freshness_summary_ar": "بيانات قديمة",
                                "current_session_date": "2026-11-17"}, {})
        for f in ("coverage_status", "coverage_acceptable", "data_state",
                  "freshness_summary_ar", "current_session_date"):
            self.assertIn(f, out, "⛔ حقل ناقص في العقد: " + f)


if __name__ == "__main__":
    unittest.main(verbosity=2)
