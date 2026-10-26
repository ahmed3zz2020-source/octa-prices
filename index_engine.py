#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧮 محرك تحليل المؤشرات — ٢٦ أكتوبر ٢٠٢٦
═══════════════════════════════════════════════════════════════════════════

📌 responsibility واحدة: تحسب كل الأرقام من **سلسلة إغلاقات حقيقية**.
📌 ⛔ ممنوع أي رقم مخترع — لو البيانات ناقصة، الحقل بيبقى None (مش 0).
📌 ⛔ منفصل تماماً عن طبقة العرض (الواجهة) — عشان نقدر نختبره لوحده.

📌 الحسابات:
   · عائد الفترة            (نهاية/بداية − ١) × ١٠٠
   · التغير المطلق          نهاية − بداية
   · المؤشر المطبّع         (القيمة ÷ بداية الفترة) × ١٠٠
   · أقصى هبوط (Drawdown)   أكبر انخفاض من قمة سابقة إلى قاع لاحق
   · التعافي                هل رجع القمة؟ ومتى؟ ومنذ إيه؟
   · التقلب (Volatility)    الانحراف المعياري للعيائد اليومية × √٢٥٢
   · المراحل                اكتشاف آلي للترند/التصحيح/التعافي
   · حالة السوق (Regime)   تصنيف آلي من عدة مؤشرات
   · الإحصائيات             أعلى/أقل/متوسط/عدد الفترات الصاعدة

📌 كل الدوال نقية (Pure) — مفيش I/O جواها — عشان نختبرها بسهولة.
"""

import math
import json
import os

# ════════════════════════════════════════════════════════════════
#  ثوابت
# ════════════════════════════════════════════════════════════════
TRADING_DAYS = 252          # أيام التداول في السنة (البورصة المصرية)
DRAWDOWN_MAJOR = -20.0      # هبوط حاد  (حد افتراضي — قابل للضبط)
DRAWDOWN_CORRECTION = -10.0 # تصحيح   (حد افتراضي — قابل للضبط)
MIN_PHASE_DAYS = 20         # أقل مدة لمرحلة تُحتسب (بالعامل)
PHASE_EDGE = 0.03           # ٣٪ —無視 ضوضاء


# ════════════════════════════════════════════════════════════════
#  أدوات أساسية
# ════════════════════════════════════════════════════════════════
def _f(v, default=None):
    """تحويل آمن للرقم — NaN/Inf بيبقوا None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    return x


def period_return(start, end):
    """عائد الفترة % — أو None لو القيم ناقصة/صفر."""
    s, e = _f(start), _f(end)
    if s is None or e is None or s == 0:
        return None
    return round((e / s - 1.0) * 100.0, 2)


def absolute_change(start, end):
    s, e = _f(start), _f(end)
    if s is None or e is None:
        return None
    return round(e - s, 4)


def normalize(series, base=100.0):
    """يطبّع السلسلة على نقطة بداية = base."""
    if not series:
        return []
    first = _f(series[0][1])
    if first is None or first == 0:
        return []
    return [[t, round((_f(v) / first) * base, 4)] for t, v in series if _f(v) is not None]


def drawdown_series(series):
    """سلسلة الانسحاب من القمة: كل نقطة = (القيمة ÷ قمة سابقة) − ١."""
    out = []
    peak = None
    for t, v in series:
        v = _f(v)
        if v is None:
            continue
        if peak is None or v > peak:
            peak = v
        out.append([t, round((v / peak - 1.0) * 100.0, 4) if peak else 0.0])
    return out


def max_drawdown(series):
    """أكبر هبوط: {pct, peak, trough, peak_ts, trough_ts}."""
    if not series:
        return None
    peak = None
    peak_ts = None
    best = {"pct": 0.0, "peak": None, "trough": None, "peak_ts": None, "trough_ts": None}
    for t, v in series:
        v = _f(v)
        if v is None:
            continue
        if peak is None or v > peak:
            peak, peak_ts = v, t
        dd = (v / peak - 1.0) * 100.0 if peak else 0.0
        if dd < best["pct"]:
            best = {"pct": round(dd, 2), "peak": round(peak, 4), "trough": round(v, 4),
                    "peak_ts": peak_ts, "trough_ts": t}
    return best


