#!/usr/bin/env bash
# 🛡️ OCTA — الجولة ٢٤ (R24) — تشغيل معاينة الـDurable Object المعزولة ⭐
#
# ⛔ ممنوع ⭐: نشر ⭐ · أي مورد سحابي ⭐ · أي مورد مدفوع ⭐.
# ✅ كله محلي ⭐ (wrangler 3.114.14 ⭐ + workerd ⭐) ⭐ والتكلفة ٠$ ⭐.
#
# 📌 الخطوات ⭐:
#   ① phase1 ⭐ — كسر كتابة التخزين ⭐ (عطل مدروس ⭐) ⭐ ⇒ لازم يطلع ٥٠٣ ⭐
#      (ممنوع نجاح وهمي ⭐) ⭐.
#   ② phase2 ⭐ — التشغيل السليم ⭐ ⇒ إبطال فوري ⭐ + ٢٥ طلب متوازي ⭐.
#   ③ phase3 ⭐ — إعادة تشغيل المشغّل ⭐ ⇒ المصدر القوي صامد ⭐.
#
# 📌 النتيجة ⭐: /workspace/output/OCTA-ROUND24-EVIDENCE/do-preview/results/ ⭐
set -u
PREVIEW="/workspace/output/OCTA-ROUND24-EVIDENCE/do-preview"
EVIDENCE="/workspace/output/OCTA-ROUND24-EVIDENCE/evidence"

if [ ! -d "$PREVIEW/node_modules" ]; then
  echo "PREVIEW_DEPS_MISSING: cd $PREVIEW && npm install --no-audit --no-fund"
  exit 2
fi

bash "$PREVIEW/run-preview.sh"
RC=$?

echo ""
echo "=== rebuilding the evidence files ⭐ ==="
HERE="$(cd "$(dirname "$0")" && pwd)"
/tmp/ci_r23_venv/bin/python "$HERE/r24_evidence.py" || \
  python3 "$HERE/r24_evidence.py"

echo "PREVIEW_RC=$RC"
exit $RC
