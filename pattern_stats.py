# -*- coding: utf-8 -*-
"""
وحدة إحصاء الأنماط (walk-forward backtest) لمكتشف أنماط OCTA.

⛔ **walk-forward حقيقي**: لكل سهم ولكل نقطة i بنستدعي `detect(bars[:i+1])`
   يعني الكاشف بيشوف الشموع اللي وقعت لحد اللحظة دي بس.
⛔ **حاجز الـlook-ahead**: الإشارة بتقبل لو `detected_at == تاريخ الشمعة i`.
⛔ **مفيش أرقام مخترعة**: family فاضية ⇒ signals=0 والباقي None (مش صفر).
⛔ **hit_rate** = wins / (wins + losses) — الـopen والـambiguous بره المقام.
⛔ **الـR المحقق** = +R عند الفوز و−R عند الخسارة (المضاعف نفسه دايماً موجب).

📌 **النافذة**: الكاشف نفسه بيقصّ على آخر 320 شمعة ⇒ المسح اليومي
   والاختبار التاريخي بيشتغلوا بنفس القواعد بالظبط.
"""

from __future__ import annotations

import inspect

__all__ = ["evaluate", "risk_multiple", "FAMILIES"]

# العائلات اللي بيتعمل عليها إحصاء
FAMILIES = ("BREAKOUT", "PULLBACK")

# اتجاهات الإشارة
DIRECTIONS = ("up", "down")

try:
    from pattern_detector import detect  # type: ignore
except Exception:
    detect = None


# ══════════════════════════════════════════════════════════════════════
#  أدوات مساعدة
# ══════════════════════════════════════════════════════════════════════

def _to_float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "y", "on", "confirmed", "مؤكد", "تأكيد"):
            return True
        if text in ("0", "false", "no", "n", "off", "unconfirmed", "غير مؤكد"):
            return False
    return bool(value)


def _signal_value(signal, keys):
    for key in keys:
        if key in signal and signal[key] is not None:
            return signal[key]
    return None


def _signal_price(signal, keys):
    return _to_float(_signal_value(signal, keys))


def _signal_flag(signal, keys):
    return _to_bool(_signal_value(signal, keys))


def _date_key(value):
    if value is None:
        return ""
    return str(value)[:10]


def _bar_date(bar):
    if not isinstance(bar, dict):
        return ""
    for key in ("d", "date", "dt", "day"):
        value = bar.get(key)
        if value is not None:
            return str(value)
    return ""


def _bar_value(bar, keys):
    if not isinstance(bar, dict):
        return None
    for key in keys:
        if key in bar and bar[key] is not None:
            return bar[key]
    return None


def _bar_high(bar):
    return _to_float(_bar_value(bar, ("h", "high")))


def _bar_low(bar):
    return _to_float(_bar_value(bar, ("l", "low")))


def _normalize_family(signal):
    """BREAKOUT / PULLBACK من أي تسمية في الإشارة."""
    raw = _signal_value(signal, ("family", "kind", "pattern", "type"))
    if raw is None:
        return None
    text = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
    if "BREAKOUT" in text:
        return "BREAKOUT"
    if "PULLBACK" in text or "PULL_BACK" in text:
        return "PULLBACK"
    return text


def _normalize_direction(signal):
    raw = _signal_value(signal, ("direction", "dir", "side"))
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return "up" if raw > 0 else "down"
    text = str(raw).strip().lower()
    if text in ("up", "long", "bull", "bullish", "buy", "صاعد", "صاعدة", "شراء"):
        return "up"
    if text in ("down", "short", "bear", "bearish", "sell", "هابط", "هابطة", "بيع"):
        return "down"
    return None


def _signal_detected_at(signal):
    raw = _signal_value(signal, ("detected_at", "date", "d", "timestamp"))
    if raw is None:
        return None
    return str(raw)


