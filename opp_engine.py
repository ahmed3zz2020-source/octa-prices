# -*- coding: utf-8 -*-
"""🎯 opp_engine.py — محرّك الفرص الحي (OPP-002).

📌 الهدف: حساب الفرص **من البيانات الحيّة** بدل اللقطة الثابتة.
📌 nine strategies: التسع استراتيجيات المعرّفة في data/opp_definitions.json
   (نفس تعريفات الواجهة — مش السبعة القديمة).

⛔⛔⛔ السرّية (١٥ نوفمبر ٢٠٢٦):
   الأوزان والعتبات (weight · points_max · min_coverage · min_liquidity_value)
   **سرّية** ⇒ ما بتترجعش في أي رد عام. الردود العامة فيها:
   · تعريف الاستراتيجية بالعربي (accept/reject/risk/invalidation)
   · نسبة المطابقة لكل معيار (ratio 0..1) والسبب المبسّط
   · التغطية والبيانات الناقصة
   ⛔ الأوزان الحقيقية ما بتظهرش.

⛔ مافيش شبكة · مافيش فلاس · الملف ده مستقل ⇒ يتختبر لوحده.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEF_FILE = HERE / "data" / "opp_definitions.json"

# ⛔ سياسات الصلاحيات المعتمدة (٢٠٢٦):
#    كل مسارات محرّك الفرص متاحة لكل مستخدم **مسجّل**.
#    لو المالك يريد حصر استراتيجيات Pro ⇒ حدّد المفاتيح هنا.
OPP_PRO_STRATEGIES = ()

# ⛔ حدود التشغيل (اختيارية) — الافتراضي: كل الأسهم
OPP_LIMIT_PER_STRATEGY = 20


def _f(v, d=None):
    try:
        if v is None:
            return d
        return float(v)
    except (TypeError, ValueError):
        return d


def _clamp(x, lo=0.0, hi=1.0):
    if x is None:
        return None
    return max(lo, min(hi, x))


def load_definitions(path=None):
    """يحمّل تعريفات الاستراتيجيات التسع (مرة واحدة)."""
    p = Path(path or os.environ.get("OCTA_OPP_DEFS") or DEF_FILE)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"model_version": "OPP-002.0", "strategies": []}
    d.setdefault("strategies", [])
    return d


# ════════════════════════════════════════════════════════════
#  ⭐ مقيّمو المعايير — كل واحد يرجّع (نسبة 0..1، دليل، ملاحظة)
#  ⛔ مافيش رقم مخترع: لو البيانات ناقصة ⇒ None (ناقص)
# ════════════════════════════════════════════════════════════

def _axis(item, key):
    ax = item.get("all_axes") or {}
    return _f(ax.get(key))


def c_trend(item):
    """الاتجاه الفني — من محور الفني + إشارة الاتجاه."""
    v = _axis(item, "technical")
    if v is None:
        return None
    r = v / 100.0
    sig = str(item.get("technical_signal") or "")
    if "هابط" in sig or "سالب" in sig:
        r *= 0.6
    return _clamp(r), {"technical": v, "signal": sig}, "موقع السعر من المتوسطات واتجاهها"


def c_momentum(item):
    """الزخم السعري — من أداء الشهر و٣ شهور."""
    p1 = _f(item.get("perf_1m"))
    p3 = _f(item.get("perf_3m"))
    if p1 is None and p3 is None:
        return None
    r = 0.5
    if p3 is not None:
        r += p3 / 40.0
    if p1 is not None:
        r += p1 / 60.0
    return _clamp(r), {"perf_1m": p1, "perf_3m": p3}, "قوة الحركة على الأفق الزمني"


def c_liquidity(item):
    """نشاط التداول والسيولة — من محور السيولة + الحجم النسبي."""
    v = _f(item.get("liquidity_score"))
    if v is None:
        return None
    rv = _f(item.get("rel_volume"))
    r = v / 100.0
    if rv is not None:
        r = r * 0.8 + _clamp(rv / 2.0) * 0.2
    return _clamp(r), {"liquidity_score": v, "rel_volume": rv}, "عمق التداول وحجمه النسبي"


def c_structure(item):
    """التكوين الفني والدعم والمقاومة — RSI + المحور الفني."""
    rsi = _f(item.get("rsi"))
    tech = _axis(item, "technical")
    if rsi is None and tech is None:
        return None
    r = 0.5
    if rsi is not None:
        if rsi < 30:
            r = 0.85
        elif rsi > 75:
            r = 0.35
        else:
            r = 0.6 + (50 - abs(rsi - 55)) / 100.0
    if tech is not None:
        r = r * 0.6 + (tech / 100.0) * 0.4
    return _clamp(r), {"rsi": rsi, "technical": tech}, "موقع السعر من مناطق الدعم والمقاومة"


def c_rr(item):
    """العائد مقابل المخاطرة — من محور المخاطرة."""
    v = _axis(item, "risk")
    if v is None:
        return None
    return _clamp(v / 100.0), {"risk": v}, "العائد المتوقع مقابل المخاطر"


def c_news(item):
    """الأخبار ومخاطر الأحداث — من محرك الأخبار."""
    v = _f(item.get("news_score"))
    if v is None:
        return None
    return _clamp(v / 100.0), {"news_score": v}, "قوة الأحداث الحالية ومخاطرها"


def c_fund_quality(item):
    """جودة الأعمال والنتائج المالية — من المحور الأساسي + ROE."""
    v = _axis(item, "fundamental")
    roe = _f(item.get("roe"))
    if v is None:
        return None
    r = v / 100.0
    if roe is not None:
        r = r * 0.7 + _clamp(roe / 30.0) * 0.3
    return _clamp(r), {"fundamental": v, "roe": roe}, "جودة الربحية والملاءة المالية"


def c_growth(item):
    """نمو الأرباح وتحسن الأداء."""
    p3 = _f(item.get("perf_3m"))
    rev = _f(item.get("revenue_growth"))
    ni = _f(item.get("ni_growth"))
    if p3 is None and rev is None and ni is None:
        return None
    parts = [x for x in (p3, rev, ni) if x is not None]
    r = 0.5 + (sum(parts) / len(parts)) / 40.0
    return _clamp(r), {"perf_3m": p3, "revenue_growth": rev, "ni_growth": ni}, \
        "معدل نمو الأرباح"


def c_catalyst(item):
    """المحفزات المتوقعة — من التغير اليومي والأخبار."""
    ch = _f(item.get("change"))
    news = _f(item.get("news_score"))
    if ch is None and news is None:
        return None
    r = 0.45
    if ch is not None:
        r += max(-0.25, min(0.35, ch / 20.0))
    if news is not None:
        r = r * 0.6 + (news / 100.0) * 0.4
    return _clamp(r), {"change": ch, "news_score": news}, "المحفزات المتوقعة والحركة الحالية"


def c_valuation(item):
    """جاذبية التقييم — PE/PB منخفضين أفضل."""
    pe = _f(item.get("pe"))
    pb = _f(item.get("pb"))
    up = _f(item.get("upside"))
    if pe is None and pb is None and up is None:
        return None
    r = 0.5
    if pe is not None and pe > 0:
        r = _clamp(1.0 - (pe - 6.0) / 54.0) * 0.6 + r * 0.4
    if pb is not None and pb > 0:
        r = r * 0.8 + _clamp(1.0 - (pb - 0.6) / 4.4) * 0.2
    if up is not None:
        r = r * 0.7 + _clamp(0.5 + up / 40.0) * 0.3
    return _clamp(r), {"pe": pe, "pb": pb, "upside": up}, "مساحة التقييم مقارنة بالسعر"


def c_funds(item):
    """استدامة نموذج الأعمال — ROE + هامش + دين."""
    roe = _f(item.get("roe"))
    nm = _f(item.get("net_margin"))
    de = _f(item.get("de_ratio"))
    if roe is None and nm is None and de is None:
        return None
    r = 0.5
    if roe is not None:
        r += (roe - 12.0) / 60.0
    if nm is not None:
        r += (nm - 8.0) / 40.0
    if de is not None:
        r -= max(0.0, (de - 40.0) / 60.0)
    return _clamp(r), {"roe": roe, "net_margin": nm, "de_ratio": de}, \
        "استدامة النموذج"


def c_returns(item):
    """جودة الربحية والعائد على رأس المال."""
    roe = _f(item.get("roe"))
    fund = _axis(item, "fundamental")
    if roe is None and fund is None:
        return None
    r = 0.5
    if roe is not None:
        r = _clamp(roe / 28.0)
    if fund is not None:
        r = r * 0.7 + (fund / 100.0) * 0.3
    return _clamp(r), {"roe": roe, "fundamental": fund}, "العائد على رأس المال"


def c_cfo(item):
    """التدفقات النقدية — من cfo/ni إن وُجدت."""
    cfo = _f(item.get("cfo"))
    ni = _f(item.get("ni"))
    if cfo is None or ni is None or ni == 0:
        return None
    ratio = cfo / ni
    return _clamp(ratio / 1.2), {"cfo": cfo, "ni": ni, "ratio": round(ratio, 2)}, \
        "التحويل من صافي الربح إلى نقد"


def c_safety_margin(item):
    """التقييم وهامش الأمان — من fair_value مقابل السعر."""
    fv = _f(item.get("fair_value"))
    px = _f(item.get("price"))
    up = _f(item.get("upside"))
    if fv is None or px is None or px <= 0:
        if up is None:
            return None
        return _clamp(0.5 + up / 40.0), {"upside": up}, "هامش الأمان التقديري"
    ratio = fv / px
    return _clamp((ratio - 0.7) / 0.9), {"fair_value": fv, "price": px, "ratio": round(ratio, 2)}, \
        "الفرق بين القيمة التقديرية والسعر"


def c_governance(item):
    """الحوكمة والمخاطر — من محور المخاطرة + أخبار السوء."""
    v = _axis(item, "risk")
    if v is None:
        return None
    return _clamp(v / 100.0), {"risk": v}, "استقرار الحوكمة ومخاطر المخاطر"


def c_debt(item):
    """المديونية — دين أقل أفضل."""
    de = _f(item.get("de_ratio"))
    if de is None:
        return None
    return _clamp(1.0 - max(0.0, (de - 15.0)) / 85.0), {"de_ratio": de}, "مستوى المديونية"


def c_growth_profit(item):
    """نمو الأرباح والتدفقات النقدية."""
    g = c_growth(item)
    cf = c_cfo(item)
    if g is None and cf is None:
        return None
    rs = [x[0] for x in (g, cf) if x is not None]
    r = sum(rs) / len(rs)
    ev = {}
    if g:
        ev.update(g[1])
    if cf:
        ev.update(cf[1])
    return _clamp(r), ev, "نمو الأرباح مدعوماً بالتدفق النقدي"


def c_reinvest(item):
    """كفاءة إعادة الاستثمار — ROE مع الاحتفاظ بالأرباح."""
    roe = _f(item.get("roe"))
    dy = _f(item.get("div_yield"))
    if roe is None:
        return None
    retention = 1.0 if dy is None else max(0.0, 1.0 - min(1.0, dy / 20.0))
    return _clamp((roe / 25.0) * (0.6 + 0.4 * retention)), {"roe": roe, "div_yield": dy}, \
        "العائد على المبلغ المُعاد استثماره"


def c_margins(item):
    """استدامة الهوامش."""
    nm = _f(item.get("net_margin"))
    if nm is None:
        return None
    return _clamp((nm + 5.0) / 35.0), {"net_margin": nm}, "هامش الربح الصافي"


def c_div_regular(item):
    """انتظام التوزيعات."""
    dy = _f(item.get("div_yield"))
    if dy is None:
        return None
    if dy <= 0:
        return 0.0, {"div_yield": dy}, "مفيش توزيعات"
    return _clamp(dy / 12.0), {"div_yield": dy}, "حجم العائد الموزّع"


def c_div_cover(item):
    """تغطية التوزيعات بالأرباح."""
    dy = _f(item.get("div_yield"))
    eps = _f(item.get("eps"))
    px = _f(item.get("price"))
    if dy is None or eps is None or px is None or px <= 0 or eps <= 0:
        return None
    payout = (dy / 100.0) * px / eps
    return _clamp(1.0 - max(0.0, payout - 0.4) / 0.6), \
        {"div_yield": dy, "eps": eps, "payout": round(payout, 2)}, \
        "نسبة الأرباح الموزّعة"


def c_balance(item):
    """القوة المالية — دين + حجم."""
    de = _f(item.get("de_ratio"))
    mc = _f(item.get("mkt_cap"))
    if de is None and mc is None:
        return None
    r = 0.5
    if de is not None:
        r += (50.0 - de) / 120.0
    if mc is not None:
        r += 0.15 if mc > 10e9 else (0.05 if mc > 2e9 else -0.1)
    return _clamp(r), {"de_ratio": de, "mkt_cap": mc}, "قوة الميزانية"


def c_div_yield_risk(item):
    """عائد التوزيع مقارنة بالمخاطرة."""
    dy = _f(item.get("div_yield"))
    risk = _axis(item, "risk")
    if dy is None or risk is None:
        return None
    r = _clamp(dy / 12.0) * 0.6 + _clamp(risk / 100.0) * 0.4
    return _clamp(r), {"div_yield": dy, "risk": risk}, "العائد مقابل مستوى المخاطر"


def c_div_events(item):
    """مخاطر الأحداث والاستحقاقات."""
    risk = _axis(item, "risk")
    news = _f(item.get("news_score"))
    if risk is None and news is None:
        return None
    r = 0.5
    if risk is not None:
        r = r * 0.6 + _clamp(risk / 100.0) * 0.4
    if news is not None:
        r = r * 0.7 + _clamp(news / 100.0) * 0.3
    return _clamp(r), {"risk": risk, "news_score": news}, "سلامة الأحداث والمستحقاقات"


def c_growth_mix(item):
    """مزيج النمو والدخل."""
    g = c_growth(item)
    dy = _f(item.get("div_yield"))
    if g is None and dy is None:
        return None
    rg = g[0] if g else 0.5
    rd = _clamp(dy / 12.0) if dy is not None else 0.3
    return _clamp(rg * 0.6 + rd * 0.4), {"growth": rg, "div_yield": dy}, \
        "توازن النمو والدخل"


def c_risk_stability(item):
    """استقرار المخاطر — من محور المخاطرة والتقلب."""
    risk = _axis(item, "risk")
    vol = _f(item.get("vol1y"))
    if risk is None and vol is None:
        return None
    r = 0.5
    if risk is not None:
        r = _clamp(risk / 100.0)
    if vol is not None:
        r = r * 0.7 + _clamp(1.0 - vol / 80.0) * 0.3
    return _clamp(r), {"risk": risk, "vol1y": vol}, "ثبات المخاطر عبر الوقت"


def c_cash_stability(item):
    """استقرار التدفقات النقدية."""
    cf = c_cfo(item)
    nm = _f(item.get("net_margin"))
    if cf is None and nm is None:
        return None
    rc = cf[0] if cf else 0.5
    rn = _clamp((nm + 5.0) / 35.0) if nm is not None else 0.5
    return _clamp(rc * 0.6 + rn * 0.4), {"cfo_ratio": rc, "net_margin": nm}, \
        "ثبات التدفق النقدي"


def c_volatility(item):
    """التقلبات والتراجعات التاريخية."""
    vol = _f(item.get("vol1y"))
    mdd = _f(item.get("mdd1y"))
    if vol is None and mdd is None:
        return None
    r = 0.5
    if vol is not None:
        r -= max(0.0, (vol - 20.0)) / 60.0
    if mdd is not None:
        r -= max(0.0, (abs(mdd) - 20.0)) / 60.0
    return _clamp(r), {"vol1y": vol, "mdd1y": mdd}, "التقلبات وأكبر تراجع"


def c_aggressive_momentum(item):
    m = c_momentum(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.1), m[1], "زخم مكثّف على أفق قصير"


def c_aggressive_catalyst(item):
    m = c_catalyst(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.1), m[1], "محفزات وأحداث مكثّفة"


def c_aggressive_liquidity(item):
    m = c_liquidity(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "سيولة تكفي لدخول وخروج سريع"


def c_aggressive_structure(item):
    m = c_structure(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "تكوين فني قوي"


def c_aggressive_rr(item):
    m = c_rr(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "عائد محتمل أعلى مقابل مخاطرة أعلى"


CRITERIA_SCORERS = {
    "trend": c_trend,
    "momentum": c_momentum,
    "liquidity": c_liquidity,
    "structure": c_structure,
    "rr": c_rr,
    "news": c_news,
    "fund_quality": c_fund_quality,
    "growth": c_growth,
    "catalyst": c_catalyst,
    "valuation": c_valuation,
    "funds": c_funds,
    "returns": c_returns,
    "cfo": c_cfo,
    "safety_margin": c_safety_margin,
    "governance": c_governance,
    "debt": c_debt,
    "growth_profit": c_growth_profit,
    "reinvest": c_reinvest,
    "margins": c_margins,
    "div_regular": c_div_regular,
    "div_cover": c_div_cover,
    "balance": c_balance,
    "div_yield_risk": c_div_yield_risk,
    "div_events": c_div_events,
    "growth_mix": c_growth_mix,
    "risk_stability": c_risk_stability,
    "cash_stability": c_cash_stability,
    "volatility": c_volatility,
    "aggressive_momentum": c_aggressive_momentum,
    "aggressive_catalyst": c_aggressive_catalyst,
    "aggressive_liquidity": c_aggressive_liquidity,
    "aggressive_structure": c_aggressive_structure,
    "aggressive_rr": c_aggressive_rr,
}

ARABIC_GRADES = (
    (85.0, "مطابقة مرتفعة"),
    (70.0, "مطابقة جيدة"),
    (55.0, "مطابقة متوسطة"),
    (0.0, "مطابقة ضعيفة"),
)


def _grade(score):
    for thr, name in ARABIC_GRADES:
        if score >= thr:
            return name
    return "مطابقة ضعيفة"


def _risk_label(item):
    rl = item.get("risk_level")
    if rl:
        return str(rl)
    v = _axis(item, "risk")
    if v is None:
        return "غير متاح"
    if v >= 70:
        return "منخفض"
    if v >= 50:
        return "متوسط"
    if v >= 30:
        return "مرتفع"
    return "مرتفع جداً"


def evaluate_item(item):
    """يحسب كل المعايير لسهم واحد ⇒ نتيجة مشتركة لكل الاستراتيجيات.

    ⛔ النتيجة: {criterion_key: {ratio, evidence, note_ar}} + ملخّص التغطية.
    """
    out = {}
    for key, fn in CRITERIA_SCORERS.items():
        try:
            res = fn(item)
        except Exception:
            res = None
        if res is None:
            out[key] = {"ratio": None, "evidence": {}, "note_ar": None}
        else:
            ratio, ev, note = res
            out[key] = {"ratio": ratio, "evidence": ev or {}, "note_ar": note}
    return out


def evaluate_strategy(item, strategy, crit):
    """يحسب نتيجة السهم في استراتيجية واحدة.

    📌 الأوزان والعتبات من ملف التعريفات (الخادم بس).
    📌 النتيجة: score (0..100) · coverage · missing · reasons مبسّطة.
    """
    crit_defs = strategy.get("criteria") or []
    total_w = sum(float(c.get("weight") or 0) for c in crit_defs) or 1.0
    got_w = 0.0
    pts = 0.0
    missing = []
    public_crit = []
    for c in crit_defs:
        k = c.get("key")
        w = float(c.get("weight") or 0)
        r = (crit.get(k) or {}).get("ratio")
        if r is None:
            missing.append(c.get("label_ar") or k)
            public_crit.append({"key": k, "label_ar": c.get("label_ar"),
                                "ratio": None, "note_ar": (crit.get(k) or {}).get("note_ar")})
            continue
        got_w += w
        pts += r * w
        public_crit.append({"key": k, "label_ar": c.get("label_ar"),
                            "ratio": round(r, 4),
                            "note_ar": (crit.get(k) or {}).get("note_ar")})
    coverage = round((got_w / total_w) * 100.0, 1)
    score = round((pts / total_w) * 100.0, 1)

    # ⛔Reasons مبسّطة — من غير الأوزان ولا نقاط Maximال (سرّية)
    reasons = []
    for pc in public_crit:
        if pc.get("ratio") is None:
            continue
        pct = round(pc["ratio"] * 100)
        label = pc.get("label_ar") or ""
        if pct >= 80:
            reasons.append(f"{label}: مطابقة قوية ({pct}٪).")
        elif pct >= 55:
            reasons.append(f"{label}: مطابقة مقبولة ({pct}٪).")
        else:
            reasons.append(f"{label}: مطابقة ضعيفة ({pct}٪).")
    reasons = reasons[:4]

    # ⛔ الأهلية: مخاطرة أساسية غير كافية ⇒ مش «فرصة مؤكدة»
    risk_ok = _axis(item, "risk") is not None
    # ⛔ min_liquidity_value **قيمة نقدية** (حجم تداول بالجنيه) — مش
    #    درجة السيولة 0..100. ⇒ نقارنها بقيمة التداول الفعلية.
    liq_min = float(strategy.get("min_liquidity_value") or 0)
    liq_value = None
    _vol = _f(item.get("vol_60"))
    if _vol is None:
        _vol = _f(item.get("volume"))
    _px = _f(item.get("price"))
    if _vol is not None and _px is not None:
        liq_value = _vol * _px
    if liq_min:
        liq_ok = (liq_value is not None and liq_value >= liq_min)
    else:
        liq_ok = True
    cov_min = float(strategy.get("min_coverage") or 0)
    cov_ok = coverage >= cov_min
    exclusion = None
    if not risk_ok:
        exclusion = "بيانات المخاطر غير كافية"
    elif not liq_ok:
        exclusion = "حجم التداول أقل من الحد المطلوب"
    elif not cov_ok:
        exclusion = "تغطية البيانات أقل من الحد المطلوب"
    return {
        "score": score,
        "coverage": coverage,
        "available_weight": round(got_w, 1),
        "missing": missing,
        "reasons": reasons,
        "criteria": public_crit,
        "eligible": exclusion is None,
        "exclusion": exclusion,
        "grade_ar": _grade(score),
        "risk_level_ar": _risk_label(item),
        "risk_score": _axis(item, "risk"),
        "hold_days": strategy.get("horizon_ar"),
        "state": "watch" if exclusion is None else "excluded",
    }


def public_strategy(strategy):
    """النسخة العامة من الاستراتيجية ⛔ بدون الأوزان والعتبات."""
    return {
        "key": strategy.get("key"),
        "name_ar": strategy.get("name_ar"),
        "group": strategy.get("group"),
        "icon": strategy.get("icon"),
        "horizon_ar": strategy.get("horizon_ar"),
        "horizon_days": strategy.get("horizon_days"),
        "definition_ar": strategy.get("definition_ar"),
        "looks_for_ar": strategy.get("looks_for_ar"),
        "accept_ar": strategy.get("accept_ar") or [],
        "reject_ar": strategy.get("reject_ar") or [],
        "risk_ar": strategy.get("risk_ar") or [],
        "invalidation_ar": strategy.get("invalidation_ar") or [],
        # ⛔ criteria بدون weight/points_max (سرّية)
        "criteria": [{"key": c.get("key"), "label_ar": c.get("label_ar"),
                      "hint_ar": c.get("hint_ar"), "not_ar": c.get("not_ar")}
                     for c in (strategy.get("criteria") or [])],
        "pro_only": strategy.get("key") in OPP_PRO_STRATEGIES,
    }


def build_payload(stocks, definitions=None, meta=None):
    """يبني payload الفرص الكامل من البيانات الحيّة.

    📌 stocks: قائمة عناصر فيها كل الحقول (من دورة التحديث).
    📌 meta: generated_at · source · freshness
    """
    defs = definitions or load_definitions()
    strategies = defs.get("strategies") or []
    meta = meta or {}
    lists = {}
    for st in strategies:
        key = st.get("key")
        rows = []
        excluded = []
        for item in stocks:
            crit = item.get("_opp_criteria")
            if crit is None:
                crit = evaluate_item(item)
                item["_opp_criteria"] = crit
            ev = evaluate_strategy(item, st, crit)
            row = {
                "code": item.get("code"),
                "name": item.get("name"),
                "sector": item.get("sector") or "—",
                "price": item.get("price"),
                "price_label": "سعر إغلاق",
                "session_date": str(item.get("session_date") or item.get("ts") or "")[:10],
                "change": item.get("change"),
                "score": ev["score"],
                "coverage": ev["coverage"],
                "available_weight": ev["available_weight"],
                "missing": ev["missing"],
                "grade_ar": ev["grade_ar"],
                "risk_level_ar": ev["risk_level_ar"],
                "risk_score": ev["risk_score"],
                "hold_days": ev["hold_days"],
                "state": ev["state"],
                "reasons": ev["reasons"],
                "criteria": ev["criteria"],
                "eligible": ev["eligible"],
                "exclusion": ev["exclusion"],
            }
            if ev["eligible"]:
                rows.append(row)
            else:
                excluded.append({"code": row["code"], "exclusion": ev["exclusion"]})
        rows.sort(key=lambda r: -(r["score"] or 0))
        limit = OPP_LIMIT_PER_STRATEGY or len(rows)
        lists[key] = {
            "strategy": key,
            "strategy_name_ar": st.get("name_ar"),
            "model_version": defs.get("model_version"),
            "total": len(stocks),
            "eligible": len(rows),
            "excluded": len(excluded),
            "returned": min(len(rows), limit),
            "limit": limit,
            "excluded_codes": [e["code"] for e in excluded][:80],
            "exclusions": excluded[:80],
            "items": rows[:limit],
            "generated_at": meta.get("generated_at"),
            "source": meta.get("source") or "live",
            "freshness": meta.get("freshness") or "unknown",
        }
    return {
        "ok": True,
        "model_version": defs.get("model_version"),
        "generated_at": meta.get("generated_at"),
        "source": meta.get("source") or "live",
        "freshness": meta.get("freshness") or "unknown",
        "note_ar": "محسوبة من البيانات الحيّة — بتتحدّث مع كل دورة تحديث.",
        "strategies": [public_strategy(s) for s in strategies],
        "lists": lists,
    }
