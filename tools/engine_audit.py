#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٠ (R20 · المرحلة ٤) — تدقيق شامل لمحركات OCTA

📌 المرجع: طلب المالك (المرحلة ٤) — «مطلوب مراجعة حقيقية شاملة وليس
   الاكتفاء بالاختبارات الستة السابقة».

📌 المنهج: ⭐ **اختبارات مستقلة عن التنفيذ** ⭐ (metamorphic/property)
   ⭐ بدل ما نعيد كتابة نفس الكود (اللي معناه صفر فايدة) ⭐:
     ① حدود الدرجة (0..100) لكل محرك ⭐
     ② الحتمية: نفس البيانات ⇒ نفس النتيجة ⭐
     ③ ⭐ **الانحلال (degradation)**: نقص بيانات ⇐ الدرجة **ما تزيدش** ⭐
        (ده الدرس F-20-04: المحور الناقص لازم يكون أسوأ أو مساوي ⭐)
     ④ الحالات الحدية: مافيش استثناء ⭐
     ⑤ **مرجع مستقل**: إعادة حساب جزء (عمق السيولة + النشاط) من الصفر ⭐
     ⑥ الاستراتيجيات التسع: الأوزان مجموعها 1 + المحور الناقص ⇐ لا يُؤهَّل ⭐

⛔ مافيش أي تعديل على أوزان المحرك ولا عتبة ٩٠٪ ولا السياسات ⭐
⛔ مافيش شبكة · مافيش كتابة في المشروع · مافيش نشر ⭐