def _is_insufficient(result):
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    if status is None:
        return False
    return str(status).strip().lower() in (
        "insufficient", "insufficient_data", "insufficient_bars",
        "not_enough_data", "too_few_bars",
    )


def _extract_signals(result):
    if result is None:
        return []
    if isinstance(result, dict):
        for key in ("signals", "patterns", "items", "results"):
            value = result.get(key)
            if value is None:
                continue
            if isinstance(value, dict):
                return [value]
            if isinstance(value, (list, tuple)):
                return [item for item in value if isinstance(item, dict)]
            return []
        single = result.get("signal")
        if isinstance(single, dict):
            return [single]
        return []
    if isinstance(result, (list, tuple)):
        return [item for item in result if isinstance(item, dict)]
    return []


def _resolve_detect(cfg):
    for key in ("detect", "detector"):
        candidate = (cfg or {}).get(key)
        if callable(candidate):
            return candidate
    if callable(detect):
        return detect
    return None


def _call_detect(detector, bars, code, cfg):
    kwargs = {}
    try:
        parameters = inspect.signature(detector).parameters
    except (TypeError, ValueError):
        parameters = None
    if parameters and cfg:
        for key in ("cfg", "config", "params", "options"):
            if key in parameters:
                kwargs[key] = cfg
                break
    try:
        return detector(bars, code=code, **kwargs)
    except TypeError as error:
        if "code" not in str(error):
            raise
        return detector(bars, **kwargs)


# ══════════════════════════════════════════════════════════════════════
#  حساب النتيجة
# ══════════════════════════════════════════════════════════════════════

def risk_multiple(direction, entry, target, stop):
    """المضاعف R (دايماً موجب)."""
    entry_value = _to_float(entry)
    target_value = _to_float(target)
    stop_value = _to_float(stop)
    if entry_value is None or target_value is None or stop_value is None:
        return 0.0
    if direction == "up":
        numerator = target_value - entry_value
        denominator = entry_value - stop_value
    else:
        numerator = entry_value - target_value
        denominator = stop_value - entry_value
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _evaluate_outcome(bars, index, horizon, direction, target, stop):
    """win / loss / ambiguous / open على الشموع اللي بعد index."""
    target_index = None
    stop_index = None
    last_index = min(index + horizon, len(bars) - 1)
    for position in range(index + 1, last_index + 1):
        bar = bars[position]
        high = _bar_high(bar)
        low = _bar_low(bar)
        if high is None or low is None:
            continue
        if direction == "up":
            hit_target = high >= target
            hit_stop = low <= stop
        else:
            hit_target = low <= target
            hit_stop = high >= stop
        if target_index is None and hit_target:
            target_index = position
        if stop_index is None and hit_stop:
            stop_index = position
        if target_index is not None and stop_index is not None:
            break
    if target_index is not None and stop_index is not None:
        if target_index == stop_index:
            return "ambiguous"
        return "win" if target_index < stop_index else "loss"
    if target_index is not None:
        return "win"
    if stop_index is not None:
        return "loss"
    return "open"


# ══════════════════════════════════════════════════════════════════════
#  تجميع الأرقام
# ══════════════════════════════════════════════════════════════════════

def _new_counts():
    return {"signals": 0, "wins": 0, "losses": 0, "open": 0,
            "ambiguous": 0, "total_r": 0.0}


def _new_breakdown():
    return {"by_direction": {}, "by_year": {}, "by_confirmed": {},
            "by_volume_confirmed": {}, "by_fillable": {}}


def _is_fillable(bars, index, direction, entry):
    """هل كان ممكن تنفيذ الدخول في الشمعة التالية؟

    ⛔ لو الشمعة التالية فتحت بعيدة عن سعر الدخول ⇒ الصفقة كانت مش
       هتنفّذ ⇒ القياس لازم يعدّيها (ده الفرق بين «نسبة نجاح حقيقية»
       و«نسبة نجاح على صفقات مفترضة»).
    """
    if index + 1 >= len(bars):
        return False
    nxt = bars[index + 1]
    if direction == "up":
        low = nxt.get("l")
        if low is None:
            low = nxt.get("c")
        return low is not None and low <= entry
    high = nxt.get("h")
    if high is None:
        high = nxt.get("c")
    return high is not None and high >= entry


