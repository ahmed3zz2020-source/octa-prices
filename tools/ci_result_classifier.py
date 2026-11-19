#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧭 مُصنِّف نتائج الاختبارات — الجولة ٢٦ (R26 · مرحلة الـCI)

🎯 الغرض:
   تشغيل الاختبارات الحقيقية وتصدر **JSON** فيه أربع حالات صريحة لكل ملف:
      · passed  — الملف اشتغل وكل الحالات عدّت
      · failed  — الملف اشتغل وفيه حالات فاشلة
      · skipped — الملف اشتغل لكنه **تخطّى** حالات ⇒ مش نجاح
      · blocked — الملف **ما قدرش** يكمّش (رجوع صامت · مهلة · مفيش إخراج)

📌 القاعدة الذهبية (الجولة ٢٦):
   ⛔ المتخطى **مش نجاح** ⭐
   ⛔ والمتخطى بيتحسب **فشل** في بوابة الـjob ⭐ (يعني rc مخالف للصفر)
   ⛔ والـblocked كمان **مش نجاح** ⭐ (والسبب لازم يكون **موثّق** ⭐)

📌 ليه_cases_ معلن/منفَّذ مهم؟
   فيه اختبارات برهان سالب بتعمل `return` صامت لو مرجع git مش موجود
   (زي R25-PV-07 في الواجهة) ⭐ ⇒ الاختبار بيطلع «ناجح» وهو **ما عملش حاجة**
   ⭐ ⇒ المُصنِّف بيقارن **عدد الحالات المعلنة في الملف** بالـ**المنفَّذة فعلاً**
   ⭐ ⇒ الفرق = **blocked** (مش نجاح صامت ⭐).

📌 مفيش أي اتصال بالشبكة · مفيش أي سر · مفيش أي تعديل على الملفات.

── التشغيل ───────────────────────────────────────────────
   python3 tools/ci_result_classifier.py run --kind python --out ci-results.json
   python3 tools/ci_result_classifier.py run --kind node --out ci-results.json \
       --pattern 'assets/tests/*.test.js'
   python3 tools/ci_result_classifier.py classify --kind node --name x.test.js \
       --output out.txt --rc 0
   python3 tools/ci_result_classifier.py run --kind python --json
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

SCHEMA = "octa.ci.results.v1"

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED = "blocked"

ALL_STATUSES = (STATUS_PASSED, STATUS_FAILED, STATUS_SKIPPED, STATUS_BLOCKED)

# ⛔ كود خروج مميز للمتخطى (زي كود ٩٧ في مُشغّل الجولة ٢٥)
RC_SKIPPED = 97
RC_TIMEOUT = 124


# ══════════════════════════════════════════════════════════════
#  مُشغّل الطفل: بيشغّل ملف الاختبار زي `python <file>` بالظبط
#  بس بيقفل العملية بـ os._exit بعد ما الاختبار يخلص ⭐
#  (بعض الملفات بتسيب خيوط شغّالة ⇒ انهيار بعد نجاح الاختبار ⭐)
# ══════════════════════════════════════════════════════════════
CHILD = '''import os
import runpy
import sys

target = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
code = 0
try:
    runpy.run_path(target, run_name="__main__")
except SystemExit as exc:
    code = exc.code
    if code is None:
        code = 0
    if not isinstance(code, int):
        code = 1
except BaseException:
    import traceback
    traceback.print_exc()
    code = 1
sys.stdout.flush()
sys.stderr.flush()
os._exit(code)
'''


def _child_path():
    d = tempfile.mkdtemp(prefix="octa_ci_child_")
    p = os.path.join(d, "child.py")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(CHILD)
    return p


# ══════════════════════════════════════════════════════════════
#  عدّادات الحالات
# ══════════════════════════════════════════════════════════════
UNITTEST_SUMMARY_RE = re.compile(
    r"^Ran\s+(\d+)\s+tests?\b", re.M)
UNITTEST_STATUS_RE = re.compile(r"^(OK|FAILED)\b(.*)$", re.M)
PYTEST_SUMMARY_RE = re.compile(
    r"^(?:=+\s*)?(\d+)\s+(passed|failed|error|errors|skipped|xfailed|"
    r"xpassed)\b.*(?:in\s+[\d.]+s\s*)?(?:=+\s*)?$", re.M)