def recovery(series):
    """التعافي: هل رجع القمة؟ متى؟ ومنذ إيه؟
    ⛔ لو مش رجع ⇒ recovered=False و recovery_date=None (مفيش تاريخ مخترع)."""
    if not series:
        return None
    md = max_drawdown(series)
    if not md or md["pct"] >= 0:
        return {"recovered": True, "recovery_date": None, "days_to_recover": None,
                "underwater_days": 0, "drawdown_pct": 0.0, "peak": None, "trough": None}
    peak_ts, trough_ts = md["peak_ts"], md["trough_ts"]
    peak_v = _f(md["peak"])
    rec_ts = None
    for t, v in series:
        if t is None or t <= trough_ts:
            continue
        vv = _f(v)
        if vv is not None and peak_v is not None and vv >= peak_v:
            rec_ts = t
            break
    idx_peak = idx_tr = idx_rec = None
    for i, (t, _v) in enumerate(series):
        if t == peak_ts:
            idx_peak = i
        if t == trough_ts:
            idx_tr = i
    if rec_ts is not None:
        for i, (t, _v) in enumerate(series):
            if t == rec_ts:
                idx_rec = i
                break
    days_peak_to_trough = (idx_tr - idx_peak) if (idx_peak is not None and idx_tr is not None) else None
    days_to_recover = (idx_rec - idx_peak) if (idx_rec is not None and idx_peak is not None) else None
    return {
        "recovered": rec_ts is not None,
        "recovery_date": rec_ts,
        "days_peak_to_trough": days_peak_to_trough,
        "days_to_recover": days_to_recover,
        "underwater_days": (len(series) - 1 - idx_tr) if idx_tr is not None else None,
        "drawdown_pct": md["pct"],
        "peak": md["peak"],
        "trough": md["trough"],
    }


def volatility(series, window=30, annualize=True):
    """التقلب التاريخي: انحراف معياري للعيائد اليومية (moving window).
    📌 ملاحظة مهمة: التقلب مش احتمال خسارة — بيقيس تشتت العوائد."""
    if len(series) < window + 2:
        return None
    rets = []
    for i in range(1, len(series)):
        a, b = _f(series[i - 1][1]), _f(series[i][1])
        if a and b and a != 0:
            rets.append(b / a - 1.0)
    if len(rets) < window + 1:
        return None
    out = []
    for i in range(window, len(rets) + 1):
        w = rets[i - window:i]
        m = sum(w) / len(w)
        var = sum((x - m) ** 2 for x in w) / (len(w) - 1) if len(w) > 1 else 0.0
        sd = math.sqrt(var)
        if annualize:
            sd *= math.sqrt(TRADING_DAYS)
        out.append(round(sd * 100.0, 2))
    if not out:
        return None
    return {"latest": out[-1], "avg": round(sum(out) / len(out), 2),
            "min": min(out), "max": max(out), "window": window, "annualized": annualize}


def sma(series, n):
    """متوسط متحرك simple — آخر n قيمة."""
    if len(series) < n or n <= 0:
        return None
    vals = [_f(v) for _t, v in series[-n:]]
    if any(v is None for v in vals):
        return None
    return round(sum(vals) / len(vals), 4)


