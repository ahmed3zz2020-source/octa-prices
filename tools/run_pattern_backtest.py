#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تشغيل الاختبار التاريخي (walk-forward) على كاش الشموع الحقيقي.

⛔ مفيش أرقام مخترعة: كل رقم في التقرير من شموع حقيقية اتجابت من المصدر.
⛔ القصّ لازم يكون صريح: لو حدّدنا تاريخ بداية، بيبقى مكتوب في التقرير.
⛔ التوازي: بيشتغل على أكتر من عملية (2 نواة في البيئة) والنتائج بتتجمع
   من العدّادات الخام (مش من متوسطات متوسطات).

الاستخدام:
    python3 tools/run_pattern_backtest.py \
        --candles-dir /workspace/pattern_data/candles \
        --start 2024-01-01 --horizon 10 --out /tmp/backtest.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pattern_stats  # noqa: E402


def _load(candles_dir):
    """يحمّل كل ملفات الشموع + الكون."""
    data = {}
    universe = {}
    upath = os.path.join(os.path.dirname(candles_dir.rstrip("/")), "universe.json")
    if os.path.exists(upath):
        try:
            with open(upath, "r", encoding="utf-8") as f:
                universe = json.load(f)
        except Exception:
            universe = {}
    for name in sorted(os.listdir(candles_dir)):
        if not name.endswith(".json"):
            continue
        code = name[:-5]
        try:
            with open(os.path.join(candles_dir, name), "r", encoding="utf-8") as f:
                bars = json.load(f)
        except Exception:
            continue
        if isinstance(bars, list) and bars:
            data[code] = bars
    return data, universe


def _work(payload):
    """يشتغل على دفعة من الأكواد ويرجّع العدّادات الخام."""
    chunk, kwargs = payload
    raw = pattern_stats.evaluate_raw(chunk, **kwargs)
    return raw


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="اختبار تاريخي لمكتشف الأنماط")
    ap.add_argument("--candles-dir", required=True)
    ap.add_argument("--start", default=None, help="YYYY-MM-DD — بداية القياس")
    ap.add_argument("--horizon", type=int, default=10)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=320)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.candles_dir):
        print("مجلد الشموع مش موجود: %s" % args.candles_dir)
        return 1
    data, universe = _load(args.candles_dir)
    if not data:
        print("مفيش ملفات شموع في: %s" % args.candles_dir)
        return 1
    codes = sorted(data.keys())
    if args.limit:
        codes = codes[:args.limit]

    kwargs = {"horizon": args.horizon, "step": args.step,
              "warmup": args.warmup, "start_date": args.start}
    chunks = []
    size = max(1, len(codes) // max(1, args.jobs) + 1)
    for i in range(0, len(codes), size):
        part = {c: data[c] for c in codes[i:i + size]}
        chunks.append((part, kwargs))

    t0 = time.time()
    merged = pattern_stats._empty_raw()
    if args.jobs > 1 and len(chunks) > 1:
        with Pool(args.jobs) as pool:
            for raw in pool.imap_unordered(_work, chunks):
                pattern_stats._merge_raw(merged, raw)
    else:
        for ch in chunks:
            pattern_stats._merge_raw(merged, pattern_stats.evaluate_raw(ch[0], **ch[1]))
    elapsed = time.time() - t0

    families = {}
    for fam in pattern_stats.FAMILIES:
        m = pattern_stats._finalize(merged["counts"][fam])
        bd = {}
        for dim, buckets in merged["breakdowns"][fam].items():
            bd[dim] = {k: pattern_stats._finalize(v) for k, v in buckets.items()}
        m["breakdown"] = bd
        families[fam] = m
    universe_out = dict(merged["universe"])
    universe_out["codes_total"] = len(codes)
    # ⭐ الـmerge بيرجّع العدّادات بس ⇒ horizon/warmup/start_date من الـCLI
    universe_out["horizon"] = args.horizon
    universe_out["step"] = args.step
    universe_out["warmup"] = args.warmup
    universe_out["start_date"] = args.start
    universe_out["codes_skipped"] = len(codes) - universe_out["codes"]
    result = {"families": families, "universe": universe_out,
              "notes": merged["notes"],
              "meta": {"elapsed_sec": round(elapsed, 1),
                       "jobs": args.jobs, "candles_dir": args.candles_dir,
                       "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}}

    # ملخص نصي
    print("=== الاختبار التاريخي لمكتشف الأنماط ===")
    print("أسهم: %d · إشارات: %d · المدة: %.1f ثانية"
          % (universe_out["codes"], universe_out["signals"], elapsed))
    if args.start:
        print("بداية القياس: %s" % args.start)
    print("horizon=%d شمعة · step=%d · warmup=%d"
          % (args.horizon, args.step, args.warmup))
    print("")
    for fam, m in families.items():
        print("%s: إشارات %s" % (fam, m["signals"]))
        if m["signals"] == 0:
            continue
        hr = m["hit_rate"]
        print("   فوز %s · خسارة %s · مفتوحة %s · ملتبسة %s"
              % (m["wins"], m["losses"], m["open"], m["ambiguous"]))
        print("   نسبة النجاح: %s" % ("%.1f%%" % (hr * 100) if hr is not None else "—"))
        print("   متوسط R المحقق: %s"
              % ("%.2f" % m["avg_r"] if m["avg_r"] is not None else "—"))
        for dim in ("by_direction", "by_confirmed", "by_volume_confirmed",
                    "by_fillable"):
            parts = []
            for k, v in sorted(m["breakdown"][dim].items()):
                if not v["signals"]:
                    continue
                h = v["hit_rate"]
                parts.append("%s: %s إشارة · نجاح %s · R %s"
                             % (k, v["signals"],
                                ("%.0f%%" % (h * 100)) if h is not None else "—",
                                ("%.2f" % v["avg_r"]) if v["avg_r"] is not None else "—"))
            if parts:
                print("   %s → %s" % (dim, " | ".join(parts)))
        years = []
        for k, v in sorted(m["breakdown"]["by_year"].items()):
            if not v["signals"]:
                continue
            h = v["hit_rate"]
            years.append("%s: %s (نجاح %s · R %s)"
                         % (k, v["signals"],
                            ("%.0f%%" % (h * 100)) if h is not None else "—",
                            ("%.2f" % v["avg_r"]) if v["avg_r"] is not None else "—"))
        if years:
            print("   حسب السنة → %s" % " | ".join(years))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("")
        print("اتكتب في: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
