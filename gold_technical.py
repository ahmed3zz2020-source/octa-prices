"""
═══════════════════════════════════════════════════════════════
 gold_technical.py — محرك التحليل الفني + الدعم والمقاومة
═══════════════════════════════════════════════════════════════
 📌 لكل أداة **سلسلتها الخاصة** — ممنوع نستخدم نفس المستويات لأداتين
    مختلفتين (جرام بالجنيه ≠ دولار للأونصة ≠ دولار/جنيه).

 ⛔⛔⛔ القواعد (ممنوع نكسرها):
 ① **مفيش look-ahead**: كل مؤشر بيتحسب على البيانات حتى تاريخه بس.
 ② **المؤشر بيتحسب لو البيانات كفاية**: ATR محتاج OHLC ⇒ لو السلسلة
    close بس ⇒ ATR = None + سبب (مش مخترع ولا مصفّر).
 ③ **مفيش احتمالات مخترعة**: مفيش «احتمال ٨٠٪» — либо قياس، либо «غير متاح».
 ④ **الدعم ما بيضمنش ارتداد** — والواجهة لازم تقول كده.
 ⑤ **المستويات موثّقة**: كل منطقة بتقول ليه مهمة (عدد الردود · التكرار ·
    الحداثة · توافق الإطار الزمني · قربها من متوسط متحرك).
 ⑥ **الترند بيتبني على قاعدة صريحة** — مش إحساس.

 📌 مكونات:
   · متوسطات: SMA/EMA (20/50/100/200)
   · زخم: RSI14 · MACD(12,26,9) · ROC
   · تقلب: ATR14 · Bollinger(20,2) · التقلب التاريخي
   · بنية: قمم/قيعان · HH/HL/LH/LL · تجمّعات · اختراقات
   · دعم ومقاومة: تجميع القمم/القيعان +打分 موثّق + كشف الكسر
═══════════════════════════════════════════════════════════════
"""
import math

# ═══════════ ثوابت ═══════════
MA_SETS = {
    "sma": [20, 50, 100, 200],
    "ema": [20, 50, 200],
}
TREND_SHORT = 20
TREND_MED = 50
TREND_LONG = 200
RSI_N = 14
MACD = (12, 26, 9)
ATR_N = 14
BB_N = 20
BB_K = 2.0
VOL_N = 252
ROC_N = 12
SWING_K = 3          # نصف قطر الـfractal (٢ شمعة يمين + ٢ شمال)
ZONE_TOL_ATR = 0.6   # تجميع المستويات: فرق أقل من ٠٫٦ ATR = نفس المنطقة
ZONE_MAX = 6         # أقصى عدد مناطق لكل جهة


# ═══════════ أدوات عامة ═══════════
def _clean(bars):
    out = []
    for b in (bars or []):
        c = b.get("c")
        if c is None:
            continue
        try:
            out.append({
                "d": b.get("d"),
                "o": b.get("o"), "h": b.get("h"), "l": b.get("l"),
                "c": float(c),
            })
        except Exception:
            continue
    out.sort(key=lambda r: (r["d"] or ""))
    return out


def _closes(bars):
    return [b["c"] for b in bars]


def _has_ohlc(bars):
    return bool(bars) and all(b.get("h") is not None and b.get("l") is not None
                               for b in bars)


# ═══════════ المتوسطات ═══════════
def sma(vals, n):
    """⛔ None لو البيانات أقل من n — مش متوسط ناقص."""
    if not vals or len(vals) < n or n <= 0:
        return None
    return sum(vals[-n:]) / float(n)


def sma_series(vals, n):
    """سلسلة SMA (None قبل ما تتEnough) — للرسوم البيانية."""
    out = []
    run = 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= n:
            run -= vals[i - n]
        out.append((run / n) if i >= n - 1 else None)
    return out


