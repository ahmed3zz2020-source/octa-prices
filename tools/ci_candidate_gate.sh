#!/usr/bin/env bash
# 🔒 بوابة بصمة المرشح — الجولة ٢٦ (R26 · مرحلة الـCI)
#
# 📌 الغرض:
#    كل نتيجة في الـCI لازم تكون مربوطة ببصمة المرشح ⭐
#    ⇒ الـSHA اللي اتختبَر لازم يكون **من عائلة المرشح** ⭐
#    ⇒ (هو سلف أو نسل لـOCTA_CANDIDATE_SHA ⭐)
#
# 📌 الفحوصات (كلها ببوابة صارمة ⭐):
#    ① المتغيّر OCTA_CANDIDATE_SHA لازم يكون موجود ⭐
#    ② الـSHA الفعلي (git rev-parse HEAD) لازم يكون من عائلة المرشح ⭐
#       (git merge-base --is-ancestor ⭐)
#    ③ الفرق بين المرشح والـSHA المختبَر لازم يكون **ملفات الـCI بس** ⭐
#       (أي ملف تاني اتغيّر ⇒ النتيجة مش بتتقرأ ⭐)
#
# ⛔ مفيش أي سر · مفيش أي نشر · مفيش أي دفع.
#
# 📌 التشغيل:
#    OCTA_CANDIDATE_SHA=<sha> bash tools/ci_candidate_gate.sh
set -euo pipefail

CANDIDATE="${OCTA_CANDIDATE_SHA:-}"
if [ -z "$CANDIDATE" ]; then
  echo "⛔ متغيّر OCTA_CANDIDATE_SHA مش موجود — مفيش بصمة مرشح"
  exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "⛔ المجلد ده مش مستودع git"
  exit 1
fi

ACTUAL="$(git rev-parse HEAD)"
echo "🔒 بصمة المرشح : $CANDIDATE"
echo "🔒 الـSHA المختبَر: $ACTUAL"

# ── ② هل الـSHA من عائلة المرشح؟ ─────────────────────────
if ! git cat-file -e "${CANDIDATE}^{commit}" 2>/dev/null; then
  echo "⛔ بصمة المرشح مش موجودة في التاريخ (clone ناقص؟)"
  exit 1
fi
if ! git merge-base --is-ancestor "$CANDIDATE" "$ACTUAL"; then
  echo "⛔ الـSHA المختبَر مش من عائلة المرشح — النتيجة ملغاة"
  exit 1
fi
echo "✅ الـSHA المختبَر من عائلة المرشح"

# ── ③ الفرق لازم يكون ملفات الـCI بس ─────────────────────
# ⭐ (R27) ⭐ .gitignore ⭐ داخل النطاق ⭐: ⭐ فرع الـCI بيوسّعه ⭐
#    (بيتجاهل ملفات حالة المستخدمين ⭐ ⇒ ⛔ مافيش تسليم ⭐).
ALLOWED='^(\.github/workflows/|ci-workflow/|tools/ci_|tools/test_ci_|\.gitignore$)'
UNEXPECTED=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if ! printf '%s\n' "$f" | grep -Eq "$ALLOWED"; then
    UNEXPECTED="$UNEXPECTED$f "
  fi
done <<< "$(git diff --name-only "$CANDIDATE" "$ACTUAL")"

if [ -n "$UNEXPECTED" ]; then
  echo "⛔⛔⛔ ملفات خارج نطاق الـCI اتغيّرت عن المرشح ⭐:"
  for f in $UNEXPECTED; do
    echo "   - $f"
  done
  echo "⛔ النتيجة دي مش بتتقرأ — الـjob بيفشل"
  exit 1
fi
echo "✅ الشجرة المختبَرة = المرشح + ملفات الـCI بس"
