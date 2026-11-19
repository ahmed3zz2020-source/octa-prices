#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ الجولة ٢٥ (R25 · المرحلة ٦) — F-24-01: منع عرض أداء السعر على أنه نمو أرباح.

📌 المطلوب من المالك ⭐:
   «ممنوع عرض أداء السعر على أنه نمو أرباح الشركة» ⭐
   «إذا لم يتوفر نمو الأرباح، اعرض البيانات باعتبارها غير متاحة، ولا تخترع قيمة بديلة» ⭐
   ⭐ «لا تفعل نقاط PEG الجديدة في الترتيب قبل تقييم أثرها والحصول على اعتماد المنهجية» ⭐.

📌 طريقة الإثبات ⭐:
   ① التسمية والدليل لازم يقولوا الحقيقة ⭐ (نمو الأرباح غير متاح ⭐ ⇒ معلن ⭐).
   ② ⭐⭐ الدرجة **ما اتغيرتش** ⭐ ⇒ ⛔ مفيش تغيير في الترتيب ⭐
      (نفس المعادلة محسوبة جوه الاختبار ⭐ ⇒ المقارنة رقمية ⭐).
   ③ التسميات المعلن للمستخدم في التعريفات ⭐.
   ④ نصوص الواجهة ⭐ (قوالب الأسباب ⭐).

📌 التشغيل: python3 tools/test_r25_growth_truthfulness.py
   ⭐ وللتشغيل على الكود القديم ⭐:
      OCTA_ROOT=<مجلد فيه الكود القديم> python3 tools/test_r25_growth_truthfulness.py
