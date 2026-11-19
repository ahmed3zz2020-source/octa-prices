#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧰 طبقة HTTP معزولة للاختبارات — الجولة ٢٥ (R25 · المرحلة ٩)

📌 ليه الأداة دي موجودة ⭐:
   بيئة الاختبار هنا **مفيش فيها** `flask` ولا `requests` ولا أي شبكة ⭐
   (والمستودع نفسه بيشتغل في الإنتاج على `flask` + `requests` ⭐) ⭐
   ⇒ عشان نعمل **قياس حقيقي** على المسارات الحقيقية ⭐
     (مش على نسخة وهمية من التطبيق ⭐) ⭐
   بنعمل طبقة نقل **بمكتبة بايثون القياسية بس** ⭐
   بتشغّل **نفس كود المسارات** اللي في `update_prices.py` ⭐.

⛔⛔⛔ قواعد صارمة ⬇️ ⬇️
  ⛔ مفيش أي اتصال خارجي ⬇️ ⬇️ (شبكة الوكيل مُقفلة بصرامة ⭐)
  ⛔ مفيش أي سر إنتاج ⬇️ ⬇️ (الأسرار بتتولّد في الاختبار ⭐)
  ⛔ الأداة دي **لاختبارات الـstaging المعزولة بس** ⬇️ ⬇️
  ⛔ كود التطبيق في الإنتاج ما اتغيّرش ⭐ ⭐

📌 إيه اللي بتعمله ⭐:
   ① `flask` مُصغّر ⭐ — بيدعم اللي التطبيق بيستخدمه بس ⭐:
      `Flask` · `jsonify` · `request` · `Response` · `g` ·
      `send_from_directory` ⭐.
   ② `requests` مُقفل ⭐ — أي محاولة اتصال خارجي بترمي استثناء ⭐
      (إلا لو الاختبار حطّ يد وهمية ⭐ ⇒ عشان نحاكي فشل المصدر ⭐).
   ③ سيرفر HTTP حقيقي ⭐ (`ThreadingHTTPServer` ⭐) ⭐
      ⇒ الطلبات بتيجي من عميل حقيقي ⭐ ⇒ القياسات حقيقية ⭐.
