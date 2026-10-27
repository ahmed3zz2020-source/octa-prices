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
import json
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

print("\n▶️ ⑧ ⛔ collect_signals يطابق evaluate (نفس المسار بالظبط)")
if pattern_stats.detect is not None:
    import pattern_detector as _pdet
    # سلسلة حقيقية: نتحقق إن العدّادات متطابقة مع الإشارات المجموعة
    _real = None
    _cd = "/workspace/pattern_data/candles"
    if os.path.isdir(_cd):
        for _n in sorted(os.listdir(_cd)):
            if _n.endswith(".json"):
                try:
                    with open(os.path.join(_cd, _n), "r", encoding="utf-8") as _f:
                        _real = json.load(_f)
                except Exception:
                    _real = None
                break
    if _real:
        _bars = {"REAL": _real}
        _ev = pattern_stats.evaluate(_bars, horizon=10, warmup=320)
        _recs = pattern_stats.collect_signals(_bars, horizon=10, warmup=320)
        _counted = sum(_ev["families"][f]["signals"] for f in ("BREAKOUT", "PULLBACK"))
        check("عدد الإشارات المجمّعة = عدد المحسوب في evaluate",
              len(_recs) == _counted, "%d مقابل %d" % (len(_recs), _counted))
        if _recs and _counted:
            _w = sum(1 for r in _recs if r["outcome"] == "win")
            _l = sum(1 for r in _recs if r["outcome"] == "loss")
            _fam = _ev["families"]["BREAKOUT"]
            _check_ok = True
            for _f in ("BREAKOUT", "PULLBACK"):
                _m = _ev["families"][_f]
                if _m["signals"] == 0:
                    continue
                _sub = [r for r in _recs if r["kind"] == _f]
                if sum(1 for r in _sub if r["outcome"] == "win") != _m["wins"]:
                    _check_ok = False
                if sum(1 for r in _sub if r["outcome"] == "loss") != _m["losses"]:
                    _check_ok = False
            check("النتائج (فوز/خسارة) متطابقة لكل عائلة", _check_ok)
            check("كل سجل فيه النتيجة والحقول الأساسية",
                  all(all(k in r for k in ("code", "kind", "direction", "date",
                                          "outcome", "r", "fillable", "atr_pct",
                                          "zone_score", "turnover")) for r in _recs))
    else:
        check("مفيش كاش شموع محلي للاختبار المقارن", True, "تخطّي")

print("\n▶️ ٧ نماذج التنفيذ والضوابط (٢٨ أكتوبر ٢٠٢٦)")
_B = [
 {"d": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
 {"d": "2026-01-02", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},   # الإشارة
 {"d": "2026-01-03", "o": 101, "h": 106, "l": 100.5, "c": 105, "v": 1000},  # لمس الهدف
 {"d": "2026-01-04", "o": 105, "h": 106, "l": 104, "c": 105, "v": 1000},
]
_ex = pattern_stats._exec_variants(_B, 1, 10, "up", 101.0, 99.0, 105.0,
                                   cost_pct=0.35)
check("النماذج الأربعة موجودة",
      all(k in _ex for k in ("planned", "next_open", "limit", "flip")),
      str(sorted(_ex.keys())))
check("الدخول بفتتاح الشمعة التالية ⇒ فوز",
      _ex["next_open"]["status"] == "win", str(_ex["next_open"]))
check("المفاضلة (plan) تبدأ من الشمعة بعد الإشارة (مش الشمعة نفسها)",
      _ex["planned"]["status"] == "win", str(_ex["planned"]))
check("الانعكاس (ضابط) لازم يخسر",
      _ex["flip"]["status"] == "loss", str(_ex["flip"]))
check("التكلفة بتتخفض من الـR",
      _ex["planned"]["r_net"] < _ex["planned"]["r"],
      "%s مقابل %s" % (_ex["planned"]["r_net"], _ex["planned"]["r"]))

# ⛔ حالة: الافتتاح تجاوز الهدف ⇒ الصفحة فاتتها (مش خسارة)
_B2 = [
 {"d": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
 {"d": "2026-01-02", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
 {"d": "2026-01-03", "o": 106, "h": 107, "l": 105.5, "c": 106, "v": 1000},
]
_ex2 = pattern_stats._exec_variants(_B2, 1, 10, "up", 101.0, 99.0, 105.0)
check("لو الافتتاح عدّى الهدف ⇒ not_filled (مش خسارة)",
      _ex2["next_open"]["status"] == "not_filled", str(_ex2["next_open"]))

# ⛔ حالة: ما لمسش الهدف ⇒ open مع mark-to-market (مش 0)
_B3 = [
 {"d": "2026-01-01", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
 {"d": "2026-01-02", "o": 100, "h": 101, "l": 99, "c": 100, "v": 1000},
 {"d": "2026-01-03", "o": 101, "h": 102, "l": 100.5, "c": 102, "v": 1000},
]
_ex3 = pattern_stats._exec_variants(_B3, 1, 10, "up", 101.0, 99.0, 105.0)
check("الصفحة المفتوحة بتتقوّم بالسعر (mark-to-market) مش 0",
      _ex3["planned"]["status"] == "open" and abs(_ex3["planned"]["r"]) > 0,
      str(_ex3["planned"]))
check("الحدود: هدف ووقف متساويين في نفس الشمعة ⇒ ambiguous",
      pattern_stats._simulate(
          [{"d": "x", "o": 100, "h": 110, "l": 90, "c": 100, "v": 1}],
          0, 5, "up", 100, 95, 105)["status"] == "ambiguous")

print("\n" + ("✅ كل الاختبارات عدّت" if not FAILED else "❌ فشل: %d" % FAILED))
for f in FAILURES:
    print("   -", f)
sys.exit(1 if FAILED else 0)