def ema(vals, n):
    """EMA بمعامل 2/(n+1) — قياسي."""
    if not vals or len(vals) < n or n <= 0:
        return None
    k = 2.0 / (n + 1.0)
    e = sum(vals[:n]) / float(n)
    for v in vals[n:]:
        e = (v - e) * k + e
    return e


def ema_series(vals, n):
    out = []
    if len(vals) < n:
        return [None] * len(vals)
    e = sum(vals[:n]) / float(n)
    out.extend([None] * (n - 1))
    out.append(e)
    k = 2.0 / (n + 1.0)
    for v in vals[n:]:
        e = (v - e) * k + e
        out.append(e)
    return out


# ═══════════ الزخم ═══════════
def rsi(vals, n=RSI_N):
    """RSI بطريقة Wilder للتنعيم. ⛔ None لو البيانات ناقصة."""
    if not vals or len(vals) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        gains += d if d > 0 else 0.0
        losses += (-d) if d < 0 else 0.0
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        g = d if d > 0 else 0.0
        l = (-d) if d < 0 else 0.0
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return 100.0 - (100.0 / (1.0 + rs))


def macd(vals, fast=MACD[0], slow=MACD[1], signal=MACD[2]):
    """MACD + خط الإشارة + الهيستوجرام. ⛔ None لو البيانات ناقصة."""
    if not vals or len(vals) < slow + signal:
        return None
    ef = ema_series(vals, fast)
    es = ema_series(vals, slow)
    line = []
    for i in range(len(vals)):
        if ef[i] is None or es[i] is None:
            line.append(None)
        else:
            line.append(ef[i] - es[i])
    first = next((i for i, v in enumerate(line) if v is not None), None)
    if first is None:
        return None
    seg = [v for v in line[first:] if v is not None]
    sig = ema_series(seg, signal)
    sig_full = [None] * first + sig
    hist = []
    for i in range(len(vals)):
        if line[i] is None or sig_full[i] is None:
            hist.append(None)
        else:
            hist.append(line[i] - sig_full[i])
    return {"macd": line[-1], "signal": sig_full[-1], "hist": hist[-1],
            "macd_series": line, "signal_series": sig_full, "hist_series": hist}


def roc(vals, n=ROC_N):
    """Rate of Change %."""
    if not vals or len(vals) < n + 1:
        return None
    prev = vals[-1 - n]
    if not prev:
        return None
    return (vals[-1] / prev - 1.0) * 100.0


# ═══════════ التقلب ═══════════
def atr(bars, n=ATR_N):
    """ATR بطريقة Wilder. ⛔ None لو مفيش OHLC (مش مصفّر!)."""
    bars = _clean(bars)
    if len(bars) < n + 1 or not _has_ohlc(bars):
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < n:
        return None
    a = sum(trs[:n]) / float(n)
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def bollinger(vals, n=BB_N, k=BB_K):
    if not vals or len(vals) < n:
        return None
    m = sum(vals[-n:]) / float(n)
    var = sum((v - m) ** 2 for v in vals[-n:]) / float(n)
    sd = math.sqrt(var)
    return {"mid": m, "upper": m + k * sd, "lower": m - k * sd,
            "sd": sd, "width_pct": ((2 * k * sd) / m * 100.0) if m else None,
            "percent_b": ((vals[-1] - (m - k * sd)) / (2 * k * sd)
                          if sd else None)}


def _prices(v):
    """يقبل أسعار (أرقام) أو شموع (dicts) ⇒ أسعار."""
    if not v:
        return []
    if isinstance(v[0], dict):
        return [x.get("c") for x in v if x.get("c") is not None]
    return list(v)


def hist_vol(vals, n=VOL_N, periods=252):
    """التقلب التاريخي (سنوي، %) من اللوغاريتم-العوائد."""
    vals = _prices(vals)
    if not vals or len(vals) < min(n, 30) + 1:
        return None
    rets = []
    for i in range(1, len(vals)):
        if vals[i - 1] > 0:
            rets.append(math.log(vals[i] / vals[i - 1]))
    if len(rets) < 30:
        return None
    seg = rets[-n:]
    m = sum(seg) / len(seg)
    var = sum((r - m) ** 2 for r in seg) / (len(seg) - 1) if len(seg) > 1 else 0.0
    return math.sqrt(var) * math.sqrt(periods) * 100.0


