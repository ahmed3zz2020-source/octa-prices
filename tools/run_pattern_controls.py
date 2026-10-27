#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 ضوابط محرك الأنماط — قِس: هل للمحرّك أفضلية حقيقية؟

⛔ ليه ده مهم: رقم «٨١٪ نجاح» لوحده مش بيقول حاجة. لازم نقارنه
   بأساس ساذج بنفس الشروط ونفس أسلوب التنفيذ. من غير كده، أي
   كسرalos يكسب.

📌 الضوابط الثلاثة:
   ① محرّك OCTA (كسر المناطق) — بنفس مستويات ثابتة (هدف ٢ ATR / وقف ٠٫٥ ATR)
      عشان المقارنة تكون apples-to-apples.
   ② الأساس الساذج: «إغلاق فوق أعلى ٢٠ شمعة سابقة» + تأكيد حجم.
   ③ случай عشوائي: دخول عشوائي بنفس_levels_ ونفس التوقيت.

📌 كلهم بيتقاسوا بنفس:
   · أسلوب التنفيذ: الدخول بسعر افتتاح الشمعة التالية (واقعي)
   · أفق: ١٠ شموع
   · تكلفة: ٠٫٣٥٪ لكل صفقة (عمولة + دمغة + سبريد)
   · الصفقات المفتوحة بتتقوّم بسعر آخر شمعة (mark-to-market)

