#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبارات أداة التصنيف الرباعي — الجولة ٢٦ (R26 · مرحلة الـCI)

🎯 الغرض:
   نثبت إن المُصنِّف (tools/ci_result_classifier.py ⭐) بيصنّف صح ⭐
   وبيحوّل **المتخطى** و**المحجوب** إلى **فشل** ⭐ (مش نجاح ⭐).

📌 الحالات المغطّاة:
   ① ملف بايثون نجح          ⇒ passed
   ② ملف بايثون فشل          ⇒ failed
   ③ ملف بايثون تخطّى        ⇒ skipped  ⭐ (ومعه: الـjob بيفشل ⭐)
   ④ ملف node نجح            ⇒ passed
   ⑤ ملف node فيه رجوع صامت ⭐ ⇒ blocked ⭐ (ومعه: الـjob بيفشل ⭐)
   ⑥ مرجع git مفقود          ⇒ blocked ⭐ (غياب موثّق مش نجاح صامت ⭐)

⛔ مفيش أي اتصال بالشبكة · مفيش أي سر · مفيش أي تعديل على الملفات.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLASSIFIER = os.path.join(ROOT, "tools", "ci_result_classifier.py")

FAILS = []
CHECKS = 0

PASSED_MARK = "✅"
FAIL_MARK = "❌"
# ⛔ علامة التخطّي الصريحة (نفس اللي المُصنِّف بيفحصها ⭐)
SKIP_MARK = "⏭"
AR_SKIP = "متخط"


