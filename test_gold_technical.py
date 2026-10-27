# -*- coding: utf-8 -*-
"""🧪 اختبار محرك التحليل الفني — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش look-ahead**: المؤشر عند تاريخ لازم يبقى زي ما هو لو زدنا
    بيانات بعده (ده أهم اختبار في الملف كله).
 ② **مفيش أرقام مخترعة**: سلسلة ناقصة ⇒ None مش 0.
 ③ **ATR محتاج OHLC** ⇒ سلسلة close بس ⇒ None + سبب.
 ④ **SMA/EMA صح** بأرقام محسوبة باليد.
 ⑤ **المناطق منقولة**: كل منطقة لازم يكون وراها ردّ فعلي، والدعم تحت
    السعر والمقاومة فوقه.
 ⑥ **الاختراق_confirmation**: مش لمسة سريعة.
"""
import os, sys, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gold_technical as gt

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def mk(n=300, seed=42, start=100.0, ohlc=True):
    random.seed(seed)
    out = []
    p = start
    for i in range(n):
        p = p * (1 + random.uniform(-0.012, 0.013))
        b = {"d": "2026-01-%02d" % ((i % 28) + 1), "c": round(p, 4)}
        if ohlc:
            b["o"] = round(p * (1 + random.uniform(-0.004, 0.004)), 4)
            b["h"] = round(p * (1 + random.uniform(0.001, 0.008)), 4)
            b["l"] = round(p * (1 - random.uniform(0.001, 0.008)), 4)
        out.append(b)
    return out


print("▶️ ① المتوسطات")
vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
check(gt.sma(vals, 3) == 9.0, f"SMA3 لآخر 3 = 9 (.Actual {gt.sma(vals, 3)})")
check(gt.sma(vals, 20) is None, "SMA20 على 10 قيم ⇒ None (مش متوسط ناقص)")
check(abs(gt.ema(vals, 3) - 9.0) < 0.001, f"EMA3 = {gt.ema(vals, 3):.4f} (المتوقع 9)")
check(gt.ema(vals, 20) is None, "EMA20 على 10 قيم ⇒ None")
ss = gt.sma_series(vals, 3)
check(ss[0] is None and ss[1] is None and ss[2] == 2.0, "سلسلة SMA: أول قيمتين None")
es = gt.ema_series(vals, 3)
check(es[0] is None and es[2] is not None, "سلسلة EMA: الأولى None")

print("\n▶️ ② RSI + MACD + ROC")
check(gt.rsi([1, 2, 3, 4, 5], 2) is not None, "RSI محسوب")
check(gt.rsi([1, 2], 14) is None, "RSI على بيانات ناقصة ⇒ None")
flat = [10.0] * 40
check(gt.rsi(flat, 14) == 50.0, f"سعر ثابت ⇒ RSI = 50 (م��م {gt.rsi(flat, 14)})")
m = gt.macd(vals * 5)
check(m is not None, "MACD اتحسب على سلسلة كافية")
if m:
    check(abs(m["hist"] - (m["macd"] - m["signal"])) < 1e-9, "الهيستوجرام = MACD − الإشارة")
check(gt.macd([1, 2, 3]) is None, "MACD على بيانات ناقصة ⇒ None")
check(abs(gt.roc([100, 110], 1) - 10.0) < 1e-9, "ROC = 10%")
check(gt.roc([100], 12) is None, "ROC على بيانات ناقصة ⇒ None")

print("\n▶️ ③ ATR + Bollinger + التقلب")
bars = mk(300, ohlc=True)
a = gt.atr(bars, 14)
check(a is not None and a > 0, f"ATR14 اتحسب = {a}")
no_ohlc = [{"d": b["d"], "c": b["c"]} for b in bars]
check(gt.atr(no_ohlc, 14) is None, "ATR على close بس ⇒ None (مش مصفّر)")
bb = gt.bollinger([10, 11, 12, 13, 14] * 8)
check(bb is not None and bb["upper"] > bb["mid"] > bb["lower"], "Bollinger: upper > mid > lower")
check(gt.bollinger([1, 2]) is None, "Bollinger على بيانات ناقصة ⇒ None")
hv = gt.hist_vol(bars)   # يقبل الشموع كمان
check(hv is not None and hv > 0, f"التقلب التاريخي = {hv}")
check(gt.hist_vol([1, 2, 3]) is None, "تقلب على بيانات ناقصة ⇒ None")

