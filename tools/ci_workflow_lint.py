#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 مدقّق تعريف الـActions — الجولة ٢٦ (R26 · مرحلة الـCI)

🎯 الغرض:
   `actionlint` مش مضمون يكون متاح على المُشغّل ⭐ ⇒ لازم يكون عندنا
   **مدقّق أدق** يفحص **تعريف ملف الـworkflow** نفسه ⭐ (مش بس صحّة YAML)
   ⭐ ويقول: «لا تعريف ناقص» ⭐.

📌 وش اللي بيفحصه بالظبط (كله بخط سطر):
   ① المفاتيح على مستوى الملف: مفيش مفتاح مجهول ⭐
   ② لازم `on:` و `jobs:` ⭐
   ③ كل job: لازم `runs-on:` و `steps:` ⭐
   ④ كل step: لازم `name:` + واحد بالظبط من `run:` أو `uses:` ⭐
   ⑤ ⛔ `fetch-depth` (وأي input) لازم يكون **جوه `with:`** ⭐
      (لو واقف جنب `uses:` ⇒ الـworkflow مش بيتقراش أصلاً ⭐)
   ⑥ ⛔ `with:` على خطوة `run:` ⇒ تعريف ناقص ⭐
   ⑦ ⛔ `continue-on-error: true` ⇒ الفشل مش بيفشّل الـjob ⭐
   ⑧ ⛔ `|| true` / `|| echo` / `|| :` ⇒ بيخفي فشل الخطوة ⭐
   ⑨ ⛔ `if: always()` / `failure()` ⇒ الخطوة بتشتغل بعد فشل ⭐
   ⑩ `needs` لازم يشير على job موجود ⭐
   ⑪ (اختياري · لو PyYAML متاح) فحص بنيوي كامل: أنواع القيم ·
       مفاتيح مجهولة · تكرار المفاتيح · `with:` مع `run:` ⭐

⛔ مفيش أي اتصال بالشبكة · مفيش أي سر · مفيش أي تعديل على الملفات.

── التشغيل ───────────────────────────────────────────────
   python3 tools/ci_workflow_lint.py .github/workflows/ci.yml
   python3 tools/ci_workflow_lint.py .github/workflows/ci.yml --json
"""
import argparse
import json
import re
import sys

TOP_LEVEL_OK = {
    "name", "on", "env", "jobs", "concurrency", "permissions",
    "defaults", "run-name",
}
JOB_KEYS_OK = {
    "name", "needs", "runs-on", "permissions", "environment", "concurrency",
    "outputs", "env", "defaults", "if", "steps", "timeout-minutes",
    "continue-on-error", "container", "services", "strategy",
}
STEP_KEYS_OK = {
    "name", "id", "if", "uses", "with", "run", "env", "working-directory",
    "shell", "timeout-minutes", "continue-on-error", "defaults",
}
# ⛔ inputs المسموح بها لـactions/checkout
CHECKOUT_WITH_OK = {
    "repository", "ref", "token", "ssh-key", "ssh-known-hosts",
    "ssh-strict", "ssh-user", "persist-credentials", "path", "clean",
    "fetch-depth", "submodules", "lfs", "set-safe-directory",
}
# ⛔ مدخلات مُشغّلات الإعداد (setup-python / setup-node) — حدود معروفة
SETUP_WITH_OK = {
    "python-version", "architecture", "check-latest", "cache",
    "cache-dependency-path", "cache-python-version", "token",
    "node-version", "node-version-file", "registry-url", "scope",
    "always-auth", "mirror", "mirror-token",
}
WITH_OK = CHECKOUT_WITH_OK | SETUP_WITH_OK
# ⛔ أي input شائع — لو وقف برّه with: فهو غلطRegardless
KNOWN_INPUTS = {
    "fetch-depth", "python-version", "node-version", "cache", "repository",
    "ref", "token", "submodules", "lfs", "path", "clean", "persist-credentials",
    "sparse-checkout", "sparse-checkout-cone-mode", "set-safe-directory",
    "architecture", "check-latest", "cache-dependency-path", "node-version-file",
    "registry-url", "scope", "always-auth", "mirror", "mirror-token",
}

BLOCK_SCALAR_RE = re.compile(r"^[|>][+-]?\d*$")
FORBIDDEN_OR_RE = re.compile(r"\|\|\s*(true|echo|:)\b")
ALWAYS_IF_RE = re.compile(r"always\s*\(|failure\s*\(|cancelled\s*\(")
KEY_RE = re.compile(r"^([A-Za-z0-9_.\-]+|\"[^\"]+\"|'[^']+')\s*:(.*)$")


class LintError(object):
    def __init__(self, path, line, code, msg):
        self.path = path
        self.line = line
        self.code = code
        self.msg = msg

    def __str__(self):
        return "%s:%s · %s — %s" % (self.path, self.line, self.code, self.msg)


# ══════════════════════════════════════════════════════════════
#  أدوات YAML النصّية
# ══════════════════════════════════════════════════════════════
def _strip_comment(line):
    """يشيل التعليق من السطر — مبيشيلش الـ# جوه اقتباس."""
    out = []
    quote = None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def scan_lines(text):
    """بيرجّع قائمة سطور: (indent, content, line_no, raw)."""
    out = []
    for i, raw in enumerate(text.splitlines()):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            out.append((None, "", i + 1, raw))
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        out.append((indent, stripped.strip(), i + 1, raw))
    return out