def _record(counts, outcome, realized_r):
    counts["signals"] += 1
    if outcome == "win":
        counts["wins"] += 1
    elif outcome == "loss":
        counts["losses"] += 1
    elif outcome == "ambiguous":
        counts["ambiguous"] += 1
    else:
        counts["open"] += 1
    counts["total_r"] += realized_r


def _finalize(counts):
    signals = counts["signals"]
    if signals == 0:
        return {"signals": 0, "wins": None, "losses": None, "open": None,
                "ambiguous": None, "hit_rate": None, "avg_r": None,
                "total_r": None, "expectancy_r": None}
    wins = counts["wins"]
    losses = counts["losses"]
    resolved = wins + losses
    hit_rate = (wins / resolved) if resolved else None
    total_r = counts["total_r"] if resolved else None
    avg_r = (total_r / resolved) if (resolved and total_r is not None) else None
    return {"signals": signals, "wins": wins, "losses": losses,
            "open": counts["open"], "ambiguous": counts["ambiguous"],
            "hit_rate": hit_rate, "avg_r": avg_r, "total_r": total_r,
            "expectancy_r": avg_r}


# ══════════════════════════════════════════════════════════════════════
#  جمع الإشارات بتفاصيلها (لأبحاث الفلاتر)
# ══════════════════════════════════════════════════════════════════════

def _turnover(bars, idx):
    """قيمة التداول في الشمعة (إقفال × حجم) بالجنيه — مقياس سيولة مبدئي."""
    b = bars[idx]
    close = b.get("c")
    vol = b.get("v")
    if close is None or vol is None:
        return None
    try:
        return float(close) * float(vol)
    except (TypeError, ValueError):
        return None


def _avg_turnover(bars, idx, lookback=20):
    """متوسط قيمة التداول قبل الشمعة."""
    seg = [_turnover(bars, i) for i in range(max(0, idx - lookback), idx)]
    seg = [x for x in seg if x is not None]
    if len(seg) < 5:
        return None
    return sum(seg) / float(len(seg))