"""
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote

__all__ = [
    "Flask", "jsonify", "request", "Response", "g", "send_from_directory",
    "install_shims", "make_server", "serve_forever", "shutdown_server",
    "block_network", "unblock_network", "fake_http", "source_handler",
    "FakeResponse", "IPO_HTML", "NetworkBlocked",
]


# ══════════════════════════════════════════════════════════════════
#  🧱 جمع البيانات — توافق مع `werkzeug`
# ══════════════════════════════════════════════════════════════════
class MultiDict(dict):
    """قيمة واحدة أو أكتر لكل مفتاح — زي `werkzeug.MultiDict`."""

    def __init__(self, mapping=None):
        super().__init__()
        self._lists = {}
        if mapping:
            items = mapping.items() if hasattr(mapping, "items") else mapping
            for k, v in items:
                if isinstance(v, (list, tuple)):
                    for one in v:
                        self._lists.setdefault(k, []).append(one)
                else:
                    self._lists.setdefault(k, []).append(v)
        for k, v in self._lists.items():
            dict.__setitem__(self, k, v[0])

    def get(self, key, default=None, type=None):
        val = dict.get(self, key, default)
        if type is not None and val is not None:
            try:
                return type(val)
            except (TypeError, ValueError):
                return default
        return val

    def getlist(self, key):
        return list(self._lists.get(key, []))

    def items(self):
        return [(k, self[k]) for k in self._lists]


class Headers:
    """ترويسات HTTP — البحث فيها مش حسّاس لحالة الأحرف."""

    def __init__(self, data=None):
        self._d = {}
        if data:
            for k, v in dict(data).items():
                self._d[str(k).lower()] = [str(k), str(v)]

    def get(self, key, default=None):
        hit = self._d.get(str(key).lower())
        return hit[1] if hit else default

    def __getitem__(self, key):
        hit = self._d.get(str(key).lower())
        if hit is None:
            raise KeyError(key)
        return hit[1]

    def __setitem__(self, key, value):
        self._d[str(key).lower()] = [str(key), str(value)]

    def __contains__(self, key):
        return str(key).lower() in self._d

    def __iter__(self):
        return iter(self._d.values())

    def items(self):
        return [(v[0], v[1]) for v in self._d.values()]

    def keys(self):
        return [v[0] for v in self._d.values()]

    def setdefault(self, key, default=None):
        if key not in self._d:
            self[key] = default
        return self[key]

    def pop(self, key, default=None):
        hit = self._d.pop(str(key).lower(), None)
        return hit[1] if hit else default


class _G:
    """مساحة أسماء خاصة بالطلب — زي `flask.g`."""

    def __init__(self):
        self.__dict__["_loc"] = threading.local()

    def __getattr__(self, name):
        try:
            return getattr(self.__dict__["_loc"], name)
        except AttributeError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        setattr(self.__dict__["_loc"], name, value)

    def __delattr__(self, name):
        try:
            delattr(self.__dict__["_loc"], name)
        except AttributeError:
            pass


g = _G()


# ══════════════════════════════════════════════════════════════════
#  📨 الطلب
# ══════════════════════════════════════════════════════════════════
class _Request:
    """الطلب الحالي — مبني على `environ` زي WSGI."""

    def __init__(self, environ):
        self.environ = environ
        self.method = environ.get("REQUEST_METHOD", "GET")
        self.path = environ.get("PATH_INFO", "/")
        self.query_string = environ.get("QUERY_STRING", "") or ""
        self.headers = Headers()
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                self.headers[k[5:].replace("_", "-")] = v
        if environ.get("CONTENT_TYPE"):
            self.headers["Content-Type"] = environ["CONTENT_TYPE"]
        self.remote_addr = environ.get("REMOTE_ADDR", "127.0.0.1")
        self.cookies = self._parse_cookies()
        self._body = None

    @staticmethod
    def _parse_cookies():
        out = {}
        raw = os.environ.get("_OCTA_MINI_COOKIES", "")
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip()] = unquote(v.strip())
        return out

    @property
    def args(self):
        cache = self.__dict__.get("args")
        if cache is None:
            cache = MultiDict(parse_qs(self.query_string, keep_blank_values=True))
            self.__dict__["args"] = cache
        return cache

    @property
    def url(self):
        cache = self.__dict__.get("url")
        if cache is None:
            host = self.environ.get("HTTP_HOST", "127.0.0.1")
            cache = "http://%s%s" % (host, self.path)
            if self.query_string:
                cache = cache + "?" + self.query_string
            self.__dict__["url"] = cache
        return cache

    def get_data(self, as_text=False):
        if self._body is None:
            try:
                n = int(self.environ.get("CONTENT_LENGTH") or 0)
            except (TypeError, ValueError):
                n = 0
            stream = self.environ.get("wsgi.input")
            raw = stream.read(n) if (stream is not None and n > 0) else b""
            self._body = raw
        if as_text:
            return self._body.decode("utf-8", "replace")
        return self._body

    def get_json(self, force=False, silent=False):
        raw = self.get_data()
        if not raw:
            if silent:
                return None
            raise ValueError("الطلب مافيشوش جسم JSON")
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            if silent:
                return None
            raise


class _RequestProxy:
    """وكيل للطلب الحالي — بيدّيك الطلب في الـthread اللي شغّال."""

    def __init__(self):
        self._local = threading.local()

    def _push(self, req):
        self._local.req = req

    def _pop(self):
        req = getattr(self._local, "req", None)
        self._local.req = None
        return req

    def __getattr__(self, name):
        req = getattr(self._local, "req", None)
        if req is None:
            raise RuntimeError("مافيش طلب شغّال في الـthread ده")
        return getattr(req, name)


request = _RequestProxy()


# ══════════════════════════════════════════════════════════════════
#  📨 الرد
# ══════════════════════════════════════════════════════════════════
class Response:
    """رد HTTP — شبيه بـ`flask.Response` في الحاجات اللي التطبيق بيستخدمها."""

    def __init__(self, response=None, status=200, headers=None,
                 mimetype=None, content_type=None):
        if response is None:
            body = b""
        elif isinstance(response, bytes):
            body = response
        elif isinstance(response, str):
            body = response.encode("utf-8")
        else:
            body = json.dumps(response, ensure_ascii=False).encode("utf-8")
            if content_type is None and mimetype is None:
                content_type = "application/json"
        self._body = body
        self.status_code = int(status)
        self.headers = Headers(headers or {})
        if content_type:
            self.headers["Content-Type"] = content_type
        elif mimetype:
            self.headers["Content-Type"] = mimetype
        else:
            self.headers.setdefault("Content-Type", "text/html; charset=utf-8")
        self._cookies = []

    @property
    def is_json(self):
        return str(self.headers.get("Content-Type", "")).startswith("application/json")

    def get_data(self, as_text=False):
        return self._body.decode("utf-8", "replace") if as_text else self._body

    def set_data(self, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self._body = value

    def get_json(self, silent=False):
        try:
            return json.loads(self._body.decode("utf-8"))
        except Exception:
            if silent:
                return None
            raise

    def set_cookie(self, key, value="", max_age=None, httponly=False,
                   secure=False, samesite=None, path="/", expires=None):
        self._cookies.append((str(key), str(value), max_age, httponly,
                               secure, samesite, path, expires))
        self.headers["Set-Cookie"] = self._cookie_header()

    def delete_cookie(self, key, path="/"):
        self._cookies.append((str(key), "", 0, False, False, None, path, None))
        self.headers["Set-Cookie"] = self._cookie_header()

    def _cookie_header(self):
        parts = []
        for k, v, ma, ho, se, ss, p, ex in self._cookies:
            piece = "%s=%s; Path=%s" % (k, v, p)
            if ma is not None:
                piece += "; Max-Age=%d" % int(ma)
            if ex is not None:
                piece += "; Expires=%s" % ex
            if ho:
                piece += "; HttpOnly"
            if se:
                piece += "; Secure"
            if ss:
                piece += "; SameSite=%s" % ss
            parts.append(piece)
        return "; ".join(parts)


def jsonify(*args, **kwargs):
    """رد JSON — زي `flask.jsonify`."""
    if args and kwargs:
        raise TypeError("jsonify: مينفعش Arguments وKeywords مع بعض")
    if len(args) == 1:
        payload = args[0]
    elif args:
        payload = list(args)
    else:
        payload = kwargs
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return Response(body, mimetype="application/json")


def send_from_directory(directory, filename, **_kw):
    """إرسال ملف من مجلد — زي `flask.send_from_directory`."""
    base = os.path.abspath(str(directory))
    target = os.path.abspath(os.path.join(base, str(filename)))
    if not target.startswith(base + os.sep) and target != base:
        return Response("forbidden", status=403)
    if not os.path.isfile(target):
        return Response("not found", status=404)
    with open(target, "rb") as fh:
        data = fh.read()
    resp = Response(data)
    resp.headers["Content-Type"] = "application/octet-stream"
    return resp


# ══════════════════════════════════════════════════════════════════
#  🗺️ التطبيق
# ══════════════════════════════════════════════════════════════════
_RULE_PART = re.compile(r"<(?:(?P<conv>[a-zA-Z_]+):)?(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)>")


def _rule_to_regex(rule):
    """يحوّل قاعدة Flask لعملية regexp — الدوال المدعومة زي originals."""
    pattern = "^"
    pos = 0
    for m in _RULE_PART.finditer(rule):
        pattern += re.escape(rule[pos:m.start()])
        conv = m.group("conv") or "string"
        name = m.group("name")
        if conv == "path":
            pattern += "(?P<%s>.+)" % name
        elif conv == "int":
            pattern += "(?P<%s>[^/]+)" % name
        elif conv == "float":
            pattern += "(?P<%s>[^/]+)" % name
        else:
            pattern += "(?P<%s>[^/]+)" % name
        pos = m.end()
    pattern += re.escape(rule[pos:]) + "$"
    return re.compile(pattern)


class _Rule:
    def __init__(self, rule, methods, view):
        self.rule = rule
        self.methods = methods
        self.view = view
        self.regex = _rule_to_regex(rule)


class _UrlMap:
    def __init__(self):
        self._rules = []


class Flask:
    """تطبيق مصغّر — بيدعم الحاجات اللي `update_prices.py` بيستخدمها."""

    def __init__(self, import_name=None):
        self.import_name = import_name
        self.url_map = _UrlMap()
        self.config = {}
        self.before_request_funcs = []
        self.after_request_funcs = []
        self.error_handler_specs = {}
        self._rules = self.url_map._rules

    # ── تسجيل المسارات ⭐ ──
    def route(self, rule, methods=None):
        def deco(fn):
            self.add_url_rule(rule, fn, methods)
            return fn
        return deco

    def add_url_rule(self, rule, view_func=None, methods=None):
        if methods is None:
            methods = ["GET"]
        methods = [str(m).upper() for m in methods]
        if "GET" in methods and "HEAD" not in methods:
            methods.append("HEAD")
        r = _Rule(rule, methods, view_func)
        self.url_map._rules.append(r)
        return view_func

    def before_request(self, fn):
        self.before_request_funcs.append(fn)
        return fn

    def after_request(self, fn):
        self.after_request_funcs.append(fn)
        return fn

    def errorhandler(self, code_or_exception):
        def deco(fn):
            self.error_handler_specs[code_or_exception] = fn
            return fn
        return deco

    def teardown_request(self, fn):
        return fn

    def after_request_funcs_sorted(self):
        return list(self.after_request_funcs)

    # ── المطابقة ⭐ ──
    def _match(self, path, method):
        allowed = set()
        for rule in self.url_map._rules:
            m = rule.regex.match(path)
            if not m:
                continue
            if method not in rule.methods:
                allowed.update(rule.methods)
                continue
            return rule, m.groupdict()
        if allowed:
            return None, {"__allowed__": sorted(allowed)}
        return None, {}

    # ── التنفيذ ⭐ ──
    def handle(self, environ):
        req = _Request(environ)
        request._push(req)
        try:
            resp = self._dispatch(req)
        finally:
            request._pop()
        return resp

    def _dispatch(self, req):
        try:
            for fn in self.before_request_funcs:
                out = fn()
                if out is not None:
                    return self._normalize(out)
            rule, params = self._match(req.path, req.method)
            if rule is None:
                if params.get("__allowed__"):
                    resp = jsonify({"error": "الطريقة مش مسموحة"})
                    resp.status_code = 405
                    resp.headers["Allow"] = ", ".join(params["__allowed__"])
                    return self._after(resp)
                resp = jsonify({"error": "المسار مش موجود",
                                "path": req.path})
                resp.status_code = 404
                return self._after(resp)
            req.environ["octa.view_args"] = params
            out = rule.view(**params)
            resp = self._normalize(out)
            return self._after(resp)
        except Exception as exc:                       # noqa: BLE001
            handler = self.error_handler_specs.get(Exception)
            if handler is None:
                raise
            try:
                out = handler(exc)
            except Exception:
                raise
            resp = self._normalize(out)
            return self._after(resp)

    def _after(self, resp):
        for fn in reversed(self.after_request_funcs):
            resp = fn(resp)
        return resp

    @staticmethod
    def _normalize(out):
        if isinstance(out, Response):
            return out
        if isinstance(out, tuple):
            body = out[0]
            status = out[1] if len(out) > 1 else 200
            if isinstance(body, Response):
                body.status_code = int(status)
                return body
            resp = jsonify(body)
            resp.status_code = int(status)
            return resp
        if isinstance(out, (dict, list)):
            return jsonify(out)
        if out is None:
            resp = Response("", status=204)
            return resp
        if isinstance(out, (bytes, str)):
            return Response(out)
        return jsonify(out)

    # ── التشغيل ⭐ ──
    def run(self, host="127.0.0.1", port=5000, threaded=True, debug=False,
            use_reloader=False, **_kw):
        server = make_server(host, int(port), self)
        server.serve_forever()

    def __call__(self, environ, start_response):        # WSGI
        resp = self.handle(environ)
        start_response("%d STATUS" % resp.status_code, list(resp.headers.items()))
        return [resp.get_data()]


# ══════════════════════════════════════════════════════════════════
#  🌐 السيرفر
# ══════════════════════════════════════════════════════════════════
class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # ⛔⛔⛔ مهم للقياس ⭐ — بدون تعطيل Nagle ⭐
    # 📌 الترويسات والجسم بيتكتبوا في مرحلتين ⭐ ⇒ الرAcknowledgments
    # 📌 المتأخّر (40ms) بيدخل على قياس زمن الاستجابة ⭐
    # 📌 ⇒ القياس كان هيتلوّث بتأخير مش من التطبيق ⭐
    disable_nagle_algorithm = True
    app = None

    def log_message(self, *_a):
        return

    def _build_environ(self, body):
        env = {
            "REQUEST_METHOD": self.command,
            "PATH_INFO": unquote(self.path.split("?", 1)[0]),
            "QUERY_STRING": self.path.split("?", 1)[1] if "?" in self.path else "",
            "SERVER_NAME": self.server.server_address[0],
            "SERVER_PORT": str(self.server.server_address[1]),
            "SERVER_PROTOCOL": self.request_version,
            "REMOTE_ADDR": self.client_address[0],
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": _BytesStream(body),
            "wsgi.url_scheme": "http",
        }
        ctype = self.headers.get("Content-Type")
        if ctype:
            env["CONTENT_TYPE"] = ctype
        for k, v in self.headers.items():
            env["HTTP_" + k.upper().replace("-", "_")] = v
        return env

    def _serve(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        env = self._build_environ(body)
        resp = self.app.handle(env)
        data = resp.get_data()
        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() == "content-length":
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = _serve
    do_POST = _serve
    do_PUT = _serve
    do_DELETE = _serve
    do_PATCH = _serve
    do_HEAD = _serve
    do_OPTIONS = _serve


class _BytesStream:
    def __init__(self, data):
        self._d = data
        self._p = 0

    def read(self, n=-1):
        if n < 0:
            out = self._d[self._p:]
            self._p = len(self._d)
            return out
        out = self._d[self._p:self._p + n]
        self._p += len(out)
        return out


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(host, port, app):
    handler = type("_BoundHandler", (_Handler,), {"app": app})
    return _Server((host, int(port)), handler)


def free_port():
    """بورت فاضي على الـloopback — عشان نتفادى تعارض البورتات ⭐."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def serve_forever(app, host="127.0.0.1", port=0):
    """بيرجع (server · base_url) ⭐."""
    srv = make_server(host, port or free_port(), app)
    real_port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, "http://%s:%d" % (host, real_port)


