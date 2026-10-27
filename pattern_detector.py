#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مكتشف أنماط (OCTA Pattern Engine) — بايثون نقي، بدون أي مكتبة خارجية.

⛔ **ممنوع look-ahead**: كل دالة بتشتغل على الشموع اللي اتبعتت لها بس.
   لما بنعمل walk-forward بنمرّر `bars[:i+1]` ⇒ مفيش شمعة بعد i بتتسرّب.
⛔ **ممنوع اختراع أي رقم**: النقص = status "insufficient" + سبب مكتوب.
   «مفيش نمط» (signals فاضية) ≠ «ناقص» (بيانات مش كفاية).
⛔ **مصدر واحد للحقيقة**: ATR وبنية السعر مأخوذة من `gold_technical`
   (نفس دوال الذهب) عشان الأرقام متطابقة في كل مكان.

────────────────────────────────────────────────────────────────────────
أنواع الأنماط (اتنين بس في النسخة الأولى — بالنية في نبدأ بأقل عدد):

① BREAKOUT (كسر منطقة)
   resistance (مقاومة) كسرها السعر صعوداً  ·  support (دعم) كسرها هبوطاً.
   الحدث: أول شمعة بعد آخر اختبار للمنطقة إغلاقها يتخطى حافة المنطقة
          بـ `break_atr_mult` ATR، وبعدها `break_confirm` إغلاقات متتالية
          في نفس الاتجاه ⇒ تأكيد.

② PULLBACK (ارتداد من منطقة)
   دعم تحت السعر (ارتداد صاعد) · مقاومة فوق السعر (ارتداد هابط).
   الحدث: السعر لمس المنطقة خلال آخر `pullback_lookback` شموع،
          والمنطقة ردّت فعلياً `min_reactions` مرات.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys

try:
    from gold_technical import atr as _gold_atr, structure as _gold_structure
except Exception:  # pragma: no cover - لما المستورَد من مجلد تاني
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gold_technical import atr as _gold_atr, structure as _gold_structure


# ══════════════════════════════════════════════════════════════════════
#  الإعدادات الافتراضية
# ══════════════════════════════════════════════════════════════════════

DEFAULTS = {
    "min_bars": 120,          # أقل عدد شموع لازم لازم
    "max_window": 320,        # ⭐ النافذة القصوى (نفس n بتاع radar_api) — نافذة متحركة
    "atr_len": 14,
    "zone_tol_atr": 0.6,      # تجميع المناطق: فرق أقل من ٠٫٦ ATR = نفس المنطقة
    "swing_k": 3,             # نصف قطر الـfractal (نفس gold_technical)
    "break_atr_mult": 0.5,    # الإغلاق يتخطى المنطقة بـ ٠٫٥ ATR
    "break_confirm": 3,       # ٣ إغلاقات متتالية
    "vol_lookback": 20,       # متوسط الحجم
    "vol_mult": 1.3,          # حجم شمع الكسر ≥ ١٫٣ × المتوسط
    "pullback_atr_mult": 0.4, # قرب المنطقة (داخل ٠٫٤ ATR)
    "pullback_lookback": 3,   # الشموع اللي بندوّر فيها عن اللمسة
    "min_reactions": 2,       # أقل ردّ فعلي على المنطقة
    "atr_target_mult": 2.0,   # هدف احتياطي = ٢ ATR
    "stop_buffer_atr": 0.5,   # بافافيز الوقف تحت/فوق المنطقة
    "entry_buffer_atr": 0.25, # بافافيز الدخول بعد الحافة
    "max_age_bars": 5,        # أقصى حداثة للإشارة (بالشموع)
    "max_zones": 6,           # أقصى عدد مناطق لكل جهة
    # ── فلاتر اختيارية (مقفولة بالافتراضي — تُقاس قبل ما تتفعّل) ──
    "require_trend_alignment": False,  # الإشارات بس في اتجاه البنية
    "require_reversal": False,         # لازم إغلاق راجع فوق/تحت المنطقة
}

# أسماء عربية لل 방향 — بتظهر في التقرير
DIR_AR = {"up": "صاعد", "down": "هابط"}
KIND_AR = {"BREAKOUT": "كسر منطقة", "PULLBACK": "ارتداد من منطقة"}