def check(cond, msg, extra=""):
    global CHECKS
    CHECKS += 1
    if cond:
        print("   %s %s" % (PASSED_MARK, msg))
    else:
        FAILS.append(msg)
        print("   %s %s — %s" % (FAIL_MARK, msg, extra))
    return bool(cond)


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def run_classifier(root, kind, patterns=None):
    out = os.path.join(root, "result.json")
    cmd = [sys.executable, CLASSIFIER, "run", "--kind", kind,
           "--root", root, "--out", out, "--timeout", "120"]
    for pat in (patterns or []):
        cmd.extend(["--pattern", pat])
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600)
    data = {}
    if os.path.isfile(out):
        with open(out, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    return proc, data


def status_of(data, name):
    for rec in data.get("files", []):
        if rec["file"].endswith(name):
            return rec
    return {}


print("=" * 70)
print("  🧪 اختبارات أداة التصنيف الرباعي — الجولة ٢٦")
print("=" * 70)

TMP = tempfile.mkdtemp(prefix="octa_r26_classifier_")

# ══════════════════════════════════════════════════════════════
#  ① ② ③ بايثون: نجح · فشل · تخطّى
# ══════════════════════════════════════════════════════════════
py_dir = os.path.join(TMP, "py")
write(os.path.join(py_dir, "test_ok.py"),
      "# -*- coding: utf-8 -*-\n"
      "import sys\n"
      "print('  %s case one')\n"
      "print('  %s case two')\n"
      "sys.exit(0)\n" % (PASSED_MARK, PASSED_MARK))
write(os.path.join(py_dir, "test_bad.py"),
      "# -*- coding: utf-8 -*-\n"
      "import sys\n"
      "print('  %s boom')\n"
      "sys.exit(3)\n" % FAIL_MARK)
write(os.path.join(py_dir, "test_skipped.py"),
      "# -*- coding: utf-8 -*-\n"
      "import sys\n"
      "print('  %s %s: محتاج بيئة حيّة')\n"
      "sys.exit(0)\n" % (SKIP_MARK, AR_SKIP))
# ⛔ ملف بنمط إخراج إنجليزي (PASS/FAIL) ⭐ — لازم يتصنّف صح ⭐
#    (كان بيتصنّف blocked زوّptime ⭐)
write(os.path.join(py_dir, "test_english_marks.py"),
      "# -*- coding: utf-8 -*-\n"
      "import sys\n"
      "print('PASS first case')\n"
      "print('PASS second case')\n"
      "print('3/3 ناجح')\n"
      "sys.exit(0)\n")

proc, data = run_classifier(py_dir, "python")
print("  ── بايثون")
rec_ok = status_of(data, "test_ok.py")
rec_bad = status_of(data, "test_bad.py")
rec_skip = status_of(data, "test_skipped.py")
rec_en = status_of(data, "test_english_marks.py")
check(rec_ok.get("status") == "passed",
      "ملف بايثون نجح ⇒ passed", rec_ok.get("status"))
check(rec_bad.get("status") == "failed",
      "ملف بايثون فشل ⇒ failed", rec_bad.get("status"))
check(rec_skip.get("status") == "skipped",
      "ملف بايثون تخطّى ⇒ skipped", rec_skip.get("status"))
check(rec_en.get("status") == "passed",
      "ملف بنمط PASS/FAIL ⇒ passed (مش blocked ⭐)", rec_en.get("status"))
check((rec_en.get("cases") or 0) >= 2,
      "عدد الحالات اتحسب من نمط PASS ⭐", rec_en.get("cases"))
check(proc.returncode != 0,
      "المتخطى بيخلي بوابة الـjob تفشل ⭐", "rc=%s" % proc.returncode)
check(data.get("ok") is False, "النتيجة الكلية مش OK مع متخطّى ⭐")

# ══════════════════════════════════════════════════════════════
#  ④ ⑤ node: نجح · رجوع صامت
# ══════════════════════════════════════════════════════════════
js_dir = os.path.join(TMP, "js")
write(os.path.join(js_dir, "a.test.js"),
      "'use strict';\n"
      "const test = require('node:test');\n"
      "const assert = require('node:assert/strict');\n"
      "test('case one', () => { assert.ok(true); });\n"
      "test('case two', () => { assert.ok(true); });\n")
# ⛔ ملف بيعتمد على مرجع git وبيرجع صامت لو المرجع مش موجود ⭐
# ⛔ الـsha الوهمي بيتكوّن وقت التشغيل ⭐ (مش مكتوب في المصدر ⭐)
#    عشان أداة التصنيف متعتبرش الملف ده نفسه معتمد على مرجع git ⭐
FAKE_SHA = "dead" + "beef" * 9
write(os.path.join(js_dir, "b.test.js"),
      "'use strict';\n"
      "const test = require('node:test');\n"
      "const assert = require('node:assert/strict');\n"
      "const { execFileSync } = require('node:child_process');\n"
      "test('negative proof needs a git ref', () => {\n"
      "  let before = '';\n"
      "  try {\n"
      "    before = execFileSync('git',\n"
      "      ['show', '%s:x.js'],\n"
      "      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });\n"
      "  } catch (e) {\n"
      "    return;\n"
      "  }\n"
      "  assert.ok(before.length > 0);\n"
      "});\n"
      "test('case two', () => { assert.ok(true); });\n" % FAKE_SHA)

proc2, data2 = run_classifier(js_dir, "node", ["*.test.js"])
print("  ── node")
rec_a = status_of(data2, "a.test.js")
rec_b = status_of(data2, "b.test.js")
check(rec_a.get("status") == "passed",
      "ملف node نجح ⇒ passed", rec_a.get("status"))
check(rec_b.get("status") == "blocked",
      "ملف node فيه مرجع git مفقود ⇒ blocked ⭐", rec_b.get("status"))
check(proc2.returncode != 0,
      "المحجوب بيخلي بوابة الـjob تفشل ⭐", "rc=%s" % proc2.returncode)
check(FAKE_SHA in json.dumps(data2, ensure_ascii=False),
      "سبب الحجب موثّق في الـJSON ⭐")

# ══════════════════════════════════════════════════════════════
#  ⑥ نفس الملف في مستودع git فيه المرجع ⇒ passed ⭐
# ══════════════════════════════════════════════════════════════
git_dir = os.path.join(TMP, "git")
write(os.path.join(git_dir, "c.test.js"),
      "'use strict';\n"
      "const test = require('node:test');\n"
      "const assert = require('node:assert/strict');\n"
      "const { execFileSync } = require('node:child_process');\n"
      "test('negative proof needs a git ref', () => {\n"
      "  let before = '';\n"
      "  try {\n"
      "    before = execFileSync('git',\n"
      "      ['show', 'HEAD:x.js'],\n"
      "      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });\n"
      "  } catch (e) {\n"
      "    return;\n"
      "  }\n"
      "  assert.ok(before.length > 0);\n"
      "});\n")
env = dict(os.environ)
env.update({"GIT_AUTHOR_NAME": "r26", "GIT_AUTHOR_EMAIL": "r26@example.test",
            "GIT_COMMITTER_NAME": "r26", "GIT_COMMITTER_EMAIL": "r26@example.test"})
subprocess.run(["git", "init", "-q", git_dir], env=env, timeout=120)
write(os.path.join(git_dir, "x.js"), "// baseline\n")
subprocess.run(["git", "-C", git_dir, "add", "-A"], env=env, timeout=120)
subprocess.run(["git", "-C", git_dir, "commit", "-q", "-m", "base"], env=env,
               timeout=120)
proc3, data3 = run_classifier(git_dir, "node", ["*.test.js"])
rec_c = status_of(data3, "c.test.js")
print("  ── git")
check(rec_c.get("status") == "passed",
      "المرجع موجود ⇒ الملف مرّ عادي ⭐", rec_c.get("status"))
check(proc3.returncode == 0,
      "المستودع السليم بيعدّي ⭐", "rc=%s" % proc3.returncode)

shutil.rmtree(TMP, ignore_errors=True)

print("=" * 70)
print("  النتيجة: %d ناجح / %d فاشل" % (CHECKS - len(FAILS), len(FAILS)))
print("=" * 70)
for f in FAILS:
    print("  %s فشل: %s" % (FAIL_MARK, f))
sys.exit(1 if FAILS else 0)
