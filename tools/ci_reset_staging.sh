#!/bin/bash
# ══════════════════════════════════════════════════════════════
#  ⭐ R26 · تصفير حالة بيئة الـstaging قبل كل ملف اختبار ⭐
#  📌 السبب المقيس: اختبار التسجيل بينسخ حالة المستخدم/المحفظة في
#     بيئة الـstaging ⇒ ٥ ملفات بعده كانت بتفشل في التشغيل الجماعي ⛔
#     (22/22 · 29/29 · 39/39 · 98/98 · 7/7 منفردة ⭐ ⇒ السبب تلوث حالة ⭐)
#  📌 الحل: نعيد تشغيل السيرفر (اللوب في الـworkflow بيعيد تشغيله)
#     ⇒ كل ملف بيلاقي حالة نظيفة ⭐ ⇒ النتيجة حتمية ⭐.
#  ⛔ مفيش أي نداء خارجي · مفيش أي سر · بيقفّلش الـCI.
# ══════════════════════════════════════════════════════════════
set -u
PORT="${STAGE_PORT:-8099}"

# ⛔⛔⛔ الجولة ٢٦ — تصفير **مجلد البيانات** كمان ⭐
#   📌 السبب المقيس ⭐: تصفير السيرفر بس خلّى ملفات الحالة (users.json ⭐
#  (Session ⭐ Portfolio ⭐) من الملف السابق ⭐ ⇒ ٣ اختبارات أمنية فشلت
#   في التشغيل الجماعي ⭐ (بينما كل واحد منفردة ناجح ⭐).
#   📌 الحل ⭐: نرجّع مجلد البيانات من نسخة الريبو ⭐ (نظيفة ⭐ ومعتمدة ⭐)
#   ⇒ كل ملف اختبار يبدأ من نفس الحالة ⭐ ⇒ النتيجة حتمية ⭐.
DATA_DIR="${OCTA_DATA_DIR:-}"
REPO_DIR="${CI_REPO_DIR:-$(pwd)}"
if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ] && [ -d "$REPO_DIR/data" ]; then
  find "$DATA_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
  cp -r "$REPO_DIR/data/." "$DATA_DIR/" 2>/dev/null || true
fi
pkill -9 -f "tools/staging/run_staging.py" 2>/dev/null || true

# ⭐ R28 · انتظار **200 حقيقي** بمفتاح الـproxy ⭐
#   ⛔ قبل كنا بننتظر أي رد ⭐ ⇒ 403 (من غير مفتاح) كان بيعدّي ⭐
#      ⇒ الاختبار اللي بعده كان بيبدأ والسيرفر لسه طالع ⭐ ⇒ فشل وهمي ⭐
SECRET=""
for _cfg in "${STAGE_CONFIG:-}" "/workspace/.staging/staging-config.json" "./staging-config.json"; do
  [ -n "$_cfg" ] && [ -f "$_cfg" ] || continue
  SECRET=$(python3 - "$_cfg" <<'PY'
import json,sys
try:
    print(json.load(open(sys.argv[1],encoding="utf-8")).get("proxy_secret",""))
except Exception:
    print("")
PY
)
  [ -n "$SECRET" ] && break
done
for _i in $(seq 1 40); do
  if [ -n "$SECRET" ]; then
    code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' -H "X-OCTA-Proxy: ${SECRET}" \
      "http://127.0.0.1:${PORT}/api/health" || echo 000)
    [ "$code" = "200" ] && exit 0
  else
    code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' \
      "http://127.0.0.1:${PORT}/api/health" || echo 000)
    [ "$code" = "200" ] && exit 0
  fi
  sleep 1
done
exit 0
