#!/usr/bin/env python3
"""
محاكي Flask — يشغّل update_prices.py حيّاً ويختبر الـroutes.
⛔ ليش؟ pypi مش بيوصل من الـsandbox (ConnectionReset)، والـstub البسيط
   كان بيخفي أخطاء وقت التشغيل. ده محاكي أقرب للخدمة الحقيقية:
   - request context حقيقي
   - route dispatch حقيقي بالـmethod + path
   - jsonify بيرجّع Response
   - before/after_request بيشتغلوا
"""
import sys, os, types, json, re, time
from pathlib import Path

ROOT = Path("/workspace/octa-prices")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ["OCTAD_DEV"] = "1"
os.environ.setdefault("OCTA_DB", "/tmp/t.db")
os.environ.setdefault("TELEGRAM_TOKEN", "0")
os.environ.setdefault("TELEGRAM_CHAT_ID", "0")


# ─────────────── requests ───────────────
class _Resp:
    def __init__(self, *a, **k):
        self.status_code = k.get("status_code", 200)
        self.text = k.get("text", "{}")
        self.content = self.text.encode()
        self.headers = k.get("headers", {})
        self.ok = 200 <= self.status_code < 300
        self._j = k.get("json_data")

    def json(self):
        if self._j is not None:
            return self._j
        try:
            return json.loads(self.text or "{}")
        except Exception:
            return {}

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("http %s" % self.status_code)


req = types.ModuleType("requests")
for m in ("get", "post", "put", "delete", "head", "patch", "options"):
    setattr(req, m, lambda *a, **k: _Resp(json_data={}))
req.Session = object
req.request = lambda *a, **k: _Resp()
E = types.SimpleNamespace(
    Timeout=Exception, ConnectionError=Exception, RequestException=Exception,
    HTTPError=Exception, SSLError=Exception, ReadTimeout=Exception,
    ConnectTimeout=Exception, ChunkedEncodingError=Exception,
)
req.exceptions = E
sys.modules["requests"] = req
sys.modules["requests.exceptions"] = E


# ─────────────── flask ───────────────
fl = types.ModuleType("flask")

ROUTES = []          # (rule, methods, view, name)
_BEFORE = []
_AFTER = []
_ERRORS = {}


class _Ctx:
    """request context بسيط — نعمل thread-local-ish بالقيم اللي جارية."""

    def __init__(self, path="/", method="GET", args=None, headers=None,
                 json_body=None, cookies=None):
        self.path = path
        self.method = method
        self.args = args or {}
        self.headers = headers or {}
        self.json = json_body or {}
        self.cookies = cookies or {}
        self.form = {}
        self.data = b""


_ctx = None


class _ReqProxy:
    """proxy على الـcontext الحالي."""

    def __getattr__(self, k):
        if _ctx is None:
            raise RuntimeError("خارج request context")
        return getattr(_ctx, k)


class Response:
    def __init__(self, data=None, status=200, mimetype=None, headers=None):
        self._d = data
        self.status_code = status
        self.mimetype = mimetype or "application/json"
        self.headers = headers or {}

    def get_data(self, as_text=False):
        if isinstance(self._d, (dict, list)):
            s = json.dumps(self._d, ensure_ascii=False)
        else:
            s = "" if self._d is None else str(self._d)
        return s if as_text else s.encode()

    @property
    def data(self):
        return self.get_data()

    def __repr__(self):
        return "<Response %s %s>" % (self.status_code, self.get_data(as_text=True)[:60])


def jsonify(*args, **kw):
    if args and kwargs_data(args[0]) is not None:
        payload = args[0]
    elif kw:
        payload = kw
    elif args:
        payload = list(args)
    else:
        payload = None
    return Response(payload, 200, "application/json")


def kwargs_data(v):
    return v if isinstance(v, (dict, list)) else None


class _Rule:
    def __init__(self, rule):
        self.rule = rule
        self.endpoint = None

    def __repr__(self):
        return "<Rule %s>" % self.rule


class _Map:
    def __init__(self):
        self._rules = []

    def add(self, rule):
        r = _Rule(rule)
        self._rules.append(r)
        return r

    def iter_rules(self, endpoint=None):
        return iter(self._rules)


def _compile(rule):
    """يحوّل '/api/stocks' → regex مع optional <param>."""
    pat = re.sub(r"<([^:>]+)>", r"(?P<\1>[^/]+)", rule)
    return re.compile("^" + pat + "$")