"""
import json
import os
import re
import sys

ROOT = os.environ.get("OCTA_ROOT", "/workspace/.wt_r18")
FE = os.environ.get("OCTA_FE_ROOT", "/workspace/.wt_r18fe")

sys.path.insert(0, ROOT)
import opp_engine as opp  # noqa: E402

FAILS = []
OKS = [0]


def check(cond, msg):
    if cond:
        OKS[0] += 1
    else:
        FAILS.append(msg)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def clamp(v):
    return max(0.0, min(1.0, v))


def old_ratio(item):
    """⭐ المعادلة القديمة ⭐ — مرجع مستقل ⭐ (مكتوبة هنا ⭐ مش مستوردة ⭐)."""
    p3 = _f(item.get("perf_3m"))
    rev = _f(item.get("revenue_growth"))
    ni = _f(item.get("ni_growth"))
    if p3 is None and rev is None and ni is None:
        return None
    parts = [x for x in (p3, rev, ni) if x is not None]
    return clamp(0.5 + (sum(parts) / len(parts)) / 40.0)


# ── ① المحرك: التسمية + الدليل ⭐ ──
item = {"perf_3m": 10.0, "revenue_growth": None, "ni_growth": None}
res = opp.c_growth(item)
check(res is not None, "⛔ c_growth لازم يرجع نتيجة ⭐")
ratio, ev, note = res
check("معدل نمو الأرباح" not in note,
      "⛔⛔⛔ التسمية لسه بتقول «معدل نمو الأرباح» ⭐ والأداء سعر ⭐ — got: " + str(note))
check("غير متاح" in note,
      "⛔⛔⛔ لازم يعلن إن نمو الأرباح **غير متاح** ⭐ — got: " + str(note))
check(ev.get("earnings_growth_available") is False,
      "⛔ الدليل لازم يعلن إن نمو الأرباح غير متاح ⭐ — got: " + str(ev))
check(abs(ratio - old_ratio(item)) < 1e-9,
      "⛔⛔⛔ الدرجة اتغيرت ⭐ ⛔ (تغيير منهجية محتاج إذن المالك ⭐) ⭐ got %r" % (ratio,))
check(abs(ratio - 0.75) < 1e-9, "⛔ الرقم المرجعي غلط ⭐ got %r" % (ratio,))

# ── ② مع نمو الأرباح متاح ⭐ ⇒ التسمية بتقولها ⭐ ──
item2 = {"perf_3m": 10.0, "revenue_growth": 5.0, "ni_growth": 7.0}
r2 = opp.c_growth(item2)
check(r2 is not None, "⛔ c_growth مع نمو الأرباح ⭐")
check("نمو الأرباح" in r2[2],
      "⛔ لازم التسمية تذكر نمو الأرباح ⭐ (هو متاح ⭐) — got: " + str(r2[2]))
check(r2[1].get("earnings_growth_available") is True,
      "⛔ الدليل لازم يقول إن نمو الأرباح متاح ⭐")
check(abs(r2[0] - old_ratio(item2)) < 1e-9,
      "⛔⛔⛔ الدرجة اتغيرت ⭐ got %r" % (r2[0],))

# ── ③ مفيش بيانات ⇒ مفيش نتيجة ⭐ (مش نص درجة ⭐) ──
check(opp.c_growth({"perf_3m": None, "revenue_growth": None, "ni_growth": None}) is None,
      "⛔ مافيش بيانات ⇒ لازم ترجع None ⭐")

# ── ④ المحور المركّب (growth_profit) ⭐ ──
rp = opp.c_growth_profit(item)
check(rp is not None, "⛔ c_growth_profit لازم يرجع نتيجة ⭐")
check(("نمو الأرباح" not in rp[2]) or ("غير متاح" in rp[2])
      or rp[1].get("earnings_growth_available"),
      "⛔⛔⛔ المحور المركّب لسه بيقول «نمو الأرباح» ⭐ وهو غير متاح ⭐ — got: " + str(rp[2]))

# ── ⑤ تسميات التعريفات ⭐ (المعلن للمستخدم ⭐) ──
defs = json.load(open(os.path.join(ROOT, "data", "opp_definitions.json"), encoding="utf-8"))


def walk_crit(obj, out):
    if isinstance(obj, dict):
        if "key" in obj and "label_ar" in obj:
            out.append(obj)
        for v in obj.values():
            walk_crit(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_crit(v, out)


crits = []
walk_crit(defs, crits)
growth_like = [c for c in crits if c.get("key") in ("growth", "growth_profit")]
check(len(growth_like) >= 2,
      "⛔ لازم معايير النمو موجودة في التعريفات ⭐ (%d)" % len(growth_like))
for c in growth_like:
    label = c.get("label_ar") or ""
    hint = c.get("hint_ar") or ""
    check("نمو الأرباح" not in label,
          "⛔⛔⛔ تسمية المعيار بتوعد بنمو الأرباح ⭐ («%s») ⭐" % label)
    if "نمو الأرباح" in hint:
        check("لو متاح" in hint,
              "⛔⛔⛔ التلميح لازم يقول «لو متاح» ⭐ — got: %s" % hint)

# ── ⑥ نصوص الواجهة ⭐ (قوالب الأسباب ⭐) ──
copy_path = os.path.join(FE, "assets", "js", "octa-opps-copy.js")
if os.path.exists(copy_path):
    txt = open(copy_path, encoding="utf-8").read()
    blocks = re.findall(r"reason_templates\s*:\s*\[(.*?)\]", txt, re.S)
    check(len(blocks) >= 1, "⛔ لازم قوالب الأسباب موجودة ⭐")
    for i, b in enumerate(blocks):
        check("نمو الأرباح" not in b,
              "⛔⛔⛔ قالب سبب (%d) بيعد بنمو الأرباح ⭐ وهو غير متاح ⭐" % (i + 1))
else:
    check(False, "⛔ ملف نصوص الواجهة مش موجود ⭐")

core_path = os.path.join(FE, "assets", "js", "octa-core.js")
if os.path.exists(core_path):
    ctxt = open(core_path, encoding="utf-8").read()
    check("الأرباح نمت" not in ctxt,
          "⛔⛔⛔ نص تسويقي بيعد بنمو الأرباح ⭐ (المصدر مش موجود ⭐) ⭐")

# ── النتيجة ──
print("checks passed: %d" % OKS[0])
if FAILS:
    print("FAILED: %d" % len(FAILS))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("RESULT: CLEAN")
