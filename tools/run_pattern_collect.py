#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
جمع كل الإشارات بتفاصيلها (مرة واحدة) — لأبحاث الفلاتر.

⛔ الفكرة: القياس التاريخي بياخد ~٥٠ دقيقة. لو عايزين نجرّب ٢٠ فلتر
   هنلاقي وقت ما بينفع. فبنعمل反过来: نجمع كل إشارة مرة واحدة بكل
   تفاصيلها (النتيجة + المميزات) في ملف JSONL، وبعدين الفلترة بتحصل
   في ثواني على نفس البيانات.
⛔ نفس منطق `pattern_stats.evaluate` بالظبط (فيه اختبار مقارنة).

الاستخدام:
    python3 tools/run_pattern_collect.py \
        --candles-dir /workspace/pattern_data/candles \
        --start 2021-01-01 --horizon 10 --jobs 2 \
        --out pattern_signals.jsonl
"""
from __future__ import annotations

import argparse
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
    data = {}
    for name in sorted(os.listdir(candles_dir)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(candles_dir, name), "r", encoding="utf-8") as f:
                bars = json.load(f)
        except Exception:
            continue
        if isinstance(bars, list) and bars:
            data[name[:-5]] = bars
    return data


def _work(payload):
    chunk, kwargs = payload
    return pattern_stats.collect_signals(chunk, **kwargs)


def main(argv=None):
    ap = argparse.ArgumentParser(description="جمع الإشارات بأول مرة")
    ap.add_argument("--candles-dir", required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--horizon", type=int, default=10)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=320)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default="pattern_signals.jsonl")
    ap.add_argument("--execution", action="store_true",
                    help="يضيف نماذج التنفيذ والضوابط لكل إشارة")
    ap.add_argument("--cost-pct", type=float, default=0.0,
                    help="تكلفة صفقة كاملة %% (عمولة+دمغة+spread)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.candles_dir):
        print("مجلد الشموع مش موجود: %s" % args.candles_dir)
        return 1
    data = _load(args.candles_dir)
    if not data:
        print("مفيش ملفات شموع في: %s" % args.candles_dir)
        return 1
    codes = sorted(data.keys())
    if args.limit:
        codes = codes[:args.limit]

    kwargs = {"horizon": args.horizon, "step": args.step,
              "warmup": args.warmup, "start_date": args.start,
              "execution": args.execution, "cost_pct": args.cost_pct}
    chunks = []
    size = max(1, len(codes) // max(1, args.jobs) + 1)
    for i in range(0, len(codes), size):
        chunks.append(({c: data[c] for c in codes[i:i + size]}, kwargs))

    t0 = time.time()
    records = []
    if args.jobs > 1 and len(chunks) > 1:
        with Pool(args.jobs) as pool:
            for part in pool.imap_unordered(_work, chunks):
                records.extend(part)
    else:
        for ch in chunks:
            records.extend(pattern_stats.collect_signals(ch[0], **ch[1]))
    elapsed = time.time() - t0

    records.sort(key=lambda r: (r.get("date") or "", r.get("code") or ""))
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    kinds = {}
    for r in records:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("=== جمع الإشارات ===")
    print("أسهم: %d · إشارات: %d · المدة: %.1f ثانية" % (len(codes), len(records), elapsed))
    for k, v in sorted(kinds.items()):
        print("   %s: %d" % (k, v))
    print("اتكتب في: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
