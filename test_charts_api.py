#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار مسارات /api/charts — تشغيل حقيقي للمسارات، مش تحليل ساكن.

⛔⛔ داتا الاختبار كلها بتتبعت في مجلد مؤقت ⬇️ الملف ده بيفحص
   المفيش وبيكتبش في المشروع ولا في مجلد البيانات الدائم.

شغّله:
    python3 -m pytest test_charts_api.py -q     (لو pytest موجود)
    python3 -m unittest test_charts_api -v       (مش محتاج pip)
"""
import os
import re
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="chartstest_", dir="/tmp")
sys.path.insert(0, HERE)

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

# ⛔⛔ مفيش سر حقيقي في الكود ولا في الملف ده ⬇️ قيم اختبار محلية بس
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"

import update_prices as up  # noqa: E402

# ── كل التخزين يروح على /tmp ⬇️ مافيش ملف في المشروع بيتلمس ──
up.USERS_FILE = Path(TMP) / "users.json"
up.CHARTS_FILE = Path(TMP) / "charts.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.MAIL_ON = False
up._send_mail = lambda *a, **k: True

# ⛔ الـstub مافيش فيه get_data/set_data ⬇️ والـafter_request بيحتاجهم
if not hasattr(fl_mod.jsonify.__globals__["_Response"], "set_data"):
    def _get_data(self):
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")

    def _set_data(self, raw):
        if isinstance(raw, (bytes, bytearray)):
            self.body = json.loads(raw.decode("utf-8"))
        else:
            self.body = raw

    fl_mod.jsonify.__globals__["_Response"].get_data = _get_data
    fl_mod.jsonify.__globals__["_Response"].set_data = _set_data

app = up.app
_ORIG_DISPATCH = app.dispatch


def _tpl_re(tpl):
    """ turning قالب المسار <param> ⬇️ regex """
    parts = re.split(r"(<[^>]+>)", tpl)
    out = []
    for p in parts:
        if p.startswith("<") and p.endswith(">"):
            out.append(r"[^/]+")
        else:
            out.append(re.escape(p))
    return re.compile("^" + "".join(out) + "$")


def call(path, method="GET", body=None, token=None, ip="10.0.0.1", headers=None):
    """📞 نداء مسار ⬇️ بنفس دالة السيرفر.

    ⛌ الـrate limit في الذاكرة ⬇️ بنصفّره بين الخطوات (نفس
       النمط بتاع test_pin_auth.py) ⬇️ عشان نختبر 기능 مش
       الأقفال.
    ⛌ المكتبة المصغّرة (الـstub) ما بتعرفش المسارات اللي فيها
       <param> ⬇️ فنعملها بإيدنا: بنغيّر قالب المسار مؤقتاً
       ونسيب request.path زي ما هو ⬇️ عشان الكود يقرا الـid
       منه (زي ما بيعمل في Flask الحقيقي).
    """
    up._HITS.clear()
    h = {"X-Forwarded-For": ip}
    h.update(headers or {})
    if token:
        h["Authorization"] = "Bearer " + token
    m = method.upper()

    # ① مسار موجود زي ما هو
    for r in app.url_map:
        if r.path == path and m in r.methods:
            return _ORIG_DISPATCH(path, method=m, body=body, headers=h)

    # ② مسار فيه <param>
    for r in app.url_map:
        if "<" not in r.path or m not in r.methods:
            continue
        if not _tpl_re(r.path).match(path):
            continue
        old = r.path
        r.path = path
        try:
            return _ORIG_DISPATCH(path, method=m, body=body, headers=h)
        finally:
            r.path = old

    return _ORIG_DISPATCH(path, method=m, body=body, headers=h)


def make_user(name, email):
    """👤 حساب حقيقي ⬇️ من مسار التسجيل ⬇️ وبيطلع توكن صالح."""
    r = call("/api/auth/register", method="POST",
             body={"name": name, "key": "482913", "email": email})
    assert r.status_code == 200, "تسجيل %s → %s %s" % (email, r.status_code,
                                                        r.get_json())
    b = r.get_json()
    return b["user"]["id"], b["token"]


def body_of(r):
    try:
        return r.get_json() or {}
    except Exception:
        return {}


SAMPLE = {
    "name": "COMI — تحليل",
    "note": "أقرب مقاومة",
    "symbol": "COMI",
    "tf": "1D",
    "type": "candles",
    "indicators": [{"id": "sma", "params": {"p": 20}}],
    "drawings": [{"id": "d1", "type": "trendline",
                  "points": [{"t": "2026-01-01", "p": 10.5},
                             {"t": "2026-02-01", "p": 12.0}],
                  "color": "#2962ff", "width": 2, "locked": False}],
}


class ChartsApiTest(unittest.TestCase):
    """🧪 كل مسارات /api/charts"""

    @classmethod
    def setUpClass(cls):
        cls.a_uid, cls.a_tok = make_user("أمينة", "amina@example.com")
        cls.b_uid, cls.b_tok = make_user("كريم", "karim@example.com")

    # ── ① مافيش توكن ⬇️ 401 على كل المسارات ──
    def test_01_no_token_401(self):
        cases = (("GET", "/api/charts"),
                 ("GET", "/api/charts/list"),
                 ("GET", "/api/charts/abc123"),
                 ("POST", "/api/charts"),
                 ("DELETE", "/api/charts/abc123"))
        for method, path in cases:
            r = call(path, method=method, body=SAMPLE)
            self.assertEqual(r.status_code, 401,
                             "%s %s → %s %s" % (method, path, r.status_code,
                                                body_of(r)))
            b = body_of(r)
            self.assertFalse(b.get("ok"))
            # ⛔ نفس رسالة الموقع
            self.assertEqual(b.get("error"), "المسار ده محمي")
            self.assertEqual(b.get("hint"), "سجّل دخول الأول")

    # ── ② توكن غلط ⬇️ 401 برضه ──
    def test_02_bad_token_401(self):
        for tok in ("", "abc.def", "x" * 300):
            r = call("/api/charts", method="GET", token=tok or None)
            self.assertEqual(r.status_code, 401, "توكن %r → %s"
                             % (tok, r.status_code))

    # ── ③ حفظ ⬇️ قراءة ⬇️ round-trip ──
    def test_03_save_and_read(self):
        r = call("/api/charts", method="POST", body=SAMPLE, token=self.a_tok)
        self.assertEqual(r.status_code, 200, body_of(r))
        b = body_of(r)
        self.assertTrue(b.get("ok"))
        cid = b.get("id")
        self.assertTrue(cid, "مافيش id في الرد")
        # ⛔ الـid = ١٦ حرف hex ⬇️ مش تسلسلي
        self.assertTrue(re.match(r"^[0-9a-f]{16}$", cid),
                        "الـid شكله غلط: %r" % cid)

        # ⛔ اقرأ الرسمة
        r2 = call("/api/charts/%s" % cid, method="GET", token=self.a_tok)
        self.assertEqual(r2.status_code, 200, body_of(r2))
        c = body_of(r2).get("chart") or {}
        self.assertEqual(c.get("id"), cid)
        self.assertEqual(c.get("name"), SAMPLE["name"])
        self.assertEqual(c.get("note"), SAMPLE["note"])
        self.assertEqual(c.get("symbol"), SAMPLE["symbol"])
        self.assertEqual(c.get("tf"), SAMPLE["tf"])
        self.assertEqual(c.get("type"), SAMPLE["type"])
        # ⛔ round-tripPayload == الأصل بالـJSON
        self.assertEqual(c.get("indicators"), SAMPLE["indicators"])
        self.assertEqual(c.get("drawings"), SAMPLE["drawings"])
        self.assertTrue(c.get("created"))
        self.assertTrue(c.get("updated"))

        # ⛔ في القايمتين
        for path in ("/api/charts", "/api/charts/list"):
            rl = call(path, method="GET", token=self.a_tok)
            self.assertEqual(rl.status_code, 200, path)
            charts = body_of(rl).get("charts") or []
            self.assertTrue(any(x.get("id") == cid for x in charts),
                            "%s مافيش فيه الرسمة" % path)
            one = [x for x in charts if x.get("id") == cid][0]
            # ⛔ شكل عنصر القائمة
            for k in ("id", "name", "note", "symbol", "tf", "type", "updated"):
                self.assertIn(k, one, "الحقل %s ناقص" % k)
            # ⛔ مافيش حقول كبيرة في القايمة
            self.assertNotIn("drawings", one)
            self.assertNotIn("indicators", one)

        # ⛔ المستخدم التاني مش شايف حاجة
        rl = call("/api/charts", method="GET", token=self.b_tok)
        self.assertFalse(any(x.get("id") == cid
                             for x in (body_of(rl).get("charts") or [])))
        globals()["_CHART_ID"] = cid

    # ── ④ تحديث رسمة موجودة ──
    def test_04_update(self):
        cid = globals().get("_CHART_ID")
        self.assertTrue(cid, "مافيش رسمة من الخطوة اللي قبلها")
        before = body_of(call("/api/charts/%s" % cid, method="GET",
                               token=self.a_tok)).get("chart") or {}

        upd = dict(SAMPLE)
        upd["id"] = cid
        upd["name"] = "COMI — اسم جديد"
        r = call("/api/charts", method="POST", body=upd, token=self.a_tok)
        self.assertEqual(r.status_code, 200, body_of(r))
        self.assertEqual(body_of(r).get("id"), cid)
        self.assertFalse(body_of(r).get("created"))

        after = body_of(call("/api/charts/%s" % cid, method="GET",
                              token=self.a_tok)).get("chart") or {}
        self.assertEqual(after.get("name"), "COMI — اسم جديد")
        # ⛔ عدد الرسومات ما زادش ⬇️ ووقت الإنشاء ما اتغيّرش
        self.assertEqual(after.get("created"), before.get("created"))
        lst = body_of(call("/api/charts", method="GET", token=self.a_tok))
        self.assertEqual(len(lst.get("charts") or []), 1)

    # ── ⑤ رسمة حد تاني ⬇️ 404 مش 403 ──
    def test_05_other_user_404(self):
        cid = globals().get("_CHART_ID")
        self.assertTrue(cid)

        # ⛔ قراءة
        r = call("/api/charts/%s" % cid, method="GET", token=self.b_tok)
        self.assertEqual(r.status_code, 404, body_of(r))
        self.assertNotIn("chart", body_of(r))

        # ⛔ تعديل
        hijack = dict(SAMPLE)
        hijack["id"] = cid
        hijack["name"] = "اختطاف"
        r = call("/api/charts", method="POST", body=hijack, token=self.b_tok)
        self.assertEqual(r.status_code, 404, body_of(r))

        # ⛔ حذف
        r = call("/api/charts/%s" % cid, method="DELETE", token=self.b_tok)
        self.assertEqual(r.status_code, 404, body_of(r))

        # ⛔ والرسمة لسه بتاعتها ⬇️ ومفيش رسمة جديدة اتعملت
        r = call("/api/charts/%s" % cid, method="GET", token=self.a_tok)
        self.assertEqual(r.status_code, 200)
        lst = body_of(call("/api/charts", method="GET", token=self.b_tok))
        self.assertEqual(len(lst.get("charts") or []), 0)

    # ── ⑥ uid من التوكن ⬇️ مش من الـbody ──
    def test_06_uid_from_token_only(self):
        bad = dict(SAMPLE)
        bad["uid"] = self.b_uid
        bad["user_id"] = self.b_uid
        bad["userId"] = self.b_uid
        r = call("/api/charts", method="POST", body=bad, token=self.a_tok)
        self.assertEqual(r.status_code, 200, body_of(r))
        cid = body_of(r).get("id")

        # ⛔ الرسمة اتحفظت تحت uid صاحب التوكن
        disk = json.loads(up.CHARTS_FILE.read_text(encoding="utf-8"))
        self.assertIn(self.a_uid, disk)
        self.assertIn(cid, disk.get(self.a_uid) or {})

        # ⛔ ومفيش ولا uid تاني اتضاف
        mine = disk.get(self.b_uid) or {}
        self.assertNotIn(cid, mine)
        for rec in mine.values():
            self.assertNotEqual(rec.get("uid"), self.a_uid)

    # ── ⑦ حذف ──
    def test_07_delete(self):
        r = call("/api/charts", method="POST", body=SAMPLE, token=self.a_tok)
        cid = body_of(r).get("id")
        self.assertTrue(cid)

        r = call("/api/charts/%s" % cid, method="DELETE", token=self.a_tok)
        self.assertEqual(r.status_code, 200, body_of(r))
        b = body_of(r)
        self.assertTrue(b.get("ok"))
        self.assertTrue(b.get("deleted"))

        # ⛔ راحت فعلاً
        r = call("/api/charts/%s" % cid, method="GET", token=self.a_tok)
        self.assertEqual(r.status_code, 404)
        # ⛔ وتaningش من القايمة
        lst = body_of(call("/api/charts", method="GET", token=self.a_tok))
        self.assertFalse(any(x.get("id") == cid
                             for x in (lst.get("charts") or [])))

    # ── ⑧ الحدود ──
    def test_08_limits(self):
        # ⛔ payload أكبر من 1 ميجا
        big = dict(SAMPLE)
        big["note"] = "x" * (1024 * 1024 + 512)
        r = call("/api/charts", method="POST", body=big, token=self.a_tok)
        self.assertEqual(r.status_code, 400, "payload كبير → %s %s"
                         % (r.status_code, body_of(r)))

        # ⛔ ٣٠١ نقطة في رسمة واحدة
        many = dict(SAMPLE)
        many["drawings"] = [{"id": "d", "type": "trendline",
                             "points": [{"t": "2026-01-%02d" % (i % 28 + 1),
                                         "p": i} for i in range(301)]}]
        r = call("/api/charts", method="POST", body=many, token=self.a_tok)
        self.assertEqual(r.status_code, 400, "٣٠١ نقطة → %s %s"
                         % (r.status_code, body_of(r)))

        # ⛔ ٣٠٠ نقطة بالظبط ⬇️ لازم تنجح
        ok300 = dict(SAMPLE)
        ok300["drawings"] = [{"id": "d", "type": "trendline",
                              "points": [{"t": "2026-01-%02d" % (i % 28 + 1),
                                          "p": i} for i in range(300)]}]
        r = call("/api/charts", method="POST", body=ok300, token=self.a_tok)
        self.assertEqual(r.status_code, 200, "٣٠٠ نقطة → %s %s"
                         % (r.status_code, body_of(r)))
        call("/api/charts/%s" % body_of(r).get("id"), method="DELETE",
             token=self.a_tok)

        # ⛌ عدد الرسومات ⬇️ مستخدم لوحده عشان مابيلغّرش الباقي
        c_uid, c_tok = make_user("سلمى", "salma@example.com")
        for i in range(50):
            r = call("/api/charts", method="POST",
                     body={"name": "رسمة %d" % i, "symbol": "COMI"},
                     token=c_tok)
            self.assertEqual(r.status_code, 200, "رسمة %d → %s %s"
                             % (i, r.status_code, body_of(r)))
        # ⛔ الرسمة ٥١ ⬇️ 400
        r = call("/api/charts", method="POST",
                 body={"name": "زيادة", "symbol": "COMI"}, token=c_tok)
        self.assertEqual(r.status_code, 400, "الرسمة ٥١ → %s %s"
                         % (r.status_code, body_of(r)))
        # ⛔ والتعديل على رسمة موجودة لسه شغال ⬇️ الحد مش بيزيد
        lst = body_of(call("/api/charts", method="GET", token=c_tok))
        first = (lst.get("charts") or [])[0]
        r = call("/api/charts", method="POST",
                 body={"id": first.get("id"), "name": "معدّلة"},
                 token=c_tok)
        self.assertEqual(r.status_code, 200, "تعديل عند الحد → %s %s"
                         % (r.status_code, body_of(r)))

    # ── ٩ payload مش JSON ──
    def test_09_bad_json(self):
        for body in ("مش JSON", b"not-json", [1, 2, 3], None, 12):
            r = call("/api/charts", method="POST", body=body, token=self.a_tok)
            self.assertEqual(r.status_code, 400, "body=%r → %s %s"
                             % (body, r.status_code, body_of(r)))

    # ── ⑩ مافيش سر في الرد + شكل التخزين ──
    def test_10_no_secret_and_storage_shape(self):
        r = call("/api/charts", method="POST", body=SAMPLE, token=self.a_tok)
        cid = body_of(r).get("id")
        raw = json.dumps(body_of(r), ensure_ascii=False)
        self.assertNotIn(self.a_tok, raw, "التوكن مرجع في الرد")
        self.assertNotIn("OCTAD", raw)
        self.assertNotIn(up._SECRET, raw)

        one = body_of(call("/api/charts/%s" % cid, method="GET",
                           token=self.a_tok)).get("chart") or {}
        for k in ("id", "name", "note", "symbol", "tf", "type",
                  "indicators", "drawings", "created", "updated"):
            self.assertIn(k, one, "الحقل %s ناقص في الرسمة" % k)

        # ⛔ شكل الملف على القرص
        disk = json.loads(up.CHARTS_FILE.read_text(encoding="utf-8"))
        self.assertIsInstance(disk, dict)
        self.assertIn(self.a_uid, disk)
        rec = disk[self.a_uid][cid]
        self.assertEqual(rec.get("id"), cid)
        self.assertEqual(rec.get("name"), SAMPLE["name"])
        self.assertEqual(rec.get("indicators"), SAMPLE["indicators"])
        self.assertEqual(rec.get("drawings"), SAMPLE["drawings"])

    # ── ⑪ مافيش ملفات temp متبقية (الكتابة ذرّية) ──
    def test_11_atomic_write(self):
        call("/api/charts", method="POST", body=SAMPLE, token=self.a_tok)
        leftovers = [p.name for p in Path(TMP).iterdir()
                     if p.name.startswith(".charts")]
        self.assertEqual(leftovers, [], "في ملفات temp متبقية: %s" % leftovers)
        # ⛔ والملف سليم ⬇️ JSON كامل
        json.loads(up.CHARTS_FILE.read_text(encoding="utf-8"))

    # ── ⑫ rate limit ⬇️ الكتابة في bucket "write" ──
    def test_12_rate_bucket(self):
        self.assertEqual(up._route_bucket("/api/charts", "POST"), "write")
        self.assertEqual(up._route_bucket("/api/charts", "DELETE"), "write")
        self.assertEqual(up._route_bucket("/api/charts", "GET"), "default")
        self.assertEqual(up._route_bucket("/api/charts/list", "GET"), "default")
        # ⛌ والمسارات القديمة مالتغيرتش
        self.assertEqual(up._route_bucket("/api/portfolio"), "write")
        self.assertEqual(up._route_bucket("/api/auth/me"), "default")
        self.assertEqual(up._route_bucket("/api/analyze"), "expensive")
        self.assertEqual(up._route_bucket("/api/auth/signup/newpin"),
                         "pin_signup_newpin")


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
