import json, time, requests, os, threading
import div_actions
from flask import Flask, jsonify, request
from pathlib import Path
from datetime import datetime, timedelta

app = Flask(__name__)

# ============ CORS (ضروري عشان المتصفح يسمح للfrontend ينادي الـ API) ============
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
LIVE_DATA = {
    "lastUpdate": None,
    "market": "EGX",
    "status": "open",
    "ticker": [],
    "egx30": []
}

# ============ GEMINI AI ============
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
# موديلات Gemini — 2.0/2.5 بقوا obsolete في 2026، الجديد 3.5
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-lite-latest"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Cache للتحليلات: {code: {data, timestamp}}
AI_CACHE = {}
AI_CACHE_TTL = 3600

# آخر سعر شفناه لكل سهم (بيتبني من ENGINE_TABLE_DATA أو أي مصدر)
# بيتحفظ هنا عشان لو السعر الحي مش متاح، نستخدم آخر سعر معروف
LAST_KNOWN_PRICES = [
    {"code": "COMI",  "price": 127.69, "change": 1.10},
    {"code": "TMGH",  "price": 87.70,  "change": 0.83},
    {"code": "HRHO",  "price": 24.20,  "change": 1.68},
    {"code": "ISPH",  "price": 11.70,  "change": 1.74},
    {"code": "QNBE",  "price": 59.25,  "change": 2.16},
    {"code": "EMFD",  "price": 13.56,  "change": 10.24},
    {"code": "VLMRA", "price": 29.70,  "change": 2.41},
    {"code": "DSCW",  "price": 1.70,   "change": 3.03},
    {"code": "CIRA",  "price": 39.29,  "change": 3.18},
    {"code": "FWRY",  "price": 18.85,  "change": 3.29},
    {"code": "ORHD",  "price": 38.90,  "change": 3.48},
    {"code": "ETEL",  "price": 138.71, "change": 3.51},
    {"code": "CLHO",  "price": 15.70,  "change": 3.63},
    {"code": "CCAP",  "price": 6.88,   "change": 3.77},
    {"code": "ORAS",  "price": 819.99, "change": 3.78},
    {"code": "ORWE",  "price": 27.84,  "change": 4.27},
    {"code": "BONY",  "price": 4.09,   "change": 5.14},
    {"code": "EFIH",  "price": 23.40,  "change": 5.31},
    {"code": "RACC",  "price": 9.32,   "change": 5.31},
    {"code": "AMOC",  "price": 14.05,  "change": 5.72},
    {"code": "RAYA",  "price": 6.65,   "change": 7.26},
    {"code": "EXPA",  "price": 21.03,  "change": 0.53},
    {"code": "MNHD",  "price": 5.20,   "change": 1.96},
    {"code": "SKPC",  "price": 15.84,  "change": 0.13},
    {"code": "ABUK",  "price": 73.10,  "change": 0.29},
    {"code": "SWDY",  "price": 91.80,  "change": -0.22},
    {"code": "PHDC",  "price": 13.00,  "change": 1.96},
    {"code": "JUFO",  "price": 8.30,   "change": 1.22},
    {"code": "EGCH",  "price": 40.00,  "change": 0.50},
    {"code": "MFPC",  "price": 58.00,  "change": 0.80},
    {"code": "OCDI",  "price": 25.00,  "change": 0.40},
    {"code": "ALEX",  "price": 60.00,  "change": 0.30},
    {"code": "NINH",  "price": 30.00,  "change": 1.10},
    {"code": "HDBK",  "price": 15.00,  "change": 0.70},
    {"code": "FAIT",  "price": 20.00,  "change": 0.90},
    {"code": "ADIB",  "price": 47.15,  "change": 0.34},
    {"code": "CIEB",  "price": 25.00,  "change": 0.60},
    {"code": "EKHO",  "price": 8.50,   "change": 0.59},
    {"code": "PIOH",  "price": 12.00,  "change": 1.20},
    {"code": "GBCO",  "price": 15.00,  "change": 0.80},
    {"code": "AUTO",  "price": 4.50,   "change": 0.30},
    {"code": "EASB",  "price": 18.00,  "change": 0.50},
    {"code": "SUFI",  "price": 35.00,  "change": 0.70},
    {"code": "UEGC",  "price": 10.00,  "change": 0.40},
    {"code": "EAST",  "price": 80.00,  "change": 0.20},
    {"code": "ESRS",  "price": 120.00, "change": 1.50},
]  # ساعة


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
- خلي التوصية واضحة: شراء / تجميع / احتفظ / بيع / تجنّب