⛔ ملاحظة: مفيش look-ahead — كل الحسابات بتستخدم الشمعة i وبيبعدها بس.
"""
import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pattern_stats as ps  # noqa: E402

HORIZON = 10
COST_PCT = 0.35
TARGET_ATR = 2.0
STOP_ATR = 0.5
WARMUP = 320
BENCH_LOOKBACK = 20
VOL_MULT = 1.3


def _atr_series(bars, n=14):
    """سلسلة ATR (Wilder) — نفس gold_technical.atr."""
    out = [None] * len(bars)
    if len(bars) < n + 1:
        return out
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < n:
        return out
    a = sum(trs[:n]) / float(n)
    out[n] = a
    for k in range(n, len(trs)):
        a = (a * (n - 1) + trs[k]) / float(n)
        out[k + 1] = a
    return out


def _levels(entry, atr_val, direction):
    if atr_val is None or atr_val <= 0:
        return None
    if direction == "up":
        return entry - STOP_ATR * atr_val, entry + TARGET_ATR * atr_val
    return entry + STOP_ATR * atr_val, entry - TARGET_ATR * atr_val


def _agg(rows):
    """ملخّص: عدد · فوز · خسارة · R لكل إشارة · نسبة الصفقات المنفَّذة."""
    n = len(rows)
    if not n:
        return {"n": 0}
    wins = sum(1 for r in rows if r["status"] == "win")
    losses = sum(1 for r in rows if r["status"] == "loss")
    amb = sum(1 for r in rows if r["status"] == "ambiguous")
    opened = sum(1 for r in rows if r["status"] == "open")
    filled = sum(1 for r in rows if r["status"] not in ("not_filled",))
    r_all = sum(r["r_net"] for r in rows) / float(n)
    r_filled = (sum(r["r_net"] for r in rows if r["status"] != "not_filled")
                / float(filled)) if filled else 0.0
    hit = (wins / float(wins + losses)) if (wins + losses) else 0.0
    return {"n": n, "wins": wins, "losses": losses, "ambiguous": amb,
            "open": opened, "filled": filled,
            "hit_rate": round(hit, 4), "r_per_signal": round(r_all, 4),
            "r_per_filled": round(r_filled, 4)}


def _bench_signals(bars, atr_s):
    """الأساس الساذج: إغلاق فوق أعلى ٢٠ شمعة + حجم ≥ ١٫٣× متوسط ٢٠."""
    out = []
    n = len(bars)
    vols = [b.get("v") or 0 for b in bars]
    for i in range(WARMUP, n):
        a = atr_s[i]
        if not a:
            continue
        hi_prev = max(bars[j]["h"] for j in range(i - BENCH_LOOKBACK, i))
        c = bars[i]["c"]
        if c <= hi_prev:
            continue
        v0 = vols[i]
        past = [vols[j] for j in range(max(0, i - 20), i) if vols[j]]
        if not past or v0 < VOL_MULT * (sum(past) / float(len(past))):
            continue
        out.append({"index": i, "date": bars[i].get("d"), "direction": "up",
                    "entry": c, "atr": a})
    return out


def _rand_signals(bars, atr_s, k, seed):
    """حالة عشوائية: دخول عشوائي بنفس المستويات."""
    rnd = random.Random(seed)
    idxs = list(range(WARMUP, len(bars)))
    if not idxs:
        return []
    rnd.shuffle(idxs)
    out = []
    for i in idxs[:k]:
        a = atr_s[i]
        if not a:
            continue
        out.append({"index": i, "date": bars[i].get("d"), "direction": "up",
                    "entry": bars[i]["c"], "atr": a})
    return out


def _evaluate(bars, sig, cost_pct=COST_PCT):
    """تقييم إشارة بأسلوب التنفيذ الواقعي (دخول بافتتاح الشمعة التالية)."""
    i = sig["index"]
    if i + 1 >= len(bars):
        return None
    lv = _levels(sig["entry"], sig.get("atr"), sig["direction"])
    if not lv:
        return None
    stop, target = lv
    res = ps._simulate(bars, i + 1, HORIZON, sig["direction"], sig["entry"],
                       stop, target, skip_if_beyond=True, cost_pct=cost_pct)
    res["date"] = sig.get("date")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="ضوابط محرك الأنماط")
    ap.add_argument("--candles-dir", required=True)
    ap.add_argument("--signals", default=None,
                    help="ملف JSONL من run_pattern_collect.py (للمقارنة apples-to-apples)")
    ap.add_argument("--out", default="pattern_controls.json")
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args(argv)

    data = {}
    for fn in sorted(os.listdir(args.candles_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(args.candles_dir, fn), "r", encoding="utf-8") as f:
                arr = json.load(f)
        except Exception:
            continue
        if not arr:
            continue
        code = fn[:-5]
        bars = []
        for r in arr:
            if not isinstance(r, dict):
                continue
            d = r.get("d") or r.get("date")
            o = r.get("o"); h = r.get("h"); l = r.get("l"); c = r.get("c")
            if d is None or o is None or h is None or l is None or c is None:
                continue
            bars.append({"d": d, "o": float(o), "h": float(h), "l": float(l),
                         "c": float(c), "v": float(r.get("v") or 0)})
        if len(bars) > WARMUP + 30:
            data[code] = bars
    if not data:
        print("⛔ مفيش شموع")
        return 1

    # ⭐ إشارات المحرّك من ملف الجمع (بنفس المستويات الثابتة للمقارنة)
    octa_rows = []
    if args.signals and os.path.exists(args.signals):
        idx_by_code = {}
        for code, bars in data.items():
            idx_by_code[code] = {b["d"]: i for i, b in enumerate(bars)}
        with open(args.signals, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("kind") != "BREAKOUT":
                    continue
                code = r.get("code")
                idx = idx_by_code.get(code, {}).get(r.get("date"))
                if idx is None:
                    continue
                bars = data[code]
                atr_s = _atr_series(bars)
                a = atr_s[idx]
                if not a:
                    continue
                octa_rows.append({
                    "code": code, "index": idx, "date": r.get("date"),
                    "direction": r.get("direction") or "up",
                    "entry": r.get("entry"), "atr": a,
                })

    bench_rows, rand_rows = [], []
    t0 = time.time()
    for code, bars in data.items():
        atr_s = _atr_series(bars)
        for s in _bench_signals(bars, atr_s):
            if args.start and (s["date"] or "") < args.start:
                continue
            res = _evaluate(bars, s)
            if res:
                res["code"] = code
                bench_rows.append(res)
        for s in _rand_signals(bars, atr_s, 3, hash(code) & 0xffff):
            if args.start and (s["date"] or "") < args.start:
                continue
            res = _evaluate(bars, s)
            if res:
                res["code"] = code
                rand_rows.append(res)

    # ⭐ تقييم إشارات المحرّك بنفس المستويات الثابتة
    octa_eval = []
    for r in octa_rows:
        bars = data[r["code"]]
        lv = _levels(r["entry"], r["atr"], r["direction"])
        if not lv:
            continue
        stop, target = lv
        res = ps._simulate(bars, r["index"] + 1, HORIZON, r["direction"],
                           r["entry"], stop, target, skip_if_beyond=True,
                           cost_pct=COST_PCT)
        res["date"] = r["date"]
        res["code"] = r["code"]
        octa_eval.append(res)

    def _by_year(rows):
        g = defaultdict(list)
        for r in rows:
            g[(r.get("date") or "")[:4]].append(r)
        return {y: _agg(v) for y, v in sorted(g.items())}

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": {
            "execution": "next_open (الدخول بافتتاح الشمعة التالية)",
            "horizon": HORIZON, "cost_pct": COST_PCT,
            "levels": "هدف ٢ ATR / وقف ٠٫٥ ATR (ثابت — للمقارنة)",
            "start": args.start,
        },
        "octa": _agg(octa_eval),
        "octa_by_year": _by_year(octa_eval),
        "benchmark_20d_high": _agg(bench_rows),
        "benchmark_by_year": _by_year(bench_rows),
        "random": _agg(rand_rows),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("=== ضوابط محرك الأنماط ===")
    for key, label in (("octa", "محرّك OCTA"),
                       ("benchmark_20d_high", "أساس ساذج (أعلى ٢٠ شمعة)"),
                       ("random", "حالة عشوائية")):
        m = out[key]
        print("  %-28s n=%-6s نجاح=%-6s R/إشارة=%-7s" % (
            label, m.get("n"), m.get("hit_rate"), m.get("r_per_signal")))
    print("  اتكتب في: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
