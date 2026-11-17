#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🔇 مراجعة الجولة ١٧ — **Flask حقيقي + ربط Frontend/Backend**.

📌 المطلوب من المراجع:
   (١) اختبار Flask **الحقيقي** (مش stub).
   (٢) ربط Frontend/Backend: الرد الفعلي من الخادم + نفس توقعات الواجهة.

📌 الفكرة:
   · الخادم = بيئة الـstaging المعزولة (Flask حقيقي على 127.0.0.1:8099)
     ⇒ مافيش أي اتصال بالإنتاج.
   · الدخول = PIN حقيقي من `/api/auth/pin/login`.
   · المسارات = الخمسة `/api/opp/*` ⇒ لازم تنشر **نفس** حقول العقد.
   · الربط = نفس القواعد اللي الواجهة بتطبّقها (coverage_acceptable ·
     data_state · منع «live» من غير دليل · منع ادعاء «الآن»).
   · كمان: فحص مصدر الواجهة نفسه إن فيه تعامل مع الحقول الجديدة.

📌 التشغيل:
   python3 tools/staging/run_staging.py &        # الخادم (من جذر الريبو)
   python3 evidence/r17_integration_flask_binding.py
⛔ مافيش نشر · مافيش إنتاج · مافيش تكلفة.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

STAGE_URL = os.environ.get("STAGE_URL", "http://127.0.0.1:8099")
CFG = json.load(open("/workspace/.staging/staging-config.json", encoding="utf-8"))
FE_JS = os.environ.get(
    "OCTA_FRONTEND_JS",
    "/workspace/repos/octa/assets/js/octa-opps.js")
BE_DIR = os.environ.get("OCTA_BACKEND_DIR", os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

PASS = []
FAIL = []


def t(name, fn):
    try:
        fn()
        PASS.append(name)
        print("  ✅ " + name)
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print("  ❌ " + name + " — " + str(e))
    except Exception as e:  # noqa: BLE001
        FAIL.append((name, "EXC " + repr(e)))
        print("  ❌ " + name + " — EXC " + repr(e))


def _req(path, method="GET", body=None, headers=None):
    url = STAGE_URL + path
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"raw": raw[:200]}


print("=== ربط Frontend/Backend على Flask حقيقي · %s ===" % STAGE_URL)

# ── ① الدخول بـPIN حقيقي ──
st, body = _req("/api/auth/pin/login", "POST",
                 {"pin": CFG["pro"]["pin"], "device": CFG["pro"]["device"]},
                 {"X-Forwarded-For": "10.0.0.1",
                  "X-OCTA-Proxy": CFG["proxy_secret"]})
TOK = body.get("token") or body.get("access_token")
t("دخول Pro بـPIN (Flask حقيقي)", lambda: (_ for _ in ()).throw(
    AssertionError("فشل الدخول: %s" % json.dumps(body)[:160])) if not TOK else None)
if not TOK:
    print("RESULT: FAIL (مفيش جلسة)")
    sys.exit(1)
# ⛔ البوابة في الـstaging بتطلب هيدر الوسيط (زي ما اختبارات المستودع بتعمل)
PROXY_HDR = {"X-OCTA-Proxy": CFG["proxy_secret"]}
AUTH = {"Authorization": "Bearer " + TOK, "X-Forwarded-For": "10.0.0.2"}
AUTH.update(PROXY_HDR)

# ── ② المسارات الخمسة ──
st_strat, d_strat = _req("/api/opp/strategies", headers=AUTH)
st_list, d_list = _req("/api/opp/list/swing", headers=AUTH)
st_sum, d_sum = _req("/api/opp/summary", headers=AUTH)

CODE = ""
if d_list.get("items"):
    CODE = d_list["items"][0].get("code")
st_det, d_det = _req("/api/opp/detail/swing/%s" % CODE, headers=AUTH)
st_exp, d_exp = _req("/api/opp/explain/swing/%s" % CODE, headers=AUTH)

CONTRACT_FIELDS = ("coverage_status", "coverage_acceptable", "data_state",
                   "freshness_summary_ar", "current_session_date")
