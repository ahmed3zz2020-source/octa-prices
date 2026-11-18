#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
valuation_audit.py — تدقيق مستقل لحساب التقييم (P/E · P/B · PEG) في محرك OCTA

الهدف: نعيد حساب P/E و P/B و PEG **بشكل مستقل** (من الدلالات الموثّقة، مش بنسخ
كود المحرك) ونقارنها بمخرجات المحرك نفسها على بيانات تجريبية واقعية، ونفحص
الحالات الحدّية (EPS ≤ 0 · PE ≤ 0 · حقوق ملكية ≤ 0 · عدد أسهم ≤ 0 · نمو ≤ 0).

⛔ **مفيش أي تعديل على كود المحرك** — Audit فقط. أي عيب لازم يتبلّغ عنه
   (file:line · المُدخل · المتوقع vs الفعلي · إعادة إنتاج).
⛔ **مفيش كتابة خارج /tmp** — كل التخزين بيروح لمجلد مؤقت.
⛔ مفيش أي استدعاء شبكي · مفيش أي معاملة مالية.

نمط التشغيل (نفس نمط test_r20_az31_36.py):
   import _stub_env; fl_mod, _ = _stub_env.install()
   import update_prices as up
   up.app.dispatch(path, method=_DOTS, body=_DOTS, headers=_DOTS)   +   up._HITS.clear()

شغّله:  python3 tools/valuation_audit.py
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r22_valuation_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)      # _stub_env lives in the repo root (like the other harnesses)

# ⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع ولا في /app
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

import update_prices as up  # noqa: E402
import octa_score  # noqa: E402
from pathlib import Path  # noqa: E402

# ── كل مسارات التخزين على TMP ──
up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.OTP_FILE = Path(TMP) / "otp.json"
up.PIN_CHAL_FILE = Path(TMP) / "pinchal.json"
up.SIGNUP_FILE = Path(TMP) / "signup.json"
up.TRACK_FILE = Path(TMP) / "track.json"
up.CACHE_FILE = Path(TMP) / "cache.json"
up.BT_FILE = Path(TMP) / "backtest_snapshots.json"
up.CHARTS_FILE = Path(TMP) / "charts.json"

RESULTS = []        # (ok, label, detail)
DEFECTS = []        # structured defect reports


# ══════════════════════════════════════════════════════════════════════
#  أدوات التقرير
# ══════════════════════════════════════════════════════════════════════

def check(cond, label, detail="", defect=None):
    ok = bool(cond)
    RESULTS.append((ok, label, detail))
    print(("  PASS  " if ok else "  FAIL  ") + label + (("   -- " + str(detail)) if detail and not ok else ""))
    if not ok and defect:
        DEFECTS.append(defect)
    return ok


def section(title):
    print("")
    print("─" * 78)
    print("  " + title)
    print("─" * 78)


def num(v, default=None):
    try:
        if v is None:
            return default
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


# ══════════════════════════════════════════════════════════════════════
#  1) التنفيذ المستقل (من الدلالات الموثّقة — مش بنسخ من المحرك)
# ══════════════════════════════════════════════════════════════════════
#  P/E = السعر ÷ ربحية السهم    → معرّف بسعر > 0 وربحية > 0 فقط
#  P/B = السعر ÷ (حقوق الملكية ÷ عدد الأسهم)  → معرّف بسعر > 0 وحقوق > 0 وأسهم > 0 فقط
#  PEG = P/E ÷ (نمو الأرباح %)   → معرّف بـ P/E > 0 ونمو > 0 فقط
#  أي قيمة خارج الشروط ⇒ None (مش 0 ولا inf ولا رقم مخترع)

def independent_pe(price, eps):
    """P/E implied by (price, eps)."""
    p, e = num(price), num(eps)
    if p is None or e is None:
        return None
    if not (p > 0 and e > 0):
        return None
    return p / e


def independent_bvps(equity, shares):
    """Book value per share = equity / shares."""
    q, n = num(equity), num(shares)
    if q is None or n is None:
        return None
    if not (q > 0 and n > 0):
        return None
    return q / n


def independent_pb(price, equity, shares):
    """P/B implied by (price, book value per share)."""
    p = num(price)
    bv = independent_bvps(equity, shares)
    if p is None or bv is None:
        return None
    if not p > 0:
        return None
    return p / bv


def independent_peg(pe, growth_pct):
    """PEG = PE / growth% — only when both exist and growth is positive."""
    p, g = num(pe), num(growth_pct)
    if p is None or g is None:
        return None
    if not (p > 0 and g > 0):
        return None
    return p / g


# ══════════════════════════════════════════════════════════════════════
#  2) البيانات التجريبية (FIXTURE) — قيم معلنة صراحة
# ══════════════════════════════════════════════════════════════════════
#  كل الأرقام دي **متختلقة**lake本页 — بتتعلن هنا علشان كل رقم في التقرير
#  يكون مرجوع لمصدره. مافيش أي رقم جاي من بيانات حقيقية.

SECTOR = "الخدمات المالية"          # قطاع FIXTURE

PEERS = {                              # وسائط القطاع (بوابة المحرك)
    SECTOR: {
        "count": 12, "with_pe": 12,
        "median_pe": 20.0, "median_pb": 1.5, "median_roe": 15.0,
        "pe_range": [8.0, 40.0],
        "median_volatility": 30.0, "median_mdd1y": 28.0, "median_sharpe3y": 0.8,
    }
}

