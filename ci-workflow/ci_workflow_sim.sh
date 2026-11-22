#!/usr/bin/env bash
# ⭐⭐⭐ (R32) ⭐⭐⭐ محاكاة **كاملة** ⭐ ⭐ ⭐ لجولة الـCI ⭐ ⭐ ⭐ (تسلسل GitHub Actions ⭐ ⭐ ⭐)
# 📌 الغرض ⭐: ⛔ إثبات ⭐ ⭐ ⭐ أن الـworkflow ⭐ ⭐ ⭐ **يشتغل** ⭐ ⭐ ⭐
#    ⭐ ⭐ ⭐ (fetch ⭐ ⭐ ⭐ + checkout ⭐ ⭐ ⭐ + بوابة البصمة ⭐ ⭐ ⭐) ⭐ ⭐ ⭐
#    ⭐ ⭐ ⭐ على نسخ نظيفة ⭐ ⭐ ⭐ من الفرعين ⭐ ⭐ ⭐ البعيدين ⭐ ⭐ ⭐.
# ⛔ مبني على نفس الأوامر ⭐ ⭐ ⭐ اللي في ملف الـworkflow ⭐ ⭐ ⭐ حرفياً ⭐ ⭐ ⭐.
#
# ── الاستخدام ─────────────────────────────────────────────────────────────
#   bash tools/ci_workflow_sim.sh be <repo> <ci_ref> <candidate_sha> <workflow_file>
#   bash tools/ci_workflow_sim.sh fe <repo> <ci_ref> <candidate_sha> <workflow_file>
# ───────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODE="${1:-}"
REPO="${2:-}"
CI_REF="${3:-}"
CAND_SHA="${4:-}"
WF="${5:-}"

if [ -z "$MODE" ] || [ -z "$REPO" ] || [ -z "$CI_REF" ] || [ -z "$CAND_SHA" ] || [ -z "$WF" ]; then
  echo "usage: $0 <be|fe> <repo-url> <ci_ref> <candidate_sha> <workflow_file>"
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "▶ محاكاة ($MODE) ⭐ ⇒ $REPO ⭐"
echo "  ci_ref=$CI_REF  candidate=$CAND_SHA  workflow=$WF"

echo "▶ ① checkout المرشّح (actions/checkout@v4 ⇒ fetch-depth: 0 ⭐)"
git clone --quiet "$REPO" "$WORK/repo"
git -C "$WORK/repo" fetch --quiet --tags origin
git -C "$WORK/repo" checkout --quiet "$CAND_SHA"
echo "  HEAD = $(git -C "$WORK/repo" rev-parse HEAD)"

echo "▶ ② استرجاع أدوات الـCI من فرع الـCI (نفس تسلسل الـworkflow ⭐)"
git -C "$WORK/repo" fetch --no-tags --depth=1 origin "$CI_REF"
if [ "$MODE" = "fe" ]; then
  git -C "$WORK/repo" checkout FETCH_HEAD -- \
    tools/ci_isolated_tests.json \
    tools/ci_result_classifier.py \
    tools/ci_workflow_lint.py \
    tools/test_ci_alt_gates.py \
    tools/test_ci_gates.py \
    tools/test_ci_result_classifier.py
else
  git -C "$WORK/repo" checkout FETCH_HEAD -- \
    tools/ci_candidate_gate.sh \
    tools/ci_isolated_tests.json \
    tools/ci_reset_staging.sh \
    tools/ci_result_classifier.py \
    tools/ci_workflow_lint.py \
    tools/test_ci_alt_gates.py \
    tools/test_ci_gates.py \
    tools/test_ci_result_classifier.py \
    tools/test_cross_repo_contract.py
fi
echo "  ✅ الأدوات اترجعت"

echo "▶ ③ بوابة بصمة المرشّح (مطابقة بالضبط ⭐)"
ACTUAL="$(git -C "$WORK/repo" rev-parse HEAD)"
if [ "$ACTUAL" != "$CAND_SHA" ]; then
  echo "  FAIL: الـSHA المختبَر ($ACTUAL ⭐ ≠ ⭐ $CAND_SHA ⭐)"
  exit 1
fi
echo "  ✅ PASS: الـSHA المختبَر = المرشّح بالضبط ⭐"

echo "▶ ④ بوابة بصمة أدوات القياس (نفس سطر الـworkflow ⭐)"
WF_IN_REPO="$(git -C "$WORK/repo" show FETCH_HEAD:$WF 2>/dev/null || true)"
if [ -z "$WF_IN_REPO" ]; then
  echo "  FAIL: ملف الـworkflow مش موجود في فرع الـCI ⭐ ($WF ⭐)"
  exit 1
fi
mkdir -p "$WORK/repo/$(dirname "$WF")"
git -C "$WORK/repo" show FETCH_HEAD:$WF > "$WORK/repo/$WF"
PIN="$(grep -oE "OCTA_CI_TOOLS_SHA256: '[0-9a-f]{64}'" "$WORK/repo/$WF" | head -1 | grep -oE "[0-9a-f]{64}")"
LIST="$(grep -oE 'for f in [^;]+;' "$WORK/repo/$WF" | head -1 | sed 's/^for f in //; s/;[[:space:]]*$//')"
cd "$WORK/repo"
DIGEST="$(for f in $LIST; do printf '%s ' "$f"; sha256sum "$f" | cut -d' ' -f1; done | sha256sum | cut -d' ' -f1)"
echo "  computed=$DIGEST"
echo "  pinned  =$PIN"
if [ "$DIGEST" != "$PIN" ]; then
  echo "  FAIL: البصمة المثبّتة ⭐ ⭐ ⭐ لا تطابق ⭐ ⭐ ⭐ المحسوبة ⭐ ⭐ ⭐"
  exit 1
fi
echo "  ✅ PASS: بصمة أدوات القياس مطابقة ⭐"

echo "▶ ⑤ حارس بوّابات الـCI على ملف الـworkflow الحقيقي ⭐"
python3 "$WORK/repo/tools/test_ci_gates.py" "$WORK/repo/$WF" | tail -4

echo ""
echo "✅ SIM PASS ($MODE) ⭐"
exit 0
