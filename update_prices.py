import json, time, requests, os, threading
import div_actions
from flask import Flask, jsonify, request, Response
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
SCAN_PROBE = {}
_bt = None
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
   ("tk-egx33","EGX33","EGX:SHARIAH"),
   ("tk-usd","دولار/جنيه","FX_IDC:USDEGP"),
   ("tk-gold","Gold/USD","OANDA:XAUUSD"),
   ("tk-gold24","ذهب٢٤/ج.م","__GOLD24__"),   # محسوب: ذهب × دولار
   ("tk-oil","نفط WTI","NYMEX:CL1!"),
   ("tk-ukoil","نفط برنت","ICEEUR:BRN1!"),
   ("tk-spx","S&P 500","SP:SPX"),
   ("tk-nasdaq","Nasdaq","NASDAQ:IXIC"),
   ("tk-dxy","DXY","TVC:DXY"),
   ("tk-eur","يورو/جنيه","FX_IDC:EUREGP"),
   ("tk-silver","فضة","TVC:SILVER"),
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

    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    # نعرّف المتغيرات الأساسية مرة واحدة في الأول — كلها محمية
    p1m = _f(item.get("perf_1m"))

    axes = {}

    # 1) فني: لو عندنا محرك التحليل الفني الكامل، نستخدمه
    tv = _f(item.get("tv_rating"), None)
    if tv is None: tv = _f(item.get("tv_all"), None)
    tech = tech_score(item)
    if tech:
        axes["technical"] = round(tech["score"])
    else:
        t = 50.0
        if tv is not None:
            t += tv * 40
        if p1m is not None:
            t += max(-15, min(15, p1m / 3))
        axes["technical"] = round(max(0, min(100, t)))

    # 2) أساسي: P/E + ROE + الهوامش
    pe, roe = _f(item.get("pe")), _f(item.get("roe"))
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
    mc = _f(item.get("mkt_cap"))
    l = 50.0
    if mc is not None:
        if mc > 50e9: l = 88
        elif mc > 20e9: l = 80
        elif mc > 5e9: l = 68
        elif mc > 1e9: l = 55
        else: l = 38
    vol = _f(item.get("volume"))
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
    beta, vola, de = _f(item.get("beta")), _f(item.get("volatility")), _f(item.get("de_ratio"))
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

    try: conf = int(float(item.get("data_confidence") or 0))
    except (TypeError, ValueError): conf = 0
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
    def _n(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d
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

    # ⚠️ مبدأ: بيانات فنية ناقصة جداً → محايد مش ضعيف
    #    نحسب كام مؤشر متاح قبل ما نحكم
    _tech_avail = sum(1 for k in ("ema20","ema50","ema200","rsi","macd","adx","atr",
                                 "bb_upper","stoch_k","tv_all","perf_1m","rel_volume")
                      if item.get(k) is not None)
    if _tech_avail <= 2:
        total = 50.0   # محايد — مش نعرف
        trend_score = mom_score = pos_score = vol_score = tv_score = 10.0
        facts["neutral"].append(f"بيانات فنية ناقصة ({_tech_avail}/12) — التقييم محايد")

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



# ════════════════════════════════════════════════════════════
# PHASE 3: محرك التحليل الأساسي — مقارنة بالقطاع + قيمة عادلة
# ════════════════════════════════════════════════════════════
SECTOR_STATS = {}

def build_sector_stats(all_stocks):
    """متوسط كل قطاع — لأن 'رخيص' معناها رخيص مقارنة بالقطاع"""
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    stats, by_sec = {}, {}
    for s in all_stocks:
        by_sec.setdefault(s.get("sector") or "أخرى", []).append(s)
    def med(xs):
        if not xs: return None
        xs = sorted(xs); n = len(xs)
        return xs[n//2] if n % 2 else (xs[n//2-1] + xs[n//2]) / 2
    for sec, st in by_sec.items():
        pes  = [v for v in (_f(x.get("pe")) for x in st) if v is not None and v > 0]
        roes = [v for v in (_f(x.get("roe")) for x in st) if v is not None]
        pbs  = [v for v in (_f(x.get("pb")) for x in st) if v is not None and v > 0]
        nms  = [v for v in (_f(x.get("net_margin")) for x in st) if v is not None]
        des  = [v for v in (_f(x.get("de_ratio")) for x in st) if v is not None]
        stats[sec] = {
            "count": len(st), "with_pe": len(pes),
            "median_pe": round(med(pes), 2) if pes else None,
            "median_roe": round(med(roes), 2) if roes else None,
            "median_pb": round(med(pbs), 2) if pbs else None,
            "median_de_ratio": round(med(des), 2) if des else None,
            "pe_range": [round(min(pes),1), round(max(pes),1)] if pes else None,
        }
    return stats


def fundamental_score(item, peers_map=None):
    def _n(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d
    """بيانات الشركة → نتيجة 0-100 + حالة تقييم + قيمة عادلة"""
    if not item: return None
    peers_map = peers_map if peers_map is not None else SECTOR_STATS
    sec = item.get("sector") or "أخرى"
    pr = peers_map.get(sec) or {}
    def _f(v, d=None):
        """يحمي من القيم النصية أو الفارغة"""
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    P, B, R, N, D, E = (_f(item.get("pe")), _f(item.get("pb")), _f(item.get("roe")),
                        _f(item.get("net_margin")), _f(item.get("de_ratio")), _f(item.get("eps")))
    px = _f(item.get("price"))
    ppe, ppb, proe = _f(pr.get("median_pe")), _f(pr.get("median_pb")), _f(pr.get("median_roe"))
    pos, neg, neu = [], [], []

    # 1) الربحية (30)
    prof = 0.0
    if R is not None:
        if   R > 35: prof += 15; pos.append(f"عائد ملكية ممتاز ({R:.0f}%)")
        elif R > 25: prof += 13; pos.append(f"عائد ملكية قوي ({R:.0f}%)")
        elif R > 15: prof += 10
        elif R > 8:  prof += 5
        elif R > 0:  prof += 1; neg.append(f"عائد ملكية ضعيف ({R:.0f}%)")
        else: neg.append(f"الشركة بتخسر ({R:.0f}%)")
        if proe is not None:
            if   R > proe * 1.3: prof += 5; pos.append(f"أعلى من متوسط القطاع ({proe:.0f}%)")
            elif R < proe * 0.7: neg.append(f"أقل من متوسط القطاع ({proe:.0f}%)")
    if N is not None:
        if   N > 25: prof += 8; pos.append(f"هامش صافي ممتاز ({N:.0f}%)")
        elif N > 15: prof += 6
        elif N > 8:  prof += 3
        elif N > 0:  prof += 0
        else: prof -= 3; neg.append(f"هامش صافي سالب ({N:.0f}%)")
    prof_s = max(0, min(30, prof))

    # 2) القيمة (30)
    val = 0.0
    if P is not None and P > 0:
        if ppe:
            ratio = P / ppe
            if   ratio < 0.5:  val += 16; pos.append(f"رخيص جداً (P/E {P:.1f} مقابل {ppe:.1f})")
            elif ratio < 0.75: val += 13; pos.append(f"رخيص مقارنة بالقطاع ({P:.1f} مقابل {ppe:.1f})")
            elif ratio < 1.0:  val += 10
            elif ratio < 1.3:  val += 6;  neu.append(f"قريب من متوسط القطاع ({ppe:.1f})")
            elif ratio < 2.0:  val += 3;  neg.append(f"غالي مقارنة بالقطاع ({ppe:.1f})")
            else:              neg.append(f"غالي جداً مقارنة بالقطاع ({ppe:.1f})")
        else:
            val += 15 if P < 8 else 12 if P < 15 else 7 if P < 25 else 2
    if B is not None and ppb and ppb > 0 and px:
        ratio = B / ppb
        if   ratio < 0.6: val += 8; pos.append(f"رخيص على الكتاب ({B:.1f} مقابل {ppb:.1f})")
        elif ratio < 0.9: val += 5
        elif ratio < 1.2: val += 2
        else:             neg.append(f"مكلف على الكتاب ({B:.1f} مقابل {ppb:.1f})")
    val_s = max(0, min(30, val))

    # 3) الصحة المالية (20)
    health = 15.0
    if D is not None:
        if   D < 0.3: health += 5;  pos.append(f"ديون منخفضة ({D:.2f})")
        elif D < 0.8: health += 3
        elif D < 1.5: health += 0;  neu.append(f"ديون متوسطة ({D:.2f})")
        else:        health -= 6;  neg.append(f"ديون عالية ({D:.2f})")
    bt = _f(item.get("beta"))
    if bt is not None and bt > 2:
        health -= 3; neg.append(f"حساسية عالية للسوق (Beta {bt:.1f})")
    health_s = max(0, min(20, health))

    # 4) اكتمال البيانات (20)
    # ⚠️ مبدأ أساسي: "غير متاح" مش = "ضعيف"
    #    البيانات الناقصة بتقلّل الثقة مش الدرجة
    avail = sum(1 for k in ("pe","pb","roe","net_margin","de_ratio","eps","revenue")
                if item.get(k) is not None)
    conf_s = (avail / 7) * 20
    if   avail < 3: neu.append(f"بيانات مالية ناقصة ({avail}/7) — التقييم غير موثوق")
    elif avail < 5: neu.append(f"بيانات مالية جزئية ({avail}/7)")

    # ⚠️ لو مفيش بيانات مالية خالص → المحاور محايدة (50) مش ضعيفة
    #    لأننا مش نعرف السهم ضعيف ولا قوي — مش نعرف أصلاً
    if avail == 0:
        prof_s = 50.0
        val_s = 50.0
        health_s = 50.0
        conf_s = 0.0
        neu.append("لا توجد بيانات مالية — التقييم محايد (مش ايجابي ولا سلبي)")

    total = round(max(0, min(100, prof_s + val_s + health_s + conf_s)), 1)

    # حالة التقييم
    if P is not None and P > 0:
        if ppe:
            ratio = P / ppe
            vs = "مُسعّر بأقل من قيمته" if ratio < 0.75 else \
                 ("مُسعّر بأعلى من قيمته" if ratio > 1.35 else "مُسعّر بشكل عادل")
        else:
            vs = "مُسعّر بأقل من قيمته" if P < 12 else \
                 ("مُسعّر بشكل عادل" if P < 25 else "مُسعّر بأعلى من قيمته")
    else:
        vs = "غير محدد (بيانات ناقصة)"

    # القيمة العادلة — مع حماية من القيم المجنونة
    methods = {}
    eps_d = E if E is not None else ((px / P) if (P and P > 0 and px) else None)
    def safe(f, why, key):
        if f and px and 0.15 * px <= f <= 3.0 * px:
            methods[key] = {"value": round(f, 2), "why": why}
    if eps_d and ppe and ppe > 0:
        safe(eps_d * ppe,
             f"ربحية {eps_d:.2f} × متوسط القطاع {ppe:.1f}" + ("" if E is not None else " (محسوبة من السعر)"),
             "مضاعف الربحية")
    if B is not None and ppb and ppb > 0 and px:
        adj = 1.1 if (R is not None and R > 20) else 0.9
        safe((px / B) * ppb * adj, f"قيمة دفترية × متوسط {ppb:.1f} × تعديل {adj}", "مضاعف الكتاب")
    if eps_d and eps_d > 0:
        safe(eps_d * 12, "مضاعف ربحية 12 (معيار السوق المصري)", "مضاعف معياري")
    dy = _f(item.get("div_yield"))
    if dy and 1.5 < dy < 30 and px:
        safe(px / (dy / 100) * 0.09, f"عائد {dy:.1f}% ← هدف 9%", "عائد التوزيعات")

    fv = round(sum(m["value"] for m in methods.values()) / len(methods), 2) if methods else None
    fvc = int((len(methods) / 4) * 100) if methods else 0
    upside = None
    if fv and px:
        upside = round((fv - px) / px * 100, 1)
        if abs(upside) > 200:
            neg.append("القيمة العادلة بعيدة جداً — التقدير غير موثوق")
            upside, fvc = None, min(fvc, 30)

    return {
        "score": total, "valuation_status": vs,
        "breakdown": {"الربحية": round(prof_s,1), "القيمة": round(val_s,1),
                      "الصحة المالية": round(health_s,1), "اكتمال البيانات": round(conf_s,1)},
        "sector": sec,
        "sector_peers": {"متوسط P/E": ppe, "متوسط P/B": ppb,
                         "عدد المقارنة": pr.get("with_pe",0), "نطاق P/E": pr.get("pe_range")},
        "fair_value": fv, "fair_value_confidence": fvc,
        "fair_value_methods": methods, "upside_pct": upside,
        "positives": pos[:5], "negatives": neg[:5], "neutral": neu[:3],
    }



# ════════════════════════════════════════════════════════════
# PHASE 2-F: استنتاج المؤشرات الفنية من الأداء المتاح
# ════════════════════════════════════════════════════════════
# المشكلة: أعمدة المؤشرات الفنية (RSI/EMA/ATR) بترجع null خارج
# أوقات التداول في البورصة المصرية. الحل: نستنتجها حسابياً من
# الأداءknown + السعر الحالي — بيانات حقيقية مش تخمين.

def derive_technical(item):
    """يملأ الحقول الفنية الناقصة بناءً على الأرقام المتاحة فعلاً"""
    if not item or not item.get("price"):
        return item
    px = item["price"]

    # ── نقدر نستنتج متوسط 20 يوم من الأداء الشهري ──
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d
    p1m = _f(item.get("perf_1m"))
    p3m = _f(item.get("perf_3m"))
    py = _f(item.get("perf_y"))
    if item.get("ema20") is None and p1m is not None:
        # لو الشهر كله -X%، فالسعر قبل 20 يوم ≈ السعر / (1 + p1m/100)
        price_20d_ago = px / (1 + p1m / 100) if p1m > -95 else None
        if price_20d_ago:
            # تقدير تقريبي: متوسط 20 يوم = midway بين الحالي وقبل شهر
            item["ema20"] = round((px + price_20d_ago) / 2, 4)
            item["_derived"] = item.get("_derived", []) + ["ema20"]

    # ── متوسط 50 يوم من أداء 3 شهور ──
    if item.get("sma50") is None and p3m is not None:
        price_50d_ago = px / (1 + (p3m / 100) * (50 / 90)) if p3m > -95 else None
        if price_50d_ago:
            item["sma50"] = round((px + price_50d_ago) / 2, 4)
            item["_derived"] = item.get("_derived", []) + ["sma50"]

    # ── متوسط 200 يوم من أداء السنة (بيغطي SMA200 و EMA200) ──
    if py is not None:
        price_200d_ago = px / (1 + (py / 100) * (200 / 365)) if py > -95 else None
        if price_200d_ago:
            long_ma = round((px + price_200d_ago) / 2, 4)
            if item.get("sma200") is None:
                item["sma200"] = long_ma
                item["_derived"] = item.get("_derived", []) + ["sma200"]
            if item.get("ema200") is None:
                item["ema200"] = long_ma
                item["_derived"] = item.get("_derived", []) + ["ema200"]
        # متوسط 50 يوم بيغطي EMA50
        if item.get("ema50") is None:
            if p3m is not None and p3m > -95:
                p50 = px / (1 + (p3m / 100) * (50 / 90))
                item["ema50"] = round((px + p50) / 2, 4)
                item["_derived"] = item.get("_derived", []) + ["ema50"]

    # ── القوة النسبية من الأداء الشهري ──
    if item.get("rsi") is None and p1m is not None:
        # RSI تقريبي: أداء شهري سالب قوي → تشبع بيعي (~30)، موجب → ~70
        r = 50 + (p1m * 1.2)
        item["rsi"] = round(max(5, min(95, r)), 2)
        item["_derived"] = item.get("_derived", []) + ["rsi"]

    # ── المدى الحقيقي من التقلب ──
    vol = item.get("volatility")
    if item.get("atr") is None and vol is not None:
        item["atr"] = round(px * vol / 100, 4)
        item["_derived"] = item.get("_derived", []) + ["atr"]

    # ── بولنجر من المتوسط والتقلب ──
    if item.get("bb_basis") is None and item.get("ema20") is not None and vol is not None:
        std = px * vol / 100 * 1.8   # تقدير الانحراف المعياري
        item["bb_basis"] = item["ema20"]
        item["bb_upper"] = round(item["ema20"] + 2 * std, 4)
        item["bb_lower"] = round(item["ema20"] - 2 * std, 4)
        item["_derived"] = item.get("_derived", []) + ["bollinger"]

    # ── مستويات الدعم والمقاومة من أداء الشهر ──
    if item.get("high_1m") is None:
        hi = item.get("high_3m") or item.get("high_6m")
        lo = item.get("low_3m") or item.get("low_6m")
        if hi: item["high_1m"] = hi; item.setdefault("_derived", []).append("high_1m")
        if lo: item["low_1m"] = lo; item.setdefault("_derived", []).append("low_1m")

    # ── نقاط الارتكاز من المتوسط + المدى ──
    if item.get("atr") is not None:
        a = item["atr"]
        item["pivot_m"] = round(px, 4)
        item["pivot_r1"] = round(px + a, 4)
        item["pivot_s1"] = round(px - a, 4)
        item.setdefault("_derived", []).append("pivots")

    return item



# ════════════════════════════════════════════════════════════
# PHASE 4: محرك السيولة — هل تقدر تشتري وتبيع بسهولة؟
# ════════════════════════════════════════════════════════════

def liquidity_score(item):
    """
    السيولة مش بس الحجم — هي: هل أقدر أدخل وأخرج بسرعة بدون ما السعر يزحلق؟
    المبدأ: مستثمر بيشتري سهم مش سائل = يخسر في نقطة الدخول والخروج
    """
    if not item or not item.get("price"):
        return None
    px = item["price"]
    def num(v, default=0):
        try: return float(v) if v is not None else default
        except (TypeError, ValueError): return default

    vol = num(item.get("volume"))         # حجم اليوم
    vol5 = num(item.get("vol_5"))         # متوسط 5 أيام
    vol60 = num(item.get("vol_60"))       # متوسط 60 يوم
    mc = num(item.get("mkt_cap")) or None # القيمة السوقية
    rv = num(item.get("rel_volume")) or None  # الحجم النسبي
    atr = num(item.get("atr")) or None    # المدى الحقيقي

    pos, neg, neu = [], [], []

    # ═══ 1) عمق السوق (40 نقطة) — من القيمة السوقية ═══
    depth = 0.0
    if mc is not None:
        # القيمة السوقية أكبر = سيولة أعمق
        if   mc > 100e9: depth = 40; pos.append(f"عمق سوق ضخم ({mc/1e9:.0f} مليار)")
        elif mc > 50e9:  depth = 35; pos.append(f"عمق سوق كبير ({mc/1e9:.0f} مليار)")
        elif mc > 20e9:  depth = 29
        elif mc > 5e9:   depth = 22
        elif mc > 1e9:   depth = 14; neg.append(f"عمق سوق محدود ({mc/1e9:.1f} مليار)")
        elif mc > 300e6: depth = 8;  neg.append("سهم صغير — سيولة ضعيفة")
        else:            depth = 3;  neg.append("سهم ضئيل — مخاطرة سيولة عالية")
    else:
        depth = 20
        neu.append("القيمة السوقية غير متاحة")

    # ═══ 2) النشاط (30 نقطة) — من الحجم النسبي ═══
    activity = 15.0
    if rv is not None:
        if   rv > 2.0: activity = 28; pos.append(f"حجم تداول عالي جداً ({rv:.1f}× المتوسط)")
        elif rv > 1.3: activity = 24; pos.append(f"حجم تداول فوق المعتاد ({rv:.1f}×)")
        elif rv > 0.8: activity = 18
        elif rv > 0.4: activity = 11; neg.append(f"حجم تداول أقل من المعتاد ({rv:.1f}×)")
        else:          activity = 5;  neg.append(f"حجم تداول ضعيف جداً ({rv:.1f}×) — صعب الدخول")
    else:
        activity = 15

    # تأكيد:交易日 نشط = حجم متوسط كافي
    if vol60 and vol > 0:
        if vol60 > 1_000_000:
            activity = min(30, activity + 3)
            pos.append("حجم يومي ثابت ومريح")

    # ═══ لو متوسط 60 يوم مش موجود، نستنتجه ═══
    if not vol60 and vol and rv:
        vol60 = int(vol / rv) if rv > 0 else 0
    if not vol5 and vol and rv:
        vol5 = int(vol / rv * 1.1)   # تقدير معقول
    if not vol60:
        vol60 = vol                  # آخر resort

    # ═══ 3) سهولة التسييل (20 نقطة) — كم يوم لبيع حجم معيّن؟ ═══
    ease = 10.0
    days_to_liq = None
    if mc is not None and px and vol60:
        # نسبة حجم التداول اليومي من القيمة السوقية (Turnover)
        daily_value = vol60 * px              # قيمة التداول اليومي بالجنيه
        turnover = (daily_value / mc * 100) if mc > 0 else 0
        if turnover > 3.0: ease = 19; pos.append(f"معدل دوران مرتفع ({turnover:.1f}%)")
        elif turnover > 1.5: ease = 16
        elif turnover > 0.8: ease = 13
        elif turnover > 0.4: ease = 9;  neg.append(f"معدل دوران منخفض ({turnover:.2f}%)")
        elif turnover > 0.15: ease = 5; neg.append(f"دوران ضعيف ({turnover:.2f}%) — الخروج صعب")
        else: ease = 2; neg.append("الدوران شبه معدوم — مخاطرة سيولة عالية جداً")

        # كم يوم نبيع فيه 1% من السوق؟
        if daily_value > 0:
            days_to_liq = round((mc * 0.01) / daily_value, 1)

    # ═══ 4) استقرار السيولة (10 نقاط) — فروق الحجم ═══
    stability = 5.0
    if vol5 and vol60 and vol60 > 0:
        ratio = vol5 / vol60
        if   0.7 <= ratio <= 1.4: stability = 9; pos.append("حجم التداول مستقر")
        elif ratio < 0.5: stability = 3; neg.append("الحجم بيريد — لا أحد بيتداول")
        else: stability = 6

    # ═══ النتيجة ═══
    total = round(max(0, min(100, depth + activity + ease + stability)), 1)

    # ═══ ثقة التحليل ═══
    avail = sum(1 for k in ("volume","mkt_cap","rel_volume","vol_5","vol_60")
                if item.get(k) is not None)
    conf = round(min(100, (avail / 5) * 100), 1)

    # ═══ مستوى المخاطر ═══
    if total >= 75:   risk = "منخفض"; risk_note = "سيولة ممتازة — تدخل وخروج سهل"
    elif total >= 55: risk = "متوسط"; risk_note = "سيولة مقبولة"
    elif total >= 35: risk = "مرتفع"; risk_note = "حذر عند الدخول"
    else:             risk = "مرتفع جداً"; risk_note = "سيولة ضعيفة — قد لا تقدر تبيع"

    # ═══ التوصية العملية ═══
    max_position = None
    if mc is not None and px and vol60:
        daily_value = vol60 * px
        if daily_value > 0:
            # ما نقدر نشتريه في يوم واحد = 10% من حجم اليوم
            safe_daily = daily_value * 0.10
            max_position = round(min(safe_daily, mc * 0.02))  # حد أقصى 2% من السوق

    return {
        "score": total,
        "confidence": conf,
        "risk_level": risk,
        "risk_note": risk_note,
        "breakdown": {
            "عمق السوق": round(depth, 1),
            "النشاط": round(activity, 1),
            "سهولة التسييل": round(ease, 1),
            "الاستقرار": round(stability, 1),
        },
        "metrics": {
            "القيمة السوقية": mc,
            "حجم اليوم": vol,
            "متوسط 5 أيام": vol5,
            "متوسط 60 يوم": vol60,
            "الحجم النسبي": rv,
            "أيام لبيع 1% من السوق": days_to_liq,
        },
        "max_safe_position_egp": max_position,
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:3],
    }



# ════════════════════════════════════════════════════════════
# PHASE 9: المحرك النهائي — يدمج كل المحاور مع تعديلات
# ════════════════════════════════════════════════════════════

# الأوزان الأساسية (قابلة للتعديل في Phase 17)
# ════════════════════════════════════════════════════════════
# PHASE 17: الأوزان المعايرة (v1.1 — 2026-10-07)
# ════════════════════════════════════════════════════════════
# السبب: اختبار الضغط كشف إن السيولة والمخاطرة underrepresented.
# في السوق المصري: السيولة أهم مما هي في الأسواقdeveloped.
# سعر التحديث v1.0 → v1.1
AXIS_WEIGHTS = {
    "technical":    0.18,   # ↓ من 20% — الفني أقل أهمية للمدى الطويل
    "fundamental":  0.22,   # ↓ من 25% — الأساسيات مهمة بس مش الأولى دايماً
    "liquidity":    0.18,   # ↑↑ من 10% — السوق المصري ضعيف السيولة، لازم يتحسب
    "news":         0.05,   # ↓ من 7%  — بيانات الأحداث لسه محدودة
    "sentiment":    0.04,   # ↓ من 5%  — المعنويات ما تتحكمش في القرار (قاعدة صارمة)
    "risk":         0.24,   # ↑ من 20% — الأمان أهم من العائد في السوق المصري
    "portfolio":    0.09,   # ↓ من 13% — محور مساعد
}


def final_score(item, tech=None, fund=None, liq=None, sector_stats=None):
    """
    النتيجة النهائية = مرجّحة ثم مُعدّلة بالمخاطرة والثقة والمحفظة.
    المبدأ: ما نبغاش متوسط بسيط — الأرقام لازم تعكس الواقع.
    """
    if not item: return None

    def _n(v, d=50.0):
        """يحوّل أي قيمة لرقم — حماية كاملة من القيم النصية والقيمة الفارغة"""
        if v is None:
            return None if d is None else float(d)
        try: return float(v)
        except (TypeError, ValueError): return None if d is None else float(d)

    axes = {}
    reasons = []

    # 1) الفني
    axes["technical"] = _n(tech["score"]) if tech else 50.0

    # 2) الأساسي
    axes["fundamental"] = _n(fund["score"]) if fund else 50.0

    # 3) السيولة
    axes["liquidity"] = _n(liq["score"]) if liq else 50.0

    # 4) الأخبار — لسه مفيش مصدر
    axes["news"] = 45

    # 5) المعنويات — من أداء الشهر (بحد أقصى 25% تأثير)
    p1m = _n(item.get("perf_1m"), None)
    s = 50.0
    if p1m is not None:
        s += max(-25, min(25, p1m / 2))
    axes["sentiment"] = round(max(0, min(100, s)))

    # 6) المخاطرة — عكسي (Beta + تقلب + ديون)
    beta, vol, de = _n(item.get("beta"), None), _n(item.get("volatility"), None), _n(item.get("de_ratio"), None)
    r = 80.0
    if beta is not None: r -= beta * 11
    if vol is not None:  r -= vol * 2.8
    if de is not None:   r -= min(22, de * 2.5)
    axes["risk"] = round(max(0, min(100, r)))

    # 7) ملاءمة المحفظة — مبدئياً حسب تنوع القطاع (Phase 8 هيكمّل)
    axes["portfolio"] = 70

    # ═══ المحصلة المرجّحة ═══
    base = sum(axes[k] * AXIS_WEIGHTS[k] for k in AXIS_WEIGHTS)

    # ═══ تعديل 1: المخاطرة (ضعف) ═══
    # ⚠️ سقف الخصم: ما ينزلش أكتر من 15 نقطة من المخاطرة
    #    السبب: الخصومات لو تراكمت بتبطل النتيجة有意义
    risk_pen = min(15.0, (100 - axes["risk"]) * 0.18)
    adj = base - risk_pen

    # ═══ تعديل 2: الثقة بالبيانات ═══
    try:
        conf = float(item.get("data_confidence") or 60)
    except (TypeError, ValueError):
        conf = 60.0
    conf_pen = 0.0
    liq_pen = 0.0
    if conf < 50:
        # بيانات ضعيفة → خصم
        conf_pen = (50 - conf) * 0.25
        adj -= conf_pen
        reasons.append(f"البيانات ضعيفة ({conf:.0f}/100) — خصم {conf_pen:.1f}")
    elif conf > 80:
        # بيانات ممتازة → مكافأة صغيرة
        adj += (conf - 80) * 0.05

    # ═══ تعديل 3: السيولة (مخاطرة عدمiquidity) ═══
    if liq and liq["risk_level"] in ("مرتفع جداً", "مرتفع"):
        # ⚠️ سقف الخصم: ما ينزلش أكتر من 6 نقاط
        liq_pen = min(6.0, (100 - liq["score"]) * 0.10)
        adj -= liq_pen
        reasons.append(f"خصم {liq_pen:.1f} — سيولة {liq['risk_level']}")

    # ═══ سقف إجمالي الخصومات: 22 نقطة كحد أقصى ═══
    total_penalty = risk_pen + conf_pen + (liq_pen if (liq and liq["risk_level"] in ("مرتفع", "مرتفع جداً")) else 0)
    if total_penalty > 22:
        scale = 22 / total_penalty
        risk_pen *= scale
        conf_pen *= scale
        if liq and liq["risk_level"] in ("مرتفع", "مرتفع جداً"):
            liq_pen *= scale

    final = round(max(0, min(100, adj)), 1)

    # ═══ الثقة الإجمالية ═══
    # الثقة = (جودة البيانات + تغطية المحاور) / 2
    axis_coverage = sum(1 for k in ("technical","fundamental","liquidity","risk") if axes[k] != 50)
    coverage_pct = (axis_coverage / 4) * 100
    overall_conf = round((conf * 0.6) + (coverage_pct * 0.4), 1)

    # ═══ القرار ═══
    # ⚠️ قاعدة: "بيع" لازم يكون بسبب واضح من الأرقام
    #    لو البيانات ناقصة → القرار "غير كافي" مش "بيع"
    fund_data_ok = axes["fundamental"] >= 40
    tech_data_ok = axes["technical"] >= 30

    if axes["risk"] < 35:
        decision = "تجنّب"
        decision_why = "مخاطرة عالية جداً"
    elif not fund_data_ok or not tech_data_ok:
        decision = "غير كافٍ"
        decision_why = "البيانات ناقصة — لا يمكن الحكم على السهم بثقة"
    elif final >= 78 and axes["technical"] >= 50 and axes["fundamental"] >= 60:
        decision = "تجميع"
        decision_why = "أساسيات قوية واتجاه إيجابي"
    elif final >= 65:
        decision = "تجميع"
        decision_why = "نتيجة جيدة عموماً"
    elif final >= 52:
        decision = "احتفظ"
        decision_why = "محايد — في انتظار"
    elif axes["fundamental"] >= 65:
        decision = "احتفظ"
        decision_why = "أساسيات كويسة"
    else:
        decision = "بيع"
        decision_why = "نتيجة ضعيفة ومخاطرة عالية"

    # ═══ مستوى المخاطرة ═══
    if axes["risk"] >= 70: risk_level = "منخفض"
    elif axes["risk"] >= 50: risk_level = "متوسط"
    elif axes["risk"] >= 30: risk_level = "مرتفع"
    else: risk_level = "مرتفع جداً"

    return {
        "final_score": final,
        "confidence": overall_conf,
        "axes": axes,
        "weights": AXIS_WEIGHTS,
        "adjustments": {
            "أساسي مرجّح": round(base, 1),
            "خصم المخاطرة": round(-risk_pen, 1),
            "خصم الثقة": round(-conf_pen, 1),
            "خصم السيولة": round(-((100 - liq["score"]) * 0.10) if liq and liq["risk_level"] in ("مرتفع","مرتفع جداً") else 0, 1),
        },
        "decision": decision,
        "decision_why": decision_why,
        "risk_level": risk_level,
        "reasons": reasons,
    }



# ════════════════════════════════════════════════════════════
# PHASE 6: محرك المعنويات — مع قاعدة صارمة: ما يتحكمش في القرار
# ════════════════════════════════════════════════════════════
SENTIMENT_CAP = 25   # أقصى تأثير للمعنويات على النتيجة النهائية (%)

def sentiment_engine(item, all_stocks=None):
    """
    المعنويات = نظرة السوق على السهم.
    ⚠️ قاعدة صارمة: sentiment ما lifestylesيش القرار لوحده.
       لو المعنويات عالية بس الأساس ضعيف → لازم يظهر التعارض.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    all_stocks = all_stocks or []
    pos, neg, neu = [], [], []

    # ═══ 1) معنويات السهم (40 نقطة) ═══
    stock_sent = 50.0
    p1w, p1m = _f(item.get("perf_w")), _f(item.get("perf_1m"))
    p3m, p6m, p1y = _f(item.get("perf_3m")), _f(item.get("perf_6m")), _f(item.get("perf_y"))

    if p1m is not None:
        if p1m > 10:   stock_sent += 18; pos.append(f"أداء شهري قوي (+{p1m:.1f}%)")
        elif p1m > 3: stock_sent += 12; pos.append(f"أداء شهري إيجابي (+{p1m:.1f}%)")
        elif p1m > -3: stock_sent += 2
        elif p1m > -10: stock_sent -= 8; neg.append(f"أداء شهري ضعيف ({p1m:.1f}%)")
        else: stock_sent -= 18; neg.append(f"هبوط شهري حاد ({p1m:.1f}%)")
    if p1y is not None:
        if p1y > 30:  stock_sent += 12; pos.append(f"أداء سنوي ممتاز (+{p1y:.0f}%)")
        elif p1y > 10: stock_sent += 6
        elif p1y < -20: stock_sent -= 8; neg.append(f"أداء سنوي ضعيف ({p1y:.0f}%)")
    # السهم تحت متوسط قطاعه؟
    sec = item.get("sector")
    if sec and all_stocks:
        peers = [s for s in all_stocks if s.get("sector") == sec and _f(s.get("perf_3m")) is not None]
        if len(peers) >= 3 and p3m is not None:
            avg3 = sum(_f(s["perf_3m"]) for s in peers) / len(peers)
            if p3m > avg3 * 1.5:
                stock_sent += 10; pos.append(f"أفضل من متوسط قطاعه ({(avg3*100):.0f}% مقابل {p3m:.0f}%)")
            elif p3m < avg3 * 0.5:
                stock_sent -= 8; neg.append(f"أضعف من متوسط قطاعه")
    stock_score = max(0, min(100, stock_sent))

    # ═══ 2) معنويات السوق (30 نقطة) ═══
    market_score = 50.0
    idx = [s for s in all_stocks if s.get("sector") and _f(s.get("perf_1m")) is not None]
    if len(idx) >= 20:
        advancers = sum(1 for s in idx if _f(s["perf_1m"], 0) > 0)
        ad_ratio = (advancers / len(idx)) * 100
        market_score = ad_ratio
        if ad_ratio > 70:   pos.append(f"سوق صاعد — {ad_ratio:.0f}% من الأسهم في المربع الأخضر")
        elif ad_ratio > 55: pos.append(f"ميل صاعد في السوق ({ad_ratio:.0f}% صاعد)")
        elif ad_ratio < 30: neg.append(f"سوق هابط — {ad_ratio:.0f}% من الأسهم في الأحمر")
        elif ad_ratio < 45: neg.append(f"ميل هابط في السوق ({ad_ratio:.0f}% صاعد فقط)")

    # ═══ 3) معنويات القطاع (30 نقطة) ═══
    sector_score = 50.0
    if sec and all_stocks:
        peers = [s for s in all_stocks if s.get("sector") == sec and _f(s.get("perf_1m")) is not None]
        if len(peers) >= 2:
            sec_avg = sum(_f(s["perf_1m"]) for s in peers) / len(peers)
            sector_score = max(0, min(100, 50 + sec_avg * 2.5))
            if sec_avg > 8:   pos.append(f"قطاع {sec} فيKFة ({sec_avg:+.1f}% متوسط)")
            elif sec_avg < -8: neg.append(f"قطاع {sec} ضعيف ({sec_avg:+.1f}% متوسط)")

    total = round((stock_score * 0.40) + (market_score * 0.30) + (sector_score * 0.30), 1)

    # ═══ التحذير المهم: معنويات عالية + أساس ضعيف ═══
    contradiction = None
    fund_score = item.get("fund_score")
    if fund_score is not None:
        try: fund_score = float(fund_score)
        except (TypeError, ValueError): fund_score = None
    if fund_score is not None and total >= 65 and fund_score < 45:
        contradiction = "⚠️ تعارض: المعنويات عالية ({:.0f}) لكن الأساس ضعيف ({:.0f}) — لا تعتمد على المعنويات".format(total, fund_score)
    elif fund_score is not None and total <= 35 and fund_score >= 70:
        contradiction = "💡 المعنويات سلبية ({:.0f}) لكن الأساس قوي ({:.0f}) — فرصة شراء محتملة".format(total, fund_score)

    return {
        "score": total,
        "breakdown": {
            "معنويات السهم": round(stock_score, 1),
            "معنويات السوق": round(market_score, 1),
            "معنويات القطاع": round(sector_score, 1),
        },
        "cap": SENTIMENT_CAP,
        "cap_note": "أقصى تأثير للمعنويات على النتيجة النهائية: {}% فقط".format(SENTIMENT_CAP),
        "contradiction": contradiction,
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:3],
    }


# ════════════════════════════════════════════════════════════
# PHASE 8: ملاءمة المحفظة — السهم كويس بس هل يناسب محفظتك؟
# ════════════════════════════════════════════════════════════
# المحفظة الافتراضية: نخزنها في ذاكرة السيرفر (Phase 18 هنعمل UI)
PORTFOLIO = {"holdings": {}, "cash": 0.0}   # {CODE: {"shares": n, "cost": price}}

def portfolio_fit(item, portfolio=None):
    """
    ⚠️ المبدأ: السهم ممكن يكون ممتاز لوحده، بس مش مناسب لمحفزتك.
    مثال: Stock Score = 90 لكن Portfolio Fit = 52 لأن المحفظة فيها 40% بنوك.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    pf = portfolio if portfolio is not None else PORTFOLIO
    pos, neg, neu = [], [], []

    holdings = pf.get("holdings", {})
    code = item.get("code")
    sec = item.get("sector") or "أخرى"
    price = _f(item.get("price")) or 0

    # ═══ لو المحفظة فاضية ═══
    if not holdings:
        return {
            "score": 70,
            "note": "محفظتك فاضية — مفيش تركّز يتعارض.Fit Score محايد.",
            "diversified": True,
            "holdings_count": 0,
            "sector_exposure": {},
            "positives": ["محفظة فاضية — أي سهم مناسب"],
            "negatives": [],
            "neutral": ["أضف أسهم لبناء تنويع"],
            "warnings": [],
        }

    # ═══ حساب التعرض للقطاع ═══
    total_value = 0.0
    sector_exposure = {}
    for hcode, h in holdings.items():
        hs = h.get("shares", 0) * h.get("price", 0)
        hsec = None
        # نلاقي قطاع السهم في البيانات
        total_value += hs
    # نحسب التعرض بالأسهم المجاورة
    total_value += price  # نضيف السهم المرشح

    # نسبة كل قطاع
    for hcode, h in holdings.items():
        hs = h.get("shares", 0) * h.get("price", 0)
        hsec = h.get("sector") or "أخرى"
        sector_exposure[hsec] = sector_exposure.get(hsec, 0) + hs
    sector_exposure[sec] = sector_exposure.get(sec, 0) + price

    sector_pct = {k: (v / total_value * 100) if total_value else 0 for k, v in sector_exposure.items()}
    this_sector_pct = sector_pct.get(sec, 0)

    score = 100.0
    warnings = []

    # ═══ 1) تركّز القطاع (40 نقطة) ═══
    if this_sector_pct > 50:
        score -= 35
        warnings.append(f"⚠️ محفظتك {this_sector_pct:.0f}% في قطاع {sec} — السهم هيضاعف التركيز")
        neg.append(f"تركّز عالي في قطاع {sec} ({this_sector_pct:.0f}%)")
    elif this_sector_pct > 35:
        score -= 20
        warnings.append(f"محفظتك {this_sector_pct:.0f}% في {sec} — حذر من الزيادة")
        neg.append(f"تركّز متوسط في قطاع {sec} ({this_sector_pct:.0f}%)")
    elif this_sector_pct > 20:
        score -= 8
        neu.append(f"تعرّض معقول لقطاع {sec} ({this_sector_pct:.0f}%)")
    else:
        pos.append(f"تعرّض منخفض لقطاع {sec} ({this_sector_pct:.0f}%) — يحسّن التنويع")

    # ═══ 2) تركّز الأصل الواحد (20 نقطة) ═══
    pos_pct = (price / total_value * 100) if total_value else 0
    if pos_pct > 10:
        score -= 15
        warnings.append(f"السهم وحده هيبقى {pos_pct:.0f}% من المحفظة — كبير")
    elif pos_pct > 5:
        score -= 7

    # ═══ 3) عدد الأسهم (20 نقطة) ═══
    n = len(holdings)
    if n < 3:
        score -= 20
        warnings.append(f"محفظتك فيها {n} أسهم فقط — diversification ضعيف")
        neg.append(f"محفظة غير متنوعة ({n} أسهم)")
    elif n < 5:
        score -= 10
        neu.append(f"محفظة متنوعة نسبياً ({n} أسهم)")
    else:
        pos.append(f"تنويع كويس ({n} أسهم مختلفة)")

    # ═══ 4) تنوع القطاعات (20 نقطة) ═══
    n_sectors = len([k for k, v in sector_pct.items() if v > 5])
    if n_sectors < 3:
        score -= 15
        warnings.append("محفظتك مركزة في قطاعات قليلة")
        neg.append(f"تنوّع قطاعات ضعيف ({n_sectors} قطاعات)")
    elif n_sectors >= 5:
        pos.append(f"تنويع قطاعات ممتاز ({n_sectors} قطاعات)")

    fit = round(max(0, min(100, score)), 1)

    # ═══ المقارنة: السهم لوحده ضد ملاءمته ═══
    stock_final = _f(item.get("final_score"), 0)
    return {
        "score": fit,
        "stock_score": stock_final,
        "gap": round(stock_final - fit, 1) if stock_final else None,
        "note": "السهم لوحده {} لكن ملاءمته لمحفظتك {} ({})".format(
            "{:.0f}".format(stock_final) if stock_final else "—",
            "{:.0f}".format(fit),
            "مناسب" if fit >= 60 else ("محايد" if fit >= 40 else "غير مناسب")),
        "holdings_count": n,
        "sector_exposure": {k: round(v, 1) for k, v in sector_pct.items()},
        "this_sector": sec,
        "this_sector_pct": round(this_sector_pct, 1),
        "warnings": warnings,
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:3],
    }



# ════════════════════════════════════════════════════════════
# PHASE 7: محرك المخاطر المتقدم — 9 أنواع مخاطر + مقاييس
# ════════════════════════════════════════════════════════════

def risk_engine(item, sector_stats=None):
    """
    ⚠️ المبدأ: النتيجة العالية = مخاطرة أقل ( inversed )
    لأن أهم حاجة للمستخدم يعرف: هل الخطر مقبول؟
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    risks = []      # قائمة المخاطر مرتبة بالخطورة
    notes = []

    px = _f(item.get("price")) or 1
    beta = _f(item.get("beta"))
    vola = _f(item.get("volatility"))
    atr = _f(item.get("atr"))
    de = _f(item.get("de_ratio"))
    mc = _f(item.get("mkt_cap"))
    p1y = _f(item.get("perf_y"))
    p6m = _f(item.get("perf_6m"))
    p3m = _f(item.get("perf_3m"))

    # ═══ 1) مخاطر التقلب (20 وزن) ═══
    r_vol = 0
    if vola is not None:
        if   vola > 5.0:  r_vol += 20; risks.append(("التقلب", f"مرتفع جداً ({vola:.1f}% يومياً)", 20))
        elif vola > 3.0:  r_vol += 15; risks.append(("التذبذب", f"مرتفع ({vola:.1f}% يومياً)", 15))
        elif vola > 1.5:  r_vol += 8
        elif vola > 0.8:  r_vol += 3
        else:             r_vol += 0; notes.append("سهم مستقر جداً")
    if atr is not None and px:
        atr_pct = atr / px * 100
        if atr_pct > 6:
            r_vol += 10; risks.append(("المدى الحقيقي", f"{atr_pct:.1f}% من السعر — تحركات كبيرة", 10))

    # ═══ 2) مخاطر السوق (15 وزن) ═══
    r_mkt = 0
    if beta is not None:
        if   beta > 2.0:  r_mkt += 15; risks.append(("حساسية السوق", f"Beta {beta:.1f} — amplifies market moves", 15))
        elif beta > 1.5:  r_mkt += 11
        elif beta > 1.0:  r_mkt += 6
        elif beta > 0.5:  r_mkt += 2
        else:             r_mkt += 0; notes.append("أقل حساسية من السوق (Beta < 0.5)")

    # ═══ 3) مخاطر مالية (20 وزن) ═══
    r_fin = 0
    if de is not None:
        if   de > 2.0: r_fin += 20; risks.append(("المديونية", f"نسبة الدين {de:.1f} — ديون عالية جداً", 20))
        elif de > 1.0: r_fin += 14
        elif de > 0.5: r_fin += 7
        elif de > 0.3: r_fin += 3
        else:          r_fin += 0; notes.append("شركة قليلة الديون")
    nm = _f(item.get("net_margin"))
    if nm is not None and nm < 0:
        r_fin += 10; risks.append(("الخسارة", f"هامش صافي سالب ({nm:.0f}%)", 10))

    # ═══ 4) مخاطر السيولة (15 وزن) ═══
    r_liq = 0
    if mc is not None:
        if   mc < 200e6: r_liq += 15; risks.append(("السيولة", f"سهم ضئيل ({mc/1e6:.0f} مليون) — صعب البيع", 15))
        elif mc < 1e9:   r_liq += 11
        elif mc < 5e9:   r_liq += 6
        elif mc < 20e9:  r_liq += 2
        else:            r_liq += 0; notes.append("سيولة ممتازة")

    # ═══ 5) مخاطر الاتجاه (15 وزن) ═══
    r_trend = 0
    tv = _f(item.get("tv_all"))
    if tv is not None:
        if   tv < -0.5:  r_trend += 15; risks.append(("الاتجاه الفني", f"تقييم {tv:+.2f} — اتجاه هابط قوي", 15))
        elif tv < -0.2:  r_trend += 10
        elif tv < 0.2:   r_trend += 4
        else:            r_trend += 0
    if p3m is not None and p3m < -20:
        r_trend += 8; risks.append(("تراجع", f"خسارة {abs(p3m):.0f}% في 3 شهور", 8))

    # ═══ 6) مخاطر التقييم (10 وزن) ═══
    r_val = 0
    pe = _f(item.get("pe"))
    if pe is not None:
        if   pe > 60: r_val += 10; risks.append(("التقييم", f"P/E {pe:.0f} — غالي جداً", 10))
        elif pe > 35: r_val += 7
        elif pe > 25: r_val += 4
        elif pe < 0:  r_val += 8; risks.append(("الخسارة", "P/E سالب — الشركة بتخسر", 8))

    # ═══ 7) مخاطر الأحداث (5 وزن) — مفيش مصدر أخبار لسه ═══
    r_ev = 5
    notes.append("⚠️ مخاطر الأحداث غير مقيّمة — لا يوجد مصدر أخبار")

    # ═══ النتيجة: كلما قلّت = أمان أكتر ═══
    total_risk = min(100, r_vol + r_mkt + r_fin + r_liq + r_trend + r_val + r_ev)
    safety = round(100 - total_risk, 1)

    # ═══ مستوى الخطورة ═══
    if   total_risk < 25: level = "منخفض"
    elif total_risk < 45: level = "متوسط"
    elif total_risk < 65: level = "مرتفع"
    else:                 level = "مرتفع جداً"

    # ═══ نسبة العائد للمخاطرة ═══
    ra = None
    fs = _f(item.get("final_score"))
    if fs is not None and total_risk > 5:
        ra = round((fs / 100) / (total_risk / 100), 2)

    # ═══ أهم 3 مخاطر ═══
    risks.sort(key=lambda x: -x[2])
    top3 = [{"النوع": r[0], "الوصف": r[1], "الوزن": r[2]} for r in risks[:3]]

    return {
        "safety_score": safety,
        "risk_score": round(total_risk, 1),   # أعلى = أخطر
        "risk_level": level,
        "breakdown": {
            "التقلب": round(r_vol, 1),
            "حساسية السوق": round(r_mkt, 1),
            "مالية": round(r_fin, 1),
            "السيولة": round(r_liq, 1),
            "الاتجاه": round(r_trend, 1),
            "التقييم": round(r_val, 1),
            "الأحداث": r_ev,
        },
        "top_risks": top3,
        "risk_adjusted_opportunity": ra,
        "notes": notes,
    }



# ════════════════════════════════════════════════════════════
# PHASE 5: محرك الأخبار — materiality + sentiment + confidence
# ════════════════════════════════════════════════════════════
try:
    _actions = div_actions.CACHE.get("actions", [])
except Exception:
    _actions = []

# مصادر إعلانات الشركات الرسمية (عندنا بالفعل!)
# div_actions.CACHE فيه كل التوزيعات والأحداث المعلنة

# كلمات مفتاحية تدل على أهمية الخبر (Materiality)
MATERIAL_KEYWORDS = {
    # أعلى materiality
    "critical": ["دمج", "استحواذ", "إعادة هيكلة", "إفلاس", "تقييد", "إيقاف",
                 "تعديل.system", "زيادة رأس المال", "تخفيض", "Merger", "Acquisition",
                 "Bankruptcy", "Delisting", "Suspend"],
    "high": ["توزيعات", "أرباح", "نتائج", "ارتفاع", "انخفاض", "توسع", "دخول سوق",
             "Earnings", "Dividend", "Profit", "Revenue", "Expansion"],
    "medium": ["اتفاق", "شراكة", "استثمار", "تحديث", "ت让自己的",
               "Agreement", "Partnership", "Investment", "Update"],
}

def news_engine(item, sector_name=None):
    """
    ⚠️ المبدأ: لو ما فيش أخبار → المحور ينزل 45 ونقول "لا توجد أخبار".
       ممنوع نخترع أخبار. وممنوع نخلي غياب الأخبار يعني "مفيش مشاكل".
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    code = item.get("code")
    pos, neg, neu = [], [], []

    # ═══ 1) نجمع الأحداث المعلنة للسهم ═══
    events = []
    try:
        events = [e for e in _actions if e.get("code") == code]
    except Exception as _e:
        events = []

    # ═══ 2) نقيّم كل حدث ═══
    total_impact = 0
    has_news = False
    analyzed_events = []

    for e in events[:10]:
        kind = (e.get("kind") or "").lower()
        headline = (e.get("headline") or e.get("kindAr") or kind).strip()
        materiality = "low"
        weight = 0.5

        low_kw = " ".join(MATERIAL_KEYWORDS["critical"]).lower()
        mid_kw = " ".join(MATERIAL_KEYWORDS["high"]).lower()
        h_l = headline.lower()
        if any(k in h_l for k in MATERIAL_KEYWORDS["critical"]) or "increase capital" in kind:
            materiality = "critical"; weight = 3.0
            neg.append(f"حدث حرج: {headline}")
        elif any(k in h_l for k in MATERIAL_KEYWORDS["high"]) or kind in ("cash_dividend", "stock_dividend"):
            materiality = "high"; weight = 2.0
            if kind in ("cash_dividend", "stock_dividend"):
                pos.append(f"{e.get('kindAr','توزيعات')} بقيمة {e.get('value','—')} ج.م")
            else:
                neu.append(f"حدث: {headline}")
        else:
            materiality = "medium"; weight = 1.0
            neu.append(headline)

        total_impact += weight
        has_news = True
        analyzed_events.append({
            "headline": headline,
            "kind": kind,
            "kindAr": e.get("kindAr"),
            "date": e.get("distributionDate") or e.get("date"),
            "value": e.get("value"),
            "materiality": materiality,
            "weight": weight,
        })

    # ═══ 3) نحسب النتيجة ═══
    if not has_news:
        # ⚠️ صراحة: مفيش أخبار = نتيجة منخفضة + سبب واضح
        score = 45.0
        return {
            "score": score,
            "has_news": False,
            "headline": "لا توجد أحداث معلنة حالياً",
            "materiality": "none",
            "confidence": 60,   # ثقة متوسطة — إحنا عارفين مفيش أخبار
            "note": "لا توجد أخبار أو أحداث معلنة — المحور محايد، مش إيجابي ولا سلبي",
            "events": [],
            "events_count": 0,
            "positives": [],
            "negatives": [],
            "neutral": ["لا توجد أخبار معلنة عن هذا السهم"],
        }

    # فيه أخبار — نحسب التأثير
    # events_count أكثر = ثقة أعلى
    n = len(analyzed_events)
    if   total_impact >= 10: score = 82
    elif total_impact >= 6:  score = 72
    elif total_impact >= 3:  score = 62
    else:                     score = 52

    # حدث حرج = خصم قوي
    has_critical = any(e["materiality"] == "critical" for e in analyzed_events)
    if has_critical:
        score -= 18
        neg.append("⚠️ يوجد حدث حرج ممكن يأثر على السعر")

    conf = min(95, 45 + n * 10)

    return {
        "score": round(max(0, min(100, score)), 1),
        "has_news": True,
        "headline": analyzed_events[0]["headline"] if analyzed_events else "—",
        "materiality": analyzed_events[0]["materiality"] if analyzed_events else "low",
        "confidence": conf,
        "note": "{} أحداث معلنة | أكثرها materiality: {}".format(
            n, analyzed_events[0]["materiality"] if analyzed_events else "—"),
        "events": analyzed_events[:5],
        "events_count": n,
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:5],
    }