def shutdown_server(srv):
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  🚧 حجب الشبكة — ضمان صريح إن مفيش اتصال خارجي
# ══════════════════════════════════════════════════════════════════
class NetworkBlocked(RuntimeError):
    """محاولة اتصال خارجي والاختبار معزول ⭐."""


_FAKE = {"handler": None, "blocked": True}
_ORIGINALS = {}


def block_network():
    """يقفل أي اتصال خارجي ⭐ — مافيش استثناء ⭐."""
    _FAKE["blocked"] = True
    _FAKE["handler"] = None


def unblock_network():
    _FAKE["blocked"] = False


def fake_http(handler):
    """حطّ يد وهمية ⭐ — عشان نحاكي فشل المصدر أو بطئه ⭐."""
    _FAKE["handler"] = handler


def current_source_mode():
    """وضع المصدر الحالي ⭐ — للتبليغ ⭐."""
    if _FAKE.get("handler") is not None:
        return "fake"
    return "blocked" if _FAKE.get("blocked", True) else "open"


def _fake_call(method, url, **kw):
    handler = _FAKE.get("handler")
    if handler is not None:
        return handler(method, url, **kw)
    if _FAKE.get("blocked", True):
        raise NetworkBlocked(
            "الشبكة مقفولة في بيئة الاختبار المعزولة: %s %s" % (method, url))
    raise NetworkBlocked("الشبكة مقفولة في بيئة الاختبار المعزولة")


