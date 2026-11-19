#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ حارس نظافة الكود — ملفات الدفعة الأمنية (١٥ نوفمبر ٢٠٢٦)

🎯 السبب: اكتُشف في المراجعة شظايا حروف صينية/كورية/يابانية متلخطة
   جوّه تعليقات عربية في ملفات الدفعة (مش بتكسر الكود، بس الكود شكله غريب
   وفيه كلمات عربية معطوبة).

📌 النطاق: **ملفات الدفعة الأمنية بس** — مش كل الريبو.
   (فيه شظايا أقدم في ملفات تانية ⇒ بتتReport في جدول المشاكل المفتوحة
    بدل ما نكسر الـCI على نطاق أوسع.)

الفحوصات:
   ① مافيش حروف CJK في ملفات الدفعة
   ② مافيش أسماء أدوات ذكاء اصطناعي في الكود
   ③ مافيش نقطة-نقطة-نقطة برّه التعليقات (قاعدة الـCI)
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "update_prices.py",
    "opp_engine.py",
    "test_security_batch01.py",
    "test_security_batch02.py",
    "test_security_p0.py",
    "test_security_bgstore.py",
    "test_pin_auth.py",
    "test_opp_freshness13.py",
    "test_round14_release.py",
    "_stub_env.py",
    "tools/staging/run_staging.py",
    "tools/staging/run_all.sh",
    "staging_probe.py",
    "doc/GITHUB-DATA-CONTAINMENT.md",
    "docs/WEBAUTHN-DESIGN.md",
    "docs/WEBAUTHN-DESIGN.md",
    "docs/REVIEW-LOG.md",
]

# ⛔ النمط مكتوب كرموز سداسية عشان الـguard نفسه مايفحصش نفسه
CJK = re.compile("[" + "".join([
    "\\u3040-\\u30FF", "\\u3400-\\u4DBF", "\\u4E00-\\u9FFF",
    "\\uAC00-\\uD7AF", "\\uFF01-\\uFF60", "\\uFFE0-\\uFFE6",
]) + "]")

# ⛔ نفس القاعدة: ما بنكتبش أسماء الأدوات في الكود
TOOL_NAMES = ["Mini" + "Max", "Chat" + "GPT", "Claude", "Copilot", "Gemini"]

DOTS = "." * 3

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def strip_comments(text):
    """يشيل تعليقات Python و shell ⇒ عشان نفحص الكود بس"""
    out = []
    in_s = None
    for line in text.splitlines():
        stripped = line
        if in_s:
            end = line.find(in_s)
            if end == -1:
                continue
            stripped = line[end + len(in_s):]
            in_s = None
        for q in ('"""', "'''"):
            if q in stripped:
                pre, rest = stripped.split(q, 1)
                if rest.find(q) == -1:
                    in_s = q
                stripped = pre
                break
        if "#" in stripped:
            stripped = stripped.split("#", 1)[0]
        out.append(stripped)
    return "\n".join(out)


print("🛡️ حارس نظافة الكود — ملفات الدفعة الأمنية")
print("=" * 62)

# ---- ① CJK ----------------------------------------------------------------
bad = []
for rel in sorted(set(FILES)):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    for i, line in enumerate(text.splitlines(), 1):
        if CJK.search(line):
            bad.append("%s:%d" % (rel, i))
ok(not bad, "مافيش حروف صينية/كورية/يابانية في ملفات الدفعة", bad[:6])

