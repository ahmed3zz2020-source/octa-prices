#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٤ (R24 · المرحلة ٥) — براهين **سالبة** أقوى لحارس بيانات تاريخ المؤشرات

📌 المبدأ: الدليل مش إن الاختبار يعدّي ⭐ — الدليل إن الحارس **يفشل**
  Facing كل نوع عيب ⭐، وإنه يفشل **بسبب العيب نفسه** ⭐.

📌 الحالات المطلوبة (الجولة ٢٤) ⭐:
   ①  ⛔ فقد تاريخ مع **ثبات العدد** ⭐ — نسخة بتاريخ عدد صفوف ثابت ⇐
       تاريخ قديم اتبدّل بتاريخ جديد ⇐ لازم الحارس يفشل ⭐
   ②  ⛔ **إزاحة** كل التواريخ بنفس المقدار ⇐ لازم الحارس يفشل ⭐
       (حتى لو التداخل الزمني فضل كبير ⭐ — ده هو الاختبار الصعب ⭐)
   ③  ⛔ مقارنة بتداخل **فارغ** ⇐ لازم تفشل مش تمرّ ⭐
       (مدى كامل بعد المدى · مدى كامل قبله · سلسلة فارغة ⭐)
   ④  ⛔ **تكرار** التواريخ مرفوض ⭐ (بقيمة مطابقة ⇐ يثبت إن الفشل
       منسوب للتكرار نفسه ⭐)
   ⑤  ⛔ صحة `count` و `from` و `to` مطابقة للصفوف **فعلياً** ⭐
   ⑥  ⛔ الكتابة **ذرّية** ⇐ لو الكتابة اتقفلت في النص ⇐ مافيش ملف
       نصيف يبان كأنه سليم ⭐
   ⑦  ⛔ تشغيل التحديث **اليومي** على نسخة صناعية ⇐ مش على بيانات
       الإنتاج الحقيقية ⭐

📌 كل الـfixtures في **مجلد مؤقّت** ⭐ — data/index_history.json **ما يتلمسش**
   ⭐ (والاختبار بيتأكد من ده بالـsha256 قبل وبعد ⭐).

📌 كل حالة بتطبع **Assertions اللي فشلت بالظبط** ⭐ ⇒ يبقى الفشل
   **مُنسب للعيب** مش لإعداد الاختبار ⭐.

📌 طريقة التشغيل ⭐:
   python3 tools/test_data_integrity_proofs_r24.py
   python3 tools/test_data_integrity_proofs_r24.py --report-json /tmp/r24.json