def _cfg(cfg):
    out = dict(DEFAULTS)
    if cfg:
        for k, v in cfg.items():
            if k in out and v is not None:
                out[k] = v
    return out


# ══════════════════════════════════════════════════════════════════════
#  تنظيف الشموع
# ══════════════════════════════════════════════════════════════════════

def clean_bars(bars):
    """ينضّف ويرتّب الشموع تصاعدياً — ويحافظ على الحجم لو موجود.

    ⛔ الشمعة اللي c ناقص أو مش رقم بتتشال (مش مصفّرة).
    ⛔ v لو مش موجود ⇒ بتفضل None (مش صفر) عشان «تأكيد الحجم» يبقى False.
    """
    out = []
    for b in (bars or []):
        if not isinstance(b, dict):
            continue
        c = b.get("c")
        if c is None:
            continue
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        row = {
            "d": b.get("d"),
            "o": _num(b.get("o")),
            "h": _num(b.get("h")),
            "l": _num(b.get("l")),
            "c": c,
            "v": _vol(b.get("v")),
        }
        out.append(row)
    out.sort(key=lambda r: (r.get("d") or ""))
    return out


def _num(x):
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _vol(x):
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _has_ohlc(bars):
    return bool(bars) and all(
        (b.get("h") is not None and b.get("l") is not None) for b in bars)


def _age_days(d_from, d_to):
    """عدد الأيام بين تاريخين (둘هم YYYY-MM-DD) — None لو مش صالحين."""
    if not d_from or not d_to:
        return None
    try:
        a = _dt.datetime.strptime(str(d_from)[:10], "%Y-%m-%d").date()
        b = _dt.datetime.strptime(str(d_to)[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    return (b - a).days


# ══════════════════════════════════════════════════════════════════════
#  المناطق (زوايا الدعم والمقاومة)
# ══════════════════════════════════════════════════════════════════════

def _cluster(points, tol):
    """تجميع نقاط قريبة (بفرق مطلق ≤ tol) ⇒ مجموعات."""
    if not points:
        return []
    pts = sorted(points, key=lambda x: x["p"])
    groups, cur = [], [pts[0]]
    for p in pts[1:]:
        if abs(p["p"] - cur[-1]["p"]) <= tol:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    return groups


def _swings(bars, k):
    """قمم/قيعان بالـfractal — نسخة خفيفة ترجّع الفهارس."""
    highs, lows = [], []
    n = len(bars)
    if n < (2 * k + 1):
        return {"highs": highs, "lows": lows}
    for i in range(k, n - k):
        h = bars[i].get("h")
        l = bars[i].get("l")
        if h is None or l is None:
            continue
        wh = max((bars[j].get("h") if bars[j].get("h") is not None
                   else bars[j]["c"]) for j in range(i - k, i + k + 1))
        wl = min((bars[j].get("l") if bars[j].get("l") is not None
                   else bars[j]["c"]) for j in range(i - k, i + k + 1))
        if h >= wh:
            highs.append({"i": i, "d": bars[i].get("d"), "p": float(h)})
        if l <= wl:
            lows.append({"i": i, "d": bars[i].get("d"), "p": float(l)})
    return {"highs": highs, "lows": lows}


def _zone_group(group, kind, bars, atr_val, last_i):
    """يحسب منطقة واحدة من مجموعة قمم/قيعان — مع فهارس القمم."""
    ps = [x["p"] for x in group]
    lo, hi = min(ps), max(ps)
    mid = sum(ps) / len(ps)

    # الردود: عدد المرات اللي السعر لمس المنطقة
    touches = 0
    reactions = 0
    max_react = 0.0
    for i, b in enumerate(bars):
        if i < group[0]["i"]:
            continue
        bl = b.get("l") if b.get("l") is not None else b["c"]
        bh = b.get("h") if b.get("h") is not None else b["c"]
        if bl <= hi and bh >= lo:
            touches += 1
            fwd = bars[i + 1:i + 6]
            if fwd:
                ex = min((f.get("l") if f.get("l") is not None
                          else f.get("c")) for f in fwd)
                reactions += 1
                max_react = max(max_react, abs(mid - ex))

    last_pivot = group[-1]
    last_touch = last_pivot.get("d")
    age = _age_days(last_touch, bars[last_i].get("d"))

    # ⭐ نفس أوزان gold_technical (ردود + حداثة + حجم ارتداد + عدد القمم)
    s_react = min(touches, 6) * 10.0
    s_recency = max(0.0, 20.0 - (age or 999) / 15.0)
    s_mag = min(max_react / (atr_val or 0.0001), 3.0) * 10.0
    s_touch = min(len(group), 4) * 5.0
    score = round(s_react + s_recency + s_mag + s_touch, 1)

    return {
        "kind": kind,
        "low": round(lo, 4), "high": round(hi, 4),
        "mid": round(mid, 4), "center": round(mid, 4),
        "touches": touches, "reactions": reactions,
        "max_reaction": round(max_react, 4),
        "last_test": last_touch, "age_days": age,
        "last_pivot_i": last_pivot["i"],
        "pivot_is": [g["i"] for g in group],
        "score": score,
        "score_parts": {
            "reactions": round(s_react, 1),
            "recency": round(s_recency, 1),
            "magnitude": round(s_mag, 1),
            "touches": round(s_touch, 1),
        },
        "why": ("المنطقة ظهرت من %d ردّ فعلي · أحدث اختبار %s · أقصى ارتداد %.4g"
                % (touches, last_touch, max_react)),
    }


def _build_zones(bars, atr_val, cfg):
    """كل المناطق (مقاومة + دعم) مرتبة بالأقوى."""
    sw = _swings(bars, cfg["swing_k"])
    tol = (atr_val * cfg["zone_tol_atr"]) if atr_val else 0.0
    last_i = len(bars) - 1
    out = []
    for g in _cluster(sw["highs"], tol):
        out.append(_zone_group(g, "resistance", bars, atr_val, last_i))
    for g in _cluster(sw["lows"], tol):
        out.append(_zone_group(g, "support", bars, atr_val, last_i))
    out.sort(key=lambda z: -z["score"])
    return out


# ══════════════════════════════════════════════════════════════════════
#  أحداث الكسر واللمسة
# ══════════════════════════════════════════════════════════════════════

def _atr_series(bars, n):
    """سلسلة ATR بطريقة Wilder — ATR عند كل شمعة.

    ⛔ `out[i]` = ATR محسوب على الشموع لحد i بس (مفيش look-ahead).
    ⛔ أول قيمة صالحة عند الفهرس n (لأن ATR محتاج n+1 شمعة).
    ⭐ ده بيخلّي كشف الكسر O(n) بدل O(n²) — فرق كبير في المسح اليومي.
    """
    out = [None] * len(bars)
    if len(bars) < n + 1:
        return out
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:n]) / float(n)
    out[n] = a
    for k in range(n, len(trs)):
        a = (a * (n - 1) + trs[k]) / n
        out[k + 1] = a
    return out


