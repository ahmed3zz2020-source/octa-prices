#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 stubs بسيطة جداً لـ Flask و requests.

الجهاز المحلي مافيش فيه pip، فبنعمل أقل قدر ممكن من الحكايات
عشان نقدر نشغّل update_prices.py ونختبر المسارات فعلياً
(كود حالة حقيقي من Flask، مش تحليل ساكن).

الهدف اختبار بس — مش بديل عن Flask.
"""
import sys
import types
import json as _json


# ══════════════════════════════════════════════════════════
#  jsonify / Response
# ══════════════════════════════════════════════════════════
class Resp:
    """شكل الرد النهائي — زي ما Flask بيرجّعه"""

    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {}

    def get_json(self):
        return self.body

    # ⛔⛔⛔ 16 نوفمبر 2026 — الستب يُحاðي صفة الرد مش كمّل حقيقي:
    # كان ينادع requests بيستخدم · .json() ولا · get_json()
    # ⇒ المجموع الحيّ (مقاصة الأسهم بالنتاجة الشريط) بيسقط.
    def json(self):
        return self.body

    def is_json(self):
        return True

    @property
    def ok(self):
        return self.status_code < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)

    @property
    def text(self):
        return _json.dumps(self.body, ensure_ascii=False)

    @property
    def data(self):
        return _json.dumps(self.body, ensure_ascii=False).encode("utf-8")

    def __repr__(self):
        return "<Resp %s %s>" % (self.status_code, str(self.body)[:60])


def jsonify(*args, **kw):
    if args and kw:
        raise TypeError("jsonify: لا يMix بين positional و keyword")
    if len(args) == 1:
        return Resp(args[0])
    if args:
        return Resp(list(args))
    return Resp(kw)


class _Response(Resp):
    pass


# ══════════════════════════════════════════════════════════
#  request
# ══════════════════════════════════════════════════════════
class _Request:
    """request عالمي — بيتبدّل قبل كل نداء

    ⛔⛔⛔ الجولة ١٦ (١٧ نوفمبر ٢٠٢٦) — الستب بقى **محاكي لـ Werkzeug**
    في حقلين أساسيين:
      ① `environ` — في Flask/Werkzeug **دايمًا** موجود (dict).
         كان ناقص ⇒ `_apply_clean_query` بيرجع False (fail-closed)
         ⇒ كل طلب في بيئة الاختبار كان بيرجع 400 ⇒ ارتجاع سلوكي.
      ② `args` — في Werkzeug **ملكية محسوبة** من `QUERY_STRING`
         ⇒ بعد التنظيف (كتابة environ + إبطال الكاش) بتتحدّث لوحدها.
         قبل كنا `args` dict عادي ⇒ ما كانش بيتحدّث ⇒ قيم قديمة.
    ⛔ الاستبدال ده بيخلّي بيئة الاختبار **بتنفّذ نفس مسار الإنتاج**
       (بما فيه fail-closed) بدل مسار احتياطي ميت.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.method = "GET"
        self.path = "/"
        self.environ = {}
        self.form = {}
        self.headers = {}
        self.json = None
        self.remote_addr = "127.0.0.1"
        self._args = {}

    @property
    def args(self):
        """زي Werkzeug: مبني من QUERY_STRING (لما يكون موجود)."""
        try:
            if "QUERY_STRING" in self.environ:
                from urllib.parse import parse_qsl as _parse_qsl
                out = {}
                for _k, _v in _parse_qsl(self.environ.get("QUERY_STRING") or "",
                                         keep_blank_values=True):
                    out.setdefault(_k, _v)
                return out
        except Exception:
            pass
        return dict(getattr(self, "_args", {}) or {})

    @args.setter
    def args(self, value):
        self._args = dict(value or {})
        try:
            from urllib.parse import urlencode as _urlencode
            self.environ["QUERY_STRING"] = _urlencode(self._args, doseq=False)
        except Exception:
            pass

    def get_json(self, silent=False, force=False):
        return self.json

    def get_data(self):
        if self.json is None:
            return b""
        return _json.dumps(self.json).encode("utf-8")


request = _Request()


class _G:
    pass


g = _G()


# ══════════════════════════════════════════════════════════
#  Flask
# ══════════════════════════════════════════════════════════
class _Rule:
    def __init__(self, path, methods, handler):
        self.path = path
        self.methods = methods
        self.handler = handler


class Flask:
    def __init__(self, name="stub"):
        self.name = name
        self.url_map = []
        self.config = {}
        self.before_reqs = []
        self.after_reqs = []
        self.error_handlers = {}

    def route(self, path, methods=None):
        ms = set(methods or ["GET"])

        def deco(fn):
            self.url_map.append(_Rule(path, ms, fn))
            return fn

        return deco

    def before_request(self, fn):
        self.before_reqs.append(fn)
        return fn

    def after_request(self, fn):
        self.after_reqs.append(fn)
        return fn

    def errorhandler(self, code):
        def deco(fn):
            self.error_handlers[code] = fn
            return fn

        return deco

    # ── تشغيل المسار ──
    def dispatch(self, path, method="GET", headers=None, body=None, query=None):
        request.reset()
        request.path = path
        request.method = method.upper()
        request.headers = {k: v for k, v in (headers or {}).items()}
        request.json = body
        request.args = dict(query or {})

        for fn in self.before_reqs:
            early = fn()
            if early is not None:
                return early if isinstance(early, Resp) else Resp(early)

        rule = None
        for r in self.url_map:
            if r.path == path and method.upper() in r.methods:
                rule = r
                break
        if rule is None:
            return Resp({"error": "not found", "_path": path}, 404)

        try:
            out = rule.handler()
        except Exception as e:  # noqa
            return Resp({"error": "%s: %s" % (type(e).__name__, e)}, 500)

        # ⛔ ⛔ Flask بيرجّع (body, status) — لازم نفكّ الطقم ourselves
        if isinstance(out, tuple):
            body = out[0] if out else Resp({})
            st = out[1] if len(out) > 1 else 200
            out = Resp(body.get_json() if isinstance(body, Resp) else body, st)
        if not isinstance(out, Resp):
            out = Resp(out)
        for fn in self.after_reqs:
            r2 = fn(out)
            if isinstance(r2, Resp):
                out = r2
        return out


def install():
    """ثبّت الـstubs في sys.modules"""
    fl = types.ModuleType("flask")
    fl.Flask = Flask
    fl.jsonify = jsonify
    fl.request = request
    fl.Response = _Response
    fl.g = g
    fl.send_file = lambda *a, **k: Resp({}, 200)
    fl.send_from_directory = lambda *a, **k: Resp({}, 200)
    fl.static_folder = "static"
    fl.static_url_path = "/static"
    fl.redirect = lambda *a, **k: Resp({}, 302)
    fl.abort = lambda *a, **k: (_ for _ in ()).throw(RuntimeError(str(k or a)))
    sys.modules["flask"] = fl

    rq = types.ModuleType("requests")
    rq.get = lambda *a, **k: Resp({}, 200)
    rq.post = lambda *a, **k: Resp({}, 200)
    rq.exceptions = types.SimpleNamespace(
        RequestException=Exception, Timeout=Exception)
    sys.modules["requests"] = rq

    return fl, rq