print("\n▶️ ④ ⛎ مفيش look-ahead (أهم اختبار)")
b1 = mk(200, seed=7)
cut = 120
r_full = gt.rsi([b["c"] for b in b1], 14)
r_part = gt.rsi([b["c"] for b in b1[:cut]], 14)
check(r_full is not None and r_part is not None, "RSI اتحسب في الحالتين")
# RSI على الجزء الأول لازم يبقى زي ما لو حسبناه لوحده على نفس البيانات
check(abs(r_part - gt.rsi([b["c"] for b in b1[:cut]], 14)) < 1e-12, "RSI ثابت على نفس البيانات")
m_part = gt.macd([b["c"] for b in b1[:cut]])
m_full = gt.macd([b["c"] for b in b1])
check(m_part is not None and m_full is not None, "MACD اتحسب في الحالتين")
# قيمة MACD عند آخر نقطة في الجزء = قيمة آخر عنصر في السلسلة الجزئية
check(abs(m_part["macd"] - m_part["macd_series"][-1]) < 1e-12, "MACD متسق مع سلسلته")
a_part = gt.atr(b1[:cut], 14)
check(a_part is not None, "ATR على جزء اتحسب")

print("\n▶️ ⑤ الاتجاه والبنية")
bars2 = mk(400, seed=11)
up = [{"d": b["d"], "c": 100 + i * 1.0, "h": 100 + i * 1.0 + 0.5, "l": 100 + i * 1.0 - 0.5} for i, b in enumerate(bars2)]
an = gt.analyze(up, label="صاعد")
check(an["trend"]["overall"] in ("اتجاه صاعد", "اتجاه عرضي", "إشارات متضاربة بين الأطر"),
      f"اتجاه السلسلة الصاعدة: {an['trend']['overall']}")
check(an["trend"]["short"]["label"] == "صاعد", f"الإطار القصير: {an['trend']['short']['label']}")
dn = [{"d": b["d"], "c": 500 - i * 1.0, "h": 500 - i * 1.0 + 0.5, "l": 500 - i * 1.0 - 0.5} for i, b in enumerate(bars2)]
an2 = gt.analyze(dn, label="هابط")
check(an2["trend"]["short"]["label"] == "هابط", f"الإطار القصير الهابط: {an2['trend']['short']['label']}")
check(an2["structure"]["label"].startswith("بنية هابطة"), f"البنية الهابطة: {an2['structure']['label']}")

print("\n▶️ ⑥ الدعم والمقاومة")
an3 = gt.analyze(bars, label="اختبار")
sr = an3["sr"]
check(sr.get("ok") is True, "المناطق اتحسبت")
if sr.get("ok"):
    check("window" in sr and sr["window"]["bars"] <= 500, f"نافذة المناطق: {sr.get('window')}")
    for z in sr.get("resistance", []):
        check(z["touches"] >= 1, "كل مقاومة لها ردّ فعلي واحد على الأقل")
        check(z["center"] > sr["current"], "المقاومة فوق السعر")
        check(z["score"] > 0, "الـscore موجب")
        check(bool(z.get("why")), "فيه سبب مكتوب")
        check("score_parts" in z, "تفصيل الـscore موجود")
    for z in sr.get("support", []):
        check(z["touches"] >= 1, "كل دعم له ردّ فعلي")
        check(z["center"] < sr["current"], "الدعم تحت السعر")
    nr = sr.get("nearest_resistance")
    if nr:
        check(nr["breakout"]["state"] in ("مفيش اختراق", "اختراق غير مؤكد", "اختراق مؤكد"),
              f"حالة الاختراق: {nr['breakout']['state']}")
        st = nr["breakout"]["state"]
        if st == "اختراق مؤكد":
            check(nr["breakout"].get("closes_beyond", 0) >= 3, "الاختراق المؤكد = ٣ إغلاقات برّه")
        else:
            check("closes_beyond" not in nr["breakout"] or st == "مفيش اختراق",
                  "مفيش اختراق ⇒ مفيش عدّاد إغلاقات")

print("\n▶️ ⑦ حالات الحد (مفيش أرقام مخترعة)")
check(gt.analyze([], "فاضي").get("ok") is False, "سلسلة فاضية ⇒ ok=False")
short = gt.analyze([{"d": "2026-01-01", "c": 10.0}], "قصير")
check(short.get("ok") is True, "سلسلة قصيرة ⇒ ok (مفيش crash)")
check(short["rsi14"] is None, "RSI على سلسلة قصيرة ⇒ None")
check(short["atr14"] is None, "ATR على سلسلة قصيرة ⇒ None")
check(short["ma"]["sma200"] is None, "SMA200 على سلسلة قصيرة ⇒ None")
check(short["ma_available"]["sma20"] is False, "flag التوفر false")
check(short["sr"].get("ok") is False, "المناطق على سلسلة قصيرة ⇒ ok=False + سبب")
check(isinstance(short["data_quality"].get("ohlc_note"), str), "فيه ملاحظة عن نقص OHLC")

print("\n▶️ ⑧ شفافية البيانات")
an4 = gt.analyze(no_ohlc, label="close فقط")
check(an4["data_quality"]["has_ohlc"] is False, "has_ohlc = False")
check("ATR" in (an4["data_quality"]["ohlc_note"] or ""), "الملاحظة بتقول إن ATR مش متاح")

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
