#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ١٦ — حدود الـquery: رفض آمن (fail-closed) قبل أي تحليل.

📌 المطلوب (ملاحظة المالك · الجولة ١٦ · بند ٤) — ٦ حدود لازم
   تتأكد على **مسارات حقيقية** (مش تحليل ساكن):
   ① طول الـQuery String كله            ⇒ ٤٠٠ صريح (query_too_long)
   ② عدد المعاملات                       ⇒ ٤٠٠ صريح (too_many_params)
   ③ طول اسم المعاملة                   ⇒ ٤٠٠ صريح (param_name_too_long)
   ④ طول قيمة المعاملة الواحدة          ⇒ ٤٠٠ صريح (param_value_too_long)
   ⑤ فشل كتابة request.query_string    ⇒ ٤٠٠ صريح (query_sanitize_failed)
   ⑥ فشل إبطال كاش request.args         ⇒ ٤٠٠ صريح (query_sanitize_failed)

   ⛔ الأسبقية: كل الحدود دي بتتحقق **قبل** أي parse (parse_qsl)
      ⇒ ولا قيمة خام واحدة بتمشي لحد الـroute.
   ⛔ وكل رفض لازم يكون: رد ٤٠٠ واضح + **مافيش** أي جزء من الـquery
      الخام في الرد + الـroute **ما شغّاش**.

📌 خريطة «الاختبار ⇐ العيب اللي بيكشفه» (كل سطر اختبار سالب حقيقي):
   TestQueryLimitConstants (مستوى العقد: الثوابت في مكان واحد):
     test_limits_are_declared_in_one_place
        ⇐ لو الثوابت اتنقلت/اتشالت من مكانها المعلن
     test_limit_values_are_sane
        ⇐ لو حد بقى صفر أو سالب (يعني مافيش حماية خالص)
   TestQueryLimitContract (مستوى الـsanitizer نفسه):
     test_normal_query_passes_the_limits
        ⇐ لو الحدود بقت شنطة ⇒ الطلبات العادية اترفضت
     test_too_many_params_are_rejected
        ⇐ لو عدد المعاملات مش متbounded
     test_long_param_name_is_rejected
        ⇐ لو طول اسم المعاملة مش متbounded
     test_long_param_value_is_rejected
        ⇐ لو طول قيمة المعاملة مش متbounded
     test_long_query_string_is_rejected
        ⇐ لو طول الـquery الكلي مش متbounded
     test_rejection_empties_the_raw_query
        ⇐ لو الـquery الخام فضل في الـrequest بعد الرفض
   TestQueryLimitEndToEnd (الرد النهائي · مسارات حقيقية):
     test_many_params_are_rejected_without_leak
        ⇐ ② على المسار الحقيقي: رفض واضح + مافيش قيمة خام في الرد
     test_long_name_is_rejected_without_leak
        ⇐ ③ على المسار الحقيقي: رفض واضح + مافيش قيمة خام في الرد
     test_long_value_is_rejected_without_leak
        ⇐ ④ على المسار الحقيقي: رفض واضح + مافيش قيمة خام في الرد
     test_long_query_is_rejected_without_leak
        ⇐ ① على المسار الحقيقي: رفض واضح + مافيش قيمة خام في الرد
     test_route_never_runs_on_rejected_request
        ⇐ ⛔ الـroute ما شغّاش بالقيمة غير النضيفة
     test_query_string_write_failure_is_rejected
        ⇐ ⑤ فشل الكتابة ⇒ رفض ٤٠٠ (مش 200 بالقيمة الخام)
     test_args_cache_invalidation_failure_is_rejected
        ⇐ ⑥ فشل إبطال الكاش ⇒ رفض ٤٠٠ (مش 200 بالقيمة الخام)
   TestFileHygiene:
     test_no_three_dots_outside_comments   ⇐ قاعدة الـCI
     test_no_broken_or_cjk_or_cyrillic_chars ⇐ سلامة النص العربي

📌 محاكاة الفشل (٥ و ٦) — على **طلب حقيقي** من غير لمس كود الباك:
   · ⑤ بنبدّل class الطلب بـclass الـquery_string بتاعها setter بيرمي
     ⇒ الكتابة بتفشل والقراءة بتفضل شغّالة (زي الواقع).
   · ⑥ بنبدّل __dict__ الطلب بـdict ف(pop) بتيرمي على "args"
     ⇒ إبطال الكاش بيفشل.

📌 التشغيل:  python3 test_round16_query_limits.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