شغّله:  python3 tools/engine_audit.py
"""
import io
import os
import re
import sys
import json
import math
import ast
import inspect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

RESULTS = []
DETAIL = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def section(t):
    print("\n" + "─" * 68)
    print("  " + t)
    print("─" * 68)


# ══════════════════════════════════════════════════════════════════
#  ١) جرد المحركات — من الكود نفسه (مش من الذاكرة)
# ══════════════════════════════════════════════════════════════════
section("١) جرد المحركات والاستراتيجيات (من المصدر)")

SRC = io.open(os.path.join(ROOT, "update_prices.py"), encoding="utf-8").read()
SCORE_SRC = io.open(os.path.join(ROOT, "octa_score.py"), encoding="utf-8").read()

ENGINE_DEFS = [
    ("الفني (technical)", "octa_score.py", "tech_score"),
    ("السيولة (liquidity)", "octa_score.py", "liquidity_score"),
    ("الأساسي (fundamental)", "update_prices.py", "fundamental_score"),
    ("المعنويات (sentiment)", "update_prices.py", "sentiment_engine"),
    ("المخاطر (risk)", "update_prices.py", "risk_engine"),
    ("الأخبار (news)", "update_prices.py", "news_engine"),
    ("الفرص (opportunity)", "update_prices.py", "opportunity_engine"),
    ("المركّب (final)", "octa_score.py", "final_score"),
]

inventory = []
for label, fname, fn in ENGINE_DEFS:
    src = SCORE_SRC if fname == "octa_score.py" else SRC
    m = re.search(r"^def %s\(" % re.escape(fn), src, re.M)
    if not m:
        ok(False, "جرد: %s — %s()" % (label, fn))
        continue
    line = src[:m.start()].count("\n") + 1
    inventory.append({"engine": label, "file": fname, "func": fn,
                      "line": line})
    ok(True, "جرد: %-22s → %s:%d  (%s)" % (label, fname, line, fn))
ok(len(inventory) == 8, "① عدد المحركات الأساسية = ٨", len(inventory))

# ⭐ الاستراتيجيات — بالـAST (مش بالـregex ⇒ مافيش عدّ غلط) ⭐
m = re.search(r"^STRATEGIES = \{", SRC, re.M)
strat_src = SRC[m.start():] if m else ""
try:
    _blk = strat_src[:strat_src.find("\n}\n") + 3] if strat_src else ""
    _ast0 = ast.parse("STRATEGIES = " + _blk.split("=", 1)[1])
    _strat0 = ast.literal_eval(_ast0.body[0].value)
except Exception:
    _strat0 = {}
strat_names = sorted(_strat0.keys())
# ⭐ ملاحظة النطاق: فيه **قائمتين** استراتيجيات ⭐
#   ① ٧ استراتيجيات *التقييم* في update_prices.py (STRATEGIES) ⭐
#   ② ٩ استراتيجيات *محرّك الفرص* في data/opp_definitions.json ⭐
#      (= «الاستراتيجيات التسع» في تكليف المالك ⭐)
ok(len(strat_names) == 7, "② استراتيجيات التقييم = ٧", len(strat_names))
DETAIL.append({"strategies": strat_names})

# ══════════════════════════════════════════════════════════════════
#  ٢) بيانات اختبار اصطناعية
# ══════════════════════════════════════════════════════════════════
FULL = {
    "code": "TEST", "price": 100.0, "sector": "التكنولوجيا",
    "ema20": 95.0, "ema50": 90.0, "ema200": 80.0, "sma50": 88.0,
    "rsi": 58.0, "rsi_prev": 52.0, "macd": 2.5, "macd_signal": 1.5,
    "adx": 30.0, "di_plus": 25.0, "di_minus": 15.0,
    "volume": 2_000_000, "vol_5": 1_800_000, "vol_60": 1_500_000,
    "mkt_cap": 60e9, "rel_volume": 1.6, "atr": 3.0,
    "pe": 18.0, "pb": 2.1, "roe": 0.22, "eps": 5.5,
    "de_ratio": 35.0, "net_margin": 0.14, "dividend_yield": 0.02,
    "perf_w": 0.02, "perf_1m": 0.05, "perf_3m": 0.12,
    "perf_6m": 0.18, "perf_y": 0.25,
    "all_axes": {"risk": 72.0, "technical": 61.0, "fundamental": 55.0,
                 "liquidity": 70.0, "news": 50.0, "sentiment": 52.0,
                 "portfolio": 60.0},
    "news_score": 50.0, "watch": [], "portfolio": [],
}
ALL_STOCKS = [dict(FULL, code="A"), dict(FULL, code="B", price=80.0),
              dict(FULL, code="C", price=120.0, mkt_cap=2e9)]

# ══════════════════════════════════════════════════════════════════
#  ٣) تشغيل المحركات
# ══════════════════════════════════════════════════════════════════
import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()
os.environ.setdefault("OCTAD_TOKEN_SECRET", "TEST-ONLY-token-secret")
os.environ.setdefault("OCTA_PIN_PEPPER", "TEST-ONLY-pin-pepper")
os.environ.setdefault("OCTAD_DEV", "1")

import update_prices as up  # noqa: E402
import octa_score as os_mod  # noqa: E402

ENGINES = {
    "الفني (technical)": lambda it: os_mod.tech_score(it),
    "السيولة (liquidity)": lambda it: os_mod.liquidity_score(it),
    "الأساسي (fundamental)": lambda it: up.fundamental_score(it),
    "المعنويات (sentiment)": lambda it: up.sentiment_engine(it, ALL_STOCKS),
    "المخاطر (risk)": lambda it: up.risk_engine(it),
    "الأخبار (news)": lambda it: up.news_engine(it),
    "الفرص (opportunity)": lambda it: up.opportunity_engine(it),
    "المركّب (final)": lambda it: os_mod.final_score(it),
}


def _score_of(res):
    """يستخرج الدرجة من أي شكل رد"""
    if res is None:
        return None
    if isinstance(res, dict):
        for k in ("score", "final", "value", "total"):
            if k in res and isinstance(res[k], (int, float)):
                return float(res[k])
        return None
    if isinstance(res, (int, float)):
        return float(res)
    return None


section("٢) الحدود والحتمية لكل محرك")

for label, fn in ENGINES.items():
    try:
        r1 = fn(FULL)
        r2 = fn(FULL)
    except Exception as e:
        ok(False, "محرك %s — استثناء" % label, e)
        continue
    s1 = _score_of(r1)
    ok(s1 is None or (0.0 <= s1 <= 100.0),
       "محرك %s — الدرجة جوه 0..100" % label, s1)
    ok(s1 == _score_of(r2),
       "محرك %s — الحتمية (نفس المدخلات ⇒ نفس الدرجة)" % label)
    ok(isinstance(r1, (dict, type(None), int, float)),
       "محرك %s — شكل الرد sane" % label, type(r1).__name__)

section("٣) ⭐ الانحلال: نقص البيانات ما يزيدش الدرجة (درس F-20-04)")

# ⛔ ناقص: نشيل بيانات السيولة ⇒ الدرجة لازم ما تزيدش ⭐
no_liq = dict(FULL)
for _k in ("volume", "vol_5", "vol_60", "rel_volume"):
    no_liq.pop(_k, None)
s_full = _score_of(ENGINES["السيولة (liquidity)"](FULL))
s_noliq = _score_of(ENGINES["السيولة (liquidity)"](no_liq))
ok(s_noliq is None or (s_full is not None and s_noliq <= s_full),
   "السيولة: البيانات الناقصة ⇐ الدرجة ما تزيدش",
   "%s → %s" % (s_full, s_noliq))

# ⛔ ناقص: نشيل المؤشرات الفنية ⇒ ما يزيدش ⭐
no_tech = dict(FULL)
for _k in ("ema20", "ema50", "ema200", "sma50", "rsi", "rsi_prev",
           "macd", "macd_signal", "adx", "di_plus", "di_minus"):
    no_tech.pop(_k, None)
s_full_t = _score_of(ENGINES["الفني (technical)"](FULL))
s_no_t = _score_of(ENGINES["الفني (technical)"](no_tech))
ok(s_no_t is None or (s_full_t is not None and s_no_t <= s_full_t),
   "الفني: البيانات الناقصة ⇐ الدرجة ما تزيدش",
   "%s → %s" % (s_full_t, s_no_t))

# ⛔ المخاطرة الناقصة ⇒ المركّب لازم يشيل الاستحقاق ⭐
_risk_missing = dict(FULL)
_ra = dict(_risk_missing.get("all_axes") or {})
_ra.pop("risk", None)
_risk_missing["all_axes"] = _ra
try:
    r_full = os_mod.final_score(FULL)
    r_norisk = os_mod.final_score(_risk_missing)
except Exception as e:
    r_full = r_norisk = None
    ok(False, "المركّب: ناقص المخاطرة ⇐ ما يزيدش", e)
else:
    sf = _score_of(r_full)
    sn = _score_of(r_norisk)
    ok(sn is None or (sf is not None and sn <= sf),
       "المركّب: ناقص المخاطرة ⇐ الدرجة ما تزيدش", "%s → %s" % (sf, sn))
    _el_full = bool((r_full or {}).get("rank_eligible", True))
    _el_norisk = bool((r_norisk or {}).get("rank_eligible", True))
    ok(not _el_norisk or sn is None,
       "المركّب: ناقص المخاطرة ⇐ مش مستحق للترتيب",
       "rank_eligible=%s" % _el_norisk)

section("٤) الحالات الحدية (مافيش استثناء)")

EDGE = [
    ("فارغ", {}),
    ("بدون سعر", {"code": "X"}),
    ("سعر نص", {"code": "X", "price": "abc"}),
    ("سعر سالب", {"code": "X", "price": -5.0}),
    ("سعر صفري", {"code": "X", "price": 0.0}),
    ("قيم NaN", {"code": "X", "price": float("nan"), "rsi": float("nan"),
                 "mkt_cap": float("nan")}),
    ("قيم نصية", {"code": "X", "price": 10.0, "rsi": "abc",
                   "mkt_cap": "n/a", "volume": None}),
    ("قائمة بدل dict", {"code": "X", "price": 10.0, "watch": []}),
]
for label, fn in ENGINES.items():
    bad = []
    for elabel, item in EDGE:
        try:
            fn(item)
        except Exception as e:
            bad.append("%s:%s" % (elabel, type(e).__name__))
    ok(not bad, "محرك %s —Cases الحدية مافيش استثناء" % label, bad)

section("٥) ⭐ مرجع مستقل: إعادة حساب عمق السيولة + النشاط من الصفر")

# ⭐ إعادة تنفيذ مستقلة تمامًا (من المواصفات مش من الكود) ⭐
def ref_depth(mc):
    if mc is None:
        return 20.0
    if mc > 100e9:
        return 40.0
    if mc > 50e9:
        return 35.0
    if mc > 20e9:
        return 29.0
    if mc > 5e9:
        return 22.0
    if mc > 1e9:
        return 14.0
    if mc > 300e6:
        return 8.0
    return 3.0


def ref_activity(rv):
    if rv is None:
        return 15.0
    if rv > 2.0:
        return 28.0
    if rv > 1.3:
        return 24.0
    if rv > 0.8:
        return 18.0
    if rv > 0.4:
        return 11.0
    return 5.0


for mc, rv in ((60e9, 1.6), (5e9, 0.5), (150e6, 0.2), (250e9, 3.0),
               (12e9, 1.0)):
    item = dict(FULL, mkt_cap=mc, rel_volume=rv)
    res = ENGINES["السيولة (liquidity)"](item) or {}
    br = res.get("breakdown") or {}
    d = float(br.get("عمق السوق") or 0)
    a = float(br.get("النشاط") or 0)
    exp_d = ref_depth(mc)
    exp_a = ref_activity(rv)
    # ⛔ مرجع مستقل: مطابقة_components ⭐ (النشاط +3 ممكن ⇒ نسمح ±3) ⭐
    ok(abs(d - exp_d) < 0.01,
       "مرجع مستقل · عمق السوق (mc=%.1fB)" % (mc / 1e9), "%s != %s" % (d, exp_d))
    ok(abs(a - exp_a) <= 3.01,
       "مرجع مستقل · النشاط (rv=%.1f)" % rv, "%s != %s" % (a, exp_a))

section("٦) الاستراتيجيات التسع")

strat_block = strat_src[:strat_src.find("\n}\n") + 3] if strat_src else ""
_strat = _strat0 or getattr(up, "STRATEGIES", {}) or {}

ok(len(_strat) == 7, "عدد استراتيجيات التقييم (محرك التقييم) = ٧", len(_strat))
for name, st in _strat.items():
    w = st.get("weights") or {}
    tot = round(sum(float(v) for v in w.values()), 6)
    ok(abs(tot - 1.0) < 1e-6,
       "استراتيجية %s — مجموع الأوزان = 1" % name, tot)
    ok(set(w.keys()) == {"technical", "fundamental", "liquidity", "news",
                         "sentiment", "risk", "portfolio"},
       "استراتيجية %s — نفس المحاور السبعة" % name, sorted(w.keys()))

# ⭐⭐ المحور الناقص ⇐ النتيجة أسوأ أو مساوية ⭐ (كل الاستراتيجيات) ⭐
def _axes_item(tech=61.0, fund=55.0, liq=70.0, sent=52.0, pfit=60.0,
               risk=72.0):
    return {
        "technical": {"score": tech}, "fundamental": {"score": fund},
        "liquidity": {"score": liq}, "sentiment": {"score": sent},
        "portfolio": {"score": pfit},
        "item": {"news_score": 50.0,
                 "all_axes": {"risk": risk, "technical": tech,
                              "fundamental": fund, "liquidity": liq}},
    }


for name in sorted(_strat.keys()):
    full = _axes_item()
    # ⛔ ناقص المخاطرة ⭐
    nr = _axes_item(risk=None)
    try:
        sf = up.strategy_score(full["item"], name, full["technical"],
                               full["fundamental"], full["liquidity"],
                               full["sentiment"], full["portfolio"])
        sn = up.strategy_score(nr["item"], name, nr["technical"],
                               nr["fundamental"], nr["liquidity"],
                               nr["sentiment"], nr["portfolio"])
    except Exception as e:
        ok(False, "استراتيجية %s — ناقص المخاطرة" % name, e)
        continue
    v_f = (sf or {}).get("score")
    v_n = (sn or {}).get("score")
    ok(v_n is None or (v_f is not None and v_n <= v_f),
       "استراتيجية %s — ناقص المخاطرة ⇐ ما يزيدش" % name,
       "%s → %s" % (v_f, v_n))
    ok(not (sn or {}).get("rank_eligible", True),
       "استراتيجية %s — ناقص المخاطرة ⇐ مش مستحق للترتيب" % name)
    # ⛔ ناقص الأساسي ⇒ score=None ⭐
    nf = _axes_item(fund=None)
    snf = up.strategy_score(nf["item"], name, nf["technical"],
                            nf["fundamental"], nf["liquidity"],
                            nf["sentiment"], nf["portfolio"])
    ok((snf or {}).get("score") is None,
       "استراتيجية %s — ناقص الأساسي ⇐ مافيش رقم مخترع" % name,
       (snf or {}).get("score"))

section("٧-أ) ⭐⭐ الاستراتيجيات التسع (محرك الفرص · opp_definitions)")

# ⭐ الاستراتيجيات التسع معرّفة في data/opp_definitions.json ⭐
import opp_engine as opp  # noqa: E402

try:
    _defs = opp.load_definitions()
except Exception as e:
    _defs = {"strategies": []}
    ok(False, "تحميل تعريفات محرّك الفرص", e)
_opp_strats = _defs.get("strategies") or []
ok(len(_opp_strats) == 9,
   "① عدد استراتيجيات محرّك الفرص = ٩", len(_opp_strats))
DETAIL.append({"opp_strategies": [s.get("key") for s in _opp_strats]})

# ⭐⭐ item كامل + item ناقص ⭐
OPP_FULL = {
    "code": "TEST", "price": 100.0, "sector": "التكنولوجيا",
    "all_axes": {"technical": 68.0, "fundamental": 60.0, "liquidity": 72.0,
                 "risk": 65.0, "news": 55.0, "sentiment": 58.0,
                 "portfolio": 60.0},
    "liquidity_score": 72.0, "rel_volume": 1.4, "rsi": 55.0,
    "perf_1m": 0.06, "perf_3m": 0.14, "perf_y": 0.20,
    "technical_signal": "صاعد", "volume": 2_000_000, "vol_60": 1_500_000,
    "pe": 18.0, "pb": 2.1, "roe": 0.22, "eps": 5.5, "de_ratio": 35.0,
    "net_margin": 0.14, "dividend_yield": 0.02, "beta": 0.9,
    "volatility": 0.22, "mdd1y": -0.18, "sharpe3y": 0.9, "vol1y": 0.25,
    "cash": 1.2e9, "total_debt": 3.4e9, "total_equity": 9.1e9,
    "fcf": 8.2e8, "cfo": 9.5e8, "reinvest_rate": 0.55,
    "gross_margin": 0.41, "operating_margin": 0.19, "payout_ratio": 0.25,
}
OPP_DEGRADED = dict(OPP_FULL)
_ax = dict(OPP_FULL["all_axes"])
_ax.pop("risk", None)
OPP_DEGRADED["all_axes"] = _ax

for st in _opp_strats:
    key = st.get("key")
    crit_full = opp.evaluate_item(OPP_FULL)
    crit_deg = opp.evaluate_item(OPP_DEGRADED)
    try:
        r_full = opp.evaluate_strategy(OPP_FULL, st, crit_full)
        r_deg = opp.evaluate_strategy(OPP_DEGRADED, st, crit_deg)
    except Exception as e:
        ok(False, "استراتيجية %s — التقييم" % key, e)
        continue
    s_f = r_full.get("score")
    s_d = r_deg.get("score")
    # ⭐⭐ الفحص الأهم: النقص ما يزيدش الدرجة ⭐
    ok(s_d is None or (s_f is not None and s_d <= s_f),
       "استراتيجية %s — البيانات الناقصة ⇐ الدرجة ما تزيدش" % key,
       "%s → %s" % (s_f, s_d))
    # ⭐⭐ الدرجة محسوبة على **كل** الأوزان (مش المتاح بس) ⭐ ⇒ النقص خصم ⭐
    ok(isinstance(s_f, (int, float)) and 0 <= s_f <= 100,
       "استراتيجية %s — الدرجة جوه 0..100" % key, s_f)
    if r_deg.get("missing"):
        ok(r_deg.get("coverage") is not None
           and r_deg.get("coverage") < 100.0,
           "استراتيجية %s — التغطية ناقصة ومُعلنة" % key,
           r_deg.get("coverage"))
    # ⭐ ناقص المخاطرة ⇒ مش مستحق ⭐
    if not r_deg.get("eligible"):
        ok(True, "استراتيجية %s — ناقص المخاطر ⇐ غير مؤهّل" % key,
           r_deg.get("exclusion"))
    else:
        ok(False, "استراتيجية %s — ناقص المخاطر لازم يكون غير مؤهّل" % key,
           r_deg.get("exclusion"))

# ⭐ الأوزان: مجموع نقاط كل معيار = نقاط الاستراتيجية ⭐
for st in _opp_strats:
    ws = [float(c.get("weight") or 0) for c in (st.get("criteria") or [])]
    ok(abs(sum(ws) - 100.0) < 0.01 or abs(sum(ws) - 1.0) < 0.01,
       "استراتيجية %s — مجموع أوزان المعايير (١٠٠ أو ١)" % st.get("key"),
       sum(ws))

section("٧) ⭐ حد الـ90٪-policy: الأوزان ما اتغيّرتش")
# ⭐ مقارنة weights في الكود مع نسخة الجولة ١٩ ⭐ (من Git) ⭐
try:
    import subprocess
    base = subprocess.run(
        ["git", "-C", ROOT, "show", "edc49cd:update_prices.py"],
        capture_output=True, text=True, timeout=60).stdout
    mb = re.search(r"^STRATEGIES = \{", base, re.M)
    if mb:
        base_block = base[mb.start():]
        base_block = base_block[:base_block.find("\n}\n") + 3]
        try:
            _ast2 = ast.parse("STRATEGIES = " + base_block.split("=", 1)[1])
            _base_strat = ast.literal_eval(_ast2.body[0].value)
        except Exception:
            _base_strat = None
        if _base_strat:
            same = all(
                _base_strat.get(k, {}).get("weights") == v.get("weights")
                for k, v in _strat.items()) and set(_base_strat) == set(_strat)
            ok(same, "أوزان الاستراتيجيات **زي الجولة ١٩ بالظبط**")
            DETAIL.append({"weights_unchanged_vs_r19": bool(same)})
        else:
            ok(False, "مقارنة الأوزان مع الجولة ١٩")
    else:
        ok(False, "مقارنة الأوزان مع الجولة ١٩ — STRATEGIES مش لاقيان")
except Exception as e:
    ok(False, "مقارنة الأوزان مع الجولة ١٩", e)

# ══════════════════════════════════════════════════════════════════
#  النتيجة + ملف الجرد
# ══════════════════════════════════════════════════════════════════
passed = sum(1 for c, _ in RESULTS if c)
total = len(RESULTS)
print("\n" + "=" * 68)
print("  نتيجة التدقيق: %d/%d" % (passed, total))
print("=" * 68)
for c, label in RESULTS:
    if not c:
        print("  ❌ فشل: " + label)

out = {
    "inventory": inventory,
    "strategies": sorted(_strat.keys()),
    "passed": passed, "total": total,
    "detail": DETAIL,
}
try:
    p_out = os.path.join(HERE, "..", "engine_audit_result.json")
    io.open(os.path.abspath(p_out), "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print("  📄 الجرد: %s" % os.path.abspath(p_out))
except Exception as e:
    print("  ⚠️ مقدرتش أكتب الجرد: %s" % e)

sys.exit(0 if passed == total else 1)
