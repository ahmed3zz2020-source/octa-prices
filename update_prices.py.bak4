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
# التحليل بياخد ~30 ثانية — نخزنه 6 ساعات بدل ساعة
# (البيانات الأساسية بتتحدث كل 2 دقيقة، لكن التحليل مالوش لازم يتكرر)
AI_CACHE_TTL = 21600  # 6 ساعات
AI_CACHE_MAX = 300    # أكبر عدد أسmemo محفوظة في الذاكرة

# كاش على القرص — يفضل موجود حتى لو السيرفر اتعمله restart
AI_DISK = Path("/app/ai_cache.json")

def _load_ai_disk():
    try:
        if AI_DISK.exists():
            with open(AI_DISK, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"  AI disk cache load err: {e}")
    return {}

def _save_ai_disk():
    try:
        with open(AI_DISK, "w", encoding="utf-8") as f:
            json.dump(AI_CACHE, f, ensure_ascii=False)
    except Exception as e:
        print(f"  AI disk cache write err: {e}")

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


SYSTEM_PROMPT = """أنت محرك التحليل المالي OCTA — خبير البورصة المصرية (EGX).

تحليلك يقوم على **أرقام حقيقية من البورصةProvided لك** — مش على التذكر أو التخمين.

═══════════════════════════════════════
📊 المحاور الثمانية (كلها من 0 إلى 100)
═══════════════════════════════════════
1. technical   — التحليل الفني: مش من تقييم tv_rating وأداء الفترات
2. fundamental — التحليل الأساسي: P/E, P/B, ROE, الهوامش
3. liquidity   — السيولة: حجم التداول والحجم النسبي والحجم السوقي
4. news        — الأخبار: ⚠️ لو ما اتقالوش أخبار، اكتب 45 واقول "لا توجد أخبار"
5. sentiment   — المعنويات: من الاتجاه العام وأداء القطاع
6. risk        — المخاطر: Beta + التقلب + نسبة الدين
7. portfolio   — ملاءمة المحفظة: تنويع القطاع وحجم المخاطرة
8. overall     — التوافق العام: ناتج مرجّح للمحاور (ماشي)

═══════════════════════════════════════
🔢 كيف تحسب كل محور (مهم جداً)
═══════════════════════════════════════
**technical** = 50 + (tv_rating × 40) + (perf_1m محدود ±15)
  - يعني tv_rating = 0.5 → 70
  - tv_rating = -0.5 → 30

**fundamental** = لو فيه P/E:
  - P/E < 8 → 88 (رخيص جداً)
  - P/E < 15 → 78
  - P/E < 25 → 65
  - P/E < 40 → 50
  - P/E > 40 → 35
  زوّد/نقص حسب ROE: ROE > 30% → +10، ROE < 10% → -10

**liquidity** = حسب حجم التداول والحجم السوقي والحجم النسبي
  - حجم سوقي > 50 مليار وثباتي → 88
  - حجم سوقي < 1 مليار → 35

**risk** = 100 - (Beta × 15 + volatility × 3 + نسبة الدين × 3)
  - ⚠️ لاحظ: المحور ده عكسي — يعني，风险 أعلى = رقم أقل

**news** = 45 افتراضياً (لأن ما فيش أخبار provided)
  - لو في خبر ايجابي في analysis_pass → ترفع

═══════════════════════════════════════
⚠️ قواعد صارمة — مخالفة = خطأ
═══════════════════════════════════════
1. **ممنوع تخمّن أي رقم** — لو الحقل "غير متاح" اكتب 0 أو اعترف
2. **ممنوع تكتب رقم مش في القائمة** — استخدم المعادلات فوق
3. **confidence لازم يعكس البيانات**: لو data_confidence < 55 → confidence < 40
4. **لو البيانات ضعيفة** → confidence منخفض + reason "البيانات ناقصة"
5. **الrisky stocks** (Beta > 2 أو volatility > 5) → decision ماكونش "شراء"
6. **target = 0 و stop_loss = 0 دايماً** — محرك التسعير يحسبهم رياضياً
7. **reasons** لازم تكون محددة بأرقام من القوائم، مش كلام عام

═══════════════════════════════════════
📋 صيغة الإخراج (JSON فقط)
═══════════════════════════════════════
{
  "code": "COMI",
  "name": "اسم الشركة",
  "axes": {
    "technical": 72,
    "fundamental": 85,
    "liquidity": 90,
    "news": 45,
    "sentiment": 78,
    "risk": 82,
    "portfolio": 75,
    "overall": 80
  },
  "decision": "شراء" | "تجميع" | "احتفظ" | "بيع" | "تجنّب",
  "confidence": 75,
  "reasons": [
    "سبب فيه رقم محدد (مثل: P/E 6.1 أقل من متوسط القطاع)",
    "سبب تاني فيه رقم",
    "سبب تالت فيه رقم"
  ],
  "risk_level": "منخفض" | "متوسط" | "مرتفع",
  "target": 0,
  "stop_loss": 0
}
"""