TMP = Path(tempfile.mkdtemp(prefix="octa_r16_limits_"))
os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "R16-ONLY-LIMITS-SECRET"
os.environ["OCTA_PIN_PEPPER"] = "R16-ONLY-LIMITS-PEPPER"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["OCTA_RATE_MULT"] = "100"
os.environ["MAIL_ON"] = "0"

import update_prices as up  # noqa: E402
from flask import jsonify, request as flask_request  # noqa: E402

app = up.app
app.testing = True

# ══════════════════════════════════════════════════════════════
#  🎯 مسار اختبار (fixture) — بيرد بالظبط اللي وصله الـroute
#  ⛔ لازم يتسجّل **قبل** أول طلب (Flask 3 بيمنع بعد أول طلب)
#  📌 الهدف: نعرف الـroute شاف إيه (-its args) مش بس الـenviron
# ══════════════════════════════════════════════════════════════
PROBE_HITS = []


@app.route("/__r16_probe", methods=["GET"])
def _r16_probe():
    """مسار اختبار بيقول للاختبار: الـroute شاف إيه بالظبط."""
    _seen = {k: v for k, v in flask_request.args.items()}
    PROBE_HITS.append(_seen)
    return jsonify({"args": _seen,
                    "qs": flask_request.environ.get("QUERY_STRING") or ""})


CLIENT = app.test_client()

# ══════════════════════════════════════════════════════════════
#  🧪 ثوابت الحالات المطلوبة (أحجام ثابتة — مش متعلقة بالثوابت)
# ══════════════════════════════════════════════════════════════
RAW_MARK = "R16-RAW-MARKER"        # ⛔ لازم ما يبانش في أي رد
FAIL_MARK = "R16-SIMULATED-FAILURE"  # ⛔ لازم يبان في اللوج (مافيش بلع صامت)

MANY_PARAMS = 500        # ⛔ أكبر من أي حد معقول (السقف ٦٤)
LONG_NAME_CHARS = 1000   # ⛔ أطول من أي اسم معقول (السقف ١٢٨)
LONG_VALUE_CHARS = 12000  # ⛔ أطول من أي قيمة معقولة (السقف ٨١٩٢)
LONG_QUERY_CHARS = 20000   # ⛔ أطول من أي query معقول (السقف ١٦٣٨٤)

WHY_TOO_LONG = "query_too_long"
WHY_TOO_MANY = "too_many_params"
WHY_NAME_TOO_LONG = "param_name_too_long"
WHY_VALUE_TOO_LONG = "param_value_too_long"
WHY_SANITIZE_FAILED = "query_sanitize_failed"


def _limit(name, fallback):
    """⛔ حد الباك لو موجود — وإلا القيمة المرجعية (عشان الاختبار
    ⛔ يفضل شغّال على الكود القديم (اللي مافيش فيه حدود أصلاً)."""
    return getattr(up, name, fallback)


# ══════════════════════════════════════════════════════════════
#  🔧 أدوات مساعدة
# ══════════════════════════════════════════════════════════════
def _get(path, query=""):
    """طلب حقيقي على مسار حقيقي ⇒ (status, نص الرد)."""
    url = path + ("?" + query if query else "")
    resp = CLIENT.get(url)
    return resp.status_code, resp.get_data(as_text=True)


def _sanitize_call(query):
    """يشغّل الـsanitizer جوّه سياق طلب حقيقي.

    ⏎ (status, why, qs_بعد_التنظيف) — status=0 يعني مفيش رفض.
    """
    with app.test_request_context("/__r16_probe?" + query):
        with contextlib.redirect_stdout(io.StringIO()):
            out = up._sanitize_request()
        qs = flask_request.environ.get("QUERY_STRING") or ""
        status = 0
        why = None
        if isinstance(out, tuple) and len(out) == 2:
            status = out[1]
            try:
                why = (out[0].get_json() or {}).get("why")
            except Exception:
                why = None
        return status, why, qs


def _real_request():
    """⛔ الطلب الحقيقي (مش الـproxy) — عشان نحاكي الفشل عليه."""
    return flask_request._get_current_object()


def _simulate_query_string_write_failure():
    """⛔ محاكاة ⑤: كتابة request.query_string بترمي exception."""
    real = _real_request()
    base = type(real)

    class _BoomQueryString(base):
        @property
        def query_string(self):
            return self.__dict__.get("query_string", b"")

        @query_string.setter
        def query_string(self, value):
            raise RuntimeError(FAIL_MARK)

    real.__class__ = _BoomQueryString


