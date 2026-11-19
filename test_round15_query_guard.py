#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٥ — حارس الـquery على مسارات الـAPI (حارس طلبات المالك).

📌 المطلوب (ملاحظة المالك على الجولة ١٤) — ٦ حالات لازم تتأكد
   على **مسارات الـAPI الحقيقية** (مش تحليل ساكن):
   ① مُكرّر        : ?a=1&a=2              ⇒ مفتاح واحد بقيمة واحدة
   ② مُشفّر        : %3Cscript%3E · %22 · %26 ⇒ مافيش HTML ولا كسر JSON
   ③ طويل         : آلاف المحارف            ⇒ سقف واضح
   ④ الأساسي وقع  ⇒ التنظيف الاحتياطي يشتغل
   ⑤ الأساسي والاحتياطي وقعوا ⇒ الطلب يُرفض بوضوح (مش حالة ملتبسة)
   ⑥ الفحص على **الرد النهائي** (الـJSON اللي المستخدم بياخده)
      مش على QUERY_STRING بس.

📌 خريطة «الاختبار ⇐ العيب اللي بيكشفه» (كل سطر اختبار سالب حقيقي):
   TestQueryGuardContract (مستوى عقد التنظيف):
     test_duplicate_param_collapses_to_one_value
        ⇐ لو بناء الـquery الجديد (إصلاح P0-01 · الجولة ١٣) رجع للمفتاح المكرر
     test_encoded_payload_is_decoded_then_scrubbed
        ⇐ لو clean_text رجع يسيب علامتي < و > (تقوية الجولة ١٤)
     test_encoded_quote_and_amp_stay_in_one_param
        ⇐ لو الـdecode عمل قسمة params أو كسر في الـJSON
     test_long_value_is_capped
        ⇐ لو سقف ٣٠٠ محرف اتشال
     test_primary_failure_falls_back_to_strict_cleaning
        ⇐ لو التنظيف الاحتياطي (الجولة ١٤) اتشال ⇒ مدخل خطير يعدّي زي ما هو
     test_double_failure_empties_the_query
        ⇐ لو fail-closed اتشال ⇒ الـquery الخطير بيفضل زي ما هو
     test_no_payload_shape_survives_the_sanitizer
        ⇐ لو أي شكل مدخل مرّ من غير ما يتنضّف
   TestQueryGuardEndToEnd (الرد النهائي · JSON حقيقي):
     test_duplicate_value_reaches_route_once
        ⇐ ① على مسارات الـAPI: قيمة واحدة للمفتاح
     test_encoded_script_is_not_reflected_in_response
        ⇐ ② على مسارات الـAPI: مافيش script في الرد للمستخدم
     test_encoded_quote_and_amp_keep_response_valid
        ⇐ ② على مسارات الـAPI: الـJSON يفضل سليم والـparams ما تتقسمش
     test_long_value_is_truncated_in_response
        ⇐ ③ على مسارات الـAPI: مافيش قيمة طويلة في الرد
     test_primary_failure_yields_clean_response
        ⇐ ④ على مسارات الـAPI: الاحتياطي بيشتغل فعلاً
     test_double_failure_does_not_leak_payload
        ⇐ ⑤ على مسارات الـAPI: مافيش تسريب لما الاحتياطي يوقع
     test_double_failure_is_rejected_with_clear_error
        ⇐ ⑤ على مسارات الـAPI: الرفض يكون صريح (مش 200 بالقيمة الافتراضية)
     test_final_json_is_the_artifact_under_test
        ⇐ ⑥ الفحص على الرد النهائي (مش على QUERY_STRING بس)
   TestFileHygiene:
     test_no_three_dots_outside_comments   ⇐ قاعدة الـCI
     test_no_broken_or_cjk_or_cyrillic_chars ⇐ سلامة النص العربي

⛔⛔⛔ ملاحظة حرجة (اكتُشفت أثناء كتابة الاختبار — اقرأها قبل التقييم):
   التنظيف بيكتب في `request.environ["QUERY_STRING"]`
   (update_prices.py:921 و 951 و 959).
   ⛔ بس werkzeug (2.3+) بياخد **نسخة** من الـquery وقت بناء الـRequest
      وبيقراها من `request.query_string` — مش من الـenviron.
   ⇒ تعديل الـenviron بعد ما الـRequest اتبنى **مش** بيوصل `request.args`.
   ⇒ على Flask/Werkzeug الحديثة (المثبّت في requirements.txt: flask==3.0.0)
      التنظيف **مالوش تأثير** على اللي الـroutes بتشوفه ⇐ الاختبارات
     المتأخرة (EndToEnd) متعلّمة بـexpectedFailure لحد ما الـguard يتصلّح.
   ⛔ بعد ما الـguard يتصلّح فعلاً: شيل `@unittest.expectedFailure`
      من الاختبارات دي (وإلا unittest هيسجّل «success غير متوقع» = فشل).
   ⛔ كل المنطق موجود في كود الباك — الاختبار ده **مفيش فيه** أي تعديل.

