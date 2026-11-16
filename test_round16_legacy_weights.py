#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ الجولة ١٦ — سرّية أوزان المحرّك القديم (Legacy).

📌 المطلوب (ملاحظة المالك على تقرير الجولة ١٥ — بند ٥ · خطورة 4/5):
   ① المسار القديم /api/strategies كان **مفتوح** (من غير جلسة) ⇒ بيرجّع
      بنية أوزان الاستراتيجيات القديمة (STRATEGIES[key]["weights"]).
   ② المسار القديم /api/strategy/<code>/<strategy> كان **مفتوح** كمان ⇒
      بيرجّع نتيجة التقييم كاملة (المحاور · المجموع قبل الخصم · خصم
      المخاطرة · خصم الفلاتر) ⇒ **الوصفة بتتسرّب رياضياً** (مش بس
      المفتاح اللي اسمه weights).
   ③ الإصلاح: قفل المسارين بجلسة (زي محرّك الفرص الجديد بالظبط) + منع
      بناء مفتاح weights في الرد خالص (مش بس إخفاء بالاسم).

📌 كل اختبار سالب: التعليق فوق كل واحد بيوضح «بيكشف إيه».
📌 التشغيل: python test_round16_legacy_weights.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import ast
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_r16weights_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r16weights-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r16weights-pepper"
os.environ["OCTAD_DEV"] = "1"
# ⛔⛔⛔ البوابة العامة (OCTA_API_DENY_DEFAULT) **مطفية** هنا — زي
#    الإنتاج بالظبط (الافتراضي off في update_prices.py:716).
#    ⇒ الاختبار بيكشف الثغرة الحقيقية: المسار القديم ما كانش
#    محمي بجلسته هو ⇒ لازم guard جوّه المسار نفسه.
os.environ["OCTA_API_DENY_DEFAULT"] = "off"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402
import update_prices as up  # noqa: E402

SRC = Path(HERE) / "update_prices.py"

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"

FREE_UID = "r16w-free"
PRO_UID = "r16w-pro"
FREE_PIN = "5566"
PRO_PIN = "7788"
FREE_DEV = "f" * 64
PRO_DEV = "9" * 64

# ⛔ مفاتيح الوصفة اللي ما بتترجعش في أي رد عام
RECIPE_KEYS = {
    "weights", "available_weight", "strategy_score", "axis_weights",
    "axisWeights", "AXIS_WEIGHTS", "current_weights", "old_weights",
    "new_weights", "risk_penalty_mult", "min_liquidity", "min_safety",
    "min_div_yield", "points_max", "criteria_weight", "sub_scores",
    "subScores", "raw_scores", "rawScore", "part_scores", "formula",
    "formulae", "scoring", "calibration",
}

# ⛔ حقول كشف بنية التقييم (المسار القديم كان بيرجّعها للزائر)
EVAL_FIELDS = {"axes", "base", "risk_penalty", "liquidity_penalty",
               "filter_penalty", "filters_passed", "filter_notes",
               "missing_axes", "confidence"}

# ⛔ كل المسارات اللي فيها استراتيجيات (القديمة + الجديدة)
LEGACY_PATHS = ("/api/strategies",
                "/api/strategy/S00/balanced",
                "/api/strategy/S00/swing")
NEW_PATHS = ("/api/opp/strategies",
             "/api/opp/summary",
             "/api/opp/list/swing",
             "/api/opp/detail/swing/S00",
             "/api/opp/explain/swing/S00")
ENGINE_PATHS = ("/api/engine-weights",)

SECTORS = ["banks", "food", "real estate", "chemicals",
           "retail", "services", "mining", "insurance"]

AXIS_KEYS = ("technical", "fundamental", "liquidity", "news",
             "sentiment", "risk", "portfolio")