def call_gemini(code, name, item=None):
    """يستدعي Gemini ويرجّع JSON — مع البيانات الحقيقية"""
    if not GEMINI_KEY:
        return {"error": "API key not configured"}

    item = item or {}
    price = item.get("price", 0)
    change = item.get("change", 0)

    user_msg = f"حلل السهم المصري '{name}' (الرمز: {code})"

    if item:
        conf = item.get("data_confidence", 0)
        grade = item.get("data_grade", "")
        user_msg += (
            f"\n\n{'='*52}"
            f"\n📊 بيانات حقيقية من البورصة (TradingView — Timestamp: {item.get('ts','—')})"
            f"\n{'='*52}"
            f"\n{facts_text(item)}"
            f"\n\n🎯 درجة الثقة بالبيانات: {conf}/100 ({grade})"
        )
        if conf < 55:
            user_msg += (
                f"\n\n⚠️ تنبيه: البيانات ضعيفة — لو حقل写着 'غير متاح'"
                f" ما تخمّنش قيمته. اكتب confidence منخفض (أقل من 40)."
            )
        user_msg += (
            f"\n\n⚠️ قواعد إلزامية:"
            f"\n  1. حلّل على الأرقام المعطاة فوق — هي حقيقية"
            f"\n  2. لو الحقل 'غير متاح' → اعترف بحدود التحليل"
            f"\n  3. السعر {price} ج.م هو نقطة البداية للهدف والستوب"
            f"\n  4. اكتب target = 0 و stop_loss = 0 (محرك التسعير يحسبهم)"
        )
    else:
        user_msg += "\n\n⚠️ لا توجد بيانات — اكتب price = 0 و target = 0 و stop_loss = 0"

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
    ("AALR","العامة لاستصلاح الأراضي","زراعة"),
    ("ABUK","أبو قير للأسمدة","زراعة"),
    ("ACAMD","الشركة العربية لإدارة وتطوير الأصول","متنوع"),
    ("ACAP","أي كابيتال القابضة","خدمات مالية"),
    ("ACGC","العربية لحليج الأقطان","صناعة"),
    ("ACTF","أكت فاينانشال","خدمات مالية"),
    ("ADCI","العربية للأدوية","رعاية صحية"),
    ("ADIB","مصرف أبوظبي الإسلامي - مصر","بنوك"),
    ("ADPC","العربية لمنتجات الألبان","سلع استهلاكية"),
    ("ADRI","أراب للتنمية و الاستثمار العقاري","عقارات"),
    ("AFDI","الأهلي للتنمية والاستثمار","عقارات"),
    ("AFMC","مطاحن الإسكندرية","سلع استهلاكية"),
    ("AIDC","أرابيا للاستثمار والتنمية","متنوع"),
    ("AIFI","أطلس","عقارات"),
    ("AJWA","أجواء للصناعات الغذائية","سلع استهلاكية"),
    ("ALCN","الإسكندرية لتداول الحاويات والبضائع","نقل"),
    ("ALEX","أسمنت بورتلاند الإسكندرية","مواد أساسية"),
    ("ALUM","العربية للألومنيوم","صناعة"),
    ("AMER","عامر جروب القابضة","عقارات"),
    ("AMES","الإسكندرية للخدمات الطبية","رعاية صحية"),
    ("AMIA","الملتقى العربي للاستثمارات","متنوع"),
    ("AMII","العربية للصناعات المعدنية","صناعة"),
    ("AMOC","الإسكندرية لمنتجات البترول","طاقة"),
    ("AMPI","المؤشر للبرمجة","تكنولوجيا"),
    ("APPC","المتقدمة للتعبئة الدوائية","رعاية صحية"),
    ("APSW","يونيراب بولفارا للغزل والنسيج","صناعة"),
    ("ARAB","المطورون العرب القابضة","عقارات"),
    ("ARCC","أسمنت العربية","مواد أساسية"),
    ("AREH","المجموعة المصرية العقارية","عقارات"),
    ("ASCM","أسكوم للتعدين","صناعة"),
    ("ASPI","أسباير كابيتال القابضة","خدمات مالية"),
    ("ATLC","التوفيق للتأجير التمويلي","متنوع"),
    ("ATQA","مصر الوطنية للصلب - عتاقة","طاقة"),
    ("AXPH","الإسكندرية للأدوية","رعاية صحية"),
    ("BIDI","بي اي دي – البدر للاستثمار والتنمية","صناعة"),
    ("BIGP","بى اى جى للتجارة والاستثمار","سلع استهلاكية"),
    ("BINV","بي إنفستمنتس القابضة","خدمات مالية"),
    ("BIOC","جلاكسو سميثكلاين مصر","رعاية صحية"),
    ("BONY","بنيان للتطوير والتجاري","عقارات"),
    ("BTFH","بلتون المالية القابضة","خدمات مالية"),
    ("CAED","القاهرة للخدمات التعليمية","تكنولوجيا"),
    ("CANA","بنك قناة السويس","بنوك"),
    ("CCAP","القلعة القابضة","خدمات مالية"),
    ("CCRS","الخليجية الكندية للاستثمار العقاري","عقارات"),
    ("CEFM","مطاحن مصر الوسطى","سلع استهلاكية"),
    ("CERA","العربية للخزف (ريماس)","مواد أساسية"),
    ("CFGH","كونكريت فاشون جروب","متنوع"),
    ("CICH","سي آي كابيتال القابضة","خدمات مالية"),
    ("CIEB","بنك كريدي أجريكوول مصر","بنوك"),
    ("CIRA","القاهرة للاستثمار والتنمية العقارية","عقارات"),
    ("CLHO","مستشفى كليوباترا","رعاية صحية"),
    ("CNFN","كونتكت المالية القابضة","خدمات مالية"),
    ("COMI","البنك التجاري الدولي - مصر","بنوك"),
    ("COPR","كوبر للاستثمار التجاري والعقاري","عقارات"),
    ("COSG","القاهرة للزيوت والصابون","سلع استهلاكية"),
    ("CPCI","القاهرة للأدوية والصناعات الكيماوية","رعاية صحية"),
    ("CPME","كاتاليست بارتنرز","خدمات مالية"),
    ("CRST","كريست مارك للمقاولات والتطوير العقاري","عقارات"),
    ("CSAG","القناة للتوكيلات الملاحية","نقل"),
    ("DAPH","التعمير والاستشارات الهندسية","متنوع"),
    ("DCRC","دلتا للإنشاء والتعمير","عقارات"),
    ("DEIN","دلتا للتأمين","تأمين"),
    ("DGTZ","ديجيتايز للاستثمار والتقنية","تكنولوجيا"),
    ("DOMT","دومتي للصناعات الغذائية","سلع استهلاكية"),
    ("DSCW","دايس للملابس الجاهزة","صناعة"),
    ("DTPP","دلتا للطباعة والتغليف","صناعة"),
    ("EALR","العربية لاستصلاح الأراضي","زراعة"),
    ("EASB","المصرية العربية ثمار لتداول الأوراق المالية","خدمات مالية"),
    ("EAST","الشرقية للدخان","سلع استهلاكية"),
    ("EBSC","أصول للسمسرة في الأوراق المالية","خدمات مالية"),
    ("ECAP","العز للسيراميك والبورسلين","صناعة"),
    ("EDFM","مطاحن شرق الدلتا","سلع استهلاكية"),
    ("EEII","العربية للصناعات الهندسية","صناعة"),
    ("EFIC","المالية والصناعية المصرية","متنوع"),
    ("EFID","إيديتا للصناعات الغذائية","سلع استهلاكية"),
    ("EFIH","إي فاينانس للاستثمارات الرقمية","تكنولوجيا"),
    ("EGAL","مصر للألومنيوم","صناعة"),
    ("EGAS","غاز مصر","طاقة"),
    ("EGBE","البنك المصري الخليجي","بنوك"),
    ("EGCH","مصر للكيماويات (موبكو)","بتروكيماويات"),
    ("EGREF","صندوق المصريين للاستثمار العقاري","صناديق"),
    ("EGSA","نايل سات","إعلام"),
    ("EGTS","المصرية للمنتجعات السياحية","سياحة"),
    ("EHDR","المصريين للإسكان والتنمية والتعمير","عقارات"),
    ("EITP","المصرية للمشروعات السياحية العالمية","سياحة"),
    ("ELEC","الكابلات الكهربائية المصرية","صناعة"),
    ("ELKA","القاهرة للإسكان والتعمير","عقارات"),
    ("ELNA","النصر لتصنيع الحاصلات الزراعية","سلع استهلاكية"),
    ("ELSH","الشمس للإسكان والتعمير","عقارات"),
    ("ELWA","الوادي العالمية للاستثمار والتنمية","متنوع"),
    ("EMFD","إعمار مصر للتنمية","عقارات"),
    ("ENGC","الصناعات الهندسية (أيكون)","صناعة"),
    ("EOSB","العروبة للسمسرة في الأوراق المالية","خدمات مالية"),
    ("EPCO","المصرية للدواجن","سلع استهلاكية"),
    ("EPPK","الأهرام للطباعة والتغليف","صناعة"),
    ("ETEL","المصرية للاتصالات","اتصالات"),
    ("ETRS","إيجيترانس للنقل","نقل"),
    ("EXPA","البنك المصري لتنمية الصادرات","بنوك"),
    ("FAIT","بنك فيصل الإسلامي","بنوك"),
    ("FAITA","بنك فيصل الإسلامي بالدولار","بنوك"),
    ("FERC","فيركيم مصر للأسمدة","بتروكيماويات"),
    ("FIRE","الأولى للاستثمار","عقارات"),
    ("FNAR","الفنار للمقاولات","متنوع"),
    ("FTNS","فتنس برايم للاندية الصحية","سياحة"),
    ("FWRY","فوري لتكنولوجيا البنوك والمدفوعات الإلكترونية","تكنولوجيا"),
    ("GBCO","جي بي كورب القابضة","متنوع"),
    ("GDWA","جدوى للتنمية الصناعية","صناعة"),
    ("GGCC","الجيزة العامة للمقاولات","متنوع"),
    ("GGRN","جو جرين للاستثمار الزراعي","زراعة"),
    ("GIHD","الغربية الإسلامية للتنمية العمرانية","عقارات"),
    ("GMCI","جي إم سي جروب","متنوع"),
    ("GOUR","جورميه إيجيبت","سلع استهلاكية"),
    ("GPIM","جي بي آي","مواد أساسية"),
    ("GPPL","الأهرام الذهبية بلازا","عقارات"),
    ("GRCA","جراند إنفستمنت القابضة","خدمات مالية"),
    ("GSSC","العامة للصوامع والتخزين","متنوع"),
    ("GTEX","جي تكس للاستثمارات التجارية والصناعية","صناعة"),
    ("GTHE","جلوبال تيلكوم","تكنولوجيا"),
    ("GTWL","جولدن تكس للأصواف","صناعة"),
    ("HBCO","هيبكو","مواد أساسية"),
    ("HDBK","بنك الإسكندرية","بنوك"),
    ("HELI","مصر الجديدة للإسكان","عقارات"),
    ("HRHO","مجموعة أي إف جي القابضة","خدمات مالية"),
    ("IBCT","انترناشيونال بزنيس كوربوريشن","سلع استهلاكية"),
    ("ICFC","الدولية للأسمدة","بتروكيماويات"),
    ("ICID","العالمية للاستثمار والتنمية","متنوع"),
    ("ICLE","الدولية للتأجير التمويلي","خدمات مالية"),
    ("IDRE","الإسماعيلية الجديدة للتطوير العمراني","عقارات"),
    ("IEEC","المشروعات الصناعية والهندسية","مواد أساسية"),
    ("IFAP","الدولية للمحاصيل الزراعية","زراعة"),
    ("INEG","المجموعة المتكاملة للاعمال الهندسية","مواد أساسية"),
    ("INFI","الإسماعيلية الوطنية للصناعات الغذائية","سلع استهلاكية"),
    ("IRAX","العز الدخيلة للصلب","صناعة"),
    ("IRON","الحديد والصلب المصرية","صناعة"),
    ("ISMA","الإسماعيلية مصر للدواجن","سلع استهلاكية"),
    ("ISMQ","الحديد والصلب للمناجم والمحاجر","صناعة"),
    ("ISPH","ابن سينا فارما","رعاية صحية"),
    ("JUFO","جهينة للصناعات الغذائية","سلع استهلاكية"),
    ("KABO","النصر للملابس والمنسوجات (كابو)","صناعة"),
    ("KORA","قرة لمشروعات الطاقة والاستثمار","مواد أساسية"),
    ("KRDI","نهر الخير للتنمية الزراعية","زراعة"),
    ("KWIN","القاهرة الوطنية للاستثمار","خدمات مالية"),
    ("KZPC","كفر الزيات للمبيدات","بتروكيماويات"),
    ("LCSW","ليسيكو مصر","صناعة"),
    ("LUTS","لوتس للتنمية والاستثمار الزراعي","زراعة"),
    ("MAAL","مرسيليا المصرية الخليجية","متنوع"),
    ("MASR","مدينة مصر للإسكان والتعمير","عقارات"),
    ("MBEG","إم بي","صناعة"),
    ("MBSC","مصر بني سويف للأسمنت","مواد أساسية"),
    ("MCQE","مصر للأسمنت قنا","مواد أساسية"),
    ("MCRO","ماكرو جروب للأدوية","رعاية صحية"),
    ("MENA","مينا للاستثمار السياحي والعقاري","عقارات"),
    ("MEPA","العبوات الطبية","رعاية صحية"),
    ("MFPC","مصر لإنتاج الأسمدة (موبكو","زراعة"),
    ("MFSC","مصر للأسواق الحرة","سلع استهلاكية"),
    ("MHOT","مصر للفنادق","سياحة"),
    ("MICH","مصر للصناعات الكيماوية","بتروكيماويات"),
    ("MILS","مطاحن شمال القاهرة","سلع استهلاكية"),
    ("MIPH","مينا فارم للأدوية","رعاية صحية"),
    ("MISR","ايجى ستون","مواد أساسية"),
    ("MMAT","مرسى علم للتنمية السياحية","سياحة"),
    ("MOED","نظم التعليم الحديثة","تكنولوجيا"),
    ("MOIL","ماريديف لخدمات البترول","نقل"),
    ("MOIN","المهندس للتأمين","تأمين"),
    ("MOSC","مصر للزيوت والصابون","سلع استهلاكية"),
    ("MPCI","ممفيس للأدوية","رعاية صحية"),
    ("MPCO","المنصورة للدواجن","سلع استهلاكية"),
    ("MPRC","المصرية لمدينة الإنتاج الإعلاني","إعلام"),
    ("MTIE","إم إم جروب للصناعة والتجارة العالمية","متنوع"),
    ("NAHO","نعيم القابضة للاستثمارات","خدمات مالية"),
    ("NARE","نعيم العقارية القابضة","عقارات"),
    ("NBKE","الوطني","بنوك"),
    ("NCCW","النصر للأعمال المدنية","متنوع"),
    ("NCGC","النيل لحليج الاقطان","سلع استهلاكية"),
    ("NDRL","الحفر الوطنية","متنوع"),
    ("NEDA","شمال الصعيد للتنمية الزراعية","زراعة"),
    ("NHPS","الوطنية لإسكان النقابات المهنية","عقارات"),
    ("NINH","النيل للأدوية","رعاية صحية"),
    ("NIPH","النيل للأدوية والصناعات الكيماوية","رعاية صحية"),
    ("OBRI","العبور للاستثمار العقاري","عقارات"),
    ("OCDI","الإسكندرية لتداول الحاويات","نقل"),
    ("OCPH","أكتوبر فارما","رعاية صحية"),
    ("ODIN","أودن للاستثمارات","متنوع"),
    ("OFH","أو بي المالية القابضة","خدمات مالية"),
    ("OIH","أوراسكوم للاستثمار القابضة","متنوع"),
    ("OLFI","عبور لاند للصناعات الغذائية","سلع استهلاكية"),
    ("ORAS","أوراسكوم للاستثمار","خدمات مالية"),
    ("ORHD","أوراسكوم للتنمية مصر","عقارات"),
    ("ORWE","النساجون الشرقيون","صناعة"),
    ("PACH","باكين","صناعة"),
    ("PHAR","فاركو للأدوية","رعاية صحية"),
    ("PHDC","بالم هيلز للتعمير","عقارات"),
    ("PHGC","بريميوم هيلثكير جروب","رعاية صحية"),
    ("PHTV","بيراميزا للفنادق والمنتجعات","سياحة"),
    ("POUL","القاهرة للدواجن","سلع استهلاكية"),
    ("PRCL","العامة للخزف والصيني","صناعة"),
    ("PRDC","بايونيرز بروبرتيز","عقارات"),
    ("PRMH","برايم القابضة","خدمات مالية"),
    ("QNBE","بنك قطر الوطني الأهلي","بنوك"),
    ("RACC","رايا كاستومر إكسبرينس","تكنولوجيا"),
    ("RAKT","راكتا لصناعة الورق","صناعة"),
    ("RAYA","راية القابضة للاستثمارات المالية","خدمات مالية"),
    ("RKAZ","ركاز القابضة","صناعة"),
    ("RMDA","راميدا للأدوية","رعاية صحية"),
    ("ROTO","رواد السياحة","سياحة"),
    ("RREI","أليكو للاستثمار العقاري","عقارات"),
    ("RTVC","ريمكو للقرى السياحية","سياحة"),
    ("RUBX","روبكس العالمية للبلاستيك","صناعة"),
    ("SAIB","بنك الشركة المصرفية العربية الدولية","بنوك"),
    ("SAUD","بنك البركة مصر","بنوك"),
    ("SCEM","أسمنت سيناء","مواد أساسية"),
    ("SCFM","مطاحن جنوب القاهرة والجيزة","سلع استهلاكية"),
    ("SCTS","قناة السويس لتوطين التكنولوجيا","نقل"),
    ("SDTI","شرم دريمز للاستثمار السياحي","سياحة"),
    ("SEIG","السعودية المصرية للاستثمار","خدمات مالية"),
    ("SIPC","سبأ الدولية للأدوية","رعاية صحية"),
    ("SKPC","سيدي كرير للبتروكيماويات","بتروكيماويات"),
    ("SMFR","سماد مصر","بتروكيماويات"),
    ("SMPP","الشروق الحديثة للطباعة والتغليف","صناعة"),
    ("SNFC","الشرقية الوطنية للأمن الغذائي","سلع استهلاكية"),
    ("SNFI","سوهاج الوطنية","زراعة"),
    ("SPHT","الشمس بيراميدز للفنادق","عقارات"),
    ("SPIN","الإسكندرية للغزل والنسيج","صناعة"),
    ("SPMD","سبيد ميديكال","رعاية صحية"),
    ("SUCE","هايدلبرج ماتريالز -السويس للأسمنت","مواد أساسية"),
    ("SUGR","دلتا للسكر","سلع استهلاكية"),
    ("SVCE","جنوب الوادي للأسمنت","مواد أساسية"),
    ("SWDY","السويدي إليكتريك","صناعة"),
    ("TALM","تعليم لخدمات الإدارة","تكنولوجيا"),
    ("TANM","تنمية للاستثمار العقاري","عقارات"),
    ("TAQA","طاقة عربية","طاقة"),
    ("TMGH","مجموعة طلعت مصطفى القابضة","عقارات"),
    ("TORA","اسمنت طرة","مواد أساسية"),
    ("TRTO","عبر المحيطات للسياحة","سياحة"),
    ("TWSA","توسع للتخصيم","خدمات مالية"),
    ("TYCN","تايكون للاستثمارات القابضة","خدمات مالية"),
    ("UBEE","البنك المتحد","بنوك"),
    ("UEFM","مطاحن مصر العليا","سلع استهلاكية"),
    ("UEGC","الصعيد العامة للمقاولات والاستثمار العقاري","عقارات"),
    ("UNIP","يونيفرسال للورق والتغليف","صناعة"),
    ("UNIT","المتحدة للإسكان والتعمير","عقارات"),
    ("UPMS","الاتحاد الصيدلى","رعاية صحية"),
    ("UTOP","يوتوبيا","عقارات"),
    ("VALU","ڤاليو للتمويل الاستهلاكي","تكنولوجيا"),
    ("VERT","فرتيكا","صناعة"),
    ("VLMR","فالمور القابضة","متنوع"),
    ("VLMRA","فالمور القابضة للاستثمار بالجنيه","خدمات مالية"),
    ("WATP","بيتومود","مواد أساسية"),
    ("WCDF","مطاحن وسط وغرب الدلتا","سلع استهلاكية"),
    ("WKOL","وادي كوم أمبو لاستصلاح الأراضي","زراعة"),
    ("ZEOT","الزيوت المستخلصة ومنتجاتها","سلع استهلاكية"),
    ("ZMID","زهراء المعادي للاستثمار والتعمير","عقارات"),
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
    ("tk-egx","EGX30","EGX:EGX30"),
    ("tk-egx70","EGX70","EGX:EGX70EWI"),
    ("tk-egx100","EGX100","EGX:EGX100EWI"),
    ("tk-egx33","EGX33","EGX:SHARIAH"),  # TradingView مAPHitEH في API — بنحسبه
    ("tk-egx33","EGX33","EGX:EGX33"),("tk-gold","GOLD","OANDA:XAUUSD"),
    ("tk-oil","نفط WTI","NYMEX:CL1!"),("tk-ukoil","نفط برنت","ICEEUR:BRN1!"),
    ("tk-usd","دولار/جنيه","FX_IDC:USDEGP"),("tk-eur","يورو/جنيه","FX_IDC:EUREGP"),
    ("tk-spx","S&P 500","SP:SPX"),("tk-silver","فضة","TVC:SILVER"),
]