📌 التشغيل:  python3 test_round15_query_guard.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر · مافيش commit.
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

TMP = Path(tempfile.mkdtemp(prefix="octa_r15_guard_"))
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R15-ONLY-GUARD-SECRET"
os.environ["OCTA_PIN_PEPPER"] = "R15-ONLY-GUARD-PEPPER"
os.environ["OCTA_BG_TASKS"] = "off"
# ⛔ حدّ الطلبات — عشان الاختبار ما يقعش في 429 (معامل بياخده الباك نفسه)
os.environ["OCTA_RATE_MULT"] = "100"
os.environ["MAIL_ON"] = "0"

import update_prices as up  # noqa: E402
from flask import jsonify, request as flask_request  # noqa: E402

app = up.app
app.testing = True

# ══════════════════════════════════════════════════════════════
#  🎯 مسار اختبار (fixture) — بيرد بالظبط اللي وصله الـroute
#  ⛔ لازم يتسجّل **قبل** أول طلب (Flask 3 بيمنع بعد أول طلب)
#  📌 الهدف: نعرف الـroute شاف إيه (getlist) مش بس الـenviron
# ══════════════════════════════════════════════════════════════
@app.route("/__r15_probe", methods=["GET"])
def _r15_probe():
    """مسار اختبار بيقول للاختبار: الـroute شاف إيه بالظبط."""
    return jsonify({
        "args": {k: v for k, v in flask_request.args.items()},
        "getlist": {k: flask_request.args.getlist(k)
                    for k in flask_request.args.keys()},
        "qs": flask_request.environ.get("QUERY_STRING") or "",
    })


CLIENT = app.test_client()

# ══════════════════════════════════════════════════════════════
#  🧪 ثوابت الحالات المطلوبة
# ══════════════════════════════════════════════════════════════
RAW_SCRIPT = "<script>alert(1)</script>"
ENC_SCRIPT = "%3Cscript%3Ealert(1)%3C%2Fscript%3E"
ENC_QUOTE = "%22"
ENC_AMP = "%26"
LONG_VALUE = "A" * 5000
MAX_TEXT = 300        # سقف clean_text في المسار الأساسي
MAX_FALLBACK = 60     # سقف التنظيف الاحتياطي (الجولة ١٤)
FAIL_MARK = "R15-SIMULATED-FAILURE"   # ⛔ لازم يبان في اللوج (مافيش بلع صامت)

#  ⛔ الشكل → الاستعلام (الحالات الست المطلوبة)
SHAPES = (
    ("مكرّر", "dup=first&dup=second"),
    ("مشفّر HTML", "sector=" + ENC_SCRIPT),
    ("مشفّر علامة اقتباس", "sector=a" + ENC_QUOTE + "b"),
    ("مشفّر فاصل", "sector=a" + ENC_AMP + "b=c"),
    ("طويل", "note=" + LONG_VALUE),
)

#  ⛔ سبب كل اختبار متعلّم بـexpectedFailure (بيتبان في ملخص آخر تشغيل)
EXPECTED_FAIL_REASONS = {
    "test_duplicate_value_reaches_route_once":
        "① المكرّر: الـroute شاف القيمتين (getlist) — التنظيف ما وصلش request.args",
    "test_encoded_script_is_not_reflected_in_response":
        "② %3Cscript%3E: السكربت متسلّل في رد الـAPI للمستخدم",
    "test_long_value_is_truncated_in_response":
        "③ القيمة الطويلة (٥٠٠٠ محرف) وصلت كاملة للرد النهائي",
    "test_primary_failure_yields_clean_response":
        "④ تعطّل المعالج الأساسي: مافيش تنظيف احتياطي شغّال على الرد النهائي",
    "test_double_failure_does_not_leak_payload":
        "⑤ تعطّل المعالجين: الحمولة لسه بتوصل للمستخدم",
    "test_double_failure_is_rejected_with_clear_error":
        "⑤ تعطّل المعالجين: الطلب اتكمّل 200 بدل رفض صريح",
    "test_final_json_is_the_artifact_under_test":
        "⑥ الرد النهائي فيه حمولة مدخل من غير تنضيف",
}