BASE_ITEM = {
    "code": "FIXT", "name": "Synthetic Fixture Co", "sector": SECTOR,
    # ── الأرقام الأساسية المستخدمة في الفحص ──
    "price": 120.0,              # السعر (ج.م)
    "eps": 6.0,                  # ربحية السهم ⇒ P/E implied = 120/6 = 20.0
    "equity": 3_600_000_000.0,   # حقوق الملكية (ج.م) ⇒ BVPS = 3.6e9/30e6 = 120.0
    "shares": 30_000_000.0,      # عدد الأسهم ⇒ P/B implied = 120/120 = 1.0
    "pe": 20.0,                  # المضاعف كما يستهلكه المحرك
    "pb": 1.0,
    "roe": 18.0, "net_margin": 12.0, "de_ratio": 0.45, "beta": 1.1,
    "volatility": 28.0, "revenue": 4_500_000_000.0, "div_yield": 5.0,
    "mkt_cap": 3_600_000_000.0,
    "volume": 1_250_000, "vol_5": 1_100_000, "vol_60": 1_000_000,
    "rel_volume": 1.25, "atr": 4.8,
    "rsi": 55.0, "rsi_prev": 51.0,
    "ema20": 112.0, "ema50": 105.0, "ema200": 95.0, "sma50": 106.0,
    "macd": 1.2, "macd_signal": 0.9, "stoch_k": 60.0, "stoch_d": 55.0,
    "high_1m": 130.0, "low_1m": 100.0,
    "perf_w": 2.0, "perf_1m": 6.0, "perf_3m": 12.0, "perf_y": 22.0,
    "change": 1.5, "tv_all": 0.2, "news_score": 55.0,
    "vol1y": 30.0, "mdd1y": 25.0, "sharpe3y": 0.9,
    "data_confidence": 80,
    "revenue_growth": 9.0, "ni_growth": 7.0,     # نمو الأرباح المستخدم في PEG
}

PE_GRID = [4.0, 8.0, 12.0, 18.0, 25.0, 35.0, 60.0]           # كلهم > 0
PB_GRID = [0.3, 0.6, 0.9, 1.2, 1.8, 3.0]                     # كلهم > 0
NON_POSITIVE_PE = [0.0, -5.0, -12.5]
NON_POSITIVE_EPS = [0.0, -1.0, -6.0]


def item_with(**over):
    it = dict(BASE_ITEM)
    it.update(over)
    return it


def fundamental(item, peers=None):
    """ نداء محرك الأساسيات — ما بيبلعش الاستثناء (عشان الفحص يكمل ويبلّغ)."""
    try:
        return up.fundamental_score(item, peers if peers is not None else PEERS), None
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


def fund_ok(item, peers=None):
    """ نفس fundamental بس بترجع النتيجة بس (لو.Exception — None)."""
    return fundamental(item, peers)[0]


VALUE_AXIS_KEY = "\u0627\u0644\u0642\u064a\u0645\u0629"      # "القيمة"


def value_axis(fund):
    """ محور «القيمة» من تكسر محرك الأساسيات (هو اللي فيه نقاط P/E و P/B)."""
    bd = (fund or {}).get("breakdown") or {}
    if VALUE_AXIS_KEY in bd:
        return bd[VALUE_AXIS_KEY]
    for k in bd:
        if "\u0627\u0644\u0642\u064a\u0645\u0629" in k:
            return bd[k]
    raise AssertionError("value axis key not found in breakdown: %r" % list(bd))


def nz5_item_score(rec, axis_id, key):
    """ درجة مؤشر واحد داخل محرك «نور» (nz5_score)."""
    sc = up.nz5_score(rec)
    for ax in sc.get("axes", []):
        if ax.get("id") == axis_id:
            for it in ax.get("items", []):
                if it.get("key") == key:
                    return it.get("score")
    return None


# ══════════════════════════════════════════════════════════════════════
#  3.5) نداء المسارات — نمط المستودع نفسه (test_round17_n3_contract.py)
#  ⛔ الستب (_stub_env.Flask.dispatch) بيطابق المسار بالنص الحرفي بس،
#     فالمسارات اللي فيها متغيّرات (<code>) مش بتوصل له.
#     بنستخدم نفس مطابقة المسارات الموجودة في المستودع (_stub_match).
# ══════════════════════════════════════════════════════════════════════

def _stub_match(rules, path):
    """مطابقة مسار فيه متغيّرات — نفس دالة test_round17_n3_contract.py:160."""
    parts = [p for p in str(path).split("/") if p]
    for rule in rules:
        if rule.path == path:
            return rule, {}
        tparts = [p for p in rule.path.split("/") if p]
        if len(tparts) != len(parts):
            continue
        params, good = {}, True
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
    """رد Flask (tuple أو Resp) ⇒ Resp واحد."""
    resp_cls = fl_mod.jsonify.__globals__["Resp"]
    if isinstance(out, tuple):
        body = out[0] if out else resp_cls({})
        status = out[1] if len(out) > 1 else 200
        out = resp_cls(body.get_json() if isinstance(body, resp_cls) else body, status)
    if not isinstance(out, resp_cls):
        out = resp_cls(out)
    return out


def api_get(path, headers=None):
    """GET على مسار ⇒ (كود الحالة، رد JSON) — منطق الـdispatch نفسه."""
    req = fl_mod.request
    req.reset()
    req.path = path
    req.method = "GET"
    req.headers = dict(headers or {})
    req.args = {}
    up._HITS.clear()
    for fn in up.app.before_reqs:
        early = fn()
        if early is not None:
            resp = _stub_norm(early)
            body = resp.get_json() if hasattr(resp, "get_json") else resp
            return int(getattr(resp, "status_code", 200) or 200), body
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
    body = resp.get_json() if hasattr(resp, "get_json") else resp
    if not isinstance(body, dict):
        body = {"body": body}
    return int(getattr(resp, "status_code", 200) or 200), body