# ══════════ TradingView Scanner API (batch — كل الأسهم في طلب واحد) ══════════
SCANNER_URL = "https://scanner.tradingview.com/egypt/scan"
TV_HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}



# ═══════════ PHASE 1: درجة الثقة بالبيانات ═══════════
# عدد الحقول الأساسية المطلوبة لكل تقييم
CORE_FIELDS = ["price", "change", "volume"]
FUND_FIELDS = ["pe", "pb", "roe", "beta", "volatility"]
VAL_FIELDS  = ["pe", "roe", "net_margin"]

def _quality_of(item):
    """
    درجة ثقة البيانات من 0 إلى 100.
    مبدأ: بيانات ناقصة = ثقة منخفضة، عشان النظام ما يقولش 'ممتاز' وهو مش ماسك
    """
    # البيانات الأساسية لازم تكون موجودة (السعر والنسب والحجم)
    base_have = sum(1 for f in CORE_FIELDS if item.get(f) is not None)
    base_score = (base_have / len(CORE_FIELDS)) * 60   # 60 نقطة للأساسيات

    # البيانات المالية بتدي 40 نقطة
    fund_have = sum(1 for f in FUND_FIELDS if item.get(f) is not None)
    fund_score = (fund_have / len(FUND_FIELDS)) * 40   # 40 نقطة للمالية

    # خصم على القيم المرفوضة (10% لكل خطأ، بحد أقصى 20)
    penalty = min(20, len(item.get("_invalid", [])) * 10)

    score = max(0, min(100, base_score + fund_score - penalty))
    item["data_confidence"] = round(score, 1)
    item["data_grade"] = "عالية" if score >= 80 else ("متوسطة" if score >= 55 else "ضعيفة")
    return score