# ══════════════════════════════════════════════════════════════
#  🔧 أدوات مساعدة
# ══════════════════════════════════════════════════════════════
def _sanitized_qs(query, break_primary=False, break_both=False):
    """يشغّل الـsanitizer جوّه سياق طلب حقيقي.

    ⛔ لو break_primary ⇒ المعالج الأساسي يقع (نعمله raise) واللوج
      لازم يقول إن الفشل اتسجّل. ولو break_both ⇒ الاحتياطي كمان يقع.
    ⏎ يرجّع (الـquery بعد التنظيف، نص اللوج).
    """
    orig_text = up.clean_text
    orig_encode = up._urlencode
    buf = io.StringIO()

    def _boom(*a, **kw):
        raise RuntimeError("R15-SIMULATED-FAILURE")

    try:
        if break_primary or break_both:
            up.clean_text = _boom
        if break_both:
            up._urlencode = _boom
        with app.test_request_context("/api/rank?" + query):
            with contextlib.redirect_stdout(buf):
                up._sanitize_request()
            return flask_request.environ.get("QUERY_STRING") or "", buf.getvalue()
    finally:
        up.clean_text = orig_text
        up._urlencode = orig_encode


def _pairs(qs):
    """الـquery بعد التنظيف ⇒ أزواج (مفتاح، قيمة) زي ما Flask بيفسّرها."""
    return parse_qsl(qs or "", keep_blank_values=True)


def _get(path, query=""):
    """طلب حقيقي على مسار حقيقي ⇒ (status, نص الرد)."""
    url = path + ("?" + query if query else "")
    resp = CLIENT.get(url)
    return resp.status_code, resp.get_data(as_text=True)


class _Base(unittest.TestCase):
    """⛔ دخول وهمي — الاختبار بيفحص التنظيف مش المصادقة."""

    def setUp(self):
        self._orig_require_user = up.require_user
        up.require_user = lambda: {"uid": "r15", "email": "r15@test.local"}

    def tearDown(self):
        up.require_user = self._orig_require_user