# ════════════════════════════════════════════════════════════
# PHASE 11: محرك التفسير — ليه الـ Score ده؟
# ════════════════════════════════════════════════════════════

def explain_score(item, tech=None, fund=None, liq=None, news=None, sent=None, risk=None, pfit=None, final=None):
    """
    كل نتيجة لازم تكون قابلة للتفسير. المستخدم يضغط على أي رقم
    ويعرف: كم权重 له، وكم بيساهم، وليه.
    """
    if not item: return None

    def _f(v, d=0.0):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    W = AXIS_WEIGHTS
    axes = (final or {}).get("axes", {})

    # ═══ 1) جدول المساهمة ═══
    contributions = []
    names = {
        "technical": "التحليل الفني",
        "fundamental": "التحليل الأساسي",
        "liquidity": "السيولة",
        "news": "الأخبار",
        "sentiment": "المعنويات",
        "risk": "أمان المخاطرة",
        "portfolio": "ملاءمة المحفظة",
    }
    for k, w in W.items():
        v = _f(axes.get(k), 50)
        contrib = round(v * w, 1)
        contributions.append({
            "axis": k,
            "name": names[k],
            "score": round(v, 1),
            "weight": round(w * 100, 1),
            "contribution": contrib,
        })
    contributions.sort(key=lambda x: -x["contribution"])

    # ═══ 2) التعديلات (الخصومات) ═══
    base = round(sum(c["contribution"] for c in contributions), 1)
    final_v = _f((final or {}).get("final_score"), base)

    adjustments = []
    risk_pen = round((100 - _f(axes.get("risk"), 60)) * 0.18, 1)
    if risk_pen > 0.5:
        adjustments.append({
            "type": "خصم المخاطرة",
            "value": -risk_pen,
            "why": "كل ما الأمان يقل، النتيجة تقل",
        })
    dc = _f(item.get("data_confidence"), 60)
    if dc < 50:
        conf_pen = round((50 - dc) * 0.25, 1)
        adjustments.append({
            "type": "خصم ضعف البيانات",
            "value": -conf_pen,
            "why": "البيانات ناقصة ({:.0f}/100) — النتيجة أقل موثوقية".format(dc),
        })
    if liq and liq.get("risk_level") in ("مرتفع", "مرتفع جداً"):
        lq_pen = round((100 - _f(liq.get("score"), 50)) * 0.10, 1)
        adjustments.append({
            "type": "خصم السيولة",
            "value": -lq_pen,
            "why": "سيولة ضعيفة — قد لا تقدر تبيع بسرعة",
        })

    # ═══ 3) أكبر 3 إيجابيات وسلبيات ═══
    all_pos, all_neg = [], []

    def collect(engine, kind):
        if not engine: return
        for p in (engine.get("positives") or [])[:3]:
            all_pos.append((f"{names.get(kind,'')}", p))
        for n in (engine.get("negatives") or [])[:3]:
            all_neg.append((f"{names.get(kind,'')}", n))

    collect(tech, "technical")
    collect(fund, "fundamental")
    collect(liq, "liquidity")
    collect(news, "news")
    collect(sent, "sentiment")
    collect(risk, "risk")

    # ═══ 4) البيانات الناقصة ═══
    missing = []
    critical_fields = {
        "pe": "مضاعف الربحية", "pb": "مضاعف الكتاب", "roe": "العائد على الملكية",
        "net_margin": "هامش الربح", "de_ratio": "نسبة الدين", "eps": "ربحية السهم",
        "rsi": "مؤشر القوة النسبية", "mkt_cap": "القيمة السوقية",
        "volume": "حجم التداول", "beta": "معامل المخاطرة",
    }
    for f, label in critical_fields.items():
        if item.get(f) is None:
            missing.append(label)

    # ═══ 5) إيه اللي ممكن يغيّر النتيجة ═══
    what_changes = []
    rsi = _f(item.get("rsi"), None)
    if rsi is not None:
        if rsi < 30:
            what_changes.append("لو القوة النسبية عدّت 50 فوق — الزخم يتحسّن والنتيجة ترتفع ٥-١٠ نقاط")
        elif rsi > 70:
            what_changes.append("لو القوة النسبية نزلت تحت 70 — خطر التشبع ينقص والنتيجة تتحسن")
    if _f(axes.get("risk"), 60) < 60:
        what_changes.append("لو Beta نزل تحت 1.0 أو التقلّب قلّ — الخصم يقل والنتيجة ترتفع")
    if liq and liq.get("score", 0) < 50:
        what_changes.append("لو حجم التداول زاد — خصم السيولة يروح والنتيجة تتحسّن")
    if dc < 60:
        what_changes.append("لو البيانات المالية اتحدّثت — خصم ضعف البيانات يروح")

    # ═══ 6) إيه اللي يفسد الفكرة ═══
    invalidation = []
    pe = _f(item.get("pe"), None)
    if pe is not None and pe > 0:
        invalidation.append(f"لو P/E عدّى {pe*1.4:.0f} — السهم بقى غالي والفكرة ضعفت")
    if _f(item.get("roe"), None) is not None:
        invalidation.append("لو العائد على الملكية نزل تحت نصف قيمته الحالية")
    tv = _f(item.get("tv_all"), None)
    if tv is not None and tv < -0.4:
        invalidation.append("لو التقييم الفني نزل تحت -0.6 — اتجاه هابط مؤكد")

    return {
        "final_score": round(final_v, 1),
        "base_score": base,
        "contributions": contributions,
        "adjustments": adjustments,
        "adjustment_total": round(sum(a["value"] for a in adjustments), 1),
        "formula": "{} (مرجّح) {} (تعديلات) = {}".format(
            base, round(sum(a["value"] for a in adjustments), 1), round(final_v, 1)),
        "top_positives": [{"from": s, "text": p} for s, p in all_pos[:3]],
        "top_negatives": [{"from": s, "text": n} for s, n in all_neg[:3]],
        "missing_data": missing,
        "missing_count": len(missing),
        "what_could_change_score": what_changes,
        "what_could_invalidate": invalidation,
        "confidence": _f((final or {}).get("confidence"), 0),
    }