# ═══════════ PHASE 1: تجهيز البيانات الحقيقية للذكاء الاصطناعي ═══════════
def build_facts(item):
    """يحوّل البيانات الحقيقية لسطور نصية — الذكاء الاصطناعي يقرأها ويحلّل عليها"""
    f = []
    def add(label, key, unit="", pct=False, dec=2):
        v = item.get(key)
        if v is None:
            f.append(f"- {label}: غير متاح")
        elif pct:
            f.append(f"- {label}: {v:.{dec}f}%")
        else:
            f.append(f"- {label}: {v:,.{dec}f} {unit}".strip())
    return f


def facts_text(item):
    """النص الكامل اللي هتبعت للذكاء الاصطناعي"""
    if not item:
        return "لا توجد بيانات"
    f = []
    def add(label, key, unit="", pct=False, dec=2):
        v = item.get(key)
        if v is None:
            f.append(f"  • {label}: غير متاح")
        else:
            val = f"{v:,.{dec}f}" if abs(v) < 1e7 else f"{v:,.0f}"
            if pct: val += "%"
            elif unit: val += f" {unit}"
            f.append(f"  • {label}: {val}")

    add("السعر الحالي", "price", "ج.م")
    add("التغير اليوم", "change", pct=True)
    add("حجم التداول", "volume", "سهم", dec=0)
    add("أداء الأسبوع", "perf_w", pct=True)
    add("أداء الشهر", "perf_1m", pct=True)
    add("أداء 3 شهور", "perf_3m", pct=True)
    add("أداء السنة", "perf_y", pct=True)

    f.append("\n  【التحليل المالي — أرقام حقيقية】")
    add("مضاعف الربحية", "pe")
    add("مضاعف الكتاب", "pb")
    add("العائد على حقوق الملكية", "roe", pct=True)
    add("نسبة الدين", "de_ratio")
    add("هامش الربح الصافي", "net_margin", pct=True)
    add("هامش التشغيل", "op_margin", pct=True)
    add("ربحية السهم", "eps")
    add("القيمة السوقية", "mkt_cap", "ج.م", dec=0)

    f.append("\n  【المخاطرة والسيولة】")
    add("معامل المخاطرة (Beta)", "beta")
    add("التقلب اليومي", "volatility", pct=True)
    add("حجم نسبي مقابل 10 أيام", "rel_volume")
    add("عائد التوزيعات", "div_yield", pct=True)
    add("تقييم المصدر الفني", "tv_rating")

    tv = item.get("tv_rating")
    if tv is not None:
        if tv > 0.3: tvs = "شراء قوي"
        elif tv > 0.1: tvs = "شراء"
        elif tv > -0.1: tvs = "محايد"
        elif tv > -0.3: tvs = "بيع"
        else: tvs = "بيع قوي"
        f.append(f"  → تقييم المصدر الفني = {tvs}")

    return "\n".join(f)



