import json, time, requests, os, threading
from flask import Flask, jsonify, request
from pathlib import Path
from datetime import datetime

app = Flask(__name__)


# ============ CORS (ضروري للمتصفح) ============
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/<path:any>", methods=["OPTIONS"])
@app.route("/", methods=["OPTIONS"])
def preflight(any=""):
    return "", 204
CACHE_FILE = Path("/app/cache.json")
LIVE_DATA = {"lastUpdate": None, "market": "EGX", "status": "open", "ticker": [], "egx30": []}

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-lite-latest"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
AI_CACHE = {}
AI_CACHE_TTL = 3600

SYSTEM_PROMPT = """أنت محرك التحليل المالي OCTA، خبير في البورصة المصرية EGX.

مهمتك: حلل السهم المصري المعطى وقيّمه على 8 محاور.

**المحاور الثمانية (أرقام من 0 لـ 100):**
1. التحليل الفني (chart patterns, momentum, RSI)
2. التحليل الأساسي (P/E, ROE, revenue growth, margins)
3. السيولة (volume, institutional flows, bid/ask spread)
4. الأخبار (recent news sentiment)
5. المعنويات (market sentiment, sector rotation)
6. المخاطر (volatility, beta, country risk)
7. ملاءمة المحفظة (portfolio fit, diversification)
8. التوافق العام (overall score, risk/reward)

**قواعد مهمة:**
- استخدم knowledge بتاعك عن الشركات المصرية
- كن واقعي - لو مش متأكد قول "غير متاح"
- اكتب بالعربية الفصحى المبسطة
- خلي التوصية واضحة: شراء / تجميع / احتفظ / بيع / تجنب

**الصيغة المطلوبة (JSON فقط، بدون أي كلام تاني):**
{
  "code": "COMI",
  "name": "البنك التجاري الدولي",
  "price": 137.20,
  "change": 0.44,
  "axes": {
    "technical": 72,
    "fundamental": 85,
    "liquidity": 90,
    "news": 65,
    "sentiment": 78,
    "risk": 82,
    "portfolio": 75,
    "overall": 80
  },
  "decision": "شراء",
  "confidence": 75,
  "reasons": ["سبب أول", "سبب ثاني", "سبب ثالث"],
  "risk_level": "متوسط",
  "target": 155.00,
  "stop_loss": 130.00
}
"""