def _stock(code, i, **kw):
    """سهم اصطناعي بمتغيرات مختلفة ⇒ محاور مختلفة بين الأسهم."""
    d = {
        "code": code, "name": "s-" + code, "sector": SECTORS[i % len(SECTORS)],
        "price": 20.0 + i * 7.5, "change": 0.4 * i - 1.5,
        "technical_score": 50.0 + i, "technical_signal": "up",
        "fund_score": 45.0 + i * 1.3, "liquidity_score": 40.0 + i * 2.1,
        "news_score": 35.0 + i * 3.3, "sentiment_score": 30.0 + i * 2.7,
        "safety_score": 40.0 + i * 1.9,
        "rsi": 30.0 + i * 4.0, "perf_1m": 1.0 + i * 2.0,
        "perf_3m": 2.0 + i * 3.0, "roe": 8.0 + i * 1.6,
        "net_margin": 6.0 + i * 1.1, "de_ratio": 20.0 + i * 2.5,
        "pe": 8.0 + i * 1.4, "pb": 0.8 + i * 0.2, "eps": 2.0 + i * 0.5,
        "div_yield": 2.0 + i * 0.9, "mkt_cap": 5e9 + i * 1e9,
        "rel_volume": 0.8 + i * 0.1, "volume": 400000 + i * 50000,
        "vol_5": 390000 + i * 48000, "vol_60": 380000 + i * 46000,
        "beta": 0.5 + i * 0.12, "volatility": 15.0 + i * 1.7,
        "vol1y": 18.0 + i * 1.9, "mdd1y": -10.0 - i * 1.3,
        "cfo": 300.0 + i * 40.0, "ni": 200.0 + i * 30.0,
        "upside": 5.0 + i * 2.0, "fair_value": 25.0 + i * 6.0,
        "ts": "2026-11-17T10:00:00Z",
        "all_axes": {"technical": 40.0 + i * 2.0, "fundamental": 35.0 + i * 1.8,
                     "liquidity": 38.0 + i * 1.6, "risk": 36.0 + i * 2.2,
                     "news": 30.0 + i * 1.4, "sentiment": 28.0 + i * 1.2},
    }
    d.update(kw)
    return d


def _stocks(n=25):
    """قائمة أسهم — أكتر من 20 عشان حدّ الباقة يبان (5/20)."""
    return [_stock("S%02d" % i, i) for i in range(n)]


def _mk_user(uid, pin, dev, pro=False):
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(dev)
    rec = {
        "id": uid, "name": "r16w-" + uid, "email": uid + "@example.test",
        "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
        "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": 0,
        "bio_hash": dev_hash, "bio_hashes": [dev_hash],
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
    }
    if pro:
        rec["plan"] = "pro"
        rec["plan_until"] = int(time.time()) + 30 * 86400
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = rec
        up._save_users(users)


def _login(client, pin, dev):
    r = client.post("/api/auth/pin/login", json={"pin": pin, "device": dev},
                     headers={"X-Forwarded-For": "10.0.0.1"})
    body = r.get_json() or {}
    tok = body.get("token") or body.get("access_token")
    if not tok:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    return {"Authorization": "Bearer " + tok}


def _blob(body):
    return json.dumps(body, ensure_ascii=False, default=str)


def _all_keys(obj, acc=None):
    """كل مفاتيح الـJSON (متكرر) — عشان نفحص السرّية بنيويًا."""
    if acc is None:
        acc = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _all_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _all_keys(v, acc)
    return acc