# ═══════════ Phase 1: نتيجة فورية من الأرقام الحقيقية ═══════════
# لو الكاش فاضي، نرجع نتيجة محسوبة رياضياً فوراً (بدون انتظار الـ AI)
# الـ AI بعدين يحدّثها لما يجي دوره
def quick_score(item):
    """حساب رياضي سريع من الأرقام الحقيقية — هي دقيق كفاية كبداية"""
    if not item or not item.get("price"):
        return None

    axes = {}

    # 1) فني: لو عندنا محرك التحليل الفني الكامل، نستخدمه
    tech = tech_score(item)
    if tech:
        axes["technical"] = round(tech["score"])
    else:
        tv = item.get("tv_rating") or item.get("tv_all")
        p1m = item.get("perf_1m")
        t = 50.0
        if tv is not None:
            t += tv * 40
        if p1m is not None:
            t += max(-15, min(15, p1m / 3))
        axes["technical"] = round(max(0, min(100, t)))

    # 2) أساسي: P/E + ROE + الهوامش
    pe, roe = item.get("pe"), item.get("roe")
    f = 55.0
    if pe is not None:
        if pe < 0: f = 30
        elif pe < 8: f = 88
        elif pe < 15: f = 78
        elif pe < 25: f = 65
        elif pe < 40: f = 50
        else: f = 35
    if roe is not None:
        if roe > 30: f += 10
        elif roe < 10: f -= 10
    axes["fundamental"] = round(max(0, min(100, f)))

    # 3) سيولة: الحجم السوقي + الحجم النسبي
    mc = item.get("mkt_cap")
    l = 50.0
    if mc is not None:
        if mc > 50e9: l = 88
        elif mc > 20e9: l = 80
        elif mc > 5e9: l = 68
        elif mc > 1e9: l = 55
        else: l = 38
    vol = item.get("volume")
    if vol and vol > 1_000_000: l += 5
    axes["liquidity"] = round(max(0, min(100, l)))

    # 4) أخبار: ما فيش أخبار لسه = 45
    axes["news"] = 45

    # 5) معنويات: من أداء الشهر
    s = 50.0
    if p1m is not None:
        s += max(-25, min(25, p1m / 2))
    axes["sentiment"] = round(max(0, min(100, s)))

    # 6) مخاطر (عكسي)
    beta, vola, de = item.get("beta"), item.get("volatility"), item.get("de_ratio")
    r = 80.0
    if beta is not None: r -= beta * 12
    if vola is not None: r -= vola * 3
    if de is not None: r -= min(25, de * 3)
    axes["risk"] = round(max(0, min(100, r)))

    # 7) ملاءمة المحفظة: مبدئياً حسب حجم السوق (Phase 8 هتكمّل)
    axes["portfolio"] = 70

    # المحصلة: مرجّحة مع خصم المخاطرة
    w = {"technical": .18, "fundamental": .28, "liquidity": .12,
         "news": .07, "sentiment": .08, "risk": .17, "portfolio": .10}
    base = sum(axes[k] * w[k] for k in w)
    risk_penalty = (100 - axes["risk"]) * 0.15
    overall = round(max(0, min(100, base - risk_penalty)))
    axes["overall"] = overall

    # القرار من الأرقام
    if axes["risk"] < 40:
        decision = "تجنّب"
    elif overall >= 75 and axes["technical"] >= 55:
        decision = "تجميع"
    elif overall >= 60:
        decision = "احتفظ"
    elif axes["fundamental"] >= 70:
        decision = "احتفظ"
    else:
        decision = "بيع"

    conf = int(item.get("data_confidence", 0))
    level = "منخفض" if axes["risk"] < 40 else ("متوسط" if axes["risk"] < 70 else "مرتفع")

    return {
        "code": item["code"], "axes": axes,
        "decision": decision, "confidence": min(85, conf),
        "risk_level": level,
        "reasons": [
            f"مضاعف الربحية {pe:.1f}" if pe is not None else "بيانات الربحية غير متاحة",
            f"العائد على الملكية {roe:.1f}%" if roe is not None else "العائد على الملكية غير متاح",
            f"التقييم الفني {tv:+.2f}" if tv is not None else "التقييم الفني غير متاح",
        ],
        "_quick": True,
    }



# ════════════════════════════════════════════════════════════
# PHASE 2: محرك التحليل الفني — كل رقم من الأرقام الحقيقية
# ════════════════════════════════════════════════════════════