def call_gemini(code, name, price=0, change=0):
    if not GEMINI_KEY:
        return {"error": "API key not configured"}
    user_msg = f"حلل السهم المصري '{name}' (الرمز: {code})"
    if price > 0:
        user_msg += f"\nالسعر الحالي: {price} جنيه | التغير: {change:+.2f}%"
    payload = {
        "contents": [{"parts": [{"text": user_msg}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500, "responseMimeType": "application/json"}
    }
    last_err = ""
    for model in GEMINI_MODELS:
        for attempt in range(2):
            try:
                r = requests.post(
                    f"{GEMINI_BASE}/{model}:generateContent",
                    json=payload, timeout=45,
                    headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY}
                )
                if r.status_code == 200:
                    data = r.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    result = json.loads(text)
                    result["model"] = model
                    return result
                last_err = f"{model} → {r.status_code}"
                if r.status_code in (429, 503, 500):
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_err = f"{model} → {str(e)[:100]}"
                time.sleep(2)
    return {"error": last_err or "all models failed"}


EGX = [
    ("COMI", "البنك التجاري الدولي", "بنوك"), ("TMGH", "طلعت مصطفى", "عقارات"),
    ("HRHO", "إي إف جي القابضة", "خدمات مالية"), ("ETEL", "المصرية للاتصالات", "اتصالات"),
    ("EFIH", "إي فاينانس", "تكنولوجيا"), ("FWRY", "فوري", "تكنولوجيا"),
    ("PHDC", "بالم هيلز", "عقارات"), ("SWDY", "السويدي إليكتريك", "صناعة"),
    ("ABUK", "أبو قير للأسمدة", "أسمدة"), ("AMOC", "الإسكندرية للبترول", "بترول"),
    ("ORAS", "أوراسكوم", "استثمار"), ("CCAP", "القلعة القابضة", "استثمار"),
    ("CLHO", "مستشفى كليوباترا", "صحة"), ("JUFO", "جهينة", "أغذية"),
    ("ISPH", "إيبيكو للأدوية", "أدوية"), ("EMFD", "إعمار مصر", "عقارات"),
    ("MNHD", "مصر الجديدة", "عقارات"), ("SKPC", "سيدي كرير", "بتروكيماويات"),
    ("EGCH", "مصر للكيماويات", "بتروكيماويات"), ("MFPC", "مصر لإنتاج الأسمدة", "أسمدة"),
    ("OCDI", "الإسكندرية للحاويات", "نقل"), ("EKHO", "EK القابضة", "صناعة"),
]
EGX_MAP = {c: (n, s) for c, n, s in EGX}

TICKER = [
    ("tk-egx", "EGX30", "EGX:EGX30"), ("tk-gold", "GOLD", "OANDA:XAUUSD"),
    ("tk-oil", "USOIL", "TVC:USOIL"), ("tk-ukoil", "UKOIL", "TVC:UKOIL"),
    ("tk-usd", "USD/EGP", "EGP=X"), ("tk-eur", "EUR/EGP", "EUR=X"),
    ("tk-spx", "S&P 500", "SP:SPX"), ("tk-silver", "SILVER", "OANDA:XAGUSD"),
]


def tv(sym):
    try:
        r = requests.get(f"https://www.tradingview-widget.com/api/v1/quote?symbol={sym}", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            v = r.json().get("v")
            if v and v.get("lp"):
                return float(v["lp"]), float(v.get("ch", 0))
    except Exception as e:
        print(f"TV err {sym}: {e}")
    return None


def get(sym):
    p = tv(sym)
    return p if p else (0.0, 0.0)


def update_loop():
    while True:
        try:
            print("OCTA Update:", datetime.utcnow().isoformat())
            tk = []
            for tid, label, sym in TICKER:
                p, c = get(sym)
                tk.append({"id": tid, "label": label, "value": round(p, 2), "change": round(c, 2), "trend": "up" if c >= 0 else "down", "unit": "EGP" if "EGP" in tid else ""})
                time.sleep(0.4)
            st = []
            for code, name, sec in EGX:
                p, c = get(f"EGX:{code}")
                if p > 0:
                    st.append({"code": code, "name": name, "price": round(p, 2), "change": round(c, 2), "sector": sec})
                time.sleep(0.4)
            LIVE_DATA["lastUpdate"] = datetime.utcnow().isoformat() + "Z"
            LIVE_DATA["ticker"] = tk
            LIVE_DATA["egx30"] = st
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(LIVE_DATA, f, ensure_ascii=False, indent=2)
            except: pass
            print(f"SAVED: {len(tk)} tickers, {len(st)} stocks")
        except Exception as e:
            print(f"Loop err: {e}")
        time.sleep(300)


threading.Thread(target=update_loop, daemon=True).start()


@app.route("/")
def health():
    return jsonify({"status": "ok", "service": "octa-prices", "version": "v3-gemini", "lastUpdate": LIVE_DATA["lastUpdate"], "tickers": len(LIVE_DATA["ticker"]), "stocks": len(LIVE_DATA["egx30"]), "gemini": "configured" if GEMINI_KEY else "NOT configured"})


@app.route("/api/prices")
def prices():
    return jsonify(LIVE_DATA)


@app.route("/api/ticker")
def ticker():
    return jsonify({"ticker": LIVE_DATA["ticker"]})


@app.route("/api/stocks")
def stocks():
    return jsonify({"egx30": LIVE_DATA["egx30"]})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        code = (data.get("code") or "").upper().strip()
        if not code:
            return jsonify({"error": "code is required"}), 400
        if code not in EGX_MAP:
            return jsonify({"error": f"unknown stock: {code}"}), 400
        if code in AI_CACHE:
            age = time.time() - AI_CACHE[code]["ts"]
            if age < AI_CACHE_TTL:
                cached = dict(AI_CACHE[code]["data"])
                cached["cached"] = True
                return jsonify(cached)
        name, sector = EGX_MAP[code]
        price, change = 0, 0
        for s in LIVE_DATA["egx30"]:
            if s["code"] == code:
                price, change = s["price"], s["change"]
                break
        result = call_gemini(code, name, price, change)
        if "error" in result:
            return jsonify(result), 502
        result["sector"] = sector
        result["cached"] = False
        result["ts"] = int(time.time())
        AI_CACHE[code] = {"data": result, "ts": time.time()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        if not GEMINI_KEY:
            return jsonify({"error": "API key not configured"}), 503
        data = request.get_json(force=True, silent=True) or {}
        message = (data.get("message") or "").strip()
        history = data.get("history") or []
        if not message:
            return jsonify({"error": "message is required"}), 400
        chat_prompt = """أنت OCTA، مساعد ذكي متخصص في البورصة المصرية.
أنت بتجيب على أسئلة المستخدم عن الأسهم المصرية، التحليل الفني والأساسي، التوصيات.
خليك واضح ومختصر. لو السؤال مش واضح، اسأل توضيح."""
        parts = []
        for h in history[-6:]:
            role = "user" if h.get("role") == "user" else "model"
            parts.append({"text": h.get("content", "")})
        parts.append({"text": message})
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": chat_prompt}]},
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
        }
        r = None
        for model in GEMINI_MODELS:
            try:
                r = requests.post(f"{GEMINI_BASE}/{model}:generateContent", json=payload, timeout=30,
                                 headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY})
                if r.status_code == 200:
                    break
            except Exception:
                continue
        if r is None or r.status_code != 200:
            return jsonify({"error": "Gemini unavailable"}), 502
        reply = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-status")
def ai_status():
    return jsonify({"gemini_configured": bool(GEMINI_KEY), "cache_size": len(AI_CACHE), "cache_ttl_seconds": AI_CACHE_TTL, "stocks_available": len(EGX)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting OCTA v3 on port {port}")
    print(f"Gemini AI: {'YES' if GEMINI_KEY else 'NO'}")
    app.run(host="0.0.0.0", port=port, debug=False)