def _atr_at(atr_series, idx, fallback):
    """ATR عند الشمعة idx من السلسلة المحسوبة (مفيش إعادة حساب)."""
    if 0 <= idx < len(atr_series):
        v = atr_series[idx]
        if v:
            return v
    return fallback


def _break_event(bars, zone, atr_series, atr_val, cfg):
    """يلاقي حدث الكسر وبيوقّعه.

    ⛔ الإغلاق لازم يتخطى الحافة بـ `break_atr_mult` ATR (ATR عند لحظة الكسر
       مش ATR النهائي) وبعدها `break_confirm` إغلاقات متتالية.
    """
    res = zone["kind"] == "resistance"
    start = zone["last_pivot_i"]
    n = len(bars)
    thr_mult = cfg["break_atr_mult"]
    need = max(1, int(cfg["break_confirm"]))

    j = start + 1
    while j < n:
        a = _atr_at(atr_series, j, atr_val)
        thr = thr_mult * (a or 0.0)
        c = bars[j]["c"]
        beyond = (c > zone["high"] + thr) if res else (c < zone["low"] - thr)
        if not beyond:
            j += 1
            continue
        # ⛔ لازم `need` إغلاقات متتالية في نفس الاتجاه — ولو السلسلة خلصت
        #    قبل كده ⇒ الكسر **غير مؤكد** (مفيش تساهل في آخر السلسلة).
        if j + need - 1 >= n:
            return None
        ok = True
        for k2 in range(j, j + need):
            a2 = _atr_at(atr_series, k2, atr_val)
            thr2 = thr_mult * (a2 or 0.0)
            c2 = bars[k2]["c"]
            if res and not (c2 > zone["high"] + thr2):
                ok = False
                break
            if (not res) and not (c2 < zone["low"] - thr2):
                ok = False
                break
        if ok:
            return {"break_i": j, "confirm_i": j + need - 1,
                    "confirmed": True, "closes_beyond": need}
        j += 1
    return None


