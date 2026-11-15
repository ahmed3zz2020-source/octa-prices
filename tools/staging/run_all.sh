#!/usr/bin/env bash
# 🚀 تشغيل بيئة Staging معزولة لـOCTA (باك + نفق عام)
# ⛔⛔⛔ مافيش أي اتصال بالإنتاج ⬇️ ⬇️ ⬇️
# 📌 البيانات وهمية · الأسرار متولّدة محلياً · الإيميل Mock
# 📌 الإنتاج ما يتلمسش نهائياً
#
# الاستخدام:
#   bash tools/staging/run_all.sh            # شغّل وطبع الروابط
#   bash tools/staging/run_all.sh --stop     # أوقف كل حاجة
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${STAGE_PORT:-8099}"
PY="${STAGE_PYTHON:-/workspace/.venv-sec/bin/python}"
SECRETS_FILE="/workspace/.staging-secrets.json"

stop() {
  echo "⏹️ إيقاف…"
  for pat in "run_staging.py" "cloudflared tunnel"; do
    for pid in $(ps -eo pid,args | grep -F "$pat" | grep -v grep | awk '{print $1}'); do
      kill "$pid" 2>/dev/null && echo "   ⏹️ $pid ($pat)"
    done
  done
  rm -f /workspace/.staging/tunnel.url
  echo "✅ اتوقف"
}

if [ "${1:-}" = "--stop" ]; then stop; exit 0; fi

# ① السر لازم يكون **ثابت** — نفس اللي مسجّل في Cloudflare
if [ -f "$SECRETS_FILE" ]; then
  PROXY_SECRET="$(jq -r .proxy "$SECRETS_FILE")"
else
  PROXY_SECRET="PRX-$(head -c 24 /dev/urandom | base64 | tr -d '/+=')"
fi
export STAGE_PROXY_SECRET="$PROXY_SECRET"

# ② تشغيل الباك
cd "$ROOT"
if ! curl -s -m 3 -o /dev/null "http://127.0.0.1:$PORT/api/health"; then
  setsid "$PY" tools/staging/run_staging.py > /tmp/staging.log 2>&1 < /dev/null &
  for _ in $(seq 1 30); do
    sleep 1
    curl -s -m 3 -o /dev/null "http://127.0.0.1:$PORT/api/health" && break
  done
fi
if curl -s -m 5 -o /dev/null "http://127.0.0.1:$PORT/api/health"; then
  echo "✅ الباك شغّال على 127.0.0.1:$PORT"
else
  echo "❌ الباك مش رافع — شوف /tmp/staging.log"; exit 1
fi

# ③ النفق العام (لو مش شغّال)
TUN_URL="$(cat /workspace/.staging/tunnel.url 2>/dev/null || true)"
if [ -z "$TUN_URL" ] || ! curl -s -m 6 -o /dev/null "$TUN_URL/api/health"; then
  echo "⏳ فتح النفق…"
  setsid cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate \
    > /tmp/tunnel.log 2>&1 < /dev/null &
  TUN_URL=""
  for _ in $(seq 1 40); do
    sleep 1
    TUN_URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/tunnel.log 2>/dev/null | head -1)"
    [ -n "$TUN_URL" ] && break
  done
  [ -n "$TUN_URL" ] && echo "$TUN_URL" > /workspace/.staging/tunnel.url
fi
[ -z "$TUN_URL" ] && { echo "❌ النفق مش رافع — شوف /tmp/tunnel.log"; exit 1; }
echo "✅ النفق: $TUN_URL"

# ④ ربط عامل المعاينة (بس — الإنتاج ما يتلمسش)
if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  ACC="${CF_ACCOUNT_ID:-74e046678adabf0706024b97b205882b}"
  for pair in "OCTA_API_URL:$TUN_URL" "OCTA_PROXY_SECRET:$PROXY_SECRET" "OCTA_API_DIRECT:$TUN_URL"; do
    NAME="${pair%%:*}"; VAL="${pair#*:}"
    curl -s -m 20 -X PUT \
      "https://api.cloudflare.com/client/v4/accounts/$ACC/workers/scripts/octa-preview/secrets" \
      -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
      -d "{\"name\":\"$NAME\",\"text\":\"$VAL\",\"type\":\"secret_text\"}" \
      | jq -r 'if .success then "   ✅ " + "'"$NAME"'" else "   ⚠️ " + "'"$NAME"'" + ": " + ((.errors[0].message // "")[0:120]) end'
  done
  echo "✅ أسرار المعاينة اتحدّثت (octic-preview فقط)"
else
  echo "⚠️ مافيش CLOUDFLARE_API_TOKEN ⇒ الربط اتعمل يدوي"
fi

echo ""
echo "════════════════════════════════════════════════"
echo "  🧪 Staging URL : $TUN_URL"
echo "  🔑 Proxy Secret: $PROXY_SECRET"
echo "  👤 Free: staging.free@example.test / PIN 1111"
echo "  👤 Pro : staging.pro@example.test  / PIN 2222"
echo "  📦 الحسابات في: /workspace/.staging/staging-config.json"
echo "  ⛔ الإنتاج ما اتلمسش"
echo "════════════════════════════════════════════════"
