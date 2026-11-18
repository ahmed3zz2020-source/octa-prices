#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٣ (R23) — إثبات **سلبي** (negative proof) لحارس سلامة بيانات تاريخ المؤشرات

📌 المبدأ ⭐: «الدليل مش إن الاختبار يعدّي» ⭐ — الدليل الحقيقي إن الحارس
   **يفشل**面对 كل نوع عيب ⭐، وإنه يفشل **بسبب العيب نفسه** ⭐.

📌 الحالات ⭐ (كل واحدة = نسخة **مكسورة** متعمّدة ⭐):
   ① I01 ⭐ تاريخ قديم اتمسح + تاريخ جديد اتضاف (نفس عدد الصفوف) ⇒ لازم يفشل
   ② I02 ⭐ مدى تواريخ **مشترك خالص** (صفر تداخل) ⇒ لازم يفشل
   ③ I03 ⭐ طابع زمني **مكرّر** ⇒ لازم يفشل
   ④ I03 ⭐ قيمة NaN / سالبة / خارج النطاق ⇒ لازم يفشل
   ⑤ META ⭐ ملخّص count/from/to مش مطابق للصفوف ⇒ لازم يفشل
   ⑥ الملف **الحقيقي** مقابل نسخة الأساس الحقيقية ⇒ لازم يعدّي
   ⑦ I01 ⭐ قيمة تاريخ قديم اتغيّرت (نفس التاريخ) ⇒ لازم يفشل

📌 كل الـfixtures في **مجلد مؤقّت** ⭐ — data/index_history.json **ما يتلمسش** ⭐
   (والاختبار بيتأكد من ده بالـsha256 ⭐).

📌 كل حالة بتطبع **Assertions بالظبط** اللي ات.fail ⭐ ⇒ يبقى الفشل
   **مُنسب للعيب** مش لإعداد الاختبار ⭐.