# ---- الأسطر المضافة في الدفعة (git diff) ---------------------------------
def added_lines(base="main"):
    """الأسطر اللي الدفعة أضافتها بالظبط (مش الكود القديم)"""
    import subprocess
    out = subprocess.run(["git", "diff", "-U0", base + "..HEAD"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    added = []
    cur = ""
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append((cur, line[1:]))
    return added


ADDED = added_lines()

# ---- ② أسماء الأدوات (في الأسطر المضافة فقط) ------------------------------
hits = []
GUARD_SELF = "test_code_hygiene.py"
for fname, line in ADDED:
    if fname.endswith(GUARD_SELF):
        continue
    for name in TOOL_NAMES:
        if name in line:
            hits.append("%s :: %s" % (fname, name))
ok(not hits, "مافيش اسم أداة ذكاء اصطناعي في أسطر الدفعة المضافة", hits[:6])

# ---- ③ النقاط الثلاث (قاعدة الـCI) — في الأسطر المضافة -------------------
bad3 = []
for fname, line in ADDED:
    if fname.endswith(".md"):
        continue
    code = strip_comments(line)
    if DOTS in code:
        bad3.append("%s :: %s" % (fname, code.strip()[:60]))
ok(not bad3, "مافيش ثلاث نقاط برّه التعليقات في أسطر الدفعة (قاعدة الـCI)", bad3[:6])

# ---- ④ محارف تالفة (U+FFFD) — نص عربي معطوب ⬇️ ⬇️ ⬇️
bad4 = []
for rel in sorted(set(FILES)):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    for i, line in enumerate(text.splitlines(), 1):
        if "\ufffd" in line:
            bad4.append("%s:%d" % (rel, i))
ok(not bad4, "مافيش محارف تالفة (U+FFFD) في ملفات الدفعة", bad4[:6])

# ---- ④ب حروف سيلانية متلخطة جوّه نص عربي (الجولة ١٤) ⬇️ ⬇️ ⬇️
# ⛔ اكتُشف في الجولة ١٤: كلمات سيلانية («U+0432 U+0441 U+0451» · «U+0432 U+043D U+0443 U+0442 U+0440 U+0438») جوه تعليقات
#    عربية ⇒ بتظهر سليمة بالعين ومختبّرة بالأدوات.
CYR = re.compile("[" + "".join([
    "\\u0400-\\u04FF", "\\u0500-\\u052F",
]) + "]")
bad5 = []
for rel in sorted(set(FILES)):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    for i, line in enumerate(text.splitlines(), 1):
        if CYR.search(line):
            bad5.append("%s:%d" % (rel, i))
ok(not bad5, "مافيش حروف سيلانية متلخطة في ملفات الدفعة", bad5[:6])

# ---- ⑤ الملفات موجودة فعلاً ------------------------------------------------
missing = [f for f in sorted(set(FILES)) if not os.path.exists(os.path.join(ROOT, f))]
ok(not missing, "كل ملفات الدفعة موجودة", missing)

# ---- ⑥ فحص الشجرة كاملة (الجولة ٢٦) --------------------------------------
# ⛔ الدرس: التلوّث النصي كان موجوداً في ٢٨ ملفاً خارج نطاق «ملفات الدفعة»
#    ⇒ الفحص لازم يغطّي الشجرة كلها، مش بس الملفات اللي الدفعة لمستها.
# ⛔ النمط مكتوب كرموز سداسية عشان الـguard نفسه مايفحصش نفسه.
TREE_PATTERN = re.compile("[" + "".join([
    "\\uFFFD",            # محرف بديل (نص مخروم)
    "\\u3040-\\u30FF",    # كاكا/كانا
    "\\u3400-\\u4DBF",    # صيني (توسيع)
    "\\u4E00-\\u9FFF",    # صيني
    "\\uAC00-\\uD7AF",    # كوري
    "\\uFF01-\\uFF60",    # fullwidth
    "\\uFFE0-\\uFFE6",
    "\\u3000-\\u302F",    # ترقيم CJK (أقواس وعلامات صينية)
    "\\u3031-\\u303F",
    "\\u0400-\\u052F",    # سيلاني
]) + "]")

TREE_SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__",
                  ".venv", "venv", ".pytest_cache", ".mypy_cache", "coverage"}

# استثناءات موثّقة (باك) — فاضية دلوقتي: مفيش محرف أجنبي مقصود في الباك
TREE_ALLOW = {}


def tracked_files():
    """قائمة الملفات المتتبَّعة (git) — fallback للمشي على الشجرة"""
    import subprocess
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                             capture_output=True, text=True, timeout=120).stdout
        if out.strip():
            return [l for l in out.splitlines() if l.strip()]
    except Exception:
        pass
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in TREE_SKIP_DIRS]
        for fn in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    return found


def is_binary(path):
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(4096)
    except Exception:
        return True


tree_bad = []
tree_count = 0
for rel in tracked_files():
    if rel in TREE_ALLOW:
        continue
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p) or is_binary(p):
        continue
    try:
        text = io.open(p, "r", encoding="utf-8").read()
    except Exception:
        continue
    tree_count += 1
    for i, line in enumerate(text.splitlines(), 1):
        m = TREE_PATTERN.search(line)
        if m:
            tree_bad.append("%s:%d (%r)" % (rel, i, m.group(0)))
ok(not tree_bad, "مافيش تلوّث نصي في الشجرة كاملة (%d ملف متتبَّع)" % tree_count,
   tree_bad[:8])

passed = sum(1 for r in RESULTS if r[0])
failed = len(RESULTS) - passed
print("=" * 62)
print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)" % (passed, failed, len(RESULTS)))
sys.exit(1 if failed else 0)