def _simulate_args_cache_failure():
    """⛔ محاكاة ⑥: إبطال كاش request.args بيرمي exception."""
    real = _real_request()

    class _BoomDict(dict):
        def pop(self, key, *args, **kwargs):
            if key == "args":
                raise RuntimeError(FAIL_MARK)
            return dict.pop(self, key, *args, **kwargs)

    real.__dict__ = _BoomDict(real.__dict__)


def _install_simulator(sim):
    """⛔ يثبّت المحاكاة **قبل** الـsanitizer.

    📌 Flask بيشغّل الـbefore_request بترتيب التسجيل ⇒ ندخّل
    📌 المحاكاة في أول القائمة (المحاكاة بتتنفّذ على الطلب الحقيقي).
    """
    def _hook():
        try:
            sim()
        except Exception:
            pass

    _lst = app.before_request_funcs.setdefault(None, [])
    _lst.insert(0, _hook)
    return _hook, _lst


def _uninstall_simulator(hook, lst):
    try:
        lst.remove(hook)
    except Exception:
        pass


class _Base(unittest.TestCase):
    """⛔ دخول وهمي — الاختبار بيفحص الحماية مش المصادقة."""

    def setUp(self):
        self._orig_require_user = up.require_user
        up.require_user = lambda: {"uid": "r16", "email": "r16@test.local"}
        PROBE_HITS.clear()

    def tearDown(self):
        up.require_user = self._orig_require_user
        PROBE_HITS.clear()


# ══════════════════════════════════════════════════════════════
#  🧪 ① — الثوابت (مكان واحد + قيم سليمة)
# ══════════════════════════════════════════════════════════════
class TestQueryLimitConstants(unittest.TestCase):
    """مستوى العقد: حدود الـquery معرّفة في مكان واحد وواضح."""

    def test_limits_are_declared_in_one_place(self):
        """⛔ الاختبار السالب: كل الثوابت لازم تكون موجودة ومتّسمة."""
        for _name in ("QUERY_MAX_TOTAL_BYTES", "QUERY_MAX_PARAMS",
                      "QUERY_MAX_NAME_CHARS", "QUERY_MAX_VALUE_CHARS"):
            self.assertTrue(hasattr(up, _name),
                            "الحد ناقص: " + _name)
        for _name in ("QUERY_WHY_TOO_LONG", "QUERY_WHY_TOO_MANY_PARAMS",
                      "QUERY_WHY_NAME_TOO_LONG", "QUERY_WHY_VALUE_TOO_LONG",
                      "QUERY_WHY_SANITIZE_FAILED"):
            self.assertTrue(hasattr(up, _name), "كود السبب ناقص: " + _name)

    def test_limit_values_are_sane(self):
        """⛔ الاختبار السالب: مافيش حد صفري/سالب (يعني مافيش حماية)."""
        _total = _limit("QUERY_MAX_TOTAL_BYTES", 16384)
        _params = _limit("QUERY_MAX_PARAMS", 64)
        _name = _limit("QUERY_MAX_NAME_CHARS", 128)
        _value = _limit("QUERY_MAX_VALUE_CHARS", 8192)
        for _label, _num in (("total", _total), ("params", _params),
                             ("name", _name), ("value", _value)):
            self.assertIsInstance(_num, int,
                                  "الحد مش رقم: " + _label)
            self.assertGreater(_num, 0, "الحد صفر/سالب: " + _label)
        self.assertGreaterEqual(_total, _value,
                                "سقف الـquery كله أقل من سقف القيمة")
        self.assertGreaterEqual(_value, 1000,
                                "سقف القيمة صغير أوي على الطلبات العادية")


