#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ الجولة ١٧ — عقد الحداثة/التغطية الموحّد في مسارات /api/opp/* (R16-N3).

📌 العيب (من مراجعة مستقلة):
   المسارات التلاتة دي ما كنتش بتنشر حقول الحداثة/التغطية
   في **المستوى الرئيسي** من الرد:
     /api/opp/detail/<key>/<code>
     /api/opp/explain/<key>/<code>
     /api/opp/summary
   بينما /api/opp/strategies و /api/opp/list/<key> بينشروا الحقول دي ⇒
   الواجهة بتقرا «التغطية/الحداثة» من مكان واحد وبتنسى المسارات التلاتة.

📌 المطلوب: **عقد موحّد** — المسارات الخمسة كلهم ينشروا نفس الحقول
   في المستوى الرئيسي، بنفس الأسماء ونفس الدلالات:
     coverage_status · data_state · freshness_summary_ar · current_session_date

📌 الاختبار بيفحص **رد JSON فعلي** من كل مسار (مش تحليل نص الكود):
   جلسة حقيقية (تسجيل دخول بـPIN) + payload صناعي معزول.

⛔ بيانات صناعية · مافيش شبكة · مافيش إنتاج · مافيش لمس لبيانات حقيقية.
⛔ مافيش تغيير في سلوك المسارات — فحص الرد المنشور بس.
📌 التشغيل: python3 test_round17_n3_contract.py
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="r17n3_")
sys.path.insert(0, HERE)

# ⛔ بيئة معزولة — أسرار صناعية (مافيش سر حقيقي · مافيش إنتاج)
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "R17-N3-SECRET"
os.environ["OCTA_PIN_PEPPER"] = "R17-N3-PEPPER"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["OCTA_RATE_MULT"] = "300"

# ⛔ لو Flask/requests مش موجودين ⇒ بنستخدم الستب المعزول في المستودع
try:
    import flask as _flask_probe  # noqa: F401
    import requests as _requests_probe  # noqa: F401
    REAL_FLASK = True
except Exception:
    REAL_FLASK = False

import _stub_env  # noqa: E402

FL_MOD = None
if not REAL_FLASK:
    FL_MOD, _ = _stub_env.install()
    # ⛔ الـafter_request بيحتاج get_data/set_data على رد الستب
    for _cls in (FL_MOD.jsonify.__globals__["Resp"],
                 FL_MOD.jsonify.__globals__["_Response"]):
        if not hasattr(_cls, "get_data"):
            def _get_data(self):
                return json.dumps(self.body, ensure_ascii=False).encode("utf-8")

            def _set_data(self, raw):
                if isinstance(raw, (bytes, bytearray)):
                    self.body = json.loads(raw.decode("utf-8"))
                else:
                    self.body = raw

            _cls.get_data = _get_data
            _cls.set_data = _set_data

import opp_engine as oe  # noqa: E402
import update_prices as up  # noqa: E402

# ── كل التخزين يروح على مجلد مؤقت ⬇️ مافيش ملف في المشروع بيتلمس ──
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.TRACK_FILE = Path(TMP) / "track.json"

# ⛔ قيم السجل (contract) — نفس دلالات المحرّك
COVERAGE_VALUES = ("complete", "partial", "unavailable")
CONTRACT_FIELDS = ("coverage_status", "data_state",
                   "freshness_summary_ar", "current_session_date")

UID = "r17n3-user"
PIN = "1122"
DEV = "d" * 64


def _has_arabic(text):
    """⛔ النص عربي فعلاً (مش أرقام ولا رموز)."""
    return any("؀" <= ch <= "ۿ" for ch in str(text))


def _stock(code, **kw):
    """سهم صناعي مؤهّل (مفيش بيانات حيّة)."""
    d = {
        "code": code, "name": "سهم اختبار", "sector": "صناعة", "price": 50.0,
        "change": 1.2, "technical_score": 72.0, "technical_signal": "صاعد",
        "fund_score": 65.0, "liquidity_score": 70.0, "news_score": 55.0,
        "sentiment_score": 50.0, "safety_score": 64.0,
        "rsi": 52.0, "perf_1m": 6.0, "perf_3m": 14.0,
        "roe": 18.0, "net_margin": 12.0, "de_ratio": 35.0,
        "pe": 12.0, "pb": 1.4, "eps": 4.2, "div_yield": 6.0,
        "mkt_cap": 12e9, "rel_volume": 1.3, "volume": 900000,
        "vol_5": 880000, "vol_60": 850000,
        "beta": 0.9, "volatility": 28.0, "vol1y": 30.0, "mdd1y": -18.0,
        "cfo": 900.0, "ni": 700.0, "upside": 18.0, "fair_value": 59.0,
        "ts": "2026-11-17T10:00:00Z",
        "all_axes": {"technical": 72.0, "fundamental": 65.0, "liquidity": 70.0,
                     "risk": 66.0, "news": 55.0, "sentiment": 50.0},
    }
    d.update(kw)
    return d


