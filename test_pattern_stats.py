# -*- coding: utf-8 -*-
"""🧪 اختبار وحدة إحصاء الأنماط (walk-forward) — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش look-ahead**: الكاشف بيشوف الشموع لحد الشمعة i بس.
 ② **الحاجز الزمني**: الإشارة بتقبل لو تاريخها = تاريخ الشمعة i.
 ③ **فصل الحالات**: win / loss / open / ambiguous.
 ④ **مفيش أرقام مخترعة**: family فاضية ⇒ signals=0 والباقي None.
 ⑤ **الاتجاه الهابط**: الـR المحقق سالب عند الخسارة والمضاعف موجب.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pattern_stats

PASSED = 0
FAILED = 0
FAILURES = []


def check(label, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("   ✅", label)
    else:
        FAILED += 1
        FAILURES.append(label)
        print("   ❌", label, ("=> %s" % (detail,)) if detail else "")


STUB = {"status": "ok", "signal": None, "detected_at": None, "calls": []}


def stub_detect(bars, code=None):
    STUB["calls"].append({"code": code, "length": len(bars)})
    if STUB["status"] == "insufficient":
        return {"status": "insufficient", "signals": []}
    if not STUB["signal"]:
        return {"status": "ok", "signals": []}
    sig = dict(STUB["signal"])
    sig["detected_at"] = STUB["detected_at"] or bars[-1]["d"]
    return {"status": "ok", "signals": [sig]}


def run_with_stub(bars_by_code, **kwargs):
    original = pattern_stats.detect
    STUB["calls"] = []
    pattern_stats.detect = stub_detect
    try:
        return pattern_stats.evaluate(bars_by_code, **kwargs)
    finally:
        pattern_stats.detect = original


def make_signal(direction="up", entry=100.0, target=105.0, stop=95.0,
                kind="BREAKOUT", confirmed=True, volume_confirmed=True):
    return {"kind": kind, "direction": direction, "entry": entry,
            "target": target, "stop": stop, "confirmed": confirmed,
            "volume_confirmed": volume_confirmed}


def make_bars(count, highs=None, lows=None):
    bars = []
    for i in range(count):
        bars.append({
            "d": (date(2024, 1, 1) + timedelta(days=i)).isoformat(),
            "o": 100.0,
            "h": 101.0 if highs is None else highs[i],
            "l": 99.0 if lows is None else lows[i],
            "c": 100.0, "v": 1000.0,
        })
    return bars


print("▶️ ① family فاضية ⇒ signals=0 والباقي None")
STUB["signal"] = None
res = run_with_stub({"AAA": make_bars(20)}, horizon=2, warmup=5)
for fam in ("BREAKOUT", "PULLBACK"):
    m = res["families"][fam]
    check("%s: signals=0" % fam, m["signals"] == 0)
    check("%s: hit_rate=None" % fam, m["hit_rate"] is None)
    check("%s: باقي الأرقام None" % fam,
          all(m[k] is None for k in ("wins", "losses", "open", "ambiguous", "avg_r")))

print("\n▶️ ② فصل الحالات")
bars = make_bars(8, highs=[101.0] * 6 + [105.0, 101.0])
STUB["signal"] = make_signal("up", 100.0, 105.0, 95.0)
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
check("win: wins=1", m["wins"] == 1, m)
check("win: hit_rate=1.0", m["hit_rate"] == 1.0, m)
check("win: total_r=1.0", abs(m["total_r"] - 1.0) < 1e-9, m)

bars = make_bars(8, lows=[99.0] * 6 + [95.0, 99.0])
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
check("loss: losses=1", m["losses"] == 1, m)
check("loss: total_r=-1.0", abs(m["total_r"] + 1.0) < 1e-9, m)

bars = make_bars(8, highs=[101.0] * 6 + [105.0, 101.0], lows=[99.0] * 6 + [95.0, 99.0])
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
check("ambiguous: ambiguous=1", m["ambiguous"] == 1, m)
check("ambiguous: بره مقام hit_rate", m["hit_rate"] is None, m)

bars = make_bars(8)
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
check("open: open=1", m["open"] == 1, m)

print("\n▶️ ③ ⛔ مفيش look-ahead")
count, horizon, warmup = 30, 5, 10
STUB["signal"] = make_signal("up", 100.0, 105.0, 95.0)
res = run_with_stub({"AAA": make_bars(count)}, horizon=horizon, warmup=warmup)
lengths = [c["length"] for c in STUB["calls"]]
check("عدد الاستدعاءات = عدد النقاط", len(lengths) == count - horizon - warmup, lengths)
check("الأطوال بتزيد مع i", lengths == sorted(lengths) and len(set(lengths)) == len(lengths))
check("مبنعتش السلسلة كلها", max(lengths) < count, max(lengths))
check("أطول نداء = count - horizon", max(lengths) == count - horizon, max(lengths))
check("أول نداء = warmup + 1", min(lengths) == warmup + 1, min(lengths))
STUB["detected_at"] = "2030-01-01"
res = run_with_stub({"AAA": make_bars(count)}, horizon=horizon, warmup=warmup)
check("إشارة بتاريخ مختلف اتتجاهلَت", res["universe"]["signals"] == 0, res["universe"])
STUB["detected_at"] = None

print("\n▶️ ④ الاتجاه الهابط")
STUB["signal"] = make_signal("down", 100.0, 90.0, 110.0)
bars = make_bars(8, highs=[101.0] * 6 + [110.0, 101.0], lows=[99.0] * 6 + [99.0, 99.0])
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
check("down loss: losses=1", m["losses"] == 1, m)
check("down loss: R المحقق سالب", abs(m["total_r"] + 1.0) < 1e-9, m)
check("المضاعف R موجب للهابط", pattern_stats.risk_multiple("down", 100.0, 90.0, 110.0) > 0)

print("\n▶️ ⑤ الحالات الحدّية")
res = run_with_stub({"AAA": make_bars(6)}, horizon=50, warmup=2)
check("horizon كبير: مفيش كراش", isinstance(res, dict))
check("horizon كبير: مفيش إشارات", res["families"]["BREAKOUT"]["signals"] == 0)
STUB["status"] = "insufficient"
res = run_with_stub({"AAA": make_bars(20)}, horizon=2, warmup=5)
check("insufficient: مفيش إشارات", res["families"]["BREAKOUT"]["signals"] == 0)
check("insufficient: متوثّق في notes", any("insufficient" in n for n in res["notes"]))
STUB["status"] = "ok"
res = run_with_stub({"AAA": make_bars(3)}, horizon=2, warmup=5)
check("سهم قصير: اتخطّى", res["families"]["BREAKOUT"]["signals"] == 0)

print("\n▶️ ⑥ الـbreakdown")
bars = make_bars(8, highs=[101.0] * 6 + [105.0, 101.0])
STUB["signal"] = make_signal("up", 100.0, 105.0, 95.0)
m = run_with_stub({"AAA": bars}, horizon=2, warmup=5)["families"]["BREAKOUT"]
bd = m["breakdown"]
for dim in ("by_direction", "by_year", "by_confirmed", "by_volume_confirmed"):
    check("breakdown فيه %s" % dim, dim in bd, sorted(bd.keys()))
check("by_direction: فيه up", "up" in bd["by_direction"])
check("by_direction: نفس أرقام العائلة", bd["by_direction"]["up"]["signals"] == m["signals"])

print("\n▶️ ⑦ الكاشف الحقيقي")
if pattern_stats.detect is None:
    check("pattern_detector متاح", False, "detect = None")
else:
    res = pattern_stats.evaluate({"AAA": make_bars(200)}, horizon=5, warmup=140)
    check("evaluate رجّع families/universe/notes",
          all(k in res for k in ("families", "universe", "notes")))
    check("العائلتين موجودين",
          all(f in res["families"] for f in ("BREAKOUT", "PULLBACK")))

print("\n" + ("✅ كل الاختبارات عدّت" if not FAILED else "❌ فشل: %d" % FAILED))
for f in FAILURES:
    print("   -", f)
sys.exit(1 if FAILED else 0)
