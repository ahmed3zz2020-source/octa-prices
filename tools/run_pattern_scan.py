#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مسح يومي: يكشف الأنماط في كل الأسهم ويكتب قائمة الأنماط (shortlist).

⛔ مفيش أرقام مخترعة: كل رقم جاي من كاش الشموع + محرك pattern_detector.
⛔ «مفيش نمط» مش خطأ: السهم اللي مفيش عنده نمط بيتحسب «مفيش نمط» مش «ناقص».
⛔ «ناقص» (بيانات مش كفاية) بيتحسب لوحده وبيظهر في الملخص.
⛔ بيستخدم نفس النافذة المتحركة (320) وبنفس القواعد زي الاختبار التاريخي.

الاستخدام:
    python3 tools/run_pattern_scan.py \
        --candles-dir /workspace/pattern_data/candles \
        --out pattern_shortlist.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pattern_detector as pd  # noqa: E402


def load_candles(candles_dir):
    """يحمّل ملفات الشموع (كل ملف = مصفوفة شموع) + الكون (اسم/قطاع)."""
    data = {}
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
    universe = {}
    upath = os.path.join(os.path.dirname(candles_dir.rstrip("/")), "universe.json")
    if os.path.exists(upath):
        try:
            with open(upath, "r", encoding="utf-8") as f:
                universe = json.load(f)
        except Exception:
            universe = {}
    return data, universe


def scan(data, universe, cfg=None, limit=None):
    """يمسح كل سهم ويرجّع (الإشارات، ملخص)."""
    items = []
    summary = {"codes": 0, "ok": 0, "insufficient": 0, "no_pattern": 0, "signals": 0}
    reasons = {}
    codes = sorted(data.keys())
    if limit:
        codes = codes[:limit]
    for code in codes:
        summary["codes"] += 1
        res = pd.detect(data[code], code=code, cfg=cfg)
        if res.get("status") != "ok":
            summary["insufficient"] += 1
            reason = res.get("reason") or "غير معروف"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        summary["ok"] += 1
        sigs = res.get("signals") or []
        if not sigs:
            summary["no_pattern"] += 1
            continue
        meta = (universe or {}).get(code) or {}
        for s in sigs:
            item = dict(s)
            item["code"] = code
            item["name"] = meta.get("name") or code
            item["sector"] = meta.get("sector")
            items.append(item)
        summary["signals"] += len(sigs)
    items.sort(key=lambda s: (s.get("detected_at") or "", s.get("rr") or -99),
               reverse=True)
    summary["reasons"] = reasons
    return items, summary


def _fmt(x, nd=2):
    if x is None:
        return "—"
    try:
        return ("%%.%df" % nd) % float(x)
    except (TypeError, ValueError):
        return str(x)


def print_table(items, summary):
    """طباعة على شكل كتل (سطرين لكل إشارة) — أوضح من جدول عربي."""
    print("=== مسح الأنماط اليومي ===")
    print("أسهم مفحوصة: %d · جاهزة: %d · ناقصة: %d · مفيش نمط: %d · إشارات: %d"
          % (summary["codes"], summary["ok"], summary["insufficient"],
             summary["no_pattern"], summary["signals"]))
    if summary.get("reasons"):
        for reason, count in sorted(summary["reasons"].items(),
                                    key=lambda kv: -kv[1]):
            print("سبب النقص: %s (%d سهم)" % (reason, count))
    if not items:
        print("مفيش أنماط دلوقتي.")
        return
    print("")
    for s in items[:25]:
        kind = "كسر منطقة" if s.get("kind") == "BREAKOUT" else "ارتداد من منطقة"
        direction = "صاعد" if s.get("direction") == "up" else "هابط"
        ev = s.get("evidence") or {}
        print("%s — %s" % (s.get("code") or "—", s.get("name") or "—"))
        print("   %s %s · المستوى %s · الدخول %s · الوقف %s · الهدف %s · R:R %s"
              % (kind, direction, _fmt(s.get("level")), _fmt(s.get("entry")),
                 _fmt(s.get("stop")), _fmt(s.get("target")), _fmt(s.get("rr"), 1)))
        print("   %d ردّ فعلي · %s · تاريخ الكشف %s"
              % (ev.get("touches", 0),
                 "تأكيد حجم" if s.get("volume_confirmed") else "بدون تأكيد حجم",
                 s.get("detected_at") or "—"))
    if len(items) > 25:
        print("وفي %d إشارة تانية في الملف." % (len(items) - 25))


def main(argv=None):
    ap = argparse.ArgumentParser(description="مسح يومي لمكتشف أنماط OCTA")
    ap.add_argument("--candles-dir", required=True)
    ap.add_argument("--out", default="pattern_shortlist.json")
    ap.add_argument("--cfg", default=None, help="ملف JSON اختياري للإعدادات")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    if not os.path.isdir(args.candles_dir):
        print("مجلد الشموع مش موجود: %s" % args.candles_dir)
        return 1
    try:
        data, universe = load_candles(args.candles_dir)
    except Exception as e:
        print("تعذّر قراءة الشموع: %s" % e)
        return 1
    if not data:
        print("مفيش ملفات شموع في: %s" % args.candles_dir)
        return 1

    cfg = None
    if args.cfg:
        try:
            with open(args.cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print("تعذّر قراءة ملف الإعدادات: %s" % e)
            return 1

    t0 = time.time()
    items, summary = scan(data, universe, cfg=cfg, limit=args.limit)
    elapsed = time.time() - t0

    asof = None
    for s in items:
        if s.get("detected_at"):
            asof = s["detected_at"]
            break
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "asof": asof,
        "count": len(items),
        "items": items,
        "summary": summary,
        "elapsed_sec": round(elapsed, 1),
    }
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("تعذّر كتابة الملف: %s" % e)
        return 1

    print_table(items, summary)
    print("")
    print("اتكتب في: %s (%d إشارة · %.1f ثانية)" % (args.out, len(items), elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