# ══════════════════════════════════════════════════════════════
#  🧪 ② — مستوى الـsanitizer (الرفض بيحصل قبل أي parse)
# ══════════════════════════════════════════════════════════════
class TestQueryLimitContract(_Base):
    """مستوى العقد: إيه اللي الـsanitizer بيعمله قدام الـquery."""

    def test_normal_query_passes_the_limits(self):
        """⛔ الاختبار السالب: طلب عادي لازم يعدّي من غير رفض."""
        _status, _why, _qs = _sanitize_call("sector=egx&limit=5")
        self.assertEqual(_status, 0,
                         "طلب عادي اترفض (status=%s why=%s)"
                         % (_status, _why))
        self.assertIsNone(_why, "طلب عادي اترفض بسبب: " + str(_why))

    def test_too_many_params_are_rejected(self):
        """⛔ الاختبار السالب: ٥٠٠ معاملة ⇒ رفض صريح."""
        _qs = "&".join("p%d=%s" % (i, RAW_MARK) for i in range(MANY_PARAMS))
        self.assertLess(len(_qs), _limit("QUERY_MAX_TOTAL_BYTES", 16384),
                        "حالة الاختبار عدّت حد الطول الكلي ⇒ سبب الرفض غلط")
        _status, _why, _after = _sanitize_call(_qs)
        self.assertEqual(_status, 400, "مافيش رفض صريح: " + str(_status))
        self.assertEqual(_why, WHY_TOO_MANY, "سبب الرفض غلط: " + str(_why))
        self.assertNotIn(RAW_MARK, _after, "الـquery الخام فضل موجود")

    def test_long_param_name_is_rejected(self):
        """⛔ الاختبار السالب: اسم معاملة ١٠٠٠ محرف ⇒ رفض صريح."""
        _qs = ("n" * LONG_NAME_CHARS) + "=" + RAW_MARK
        _status, _why, _after = _sanitize_call(_qs)
        self.assertEqual(_status, 400, "مافيش رفض صريح: " + str(_status))
        self.assertEqual(_why, WHY_NAME_TOO_LONG, "سبب الرفض غلط: " + str(_why))
        self.assertNotIn(RAW_MARK, _after, "الـquery الخام فضل موجود")

    def test_long_param_value_is_rejected(self):
        """⛔ الاختبار السالب: قيمة ١٢٠٠٠ محرف ⇒ رفض صريح."""
        _qs = "note=" + ("v" * LONG_VALUE_CHARS) + RAW_MARK
        _status, _why, _after = _sanitize_call(_qs)
        self.assertEqual(_status, 400, "مافيش رفض صريح: " + str(_status))
        self.assertEqual(_why, WHY_VALUE_TOO_LONG,
                         "سبب الرفض غلط: " + str(_why))
        self.assertNotIn(RAW_MARK, _after, "الـquery الخام فضل موجود")

    def test_long_query_string_is_rejected(self):
        """⛔ الاختبار السالب: query طويل جداً ⇒ رفض صريح."""
        _qs = "note=" + ("q" * LONG_QUERY_CHARS)
        _status, _why, _after = _sanitize_call(_qs)
        self.assertEqual(_status, 400, "مافيش رفض صريح: " + str(_status))
        self.assertEqual(_why, WHY_TOO_LONG, "سبب الرفض غلط: " + str(_why))
        self.assertNotIn("q" * 100, _after, "الـquery الخام فضل موجود")

    def test_rejection_empties_the_raw_query(self):
        """⛔ الاختبار السالب: بعد الرفض ⇒ الـrequest يبقى فاضي."""
        _qs = "&".join("p%d=%s" % (i, RAW_MARK) for i in range(MANY_PARAMS))
        _status, _why, _after = _sanitize_call(_qs)
        self.assertEqual(_status, 400, "مافيش رفض صريح")
        self.assertEqual(_after.strip(), "",
                         "الـquery الخام فضل في الـrequest بعد الرفض")