def _volume_ratio(bars, idx, cfg):
    """نسبة حجم شمعة الكسر لمتوسط الحجم قبلها — None لو الحجم ناقص."""
    v = bars[idx].get("v")
    if v is None:
        return None, None
    lb = int(cfg["vol_lookback"])
    seg = [b["v"] for b in bars[max(0, idx - lb):idx] if b.get("v") is not None]
    if len(seg) < 5:
        return None, None
    avg = sum(seg) / float(len(seg))
    if avg <= 0:
        return None, None
    return round(v / avg, 3), round(avg, 0)


def _touch_recent(bars, zone, cfg, last_i):
    """هل السعر لمس المنطقة في آخر `pullback_lookback` شموع؟ (ترجّع الفهرس)"""
    lo_b = max(0, last_i - int(cfg["pullback_lookback"]) + 1)
    for i in range(last_i, lo_b - 1, -1):
        b = bars[i]
        bl = b.get("l") if b.get("l") is not None else b["c"]
        bh = b.get("h") if b.get("h") is not None else b["c"]
        if bl <= zone["high"] and bh >= zone["low"]:
            return i
    return None


# ══════════════════════════════════════════════════════════════════════
#  بناء الإشارة
# ══════════════════════════════════════════════════════════════════════

def _levels_for(zone, direction, atr_val, cfg):
    """الدخول والوقف والهدف — بقواعد ثابتة."""
    up = direction == "up"
    eb = cfg["entry_buffer_atr"] * atr_val
    sb = cfg["stop_buffer_atr"] * atr_val
    if up:
        entry = zone["high"] + eb
        stop = zone["mid"] - sb
    else:
        entry = zone["low"] - eb
        stop = zone["mid"] + sb

    height = zone["high"] - zone["low"]
    if height >= 0.5 * atr_val:
        target = entry + height if up else entry - height
        method = "measured_move"
    else:
        target = entry + cfg["atr_target_mult"] * atr_val if up \
            else entry - cfg["atr_target_mult"] * atr_val
        method = "atr"
    return entry, stop, target, method


def _rr(direction, entry, stop, target):
    if entry is None or stop is None or target is None:
        return None
    if direction == "up":
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    if risk <= 0:
        return None
    return round(reward / risk, 2)


def _signal_id(code, kind, direction, date):
    return "PB-%s-%s-%s-%s" % (code or "NA", date, kind, direction)


def _why_ar(sig):
    ev = sig["evidence"]
    parts = [
        "%s %s عند %s" % (KIND_AR.get(sig["kind"], sig["kind"]),
                          DIR_AR.get(sig["direction"], sig["direction"]),
                          _fmt(sig["level"])),
        "المنطقة %s ← %s" % (_fmt(sig["zone_low"]), _fmt(sig["zone_high"])),
        "%d ردّ فعلي" % ev.get("touches", 0),
    ]
    if ev.get("atr_pct") is not None:
        parts.append("ATR %s%% من السعر" % _fmt(ev["atr_pct"]))
    if sig["kind"] == "BREAKOUT":
        if sig.get("confirmed"):
            parts.append("٣ إغلاقات متتالية خارج المنطقة")
    else:
        parts.append("لمسة المنطقة + %d ردّ موثّق" % ev.get("reactions", 0))
    if sig.get("volume_confirmed"):
        parts.append("حجم مؤكد %s× متوسط ٢٠" % _fmt(ev.get("vol_ratio")))
    elif ev.get("vol_ratio") is None:
        parts.append("الحجم غير متاح ⇒ بدون تأكيد حجم")
    if sig.get("rr") is not None:
        parts.append("المخاطرة/العائد %s" % _fmt(sig["rr"]))
    return " · ".join(parts)


def _fmt(x, nd=2):
    if x is None:
        return "—"
    try:
        return ("%%.%df" % nd) % float(x)
    except (TypeError, ValueError):
        return str(x)


# ══════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════════════