# ══════════════════════════════════════════════════════════════════════
#  4) الفحوصات
# ══════════════════════════════════════════════════════════════════════

print("=" * 78)
print("  OCTA ROUND 22 — VALUATION MATH AUDIT  (P/E · P/B · PEG)")
print("=" * 78)
print("  repo / branch : %s @ %s" % (REPO, subprocess.run(
    ["git", "-C", REPO, "branch", "--show-current"], capture_output=True, text=True).stdout.strip()))
print("  commit        : %s" % subprocess.run(
    ["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip())
print("  temp storage  : %s" % TMP)
print("  python        : %s" % sys.version.split()[0])
print("")
print("  ── FIXTURE (synthetic, fully declared) ──")
print("  sector                : %s" % SECTOR)
print("  price                 : %s" % BASE_ITEM["price"])
print("  eps                   : %s" % BASE_ITEM["eps"])
print("  equity (EGP)          : %s" % BASE_ITEM["equity"])
print("  shares                : %s" % BASE_ITEM["shares"])
print("  pe field              : %s" % BASE_ITEM["pe"])
print("  pb field              : %s" % BASE_ITEM["pb"])
print("  roe / net_margin / de : %s / %s / %s" % (BASE_ITEM["roe"], BASE_ITEM["net_margin"], BASE_ITEM["de_ratio"]))
print("  ni_growth (%%)         : %s" % BASE_ITEM["ni_growth"])
print("  sector median_pe/pb   : %s / %s" % (PEERS[SECTOR]["median_pe"], PEERS[SECTOR]["median_pb"]))
print("  implied PE = price/eps              = %s" % independent_pe(BASE_ITEM["price"], BASE_ITEM["eps"]))
print("  implied BVPS = equity/shares        = %s" % independent_bvps(BASE_ITEM["equity"], BASE_ITEM["shares"]))
print("  implied PB  = price/BVPS            = %s" % independent_pb(BASE_ITEM["price"], BASE_ITEM["equity"], BASE_ITEM["shares"]))
print("  implied PEG = PE / ni_growth(%%)      = %s" % independent_peg(BASE_ITEM["pe"], BASE_ITEM["ni_growth"]))
print("  PE grid : %s" % PE_GRID)
print("  PB grid : %s" % PB_GRID)

# ──────────────────────────────────────────────────────────────────────
section("GROUP 1 — P/E implied by (price, eps)")

check(independent_pe(BASE_ITEM["price"], BASE_ITEM["eps"]) == BASE_ITEM["pe"],
      "PE-01 · independent P/E (price/eps) equals the engine's P/E input",
      "%s != %s" % (independent_pe(BASE_ITEM["price"], BASE_ITEM["eps"]), BASE_ITEM["pe"]))

pe_values, pe_scores, pe_totals = [], [], []
for pe in PE_GRID:
    it = item_with(pe=pe, eps=round(BASE_ITEM["price"] / pe, 6))
    f = fund_ok(it)
    pe_values.append(pe)
    pe_scores.append(value_axis(f))
    pe_totals.append(f.get("score"))
print("     PE grid -> value axis : %s" % list(zip(pe_values, pe_scores)))
check(all(pe_scores[i] >= pe_scores[i + 1] for i in range(len(pe_scores) - 1)),
      "PE-02 · fundamental_score value axis is MONOTONIC NON-INCREASING in P/E",
      list(zip(pe_values, pe_scores)))
check(all(pe_totals[i] >= pe_totals[i + 1] for i in range(len(pe_totals) - 1)),
      "PE-03 · fundamental_score total is MONOTONIC NON-INCREASING in P/E",
      list(zip(pe_values, pe_totals)))

base_no_pe = value_axis(fund_ok(item_with(pe=None)))
for pe in NON_POSITIVE_PE:
    got = value_axis(fund_ok(item_with(pe=pe)))
    check(got == base_no_pe,
          "PE-04 · pe=%s contributes NO P/E points (same as pe missing) "
          "[value axis %s == %s]" % (pe, got, base_no_pe),
          "value axis %s != %s (missing pe)" % (got, base_no_pe))

for eps in NON_POSITIVE_EPS:
    for pe in (0.0, -5.0):
        it = item_with(pe=pe, eps=eps)
        f, err = fundamental(it)
        check(err is None,
              "PE-05 · eps=%s pe=%s does not crash" % (eps, pe), err)
        if f is None:
            continue
        methods = (f or {}).get("fair_value_methods") or {}
        leaked = [k for k in methods if "\u0631\u0628\u062d\u064a\u0629" in k]   # مضاعف الربحية
        check(not leaked,
              "PE-05 · eps=%s pe=%s -> no P/E-based fair value published" % (eps, pe),
              "published methods: %s" % list(methods))

nz5_pe_scores = []
for pe in PE_GRID:
    nz5_pe_scores.append(nz5_item_score(item_with(pe=pe), "val", "pe"))
print("     PE grid -> nz5 'val' P/E sub-score : %s" % list(zip(PE_GRID, nz5_pe_scores)))
check(all(nz5_pe_scores[i] >= nz5_pe_scores[i + 1] for i in range(len(nz5_pe_scores) - 1)),
      "PE-06 · nz5 'val' P/E sub-score is MONOTONIC NON-INCREASING in P/E (pe > 0)",
      list(zip(PE_GRID, nz5_pe_scores)))

worst_pe_band = nz5_item_score(item_with(pe=1000.0), "val", "pe")
for pe in NON_POSITIVE_PE:
    got = nz5_item_score(item_with(pe=pe), "val", "pe")
    check(got is None or got <= worst_pe_band,
          "PE-07 · nz5 'val' P/E sub-score for pe=%s is missing or the WORST band "
          "(<= %s) — a loss-maker must not score as 'cheapest'" % (pe, worst_pe_band),
          "sub-score %s (worst band %s)" % (got, worst_pe_band),
          defect={
              "id": "F-1",
              "title": "nz5 valuation axis gives a LOSING company the TOP P/E band",
              "file_line": "update_prices.py:6870-6871 (P/E band table) and "
                           "update_prices.py:6890-6892 (_nz_pos), consumed at "
                           "update_prices.py:6947 (_nz_band)",
              "input": "item with pe=%s (loss-making), all other fields = fixture" % pe,
              "expected": "P/E sub-score <= %s (worst band) or missing (None)" % worst_pe_band,
              "actual": "P/E sub-score = %s (best possible band)" % got,
              "why": "_nz_pos() documents '0 أو السالب = أسوأ درجة' but floors "
                     "negative P/E to 0.0; the P/E band table's first bucket is "
                     "(5, 95) = best, and validate_value() explicitly allows "
                     "negative P/E (update_prices.py:10157 'P/E السالب = شركة خسرانة').",
              "repro": "import os, sys, tempfile\n"
                       "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                       "os.environ['OCTAD_DEV'] = '1'\n"
                       "sys.path.insert(0, %r)\n"
                       "import _stub_env; _stub_env.install()\n"
                       "import update_prices as up\n"
                       "rec = {'code': 'FIXT', 'price': 120.0, 'pe': %s, 'pb': 1.0}\n"
                       "sc = up.nz5_score(rec)\n"
                       "print([i for i in sc['axes'] if i['id'] == 'val'][0]['items'][0])"
                       % (REPO, pe),
          })

conf_bad = (fund_ok(item_with(pe="N/A")) or {}).get("breakdown") or {}
conf_missing = (fund_ok(item_with(pe=None)) or {}).get("breakdown") or {}
conf_key = [k for k in conf_bad if "\u0627\u0643\u062a\u0645\u0627\u0644" in k]
conf_val = conf_bad.get(conf_key[0]) if conf_key else None
conf_val_missing = conf_missing.get(conf_key[0]) if conf_key else None
check(conf_val == conf_val_missing,
      "PE-08 · a NON-NUMERIC pe is not counted as available data in the "
      "completeness axis (same as pe missing)",
      "completeness with pe='N/A' = %s vs pe missing = %s" % (conf_val, conf_val_missing),
      defect={
          "id": "F-4",
          "title": "data-completeness axis counts a non-numeric P/E as present",
          "file_line": "update_prices.py:7651-7652 (avail counter in fundamental_score)",
          "input": "item with pe='N/A' (non-numeric string), all other fields = fixture",
          "expected": "completeness axis == the value for pe missing (%s)" % conf_val_missing,
          "actual": "completeness axis = %s" % conf_val,
          "why": "avail counts `item.get(k) is not None` — a string that _f() cannot "
                 "parse still counts as 'data present', inflating the confidence axis.",
          "repro": "import os, sys, tempfile\n"
                   "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                   "os.environ['OCTAD_DEV'] = '1'\n"
                   "sys.path.insert(0, %r)\n"
                   "import _stub_env; _stub_env.install()\n"
                   "import update_prices as up\n"
                   "peers = {%r: {'median_pe': 20.0, 'median_pb': 1.5, 'median_roe': 15.0}}\n"
                   "it = {'code': 'FIXT', 'price': 120.0, 'pe': 'N/A', 'pb': 1.0,\n"
                   "      'roe': 18.0, 'net_margin': 12.0, 'de_ratio': 0.45,\n"
                   "      'eps': 6.0, 'revenue': 4.5e9}\n"
                   "print(up.fundamental_score(it, peers)['breakdown'])" % (REPO, SECTOR),
      })

# ──────────────────────────────────────────────────────────────────────
section("GROUP 2 — P/B implied by (price, equity / shares)")

check(independent_pb(BASE_ITEM["price"], BASE_ITEM["equity"], BASE_ITEM["shares"]) == BASE_ITEM["pb"],
      "PB-01 · independent P/B (price / BVPS) equals the engine's P/B input",
      "%s != %s" % (independent_pb(BASE_ITEM["price"], BASE_ITEM["equity"], BASE_ITEM["shares"]),
                    BASE_ITEM["pb"]))

pb_values, pb_scores, pb_equity = [], [], []
for pb in PB_GRID:
    equity = BASE_ITEM["price"] * BASE_ITEM["shares"] / pb     # implied by the target P/B
    bvps = independent_bvps(equity, BASE_ITEM["shares"])
    it = item_with(pb=pb, equity=equity)
    f = fund_ok(it)
    pb_values.append(pb)
    pb_scores.append(value_axis(f))
    pb_equity.append(equity)
    print("     pb=%.2f -> equity=%.1f  bvps=%.4f  value axis=%s"
          % (pb, equity, bvps, value_axis(f)))
check(all(pb_scores[i] >= pb_scores[i + 1] for i in range(len(pb_scores) - 1)),
      "PB-02 · fundamental_score value axis is MONOTONIC NON-INCREASING in P/B (pb > 0)",
      list(zip(pb_values, pb_scores)))

# حقوق ملكية ≤ 0 ⇒ الـP/B غير معرَّف ⇒ ما فيش رقم P/B يُمرَّر للمحرك
equity_zero = 0.0
equity_neg = -600_000_000.0
check(independent_pb(BASE_ITEM["price"], equity_zero, BASE_ITEM["shares"]) is None,
      "PB-03a · equity <= 0 ⇒ independent P/B is None (no invented multiple)",
      independent_pb(BASE_ITEM["price"], equity_zero, BASE_ITEM["shares"]))
check(independent_pb(BASE_ITEM["price"], equity_neg, BASE_ITEM["shares"]) is None,
      "PB-03b · equity < 0 ⇒ independent P/B is None (no invented multiple)",
      independent_pb(BASE_ITEM["price"], equity_neg, BASE_ITEM["shares"]))
check(independent_pb(BASE_ITEM["price"], BASE_ITEM["equity"], 0.0) is None,
      "PB-03c · shares <= 0 ⇒ independent P/B is None (no invented multiple)",
      independent_pb(BASE_ITEM["price"], BASE_ITEM["equity"], 0.0))

base_no_pb = value_axis(fund_ok(item_with(pb=None)))
it_no_pb = item_with(pb=None, equity=equity_neg)
f_no_pb = fund_ok(it_no_pb)
pos_msgs = [p for p in ((f_no_pb or {}).get("positives") or []) if "\u0627\u0644\u0643\u062a\u0627\u0628" in p]
check(not pos_msgs,
      "PB-03d · equity <= 0 (no P/B in the item) ⇒ no 'cheap on book' message",
      "positives: %s" % pos_msgs)

# ── pb = 0 ⇒ المحرك بيحسب fair value فـ (px / B) ⇒ قسمة على صفر ⇒ كراش ──
f_zero, err_zero = fundamental(item_with(pb=0.0, equity=equity_zero))
check(err_zero is None,
      "PB-04a · pb = 0.0 (kept by the pipeline for a non-positive book value) "
      "⇒ fundamental_score does NOT crash",
      err_zero,
      defect={
          "id": "F-3",
          "title": "fundamental_score CRASHES (ZeroDivisionError) when P/B is 0",
          "file_line": "update_prices.py:7701 (fair-value P/B method: `(px / B) * ppb * adj`)",
          "input": "item with pb=0.0, pe=20.0, eps=6.0, price=120.0 "
                   "(sector median_pb=1.5) — pb = 0.0 is inside the pipeline bounds "
                   "(update_prices.py:10158 keeps pb in [0, 200])",
          "expected": "fundamental_score returns a result (P/B of a non-positive book "
                      "value must be ignored, not divided by)",
          "actual": "%s — the whole call dies, so /api/fundamental/<code> answers 500 "
                    "for that stock" % err_zero,
          "why": "the fair-value branch divides by B (the P/B multiple) without "
                 "checking B > 0; a company with zero/negative equity reaches the "
                 "engine with pb = 0.0 and takes the whole fundamental endpoint down.",
          "repro": "import os, sys, tempfile\n"
                   "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                   "os.environ['OCTAD_DEV'] = '1'\n"
                   "sys.path.insert(0, %r)\n"
                   "import _stub_env; _stub_env.install()\n"
                   "import update_prices as up\n"
                   "peers = {%r: {'median_pe': 20.0, 'median_pb': 1.5, 'median_roe': 15.0}}\n"
                   "it = {'code': 'FIXT', 'price': 120.0, 'pe': 20.0, 'pb': 0.0,\n"
                   "      'eps': 6.0, 'roe': 18.0, 'net_margin': 12.0,\n"
                   "      'de_ratio': 0.45, 'revenue': 4.5e9}\n"
                   "print(up.fundamental_score(it, peers))" % (REPO, SECTOR),
      })

# ── pb < 0 ⇒ المحور بيدي أعلى نقاط P/B (8/8) ويقول «رخيص على الكتاب» ──
for pb in (-2.0,):
    got = value_axis(fund_ok(item_with(pb=pb)))
    check(got == base_no_pb,
          "PB-04b · pb = %s (negative book value) ⇒ NO P/B points awarded "
          "(value axis %s == %s)" % (pb, got, base_no_pb),
          "value axis %s != %s (P/B missing) — the MAXIMUM P/B points were awarded "
          "for a NEGATIVE book value" % (got, base_no_pb),
          defect={
              "id": "F-5",
              "title": "fundamental_score awards the MAXIMUM P/B points to a "
                       "NEGATIVE book value and calls it 'cheap on book'",
              "file_line": "update_prices.py:7628-7633 (P/B branch of the value axis)",
              "input": "item with pb=%s, pe=20.0, price=120.0 (sector median_pb=1.5)" % pb,
              "expected": "value axis == %s (same as P/B missing ⇒ no P/B points, "
                          "no valuation message)" % base_no_pb,
              "actual": "value axis = %s (+8 P/B points and a 'cheap on book' positive)"
                        % got,
              "why": "ratio = B/ppb is computed without checking B > 0, so a negative "
                     "book value lands in the cheapest bucket (ratio < 0.6) and is "
                     "published as a positive signal ('رخيص على الكتاب').",
              "repro": "import os, sys, tempfile\n"
                       "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                       "os.environ['OCTAD_DEV'] = '1'\n"
                       "sys.path.insert(0, %r)\n"
                       "import _stub_env; _stub_env.install()\n"
                       "import update_prices as up\n"
                       "peers = {%r: {'median_pe': 20.0, 'median_pb': 1.5, 'median_roe': 15.0}}\n"
                       "it = {'code': 'FIXT', 'price': 120.0, 'pe': 20.0, 'pb': %s,\n"
                       "      'eps': 6.0, 'roe': 18.0, 'net_margin': 12.0,\n"
                       "      'de_ratio': 0.45, 'revenue': 4.5e9}\n"
                       "f = up.fundamental_score(it, peers)\n"
                       "print(f['breakdown'], f['positives'])" % (REPO, SECTOR, pb),
          })

for shares in (0.0, -1.0):
    it = item_with(pb=None, equity=BASE_ITEM["equity"], shares=shares)
    f, err = fundamental(it)
    check(err is None,
          "PB-05 · shares=%s does not crash" % shares, err)
    if f is None:
        continue
    check(value_axis(f) == base_no_pb,
          "PB-05 · shares=%s ⇒ no P/B points and no crash" % shares,
          "value axis %s != %s" % (value_axis(f), base_no_pb))

worst_pb_band = nz5_item_score(item_with(pb=1000.0), "val", "pb")
for pb in (0.0, -2.0):
    got = nz5_item_score(item_with(pb=pb), "val", "pb")
    check(got is None or got <= worst_pb_band,
          "PB-06 · nz5 'val' P/B sub-score for pb=%s is missing or the WORST band "
          "(<= %s)" % (pb, worst_pb_band),
          "sub-score %s (worst band %s)" % (got, worst_pb_band),
          defect={
              "id": "F-2",
              "title": "nz5 valuation axis gives a non-positive book value the TOP P/B band",
              "file_line": "update_prices.py:6872-6873 (P/B band table) and "
                           "update_prices.py:6890-6892 (_nz_pos), consumed at "
                           "update_prices.py:6947 (_nz_band)",
              "input": "item with pb=%s, all other fields = fixture" % pb,
              "expected": "P/B sub-score <= %s (worst band) or missing (None)" % worst_pb_band,
              "actual": "P/B sub-score = %s (best possible band)" % got,
              "why": "same _nz_pos() floor as F-1: pb <= 0 becomes 0.0 and the P/B "
                     "band table's first bucket is (0.5, 95) = best. pb = 0.0 is "
                     "inside the pipeline bounds (update_prices.py:10158), so it is "
                     "reachable for a company with negative equity.",
              "repro": "import os, sys, tempfile\n"
                       "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                       "os.environ['OCTAD_DEV'] = '1'\n"
                       "sys.path.insert(0, %r)\n"
                       "import _stub_env; _stub_env.install()\n"
                       "import update_prices as up\n"
                       "rec = {'code': 'FIXT', 'price': 120.0, 'pe': 20.0, 'pb': %s}\n"
                       "sc = up.nz5_score(rec)\n"
                       "print([i for i in sc['axes'] if i['id'] == 'val'][0]['items'][1])"
                       % (REPO, pb),
          })

# ──────────────────────────────────────────────────────────────────────
section("GROUP 3 — PEG = P/E / earnings growth %")

check(abs(independent_peg(20.0, 7.0) - 20.0 / 7.0) < 1e-12,
      "PEG-01 · independent PEG = PE / growth%% (20 / 7)",
      independent_peg(20.0, 7.0))
check(independent_peg(20.0, None) is None,
      "PEG-02 · missing growth ⇒ PEG is None (not 0, not inf)",
      independent_peg(20.0, None))
check(independent_peg(20.0, 0.0) is None,
      "PEG-03 · growth = 0 ⇒ PEG is None (no ZeroDivisionError, not inf)",
      independent_peg(20.0, 0.0))
check(independent_peg(20.0, -5.0) is None,
      "PEG-04 · growth < 0 ⇒ PEG is None (a shrinking company has no PEG)",
      independent_peg(20.0, -5.0))
check(independent_peg(-5.0, 10.0) is None and independent_peg(0.0, 10.0) is None,
      "PEG-05 · P/E <= 0 ⇒ PEG is None",
      (independent_peg(-5.0, 10.0), independent_peg(0.0, 10.0)))

# هل المحرك بينشر PEG من الأساس؟ (ولو نشر ⇒ لازم ما يكونش رقم مخترع)
peg_keys = []
def _scan(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "peg" in str(k).lower():
                peg_keys.append(path + "." + str(k))
            _scan(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan(v, path + "[%d]" % i)

fund_base = fund_ok(BASE_ITEM)
tech_base = octa_score.tech_score(BASE_ITEM)
liq_base = octa_score.liquidity_score(BASE_ITEM)
fin_base = octa_score.final_score(BASE_ITEM, tech_base, fund_base, liq_base, PEERS)
nz5_base = up.nz5_score(BASE_ITEM)
for obj in (fund_base, tech_base, liq_base, fin_base, nz5_base):
    _scan(obj)

git_grep = subprocess.run(["git", "-C", REPO, "grep", "-i", "-n", "peg", "--", "*.py", "*.json"],
                          capture_output=True, text=True)
tracked_peg_hits = [l for l in (git_grep.stdout or "").splitlines() if l.strip()]
all_peg = subprocess.run(["grep", "-ric", "peg", "--include=*.py", "--include=*.json", REPO],
                         capture_output=True, text=True).stdout.strip()
untracked_peg_files = [l.split(":")[0] for l in all_peg.splitlines()
                       if l.rsplit(":", 1)[-1] not in ("0", "") and "valuation_audit.py" not in l]

check(not peg_keys,
      "PEG-06 · no engine output publishes a PEG key (no invented PEG anywhere)",
      peg_keys)
check(not tracked_peg_hits,
      "PEG-07 · the tracked backend contains NO PEG computation at all "
      "(git grep -i 'peg' over tracked *.py/*.json = %d hits)" % len(tracked_peg_hits),
      tracked_peg_hits[:5])
check(not untracked_peg_files,
      "PEG-08 · no non-tracked source file (other than this audit tool) contains a "
      "PEG computation", untracked_peg_files)
print("     note: the only 'peg' occurrences in the tree are in this audit file "
      "(%s) and in the fixture label 'PEG-0x' — the engines never compute one."
      % os.path.basename(os.path.abspath(__file__)))

# ──────────────────────────────────────────────────────────────────────
section("GROUP 4 — engine integration (in-process, via the app dispatcher)")

up.SECTOR_STATS = PEERS
up.LIVE_DATA = dict(up.LIVE_DATA)
up.LIVE_DATA["egx30"] = [dict(BASE_ITEM)]
status, api_body = api_get("/api/fundamental/FIXT", headers={"X-Forwarded-For": "10.9.0.9"})
api_fund = api_body.get("fundamental") or {}
check(status == 200 and api_fund.get("score") == fund_base.get("score"),
      "ENG-01 · /api/fundamental/<code> returns the same fundamental score as the "
      "in-process call",
      "api=%s in-process=%s (status %s)" % (api_fund.get("score"), fund_base.get("score"),
                                            status))

tech = octa_score.tech_score(BASE_ITEM)
liq = octa_score.liquidity_score(BASE_ITEM)
fin_missing = octa_score.final_score(BASE_ITEM, tech, None, liq, PEERS)
fin_zero = octa_score.final_score(BASE_ITEM, tech, {"score": 0}, liq, PEERS)
check(fin_missing.get("final_score") is not None
      and fin_missing["final_score"] > fin_zero["final_score"],
      "ENG-02 · a MISSING fundamental axis is not turned into 0 "
      "(missing=%s > explicit 0=%s)" % (fin_missing.get("final_score"),
                                        fin_zero.get("final_score")),
      (fin_missing.get("final_score"), fin_zero.get("final_score")))

adj = fin_base.get("adjustments") or {}
base_adj = adj.get("\u0623\u0633\u0627\u0633\u064a \u0645\u0631\u062c\u0651\u062d")
pen = 0.0
for k, v in adj.items():
    if k != "\u0623\u0633\u0627\u0633\u064a \u0645\u0631\u062c\u0651\u062d":
        pen += float(v)
check(abs((base_adj + pen) - fin_base.get("final_score")) <= 0.11,
      "ENG-03 · published final score is consistent with its own adjustments "
      "(base+adjustments == final)",
      "%s + %s != %s" % (base_adj, pen, fin_base.get("final_score")))

check(octa_score.final_score({}, None, None, None, PEERS) is None,
      "ENG-04 · final_score on an empty item returns None (no invented number)",
      octa_score.final_score({}, None, None, None, PEERS))

# ── نفس الكراش بس على مستوى الـHTTP (السهم اللي P/B = 0) ──
up.LIVE_DATA["egx30"] = [item_with(pb=0.0, equity=0.0)]
status_pb0, body_pb0 = api_get("/api/fundamental/FIXT", headers={"X-Forwarded-For": "10.9.0.10"})
check(status_pb0 == 200,
      "ENG-05 · /api/fundamental/<code> does NOT 500 for a stock with P/B = 0",
      "HTTP %s — body: %s" % (status_pb0, body_pb0),
      defect={
          "id": "F-3",
          "title": "fundamental_score CRASHES (ZeroDivisionError) when P/B is 0 "
                   "→ the fundamental endpoint answers 500 for that stock",
          "file_line": "update_prices.py:7701 (fair-value P/B method: `(px / B) * ppb * adj`); "
                       "reached from update_prices.py:11317 (the /api/fundamental route)",
          "input": "GET /api/fundamental/FIXT with the stock carrying pb=0.0 "
                   "(sector median_pb=1.5, price=120.0)",
          "expected": "HTTP 200 with the fundamental breakdown",
          "actual": "HTTP %s — %s" % (status_pb0, body_pb0),
          "why": "the fair-value branch divides by B (the P/B multiple) with no B > 0 "
                 "guard; pb = 0.0 is inside the pipeline bounds "
                 "(update_prices.py:10158 keeps pb in [0, 200]) so a company with "
                 "zero/negative equity reaches the engine and takes the endpoint down.",
          "repro": "import os, sys, tempfile\n"
                   "TMP = tempfile.mkdtemp(dir='/tmp'); os.environ['OCTA_DATA_DIR'] = TMP\n"
                   "os.environ['OCTAD_DEV'] = '1'\n"
                   "sys.path.insert(0, %r)\n"
                   "import _stub_env; _stub_env.install()\n"
                   "import update_prices as up\n"
                   "up.LIVE_DATA['egx30'] = [{'code': 'FIXT', 'price': 120.0, 'pe': 20.0,\n"
                   "    'pb': 0.0, 'eps': 6.0, 'roe': 18.0, 'net_margin': 12.0,\n"
                   "    'de_ratio': 0.45, 'revenue': 4.5e9}]\n"
                   "up.SECTOR_STATS = {%r: {'median_pe': 20.0, 'median_pb': 1.5,\n"
                   "                          'median_roe': 15.0}}\n"
                   "up._HITS.clear()\n"
                   "r = up.app.dispatch('/api/fundamental/FIXT', method='GET',\n"
                   "                    headers={'X-Forwarded-For': '10.9.0.10'})\n"
                   "print(r.status_code, r.get_json())" % (REPO, SECTOR),
      })
up.LIVE_DATA["egx30"] = [dict(BASE_ITEM)]

# ──────────────────────────────────────────────────────────────────────
section("GROUP 5 — strategy weights: sum to 1.0 + immutability vs edc49cd")

BASELINE = "edc49cd"


def strategies_block(src_text):
    """ يستخرج كتلة STRATEGIES = { _DOTS } من نص المصدر كما هي (بايت ببايت)."""
    start = src_text.index("STRATEGIES = {")
    i = src_text.index("{", start)
    depth, in_str, quote = 0, False, ""
    for j in range(i, len(src_text)):
        ch = src_text[j]
        if in_str:
            if ch == quote and src_text[j - 1] != "\\":
                in_str = False
            continue
        if ch in "\"'":
            in_str, quote = True, ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src_text[i:j + 1]
    raise AssertionError("unbalanced STRATEGIES block")


for key in sorted(up.STRATEGIES):
    w = up.STRATEGIES[key]["weights"]
    total = sum(w.values())
    check(abs(total - 1.0) <= 1e-9,
          "W-01 · strategy '%s' weights sum to 1.0" % key,
          "sum=%r weights=%r" % (total, w))

base_src = subprocess.run(["git", "-C", REPO, "show", "%s:update_prices.py" % BASELINE],
                           capture_output=True, text=True, check=True).stdout
cur_src = open(os.path.join(REPO, "update_prices.py"), encoding="utf-8").read()
base_block = strategies_block(base_src)
cur_block = strategies_block(cur_src)

import hashlib  # noqa: E402
base_sha = hashlib.sha256(base_block.encode("utf-8")).hexdigest()
cur_sha = hashlib.sha256(cur_block.encode("utf-8")).hexdigest()
print("")
print("  ── weight-vector comparison: working tree vs %s ──" % BASELINE)
print("  %-14s %-42s %s" % ("strategy", "baseline %s" % BASELINE, "working tree"))
base_ast = ast.parse(base_src)
base_strat = None
for node in base_ast.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "STRATEGIES":
                base_strat = ast.literal_eval(node.value)
if base_strat is None:
    check(False, "W-02 · baseline %s contains a STRATEGIES literal" % BASELINE)
else:
    for key in sorted(base_strat):
        bw = base_strat[key]["weights"]
        cw = up.STRATEGIES.get(key, {}).get("weights", {})
        same = bw == cw
        print("  %-14s %-42s %s" % (key, json.dumps(bw, sort_keys=True),
                                    json.dumps(cw, sort_keys=True)))
        check(same, "W-02 · strategy '%s' weight vector is identical to %s" % (key, BASELINE),
              "baseline=%r current=%r" % (bw, cw))

print("")
print("  baseline STRATEGIES block sha256 : %s" % base_sha)
print("  working  STRATEGIES block sha256 : %s" % cur_sha)
check(base_block == cur_block,
      "W-03 · STRATEGIES block is BYTE-IDENTICAL to %s" % BASELINE,
      "baseline sha=%s current sha=%s" % (base_sha, cur_sha))
check(base_sha == cur_sha,
      "W-04 · STRATEGIES block sha256 matches the %s baseline" % BASELINE,
      "%s != %s" % (base_sha, cur_sha))

axis_total = sum(octa_score.AXIS_WEIGHTS.values())
check(abs(axis_total - 1.0) <= 1e-9,
      "W-05 · octa_score.AXIS_WEIGHTS sum to 1.0",
      "%r -> %r" % (octa_score.AXIS_WEIGHTS, axis_total))

# ──────────────────────────────────────────────────────────────────────
section("DEFECTS FOUND (engine code NOT modified)")

groups = {}
for d in DEFECTS:
    groups.setdefault(d["id"], []).append(d)

if not groups:
    print("  none")
for did in sorted(groups):
    items = groups[did]
    print("")
    print("  [%s] %s   (%d reproducing input%s)"
          % (did, items[0]["title"], len(items), "" if len(items) == 1 else "s"))
    print("      file:line : %s" % items[0]["file_line"])
    print("      why       : %s" % items[0]["why"])
    for n, d in enumerate(items, start=1):
        print("")
        print("      --- reproduction %d/%d ---" % (n, len(items)))
        print("      input     : %s" % d["input"])
        print("      expected  : %s" % d["expected"])
        print("      actual    : %s" % d["actual"])
        print("      repro     :")
        for ln in d["repro"].splitlines():
            print("        " + ln)

# ──────────────────────────────────────────────────────────────────────
passed = sum(1 for ok, _, _ in RESULTS if ok)
total = len(RESULTS)
print("")
print("=" * 78)
print("  RESULT: %d/%d checks passed   ·   %d distinct defect(s) across %d failing check(s)"
      % (passed, total, len(groups), total - passed))
print("  (a failed check is a REPORTED DEFECT — the engine code was NOT modified)")
print("=" * 78)
for ok, label, _d in RESULTS:
    if not ok:
        print("  FAILED: " + label)

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if passed == total else 1)
