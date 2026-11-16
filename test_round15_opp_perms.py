#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ الجولة ١٥ — صلاحيات وسرّية مسارات /api/opp/* (Free/Pro).

📌 المطلوب (ملاحظة المالك على تقرير الجولة ١٤):
   ① كل مسارات /api/opp/* ترجّع الكود الصح:
      401 لما مافيش جلسة · 403/404 لما الباقة/الصلاحية مانعتش ·
      503 لما المحرّك الحي مش متاح (fail-closed) — ومفيش تسريب
      لبيانات الأوزان أو العتبات.
   ② فصل Free/Pro **على الخادم**: Free = أفضل ٥ لكل استراتيجية ·
      Pro = أفضل ٢٠ — بنفس الدرجة ونفس الأهلية (الفروق في العدد
      ومستوى التفاصيل فقط).
   ③ مسار التفسير/التفاصيل (detail · explain) بنفس الحماية.

📌 كل اختبار سالب: التعليق فوق كل واحد بيوضح «بيكشف إيه».
📌 التشغيل: python test_round15_opp_perms.py
⛔ العزل: بيانات مؤقتة · مافيش شبكة · مافيش نشر.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="octa_r15opp_")
sys.path.insert(0, HERE)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r15opp-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r15opp-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"

import opp_engine as oe  # noqa: E402
import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.TRACK_FILE = Path(TMP) / "track.json"

FREE_UID = "r15opp-free"
PRO_UID = "r15opp-pro"
FREE_PIN = "1122"
PRO_PIN = "3344"
FREE_DEV = "d" * 64
PRO_DEV = "e" * 64

# ⛔ السرّية: أسماء الحقول اللي ما بتترجعش في أي رد عام.
SECRET_KEYS = {"weight", "points_max", "min_coverage", "min_liquidity_value",
                "min_score", "threshold", "criteria_weight"}

# ⛔ كل مسارات /api/opp/* الموجودة في update_prices.py
ALL_PATHS = ("/api/opp/strategies",
             "/api/opp/summary",
             "/api/opp/list/swing",
             "/api/opp/detail/swing/S24",
             "/api/opp/explain/swing/S24")

# ⛔ كلمات لو ظهرت في نص السبب ⇒ معناها تفاصيل سرّية اتسرّبت
WORD_POINTS = "نقطة"
WORD_WEIGHT = "وزن"


def _stock(code, **kw):
    """سهم مؤهّل (مخاطرة + سيولة + تغطية كافية) — زي داتا الباك."""
    d = {
        "code": code, "name": "s-" + code, "sector": "industry",
        "price": 50.0, "change": 1.2, "technical_score": 72.0,
        "technical_signal": "up", "fund_score": 65.0, "liquidity_score": 70.0,
        "news_score": 55.0, "sentiment_score": 50.0, "safety_score": 64.0,
        "rsi": 52.0, "perf_1m": 6.0, "perf_3m": 14.0, "roe": 18.0,
        "net_margin": 12.0, "de_ratio": 35.0, "pe": 12.0, "pb": 1.4,
        "eps": 4.2, "div_yield": 6.0, "mkt_cap": 12e9, "rel_volume": 1.3,
        "volume": 900000, "vol_5": 880000, "vol_60": 850000, "beta": 0.9,
        "volatility": 28.0, "vol1y": 30.0, "mdd1y": -18.0, "cfo": 900.0,
        "ni": 700.0, "upside": 18.0, "fair_value": 59.0,
        "ts": "2026-11-17T10:00:00Z",
        "all_axes": {"technical": 72.0, "fundamental": 65.0,
                     "liquidity": 70.0, "risk": 66.0, "news": 55.0,
                     "sentiment": 50.0},
    }
    d.update(kw)
    return d


def _stocks(n=25):
    """نموذج فيه أكتر من 20 سهم مؤهّل ⇒ الحدّ بين Free وPro يبان."""
    out = []
    for i in range(n):
        out.append(_stock("S%02d" % i, all_axes={
            "technical": 70.0 + i, "fundamental": 60.0 + i,
            "liquidity": 65.0 + i, "risk": 60.0 + i, "news": 50.0 + i,
            "sentiment": 50.0 + i}))
    return out


def _mk_user(uid, pin, dev, pro=False):
    salt = up._pin_salt_new()
    dev_hash = up._device_key_hash(dev)
    rec = {
        "id": uid, "name": "r15opp-" + uid, "email": uid + "@example.test",
        "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
        "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": 0,
        "bio_hash": dev_hash, "bio_hashes": [dev_hash],
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
    }
    if pro:
        # ⛔ الباقة Pro من مصدر الحقيقة (plan_gate.plan_of)
        rec["plan"] = "pro"
        rec["plan_until"] = int(time.time()) + 30 * 86400
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = rec
        up._save_users(users)


def _login(client, pin, dev):
    """تسجيل دخول حقيقي (PIN + جهاز) ⇒ توكن جلسة."""
    r = client.post("/api/auth/pin/login", json={"pin": pin, "device": dev},
                    headers={"X-Forwarded-For": "10.0.0.1"})
    body = r.get_json() or {}
    tok = body.get("token") or body.get("access_token")
    if not tok:
        raise AssertionError("login failed: " + json.dumps(body)[:200])
    return {"Authorization": "Bearer " + tok}


def _blob(body):
    return json.dumps(body, ensure_ascii=False)


def _all_keys(obj, acc):
    """كل مفاتيح الـJSON (متكرر) — عشان نفحص السرّية بنيويًا."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _all_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _all_keys(v, acc)
    return acc


def _all_numbers(obj, acc):
    """كل الأرقام في الرد (متكرر)."""
    if isinstance(obj, dict):
        for v in obj.values():
            _all_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _all_numbers(v, acc)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        acc.add(float(obj))
    return acc


def _definitions():
    return oe.load_definitions()


# ⛔⛔⛔ سقف الدخول: 10 محاولات/دقيقة (update_prices.py:1193)
#    ⇒ الدخول مرّة واحدة لكل باقة عند الإقلاع، والتوكن يُعاد استخدامه.
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


class OppPermsBase(unittest.TestCase):
    """أساس مشترك: payload حيّ + مستخدمين Free وPro."""

    @classmethod
    def setUpClass(cls):
        cls.payload = oe.build_payload(
            _stocks(), None,
            {"generated_at": "2026-11-17T10:00:00Z", "source": "live",
             "market_phase": "open", "freshness": "fresh"})

    def setUp(self):
        self.old = up.LIVE_DATA.get("opp")
        up.LIVE_DATA["opp"] = self.payload
        # ⛔ كوكي فاضي كل اختبار ⇒ الاعتماد على ترويسة Authorization بس
        self.client = up.app.test_client()
        self.free_h = _TOKENS["free"]
        self.pro_h = _TOKENS["pro"]

    def tearDown(self):
        up.LIVE_DATA["opp"] = self.old

    def _anon(self):
        """زائر: كوكي جديد من غير جلسة ⇒ مافيش توكن خالص."""
        return up.app.test_client()

    def _assert_no_engine_data(self, body, where):
        """⛔ رد الخطأ ما فيهوش أي بيانات محرّك (لا قوائم ولا درجات)."""
        self.assertIsInstance(body, dict, where)
        self.assertNotIn("items", body, where)
        self.assertNotIn("lists", body, where)
        self.assertNotIn("score", body, where)
        self.assertNotIn("criteria", body, where)
        self.assertNotIn("S24", _blob(body), where)


class TestSessionGate(OppPermsBase):
    """⛔ ① — 401 لما مافيش جلسة (كل مسارات /api/opp/*)."""

    def test_anonymous_is_401_on_every_opp_path(self):
        """⛔ بيكشف: مسار /api/opp/* بيرجّع بيانات لزائر بلا جلسة."""
        c = self._anon()
        for path in ALL_PATHS:
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path + " مش محمي")
            body = r.get_json() or {}
            self.assertIs(body.get("ok"), False, path)
            self._assert_no_engine_data(body, path)

    def test_invalid_token_is_401_on_every_opp_path(self):
        """⛔ بيكشف: توكن مزوّر/منتهي يمرّ من فتحة الـauth."""
        c = self._anon()
        bad = {"Authorization": "Bearer forged.token"}
        for path in ALL_PATHS:
            r = c.get(path, headers=bad)
            self.assertEqual(r.status_code, 401, path + " قبل توكن مزوّر")
            self._assert_no_engine_data(r.get_json() or {}, path)

    def test_route_guard_blocks_even_if_global_gate_is_off(self):
        """⛔ بيكشف: الاعتماد على البوابة العامة بس (بدون guard جوّه
        المسار) ⇒ لازم المسار نفسه يبقى محمي (دفاع في العمق)."""
        old = up.API_DENY_DEFAULT
        up.API_DENY_DEFAULT = False
        try:
            c = self._anon()
            for path in ALL_PATHS:
                r = c.get(path)
                self.assertEqual(r.status_code, 401,
                                 path + " unguarded بدون البوابة العامة")
                body = r.get_json() or {}
                self.assertEqual(body.get("code"), "auth_required", path)
                self._assert_no_engine_data(body, path)
        finally:
            up.API_DENY_DEFAULT = old

    def test_401_body_does_not_leak_strategies_or_codes(self):
        """⛔ بيكشف: رد 401 بيرجّع أسماء استراتيجيات أو رموز أسهم."""
        c = self._anon()
        for path in ALL_PATHS:
            blob = _blob(c.get(path).get_json() or {})
            self.assertNotIn("strategies", blob, path)
            self.assertNotIn("swing", blob, path)
            self.assertNotIn("S24", blob, path)


class TestEngineUnavailable(OppPermsBase):
    """⛔ ① — 503 fail-closed لما الباك الحي مش متاح."""

    def test_missing_payload_is_503_on_every_opp_path(self):
        """⛔ بيكشف: المسار بيرجّع 200 ببيانات ناقصة/فاضية لما
        المحرّك الحي مش متاح (يفترض fail-closed)."""
        up.LIVE_DATA["opp"] = None
        for headers in (self.free_h, self.pro_h):
            for path in ALL_PATHS:
                r = self.client.get(path, headers=headers)
                self.assertEqual(r.status_code, 503, path + " مش fail-closed")
                body = r.get_json() or {}
                self.assertEqual(body.get("code"), "engine_loading", path)
                self._assert_no_engine_data(body, path)

    def test_corrupt_payload_is_503_not_200(self):
        """⛔ بيكشف: payload تالف (ok=False) بيتقدّم للمستخدم كأنه سليم."""
        up.LIVE_DATA["opp"] = {"ok": False, "lists": {}, "strategies": []}
        for path in ALL_PATHS:
            r = self.client.get(path, headers=self.free_h)
            self.assertEqual(r.status_code, 503, path + " قدّم payload تالف")
            self.assertEqual((r.get_json() or {}).get("code"),
                             "engine_loading", path)

    def test_empty_payload_is_503(self):
        """⛔ بيكشف: payload فاضي يتقدّم كـ«مفيش فرص» (200) بدل 503."""
        up.LIVE_DATA["opp"] = {}
        for path in ALL_PATHS:
            r = self.client.get(path, headers=self.free_h)
            self.assertEqual(r.status_code, 503, path + " قدّم payload فاضي")

    def test_anonymous_gets_401_even_when_engine_is_down(self):
        """⛔ بيكشف: الأولوية غلط (503 بدل 401) ⇒ كشف حالة الباك
        لزائر بلا جلسة."""
        up.LIVE_DATA["opp"] = None
        c = self._anon()
        for path in ALL_PATHS:
            r = c.get(path)
            self.assertEqual(r.status_code, 401, path + " كشف حالة المحرّك")

    def test_503_body_does_not_leak_last_payload(self):
        """⛔ بيكشف: رد 503 بيرجّع بيانات المحرّك القديمة."""
        up.LIVE_DATA["opp"] = None
        for path in ALL_PATHS:
            body = self.client.get(path, headers=self.free_h).get_json() or {}
            self.assertNotIn("S24", _blob(body), path)
            self.assertNotIn("items", body, path)


class TestSecretsNotLeaked(OppPermsBase):
    """⛔ ①/③ — الأوزان والعتبات ما بتترجعش في أي رد."""

    def _forbidden_keys(self):
        keys = set(SECRET_KEYS)
        for st in (_definitions().get("strategies") or []):
            for c in (st.get("criteria") or []):
                for k in c:
                    if k in ("weight", "points_max"):
                        keys.add(k)
            for k in ("min_coverage", "min_liquidity_value", "min_score"):
                if st.get(k) is not None:
                    keys.add(k)
        return keys

    def test_no_opp_response_exposes_weight_or_threshold_keys(self):
        """⛔ بيكشف: رجوع حقل «weight»/«points_max»/«min_coverage» في
        رد أي مسار /api/opp/* (مهما كان الباقة)."""
        forbidden = self._forbidden_keys()
        for headers in (self.free_h, self.pro_h):
            for path in ALL_PATHS:
                body = self.client.get(path, headers=headers).get_json() or {}
                keys = _all_keys(body, set())
                leaked = sorted(keys & forbidden)
                self.assertEqual(leaked, [], path + " سرّب: " + str(leaked))

    def test_no_opp_response_exposes_weight_or_threshold_values(self):
        """⛔ بيكشف: الأرقام الحقيقية للأوزان/العتبات (مش بس أسماء
        الحقول) ظهرت في الرد."""
        blob_free = _blob(self.client.get("/api/opp/list/swing",
                                          headers=self.free_h).get_json() or {})
        blob_pro = _blob(self.client.get("/api/opp/list/swing",
                                         headers=self.pro_h).get_json() or {})
        for st in (_definitions().get("strategies") or []):
            liq = st.get("min_liquidity_value")
            if liq:
                for blob in (blob_free, blob_pro):
                    self.assertNotIn(str(float(liq)), blob,
                                     "عتبة سيولة سرّبت: " + str(liq))
                    self.assertNotIn(str(int(liq)), blob,
                                     "عتبة سيولة سرّبت: " + str(int(liq)))

    def test_strategies_endpoint_hides_definition_secrets(self):
        """⛔ بيكشف: نسخة الاستراتيجية العامة فيها الأوزان/العتبات."""
        body = self.client.get("/api/opp/strategies",
                               headers=self.free_h).get_json() or {}
        for st in body.get("strategies") or []:
            for k in ("weight", "points_max", "min_coverage",
                      "min_liquidity_value"):
                self.assertNotIn(k, st, "حقل سرّي في الاستراتيجية")
            for cr in st.get("criteria") or []:
                self.assertEqual(
                    sorted(cr.keys()),
                    ["hint_ar", "key", "label_ar", "not_ar"],
                    "شكلCriterion العام اتغيّر: " + str(sorted(cr.keys())))

    def test_explain_returns_ratios_only(self):
        """⛔ بيكشف: التفسير بيرجّع نسب/نقاط بدل ما يرجّع نسب بس."""
        body = self.client.get("/api/opp/explain/swing/S24",
                               headers=self.pro_h).get_json() or {}
        for cr in body.get("criteria") or []:
            self.assertTrue(set(cr.keys()) <= {"key", "label_ar", "ratio",
                                               "note_ar"},
                            "حقل زائد في التفسير: " + str(sorted(cr.keys())))
            ratio = cr.get("ratio")
            if ratio is not None:
                self.assertGreaterEqual(float(ratio), 0.0)
                self.assertLessEqual(float(ratio), 1.0,
                                     "النسبة خارج 0..1 ⇒_points_max_ مرجّع")

    def test_detail_endpoint_hides_definition_secrets(self):
        """⛔ بيكشف: مسار التفاصيل بيرجّع الأوزان/العتبات."""
        for headers in (self.free_h, self.pro_h):
            body = self.client.get("/api/opp/detail/swing/S24",
                                   headers=headers).get_json() or {}
            keys = _all_keys(body, set())
            self.assertEqual(sorted(keys & self._forbidden_keys()), [],
                             "مسار التفاصيل سرّب")

    def test_reason_text_has_no_points_or_weights(self):
        """⛔ بيكشف: نص السبب بيرجّع «نقاط»/«وزن» (تفاصيل داخلية)."""
        for headers in (self.free_h, self.pro_h):
            body = self.client.get("/api/opp/list/swing",
                                   headers=headers).get_json() or {}
            for it in body.get("items") or []:
                for reason in it.get("reasons") or []:
                    self.assertNotIn(WORD_POINTS, reason,
                                     "السبب فيه نقاط: " + reason)
                    self.assertNotIn(WORD_WEIGHT, reason,
                                     "السبب فيه وزن: " + reason)

    def test_summary_endpoint_hides_definition_secrets(self):
        """⛔ بيكشف: الملخّص بيرجّع الأوزان/العتبات."""
        for headers in (self.free_h, self.pro_h):
            body = self.client.get("/api/opp/summary",
                                   headers=headers).get_json() or {}
            keys = _all_keys(body, set())
            self.assertEqual(sorted(keys & self._forbidden_keys()), [],
                             "الملخّص سرّب")


class TestFreeProSeparation(OppPermsBase):
    """⛔ ② — فصل Free/Pro مطبَّق على الخادم (مش الواجهة)."""

    def _list(self, headers, path="/api/opp/list/swing"):
        return self.client.get(path, headers=headers).get_json() or {}

    def test_free_gets_five_and_pro_gets_twenty(self):
        """⛔ بيكشف: الباك مش بيطبّق حد الباقة (Free مش ٥ / Pro مش ٢٠)."""
        free = self._list(self.free_h)
        pro = self._list(self.pro_h)
        self.assertEqual(len(free.get("items") or []), 5,
                         "Free مش محدود بـ5 على الخادم")
        self.assertEqual(len(pro.get("items") or []), 20,
                         "Pro مش محدود بـ20 على الخادم")
        self.assertEqual(free.get("plan"), "free")
        self.assertEqual(pro.get("plan"), "pro")
        self.assertEqual(free.get("limit_per_strategy"), 5)
        self.assertEqual(pro.get("limit_per_strategy"), 20)

    def test_summary_is_tiered_server_side(self):
        """⛔ بيكشف: الملخّص بيرجّع عدد كل استراتيجية من غير تطبيق
        حد الباقة على الخادم."""
        free = self.client.get("/api/opp/summary",
                               headers=self.free_h).get_json() or {}
        pro = self.client.get("/api/opp/summary",
                              headers=self.pro_h).get_json() or {}
        self.assertEqual(free.get("limit_per_strategy"), 5)
        self.assertEqual(pro.get("limit_per_strategy"), 20)
        fmap = {s["key"]: s.get("returned") for s in free.get("strategies") or []}
        pmap = {s["key"]: s.get("returned") for s in pro.get("strategies") or []}
        self.assertTrue(fmap, "الملخّص فاضي")
        for key, returned in fmap.items():
            self.assertEqual(returned, 5, key + ": Free مش 5")
            self.assertEqual(pmap.get(key), 20, key + ": Pro مش 20")

    def test_free_and_pro_share_same_scores_and_eligibility(self):
        """⛔ بيكشف: فرق الباقة مسّي الدرجة أو الأهلية (لازم العدد
        ومستوى التفاصيل بس)."""
        free = self._list(self.free_h)
        pro = self._list(self.pro_h)
        fmap = {i["code"]: i for i in (free.get("items") or [])}
        pmap = {i["code"]: i for i in (pro.get("items") or [])}
        self.assertTrue(fmap, "قائمة Free فاضية")
        self.assertEqual(len(pmap), 20)
        for code, item in fmap.items():
            self.assertIn(code, pmap, code + " مش موجود في Pro")
            other = pmap[code]
            self.assertEqual(item.get("score"), other.get("score"), code)
            self.assertEqual(item.get("coverage"), other.get("coverage"), code)
            self.assertEqual(item.get("eligible"), other.get("eligible"), code)
            self.assertEqual(item.get("grade_ar"), other.get("grade_ar"), code)
            self.assertEqual(item.get("risk_score"), other.get("risk_score"),
                             code)
        # ⛔ الأهلية (المؤهل/المستبعد) واحدة في الباقتين
        self.assertEqual((free.get("summary") or {}).get("eligible_total"),
                         (pro.get("summary") or {}).get("eligible_total"))
        self.assertEqual((free.get("summary") or {}).get("excluded_codes"),
                         (pro.get("summary") or {}).get("excluded_codes"))

    def test_client_cannot_widen_the_free_limit(self):
        """⛔ بيكشف: الحدّ متنفّذ في الواجهة بس (العميل يقدر يطلب
        limit كبير وياخد أكتر من 5)."""
        r = self.client.get("/api/opp/list/swing?limit=50&count=100&page=2",
                            headers=self.free_h)
        body = r.get_json() or {}
        self.assertEqual(len(body.get("items") or []), 5,
                         "العميل وسّع حد Free ⇒ الحدّ مش على الخادم")
        self.assertEqual(body.get("limit_per_strategy"), 5)

    def test_detail_beyond_free_limit_is_404_for_free_and_200_for_pro(self):
        """⛔ بيكشف: السهم رقم 6 (برّه حد Free) بيتفتح لـPro ومقفول
        على Free ⇒ حد الباقة مطبَّق على الخادم."""
        pro_codes = [i["code"] for i in (self._list(self.pro_h)
                                         .get("items") or [])]
        self.assertGreater(len(pro_codes), 5)
        sixth = pro_codes[5]
        r_free = self.client.get("/api/opp/detail/swing/" + sixth,
                                 headers=self.free_h)
        r_pro = self.client.get("/api/opp/detail/swing/" + sixth,
                                headers=self.pro_h)
        self.assertEqual(r_free.status_code, 404,
                         "Free فتح سهم برّه حدّه")
        self.assertEqual(r_pro.status_code, 200, "Pro ما فتحش السهم")
        self.assertEqual((r_pro.get_json() or {}).get("code"), sixth)

    def test_explain_beyond_free_limit_is_404_for_free_and_200_for_pro(self):
        """⛔ بيكشف: مسار التفسير بيتخطّى حد الباقة (Free يقرأ تفسير
        سهم برّه الـ5)."""
        pro_codes = [i["code"] for i in (self._list(self.pro_h)
                                         .get("items") or [])]
        sixth = pro_codes[5]
        r_free = self.client.get("/api/opp/explain/swing/" + sixth,
                                 headers=self.free_h)
        r_pro = self.client.get("/api/opp/explain/swing/" + sixth,
                                headers=self.pro_h)
        self.assertEqual(r_free.status_code, 404,
                         "Free قرا تفسير سهم برّه حدّه")
        self.assertEqual(r_pro.status_code, 200, "Pro ما قراش التفسير")
        self.assertTrue((r_pro.get_json() or {}).get("criteria"),
                        "تفسير Pro فاضي")

    def test_free_items_are_brief_and_pro_items_are_detailed(self):
        """⛔ بيكشف: الباقتين رجّعتا نفس التفصيل (إما الفارق في
        البيانات نفسها مش في مستوى التفاصيل)."""
        free_items = {i["code"]: i for i in (self._list(self.free_h)
                                             .get("items") or [])}
        pro_items = {i["code"]: i for i in (self._list(self.pro_h)
                                            .get("items") or [])}
        self.assertTrue(free_items)
        for code, item in free_items.items():
            self.assertNotIn("criteria", item,
                             code + ": Free لسه شايف التحليل التفصيلي")
            self.assertIn("criteria", pro_items[code],
                          code + ": Pro مفيش تحليل تفصيلي")
            self.assertEqual(item.get("score"), pro_items[code].get("score"))
            self.assertEqual(item.get("reasons"),
                             pro_items[code].get("reasons"))

    def test_tier_label_states_the_server_side_limit(self):
        """⛔ بيكشف: الرد ما بيقولش رقم الحدّ ⇒ المستخدم مش يعرف
        قد إيه اللي ناقصه (والحدّ مش ظاهر في العقد)."""
        for headers, want in ((self.free_h, "5"), (self.pro_h, "20")):
            for path in ("/api/opp/list/swing", "/api/opp/summary",
                         "/api/opp/strategies"):
                body = self.client.get(path, headers=headers).get_json() or {}
                label = str(body.get("limit_label_ar") or "")
                self.assertTrue(label, path + ": مافيش label للحدّ")
                self.assertIn(want, label,
                              path + ": label الحدّ غلط: " + label)


class TestPlanGate(OppPermsBase):
    """⛔ ① — بوابة الباقة (403/إخفاء) على مسارات /api/opp/*."""

    def test_free_plan_gets_no_403_on_any_opp_path_today(self):
        """⛔ بيكشف:Free اتمنع بـ403 في أي مسار (السياسة المعتمدة:
        الاستراتيجيات التسع كلها متاحة لكل مسجّل ⇒ مافيش فرع 403
        في الكود الحالي — لو اتضاف، الاختبار ده بيشتكي)."""
        for path in ALL_PATHS:
            r = self.client.get(path, headers=self.free_h)
            self.assertNotEqual(r.status_code, 403,
                                path + " رجّع 403 لـFree")

    def test_pro_only_strategy_is_hidden_from_free_server_side(self):
        """⛔ بيكشف: استراتيجية Pro-only ظهرت لقائمة Free ⇒ بوابة
        الباقة مش على الخادم."""
        old = oe.OPP_PRO_STRATEGIES
        oe.OPP_PRO_STRATEGIES = ("swing",)
        try:
            free_keys = [s.get("key") for s in
                         (self.client.get("/api/opp/strategies",
                                          headers=self.free_h).get_json()
                          or {}).get("strategies") or []]
            pro_keys = [s.get("key") for s in
                        (self.client.get("/api/opp/strategies",
                                         headers=self.pro_h).get_json()
                         or {}).get("strategies") or []]
        finally:
            oe.OPP_PRO_STRATEGIES = old
        self.assertNotIn("swing", free_keys, "Free شاف استراتيجية Pro")
        self.assertIn("swing", pro_keys, "Pro ما شافش استراتيجيته")

    def test_pro_only_flag_is_not_enforced_on_data_routes_today(self):
        """⛔ بيكشف (فجوة معروفة): البوابة مطبَّقة على
        /api/opp/strategies بس — مسارات البيانات (list/detail/explain)
        مش بتفحص pro_only ⇒ لو اتفعّل pro_only، Free يفضل يقرأ
        بيانات الاستراتيجية دي. الاختبار بيسجّل السلوك الحالي."""
        old = oe.OPP_PRO_STRATEGIES
        oe.OPP_PRO_STRATEGIES = ("swing",)
        try:
            r = self.client.get("/api/opp/list/swing", headers=self.free_h)
        finally:
            oe.OPP_PRO_STRATEGIES = old
        self.assertEqual(r.status_code, 200,
                         "سلوك البيانات اتغيّر — حدّث العقد")

    def test_pro_only_strategy_metadata_is_not_leaked_to_free(self):
        """⛔ بيكشف: بيانات الاستراتيجية (تعريفها/معاييرها) بتتسرب
        لـFree حتى لو_strategy_ نفسها مخفية."""
        old = oe.OPP_PRO_STRATEGIES
        oe.OPP_PRO_STRATEGIES = ("swing",)
        try:
            body = self.client.get("/api/opp/strategies",
                                   headers=self.free_h).get_json() or {}
        finally:
            oe.OPP_PRO_STRATEGIES = old
        for st in body.get("strategies") or []:
            self.assertNotEqual(st.get("key"), "swing",
                                "بيانات استراتيجية Pro وصلت لـFree")


class TestDetailExplainContract(OppPermsBase):
    """⛔ ③ — مسار التفسير/التفاصيل: نفس الحماية + اتساق."""

    def test_unknown_strategy_and_unknown_code_are_404(self):
        """⛔ بيكشف: مسار غلط بيرجّع 200 ببيانات تانية."""
        h = self.free_h
        self.assertEqual(self.client.get("/api/opp/list/nope",
                                         headers=h).status_code, 404)
        self.assertEqual(self.client.get("/api/opp/detail/nope/S24",
                                         headers=h).status_code, 404)
        self.assertEqual(self.client.get("/api/opp/explain/nope/S24",
                                         headers=h).status_code, 404)
        self.assertEqual(self.client.get("/api/opp/detail/swing/ZZZ",
                                         headers=h).status_code, 404)
        self.assertEqual(self.client.get("/api/opp/explain/swing/ZZZ",
                                         headers=h).status_code, 404)

    def test_detail_matches_list_item_for_both_plans(self):
        """⛔ بيكشف: التفاصيل رجّعت بيانات مختلفة عن القائمة."""
        for headers in (self.free_h, self.pro_h):
            lst = (self.client.get("/api/opp/list/swing",
                                   headers=headers).get_json() or {})
            items = {i["code"]: i for i in (lst.get("items") or [])}
            code = sorted(items)[0]
            body = (self.client.get("/api/opp/detail/swing/" + code,
                                    headers=headers).get_json() or {})
            item = body.get("item") or {}
            self.assertEqual(item.get("code"), code)
            self.assertEqual(item.get("score"), items[code].get("score"))
            self.assertEqual(item.get("eligible"), items[code].get("eligible"))

    def test_error_responses_do_not_leak_payload(self):
        """⛔ بيكشف: رد 404 بيرجّع درجات/قوائم من رد آخر."""
        h = self.free_h
        for path in ("/api/opp/detail/swing/ZZZ", "/api/opp/list/nope",
                     "/api/opp/explain/swing/ZZZ"):
            body = self.client.get(path, headers=h).get_json() or {}
            self._assert_no_engine_data(body, path)

    def test_detail_and_explain_are_protected_for_both_plans(self):
        """⛔ بيكشف: مسار التفاصيل/التففسير مفتوح على باقة معيّنة."""
        for headers in (self.free_h, self.pro_h):
            for path in ("/api/opp/detail/swing/S24",
                         "/api/opp/explain/swing/S24"):
                r = self.client.get(path, headers=headers)
                self.assertEqual(r.status_code, 200, path)
                body = r.get_json() or {}
                self.assertIs(body.get("ok"), True, path)
                self.assertEqual(body.get("plan"),
                                 "pro" if headers is self.pro_h else "free",
                                 path)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