ROUTES = {
    "/api/opp/strategies": d_strat,
    "/api/opp/list/swing": d_list,
    "/api/opp/summary": d_sum,
    "/api/opp/detail/swing/<code>": d_det,
    "/api/opp/explain/swing/<code>": d_exp,
}


def _has_contract(d):
    missing = [f for f in CONTRACT_FIELDS if f not in d]
    assert not missing, "حقول ناقصة: %s" % missing


for name, d in ROUTES.items():
    t("العقد مكتمل في " + name, lambda d=d: _has_contract(d))

# ── ③ القيم الصريحة (R17-P3) محترمة في الرد ──
def _bool_values_ok(d):
    v = d.get("coverage_acceptable")
    assert v is None or isinstance(v, bool), \
        "coverage_acceptable لازم bool مش %r" % (v,)


for name, d in ROUTES.items():
    t("نوع coverage_acceptable صحيح في " + name,
      lambda d=d: _bool_values_ok(d))

# ── ④ منع صف «live» من غير دليل حداثة (R17-P1) ──
def _rows_live_honest(d):
    items = d.get("items") or []
    if not items:
        return
    ds = d.get("data_state")
    fresh = (d.get("freshness") or "")
    for it in items:
        if it.get("data_state") == "live":
            assert ds == "fresh" or fresh == "fresh", \
                "صف live والحداثة العامة %r/%r" % (ds, fresh)


for name in ("/api/opp/list/swing", "/api/opp/detail/swing/<code>"):
    t("مفيش صف «live» من غير دليل في " + name,
      lambda d=ROUTES[name]: _rows_live_honest(d))

# ── ⑤ الوصف الصادق: مفيش «سعر التداول الآن» لغير صف حيّ ──
def _label_honest(d):
    for it in (d.get("items") or []):
        if it.get("price_label") == "سعر التداول الآن":
            assert it.get("data_state") == "live", \
                "صف «الآن» مع data_state=%r" % it.get("data_state")


for name in ("/api/opp/list/swing", "/api/opp/detail/swing/<code>"):
    t("وصف «الآن» بس لصف حيّ في " + name,
      lambda d=ROUTES[name]: _label_honest(d))

# ── ⑥ مفيش تسريب أوزان (الراجعات القديمة) ──
def _no_weights(d):
    raw = json.dumps(d, ensure_ascii=False)
    assert '"weights"' not in raw, "الرد فيه أوزان"


for name, d in ROUTES.items():
    t("مفيش أوزان في " + name, lambda d=d: _no_weights(d))

# ── ⑦ ربط الواجهة: المصدر بيشتغل بالحقول الجديدة ──
try:
    src = open(FE_JS, encoding="utf-8").read()
except Exception as e:
    src = ""
    print("  ⚠️ مفيش مصدر الواجهة: %s" % e)


def _fe_handles_unknown():
    assert "data_state === 'unknown'" in src, \
        "الواجهة مش بتتعامل مع data_state=unknown"
    assert "SRC_UNKNOWN_STATE" in src, "ثابت وسم unknown مش موجود"


def _fe_handles_acceptable():
    assert "coverage_acceptable" in src, \
        "الواجهة مش بتقرا coverage_acceptable"


def _fe_has_contract_test():
    p = os.path.join(os.path.dirname(FE_JS), "..", "tests",
                     "opp-contract18.test.js")
    assert os.path.isfile(p), "اختبار العقد الجديد مش موجود"


t("الواجبة تتعامل مع حالة unknown", _fe_handles_unknown)
t("الواجهة تقرا coverage_acceptable", _fe_handles_acceptable)
t("اختبار عقد الواجهة الجديد موجود", _fe_has_contract_test)

# ── ⑧ الباك: اتساق التغطية (R17-P2) منشور في الرد ──
def _coverage_consistent_published():
    f = d_strat.get("data_freshness") or {}
    assert "coverage_consistent" in f, \
        "مافيش coverage_consistent في data_freshness"


t("حقل coverage_consistent منشور", _coverage_consistent_published)

print("")
print("نجح: %d · فاشل: %d" % (len(PASS), len(FAIL)))
for n, e in FAIL:
    print("  ❌ " + n + " — " + e[:200])
print("RESULT: " + ("PASS" if not FAIL else "FAIL"))
sys.exit(0 if not FAIL else 1)