شغّله:  python3 tools/test_data_integrity_guard.py
"""
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GUARD = os.path.join(HERE, "verify_data_integrity.py")
REAL_CURRENT = os.path.join(ROOT, "data", "index_history.json")
TARGET_REL = "data/index_history.json"

MIN_EGX30_ROWS = 7028
FALLBACK_BASE_REF = "e101401"
DAY = 86400
BASE_TS = 1704067200          # 2024-01-01T00:00:00Z

RESULTS = []


def utc_date(ts):
    return datetime.datetime.fromtimestamp(
        int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")


def sha256(path):
    digest = hashlib.sha256()
    with io.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ────────────────────────────────────────────────────────────────────────────
# ⭐ مصنع الـfixtures ⭐
# ────────────────────────────────────────────────────────────────────────────
def synth_rows(count, start_ts=BASE_TS, value0=1000.0):
    """صفوف يومية اصطناعية ⭐"""
    return [[start_ts + i * DAY, round(value0 + i, 4)] for i in range(count)]


def build_file(rows_by_index, meta_overrides=None):
    """ملف index_history كامل (نفس عقد الملف الحقيقي ⭐)"""
    indices = {}
    for name, rows in rows_by_index.items():
        ts_list = [r[0] for r in rows]
        meta = {
            "symbol": "TEST:%s" % name,
            "name_ar": "مؤشر اختباري",
            "name_en": name,
            "official_inception": "2024-01-01",
            "official_note": "fixture ⭐",
            "from": utc_date(min(ts_list)),
            "to": utc_date(max(ts_list)),
            "count": len(rows),
            "rows": rows,
        }
        if meta_overrides and name in meta_overrides:
            meta.update(meta_overrides[name])
        indices[name] = meta
    return {
        "version": "2026-10-31",
        "source": "TEST fixture ⭐",
        "source_note": "TEST fixture ⭐",
        "coverage_note": "TEST fixture ⭐",
        "indices": indices,
    }


def base_fixture():
    """النسخة السليمة ⭐ — أساس المقارنة لكل الحالات ⭐"""
    return build_file({"SYNTH": synth_rows(6),
                       "SYNTHB": synth_rows(5, start_ts=BASE_TS + 10 * DAY)})


# ────────────────────────────────────────────────────────────────────────────
# ⭐ تشغيل الحارس ⭐
# ────────────────────────────────────────────────────────────────────────────
def run_guard(workdir, base_path=None, current_path=None, base_ref=None):
    report_path = os.path.join(workdir, "report.json")
    cmd = [sys.executable, GUARD, "--report-json", report_path]
    if base_path:
        cmd += ["--base-file", base_path]
    if current_path:
        cmd += ["--current", current_path]
    if base_ref:
        cmd += [base_ref]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                          timeout=900)
    report = {}
    if os.path.exists(report_path):
        with io.open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        os.remove(report_path)
    return proc, report


def discover_base_ref():
    """يلاقي commit فيه الملف بالتاريخ الكامل ⭐ (7,028 صف ⭐)"""
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "--",
                              TARGET_REL], capture_output=True, text=True,
                             timeout=180).stdout
    except Exception:
        out = ""
    for ref in [line.strip() for line in out.splitlines() if line.strip()]:
        try:
            txt = subprocess.run(["git", "-C", ROOT, "show",
                                  "%s:%s" % (ref, TARGET_REL)],
                                 capture_output=True, text=True,
                                 timeout=300).stdout
        except Exception:
            continue
        if not txt:
            continue
        try:
            payload = json.loads(txt)
        except Exception:
            continue
        meta = ((payload.get("indices") or {}).get("EGX30") or {})
        rows = meta.get("rows") or []
        try:
            count_ok = int(meta.get("count") or 0) == len(rows)
        except (TypeError, ValueError):
            count_ok = False
        if len(rows) >= MIN_EGX30_ROWS and count_ok:
            return ref
    return FALLBACK_BASE_REF


def check_case(case, workdir):
    """يشغّل حالة واحدة ⭐ وبيحكم على سلوك الحارس ⭐"""
    base_path = os.path.join(workdir, "base_%s.json" % case["id"])
    cur_path = os.path.join(workdir, "current_%s.json" % case["id"])
    with io.open(base_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(case["base"], ensure_ascii=False))
    with io.open(cur_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(case["current"], ensure_ascii=False))

    proc, report = run_guard(workdir, base_path=base_path, current_path=cur_path)
    failed_ids = list(report.get("failed_ids") or [])
    failed_checks = [c for c in report.get("checks") or [] if not c.get("ok")]

    expect_fail = case["expect"] == "FAIL"
    good_verdict = (proc.returncode != 0) if expect_fail else (proc.returncode == 0)
    required = case.get("required") or []
    allowed = case.get("allowed")
    good_required = all(rid in failed_ids for rid in required)
    if allowed is None:
        good_attribution = good_required
    else:
        good_attribution = good_required and set(failed_ids) <= set(allowed)

    passed = bool(good_verdict and good_attribution)

    print("\n  ── %s · %s ──" % (case["id"], case["title"]))
    print("     المتوقع  : %s" % ("الحارس يفشل ⭐" if expect_fail
                                  else "الحارس يعدّي ⭐"))
    print("     النتيجة   : exit=%d · فحوص فاشلة=%d" % (proc.returncode,
                                                         len(failed_ids)))
    if failed_checks:
        for chk in failed_checks:
            print("     ❌ [%s] %s" % (chk["id"], chk["label"]))
            if chk.get("detail"):
                print("        ↳ %s" % chk["detail"])
    else:
        print("     ❌ مافيش أي فحص فشل ⭐")
    print("     الحكم    : %s" % ("✅ سلوك صح ⭐" if passed else "❌ سلوك غلط ⭐"))
    RESULTS.append({
        "id": case["id"],
        "title": case["title"],
        "expect": case["expect"],
        "passed": passed,
        "failed_ids": failed_ids,
        "exit_code": proc.returncode,
    })
    return passed


def check_refresh_cases(workdir):
    """الحالات ⑧⑨⑩ — أداة التحديث (refresh_index_history.py) ⭐

    ⛔ لازم ترفض كتابة تاريخ مبتور ⭐ / تاريخ مُعاد كتابته ⭐
    ⛔ ولازم الكتابة تكون ذرّية (fail-closed ⭐) ⭐.
    """
    import types

    sys.path.insert(0, HERE)
    import refresh_index_history as refresh

    # ── تجهيز ملف قديم (10 أيام لكل مؤشر ⭐)
    SYMS = {"EGX30": "EGX:EGX30", "EGX70": "EGX:EGX70EWI",
            "EGX100": "EGX:EGX100EWI", "EGX33": "EGX:SHARIAH"}
    old_rows = synth_rows(10)
    old_payload = build_file({name: old_rows for name in SYMS})
    old_path = os.path.join(workdir, "refresh_old.json")
    with io.open(old_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(old_payload, ensure_ascii=False))
    old_digest = sha256(old_path)

    def bars_from(rows):
        return [{"t": r[0], "c": r[1]} for r in rows]

    def fake_tv(series):
        module = types.ModuleType("tv_ws")
        module.fetch_series = lambda sym, count: list(series.get(sym) or [])
        return module

    sym = "EGX:EGX30"

    def run_refresh(series):
        """يشغّل أداة التحديث كاملة ⭐ على ملف مؤقّت ⭐"""
        saved_out = refresh.OUT
        saved_mod = sys.modules.get("tv_ws")
        refresh.OUT = old_path
        sys.modules["tv_ws"] = fake_tv(series)
        try:
            code = refresh.main()
        finally:
            refresh.OUT = saved_out
            if saved_mod is None:
                sys.modules.pop("tv_ws", None)
            else:
                sys.modules["tv_ws"] = saved_mod
        return code

    def series_for(rows):
        return {sym_value: bars_from(rows) for sym_value in SYMS.values()}

    results = []

    # ── ⑧ التحديث اللي بيقصّ التاريخ ⭐
    code = run_refresh(series_for(old_rows[:5]))
    refused = (code != 0) and (sha256(old_path) == old_digest) \
        and (not os.path.exists(old_path + ".tmp"))
    results.append(("⑧", "أداة التحديث ترفض التاريخ المبتور (قصّ 5 أيام)", refused,
                    "exit=%d · الملف القديم %s · ملف مؤقّت متبقّى: %s"
                    % (code, "متطابق ⭐" if sha256(old_path) == old_digest else "اتغيّر ⛔",
                       "أيوه ⛔" if os.path.exists(old_path + ".tmp") else "لأ ⭐")))

    # ── ⑧ب التحديث اللي بيعيد كتابة قيمة تاريخية ⭐
    rewritten = [list(r) for r in old_rows]
    rewritten[3][1] = round(rewritten[3][1] + 11.0, 4)
    code = run_refresh(series_for(rewritten))
    refused = (code != 0) and (sha256(old_path) == old_digest) \
        and (not os.path.exists(old_path + ".tmp"))
    results.append(("⑧ب", "أداة التحديث ترفض إعادة كتابة قيمة تاريخ قديمة", refused,
                    "exit=%d · الملف القديم %s" % (
                        code, "متطابق ⭐" if sha256(old_path) == old_digest
                        else "اتغيّر ⛔")))

    # ── ⑨ التاريخ المكرّر ⭐
    dup_payload = build_file({"SYNTH": old_rows + [list(old_rows[2])]})
    problems = refresh.validate_payload(dup_payload)
    dup_detected = any("مكرّر" in problem for problem in problems)
    results.append(("⑨", "الحارس يرفض الطوابع الزمنية المكرّرة", dup_detected,
                    "المشاكل: %s" % ("; ".join(problems[:2]) if problems else "مافيش ⛔")))

    # ── ⑩ الكتابة الذرّية (fail-closed ⭐) ⭐
    new_rows = old_rows + [[old_rows[-1][0] + DAY, 1111.5]]
    code = run_refresh(series_for(new_rows))
    written = False
    detail = ""
    if code == 0:
        with io.open(old_path, encoding="utf-8") as handle:
            after = json.load(handle)
        meta = after["indices"]["EGX30"]
        written = (meta.get("count") == len(new_rows)
                   and len(meta.get("rows") or []) == len(new_rows)
                   and not os.path.exists(old_path + ".tmp"))
        detail = ("count=%s · rows=%d · to=%s · ملف مؤقّت متبقّى: %s"
                  % (meta.get("count"), len(meta.get("rows") or []), meta.get("to"),
                     "أيوه ⛔" if os.path.exists(old_path + ".tmp") else "لأ ⭐"))
    else:
        detail = "exit=%d ⛔" % code
    results.append(("⑩", "الكتابة الذرّية: تحديث شرعي يكتب الملف كامل ⭐", written,
                    detail))

    for case_id, title, passed, detail in results:
        print("\n  ── %s · %s ──" % (case_id, title))
        print("     التفاصيل : %s" % detail)
        print("     الحكم    : %s" % ("✅ سلوك صح ⭐" if passed else "❌ سلوك غلط ⭐"))
        RESULTS.append({"id": case_id, "title": title, "expect": "FAIL/OK",
                        "passed": passed, "failed_ids": [detail], "exit_code": 0})
    return all(item[2] for item in results)


def check_real_case(workdir):
    """الحالة ⑥ — الملف الحقيقي مقابل نسخة الأساس الحقيقية ⭐"""
    ref = discover_base_ref()
    before = sha256(REAL_CURRENT)
    proc, report = run_guard(workdir, current_path=REAL_CURRENT, base_ref=ref)
    after = sha256(REAL_CURRENT)
    failed_ids = list(report.get("failed_ids") or [])
    unchanged = before == after
    passed = (proc.returncode == 0) and (not failed_ids) and unchanged

    print("\n  ── ⑥ · الملف الحقيقي مقابل نسخة الأساس الحقيقية ──")
    print("     نسخة الأساس : %s ⭐" % ref)
    print("     الملف       : %s" % REAL_CURRENT)
    print("     sha256 قبل/بعد: %s ⭐" % ("متطابق ⭐" if unchanged else
                                         "اتغيّر ⛔ ⭐"))
    print("     النتيجة     : exit=%d · فحوص فاشلة=%d" % (proc.returncode,
                                                         len(failed_ids)))
    for chk in (report.get("checks") or []):
        if not chk.get("ok"):
            print("     ❌ [%s] %s" % (chk["id"], chk["label"]))
    if not failed_ids:
        print("     ✅ كل الفحوص عدّت ⭐")
    print("     الحكم       : %s" % ("✅ سلوك صح ⭐" if passed else
                                    "❌ سلوك غلط ⭐"))
    RESULTS.append({
        "id": "⑥",
        "title": "الملف الحقيقي مقابل الأساس الحقيقي",
        "expect": "PASS",
        "passed": passed,
        "failed_ids": failed_ids,
        "exit_code": proc.returncode,
    })
    return passed


def main():
    print("\n" + "=" * 78)
    print("  🧪 إثبات سلبي ⭐ — حارس سلامة بيانات تاريخ المؤشرات (الجولة ٢٣)")
    print("  الحارس: %s" % GUARD)
    print("=" * 78)

    if not os.path.exists(GUARD):
        print("❌ مافيش الحارس: %s" % GUARD)
        return 1

    base = base_fixture()
    base_rows = base["indices"]["SYNTH"]["rows"]
    other_rows = base["indices"]["SYNTHB"]["rows"]

    cases = []

    # ── ① I01 · تاريخ قديم اتمسح + تاريخ جديد اتضاف (نفس عدد الصفوف) ──
    dropped = base_rows[1:] + [[base_rows[-1][0] + DAY, 1234.5]]
    cases.append({
        "id": "①", "title": "I01 · تاريخ قديم اتمسح + تاريخ جديد اتضاف (نفس عدد الصفوف)",
        "expect": "FAIL",
        "required": ["I01.TS_SUBSET"],
        "allowed": ["I01.TS_SUBSET"],
        "base": base,
        "current": build_file({"SYNTH": dropped, "SYNTHB": other_rows}),
    })

    # ── ② I02 · مدى تواريخ مشترك خالص (صفر تداخل) ──
    disjoint = synth_rows(6, start_ts=base_rows[-1][0] + 400 * DAY)
    cases.append({
        "id": "②", "title": "I02 · مدى تواريخ مشترك خالص (صفر تداخل)",
        "expect": "FAIL",
        "required": ["I02.OVERLAP_WINDOW", "I02.OVERLAP_MIN_DAYS",
                     "I02.OVERLAP_BASE_FRACTION", "I02.SHARED_COUNT"],
        "allowed": ["I01.TS_SUBSET", "I02.OVERLAP_WINDOW",
                    "I02.OVERLAP_MIN_DAYS", "I02.OVERLAP_BASE_FRACTION",
                    "I02.SHARED_COUNT"],
        "base": base,
        "current": build_file({"SYNTH": disjoint, "SYNTHB": other_rows}),
    })

    # ── ③ I03 · طابع زمني مكرّر ──
    duplicated = base_rows + [list(base_rows[2])]
    cases.append({
        "id": "③", "title": "I03 · طابع زمني مكرّر",
        "expect": "FAIL",
        "required": ["I03.STRICTLY_INCREASING"],
        "allowed": ["I03.STRICTLY_INCREASING"],
        "base": base,
        "current": build_file({"SYNTH": duplicated, "SYNTHB": other_rows}),
    })

    # ── ④ I03 · قيمة NaN / سالبة / خارج النطاق ──
    next_ts = base_rows[-1][0] + DAY
    for tag, value, required, allowed in (
            ("NaN", float("nan"), ["I03.FINITE_VALUE"],
             ["I03.FINITE_VALUE", "I03.VALUE_RANGE"]),
            ("سالبة", -5.0, ["I03.VALUE_RANGE"], ["I03.VALUE_RANGE"]),
            ("خارج النطاق", 123456.0, ["I03.VALUE_RANGE"], ["I03.VALUE_RANGE"])):
        rows = base_rows + [[next_ts, value]]
        cases.append({
            "id": "④%s" % tag, "title": "I03 · قيمة %s" % tag,
            "expect": "FAIL",
            "required": required,
            "allowed": allowed,
            "base": base,
            "current": build_file({"SYNTH": rows, "SYNTHB": other_rows}),
        })

    # ── ⑤ META · ملخّص count/from/to مش مطابق ──
    for field, bad_value in (("count", 999),
                             ("from", "1999-01-01"),
                             ("to", "2030-01-01")):
        check_id = "META.%s" % field.upper()
        cases.append({
            "id": "⑤%s" % field,
            "title": "META · `%s` مش مطابق للصفوف" % field,
            "expect": "FAIL",
            "required": [check_id],
            "allowed": [check_id],
            "base": base,
            "current": build_file({"SYNTH": base_rows, "SYNTHB": other_rows},
                                  meta_overrides={"SYNTH": {field: bad_value}}),
        })

    # ── ⑦ I01 · قيمة تاريخ قديم اتغيّرت ──
    changed_rows = [list(r) for r in base_rows]
    changed_rows[3][1] = round(changed_rows[3][1] + 7.5, 4)
    cases.append({
        "id": "⑦", "title": "I01 · قيمة تاريخ قديم اتغيّرت (التاريخ موجود)",
        "expect": "FAIL",
        "required": ["I01.VALUE_IDENTICAL"],
        "allowed": ["I01.VALUE_IDENTICAL", "LEGACY.SHARED_VALUES.SYNTH",
                    "LEGACY.SHARED_VALUES.TOTAL"],
        "base": base,
        "current": build_file({"SYNTH": changed_rows, "SYNTHB": other_rows}),
    })

    workdir = tempfile.mkdtemp(prefix="octa_r23_guard_")
    try:
        for case in cases:
            check_case(case, workdir)
        check_refresh_cases(workdir)
        check_real_case(workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # ── الجدول النهائي ⭐
    print("\n" + "=" * 78)
    print("  📊 جدول الإثبات السلبي ⭐")
    print("  " + "-" * 74)
    print("  %-4s │ %-52s │ %-9s │ %s" % ("#", "الحالة", "المتوقع", "الحكم"))
    print("  " + "-" * 74)
    for res in RESULTS:
        failed = ", ".join(res["failed_ids"]) if res["failed_ids"] else "مافيش ⭐"
        if len(failed) > 46:
            failed = failed[:43] + " ⭐"
        print("  %-4s │ %-52s │ %-9s │ %s"
              % (res["id"], res["title"][:52], res["expect"],
                 ("✅ صح" if res["passed"] else "❌ غلط")))
        print("  %-4s │ %-52s │ %-9s │   ↳Assertions اللي فشلت: %s"
              % ("", "", "", failed))
    print("  " + "-" * 74)
    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print("  النتيجة: %d/%d ⭐" % (passed, total))
    if passed != total:
        print("  ❌ فيه حالات سلوكها مش متوقّع ⭐")
    else:
        print("  ✅ كل الحالات سلوكها متوقّع ⭐ (وكل حالة فشلت بسبب عيبها ⭐)")
    print("=" * 78)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