def _find_key(obj, key):
    """أول قيمة لمفتاح معيّن في أي عمق (أو None)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            got = _find_key(v, key)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _find_key(v, key)
            if got is not None:
                return got
    return None


def _route_source(fn_name):
    """مصدر الكود لدالة معيّنة (فحص ساكن على الكود نفسه)."""
    text = SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return ast.get_source_segment(text, node) or ""
    return ""


def _engine_score(item, strategy, stocks):
    """نتيجة المحرّك مباشرة (مصدر الحقيقة للدرجة)."""
    return up.strategy_score(
        item, strategy,
        up.tech_score(item),
        up.fundamental_score(item, up.SECTOR_STATS),
        up.liquidity_score(item),
        up.sentiment_engine(item, stocks),
        up.portfolio_fit(item, up.PORTFOLIO))


# ⛔⛔⛔ سقف الدخول: 10 محاولات/دقيقة ⇒ الدخول مرّة واحدة لكل باقة
#    عند الإقلاع، والتوكن يُعاد استخدامه.
_TOKENS = {}


def _boot():
    if _TOKENS:
        return
    _mk_user(FREE_UID, FREE_PIN, FREE_DEV, pro=False)
    _mk_user(PRO_UID, PRO_PIN, PRO_DEV, pro=True)
    c = up.app.test_client()
    _TOKENS["free"] = _login(c, FREE_PIN, FREE_DEV)
    _TOKENS["pro"] = _login(c, PRO_PIN, PRO_DEV)


_boot()


class Round16Base(unittest.TestCase):
    """أساس مشترك: بيانات حيّة + محفظة + مستخدمين Free وPro."""

    @classmethod
    def setUpClass(cls):
        cls.payload = oe.build_payload(
            _stocks(), None,
            {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
             "market_phase": "open", "freshness": "fresh"})
        cls.old_portfolio = up.PORTFOLIO
        up.PORTFOLIO = {
            "holdings": {
                "H1": {"shares": 100, "price": 20.0, "sector": "banks"},
                "H2": {"shares": 80, "price": 30.0, "sector": "food"},
                "H3": {"shares": 60, "price": 25.0, "sector": "real estate"},
                "H4": {"shares": 50, "price": 40.0, "sector": "chemicals"},
                "H5": {"shares": 40, "price": 15.0, "sector": "retail"},
                "H6": {"shares": 30, "price": 35.0, "sector": "services"},
            },
            "cash": 0,
        }

    @classmethod
    def tearDownClass(cls):
        up.PORTFOLIO = cls.old_portfolio

    def setUp(self):
        self.old_egx = up.LIVE_DATA.get("egx30")
        self.old_opp = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["egx30"] = _stocks()
        up.LIVE_DATA["opp"] = self.payload
        self.client = up.app.test_client()
        self.free_h = _TOKENS["free"]
        self.pro_h = _TOKENS["pro"]

    def tearDown(self):
        up.LIVE_DATA["egx30"] = self.old_egx
        up.LIVE_DATA["opp"] = self.old_opp

    def _anon(self):
        """زائر: كوكي جديد من غير جلسة ⇒ مافيش توكن خالص."""
        return up.app.test_client()

    def _assert_no_recipe(self, body, where):
        """⛔ مافيش أي مفتاح وصفة في الرد (في أي عمق)."""
        keys = _all_keys(body) & RECIPE_KEYS
        self.assertFalse(keys, "%s ⇒ فيه مفاتيح وصفة: %s" % (where, sorted(keys)))
        blob = _blob(body)
        for needle in ("weights", "available_weight", "strategy_score"):
            self.assertNotIn(needle, blob, "%s ⇒ فيه '%s' في نص الرد" % (where, needle))


class TestAnonymousBlocked(Round16Base):
    """⛔ ① — 401 للزائر المجهول على كل المسارات (القديمة والجديدة)."""

    def test_anonymous_gets_401_on_legacy_strategies_list(self):
        """⛔ بيكشف: /api/strategies بيرجّع 200 لزائر ⇒ تسريب عام."""
        r = self._anon().get("/api/strategies")
        self.assertEqual(r.status_code, 401, "المسار القديم مفتوح للزائر")
        body = r.get_json() or {}
        self.assertIs(body.get("ok"), False)
        self._assert_no_recipe(body, "/api/strategies")

    def test_anonymous_gets_401_on_legacy_strategy_detail(self):
        """⛔ بيكشف: /api/strategy/<code>/<strategy> بيرجّع 200 لزائر."""
        c = self._anon()
        for path in LEGACY_PATHS[1:]:
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path + " مفتوح للزائر")
            body = r.get_json() or {}
            self.assertIs(body.get("ok"), False, path)
            self._assert_no_recipe(body, path)

    def test_anonymous_gets_401_on_every_strategy_path(self):
        """⛔ بيكشف: أي مسار استراتيجيات بيفتح على الزائر (قديم أو جديد)."""
        c = self._anon()
        for path in LEGACY_PATHS + NEW_PATHS + ENGINE_PATHS:
            r = c.get(path)
            self.assertIn(r.status_code, (401, 403), path + " مش محمي")
            self._assert_no_recipe(r.get_json() or {}, path)

    def test_anonymous_response_has_no_evaluation_internals(self):
        """⛔ بيكشف: رد الزائر فيه محاور/مجموع/خصم ⇒ استنتاج الوصفة."""
        c = self._anon()
        for path in LEGACY_PATHS:
            body = c.get(path).get_json() or {}
            leaked = EVAL_FIELDS & _all_keys(body)
            self.assertFalse(leaked, path + " ⇒ فيه: %s" % sorted(leaked))

    def test_forged_token_gets_401_on_legacy_paths(self):
        """⛔ بيكشف: توكن مزوّر يمرّ من فتحة الـauth."""
        c = self._anon()
        bad = {"Authorization": "Bearer forged.token"}
        for path in LEGACY_PATHS:
            r = c.get(path, headers=bad)
            self.assertEqual(r.status_code, 401, path + " قبل توكن مزوّر")
            self._assert_no_recipe(r.get_json() or {}, path)

    def test_route_guard_blocks_with_global_gate_on_and_off(self):
        """⛔ بيكشف: الاعتماد على البوابة العامة بس (بدون guard جوّه
        المسار) ⇒ لازم المسار نفسه يبقى محمي (دفاع في العمق) في
        الحالتين: البوابة مطفية (الافتراضي في الإنتاج) ومفعّلة."""
        for gate in (False, True):
            old = up.API_DENY_DEFAULT
            up.API_DENY_DEFAULT = gate
            try:
                c = self._anon()
                for path in LEGACY_PATHS:
                    r = c.get(path)
                    self.assertEqual(r.status_code, 401,
                                     path + " unguarded والبوابة العامة "
                                            + ("مفعّلة" if gate else "مطفية"))
                    body = r.get_json() or {}
                    if not gate:
                        # ⛔ البوابة العامة مطفية ⇒ اللي رجّع 401 هو
                        #    guard جوّه المسار نفسه (لازم يكون موجود).
                        self.assertEqual(body.get("code"), "auth_required", path)
            finally:
                up.API_DENY_DEFAULT = old

    def test_anonymous_gets_401_even_when_engine_is_down(self):
        """⛔ بيكشف: الأولوية غلط (503 بدل 401) ⇒ كشف حالة المحرّك."""
        up.LIVE_DATA["opp"] = None
        c = self._anon()
        for path in LEGACY_PATHS:
            self.assertEqual(c.get(path).status_code, 401, path)


class TestNoWeightsAnywhere(Round16Base):
    """⛔ ② (بند ٥) — مافيش أي مسار تاني بيرجّع الأوزان."""

    # ⛔ المسارات العامة اللي ممكن ترجّع بيانات محرّك (كلها GET)
    PUBLIC_PROBES = (
        "/api/health", "/api/prices", "/api/ticker", "/api/sector-stats",
        "/api/technical/S00", "/api/fundamental/S00", "/api/sentiment/S00",
        "/api/risk/S00", "/api/news/S00", "/api/explain/S00",
        "/api/opportunity/S00", "/api/opportunities", "/api/portfolio/fit/S00",
        "/api/strategies", "/api/strategy/S00/balanced",
        "/api/score-error", "/api/filters", "/api/calibration",
        "/api/indices", "/api/gold", "/api/gold/candles", "/api/gold/history",
        "/api/gold/local", "/api/gold/attribution", "/api/gold/gram",
        "/api/gold/technical", "/api/gold/scenarios", "/api/gold/factors",
        "/api/top-movers", "/api/heat", "/api/sector/banks",
        "/api/search/COMI", "/api/dividends", "/api/dividends/stats",
        "/api/ipo", "/api/obdepth/S00", "/api/tg-status", "/api/alerts/state",
        "/api/logos", "/api/candles/S00", "/api/quotes",
    )

    def test_no_public_route_returns_recipe_keys(self):
        """⛔ بيكشف: مسار عام بيرجّع مفتاح وصفة (weights/available_weight…)."""
        c = self._anon()
        for path in self.PUBLIC_PROBES:
            body = c.get(path).get_json() or {}
            keys = _all_keys(body) & RECIPE_KEYS
            self.assertFalse(keys, path + " ⇒ فيه مفاتيح وصفة: %s" % sorted(keys))

    def test_no_public_route_returns_the_weight_vectors(self):
        """⛔ بيكشف: المسار بيرجّع **قيمة** الأوزان (مش المفتاح بس) —
        يعني حد يقدر يبني نفس النظام."""
        c = self._anon()
        vectors = []
        for key, st in up.STRATEGIES.items():
            vectors.append(("STRATEGIES." + key, st["weights"]))
        vectors.append(("AXIS_WEIGHTS", dict(up.AXIS_WEIGHTS)))
        for path in self.PUBLIC_PROBES:
            blob = _blob(c.get(path).get_json() or {})
            for name, vec in vectors:
                for k, v in vec.items():
                    for probe in (("%s:%s=%s" % (name, k, v)),
                                  ('"%s": %s' % (k, v))):
                        if probe in blob:
                            self.fail("%s ⇒ فيه %s" % (path, probe))

    def test_legacy_route_source_has_no_weights_literal(self):
        """⛔ بيكشف: الكود نفسه بيبني مفتاح weights في الرد العام."""
        for fn in ("strategies_list", "strategy_api"):
            body = _route_source(fn)
            self.assertTrue(body, "مالقيناش الدالة " + fn)
            self.assertIn("require_user", body,
                          fn + " مفيهاش تحقق جلسة")
            self.assertNotIn('"weights"', body,
                             fn + " لسه بيبني مفتاح weights")

    def test_legacy_strategies_payload_has_no_weights_key(self):
        """⛔ بيكشف: قائمة الاستراتيجيات (بعد القفل) مفيش فيها weights."""
        body = self.client.get("/api/strategies",
                               headers=self.free_h).get_json() or {}
        for item in body.get("strategies") or []:
            self.assertNotIn("weights", item)
        self.assertNotIn("weights", _blob(body))


class TestRecipeNotRecoverable(Round16Base):
    """⛔ ③ — الأرقام اللي بتثبت إن الوصفة كانت بتتسرّب."""

    def test_base_is_a_linear_function_of_the_secret_weights(self):
        """⛔ بيكشف (بالرقم): «base» = مجموع المحاور مضروباً في الأوزان
        السرّية ⇒ لو الرد وصل للزائر ⇒ الأوزان بتتحدّد رياضياً."""
        weights = up.STRATEGIES["balanced"]["weights"]
        checked = 0
        for item in _stocks(6):
            res = _engine_score(item, "balanced", up.LIVE_DATA["egx30"])
            axes = res["axes"]
            expect = sum(float(axes[k]) * float(weights[k]) for k in AXIS_KEYS)
            self.assertAlmostEqual(
                float(res["base"]), expect, delta=0.15,
                msg="base مش مجموع مرجّح ⇒ المعادلة اتغيّرت")
            checked += 1
        self.assertGreaterEqual(checked, 5)

    def test_risk_penalty_multiplier_is_recoverable_from_exposed_fields(self):
        """⛔ بيكشف (بالرقم): risk_penalty + محور الأمان ⇒ معامل خصم
        المخاطرة (risk_penalty_mult) بتاع الاستراتيجية بيتقرأ من رد
        واحد ⇒ ده ثابت في وصفة المحرّك."""
        checked = 0
        for key, st in up.STRATEGIES.items():
            mult = float(st["risk_penalty_mult"])
            hit = False
            for item in _stocks(8):
                res = _engine_score(item, key, up.LIVE_DATA["egx30"])
                risk = res["axes"].get("risk")
                if risk is None:
                    continue
                rp = abs(float(res["risk_penalty"] or 0.0))
                lp = abs(float(res["liquidity_penalty"] or 0.0))
                # ⛔ السقف (22 نقطة) بيحجّم الخصم ⇒ في الحالة دي مش
                #    يتقارن بالمعامل. بنتخطاها (ومش بنتحقق منها).
                if abs((rp + lp) - 22.0) < 0.15:
                    continue
                denom = (100.0 - float(risk)) * 0.18
                if abs(denom) < 1e-9:
                    continue
                got = rp / denom
                self.assertAlmostEqual(got, mult, delta=0.03,
                                       msg="المعامل اتغيّر للاستراتيجية " + key)
                hit = True
                checked += 1
                break
            self.assertTrue(hit, "مافيش عيّنة بلا سقف للاستراتيجية " + key)
        self.assertGreaterEqual(checked, len(up.STRATEGIES))

    def test_liquidity_threshold_is_recoverable_from_exposed_fields(self):
        """⛔ بيكشف (بالرقم): محور السيولة + خصم الفلاتر ⇒ عتبة السيولة
        (min_liquidity) بتاع الاستراتيجية بتقرأ من رد واحد."""
        key = "swing"
        want = up.STRATEGIES[key]["min_liquidity"]
        found = False
        for item in _stocks(8):
            res = _engine_score(item, key, up.LIVE_DATA["egx30"])
            liq = res["axes"].get("liquidity")
            pen = abs(float(res["filter_penalty"] or 0.0))
            if liq is None or pen <= 0.0:
                continue
            got = float(liq) + 2.0 * pen
            self.assertAlmostEqual(got, float(want), delta=0.2,
                                   msg="العتبة اتغيّرت")
            found = True
            break
        self.assertTrue(found, "مالقيناش سهم بيقع تحت عتبة السيولة")

    def test_anonymous_cannot_recover_anything(self):
        """⛔ بيكشف: الزائر مالوش أي خامة (محاور/مجموع/خصم) ⇒ مستحيل
        يستنتج الوصفة."""
        c = self._anon()
        for path in LEGACY_PATHS:
            body = c.get(path).get_json() or {}
            self.assertFalse(EVAL_FIELDS & _all_keys(body), path)
            self.assertIsNone(_find_key(body, "axes"), path)
            self.assertIsNone(_find_key(body, "base"), path)

    def test_exposed_fields_are_not_in_the_sanitizer_allow_list(self):
        """⛔ بيكشف: الحقول دي كانت **بتعدّي** الفلتر بالاسم ⇒ الرد العام
        كان فعلاً بيحملها."""
        for name in ("axes", "base", "risk_penalty", "filter_penalty",
                     "confidence", "score"):
            self.assertNotIn(name, up._HIDDEN_KEYS_OUTPUT,
                             name + " كان بيتشال — يبقى الرد العام ماشي")


class TestPositivePath(Round16Base):
    """⛔ ④ — المستخدم المسجّل: نفس الدرجة، والبيانات المسموحة بس."""

    def test_logged_in_gets_same_score_as_the_engine(self):
        """⛔ بيكشف: القفل غيّر الدرجة أو خبّى نتيجة التقييم."""
        for path in ("/api/strategy/S00/balanced", "/api/strategy/S03/swing"):
            code = path.split("/")[3]
            strategy = path.split("/")[4]
            item = next(s for s in up.LIVE_DATA["egx30"] if s["code"] == code)
            want = _engine_score(item, strategy, up.LIVE_DATA["egx30"])
            r = self.client.get(path, headers=self.free_h)
            self.assertEqual(r.status_code, 200, path)
            got = (r.get_json() or {}).get("strategy") or {}
            self.assertEqual(got.get("score"), want.get("score"), path)
            self.assertEqual(got.get("axes"), want.get("axes"), path)
            self.assertEqual(got.get("base"), want.get("base"), path)
            self.assertEqual(got.get("risk_penalty"), want.get("risk_penalty"), path)
            self.assertEqual(got.get("filter_notes"), want.get("filter_notes"), path)
            self.assertEqual(got.get("confidence"), want.get("confidence"), path)

    def test_logged_in_still_gets_the_frontend_fields(self):
        """⛔ بيكشف: القفل خبّى حقول الواجهة (محاور/مجموع/خصم/ثقة)."""
        r = self.client.get("/api/strategy/S00/balanced", headers=self.free_h)
        got = (r.get_json() or {}).get("strategy") or {}
        for field in ("strategy_name", "timeframe", "focus", "score", "axes",
                      "base", "risk_penalty", "filters_passed",
                      "filter_notes", "confidence"):
            self.assertIn(field, got, "الحقل '" + field + "' اتشال من الرد")

    def test_logged_in_response_has_no_weights_at_any_depth(self):
        """⛔ بيكشف: الرد المسموح مافيش فيه أي أوزان (في أي عمق)."""
        r = self.client.get("/api/strategy/S00/balanced", headers=self.free_h)
        body = r.get_json() or {}
        self._assert_no_recipe(body, "/api/strategy (مسجّل)")
        blob = _blob(body)
        for key, st in up.STRATEGIES.items():
            for k, v in st["weights"].items():
                self.assertNotIn('"%s": %s' % (k, v), blob,
                                 "الوزن %s بتاع %s ظهر" % (k, key))

    def test_logged_in_strategies_list_keeps_what_the_frontend_reads(self):
        """⛔ بيكشف: القفل كسر لوحة الاستراتيجيات (الواجهة بتقرأ key+name)."""
        r = self.client.get("/api/strategies", headers=self.free_h)
        self.assertEqual(r.status_code, 200)
        items = (r.get_json() or {}).get("strategies") or []
        self.assertEqual(len(items), len(up.STRATEGIES))
        for item in items:
            for field in ("key", "name", "desc", "timeframe", "focus"):
                self.assertIn(field, item)
            self.assertNotIn("weights", item)

    def test_missing_axis_is_the_worst_not_redistributed(self):
        """⛔ بيكشف: «المحور الناقص = الأسوأ» اتغيّر (وزن المحور الناقص
        اتوزّع على الباقي) ⇒ الدرجة زادت غلط."""
        stocks = _stocks(3)
        full = _stocks(3)[0]
        broken = dict(stocks[1])
        broken["all_axes"] = {k: v for k, v in broken["all_axes"].items()
                              if k != "risk"}
        res_full = _engine_score(full, "balanced", stocks)
        res_broken = _engine_score(broken, "balanced", stocks)
        self.assertEqual(res_broken.get("score_status"), "insufficient_risk")
        self.assertIs(res_broken.get("rank_eligible"), False)
        self.assertIn("risk", res_broken.get("missing_axes") or [])
        self.assertLess(float(res_broken.get("score")),
                        float(res_full.get("score")),
                        "السهم الناقص مخاطرة لازم يكون أسوأ")

    def test_missing_axis_stock_is_not_eligible_in_the_response(self):
        """⛔ بيكشف: السهم الناقص مخاطرة اتقدّم للمستخدم كأنه مؤهّل."""
        up.LIVE_DATA["egx30"] = _stocks(3)
        broken = dict(up.LIVE_DATA["egx30"][1])
        broken["code"] = "SBROKEN"
        broken["all_axes"] = {k: v for k, v in broken["all_axes"].items()
                              if k != "risk"}
        up.LIVE_DATA["egx30"].append(broken)
        r = self.client.get("/api/strategy/SBROKEN/balanced",
                             headers=self.free_h)
        self.assertEqual(r.status_code, 200)
        got = (r.get_json() or {}).get("strategy") or {}
        item = next(s for s in up.LIVE_DATA["egx30"] if s["code"] == "SBROKEN")
        want = _engine_score(item, "balanced", up.LIVE_DATA["egx30"])
        self.assertEqual(got.get("score"), want.get("score"))

    def test_free_and_pro_limits_are_unchanged(self):
        """⛔ بيكشف: حدود الباقة (5/20) اتغيّرت في الجولة دي."""
        for headers, want in ((self.free_h, 5), (self.pro_h, 20)):
            r = self.client.get("/api/opp/list/swing", headers=headers)
            self.assertEqual(r.status_code, 200)
            body = r.get_json() or {}
            self.assertEqual(len(body.get("items") or []), want)
            self.assertEqual(body.get("limit_per_strategy"), want)

    def test_free_and_pro_share_the_same_scores(self):
        """⛔ بيكشف: الباقة غيّرت الدرجة أو الأهلية."""
        free = self.client.get("/api/opp/list/swing",
                               headers=self.free_h).get_json() or {}
        pro = self.client.get("/api/opp/list/swing",
                              headers=self.pro_h).get_json() or {}
        f_items = {i.get("code"): i for i in (free.get("items") or [])}
        p_items = {i.get("code"): i for i in (pro.get("items") or [])}
        self.assertTrue(f_items)
        for code, item in f_items.items():
            other = p_items.get(code)
            self.assertIsNotNone(other, "السهم " + code + " ناقص في Pro")
            self.assertEqual(item.get("score"), other.get("score"), code)
            self.assertEqual(item.get("eligible"), other.get("eligible"), code)


def _cleanup():
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    try:
        result = unittest.main(exit=False, verbosity=2).result
    finally:
        _cleanup()
    sys.exit(0 if result.wasSuccessful() else 1)