class FakeResponse:
    """رد وهمي ⭐ — عشان نحاكي سلوك مصدر خارجي ⭐ (بلا أي شبكة ⭐)."""

    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = int(status_code)
        self._json = json_data
        self.content = text.encode("utf-8") if isinstance(text, str) else text
        self.headers = {"Content-Type": "application/json"}

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        if self._json is not None:
            return self._json
        return json.loads(self.text)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("HTTP %s" % self.status_code)
        return self

    def __repr__(self):
        return "<FakeResponse %s>" % self.status_code


# ⛔ نموذج HTML اصطناعي لصفحة الاكتتاب ⭐ (مش بيانات حقيقية ⭐)
IPO_HTML = (
    "<html><body><div class='ipo'>"
    "<h3>شركة الاختبار المعزولة</h3><span>قادم</span>"
    "<p>سعر الطرح</p><p>10.50 جنيه</p>"
    "<p>قيمة الطرح</p><p>100 مليون جنيه</p>"
    "<p>وصف طويل للتشغيل في بيئة الاختبار المعزولة فقط "
    "وكل الأرقام فيه اصطناعية ومكتوبة للاختبار.</p>"
    "</div><a href=\"/ar/stock/TSTX.CA\">تفاصيل</a></body></html>"
)

# ⛔ مولّد بيانات السوق الاصطناعية ⭐
# 📌 مفيش أي رقم حقيقي ⭐ — كل الأرقام **محسوبة** من ترتيب الصف ⭐
# 📌 والهدف إن التطبيق يعالج **مسار البيانات الحقيقي** ⭐
# 📌 (المسح ⇒ التقييم ⇒ محرّك الفرص ⭐) في بيئة معزولة ⭐.
def _synthetic_value(col, base, idx):
    """قيمة اصطناعية plausível لعمود معيّن ⭐."""
    i = idx
    if col == "close":
        return round(base, 2)
    if col == "change":
        return round(((i % 17) - 8) * 0.83, 2)
    if col == "change_abs":
        return round(base * (((i % 17) - 8) * 0.83) / 100.0, 3)
    if col == "volume":
        return 250000 + (i % 900) * 3700
    if col == "Volatility.D":
        return round(12.0 + (i % 21) * 1.7, 2)
    if col == "relative_volume_10d_calc":
        return round(0.55 + (i % 13) * 0.16, 3)
    if col == "Recommend.All":
        return round(((i % 5) - 2) * 0.4, 2)
    if col == "Recommend.MA":
        return round(((i % 5) - 2) * 0.35, 2)
    if col == "Recommend.Other":
        return round(((i % 5) - 2) * 0.3, 2)
    if col == "beta_1_year":
        return round(0.55 + (i % 9) * 0.18, 3)
    if col == "dividends_yield_current":
        return round((i % 7) * 1.15, 2)
    if col == "market_cap_basic":
        return 1500000000 + (i % 500) * 9100000
    if col == "price_earnings_ttm":
        return round(6.0 + (i % 22), 2)
    if col == "price_book_fq":
        return round(0.75 + (i % 11) * 0.22, 3)
    if col == "return_on_equity":
        return round((i % 34) - 4.0, 2)
    if col == "debt_to_equity":
        return round((i % 46) * 1.1, 2)
    if col == "net_margin":
        return round((i % 29) - 3.0, 2)
    if col == "operating_margin":
        return round((i % 21) - 2.0, 2)
    if col == "earnings_per_share_diluted_ttm":
        return round(base * 0.045, 3)
    if col == "total_revenue":
        return 120000000 + (i % 400) * 1300000
    if col == "price_target_median":
        return round(base * 1.12, 2)
    if col == "price_target_low":
        return round(base * 0.88, 2)
    if col == "price_target_high":
        return round(base * 1.31, 2)
    if col.startswith("Perf."):
        return round(((i % 23) - 11) * 1.7, 2)
    if col in ("EMA10", "EMA20", "EMA50", "EMA200", "SMA20", "SMA50",
               "SMA200", "SMA30|1W", "HullMA9", "Ichimoku.BLine", "P.SAR",
               "BB.upper", "BB.lower", "BB.basis", "VWMA"):
        return round(base * (0.94 + (i % 9) * 0.015), 3)
    if col in ("RSI", "RSI[1]"):
        return round(28.0 + (i % 45), 2)
    if col in ("MACD.macd", "MACD.signal"):
        return round(((i % 21) - 10) * 0.35, 4)
    if col in ("Stoch.K", "Stoch.D"):
        return round(12.0 + (i % 76), 2)
    if col == "CCI20":
        return round(((i % 241) - 120), 2)
    if col in ("ADX", "ADX+DI", "ADX-DI"):
        return round(8.0 + (i % 33), 2)
    if col == "Mom":
        return round(((i % 19) - 9) * 0.8, 3)
    if col == "AO":
        return round(((i % 15) - 7) * 0.6, 4)
    if col == "UO":
        return round(18.0 + (i % 62), 2)
    if col == "W.R":
        return round(-(5.0 + (i % 88)), 2)
    if col == "ATR":
        return round(base * 0.035, 4)
    if col == "BBPower":
        return round(((i % 17) - 8) * 0.9, 4)
    if col.startswith("Pivot.M.Classic"):
        return round(base * (1.0 + ((i % 7) - 3) * 0.012), 3)
    if col.startswith("High."):
        return round(base * 1.18, 3)
    if col.startswith("Low."):
        return round(base * 0.82, 3)
    if col.startswith("volume|"):
        return 200000 + (i % 700) * 2900
    return None