def _key_of(content):
    m = KEY_RE.match(content)
    if not m:
        return None, None
    key = m.group(1).strip("\"'")
    return key, m.group(2).strip()


def _is_block_body(lines, idx, parent_indent):
    """هل السطر ده جسم بلوك (سلّ-quantifier)؟"""
    return False


def _collect_block(lines, idx, parent_indent):
    """يجمع جسم البلوك (السطور الأعمق) ويرجّع (نص, سطر_بعد)."""
    body = []
    while idx < len(lines):
        ind, content, line_no, raw = lines[idx]
        if ind is None:
            body.append("")
            idx += 1
            continue
        if ind <= parent_indent:
            break
        body.append(raw)
        idx += 1
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body), idx


# ══════════════════════════════════════════════════════════════
#  الفحص النصّي (بدون أي اعتماد خارجي)
# ══════════════════════════════════════════════════════════════
def _block_end(lines, start, indent):
    """أول فهرس بعد `start` بـindentation سطحي أو أقل."""
    for j in range(start + 1, len(lines)):
        ind = lines[j][0]
        if ind is None:
            continue
        if ind <= indent:
            return j
    return len(lines)


def lint_text(path, text):
    findings = []
    lines = scan_lines(text)
    total = len(lines)

    # ── ① المفاتيح على مستوى الملف ─────────────────────────
    top_keys = {}
    for ind, content, line_no, _raw in lines:
        if ind is None or ind != 0:
            continue
        key, value = _key_of(content)
        if key is None:
            continue
        top_keys[key] = (value, line_no, )
        if key not in TOP_LEVEL_OK:
            findings.append(LintError(path, line_no, "E001",
                                      "مفتاح مجهول على مستوى الملف: %s" % key))

    # ── ② on + jobs ───────────────────────────────────────
    if "on" not in top_keys:
        findings.append(LintError(path, 1, "E002", "مفيش `on:` في الملف"))
    jobs_idx = None
    for i, (ind, content, line_no, _raw) in enumerate(lines):
        if ind == 0:
            key, _v = _key_of(content)
            if key == "jobs":
                jobs_idx = i
                break
    if jobs_idx is None:
        findings.append(LintError(path, 1, "E003", "مفيش `jobs:` في الملف"))
        return findings

    jobs_end = _block_end(lines, jobs_idx, 0)
    job_indent = None
    for i in range(jobs_idx + 1, jobs_end):
        if lines[i][0] is None:
            continue
        job_indent = lines[i][0]
        break
    if job_indent is None:
        findings.append(LintError(path, 1, "E004", "`jobs:` فاضي"))
        return findings

    job_ids = []
    job_lines = {}
    job_starts = []
    for i in range(jobs_idx + 1, jobs_end):
        ind, content, line_no, _raw = lines[i]
        if ind != job_indent:
            continue
        key, _v = _key_of(content)
        if key is None:
            continue
        job_ids.append(key)
        job_lines[key] = line_no
        job_starts.append((key, i))

    # ── ③⑤⑥⑦⑧⑨ كل job وخطواته ───────────────────────────
    for pos, (job_id, start) in enumerate(job_starts):
        job_end = job_starts[pos + 1][1] if pos + 1 < len(job_starts) else jobs_end
        job_key_indent = None
        for i in range(start + 1, job_end):
            ind = lines[i][0]
            if ind is None:
                continue
            job_key_indent = ind
            break
        job_keys = {}
        if job_key_indent is not None:
            for i in range(start + 1, job_end):
                ind, content, line_no, _raw = lines[i]
                if ind != job_key_indent:
                    continue
                key, value = _key_of(content)
                if key is None:
                    continue
                job_keys[key] = (value, line_no)
        # مفاتيح مجهولة في الـjob
        for jkey, (_jv, jline) in job_keys.items():
            if jkey not in JOB_KEYS_OK:
                findings.append(LintError(path, jline, "E011",
                                          "مفتاح مجهول في الـjob %s: %s"
                                          % (job_id, jkey)))
        # ③ runs-on + steps
        if "runs-on" not in job_keys:
            findings.append(LintError(path, job_lines.get(job_id, 1), "E012",
                                      "الـjob %s مفيش `runs-on:`" % job_id))
        if "steps" not in job_keys:
            findings.append(LintError(path, job_lines.get(job_id, 1), "E013",
                                      "الـjob %s مفيش `steps:`" % job_id))
        else:
            findings.extend(_lint_steps(path, job_id, lines, start, job_end,
                                        job_key_indent))
        # ⑩ needs
        if "needs" in job_keys:
            nvalue, nline = job_keys["needs"]
            for dep in re.split(r"[,\s]+", nvalue.strip("[]\"' ")):
                dep = dep.strip()
                if dep and dep not in job_ids:
                    findings.append(LintError(
                        path, nline, "E015",
                        "الـjob %s محتاج job مش موجود: %s" % (job_id, dep)))
    return findings