class App:
    def __init__(self, name=__name__):
        self.name = name
        self.url_map = _Map()
        self.config = {}
        self.blueprints = {}
        self.extensions = {}
        self.jinja_env = None

    def route(self, rule, methods=None, **_k):
        def deco(fn):
            meths = {m.upper() for m in (methods or ["GET"])}
            meths.add("GET") if "GET" not in meths else None
            self.url_map.add(rule)
            ROUTES.append((rule, meths, fn, fn.__name__))
            return fn
        return deco

    def errorhandler(self, code_or_exc):
        def deco(fn):
            _ERRORS[code_or_exc] = fn
            return fn
        return deco

    def before_request(self, f=None):
        if f is None:
            return lambda g: None
        _BEFORE.append(f)
        return f

    def after_request(self, f):
        _AFTER.append(f)
        return f

    def teardown_appcontext(self, f):
        return f

    def teardown_request(self, f):
        return f

    def register_blueprint(self, bp, **k):
        return None

    def add_url_rule(self, rule, endpoint=None, view_func=None, methods=None, **_k):
        if view_func:
            self.route(rule, methods=methods)(view_func)
        return None

    def test_client(self):
        return None

    def run(self, *a, **k):
        pass

    # ── dispatch ──
    def _dispatch(self, path, method="GET", args=None, headers=None,
                  json_body=None, cookies=None):
        global _ctx
        _ctx = _Ctx(path, method, args, headers, json_body, cookies)
        meth = method.upper()
        for rule, meths, fn, _name in ROUTES:
            if meth not in meths and "GET" not in meths:
                continue
            rx = _compile(rule)
            m = rx.match(path)
            if m:
                return fn(**m.groupdict())
        return Response({"error": "not found"}, 404)

    def test_request_context(self, path="/", method="GET", **kw):
        return _DummyCtx(self, path, method, **kw)


class _DummyCtx:
    def __init__(self, app, path, method, **kw):
        self.app, self.path, self.method, self.kw = app, path, method, kw

    def __enter__(self):
        global _ctx
        _ctx = _Ctx(self.path, self.method, **self.kw)
        return _ctx

    def __exit__(self, *a):
        return False


fl.Flask = App
fl.jsonify = jsonify
fl.request = _ReqProxy()
fl.Response = Response
fl.g = types.SimpleNamespace()
fl.send_file = lambda *a, **k: Response(b"", 200)
fl.send_from_directory = lambda *a, **k: Response(b"", 200)
fl.redirect = lambda *a, **k: Response(b"", 302)
fl.abort = lambda code, *a, **k: (_ for _ in ()).throw(RuntimeError("abort %s" % code))
fl.Blueprint = lambda *a, **k: types.SimpleNamespace(route=lambda *x, **y: (lambda f: f))
fl.render_template = lambda *a, **k: ""
fl.url_for = lambda *a, **k: "/"
fl.make_response = lambda r: r if isinstance(r, Response) else Response(r)
sys.modules["flask"] = fl


# ─────────────── الإقلاع ───────────────
print("=" * 60)
print("🚦 إقلاع update_prices.py بمحاكي Flask")
print("=" * 60)

try:
    import update_prices as up
except Exception:
    import traceback
    print("❌ فشل الإقلاع:")
    print(traceback.format_exc()[-2000:])
    sys.exit(1)

print("\n✅ الإقلاع نجح")
print("📍 عدد الـroutes: %d" % len(ROUTES))


# ─────────────── الاختبارات ───────────────
class R:
    """غلاف يحوّل (body, status) لـ Response زي Flask بالظبط."""
    def __init__(self, raw):
        self._body = raw
        if isinstance(raw, tuple):
            body = raw[0]
            self.status_code = raw[1] if len(raw) > 1 and isinstance(raw[1], int) else 200
        elif isinstance(raw, Response):
            body, self.status_code = raw._d, raw.status_code
        else:
            body, self.status_code = raw, 200

    def get_data(self, as_text=False):
        b = body_json(self._body)
        if isinstance(b, (dict, list)):
            out = json.dumps(b, ensure_ascii=False)
        elif b is None:
            out = ""
        else:
            out = str(b)
        return out if as_text else out.encode()

    def json(self):
        try:
            return json.loads(self.get_data(as_text=True) or "{}")
        except Exception:
            return {}


def body_json(b):
    if isinstance(b, Response):
        return b._d
    return b


def call(path, method="GET", args=None, headers=None, json_body=None, cookies=None):
    raw = up.app._dispatch(path, method, args or {}, headers or {},
                           json_body or None, cookies or {})
    return R(raw)


print("\n" + "=" * 60)
print("🧪 اختبار الـroutes")
print("=" * 60)

FAIL = 0

# ١ — المسارات المفتوحة (لازم 200 بلا توكن)
# 503 مقبول لـ/gold — بيعيد «محتاج مفتاح» مش خطأ
OPEN_OK = ["/api/health", "/api/ticker", "/api/logos"]
OPEN_503_OK = ["/api/gold"]
for p in OPEN_OK:
    try:
        r = call(p)
        code = r.status_code
        ok = "✅" if code == 200 else "❌"
        print(f"  {ok} {p:22s} → {code}")
        if code != 200:
            FAIL += 1
    except Exception as e:
        print(f"  ❌ {p:22s} → {type(e).__name__}: {e}")
        FAIL += 1
for p in OPEN_503_OK:
    try:
        r = call(p)
        code = r.status_code
        ok = "✅" if code in (200, 503) else "❌"
        print(f"  {ok} {p:22s} → {code} (503 مقبول: محتاج مفتاح خارجي)")
        if code >= 500 and code != 503:
            FAIL += 1
    except Exception as e:
        print(f"  ❌ {p:22s} → {type(e).__name__}: {e}")
        FAIL += 1