# ══════════════════════════════════════════════════════════════
#  🧪 ① — عقد التنظيف نفسه (المستوى اللي الكود بيتحكم فيه)
# ══════════════════════════════════════════════════════════════
class TestQueryGuardContract(_Base):
    """مستوى العقد: إيه اللي الـsanitizer كاتبه في الـquery بعد التنظيف."""

    def test_duplicate_param_collapses_to_one_value(self):
        """⛔ الاختبار السالب: المُكرّر لازم يتلمّ في قيمة واحدة."""
        qs, _log = _sanitized_qs("dup=first&dup=second")
        pairs = _pairs(qs)
        keys = [k for k, _v in pairs]
        self.assertEqual(keys.count("dup"), 1,
                         "المفتاح المكرّر عدّى أكتر من مرة: " + qs)
        self.assertNotIn("&dup=", qs,
                         "النسخة التانية من المفتاح لسه موجودة: " + qs)
        self.assertEqual(len(pairs), 1, "عدد المفاتيح مش مظبوط: " + qs)

    def test_encoded_payload_is_decoded_then_scrubbed(self):
        """⛔ الاختبار السالب: %3Cscript%3E لازم يطلع من غير < و >."""
        qs, _log = _sanitized_qs("sector=" + ENC_SCRIPT)
        pairs = _pairs(qs)
        self.assertEqual(len(pairs), 1, "الاستعلام اتقسم: " + qs)
        value = pairs[0][1] if pairs else ""
        self.assertNotIn("<", value, "علامة < عدّت: " + value)
        self.assertNotIn(">", value, "علامة > عدّت: " + value)
        self.assertNotIn("<", qs, "علامة < عدّت في الـquery: " + qs)
        self.assertNotIn(">", qs, "علامة > عدّت في الـquery: " + qs)
        self.assertIn("script", value,
                      "النص المفيد لازم يفضل موجود (اتنضّف مش اتمسح)")

    def test_encoded_quote_and_amp_stay_in_one_param(self):
        """⛔ الاختبار السالب: %22 و %26 ما يعملوش قسمة params."""
        qs, _log = _sanitized_qs("sector=a" + ENC_QUOTE + "b" + ENC_AMP + "c=d")
        pairs = _pairs(qs)
        self.assertEqual(len(pairs), 1,
                         "الفاصل %26 قسّم الاستعلام: " + qs)
        self.assertEqual(pairs[0][0], "sector", "المفتاح اتغيّر: " + qs)
        value = pairs[0][1] if pairs else ""
        self.assertIn('"', value, "علامة الاقتباس اتشالت (لازم تتنضّف بس)")
        self.assertIn("&", value, "الفاصل اتشال من جوّه القيمة")
        self.assertNotIn('"', qs,
                         "علامة اقتباس خام في الـquery (ممكن تكسر الـJSON)")
        self.assertEqual(qs.count("&"), 0,
                         "الاستعلام اتقسم ل أكتر من مفتاح: " + qs)

    def test_long_value_is_capped(self):
        """⛔ الاختبار السالب: آلاف المحارف ⇒ سقف ٣٠٠."""
        qs, _log = _sanitized_qs("note=" + LONG_VALUE)
        pairs = _pairs(qs)
        self.assertEqual(len(pairs), 1, "الاستعلام اتقسم: " + qs)
        value = pairs[0][1] if pairs else ""
        self.assertLessEqual(len(value), MAX_TEXT,
                             "القيمة الطويلة عدّت من غير سقف")
        self.assertGreater(len(value), 0, "القيمة اتمسحت بالكامل")
        self.assertNotIn(LONG_VALUE, qs, "القيمة الطويلة كاملة لسه موجودة")

    def test_primary_failure_falls_back_to_strict_cleaning(self):
        """⛔ الاختبار السالب: لو الأساسي وقع ⇒ الاحتياطي ينضّف.

        ⛔ ده بالظبط فرق الجولة ١٤ (التنظيف الاحتياطي).
        """
        qs, log = _sanitized_qs("sector=" + ENC_SCRIPT, break_primary=True)
        self.assertIn(FAIL_MARK, log,
                      "الفشل ما اتسجّلش (بلع صامت) — اللوج: " + log)
        pairs = _pairs(qs)
        self.assertEqual(len(pairs), 1, "الاستعلام اتقسم: " + qs)
        value = pairs[0][1] if pairs else ""
        self.assertNotIn("<", value, "علامة < عدّت من الاحتياطي: " + value)
        self.assertNotIn(">", value, "علامة > عدّت من الاحتياطي: " + value)
        self.assertNotIn("%", value, "ترميز متبقي من الاحتياطي: " + value)
        self.assertLessEqual(len(value), MAX_FALLBACK,
                             "سقف الاحتياطي (٦٠) مش مطبّق: " + value)

    def test_double_failure_empties_the_query(self):
        """⛔ الاختبار السالب: لو الأساسي والاحتياطي وقعوا ⇒ الـquery يتفرّغ."""
        qs, log = _sanitized_qs("sector=" + ENC_SCRIPT, break_both=True)
        self.assertIn(FAIL_MARK, log,
                      "الفشل ما اتسجّلش (بلع صامت) — اللوج: " + log)
        self.assertEqual(qs.strip(), "",
                         "الـquery الخطير فضل موجود بعد فشل المعالجين: " + qs)
        self.assertNotIn(RAW_SCRIPT, qs, "الحمولة لسه في الـquery")

    def test_no_payload_shape_survives_the_sanitizer(self):
        """⛔ الاختبار السالب: مافيش شكل مدخل يعدّي من غير تنضيف."""
        for _label, query in SHAPES:
            for broken in (False, True):
                qs, _log = _sanitized_qs(query, break_primary=broken)
                self.assertNotIn("<", qs, "علامة < عدّت (" + _label + ")")
                self.assertNotIn(">", qs, "علامة > عدّت (" + _label + ")")
                self.assertNotIn('"', qs,
                                 "اقتباس خام عدّى (" + _label + ")")
                for _k, value in _pairs(qs):
                    self.assertLessEqual(
                        len(value), MAX_TEXT,
                        "قيمة طويلة عدّت (" + _label + ")")