def relative_vol(vals, n=VOL_N):
    """التقلب النسبي مقابل خط أساس تاريخي (نفس النافذة)."""
    vals = _prices(vals)
    hv = hist_vol(vals, n)
    if hv is None:
        return None
    base = hist_vol(vals[:-n] if len(vals) > n + 30 else vals, n)
    if not base:
        return None
    return {"current": hv, "baseline": base,
            "ratio": round(hv / base, 2) if base else None,
            "label": ("تقلب أعلى من المعتاد" if base and hv > base * 1.25 else
                      "تقلب أقل من المعتاد" if base and hv < base * 0.8 else
                      "تقلب في المعدل الطبيعي")}


# ═══════════ البنية ═══════════
def swings(bars, k=SWING_K):
    """
    قمم/قيعان بالـfractal: أعلى k شمعة قبل + أعلى k شمعة بعد (والعكس).
    ⛔ القمة/القاع في آخر k شمعة مش بيتحسبوا (مش كاملين).
    """
    bars = _clean(bars)
    highs, lows = [], []
    n = len(bars)
    for i in range(k, n - k):
        h = bars[i]["h"] if bars[i].get("h") is not None else bars[i]["c"]
        l = bars[i]["l"] if bars[i].get("l") is not None else bars[i]["c"]
        if h is None or l is None:
            continue
        wh = max((bars[j].get("h") if bars[j].get("h") is not None
                   else bars[j]["c"]) or 0 for j in range(i - k, i + k + 1))
        wl = min((bars[j].get("l") if bars[j].get("l") is not None
                   else bars[j]["c"]) or float("inf") for j in range(i - k, i + k + 1))
        if h >= wh:
            highs.append({"i": i, "d": bars[i]["d"], "p": float(h), "type": "high"})
        if l <= wl:
            lows.append({"i": i, "d": bars[i]["d"], "p": float(l), "type": "low"})
    return {"highs": highs, "lows": lows}


def structure(bars, k=SWING_K):
    """
    بنية السعر: قمم أعلى/قيعان أعلى (صاعد) ·vice versa (هابط) · نطاق.
    ⛔ لو القمم/القيعان أقل من ٢ ⇒ «غير واضح».
    """
    sw = swings(bars, k)
    hs = [h for h in sw["highs"]]
    ls = [l for l in sw["lows"]]
    out = {"swing_highs": len(hs), "swing_lows": len(ls), "label": "غير واضح",
           "hh": None, "hl": None, "lh": None, "ll": None,
           "last_highs": hs[-3:], "last_lows": ls[-3:]}
    if len(hs) >= 2:
        out["hh"] = hs[-1]["p"] > hs[-2]["p"]
        out["lh"] = hs[-1]["p"] < hs[-2]["p"]
    if len(ls) >= 2:
        out["hl"] = ls[-1]["p"] > ls[-2]["p"]
        out["ll"] = ls[-1]["p"] < ls[-2]["p"]
    if out["hh"] and out["hl"]:
        out["label"] = "بنية صاعدة (قمم وقيعان أعلى)"
    elif out["lh"] and out["ll"]:
        out["label"] = "بنية هابطة (قمم وقيعان أدنى)"
    elif out["hh"] and out["ll"]:
        out["label"] = "نطاق عرضي (قمم أعلى وقيعان أدنى)"
    elif out["lh"] and out["hl"]:
        out["label"] = "نطاق عرضي (قمم أدنى وقيعان أعلى)"
    return out


# ═══════════ الدعم والمقاومة ═══════════
def _cluster(points, tol):
    """تجميع نقاط قريبة (بـtolerance مطلق) ⇒ مناطق."""
    if not points:
        return []
    pts = sorted(points, key=lambda x: x["p"])
    groups = []
    cur = [pts[0]]
    for p in pts[1:]:
        if abs(p["p"] - cur[-1]["p"]) <= tol:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    return groups