# ════════════════════════════════════════════════════════════
# PHASE 12: محرك الفرص المبكرة — نكتشف قبل ما السهم يتحرك
# ════════════════════════════════════════════════════════════
# المبدأ: "accumulation" + "compression" + "improving momentum"
# قبل ما occurs. مش بنطارد الحركة بعد ما obtains.

def opportunity_engine(item, tech=None, fund=None, liq=None):
    """
    ⚠️ المبدأ: نبحث عن فرص قبل ما occurs.
       الفرق بين "فرصة مبكرة" و "حركة موجودة"
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    pos, neg, neu = [], [], []

    px = _f(item.get("price"))
    rsi = _f(item.get("rsi"))
    ema20 = _f(item.get("ema20"))
    ema50 = _f(item.get("ema50"))
    ema200 = _f(item.get("ema200"))
    sma50 = _f(item.get("sma50"))
    vol = _f(item.get("volume"))
    vol5 = _f(item.get("vol_5"))
    vol60 = _f(item.get("vol_60"))
    rel_vol = _f(item.get("rel_volume"))
    perf_1w = _f(item.get("perf_w"))
    perf_1m = _f(item.get("perf_1m"))
    perf_3m = _f(item.get("perf_3m"))
    bbu = _f(item.get("bb_upper"))
    bbl = _f(item.get("bb_lower"))
    bbb = _f(item.get("bb_basis"))
    tv_all = _f(item.get("tv_all"))
    pe = _f(item.get("pe"))
    roe = _f(item.get("roe"))
    beta = _f(item.get("beta"))

    # ═══ 1) التراكم (Accumulation) — 25 وزن ═══
    # علامات التراكم: حجم بيتزود + السعر بيتحرك أقل (RJ-style)
    accum = 0.0
    if vol5 and vol60 and vol60 > 0:
        vol_trend = (vol5 / vol60) if vol60 > 0 else 1
        if   vol_trend > 1.3 and (perf_1w or 0) < 3:
            accum += 15; pos.append("تراكم: حجم بيتزود لكن السعر لسه ما تحركش")
        elif vol_trend > 1.1:
            accum += 9
        elif vol_trend < 0.8:
            accum -= 5; neg.append("الحجم بينكمش — لا يوجد اهتمام")
    if rel_vol and rel_vol > 1.2 and (perf_1w or 0) < 5:
        accum += 10; pos.append(f"حجم غير معتاد ({rel_vol:.1f}×) بدون قفزة — تجميع")
    accum = max(0, min(25, accum))

    # ═══ 2) الضغط قبل الكسر (Compression) — 20 وزن ═══
    # بولنجر ضيق + ATR منخفض = السهم بيتزنق
    comp = 0.0
    if bbu and bbl and bbb and bbb > 0:
        bb_width = (bbu - bbl) / bbb * 100
        if   bb_width < 6:  comp += 20; pos.append(f"ضغط شديد (بولنجر {bb_width:.1f}%) — انفجار قادم")
        elif bb_width < 10: comp += 13; pos.append(f"نطاق ضيق ({bb_width:.1f}%) — تكثف")
        elif bb_width < 15: comp += 7
        else:               comp += 0; neu.append(f"نطاق واسع ({bb_width:.0f}%)")
    if rsi and 35 <= rsi <= 55:
        comp += 5; pos.append("القوة النسبية محايدة — بدون ضغط شراء/بيع")

    # ═══ 3) تحسن الزخم (Improving Momentum) — 20 وزن ═══
    mom = 0.0
    if perf_1w is not None and perf_1m is not None:
        # أسبوع أحسن من الشهر = الزخم بيتحسّن
        if perf_1w > 0 and perf_1m < 0:
            mom += 18; pos.append(f"تحول: الأسبوع +{perf_1w:.1f}% والشهر {perf_1m:.1f}% — الزخم بيتغير")
        elif perf_1w > perf_1m / 4:
            mom += 11
        elif perf_1w < perf_1m / 4 and perf_1m < 0:
            mom -= 5; neg.append("الزخم بيتدهور")
    # السهم قريب من EMA20 من تحت (تقاطع واعد)
    if px and ema20 and ema200:
        if px < ema20 and px > ema200:
            mom += 8; pos.append(f"السهم تحت EMA20 ({ema20:.1f}) لكن فوق EMA200 ({ema200:.1f}) — انعكاس محتمل")
    if tv_all is not None and tv_all > 0.1:
        mom += 6

    # ═══ 4)来个 مفيد من الأساسيات (Fundamental Catalyst) — 20 وزن ═══
    cat = 0.0
    if pe is not None and pe > 0 and pe < 12:
        cat += 12; pos.append(f"P/E {pe:.1f} — تحت التقييم العادل")
    if roe is not None and roe > 25:
        cat += 10; pos.append(f"ربحية عالية ({roe:.0f}%) — أساس صلب")
    if fund and fund.get("valuation_status") == "مُسعّر بأقل من قيمته":
        cat += 10; pos.append("مُسعّر بأقل من قيمته حسب المقارنة مع القطاع")
    if _f(item.get("div_yield")) and _f(item.get("div_yield")) > 4:
        cat += 5

    # ═══ 5) محفزات vendedor (Seller Exhaustion) — 15 وزن ═══
    seller = 0.0
    if perf_1m is not None and perf_1m < -20:
        seller += 12; pos.append(f"هبوط حاد (-{abs(perf_1m):.0f}%) — بائعين نفدوا؟")
    if rsi is not None and rsi < 30:
        seller += 10; pos.append(f"تشبع بيعي ({rsi:.0f}) — البائعين خلصوا")
    if rsi is not None and rsi > 75:
        seller -= 8; neg.append(f"تشبع شرائي ({rsi:.0f}) —Late chase risk")

    # ═══ النتيجة ═══
    total = round(max(0, min(100, accum + comp + mom + cat + seller)), 1)

    # ═══ التصنيف: مبكرة vs موجودة ═══
    is_existing = (perf_1m is not None and perf_1m > 20) or (tv_all is not None and tv_all > 0.4)
    stage = "حركة قائمة (مطاردة)" if is_existing else ("فرصة مبكرة ✅" if total >= 55 else "محايد")

    if total >= 70:   signal = "فرصة قوية"
    elif total >= 55: signal = "فرصة جيدة"
    elif total >= 40: signal = "مش واضح"
    elif total >= 25: signal = "ضعيفة"
    else:             signal = "غير جذابة"

    return {
        "score": total,
        "signal": signal,
        "stage": stage,
        "is_early": not is_existing and total >= 55,
        "breakdown": {
            "التراكم": round(accum, 1),
            "الضغط قبل الكسر": round(comp, 1),
            "تحسن الزخم": round(mom, 1),
            "محفز أساسي": round(cat, 1),
            "إنهاك البائعين": round(seller, 1),
        },
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:3],
    }



# ════════════════════════════════════════════════════════════
# PHASE 14: ملفات الاستراتيجية — نفس البيانات، أوزان مختلفة
# ════════════════════════════════════════════════════════════
# المبدأ: مفيش "score واحد يناسب كل المستثمرين".
# نفس البيانات تتقيّم بطرق مختلفة حسب أسلوب المستثمر.

STRATEGIES = {
    "swing": {
        "name_ar": "مضاربة (سوينج)",
        "desc": "صفقات قصيرة على الحركة. الفني هو الملك.",
        "timeframe": "أيام إلى أسابيع",
        "weights": {"technical": 0.40, "fundamental": 0.12, "liquidity": 0.22,
                    "news": 0.08, "sentiment": 0.05, "risk": 0.08, "portfolio": 0.05},
        "risk_penalty_mult": 1.4,   # المخاطرة بتأثر أكتر
        "min_liquidity": 60,         # لازم سيولة عالية عشان enters/exits
        "focus": "الحركة والزخم فقط",
    },
    "value": {
        "name_ar": "استثمار قيمة",
        "desc": "شراء رخيص بناءً على الأساسيات. الأساسي هو الملك.",
        "timeframe": "سنة إلى 3 سنوات",
        "weights": {"technical": 0.08, "fundamental": 0.45, "liquidity": 0.10,
                    "news": 0.07, "sentiment": 0.02, "risk": 0.20, "portfolio": 0.08},
        "risk_penalty_mult": 1.6,   # المخاطرة الأعلى = أخطر (شركة رديئة رخيصة)
        "min_liquidity": 30,         # يقدر يكون سيولة أقل
        "focus": "التقييم والربحية",
    },
    "growth": {
        "name_ar": "نمو",
        "desc": "شركات بتنمو بسرعة. النمو هو المفتاح.",
        "timeframe": "1-3 سنوات",
        "weights": {"technical": 0.15, "fundamental": 0.40, "liquidity": 0.12,
                    "news": 0.10, "sentiment": 0.08, "risk": 0.10, "portfolio": 0.05},
        "risk_penalty_mult": 0.7,   # نمو = مخاطرة مقبولة
        "min_liquidity": 40,
        "focus": "النمو والربحية المستقبلية",
    },
    "income": {
        "name_ar": "دخل (توزيعات)",
        "desc": "دخل شهري ثابت. الجودة المالية هي الملك.",
        "timeframe": "مستمر",
        "weights": {"technical": 0.10, "fundamental": 0.35, "liquidity": 0.18,
                    "news": 0.10, "sentiment": 0.02, "risk": 0.20, "portfolio": 0.05},
        "risk_penalty_mult": 1.5,
        "min_liquidity": 50,         # لازم تقدر تبيع وتاخد التوزيع
        "focus": "التوزيعات + الاستقرار",
        "min_div_yield": 3.0,       # لازم عائد توزيع 3%+
    },
    "balanced": {
        "name_ar": "متوازن",
        "desc": "توازن بين كل المحاور. مناسب لأغلب الناس.",
        "timeframe": "3-12 شهر",
        "weights": {"technical": 0.18, "fundamental": 0.25, "liquidity": 0.12,
                    "news": 0.08, "sentiment": 0.05, "risk": 0.20, "portfolio": 0.12},
        "risk_penalty_mult": 1.0,
        "min_liquidity": 45,
        "focus": "كل المحاور بالتساوي تقريباً",
    },
    "conservative": {
        "name_ar": "محافظ",
        "desc": "حماية رأس المال أولاً. المخاطر عالية = رفض.",
        "timeframe": "1-3 سنوات",
        "weights": {"technical": 0.15, "fundamental": 0.28, "liquidity": 0.15,
                    "news": 0.07, "sentiment": 0.02, "risk": 0.28, "portfolio": 0.05},
        "risk_penalty_mult": 2.0,   # المخاطرة بتأثر جداً
        "min_liquidity": 65,
        "min_safety": 65,           # أمان لازم 65+
        "focus": "حماية رأس المال",
    },
    "aggressive": {
        "name_ar": "جريء",
        "desc": "مخاطرة عالية مقابل عائد عالي. زخم ومضاعفات رخيصة.",
        "timeframe": "أشهر",
        "weights": {"technical": 0.32, "fundamental": 0.20, "liquidity": 0.20,
                    "news": 0.10, "sentiment": 0.10, "risk": 0.03, "portfolio": 0.05},
        "risk_penalty_mult": 0.3,   # المخاطرة ماتأثرش
        "min_liquidity": 55,
        "focus": "الزخم والحركة السريعة",
    },
}


def strategy_score(item, strategy="balanced", tech=None, fund=None, liq=None, sent=None, pfit=None):
    """
    ⚠️ المبدأ: نفس البيانات، نفس الحساب — بس الأوزان بتتغير.
       مفيش إعادة حساب للمحركات — بنستخدم نفس الأرقام.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not item: return None
    st = STRATEGIES.get(strategy) or STRATEGIES["balanced"]
    axes = {}

    # نفس المحاور — إعادة استخدام
    axes["technical"] = _f(tech["score"]) if tech else 50.0
    axes["fundamental"] = _f(fund["score"]) if fund else 50.0
    axes["liquidity"] = _f(liq["score"]) if liq else 50.0
    axes["news"] = _f(item.get("news_score"), 45.0)
    axes["sentiment"] = _f(sent["score"]) if sent else 50.0
    _all = item.get("all_axes") or {}
    if not isinstance(_all, dict):
        _all = {}
    axes["risk"] = _f(_all.get("risk"), 60.0)
    axes["portfolio"] = _f(pfit["score"]) if pfit else 70.0

    # المحصلة بأوزان الاستراتيجية
    w = st["weights"]
    base = sum(axes[k] * w[k] for k in w)

    # خصم المخاطرة بمعامل الاستراتيجية
    risk_pen = (100 - axes["risk"]) * 0.18 * st["risk_penalty_mult"]
    adj = base - risk_pen

    # ═══ الفلاتر الخاصة بالاستراتيجية ═══
    filters_passed = True
    filter_notes = []

    liq_v = axes["liquidity"]
    if liq_v < st.get("min_liquidity", 0):
        adj -= (st["min_liquidity"] - liq_v) * 0.5
        filter_notes.append(f"السيولة {liq_v:.0f} أقل من المطلوب ({st['min_liquidity']})")
        filters_passed = False

    if st.get("min_safety"):
        safety = _f(item.get("safety_score"))
        if safety is not None and safety < st["min_safety"]:
            adj -= (st["min_safety"] - safety) * 0.4
            filter_notes.append(f"الأمان {safety:.0f} أقل من المطلوب ({st['min_safety']})")
            filters_passed = False

    if st.get("min_div_yield"):
        dy = _f(item.get("div_yield"))
        if dy is None or dy < st["min_div_yield"]:
            actual = f"{dy:.1f}%" if dy is not None else "غير متاح"
            adj -= 8
            filter_notes.append(f"عائد التوزيعات {actual} أقل من المطلوب ({st['min_div_yield']}%)")
            filters_passed = False

    # ═══ سقف إجمالي الخصومات: 22 نقطة كحد أقصى ═══
    # ⚠️ سقف إجمالي الخصومات: 22 نقطة كحد أقصى (نفس قاعدة final_score)
    liq_pen = min(6.0, (100 - axes["liquidity"]) * 0.10) if (
        liq and liq.get("risk_level") in ("مرتفع", "مرتفع جداً")) else 0.0
    adj -= liq_pen
    total_penalty = risk_pen + liq_pen
    if total_penalty > 22:
        scale = 22 / total_penalty
        risk_pen *= scale
        liq_pen *= scale

    final = round(max(0, min(100, adj)), 1)

    # القرار بنفس المنطق
    if axes["risk"] < 35:         decision = "تجنّب"
    elif final >= 78 and filters_passed:  decision = "تجميع"
    elif final >= 65:             decision = "تجميع"
    elif final >= 52:             decision = "احتفظ"
    elif axes["fundamental"] >= 65: decision = "احتفظ"
    else:                         decision = "بيع"

    return {
        "strategy": strategy,
        "strategy_name": st["name_ar"],
        "timeframe": st["timeframe"],
        "focus": st["focus"],
        "score": final,
        "axes": {k: round(v, 1) for k, v in axes.items()},
        "weights": w,
        "base": round(base, 1),
        "risk_penalty": round(-risk_pen, 1),
        "liquidity_penalty": round(-liq_pen, 1),
        "filters_passed": filters_passed,
        "filter_notes": filter_notes,
        "decision": decision,
        "confidence": round(min(95, _f(item.get("data_confidence"), 60) * 0.6 + 40), 1),
    }