def tech_score(item):
    """
    يحوّل 43 مؤشر فني → نتيجة 0-100 مع تفسير كامل.
    المبدأ: كل نقطة ليها وزن وليها سبب — مفيش رقم بلا مبرر.
    """
    if not item or not item.get("price"):
        return None
    price = item["price"]
    facts = {"positives": [], "negatives": [], "neutral": []}

    # ─────────── 1) الاتجاه (35 نقطة) ───────────
    trend = 0.0
    # ترتيب المتوسطات: Golden alignment؟
    ema20, ema50, ema200 = item.get("ema20"), item.get("ema50"), item.get("ema200")
    sma50 = item.get("sma50")

    ma_above = 0  # كام متوسط تحت السعر
    for name, v in (("EMA20", ema20), ("EMA50", ema50), ("EMA200", ema200), ("SMA50", sma50)):
        if v is not None:
            if price > v:
                ma_above += 1
                facts["positives"].append(f"السعر فوق {name} ({v:.2f})")
            else:
                facts["negatives"].append(f"السعر تحت {name} ({v:.2f})")
    trend += (ma_above / 4) * 20   # 20 نقطة

    # ترتيب المتوسطات (EMA20 > EMA50 > EMA200 = صاعد)
    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            trend += 10
            facts["positives"].append("ترتيب المتوسطات صاعد (EMA20 > EMA50 > EMA200)")
        elif ema20 < ema50 < ema200:
            trend += 0
            facts["negatives"].append("ترتيب المتوسطات هابط (اتجاه bearish)")
        else:
            trend += 5
            facts["neutral"].append("المتوسطات متشابكة — اتجاه عرضي")

    # قوة الاتجاه (ADX) — فوق 25 = اتجاه قوي
    adx, di_p, di_m = item.get("adx"), item.get("di_plus"), item.get("di_minus")
    if adx is not None:
        if adx > 40:
            trend += 5
            facts["positives"].append(f"قوة اتجاه عالية ({adx:.0f})")
        elif adx < 20:
            trend += 0
            facts["neutral"].append(f"اتجاه ضعيف/عرضي ({adx:.0f})")
    if di_p is not None and di_m is not None:
        if di_p > di_m:
            trend += 3
            facts["positives"].append("الحركة الصاعدة أقوى من الهابطة")
        elif di_m > di_p:
            facts["negatives"].append("الحركة الهابطة أقوى من الصاعدة")

    trend_score = max(0, min(35, trend))

    # ─────────── 2) الزخم (25 نقطة) ───────────
    mom = 0.0
    rsi, rsi_prev = item.get("rsi"), item.get("rsi_prev")
    if rsi is not None:
        if rsi > 70:
            mom += 8
            facts["negatives"].append(f"القوة النسبية {rsi:.0f} — منطقة تشبع شرائي")
        elif rsi > 55:
            mom += 15
            facts["positives"].append(f"القوة النسبية {rsi:.0f} — زخم صاعد")
        elif rsi > 45:
            mom += 10
        elif rsi > 30:
            mom += 12
            facts["positives"].append(f"القوة النسبية {rsi:.0f} — منطقة تشبع بيعي (فرصة شراء)")
        else:
            mom += 6
            facts["negatives"].append(f"القوة النسبية {rsi:.0f} — زخم هابط قوي")
        # RSI اتجاه
        if rsi_prev is not None:
            if rsi > rsi_prev + 2:
                mom += 4
                facts["positives"].append("الزخم بيتسارع")
            elif rsi < rsi_prev - 2:
                mom -= 2
                facts["negatives"].append("الزخم بيتباطأ")

    # التقارب والانحراف
    macd, sig = item.get("macd"), item.get("macd_signal")
    if macd is not None and sig is not None:
        if macd > sig:
            mom += 8
            facts["positives"].append("التقارب فوق خط الإشارة")
        else:
            mom += 2
            facts["negatives"].append("التقارب تحت خط الإشارة")
        if macd > 0:
            mom += 3
            facts["positives"].append("التقارب موجب")

    # ستوكاستك
    k, d = item.get("stoch_k"), item.get("stoch_d")
    if k is not None and d is not None:
        if k > d and k < 80:
            mom += 5
            facts["positives"].append("الستوكاستك صاعد")
        elif k < d and k > 20:
            mom -= 2
            facts["negatives"].append("الستوكاستك هابط")

    # التذبذبurzugs (momentum oscillator)
    mo = item.get("momentum")
    if mo is not None:
        mom += max(-3, min(3, mo / 3))
    ao = item.get("awesome")
    if ao is not None:
        mom += 3 if ao > 0 else -2

    mom_score = max(0, min(25, mom))

    # ─────────── 3) الموقع من النطاق (20 نقطة) ───────────
    pos_score = 10.0
    hi1m, lo1m = item.get("high_1m"), item.get("low_1m")
    if hi1m and lo1m and hi1m > lo1m:
        where = (price - lo1m) / (hi1m - lo1m) * 100  # 0 = قاع الشهر، 100 = قمته
        if where > 85:
            pos_score = 3
            facts["negatives"].append(f"السهم قرب قمة الشهر ({where:.0f}% من النطاق)")
        elif where > 65:
            pos_score = 12
            facts["positives"].append(f"السهم في الجزء العلوي من نطاق الشهر ({where:.0f}%)")
        elif where > 40:
            pos_score = 16
            facts["neutral"].append(f"السهم في منتصف نطاق الشهر ({where:.0f}%)")
        elif where > 20:
            pos_score = 18
            facts["positives"].append(f"السهم في الجزء السفلي — فرصة أفضل ({where:.0f}%)")
        else:
            pos_score = 15
            facts["positives"].append(f"السهم قرب قاع الشهر ({where:.0f}%)")

    # نطاقات بولنجر
    bbu, bbl = item.get("bb_upper"), item.get("bb_lower")
    if bbu and bbl and bbu > bbl:
        bw = (bbu - bbl) / price * 100
        pos_score = max(0, min(20, pos_score + 2))
        if bw < 8:
            facts["positives"].append(f"نطاق بولنجر ضيق ({bw:.1f}%) — ضغط قبل اختراق")
    pos_score = max(0, min(20, pos_score))

    # ─────────── 4) الحجم والتأكيد (10 نقاط) ───────────
    vol_score = 5.0
    rv = item.get("rel_volume")
    if rv is not None:
        if rv > 1.5:
            vol_score = 9
            facts["positives"].append(f"حجم تداول أعلى من المعتاد ({rv:.1f}×)")
        elif rv > 1.0:
            vol_score = 7
        elif rv < 0.5:
            vol_score = 3
            facts["neutral"].append(f"حجم تداول ضعيف ({rv:.1f}×) — مفيش تأكيد")
    # تأكيد الاتجاه بالحجم: لو السعر طالع والحجم عالي = مؤكد
    perf1m = item.get("perf_1m")
    if perf1m is not None and rv is not None:
        if perf1m > 3 and rv > 1.2:
            vol_score = min(10, vol_score + 3)
            facts["positives"].append("الصعود مؤكّد بحجم تداول")
        elif perf1m < -3 and rv > 1.2:
            vol_score = max(0, vol_score - 3)
            facts["negatives"].append("الهبوط مؤكّد بحجم تداول")

    # ─────────── 5) تقييم المصدر الفني (10 نقاط) ───────────
    tv_all, tv_ma, tv_osc = item.get("tv_all"), item.get("tv_ma"), item.get("tv_osc")
    tv_score = 5.0
    if tv_all is not None:
        tv_score = max(0, min(10, 5 + tv_all * 10))
        label = "شراء قوي" if tv_all > 0.3 else ("شراء" if tv_all > 0.1 else
                ("محايد" if tv_all > -0.1 else ("بيع" if tv_all > -0.3 else "بيع قوي")))
        if tv_all > 0.15:
            facts["positives"].append(f"التقييم الفني: {label} ({tv_all:+.2f})")
        elif tv_all < -0.15:
            facts["negatives"].append(f"التقييم الفني: {label} ({tv_all:+.2f})")
        else:
            facts["neutral"].append(f"التقييم الفني محايد ({tv_all:+.2f})")

    # ─────────── 6) المخاطرة الفنية (الخصم) ───────────
    atr = item.get("atr")
    atr_pct = 0.0
    if atr and price:
        atr_pct = atr / price * 100
        if atr_pct > 6:
            facts["negatives"].append(f"تذبذب عالي جداً ({atr_pct:.1f}% يومياً) — مخاطرة عالية")
        elif atr_pct > 3.5:
            facts["negatives"].append(f"تذبذب عالي ({atr_pct:.1f}% يومياً)")
        elif atr_pct < 1.5:
            facts["positives"].append(f"سهم مستقر (تذبذب {atr_pct:.1f}%)")

    # ─────────── النتيجة النهائية ───────────
    total = trend_score + mom_score + pos_score + vol_score + tv_score
    total = max(0, min(100, total))

    # مستوى الثقة الفني: كام مؤشر متاح فعلاً
    avail = sum(1 for k in ("ema20","ema50","ema200","rsi","macd","macd_signal","adx",
                            "atr","bb_upper","stoch_k","tv_all","perf_1m")
                if item.get(k) is not None)
    tech_conf = min(100, avail / 12 * 100)

    # التوصية
    if total >= 70 and trend_score >= 20:
        signal = "إيجابي قوي"
    elif total >= 55:
        signal = "إيجابي"
    elif total >= 42:
        signal = "محايد"
    elif total >= 28:
        signal = "سلبي"
    else:
        signal = "سلبي قوي"

    return {
        "score": round(total, 1),
        "signal": signal,
        "breakdown": {
            "الاتجاه": round(trend_score, 1),
            "الزخم": round(mom_score, 1),
            "الموقع من النطاق": round(pos_score, 1),
            "الحجم": round(vol_score, 1),
            "تقييم المصدر": round(tv_score, 1),
        },
        "confidence": round(tech_conf, 1),
        "atr_pct": round(atr_pct, 2),
        "positives": facts["positives"][:5],
        "negatives": facts["negatives"][:5],
        "neutral": facts["neutral"][:3],
        "levels": {
            "دعم_1": item.get("pivot_s1"),
            "مقاومة_1": item.get("pivot_r1"),
            "نقطة_محايدة": item.get("pivot_m"),
            "أعلى_شهر": item.get("high_1m"),
            "أدنى_شهر": item.get("low_1m"),
        }
    }


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


# ═══════════ PHASE 1: الأعمدة المتاحة من المصدر ═══════════
# كل عمود اتأكد إنه بيرجع بيانات حقيقية من TradingView
TV_COLUMNS = [
    ("close",              "price"),            # السعر
    ("change",             "change"),           # التغير %
    ("change_abs",         "change_abs"),       # التغير بالجنيه
    ("volume",             "volume"),           # حجم التداول
    ("Perf.W",             "perf_w"),           # أداء أسبوع
    ("Perf.1M",            "perf_1m"),          # أداء شهر
    ("Perf.3M",            "perf_3m"),          # أداء 3 شهور
    ("Perf.6M",            "perf_6m"),          # أداء 6 شهور
    ("Perf.Y",             "perf_y"),           # أداء سنة
    ("Volatility.D",       "volatility"),       # التقلب اليومي %
    ("relative_volume_10d_calc", "rel_volume"), # حجم نسبي
    ("Recommend.All",      "tv_rating"),        # تقييم المصدر الفني (-1..1)
    ("beta_1_year",        "beta"),             # معامل المخاطرة
    ("dividends_yield_current", "div_yield"),   # عائد التوزيع %
    ("market_cap_basic",   "mkt_cap"),          # القيمة السوقية
    ("price_earnings_ttm", "pe"),               # مضاعف الربحية
    ("price_book_fq",      "pb"),               # مضاعف الكتاب
    ("return_on_equity",   "roe"),              # العائد على حقوق الملكية
    ("debt_to_equity",     "de_ratio"),         # نسبة الدين
    ("net_margin",         "net_margin"),       # هامش الربح الصافي
    ("operating_margin",   "op_margin"),        # هامش التشغيل
    ("earnings_per_share_diluted_ttm", "eps"),  # ربحية السهم
    ("total_revenue",      "revenue"),          # الإيرادات
]