def _simulate(bars, fill_index, horizon, direction, entry, stop, target,
              require_touch=False, skip_if_beyond=False, cost_pct=0.0):
    """محاكاة صفقة بأسلوب تنفيذ محدد.

    ⛔ بتمشي شمعة شمعة (مش min/max على النافذة) ⇒ لو الهدف والوقف اتلموا
       في نفس الشمعة ⇒ ambiguous (مش success تلقائي).
    📌 المخرجات: {"status": "win|loss|open|ambiguous|not_filled",
                  "r": R محقق, "r_net": R بعد التكلفة, "bars": عدد الشموع}
    """
    n = len(bars)
    if fill_index >= n or entry is None:
        return {"status": "no_data", "r": 0.0, "r_net": 0.0, "bars": 0}

    # ── شرط التنفيذ ───────────────────────────────────────────────
    if skip_if_beyond:
        # لو الافتتاح تجاوز الهدف ⇒ الصفقة فاتتها (مش خسارة)
        first = bars[fill_index]
        o = first.get("o")
        if o is not None:
            if direction == "up" and o >= target:
                return {"status": "not_filled", "r": 0.0, "r_net": 0.0, "bars": 0}
            if direction == "down" and o <= target:
                return {"status": "not_filled", "r": 0.0, "r_net": 0.0, "bars": 0}
    fill_bar = bars[fill_index]
    if require_touch:
        hi = fill_bar.get("h")
        lo = fill_bar.get("l")
        if hi is None or lo is None:
            return {"status": "no_data", "r": 0.0, "r_net": 0.0, "bars": 0}
        touched = (lo <= entry <= hi)
        if not touched:
            return {"status": "not_filled", "r": 0.0, "r_net": 0.0, "bars": 0}

    # ── المخاطر بعد التنفيذ الفعلي ───────────────────────────────
    if direction == "up":
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    if risk <= 0:
        return {"status": "invalid", "r": 0.0, "r_net": 0.0, "bars": 0}
    mult = reward / risk

    # ── المشي شمعة شمعة ──────────────────────────────────────────
    status = "open"
    exit_i = None
    last_i = min(fill_index + horizon, n - 1)
    for j in range(fill_index, last_i + 1):
        b = bars[j]
        hi = b.get("h")
        lo = b.get("l")
        if hi is None or lo is None:
            continue
        hit_t = (hi >= target) if direction == "up" else (lo <= target)
        hit_s = (lo <= stop) if direction == "up" else (hi >= stop)
        if hit_t and hit_s:
            status = "ambiguous"
            exit_i = j
            break
        if hit_t:
            status = "win"
            exit_i = j
            break
        if hit_s:
            status = "loss"
            exit_i = j
            break

    r = 0.0
    if status == "win":
        r = mult
    elif status == "loss":
        r = -1.0
    elif status == "open":
        # ⭐ mark-to-market عند آخر شمعة في الأفق (أعدل من ٠)
        last_close = bars[last_i].get("c")
        if last_close is not None:
            if direction == "up":
                r = (last_close - entry) / risk
            else:
                r = (entry - last_close) / risk
    r_net = r
    if cost_pct and risk:
        entry_pct = abs(entry) or 1.0
        cost_r = (float(cost_pct) / 100.0) / (risk / entry_pct)
        r_net = r - cost_r
    return {"status": status, "r": round(r, 4), "r_net": round(r_net, 4),
            "mult": round(mult, 3),
            "bars": (exit_i - fill_index + 1) if exit_i is not None
            else (last_i - fill_index + 1)}


def _exec_variants(bars, index, horizon, direction, entry, stop, target,
                   cost_pct=0.0):
    """نماذج التنفيذ + الضوابط لكل إشارة.

    📌 ① planned  : الدخول بسعر الإشارة المخطط (متفائل)
    📌 ② next_open: الدخول بسعر افتتاح الشمعة التالية (واقعي للبوت)
    📌 ③ limit    : أمر حد عند السعر المخطط (يتنفّذ بس لو السعر لمسه)
    📌 ④ flip     : نفس الإشارة معكوسة الاتجاه (ضابط: لازم يفشل)
    📌 ⑤ delay1/2 : الدخول بعد شمعة/شمعتين (ضابط: لازم يضعف)
    """
    out = {}
    nxt = index + 1
    # ⭐ كل النماذج بتبدأ من الشمعة اللي بعد الإشارة (القرار بيتم عند
    #   إغلاق الشمعة i ⇒ مش معروف قبل كده).
    if nxt < len(bars):
        out["planned"] = _simulate(bars, nxt, horizon, direction, entry, stop,
                                   target, cost_pct=cost_pct)
        o = bars[nxt].get("o")
        out["next_open"] = _simulate(bars, nxt, horizon, direction, o, stop,
                                     target, skip_if_beyond=True,
                                     cost_pct=cost_pct)
        out["limit"] = _simulate(bars, nxt, horizon, direction, entry, stop,
                                 target, require_touch=True, cost_pct=cost_pct)
        out["delay1"] = _simulate(bars, nxt + 1, horizon, direction,
                                   bars[nxt + 1].get("o") if nxt + 1 < len(bars)
                                   else None, stop, target,
                                   skip_if_beyond=True, cost_pct=cost_pct)
        out["delay2"] = _simulate(bars, nxt + 2, horizon, direction,
                                   bars[nxt + 2].get("o") if nxt + 2 < len(bars)
                                   else None, stop, target,
                                   skip_if_beyond=True, cost_pct=cost_pct)
    # ── الانعكاس: نفس السعر والمسافات بس الاتجاه المعاكس (ضابط) ──
    if direction == "up":
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    out["flip"] = _simulate(bars, nxt, horizon,
                            "down" if direction == "up" else "up",
                            entry,
                            entry + risk if direction == "up" else entry - risk,
                            entry - reward if direction == "up" else entry + reward,
                            skip_if_beyond=True, cost_pct=cost_pct)
    return out