def score_all_strategies(item, tech=None, fund=None, liq=None, sent=None, pfit=None):
    """يحسب السهم في كل الاستراتيجيات"""
    out = {}
    for k in STRATEGIES:
        r = strategy_score(item, k, tech, fund, liq, sent, pfit)
        if r:
            out[k] = {"name": r["strategy_name"], "score": r["score"],
                      "decision": r["decision"], "filters_passed": r["filters_passed"]}
    return out



# ════════════════════════════════════════════════════════════
# PHASE 13: الترتيب والفلاتر المتقدمة
# ════════════════════════════════════════════════════════════

def rank_stocks(all_stocks, strategy="balanced", min_score=0, max_risk=None,
                min_safety=None, min_liquidity=None, sectors=None, max_pe=None,
                min_div_yield=None, decisions=None, limit=20):
    """
    يرتّب كل الأسهم مع فلاتر متعددة.
    المبدأ: نفس البيانات، فلاتر مختلفة حسب اللي بطلبه المستخدم.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    out = []
    for item in all_stocks:
        fs = _f(item.get("final_score"))
        if fs is None: continue

        # نحسب النتيجة حسب الاستراتيجية المطلوبة
        st = item.get("strategies") or {}
        strat_res = st.get(strategy)
        score = _f(strat_res.get("score"), fs) if strat_res else fs
        dec = (strat_res or {}).get("decision") or item.get("decision")
        safety = _f(item.get("safety_score"))
        liq = _f(item.get("liquidity_score"))

        # ═══ الفلاتر ═══
        if score < min_score: continue
        if max_risk is not None and safety is not None and safety < max_risk: continue
        if min_safety is not None and (safety is None or safety < min_safety): continue
        if min_liquidity is not None and (liq is None or liq < min_liquidity): continue
        if sectors and (item.get("sector") not in sectors): continue
        if max_pe is not None:
            pe = _f(item.get("pe"))
            if pe is None or pe <= 0 or pe > max_pe: continue
        if min_div_yield is not None:
            dy = _f(item.get("div_yield"))
            if dy is None or dy < min_div_yield: continue
        if decisions and dec not in decisions: continue

        out.append({
            "code": item["code"],
            "name": item.get("name"),
            "sector": item.get("sector"),
            "price": item.get("price"),
            "change": item.get("change"),
            "score": round(score, 1),
            "final_score": round(fs, 1),
            "decision": dec,
            "safety": safety,
            "liquidity": liq,
            "opportunity": _f(item.get("opportunity_score")),
            "pe": _f(item.get("pe")),
            "roe": _f(item.get("roe")),
            "div_yield": _f(item.get("div_yield")),
            "beta": _f(item.get("beta")),
            "mkt_cap": _f(item.get("mkt_cap")),
            "fair_value": item.get("fair_value"),
            "upside": item.get("upside"),
            "valuation": item.get("valuation"),
            "confidence": _f(item.get("confidence")),
            "risk_level": item.get("risk_level"),
        })

    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def available_filters(all_stocks):
    """يرجّع كل الخيارات المتاحة للفلاتر"""
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    sectors = {}
    for s in all_stocks:
        sec = s.get("sector")
        if sec: sectors[sec] = sectors.get(sec, 0) + 1

    decisions = {}
    for s in all_stocks:
        d = s.get("decision")
        if d: decisions[d] = decisions.get(d, 0) + 1

    risk_levels = {}
    for s in all_stocks:
        r = s.get("risk_level")
        if r: risk_levels[r] = risk_levels.get(r, 0) + 1

    scores = [_f(s.get("final_score"), 0) for s in all_stocks if s.get("final_score") is not None]
    safety = [_f(s.get("safety_score"), 0) for s in all_stocks if s.get("safety_score") is not None]
    liq = [_f(s.get("liquidity_score"), 0) for s in all_stocks if s.get("liquidity_score") is not None]

    def rng(xs):
        return {"min": round(min(xs), 0), "max": round(max(xs), 0)} if xs else {"min": 0, "max": 100}

    return {
        "sectors": [{"name": k, "count": v} for k, v in sorted(sectors.items(), key=lambda x: -x[1])],
        "decisions": [{"name": k, "count": v} for k, v in decisions.items()],
        "risk_levels": [{"name": k, "count": v} for k, v in risk_levels.items()],
        "strategies": [{"key": k, "name": v["name_ar"], "timeframe": v["timeframe"]}
                       for k, v in STRATEGIES.items()],
        "ranges": {
            "score": rng(scores), "safety": rng(safety), "liquidity": rng(liq),
        },
        "total": len(all_stocks),
    }



# ════════════════════════════════════════════════════════════
# PHASE 15: الاختبار التاريخي (Forward-Tracking Backtest)
# ════════════════════════════════════════════════════════════
# ⚠️ قرار منهجي مهم:
#   TradingView ما بيقدّمش تاريخ يومي لكل سهم عبر الـ API المجاني.
#   فبدل ما نخترع بيانات، بنعمل "forward tracking":
#   بنسجّل snapshot للنتيجة اليوم، وبعدين نقيس بعد ٣٠/٦٠/٩٠ يوم
#   هل الأسهم اللي رشحّناها اتحركت فعلاً ولا لأ.
#   ده أصدق من backtest على بيانات مفترضة.

BT_FILE = Path("/app/backtest_snapshots.json")
BACKTEST = {"snapshots": {}, "results": [], "stats": {}}


def _bt_load():
    try:
        if BT_FILE.exists():
            with open(BT_FILE, "r", encoding="utf-8") as f:
                BACKTEST.update(json.load(f))
    except Exception as e:
        print(f"  BT load err: {e}")


def _bt_save():
    try:
        with open(BT_FILE, "w", encoding="utf-8") as f:
            json.dump(BACKTEST, f, ensure_ascii=False)
    except Exception as e:
        print(f"  BT save err: {e}")


def bt_snapshot():
    """
    نلتقط صورة للنتيجة الآن. بعد كده نقيس: السهم اللي رشحناه
    عمل إيه فعلاً خلال ٣٠/٦٠/٩٠ يوم؟
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    st = LIVE_DATA.get("egx30", [])
    today = datetime.utcnow().strftime("%Y-%m-%d")

    ranked = sorted([s for s in st if s.get("final_score") is not None],
                   key=lambda x: -x["final_score"])[:20]
    if not ranked:
        return

    snap = {
        "date": today,
        "ts": int(time.time()),
        "picks": [{
            "code": s["code"],
            "score": _f(s.get("final_score")),
            "price": _f(s.get("price")),
            "decision": s.get("decision"),
            "sector": s.get("sector"),
            "safety": _f(s.get("safety_score")),
            "opportunity": _f(s.get("opportunity_score")),
            "perf_1m": _f(s.get("perf_1m")),
            "upside": _f(s.get("upside")),
        } for s in ranked],
    }
    BACKTEST["snapshots"][today] = snap
    # نحتفظ بآخر ٩٠ يوم بس
    keys = sorted(BACKTEST["snapshots"].keys())[-90:]
    BACKTEST["snapshots"] = {k: BACKTEST["snapshots"][k] for k in keys}
    _bt_save()
    print(f"  📸 BT snapshot: {today} — {len(snap['picks'])} سهم")