def _payload():
    """⛔ payload صناعي — تغطية كاملة وحداثة fresh (مافيش شبكة)."""
    now = time.time()
    meta = {
        "generated_at": "2026-11-17T10:00:00Z", "source": "live",
        "market_phase": "open", "session_date": "2026-11-17",
        "source_as_of": "2026-11-17T09:59:00Z",
        "last_success_at": now - 30,
        "data_freshness": oe.freshness_state(now - 30, "open", now,
                                             coverage=100.0,
                                             requested=3, updated=3),
        "sources": [{"source": "Test", "as_of": "2026-11-17T09:59:00Z"}],
    }
    stocks = [_stock("R17A"), _stock("R17B"), _stock("R17C")]
    return oe.build_payload(stocks, None, meta)


def _mk_user():
    """مستخدم صناعي (Free) + توكن جلسة حقيقي."""
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(DEV)
    rec = {
        "id": UID, "name": "r17n3", "email": UID + "@example.test",
        "pin_hash": up._pin_hash(PIN, salt), "pin_salt": salt,
        "pin_idx": up._pin_index(PIN), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": 0,
        "bio_hash": dev_hash, "bio_hashes": [dev_hash],
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
    }
    with up.USERS_LOCK:
        users = up._load_users()
        users[UID] = rec
        up._save_users(users)


# ── طبقة الطلبات ──────────────────────────────────────────────────────────
def _stub_match(rules, path):
    """⛔ الستب: مطابقة المسار مع المتغيّرات (<key> · <code>)."""
    parts = [p for p in str(path).split("/") if p]
    for rule in rules:
        if rule.path == path:
            return rule, {}
        tparts = [p for p in rule.path.split("/") if p]
        if len(tparts) != len(parts):
            continue
        params = {}
        good = True
        for tpart, part in zip(tparts, parts):
            if tpart.startswith("<") and tpart.endswith(">"):
                params[tpart[1:-1]] = part
            elif tpart != part:
                good = False
                break
        if good:
            return rule, params
    return None, {}


def _stub_norm(out):
    """⛔ الستب: رد Flask (tuple أو Resp) ⇒ Resp واحد."""
    resp_cls = FL_MOD.jsonify.__globals__["Resp"]
    if isinstance(out, tuple):
        body = out[0] if out else resp_cls({})
        status = out[1] if len(out) > 1 else 200
        out = resp_cls(body.get_json() if hasattr(body, "get_json") else body,
                       status)
    if not isinstance(out, resp_cls):
        out = resp_cls(out)
    return out


def _stub_final(resp):
    """⛔ الستب: (كود الحالة، رد JSON) بعد الـafter_request."""
    body = resp.get_json() if hasattr(resp, "get_json") else resp
    if not isinstance(body, dict):
        body = {"body": body}
    return int(getattr(resp, "status_code", 200) or 200), body


def _stub_get(path, headers=None):
    """⛔ الستب: نفس منطق الـdispatch (before/after + معالج المسار)."""
    req = FL_MOD.request
    req.reset()
    req.path = path
    req.method = "GET"
    req.headers = dict(headers or {})
    req.args = {}
    for fn in up.app.before_reqs:
        early = fn()
        if early is not None:
            return _stub_final(_stub_norm(early))
    rule, params = _stub_match(up.app.url_map, path)
    if rule is None:
        return 404, {"error": "not found"}
    try:
        resp = _stub_norm(rule.handler(**params))
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": "%s: %s" % (type(exc).__name__, exc)}
    for fn in up.app.after_reqs:
        out2 = fn(resp)
        if out2 is not None and hasattr(out2, "status_code"):
            resp = out2
    return _stub_final(resp)


def _get(path, headers=None):
    """GET على مسار ⇒ (كود الحالة، رد JSON)."""
    if REAL_FLASK:
        resp = up.app.test_client().get(path, headers=headers or {})
        return resp.status_code, (resp.get_json() or {})
    return _stub_get(path, headers)


# ⛔ الجلسة: تسجيل دخول حقيقي (PIN + جهاز) ⇒ توكن
_HEADERS = {}


def _boot():
    global _HEADERS
    if _HEADERS:
        return _HEADERS
    _mk_user()
    if REAL_FLASK:
        resp = up.app.test_client().post(
            "/api/auth/pin/login", json={"pin": PIN, "device": DEV},
            headers={"X-Forwarded-For": "10.0.0.1"})
        status = resp.status_code
        body = resp.get_json() or {}
    else:
        status, body = _stub_get_login()
    if status != 200:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    token = body.get("token") or body.get("access_token")
    if not token:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    _HEADERS = {"Authorization": "Bearer " + token}
    return _HEADERS