def rsi(series, n=14):
    """RSI بسيط."""
    if len(series) < n + 1:
        return None
    gains, losses = 0.0, 0.0
    vals = [_f(v) for _t, v in series]
    for i in range(len(vals) - n, len(vals)):
        d = vals[i] - vals[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = (gains / n) / (losses / n)
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


# ════════════════════════════════════════════════════════════════
#  اكتشاف المراحل — آلي بالكامل من البيانات
# ════════════════════════════════════════════════════════════════
def _zigzag(vals, threshold_pct=PHASE_EDGE * 100):
    """نقاط التبديل (قمم وقيعان) بطريقة الـzigzag.
    📌 بيشيل الضوضاء: أي حركة أصغر من العتبة بتعتبر جزء من الاتجاه.
    📌 ⛔ مفيش تفسير — كل نقطة من البيانات الحقيقية."""
    if len(vals) < 3:
        return []
    pivots = []
    direction = 0
    last_pivot_i, last_pivot_v = 0, vals[0][1]
    extreme_i, extreme_v = 0, vals[0][1]
    for i in range(1, len(vals)):
        v = vals[i][1]
        if direction >= 0:
            if v > extreme_v:
                extreme_i, extreme_v = i, v
            drop = ((extreme_v - v) / extreme_v * 100.0) if extreme_v else 0.0
            if drop >= threshold_pct and direction != -1:
                pivots.append((extreme_i, extreme_v, "peak"))
                direction = -1
                extreme_i, extreme_v = i, v
                last_pivot_i, last_pivot_v = i, v
        if direction <= 0:
            if v < extreme_v:
                extreme_i, extreme_v = i, v
            rise = ((v - extreme_v) / extreme_v * 100.0) if extreme_v else 0.0
            if rise >= threshold_pct and direction != 1:
                pivots.append((extreme_i, extreme_v, "trough"))
                direction = 1
                extreme_i, extreme_v = i, v
                last_pivot_i, last_pivot_v = i, v
    if pivots:
        li = len(vals) - 1
        pivots.append((li, vals[li][1], "peak" if direction >= 0 else "trough"))
    return pivots


def detect_phases(series, major=DRAWDOWN_MAJOR, correction=DRAWDOWN_CORRECTION,
                  min_days=MIN_PHASE_DAYS, min_abs_return=10.0):
    """بيقسّم السلسلة إلى مراحل: صعود / هبوط / تصحيح / تذبذب.
    📌 القواعد رقمية وقابلة للضبط — مش تصنيف يدوي.
    📌 ⛔ أي مرحلة لازم تستوفي الحد الأدنى للمدة."""
    if not series or len(series) < min_days + 2:
        return []
    vals = [(t, _f(v)) for t, v in series]
    vals = [(t, v) for t, v in vals if v is not None]
    if len(vals) < min_days + 2:
        return []

    pivots = _zigzag(vals)
    if len(pivots) < 2:
        return []

    phases = []
    for k in range(len(pivots) - 1):
        (i0, v0, k0), (i1, v1, k1) = pivots[k], pivots[k + 1]
        days = i1 - i0
        if days < min_days:
            continue
        ret = period_return(v0, v1)
        if ret is None:
            continue
        seg = vals[i0:i1 + 1]
        md = max_drawdown(seg) or {"pct": 0.0}
        if k0 == "peak" and k1 == "trough":
            kind = "major_drawdown" if md["pct"] <= major else (
                "correction" if md["pct"] <= correction else "consolidation")
        elif k0 == "trough" and k1 == "peak":
            kind = "uptrend"
        else:
            kind = "consolidation"
        # ⛔ نتجاهل المراحل اللي movement بتاعها مش مؤثر (مش كل fluctuation مرحلة)
        if kind != "major_drawdown" and abs(ret) < min_abs_return:
            continue
        phases.append(_phase(
            vals[i0][0], vals[i1][0], v0, v1, kind, ret,
            peak_ts=(vals[i0][0] if k0 == "peak" else vals[i1][0]),
            peak_value=(v0 if k0 == "peak" else v1),
            trough_ts=(vals[i1][0] if k1 == "trough" else vals[i0][0]),
            trough_value=(v1 if k1 == "trough" else v0),
            days=days, recovered=None, dd=md["pct"]))
    return phases


def _phase(start_ts, end_ts, start_v, end_v, kind, ret, peak_ts=None, peak_value=None,
           trough_ts=None, trough_value=None, days=None, recovered=None, dd=None):
    return {
        "start": start_ts, "end": end_ts,
        "start_value": round(_f(start_v, 0) or 0, 4), "end_value": round(_f(end_v, 0) or 0, 4),
        "kind": kind, "return_pct": ret, "days": days,
        "peak_ts": peak_ts, "peak_value": round(_f(peak_value, 0) or 0, 4) if peak_value is not None else None,
        "trough_ts": trough_ts, "trough_value": round(_f(trough_value, 0) or 0, 4) if trough_value is not None else None,
        "max_drawdown_pct": dd, "recovered": recovered,
    }


# ════════════════════════════════════════════════════════════════
#  حالة السوق (Regime) — آلي من عدة مؤشرات
# ════════════════════════════════════════════════════════════════
def market_regime(series):
    """يصنّف حالة المؤشر الحالي. ⛔ مش تنبؤ بالمستقبل.
    📌 لو المؤشرات متعارضة ⇒ "uncertain" (مش بنفرض رأي)."""
    if not series or len(series) < 60:
        return {"regime": "uncertain", "confidence": 0, "reasons": ["البيانات التاريخية غير كافية للحساب"],
                "signals": {}, "as_of": None}

    last_v = _f(series[-1][1])
    s20, s50, s200 = sma(series, 20), sma(series, 50), sma(series, 200)
    r14 = rsi(series, 14)
    vol = volatility(series, 30)
    md = max_drawdown(series)
    m1 = period_return(series[0][1], series[-1][1])
    m3 = period_return(series[min(len(series) - 1, 63)][1], series[-1][1])
    m12 = period_return(series[min(len(series) - 1, 252)][1], series[-1][1])

    signals = {
        "above_sma20": None if s20 is None else bool(last_v > s20),
        "above_sma50": None if s50 is None else bool(last_v > s50),
        "above_sma200": None if s200 is None else bool(last_v > s200),
        "sma50_rising": None if (s50 is None or sma(series[:-5], 50) is None) else bool(s50 > sma(series[:-5], 50)),
        "sma200_rising": None if (s200 is None or sma(series[:-10], 200) is None) else bool(s200 > sma(series[:-10], 200)),
        "rsi14": r14,
        "volatility_30d": None if vol is None else vol["latest"],
        "max_drawdown": None if md is None else md["pct"],
        "return_1m": m1, "return_3m": m3, "return_12m": m12,
    }

    up = sum(1 for k in ("above_sma20", "above_sma50", "above_sma200", "sma50_rising", "sma200_rising")
             if signals.get(k) is True)
    dn = sum(1 for k in ("above_sma20", "above_sma50", "above_sma200", "sma50_rising", "sma200_rising")
             if signals.get(k) is False)
    bullish = (m12 is not None and m12 > 0) or (m3 is not None and m3 > 0)
    bearish = (m12 is not None and m12 < 0) or (m3 is not None and m3 < 0)

    reasons = []
    if signals["above_sma50"] is True:
        reasons.append("المؤشر أعلى من متوسطه المتحرك (50 يوم).")
    if signals["above_sma50"] is False:
        reasons.append("المؤشر تحت متوسطه المتحرك (50 يوم).")
    if signals["sma50_rising"] is True:
        reasons.append("اتجاه المتوسط المتحرك (50 يوم) لأعلى.")
    if signals["sma50_rising"] is False:
        reasons.append("اتجاه المتوسط المتحرك (50 يوم) لأسفل.")
    if r14 is not None:
        if r14 > 70:
            reasons.append("مؤشر القوة النسبية (RSI) فوق 70 — منطقة تشبع شرائي.")
        elif r14 < 30:
            reasons.append("مؤشر القوة النسبية (RSI) تحت 30 — منطقة تشبع بيعي.")
        else:
            reasons.append("مؤشر القوة النسبية (RSI) في المنطقة المحايدة (%.0f)." % r14)
    if md is not None and md["pct"] <= DRAWDOWN_MAJOR:
        reasons.append("المؤشر لسه تعافى من هبوط %.1f%% من قمته." % abs(md["pct"]))

    conflict = (up > 0 and dn > 0)
    if conflict and up == dn:
        regime, conf = "uncertain", 40
    elif up >= 4 and bullish and not bearish:
        regime, conf = ("strong_uptrend" if (m12 is not None and m12 > 15) else "uptrend"), min(95, 55 + up * 8)
    elif dn >= 4 and bearish and not bullish:
        regime, conf = ("strong_downtrend" if (m12 is not None and m12 < -15) else "downtrend"), min(95, 55 + dn * 8)
    elif conflict:
        regime, conf = "uncertain", 45
    elif up > dn:
        regime, conf = "uptrend", 60
    elif dn > up:
        regime, conf = "downtrend", 60
    else:
        regime, conf = "sideways", 50

    if vol is not None and vol["latest"] >= 25:
        regime = "high_volatility"
        reasons.append("التقلب الشهري %.1f%% — أعلى من المعتاد." % vol["latest"])
        conf = min(conf, 70)

    if not reasons:
        reasons.append("المؤشرات متقاربة — الاتجاه غير واضح.")

    return {"regime": regime, "confidence": conf, "reasons": reasons[:5],
            "signals": signals, "as_of": series[-1][0]}


# ════════════════════════════════════════════════════════════════
#  إحصائيات الفترة
# ════════════════════════════════════════════════════════════════
def period_stats(series):
    """كل إحصائيات الفترة — من البيانات الحقيقية بس."""
    if not series:
        return None
    vals = [_f(v) for _t, v in series]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    rets = []
    for i in range(1, len(series)):
        a, b = _f(series[i - 1][1]), _f(series[i][1])
        if a and b and a != 0:
            rets.append(b / a - 1.0)
    pos = sum(1 for r in rets if r > 0)
    neg = sum(1 for r in rets if r < 0)
    flat = len(rets) - pos - neg
    md = max_drawdown(series)
    return {
        "start": series[0][0], "end": series[-1][0],
        "start_value": round(vals[0], 4), "end_value": round(vals[-1], 4),
        "high": round(max(vals), 4), "low": round(min(vals), 4),
        "avg": round(sum(vals) / len(vals), 4),
        "return_pct": period_return(vals[0], vals[-1]),
        "abs_change": absolute_change(vals[0], vals[-1]),
        "max_drawdown": md,
        "volatility": volatility(series, 30),
        "recovery": recovery(series),
        "positive_periods": pos, "negative_periods": neg, "flat_periods": flat,
        "observations": len(series),
    }


def slice_by_range(series, start_ts, end_ts):
    if not series:
        return []
    return [[t, v] for t, v in series if (start_ts is None or t >= start_ts) and (end_ts is None or t <= end_ts)]


def slice_by_days(series, days):
    if not series or not days:
        return list(series)
    last = series[-1][0]
    return [[t, v] for t, v in series if t >= last - days * 86400]


def validate_series(series):
    """فحص جودة السلسلة: تواريخ مكررة، قيم ناقصة، فجوات كبيرة."""
    issues = []
    if not series:
        return {"ok": False, "issues": ["السلسلة فاضية"], "dupes": 0, "gaps": 0, "nulls": 0}
    seen = set()
    dupes = 0
    nulls = 0
    days = []
    for t, v in series:
        if t in seen:
            dupes += 1
        seen.add(t)
        if _f(v) is None:
            nulls += 1
        else:
            days.append(t)
    days.sort()
    gaps = 0
    big = []
    for i in range(1, len(days)):
        d = (days[i] - days[i - 1]) / 86400.0
        if d > 10:
            gaps += 1
            big.append(round(d, 1))
    if dupes:
        issues.append("%d تاريخ مكرر" % dupes)
    if nulls:
        issues.append("%d قيمة ناقصة" % nulls)
    if gaps:
        issues.append("%d فجوة كبيرة (أكبرها %s يوم)" % (gaps, max(big) if big else "?"))
    return {"ok": not issues, "issues": issues, "dupes": dupes, "gaps": gaps,
            "nulls": nulls, "big_gaps": big[:10]}


if __name__ == "__main__":
    # اختبار سريع ذاتي
    s = [[i, 100 + i] for i in range(300)]
    assert period_return(100, 110) == 10.0
    assert period_return(0, 110) is None
    assert normalize(s)[0][1] == 100.0
    md = max_drawdown([[0, 100], [1, 120], [2, 90], [3, 130]])
    assert abs(md["pct"] - (-25.0)) < 0.01, md
    rec = recovery([[0, 100], [1, 120], [2, 90], [3, 130]])
    assert rec["recovered"] is True
    assert recovery([[0, 100], [1, 120], [2, 90]])["recovered"] is False
    v = volatility(s)
    assert v is None or v["latest"] >= 0
    r = market_regime(s)
    assert r["regime"]
    ph = detect_phases(s)
    print("✅ اختبارات المحرك نجحت")
    print("   drawdown:", md)
    print("   recovery:", rec["recovered"], rec["days_to_recover"])
    print("   regime:", r["regime"], r["confidence"])
    print("   phases:", len(ph))
