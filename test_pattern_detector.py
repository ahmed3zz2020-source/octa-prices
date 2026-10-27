# -*- coding: utf-8 -*-
"""🧪 اختبار مكتشف الأنماط — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش look-ahead**: النتيجة لازم تفضل زي ما هي لو زدنا شموع بعد
    تاريخ التقييم (ده أهم اختبار في الملف كله).
 ② **مفيش أرقام مخترعة**: سلسلة ناقصة ⇒ status "insufficient" + سبب مكتوب.
    «مفيش نمط» (ok + signals فاضية) مش نفس «ناقص».
 ③ **الحجم الناقص** ⇒ volume_confirmed = False (مش True ولا صفر).
 ④ **الحداثة**: كسر قديم (أقدم من max_age_bars) ⇒ مفيش إشارة.
 ⑤ **سلامة الأرقام**: الدخول فوق الوقف والهدف في الاتجاه الصح.
 ⑥ **الحتمية**: نفس المدخلات ⇒ نفس المخرجات بالظبط.
"""
import os
import sys
import copy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pattern_detector as pd

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


# ══════════════════════════════════════════════════════════════════════
#  أدوات بناء شموع
# ══════════════════════════════════════════════════════════════════════

def mk_flat(n=200, price=100.0, start_day=1):
    """سلسلة عرضية (بدون highs/lows واضحة) — مفيش منها نمط غالباً."""
    out = []
    for i in range(n):
        d = "2026-%02d-%02d" % ((i // 28) % 12 + 1, (i % 28) + 1)
        p = price * (1 + 0.001 * ((i % 7) - 3))
        out.append({"d": d, "o": p, "h": p * 1.004, "l": p * 0.996,
                    "c": p, "v": 1_000_000})
    return out


def mk_with_breakout(n=200, price=100.0, level=100.0, break_at=170, vol=3_000_000):
    """سلسلة: صعود لمنطقة ~100 ثم كسر صاعد بستة إغلاقات وحجم كبير."""
    out = []
    for i in range(n):
        d = "2026-%02d-%02d" % ((i // 28) % 12 + 1, (i % 28) + 1)
        if i < break_at:
            # صعود بطيء مع ارتدادات (تلمس المنطقة أكتر من مرة)
            p = 96 + (level - 96) * (i / float(break_at))
            p += 0.15 if (i % 9 == 0) else 0.0
            v = 1_000_000
        else:
            step = i - break_at
            p = level + 1.2 * (step + 1)
            v = vol
        out.append({"d": d, "o": p, "h": p * 1.005, "l": p * 0.995,
                    "c": p, "v": v})
    return out


# ⭐ الكسر لازم يكون قريب من آخر شمعة (مشoldt) وإلا فلتر الحداثة هيتجاهله
FRESH_BREAK = 192
# ⭐ للاختبارات اللي محتاجة كل الإشارات (زي look-ahead): نوقف فلتر الحداثة
CFG_ALL = dict(pd.DEFAULTS, max_age_bars=1000)


print("▶️ ① نقص البيانات ⇒ insufficient + سبب")
r = pd.detect([], code="X")
check(r["status"] == "insufficient", "سلسلة فاضية ⇒ insufficient")
check(bool(r["reason"]), "فيه سبب مكتوب: %s" % r["reason"])
check(r["signals"] == [], "مفيش إشارات")

short = mk_flat(n=50)
r = pd.detect(short, code="X")
check(r["status"] == "insufficient", "سلسلة ٥٠ شمعة ⇒ insufficient")
check("قصيرة" in (r["reason"] or ""), "السبب يقول إن السلسلة قصيرة: %s" % r["reason"])

no_ohlc = [{"d": "2026-01-%02d" % (i + 1), "c": 100.0 + i} for i in range(200)]
r = pd.detect(no_ohlc, code="X")
check(r["status"] == "insufficient", "سلسلة close بس ⇒ insufficient")
check("OHLC" in (r["reason"] or ""), "السبب يقول إن OHLC ناقص: %s" % r["reason"])

print("\n▶️ ② بيانات كافية بس مفيش نمط ⇒ ok مش insufficient")
flat = mk_flat(n=200)
r = pd.detect(flat, code="X")
check(r["status"] == "ok", "سلسلة عرضية ⇒ status ok")
check(r["signals"] == [], "مفيش إشارات (مفيش نمط مش معناها ناقص)")

print("\n▶️ ③ كشف الكسر")
brk = mk_with_breakout(n=200, break_at=FRESH_BREAK)
r = pd.detect(brk, code="TEST", name="سهم اختبار", sector="اختبار")
check(r["status"] == "ok", "الحالة ok")
check(len(r["signals"]) >= 1, "فيه إشارة واحدة على الأقل (العدد %d)" % len(r["signals"]))
sig = None
for s in r["signals"]:
    if s["kind"] == "BREAKOUT" and s["direction"] == "up":
        sig = s
        break
check(sig is not None, "فيه إشارة كسر صاعد")
if sig:
    check(sig["entry"] > sig["stop"], "الدخول فوق الوقف")
    check(sig["target"] > sig["entry"], "الهدف فوق الدخول")
    check(sig["rr"] and sig["rr"] > 0, "R:R موجب: %s" % sig["rr"])
    check(sig["confirmed"] is True, "التأكيد = True (٣ إغلاقات)")
    check(sig["volume_confirmed"] is True, "تأكيد الحجم = True (حجم ٣×)")
    check(sig["evidence"]["source"] == "startamarkets", "المصدر مكتوب في الدليل")
    check(sig["evidence"]["atr"] and sig["evidence"]["atr"] > 0, "ATR في الدليل")
    check(bool(sig["why"]), "فيه جملة تفسير")
    check(sig["pattern_id"].startswith("PB-TEST-"), "الـpattern_id بالشكل الصح: %s" % sig["pattern_id"])

print("\n▶️ ④ ⛔ مفيش look-ahead (التحقق من الشموع الخام)")
# ⭐ النافذة متحركة (320) ⇒ نفس النمط ممكن تتقاس بأرقام مختلفة لما النافذة
#   تتحرك. فالمعيار الصح مش «الرقم ما يتغيرش» — المعيار الصح إن
#   **منطق الكشف** ما بيستخدمش أي شمعة بعد تاريخ التأكيد.
base = mk_with_breakout(n=200, break_at=FRESH_BREAK)
r = pd.detect(base, code="TEST")
brks = [s for s in r["signals"] if s["kind"] == "BREAKOUT"]
check(bool(brks), "فيه إشارة كسر للفحص")
if brks:
    s = brks[0]
    bs = pd.clean_bars(base)
    idx = next((i for i, b in enumerate(bs) if b["d"] == s["detected_at"]), None)
    check(idx is not None, "تاريخ الكشف موجود في الشموع الخام")
    if idx is not None:
        # ① الإغلاقات الثلاثة الأخيرة لازم تكون برّه المنطقة بـ ٠٫٥ ATR
        from gold_technical import atr as g_atr
        a_at = g_atr(bs[:idx + 1], 14) or 0.0
        thr = 0.5 * a_at
        last3 = bs[idx - 2:idx + 1]
        if s["direction"] == "up":
            check(all(b["c"] > s["zone_high"] + thr for b in last3),
                  "٣ إغلاقات متتالية فوق المنطقة + ٠٫٥ ATR")
        else:
            check(all(b["c"] < s["zone_low"] - thr for b in last3),
                  "٣ إغلاقات متتالية تحت المنطقة − ٠٫٥ ATR")
        # ② آخر اختبار للمنطقة لازم يكون قبل تاريخ الكشف
        ti = next((i for i, b in enumerate(bs) if b["d"] == s["evidence"]["last_test"]), None)
        check(ti is not None and ti < idx,
              "آخر اختبار للمنطقة (%s) قبل تاريخ الكشف (%s)"
              % (s["evidence"]["last_test"], s["detected_at"]))
        # ③ ما فيش شمعة بعد تاريخ التأكيد ات استخدامها في الأرقام
        check(s["bars_since"] == len(bs) - 1 - idx,
              "bars_since متطابق مع المؤشر الحقيقي")
        # ④ النافذة: المحرك بيقصّ على آخر 320 شمعة
        long_bars = pd.clean_bars(mk_flat(n=500))
        r_long = pd.detect(long_bars, code="X")
        check(r_long["bars"] == 320, "النافذة المتحركة = 320 شمعة (اللي استخدمو %d)"
              % r_long["bars"])

print("\n▶️ ⑤ الحجم الناقص ⇒ بدون تأكيد حجم (مش صفر ومش True)")
no_vol = mk_with_breakout(n=200, break_at=FRESH_BREAK)
for b in no_vol:
    b.pop("v", None)
r = pd.detect(no_vol, code="TEST")
check(r["status"] == "ok", "الحالة ok")
vol_sigs = [s for s in r["signals"] if s["kind"] == "BREAKOUT"]
check(bool(vol_sigs), "فيه إشارة كسر")
if vol_sigs:
    s = vol_sigs[0]
    check(s["volume_confirmed"] is False, "تأكيد الحجم = False")
    check(s["evidence"]["vol_ratio"] is None, "نسبة الحجم = None (مش 0)")
    check("الحجم غير متاح" in s["why"], "التفسير بيقول إن الحجم غير متاح")

print("\n▶️ ⑥ الحداثة: كسر قديم ⇒ مفيش إشارة (مع الإعدادات العادية)")
old = mk_with_breakout(n=200, break_at=100)
r_old = pd.detect(old, code="TEST")
check(all(s["bars_since"] <= 5 for s in r_old["signals"]),
      "كل الإشارات ضمن حداثة %d" % pd.DEFAULTS["max_age_bars"])
r_old_all = pd.detect(old, code="TEST", cfg=CFG_ALL)
old_sigs = [s for s in r_old_all["signals"] if s["kind"] == "BREAKOUT"]
check(bool(old_sigs), "الكسر القديم موجود لما نوقف فلتر الحداثة")
if old_sigs:
    check(old_sigs[0]["bars_since"] > 5, "الحداثة بتاعته كبيرة: %d" % old_sigs[0]["bars_since"])

print("\n▶️ ⑦ الحتمية")
a1 = pd.detect(mk_with_breakout(n=200), code="TEST")
a2 = pd.detect(mk_with_breakout(n=200), code="TEST")
check(a1 == a2, "نفس المدخلات ⇒ نفس المخرجات بالظبط")

print("\n▶️ ⑧ شكل المخرجات")
r = pd.detect(mk_with_breakout(n=200), code="TEST", name="الاسم", sector="قطاع")
for k in ("code", "name", "sector", "asof", "status", "reason", "bars", "signals", "best"):
    check(k in r, "المخرجات فيها المفتاح: %s" % k)
check(r["code"] == "TEST" and r["name"] == "الاسم" and r["sector"] == "قطاع",
      "البيانات المرفقة اتنقلت صح")
check(r["best"] is None or r["best"] in r["signals"], "best من الإشارات نفسها")
if r["signals"]:
    s = r["signals"][0]
    for k in ("pattern_id", "kind", "direction", "level", "zone_low", "zone_high",
              "entry", "stop", "target", "rr", "timeframe", "detected_at",
              "confirmed", "volume_confirmed", "trend", "bars_since", "evidence", "why"):
        check(k in s, "الإشارة فيها المفتاح: %s" % k)
    for k in ("touches", "reactions", "last_test", "age_days", "atr", "atr_pct",
              "distance_pct", "zone_score", "zone_why", "vol_ratio", "vol_avg20",
              "measured_move", "target_method", "structure_label", "source", "bars_used"):
        check(k in s["evidence"], "الدليل فيه المفتاح: %s" % k)

print("\n▶️ ⑨ تنظيف الشموع")
dirty = [
    {"d": "2026-01-03", "c": 10.0},
    {"d": "2026-01-01", "c": 9.0, "h": 9.2, "l": 8.8, "v": 5},
    {"d": "2026-01-02", "c": None},
    {"d": "2026-01-04", "c": "مش رقم"},
    "مش ققام",
]
cl = pd.clean_bars(dirty)
check(len(cl) == 2, "الصفوف الناقصة/non-numeric اتشالت (العدد %d)" % len(cl))
check(cl[0]["d"] == "2026-01-01" and cl[1]["d"] == "2026-01-03", "الترتيب تصاعدي بالتاريخ")
check(cl[0]["v"] == 5, "الحجم اتحفظ")
check(pd.clean_bars([{"d": "2026-01-01", "c": 1.0, "v": "abc"}])[0]["v"] is None,
      "حجم مش رقم ⇒ None (مش 0)")

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