# ═══════════ PHASE 2: الأعمدة الفنية (60 مؤشر في طلب واحد) ═══════════
TV_TECH_COLUMNS = [
    # الاتجاه — المتوسطات المتحركة
    ("EMA10",              "ema10"),
    ("EMA20",              "ema20"),
    ("EMA50",              "ema50"),
    ("EMA200",             "ema200"),
    ("SMA20",              "sma20"),
    ("SMA50",              "sma50"),
    ("SMA200",             "sma200"),
    ("SMA30|1W",           "sma30w"),          # متوسط 30 أسبوع
    # الزخم — المؤشرات
    ("RSI",                "rsi"),
    ("RSI[1]",             "rsi_prev"),        # RSI امبارح → نقارن الاتجاه
    ("MACD.macd",          "macd"),
    ("MACD.signal",        "macd_signal"),
    ("Stoch.K",            "stoch_k"),
    ("Stoch.D",            "stoch_d"),
    ("CCI20",              "cci20"),
    ("ADX",                "adx"),             # قوة الاتجاه
    ("ADX+DI",             "di_plus"),
    ("ADX-DI",             "di_minus"),
    ("Mom",                "momentum"),
    ("AO",                 "awesome"),
    ("UO",                 "ultimate"),
    ("W.R",                "williams_r"),
    ("HullMA9",            "hull9"),
    ("Ichimoku.BLine",     "ichimoku_b"),
    ("P.SAR",              "psar"),
    # التذبذب
    ("ATR",                "atr"),
    ("BB.upper",           "bb_upper"),
    ("BB.lower",           "bb_lower"),
    ("BB.basis",           "bb_basis"),
    ("BBPower",            "bb_power"),
    # مستويات
    ("Pivot.M.Classic.Middle", "pivot_m"),
    ("Pivot.M.Classic.R1",  "pivot_r1"),
    ("Pivot.M.Classic.S1",  "pivot_s1"),
    ("High.1M",            "high_1m"),
    ("Low.1M",             "low_1m"),
    ("High.3M",            "high_3m"),
    ("Low.3M",             "low_3m"),
    ("High.6M",            "high_6m"),
    ("Low.6M",             "low_6m"),
    # التقييم الفني التفصيلي
    ("Recommend.All",      "tv_all"),
    ("Recommend.MA",       "tv_ma"),           # تقييم المتوسطات (فني بحت)
    ("Recommend.Other",    "tv_osc"),          # تقييم المؤشرات (فني بحت)
    # الحجم
    ("volume|5",           "vol_5"),
    ("volume|60",          "vol_60"),
    ("VWMA",               "vwma"),
]

# ═══════════ PHASE 1: قواعد التحقق من صحة البيانات ═══════════
# أي رقم بيمر من هنا، لو خالف بيتباعد
def validate_value(field, value, price=None):
    """يرجع (القيمة، سبب_الرفض_ان_فشل)"""
    if value is None:
        return None, None

    # حدود منطقية عامة
    BOUNDS = {
        "price":        (0.01, 1_000_000),
        "change":       (-99.0, 99.0),      # التغير % مينفعش يعدي 99%
        "change_abs":   (-1_000_000, 1_000_000),
        "volume":       (0, 500_000_000),
        "perf_w":       (-100.0, 500.0),
        "perf_1m":      (-100.0, 500.0),
        "perf_3m":      (-100.0, 800.0),
        "perf_6m":      (-100.0, 1000.0),
        "perf_y":       (-100.0, 3000.0),
        "volatility":   (0.0, 100.0),       # التقلب 0-100%
        "rel_volume":   (0.0, 1000.0),
        "tv_rating":    (-1.0, 1.0),        # تقييم المصدر -1..1
        "beta":         (-5.0, 10.0),       # معامل المخاطرة المعقول
        "div_yield":    (0.0, 100.0),
        "mkt_cap":      (0, 10_000_000_000_000),
        "pe":           (-500.0, 1000.0),   # P/E السالب = شركة خسرانة
        "pb":           (0.0, 200.0),
        "roe":          (-200.0, 200.0),    # % 
        "de_ratio":     (0.0, 1000.0),
        "net_margin":   (-500.0, 200.0),    # %
        "op_margin":    (-500.0, 300.0),    # %
        "eps":          (-1000.0, 1000.0),
        "revenue":      (0, 10_000_000_000_000),
        # ── المرحلة الثانية: الفنية ──
        "ema10":        (0.01, 1_000_000), "ema20": (0.01, 1_000_000),
        "ema50":        (0.01, 1_000_000), "ema200": (0.01, 1_000_000),
        "sma20":        (0.01, 1_000_000), "sma50": (0.01, 1_000_000),
        "sma200":       (0.01, 1_000_000), "sma30w": (0.01, 1_000_000),
        "rsi":          (0.0, 100.0),      # مؤشر القوة 0-100
        "rsi_prev":     (0.0, 100.0),
        "macd":         (-10000.0, 10000.0),
        "macd_signal":  (-10000.0, 10000.0),
        "stoch_k":      (0.0, 100.0),
        "stoch_d":      (0.0, 100.0),
        "cci20":        (-500.0, 500.0),
        "adx":          (0.0, 100.0),       # قوة الاتجاه 0-100
        "di_plus":      (0.0, 100.0),
        "di_minus":     (0.0, 100.0),
        "momentum":     (-1000.0, 1000.0),
        "awesome":      (-10000.0, 10000.0),
        "ultimate":     (0.0, 100.0),
        "williams_r":   (-100.0, 0.0),      # وليمiams 0 إلى -100
        "hull9":        (0.01, 1_000_000),
        "ichimoku_b":    (0.01, 1_000_000),
        "psar":         (0.01, 1_000_000),
        "atr":          (0.0, 100_000.0),
        "bb_upper":     (0.01, 1_000_000),
        "bb_lower":     (0.01, 1_000_000),
        "bb_basis":     (0.01, 1_000_000),
        "bb_power":     (-200.0, 200.0),
        "pivot_m":      (0.01, 1_000_000),
        "pivot_r1":     (0.01, 1_000_000),
        "pivot_s1":     (0.01, 1_000_000),
        "high_1m":      (0.01, 1_000_000), "low_1m": (0.0, 1_000_000),
        "high_3m":      (0.01, 1_000_000), "low_3m": (0.0, 1_000_000),
        "high_6m":      (0.01, 1_000_000), "low_6m": (0.0, 1_000_000),
        "tv_all":       (-1.0, 1.0),
        "tv_ma":        (-1.0, 1.0),
        "tv_osc":       (-1.0, 1.0),
        "vol_5":        (0, 5_000_000_000),
        "vol_60":       (0, 5_000_000_000),
        "vwma":         (0.01, 1_000_000),
    }

    lo, hi = BOUNDS.get(field, (float("-inf"), float("inf")))
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, f"{field}: ليس رقماً ({value})"

    if v != v:  # NaN
        return None, f"{field}: قيمة غير صالحة"
    if v < lo or v > hi:
        return None, f"{field}: {v} خارج النطاق المقبول ({lo}..{hi})"

    return v, None