def synthetic_scan_response(payload):
    """بيرجّع رد مسح اصطناعي ⭐ بنفس شكل الـTradingView ⭐."""
    payload = payload or {}
    cols = list(payload.get("columns") or [])
    tickers = list(((payload.get("symbols") or {}).get("tickers")) or [])
    rows = []
    for idx, tk in enumerate(tickers):
        base = 12.0 + (idx % 89) * 4.75
        d = [_synthetic_value(c, base, idx) for c in cols]
        rows.append({"s": str(tk), "d": d})
    return {"data": rows}


def source_handler(mode, delay=0.0):
    """بيرجّع يد وهمية للمصدر ⭐ — بأنماط أعطال متدرجة ⭐."""
    def handler(method, url, **kw):
        if delay:
            time.sleep(float(delay))
        low = str(url or "").lower()
        if mode == "timeout":
            raise TimeoutError("source timeout (synthetic)")
        if mode == "http_500":
            return FakeResponse("upstream error", status_code=500)
        if mode == "garbage":
            return FakeResponse("<html>garbage payload</html>", status_code=200)
        if mode == "ok":
            body = kw.get("json")
            if isinstance(body, dict) and body.get("symbols") \
                    and body.get("columns"):
                data = synthetic_scan_response(body)
                return FakeResponse(json.dumps(data), status_code=200,
                                    json_data=data)
            if "foudalens" in low or "/ipo" in low:
                return FakeResponse(IPO_HTML, status_code=200)
            return FakeResponse('{"ok": true}', status_code=200)
        raise NetworkBlocked("الشبكة مقفولة: %s %s" % (method, url))
    return handler