def _lint_steps(path, job_id, lines, job_start, job_end, job_key_indent):
    """يفحص خطوات الـjob — بيرجّع قائمة مشاكل."""
    findings = []
    if job_key_indent is None:
        return findings
    # نلاقي مستوى عناصر الـsteps
    step_indent = None
    for i in range(job_start + 1, job_end):
        ind, content, _line_no, _raw = lines[i]
        if ind is None or ind <= job_key_indent:
            continue
        if content.startswith("- "):
            step_indent = ind
            break
    if step_indent is None:
        return findings

    # نجمّع الخطوات — مفاتيح الخطوة على مستوى `step_indent + 2` بالظبط
    # (يعني `with:`/`env:` وأجسام البلوكات — اللي أعمق — مش مفاتيح خطوة)
    step_key_indent = step_indent + 2
    steps = []
    cur = None
    for i in range(job_start + 1, job_end):
        ind, content, line_no, _raw = lines[i]
        if ind is None or ind <= job_key_indent:
            continue
        if ind == step_indent and content.startswith("- "):
            rest = content[2:].strip()
            cur = {"line": line_no, "keys": {}, "body": []}
            steps.append(cur)
            key, value = _key_of(rest)
            if key is not None:
                cur["keys"][key] = (value, line_no)
            continue
        if cur is None or ind != step_key_indent:
            continue
        key, value = _key_of(content)
        if key is not None:
            cur["keys"][key] = (value, line_no)

    # نجمع نصوص البلوكات
    for st in steps:
        for key, (value, line_no) in list(st["keys"].items()):
            if BLOCK_SCALAR_RE.match(value or ""):
                start = None
                for idx, (_ind, _content, lno, _raw) in enumerate(lines):
                    if lno == line_no:
                        start = idx
                        break
                if start is None:
                    continue
                body, _end = _collect_block(lines, start + 1, step_key_indent)
                st["body"].append(body)

    for st in steps:
        keys = st["keys"]
        line_no = st["line"]
        # ④ اسم + run/uses
        if "name" not in keys:
            findings.append(LintError(path, line_no, "E021",
                                      "خطوة في الـjob %s من غير `name:`" % job_id))
        has_run = "run" in keys
        has_uses = "uses" in keys
        if not has_run and not has_uses:
            findings.append(LintError(path, line_no, "E022",
                                      "خطوة في الـjob %s من غير `run:` "
                                      "ومن غير `uses:`" % job_id))
        if has_run and has_uses:
            findings.append(LintError(path, line_no, "E023",
                                      "خطوة في الـjob %s عندها `run:` و `uses:`"
                                      % job_id))
        for key, (_v, ln) in keys.items():
            if key not in STEP_KEYS_OK:
                findings.append(LintError(path, ln, "E024",
                                          "مفتاح مجهول في الخطوة: %s" % key))
            # ⑤ inputs برّه with:
            if key in KNOWN_INPUTS:
                findings.append(LintError(
                    path, ln, "E025",
                    "`%s` لازم يكون جوّه `with:` — كده الـworkflow "
                    "مش بيتقراش" % key))
        # ⑥ with: على خطوة run:
        if "with" in keys and not has_uses:
            findings.append(LintError(
                path, keys["with"][1], "E026",
                "`with:` على خطوة فيها `run:` — ده تعريف ناقص"))
        # ⑦ continue-on-error
        if "continue-on-error" in keys:
            val = str(keys["continue-on-error"][0]).strip().lower()
            if val in ("true", "yes", "1"):
                findings.append(LintError(
                    path, keys["continue-on-error"][1], "E027",
                    "continue-on-error: true — الفشل مش بيفشّل الـjob"))
        # ⑧ بيخفي فشل الخطوة
        body = "\n".join(st["body"])
        for m in FORBIDDEN_OR_RE.finditer(body):
            findings.append(LintError(path, line_no, "E028",
                                      "`%s` بيخفي فشل الخطوة"
                                      % m.group(0).strip()))
        # ⑨ always/failure
        if "if" in keys:
            cond = keys["if"][0] or ""
            if ALWAYS_IF_RE.search(cond):
                findings.append(LintError(
                    path, keys["if"][1], "E029",
                    "`if:` فيه always/failure — الخطوة بتشتغل بعد فشل"))
    return findings