NODE_COUNT_RE = re.compile(r"^#\s*(tests|pass|fail|skipped|todo|cancelled)\s+(\d+)\s*$",
                           re.M)

# ⛔ علامة التخطّي الصريحة في السكربتات المخصّصة (سهم التخطّي)
SKIP_MARK_RE = re.compile(r"⏭|متخط[ىي]\s*:")
# ⛔ unittest: "OK (skipped=2)" · "FAILED (failures=1, skipped=2)"
UNITTEST_SKIP_RE = re.compile(r"skipped=(\d+)")
# ⛔ pytest: "3 passed, 1 skipped"
PYTEST_SKIP_RE = re.compile(r"(\d+)\s+skipped")

OK_MARK = "✅"
FAIL_MARK = "❌"
# ⛔ علامات إنجليزية (نمط تاني مستخدم في المستودع ⭐)
OK_MARK_EN_RE = re.compile(r"^PASS\b", re.M)
FAIL_MARK_EN_RE = re.compile(r"^FAIL\b", re.M)

# ⛔ مراجع git اللي اختبارات البرهان السالب بتعتمد عليها ⭐
#    (زي R25-PV-07 في الواجهة ⭐) ⇒ لو المرجع مش موجود ⭐
#    الاختبار بيرجع **صامت** ⭐ ⇒ الغياب لازم يبقى Blocked موثّق ⭐
HEX_REF_RE = re.compile(r"['\"]([0-9a-f]{7,40})(?::[^'\"\s]*)?['\"]")
GIT_VERBS = ("show", "cat-file", "rev-parse", "diff", "merge-base",
             "checkout", "log")