def _stub_get_login():
    """⛔ الستب: POST على مسار المصادقة (بنفس منطق الـdispatch)."""
    req = FL_MOD.request
    req.reset()
    req.path = "/api/auth/pin/login"
    req.method = "POST"
    req.headers = {"X-Forwarded-For": "10.0.0.1"}
    req.json = {"pin": PIN, "device": DEV}
    req.args = {}
    for fn in up.app.before_reqs:
        early = fn()
        if early is not None:
            return _stub_final(_stub_norm(early))
    rule, params = _stub_match(up.app.url_map, req.path)
    if rule is None:
        return 404, {"error": "not found"}
    try:
        resp = _stub_norm(rule.handler(**params))
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": "%s: %s" % (type(exc).__name__, exc)}
    return _stub_final(resp)


def _first_strategy(payload):
    """أول استراتيجية فيها صفوف (عشان نفحص detail/explain)."""
    for key, lst in (payload.get("lists") or {}).items():
        items = lst.get("items") or []
        if items:
            return key, items[0].get("code")
    return None, None


class OppContractBase(unittest.TestCase):
    """⛔ أساس مشترك: payload صناعي + جلسة حقيقية."""

    @classmethod
    def setUpClass(cls):
        cls.payload = _payload()
        cls.headers = _boot()

    def setUp(self):
        self.old = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["opp"] = self.payload
        self.key, self.code = _first_strategy(self.payload)
        if not self.key:
            self.skipTest("مافيش استراتيجية فيها صفوف")

    def tearDown(self):
        up.LIVE_DATA["opp"] = self.old

    def _body(self, path):
        """رد JSON فعلي من المسار (بعد التأكد إنه مش خطأ)."""
        status, body = _get(path, self.headers)
        self.assertEqual(status, 200, "%s => %s %s"
                         % (path, status, json.dumps(body)[:200]))
        self.assertIsInstance(body, dict, path)
        return body

    def _assert_contract(self, body, where):
        """⛔ العقد: 4 حقول في **المستوى الرئيسي** (مش جوه item)."""
        for field in CONTRACT_FIELDS:
            self.assertIn(field, body,
                          "%s مافيش %s في المستوى الرئيسي" % (where, field))
        self.assertIn(body.get("coverage_status"), COVERAGE_VALUES,
                      "%s ⇒ coverage_status مش من القيم المعروفة: %r"
                      % (where, body.get("coverage_status")))
        self.assertTrue(str(body.get("data_state") or "").strip(),
                        "%s ⇒ data_state فاضي" % where)
        summary = body.get("freshness_summary_ar")
        self.assertTrue(str(summary or "").strip(),
                        "%s ⇒ freshness_summary_ar فاضي" % where)
        self.assertTrue(_has_arabic(summary),
                        "%s ⇒ freshness_summary_ar مش عربي: %r" % (where, summary))
        self.assertTrue(str(body.get("current_session_date") or "").strip(),
                        "%s ⇒ current_session_date فاضي" % where)


class TestOppContractOnMissingRoutes(OppContractBase):
    """⛔ المسارات التلاتة الناقصة — لازم تنشر العقد في المستوى الرئيسي."""

    def test_detail_publishes_freshness_contract(self):
        """⛔ بيكشف: /api/opp/detail مافيش فيه عقد الحداثة/التغطية."""
        body = self._body("/api/opp/detail/%s/%s" % (self.key, self.code))
        self._assert_contract(body, "/api/opp/detail")

    def test_explain_publishes_freshness_contract(self):
        """⛔ بيكشف: /api/opp/explain مافيش فيه عقد الحداثة/التغطية."""
        body = self._body("/api/opp/explain/%s/%s" % (self.key, self.code))
        self._assert_contract(body, "/api/opp/explain")

    def test_summary_publishes_freshness_contract(self):
        """⛔ بيكشف: /api/opp/summary مافيش فيه عقد الحداثة/التغطية."""
        body = self._body("/api/opp/summary")
        self._assert_contract(body, "/api/opp/summary")


class TestOppContractNoRegression(OppContractBase):
    """⛔ عهد عدم التراجع: المسارات اللي كانت شغالة لازم تفضل شغالة."""

    def test_strategies_still_publishes_freshness_contract(self):
        """⛔ بيكشف: /api/opp/strategies فقد عقد الحداثة/التغطية."""
        body = self._body("/api/opp/strategies")
        self._assert_contract(body, "/api/opp/strategies")

    def test_list_still_publishes_freshness_contract(self):
        """⛔ بيكشف: /api/opp/list فقد عقد الحداثة/التغطية."""
        body = self._body("/api/opp/list/%s" % self.key)
        self._assert_contract(body, "/api/opp/list")


if __name__ == "__main__":
    unittest.main(verbosity=2)