# ══════════════════════════════════════════════════════════════
#  الفحص الإضافي بـPyYAML (لو متاح)
# ══════════════════════════════════════════════════════════════
def lint_with_pyyaml(path, text, findings):
    """فحص إضافي: أنواع القيم · مفاتيح مجهولة · تكرار المفاتيح."""
    try:
        import yaml
    except ImportError:
        return False
    try:
        doc = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001
        findings.append(LintError(path, 1, "E100",
                                  "الملف مش YAML صالح: %s" % exc))
        return True
    if not isinstance(doc, dict):
        findings.append(LintError(path, 1, "E101", "الملف لازم يكون map"))
        return True
    # ⛔ PyYAML بيحوّل `on` لـTrue (قاعدة YAML 1.1)
    if ("on" not in doc) and (True not in doc):
        findings.append(LintError(path, 1, "E102", "مفيش `on:` بعد التحليل"))
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        findings.append(LintError(path, 1, "E103",
                                  "`jobs:` لازم يكون map غير فاضي"))
        return True
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            findings.append(LintError(path, 1, "E104",
                                      "الـjob %s مش map" % job_id))
            continue
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            continue
        for step in steps:
            if not isinstance(step, dict):
                findings.append(LintError(path, 1, "E105",
                                          "خطوة في %s مش map" % job_id))
                continue
            for key, value in step.items():
                if key == "with" and not isinstance(value, dict):
                    findings.append(LintError(
                        path, 1, "E106",
                        "`with:` في خطوة الـjob %s لازم يكون map" % job_id))
            uses = str(step.get("uses", ""))
            if uses.startswith("actions/checkout@"):
                with_vals = step.get("with") or {}
                if isinstance(with_vals, dict):
                    for key in with_vals:
                        if key not in CHECKOUT_WITH_OK:
                            findings.append(LintError(
                                path, 1, "E107",
                                "input مجهول لـactions/checkout: %s" % key))
            if "run" in step and "with" in step:
                findings.append(LintError(
                    path, 1, "E108",
                    "خطوة فيها `run:` و `with:` مع بعض — تعريف ناقص"))
    for key in ("jobs", "env", "on"):
        occurrences = len(re.findall(r"^%s\s*:" % re.escape(key), text, re.M))
        if occurrences > 1:
            findings.append(LintError(path, 1, "E109",
                                      "المفتاح `%s` متكرر %d مرات"
                                      % (key, occurrences)))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="مدقّق تعريف الـActions — لا تعريف ناقص")
    ap.add_argument("paths", nargs="*",
                    help="ملفات workflow (افتراضياً .github/workflows/*.yml)")
    ap.add_argument("--json", action="store_true", help="ناتج JSON")
    ap.add_argument("--no-pyyaml", action="store_true",
                    help="منع الفحص الإضافي بـPyYAML")
    args = ap.parse_args(argv)

    paths = args.paths
    if not paths:
        import glob as _glob
        paths = sorted(_glob.glob(".github/workflows/*.yml")
                       + _glob.glob(".github/workflows/*.yaml"))
    if not paths:
        print("❌ مفيش أي ملف workflow اتفحص")
        return 2

    findings = []
    scanned = []
    pyyaml_used = False
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        scanned.append(p)
        findings.extend(lint_text(p, text))
        if not args.no_pyyaml:
            pyyaml_used = lint_with_pyyaml(p, text, findings) or pyyaml_used

    if args.json:
        print(json.dumps({
            "ok": not findings,
            "pyyaml": pyyaml_used,
            "scanned": scanned,
            "findings": [{"file": f.path, "line": f.line, "code": f.code,
                          "message": f.msg} for f in findings],
        }, ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    print("═" * 72)
    print("🔍 مدقّق تعريف الـActions")
    print("═" * 72)
    print("📂 ملفات اتفحصت: %d" % len(scanned))
    for p in scanned:
        print("   · %s" % p)
    print("🧩 الفحص البنيوي الكامل (PyYAML): %s"
          % ("مفعّل" if pyyaml_used else "غير متاح — الفحص النصّي بس"))
    if not findings:
        print("✅ كل تعريفات الـActions سليمة — مفيش تعريف ناقص")
        return 0
    print("❌ لقيت %d مشكلة:" % len(findings))
    for f in findings:
        print("   ⛔ %s" % f)
    return 1


if __name__ == "__main__":
    sys.exit(main())