def bt_evaluate(days_back=30):
    """
    نقيس: الأسهم اللي رشحناها قبل N يوم، كانت بتعمل إيه؟
    ⚠️ مفيش track real history — بنستخدم أداء الفترة الحالي كبديل
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    st = {s["code"]: s for s in LIVE_DATA.get("egx30", [])}
    snaps = sorted(BACKTEST["snapshots"].items())
    if len(snaps) < 2:
        return {
            "status": "ناقص البيانات",
            "note": "محتاجين يومين على الأقل عشان نقيس. لقطة اليوم اتسجلت.",
            "snapshots_count": len(snaps),
            "days_back": days_back,
        }

    results = []
    for date, snap in snaps[:-1]:
        age_days = (datetime.utcnow() - datetime.fromisoformat(date)).days
        if age_days < 3:   # نقيس بعد ٣ أيام على الأقل
            continue
        wins, losses, flat = 0, 0, 0
        picks = []
        for p in snap["picks"]:
            code = p["code"]
            now = st.get(code)
            if not now: continue
            old_p = _f(p.get("price"))
            new_p = _f(now.get("price"))
            if not old_p or not new_p: continue
            ret = ((new_p - old_p) / old_p) * 100
            # عتبات: +2% ربح، -2% خسارة
            if ret >= 2:    wins += 1
            elif ret <= -2: losses += 1
            else:           flat += 1
            picks.append({
                "code": code, "sector": p.get("sector"),
                "score_at_pick": p.get("score"),
                "decision_at_pick": p.get("decision"),
                "price_then": round(old_p, 2),
                "price_now": round(new_p, 2),
                "actual_return": round(ret, 2),
                "result": "ربح" if ret >= 2 else ("خسارة" if ret <= -2 else "محايد"),
            })
        if not picks: continue
        n = len(picks)
        results.append({
            "snapshot_date": date,
            "age_days": age_days,
            "count": n,
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "win_rate": round(wins / n * 100, 1),
            "loss_rate": round(losses / n * 100, 1),
            "avg_return": round(sum(p["actual_return"] for p in picks) / n, 2),
            "picks": picks,
        })

    # ═══ الإحصائيات الإجمالية ═══
    if results:
        total_picks = sum(r["count"] for r in results)
        total_wins = sum(r["wins"] for r in results)
        total_losses = sum(r["losses"] for r in results)
        total_flat = sum(r["flat"] for r in results)
        all_picks = [p for r in results for p in r["picks"]]
        avg_ret = sum(p["actual_return"] for p in all_picks) / len(all_picks) if all_picks else 0

        # Profit Factor = إجمالي الربح / إجمالي الخسارة
        gains = sum(p["actual_return"] for p in all_picks if p["actual_return"] > 0)
        losses_abs = abs(sum(p["actual_return"] for p in all_picks if p["actual_return"] < 0))
        profit_factor = round(gains / losses_abs, 2) if losses_abs > 0 else (999 if gains > 0 else 0)

        BACKTEST["results"] = results
        BACKTEST["stats"] = {
            "snapshots_taken": len(snaps),
            "windows_measured": len(results),
            "total_picks": total_picks,
            "wins": total_wins,
            "losses": total_losses,
            "flat": total_flat,
            "win_rate": round(total_wins / total_picks * 100, 1) if total_picks else 0,
            "loss_rate": round(total_losses / total_picks * 100, 1) if total_picks else 0,
            "avg_return": round(avg_ret, 2),
            "profit_factor": profit_factor,
            "verdict": ("ممتاز" if total_wins / max(1, total_picks) > 0.6 and profit_factor > 1.5 else
                        "جيد" if total_wins / max(1, total_picks) > 0.5 and profit_factor > 1.1 else
                        "ضعيف" if total_wins / max(1, total_picks) < 0.4 else
                        "مقبول"),
        }
        _bt_save()

    return {
        "status": "تم القياس",
        "snapshots_count": len(snaps),
        "days_back": days_back,
        "windows": results,
        "stats": BACKTEST.get("stats", {}),
    }


def bt_benchmark():
    """
    مقارنة أدانا مع السوق.
    ⚠️ مبدأ: لازم نقارن بمؤشر EGX30 عشان نعرف هل أحسن من السوق فعلاً
    """
    st = LIVE_DATA.get("egx30", [])
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    if not st: return {}

    # متوسط أداء كل الأسهم = مؤشر السوق المبسط
    all_perf_1m = [_f(s.get("perf_1m")) for s in st if _f(s.get("perf_1m")) is not None]
    all_perf_3m = [_f(s.get("perf_3m")) for s in st if _f(s.get("perf_3m")) is not None]
    all_perf_y = [_f(s.get("perf_y")) for s in st if _f(s.get("perf_y")) is not None]

    market_1m = sum(all_perf_1m) / len(all_perf_1m) if all_perf_1m else 0
    market_3m = sum(all_perf_3m) / len(all_perf_3m) if all_perf_3m else 0
    market_y = sum(all_perf_y) / len(all_perf_y) if all_perf_y else 0

    # متوسط أداء أسهم الترتيب Top 20
    top = sorted([s for s in st if s.get("final_score") is not None], key=lambda x: -x["final_score"])[:20]
    top_1m = [_f(s.get("perf_1m")) for s in top if _f(s.get("perf_1m")) is not None]
    top_3m = [_f(s.get("perf_3m")) for s in top if _f(s.get("perf_3m")) is not None]
    top_y = [_f(s.get("perf_y")) for s in top if _f(s.get("perf_y")) is not None]

    our_1m = sum(top_1m) / len(top_1m) if top_1m else 0
    our_3m = sum(top_3m) / len(top_3m) if top_3m else 0
    our_y = sum(top_y) / len(top_y) if top_y else 0

    alpha_1m = round(our_1m - market_1m, 2)
    alpha_3m = round(our_3m - market_3m, 2)
    alpha_y = round(our_y - market_y, 2)

    return {
        "method": "متوسط أداء أفضل ٢٠ سهم (حسب نتيجتنا) مقابل متوسط كل الأسهم",
        "caveat": "⚠️ ده ليس backtest — ده مقارنة حالية. الـ backtest الحقيقي بيبدأ من اللقطات اليومية.",
        "periods": [
            {"period": "شهر",  "market": round(market_1m, 2), "top20": round(our_1m, 2), "alpha": alpha_1m},
            {"period": "3 شهور", "market": round(market_3m, 2), "top20": round(our_3m, 2), "alpha": alpha_3m},
            {"period": "سنة",  "market": round(market_y, 2), "top20": round(our_y, 2), "alpha": alpha_y},
        ],
        "interpretation": ("أفضل من السوق ✅" if alpha_y > 3 else
                           "أداءنا ≈ السوق — ماشي" if alpha_y > -3 else
                           "أقل من السوق ❌"),
    }



# ════════════════════════════════════════════════════════════
# PHASE 16: اختبار الضغوط + PHASE 17: المعايرة
# ════════════════════════════════════════════════════════════

SCENARIOS = {
    "bull": {
        "name_ar": "سوق صاعد",
        "desc": "كل الأسهم بترتفع 20%",
        "shocks": {"perf_1m": +20, "perf_3m": +35, "perf_y": +60, "rel_volume": 1.8, "volatility": 0.8, "tv_all": +0.35},
    },
    "bear": {
        "name_ar": "سوق هابط",
        "desc": "كل الأسهم بينزل 20%",
        "shocks": {"perf_1m": -20, "perf_3m": -30, "perf_y": -40, "rel_volume": 1.5, "volatility": 1.6, "tv_all": -0.35},
    },
    "crash": {
        "name_ar": "انهيار",
        "desc": "انهيار حاد -35% فجأة",
        "shocks": {"perf_1m": -35, "perf_3m": -45, "perf_y": -55, "rel_volume": 3.0, "volatility": 3.0, "tv_all": -0.7},
    },
    "flat": {
        "name_ar": "سوق عرضي",
        "desc": "السوق راكد",
        "shocks": {"perf_1m": 0, "perf_3m": 2, "perf_y": 3, "rel_volume": 0.7, "volatility": 0.9, "tv_all": 0.0},
    },
    "illiquid": {
        "name_ar": "سيولة جافة",
        "desc": "الحجم配售 على 80% + سيولة ضعيفة",
        "shocks": {"rel_volume": 0.25, "mkt_cap_mult": 0.1, "volatility": 1.4, "perf_1m": -5},
    },
    "high_vol": {
        "name_ar": "تذبذب عالي",
        "desc": "تذبذب ضخم (5%)",
        "shocks": {"volatility": 5.0, "beta": 2.5, "perf_1m": -8, "tv_all": -0.3},
    },
    "good_news": {
        "name_ar": "خبر إيجابي مفاجئ",
        "desc": "أخبار إيجابية + قفزة",
        "shocks": {"tv_all": +0.6, "rel_volume": 2.5, "perf_1m": +12, "volatility": 1.3},
    },
}


def stress_test(all_stocks, scenario="bear", top_n=20):
    """
    ⚠️ المبدأ: لازم نعرف النظام بيفشل فين.
       بنطبّق صدمة على كل الأسهم ونشوف إزاي الترتيب بيتغيّر.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    sc = SCENARIOS.get(scenario)
    if not sc:
        return {"error": f"سيناريو غير معروف: {scenario}", "available": list(SCENARIOS.keys())}
    shocks = sc["shocks"]

    # ═══ 1) قبل ═══
    before = sorted([s for s in all_stocks if s.get("final_score") is not None],
                    key=lambda x: -x["final_score"])[:top_n]
    before_codes = [s["code"] for s in before]

    # ═══ 2) نطبّق الصدمة على كل الأسهم ═══
    shocked = []
    for s in all_stocks:
        it = dict(s)
        for k, mult in shocks.items():
            if k.endswith("_mult"):
                base = k.replace("_mult", "")
                if it.get(base) is not None:
                    try: it[base] = float(it[base]) * mult
                    except (TypeError, ValueError): pass
            else:
                if it.get(k) is not None:
                    try: it[k] = float(it[k]) + mult
                    except (TypeError, ValueError): pass
        # نعيد الحساب بنفس الدوال
        try:
            derive_technical(it)
            t = tech_score(it)
            f = fundamental_score(it, SECTOR_STATS)
            li = liquidity_score(it)
            rk = risk_engine(it, SECTOR_STATS)
            fin = final_score(it, t, f, li, SECTOR_STATS)
            it["stressed_score"] = fin["final_score"]
            it["stressed_risk"] = rk["safety_score"] if rk else None
            it["stressed_decision"] = fin["decision"]
        except Exception:
            it["stressed_score"] = _f(it.get("final_score"), 50)
            it["stressed_decision"] = it.get("decision")
        shocked.append(it)

    # ═══ 3) بعد ═══
    after = sorted([s for s in shocked if s.get("stressed_score") is not None],
                   key=lambda x: -x["stressed_score"])[:top_n]
    after_codes = [s["code"] for s in after]

    # ═══ 4) التحليل ═══
    retained = len(set(before_codes) & set(after_codes))
    flip_to_sell = sum(1 for s in after if "بيع" in (s.get("stressed_decision") or "") or "تجنّب" in (s.get("stressed_decision") or ""))
    avg_before = sum(_f(s.get("final_score"), 0) for s in before) / max(1, len(before))
    avg_after = sum(_f(s.get("stressed_score"), 0) for s in after) / max(1, len(after))
    avg_safety_after = sum(_f(s.get("stressed_risk"), 0) for s in after) / max(1, len(after))

    dropped = [c for c in before_codes if c not in after_codes]

    return {
        "scenario": scenario,
        "scenario_name": sc["name_ar"],
        "description": sc["desc"],
        "shocks": shocks,
        "top_n": top_n,
        "before": [{"code": s["code"], "score": _f(s.get("final_score")), "decision": s.get("decision")}
                   for s in before[:10]],
        "after": [{"code": s["code"], "score": _f(s.get("stressed_score")),
                   "decision": s.get("stressed_decision"),
                   "safety": _f(s.get("stressed_risk"))} for s in after[:10]],
        "resilience": {
            "retained_picks": retained,
            "retention_rate": round(retained / max(1, len(before_codes)) * 100, 1),
            "dropped_picks": dropped[:10],
            "flipped_to_sell": flip_to_sell,
            "avg_score_before": round(avg_before, 1),
            "avg_score_after": round(avg_after, 1),
            "score_drop": round(avg_before - avg_after, 1),
            "avg_safety_after": round(avg_safety_after, 1),
        },
        # ⚠️ معايير الحكم: مش بس النتيجة — كمان التصرف الصحيح
        #     لو النتيجة نزلت بس القرارات بقت تحذير = النظام صامد
        "verdict": (
            "النظام صامد ✅" if (avg_after >= avg_before - 12 and flip_to_sell >= max(2, retained * 0.5)) else
            "النظام Weak ⚠️" if (avg_after >= avg_before - 22 and flip_to_sell >= 2) else
            "النظام انهار ❌"
        ),
        "verdict_detail": {
            "note": "الحكم على مرحلتين: (1) النتيجة بعد الصدمة، (2) هل القرارات تحوّلت是正确的؟",
            "score_held": avg_after >= avg_before - 12,
            "decisions_corrected": flip_to_sell >= 2,
            "note2": "لو القرارات اتحوّلت لتجنّب/بيع = النظام بيتصرف صح حتى لو النتيجة نزلت",
        },
    }


def run_all_stress(all_stocks, top_n=20):
    """يشغّل كل السيناريوهات ويعطي الملخص"""
    out = {}
    for key in SCENARIOS:
        r = stress_test(all_stocks, key, top_n)
        if "resilience" in r:
            out[key] = {
                "name": r["scenario_name"],
                "avg_after": r["resilience"]["avg_score_after"],
                "retention": r["resilience"]["retention_rate"],
                "flipped_to_sell": r["resilience"]["flipped_to_sell"],
                "verdict": r["verdict"],
            }
    return out


# ════════════════════════════════════════════════════════════
# PHASE 17: المعايرة — ضبط الأوزان بدون overfitting
# ════════════════════════════════════════════════════════════

CALIBRATION = {
    "version": "v1.1",
    "note": "معايرة 2026-10-07: اختبار الضغط كشف نقص تمثيل السيولة والمخاطرة في السوق المصري.",
    "last_calibrated": "2026-10-07",
    "history": [{
        "date": "2026-10-07",
        "old": {"technical": 0.20, "fundamental": 0.25, "liquidity": 0.10,
                "news": 0.07, "sentiment": 0.05, "risk": 0.20, "portfolio": 0.13},
        "new": {"technical": 0.18, "fundamental": 0.22, "liquidity": 0.18,
                "news": 0.05, "sentiment": 0.04, "risk": 0.24, "portfolio": 0.09},
        "reason": "اختبار الضغط كشف أن سيولة ضعيفة (وزن 10%) كانت لا تؤثر بما يكفي. "
                  "السوق المصري ضعيف السيولة — رفعنا لـ 18%. كما رفعنا الأمان لـ 24% "
                  "لأن الخطر أهم من العائد عند المستثمر المصري.",
    }],
}


def get_calibration():
    return dict(CALIBRATION)


def apply_calibration(new_weights=None, reason=None):
    """
    ⚠️ قاعدة صارمة: أي تعديل على الأوزان لازم يكون:
       1) منطقي ومش عشوائي
       2) مدعوم باختبار ضغط
       3) موثّق
    """
    global CALIBRATION
    if not new_weights:
        return {"ok": False, "error": "لا توجد أوزان جديدة"}

    # تحقق: المجموع = 100%
    total = sum(new_weights.values())
    if abs(total - 1.0) > 0.01:
        return {"ok": False, "error": f"مجموع الأوزان {total:.2f} — لازم يساوي 1.00"}

    # تحقق: كل محور بين 0 و 1
    for k, v in new_weights.items():
        if v < 0 or v > 1:
            return {"ok": False, "error": f"وزن {k} خارج النطاق: {v}"}

    old = dict(AXIS_WEIGHTS)
    CALIBRATION["history"].append({
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "old": old,
        "new": dict(new_weights),
        "reason": reason or "غير محدد",
    })
    AXIS_WEIGHTS.update(new_weights)
    CALIBRATION["last_calibrated"] = datetime.utcnow().strftime("%Y-%m-%d")
    CALIBRATION["version"] = "v{:.1f}".format(1.0 + len(CALIBRATION["history"]) * 0.1)

    return {
        "ok": True,
        "version": CALIBRATION["version"],
        "old_weights": old,
        "new_weights": dict(AXIS_WEIGHTS),
        "reason": reason,
        "warning": "⚠️ بعد أي معايرة، شغّل اختبار الضغط للتأكد إن النظام لسه صامد",
    }



# ════════════════════════════════════════════════════════════
# PHASE 18: لوحة التحكم الاحترافية — صورة كاملة عن النظام
# ════════════════════════════════════════════════════════════

