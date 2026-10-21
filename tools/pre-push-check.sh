#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
# 🔬 حارس ما قبل الـpush — ٢١ أكتوبر ٢٠٢٦
# ══════════════════════════════════════════════════════════════
# ⛔ ليش ده وُجد؟
#   commit 8254bf2 حط @_require_user على /api/stocks و /api/markets
#   بدون ما يعرّف الاسم. بايثون raise NameError وقت الإقلاع
#   → gunicorn مش بيقوم → Railway 502 على كل endpoint لمدة ٧ ساعات.
#
#   ⛌ ⛌ الـCI كان بيمرّ! لأن CI بيفحص الـsyntax بس (py_compile)
#   ⛌ ⛌ والـsyntax فعلاً سليم — الـNameError بيحصل وقت التشغيل
#   ⛌ ⛌ وقت الـimport، مش وقت الـparse.
#
# ✅ الحل: قبل أي push — نعمل AST scan على كل الديكوريتورات
#   المستخدمة في الملف ونتأكد إنها كلها متعرّفة قبل الاستخدام.
#
# 📌 الاستعمال:  bash tools/pre-push-check.sh
# 📌 أو:         أضفه كـpre-push hook
# ══════════════════════════════════════════════════════════════

set -u
cd "$(dirname "$0")/.." || exit 2

echo "🔬 حارس ما قبل الـpush — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "══════════════════════════════════════════════════════"

python3 - <<'PYEOF'
import ast
import builtins
import sys

PATH = "update_prices.py"
problems = []

try:
    src = open(PATH, encoding="utf-8").read()
except FileNotFoundError:
    print("❌ مفيش update_prices.py — غلط مسار")
    sys.exit(2)

# ١ — الـsyntax
try:
    tree = ast.parse(src)
except SyntaxError as e:
    print(f"❌ SyntaxError سطر {e.lineno}: {e.msg}")
    sys.exit(1)
print("✅ ١/٣  الـsyntax سليم")

# ٢ — كل الأسماء المعرّفة
defined = set(dir(builtins))
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined.add(node.name)
    elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        defined.add(node.id)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for al in node.names:
            defined.add((al.asname or al.name).split(".")[0])
    elif isinstance(node, ast.arg):
        defined.add(node.arg)
    elif isinstance(node, ast.ExceptHandler) and node.name:
        defined.add(node.name)
    elif isinstance(node, (ast.Global, ast.Nonlocal)):
        defined.update(node.names)

# ٣ — الديكوريتورات: مستخدمة؟ معرّفة؟ وبعدين سطر التعريف؟
def_lines = {}
use_lines = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name.startswith("_") and node.name.endswith(("_user", "_auth", "_login")):
            def_lines[node.name] = node.lineno
        for d in node.decorator_list:
            names = []
            if isinstance(d, ast.Name):
                names = [d.id]
            elif isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
                names = [d.func.id]
            for n in names:
                if n.startswith("_") and n not in defined:
                    problems.append(f"NameError: @{n} على {node.name}() سطر {node.lineno} — الاسم مش معرّف")
                elif n in def_lines and node.lineno < def_lines[n]:
                    problems.append(
                        f"ترتيب غلط: {node.name}() سطر {node.lineno} يستعمل "
                        f"@{n} معرّف في سطر {def_lines[n]} (لازم يكون قبله)"
                    )
                elif n.startswith("_"):
                    use_lines.append((n, node.name, node.lineno))

# ٤ — أي اسم يبدأ بـ_ مستخدم كـfunction call بس مش معرّف
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        n = node.func.id
        if n.startswith("_") and n not in defined and n not in ("_json",):
            problems.append(f"NameError: استدعاء {n}() سطر {node.lineno} — مش معرّف")

if problems:
    print("\n❌ مشاكل تمنع النشر:")
    for p in problems:
        print("   •", p)
    print("\n⛔ متعملش push. صلّح الأول.")
    sys.exit(1)

print("✅ ٢/٣  مافيش اسم غير معرّف")
print("✅ ٣/٣  كل الديكوريتورات معرّفة قبل الاستخدام")
if use_lines:
    print(f"ℹ️  {len(use_lines)} ديكوريتور حماية مستخدم (كلهم آمنين):")
    for n, fn, ln in use_lines:
        print(f"      @{n} → {fn}() سطر {ln}")
PYEOF
RC=$?

echo "══════════════════════════════════════════════════════"
if [ "$RC" -eq 0 ]; then
  echo "🟢 آمن — ينفع تعمل push"
  exit 0
else
  echo "🔴 متوقف — صلّح الأول"
  exit 1
fi