def _git_refs_in_source(path):
    """بيرجّع مراجع git المذكورة في الملف (بالسياق)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return []
    refs = []
    for m in HEX_REF_RE.finditer(src):
        ctx = src[max(0, m.start() - 70):m.start()]
        if any(v in ctx for v in GIT_VERBS):
            ref = m.group(1)
            if ref not in refs:
                refs.append(ref)
    return refs


def _missing_git_refs(root, rel):
    """بيرجّع مراجع git المفقودة من تاريخ المستودع (فارغة = كله موجود)."""
    path = os.path.join(root, rel)
    refs = _git_refs_in_source(path)
    if not refs:
        return []
    missing = []
    for ref in refs:
        rc = subprocess.run(["git", "cat-file", "-e", "%s^{commit}" % ref],
                            cwd=root, capture_output=True, timeout=60).returncode
        if rc != 0:
            missing.append(ref)
    return missing


def _count_marks(text):
    """عدد علامات النجاح/الفشل في السكربتات المخصّصة (عربي + إنجليزي)."""
    ok = text.count(OK_MARK) + len(OK_MARK_EN_RE.findall(text))
    bad = text.count(FAIL_MARK) + len(FAIL_MARK_EN_RE.findall(text))
    return ok, bad


def _declared_python_cases(path):
    """عدد الحالات المعلنة في ملف بايثون (دوال test_* على مستوى المودل)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return None
    n = len(re.findall(r"^def\s+(test_[A-Za-z0-9_]+)\s*\(", src, re.M))
    n += len(re.findall(r"^\s{4,}def\s+(test_[A-Za-z0-9_]+)\s*\(", src, re.M))
    # ⛔ ما نحسبش نفس الدالة مرتين
    names = set(re.findall(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", src, re.M))
    return len(names)


def _declared_node_cases(path):
    """عدد الحالات المعلنة في ملف جافاسكربت (test( على سطر جديد)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    except OSError:
        return None
    names = set(re.findall(r"^\s*(?:test|it)\s*\(\s*[`'\"]([^`'\"]+)", src, re.M))
    return len(names)


# ══════════════════════════════════════════════════════════════
#  التصنيف
# ══════════════════════════════════════════════════════════════
def classify_python(rc, out, err, declared=None):
    """بيرجّع (status, reason, cases, skipped_cases) لملف بايثون."""
    text = (out or "") + "\n" + (err or "")
    skip_hits = []

    # ① unittest
    m = UNITTEST_SUMMARY_RE.search(text)
    if m:
        cases = int(m.group(1))
        sm = UNITTEST_STATUS_RE.search(text)
        status_line = sm.group(0) if sm else ""
        sk = 0
        for sm2 in UNITTEST_SKIP_RE.finditer(text):
            sk = max(sk, int(sm2.group(1)))
        if sk:
            skip_hits.append("unittest: %d حالة متخطّاة" % sk)
        if rc != 0 or status_line.startswith("FAILED"):
            return (STATUS_FAILED,
                    "فشل الاختبار (rc=%s)" % rc, cases, sk)
        if sk:
            return (STATUS_SKIPPED,
                    "unittest: %d حالة متخطّاة" % sk, cases, sk)
        if cases == 0:
            return (STATUS_BLOCKED,
                    "الملف معلنش ولا حالة اختبار واحدة", 0, 0)
        return (STATUS_PASSED, "", cases, 0)

    # ② pytest
    pm = PYTEST_SUMMARY_RE.search(text)
    if pm:
        passed_n = 0
        failed_n = 0
        skipped_n = 0
        for mm in re.finditer(
                r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed)",
                text):
            cnt = int(mm.group(1))
            kind = mm.group(2)
            if kind == "passed":
                passed_n += cnt
            elif kind in ("failed", "error", "errors"):
                failed_n += cnt
            elif kind in ("skipped", "xfailed", "xpassed"):
                skipped_n += cnt
        if skipped_n:
            skip_hits.append("pytest: %d حالة متخطّاة" % skipped_n)
        cases = passed_n + failed_n + skipped_n
        if failed_n or rc != 0:
            return (STATUS_FAILED,
                    "فشل الاختبار (rc=%s · %d حالة فاشلة)"
                    % (rc, failed_n), cases, skipped_n)
        if skipped_n:
            return (STATUS_SKIPPED, skip_hits[0], cases, skipped_n)
        if cases == 0:
            return (STATUS_BLOCKED,
                    "الملف معلنش ولا حالة اختبار واحدة", 0, 0)
        return (STATUS_PASSED, "", cases, 0)

    # ③ سكربتات مخصّصة (نمط المستودع: علامات نجاح/فشل + كود خروج)
    ok_marks, bad_marks = _count_marks(text)
    if SKIP_MARK_RE.search(text):
        skip_hits.append("علامة تخطّي صريحة في الإخراج")
    if rc != 0:
        return (STATUS_FAILED,
                "فشل الاختبار (rc=%s)" % rc, ok_marks + bad_marks, 0)
    if skip_hits:
        return (STATUS_SKIPPED, skip_hits[0], ok_marks + bad_marks,
                len(SKIP_MARK_RE.findall(text)))
    # ⛔ مفيش أي إخراج إطلاقاً ⇒ ما نعرفش النتيجة ⇒ blocked مش نجاح صامت ⭐
    if not text.strip():
        return (STATUS_BLOCKED,
                "مفيش أي إخراج من الاختبار — النتيجة غير معروفة", 0, 0)
    # ⛔ فيه علامات فشل رغم إن الكود خرج ٠ ⇒ مش نجاح ⭐
    if bad_marks:
        return (STATUS_FAILED,
                "فيه %d علامة فشل رغم إن الكود خرج ٠" % bad_marks,
                ok_marks + bad_marks, 0)
    if declared is not None and declared > 0 and ok_marks + bad_marks < declared:
        return (STATUS_BLOCKED,
                "اتنفّذ %d من %d حالة معلنة — رجوع صامت محتمل"
                % (ok_marks + bad_marks, declared),
                ok_marks + bad_marks, 0)
    return (STATUS_PASSED, "", ok_marks + bad_marks, 0)


def classify_node(rc, out, err, declared=None):
    """بيرجّع (status, reason, cases, skipped_cases) لملف node --test."""
    text = (out or "") + "\n" + (err or "")
    counts = {}
    for m in NODE_COUNT_RE.finditer(text):
        counts[m.group(1)] = int(m.group(2))
    passed_n = counts.get("pass", 0)
    failed_n = counts.get("fail", 0)
    skipped_n = counts.get("skipped", 0)
    todo_n = counts.get("todo", 0)
    tests_n = counts.get("tests", 0)
    executed = passed_n + failed_n

    if rc == RC_TIMEOUT:
        return (STATUS_BLOCKED, "تجاوزت المهلة", tests_n, skipped_n)
    if failed_n or rc not in (0, None):
        return (STATUS_FAILED,
                "فشل الاختبار (rc=%s · %d حالة فاشلة)" % (rc, failed_n),
                tests_n, skipped_n + todo_n)
    if skipped_n or todo_n:
        return (STATUS_SKIPPED,
                "%d حالة متخطّاة" % (skipped_n + todo_n),
                tests_n, skipped_n + todo_n)
    # ⛔⛔⛔ البرهان السالب: رجوع صامت ⭐
    #    الملف يعلن حالات أكتر من اللي اتنفّذ ⇒ فيه `return` صامت ⭐
    if declared is not None and declared > 0 and executed < declared:
        return (STATUS_BLOCKED,
                "اتنفّذ %d من %d حالة معلنة — رجوع صامت محتمل "
                "(زي absence مرجع git)" % (executed, declared),
                tests_n, skipped_n + todo_n)
    if tests_n == 0 and passed_n == 0:
        return (STATUS_BLOCKED,
                "مفيش ولا حالة اتنفّذت — النتيجة غير معروفة", 0, 0)
    return (STATUS_PASSED, "", tests_n, skipped_n + todo_n)


def classify(kind, rc, out, err, declared=None):
    if kind == "node":
        return classify_node(rc, out, err, declared)
    return classify_python(rc, out, err, declared)


# ══════════════════════════════════════════════════════════════
#  التشغيل
# ══════════════════════════════════════════════════════════════
def discover(root, kind, patterns):
    # ⛔ أدوات الـCI نفسها (مش اختبارات) ⇒ بتتشال من الكشف ⭐
    #    (البوابات البديلة بتشتغل صريح من السجل ⭐)
    not_tests = {"tools/test_ci_gates.py", "tools/test_ci_alt_gates.py",
                "tools/ci_result_classifier.py", "tools/ci_workflow_lint.py"}
    if patterns:
        files = []
        for pat in patterns:
            files.extend(glob.glob(os.path.join(root, pat), recursive=True))
    elif kind == "node":
        files = glob.glob(os.path.join(root, "assets", "tests", "*.test.js"))
    else:
        files = []
        for pat in ("test_*.py", "tools/test_*.py", "tools/**/test_*.py"):
            files.extend(glob.glob(os.path.join(root, pat), recursive=True))
    out = []
    seen = set()
    for f in sorted(files):
        if not os.path.isfile(f):
            continue
        rel = os.path.relpath(f, root)
        if rel in seen or rel in not_tests:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def run_one(kind, root, rel, child, timeout, env_extra):
    env = dict(os.environ)
    env.update(env_extra or {})
    env["PYTHONIOENCODING"] = "utf-8"
    if kind == "node":
        cmd = ["node", "--test", rel]
    else:
        cmd = [sys.executable, child, rel]
    started = time.time()
    try:
        r = subprocess.run(cmd, cwd=root, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, encoding="utf-8",
                           errors="replace", timeout=timeout)
        rc, out, err = r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        rc, out, err = RC_TIMEOUT, "", "تجاوزت المهلة (%s ثانية)" % timeout
    except OSError as exc:
        rc, out, err = 127, "", "تعذّر تشغيل الملف: %s" % exc
    dur = round(time.time() - started, 3)
    declared = (_declared_node_cases(os.path.join(root, rel))
                if kind == "node"
                else _declared_python_cases(os.path.join(root, rel)))
    missing_refs = _missing_git_refs(root, rel)
    status, reason, cases, skipped_cases = classify(kind, rc, out, err, declared)
    if missing_refs and status == STATUS_PASSED:
        # ⛔⛔⛔ البرهان السالب رجع صامت ⭐
        #    المرجع اللي الاختبار بيعتمد عليه مش موجود ⭐
        #    ⇒ الاختبار ما عملش حاجة وبعتبره «ناجح» ⭐
        #    ⇒ الغياب لازم يبقى Blocked موثّق ⭐
        status = STATUS_BLOCKED
        reason = ("مرجع git مفقود (%s) ⇒ الاختبار بيرجع صامت "
                  "والنتيجة ملغاة ⭐" % ", ".join(missing_refs))
    return {
        "file": rel,
        "status": status,
        "gate_status": STATUS_PASSED if status == STATUS_PASSED else STATUS_FAILED,
        "rc": rc,
        "cases": cases,
        "skipped_cases": skipped_cases,
        "declared_cases": declared,
        "duration_s": dur,
        "reason": reason,
        "command": " ".join(cmd),
        "missing_git_refs": missing_refs,
    }


# ══════════════════════════════════════════════════════════════
#  سجل العزل (مش استبعاد صامت ⭐ — بوابة بديلة إلزامية ⭐)
# ══════════════════════════════════════════════════════════════
ISOLATION_FILE = os.path.join("tools", "ci_isolated_tests.json")


def load_isolation(root):
    """بيرجّع قاموس العزل (فاضي لو مفيش سجل)."""
    path = os.path.join(root, ISOLATION_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    entries = doc.get("entries") or {}
    return entries if isinstance(entries, dict) else {}


def run_gate(root, rel, meta, timeout, env_extra):
    """يشغّل البوابة البديلة لملف معزول ⭐."""
    gate = (meta or {}).get("gate", "")
    gate_args = (meta or {}).get("gate_args", []) or []
    reason = (meta or {}).get("reason", "")
    started = time.time()
    rec = {
        "file": rel,
        "status": STATUS_FAILED,
        "gate_status": STATUS_FAILED,
        "rc": 1,
        "cases": 0,
        "skipped_cases": 0,
        "declared_cases": None,
        "duration_s": 0.0,
        "reason": "",
        "command": "",
        "isolated": True,
        "isolation_reason": reason,
        "gate": gate,
    }
    if not gate:
        rec["reason"] = "الملف معزول من غير بوابة بديلة — تعريف ناقص"
        return rec
    gate_path = os.path.join(root, gate)
    if not os.path.isfile(gate_path):
        rec["reason"] = "البوابة البديلة مش موجودة: %s" % gate
        return rec
    cmd = [sys.executable, gate] + list(gate_args)
    rec["command"] = " ".join(cmd)
    env = dict(os.environ)
    env.update(env_extra or {})
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run(cmd, cwd=root, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, encoding="utf-8",
                           errors="replace", timeout=timeout)
        rc, out, err = r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        rec["reason"] = "البوابة البديلة تجاوزت المهلة"
        rec["duration_s"] = round(time.time() - started, 3)
        return rec
    except OSError as exc:
        rec["reason"] = "تعذّر تشغيل البوابة البديلة: %s" % exc
        return rec
    rec["rc"] = rc
    rec["duration_s"] = round(time.time() - started, 3)
    text = (out or "") + "\n" + (err or "")
    rec["cases"] = text.count(OK_MARK) + text.count(FAIL_MARK)
    if rc == 0:
        rec["status"] = STATUS_PASSED
        rec["gate_status"] = STATUS_PASSED
        rec["reason"] = "مُستبدل بالبوابة البديلة %s%s" % (
            gate, (" · " + reason) if reason else "")
        return rec
    if SKIP_MARK_RE.search(text):
        rec["status"] = STATUS_SKIPPED
        rec["skipped_cases"] = 1
        rec["reason"] = "البوابة البديلة %s اتخطّت ⭐" % gate
        return rec
    rec["status"] = STATUS_FAILED
    rec["reason"] = "البوابة البديلة %s فشلت (rc=%s)" % (gate, rc)
    rec["tail"] = text[-2000:]
    return rec



def cmd_run(args):
    root = os.path.abspath(args.root)
    files = discover(root, args.kind, args.pattern)
    if not files:
        print("⛔ مفيش أي ملف اختبار اتكتشف")
        return 2
    child = _child_path()
    env_extra = json.loads(args.env) if args.env else {}
    isolation = load_isolation(root) if args.kind == "python" else {}
    results = []
    print("📂 %s · %d ملف" % (args.kind, len(files)))
    if isolation:
        print("🚪 سجل العزل: %d ملف (لكل واحد بوابة بديلة إلزامية ⭐)"
              % len(isolation))
    for rel in files:
        if rel in isolation:
            rec = run_gate(root, rel, isolation[rel], args.timeout, env_extra)
        else:
            rec = run_one(args.kind, root, rel, child, args.timeout, env_extra)
        results.append(rec)
        print("   %-52s %-8s rc=%-4s cases=%-5s skipped=%-4s %s"
              % (rec["file"], rec["status"], rec["rc"], rec["cases"],
                 rec["skipped_cases"], rec["reason"]))
    # ⛔ تصنيف قديم: ملف معزول مش موجود في المستودع ⭐
    #    (الفحص ده بس مع الاكتشاف الكامل ⭐ — مع subset من الاختبارات
    #     الملفات المعزولة بتبقى برّه المجموعة ⭐)
    for rel in sorted(isolation) if not args.pattern else []:
        if rel not in files:
            results.append({
                "file": rel, "status": STATUS_FAILED,
                "gate_status": STATUS_FAILED, "rc": 1, "cases": 0,
                "skipped_cases": 0, "declared_cases": None,
                "duration_s": 0.0,
                "reason": "الملف المعزول مش موجود في المستودع — تصنيف قديم ⭐",
                "command": "", "isolated": True,
                "isolation_reason": isolation[rel].get("reason", ""),
                "gate": isolation[rel].get("gate", ""),
            })
            print("   %-52s %-8s ⛔ تصنيف قديم" % (rel, STATUS_FAILED))
    summary = {s: 0 for s in ALL_STATUSES}
    for rec in results:
        summary[rec["status"]] += 1
    total_cases = sum(r["cases"] or 0 for r in results)
    total_skipped = sum(r["skipped_cases"] or 0 for r in results)
    payload = {
        "schema": SCHEMA,
        "kind": args.kind,
        "root": root,
        "candidate_sha": os.environ.get("OCTA_CANDIDATE_SHA", ""),
        "summary": {
            "files": len(results),
            "passed": summary[STATUS_PASSED],
            "failed": summary[STATUS_FAILED],
            "skipped": summary[STATUS_SKIPPED],
            "blocked": summary[STATUS_BLOCKED],
            "cases": total_cases,
            "skipped_cases": total_skipped,
            "isolated": len(isolation),
            "duration_s": round(sum(r["duration_s"] for r in results), 3),
        },
        "ok": summary[STATUS_PASSED] == len(results),
        "files": results,
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print("📄 النتيجة اتكتبت: %s" % args.out)
    print("")
    print("=" * 70)
    print("📊 %s: %d ملف · %d نجح · %d فشل · %d متخطى · %d محجوب · %d حالة"
          % (args.kind, len(results), summary[STATUS_PASSED],
             summary[STATUS_FAILED], summary[STATUS_SKIPPED],
             summary[STATUS_BLOCKED], total_cases))
    print("=" * 70)
    if not payload["ok"]:
        print("⛔ فيه ملفات مش ناجحة ⇒ البوابة لازم تفشل")
        for rec in results:
            if rec["status"] != STATUS_PASSED:
                print("   ⛔ %s → %s (%s)"
                      % (rec["file"], rec["status"], rec["reason"]))
        return 1
    print("✅ كل الملفات عدّت")
    return 0


def cmd_classify(args):
    text = ""
    if args.output:
        with open(args.output, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    declared = None
    if args.declared is not None:
        declared = args.declared
    elif args.name and os.path.isfile(args.name):
        declared = (_declared_node_cases(args.name) if args.kind == "node"
                    else _declared_python_cases(args.name))
    status, reason, cases, skipped_cases = classify(
        args.kind, args.rc, text, "", declared)
    payload = {
        "schema": SCHEMA,
        "file": args.name,
        "status": status,
        "gate_status": STATUS_PASSED if status == STATUS_PASSED else STATUS_FAILED,
        "rc": args.rc,
        "cases": cases,
        "skipped_cases": skipped_cases,
        "declared_cases": declared,
        "reason": reason,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("%s · %s · %s" % (args.name, status, reason))
    return 0 if status == STATUS_PASSED else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="مُصنِّف نتائج الاختبارات (أربع حالات صريحة)")
    sub = ap.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="شغّل ملفات الاختبار وصنّفها")
    run.add_argument("--kind", choices=("python", "node"), default="python")
    run.add_argument("--root", default=".")
    run.add_argument("--pattern", action="append", default=[])
    run.add_argument("--out", default="")
    run.add_argument("--timeout", type=int, default=900)
    run.add_argument("--env", default="",
                     help="JSON من متغيّرات البيئة الإضافية")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=cmd_run)

    cl = sub.add_parser("classify", help="صنّف إخراجاً محفوظاً")
    cl.add_argument("--kind", choices=("python", "node"), default="python")
    cl.add_argument("--name", default="")
    cl.add_argument("--output", default="")
    cl.add_argument("--rc", type=int, default=0)
    cl.add_argument("--declared", type=int, default=None)
    cl.add_argument("--json", action="store_true")
    cl.set_defaults(func=cmd_classify)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