"""
import argparse
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
REFRESH = os.path.join(HERE, "refresh_index_history.py")
REAL_CURRENT = os.path.join(ROOT, "data", "index_history.json")
TARGET_REL = "data/index_history.json"

DAY = 86400
BASE_TS = 1704067200          # 2024-01-01T00:00:00Z
LONG_ROWS = 400                # ⛔ مدى طويل ⇐ عشان التداخل يفضل كبير ⭐

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


def build_file(rows_by_index, meta_overrides=None, count_override=None,
               from_override=None, to_override=None):
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
            "from": utc_date(min(ts_list)) if ts_list else "",
            "to": utc_date(max(ts_list)) if ts_list else "",
            "count": len(rows),
            "rows": rows,
        }
        if meta_overrides and name in meta_overrides:
            meta.update(meta_overrides[name])
        if count_override is not None and name == "SYNTH":
            meta["count"] = count_override
        if from_override is not None and name == "SYNTH":
            meta["from"] = from_override
        if to_override is not None and name == "SYNTH":
            meta["to"] = to_override
        indices[name] = meta
    return {
        "version": "2026-10-31",
        "source": "TEST fixture ⭐",
        "source_note": "TEST fixture ⭐",
        "coverage_note": "TEST fixture ⭐",
        "indices": indices,
    }


def base_fixture():
    """النسخة السليمة ⭐ — مدى طويل ⇐ والتداخل يفضل كبير ⭐"""
    return build_file({"SYNTH": synth_rows(LONG_ROWS),
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
    print("     النتيجة   : exit=%d · فحوص فاشلة=%d · size=%s"
          % (proc.returncode, len(failed_ids),
             case.get("size_note") or "-"))
    for chk in failed_checks:
        print("     ❌ [%s] %s" % (chk["id"], chk["label"]))
        if chk.get("detail"):
            print("        ↳ %s" % chk["detail"])
    if not failed_checks:
        print("     ❌ مافيش أي فحص فشل ⭐")
    print("     الحكم    : %s" % ("✅ سلوك صح ⭐" if passed else "❌ سلوك غلط ⭐"))
    RESULTS.append({
        "id": case["id"],
        "title": case["title"],
        "expect": case["expect"],
        "passed": passed,
        "failed_ids": failed_ids,
        "exit_code": proc.returncode,
        "size_note": case.get("size_note") or "",
    })
    return passed


# ────────────────────────────────────────────────────────────────────────────
# ⑥ الكتابة الذرّية ⭐
# ────────────────────────────────────────────────────────────────────────────
def check_atomic_write(workdir):
    """⑥ — لو الكتابة اتقفلت في النص ⇐ مافيش ملف نصيف يبان كأنه سليم ⭐"""
    sys.path.insert(0, HERE)
    import refresh_index_history as refresh

    target = os.path.join(workdir, "atomic_target.json")
    # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ اسم ⭐⭐⭐ مؤقت ⭐⭐⭐ **فريد** ⭐⭐⭐ ⭐ (pid ⭐)
    tmp_path = "%s.tmp-%d" % (target, os.getpid())
    old_payload = build_file({"SYNTH": synth_rows(6)})
    with io.open(target, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(old_payload, ensure_ascii=False))
    old_digest = sha256(target)

    results = []

    def snapshot():
        """حالة الديسك بعد كل محاولة ⭐"""
        return {
            "target_exists": os.path.exists(target),
            "target_sha": sha256(target) if os.path.exists(target) else "",
            "target_valid_json": False,
            "tmp_exists": os.path.exists(tmp_path),
        }

    def target_is_valid():
        try:
            with io.open(target, encoding="utf-8") as handle:
                json.load(handle)
            return True
        except Exception:
            return False

    # ── ⑥أ الكتابة اتقفلت في النص (الكتابة نفسهاCrash ⭐) ──
    real_dump = json.dump

    def boom_dump(obj, fp, **kwargs):
        # ⛔ نكتب **جزء** من الملف ونقفل الكتابة ⭐
        fp.write('{"version": "2026-01-01", "indices": {"SYNTH": {"rows": [[170')
        fp.flush()
        raise IOError("قطع مقصود في نص الكتابة ⭐")

    json.dump = boom_dump
    try:
        raised = False
        try:
            refresh.atomic_write_json(target, old_payload)
        except Exception:
            raised = True
    finally:
        json.dump = real_dump
    snap = snapshot()
    ok_a = (raised and snap["target_sha"] == old_digest
            and not snap["tmp_exists"] and target_is_valid())
    results.append(("⑥أ", "الكتابة اتقفلت في النص ⇐ الملف القديم سليم ومافيش ملف نصيف",
                    ok_a,
                    "رُمي الاستثناء=%s · sha256 الملف=%s · ملف مؤقّت متبقّي=%s · "
                    "الملف لسه JSON صالح=%s"
                    % (raised,
                       "متطابق ⭐" if snap["target_sha"] == old_digest else "اتغيّر ⛔",
                       "أيوه ⛔" if snap["tmp_exists"] else "لأ ⭐",
                       "أيوه ⭐" if target_is_valid() else "لأ ⛔")))

    # ── ⑥ب الكتابة وصلت لحد الـrename وبعدين فشلت ──
    real_replace = os.replace

    def boom_replace(src, dst):
        raise OSError("فشل الـrename ⭐")

    os.replace = boom_replace
    try:
        raised = False
        try:
            refresh.atomic_write_json(target, old_payload)
        except Exception:
            raised = True
    finally:
        os.replace = real_replace
    snap = snapshot()
    ok_b = (raised and snap["target_sha"] == old_digest
            and not snap["tmp_exists"] and target_is_valid())
    results.append(("⑥ب", "الـrename فشل ⇐ الملف القديم سليم ومافيش ملف نصيف",
                    ok_b,
                    "رُمي الاستثناء=%s · sha256 الملف=%s · ملف مؤقّت متبقّي=%s · "
                    "الملف لسه JSON صالح=%s"
                    % (raised,
                       "متطابق ⭐" if snap["target_sha"] == old_digest else "اتغيّر ⛔",
                       "أيوه ⛔" if snap["tmp_exists"] else "لأ ⭐",
                       "أيوه ⭐" if target_is_valid() else "لأ ⛔")))

    # ── ⑥ج حمولة غير سليمة (تاريخ مكرّر ⭐) ⇐ مينفعش تكتب أصلاً ──
    bad_payload = build_file({"SYNTH": synth_rows(6) + [list(synth_rows(6)[2])]})
    raised = False
    try:
        refresh.atomic_write_json(target, bad_payload)
    except Exception:
        raised = True
    snap = snapshot()
    ok_c = (raised and snap["target_sha"] == old_digest
            and not snap["tmp_exists"] and target_is_valid())
    results.append(("⑥ج", "حمولة فيها تاريخ مكرّر ⇐ اترفضت قبل الكتابة",
                    ok_c,
                    "رُمي الاستثناء=%s · sha256 الملف=%s · ملف مؤقّت متبقّي=%s"
                    % (raised,
                       "متطابق ⭐" if snap["target_sha"] == old_digest else "اتغيّر ⛔",
                       "أيوه ⛔" if snap["tmp_exists"] else "لأ ⭐")))

    # ── ⑥د ضابط موجب: كتابة سليمة ⇐ الملف اتبدّل كامل ومافيش مؤقّت ──
    new_payload = build_file({"SYNTH": synth_rows(9)})
    code_ok = True
    try:
        refresh.atomic_write_json(target, new_payload)
    except Exception:
        code_ok = False
    snap = snapshot()
    written_ok = False
    if code_ok and snap["target_sha"] != old_digest:
        with io.open(target, encoding="utf-8") as handle:
            after = json.load(handle)
        meta = after["indices"]["SYNTH"]
        written_ok = (meta.get("count") == 9
                      and len(meta.get("rows") or []) == 9
                      and not snap["tmp_exists"])
    results.append(("⑥د", "ضابط موجب: كتابة سليمة ⇐ الملف اتبدّل كامل",
                    bool(written_ok),
                    "sha256=%s · ملف مؤقّت متبقّي=%s"
                    % ("اتغيّر ⭐" if snap["target_sha"] != old_digest else "متطابق ⛔",
                       "أيوه ⛔" if snap["tmp_exists"] else "لأ ⭐")))

    for case_id, title, passed, detail in results:
        print("\n  ── %s · %s ──" % (case_id, title))
        print("     التفاصيل : %s" % detail)
        print("     الحكم    : %s" % ("✅ سلوك صح ⭐" if passed else "❌ سلوك غلط ⭐"))
        RESULTS.append({"id": case_id, "title": title, "expect": "FAIL/OK",
                        "passed": passed, "failed_ids": [detail], "exit_code": 0})
    return all(item[2] for item in results)


# ────────────────────────────────────────────────────────────────────────────
# ⑦ تشغيل التحديث اليومي على نسخة صناعية ⭐
# ────────────────────────────────────────────────────────────────────────────
def build_synthetic_root(workdir, rows, count):
    """نسخة صناعية كاملة من المشروع ⇐ مافيشش لمس لملف الإنتاج ⭐"""
    root = os.path.join(workdir, "synthetic_root")
    os.makedirs(os.path.join(root, "tools"), exist_ok=True)
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    shutil.copy2(REFRESH, os.path.join(root, "tools", "refresh_index_history.py"))
    shutil.copy2(GUARD, os.path.join(root, "tools", "verify_data_integrity.py"))
    payload = build_file({name: [list(r) for r in rows] for name in
                          ("EGX30", "EGX70", "EGX100", "EGX33")})
    payload["version"] = "2026-01-01"
    with io.open(os.path.join(root, TARGET_REL), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
    with io.open(os.path.join(root, "tv_ws.py"), "w", encoding="utf-8") as handle:
        handle.write(
            "BARS = %r\n"
            "\n"
            "def fetch_series(symbol, count=12000):\n"
            "    return [dict(b) for b in BARS]\n"
            % ([{"t": r[0], "c": r[1]} for r in rows],))
    return root


def run_daily_update(root):
    """يشغّل سكربت التحديث اليومي كامل ⭐ (عملية مستقلة ⭐)"""
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, os.path.join(root, "tools",
                                                         "refresh_index_history.py")],
                          capture_output=True, text=True, cwd=root, env=env,
                          timeout=900)
    return proc


def check_daily_run(workdir):
    """⑦ — التحديث اليومي على نسخة صناعية ⇐ وملف الإنتاج ما يتلمسش ⭐"""
    real_before = sha256(REAL_CURRENT)
    rows = synth_rows(10)
    results = []

    # ── ⑦أ تشغيل شرعي ⇐ الكتابة في النسخة الصناعية بس ⭐
    root = build_synthetic_root(workdir, rows, 10)
    proc = run_daily_update(root)
    synthetic = os.path.join(root, TARGET_REL)
    written_ok = False
    detail = ""
    if proc.returncode == 0 and os.path.exists(synthetic):
        with io.open(synthetic, encoding="utf-8") as handle:
            after = json.load(handle)
        meta = (after.get("indices") or {}).get("EGX30") or {}
        written_ok = (int(meta.get("count") or 0) == 10
                      and len(meta.get("rows") or []) == 10
                      and str(meta.get("from")) == utc_date(rows[0][0])
                      and str(meta.get("to")) == utc_date(rows[-1][0])
                      and not os.path.exists(synthetic + ".tmp"))
        detail = ("count=%s · rows=%d · from=%s · to=%s · ملف مؤقّت متبقّي=%s"
                  % (meta.get("count"), len(meta.get("rows") or []),
                     meta.get("from"), meta.get("to"),
                     "أيوه ⛔" if os.path.exists(synthetic + ".tmp") else "لأ ⭐"))
    else:
        detail = "exit=%d ⛔ · %s" % (proc.returncode,
                                      (proc.stdout or "")[-120:].replace("\n", " "))
    results.append(("⑦أ", "التحديث اليومي شغّل على النسخة الصناعية ⇐ وكتبها صح",
                    bool(written_ok), detail))

    # ── ⑦ب نفس التشغيل ⇐ ببيانات **مبتورة** ⇐ لازم يرفض ⭐
    root2 = build_synthetic_root(workdir, rows, 10)
    synthetic2 = os.path.join(root2, TARGET_REL)
    digest2 = sha256(synthetic2)
    short = [{"t": r[0], "c": r[1]} for r in rows[:4]]
    with io.open(os.path.join(root2, "tv_ws.py"), "w",
                 encoding="utf-8") as handle:
        handle.write("BARS = %r\n\n\ndef fetch_series(symbol, count=12000):\n"
                     "    return [dict(b) for b in BARS]\n" % (short,))
    proc2 = run_daily_update(root2)
    refused = (proc2.returncode != 0
               and sha256(synthetic2) == digest2
               and not os.path.exists(synthetic2 + ".tmp"))
    results.append(("⑦ب", "التحديث اليومي على بيانات مبتورة ⇐ رفض الكتابة",
                    bool(refused),
                    "exit=%d · الملف=%s · ملف مؤقّت متبقّي=%s"
                    % (proc2.returncode,
                       "متطابق ⭐" if sha256(synthetic2) == digest2
                       else "اتغيّر ⛔",
                       "أيوه ⛔" if os.path.exists(synthetic2 + ".tmp") else "لأ ⭐")))

    real_after = sha256(REAL_CURRENT)
    untouched = real_before == real_after
    results.append(("⑦ج", "ملف الإنتاج (data/index_history.json) ما اتلمسش",
                    bool(untouched),
                    "sha256 قبل=%s · بعد=%s"
                    % (real_before[:16], real_after[:16])))

    for case_id, title, passed, detail in results:
        print("\n  ── %s · %s ──" % (case_id, title))
        print("     التفاصيل : %s" % detail)
        print("     الحكم    : %s" % ("✅ سلوك صح ⭐" if passed else "❌ سلوك غلط ⭐"))
        RESULTS.append({"id": case_id, "title": title, "expect": "FAIL/OK",
                        "passed": passed, "failed_ids": [detail], "exit_code": 0})
    return all(item[2] for item in results)


# ────────────────────────────────────────────────────────────────────────────
# ⭐ البرنامج الرئيسي ⭐
# ────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(description="براهين سالبة (R24) ⭐")
    parser.add_argument("--report-json", default="",
                        help="يكتب تقرير الحالات كـ JSON ⭐")
    args = parser.parse_args(argv)

    print("\n" + "=" * 78)
    print("  🧪 براهين سالبة ⭐ — حارس بيانات تاريخ المؤشرات (الجولة ٢٤)")
    print("  الحارس : %s" % GUARD)
    print("  التحديث: %s" % REFRESH)
    print("=" * 78)

    if not os.path.exists(GUARD) or not os.path.exists(REFRESH):
        print("❌ مافيش الحارس أو أداة التحديث ⭐")
        return 1

    real_before = sha256(REAL_CURRENT)
    base = base_fixture()
    base_rows = base["indices"]["SYNTH"]["rows"]
    other_rows = base["indices"]["SYNTHB"]["rows"]

    cases = []

    # ── ① فقد تاريخ مع ثبات العدد ⭐
    # 📌 تاريخ قديم (في النص) اتشال ⇐ تاريخ جديد اتضاف في مكانه ⇐
    # 📌 عدد الصفوف **ثابت** ⇐ فالفحص بالعدد لوحده مش هيلقطه ⭐
    dropped_old = base_rows[0]
    fresh_ts = base_rows[100][0] - (base_rows[0][0] - base_rows[1][0]) // 2
    replaced = [list(r) for r in base_rows]
    replaced[0] = [fresh_ts, round(base_rows[0][1] + 3.5, 4)]
    replaced.sort(key=lambda r: r[0])
    cases.append({
        "id": "①", "title": "فقد تاريخ قديم مع ثبات عدد الصفوف ⇐ التاريخ الجديد في النص",
        "expect": "FAIL",
        "required": ["I01.TS_SUBSET"],
        "allowed": ["I01.TS_SUBSET", "I01.VALUE_IDENTICAL",
                    "LEGACY.SHARED_VALUES.SYNTH", "LEGACY.SHARED_VALUES.TOTAL"],
        "size_note": "base=%d · current=%d (ثابت ⭐)"
                     % (len(base_rows), len(replaced)),
        "base": base,
        "current": build_file({"SYNTH": replaced, "SYNTHB": other_rows}),
    })

    # ── ② إزاحة كل التواريخ بنفس المقدار ⭐
    # 📌 المدى طويل ⇐ والتداخل يفضل كبير ⇐ فالتداخل **مش** هيلقطها ⭐
    shift_days = 30
    shifted = [[r[0] + shift_days * DAY, r[1]] for r in base_rows]
    cases.append({
        "id": "②", "title": "إزاحة كل التواريخ بنفس المقدار (%d يوم) ⇐ لازم تفشل"
                 % shift_days,
        "expect": "FAIL",
        "required": ["I01.TS_SUBSET"],
        "allowed": ["I01.TS_SUBSET", "I01.VALUE_IDENTICAL", "I02.OVERLAP_WINDOW",
                    "I02.OVERLAP_MIN_DAYS", "I02.OVERLAP_BASE_FRACTION",
                    "I02.SHARED_COUNT", "LEGACY.SHARED_VALUES.SYNTH",
                    "LEGACY.SHARED_VALUES.TOTAL", "META.FROM", "META.TO"],
        "size_note": "base=%d · current=%d (ثابت ⭐) · التداخل فضل كبير ⭐"
                     % (len(base_rows), len(shifted)),
        "base": base,
        "current": build_file({"SYNTH": shifted, "SYNTHB": other_rows}),
    })

    # ── ③ تداخل فارغ ⭐
    after_base = synth_rows(LONG_ROWS, start_ts=base_rows[-1][0] + 400 * DAY)
    before_base = synth_rows(LONG_ROWS, start_ts=base_rows[0][0] - 400 * DAY)
    cases.append({
        "id": "③أ", "title": "المدى الحالي **بعد** المدى الأساسي ⇐ تداخل فارغ",
        "expect": "FAIL",
        "required": ["I02.OVERLAP_WINDOW", "I02.OVERLAP_MIN_DAYS",
                     "I02.OVERLAP_BASE_FRACTION", "I02.SHARED_COUNT"],
        "allowed": ["I01.TS_SUBSET", "I02.OVERLAP_WINDOW", "I02.OVERLAP_MIN_DAYS",
                    "I02.OVERLAP_BASE_FRACTION", "I02.SHARED_COUNT",
                    "LEGACY.SHARED_VALUES.SYNTH", "LEGACY.SHARED_VALUES.TOTAL"],
        "base": base,
        "current": build_file({"SYNTH": after_base, "SYNTHB": other_rows}),
    })
    cases.append({
        "id": "③ب", "title": "المدى الحالي **قبل** المدى الأساسي ⇐ تداخل فارغ",
        "expect": "FAIL",
        "required": ["I02.OVERLAP_WINDOW", "I02.SHARED_COUNT"],
        "allowed": ["I01.TS_SUBSET", "I02.OVERLAP_WINDOW", "I02.OVERLAP_MIN_DAYS",
                    "I02.OVERLAP_BASE_FRACTION", "I02.SHARED_COUNT",
                    "LEGACY.SHARED_VALUES.SYNTH", "LEGACY.SHARED_VALUES.TOTAL"],
        "base": base,
        "current": build_file({"SYNTH": before_base, "SYNTHB": other_rows}),
    })
    cases.append({
        "id": "③ج", "title": "السلسلة الحالية **فارغة** ⇐ المقارنة ما تمرّش فاضية",
        "expect": "FAIL",
        "required": ["I01.TS_SUBSET", "I02.OVERLAP_WINDOW"],
        "allowed": ["I01.TS_SUBSET", "I01.VALUE_IDENTICAL", "I02.OVERLAP_WINDOW",
                    "I02.OVERLAP_MIN_DAYS", "I02.OVERLAP_BASE_FRACTION",
                    "I02.SHARED_COUNT", "META.COUNT", "META.FROM", "META.TO",
                    "I03.ROW_SHAPE", "I03.STRICTLY_INCREASING", "I03.FINITE_VALUE",
                    "I03.VALUE_RANGE", "I03.TS_PLAUSIBLE",
                    "LEGACY.SHARED_VALUES.SYNTH", "LEGACY.SHARED_VALUES.TOTAL",
                    "LEGACY.ROW_COUNT.SYNTH"],
        "size_note": "base=%d · current=0" % len(base_rows),
        "base": base,
        "current": build_file({"SYNTH": [], "SYNTHB": other_rows}),
    })

    # ── ④ تكرار التواريخ ⭐ (بقيمة مطابقة ⇐ الفشل منسوب للتكرار ⭐)
    duplicated = [list(r) for r in base_rows]
    duplicated.insert(50, list(base_rows[50]))
    cases.append({
        "id": "④", "title": "تاريخ مكرّر (بنفس القيمة) ⇐ مرفوض",
        "expect": "FAIL",
        "required": ["I03.STRICTLY_INCREASING"],
        "allowed": ["I03.STRICTLY_INCREASING"],
        "size_note": "base=%d · current=%d" % (len(base_rows), len(duplicated)),
        "base": base,
        "current": build_file({"SYNTH": duplicated, "SYNTHB": other_rows}),
    })

    # ── ⑤ صحة count و from و to ⭐
    cases.append({
        "id": "⑤أ", "title": "`count` غلط ⇐ لازم يطابق عدد الصفوف",
        "expect": "FAIL",
        "required": ["META.COUNT"],
        "allowed": ["META.COUNT"],
        "base": base,
        "current": build_file({"SYNTH": base_rows, "SYNTHB": other_rows},
                              count_override=len(base_rows) + 1),
    })
    cases.append({
        "id": "⑤ب", "title": "`from` و `to` مربوطين بصفوف تانية ⇐ لازم يطابقوا",
        "expect": "FAIL",
        "required": ["META.FROM", "META.TO"],
        "allowed": ["META.FROM", "META.TO"],
        "base": base,
        "current": build_file({"SYNTH": base_rows, "SYNTHB": other_rows},
                              from_override=utc_date(base_rows[1][0]),
                              to_override=utc_date(base_rows[-2][0])),
    })

    # ── ⑤ج ضابط موجب: الملف السليم ⇐ الـcount والـfrom والـto مطابقين ⭐
    cases.append({
        "id": "⑤ج", "title": "ضابط موجب: الملف السليم ⇐ count/from/to مطابقين",
        "expect": "PASS",
        "required": [],
        "allowed": None,
        "base": base,
        "current": build_file({"SYNTH": base_rows, "SYNTHB": other_rows}),
    })

    workdir = tempfile.mkdtemp(prefix="octa_r24_proofs_")
    try:
        for case in cases:
            check_case(case, workdir)
        check_atomic_write(workdir)
        check_daily_run(workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    real_after = sha256(REAL_CURRENT)

    print("\n" + "=" * 78)
    print("  📊 جدول البراهين السالبة ⭐")
    print("  " + "-" * 74)
    print("  %-4s │ %-54s │ %-8s │ %s" % ("#", "الحالة", "المتوقع", "الحكم"))
    print("  " + "-" * 74)
    for res in RESULTS:
        failed = ", ".join(res["failed_ids"]) if res["failed_ids"] else "مافيش ⭐"
        if len(failed) > 44:
            failed = failed[:41] + " ⭐"
        print("  %-4s │ %-54s │ %-8s │ %s"
              % (res["id"], res["title"][:54], res["expect"],
                 ("✅ صح" if res["passed"] else "❌ غلط")))
        print("  %-4s │ %-54s │ %-8s │   ↳Assertions اللي فشلت: %s"
              % ("", "", "", failed))
    print("  " + "-" * 74)
    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print("  النتيجة: %d/%d ⭐" % (passed, total))
    print("  ملف الإنتاج: sha256 قبل=%s · بعد=%s ⭐"
          % (real_before[:16], real_after[:16]))
    if passed != total:
        print("  ❌ فيه حالات سلوكها مش متوقّع ⭐")
    else:
        print("  ✅ كل الحالات سلوكها متوقّع ⭐ (وكل حالة فشلت بسبب عيبها ⭐)")
    print("=" * 78)

    if args.report_json:
        payload = {
            "ok": passed == total,
            "passed": passed,
            "total": total,
            "real_current_sha256_before": real_before,
            "real_current_sha256_after": real_after,
            "real_current_untouched": real_before == real_after,
            "cases": RESULTS,
        }
        try:
            with io.open(args.report_json, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            print("  📄 التقرير: %s" % args.report_json)
        except Exception as exc:
            print("  ⚠️ مقدرتش أكتب التقرير: %s" % str(exc)[:120])

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
