# -*- coding: utf-8 -*-
"""🧪 اختبار مشغّل المسح اليومي (run_pattern_scan) — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① مجلد الشموع مفقود ⇒ return 1 من غير exception.
 ② الملف بيتكتب بالشكل الصح (generated_at · asof · count · items).
 ③ `insufficient` ⇒ السهم بيتحسب «ناقص» والمسح بيكمّل.
 ④ مفيش إشارات ⇒ count=0 و items=[] (ومفيش رسالة خطأ).
 ⑤ `universe.json` مش بيتعامل معاه كملف شموع.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))   # جذر الريبو
TOOLS = os.path.join(HERE, "tools")
for _p in (HERE, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_spec = importlib.util.spec_from_file_location(
    "run_pattern_scan", os.path.join(TOOLS, "run_pattern_scan.py"))
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def mk_bars(n=140):
    out = []
    for i in range(n):
        p = 100.0 + i * 0.05
        out.append({"d": "2026-%02d-%02d" % ((i // 28) % 12 + 1, (i % 28) + 1),
                    "o": p, "h": p * 1.01, "l": p * 0.99, "c": p, "v": 1000 + i})
    return out


def mk_signal(code, date, rr=2.0, kind="BREAKOUT", direction="up"):
    return {"pattern_id": "PB-%s-%s" % (code, date), "kind": kind,
            "direction": direction, "level": 100.0, "zone_low": 99.0,
            "zone_high": 101.0, "entry": 101.5, "stop": 98.0, "target": 110.0,
            "rr": rr, "timeframe": "1D", "detected_at": date, "confirmed": True,
            "volume_confirmed": True, "trend": "up", "bars_since": 0,
            "evidence": {"touches": 4, "reactions": 3, "atr": 2.0},
            "why": "اختبار"}


def make_dir(tmp, names):
    d = os.path.join(tmp, "candles")
    os.makedirs(d, exist_ok=True)
    for n in names:
        with open(os.path.join(d, n + ".json"), "w", encoding="utf-8") as f:
            json.dump(mk_bars(), f)
    return d


def main():
    tmp = tempfile.mkdtemp(prefix="pat_scan_")
    try:
        print("▶️ ① مجلد مفقود ⇒ return 1")
        out = os.path.join(tmp, "s1.json")
        rc = runner.main(["--candles-dir", os.path.join(tmp, "nope"),
                          "--out", out])
        check(rc == 1, "رجع 1 (مش exception)")
        check(not os.path.exists(out), "مافيش ملف اتكتب")

        print("\n▶️ ② مجلد فاضي ⇒ return 1")
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty, exist_ok=True)
        rc = runner.main(["--candles-dir", empty, "--out", os.path.join(tmp, "s2.json")])
        check(rc == 1, "رجع 1")

        print("\n▶️ ③ مسح حقيقي + universe")
        d = make_dir(tmp, ["AAA", "BBB"])
        with open(os.path.join(d, "universe.json"), "w", encoding="utf-8") as f:
            json.dump({"AAA": {"name": "شركة ألفا", "sector": "الصناعة"},
                       "BBB": {"name": "شركة بيتا", "sector": "البنوك"}},
                      f, ensure_ascii=False)
        out3 = os.path.join(tmp, "s3.json")
        rc = runner.main(["--candles-dir", d, "--out", out3])
        check(rc == 0, "رجع 0")
        check(os.path.exists(out3), "الملف اتكتب")
        if os.path.exists(out3):
            with open(out3, "r", encoding="utf-8") as f:
                payload = json.load(f)
            for k in ("generated_at", "asof", "count", "items"):
                check(k in payload, "في المفتاح: %s" % k)
            check(payload["count"] == len(payload["items"]), "count = عدد العناصر")
            check("universe.json" not in [i.get("code") for i in payload["items"]],
                  "universe.json مااتحسبش سهم")

        print("\n▶️ ④ insufficiency بيتحسب وبيكمّل")
        items, summary = runner.scan({"AAA": mk_bars(50), "BBB": mk_bars(140)},
                                      {})
        check(summary["codes"] == 2, "اتفحص سهمين")
        check(summary["insufficient"] == 1, "واحد ناقص")
        check(summary["ok"] == 1, "واحد جاهز")
        check(bool(summary.get("reasons")), "السبب مكتوب: %s" % summary.get("reasons"))

        print("\n▶️ ⑤ مفيش إشارات ⇒ count=0")
        items, summary = runner.scan({"AAA": mk_bars(140)}, {})
        check(summary["ok"] == 1 and summary["no_pattern"] == 1, "مفيش نمط")
        check(items == [], "مفيش عناصر")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
    for f in fails:
        print("   -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