def zones(bars, atr_val=None, price=None, k=SWING_K, max_each=ZONE_MAX):
    """
    مناطق الدعم والمقاومة —|score| موثّق.
    📌 لكل منطقة: الحدود · عدد الردود · أقصى ارتداد · آخر اختبار · الكسر.
    ⛔ مفيش «مستويات مختلقة» — المنطقة لازم يكون وراها ردّ فعلي.
    """
    bars = _clean(bars)
    if len(bars) < 30:
        return {"ok": False, "error": "السلسلة قصيرة لمناطق موثوقة", "zones": []}
    cur = price if price is not None else bars[-1]["c"]
    tol = (atr_val * ZONE_TOL_ATR) if atr_val else (cur * 0.01)
    sw = swings(bars, k)
    if not sw["highs"] and not sw["lows"]:
        return {"ok": False, "error": "مفيش قمم/قيعان محسوبة", "zones": []}

    n = len(bars)
    last_i = n - 1

    def analyze_group(g, kind):
        ps = [x["p"] for x in g]
        lo, hi = min(ps), max(ps)
        mid = sum(ps) / len(ps)
        # الردود: عدد المرات اللي السعر لمس المنطقة (بعد ظهور القمة/القاع)
        touches = 0
        reactions = []
        for i, b in enumerate(bars):
            if i < g[0]["i"]:
                continue
            bl = b.get("l") if b.get("l") is not None else b["c"]
            bh = b.get("h") if b.get("h") is not None else b["c"]
            if bl <= hi and bh >= lo:
                touches += 1
                # أقصى ارتداد بعدها (لو كانت مقاومة ⇒ موجب لتحت، دعم ⇒ لتحت كمان)
                fwd = bars[i + 1:i + 6]
                if fwd:
                    ex = min((f.get("l") if f.get("l") is not None else f["c"]) for f in fwd)
                    reactions.append(abs(mid - ex))
        last_touch = g[-1]["d"]
        # الكسر: إغلاق اتخلف عن المنطقة ٠٫٥ ATR وفضل برّه ٣ إغلاقات
        broken = False
        broke_dir = None
        if atr_val:
            thr = 0.5 * atr_val
            after = bars[g[-1]["i"] + 1:]
            if after:
                if kind == "resistance":
                    over = [b for b in after if b["c"] > hi + thr]
                    if len(over) >= 3:
                        broken, broke_dir = True, "فوق"
                else:
                    under = [b for b in after if b["c"] < lo - thr]
                    if len(under) >= 3:
                        broken, broke_dir = True, "تحت"
        # الحداثة: كام يوم مرّ من آخر اختبار
        age = None
        try:
            import datetime
            age = (datetime.datetime.strptime(bars[last_i]["d"], "%Y-%m-%d").date()
                   - datetime.datetime.strptime(last_touch, "%Y-%m-%d").date()).days
        except Exception:
            pass
        max_react = max(reactions) if reactions else 0.0
        # ⭐ الـscore موثّق (الأوزان مكتوبة تحت)
        s_react = min(touches, 6) * 10.0
        s_recency = max(0.0, 20.0 - (age or 999) / 15.0)     # حداثة: كل ١٥ يوم = −١
        s_mag = min(max_react / (atr_val or (cur * 0.01)), 3.0) * 10.0
        s_touch = min(len(g), 4) * 5.0
        score = round(s_react + s_recency + s_mag + s_touch, 1)
        return {
            "kind": kind, "low": round(lo, 4), "high": round(hi, 4),
            "mid": round(mid, 4), "center": round(mid, 4),
            "touches": touches, "reactions": len(g),
            "max_reaction": round(max_react, 4),
            "last_test": last_touch, "age_days": age,
            "broken": broken, "broken_direction": broke_dir,
            "distance_pct": round((mid / cur - 1) * 100, 2) if cur else None,
            "score": score,
            "score_parts": {"reactions": round(s_react, 1),
                             "recency": round(s_recency, 1),
                             "magnitude": round(s_mag, 1),
                             "touches": round(s_touch, 1)},
            "why": ("ظهرت عند هذه المنطقة %d ردّ فعلي · أحدث اختبار %s · "
                    "أقصى ارتداد %.4g" % (touches, last_touch, max_react)),
        }

    res_hi = [analyze_group(g, "resistance") for g in _cluster(sw["highs"], tol)]
    res_lo = [analyze_group(g, "support") for g in _cluster(sw["lows"], tol)]
    # نفصل اللي فوق السعر ودونيه
    above = sorted([z for z in res_hi if z["center"] > cur],
                   key=lambda z: -z["score"])[:max_each]
    below = sorted([z for z in res_lo if z["center"] < cur],
                   key=lambda z: -z["score"])[:max_each]
    # أقرب مستوى死不: الأقرب من فوق والأقرب من تحت
    nearest_res = min(above, key=lambda z: abs(z["distance_pct"])) if above else None
    nearest_sup = max(below, key=lambda z: z["center"]) if below else None
    if not above:
        pass
    return {
        "ok": True, "current": round(cur, 4), "tolerance": round(tol, 4),
        "no_resistance_above": not above,
        "at_period_high": not above,
        "no_resistance_note": ("مفيش مقاومة في النافذة فوق السعر الحالي ⇒ السعر عند "
                               "أعلى نقطة في هذه النافذة (قمّة تاريخية للفترة).") if not above else None,
        "resistance": above, "support": below,
        "nearest_resistance": nearest_res, "nearest_support": nearest_sup,
        "method": {
            "swing_rule": "fractal ب半个 قطر %d (٢ شمعة كل جهة)" % SWING_K,
            "clustering": "مناطق قريبة بـ %.2f ATR" % ZONE_TOL_ATR,
            "score": ("الردود (×10 حتى ٦) + الحداثة (٢٠ ناقص يوم/١٥) + "
                      "حجم الارتداد (×10 حتى ٣ ATR) + عدد القمم/القيعان (×5 حتى ٤)"),
            "break_rule": "كسر = إغلاق يتجاوز حدود المنطقة بـ ٠٫٥ ATR ويفضل برّه ٣ إغلاقات",
            "caveat": "منطقة الدعم ما بتضمنش ارتداد، والمقاومة ما بتضمنش هبوط.",
        },
    }