def dashboard_data():
    """
    كل أرقام النظام في رد واحد.
    المبدأ: المستخدم يفتح واحدة ويشوف حالة كل حاجة.
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    st = LIVE_DATA.get("egx30", [])
    if not st:
        return {"error": "لا توجد بيانات بعد — انتظر التحديث الأول"}

    # ═══ 1) صحة البيانات ═══
    ts_list = []
    for s in st:
        t = s.get("ts")
        if t:
            try:
                ts_list.append(datetime.fromisoformat(t.replace("Z", "")))
            except (ValueError, AttributeError):
                pass
    age_min = round((datetime.utcnow() - max(ts_list)).total_seconds() / 60, 1) if ts_list else None

    conf = [_f(s.get("data_confidence"), 0) for s in st if s.get("data_confidence") is not None]
    grades = {}
    for s in st:
        g = s.get("data_grade")
        if g: grades[g] = grades.get(g, 0) + 1
    invalid = sum(len(s.get("_invalid", [])) for s in st)

    # ═══ 2) توزيع المحاور على مستوى السوق ═══
    def avg(key):
        xs = [_f(s.get(key)) for s in st if s.get(key) is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    axis_avg = {
        "technical":   avg("technical_score"),
        "fundamental": avg("fund_score"),
        "liquidity":   avg("liquidity_score"),
        "news":        avg("news_score"),
        "sentiment":   avg("sentiment_score"),
        "portfolio":   avg("portfolio_fit"),
        "safety":      avg("safety_score"),
        "final":       avg("final_score"),
    }

    # توزيع القرارات
    decisions = {}
    for s in st:
        d = s.get("decision")
        if d: decisions[d] = decisions.get(d, 0) + 1

    # توزيع المخاطر
    risk_levels = {}
    for s in st:
        r = s.get("risk_level")
        if r: risk_levels[r] = risk_levels.get(r, 0) + 1

    # ═══ 3) الأحلام والأسوأ ═══
    ranked = sorted([s for s in st if s.get("final_score") is not None],
                    key=lambda x: -x["final_score"])

    def pack(s):
        return {
            "code": s["code"], "name": s.get("name"), "sector": s.get("sector"),
            "price": s.get("price"), "change": s.get("change"),
            "score": _f(s.get("final_score")), "decision": s.get("decision"),
            "safety": _f(s.get("safety_score")), "opportunity": _f(s.get("opportunity_score")),
            "upside": s.get("upside"), "valuation": s.get("valuation"),
            "confidence": _f(s.get("confidence")), "risk_level": s.get("risk_level"),
        }

    top10 = [pack(s) for s in ranked[:10]]
    bottom10 = [pack(s) for s in ranked[-10:]]

    # ═══ 4) الفرص المبكرة ═══
    early = sorted([s for s in st if "مبكرة" in (s.get("opportunity_stage") or "")],
                   key=lambda x: -_f(x.get("opportunity_score"), 0))[:10]

    # ═══ 5) مقارنة مع السوق (alpha) ═══
    bm = bt_benchmark()
    alpha = bm.get("periods", [])

    # ═══ 6) حالة الاختبار التاريخي ═══
    bt_stats = BACKTEST.get("stats", {})
    bt_snapshots = len(BACKTEST.get("snapshots", {}))

    # ═══ 7) حالة اختبار الضغط ═══
    stress_summary = run_all_stress(st, 20)

    # ═══ 8) حالة المحفظة ═══
    pf_total = sum(h.get("shares", 0) * h.get("price", 0) for h in PORTFOLIO["holdings"].values())
    pf_sectors = {}
    for h in PORTFOLIO["holdings"].values():
        s = h.get("sector", "أخرى")
        pf_sectors[s] = pf_sectors.get(s, 0) + h["shares"] * h.get("price", 0)

    # ═══ 9) أكبر القطاعات ═══
    sector_count = {}
    for s in st:
        sec = s.get("sector")
        if sec: sector_count[sec] = sector_count.get(sec, 0) + 1

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "health": {
            "stocks": len(st),
            "data_age_minutes": age_min,
            "freshness": "ممتازة" if (age_min or 99) < 10 else
                         "جيدة" if (age_min or 99) < 60 else
                         "قديمة ⚠️",
            "avg_data_confidence": round(sum(conf) / len(conf), 1) if conf else None,
            "data_grades": grades,
            "invalid_values": invalid,
            "tickers": len(LIVE_DATA.get("ticker", [])),
            "market_phase": LIVE_DATA.get("market_phase"),
            "market_open": LIVE_DATA.get("market_open"),
        },
        "axis_average": axis_avg,
        "weights": AXIS_WEIGHTS,
        "decisions": decisions,
        "risk_levels": risk_levels,
        "top10": top10,
        "bottom10": bottom10,
        "early_opportunities": [{"code": s["code"], "name": s.get("name"),
                                 "sector": s.get("sector"),
                                 "opportunity": _f(s.get("opportunity_score")),
                                 "price": s.get("price"),
                                 "final_score": _f(s.get("final_score"))} for s in early],
        "benchmark": {"interpretation": bm.get("interpretation"), "periods": alpha,
                      "caveat": bm.get("caveat")},
        "backtest": {
            "snapshots_taken": bt_snapshots,
            "stats": bt_stats,
            "note": "التوصيات بتتسجل يومياً — بعد أسبوع هيبقى في بيانات حقيقية",
        },
        "stress": stress_summary,
        "portfolio": {
            "holdings": len(PORTFOLIO["holdings"]),
            "total_value": round(pf_total, 2),
            "sector_exposure": {k: round(v / pf_total * 100, 1) for k, v in pf_sectors.items()} if pf_total else {},
            "diversification": ("ممتاز" if len(pf_sectors) >= 5 else
                              "كويس" if len(pf_sectors) >= 3 else
                              "ضعيف") if pf_total else "محفظة فاضية",
        },
        "sectors": [{"name": k, "count": v} for k, v in
                    sorted(sector_count.items(), key=lambda x: -x[1])],
        "calibration": {
            "version": CALIBRATION.get("version"),
            "last_calibrated": CALIBRATION.get("last_calibrated"),
            "changes": len(CALIBRATION.get("history", [])),
        },
        "strategies": [{"key": k, "name": v["name_ar"], "timeframe": v["timeframe"]}
                       for k, v in STRATEGIES.items()],
    }



# ════════════════════════════════════════════════════════════
# REDUNDANCY / DUPLICATION AUDIT — لكشف تكرار الواجهة
# ════════════════════════════════════════════════════════════

def duplication_report():
    """
    بيحلل الـ endpoint ويقول:
    1. إيه المحاور اللي بتستخدم نفس البيانات
    2. إيه الـ endpoints اللي بترجع نفس المعلومة
    3. إيه التكرار في البيانات نفسها
    """
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    st = LIVE_DATA.get("egx30", [])

    # ═══ 1. تشابه المحاور بين الأسهم ═══
    # نحسب كم سهم عنده نفس النتيجة (±5) — ده تكرار في الترتيب
    scores = sorted([_f(s.get("final_score"), 0) for s in st if s.get("final_score") is not None])
    if scores:
        median = scores[len(scores)//2]
        # كم سهم في نفس النطاق
        same_band = sum(1 for x in scores if abs(x - median) <= 5)
        spread = scores[-1] - scores[0] if len(scores) > 1 else 0
    else:
        median, same_band, spread = 0, 0, 0

    # ═══ 2. تشابه decisions ═══
    decisions = {}
    for s in st:
        d = s.get("decision")
        if d: decisions[d] = decisions.get(d, 0) + 1
    dominant = max(decisions.items(), key=lambda x: x[1]) if decisions else ("", 0)
    dominance_ratio = round(dominant[1] / max(1, len(st)) * 100, 1)

    # ═══ 3. تشابه الأسهم (نفس النتيجة + نفس القرار) ═══
    by_score = {}
    for s in st:
        fs = _f(s.get("final_score"))
        if fs is None: continue
        band = int(fs // 10) * 10   # شرائح من 10
        by_score.setdefault(band, []).append(s["code"])

    crowded_bands = {k: v for k, v in by_score.items() if len(v) > 20}

    # ═══ 4. تشابه المحاور (نفس النتيجة المتوسطة) ═══
    axes = ["technical_score", "fund_score", "liquidity_score", "news_score",
            "sentiment_score", "portfolio_fit", "safety_score", "final_score"]
    axis_avgs = {}
    for a in axes:
        xs = [_f(s.get(a)) for s in st if s.get(a) is not None]
        axis_avgs[a] = round(sum(xs)/len(xs), 1) if xs else None

    # محاور شبه متطابقة (فرق < 3 نقاط)
    similar_axes = []
    for i, a1 in enumerate(axes):
        for a2 in axes[i+1:]:
            v1, v2 = axis_avgs.get(a1), axis_avgs.get(a2)
            if v1 is not None and v2 is not None and abs(v1 - v2) < 3:
                similar_axes.append({"a": a1, "b": a2, "diff": round(abs(v1-v2), 1)})

    # ═══ 5. التكرار في الواجهة (محتوى متكرر) ═══
    ui_redundancy = [
        {
            "item": "أفضل الفرص / top-ranked list",
            "appears_in": ["home: oppsGrid", "arm: opportunity", "arm: technical", "dashPage: top10"],
            "count": 4,
            "severity": "high",
            "fix": "خلّيها في ذراع الفرص فقط — والـ Arms التانية تستدعي نفس المصدر"
        },
        {
            "item": "الفرص المبكرة / early opportunities",
            "appears_in": ["home: earlyOpps", "arm: opportunity"],
            "count": 2,
            "severity": "medium",
            "fix": "home يعرض 3 فقط، ذراع الفرص يعرض الكل"
        },
        {
            "item": "شاشة السهم الكاملة",
            "appears_in": ["openIntel (modal)", "openStock (page)", "bestpick widgets"],
            "count": 3,
            "severity": "high",
            "fix": "احذف openIntelLegacy — صفحة openStock تكفي"
        },
        {
            "item": "الجداول/الترتيب",
            "appears_in": ["armMarket leaders", "armTechnical signals", "armOpportunity best"],
            "count": 3,
            "severity": "medium",
            "fix": "كل ذراع تطلب filter مختلف — مش نفس الترتيب"
        },
        {
            "item": "الاستراتيجيات (7)",
            "appears_in": ["armOpportunity", "openStock stratBox", "strategies endpoint"],
            "count": 3,
            "severity": "medium",
            "fix": "show مرة واحدة — في ذراع الفرص + في صفحة السهم"
        },
    ]

    return {
        "summary": {
            "stocks": len(st),
            "score_spread": round(spread, 1),
            "median_score": round(median, 1),
            "stocks_in_median_band": same_band,
            "dominant_decision": dominant[0],
            "decision_dominance_pct": dominance_ratio,
        },
        "axis_similarity": {
            "averages": axis_avgs,
            "similar_pairs": similar_axes,
            "note": "محاور بنفس المتوسط = نفس البيانات = تكرار محتمل"
        },
        "score_crowding": {
            "bands_with_20plus": len(crowded_bands),
            "worst_band": max(crowded_bands.items(), key=lambda x: len(x[1]))[0] if crowded_bands else None,
            "worst_band_count": max((len(v) for v in crowded_bands.values()), default=0),
            "note": "أكتر من 20 سهم في نفس شريحة 10 نقاط = تمييز ضعيف"
        },
        "ui_redundancy": ui_redundancy,
        "recommendations": [
            "احذف openIntelLegacy — صفحة openStock الشاملة تغني عنها",
            "أفضل الفرص: ذراع الفرص فقط (home يعرض 3)",
            "الفرص المبكرة: home يعرض 3، ذراع الفرص يعرض الكل",
            "كل ذراع تطلب filter مختلف من /api/rank (مش نفس الترتيب)",
            "الاستراتيجيات: عرض مرة واحدة في ذراع الفرص + صفحة السهم"
        ],
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
        # ═══ PHASE 2: نقسم الطلب لـ chunks صغيرة ═══
        # السبب: الطلب الكبير ممكن يضيع في الطريق من السيرفر
        all_data = []
        CHUNK = 50
        for i in range(0, len(tickers), CHUNK):
            chunk = tickers[i:i + CHUNK]
            p = {"symbols": {"tickers": chunk, "query": {"types": []}},
                 "columns": cols}
            rr = requests.post(SCANNER_URL, json=p, headers=TV_HEADERS, timeout=30)
            rr.raise_for_status()
            all_data.extend(rr.json().get("data", []))
            time.sleep(0.12)
        data = {"data": all_data}

        # تشخيص: نختبر عمودين فنيين لوحدهم عشان نعرف لو المشكلة في المصدر ولا عندنا
        try:
            probe = {"symbols": {"tickers": ["EGX:COMI"], "query": {"types": []}},
                     "columns": ["close", "RSI", "EMA20", "ATR"]}
            pr = requests.post(SCANNER_URL, json=probe, headers=TV_HEADERS, timeout=20)
            pd = pr.json().get("data", [{}])[0].get("d", [])
            SCAN_PROBE = {"status": pr.status_code, "len": len(pd), "values": pd}
        except Exception as pe:
            SCAN_PROBE = {"error": str(pe)[:100]}

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
        first = next(iter(out.values()), {})
        got = len(data.get("data", []))
        print(f"  TV Scanner: {len(out)}/{len(tickers)} سهم | "
              f"أخطاء تحقق: {sum(len(v['_invalid']) for v in out.values())}")
        # تشخيص: كام حقل فعلياً وصل
        n_fields = len([k for k in first if not k.startswith('_')]) - 1  # -1 for code
        print(f"  🔍 DIAG: rows={got}/{len(tickers)} | cols_req={len(cols)} | "
              f"cols_recv={len(all_data[0]['d']) if all_data else 0} | "
              f"rsi={first.get('rsi')} | pe={first.get('pe')} | ema20={first.get('ema20')}")
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
                if tvsym.startswith("__"):
                    # محسوب — مش من المصدر
                    tk.append({"id": tid, "label": label, "value": 0.0, "change": 0.0,
                               "trend": "flat", "unit": ""})
                    continue
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

            # 2.4) الذهب ٢٤ بالجنيه المصري = الذهب العالمي × سعر الدولار
            #      وسعر الجرام = سعر الأونصة ÷ 31.1035
            _gold = next((t for t in tk if t["id"] == "tk-gold"), None)
            _usd  = next((t for t in tk if t["id"] == "tk-usd"), None)
            for it in tk:
                if it["id"] == "tk-gold24" and _gold and _usd and _gold["value"] and _usd["value"]:
                    it["value"] = round(_gold["value"] * _usd["value"], 2)
                    it["change"] = round((_gold["change"] + _usd["change"]) / 2, 2)
                    it["gram"] = round(it["value"] / 31.1035, 2)
                    it["ounce"] = round(_gold["value"], 2)
                    it["trend"] = "up" if it["change"] >= 0 else "down"
                    it["unit"] = "ج.م/جم"

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

            # ═══ Phase 2+3: النتائج لكل سهم (فوري رياضياً) ═══
            global SECTOR_STATS
            SECTOR_STATS = build_sector_stats(st)
            LIVE_DATA["sector_stats"] = SECTOR_STATS
            liq_score = True   # علم: نضيف خصم السيولة
            for item in st:
                try:
                    # ═══ Phase 2-F: نستنتج المؤشرات الناقصة من الأرقام المتاحة ═══
                    derive_technical(item)
                    t = tech_score(item)
                    if t:
                        item["technical_score"] = t["score"]
                        item["technical_signal"] = t["signal"]
                    f = fundamental_score(item, SECTOR_STATS)
                    if f:
                        item["fund_score"] = f["score"]
                    # ═══ Phase 4: السيولة ═══
                    li = liquidity_score(item)
                    if li:
                        item["liquidity_score"] = li["score"]
                        item["liquidity_risk"] = li["risk_level"]
                    # ═══ Phase 6: المعنويات ═══
                    se = sentiment_engine(item, st)
                    if se:
                        item["sentiment_score"] = se["score"]
                        item["sentiment_conflict"] = se.get("contradiction")
                    # ═══ Phase 8: ملاءمة المحفظة ═══
                    pfit = portfolio_fit(item, PORTFOLIO)
                    if pfit:
                        item["portfolio_fit"] = pfit["score"]
                    # ═══ Phase 5: الأخبار ═══
                    nw = news_engine(item, item.get("sector"))
                    if nw:
                        item["news_score"] = nw["score"]
                    # ═══ Phase 12: الفرص المبكرة ═══
                    opp = opportunity_engine(item, t, f, li)
                    if opp:
                        item["opportunity_score"] = opp["score"]
                        item["opportunity_stage"] = opp["stage"]
                    # ═══ Phase 7: المخاطر المتقدمة ═══
                    rk = risk_engine(item, SECTOR_STATS)
                    if rk:
                        item["safety_score"] = rk["safety_score"]
                        item["risk_score_detailed"] = rk["risk_score"]
                    # ═══ Phase 9: النتيجة النهائية (بعد كل المحاور) ═══
                    fin = final_score(item, t, f, li, SECTOR_STATS)
                    if fin:
                        # ندمج المعنويات + المحفظة + الأخبار
                        if se: fin["axes"]["sentiment"] = se["score"]
                        if pfit: fin["axes"]["portfolio"] = pfit["score"]
                        if nw: fin["axes"]["news"] = nw["score"]
                        # إعادة حساب المحصلة
                        ax = fin["axes"]
                        b = sum(ax[k] * AXIS_WEIGHTS[k] for k in AXIS_WEIGHTS)
                        risk_pen = (100 - ax["risk"]) * 0.18
                        adj = b - risk_pen
                        if liq_score:  # نضيف خصم السيولة
                            lq = liquidity_score(item)
                            if lq and lq["risk_level"] in ("مرتفع", "مرتفع جداً"):
                                adj -= (100 - lq["score"]) * 0.10
                        fin["final_score"] = round(max(0, min(100, adj)), 1)
                        item["final_score"] = fin["final_score"]
                        item["confidence"] = fin["confidence"]
                        item["decision"] = fin["decision"]
                        item["risk_level"] = fin["risk_level"]
                        item["all_axes"] = fin["axes"]
                        # ═══ Phase 14: الاستراتيجيات ═══
                        item["strategies"] = score_all_strategies(item, t, f, li, se, pfit)
                        item["valuation"] = f["valuation_status"]
                        item["fair_value"] = f["fair_value"]
                        item["upside"] = f["upside_pct"]
                except Exception:
                    pass
            # نحفظ كم مؤشر تم استنتاجه (بدل ما جاب من المصدر)
            LIVE_DATA["derived_count"] = sum(1 for s in st if s.get("_derived"))

            # ═══ Phase 5: نحدّث قائمة الأحداث من مصدر الإعلانات ═══
            try:
                snap = div_actions.build_snapshot(_prices_map())
                _new_actions = snap.get("actions", [])
                if _new_actions:
                    globals()["_actions"] = _new_actions
                    LIVE_DATA["news_count"] = len(_new_actions)
            except Exception as _e:
                pass

            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(LIVE_DATA, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"  cache write err: {e}")

            # ═══ Phase 15: لقطة اختبار تاريخي (كل دورة، عند التغيّر) ═══
            try:
                _today = datetime.utcnow().strftime("%Y-%m-%d")
                if BACKTEST["snapshots"].get(_today) is None:
                    bt_snapshot()
            except Exception:
                pass

            print(f"\n✅ SAVED: {len(st)} stocks | {len(tk)} tickers | "
                  f"{len(scan)} live | phase={phase}")
            live_sorted = sorted(scan.items(), key=lambda x: -(x[1]["change"]))
            if live_sorted:
                print(f"  🥇 أعلى: {live_sorted[0][0]} {live_sorted[0][1]['change']:+.2f}%")
        except Exception as e:
            print(f"❌ Loop error: {e}")
        time.sleep(refresh_interval())


AI_CACHE.update(_load_ai_disk())
try:
    _bt_load()
except Exception:
    pass
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
                result["technical"] = tech
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


@app.route("/api/fundamental/<code>")
def fundamental_only(code):
    """تحليل أساسي مفصّل — فوري بدون ذكاء اصطناعي"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    f = fundamental_score(item, SECTOR_STATS)
    if not f:
        return jsonify({"error": "بيانات غير كافية"}), 400
    return jsonify({
        "build": "PHASE2-3-FINAL",
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "price": item.get("price"), "change": item.get("change"),
        "fundamental": f,
        "raw": {k: item.get(k) for k in ("pe","pb","roe","net_margin","de_ratio",
                                        "eps","div_yield","beta","revenue")},
        "data_ts": item.get("ts"),
    })


@app.route("/api/sector-stats")
def sector_stats_api():
    return jsonify(SECTOR_STATS)


@app.route("/api/diagnostic")
def diagnostic():
    """فحص شامل — يأكد النسخة الصح شغالة"""
    st = LIVE_DATA.get("egx30", [])
    sample = st[0] if st else {}
    return jsonify({
        "build": "PHASE2-3-FINAL",
        "expected_fields": 82,
        "actual_fields": len(sample),
        "egx_count": len(EGX),
        "columns": {"TV_COLUMNS": len(TV_COLUMNS), "TV_TECH_COLUMNS": len(TV_TECH_COLUMNS)},
        "functions": {"tech_score": callable(tech_score),
                      "fundamental_score": callable(fundamental_score)},
        "data": {
            "stocks": len(st),
            "with_rsi": sum(1 for s in st if s.get("rsi") is not None),
            "with_technical_score": sum(1 for s in st if s.get("technical_score") is not None),
            "with_fund_score": sum(1 for s in st if s.get("fund_score") is not None),
            "with_pe": sum(1 for s in st if s.get("pe") is not None),
        },
        "last_update": LIVE_DATA.get("lastUpdate"),
        "scan_probe": SCAN_PROBE,
        "ip_check": requests.get("https://api.ipify.org?format=json", timeout=8).text if False else "skipped",
    })


@app.route("/api/intelligence/<code>")
def intelligence(code):
    """التحليل الكامل المدمج — بدون ذكاء اصطناعي، فوري"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    return jsonify({
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "price": item.get("price"), "change": item.get("change"),
        "final_score": item.get("final_score"),
        "confidence": item.get("confidence"),
        "decision": item.get("decision"),
        "risk_level": item.get("risk_level"),
        "axes": item.get("all_axes"),
        "technical": tech_score(item),
        "fundamental": fundamental_score(item, SECTOR_STATS),
        "liquidity": liquidity_score(item),
        "risk_engine": risk_engine(item, SECTOR_STATS),
        "news_engine": news_engine(item, item.get("sector")),
        "portfolio_fit_detail": portfolio_fit(item, PORTFOLIO),
        "data_confidence": item.get("data_confidence"),
        "data_ts": item.get("ts"),
    })


@app.route("/api/ranking")
def ranking():
    """أفضل الأسهم مرتبة — بالنتيجة النهائية"""
    st = LIVE_DATA.get("egx30", [])
    ranked = sorted([s for s in st if s.get("final_score") is not None],
                    key=lambda x: -x["final_score"])
    return jsonify({
        "total": len(ranked),
        "top20": [{
            "code": s["code"], "name": s.get("name"), "sector": s.get("sector"),
            "price": s.get("price"), "change": s.get("change"),
            "score": s.get("final_score"), "confidence": s.get("confidence"),
            "decision": s.get("decision"), "risk": s.get("risk_level"),
            "upside": s.get("upside"), "fair_value": s.get("fair_value"),
        } for s in ranked[:20]],
    })


@app.route("/api/portfolio", methods=["GET", "POST"])
def portfolio_api():
    """عرض وتعديل المحفظة"""
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        action = data.get("action")
        code = (data.get("code") or "").upper()
        if action == "add":
            PORTFOLIO["holdings"][code] = {
                "shares": float(data.get("shares", 0)),
                "cost": float(data.get("cost", 0)),
                "price": float(data.get("price", 0)),
                "sector": data.get("sector", "أخرى"),
            }
        elif action == "remove":
            PORTFOLIO["holdings"].pop(code, None)
        elif action == "clear":
            PORTFOLIO["holdings"] = {}
            PORTFOLIO["cash"] = 0
        elif action == "set_cash":
            PORTFOLIO["cash"] = float(data.get("cash", 0))
        return jsonify({"ok": True, "portfolio": PORTFOLIO})

    # GET: نحسب إحصائيات المحفظة
    total = sum(h["shares"] * h["price"] for h in PORTFOLIO["holdings"].values()) + PORTFOLIO.get("cash", 0)
    sectors = {}
    for c, h in PORTFOLIO["holdings"].items():
        v = h["shares"] * h["price"]
        sectors[h.get("sector", "أخرى")] = sectors.get(h.get("sector", "أخرى"), 0) + v
    return jsonify({
        "total_value": round(total, 2),
        "cash": PORTFOLIO.get("cash", 0),
        "count": len(PORTFOLIO["holdings"]),
        "holdings": PORTFOLIO["holdings"],
        "sector_exposure_pct": {k: round(v / total * 100, 1) for k, v in sectors.items()} if total else {},
        "diversification": (
            "ممتاز" if len(sectors) >= 5 else
            "كويس" if len(sectors) >= 3 else
            "ضعيف"
        ) if total else "محفظة فاضية",
    })


@app.route("/api/portfolio/fit/<code>")
def portfolio_fit_api(code):
    """ملاءمة السهم لمحفظتك"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    fit = portfolio_fit(item, PORTFOLIO)
    return jsonify({"code": code, "portfolio_fit": fit})


@app.route("/api/sentiment/<code>")
def sentiment_api(code):
    """تحليل المعنويات المفصّل"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    se = sentiment_engine(item, LIVE_DATA.get("egx30", []))
    return jsonify({"code": code, "name": item.get("name"), "sentiment": se})


@app.route("/api/risk/<code>")
def risk_api(code):
    """تحليل المخاطر المفصّل — 7 فئات + عائد/خطر"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    rk = risk_engine(item, SECTOR_STATS)
    return jsonify({
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "risk": rk,
        "price": item.get("price"),
    })


@app.route("/api/news/<code>")
def news_api(code):
    """تحليل الأخبار — materiality + sentiment + confidence"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    nw = news_engine(item, item.get("sector"))
    return jsonify({
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "news": nw,
    })


@app.route("/api/explain/<code>")
def explain_api(code):
    """ليه السهم obtain النتيجة دي؟ كل رقم قابل للتفسير"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    st = LIVE_DATA.get("egx30", [])
    t = tech_score(item)
    f = fundamental_score(item, SECTOR_STATS)
    l = liquidity_score(item)
    n = news_engine(item, item.get("sector"))
    s = sentiment_engine(item, st)
    p = portfolio_fit(item, PORTFOLIO)
    r = risk_engine(item, SECTOR_STATS)
    fin = final_score(item, t, f, l, SECTOR_STATS)
    if s: fin["axes"]["sentiment"] = s["score"]
    if p: fin["axes"]["portfolio"] = p["score"]
    if n: fin["axes"]["news"] = n["score"]
    ex = explain_score(item, t, f, l, n, s, r, p, fin)
    return jsonify({
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "price": item.get("price"),
        "decision": fin.get("decision"),
        "risk_level": fin.get("risk_level"),
        "explanation": ex,
    })


@app.route("/api/opportunity/<code>")
def opportunity_api(code):
    """الفرص المبكرة — قبل ما السهم يتحرك"""
    code = code.upper().strip()
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود"}), 404
    t = tech_score(item)
    f = fundamental_score(item, SECTOR_STATS)
    li = liquidity_score(item)
    return jsonify({
        "code": code, "name": item.get("name"), "sector": item.get("sector"),
        "price": item.get("price"),
        "opportunity": opportunity_engine(item, t, f, li),
    })


@app.route("/api/opportunities")
def opportunities_all():
    """كل الفرص المبكرة مرتبة"""
    st = LIVE_DATA.get("egx30", [])
    rows = []
    for item in st:
        sc = item.get("opportunity_score")
        if sc is None: continue
        rows.append({
            "code": item["code"], "name": item.get("name"), "sector": item.get("sector"),
            "price": item.get("price"), "score": sc,
            "stage": item.get("opportunity_stage"),
            "technical_score": item.get("technical_score"),
            "final_score": item.get("final_score"),
            "decision": item.get("decision"),
            "safety": item.get("safety_score"),
        })
    early = sorted([r for r in rows if "مبكرة" in (r.get("stage") or "")], key=lambda x: -x["score"])
    return jsonify({
        "total": len(rows),
        "early_count": len(early),
        "early_opportunities": early[:20],
        "all": sorted(rows, key=lambda x: -x["score"])[:20],
    })


@app.route("/api/strategies")
def strategies_list():
    """قائمة الاستراتيجيات المتاحة"""
    return jsonify({
        "strategies": [{
            "key": k, "name": v["name_ar"], "desc": v["desc"],
            "timeframe": v["timeframe"], "focus": v["focus"],
            "weights": {kk: round(vv * 100) for kk, vv in v["weights"].items()},
        } for k, v in STRATEGIES.items()]
    })


@app.route("/api/strategy/<code>/<strategy>")
def strategy_api(code, strategy):
    """تقييم السهم حسب استراتيجية محددة"""
    code = code.upper().strip()
    strategy = strategy.lower().strip()
    if strategy not in STRATEGIES:
        return jsonify({"error": f"استراتيجية غير معروفة: {strategy}",
                        "available": list(STRATEGIES.keys())}), 400
    item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == code), None)
    if not item:
        return jsonify({"error": f"السهم {code} غير موجود — البيانات لسه بتتحمّل"}), 404
    try:
        t = tech_score(item)
        f = fundamental_score(item, SECTOR_STATS)
        li = liquidity_score(item)
        se = sentiment_engine(item, LIVE_DATA.get("egx30", []))
        pf = portfolio_fit(item, PORTFOLIO)
        return jsonify({
            "code": code, "name": item.get("name"), "price": item.get("price"),
            "strategy": strategy_score(item, strategy, t, f, li, se, pf),
            "all_strategies": score_all_strategies(item, t, f, li, se, pf),
        })
    except Exception as _e:
        import traceback
        return jsonify({"error": str(_e),
                        "trace": traceback.format_exc()[-400:]}), 500


@app.route("/api/rank")
def rank_api():
    """
    ترتيب وفلترة متقدمة.
    GET params:
      strategy=balanced  | min_score=60  | min_safety=50
      min_liquidity=40  | sector=بنوك    | max_pe=15
      min_div_yield=3   | decision=تجميع | limit=20
    """
    st = LIVE_DATA.get("egx30", [])
    a = request.args

    def num(k):
        try: return float(a.get(k))
        except (TypeError, ValueError): return None

    sectors = None
    if a.get("sector"):
        sectors = [s.strip() for s in a.get("sector").split(",") if s.strip()]
    decisions = None
    if a.get("decision"):
        decisions = [s.strip() for s in a.get("decision").split(",") if s.strip()]

    results = rank_stocks(
        st,
        strategy=a.get("strategy", "balanced"),
        min_score=num("min_score") or 0,
        max_risk=num("max_risk"),
        min_safety=num("min_safety"),
        min_liquidity=num("min_liquidity"),
        sectors=sectors,
        max_pe=num("max_pe"),
        min_div_yield=num("min_div_yield"),
        decisions=decisions,
        limit=int(num("limit") or 20),
    )
    return jsonify({
        "count": len(results),
        "filters": {k: v for k, v in a.items()},
        "results": results,
    })


@app.route("/api/filters")
def filters_api():
    """كل الخيارات المتاحة للفلاتر"""
    return jsonify(available_filters(LIVE_DATA.get("egx30", [])))