def collect_signals(bars_by_code, cfg=None, horizon=10, step=1, warmup=320,
                    max_codes=None, start_date=None, kinds=None,
                    execution=False, cost_pct=0.0):
    """بيرجّع قائمة كل الإشارات بتفاصيلها ونتائجها — لأبحاث الفلاتر.

    ⛔ نفس منطق الـwalk-forward بالظبط (نفس حاجز التاريخ ونفس حساب النتيجة)
       ⇒ لازم يطابق `evaluate` (فيه اختبار مقارنة).
    ⭐ الهدف: نشتغل على البيانات مرة واحدة وبعدين نفلتر بأي شكل من غير إعادة قياس.
    """
    settings = dict(cfg or {})
    horizon = max(1, int(horizon))
    step = max(1, int(step))
    warmup = max(0, int(warmup))
    detector = _resolve_detect(settings)
    if detector is None:
        raise RuntimeError("مفيش detect متاح: لازم pattern_detector.detect")
    forward_cfg = {k: v for k, v in settings.items()
                   if k not in ("detect", "detector")}
    all_codes = list(bars_by_code.keys()) if bars_by_code else []
    codes = all_codes if max_codes is None else all_codes[:int(max_codes)]
    out = []
    for code in codes:
        bars = list(bars_by_code.get(code) or [])
        start_idx = 0
        if start_date:
            for i, b in enumerate(bars):
                if _date_key(_bar_date(b)) >= start_date:
                    start_idx = i
                    break
            else:
                start_idx = len(bars)
        first = max(warmup, start_idx)
        if len(bars) <= first + horizon:
            continue
        for index in range(first, len(bars) - horizon, step):
            result = _call_detect(detector, bars[: index + 1], code, forward_cfg)
            if result is None or _is_insufficient(result):
                continue
            bar_date = _date_key(_bar_date(bars[index]))
            for signal in _extract_signals(result):
                if _date_key(_signal_detected_at(signal)) != bar_date:
                    continue
                family = _normalize_family(signal)
                if family not in FAMILIES:
                    continue
                if kinds and family not in kinds:
                    continue
                direction = _normalize_direction(signal)
                if direction not in DIRECTIONS:
                    continue
                entry = _signal_price(signal, ("entry", "entry_price", "price"))
                target = _signal_price(signal, ("target", "target_price", "tp"))
                stop = _signal_price(signal, ("stop", "stop_price", "sl"))
                if entry is None or target is None or stop is None:
                    continue
                outcome = _evaluate_outcome(bars, index, horizon, direction,
                                            target, stop)
                multiple = risk_multiple(direction, entry, target, stop)
                if outcome == "win":
                    realized_r = multiple
                elif outcome == "loss":
                    realized_r = -multiple
                else:
                    realized_r = 0.0
                ev = signal.get("evidence") or {}
                rec = {
                    "code": code, "kind": family, "direction": direction,
                    "date": bar_date, "year": bar_date[:4],
                    "month": bar_date[5:7] if len(bar_date) >= 7 else "",
                    "entry": entry, "stop": stop, "target": target,
                    "rr": round(multiple, 3),
                    "price": bars[index].get("c"),
                    "atr": ev.get("atr"), "atr_pct": ev.get("atr_pct"),
                    "zone_score": ev.get("zone_score"),
                    "touches": ev.get("touches"), "reactions": ev.get("reactions"),
                    "last_test": ev.get("last_test"),
                    "age_days": ev.get("age_days"),
                    "vol_ratio": ev.get("vol_ratio"),
                    "volume_confirmed": bool(signal.get("volume_confirmed")),
                    "confirmed": bool(signal.get("confirmed")),
                    "trend": signal.get("trend"),
                    "bars_since": signal.get("bars_since"),
                    "target_method": ev.get("target_method"),
                    "structure_label": ev.get("structure_label"),
                    "fillable": _is_fillable(bars, index, direction, entry),
                    "outcome": outcome, "r": round(realized_r, 4),
                    "turnover": _turnover(bars, index),
                    "avg_turnover20": _avg_turnover(bars, index),
                    "pattern_id": signal.get("pattern_id"),
                }
                if execution:
                    rec["exec"] = _exec_variants(bars, index, horizon,
                                                 direction, entry, stop, target,
                                                 cost_pct=cost_pct)
                out.append(rec)
    return out