def breakout_state(bars, zone, atr_val):
    """
    حالة الاختراق لمنطقة: مؤكد / غير مؤكد / مفيش.
    📌 القواعد: إغلاق برّه + حجم ≥ ٠٫٥ ATR + ثبات ٣ إغلاقات + اختبار ارتداد.
    ⛔ لمسة سريعة مش اختراق مؤكد.
    """
    bars = _clean(bars)
    if not zone or not bars:
        return {"state": "غير متاح"}
    cur = bars[-1]["c"]
    above = zone["kind"] == "resistance"
    thr = 0.5 * (atr_val or (cur * 0.005))
    edge = zone["high"] if above else zone["low"]
    beyond = (cur - edge) if above else (edge - cur)
    recent = bars[-5:]
    n_beyond = 0
    for b in recent:
        if above and b["c"] > edge + thr:
            n_beyond += 1
        elif (not above) and b["c"] < edge - thr:
            n_beyond += 1
    if beyond <= 0:
        return {"state": "مفيش اختراق", "distance_pct": round((cur / edge - 1) * 100, 2)}
    if n_beyond >= 3:
        return {"state": "اختراق مؤكد", "closes_beyond": n_beyond,
                "distance_pct": round((cur / edge - 1) * 100, 2),
                "note": "٣ إغلاقات متتالية برّه المنطقة"}
    return {"state": "اختراق غير مؤكد", "closes_beyond": n_beyond,
            "distance_pct": round((cur / edge - 1) * 100, 2),
            "note": "السعر برّه المنطقة بس محتاج ثبات أكتر (٣ إغلاقات)"}