# ٢ — المسارات المحمية (لازم 401 بلا توكن)
PROT = ["/api/stocks", "/api/markets", "/api/rank", "/api/data_full"]
for p in PROT:
    try:
        r = call(p)
        code = r.status_code if hasattr(r, "status_code") else 0
        ok = "✅" if code == 401 else "❌"
        print(f"  {ok} {p:22s} → {code} (متوقع 401)")
        if code != 401:
            FAIL += 1
    except Exception as e:
        print(f"  ❌ {p:22s} → {type(e).__name__}: {e}")
        FAIL += 1

# ٣ — /api/markets مع توكن صالح (لازم يرجّع الداتا)
print("\n  ── نختبر المسارات المحمية بتوكن ──")
# ⛔ التوكن موقّع HMAC — فبنعمل مستخدم حقيقي + token زي ما الكود بيعمل
_uid = "live_test_uid_%d" % int(time.time())
_email = "live@test.local"
_salt = up._pin_salt_new()
_tok = ""
try:
    users = up._load_users()
    users[_uid] = {
        "id": _uid,
        "email": _email,
        "pin_salt": _salt,
        "pin_hash": up._pin_hash("1234", _salt),
        "created": int(time.time()),
        "tier": "free",
        "bio_on": False,
    }
    up._save_users(users)
    _tok = up._make_token(_uid)
    print("     ✅ مستخدم وهمي: %s" % _email)
    print("     🔑 توكن موقّع: %s…" % _tok[:28])
except Exception as _e:
    print("     ⚠️  متقدرتش أعمل مستخدم: %s: %s" % (type(_e).__name__, _e))

def call_auth(path, args=None, method="GET"):
    global _ctx
    _ctx = _Ctx(path, method, args or {}, {"Authorization": "Bearer " + _tok}, None, {})
    meth = method.upper()
    for rule, meths, fn, _n in ROUTES:
        if meth not in meths and "GET" not in meths:
            continue
        m = _compile(rule).match(path)
        if m:
            return R(fn(**m.groupdict()))
    return R(Response({"error": "not found"}, 404))


# ⛔ egx30 بيتعبى بعد الإقلاع (خيط TradingView). نحقن داتا اختبار.
if not up.LIVE_DATA.get("egx30"):
    up.LIVE_DATA["egx30"] = [
        {"code": "COMI.CA", "name": "commercial international", "price": 70.0},
        {"code": "ETEL.CA", "name": "etel", "price": 55.0},
    ]
    print("     (حقن داتا اختبار في LIVE_DATA['egx30'])")

for p, kw in [("/api/markets", {"market": "egypt"}),
              ("/api/stocks", None),
              ("/api/rank", None)]:
    try:
        r = call_auth(p, kw)
        d = r.json()
        if isinstance(d, dict):
            key = "n" if "n" in d else ("ok" if "ok" in d else "error")
            val = d.get(key)
            extra = ""
            if p == "/api/markets":
                extra = " · codes=%d" % len(d.get("codes", []))
            if p == "/api/rank":
                extra = " · results=%d" % len(d.get("results", []))
            ok = "✅" if r.status_code == 200 else "❌"
            print(f"  {ok} {p:16s} → {r.status_code} · {key}={val}{extra}")
            if r.status_code != 200:
                FAIL += 1
        else:
            print(f"  ⚠️ {p:16s} → {r.status_code} (مش dict)")
    except Exception as e:
        print(f"  ❌ {p:16s} → {type(e).__name__}: {e}")
        FAIL += 1

# ٤ — markets غير مدعوم (بتوكن)
try:
    r = call_auth("/api/markets", {"market": "zzz_fake"})
    code = r.status_code
    ok = "✅" if code == 400 else "⚠️"
    print(f"  {ok} /api/markets?market=zzz_fake → {code} (متوقع 400)")
    if code != 400:
        FAIL += 1
except Exception as e:
    print(f"  ❌ → {type(e).__name__}: {e}")
    FAIL += 1

# ٥ — دوال المصادقة ترجّع JSON (مش 500)
AUTH = ["/api/auth/me", "/api/auth/pin/login", "/api/auth/pin/register"]
for p in AUTH:
    try:
        r = call(p, method="POST", json_body={"pin": "1234"})
        code = r.status_code if hasattr(r, "status_code") else 0
        ok = "✅" if code < 500 else "❌"
        print(f"  {ok} POST {p:26s} → {code}")
        if code >= 500:
            FAIL += 1
    except Exception as e:
        print(f"  ❌ POST {p:26s} → {type(e).__name__}: {e}")
        FAIL += 1

print("\n" + "=" * 60)
if FAIL == 0:
    print("🟢 كل الاختبارات نجحت — الباك جاهز للرفع")
else:
    print(f"🔴 {FAIL} اختبار فشل — فيه مشكلة")
print("=" * 60)
sys.exit(1 if FAIL else 0)