# ══════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════════════

def _walkforward(bars_by_code, cfg=None, horizon=10, step=1, warmup=320,
                 max_codes=None, start_date=None):
    """المشي التاريخي — بترجّع العدّادات الخام (مش نهائية)."""
    settings = dict(cfg or {})
    horizon = max(1, int(horizon))
    step = max(1, int(step))
    warmup = max(0, int(warmup))

    detector = _resolve_detect(settings)
    if detector is None:
        raise RuntimeError("مفيش detect متاح: لازم pattern_detector.detect")

    forward_cfg = {k: v for k, v in settings.items()
                   if k not in ("detect", "detector")}

    all_codes = list(bars_by_code.keys()) if bars_by_code else []
    codes = all_codes
    if max_codes is not None:
        limit = int(max_codes)
        codes = all_codes[:limit] if limit >= 0 else []

    counts = {f: _new_counts() for f in FAMILIES}
    breakdowns = {f: _new_breakdown() for f in FAMILIES}

    codes_used = []
    bars_min = None
    bars_max = None
    bars_total = 0
    signals_total = 0
    skipped_insufficient = 0
    skipped_invalid = 0
    skipped_direction = 0
    skipped_family = 0
    codes_too_short = 0

    for code in codes:
        bars = list(bars_by_code.get(code) or [])
        bars_total += len(bars)
        if bars_min is None or len(bars) < bars_min:
            bars_min = len(bars)
        if bars_max is None or len(bars) > bars_max:
            bars_max = len(bars)
        # ⭐ القصّ بالتاريخ بيأثر على نطاق القياس بس — الشموع اللي قبله
        #    بتفضل موجودة عشان الـwarmup (نافذة الكاشف) يبقى زي الإنتاج.
        start_idx = 0
        if start_date:
            start_idx = 0
            for i, b in enumerate(bars):
                if _date_key(_bar_date(b)) >= start_date:
                    start_idx = i
                    break
            else:
                start_idx = len(bars)
        first = max(warmup, start_idx)
        if len(bars) <= first + horizon:
            codes_too_short += 1
            continue
        codes_used.append(code)
        for index in range(first, len(bars) - horizon, step):
            window = bars[: index + 1]
            result = _call_detect(detector, window, code, forward_cfg)
            if result is None:
                continue
            if _is_insufficient(result):
                skipped_insufficient += 1
                continue
            bar_date = _date_key(_bar_date(bars[index]))
            for signal in _extract_signals(result):
                if _date_key(_signal_detected_at(signal)) != bar_date:
                    continue
                family = _normalize_family(signal)
                if family not in counts:
                    skipped_family += 1
                    continue
                direction = _normalize_direction(signal)
                if direction not in DIRECTIONS:
                    skipped_direction += 1
                    continue
                entry = _signal_price(signal, ("entry", "entry_price", "price"))
                target = _signal_price(signal, ("target", "target_price", "tp"))
                stop = _signal_price(signal, ("stop", "stop_price", "sl"))
                if entry is None or target is None or stop is None:
                    skipped_invalid += 1
                    continue
                outcome = _evaluate_outcome(bars, index, horizon, direction,
                                            target, stop)
                multiple = risk_multiple(direction, entry, target, stop)
                if outcome == "win":
                    realized_r = multiple
                elif outcome == "loss":
                    realized_r = -multiple
                else:
                    realized_r = 0.0
                confirmed = _signal_flag(signal, ("confirmed",))
                volume_ok = _signal_flag(signal, ("volume_confirmed",))
                fillable = _is_fillable(bars, index, direction, entry)
                year = bar_date[:4] if bar_date else "unknown"

                _record(counts[family], outcome, realized_r)
                for dim, key in (
                    ("by_direction", direction),
                    ("by_year", year),
                    ("by_confirmed", "confirmed" if confirmed else "unconfirmed"),
                    ("by_volume_confirmed",
                     "volume_confirmed" if volume_ok else "not_volume_confirmed"),
                    ("by_fillable", "fillable" if fillable else "not_fillable"),
                ):
                    bucket = breakdowns[family][dim].setdefault(key, _new_counts())
                    _record(bucket, outcome, realized_r)
                signals_total += 1

    for family in FAMILIES:
        if counts[family]["signals"] == 0:
            continue
        for key in DIRECTIONS:
            breakdowns[family]["by_direction"].setdefault(key, _new_counts())
        for key in ("confirmed", "unconfirmed"):
            breakdowns[family]["by_confirmed"].setdefault(key, _new_counts())
        for key in ("volume_confirmed", "not_volume_confirmed"):
            breakdowns[family]["by_volume_confirmed"].setdefault(key, _new_counts())
        for key in ("fillable", "not_fillable"):
            breakdowns[family]["by_fillable"].setdefault(key, _new_counts())

    universe = {
        "codes": len(codes_used),
        "codes_total": len(all_codes),
        "codes_used": len(codes_used),
        "codes_skipped": len(all_codes) - len(codes_used),
        "codes_list": codes_used,
        "bars_total": bars_total,
        "bars_min": bars_min,
        "bars_max": bars_max,
        "horizon": horizon,
        "step": step,
        "warmup": warmup,
        "start_date": start_date,
        "signals": signals_total,
    }

    notes = [
        "walk-forward: detect بيتنادى على bars[:i+1] بس، والإشارة بتقبل لو "
        "detected_at == تاريخ الشمعة i.",
        "hit_rate = wins / (wins + losses): الـopen والـambiguous بره المقام.",
        "الـR المحقق: +R عند الفوز و-R عند الخسارة.",
        "الكاشف بيقصّ على آخر 320 شمعة (نافذة متحركة) — زي الإنتاج بالظبط.",
    ]
    if start_date:
        notes.append("القياس بدأ من %s (قصّ صريح مش مخفي)." % start_date)
    if codes_too_short:
        notes.append("أسهم اتخطّت لأن شموعها أقل من warmup + horizon: %d" % codes_too_short)
    if skipped_insufficient:
        notes.append("شموع رجّع لها status=insufficient واتخطّت: %d" % skipped_insufficient)
    if skipped_invalid:
        notes.append("إشارات ناقصها entry/target/stop واتخطّت: %d" % skipped_invalid)
    if skipped_direction:
        notes.append("إشارات اتجاهها مش معروف واتخطّت: %d" % skipped_direction)
    if skipped_family:
        notes.append("إشارات من families مش مدعومة واتخطّت: %d" % skipped_family)

    return {"counts": counts, "breakdowns": breakdowns,
            "universe": universe, "notes": notes}


