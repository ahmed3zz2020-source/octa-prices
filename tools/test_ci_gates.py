#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ حارس بوّابات الـCI (Round 23) — يثبت إن ملف الـCI **مش ممرّر**

🎯 الغرض: الـCI اللي كان في الجولة ٢٢ كان **بيلفّ الفشل**:
   · `pip install || echo`      ⇒ فشل التثبيت مش بيفشل الـjob
   · `continue-on-error: true`   ⇒ فشل الاختبار مش بيفشل الـjob
   · `npm ci || npm install`      ⇒ بيخفي فشل التثبيت
   · ملف اختبار مش شغّال أصلاً   ⇒ استبعاد صامت

📌 هذا الحارس **بيقرأ ملف الـCI نفسه** وبيفشل لو لقى أي حاجة من دي.

⛔ مفيش أي اتصال بالشبكة · مفيش أي سر · مفيش أي تعديل على الملفات.

── التشغيل ───────────────────────────────────────────────
   python3 tools/test_ci_gates.py                       # يفحص .github/workflows/
   python3 tools/test_ci_gates.py path/to/ci.yml        # ملف واحد
   python3 tools/test_ci_gates.py --git-ref ci/octa-ci-r23
   python3 tools/test_ci_gates.py --json

── ليه `--git-ref` مهم ───────────────────────────────────
   فرع الكود بيحمل **نسخة main بالظبط** من ملف الـCI (عشان الدفع
   ميحتاجش scope الـworkflow) ⇒ البوابات الحقيقية lives على فرع `ci/`.
   فـ: `python3 tools/test_ci_gates.py --git-ref ci/octa-ci-r23`
