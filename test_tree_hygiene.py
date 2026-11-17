#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ الجولة ٢١ (R21 · المرحلة الأولى) — حارس نظافة الشجرة المرشحة

📌 المشكلة (مثبتة): الـcommit `c4adb7b` (الجولة ٢٠) ⭐ كان فيه
   ⛔ **70 ملف** في ١٤ مجلد مؤقت (`.r17_p3_tmp_*`) ⭐ ⇒ ⛔ الشجرة
   المرشحة كانت فيها مخلفات اختبارات ⭐ ⇒ ⛔ مستحضر في الحزمة ⭐.

📌 المطلوب من المالك: «إزالة ملفات الاختبارات المؤقتة من الشجرة
   المرشحة» + «منع تكرار إدراجها» ⭐ ⇒ ⭐ الحارس ده بيعمل الاثنين ⭐:
   ① يفشل لو في أي ملف مؤقت متتبَّع في git ⭐
   ② يفشل لو ملفات الـCI ناقصة ⭐ (الجولة ٢١: استرجاعها ⭐)

⛔ مافيش أي تعديل على الكود — فحص فقط ⭐
شغّله:  python3 test_tree_hygiene.py
"""
import io
import os
import re
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE  # ⭐ الملف في جذر المستودع ⭐

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def git(*args):
    try:
        return subprocess.run(["git", "-C", ROOT] + list(args),
                              capture_output=True, text=True,
                              timeout=120).stdout
    except Exception:
        return ""


print("\n" + "=" * 66)
print("  🛡️ حارس نظافة الشجرة المرشحة — الجولة ٢١")
print("=" * 66)

# ── ① مافيش ملف اختبار مؤقت متتبَّع في git ⭐
tracked = [p for p in git("ls-files").split("\n") if p.strip()]
TEMP_PAT = re.compile(
    r"(^|/)(\.[^/]*tmp[^/]*/|[^/]*_tmp_[^/]*|[^/]*\.probe_[^/]*)$"
    r"|(^|/)\.r\d+_.*tmp")
temp_hits = [p for p in tracked if TEMP_PAT.search(p)]
ok(not temp_hits,
   "① مافيش ملف/مجلد اختبار مؤقت متتبَّع في git",
   "%d ملف: %s" % (len(temp_hits), temp_hits[:5]))

# ⛔ المخرجات المولّدة ما تكونش متتبَّعة ⭐
GEN = ["engine_audit_result.json", "acceptance_center_r20.json",
       "acceptance_center_r21.json", "git_pii_scan_result.json"]
gen_hits = [p for p in tracked if os.path.basename(p) in GEN]
ok(not gen_hits, "② مافيش مخرجات مولّدة متتبَّعة", gen_hits[:5])

# ── ③ ملفات الـCI موجودة ومتتبَّعة ⭐ (الجولة ٢١: استرجاعها ⭐)
ci = ".github/workflows/ci.yml"
ok(ci in tracked, "③ ملف CI للباك موجود ومتتبَّع", ci)
ci_src = os.path.join(ROOT, ".github", "workflows", "ci.yml")
if os.path.isfile(ci_src):
    txt = io.open(ci_src, encoding="utf-8").read()
    ok("node --test" in txt or "python" in txt,
       "④ ملف الـCI بيشغّل الاختبارات الحقيقية ⭐")
    ok("jobs:" in txt and ("steps:" in txt), "⑤ ملف الـCI فيه بنية workflow")
else:
    ok(False, "③ ملف CI للباك موجود على القرص")

# ── ⑥ .gitignore ما يستثنيش مجلد workflows ⭐ (استثناء غير مبرر ⭐)
gi = io.open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
bad_ignore = [ln.strip() for ln in gi.split("\n")
              if ln.strip().startswith(".github/workflows")]
ok(not bad_ignore,
   "⑥ .gitignore ما فيهوش استثناء لمجلد workflows ⭐",
   bad_ignore)
# ⭐ وقواعد منع تكرار الإدراج موجودة ⭐
ok(".r17_p3_tmp_*/" in gi,
   "⑦ قاعدة منع تكرار إدراج المجلدات المؤقتة موجودة ⭐")

# ── ⑧ الملفات الاختبارية الحقيقية موجودة ⭐ (البراهين لازم تفضل ⭐)
need = ["test_r20_az31_36.py", "test_pin_auth.py", "test_code_hygiene.py",
        "test_security_batch02.py"]
missing = [t for t in need if t not in tracked]
ok(not missing, "⑧ ملفات الاختبار الحقيقية لسه متتبَّعة ⭐", missing)

# ── ⑨ الأدوات الجديدة متتبَّعة ⭐
need_tools = ["tools/engine_audit.py", "tools/acceptance_center.py",
              "tools/git_pii_scan.py"]
miss_t = [t for t in need_tools if t not in tracked]
ok(not miss_t, "⑨ أدوات الجولة ٢٠ متتبَّعة ⭐", miss_t)

print("\n" + "=" * 66)
passed = sum(1 for c, _ in RESULTS if c)
total = len(RESULTS)
print("  النتيجة: %d/%d" % (passed, total))
print("=" * 66)
for c, label in RESULTS:
    if not c:
        print("  ❌ فشل: " + label)
sys.exit(0 if passed == total else 1)