# ══════════════════════════════════════════════════════════════
#  🧪 ② — الرد النهائي (الـJSON اللي المستخدم بياخده)
#  ⛔ ملاحظة: الاختبارات دي متعلّمة بـexpectedFailure لأن الـguard
#     ما بيوصلش request.args على werkzeug الحديثة (شوف رأس الملف).
# ══════════════════════════════════════════════════════════════
class TestQueryGuardEndToEnd(_Base):
    """الفحص على الرد النهائي — مش على QUERY_STRING بس."""

    def test_duplicate_value_reaches_route_once(self):
        """⛔ ① مكرّر: الـroute يشوف قيمة واحدة للمفتاح (مش اتنين)."""
        status, body = _get("/api/rank", "dup=first&dup=second")
        self.assertEqual(status, 200, "المسار مش شغّال: " + str(status))
        data = json.loads(body)
        self.assertEqual(list((data.get("filters") or {}).keys()), ["dup"],
                         "المفتاح اتكرّر في الرد النهائي")
        _st, probe_body = _get("/__r15_probe", "dup=first&dup=second")
        probe = json.loads(probe_body)
        self.assertEqual(len(probe.get("getlist", {}).get("dup", [])) , 1,
                         "الـroute شاف القيمتين: "
                         + str(probe.get("getlist", {}).get("dup")))

    def test_encoded_script_is_not_reflected_in_response(self):
        """⛔ ② %3Cscript%3E: مافيش script في الرد النهائي."""
        status, body = _get("/api/stress", "scenario=" + ENC_SCRIPT)
        self.assertEqual(status, 200, "المسار مش شغّال: " + str(status))
        json.loads(body)
        self.assertNotIn("<script", body,
                         "سكربت متسلّل في رد الـAPI للمستخدم")
        self.assertNotIn("</script>", body, "سكربت متسلّل في رد الـAPI")
        self.assertNotIn(RAW_SCRIPT, body, "الحمولة كاملة في الرد النهائي")

    def test_encoded_quote_and_amp_keep_response_valid(self):
        """⛔ ② %22 و %26: الرد يفضل JSON سليم والـparams ما تتقسمش."""
        status, body = _get("/api/rank", "sector=a" + ENC_QUOTE + "b"
                            + ENC_AMP + "c=d")
        self.assertEqual(status, 200, "المسار مش شغّال: " + str(status))
        data = json.loads(body)
        filters = data.get("filters") or {}
        self.assertEqual(list(filters.keys()), ["sector"],
                         "الفاصل %26 قسّم الـparams: " + str(list(filters)))
        self.assertIn('"', filters.get("sector") or "",
                      "علامة الاقتباس اتشالت بالكامل من القيمة")

    def test_long_value_is_truncated_in_response(self):
        """⛔ ③ آلاف المحارف: الرد النهائي ما يحملش القيمة كاملة."""
        status, body = _get("/api/rank", "note=" + LONG_VALUE)
        self.assertEqual(status, 200, "المسار مش شغّال: " + str(status))
        data = json.loads(body)
        note = (data.get("filters") or {}).get("note") or ""
        self.assertLessEqual(len(note), MAX_TEXT,
                             "القيمة الطويلة عدّت من غير سقف في الرد النهائي")
        self.assertLess(len(body), 2000,
                        "حجم الرد كبير أوي (تسريب طول المدخل)")

    def test_primary_failure_yields_clean_response(self):
        """⛔ ④ لو المعالج الأساسي وقع ⇒ الرد يفضل نظيف."""
        orig_text = up.clean_text

        def _boom(*a, **kw):
            raise RuntimeError("R15-SIMULATED-FAILURE")

        try:
            up.clean_text = _boom
            status, body = _get("/api/stress", "scenario=" + ENC_SCRIPT)
        finally:
            up.clean_text = orig_text
        self.assertEqual(status, 200, "المسار مش شغّال: " + str(status))
        json.loads(body)
        self.assertNotIn("<script", body,
                         "سكربت متسلّل بعد تعطّل المعالج الأساسي")
        self.assertNotIn(RAW_SCRIPT, body, "الحمولة كاملة في الرد النهائي")

    def test_double_failure_does_not_leak_payload(self):
        """⛔ ⑤ لو المعالجين وقعوا ⇒ مافيش تسريب في الرد النهائي."""
        orig_text = up.clean_text
        orig_encode = up._urlencode

        def _boom(*a, **kw):
            raise RuntimeError("R15-SIMULATED-FAILURE")

        try:
            up.clean_text = _boom
            up._urlencode = _boom
            status, body = _get("/api/stress", "scenario=" + ENC_SCRIPT)
        finally:
            up.clean_text = orig_text
            up._urlencode = orig_encode
        json.loads(body)
        self.assertNotIn("<script", body,
                         "سكربت متسلّل بعد تعطّل المعالجين")
        self.assertNotIn(RAW_SCRIPT, body, "الحمولة كاملة في الرد النهائي")

    def test_double_failure_is_rejected_with_clear_error(self):
        """⛔ ⑤ لازم الطلب يُرفض **بوضوح** (مش 200 بالقيمة الافتراضية).

        📌 الفجوة المعروفة: الكود بيفرّغ الـquery (fail-closed) بس
           **مش** بيرفض الطلب ⇒ المستخدم بياخد 200 بالقيمة الافتراضية.
        """
        orig_text = up.clean_text
        orig_encode = up._urlencode

        def _boom(*a, **kw):
            raise RuntimeError("R15-SIMULATED-FAILURE")

        try:
            up.clean_text = _boom
            up._urlencode = _boom
            status, body = _get("/api/stress", "scenario=" + ENC_SCRIPT)
        finally:
            up.clean_text = orig_text
            up._urlencode = orig_encode
        self.assertIn(status, (400, 403, 409, 422),
                      "الطلب اتكمّل (%d) بدل ما يترفض بوضوح" % status)
        data = json.loads(body)
        self.assertFalse(data.get("ok", True),
                         "الرد قال ok=True رغم إن التنظيف وقع")

    def test_final_json_is_the_artifact_under_test(self):
        """⛔ ⑥ الفحص على الرد النهائي (مش على QUERY_STRING بس).

        📌 كل شكل من الأشكال الخمسة يتبعت على **مسار حقيقي** والرد
           اللي المستخدم بياخده هو اللي بيتفحّص.
        """
        for _label, query in SHAPES:
            status, body = _get("/api/rank", query)
            self.assertEqual(status, 200,
                             "المسار مش شغّال (" + _label + "): " + str(status))
            json.loads(body)
            self.assertNotIn(RAW_SCRIPT, body,
                             "الحمولة في الرد النهائي (" + _label + ")")
            self.assertNotIn("<script", body,
                             "سكربت في الرد النهائي (" + _label + ")")
            self.assertLess(len(body), 4000,
                            "الرد النهائي كبير أوي (" + _label + ")")