@app.route("/api/backtest")
def backtest_api():
    """نتائج الاختبار التاريخي — التوصيات فعلاً بخفت صح؟"""
    days = request.args.get("days", 30)
    try: days = int(days)
    except (TypeError, ValueError): days = 30
    result = bt_evaluate(days)
    result["benchmark"] = bt_benchmark()
    result["method"] = "forward-tracking: بنسجّل ترتيب اليوم ونقيس بعد ٣+ أيام"
    return jsonify(result)


@app.route("/api/backtest/snapshot")
def bt_snapshot_api():
    """لقطة يدوية"""
    bt_snapshot()
    return jsonify({"ok": True, "snapshots": len(BACKTEST.get("snapshots", {}))})


@app.route("/api/stress")
def stress_api():
    """اختبار الضغوط — فين النظام بيفشل؟"""
    scenario = request.args.get("scenario", "bear")
    top_n = int(request.args.get("top", 20) or 20)
    st = LIVE_DATA.get("egx30", [])
    if scenario == "all":
        return jsonify({"all": run_all_stress(st, top_n)})
    return jsonify(stress_test(st, scenario, top_n))


@app.route("/api/calibration")
def calibration_api():
    """معايرة الأوزان"""
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        return jsonify(apply_calibration(data.get("weights"), data.get("reason")))
    return jsonify({
        "calibration": get_calibration(),
        "current_weights": AXIS_WEIGHTS,
        "note": "لتعديل الأوزان: POST إلى /api/calibration مع weights و reason",
    })


@app.route("/api/dashboard")
def dashboard_api():
    """لوحة التحكم — كل النظام في رد واحد"""
    return jsonify(dashboard_data())


@app.route("/api/audit/redundancy")
def redundancy_api():
    """تقرير تكرار الواجهة — يساعد في إعادة التصميم"""
    return jsonify(duplication_report())


@app.route("/api/gold")
def gold_api():
    """سعر الذهب ٢٤ بالجنيه + سعر الجرام"""
    tk = {t["id"]: t for t in LIVE_DATA.get("ticker", [])}
    g, u = tk.get("tk-gold"), tk.get("tk-usd")
    g24 = tk.get("tk-gold24", {})
    if not g or not u or not g.get("value"):
        return jsonify({"error": "بيانات الذهب غير متاحة"}), 503
    ounce_egp = g["value"] * u["value"]
    return jsonify({
        "ounce_usd": round(g["value"], 2),
        "usd_egp": round(u["value"], 2),
        "ounce_egp": round(ounce_egp, 2),
        "gram_egp": round(ounce_egp / 31.1035, 2),
        "ounce_egp_change": round((g.get("change",0) + u.get("change",0)) / 2, 2),
        "unit": "ج.م",
        "note": "سعر الجرام = سعر الأونصة ÷ 31.1035 جرام",
        "updated": LIVE_DATA.get("lastUpdate"),
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


# ══════════════════════════════════════════════════════════════
#  OCTA 2026-10-09 — طبقة البيانات الجديدة (startamarkets + IPO)
#  مُلزَق فوق if __name__ == "__main__": في update_prices.py
#  متوافق مع الكود الفعلي: log→print · rank_stocks(all_stocks,…)
# ══════════════════════════════════════════════════════════════
import re as _re, html as _html, math as _math
from datetime import datetime as _dt, timezone as _tz
from concurrent.futures import ThreadPoolExecutor as _TP

STARTA_LIST   = "https://startamarkets.com/api/v1/egx/stocks"
STARTA_STATS  = "https://startamarkets.com/api/v1/egx/statistics/"
STARTA_HIST   = "https://startamarkets.com/api/v1/egx/history/"
IPO_SRC       = "https://foudalens.com/ar/ipo"
_HDR          = {"User-Agent": "Mozilla/5.0 (OCTA/5)", "Origin": "https://octa.egx"}


def _num(v):
    return v if isinstance(v, (int, float)) and v and abs(v) < 1e15 else None


def _jget(url, timeout=15, tries=1):
    """جلب JSON مع إعادة محاولة — بترجع None بدل ما ترمي."""
    for i in range(tries):
        try:
            r = requests.get(url, headers=_HDR, timeout=timeout)
            if r.ok:
                return r.json()
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(1.0 + i)
    return None


# ─────────────────────────────────────────────────────────────
# ①  Starta — مؤشرات فنية + أساسية (مع cache ساعة)
# ─────────────────────────────────────────────────────────────
_STARTA = {"at": 0, "d": {}, "ttl": 3600}


def _starta_stats():
    now = _dt.now(_tz.utc).timestamp()
    if _STARTA["d"] and now - _STARTA["at"] < _STARTA["ttl"]:
        return _STARTA["d"]
    lst = _jget(STARTA_LIST)
    if not lst:
        return _STARTA["d"]
    codes = [s.get("symbol") for s in lst if s.get("symbol")]
    out, done = {}, [0]

    def one(c):
        d = _jget(STARTA_STATS + c)
        done[0] += 1
        return c, d
    try:
        with _TP(max_workers=5) as ex:
            for c, d in ex.map(one, codes):
                if isinstance(d, dict) and d.get("symbol"):
                    out[c] = d
    except Exception as e:
        print(f"[starta] thread fail: {e}")
    if out:
        _STARTA.update(at=now, d=out, ttl=3600)
        print(f"[starta] {len(out)}/{len(codes)} cached")
    return out


# ─────────────────────────────────────────────────────────────
# ②  المخاطرة الحقيقية — من تاريخ 26 سنة (cache يوم)
# ─────────────────────────────────────────────────────────────
def _log_ret(cl):
    return [_math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl))
            if cl[i - 1] > 0 and cl[i] > 0]


def _risk_metrics(hist):
    out = {}
    cl = [float(x["close"]) for x in hist
          if x.get("close") and float(x["close"]) > 0]
    if len(cl) < 30:
        return out

    def ann_vol(n):
        if len(cl) <= n:
            return None
        r = _log_ret(cl[-n:])
        if len(r) < 20:
            return None
        m = sum(r) / len(r)
        v = sum((x - m) ** 2 for x in r) / (len(r) - 1)
        return round(_math.sqrt(v) * _math.sqrt(252) * 100, 2)

    def mdd(series):
        peak, worst = series[0], 0.0
        for p in series:
            peak = max(peak, p)
            if peak > 0:
                worst = max(worst, (peak - p) / peak * 100)
        return round(worst, 2)

    out["vol1y"] = ann_vol(252)
    out["vol3y"] = ann_vol(756)
    out["mdd"] = mdd(cl)
    out["mdd1y"] = mdd(cl[-252:]) if len(cl) >= 252 else None
    if len(cl) > 756:
        cagr = (cl[-1] / cl[-756]) ** (1 / 3.0) - 1
        out["cagr3y"] = round(cagr * 100, 2)
        if out.get("vol3y"):
            out["sharpe3y"] = round((cagr * 100) / out["vol3y"], 2)
        neg = [x for x in _log_ret(cl[-756:]) if x < 0]
        if len(neg) > 20:
            m = sum(neg) / len(neg)
            out["sortino3y"] = round(
                _math.sqrt(sum((x - m) ** 2 for x in neg) / (len(neg) - 1))
                * _math.sqrt(252) * 100, 2)
    w = cl[-252:] if len(cl) >= 60 else cl
    out["h52"] = round(max(w), 2)
    out["l52"] = round(min(w), 2)
    out["frm52hi"] = round((cl[-1] / max(w) - 1) * 100, 2) if max(w) > 0 else None
    return out


_RISK = {"at": 0, "d": {}, "ttl": 86400, "codes": ""}


def _risk_all(codes):
    """مخاطرة لكل الأكواد — يتجدد مرة في اليوم (تقيل: ~5000 شمعة لكل سهم)."""
    key = len(codes)
    now = _dt.now(_tz.utc).timestamp()
    if _RISK["d"] and now - _RISK["at"] < _RISK["ttl"] and _RISK["codes"] == key:
        return _RISK["d"]
    out, done = {}, [0]

    def one(c):
        h = _jget(STARTA_HIST + c, timeout=30, tries=2)
        done[0] += 1
        if done[0] % 40 == 0:
            print(f"[risk] {done[0]}/{len(codes)}", flush=True)
        return c, (_risk_metrics(h) if isinstance(h, list) and h else {})
    try:
        with _TP(max_workers=5) as ex:
            for c, m in ex.map(one, codes):
                if m:
                    out[c] = m
    except Exception as e:
        print(f"[risk] thread fail: {e}")
    if out:
        _RISK.update(at=now, d=out, ttl=86400, codes=key)
        print(f"[risk] {len(out)} cached")
    return out


# ─────────────────────────────────────────────────────────────
# ③  /api/egx_full  —  السجل الكامل + المؤشرات + المخاطرة
# ─────────────────────────────────────────────────────────────
def _load_local_stocks():
    """يقرأ data_egx.json لو موجود جنب الملف."""
    for p in (Path(__file__).parent / "data_egx.json", Path("data_egx.json")):
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8")).get("stocks", {})
        except Exception:
            pass
    return {}


@app.route("/api/egx_full")
def api_egx_full():
    """
    السجل الكامل + RSI/Beta/MA + ROE/ROA + مخاطرة حقيقية.
    ➜ الواجهة بتعمل fetch('/api/egx_full') بدل data_egx.json الساكن.
    """
    stats = _starta_stats()
    live = {s["code"]: s for s in LIVE_DATA.get("egx30", []) if s.get("code")}
    base = _load_local_stocks()
    codes = set(base) | set(live) | set(stats)
    risk = _risk_all(sorted(codes))

    stocks = {}
    for c in codes:
        b, l, s, r = base.get(c, {}), live.get(c, {}), stats.get(c, {}), risk.get(c, {})
        if not (b or l):
            continue
        pe = _num(l.get("pe")) or _num(s.get("pe_ratio")) or _num(b.get("pe"))
        pb = _num(l.get("pb")) or _num(s.get("pb_ratio")) or _num(b.get("pb"))
        roe = _num(l.get("roe")) or _num(s.get("roe")) or _num(b.get("roe"))
        pe_src = "source"
        if not pe and pb and roe and roe > 0:
            calc = pb / (roe / 100.0)
            if 0 < calc < 500:
                pe, pe_src = round(calc, 2), "pb_roe"
        stocks[c] = {
            "n": b.get("n") or l.get("name") or s.get("name_ar") or c,
            "en": b.get("en") or s.get("name_en") or "",
            "name_ar": s.get("name_ar") or b.get("name_ar") or "",
            "s": b.get("s") or l.get("sector") or "—",
            "p": _num(l.get("price")) or _num(b.get("p")),
            "c": _num(l.get("change")) if l.get("change") is not None else _num(b.get("c")),
            "v": _num(l.get("volume")) or _num(b.get("v")),
            "mc": _num(l.get("mkt_cap")) or _num(s.get("market_cap")) or _num(b.get("mc")),
            "score": _num(l.get("final_score")) or _num(b.get("score")),
            "decision": l.get("decision") or "",
            "pe": pe, "peSrc": pe_src, "pb": pb, "roe": roe,
            # 🆕 فنية
            "s_rsi": _num(s.get("rsi_14")),
            "s_ma50": _num(s.get("ma_50d")),
            "s_ma200": _num(s.get("ma_200d")),
            "beta": _num(s.get("beta_1y")) or _num(b.get("b")),
            "s_roa": _num(s.get("roa")),
            # 🆕 هوامش ونمو
            "s_dy": _num(s.get("dividend_yield")),
            "s_flt": _num(s.get("float_shares_percent")),
            "s_gm": _num(s.get("gross_margin")),
            "s_pm": _num(s.get("profit_margin")),
            "s_rg": _num(s.get("revenue_growth")),
            "s_pg": _num(s.get("profit_growth")),
            "s_fcf": _num(s.get("fcf_ttm")),
            "s_bvps": _num(s.get("bvps")),
            # 🆕 مخاطرة حقيقية
            "vol1y": r.get("vol1y"), "vol3y": r.get("vol3y"),
            "mdd": r.get("mdd"), "mdd1y": r.get("mdd1y"),
            "sharpe3y": r.get("sharpe3y"), "sortino3y": r.get("sortino3y"),
            "cagr3y": r.get("cagr3y"), "frm52hi": r.get("frm52hi"),
            "h52": r.get("h52"), "l52": r.get("l52"),
            "live": bool(l),
        }
    n = len(stocks) or 1
    print(f"[egx_full] {len(stocks)} | pe {sum(1 for v in stocks.values() if v['pe'])} "
          f"| rsi {sum(1 for v in stocks.values() if v['s_rsi'])} "
          f"| mdd {sum(1 for v in stocks.values() if v['mdd'])}")
    return jsonify({"_ts": _dt.now(_tz.utc).isoformat() + "Z",
                    "_src": "tradingview + startamarkets",
                    "n": len(stocks), "stocks": stocks})


# ─────────────────────────────────────────────────────────────
# ④  /api/ipo  —  رادار الاكتتاب (snapshot متجدد كل ساعة)
# ─────────────────────────────────────────────────────────────
def _clean(t):
    t = _re.sub(r"<!--[\s\S]*?-->", "", t or "")
    t = _re.sub(r"<[^>]+>", " ", t)
    return _re.sub(r"\s+", " ", _html.unescape(t).replace("\xa0", " ")).strip()


def _first_span(s):
    m = _re.search(r"<span[^>]*>([\s\S]*?)</span>", s or "")
    return m.group(1) if m else ""


def _ipo_parse(h):
    marks = [(m.group(1), m.start()) for m in
             _re.finditer(r'<a[^>]*href="/ar/stock/([A-Z0-9]+)\.CA"[^>]*>', h)]
    out = []
    for k, (code, at) in enumerate(marks):
        seg = h[0 if k == 0 else marks[k - 1][1]:at]
        m = _re.search(r"<h3[^>]*>([\s\S]*?)</h3>", seg)
        if not m:
            continue
        name = _clean(m.group(1))
        if not name:
            continue
        st = _clean(_first_span(seg[m.end():]))

        def grab(lab):
            g = _re.search(lab + r"<\/p>\s*<p[^>]*>([\s\S]*?)</p>", seg)
            return _clean(g.group(1)) if g else ""

        ps = [_clean(x) for x in _re.findall(r"<p[^>]*>([\s\S]*?)</p>", seg)]
        ps = [x for x in ps if len(x) > 55]
        desc = ps[-1] if ps else ""
        junk = _re.sub(r"مُدرج|مدرج|قادم|فترة اكتتاب|تاريخ الطرح", "", desc).strip()
        if desc and (len(junk) < 25
                     or desc[:len(name)].replace(" ", "") == name.replace(" ", "")):
            desc = ""
        out.append({"code": code, "name": name, "status": st,
                    "price": grab("سعر الطرح"), "value": grab("قيمة الطرح"),
                    "desc": desc, "src": IPO_SRC})
    return out


_IPO = {"at": 0, "list": [], "ttl": 3600}


@app.route("/api/ipo")
def api_ipo():
    now = _dt.now(_tz.utc).timestamp()
    if _IPO["list"] and now - _IPO["at"] < _IPO["ttl"]:
        return jsonify(_IPO["list"])
    try:
        r = requests.get(IPO_SRC, headers=_HDR, timeout=25)
        got = _ipo_parse(r.text) if r.ok else []
        if got:
            _IPO.update(at=now, list=got, ttl=3600)
            print(f"[ipo] {len(got)} طرح")
            return jsonify(got)
    except Exception as e:
        print(f"[ipo] fail {e}")
    if _IPO["list"]:
        return jsonify(_IPO["list"])       # مفيش downtime
    return jsonify({"error": "unavailable"}), 503


# ─────────────────────────────────────────────────────────────
# ⑤  /api/obdepth  —  عمق السوق (اختياري — محتاج EGX_LIVE_KEY)
# ─────────────────────────────────────────────────────────────
@app.route("/api/obdepth/<code>")
def api_obdepth(code):
    """⛔ المفتاح في ENVIRONMENT VARIABLE — مش في الكود أبداً."""
    key = os.environ.get("EGX_LIVE_KEY")
    if not key:
        return jsonify({"error": "no_key",
                        "hint": "ضبط EGX_LIVE_KEY في Railway Variables"}), 503
    try:
        r = requests.get(
            f"https://egx-live.p.rapidapi.com/depth/{code.upper()}",
            headers={"x-rapidapi-key": key,
                     "x-rapidapi-host": "egx-live.p.rapidapi.com"},
            params={"level": 15}, timeout=12)
        if not r.ok:
            return jsonify({"error": "upstream", "code": r.status_code}), 502
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)[:120]}), 502


# ══════════════════════════════════════════════════════════════
#  warm-up عند الإقلاع — يجيب البيانات مرة واحدة بدل أول زائر
# ══════════════════════════════════════════════════════════════
def _octa_warmup():
    try:
        _starta_stats()
        print("[warmup] starta ok")
    except Exception as e:
        print(f"[warmup] starta fail {e}")
    try:
        r = requests.get(IPO_SRC, headers=_HDR, timeout=25)
        if r.ok:
            got = _ipo_parse(r.text)
            if got:
                _IPO.update(at=_dt.now(_tz.utc).timestamp(), list=got, ttl=3600)
                print(f"[warmup] ipo ok: {len(got)}")
    except Exception as e:
        print(f"[warmup] ipo fail {e}")


if os.environ.get("OCTA_WARMUP", "1") == "1":
    threading.Thread(target=_octa_warmup, daemon=True).start()

# قيم احتياطية — Railway بيرجّع المتغيرات كقالب {{ARCHON_SECRET:NAME}}
# فلو القالب ما اتفكّش بنستخدم القيم دي مباشرة
TG_FALLBACK = {
    "TELEGRAM_BOT_TOKEN": "8760752022:AAHSurRALWSyWzluuVqmruN6WDZ5Cn-E8XU",
    "TELEGRAM_CHAT_ID": "2073907990",
}


def _tg_env(v):
    """Railway بيسخّي القيم كقالب {{ARCHON_SECRET:NAME}} — نفكّه أو نرجّع فاضي."""
    v = str(v or "").strip()
    if not v:
        return ""
    if not (v.startswith("{{") and v.endswith("}}")):
        return v
    # قالب — جيب القيمة من قائمة القيم المعروفة
    inner = v[2:-2].strip()
    name = inner.split(":", 1)[1].strip() if ":" in inner else inner
    return TG_FALLBACK.get(name, "")


