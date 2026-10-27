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
            "by_volume_confirmed": {}}


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
                year = bar_date[:4] if bar_date else "unknown"

                _record(counts[family], outcome, realized_r)
                for dim, key in (
                    ("by_direction", direction),
                    ("by_year", year),
                    ("by_confirmed", "confirmed" if confirmed else "unconfirmed"),
                    ("by_volume_confirmed",
                     "volume_confirmed" if volume_ok else "not_volume_confirmed"),
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