**⚠️ قاعدة مهمة جداً — ممنوع تخمّن الأرقام:**
- لو ما تعرفش السعر الحالي للسهم، اكتب price = 0
- اكتب target = 0 و stop_loss = 0 دائماً — محرك التسعير عندنا هيحسبهم صح
- الأحكام (decision, confidence, axes, reasons) هي اللي مهمتك الحقيقية

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
  "reasons": [
    "نقطة أولى للسبب",
    "نقطة ثانية",
    "نقطة ثالثة"
  ],
  "risk_level": "متوسط",
  "target": 155.00,
  "stop_loss": 130.00
}
"""


def call_gemini(code, name, price=0, change=0):
    """يستدعي Gemini ويرجّع JSON — مع fallback بين الموديلات"""
    if not GEMINI_KEY:
        return {"error": "API key not configured"}

    user_msg = f"حلل السهم المصري '{name}' (الرمز: {code})"
    if price > 0:
        user_msg += (
            f"\n\n⚠️ بيانات مؤكدة من السوق (استخدمها دي بالظبط):"
            f"\n- السعر الحالي: {price} جنيه مصري"
            f"\n- نسبة التغير اليوم: {change:+.2f}%"
            f"\n- السعر ودي نقطة البداية لحساب الهدف والستوب لوس"
        )
    else:
        user_msg += "\n\n⚠️ السعر الحالي غير متاح — اكتب price = 0 و target = 0 و stop_loss = 0"

    payload = {
        "contents": [{"parts": [{"text": user_msg}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json"
        }
    }

    last_err = ""
    for model in GEMINI_MODELS:
        for attempt in range(2):  # جرّب مرتين لكل موديل
            try:
                r = requests.post(
                    f"{GEMINI_BASE}/{model}:generateContent",
                    json=payload,
                    timeout=45,
                    headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY}
                )
                if r.status_code == 200:
                    data = r.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    result = json.loads(text)
                    result["model"] = model
                    return result
                last_err = f"{model} → {r.status_code}: {r.text[:150]}"
                # 503 = ضغط مؤقت → استنى شوية وحاول تاني
                if r.status_code in (429, 503, 500):
                    time.sleep(3 * (attempt + 1))
                    continue
                break  # 404/400 = موديل غلط، جرّب اللي بعده
            except Exception as e:
                last_err = f"{model} → {str(e)[:120]}"
                time.sleep(2)
    return {"error": last_err or "all models failed"}


# ============ EGX Stocks (للـ prompt context) ============
EGX = [
    # بنوك
    ("COMI","البنك التجاري الدولي - مصر","بنوك"),
    ("HDBK","بنك الإسكندرية","بنوك"),
    ("CIEB","بنك كريدي أجريكوول مصر","بنوك"),
    ("FAIT","بنك فيصل الإسلامي","بنوك"),
    ("ADIB","مصرف أبوظبي الإسلامي - مصر","بنوك"),
    ("QNBE","بنك قطر الوطني الأهلي","بنوك"),
    ("EXPA","البنك المصري لتنمية الصادرات","بنوك"),
    # عقارات
    ("TMGH","مجموعة طلعت مصطفى القابضة","عقارات"),
    ("PHDC","بالم هيلز للتعمير","عقارات"),
    ("EMFD","إعمار مصر للتنمية","عقارات"),
    ("MNHD","مصر الجديدة للإسكان","عقارات"),
    ("ORHD","أوراسكوم للتنمية مصر","عقارات"),
    ("BONY","بنيان للتطوير والتجاري","عقارات"),
    ("CIRA","القاهرة للاستثمارFSI","عقارات"),
    ("UEGC","الصعيد العامة للمقاولات والاستثمار العقاري","عقارات"),
    # استثمار وخدمات مالية
    ("HRHO","مجموعة أي إف جي القابضة","خدمات مالية"),
    ("CCAP","القلعة القابضة","استثمار"),
    ("VLMRA","فالمور القابضة للاستثمار بالجنيه","خدمات مالية"),
    ("RAYA","راية القابضة للاستثمارات المالية","استثمار"),
    ("RACC","رايا كاستومر إكسبرينس","تكنولوجيا"),
    ("ORAS","أوراسكوم للاستثمار","استثمار"),
    ("PIOH","بايونيرز القابضة","استثمار"),
    ("EASB","المصرية العربية ثمار لتداول الأوراق المالية","خدمات مالية"),
    # اتصالات وتكنولوجيا
    ("ETEL","المصرية للاتصالات","اتصالات"),
    ("EFIH","إي فاينانس للاستثمارات الرقمية","تكنولوجيا"),
    ("FWRY","فوري لتكنولوجيا البنوك والمدفوعات","تكنولوجيا"),
    # صناعية
    ("SWDY","السويدي إليكتريك","صناعة"),
    ("ORWE","النساجون الشرقيون","صناعة"),
    ("EKHO","إي إتش القابضة","صناعة"),
    ("DSCW","دايس للملابس","صناعة"),
    ("MFPC","مصر لإنتاج الأسمدة (موبكو)","أسمدة"),
    ("ABUK","أبو قير للأسمدة","أسمدة"),
    ("SKPC","سيدي كرير للبتروكيماويات","بتروكيماويات"),
    ("EGCH","مصر للكيماويات (موبكو)","بتروكيماويات"),
    ("SUFI","سيدي كرير للغزل والنسيج","صناعة"),
    # طاقة ونفط
    ("AMOC","الإسكندرية لمنتجات البترول","بترول"),
    ("ALEX","أسمنت بورتلاند الإسكندرية","أسمنت"),
    # صحة وأدوية
    ("ISPH","ابن سينا فارما","أدوية"),
    ("CLHO","مستشفى كليوباترا","رعاية صحية"),
    ("NINH","النيل للأدوية","أدوية"),
    #Others
    ("EAST","الشرقية للدخان","تبغ"),
    ("ESRS","حديد عز","حديد وصلب"),
    ("JUFO","جهينة للصناعات الغذائية","أغذية"),
    ("OCDI","الإسكندرية لتداول الحاويات","نقل"),
    ("GBCO","جي بي كورب القابضة","استثمار"),
    ("AUTO","أوتو جروب","استثمار"),
]

def calc_levels(price, decision, overall_score):
    """يحسب الهدف والستوب لوس رياضياً من السعر الحقيقي + القرار

    نسبة الهدف: 8% → 30% حسب قوة التوصية
    نسبة الستوب: ثابتة 7-12% حسب مستوى الخطورة
    """
    if not price or price <= 0:
        return 0, 0

    # قوة الإشارة 0..1
    strength = max(0.0, min(1.0, (overall_score or 50) / 100.0))

    # نسبة الهدف: 8% (ضعيف) → 30% (قوي جداً)
    up_pct = 0.08 + (strength * 0.22)

    # نسبة الستوب: 12% (ضعيف) → 7% (قوي)
    stop_pct = 0.12 - (strength * 0.05)

    if decision in ("بيع", "تجنب"):
        # في البيع: الهدف = downside، الستوب = أعلى من السعر (loss cut)
        target = round(price * (1 - (up_pct * 0.5)), 2)
        stop = round(price * (1 + stop_pct), 2)
    else:
        # في الشراء: الهدف = أعلى، الستوب = تحت الدعم
        target = round(price * (1 + up_pct), 2)
        stop = round(price * (1 - stop_pct), 2)

    return target, stop


EGX_MAP = {c: (n, s) for c, n, s in EGX}

TICKER = [
    ("tk-egx","EGX30","EGX:EGX30"),("tk-gold","GOLD","OANDA:XAUUSD"),
    ("tk-oil","USOIL","TVC:USOIL"),("tk-ukoil","UKOIL","TVC:UKOIL"),
    ("tk-usd","USD/EGP","EGP=X"),("tk-eur","EUR/EGP","EUR=X"),
    ("tk-spx","S&P 500","SP:SPX"),("tk-silver","SILVER","OANDA:XAGUSD"),
]

# ══════════ TradingView Scanner API (batch — كل الأسهم في طلب واحد) ══════════
SCANNER_URL = "https://scanner.tradingview.com/egypt/scan"
TV_HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}


def market_phase():
    """يرجع حالة السوق: open / closed / weekend"""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.utcnow() + timedelta(hours=3)   # UTC → القاهرة
        cairo_now = now.time()
        if now.weekday() in (4, 5):                    # الجمعة (4) والسبت (5)
            return "weekend"
        if cairo_now.hour >= 15:
            return "closed"
        if cairo_now.hour < 10:
            return "pre"
        return "open"
    except Exception:
        return "open"


def refresh_interval():
    """كل قد إيه نحدّث حسب حالة السوق"""
    phase = market_phase()
    if phase == "open":
        return 120          # دقيقتين أثناء التداول
    if phase == "pre":
        return 600          # 10 دقايق قبل الفتح
    return 3600             # ساعة بعد الإغلاق / الويك إند


def tv_scan_all():
    """يجيب كل الأسعار والتغيرات في طلب واحد"""
    tickers = [f"EGX:{c}" for c, _, _ in EGX]
    payload = {
        "symbols": {"tickers": tickers, "query": {"types": []}},
        "columns": ["close", "change", "change_abs", "volume", "name", "description"]
    }
    out = {}
    try:
        r = requests.post(SCANNER_URL, json=payload, headers=TV_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        for row in data.get("data", []):
            code = row["s"].replace("EGX:", "")
            d = row.get("d") or []
            if len(d) < 4 or d[0] is None:
                continue
            out[code] = {
                "code": code,
                "price": round(float(d[0]), 4),
                "change": round(float(d[1]), 2) if d[1] is not None else 0.0,
                "change_abs": round(float(d[2]), 4) if d[2] is not None else 0.0,
                "volume": int(d[3]) if d[3] else 0,
            }
        print(f"  📊 TV Scanner: {len(out)}/{len(EGX)} سهم")
    except Exception as e:
        print(f"  ⚠️ TV Scanner error: {e}")
    return out


def get(sym):
    p = tv_scan_all().get(sym.replace("EGX:", ""))
    return (p["price"], p["change"]) if p else (0.0, 0.0)

def update_loop():
    """loop ذكي: يحدّث حسب حالة السوق"""
    while True:
        try:
            phase = market_phase()
            interval = refresh_interval()
            print(f"\n{'='*45}")
            print(f"OCTA Update @ {datetime.utcnow().isoformat()}Z")
            print(f"Market: {phase} → every {interval}s")
            print("=" * 45)

            scan = tv_scan_all()
            global LAST_KNOWN_PRICES
            known = {s["code"]: s for s in LAST_KNOWN_PRICES}

            # 1) prices + ticker
            st = []
            for code, name, sec in EGX:
                live = scan.get(code)
                if live:
                    st.append({
                        "code": code, "name": name, "sector": sec,
                        "price": live["price"], "change": live["change"],
                        "change_abs": live["change_abs"], "volume": live["volume"]
                    })
                    known[code] = {"code": code, "price": live["price"], "change": live["change"]}
                elif code in known:
                    # مش موجود عند TradingView → نستخدم آخر سعر معروف
                    st.append({
                        "code": code, "name": name, "sector": sec,
                        "price": known[code]["price"], "change": known[code]["change"],
                        "change_abs": 0, "volume": 0, "stale": True
                    })
            LAST_KNOWN_PRICES = list(known.values())

            # 2) ticker (الذهب/الدولار/النفط)
            tk = []
            for tid, label, tvsym in TICKER:
                try:
                    rr = requests.post(
                        "https://scanner.tradingview.com/global/scan",
                        json={"symbols": {"tickers": [tvsym], "query": {"types": []}},
                              "columns": ["close", "change"]},
                        headers=TV_HEADERS, timeout=12
                    )
                    dd = rr.json().get("data", [{}])[0].get("d", [None, None])
                    price = round(float(dd[0]), 2) if dd[0] else 0.0
                    chg = round(float(dd[1]), 2) if dd[1] else 0.0
                except Exception:
                    price, chg = 0.0, 0.0
                tk.append({"id": tid, "label": label, "value": price, "change": chg,
                           "trend": "up" if chg >= 0 else "down",
                           "unit": "EGP" if "EGP" in tid else ""})
                time.sleep(0.15)

            # 3) top movers
            sorted_by_change = sorted(
                [s for s in st if s.get("change") is not None],
                key=lambda x: x["change"], reverse=True
            )
            sorted_by_volume = sorted(
                [s for s in st if s.get("volume")],
                key=lambda x: x["volume"], reverse=True
            )
            top_movers = {
                "gainers": sorted_by_change[:10],
                "losers": list(reversed(sorted_by_change[-10:])),
                "most_active": sorted_by_volume[:10]
            }

            # 4) commit للـ memory
            LIVE_DATA["lastUpdate"] = datetime.utcnow().isoformat() + "Z"
            LIVE_DATA["market_phase"] = phase
            LIVE_DATA["market_open"] = (phase == "open")
            LIVE_DATA["ticker"] = tk
            LIVE_DATA["egx30"] = st
            LIVE_DATA["top_movers"] = top_movers
            LIVE_DATA["total_stocks"] = len(st)
            LIVE_DATA["live_count"] = len(scan)

            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(LIVE_DATA, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"  cache write err: {e}")

            print(f"\n✅ SAVED: {len(st)} stocks | {len(tk)} tickers | "
                  f"{len(scan)} live | phase={phase}")
            live_sorted = sorted(scan.items(), key=lambda x: -(x[1]["change"]))
            if live_sorted:
                print(f"  🥇 أعلى: {live_sorted[0][0]} {live_sorted[0][1]['change']:+.2f}%")
        except Exception as e:
            print(f"❌ Loop error: {e}")
        time.sleep(refresh_interval())


threading.Thread(target=update_loop, daemon=True).start()


def _prices_map():
    return {s["code"]: s["price"] for s in LIVE_DATA.get("egx30", []) if s.get("price")}


def _div_snapshot():
    try:
        return div_actions.build_snapshot(_prices_map())
    except Exception as e:
        print(f"[DIV] snapshot error: {e}")
        return {"actions": [], "stats": {}, "lastUpdate": None, "source": "unavailable"}


# يجيب بيانات التوزيعات كل 6 ساعات
threading.Thread(
    target=div_actions.start_dividend_loop,
    args=(_prices_map, 6 * 3600),
    daemon=True
).start()


# ============ ROUTES: Prices ============
@app.route("/")
def health():
    return jsonify({
        "status": "ok",
        "service": "octa-prices",
        "version": "v3-gemini-3.5-flash",
        "lastUpdate": LIVE_DATA["lastUpdate"],
        "tickers": len(LIVE_DATA["ticker"]),
        "stocks": len(LIVE_DATA["egx30"]),
        "gemini": "configured" if GEMINI_KEY else "NOT configured"
    })

@app.route("/api/prices")
def prices():
    return jsonify(LIVE_DATA)

@app.route("/api/ticker")
def ticker():
    return jsonify({"ticker": LIVE_DATA["ticker"]})

@app.route("/api/stocks")
def stocks():
    return jsonify({"egx30": LIVE_DATA["egx30"]})


# ============ ROUTES: Gemini AI ============
@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        code = (data.get("code") or "").upper().strip()

        if not code:
            return jsonify({"error": "code is required"}), 400

        if code not in EGX_MAP:
            return jsonify({"error": f"unknown stock: {code}"}), 400

        # Cache check
        if code in AI_CACHE:
            age = time.time() - AI_CACHE[code]["ts"]
            if age < AI_CACHE_TTL:
                cached = dict(AI_CACHE[code]["data"])
                cached["cached"] = True
                cached["cache_age"] = int(age)
                return jsonify(cached)

        name, sector = EGX_MAP[code]

        # اجيب السعر الحالي
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
        result["name"] = name
        result["code"] = code

        # لو مفيش سعر حي (TradingView مرفوض) → نستخدم آخر سعر معروف
        if price <= 0:
            for cached_stock in LAST_KNOWN_PRICES:
                if cached_stock.get("code") == code:
                    price = cached_stock.get("price", 0)
                    change = cached_stock.get("change", 0)
                    break

        result["price"] = round(price, 2) if price else 0
        result["change"] = round(change, 2) if change else 0
        result["price_source"] = "live" if price else "unavailable"

        # الهدف والستوب محسوبين رياضياً من السعر الحقيقي (مش مخمّنين)
        t, s = calc_levels(price, result.get("decision", ""), result.get("axes", {}).get("overall"))
        result["target"] = t
        result["stop_loss"] = s

        # خزن في الـ cache
        AI_CACHE[code] = {"data": result, "ts": time.time()}

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """شات عام مع OCTA"""
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
                r = requests.post(
                    f"{GEMINI_BASE}/{model}:generateContent",
                    json=payload,
                    timeout=30,
                    headers={"Content-Type": "application/json", "X-goog-api-key": GEMINI_KEY}
                )
                if r.status_code == 200:
                    break
            except Exception:
                continue
        if r is None or r.status_code != 200:
            return jsonify({"error": "Gemini unavailable"}), 502

        data_out = r.json()
        reply = data_out["candidates"][0]["content"]["parts"][0]["text"]

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/top-movers")
def top_movers():
    """أعلى/أسفل 10 أسهم + الأكثر تداولاً"""
    tm = LIVE_DATA.get("top_movers", {})
    return jsonify({
        "lastUpdate": LIVE_DATA["lastUpdate"],
        "market_phase": LIVE_DATA.get("market_phase"),
        "market_open": LIVE_DATA.get("market_open"),
        "gainers": tm.get("gainers", []),
        "losers": tm.get("losers", []),
        "most_active": tm.get("most_active", [])
    })


@app.route("/api/heat")
def heat():
    """الخريطة الحرارية: كل الأسهم مرتبة بالتغير"""
    stocks = sorted(LIVE_DATA.get("egx30", []),
                    key=lambda s: s.get("change", 0), reverse=True)
    return jsonify({
        "lastUpdate": LIVE_DATA["lastUpdate"],
        "market_phase": LIVE_DATA.get("market_phase"),
        "stocks": stocks
    })


@app.route("/api/sector/<path:sector>")
def by_sector(sector):
    """أسهم قطاع معين"""
    stocks = [s for s in LIVE_DATA.get("egx30", [])
              if sector in (s.get("sector") or "")]
    stocks.sort(key=lambda s: s.get("change", 0), reverse=True)
    return jsonify({"sector": sector, "count": len(stocks), "stocks": stocks})


@app.route("/api/search/<path:q>")
def search(q):
    """بحث في كل الأسهم بالاسم أو الكود"""
    q = q.upper().strip()
    all_stocks = LIVE_DATA.get("egx30", [])
    hits = [s for s in all_stocks
            if q in s["code"] or q in (s.get("name") or "").upper()]
    return jsonify({"query": q, "count": len(hits), "results": hits[:50]})


@app.route("/api/dividends", methods=["GET", "POST"])
def dividends():
    """كل الـ corporate actions (نقدي/أسهم/تقسيم/زيادة رأس مال)"""
    return jsonify(_div_snapshot())


@app.route("/api/dividends/stats", methods=["GET", "POST"])
def dividends_stats():
    """ملخص ذكي للتوزيعات القادمة"""
    snap = _div_snapshot()
    return jsonify({
        "stats": snap.get("stats", {}),
        "lastUpdate": snap.get("lastUpdate"),
        "source": snap.get("source"),
    })


@app.route("/api/ai-status")
def ai_status():
    """حالة الـ AI"""
    return jsonify({
        "gemini_configured": bool(GEMINI_KEY),
        "cache_size": len(AI_CACHE),
        "cache_ttl_seconds": AI_CACHE_TTL,
        "stocks_available": len(EGX)
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting OCTA v3 on port {port}")
    print(f"Gemini AI: {'✅ configured' if GEMINI_KEY else '❌ NOT configured'}")
    app.run(host="0.0.0.0", port=port, debug=False)