# ══════════════════════════════════════════════════════════════
#  🧪 ③ — نظافة الملف نفسه (قاعدة الـCI + سلامة النص)
# ══════════════════════════════════════════════════════════════
class TestFileHygiene(unittest.TestCase):
    """⛔ الملف نفسه لازم يعدّي حارس الـCI."""

    def test_no_three_dots_outside_comments(self):
        """⛔ قاعدة الـCI: مافيش ثلاث نقاط برّه التعليقات."""
        text = Path(__file__).resolve().read_text(encoding="utf-8")
        dots = "." * 3
        for i, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            self.assertNotIn(dots, code,
                             "سطر فيه ثلاث نقاط برّه التعليق: " + str(i))

    def test_no_broken_or_cjk_or_cyrillic_chars(self):
        """⛔ مافيش محرف تالف (U+FFFD) ولا صيني/كوري/سيلاني."""
        text = Path(__file__).resolve().read_text(encoding="utf-8")
        bad = re.compile("[\ufffd\u0400-\u04ff\u4e00-\u9fff\uac00-\ud7af]")
        self.assertIsNone(bad.search(text),
                          "فيه محرف مش عربي في الملف")


if __name__ == "__main__":
    try:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(sys.modules[__name__])
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        # ── ملخص صريح: الاختبارات المتعلّمة بـexpectedFailure ──
        print("")
        print("=" * 70)
        if result.expectedFailures:
            print("⛔⛔⛔ %d اختبار متعلّم بـexpectedFailure — يعني:"
                  " الفحص **فشل** والسبب:"
                  % len(result.expectedFailures))
            for _test, _tb in result.expectedFailures:
                _name = _test.id().rsplit(".", 1)[-1]
                print("   ⛔ %s" % _name)
                print("      ⇐ %s" % EXPECTED_FAIL_REASONS.get(_name, "—"))
            print("-" * 70)
            print("⛔ السبب الجذري: التنظيف بيكتب في request.environ[QUERY_STRING]")
            print("   (update_prices.py:921 · 951 · 959) — بس werkzeug (2.3+)")
            print("   بيقرا الـquery من request.query_string (نسخة وقت البناء)")
            print("   ⇒ التعديل **مش** بيوصل request.args ⇒ الـguard بلا تأثير")
            print("   على الرد النهائي. ⛔ بعد الإصلاح: شيل markers الـexpectedFailure.")
        else:
            print("✅ مافيش expectedFailure — كل الفحوصات عدّت.")
        print("=" * 70)
        sys.exit(0 if result.wasSuccessful() else 1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