"""
import argparse
import json
import os
import re
import subprocess
import sys

# ══════════════════════════════════════════════════════════════
#  العلامة اللي بتقول: ده ملف CI فيه البوابات الحقيقية
# ══════════════════════════════════════════════════════════════
MARKER = "OCTA-CI-GATES-V1"
MARKER_RE = re.compile(r"^\s*#\s*" + MARKER + r"\s*(.*)$", re.M)
PROFILE_RE = re.compile(r"profile\s*=\s*([a-z0-9_-]+)", re.I)

# ══════════════════════════════════════════════════════════════
#  ① أنماط ممنوعة إطلاقاً (أي ملف CI)
# ══════════════════════════════════════════════════════════════
INSTALL_RE = re.compile(
    r"(^|\s|&&|;)(pip3?|python3?\s+-m\s+pip|npm|yarn|pnpm)\s+"
    r"(install|ci|add|i)\b", re.I)
TEST_RE = re.compile(
    r"(^|\s)(pytest|py\.test|node\s+--test|npm\s+(run\s+)?test|"
    r"unittest|jest|vitest|mocha|go\s+test|cargo\s+test)\b", re.I)

FORBIDDEN_LITERAL = [
    (r"\|\|\s*true\b", "|| true — بيخفي فشل الخطوة"),
    (r"\|\|\s*echo\b", "|| echo — بيخفي فشل الخطوة"),
    (r"\|\|\s*:\s*$", "|| : — بيخفي فشل الخطوة"),
    (r"--ignore(-glob)?\b", "--ignore — استبعاد ملفات من الاختبارات"),
    (r"--exclude\b", "--exclude — استبعاد من الاختبارات"),
    (r"--deselect\b", "--deselect — استبعاد حالات من الاختبارات"),
    (r"--test-name-pattern\b", "--test-name-pattern — تضييق الاختبارات"),
    (r"--test-skip-pattern\b", "--test-skip-pattern — تخطّي اختبارات"),
    (r"(^|\s)-k\s+\S", "-k — تضييق اختبارات pytest"),
    (r"\bxdescribe\s*\(", "xdescribe — تخطّي اختبارات"),
    (r"\bdescribe\s*\.\s*skip\b", "describe.skip — تخطّي اختبارات"),
    (r"\bit\s*\.\s*skip\b", "it.skip — تخطّي اختبارات"),
    (r"\btest\s*\.\s*skip\b", "test.skip — تخطّي اختبارات"),
    (r"\bpytest\s*\.\s*skip\b", "pytest.skip — تخطّي اختبارات"),
    (r"@unittest\s*\.\s*skip", "@unittest.skip — تخطّي اختبارات"),
    (r"\bunittest\s*\.\s*skip\b", "unittest.skip — تخطّي اختبارات"),
    (r"\bSKIP(_FILES|_LIST)?\s*=", "SKIP = — استبعاد ملفات الاختبار"),
    (r"\bEXCLUDE(_FILES|_LIST)?\s*=", "EXCLUDE = — استبعاد ملفات الاختبار"),
    (r"if\s+\\?['\"]test[^'\\\"]*\\?['\"]\s+not\s+in\s", "استبعاد ملفات الاختبار برمجياً"),
    (r"if\s+\\?['\"][^'\\\"]*\.(test|spec)\.[cm]?js['\"]\s+not\s+in\s", "استبعاد ملفات الاختبار برمجياً"),
    (r"if\s+not\s+[A-Za-z_]+\.startswith\(['\"]test", "استبعاد ملفات الاختبار برمجياً"),
    (r"\bskipFiles\b", "skipFiles — استبعاد ملفات الاختبار"),
    (r"\bgit\s+push\b", "git push — الدفع ممنوع في الـCI"),
    (r"\bnpm\s+publish\b", "npm publish — النشر ممنوع في الـCI"),
    (r"\bdocker\s+push\b", "docker push — النشر ممنوع في الـCI"),
    (r"\bwrangler\s+deploy\b", "wrangler deploy — النشر ممنوع في الـCI"),
    (r"\brailway\s+up\b", "railway up — النشر ممنوع في الـCI"),
    (r"\bgh\s+release\b", "gh release — النشر ممنوع في الـCI"),
    (r"\bsecrets\.", "secrets.* — مفيش أسرار في الـCI"),
]
FORBIDDEN_RE = [(re.compile(p, re.I), m) for p, m in FORBIDDEN_LITERAL]

DEPLOY_ACTIONS_RE = re.compile(
    r"uses\s*:\s*\S*(docker|deploy|publish|release|registry|wrangler)"
    r"\S*", re.I)

# ══════════════════════════════════════════════════════════════
#  ② البروفايل الإلزامي للـCI الحقيقي
# ══════════════════════════════════════════════════════════════
PROFILES = {
    "backend": {
        "jobs": ["dependency-install", "backend-suite", "frontend-suite",
                 "hygiene-guards", "data-integrity"],
        "install": "pip install -r requirements.txt",
        "guards": ["test_code_hygiene.py", "test_tree_hygiene.py",
                   "tools/test_ci_gates.py"],
        "data": ["tools/verify_data_integrity.py"],
    },
    "frontend": {
        "jobs": ["dependency-install", "frontend-suite", "hygiene-guards"],
        "install": "npm ci",
        "guards": ["check-text-hygiene.js", "xss-inventory.js", "check-dist.js"],
        "data": [],
    },
}


class Step(object):
    def __init__(self, job, name, run, uses, cond, coe):
        self.job = job
        self.name = name
        self.run = run or ""
        self.uses = uses or ""
        self.cond = cond or ""
        self.coe = coe or ""

    @property
    def text(self):
        return self.run + "\n" + self.uses

    def __repr__(self):
        return "<Step %s/%s>" % (self.job, self.name)


class Workflow(object):
    def __init__(self, path, text):
        self.path = path
        self.text = text
        self.jobs = []          # [(job_id, body_text)]
        self.steps = []         # [Step]
        self.raw = text
        # ⛔ التعليقات (سطر أوله #) مش أوامر ⇒ بتتشال من الفحص
        #    بس بتتحط مكانها سطر فاضي عشان أرقام الأسطر تفضل صح.
        self.clean = "\n".join(
            "" if l.strip().startswith("#") else l for l in text.splitlines())
        m = MARKER_RE.search(text)
        self.marked = bool(m)
        self.profile = ""
        if m:
            pm = PROFILE_RE.search(m.group(1))
            if pm:
                self.profile = pm.group(1).lower()
        self._parse()

    # ── تحليل نصي بسيط (من غير اعتماد على PyYAML) ──────────
    def _parse(self):
        lines = self.raw.splitlines()
        in_jobs = False
        job_id = None
        job_indent = 0
        job_lines = []
        step = None
        step_indent = 0

        def flush_step():
            if step is not None:
                self.steps.append(step)

        for raw in lines:
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" "))
            if not stripped or stripped.startswith("#"):
                if step is not None and stripped.startswith("#"):
                    step.run += "\n" + stripped
                continue
            if re.match(r"^jobs\s*:", stripped):
                in_jobs = True
                continue
            if not in_jobs:
                continue
            # بداية job جديد
            if indent <= 2 and re.match(r"^[A-Za-z0-9_.-]+\s*:", stripped):
                flush_step()
                step = None
                if job_id is not None:
                    self.jobs.append((job_id, "\n".join(job_lines)))
                job_id = stripped.split(":", 1)[0].strip()
                job_indent = indent
                job_lines = [raw]
                continue
            if job_id is None:
                continue
            job_lines.append(raw)
            # بداية step جديد
            if re.match(r"^-\s+", stripped) and indent >= job_indent + 2:
                flush_step()
                step = Step(job_id, "", "", "", "", "")
                step_indent = indent
                key = stripped[1:].strip()
                m = re.match(r"^(name|run|uses|id|if)\s*:\s*(.*)$", key)
                if m:
                    k, v = m.group(1), m.group(2).strip()
                    if k == "name":
                        step.name = v
                    elif k == "uses":
                        step.uses = v
                    elif k == "if":
                        step.cond = v
                    elif k == "run":
                        if v in ("|", ">", "|-", ">-", "|+", ">+"):
                            step.run = ""
                            step._block = True
                        else:
                            step.run = v
                            step._block = False
                continue
            if step is None:
                continue
            # مفاتيح داخل الـstep
            m = re.match(r"^(name|run|uses|if|continue-on-error|env)\s*:\s*(.*)$",
                         stripped)
            if m:
                k, v = m.group(1), m.group(2).strip()
                if k == "name":
                    step.name = v
                elif k == "uses":
                    step.uses = v
                elif k == "if":
                    step.cond = v
                elif k == "continue-on-error":
                    step.coe = v
                elif k == "run":
                    if v in ("|", ">", "|-", ">-", "|+", ">+"):
                        step.run = ""
                        step._block = True
                    else:
                        step.run = v
                        step._block = False
                continue
            # سطر تالي داخل بلوك run
            if getattr(step, "_block", False):
                if indent > step_indent:
                    step.run += ("\n" if step.run else "") + raw.strip()
                else:
                    step._block = False
        flush_step()
        if job_id is not None:
            self.jobs.append((job_id, "\n".join(job_lines)))

    def job_ids(self):
        return [j for j, _ in self.jobs]


# ══════════════════════════════════════════════════════════════
#  الفحوصات
# ══════════════════════════════════════════════════════════════
def parse_needs(body):
    """بيرجّع قائمة الـjobs اللي الـjob ده محتاجها."""
    m = re.search(r"^\s*needs\s*:\s*(.+)$", body, re.M)
    if not m:
        return []
    val = m.group(1).strip()
    if val.startswith("["):
        val = val.strip("[]")
    return [v.strip().strip("'\"") for v in val.split(",") if v.strip()]


def check_workflow(wf, findings):
    """قاعدة ①: أي نمط ممنوع في أي ملف CI."""
    for st in wf.steps:
        text = st.text
        clean = "\n".join("" if l.strip().startswith("#") else l
                          for l in text.splitlines())
        is_install = bool(INSTALL_RE.search(clean))
        is_test = bool(TEST_RE.search(clean))
        # continue-on-error على خطوة تثبيت/اختبار
        if st.coe and re.match(r"^(true|yes|1)$", st.coe.strip(),
                               re.I) and (is_install or is_test):
            findings.append(
                (wf.path, st.job, st.name,
                 "continue-on-error على خطوة تثبيت/اختبار — الفشل مش "
                 "بيفشّل الـjob"))
        # || جوّه أمر التثبيت
        if "||" in clean and is_install:
            findings.append(
                (wf.path, st.job, st.name,
                 "pip/npm install مع || — فشل التثبيت ممكن يتخبى"))
        # خطوة «خطأ» جوّه run
        if re.search(r"(^|\n)\s*set\s+\+\w+", clean):
            findings.append((wf.path, st.job, st.name,
                             "set +e — بيخفي فشل الخطوة"))
    # continue-on-error: true في أي مكان (متغير على مستوى الـjob)
    for m in re.finditer(r"continue-on-error\s*:\s*(true|yes|1)\b", wf.clean,
                         re.I):
        findings.append((wf.path, "-", "-",
                         "continue-on-error: true — الفشل مش بيفشّل الـjob"))
    # الأنماط النصية الممنوعة
    for rx, msg in FORBIDDEN_RE:
        for m in rx.finditer(wf.clean):
            line = wf.clean[:m.start()].count("\n") + 1
            snippet = wf.clean.splitlines()[line - 1].strip()[:90]
            findings.append((wf.path, "-", "line %d" % line,
                             "%s  ⟵ %s" % (msg, snippet)))
    # أوامر نشر/دفع في خطوة
    for st in wf.steps:
        clean = "\n".join("" if l.strip().startswith("#") else l
                          for l in st.text.splitlines())
        if re.search(r"\bgit\s+push\b|\bdeploy\b|\bpublish\b", clean,
                     re.I):
            findings.append((wf.path, st.job, st.name,
                             "خطوة فيها نشر/دفع — ممنوع في الـCI"))
    # uses لتطبيق نشر
    for m in DEPLOY_ACTIONS_RE.finditer(wf.clean):
        findings.append((wf.path, "-", "-",
                         "uses لتطبيق نشر/نشر حزم — ممنوع في الـCI"))


def check_profile(wf, findings):
    """قاعدة ②: البروفايل الإلزامي (لملفات الـCI الحقيقية فقط)."""
    prof = PROFILES.get(wf.profile)
    if prof is None:
        findings.append((wf.path, "-", "-",
                         "البروفايل غير معروف: %r" % wf.profile))
        return
    ids = wf.job_ids()
    for need in prof["jobs"]:
        if need not in ids:
            findings.append((wf.path, "-", "-",
                             "الـjob المطلوب ناقص: %s" % need))
    # تثبيت الاعتماديات لازم يكون job مستقل وبلا مراوغة
    install_job = None
    for jid, body in wf.jobs:
        if jid == "dependency-install":
            install_job = body
    if install_job is None:
        findings.append((wf.path, "-", "-",
                         "مفيش job لتثبيت الاعتماديات (dependency-install)"))
    else:
        if prof["install"].lower() not in install_job.lower():
            findings.append((wf.path, "dependency-install", "-",
                             "الأمر الإلزامي للتثبيت ناقص: %s"
                             % prof["install"]))
        if re.search(r"continue-on-error", install_job, re.I):
            findings.append((wf.path, "dependency-install", "-",
                             "continue-on-error في job التثبيت"))
        if "||" in install_job:
            findings.append((wf.path, "dependency-install", "-",
                             "|| في job التثبيت — الفشل ممكن يتخبى"))
    # الحارس: لازم كل بوابة حراسة موجودة
    all_jobs = "\n".join(b for _, b in wf.jobs)
    for g in prof["guards"] + prof["data"]:
        if g not in all_jobs:
            findings.append((wf.path, "-", "-",
                             "البوابة الإلزامية ناقصة: %s" % g))
    # لو التثبيت فشل ⇒ الخطوات اللي بعده ما تشتغلش
    for st in wf.steps:
        cond = st.cond.lower()
        if re.search(r"always\(\)|failure\(\)|!cancelled\(\)", cond):
            findings.append((wf.path, st.job, st.name,
                             "if: always() — الخطوة هتشتغل حتى لو التثبيت "
                             " فشل"))
    # الـjobs اللي محتاجة التثبيت لازم تعتمد عليه (عن طريق السلسلة)
    needs_map = {}
    for jid, body in wf.jobs:
        needs_map[jid] = parse_needs(body)
    reachable = set()
    stack = ["dependency-install"]
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for jid, deps in needs_map.items():
            if cur in deps and jid not in reachable:
                stack.append(jid)
    for jid in prof["jobs"]:
        if jid != "dependency-install" and jid not in reachable:
            findings.append((wf.path, jid, "-",
                             "الـjob ده مش مربوط بسلسلة job التثبيت "
                             "⇒ لو التثبيت فشل ممكن الـjob ده يشتغل"))


# ══════════════════════════════════════════════════════════════
#  جمع الملفات
# ══════════════════════════════════════════════════════════════
def collect(paths, git_ref=None):
    out = []
    if git_ref:
        try:
            names = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", git_ref,
                 ".github/workflows"],
                capture_output=True, text=True, timeout=120).stdout.split()
        except Exception as exc:  # pragma: no cover
            raise SystemExit("تعذّر قراءة الـgit ref %s: %s" % (git_ref, exc))
        for n in names:
            if not n.endswith((".yml", ".yaml")):
                continue
            txt = subprocess.run(["git", "show", "%s:%s" % (git_ref, n)],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=120).stdout
            out.append(("%s (%s)" % (n, git_ref), txt))
        return out
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.endswith((".yml", ".yaml")):
                        fp = os.path.join(root, f)
                        out.append((fp, read(fp)))
        elif os.path.isfile(p):
            out.append((p, read(p)))
        else:
            raise SystemExit("المسار مش موجود: %s" % p)
    return out


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ══════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="حارس بوّابات الـCI — يفشل لو ملف الـCI فيه مراوغة")
    ap.add_argument("paths", nargs="*",
                    help="ملف/مجلد workflows (افتراضياً .github/workflows)")
    ap.add_argument("--git-ref", default="",
                    help="افحص ملف الـCI من فرع/كوميت معيّن بدل الشجرة")
    ap.add_argument("--json", action="store_true", help="ناتج JSON")
    args = ap.parse_args(argv)

    paths = args.paths or [os.path.join(".github", "workflows")]
    files = collect(paths, args.git_ref or None)
    if not files:
        print("❌ مفيش أي ملف workflow اتفحص")
        return 2

    findings = []
    gated = []
    for path, text in files:
        wf = Workflow(path, text)
        check_workflow(wf, findings)
        if wf.marked:
            gated.append(wf)
            check_profile(wf, findings)

    if not gated:
        findings.append(("*" + os.pathsep + "*", "-", "-",
                         "مفيش أي ملف workflow فيه علامة %s "
                         "⇒ البوابات الحقيقية مش موجودة" % MARKER))

    ok = not findings
    if args.json:
        print(json.dumps({
            "ok": ok,
            "scanned": [p for p, _ in files],
            "gated": [w.path for w in gated],
            "findings": [{"file": f[0], "job": f[1], "step": f[2],
                          "reason": f[3]} for f in findings],
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    print("═" * 72)
    print("🛡️ حارس بوّابات الـCI — الجولة ٢٣")
    print("═" * 72)
    print("📂 ملفات اتفحصت: %d" % len(files))
    for p, _ in files:
        print("   · %s" % p)
    print("🚪 ملفات فيها البوابات الحقيقية (%s): %d" % (MARKER, len(gated)))
    for w in gated:
        print("   · %s  [بروفايل: %s]" % (w.path, w.profile))
    print("")
    if ok:
        print("✅ كل البوابات سليمة — مفيش أي مراوغة في ملف الـCI")
        return 0
    print("❌ لقيت %d مشكلة:" % len(findings))
    for f in findings:
        print("   ⛔ [%s] %s — %s" % (f[0], f[2] or f[1], f[3]))
    print("")
    print("ℹ️  لو أنت على فرع كود بيحمل نسخة main بالظبط من ملف الـCI")
    print("    (عشان الدفع ميحتاجش scope الـworkflow) ⇒ افحص فرع الـci:")
    print("       python3 tools/test_ci_gates.py --git-ref ci/octa-ci-r23")
    return 1


if __name__ == "__main__":
    sys.exit(main())