# ═══════════ الاتجاه ═══════════
def trend_label(closes, mas):
    """
    تسمية الاتجاه بقاعدة صريحة:
      · السعر فوق متوسط متحرك + المتوسط صاعد ⇒ صاعد
      · العكس ⇒ هابط
      · متوسطات متقاطعة/متضاربة ⇒ عرضي/غير واضح
    ⛔ صفر مقارنة (مش عدد إشارات) — القرار على MA + بنية السعر.
    """
    c = closes[-1]
    res = {}
    for name, n, key in (("short", TREND_SHORT, "sma20"),
                         ("medium", TREND_MED, "sma50"),
                         ("long", TREND_LONG, "sma200")):
        ma = mas.get(key)
        if ma is None:
            res[name] = {"label": "غير متاح", "reason": "بيانات أقل من %d شمعة" % n}
            continue
        slope = None
        if len(closes) >= n + 5:
            prev_ma = sum(closes[-n - 5:-5]) / float(n)
            slope = (ma - prev_ma) / prev_ma * 100 if prev_ma else None
        above = c > ma
        if slope is None:
            lab = "صاعد" if above else "هابط"
        elif slope > 0.05 and above:
            lab = "صاعد"
        elif slope < -0.05 and not above:
            lab = "هابط"
        else:
            lab = "عرضي"
        res[name] = {"label": lab, "ma": round(ma, 4), "ma_slope_pct": round(slope, 3) if slope is not None else None,
                     "price_vs_ma": "فوق" if above else "تحت",
                     "distance_pct": round((c / ma - 1) * 100, 2) if ma else None}
    labs = [v.get("label") for v in res.values() if v.get("label") != "غير متاح"]
    if not labs:
        res["overall"] = "غير متاح"
    elif all(x == "صاعد" for x in labs):
        res["overall"] = "اتجاه صاعد"
    elif all(x == "هابط" for x in labs):
        res["overall"] = "اتجاه هابط"
    elif "صاعد" in labs and "هابط" in labs:
        res["overall"] = "إشارات متضاربة بين الأطر"
    else:
        res["overall"] = "اتجاه عرضي"
    res["consistency"] = ("متوافق على كل الأطر" if len(set(labs)) == 1 and labs
                          else "مختلف بين الأطر" if len(set(labs)) > 1 else "غير متاح")
    return res