def tv_scan_all(symbols=None):
    """يجيب كل الأسعار + البيانات الأساسية في طلب واحد"""
    tickers = symbols if symbols else [f"EGX:{c}" for c, _, _ in EGX]
    # ندمج كل الأعمدة: الأساسية + الفنية
    all_cols = TV_COLUMNS + TV_TECH_COLUMNS
    cols = [c for c, _ in all_cols]
    payload = {
        "symbols": {"tickers": tickers, "query": {"types": []}},
        "columns": cols
    }
    out = {}
    try:
        r = requests.post(SCANNER_URL, json=payload, headers=TV_HEADERS, timeout=40)
        r.raise_for_status()
        data = r.json()
        for row in data.get("data", []):
            code = row["s"].replace("EGX:", "")
            d = row.get("d") or []
            rec = {"code": code, "_invalid": []}
            for i, (col, field) in enumerate(all_cols):
                raw = d[i] if i < len(d) else None
                val, err = validate_value(field, raw)
                if err:
                    rec["_invalid"].append(err)
                rec[field] = val
            # لازم يكون فيه سعر صالح عشان السهم ينفع يتعامل معاه
            if rec.get("price"):
                out[code] = rec
        print(f"  TV Scanner: {len(out)}/{len(tickers)} سهم | "
              f"أخطاء تحقق: {sum(len(v['_invalid']) for v in out.values())}")
        return out
    except Exception as e:
        print(f"  TV Scanner error: {e}")
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

            # 1) prices + fundamentals + ticker
            st = []
            now_ts = datetime.utcnow().isoformat() + "Z"
            for code, name, sec in EGX:
                live = scan.get(code)
                if live:
                    item = {
                        "code": code, "name": name, "sector": sec,
                        "ts": now_ts,
                        "_invalid": live.get("_invalid", [])
                    }
                    # كل الحقول المتاحة
                    for _, field in TV_COLUMNS:
                        item[field] = live.get(field)
                    # درجة الثقة بالبيانات: كام حقل فعلاً اتجاوب
                    item["data_quality"] = _quality_of(item)
                    st.append(item)
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

            # 2.5) EGX33 — لو رجّع 0 نحسبه كمتوسط EGX30/EGX70 (تقريبي)
            for it in tk:
                if it["id"] == "tk-egx33" and (not it.get("value") or it["value"] == 0):
                    egx30 = next((t for t in tk if t["id"] == "tk-egx"), None)
                    egx70 = next((t for t in tk if t["id"] == "tk-egx70"), None)
                    if egx30 and egx70:
                        it["value"] = round((egx30["value"] + egx70["value"]) / 2, 2)
                        it["change"] = round((egx30["change"] + egx70["change"]) / 2, 2)
                        it["_approx"] = True

            # 3) top movers
            sorted_by_change = sorted(
                [s for s in st if s.get("change") is not None],
                key=lambda x: x["change"], reverse=True
            )
            sorted_by_volume = sorted(
                [s for s in st if s.get("volume")],
                key=lambda x: x["volume"], reverse=True
            )
            PERIODS = ["change", "perf_w", "perf_1m", "perf_3m", "perf_6m", "perf_y"]
            top_movers = {}
            for pk in PERIODS:
                valid = [s for s in st if s.get(pk) is not None]
                desc = sorted(valid, key=lambda x: x[pk], reverse=True)
                top_movers[pk] = {
                    "gainers": desc[:10],
                    "losers": list(reversed(desc[-10:])),
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


AI_CACHE.update(_load_ai_disk())
print(f"  AI disk cache: {len(AI_CACHE)} entries")

threading.Thread(target=update_loop, daemon=True).start()


def _prices_map():
    return {s["code"]: s["price"] for s in LIVE_DATA.get("egx30", []) if s.get("price")}


def _div_snapshot():
    try:
        prices = _prices_map()
        codes = {a["code"] for a in div_actions.CACHE.get("actions", [])}
        missing = [c for c in codes if c not in prices]
        if missing:
            scan = tv_scan_all([f"EGX:{c}" for c in missing])
            for sym, r in (scan or {}).items():
                code = sym.replace("EGX:", "")
                if r.get("price"):
                    prices[code] = r["price"]
        return div_actions.build_snapshot(prices)
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

        # ═══ Phase 1: اجيب كل البيانات الحقيقية للسهم ═══
        item = None
        for s in LIVE_DATA.get("egx30", []):
            if s["code"] == code:
                item = s
                break

        price = (item or {}).get("price", 0)
        change = (item or {}).get("change", 0)

        # aude 1: تحليل بالأرقام الحقيقية
        # ═══ Phase 1: نتيجة فورية لو الكاش فاضي (المستخدم مش مستني 30 ثانية) ═══
        quick = quick_score(item)
        result = call_gemini(code, name, item)

        if "error" in result:
            # لو الذكاء الاصطناعي فشل، نرجع النتيجة السريعة بدل ما نرجع خطأ
            if quick:
                quick["name"] = name
                quick["sector"] = sector
                quick["price"] = round(item.get("price", 0), 2)
                quick["change"] = round(item.get("change", 0), 2)
                quick["ai_error"] = str(result["error"])[:120]
                quick["source"] = "quick_math"
                t, sl = calc_levels(item.get("price", 0), quick["decision"], quick["axes"]["overall"])
                quick["target"], quick["stop_loss"] = t, sl
                quick["fundamentals"] = {k: item.get(k) for k in
                    ("pe","pb","roe","beta","volatility","div_yield","net_margin","de_ratio","eps","tv_rating")}
                quick["data_confidence"] = item.get("data_confidence", 0)
                quick["data_grade"] = item.get("data_grade", "")
                quick["data_ts"] = item.get("ts")
                if tech_score(item):
                    quick["technical"] = tech_score(item)
                return jsonify(quick)
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

        # ═══ Phase 1: البيانات الحقيقية في الرد ═══
        if item:
            FUND_KEYS = ["pe", "pb", "roe", "de_ratio", "net_margin", "op_margin",
                         "eps", "beta", "volatility", "rel_volume", "div_yield",
                         "tv_rating", "mkt_cap", "perf_w", "perf_1m", "perf_y"]
            result["fundamentals"] = {k: item.get(k) for k in FUND_KEYS}
            result["data_confidence"] = item.get("data_confidence", 0)
            result["data_grade"] = item.get("data_grade", "غير معروف")
            result["data_ts"] = item.get("ts")
            result["data_invalid"] = item.get("_invalid", [])

            # ═══ Phase 1: تغطية المحاور — كام محور اتحسب على بيانات حقيقية ═══
            result["axes_from_data"] = {
                "technical": item.get("tv_rating") is not None,
                "fundamental": any(item.get(k) is not None for k in ("pe", "roe", "net_margin")),
                "liquidity": item.get("volume") is not None or item.get("mkt_cap") is not None,
                "risk": item.get("beta") is not None or item.get("volatility") is not None,
                "news": False,       # ما فيش أخبار — Phase 5
                "sentiment": item.get("perf_1m") is not None,
                "portfolio": False,  # محتاج portfolio — Phase 8
            }
            covered = sum(1 for v in result["axes_from_data"].values() if v)
            result["axes_coverage"] = f"{covered}/7"

            # ═══ Phase 2: التحليل الفني الكامل (محرك رياضي) ═══
            tech = tech_score(item)
            if tech:
                result["technical"] = tech
                # ندمج المحور الفني: لو الذكاء الاصطناعي خمّن أعلى من الحساب، ناخد الأدنى
                # (مبدأ: ما نبغاش نبالغ في التقييم)
                ai_tech = (result.get("axes") or {}).get("technical", 50)
                result["axes"]["technical"] = min(ai_tech, tech["score"])
                # نحدّث المحصلة
                axes = result["axes"]
                base = sum([
                    axes.get("technical", 50) * .18, axes.get("fundamental", 50) * .28,
                    axes.get("liquidity", 50) * .12, axes.get("news", 45) * .07,
                    axes.get("sentiment", 50) * .08, axes.get("risk", 60) * .17,
                    axes.get("portfolio", 70) * .10,
                ])
                axes["overall"] = round(max(0, min(100, base - (100 - axes.get("risk", 60)) * .15)))

        # الهدف والستوب محسوبين رياضياً من السعر الحقيقي (مش مخمّنين)
        t, s = calc_levels(price, result.get("decision", ""), result.get("axes", {}).get("overall"))
        result["target"] = t
        result["stop_loss"] = s

        # خزن في الـ cache (ذاكرة + قرص)
        AI_CACHE[code] = {"data": result, "ts": time.time()}
        # لو الكاش كبر، نشيل الأقدم
        if len(AI_CACHE) > AI_CACHE_MAX:
            oldest = sorted(AI_CACHE.items(), key=lambda kv: kv[1]["ts"])[:50]
            for k, _ in oldest:
                AI_CACHE.pop(k, None)
        _save_ai_disk()

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


@app.route("/api/technical/<code>")
def technical_only(code):
    """تحليل فني مفصّل بدون ذكاء اصطناعي — فوري 100%"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    tech = tech_score(item)
    if not tech:
        return jsonify({"error": "بيانات فنية غير كافية"}), 400
    return jsonify({
        "code": code,
        "name": item.get("name"),
        "price": item.get("price"),
        "change": item.get("change"),
        "technical": tech,
        "indicators": {k: item.get(k) for k in (
            "rsi","macd","macd_signal","adx","atr","ema20","ema50","ema200",
            "sma50","bb_upper","bb_lower","high_1m","low_1m","tv_all","tv_ma","tv_osc")},
        "data_ts": item.get("ts"),
    })


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
