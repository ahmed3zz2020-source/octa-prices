#!/usr/bin/env bash
# ⭐⭐⭐ (R32) ⭐⭐⭐ حارس بصمة أدوات القياس ⭐⭐⭐
# 📌 الغرض ⭐: ⛔ إثبات ⭐ أن البصمة المثبّتة في ملف الـworkflow ⭐ (OCTA_CI_TOOLS_SHA256 ⭐)
#    ⭐ **نفسها** ⭐ ⭐ ⭐ البصمة ⭐ ⭐ ⭐ اللي الـCI ⭐ ⭐ ⭐ هيحسبها ⭐ ⭐ ⭐ فعلياً ⭐ ⭐ ⭐.
# ⛔ سبب وجوده ⭐: ⭐ في R32 ⭐ ⭐ ⭐ كانت البصمة ⭐ ⭐ ⭐ محسوبة بطريقة ⭐ ⭐ ⭐ (بايثون ⭐ ⭐ ⭐)
#    ⭐ ⭐ ⭐ والـCI ⭐ ⭐ ⭐ بيحسبها بطريقة ⭐ ⭐ ⭐ (شل ⭐ ⭐ ⭐) ⭐ ⭐ ⭐ ⇒ ⛔ البوابة ⭐ ⭐ ⭐
#    ⭐ ⭐ ⭐ كانت هتفشل ⭐ ⭐ ⭐ عند أول تشغيل ⭐ ⭐ ⭐ ⇒ ⛔ «نسخة CI جاهزة» ⭐ ⭐ ⭐ كانت كاذبة ⭐.
#
# ── التشغيل ───────────────────────────────────────────────────────────────
#   bash ci-workflow/ci_digest_check.sh <جذر المستودع> <ملف الـworkflow>
#   مثال: bash ci-workflow/ci_digest_check.sh . ci-workflow/octa-ci.yml
#
# ⛔ مافيش شبكة ⭐ ⭐ ⭐ ⛔ مافيش أسرار ⭐ ⭐ ⭐ ⛔ مافيش تعديل على الملفات ⭐ ⭐ ⭐
# ───────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="${1:-.}"
WF="${2:-}"

if [ -z "$WF" ]; then
  echo "FAIL: لازم تحدد ملف الـworkflow ⭐"
  exit 2
fi
if [ ! -f "$WF" ]; then
  echo "FAIL: ملف الـworkflow مش موجود ⭐ ($WF ⭐)"
  exit 2
fi

PIN="$(grep -oE "OCTA_CI_TOOLS_SHA256: '[0-9a-f]{64}'" "$WF" | head -1 | grep -oE "[0-9a-f]{64}" || true)"
if [ -z "$PIN" ]; then
  echo "FAIL: ملف الـworkflow ⭐ مافيشش OCTA_CI_TOOLS_SHA256 ⭐"
  exit 1
fi

LIST="$(grep -oE 'for f in [^;]+;' "$WF" | head -1 | sed 's/^for f in //; s/;[[:space:]]*$//')"
if [ -z "$LIST" ]; then
  echo "FAIL: ملف الـworkflow ⭐ مافيشش سطر حساب البصمة ⭐"
  exit 1
fi

cd "$ROOT"

MISSING=""
for f in $LIST; do
  [ -f "$f" ] || MISSING="$MISSING $f"
done
if [ -n "$MISSING" ]; then
  echo "FAIL: أدوات القياس ناقصة ⭐ ⇒$MISSING ⭐"
  exit 1
fi

# ⭐ نفس سطر الـCI ⭐ حرفياً ⭐ ⇒ نفس القيمة ⭐
DIGEST="$(for f in $LIST; do printf '%s ' "$f"; sha256sum "$f" | cut -d' ' -f1; done | sha256sum | cut -d' ' -f1)"

echo "tools_count=$(echo $LIST | wc -w)"
echo "computed=$DIGEST"
echo "pinned  =$PIN"

if [ "$DIGEST" != "$PIN" ]; then
  echo "FAIL: بصمة أدوات القياس المثبّتة ⭐ ⭐ ⭐ لا تطابق ⭐ ⭐ ⭐ المحسوبة ⭐ ⭐ ⭐"
  exit 1
fi
echo "PASS: بصمة أدوات القياس مطابقة ⭐ ($DIGEST ⭐)"
exit 0