# ══════════════════════════════════════════════════════════════
#  🧪 ③ — الرد النهائي (مسارات حقيقية · JSON حقيقي)
# ══════════════════════════════════════════════════════════════
class TestQueryLimitEndToEnd(_Base):
    """الفحص على الرد النهائي اللي المستخدم بياخده."""

    def _assert_clean_rejection(self, query, why_expected, label):
        status, body = _get("/__r16_probe", query)
        self.assertEqual(status, 400,
                         "الطلب اتكمّل (%d) بدل رفض صريح (%s)"
                         % (status, label))
        data = json.loads(body)
        self.assertFalse(data.get("ok", True),
                         "الرد قال ok=True رغم الرفض (%s)" % label)
        self.assertEqual(data.get("why"), why_expected,
                         "سبب الرفض غلط (%s): " % label + str(data.get("why")))
        self.assertNotIn(RAW_MARK, body,
                         "قيمة خام متسربة في الرد (%s)" % label)
        return body

    def test_many_params_are_rejected_without_leak(self):
        """⛔ ② ٥٠٠ معاملة ⇒ رفض واضح + مافيش قيمة خام في الرد."""
        _qs = "&".join("p%d=%s" % (i, RAW_MARK) for i in range(MANY_PARAMS))
        self._assert_clean_rejection(_qs, WHY_TOO_MANY, "too_many_params")

    def test_long_name_is_rejected_without_leak(self):
        """⛔ ③ اسم ١٠٠٠ محرف ⇒ رفض واضح + مافيش قيمة خام في الرد."""
        _qs = ("n" * LONG_NAME_CHARS) + "=" + RAW_MARK
        self._assert_clean_rejection(_qs, WHY_NAME_TOO_LONG, "long_name")

    def test_long_value_is_rejected_without_leak(self):
        """⛔ ④ قيمة ١٢٠٠٠ محرف ⇒ رفض واضح + مافيش قيمة خام في الرد."""
        _qs = "note=" + ("v" * LONG_VALUE_CHARS) + RAW_MARK
        self._assert_clean_rejection(_qs, WHY_VALUE_TOO_LONG, "long_value")

    def test_long_query_is_rejected_without_leak(self):
        """⛔ ① query طويل جداً ⇒ رفض واضح + مافيش قيمة خام في الرد."""
        _qs = "note=" + ("q" * LONG_QUERY_CHARS)
        self._assert_clean_rejection(_qs, WHY_TOO_LONG, "long_query")

    def test_route_never_runs_on_rejected_request(self):
        """⛔ الـroute **ما شغّاش** بالقيمة غير النضيفة."""
        _qs = "&".join("p%d=%s" % (i, RAW_MARK) for i in range(MANY_PARAMS))
        status, _body = _get("/__r16_probe", _qs)
        self.assertEqual(status, 400, "مافيش رفض صريح")
        self.assertEqual(PROBE_HITS, [],
                         "الـroute اشتغل رغم الرفض: " + str(PROBE_HITS))
        for _hit in PROBE_HITS:
            for _k, _v in _hit.items():
                self.assertNotIn(RAW_MARK, str(_v),
                                 "الـroute شاف قيمة خام: " + _k)

    def test_query_string_write_failure_is_rejected(self):
        """⛔ ⑤ فشل كتابة request.query_string ⇒ رفض ٤٠٠ صريح."""
        _hook, _lst = _install_simulator(
            _simulate_query_string_write_failure)
        try:
            status, body = _get("/__r16_probe", "sector=" + RAW_MARK)
        finally:
            _uninstall_simulator(_hook, _lst)
        self.assertEqual(status, 400,
                         "الطلب اتكمّل (%d) بدل رفض صريح" % status)
        data = json.loads(body)
        self.assertFalse(data.get("ok", True),
                         "الرد قال ok=True رغم إن التنظيف وقع")
        self.assertEqual(data.get("why"), WHY_SANITIZE_FAILED,
                         "سبب الرفض غلط: " + str(data.get("why")))
        self.assertNotIn(RAW_MARK, body, "قيمة خام متسربة في الرد")
        self.assertEqual(PROBE_HITS, [],
                         "الـroute اشتغل رغم فشل التنظيف")

    def test_args_cache_invalidation_failure_is_rejected(self):
        """⛔ ⑥ فشل إبطال كاش request.args ⇒ رفض ٤٠٠ صريح."""
        _hook, _lst = _install_simulator(_simulate_args_cache_failure)
        try:
            status, body = _get("/__r16_probe", "sector=" + RAW_MARK)
        finally:
            _uninstall_simulator(_hook, _lst)
        self.assertEqual(status, 400,
                         "الطلب اتكمّل (%d) بدل رفض صريح" % status)
        data = json.loads(body)
        self.assertFalse(data.get("ok", True),
                         "الرد قال ok=True رغم إن التنظيف وقع")
        self.assertEqual(data.get("why"), WHY_SANITIZE_FAILED,
                         "سبب الرفض غلط: " + str(data.get("why")))
        self.assertNotIn(RAW_MARK, body, "قيمة خام متسربة في الرد")
        self.assertEqual(PROBE_HITS, [],
                         "الـroute اشتغل رغم فشل إبطال الكاش")


# ══════════════════════════════════════════════════════════════
#  🧪 ④ — نظافة الملف نفسه (قاعدة الـCI + سلامة النص)
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
        import re
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
        print("")
        print("=" * 70)
        print("✅ كل الفحوصات عدّت." if result.wasSuccessful()
              else "⛔⛔⛔ فيه اختبارات فاشلة.")
        print("=" * 70)
        sys.exit(0 if result.wasSuccessful() else 1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