# ══════════════════════════════════════════════════════════════════════
#  الواجهة العامة
# ══════════════════════════════════════════════════════════════════════

def _merge_raw(dst, src):
    """يدمج عدّادات خام في عدّادات خام (للتجميع على أكتر من عملية)."""
    for family in FAMILIES:
        for key in ("signals", "wins", "losses", "open", "ambiguous"):
            dst["counts"][family][key] += src["counts"][family][key]
        dst["counts"][family]["total_r"] += src["counts"][family]["total_r"]
        for dim, buckets in src["breakdowns"][family].items():
            for bkey, bcounts in buckets.items():
                target = dst["breakdowns"][family][dim].setdefault(
                    bkey, _new_counts())
                for key in ("signals", "wins", "losses", "open", "ambiguous"):
                    target[key] += bcounts[key]
                target["total_r"] += bcounts["total_r"]
    u = dst["universe"]
    su = src["universe"]
    u["codes"] += su["codes"]
    u["bars_total"] += su["bars_total"]
    u["signals"] += su["signals"]
    if su["bars_min"] is not None and (u["bars_min"] is None
                                       or su["bars_min"] < u["bars_min"]):
        u["bars_min"] = su["bars_min"]
    if su["bars_max"] is not None and (u["bars_max"] is None
                                       or su["bars_max"] > u["bars_max"]):
        u["bars_max"] = su["bars_max"]
    u["codes_list"] = (u.get("codes_list") or []) + (su.get("codes_list") or [])
    return dst