def detect(bars, code=None, name=None, sector=None, cfg=None):
    """يكشف الأنماط في سلسلة شموع.

    bars: شموع مرتبة (d,o,h,l,c,v) — لازم تكون مقصوصة على آخر شمعة
          عايزين نحللها (مفيش شموع بعدي).
    يرجّع dict بالشكل الموضّح في العقد.
    """
    c = _cfg(cfg)
    out = {
        "code": code, "name": name, "sector": sector,
        "asof": None, "status": "insufficient", "reason": None,
        "bars": 0, "signals": [], "best": None,
    }

    bs = clean_bars(bars)
    # ⭐ نافذة متحركة ثابتة (نفس n بتاع radar_api = 320):
    #   عشان المسح اليومي والـbacktest يشتغلوا بنفس القواعد بالظبط.
    #   ⛔ النتيجة بتتغير حسب النافذة (المناطق بتتثبّت على قمم مختلفة) ⇒
    #   لازم النافذة واحدة في كل مكان: إنتاج + اختبار تاريخي.
    win = int(c.get("max_window") or 0)
    if win and len(bs) > win:
        bs = bs[-win:]
    out["bars"] = len(bs)
    if not bs:
        out["reason"] = "مفيش شموع صالحة"
        return out
    out["asof"] = bs[-1].get("d")

    if len(bs) < c["min_bars"]:
        out["reason"] = "سلسلة قصيرة: %d < %d شمعة" % (len(bs), c["min_bars"])
        return out
    if not _has_ohlc(bs):
        out["reason"] = "بيانات OHLC ناقصة"
        return out

    atr_val = _gold_atr(bs, c["atr_len"])
    if not atr_val or atr_val <= 0:
        out["reason"] = "ATR غير متاح"
        return out
    # ⭐ سلسلة ATR مرة واحدة (O(n)) بدل إعادة حساب لكل شمعة
    atr_series = _atr_series(bs, c["atr_len"])

    last_i = len(bs) - 1
    price = bs[-1]["c"]
    st = _gold_structure(bs, c["swing_k"])
    label = st.get("label") or "غير واضح"
    trend = "up" if "صاعدة" in label else ("down" if "هابطة" in label else "flat")

    zones = _build_zones(bs, atr_val, c)
    res_zones = [z for z in zones if z["kind"] == "resistance"][:c["max_zones"]]
    sup_zones = [z for z in zones if z["kind"] == "support"][:c["max_zones"]]

    signals = []

    # ── ① الكسر ─────────────────────────────────────────────────────
    for z in res_zones + sup_zones:
        ev = _break_event(bs, z, atr_series, atr_val, c)
        if not ev:
            continue
        confirm_i = ev["confirm_i"]
        bars_since = last_i - confirm_i
        if bars_since > c["max_age_bars"]:
            continue
        direction = "up" if z["kind"] == "resistance" else "down"
        entry, stop, target, method = _levels_for(z, direction, atr_val, c)
        rr = _rr(direction, entry, stop, target)
        vol_ratio, vol_avg = _volume_ratio(bs, ev["break_i"], c)
        vol_ok = bool(vol_ratio is not None and vol_ratio >= c["vol_mult"])
        close_beyond = None
        if z["kind"] == "resistance":
            close_beyond = round((price / z["high"] - 1) * 100, 2)
        else:
            close_beyond = round((z["low"] / price - 1) * 100, 2)
        sig = {
            "pattern_id": _signal_id(code, "BREAKOUT", direction, bs[confirm_i].get("d")),
            "kind": "BREAKOUT",
            "direction": direction,
            "level": z["mid"], "zone_low": z["low"], "zone_high": z["high"],
            "entry": round(entry, 4), "stop": round(stop, 4), "target": round(target, 4),
            "rr": rr,
            "timeframe": "1D",
            "detected_at": bs[confirm_i].get("d"),
            "confirmed": True,
            "volume_confirmed": vol_ok,
            "trend": trend,
            "bars_since": bars_since,
            "evidence": {
                "touches": z["touches"], "reactions": z["reactions"],
                "last_test": z["last_test"], "age_days": z["age_days"],
                "atr": round(atr_val, 4),
                "atr_pct": round(atr_val / price * 100, 2) if price else None,
                "distance_pct": close_beyond,
                "zone_score": z["score"], "zone_why": z["why"],
                "zone_score_parts": z["score_parts"],
                "vol_ratio": vol_ratio, "vol_avg20": vol_avg,
                "close_beyond_pct": close_beyond,
                "measured_move": round(z["high"] - z["low"], 4),
                "target_method": method,
                "structure_label": label,
                "source": "startamarkets", "bars_used": len(bs),
            },
        }
        sig["why"] = _why_ar(sig)
        signals.append(sig)

    # ── ② الارتداد ───────────────────────────────────────────────────
    for z in res_zones + sup_zones:
        if z["reactions"] < c["min_reactions"]:
            continue
        ti = _touch_recent(bs, z, c, last_i)
        if ti is None:
            continue
        direction = "up" if z["kind"] == "support" else "down"
        # ⭐ فلتر اتجاه البنية (اختياري): ارتداد صاعد لازم يكون في بنية صاعدة
        if c["require_trend_alignment"] and trend != direction:
            continue
        # ⭐ فلتر الانعكاس (اختياري): لازم إغلاق راجع فوق/تحت المنطقة
        if c["require_reversal"]:
            last_close = bs[-1]["c"]
            if direction == "up" and last_close <= z["high"]:
                continue
            if direction == "down" and last_close >= z["low"]:
                continue
        entry, stop, target, method = _levels_for(z, direction, atr_val, c)
        rr = _rr(direction, entry, stop, target)
        dist_pct = round((z["mid"] / price - 1) * 100, 2) if price else None
        near_limit = (c["pullback_atr_mult"] * atr_val / price * 100) if price else None
        near_ok = (dist_pct is not None and near_limit is not None
                   and abs(dist_pct) <= near_limit)
        if not near_ok:
            continue
        bars_since = last_i - ti
        if bars_since > c["max_age_bars"]:
            continue
        vol_ratio, vol_avg = _volume_ratio(bs, ti, c)
        vol_ok = bool(vol_ratio is not None and vol_ratio >= c["vol_mult"])
        sig = {
            "pattern_id": _signal_id(code, "PULLBACK", direction, bs[ti].get("d")),
            "kind": "PULLBACK",
            "direction": direction,
            "level": z["mid"], "zone_low": z["low"], "zone_high": z["high"],
            "entry": round(entry, 4), "stop": round(stop, 4), "target": round(target, 4),
            "rr": rr,
            "timeframe": "1D",
            "detected_at": bs[ti].get("d"),
            "confirmed": True,
            "volume_confirmed": vol_ok,
            "trend": trend,
            "bars_since": bars_since,
            "evidence": {
                "touches": z["touches"], "reactions": z["reactions"],
                "last_test": z["last_test"], "age_days": z["age_days"],
                "atr": round(atr_val, 4),
                "atr_pct": round(atr_val / price * 100, 2) if price else None,
                "distance_pct": dist_pct,
                "zone_score": z["score"], "zone_why": z["why"],
                "zone_score_parts": z["score_parts"],
                "vol_ratio": vol_ratio, "vol_avg20": vol_avg,
                "close_beyond_pct": None,
                "measured_move": round(z["high"] - z["low"], 4),
                "target_method": method,
                "structure_label": label,
                "source": "startamarkets", "bars_used": len(bs),
            },
        }
        sig["why"] = _why_ar(sig)
        signals.append(sig)

    # ⛔ «مفيش نمط» مش «ناقص» — البيانات كفاية، بس مفيش نمط دلوقتي
    signals.sort(key=lambda s: (s["detected_at"] or "", s["rr"] or -99), reverse=True)
    out["status"] = "ok"
    out["reason"] = None
    out["signals"] = signals
    out["best"] = signals[0] if signals else None
    return out


# ══════════════════════════════════════════════════════════════════════
#  CLI بسيط (تشخيص سريع لسهم واحد)
# ══════════════════════════════════════════════════════════════════════

def _cli(argv=None):  # pragma: no cover
    import json
    argv = list(argv or sys.argv[1:])
    if not argv:
        print("الاستخدام: python pattern_detector.py <ملف شموع.json> [كود]")
        return 1
    path = argv[0]
    try:
        with open(path, "r", encoding="utf-8") as f:
            bars = json.load(f)
    except Exception as e:
        print("تعذّر قراءة الملف: %s" % e)
        return 1
    code = argv[1] if len(argv) > 1 else None
    res = detect(bars, code=code)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_cli())
