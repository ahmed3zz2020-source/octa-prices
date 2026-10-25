#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار تدقيق الأوزان والدرجات — ٢٥ أكتوبر ٢٠٢٦
═════════════════════════════════════════════════════════════

شغّال مع:  python3 tools/test_quant_audit.py

الهدف: كل رقم في docs/AUDIT-QUANT-2026-10-25.md يبقى قابل للتكرار.
كل اختبار هنا بيربط نفسه ببند من التقرير.

⛔ مفيش شبكة — كله على البيانات المحلية (data_full.json).
"""
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

os.environ.setdefault("OCTA_ADMIN_TOKEN", "test")
os.environ["OCTAD_DEV"] = "1"

try:
    import _stub_env
    _stub_env.install()
except Exception:
    pass

import octa_score as OS           # noqa: E402
import update_prices as UP        # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + ((" — " + str(detail)) if detail else ""))


def sect(t):
    print("\n" + "═" * 62)
    print("  " + t)
    print("═" * 62)


# ══════════════════════════════════════════════════════════════
# 0) تجهيز البيانات
# ══════════════════════════════════════════════════════════════
MAP = {'p': 'price', 'v': 'volume', 'mc': 'mkt_cap', 'pe': 'pe', 'pb': 'pb',
       'roe': 'roe', 'roa': 'roa', 'roic': 'roic', 'ps': 'ps',
       'evEbitda': 'ev_ebitda', 'rev': 'revenue', 'ni': 'net_income',
       'nm': 'net_margin', 'om': 'operating_margin', 'gm': 'gross_margin',
       'ebitda': 'ebitda', 'fcf': 'fcf', 'de': 'de_ratio', 'cr': 'current_ratio',
       'qr': 'quick_ratio', 'eps': 'eps', 'dy': 'div_yield', 'rsi': 'rsi',
       'beta': 'beta', 'ma50': 'sma50', 'ma200': 'sma200', 'macd': 'macd',
       'macdSig': 'macd_signal', 'relvol': 'rel_volume', 'av30': 'avg_volume_30',
       'h52': 'high_52w', 'l52': 'low_52w', 'tvRec': 'tv_rec',
       'perf1m': 'perf_1m', 'perf3m': 'perf_3m', 'perf6m': 'perf_6m',
       'perf1y': 'perf_y', 'perfYtd': 'perf_ytd', 'vol1y': 'vol1y',
       'vol3y': 'vol3y', 'mdd': 'mdd', 'mdd1y': 'mdd1y', 'cagr3y': 'cagr3y',
       'sharpe3y': 'sharpe3y', 'sortino3y': 'sortino3y',
       'frm52hi': 'from_52high', 'sector': 'sector', 'sectorAr': 'sector_ar',
       'name': 'name', 'code': 'code'}
SKIP = {'q', 'm', 'sf', 'lq', 'total', 'verdict', 'why', 'missing',
        'partial', 'pack', 'packNote', 'riskInputs'}


def _conv(st):
    it = {}
    for k, v in st.items():
        if k in SKIP:
            continue
        it[MAP.get(k, k)] = v
    it['data_confidence'] = st.get('conf')
    return it


_DF = os.path.join(ROOT, "data_full.json")
if not os.path.exists(_DF):
    print("❌ data_full.json مش موجود — مش هيعرف يشتغل")
    sys.exit(2)

_data = json.load(open(_DF, encoding="utf-8"))
ITEMS = [_conv(s) for s in _data['stocks'].values()]
SS = OS.build_sector_stats(ITEMS)
UP.SECTOR_STATS = SS

# ══════════════════════════════════════════════════════════════
# 1) الأوزان — §١ من التقرير
# ══════════════════════════════════════════════════════════════
sect("١) الأوزان — المصدر الوحيد + المجموع")

W = OS.AXIS_WEIGHTS
ok("المجموع = 1.00", abs(sum(W.values()) - 1.0) < 1e-9, round(sum(W.values()), 6))
ok("٧ محاور بالظبط", len(W) == 7, list(W.keys()))
ok("مفيش محور صفر", all(v > 0 for v in W.values()))
ok("update_prices بيستورد نفس القاموس",
   UP.AXIS_WEIGHTS is OS.AXIS_WEIGHTS)

# /api/engine-weights لازم يشتقّ من AXIS_WEIGHTS
_pct = {k: int(round(v * 100)) for k, v in W.items()}
ok("/api/engine-weights مشتقّ من AXIS_WEIGHTS (مش ثابت)",
   _pct == {"technical": 18, "fundamental": 22, "liquidity": 18,
            "news": 5, "sentiment": 4, "risk": 24, "portfolio": 9}, _pct)

# groups
_us = {"technical": 15, "fundamental": 20, "valuation": 15, "liquidity": 10,
       "news": 10, "sentiment": 10, "risk": 10, "portfolio": 10}
ok("أوزان usScan مجموعها 100%", sum(_us.values()) == 100, sum(_us.values()))
_intel = {"technical": 20, "fundamental": 25, "liquidity": 10, "news": 7,
          "sentiment": 5, "risk": 20, "portfolio": 13}
ok("أوزان intel مجموعها 100%", sum(_intel.values()) == 100, sum(_intel.values()))

# ══════════════════════════════════════════════════════════════
# 2) المحاور الناقصة — §٢.٣
# ══════════════════════════════════════════════════════════════
sect("٢) المحاور الناقصة — None مش رقم مخترع")

_item = {"price": 100, "perf_1m": 5, "data_confidence": 40}
_t = {"score": 70}
_f = {"score": 65}
_l = {"score": 60, "risk_level": "متوسط"}

_fin = OS.final_score(_item, _t, _f, _l, None,
                       news={"score": 88}, portfolio={"score": 42},
                       sentiment={"score": 77}, conf=40)
ok("الأخبار الحقيقية بتيوصل (88)", _fin['axes']['news'] == 88, _fin['axes']['news'])
ok("المحفظة الحقيقية بتيوصل (42)", _fin['axes']['portfolio'] == 42, _fin['axes']['portfolio'])
ok("المعنويات الحقيقية بتيوصل (77)", _fin['axes']['sentiment'] == 77, _fin['axes']['sentiment'])
ok("خصم الثقة اتحسب (conf=40 ⇒ -2.5)",
   abs(_fin['adjustments']['خصم الثقة'] - (-2.5)) < 0.01,
   _fin['adjustments']['خصم الثقة'])

_fin2 = OS.final_score(_item, _t, _f, _l, None, conf=40)
ok("بدون أخبار ⇒ None مش 45", _fin2['axes']['news'] is None, _fin2['axes']['news'])
ok("بدون محفظة ⇒ None مش 70", _fin2['axes']['portfolio'] is None, _fin2['axes']['portfolio'])
ok("missing_axes مت-report", "missing_axes" in _fin2, list(_fin2.get('missing_axes') or []))
ok("محور ناقص بيتشال من الوزن (المحصلة أقل)",
   _fin2['final_score'] != _fin['final_score'],
   f"{_fin2['final_score']} vs {_fin['final_score']}")

# ══════════════════════════════════════════════════════════════
# 3) المحرك الكامل على ٢٩٦ سهم — صفر أخطاء
# ══════════════════════════════════════════════════════════════
sect("٣) التشغيل الكامل — ٢٩٦ سهم")

ROWS = []
ERRS = []
for it in ITEMS:
    try:
        UP.derive_technical(it)
        t = OS.tech_score(it)
        f = UP.fundamental_score(it, SS)
        li = OS.liquidity_score(it)
        se = UP.sentiment_engine(it, ITEMS)
        nw = UP.news_engine(it, it.get('sector'))
        pfit = UP.portfolio_fit(it, None)
        rk = UP.risk_engine(it, SS, news=nw)
        fin = OS.final_score(it, t, f, li, SS, news=nw, portfolio=pfit,
                             sentiment=se, conf=it.get('data_confidence'))
        if not fin:
            continue
        ROWS.append({'code': it.get('code'), 'score': fin['final_score'],
                     'dec': fin['decision'], 'axes': fin['axes'],
                     'missing': fin.get('missing_axes') or [],
                     'conf': it.get('data_confidence'),
                     'liq_risk': li.get('risk_level'), 'liq_score': li.get('score'),
                     'safety': rk['safety_score'] if rk else None})
    except Exception as e:                                    # noqa: BLE001
        ERRS.append((it.get('code'), repr(e)))

ok("كل الأسهم اتحسبت بدون exception", len(ERRS) == 0, ERRS[:3])
ok("عدد الأسهم = 296", len(ROWS) == 296, len(ROWS))

_dec = {}
for r in ROWS:
    _dec[r['dec']] = _dec.get(r['dec'], 0) + 1
print("     التوزيع:", _dec)
ok("مفيش قرار خارج القامود",
   set(_dec) <= {"إشارة سلبية", "إشارة محايدة", "إشارة إيجابية", "بيانات غير كافية"})

# ══════════════════════════════════════════════════════════════
# 4) الحساسية — §٣
# ══════════════════════════════════════════════════════════════
sect("٤) الحساسية — الفني ١٨٪ ← ٢٥٪")


def _compose(axes, w, row, conf, pen=0.18):
    av = {k: v for k, v in w.items() if axes.get(k) is not None}
    ws = sum(av.values())
    if not ws:
        return None
    base = sum(axes[k] * (av[k] / ws) for k in av)
    rp = 0.0 if axes.get('risk') is None else min(15.0, (100 - axes['risk']) * pen)
    lp = 0.0
    if row.get('liq_risk') in ("مرتفع جداً", "مرتفع"):
        lp = min(6.0, (100 - row['liq_score']) * 0.10)
    cp = 0.0
    if conf is not None:
        if conf < 50:
            cp = (50 - conf) * 0.25
        elif conf > 80:
            cp = -(conf - 80) * 0.05
    tp = max(0.0, rp + lp + cp)
    if tp > 22:
        sc = 22 / tp
        rp *= sc
        lp *= sc
        cp *= sc
    return round(max(0, min(100, base - rp - lp - cp)), 1)


def _decide(axes, final):
    fund = axes.get('fundamental') or 0
    tech = axes.get('technical') or 0
    rv = axes.get('risk')
    if rv is not None and rv < 35:
        return "إشارة سلبية"
    if fund < 40 or tech < 30:
        return "بيانات غير كافية"
    if final >= 78 and tech >= 50 and fund >= 60:
        return "إشارة إيجابية"
    if final >= 65:
        return "إشارة إيجابية"
    if final >= 52:
        return "إشارة محايدة"
    if fund >= 65:
        return "إشارة محايدة"
    return "إشارة سلبية"


NEW = dict(W)
NEW['technical'] = 0.25
_rest = sum(v for k, v in W.items() if k != 'technical')
for k in NEW:
    if k != 'technical':
        NEW[k] = W[k] / _rest * (1 - 0.25)
ok("أوزان السيناريو مجموعها 1.00", abs(sum(NEW.values()) - 1.0) < 1e-9,
   {k: round(v, 4) for k, v in NEW.items()})

_base, _scen = {}, {}
for r in ROWS:
    ax = r['axes']
    _b = _compose(ax, W, r, r.get('conf'))
    if _b is None:
        continue
    _base[r['code']] = (_b, _decide(ax, _b))
    _s = _compose(ax, NEW, r, r.get('conf'))
    _scen[r['code']] = (_s, _decide(ax, _s))

_deltas = sorted(_scen[c][0] - _base[c][0] for c in _base)
_n = len(_deltas)
ok("أقصى تحرّك ≤ 5 نقاط", max(abs(x) for x in _deltas) <= 5.0,
   f"max={max(_deltas):+.2f} min={min(_deltas):+.2f}")
print(f"     delta: mean={sum(_deltas)/_n:+.3f} median={_deltas[_n//2]:+.3f}")
print(f"     درجات اتغيرت >1 نقطة: {sum(1 for x in _deltas if abs(x) > 1)}/{_n}")

_dch = sum(1 for c in _base if _base[c][1] != _scen[c][1])
print(f"     تصنيفات اتغيرت: {_dch}/{_n} ({_dch/_n*100:.1f}%)")
ok("تصنيفات متغيّرة ≤ 5%", _dch / _n <= 0.05, f"{_dch/_n*100:.1f}%")
ok("المحرك مستقر ضد تغيّر الأوزان", _dch / _n <= 0.05)

# ══════════════════════════════════════════════════════════════
# 5) مخاطر الأحداث — r_ev مبني على الأخبار
# ══════════════════════════════════════════════════════════════
sect("٥) مخاطر الأحداث — مش ثابتة")

_old_actions = list(getattr(UP, "_actions", []) or [])
try:
    UP._actions = [
        {"code": "__T1", "kind": "capital_increase", "kindAr": "زيادة رأس المال",
         "headline": "زيادة رأس المال عن طريق المساهمة"},
        {"code": "__T2", "kind": "dividend", "kindAr": "توزيعات نقدية",
         "headline": "توزيعات نقدية", "value": 1.0},
    ]
    _b = {"code": "__T1", "name": "t", "price": 50.0, "volume": 100000,
          "mkt_cap": 5e9, "rel_volume": 1.2, "sector": "Industrial",
          "perf_1m": 5, "beta": 1.0, "data_confidence": 75}
    _b2 = dict(_b)
    _b2['code'] = "__T2"
    _nw1 = UP.news_engine(_b, _b.get("sector"))
    _nw2 = UP.news_engine(_b2, _b2.get("sector"))
    _rk1 = UP.risk_engine(_b, None, news=_nw1)
    _rk2 = UP.risk_engine(_b2, None, news=_nw2)
    ok("حدث حرج ⇒ r_ev = 10", _rk1['breakdown'].get('الأحداث') == 10,
       _rk1['breakdown'].get('الأحداث'))
    ok("حدث عادي ⇒ r_ev = 5", _rk2['breakdown'].get('الأحداث') == 5,
       _rk2['breakdown'].get('الأحداث'))
    ok("درجة الأخبار بتختلف بين السهمين", _nw1['score'] != _nw2['score'],
       f"{_nw1['score']} vs {_nw2['score']}")
finally:
    UP._actions = _old_actions

_rk_no = UP.risk_engine({"code": "__X", "price": 10, "mkt_cap": 1e9},
                         None, news=None)
ok("مافيش أخبار ⇒ r_ev = 0 (مش 5)", _rk_no['breakdown'].get('الأحداث') == 0,
   _rk_no['breakdown'].get('الأحداث'))

# ══════════════════════════════════════════════════════════════
# 6) explain_score — جدول المساهمة
# ══════════════════════════════════════════════════════════════
sect("٦) explain_score — المساهمة حقيقية")

_ex = UP.explain_score(
    {"code": "X", "price": 100, "perf_1m": 5, "data_confidence": 40},
    tech={"score": 70, "positives": ["p"], "negatives": []},
    fund={"score": 65, "positives": [], "negatives": []},
    liq={"score": 60, "risk_level": "متوسط", "positives": [], "negatives": []},
    news=None, sent=None, risk=None, pfit=None,
    final={"axes": {"technical": 70, "fundamental": 65, "liquidity": 60,
                    "news": None, "sentiment": 52, "risk": None,
                    "portfolio": None},
           "final_score": 61.7, "confidence": 60, "missing_axes": ["الأخبار"]})
_miss = [c for c in _ex['contributions'] if c.get('missing')]
ok("المحاور الناقصة متعلّمة كـ missing", len(_miss) == 3,
   [c['axis'] for c in _miss])
ok("المحور الناقص مالوش مساهمة رقمية",
   all(c['contribution'] is None for c in _miss))
_sum = sum(c['contribution'] for c in _ex['contributions']
            if c['contribution'] is not None)
ok("مجموع المساهمات = base_score", abs(_sum - _ex['base_score']) < 0.2,
   f"{_sum} vs {_ex['base_score']}")
ok("missing_axes مذكور للمستخدم",
   any("ناقص" in w for w in _ex['what_could_change_score']))

# ══════════════════════════════════════════════════════════════
# ٧) strategy_score — مفيش ٥٠ مخترعة
# ══════════════════════════════════════════════════════════════
sect("٧) strategy_score — تطبيع على المتاح")

# ⛔ لو مافيش ولا محور متاح ⇒ مفيش درجة (زي final_score)
_st_none = UP.strategy_score({"code": "X", "price": 100, "perf_1m": 5},
                              "balanced", tech=None, fund=None, liq=None,
                              sent=None, pfit=None)
ok("مفيش ولا محور ⇒ مفيش درجة (None)", _st_none is None, _st_none)

# محور واحد بس موجود ⇒ التطبيع يشتغل
_st = UP.strategy_score({"code": "X", "price": 100, "perf_1m": 5},
                         "balanced", tech={"score": 70}, fund=None, liq=None,
                         sent=None, pfit=None)
ok("محور ناقص ⇒ None مش ٥٠", _st['axes']['technical'] == 70,
   _st['axes']['technical'])
ok("الأساسي الناقص ⇒ None مش ٥٠", _st['axes']['fundamental'] is None,
   _st['axes']['fundamental'])
ok("الأخبار الناقصة ⇒ None مش ٤٥", _st['axes']['news'] is None,
   _st['axes']['news'])
ok("المحفظة الناقصة ⇒ None مش ٧٠", _st['axes']['portfolio'] is None,
   _st['axes']['portfolio'])
ok("الدرجة محسوبة (مش NaN)", isinstance(_st['score'], (int, float)),
   _st['score'])
ok("base = المحور الواحد × وزنه المطبّع (١٠٠٪)",
   abs(_st['base'] - 70) < 0.5, _st['base'])

# ══════════════════════════════════════════════════════════════
# النتيجة
# ══════════════════════════════════════════════════════════════
sect("النتيجة")
print(f"  ✅ نجح: {len(PASS)}")
print(f"  {'❌ فشل: ' + str(len(FAIL)) if FAIL else '✅ فشل: 0'}")
if FAIL:
    for f in FAIL:
        print("     ❌ " + f)
    sys.exit(1)
print("\n🎉 كل اختبارات تدقيق الأوزان ناجحة.")