def _empty_raw():
    return {
        "counts": {f: _new_counts() for f in FAMILIES},
        "breakdowns": {f: _new_breakdown() for f in FAMILIES},
        "universe": {
            "codes": 0, "codes_total": 0, "codes_used": 0, "codes_skipped": 0,
            "codes_list": [], "bars_total": 0, "bars_min": None, "bars_max": None,
            "horizon": 0, "step": 0, "warmup": 0, "start_date": None,
            "signals": 0,
        },
        "notes": [],
    }


def evaluate_raw(bars_by_code, cfg=None, horizon=10, step=1, warmup=320,
                  max_codes=None, start_date=None):
    """المشي التاريخي بيرجّع العدّادات الخام — للمقارنة والتجميع."""
    return _walkforward(bars_by_code, cfg=cfg, horizon=horizon, step=step,
                        warmup=warmup, max_codes=max_codes,
                        start_date=start_date)


def evaluate(bars_by_code, cfg=None, horizon=10, step=1, warmup=320,
             max_codes=None, start_date=None):
    """إحصاء walk-forward لكل الأنماط على كل الأسهم.

    bars_by_code: {code: [شموع]}
    horizon: عدد الشموع اللي بنقيس عليها نتيجة كل إشارة
    step: خطوة التكرار بين النقط
    warmup: أقل عدد شموع قبل ما نبدأ نقيس (320 = نافذة الكاشف)
    max_codes: أقصى عدد أسهم
    start_date: "YYYY-MM-DD" ⇒ نقيس من التاريخ ده بس (مفيش قصّ مخفي)

    المخرجات: dict فيه "families" و "universe" و "notes".
    """
    raw = _walkforward(bars_by_code, cfg=cfg, horizon=horizon, step=step,
                       warmup=warmup, max_codes=max_codes,
                       start_date=start_date)
    families = {}
    for family in FAMILIES:
        metrics = _finalize(raw["counts"][family])
        breakdown = {}
        for dim, buckets in raw["breakdowns"][family].items():
            breakdown[dim] = {k: _finalize(v) for k, v in buckets.items()}
        metrics["breakdown"] = breakdown
        families[family] = metrics
    universe = dict(raw["universe"])
    universe["codes_total"] = len(bars_by_code or {})
    universe["codes_used"] = raw["universe"]["codes"]
    universe["codes_skipped"] = (universe["codes_total"]
                                  - raw["universe"]["codes"])
    return {"families": families, "universe": universe,
            "notes": raw["notes"]}
