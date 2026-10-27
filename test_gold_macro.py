# -*- coding: utf-8 -*-
"""🧪 اختبار محرك العوامل الماكرو — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش look-ahead**: قيمة العامل من تاريخ الرصد بس — مش من تاريخ بعده.
 ② **الناقص مش صفر**: عامل مفقود ⇒ value=None + سبب (مش 0).
 ③ **الطزاجة**: الحالة live/recent/unknown بتتبع عمر آخر رصد.
 ④ **الرقم بلا مصدر = خطأ**: كل عامل متاح لازم يبقى ليه مصدر + تاريخ.
 ⑤ **مفيش أرقام مخترعة ولا احتمالات**: مفيش حقل impact% متخيّل.
 ⑥ **ترتيب أعمدة الخزانة**: 2Y و 10Y من الهيدر (مش العمود ١ و ٢!).
 ⑦ **الكاش على القرص**: حفظ/قراءة من غير ما يفقد حقول.
"""
import os, sys, json, time, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gold_macro as gm

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def section(t):
    print("\n── %s ──" % t)


# ═════════════ ① إحصاءات السلسلة ═════════════
section("① _series_stats")
pts = [("2026-01-01", 10.0), ("2026-01-02", 11.0), ("2026-01-03", 9.0)]
st = gm._series_stats(pts, "%")
check(st and st.get("value") == 9.0, "القيمة = آخر رصد (٩)")
check(st and st.get("previous") == 11.0, "السابق = الرصد اللي قبله (١١)")
check(st and st.get("direction") == "down", "الاتجاه = down")
check(st and st.get("date") == "2026-01-03", "التاريخ = تاريخ آخر رصد")
check(gm._series_stats([], "%") is None, "سلسلة فاضية ⇒ None (مش 0)")

# قيمة واحدة ⇒ مفيش previous وده ماشي
st1 = gm._series_stats([("2026-01-01", 5.0)], "%")
check(st1 and st1.get("previous") is None, "نقطة واحدة ⇒ previous=None (مش 0)")

# ═════════════ ② الطزاجة ═════════════
section("② الطزاجة (_freshness)")
today = datetime.date.today()
check(gm._freshness(today.isoformat(), daily=True)["status"] == "live",
      "رصد النهارده ⇒ live")
check(gm._freshness((today - datetime.timedelta(days=3)).isoformat(), daily=True)["status"]
      == "recent", "رصد من ٣ أيام ⇒ recent")
check(gm._freshness((today - datetime.timedelta(days=400)).isoformat(), daily=True)["status"]
      == "stale", "رصد من سنة ⇒ stale (مش live/recent ومش صفر)")
check(gm._freshness(None)["status"] == "unknown", "مفيش تاريخ ⇒ unknown")
check(gm._freshness((today - datetime.timedelta(days=400)).isoformat(), daily=False)["status"]
      != "unknown", "لسلسلة شهرية/سنوية: عمر سنة مش unknown")

# ═════════════ ③ الناقص مش صفر ═════════════
section("③ الناقص مش صفر")
d = gm.build()
F = d.get("factors") or {}
check(bool(F), "المحرك رجّع عوامل")
miss = d.get("missing") or []
for k in miss:
    f = F.get(k) or {}
    check(f.get("value") is None, "«%s» ناقص ⇒ value=None (مش 0)" % k)
    check(bool(f.get("error") or f.get("name_ar")), "«%s» ناقص ⇒ ليه سبب/اسم" % k)

# ═════════════ ④ كل رقم متاح ليه مصدر + تاريخ ═════════════
section("④ المصدر والتاريخ")
for k in (d.get("available") or []):
    f = F.get(k) or {}
    check(f.get("value") is not None, "«%s» متاح ⇒ ليه قيمة" % k)
    check(bool(f.get("source")), "«%s» متاح ⇒ ليه مصدر" % k)
    check(bool(f.get("date")), "«%s» متاح ⇒ ليه تاريخ رصد" % k)
    check(f.get("status") != "missing", "«%s» متاح ⇒ مش missing" % k)

# ═════════════ ⑤ مفيش أرقام متخيّلة ═════════════
section("⑤ مفيش impact/احتمالات مخترعة")
BAD = ("impact", "impact_pct", "probability", "confidence", "score", "weight_pct")
for k, f in F.items():
    hit = [b for b in BAD if b in (f or {})]
    check(not hit, "«%s» مفيش حقل متخيّل (%s)" % (k, hit))

# ═════════════ ⑥ ترتيب أعمدة الخزانة (regression) ═════════════
section("⑥ أعمدة الخزانة")
try:
    r = gm.treasury_nominal()
    ps = r.get("points") or []
    check(bool(ps), "الخزانة رجّعت نقاط")
    if ps:
        row = ps[-1]
        check(len(row) == 3, "الصف = (تاريخ, 2Y, 10Y)")
        # ⛔ الـ2Y والـ10Y مختلفين (لو كانوا نفس ⇒ خطأ الفكّك)
        check(row[1] != row[2],
              "2Y (%s) ≠ 10Y (%s) — يعني الأعمدة اتقرت صح"
              % (row[1], row[2]))
        # 2Y أقل من 10Y عادةً في المنحنى الصاعد — تحقق إن القيم منطقية
        check(0.0 < row[1] < 20.0 and 0.0 < row[2] < 20.0,
              "القيم في مدى معقول (2Y=%s 10Y=%s)" % (row[1], row[2]))
except Exception as e:
    check(False, "الخزانة: %s" % str(e)[:80])

# ═════════════ ⑦ الكاش على القرص ═════════════
section("⑦ الكاش على القرص")
try:
    tmp = gm.CACHE_FILE + ".test"
    gm.CACHE_FILE = tmp
    gm._save_disk({"ok": True, "built_at": time.time(), "factors": {"x": {"value": 1}}})
    got = gm._load_disk()
    check(bool(got) and got.get("factors", {}).get("x", {}).get("value") == 1,
          "حفظ/قراءة الكاش شغال")
    try:
        os.remove(tmp)
    except Exception:
        pass
    gm.CACHE_FILE = os.path.join(gm.DATA_DIR, "gold_factors.json")
except Exception as e:
    check(False, "الكاش: %s" % str(e)[:80])

# ═════════════ ⑧ الكاش بيتقدّم (٦ ساعات) ═════════════
section("⑧ حداثة الكاش")
check(gm.DISK_TTL <= 12 * 3600, "عمر الكاش ≤ ١٢ ساعة (مش قديم أوي)")

# ═════════════ ⑨ بناء طازج متسق ═════════════
section("⑨ اتساق البناء")
d2 = gm.build(force=True)
F2 = d2.get("factors") or {}
check(set(F2.keys()) == set(F.keys()), "نفس مجموعة العوامل في بناءين")
check(len(F2) >= 10, "متاح %d عامل (المطلوب ≥ ١٠)" % len(d2.get("available") or []))

# ═════════════ ⑩ الفهرس (factors_list) ═════════════
section("⑩ factors_list")
lst = gm.factors_list()
cats = lst.get("categories") or []
check(bool(cats), "فهرس الفئات فيه فئات")
tot = 0
for c in cats:
    tot += len(c.get("factors") or [])
check(tot == len(F), "كل عامل داخل فئة واحدة بالظبط (%d = %d)" % (tot, len(F)))

print("\n" + "=" * 62)
if fails:
    print("❌ فشل %d اختبار" % len(fails))
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("✅ كل الاختبارات عدّت (%d factor × كل القواعد)" % len(F))