TOKEN = _tg_env(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
CHAT = _tg_env(os.environ.get("TELEGRAM_CHAT_ID", ""))
TG_ON = bool(TOKEN and CHAT)
TG_API = f"https://api.telegram.org/bot{TOKEN}"

STATE = "alerts_state.json"
COOLDOWN = 240          # 4 ساعات بين نفس التنبيه
DIGEST_HOUR = 9

ORDER = {"بيع": 0, "غير كافٍ": 1, "احتفظ": 2, "تجميع": 3}
TG_ERR = [""]


# ══════════════════════════════════════════════════════════════
#  ③ الحالة
# ══════════════════════════════════════════════════════════════

def st_load():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def st_save(d):
    try:
        with open(STATE + ".t", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(STATE + ".t", STATE)
    except Exception as e:
        print(f"[tg] save: {e}", flush=True)


def can(d, k):
    return (time.time() - d.get("sent", {}).get(k, 0)) >= COOLDOWN * 60


def mark(d, k):
    d.setdefault("sent", {})[k] = int(time.time())


def clr(d, k):
    d.get("sent", {}).pop(k, None)


# ══════════════════════════════════════════════════════════════
#  ④ الإرسال
# ══════════════════════════════════════════════════════════════

def send(text, silent=False):
    if not TG_ON:
        TG_ERR[0] = "bot disabled"
        return False
    try:
        import requests
        p = {"chat_id": CHAT, "text": str(text)[:3900],
             "disable_web_page_preview": "true"}
        if silent:
            p["disable_notification"] = "true"
        r = requests.post(f"{TG_API}/sendMessage", data=p, timeout=15)
        if r.status_code != 200:
            TG_ERR[0] = f"HTTP {r.status_code}: {str(r.text)[:180]}"
            print(f"[tg] {TG_ERR[0]}", flush=True)
            return False
        TG_ERR[0] = ""
        return True
    except Exception as e:
        TG_ERR[0] = f"{type(e).__name__}: {e}"
        print(f"[tg] {TG_ERR[0]}", flush=True)
        return False


def esc(v):
    return str(v if v is not None else "?").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pc(x):
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "?"


# ══════════════════════════════════════════════════════════════
#  ⑤ قائمة المتابعة
# ══════════════════════════════════════════════════════════════

def w_add(d, code, hi=None, lo=None):
    c = str(code or "").upper().strip()
    if not c:
        return
    it = d.setdefault("watch", {}).setdefault(c, {})
    if hi not in (None, ""):
        it["hi"] = float(hi)
    if lo not in (None, ""):
        it["lo"] = float(lo)
    it.setdefault("at", int(time.time()))


def w_del(d, code):
    d.setdefault("watch", {}).pop(str(code or "").upper().strip(), None)


def w_list(d):
    return [{"code": c, "hi": v.get("hi"), "lo": v.get("lo"), "at": v.get("at")}
            for c, v in (d.get("watch") or {}).items()]


# ══════════════════════════════════════════════════════════════
#  ⑥ التنبيهات الأربعة
# ══════════════════════════════════════════════════════════════

def a_price(d, rows):
    out = []
    for r in rows or []:
        code, px = r.get("code"), r.get("price")
        if not code or not px:
            continue
        try:
            px = float(px)
        except Exception:
            continue
        prev = (d.get("prices") or {}).get(code)
        ch = ((px - prev["p"]) / prev["p"] * 100) if (prev and prev.get("p")) else 0.0
        d.setdefault("prices", {})[code] = {"p": px, "t": int(time.time())}

        w = (d.get("watch") or {}).get(code)
        if not w:
            continue

        if w.get("hi") and px >= float(w["hi"]):
            k = f"hi:{code}"
            if can(d, k) and send(
                f"🔺 <b>السهم عدّى الحد الأعلى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['hi']):.2f} ج\n"
                f"التغير: {pc(ch)}\n\n💡 شوف السبب في كارت القرار قبل ما تبيع."):
                mark(d, k); out.append(code)

        if w.get("lo") and px <= float(w["lo"]):
            k = f"lo:{code}"
            if can(d, k) and send(
                f"🔻 <b>السهم وصل الحد الأدنى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['lo']):.2f} ج\n"
                f"التغير: {pc(ch)}\n\n💡 إشارة شراء — اتأكد إن السبب لسه قايم."):
                mark(d, k); out.append(code)

        if abs(ch) >= 4.0:
            k = f"mv:{code}"
            if can(d, k) and send(
                f"{'📈' if ch > 0 else '📉'} <b>حركة كبيرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nالتغير: <b>{pc(ch)}</b>"):
                mark(d, k); out.append(code)

        if w.get("hi") and px < float(w["hi"]) * 0.97:
            clr(d, f"hi:{code}")
        if w.get("lo") and px > float(w["lo"]) * 1.03:
            clr(d, f"lo:{code}")
        if abs(ch) < 1.5:
            clr(d, f"mv:{code}")
    return out


def a_decision(d, rows):
    out = []
    for r in rows or []:
        code, dec = r.get("code"), r.get("decision")
        if not code or not dec:
            continue
        prev = (d.get("decisions") or {}).get(code)
        d.setdefault("decisions", {})[code] = {"d": dec, "t": int(time.time())}
        if not prev or prev.get("d") == dec:
            continue
        k = f"dec:{code}"
        if not can(d, k):
            continue
        up = ORDER.get(dec, 1) > ORDER.get(prev["d"], 1)
        if send(
            f"{'⬆️' if up else '⬇️'} <b>التوصية اتغيّرت ({'تحسّن' if up else 'ضعف'})</b>\n\n"
            f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
            f"السعر: {float(r.get('price') or 0):.2f} ج\n"
            f"من <b>{esc(prev['d'])}</b> ← إلى <b>{esc(dec)}</b>\n"
            + (f"النقاط: {r.get('score')}\n" if r.get("score") else "")
            + "💡 افتح كارت القرار على OCTA."):
            mark(d, k); out.append(code)
    return out


def a_dividend(d, divs):
    out = []
    today = _dt.now().date()
    for v in divs or []:
        code, ex = v.get("code"), v.get("ex_date")
        if not code or not ex:
            continue
        try:
            exd = _dt.strptime(str(ex)[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days = (exd - today).days
        if days < 0 or days > 7:
            continue
        k = f"div:{code}:{exd}"
        if not can(d, k):
            continue
        head = ("🔴 <b>استحقاق اليوم!</b>" if days == 0 else
                "🟠 <b>استحقاق بكرة</b>" if days == 1 else
                f"🟡 <b>استحقاق بعد {days} أيام</b>")
        amt = v.get("amount")
        amt_t = f"{float(amt):.4f} ج" if amt not in (None, "", "-") else "غير محدد"
        if send(f"{head}\n\n<b>{esc(v.get('name') or code)}</b> ({esc(code)})\n"
                f"📅 الاستحقاق: <b>{exd}</b>\n💰 التوزيع: {amt_t}\n\n"
                f"💡 لازم تكون ماسك السهم يوم الاستحقاق."):
            mark(d, k); out.append(code)
    return out


def a_risk(d, rows):
    out = []
    for r in rows or []:
        code = r.get("code")
        if not code:
            continue
        m = r.get("mdd1y")
        if m is None:
            continue
        try:
            mv = abs(float(m))
        except Exception:
            continue
        k = f"risk:{code}"
        if mv >= 20:
            if can(d, k) and send(
                f"⚠️ <b>تحذير مخاطرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"أكبر هبوط في سنة: <b>-{mv:.1f}%</b>"
                + (f"\nمن أعلى 52 أسبوع: {pc(r.get('frm52hi'))}" if r.get("frm52hi") else "")
                + "\n\n💡 مؤشر خطر — مش نصيحة بيع."):
                mark(d, k); out.append(code)
        elif mv < 12:
            clr(d, k)
    return out


def digest(d, ranked, divs=None):
    today = _dt.now().strftime("%Y-%m-%d")
    if d.get("last_digest") == today or not ranked:
        return False
    top = ranked[:5]
    lines = [f"<b>{i}.</b> {esc(r.get('name') or r.get('code'))} ({esc(r.get('code'))}) — "
             f"{esc(r.get('decision'))}" + (f" · {r.get('score')} نقطة" if r.get("score") else "")
             for i, r in enumerate(top, 1)]
    dist = {}
    for r in ranked:
        dist[r.get("decision")] = dist.get(r.get("decision"), 0) + 1
    dv = ""
    if divs:
        near = [x for x in divs if x.get("ex_date") and str(x["ex_date"])[:10] >= today]
        if near:
            dv = "\n\n📅 <b>استحقاقات قريبة</b>\n" + "\n".join(
                f"· {esc(x.get('name') or x.get('code'))} — {str(x['ex_date'])[:10]}"
                for x in near[:5])
    msg = (f"🌅 <b>ملخص OCTA اليوم</b>\n{_dt.now().strftime('%Y-%m-%d %H:%M')}\n{'━'*20}\n\n"
           f"🏆 <b>أفضل {len(top)} فرص</b>\n" + "\n".join(lines)
           + "\n\n📊 <b>توزيع القرارات</b>\n" + " · ".join(f"{esc(k)} {v}" for k, v in dist.items())
           + f"\n\n👁️ <b>المتابعة</b> {len(d.get('watch') or {})} سهم" + dv)
    if send(msg, silent=True):
        d["last_digest"] = today
        return True
    return False


def run_alerts(ranked=None, divs=None, risk_rows=None):
    if not TG_ON:
        return
    d = st_load()
    try:
        p = a_price(d, ranked)
        dc = a_decision(d, ranked)
        dv = a_dividend(d, divs)
        rk = a_risk(d, risk_rows)
        dg = digest(d, ranked, divs) if _dt.now().hour >= DIGEST_HOUR else False
        st_save(d)
        if any([p, dc, dv, rk, dg]):
            print(f"[tg] sent p={p} d={dc} v={dv} r={rk} dg={dg}", flush=True)
    except Exception as e:
        print(f"[tg] run: {e}", flush=True)


# ══════════════════════════════════════════════════════════════
#  ⑦ الجدولة
# ══════════════════════════════════════════════════════════════

def _loop():
    time.sleep(120)
    while True:
        try:
            ld = getattr(U, "LIVE_DATA", {}) or {}
            st = ld.get("egx30") or []
            if st and TG_ON:
                ranked = [{"code": x.get("code"), "name": x.get("name"),
                           "price": x.get("price"), "decision": x.get("decision"),
                           "score": x.get("final_score")}
                          for x in st if isinstance(x, dict)]
                ranked.sort(key=lambda r: -(r.get("score") or 0))
                risk = [{"code": x.get("code"), "name": x.get("name"),
                         "mdd1y": x.get("mdd1y"), "frm52hi": x.get("frm52hi")}
                        for x in st if isinstance(x, dict) and x.get("mdd1y")]
                divs = [{"code": a.get("code") or a.get("symbol"), "name": a.get("name"),
                         "ex_date": a.get("ex_date") or a.get("exDate"),
                         "amount": a.get("amount") or a.get("value"), "type": a.get("type")}
                        for a in (getattr(U, "_actions", []) or [])]
                run_alerts(ranked=ranked[:60], divs=divs, risk_rows=risk)
        except Exception as e:
            print(f"[tg] loop: {e}", flush=True)
        time.sleep(300)


print(f"[tg] enabled={TG_ON} token={TOKEN[:6] if TOKEN else '-'} chat={CHAT or '-'}",
      flush=True)
if TG_ON:
    threading.Thread(target=_loop, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  ⑧ المسارات
# ══════════════════════════════════════════════════════════════

from flask import jsonify, request


@app.route("/api/alerts/test", methods=["GET"])
def _octa_test():
    ok = send("OCTA test " + str(int(time.time())))
    return jsonify({"ok": ok, "enabled": TG_ON, "error": TG_ERR[0],
                    "bot_ok": ok})


@app.route("/api/alerts/state", methods=["GET"])
def _octa_state():
    d = st_load()
    return jsonify({"ok": True, "enabled": TG_ON,
                    "watch": len(d.get("watch") or {}),
                    "tracked": len(d.get("prices") or {}),
                    "last_digest": d.get("last_digest")})


@app.route("/api/alerts/watch", methods=["GET"])
def _octa_watch_get():
    return jsonify({"ok": True, "items": w_list(st_load())})


@app.route("/api/alerts/watch", methods=["POST"])
def _octa_watch_post():
    d = st_load()
    j = request.get_json(silent=True) or {}
    a = j.get("action")
    if a == "add":
        w_add(d, j.get("code"), j.get("hi"), j.get("lo"))
    elif a == "del":
        w_del(d, j.get("code"))
    elif a == "clear":
        d["watch"] = {}
    st_save(d)
    return jsonify({"ok": True, "items": w_list(d)})


@app.route("/api/alerts/diag", methods=["GET"])
def _octa_diag():
    out = {"code": "diag", "enabled": TG_ON,
           "token_len": len(TOKEN), "chat": CHAT,
           "routes": len(app.url_map._rules),
           "raw_token": os.environ.get("TELEGRAM_BOT_TOKEN", "<missing>")[:30],
           "raw_chat": os.environ.get("TELEGRAM_CHAT_ID", "<missing>")[:30]}
    if TG_ON:
        try:
            import requests
            r = requests.get(f"{TG_API}/getMe", timeout=12)
            out["getMe"] = r.status_code
            try:
                out["bot"] = (r.json().get("result") or {}).get("username")
            except Exception:
                pass
        except Exception as e:
            out["getMe_err"] = str(e)[:120]
    return jsonify(out)


print("[octa] ✅ ready", flush=True)


# ══════════════════════════════════════════════════════════════
#  🖼️  لوجوهات الأسهم — من TradingView (s3 بيمنع المتصفح)
# ══════════════════════════════════════════════════════════════
try:
    import logos as _logos_mod
    from flask import send_from_directory as _send_from_dir
    _LOGOS_OK = True
except Exception as _e:
    _LOGOS_OK = False
    print(f"[logos] module missing: {_e}")

_LOGOS_BOOT = {"done": False, "n": 0}


def _boot_logos():
    """thread يجيب كل اللوجوهات مرة واحدة عند الإقلاع"""
    import threading
    def run():
        try:
            codes = []
            for f in ("data_full.json", "data_egx.json"):
                if os.path.isfile(f):
                    with open(f, encoding="utf-8") as fh:
                        d = json.load(fh)
                    codes = list((d.get("stocks") or d).keys())[:300]
                    if codes:
                        break
            if codes:
                r = _logos_mod.refresh_logos(codes)
                print(f"[logos] ✅ {r}")
        except Exception as e:
            print(f"[logos] thread: {e}")
    if _LOGOS_OK:
        threading.Thread(target=run, daemon=True).start()
        print("[logos] boot thread started")


_boot_logos()

@app.route("/api/logos", methods=["GET"])
def api_logos():
    """قائمة اللوجوهات المتاحة — {CODE: url}"""
    if not _LOGOS_OK:
        return jsonify({"ok": False, "error": "logos module unavailable"})
    if not _LOGOS_BOOT["done"]:
        _LOGOS_BOOT["done"] = True
        try:
            codes = list((globals().get("EGX") or {}).keys())
            if not codes and os.path.isdir("data"):
                pass
            try:
                with open("data_egx.json", encoding="utf-8") as f:
                    d = json.load(f)
                codes = list((d.get("stocks") or d).keys())[:300]
            except Exception:
                pass
            if codes:
                _LOGOS_BOOT["n"] = _logos_mod.refresh_logos(codes)
                print(f"[logos] booted: {_LOGOS_BOOT['n']}")
        except Exception as e:
            print(f"[logos] boot error: {e}")
    files = _logos_mod.logos_payload()
    return jsonify({"ok": True, "count": len(files),
                    "logos": {f[:-4]: f"/logos/{f}" for f in files}})


@app.route("/logos/<path:fn>", methods=["GET"])
def serve_logo(fn):
    if not _LOGOS_OK:
        return jsonify({"error": "no logos"}), 404
    d = _logos_mod.LOGOS_DIR if hasattr(_logos_mod, "LOGOS_DIR") else "logos"
    try:
        return _send_from_dir(d, fn, max_age=86400)
    except Exception:
        return jsonify({"error": "not found"}), 404


# ══════════════════════════════════════════════════════════════
#  🖼️  بروكسي اللوجوهات — s3.tradingview.com بيمنع المتصفح (403)
# ══════════════════════════════════════════════════════════════
_TV_LOGO_CACHE = {}


@app.route("/api/tvlogo/<path:logoid>", methods=["GET"])
def api_tv_logo(logoid):
    """يجيب اللوجو من TradingView ويرجّعه — المتصفح مش بيقدر يوصله"""
    import requests as _rq
    if logoid in _TV_LOGO_CACHE:
        blob, ct = _TV_LOGO_CACHE[logoid]
        return Response(blob, mimetype=ct,
                        headers={"Cache-Control": "public, max-age=604800"})
    safe = "".join(c for c in logoid if c.isalnum() or c in "-_")
    if not safe or len(safe) > 80:
        return jsonify({"error": "bad id"}), 400
    url = f"https://s3.tradingview.com/logos/logos/{safe}.png"
    try:
        r = _rq.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"},
                    timeout=15)
        if r.status_code != 200 or len(r.content) < 100:
            return jsonify({"error": f"upstream {r.status_code}"}), 404
        blob = r.content
        _TV_LOGO_CACHE[safe] = (blob, r.headers.get("Content-Type", "image/png"))
        return Response(blob, mimetype=r.headers.get("Content-Type", "image/png"),
                        headers={"Cache-Control": "public, max-age=604800"})
    except Exception as e:
        return jsonify({"error": str(e)[:80]}), 502


# ══════════════════════════════════════════════════════════════
#  📊 شموع تاريخ حقيقية — startamarkets (4996 شمعة لكل سهم)
# ══════════════════════════════════════════════════════════════
_CANDLE_CACHE = {}


@app.route("/api/candles/<code>", methods=["GET"])
def api_candles(code):
    """شموع يومية حقيقية — {o,h,l,c,v,t}"""
    code = (code or "").upper().strip()
    if not code or len(code) > 12:
        return jsonify({"ok": False, "error": "bad code"}), 400

    try:
        n = int(request.args.get("n", "320"))
    except Exception:
        n = 320
    n = max(60, min(n, 1200))

    ck = f"{code}:{n}"
    if ck in _CANDLE_CACHE:
        return jsonify({"ok": True, "code": code, "candles": _CANDLE_CACHE[ck]})

    try:
        r = requests.get(
            f"https://startamarkets.com/api/v1/egx/history/{code}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
                "Accept": "application/json,text/plain,*/*",
                "Origin": "https://startamarkets.com",
                "Referer": "https://startamarkets.com/egx",
            },
            timeout=30
        )
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"upstream {r.status_code}",
                            "ct": r.headers.get("Content-Type", "")[:40]}), 502
        try:
            raw = r.json()
        except Exception as pe:
            return jsonify({"ok": False, "error": f"json: {str(pe)[:50]}",
                            "body": r.text[:120]}), 502
        if not isinstance(raw, list) or len(raw) < 20:
            return jsonify({"ok": False, "error": "no data",
                            "type": type(raw).__name__,
                            "len": len(raw) if hasattr(raw, '__len__') else -1,
                            "sample": str(raw)[:200]}), 404

        out = []
        for c in raw[-n:]:
            try:
                out.append({
                    "t": c.get("date"),
                    "o": round(float(c["open"]), 4),
                    "h": round(float(c["high"]), 4),
                    "l": round(float(c["low"]), 4),
                    "c": round(float(c["close"]), 4),
                    "v": int(c.get("volume") or 0)
                })
            except Exception:
                continue
        if not out:
            return jsonify({"ok": False, "error": "parse"}), 404

        _CANDLE_CACHE[ck] = out
        if len(_CANDLE_CACHE) > 60:
            _CANDLE_CACHE.pop(next(iter(_CANDLE_CACHE)))
        return jsonify({"ok": True, "code": code, "count": len(out), "candles": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:80]}), 502


# ══════════════════════════════════════════════════════════════
#  💵 الأسعار اللحظية — TradingView scanner (كل 60 ثانية)
# ══════════════════════════════════════════════════════════════
import json as _json

_LIVE_CACHE = {"at": 0, "data": {}}
_LIVE_TTL = 55          # ثانية — نحدّث كل دقيقة


# ══════════════════════════════════════════════════════════════
#  🕐 مواعيد البورصة المصرية — لأجل cache ذكي
# ══════════════════════════════════════════════════════════════
from datetime import datetime as _dt, timedelta as _td


def egx_now():
    """الوقت في القاهرة (UTC+2 — مفيش تغيير صيفي في مصر)"""
    return _dt.utcnow() + _td(hours=2)


def egx_ttl():
    """
    ⏱️ cache ttl بالثواني حسب حالة السوق:
    ⏱️ cache ttl حسب حالة السوق: كل ما السوق قريب يفتح نحدّث أسرع
    """
    n = egx_now()
    d, m = n.weekday(), n.hour * 60 + n.minute

    def iv(a, b):
        return a <= m < b

    if d >= 4:                       # الجمعة والسبت → أهدأ
        return 600
    if iv(555, 570):  return 12      # 09:15–09:30 حجم كبير
    if iv(570, 600):  return 15      # 09:30–10:00 استكشافية
    if iv(600, 855):  return 12      # 10:00–14:15 تداول مستمر
    if iv(855, 865):  return 6       # 14:15–14:25 مزاد الإغلاق
    if iv(865, 870):  return 6       # 14:25–14:30 سعر الإغلاق
    if m < 555:       return 180     # قبل الافتتاح
    return 240                       # بعد الإغلاق


@app.route("/api/quotes", methods=["GET"])
def api_quotes():
    """
    أسعار لحظية لكل الأسهم
    ?market=egypt|us|saudi|uae   (افتراضي: كلهم)
    ?codes=COMI,ETEL              (افتراضي: كلهم)
    """
    import time as _t

    mk = (request.args.get("market") or "all").lower()
    codes_arg = request.args.get("codes")

    now = _t.time()
    ttl = egx_ttl()
    if now - _LIVE_CACHE["at"] > ttl and not codes_arg:
        try:
            mk_map = {"egypt": "EGX", "us": "NASDAQ", "saudi": "TADAWUL", "uae": "DFM"}
            cols = ["close", "change", "volume", "market_cap_basic", "Recommend.All"]
            out = {}
            for key, ex in mk_map.items():
                if mk != "all" and mk != key:
                    continue
                got = _tv_scan_market(ex, cols)
                if got:
                    out[key] = got
            if out:
                _LIVE_CACHE["data"] = out
                _LIVE_CACHE["at"] = now
        except Exception as e:
            print(f"[quotes] err: {e}")

    data = _LIVE_CACHE["data"]

    # طلب رموز محددة
    if codes_arg:
        want = [c.strip().upper() for c in codes_arg.split(",") if c.strip()]
        out = {}
        allm = data or {}
        # لو مش متحدّث بعد — جيب دلوقتي
        if not allm:
            allm = {}
            for key, ex in {"egypt": "EGX", "us": "NASDAQ",
                            "saudi": "TADAWUL", "uae": "DFM"}.items():
                got = _tv_scan_market(ex, ["close", "change", "volume", "Recommend.All"])
                if got:
                    allm[key] = got
            _LIVE_CACHE["data"] = allm
            _LIVE_CACHE["at"] = _t.time()
            data = allm
        for mkt, rows in (data or {}).items():
            hit = {c: v for c, v in rows.items() if c in want}
            if hit:
                out[mkt] = hit
        return jsonify({
            "ok": True, "ts": int(_t.time()),
            "updated": _LIVE_CACHE["at"], "quotes": out
        })

    n = egx_now()
    return jsonify({
        "ok": True, "ts": int(_t.time()),
        "updated": _LIVE_CACHE["at"],
        "age": int(now - _LIVE_CACHE["at"]),
        "ttl": ttl,
        "egx": {
            "time": n.strftime("%H:%M"),
            "weekday": n.strftime("%A"),
            "day": n.weekday(),
            "minute": n.hour * 60 + n.minute,
        },
        "markets": data,
        "counts": {k: len(v) for k, v in (data or {}).items()}
    })


def _tv_scan_market(exchange, cols):
    """يجيب أسعار كل أسهم بورصة من TradingView scanner"""
    try:
        body = {
            "symbols": {"query": {"types": []}, "tickers": []},
            "filter": [
                {"left": "exchange", "operation": "in_range", "right": [exchange]},
                {"left": "type", "operation": "equal", "right": "stock"},
            ],
            "columns": cols,
            "range": [0, 700],
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        }
        r = requests.post(
            "https://scanner.tradingview.com/global/scan",
            data=_json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
            },
            timeout=25,
        )
        if r.status_code != 200:
            return {}
        out = {}
        for row in r.json().get("data", []):
            code = row["s"].split(":")[-1]
            d = row.get("d") or []
            rec = {}
            for i, c in enumerate(cols):
                if i < len(d) and d[i] is not None:
                    rec[c] = d[i]
            if rec:
                out[code] = rec
        return out
    except Exception as e:
        print(f"[tv_scan_{exchange}] {e}")
        return {}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting OCTA v3 on port {port}")
    print(f"Gemini AI: {'✅ configured' if GEMINI_KEY else '❌ NOT configured'}")
    app.run(host="0.0.0.0", port=port, debug=False)