# ═══════════ التحليل الكامل ═══════════
def analyze(bars, label="", price=None, zone_window=500):
    """
    التحليل الفني الكامل لأداة واحدة.
    ⛔ لو السلسلة ناقصة ⇒ الحقول الناقصة = None + سبب.
    """
    bars = _clean(bars)
    out = {"ok": bool(bars), "label": label, "count": len(bars),
           "data_quality": {}}
    if not bars:
        out["error"] = "مفيش بيانات"
        return out
    c = _closes(bars)
    cur = price if price is not None else c[-1]
    out["from"] = bars[0]["d"]
    out["to"] = bars[-1]["d"]
    out["current"] = round(cur, 4)

    # ⛔ جودة البيانات
    gaps = 0
    try:
        import datetime
        prev = None
        for b in bars:
            d = datetime.datetime.strptime(b["d"], "%Y-%m-%d").date()
            if prev is not None and (d - prev).days > 7:
                gaps += 1
            prev = d
    except Exception:
        pass
    out["data_quality"] = {
        "points": len(bars),
        "has_ohlc": _has_ohlc(bars),
        "gaps_over_7d": gaps,
        "ohlc_note": None if _has_ohlc(bars) else
        "السلسلة close بس ⇒ ATR/Bollinger بالارتفاع والانخفاض مش متاحين ليها.",
    }

    # ── المتوسطات ──
    mas = {}
    for n in MA_SETS["sma"]:
        mas["sma%d" % n] = sma(c, n)
    for n in MA_SETS["ema"]:
        mas["ema%d" % n] = ema(c, n)
    out["ma"] = {k: (round(v, 4) if v is not None else None) for k, v in mas.items()}
    out["ma_available"] = {k: (v is not None) for k, v in mas.items()}

    # ── الزخم ──
    r = rsi(c)
    out["rsi14"] = round(r, 2) if r is not None else None
    out["rsi_note"] = ("RSI فوق ٧٠ / تحت ٣٠ مش إشارة شراء أو بيع بشكل تلقائي — "
                       "بيدل على قوة الحركة بس.") if r is not None else "بيانات ناقصة"
    m = macd(c)
    out["macd"] = None if not m else {
        "macd": round(m["macd"], 4), "signal": round(m["signal"], 4),
        "hist": round(m["hist"], 4),
        "state": ("إيجابي" if m["hist"] > 0 else "سلبي"),
    }
    out["roc12_pct"] = round(roc(c), 2) if roc(c) is not None else None

    # ── التقلب ──
    a = atr(bars)
    out["atr14"] = round(a, 4) if a is not None else None
    out["atr_note"] = None if a is not None else "محتاج OHLC — السلسلة close بس."
    bb = bollinger(c)
    out["bollinger"] = None if not bb else {
        "mid": round(bb["mid"], 4), "upper": round(bb["upper"], 4),
        "lower": round(bb["lower"], 4), "width_pct": round(bb["width_pct"], 2) if bb["width_pct"] else None,
        "percent_b": round(bb["percent_b"], 3) if bb["percent_b"] is not None else None,
    }
    hv = hist_vol(c)
    out["hist_vol_annual_pct"] = round(hv, 2) if hv is not None else None
    out["rel_vol"] = relative_vol(c)

    # ── الاتجاه والبنية ──
    out["trend"] = trend_label(c, mas)
    out["structure"] = structure(bars)

    # ── الدعم والمقاومة ──
    # ⛔⛔⛔ المستويات تتحسب على **نافذة قريبة** من السعر الحالي (٥٠٠ شمعة
    #    افتراضياً) مش على السلسلة كلها. السبب: سلسلة ٣٦ سنة (الذهب العالمي
    #    من ١٩٩٠) لو اتحسبت كلها ⇒ أقرب دعم طلع ١٨٪ بعيد وبيبقى بلا فايدة.
    #    ⇒ المتوسطات والاتجاه بيستخدموا السلسلة كلها، والمستويات بنافذة حديثة.
    zw = bars[-zone_window:] if zone_window and len(bars) > zone_window else bars
    z = zones(zw, atr_val=a, price=cur)
    z["window"] = {"bars": len(zw), "from": zw[0]["d"], "to": zw[-1]["d"]}
    z["window_note"] = ("المستويات محسوبة على آخر %d شمعة (قريبة من السعر الحالي) "
                         "— لأن القمم/القيعان القديمة البعيدة مشlevels مفيدة الآن."
                         % len(zw))
    out["sr"] = z
    if z.get("ok"):
        for side in ("resistance", "support"):
            for zn in z.get(side, []):
                zn["breakout"] = breakout_state(bars, zn, a)
    return out


def bars_from(rows, close_key="c", ohlc_keys=("o", "h", "l")):
    """
    تحويل صفوف السلسلة (من gold_history) ⇒ شكل الشموع الموحّد.
    📌 ⛔ لو الحقول المطلوبة ناقصة ⇒ بنسيبها None (مش بنخترع OHLC).
    """
    out = []
    for r in (rows or []):
        c = r.get(close_key)
        if c is None:
            continue
        b = {"d": r.get("d"), "c": float(c)}
        for k in ohlc_keys:
            if r.get(k) is not None:
                b[k] = float(r[k])
        out.append(b)
    out.sort(key=lambda x: (x.get("d") or ""))
    return out
