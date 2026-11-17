#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢١ (R21 · المرحلة الأولى) — إثبات سلامة البيانات + تدقيق الفرق R19→R20

📌 المطلوب من المالك:
   ① «تفسير تعديل data/index_history.json وإثبات سلامة البيانات الأصلية» ⭐
   ② «فحص الفرق الكامل بين الجولتين ١٩ و٢٠» ⭐

📌 المنهج ⭐: ⛔ **مقارنة بنيوية** ⭐ (مشMd5 للملف ⭐ — لأن الملف
   سطر واحد ضخم ⭐ ⇒ المقارنة بالبايت مش هتفيد ⭐) ⭐:
   ① الميتاداتا (version · source · coverage_note ⭐) ⭐
   ② عدد الصفوف لكل مؤشر ⭐
   ③ **تطابق القيم على الطوابع الزمنية المشتركة** ⭐ (ده الدليل الحقيقي ⭐)
   ④ التحقق من صحة القيم (monotonic time · ranges معقولة ⭐)

⛔ مافيش أي تعديل على البيانات ⭐ — فحص قراءة بس ⭐

شغّله:  python3 tools/verify_data_integrity.py [BASE_REF]
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = "data/index_history.json"

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def git_show(ref, path):
    try:
        return subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                              capture_output=True, text=True,
                              timeout=180).stdout
    except Exception:
        return ""


def load(txt):
    try:
        return json.loads(txt)
    except Exception:
        return None


def series_map(obj, key):
    """يرجّع خريطة {timestamp: value} لكل مؤشر ⭐"""
    out = {}
    try:
        for name, meta in (obj.get("indices") or {}).items():
            rows = meta.get("rows") or []
            out[name] = {int(r[0]): float(r[1]) for r in rows if len(r) >= 2}
    except Exception:
        pass
    return out


def main():
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "edc49cd"
    print("\n" + "=" * 68)
    print("  🧪 إثبات سلامة البيانات — %s (مقابل %s)" % (TARGET, base_ref))
    print("=" * 68)

    cur_txt = io.open(os.path.join(ROOT, TARGET), encoding="utf-8").read()
    base_txt = git_show(base_ref, TARGET)
    ok(bool(cur_txt), "① الملف موجود على القرص")
    ok(bool(base_txt), "② نسخة الأساس (%s) مقروءة" % base_ref)

    cur = load(cur_txt)
    base = load(base_txt)
    ok(isinstance(cur, dict), "③ الملف الحالي JSON صالح")
    ok(isinstance(base, dict), "④ ملف الأساس JSON صالح")
    if not isinstance(cur, dict) or not isinstance(base, dict):
        return 1

    # ── ① الميتاداتا ──
    same_meta = []
    for k in ("version", "source", "source_note", "coverage_note"):
        same_meta.append((k, base.get(k) == cur.get(k)))
    for k, same in same_meta:
        ok(same, "⑤ الميتاداتا `%s` ما اتغيّرتش" % k,
           "قبل: %s / بعد: %s" % (str(base.get(k))[:60], str(cur.get(k))[:60]))

    # ── ② عدد الصفوف ──
    b_idx = base.get("indices") or {}
    c_idx = cur.get("indices") or {}
    ok(set(b_idx) == set(c_idx),
       "⑥ نفس المؤشرات بالظبط", "قبل %s / بعد %s" % (sorted(b_idx), sorted(c_idx)))
    for name in sorted(set(b_idx) & set(c_idx)):
        b_rows = len(b_idx[name].get("rows") or [])
        c_rows = len(c_idx[name].get("rows") or [])
        ok(c_rows >= b_rows,
           "⑦ `%s`: عدد الصفوف ما قلّش (%d ⇒ %d)" % (name, b_rows, c_rows))

    # ── ③ القيم على الطوابع المشتركة (الدليل الحقيقي ⭐) ──
    b_map = series_map(base, "indices")
    c_map = series_map(cur, "indices")
    total_shared = 0
    total_changed = 0
    for name in sorted(set(b_map) & set(c_map)):
        shared = set(b_map[name]) & set(c_map[name])
        changed = [t for t in shared
                   if abs(b_map[name][t] - c_map[name][t]) > 1e-9]
        total_shared += len(shared)
        total_changed += len(changed)
        ok(not changed,
           "⑧ `%s`: القيم على %d طابع مشترك **ما اتغيّرتش** ⭐"
           % (name, len(shared)),
           "اتغيّر: %d" % len(changed))
    ok(total_changed == 0,
       "⑨ إجمالي القيم المشتركة المتغيّرة = 0 ⭐ (المقارنة: %d قيمة)" % total_shared,
       total_changed)

    # ── ④ صحة القيم ──
    for name in sorted(c_map):
        rows = c_idx[name].get("rows") or []
        times = [int(r[0]) for r in rows if len(r) >= 2]
        vals = [float(r[1]) for r in rows if len(r) >= 2]
        ok(times == sorted(times), "⑩ `%s`: الطوابع الزمنية مرتّبة ⭐" % name)
        ok(all(v > 0 for v in vals), "⑪ `%s`: كل القيم موجبة ⭐" % name)
        ok(all(v < 100000 for v in vals),
           "⑫ `%s`: القيم في نطاق معقول ⭐" % name)

    # ── ③ الفرق الجذري (شنو اللي اتغيّر فعلاً ⭐) ──
    diffs = []
    for k in sorted(set(base) | set(cur)):
        if k in ("indices", "series", "refreshed_at"):
            continue
        if base.get(k) != cur.get(k):
            diffs.append(k)
    ok(not diffs, "⑬ مافيش تغيير في ميتاداتا السطح ⭐", diffs)

    # ⭐ `refreshed_at` ⭐ — لازم يبقى **متناسق** مع النسخة ⭐
    #    (الملف المولّد مافيشوش ⭐ ⇒ الاتنين لازم يكونوا None ⭐)
    ok(base.get("refreshed_at") == cur.get("refreshed_at"),
       "⑭ `refreshed_at` متناسق بين النسختين ⭐",
       "قبل: %s / بعد: %s" % (base.get("refreshed_at"), cur.get("refreshed_at")))

    # ⭐ `series` (المؤشر المختصر) ⭐
    bs, cs = base.get("series") or [], cur.get("series") or []
    b_sm = {int(r[0]): float(r[1]) for r in bs if len(r) >= 2}
    c_sm = {int(r[0]): float(r[1]) for r in cs if len(r) >= 2}
    shared = set(b_sm) & set(c_sm)
    changed = [t for t in shared if abs(b_sm[t] - c_sm[t]) > 1e-9]
    ok(not changed,
       "⑮ `series`: القيم المشتركة (%d) ما اتغيّرتش ⭐" % len(shared),
       "اتغيّر: %d" % len(changed))

    print("\n" + "=" * 68)
    passed = sum(1 for c, _ in RESULTS if c)
    total = len(RESULTS)
    print("  النتيجة: %d/%d" % (passed, total))
    print("=" * 68)
    for c, label in RESULTS:
        if not c:
            print("  ❌ فشل: " + label)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