# ══════════════════════════════════════════════════════════════════
#  🔌 تركيب البدائل
# ══════════════════════════════════════════════════════════════════
def install_shims():
    """بيركّب `flask` و `requests` و `werkzeug` المصغّرة ⭐.

    ⛔ ملاحظة مهمة ⭐: ده **مش** تطبيق وهمية ⭐
    ⛔ الكود اللي بيتنفّذ هو **نفس** `update_prices.py` حرفياً ⭐
    ⛔ واللي بنبدّله هو طبقة النقل بس ⭐ (HTTP · JSON · الطلب ⭐).
    """
    import types

    flask_mod = types.ModuleType("flask")
    flask_mod.Flask = Flask
    flask_mod.jsonify = jsonify
    flask_mod.request = request
    flask_mod.Response = Response
    flask_mod.g = g
    flask_mod.send_from_directory = send_from_directory
    flask_mod.abort = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("abort"))
    flask_mod.__version__ = "mini-http (اختبار معزول)"

    werkzeug_pkg = types.ModuleType("werkzeug")
    werkzeug_exc = types.ModuleType("werkzeug.exceptions")

    class HTTPException(Exception):
        code = 500

    werkzeug_exc.HTTPException = HTTPException
    werkzeug_exc.NotFound = type("NotFound", (HTTPException,), {"code": 404})
    werkzeug_exc.BadRequest = type("BadRequest", (HTTPException,), {"code": 400})
    werkzeug_exc.TooManyRequests = type("TooManyRequests", (HTTPException,),
                                        {"code": 429})
    werkzeug_pkg.exceptions = werkzeug_exc

    req_mod = types.ModuleType("requests")
    req_mod.get = lambda url, **kw: _fake_call("GET", url, **kw)
    req_mod.post = lambda url, **kw: _fake_call("POST", url, **kw)
    # ⛔ الحجب المشترك ⭐ (نفس الطبقة في بيئتين ⭐) ⭐
    try:
        from pathlib import Path as _P
        import sys as _s
        _here = str(_P(__file__).resolve().parent)
        if _here not in _s.path:
            _s.path.insert(0, _here)
        import net_block as _nb
        _nb.install()
    except Exception:
        pass
    req_mod.put = lambda url, **kw: _fake_call("PUT", url, **kw)
    req_mod.delete = lambda url, **kw: _fake_call("DELETE", url, **kw)
    exc_mod = types.ModuleType("requests.exceptions")
    exc_mod.RequestException = type("RequestException", (Exception,), {})
    exc_mod.Timeout = type("Timeout", (exc_mod.RequestException,), {})
    exc_mod.ConnectionError = type("ConnectionError", (exc_mod.RequestException,), {})
    req_mod.exceptions = exc_mod

    sys_modules = __import__("sys").modules
    sys_modules["flask"] = flask_mod
    sys_modules["werkzeug"] = werkzeug_pkg
    sys_modules["werkzeug.exceptions"] = werkzeug_exc
    sys_modules["requests"] = req_mod
    sys_modules["requests.exceptions"] = exc_mod
    return flask_mod


if __name__ == "__main__":
    print("🧰 طبقة HTTP المعزولة — الجولة ٢٥")
    print("   شغّل: python3 tools/staging/mini_http.py")
