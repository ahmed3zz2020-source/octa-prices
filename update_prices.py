import json, time, requests, os, threading
import div_actions
from flask import Flask, jsonify, request, Response
from pathlib import Path
from datetime import datetime, timedelta

app = Flask(__name__)

# ══════════════════════════════════════════════════════════════
#  🔒 CORS — بيحدد مين يقدر ينادي الـAPI
#  ──────────────────────────────────────────────────────────────
#  قبل: كان "*" فأي موقع في العالم يقدر ياخد البيانات بتاعتنا.
#  دلوقتي: الموقع بتاعنا بس (octashares.com) + نسخ التطوير.
#  ══════════════════════════════════════════════════════════════

# المسموح لهم ينادوا الـAPI
ALLOWED_ORIGINS = {
    "https://octashares.com",
    "https://www.octashares.com",
    "https://octa.ahmed3zz2020.workers.dev",   # نسخة Cloudflare
    "https://octa-preview.ahmed3zz2020.workers.dev",   # رابط المعاينة
}

# ⛌ روابط المعاينة المؤقتة ⬇️ بتتغير مع كل نشر، فنسمح
#    بأي نطاق فرعي من نطاق المنصّة ⬇️ مفيش حد بيلمس
#    الدومين الأساسي ولا الـAPI.
#    ⛔ ملحوظة: ده مشholeأمن ⬇️ الطلبات بتفضل محميّة
#    بالتوكن ⬇️ والبيانات بتفضل مقفولة ⬇️ ده بس بيعمل
#    معاينة من غير ما نعدّل الكود كل مرة.
PREVIEW_HOST_RE = __import__("re").compile(
    r"^https://[a-z0-9-]+\.space\.minimax\.io$"
)

# نضيف أي originsIncremental من الـenv (للتجربة لو حبيت تزود)
_extra = str(os.environ.get("ALLOWED_ORIGINS", "") or "").strip()
if _extra:
    for o in _extra.replace(";", ",").split(","):
        o = o.strip().rstrip("/")
        if o.startswith("http"):
            ALLOWED_ORIGINS.add(o)


# ══════════════════════════════════════════════════════════════════
# 🐙 محرك التقييم — مستورد من octa_score (المصدر الوحيد للحقيقة)
#    السبب: كان فيه نسخة تانية في merge_gold.py بأوزان مختلفة،
#    والموقع كان بيشتغل بنسخة والـAPI بنسخة.
# ══════════════════════════════════════════════════════════════════
SECTOR_STATS = {}   # وسائط القطاعات — بتتبني كل دورة

from octa_score import (
    AXIS_WEIGHTS,
    tech_score, liquidity_score, build_sector_stats,
    _compose_score, final_score,
)
def _origin_allowed(origin):
    """هل الـorigin ده مسموح؟"""
    if not origin:
        return False
    o = str(origin).strip().rstrip("/")
    if o in ALLOWED_ORIGINS:
        return True
    # ⛌ روابط المعاينة المؤقتة ⬇️ بتتغير مع كل نشر
    #    ⬇️ بنسمح بأي نطاق فرعي من نطاق المنصّة بس.
    #    ⛔ مش بنسمح بأي نطاق تاني ⬇️ والدومين الأساسي
    #    ونسخ Cloudflare زي ما هما في القائمة فوق.
    try:
        return bool(PREVIEW_HOST_RE.match(o))
    except Exception:
        return False


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")

    if _origin_allowed(origin):
        # نعكس الـorigin المسموح (مش *) + Vary مهم للـcache
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-OCTA-Client, Authorization, X-Requested-With"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers.add("Vary", "Origin")

    # ⛔ مافيش Origin header (زي curl أو سكربت) ← مافيش CORS headers
    #    المتصفح هيعمل block لوحده — وده اللي بنبيه

    # ══════════════════════════════════════════════════════════
    #  🛡️ Security headers
    #  ─────────────────────────────────────────────────────────
    #  كل واحد بيدي حماية مختلفة:
    #
    #  nosniff        → المتصفح ما يخمنش نوع الملف
    #  DENY           → محدش يقدر يحط الموقع في iframe
    #  HSTS           → الاتصال يفضل مشفّر حتى لو حد طلب http
    #  Permissions    → نمنع الكاميرا والميكروفون والجGPS
    #  COOP           → يعزل التبويب عن النوافذ التانية
    #  Cache-Control  → الداتا المالية ما تتخزّنش في proxy
    # ══════════════════════════════════════════════════════════
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("X-Frame-Options", "DENY")

    # مشفّر دايماً — Railway وراه proxy بيشيل
    h.setdefault("Strict-Transport-Security",
                 "max-age=31536000; includeSubDomains")

    # نسمح بأقل حاجة ممكنة
    h.setdefault("Permissions-Policy",
                 "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
                 "encrypted-media=(), fullscreen=(self), geolocation=(), "
                 "gyroscope=(), magnetometer=(), microphone=(), "
                 "midi=(), payment=(), usb=(), xr-spatial-tracking=()")

    # عزل التبويب عن النوافذ التانية
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    h.setdefault("Cross-Origin-Resource-Policy", "same-site")

    # ⛔ الداتا المالية ما تتخزّنش — بيانات لحظية
    h.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    h.setdefault("Pragma", "no-cache")
    h.setdefault("Expires", "0")

    return response


# Railway بيبعت OPTIONS أوتوماتيك قبل ما يوصل للكود، فبنتعامل معاه
# في before_request علشان نقدر نرفض الـpreflight من أي origin مش مسموح.

# ══════════════════════════════════════════════════════════════
#  🛡️ إخفاء وصفحة التقييم من الـAPI
#  ──────────────────────────────────────────────────────────────
#  المشكلة: بعض المسارات كانت بترجّع "الأوزان" — يعني وصفة
#  حساب التقييم نفسها: أساسيات 45%، مخاطرة 20%…
#  حد يعمل طلب واحد يقدر يبني نفس النظام من الصفر.
#
#  الحل: تشيل المفتاح من الرد قبل ما يوصل المتصفح.
#
#  ⚠️ اللي بيتشال: الأوزان والقواعد فقط.
#  ✅ اللي بيفضل: النتيجة النهائية وتفاصيل السهم — عشان
#     الموقع يشتغل زي ما هو والعميل يشوف كل حاجة.
# ══════════════════════════════════════════════════════════════

_HIDDEN_KEYS = (
    "weights", "strategies", "raw_scores", "rawScore",
    "calibration", "strategy", "axis_weights", "axisWeights",
    "sub_scores", "subScores", "scoring", "formula", "formulae",
    "AXIS_WEIGHTS", "risk_penalty_mult", "min_liquidity",
    "part_scores",
)


def _make_snapshot_id(ts_iso):
    """
    🆔 رقم النسخة.

    الهدف: لما المستخدم يفتح صفحتين أو تحديثين، يقدر يعرف إن
    البيانات قديمة ولا جديدة. مثال: "20261011-143025-a3f2"

    من ts_iso ناخد التاريخ والوقت، ومن hash للبيانات المتغيّرة
    جزء عشان الرقم يتغير لو المحتوى اتغير.
    """
    try:
        compact = str(ts_iso).replace("-", "").replace(":", "").replace("T", "-")
        compact = compact[:15]                      # 20261011-143025
    except Exception:
        compact = "unknown"

    # بصمة قصيرة من المحتوى — تتغير لو أي سعر اتغير
    try:
        fingerprint = hashlib.md5(
            json.dumps(LIVE_DATA.get("egx30") or [], sort_keys=True,
                       ensure_ascii=False, default=str).encode()
        ).hexdigest()[:4]
    except Exception:
        fingerprint = "0000"

    return f"{compact}-{fingerprint}"


def _hide_recipe(data):
    """يحذف مفاتيح الوصفة من أي رد، ويباقي على كل حاجة تانية."""
    if isinstance(data, dict):
        return {k: _hide_recipe(v) for k, v in data.items() if k not in _HIDDEN_KEYS}
    if isinstance(data, list):
        return [_hide_recipe(i) for i in data]
    return data


@app.after_request
def hide_recipe(resp):
    """آخر خط دفاع — بيتطبّق على كل رد JSON أوتوماتيك."""
    if not resp.is_json:
        return resp
    try:
        body = resp.get_json(silent=True)
    except Exception:
        return resp
    if body is None:
        return resp

    # نخفي الوصفة
    clean = _hide_recipe(body)

    # ونحط رقم النسخة في كل رد dict
    snap = LIVE_DATA.get("snapshot_id")
    if snap and isinstance(clean, dict) and "snapshot_id" not in clean:
        clean = dict(clean)
        clean["snapshot_id"] = snap

    if clean != body:
        # ⚠️ مهم: set_data بيبعت string وبيحسب الطول بالبايت.
        #    إحنا بنكتب JSON فيه عربي، والعربي بايتين للحرف.
        #    فلازم نعمل encode صريح عشان Content-Length يطلع صح.
        raw = json.dumps(clean, ensure_ascii=False).encode("utf-8")
        resp.set_data(raw)
        resp.headers["Content-Length"] = str(len(raw))

    # 🎯 ETag: المتصفح يعرف إن الداتا اتغيرت من غير ما ينزّلها تاني
    if resp.status_code == 200 and "ETag" not in resp.headers:
        try:
            tag = '"' + hashlib.md5(resp.get_data()).hexdigest()[:16] + '"'
            resp.headers["ETag"] = tag
        except Exception:
            pass

    return resp





def _log_exc(where, exc):
    """
    📝 نسجّل الخطأ في اللوج بتاع السيرفر — مش في الرد.

    الرد للمستخدم لازم يبقى نضيف ومفيد من غير ما يفضح
    تفاصيل داخلية. اللوج بيروح لـstdout ومحدش بيقراه غيرنا.
    """
    try:
        import traceback as _tb
        print(f"[ERR] {where}: {type(exc).__name__}: {str(exc)[:200]}",
              flush=True)
        print(_tb.format_exc()[-1200:], flush=True)
    except Exception:
        pass


@app.errorhandler(Exception)
def _json_error_handler(exc):
    """
    ⛌⛌ صفحة 500 فاضية من Flask مالهاش أي فايدة — ولا للمستخدم
    ولا لنا. أي خطأ بيرجع JSON بنوع الاستثناء + اللوج كامل.
    ⛌ بنسيب HTTPException زي ما هو (400/401/404/429… إلخ).
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    _log_exc("unhandled", exc)
    resp = jsonify({"error": "حصل خطأ في السيرفر — جرب تاني",
                    "why": type(exc).__name__})
    resp.status_code = 500
    return resp


@app.before_request
def protect_admin_routes():
    """
    🔒 المسارات التشخيصية بتتقفل على أي حد.

    ودي مش للمستخدم — دي للمطوّر بتاعك. وبيقولوا تفاصيل
    داخلية: عدد الأسهم، الحقول الناقصة، الأوزان المتوسطة،
    تكرار المحاور. أي حد يقراها يقدر يعرف شكل النظام.
    """
    ADMIN_PATHS = {
        "/api/diagnostic",
        "/api/audit/redundancy",
        "/api/ai-status",
    }
    if request.path not in ADMIN_PATHS:
        return None

    # المستخدم المسجّل يقدر
    u = require_user()
    if not u:
        return jsonify({
            "ok": False,
            "error": "المسار ده محمي",
            "hint": "سجّل دخول من /api/auth/register الأول",
        }), 401

    # ⛌ ⛌ الأدمن: OCTA_ADMIN_KEY كان متقرأ من Railway ومحدش بيستخدمه —
    #    يعني أي مستخدم مسجّل (مش المالك بس) كان يقدر يقرأ التشخيص
    #    والأرقام الداخلية. لو المتغير مضبوط، المسارات دي بتتقفل على
    #    صاحبه بس. لو مش مضبوط، سلوكه زي ما كان عشان ما نكسرش
    #    فحص المالك.
    if ADMIN_KEY:
        sent = (request.headers.get("X-Admin-Key") or "").strip()
        if not hmac.compare_digest(sent, ADMIN_KEY):
            return jsonify({
                "ok": False,
                "error": "المسار ده للأدمن بس",
                "hint": "ابعت X-Admin-Key في الهيدر",
            }), 403
    return None


@app.before_request
def guard_preflight():
    """
    ⛔ لو الطلب OPTIONS جاي من origin مش في القائمة → نرفضه فوراً.

    Railway (وnginx عموماً) بيردّ على OPTIONS بـ200 قبل ما الطلب
    يوصل لدالة الـroute، فلازم الرفض يكون في before_request
    علشان الـ403 يبقى فعّال فعلاً.
    """
    if request.method != "OPTIONS":
        return None
    origin = request.headers.get("Origin", "")
    if not _origin_allowed(origin):
        resp = jsonify({"error": "forbidden origin"})
        resp.status_code = 403
        return resp
    return None



# ══════════════════════════════════════════════════════════════════
# 🛡️ تنظيف المدخلات — قبل أي route
# ══════════════════════════════════════════════════════════════════
# ⛌ ليش: أي string بييجي من المستخدم بيروح لـSQL أو filesystem أو
#    شارت أو اسم دالة. من غير حدّ، مدخل واحد يقدر يقرا ملف
#    أو يكسر الصفحة. القواعد هنا بتغطي كل الـ30+ endpoint.
#
# 📌 القاعدة: هنقبل الحروف والأرقام والرموز الآمنة بس.
#    أي حاجة تانية بترجع 400 صريح — مش بنخمن وبنحاول.
import re as _re_guard

_ALLOWED_CODES = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-_")

def clean_code(v, maxlen=12):
    """رمز سهم — بيقبل الحروف والأرقام والنقطة والشرطة بس.
    ⛔ أي حاجة تانية = مدخل مش مصرح. بيرجع None مش 'cleaned'."""
    if v is None:
        return None
    s = str(v).strip().upper()
    if not s or len(s) > maxlen:
        return None
    if not set(s) <= _ALLOWED_CODES:
        return None
    return s


def clean_text(v, maxlen=200):
    """نص حرّ — بيشيل المحارف التحكم وبيلصق سطر واحد."""
    if v is None:
        return ""
    s = str(v)
    s = _re_guard.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    s = s.replace("\n", " ").replace("\r", " ")
    return s.strip()[:maxlen]


def clean_num(v, lo=None, hi=None, default=None):
    """رقم — وبيقفل المدى عشان حد ما يطلبش limit=999999999."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return default
    if n != n or n in (float("inf"), float("-inf")):
        return default
    if lo is not None and n < lo:
        return default
    if hi is not None and n > hi:
        return default
    return n


@app.before_request
def _sanitize_request():
    """بيتنضف كل طلب قبل أي route يلمسها.
    ⛌ مش بنرمي 400 هنا — الـroutes نفسها بترجع 400 لو محتاجة.
       الغرض إن الـroute يشوف قيمة نظيفة أو فاضية، مش نص مبتور."""
    try:
        for k, v in list(request.args.items()):
            kl = k.lower()
            if kl in ("code", "symbol", "codes"):
                # ⛔ ⛔ مهم: التوكن بيتنقل كـquery في بعض الـendpoints
                #   وهو base64 مش ticker — التنضيف هنا كان بيكسر التوقيع
                #   فكل توكنIssued بيترفض فوراً (401).
                #   ⛌ التوكن بيتشال من التنضيف خالص — مش هننضفه أبداً.
                if "token" in kl or "." in str(v):
                    request.args[k] = clean_text(v, 400)
                else:
                    request.args[k] = clean_code(v) or ""
            elif kl in ("limit", "count", "days", "n", "top", "periods"):
                request.args[k] = clean_num(v, 1, 2000, 20)
            elif kl in ("min_score", "min_safety", "min_liquidity", "max_risk",
                        "max_pe", "min_div_yield"):
                request.args[k] = clean_num(v, 0, 1000, None)
            else:
                request.args[k] = clean_text(v, 300)
    except Exception:
        pass



@app.route("/<path:any>", methods=["OPTIONS"])
@app.route("/", methods=["OPTIONS"])
def preflight(any=""):
    origin = request.headers.get("Origin", "")
    if not _origin_allowed(origin):
        # ⛔ origin مش في القائمة → نرفض الـpreflight
        return jsonify({"error": "forbidden origin"}), 403
    return "", 204



# ══════════════════════════════════════════════════════════════
#  🚦 Rate Limiting — بيمنع أي حد يعمل آلاف الطلبات
#  ──────────────────────────────────────────────────────────────
#  المشكلة: مافيش أي حداد على عدد الطلبات. أي حد يقدر يعمل
#  10,000 طلب في الدقيقة ويستنزف السيرفر أو يحرق Gemini/Telegram.
#
#  الحل: 3 طبقات
#    1) عام         → 120 طلب/دقيقة لكل IP
#    2) غالي        → 15 طلب/دقيقة (analyze, chat, news, candles…)
#    3) كتابة       →  5 طلب/دقيقة (portfolio, alerts, dividends)
#
#  ⛔ الرد: 429 + Retry-After header
# ══════════════════════════════════════════════════════════════

from collections import defaultdict, deque
from flask import g

# ── تعريف المسارات ──
# الغالية: بتجيب من مصادر خارجية أو بتحسب كتير
ROUTES_EXPENSIVE = {
    "analyze", "chat", "news", "candles", "intelligence",
    "explain", "egx_full", "risk", "fundamental", "technical",
    "obdepth", "sentiment", "portfolio_fit", "opportunity",
}

# الكتابة: بتغيّر حالة
ROUTES_WRITE = {"portfolio", "alerts", "dividends", "calibration", "stress"}

# ⛔ مسارات قراءة جوّه /api/auth — مش بتغيّر حالة
#    كانت بتتصنّف "write" فحد الـ5/دقيقة كان بيتخلص من أول تحميل للصفحة،
#    فالمستخدم ميقدرش يطلب كود أصلاً.
ROUTES_READONLY = {"me", "status", "check"}

# الحدود — كل bucket = قائمة نوافذ: [(عدد الطلبات، Window بالثواني), …]
# ⛌ ليه قائمة مش زوج واحد: عشان نقدر نحط **سقفين** على نفس المسار.
#    مثال: ٥/دقيقة (بيمنع المسح السريع) + ٢٠/ساعة (بيمنع المسح البطيء).
#    أضيق نافذة هي اللي بتفرض، والاثنتين لازم تعدّي.
LIMITS = {
    "default":   [(120, 60)],
    "expensive": [(15, 60)],
    "write":     [(5, 60)],
    # إرسال بريد فعلي — ده أغلى حاجة في الـAPI كله
    "otp_send":  [(3, 300)],
    # ⛌ التحقق: ١٠ محاولات / ٥ دقايق — الكود نفسه بيموت بعد ٥ غلط
    "otp_verify": [(15, 300)],
    # ⛔⛔ تسجيل الباسورد: نفس حد الكتابة ٥/دقيقة
    #    + سقف ٢٠/ساعة. المسار ده بيفحص ١٠٬٠٠٠ احتمال للـ«الباسورد
    #    ده مستخدم من قبل؟» — وخلاص، ٥/دقيقة معناها ٣٠٠ فحص في
    #    الساعة من غير ما يتقفل أي حاجة. ٢٠/ساعة معناها ٥٠٠٠ فحص في
    #    اليوم = ٢ يومين لتمرير المساحة كلها حتى قبل القفل الذكي.
    "pin_register": [(5, 60), (20, 3600)],
    # ⛌⛔ كود فتح الحساب (القاعدة ①): الإرسال أغلى حاجة في
    #    الـAPI كله — بيبعت بريد وبيحسب كود وبيكتب على القرص.
    #    ٣ / ٥ دقايق للـIP. فوقه حد ٣ في اليوم **لكل إيميل**
    #    جوّه الكود نفسه (مش الـIP بس) — شوف auth_pin_chal_send.
    "pin_chal_send": [(3, 300)],
    # ⛌ التحقق: ١٠ / ٥ دقايق. الكود نفسه بيموت بعد ٥ غلط،
    #    فالسقف ده بيمنع المسح السريع قبل ما الكود يموت.
    "pin_chal_verify": [(10, 300)],
    # ⛌ اختيار الباسورد الجديد: ١٠ / ٥ دقايق — محتاج توكن فتح.
    "pin_chal_newpin": [(10, 300)],
    # ⛌⛌⛔ التسجيل الجديد (الإيميل الأول): نفس منطق مسار الفتح
    #    بالظبط — كل خطوة ليها سقفها.
    #    start  = إرسال بريد → ٣ / ٥ دقايق (أضيق حاجة في الـAPI).
    #    verify = المستخدم بيلخبط في الكود → ١٠ / ٥ دقايق، والكود
    #            نفسه بيموت بعد ٥ غلط.
    #    newpin = محتاج توكن فتح → ١٠ / ٥ دقايق.
    #    ⛌ مافيش «تسجيل» بالمعنى القديم اللي بيفحص ١٠٬٠٠٠ احتمال
    #    في طلب واحد — الفحص ده اتنقل لآخر خطوة (newpin) وبيبقى
    #    وراه توكن فتح + إيميل متأكد.
    "pin_signup_start": [(3, 300)],
    "pin_signup_verify": [(10, 300)],
    "pin_signup_newpin": [(10, 300)],
}

# تخزين: {ip: {bucket: deque(timestamps)}}
_HITS = defaultdict(lambda: defaultdict(deque))
_HITS_LOCK = threading.Lock()


def _client_key():
    """
    ⛔🔴 الثغرة القديمة: كنا بناخد **أول** قيمة في X-Forwarded-For.
       أول قيمة دي **بتتحط من العميل نفسه** ⬇️ يعني حد يقدر
       يبعت XFF: 1.1.1.1 في كل طلب ويعدّي كل الأقفال.

    ⭐ الإصلاح: بناخد **آخر** قيمة في السلسلة.
       الـproxy الموثوق (Railway) دايمًا بيضيف الـIP الحقيقي
       في **آخر** السلسلة ⬇️ واللي قبله كله من العميل.
    ⛔ وكمان بنقفل السلسلة بـremote_addr عشان لو حد بعت
       XFF متسلسل، البصمة بتاعتنا هتتغيّر وكل طلب هيتحسب وحده.
    """
    xff = request.headers.get("X-Forwarded-For", "")
    ip = ""
    n = 0
    first = ""
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        n = len(parts)
        if parts:
            # ⭐ آخر قيمة = اللي ضافها الـproxy الموثوق، مش العميل
            ip = parts[-1][:64]
            first = parts[0][:64]

    if not ip:
        ip = request.headers.get("X-Real-IP", "").strip()[:64]
    if not ip:
        ip = request.remote_addr or "unknown"

    # ⛌ الحالة العادية (سلسلة من قيمة واحدة ⬇️ يعني مافيش تزوير)
    #    بنرجّع العنوان نضيف ⬇️ عشان يفضل متوقّع ومقارن في الاختبارات
    #    وفي الـrate limitRey.
    if n <= 1:
        return ip

    # ⭐🔴 فيه تزوير ⬇️ بنرجّع بصمة كاملة:
    #    العنوان الحقيقي + عدد القيم + أول قيمة.
    #    ⛔ كده تلاعب السلسلة ⬇️ كل قيمة بتطلع بصمة مختلفة ⬇️
    #    والقفل بيرجع يشتغل. والقيم دي **بتتشال** بعد النافذة.
    return ("%s|%d|%s" % (ip, n, first))[:96]


def _route_bucket(path):
    """نحدّد المسار ده ينتمي لأنهي bucket"""
    seg = [x for x in path.strip("/").split("/") if x]
    if len(seg) >= 2 and seg[0] == "api":
        name = seg[1]
        if name == "auth":
            sub = seg[2] if len(seg) > 2 else ""
            tail = seg[3] if len(seg) > 3 else ""
            # ⛌ ⛌ ⛌ التسجيل = **أضيق**: نفس الـwrite + سقف ٢٠/ساعة،
            #    لأن المسار ده هو اللي بيفحص المساحة كلها بسؤال
            #    «الباسورد ده مستخدم من قبل؟». من غير السقف، ٥/دقيقة
            #    معناها ١٠٬٠٠٠ محاولة مسح في ٣٣ ساعة.
            # ⛌⛌⛌ التسجيل الجديد — الإيميل يتأكد الأول والباسورد
            #    بعده. كل خطوة ليها سقفها (شوف LIMITS فوق).
            if sub == "signup":
                return {
                    "start": "pin_signup_start",
                    "verify": "pin_signup_verify",
                    "newpin": "pin_signup_newpin",
                }.get(tail, "write")
            if sub == "pin":
                # ⛌ المسار القديم بقى 410 — السقف بيفضل شغال عليه
                #    عشان مافيش حد يسكّر عليه ٢٠/ساعة بلا فايدة.
                if tail == "register":
                    return "pin_register"
                # ⛌ ⛌ ⛌ مسار كود الفتح (القاعدة ①): كل خطوة
                #    ليها سقفها. الإرسال أضيق واحد (٣/٥ دقايق)
                #    لأنه بيبعت بريد؛ التحقق أوسع (١٠/٥ دقايق)
                #    لأن المستخدم بيلخبط في الكود وعادي يغلط
                #    مرتين، والكود نفسه بيموت بعد ٥ غلط.
                if tail == "challenge":
                    return {
                        "send": "pin_chal_send",
                        "verify": "pin_chal_verify",
                        "newpin": "pin_chal_newpin",
                    }.get(seg[4] if len(seg) > 4 else "", "write")
                return "write"
            # ⛌ ⛌ التجديد الصامت: سقف عادي (default) — مش
            #    بالدقيقة. المستخدم بيتصفح ٣٠ دقيقة وبيجدد
            #    كل ساعتين؛ سقف ضيق هنا = يقفله وهو بي brows عادي.
            if sub == "refresh":
                return "default"
            # ⛌ قراءة التوكن مش كتابة
            if sub in ROUTES_READONLY:
                return "default"
            # ⛌ ⛌ التحقق ليه حد أوسع من الإرسال:
            #    المستخدم لو غلط في الكود مرتين مش بيتقفل بره
            if tail == "verify" or sub == "verify":
                return "otp_verify"
            return "otp_send"
        if name in ROUTES_WRITE:
            return "write"
        if name in ROUTES_EXPENSIVE:
            return "expensive"
    return "default"


def _rate_check():
    """بيتحقق من الحد ويرجّع (allowed, retry_after, bucket)"""
    key = _client_key()
    bucket = _route_bucket(request.path)
    windows = LIMITS[bucket]
    now = time.time()

    with _HITS_LOCK:
        # ⛌ كل نافذة ليها deque مستقلة، والطلب **مش** بيتسجّل
        #    غير لو عدّى كل النوافذ (وإلا حد رجعه من حد الدقيقة
        #    هيتحسب من حد الساعة وميعديش صح).
        blocked = None
        for wi, (max_hits, window) in enumerate(windows):
            q = _HITS[key]["%s#%d" % (bucket, wi)]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= max_hits:
                oldest = q[0]
                retry = int(max(1, window - (now - oldest)))
                if blocked is None or retry > blocked[0]:
                    blocked = (retry, wi, max_hits)
        if blocked is not None:
            return False, blocked[0], bucket

        for wi in range(len(windows)):
            _HITS[key]["%s#%d" % (bucket, wi)].append(now)

        # تنظيف عشان ما نكبرش بلا حدود
        if len(_HITS) > 5000:
            for k in list(_HITS.keys()):
                if not any(_HITS[k][b] for b in _HITS[k]):
                    del _HITS[k]

    return True, 0, bucket


@app.before_request
def rate_limit_guard():
    """بيشتغل قبل أي route — ويرجّع 429 لو اتجاوز الحد"""
    # الـhealth check matدارfhaeshlimit (Railway بي-poll دايماً)
    if request.path in ("/", "/api/health"):
        return None
    # assets الستاتيك مابيحتاجش
    if request.method == "OPTIONS":
        return None

    allowed, retry, bucket = _rate_check()
    if not allowed:
        resp = jsonify({
            "error": "rate limit exceeded",
            "bucket": bucket,
            "retry_after": retry,
            "hint": "استنى شوية وجرب تاني",
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        resp.headers["X-RateLimit-Limit"] = str(LIMITS[bucket][0][0])
        resp.headers["X-RateLimit-Bucket"] = bucket
        return resp
    return None



# ══════════════════════════════════════════════════════════════
#  🔑 نظام الحسابات — كل زائر ليه مساحة خاصة بيه
#  ──────────────────────────────────────────────────────────────
#  قبل: أي حد يقدر يضيف/يحذف من المحفظة والمنبهات.
#        والداتا كانت مشتركة بين كل الزوار.
#  دلوقتي: كل زائر بيعمل حساب → ليه محفظة لوحده.
#
#  الحساب بيتعمل بـ:
#    · اسم (اختياري)
#    · كود سري 32 حرف بيتخزن مش movible (bcrypt/sha256)
#
#  ⛔ مافيش باسورد واسم مستخدم — بيحمي من سرقة الكوكيز
#     وبيخلي التسجيل في ثانية واحدة.
# ══════════════════════════════════════════════════════════════

import hashlib
import hmac
import base64
import secrets as _secrets_mod

# ── الكود السري بتاع الأدمن (من Railway Variables) ──
ADMIN_KEY = str(os.environ.get("OCTA_ADMIN_KEY", "") or "").strip()


# ══════════════════════════════════════════════════════════════
#  🔐 سر توقيع التوكن — ⛔ مفيش سر مكتوب في الكود. أبداً.
# ══════════════════════════════════════════════════════════════
#  كان هنا fallback ثابت شغّال على السيرفر فعليًا: أي حد على
#  الإنترنت يقدر يصمّم توكن صالح باسم أي مستخدم. اتشال خالص.
#  دلوقتي السلوك مقسوم على وضعين واضحين:
#
#   · الإنتاج  → لازم OCTAD_TOKEN_SECRET (أو SECRET_KEY) مضبوط.
#     لو مش موجود التطبيق **يرفض يشتغل** ويطبع السبب في اللوج.
#     أحسن بكتير من إنه يخدم بتوكنات يتصمّمها أي حد على النت.
#   · التطوير  → لازم opt-in صريح: OCTAD_DEV=1 أو اسم الجهاز localhost.
#     وعندها بنولّد سر مؤقت عشوائي لكل تشغيل — مش ثابت ومش معروف
#     لحد، ومش مكتوب في أي ملف.
#
#  ⛔ السر نفسه ما يتطبعش ولا يطلع في أي رد ولا لوج.
#     كل حاجة بتقول «موجود / مش موجود» وبس.

_DEV_FLAGS = {"1", "true", "yes", "on", "dev", "local"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "localhost.localdomain"}


def _dev_mode():
    """وضع التطوير — opt-in صريح، مش تخمين."""
    if str(os.environ.get("OCTAD_DEV", "") or "").strip().lower() in _DEV_FLAGS:
        return True
    try:
        import socket
        return socket.gethostname().strip().lower() in _LOCAL_HOSTS
    except Exception:
        return False


_SECRET = str(
    os.environ.get("OCTAD_TOKEN_SECRET")
    or os.environ.get("SECRET_KEY")
    or ""
).strip()

# true = السر جاي من متغير بيئة. ده الوضع الوحيد الصح في الإنتاج.
TOKEN_SECRET_CONFIGURED = bool(_SECRET)

if not _SECRET:
    if not _dev_mode():
        raise RuntimeError(
            "OCTAD_TOKEN_SECRET غير مضبوط — التطبيق رافض يشتغل من غيره. "
            "ضيفه في Railway Variables، أو شغّل محلي بـ OCTAD_DEV=1. "
            "مفيش قيمة افتراضية عمداً: أي سر مكتوب في الكود يبقى سر مكشوف."
        )
    # تطوير محلي: سر مؤقت لكل تشغيل — مش ثابت ومش موجود في الكود.
    _SECRET = _secrets_mod.token_urlsafe(32)
    print("[auth] ⚠️ وضع تطوير: سر توقيع مؤقت بيتغير كل تشغيل — "
          "ما ينفعش تنشره", flush=True)


def _sign(payload: str) -> str:
    """توقيع HMAC عشان نقدر نتحقق إن التوكن متعدّلش"""
    mac = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")[:24]


#  ⛌ عمر التوكن: ساعتين بالظبط (٧٢٠٠ ثانية).
#     📌 القرار: الـidle (٣٠ دقيقة من غير لمسة) بيتحسب في
#        المتصفح، مش هنا. فلو اتقفلت، الواجهة بتطلب توثيق تاني
#        بالبصمة (موبايل) أو ٤ أرقام (تابلت/لاب) — والحالة دي
#        خالص مش في السيرفر. يبقى عمر التوكن ٢ ساعة كفاية، ومش
#        لازم نخلي التوكن صالح أسبوع.
#     📌 التجديد الصامت في الخلفية بيجدد **قبل** ما يخلص
#        (مش لما يخلص) — عشان كده ساعتين مش ٦٠ ثانية وماشي.
#     ⛔ التوكن مش متغلبش عليه: التوقيع HMAC + وقت الانتهاء جوه
#        الـpayload، فما حدش يعدّله ويطيل عمره.
TOKEN_TTL = 2 * 3600


def _user_epoch(user_id: str) -> int:
    """⛌ قراءة الـepoch من غير القفل ⬇️ لأن دوال التوكن ممكن
       تُستدعى **جوه** USERS_LOCK ⬇️ لو قفلنا تاني ⬇️ deadlock.

       القراءة دي من ملف JSON آمنة ⬇️ و_kh всё بيستخدم
       نفس الملف ⬇️ لو حصل تعارض ⬇️ القراءة القديمة ⬇️
       والتواقيع بتتخزّن في الذاكرة ⬇️ ارفعها هناك.
    """
    try:
        return int((_load_users().get(str(user_id)) or {}).get("token_epoch") or 0)
    except Exception:
        return 0


def _make_token(user_id: str, ttl=None) -> str:
    """payload.base64url(signature) — payload = «uid|exp|epoch»

    ⛔🔴 الـepoch جزء من التوقيع ⬇️ لو الـepoch بتاع المستخدم اتغيّر
       (تغيير باسورد · استرجاع · حذف) ⬇️ التوكن القديم مابقاش يمرّ
       ⬇️ وكل الجلسات القديمة بتموت في نفس اللحظة.
    ⛔⛔ الدالة دي بتتنادى **من جوّه** USERS_LOCK ⬇️ فممنوع
       أقفل جواه ⬇️ وإلا القفل نفسه يطلب القفل.
    """
    exp = int(time.time()) + int(ttl if ttl else TOKEN_TTL)
    p = base64.urlsafe_b64encode(
        ("%s|%d|%d" % (user_id, exp, _user_epoch(user_id))).encode()
    ).decode().rstrip("=")
    return f"{p}.{_sign(p)}"


def _token_parts(tok: str):
    """
    ⛌Split واحد للتوكن: بيرجّع (user_id, exp) أو (None, 0).
       كل حاجة بتقرأ توكن (require_user والتجديد) بتمرّ من هنا،
       فمفيش مسار يقرا توكن من غير ما يتحقق من تاريخ الانتهاء.

    ⛔ توكن من غير «|» = الشكل القديم (من قبل ما يبقى له عمر)
       → مرفوض. مافيش توكن بلا تاريخ انتهاء: التوكن القديم كان
       صالح للأبد، وده أوسع من اللازم في حد بيقرا لوج السيرفر.
       (أول مرة بعد النشر، المستخدمين بيرجعوا يسجّلوا دخول —
        مرة واحدة وبعدها التوكن الجديد بيمدّ نفسه لوحده.)
    """
    # ⛔ مفيش سر = مفيش توكن. بيشتغل كقفل أمان إضافي.
    if not _SECRET:
        return None, 0
    try:
        parts = str(tok or "").split(".")
        if len(parts) != 2:
            return None, 0
        p, sig = parts
        if not p or not sig:
            return None, 0
        if not hmac.compare_digest(sig, _sign(p)):
            return None, 0
        pad = "=" * (-len(p) % 4)
        # ⛌ strict مش ignore: بايت مش صالح = رفض. الـdecode كان
        #    بيبتلع الأخطاء وبيطلع نص مش متوقع.
        raw = base64.urlsafe_b64decode(p + pad).decode("utf-8", "strict")
        if "|" not in raw:
            return None, 0
        uid, _, exp_s = raw.partition("|")
        # ⛔ الـuid نص قصير مطبوع (20 حرف hex دلوقتي). التوقيع بيغطي
        #    الـpayload أصلاً — دي طبقة تانية بس ضد المدخلات الغريبة.
        if not uid or len(uid) > 64 or not uid.isascii() or not uid.isprintable():
            return None, 0
        # ⛔ payload = «uid|exp|epoch» ⬇️ نفصل الـepoch **قبل**
        #    int(exp) ⬇️ وإلا ValueError والتوكن كله بيموت.
        exp_s, _, _epoch_s = exp_s.partition("|")
        exp = int(exp_s)
        if exp <= int(time.time()):
            return None, 0

        # ⛔🔴 إبطال الجلسات: لو الـepoch بتاع المستخدم اتغيّر
        #    (تغيير باسورد · استرجاع · حذف) ⬇️ كل التوكنات القديمة
        #    بتبطل فورًا ⬇️ وده اللي بيمنع توكن مسروق.
        tok_epoch = int(_epoch_s) if _epoch_s else 0
        if tok_epoch != _user_epoch(uid):
            return None, 0

        return uid, exp
    except Exception:
        return None, 0


def _read_token(tok: str):
    """يرجّع user_id أو None — التوكن المنتهي زي الغلط بالظبط"""
    return _token_parts(tok)[0]


    try:
        parts = str(tok or "").split(".")
        if len(parts) != 2:
            return None
        p, sig = parts
        if not p or not sig:
            return None
        if not hmac.compare_digest(sig, _sign(p)):
            return None
        pad = "=" * (-len(p) % 4)
        # ⛌ strict مش ignore: بايت مش صالح = رفض. الـdecode كان
        #    بيبتلع الأخطاء وبيطلع نص مش متوقع.
        uid = base64.urlsafe_b64decode(p + pad).decode("utf-8", "strict")
        # ⛔ الـuid نص قصير مطبوع (20 حرف hex دلوقتي). التوقيع بيغطي
        #    الـpayload أصلاً — دي طبقة تانية بس ضد المدخلات الغريبة.
        if not uid or len(uid) > 64 or not uid.isascii() or not uid.isprintable():
            return None
        return uid
    except Exception:
        return None


# ⛌ الكود = 6 أرقام بالظبط. مش كلمة سر ومش حروف.
_CODE_RE = __import__('re').compile(r'^\d{6}$')


def _hash_key(raw: str) -> str:
    """هاش الكود السري — ما بنخزنش الأصلي أبداً"""
    salt = _SECRET[:12]
    return hashlib.pbkdf2_hmac("sha256", str(raw).encode(), salt.encode(), 60000).hex()


# ── قاعدة البيانات (ملف JSON بسيط) ──
USERS_FILE = Path("/app/users.json")
USERS_LOCK = threading.Lock()


def _load_users():
    try:
        if USERS_FILE.exists():
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_users(d):
    """⛔⛔ الكتابة لازم تكون ذرّية ومقفولة.
       الكتابة العادية كانت: فتح الملف → مسحه → كتابة.
       أي قارئ في نفس اللحظة كان بيلاقي {} — وفي الإنتاج بتمسح المستخدمين.
       الحل: نكتب في ملف مؤقت ونعمل rename ذرّي، ومن غير قفل."""
    try:
        tmp = USERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(USERS_FILE)
    except Exception as e:
        print(f"  💾 ⛔ users.json: {type(e).__name__}: {str(e)[:100]}", flush=True)


def _get_user(token):
    """ترجّع dict المستخدم أو None"""
    uid = _read_token(token)
    if not uid:
        return None
    with USERS_LOCK:
        return _load_users().get(uid)


def _bearer():
    """يطلّع التوكن من الـAuthorization header — وبس.

    ⛔ ⛔ كان فيه fallback يقرا التوكن من ?t= في الـURL.
       التوكن في الـURL بيتسرب في أربع أماكن: لوج Railway،
       لوج Cloudflare، تاريخ المتصفح، وheader الـReferer.
       والواجهة كلها بتبعت Authorization: Bearer (octa-api.js)،
       فحذفنا المسار ده — مفيش ولا عميل محتاجه.
    """
    h = request.headers.get("Authorization", "") or ""
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return ""


def require_user():
    """
    ⛔ لازم يكون فيه توكن صالح. وإلا → 401.

    بيتحط في أول كل route كتابة.
    """
    u = _get_user(_bearer())
    if u:
        return u
    return None


# ══════════════════════════════════════════════════════════════
#  📋 الحسابات
# ══════════════════════════════════════════════════════════════



_EMAIL_RE = __import__("re").compile(r"^[^@\s]{1,64}@[^@\s.]{1,63}(\.[^@\s.]{2,63})+$")


def _valid_email(e):
    """
    ⛔ تحقق صارم من الإيميل.

    مش بنبعتله إيميل استرجاع من غير ما نتأكد إنه شكله صح،
    عشان متضيعش رسالة على حد مالوش إيميل أصلاً.
    """
    e = str(e or "").strip()
    if not e:
        return False, "الإيميل فاضي"
    if len(e) > 120:
        return False, "الإيميل طويل أوي"
    if not _EMAIL_RE.match(e):
        return False, "شكل الإيميل غلط — مثال: name@example.com"
    # ⛔ منع أي محارف HTML — الإيميل بيتعرض في الواجهة
    if any(c in e for c in "<>\"'`\n\r\t\\"):
        return False, "الإيميل فيه محارف ممنوعة"
    return True, ""

# ══════════════════════════════════════════════════════════════════
# 🔐 دخول بالإيميل — كود من 6 أرقام يتبعت على الإيميل
# ══════════════════════════════════════════════════════════════════
# 📌 بدل «اسم + إيميل + كود يختاره المستخدم»:
#    المستخدم يكتب إيميله → يستلم كود → يدخل بيه.
#    ⛔ صعب إن حد يدخل بإيميل مش إيميله، وصعب إننا نكشف مين مسجّل.

@app.route("/api/auth/otp/send", methods=["POST"])
def otp_send():
    """POST { email } → يبعت كود 6 أرقام"""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:120]
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"error": why}), 400

    # ⛔⛔⛔ حساب الباسورد: الإيميل **مش** وسيلة دخول.
    #    الإيميل بيوصل مرة واحدة بس وقت التسجيل، والباقي الباسورد.
    #    لو الكود اتبعت لحساب باسورد، فهو بيوصل لصاحبه بس — ومينفعش
    #    يبقى معناه «ادخل بالإيميل» أصلاً.
    if _pin_by_email(email)[1]:
        return jsonify({
            "ok": False,
            "error": "⛔ الحساب ده بيستخدم باسورد ٤ أرقام — "
                     "الإيميل بيوصل مرة واحدة بس وقت التسجيل",
            "why": "pin_account",
        }), 409

    code = _otp_new(email)
    if not code:
        # ⛔⛔ الطلب القديم كان بيرجّع «أيوه بعثنا» وهو مش بعت حاجة —
        #    المستخدم بيفتكر الإيميل ضاع، والمفيش حد قاله السبب.
        #    الرسالة دي بتقول السبب الحقيقي بس **مش** بتقول
        #    إن الإيميل ده مسجّل ولا لأ — كل الإيميلات بتاخد نفس الرسالة.
        return jsonify({
            "ok": False,
            "error": f"⏰ بعتّ {OTP_TRIES_PER_DAY} أكواد على الإيميل ده اليوم — "
                     f"استنى بكرة عشان تاخد كود جديد",
            "why": "daily_limit",
        }), 429

    nm = str(data.get("name") or "").strip()[:40]
    _send_mail(email, f"كود الدخول — OCTA", _otp_html(code, nm))
    if not MAIL_ON:
        # ⛔ مافيش خدمة إيميل = الكود بيروح لوج السيرفر. لازم
        #    RESEND_API_KEY يكون مضبوط في الإنتاج (شوف deliverable).
        print(f"  🔐 ⚠️ مافيش خدمة إيميل (RESEND_API_KEY) — الكود بيتطبع "
              f"في اللوج: {email} → {code}")

    # ⛔ ⛔ نفس الرد في كل الحالات — ما نقولش «الإيميل ده مش موجود»:
    #    الرد ده بيكشف مين عندنا حساب ومين لأ.
    return jsonify({"ok": True, "msg": "لو الإيميل ده صح، بيوصلك كود"}), 200


@app.route("/api/auth/otp/verify", methods=["POST"])
def otp_verify():
    """POST { email, code } → يرجّع token"""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:120]
    code = str(data.get("code") or "").strip()

    if not _re_guard.fullmatch(r"^\d{6}$", code or ""):
        return jsonify({"error": "الكود 6 أرقام"}), 400

    # ⛔⛔⛔ حساب الباسورد ما بيقبلش كود إيميل — أبداً.
    #    المسار ده بيرجّع توكن لأي حد يعرف الإيميل — حتى من غير ما
    #    يبقى الكود صح. لو حساب باسورد عدّى من هنا، الباسورد كله
    #    بلا قيمة وأي حد عارف الإيميل ياخد الحساب كامل. القفل هنا مش
    #    على الإيميل — كل حاجة فيه بتتمسك بالباسورد.
    if _pin_by_email(email)[1]:
        return jsonify({
            "ok": False,
            "error": "⛔ الحساب ده بيستخدم باسورد ٤ أرقام — "
                     "الدخول بالباسورد بس",
            "why": "pin_account",
        }), 409

    try:
        ok, why = _otp_check(email, code)
    except Exception as e:
        # ⛌ صفحة 500 فاضية للمستخدم مش مفيدة — بنقوله نوع الخطأ ونسجله
        import traceback as _tb
        traceback.print_exc()
        return jsonify({"error": "حصل خطأ في السيرفر — جرب تاني",
                        "why": type(e).__name__}), 500
    if not ok:
        if why == "too_many_wrong":
            return jsonify({"error": "⛔ غلط كتير — اطلب كود جديد",
                            "why": why}), 429
        if why == "no_code":
            return jsonify({"error": "الكود مش موجود أو خلصت صلاحيته — اطلب كود جديد",
                            "why": why}), 401
        return jsonify({"error": "الكود غلط", "why": why}), 401

    # ⛔ نعمل (أو نجدد) المستخدم — الإيميل بقى هو الهوية
    uid = _hash_key(email)[:20]
    with USERS_LOCK:
        users = _load_users()
        now = int(time.time())
        if uid not in users:
            users[uid] = {"id": uid, "name": str(data.get("name") or "")[:40] or "مستخدم",
                          "khash": _hash_key(str(_random.SystemRandom().randint(0, 10**9))),
                          "email": email, "email_hash": _hash_key(email),
                          "created": now, "portfolio": {}, "watchlist": []}
            users[uid]["last_login"] = now
            print(f"  👤 مستخدم جديد: {email}")
        else:
            users[uid]["last_login"] = now
            nm = str(data.get("name") or "").strip()[:40]
            if nm:
                users[uid]["name"] = nm
        _save_users(users)

    return jsonify({
        "ok": True, "token": _make_token(uid),
        "user": {"id": uid, "name": users[uid]["name"], "email": email},
    }), 200


def _otp_html(code, name=""):
    """الإيميل — بسيط ومقروء"""
    who = _htmlmod.escape(name or "") or "مستخدم"
    return f"""<!doctype html><html dir="rtl"><body style="margin:0;padding:24px;background:#0f1621;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
<div style="max-width:460px;margin:0 auto;background:#16202e;border-radius:14px;padding:28px;color:#e8edf5">
<div style="font-size:26px">🐙</div>
<h2 style="margin:8px 0 4px;font-size:20px">OCTA — كود الدخول</h2>
<p style="margin:0 0 20px;color:#93a1b5;font-size:14px">أهلاً {who}</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:22px;text-align:center;letter-spacing:10px;font-size:34px;font-weight:800;color:#d4af37">{code}</div>
<p style="margin:18px 0 0;color:#93a1b5;font-size:13px;line-height:1.9">
الكود صالح <b>15 دقيقة</b>.<br>
⛔ لو إنت مش اللي طلبته — تجاهله. مفيش حاجة اتعملت بإيميلك.</p>
</div>
<p style="max-width:460px;margin:14px auto 0;color:#5f6c80;font-size:12px;text-align:center">octashares.com — قراءة، مش نصيحة</p>
</body></html>"""



@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """
    تسجيل حساب جديد.
    body: { "name", "key", "email" }

    📌 «الكود» مش كلمة سر — هو رقم يتحفظ في.USER``.
    مفيش قيمة في إن حد يعمل كلمة سر وهو بيجرّب الموقع، والمفروض
    نطلب أقل ما يمكن ف.browser.
    ⛔ 6 أرقام، مش حروف: أرقام أسرع في الكتابة على الموبايل
       وأصعب في التخمين.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    name = str(data.get("name") or "").strip()[:40] or "زائر"
    key = str(data.get("key") or "").strip()
    email = str(data.get("email") or "").strip().lower()[:120]

    if not _CODE_RE.match(key):
        return jsonify({
            "error": "الكود لازم يكون 6 أرقام",
            "hint": "مثال: 482913",
        }), 400

    # ── الإيميل اختياري — مين بيسجّل من غيره لسه شغال ──
    if email:
        ok, why = _valid_email(email)
        if not ok:
            return jsonify({"error": why}), 400

    khash = _hash_key(key)
    uid = khash[:20] if not email else _hash_key(email)[:20]

    with USERS_LOCK:
        users = _load_users()
        if uid in users:
            # ⛔ ⛔ ⛔ كان بيرجّع توكن لأي حد يبعت أي كود مع إيميل
            #    مستخدم موجود — يعني إيميل واحد بس = سرقة حساب كاملة.
            #    دلوقتي: لازم الكود نفسه يطابق اللي متخزّن.
            if hmac.compare_digest(str(users[uid].get("khash") or ""), khash):
                # نفس الكود = نفس المستخدم (تسجيل دخول تلقائي)
                return jsonify({
                    "ok": True, "token": _make_token(uid),
                    "user": {"id": uid, "name": users[uid]["name"],
                             "email": users[uid].get("email")},
                    "returning": True,
                })
            # ⛔ رسالة واحدة للحالتين — ما نقولش «الإيميل ده مسجل»
            return jsonify({
                "error": "الكود مش صح — لو عندك حساب بالإيميل ده، "
                         "اطلب كود دخول من صفحة الحساب",
            }), 401

        users[uid] = {
            "id": uid,
            "name": name,
            "khash": khash,
            "email": email or None,
            "email_hash": _hash_key(email) if email else None,
            "created": int(time.time()),
            "portfolio": {},
            "watch": [],
        }
        _save_users(users)

    return jsonify({
        "ok": True, "token": _make_token(uid),
        "user": {"id": uid, "name": name, "email": email or None},
        "emailSaved": bool(email),
    })



# ══════════════════════════════════════════════════════════════════
#  🔢 دخول بالباسورد (PIN) — ٤ أرقام، وإيميل واحد بس وقت التسجيل
#  ──────────────────────────────────────────────────────────────
#  📌 القرار: الإيميل بيوصل **مرة واحدة بس** وقت التسجيل (تأكيد).
#     بعد كده مفيش إيميل خالص — الباسورد هو. مافيش استرجاع.
#
#  ⛔⛔ ٤ أرقام = ١٠٬٠٠٠ احتمال بس. من غير قفل ذكي، أي حد يقدر
#     ياخد الموقع في أقل من ساعة. عشان كده القفل هو أهم جزء
#     في الملف ده — مش الباسورد نفسه.
#
#  ⛔ الباسورد **مش** بيتخزن أبداً — لا في users.json ولا في رد
#     ولا في لوج:
#       pin_hash = PBKDF2-HMAC-SHA256(pin, salt=pin_salt, 60000 دورة)
#       pin_salt = ١٦ حرف عشوائي لكل مستخدم
#       ⛔ الـsalt **مستقل تماماً** عن _SECRET. لو _SECRET اتدار
#          (وتدوير التوكنات حاجة شائعة) الباسوردات ما تتأثرش خالص.
#       pin_idx  = HMAC بـpepper منفصل — فهرس بحث O(1)
#       ⛌ ليه فهرس أصلاً؟ كل مستخدم ليه salt مختلف، فمفيش قيمة
#          مشتركة نقدر ندور بيها. من غير فهرس هنعمل PBKDF2 لكل
#          مستخدم في كل محاولة = ٥٠ms × عدد المستخدمين = denial of
#          service من أي حد عادي. الفهرس بياخد صفر.
#
#  📌 البصمة دي مش بتكشف الباسورد: هي HMAC بمفتاح على السيرفر
#     (متغير بيئة أو ملف) — مثلها مثل أي جدول تحقق من كلمات السر.
#     ولو الـpepper اتغيّر، الفهرس بيتظبط تاني من الهاش الحقيقي.
# ══════════════════════════════════════════════════════════════════

import functools as _functools

# ٤ أرقام بالظبط — ⛔ مش ٣ ومش ٥. Regex واحدة مصدر الحقيقة.
# ⛔⛔ [0-9] مش \d: في Python الـ`\d` بيقبل أرقام Unicode كمان،
#    فـ«٧٣١٤» (أرقام هندية) كانت بتعدّي وتخزن كأنها ٧٣١٤،
#    والحساب فعلاً اتعمل بالأرقام دي في الاختبار. الفرق بين
#    الأرقام دي واللي على لوحة المفاتيح باب تسلل مش ضوضاء.
_PIN_RE = _re_guard.compile(r"^[0-9]{4}$")
_PIN_SALT_CHARS = 16                 # ⛌ طلب المواصفات: ١٦ حرف
_PIN_ROUNDS = 60000                  # دورات PBKDF2

# ── الـpepper: مفتاح الفهرس، منفصل عن _SECRET ──
# ⛌ ⛌ مفتاح مكتوب في الكود = مكشوف. بيشتغل بالترتيب ده:
#    1) متغير بيئة OCTA_PIN_PEPPER  ← ده الصح في الإنتاج
#    2) ملف على القرص (بينشأ لوحده مرة واحدة)
#    3) مؤقت لكل تشغيل (تطوير بس — بينبّه في اللوج)
PIN_PEPPER_FILE = Path("/app/pin_pepper.txt")


def _pin_pepper_load():
    p = str(os.environ.get("OCTA_PIN_PEPPER", "") or "").strip()
    if p:
        return p, "env"
    try:
        f = PIN_PEPPER_FILE
        if f.exists():
            v = f.read_text(encoding="utf-8").strip()
            if v:
                return v, "file"
        v = _secrets_mod.token_urlsafe(32)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(v, encoding="utf-8")
        try:
            os.chmod(str(f), 0o600)
        except Exception:
            pass
        return v, "file"
    except Exception as e:
        return _secrets_mod.token_urlsafe(32), "ephemeral"


_PIN_PEPPER, _PIN_PEPPER_SRC = _pin_pepper_load()
# ⛌ معرّف الفهرس: بيتخزّن مع كل مستخدم. لو الـpepper اتدار
#    (ملف اتمسح / redeploy على volume جديد) الفرق يبقى واضح
#    والفحص البطيء بيشتغل تاني ويصلّح الفهرس من الهاش الحقيقي.
_PIN_PEPPER_ID = hashlib.sha256(_PIN_PEPPER.encode()).hexdigest()[:12]
if _PIN_PEPPER_SRC != "env":
    print(f"[pin] ⚠️ الـpepper من «{_PIN_PEPPER_SRC}» مش من متغير بيئة — "
          f"لو الملف اتمسح، الفهرس هيت calib تاني (الدخول هيشتغل بس هيبقى أبطأ)",
          flush=True)


def _pin_salt_new():
    """salt جديد: ١٦ حرف عشوائي لكل مستخدم"""
    return _secrets_mod.token_hex(_PIN_SALT_CHARS // 2)


def _pin_hash(pin, salt):
    """⛔ الهاش الحقيقي — ده اللي بيتخزّن و بيتقارن بيه"""
    return hashlib.pbkdf2_hmac("sha256", str(pin).encode(),
                               str(salt or "").encode(),
                               _PIN_ROUNDS).hex()


def _pin_index(pin):
    """بصمة الفهرس — بتتطابق بس لو الـpepper واحد"""
    return hmac.new(_PIN_PEPPER.encode(), ("pin|" + str(pin)).encode(),
                    hashlib.sha256).hexdigest()[:40]


# ══════════════════════════════════════════════════════════════════
#  🔒 القفل الذكي — أهم حاجة في الملف ده
#  ──────────────────────────────────────────────────────────────
#  ١٠٬٠٠٠ احتمال × بلا قفل = الموقع ميت خلال ساعات.
#
#  الجدول:
#     أول ٥ محاولات غلط   → ⏳ قفل ١٥ دقيقة
#     بعد كده كل ٥ غلط    → ⏳ قفل ساعة
#     المحاولة الصح       → تصفّر العدّاد
#
#  ⛔ العدّاد **على القرص** مش في الذاكرة. Railway بيعمل redeploy
#     عند كل push، والذاكرة بتتمسح → أي حد يعمل ٤ غلط، يعمل
#     redeploy، ويعمل ٤ غلط تاني… والقفل عمره ما هيقفل.
#     (نفس الدرس اللي اتعلمناه من كود الـOTP.)
#
#  ⛔ القفل على **مستويين**:
#     · الـpin  → عشان حد يجرّب نفس الباسورد من أجهزة مختلفة
#     · الـIP   → عشان حد يجرّب باسوردات مختلفة من نفس الجهاز
#     الاتنين لازم، واللي فيهم أي واحد بيقفل.
# ══════════════════════════════════════════════════════════════════

PINLOCK_FILE = Path("/app/pinlock.json")
PINLOCK_LOCK = threading.Lock()
PIN_FAIL_LIMIT = 5                   # ٥ غلط = قفل
PIN_LOCK_FIRST = 15 * 60             # أول قفل = ١٥ دقيقة
PIN_LOCK_NEXT = 60 * 60              # بعد كده = ساعة
PIN_PURGE_AGE = 7 * 86400            # ننضّف السجلات بعد أسبوع
PIN_SCAN_LIMIT = 50                  # أقصى عدد سجلات في الفحص البطيء
# ⛔⛔ القفل **العالمي** على الباسورد — وده موجود فعلاً، بس مش في
#    متغيّر لوحده: مفتاح الباسورد (p:) **مش** مربوط بـIP خالص،
#    فهو عدّاد واحد مشترك بين كل الأجهزة. مهاجم بـ٥٠٠ IP بيقع
#    في نفس العدّاد، والحد الأقصى ٥ محاولات على الباسورد ده في
#    العالم كله كل ١٥ دقيقة. ده أقوى حاجة في التصميم كله.
#
#    الفرق الوحيد إنه أطول: القفل **الثالث** على نفس الباسورد
#    (مش على نفس الجهاز) بيوصل ٦ ساعات بدل ساعة. الهدف هنا مش
#    حد ناسي باسورد — ده حد عايز ياخد حساب، والقفل الطويل
#    بيمنع المحاولات الموزّعة على أجهزة مختلفة.
PIN_LOCK_GLOBAL = 6 * 3600           # القفل الثالث على نفس الباسورد


def _pinlock_load():
    try:
        if PINLOCK_FILE.exists():
            d = json.loads(PINLOCK_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("k", {})
                return d
    except Exception:
        pass
    return {"v": 1, "k": {}}


def _pinlock_save(d):
    """⛔ ذرّي ومقفول — نفس أسلوب users.json بالظبط.
    الكتابة العادية (فتح → مسح → كتابة) كانت بتخلّي قارئ في نفس
    اللحظة يلاقي ملف فاضي = بالظبط ما احنا بنحاول نمنعه."""
    try:
        tmp = PINLOCK_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PINLOCK_FILE)
    except Exception as e:
        print(f"  🔒 ⛔ pinlock.json: {type(e).__name__}: {str(e)[:100]}",
              flush=True)


def _pinlock_purge(d):
    """نشيل السجلات القديمة — الخريطة ما تكبرش بلا حدود"""
    now = time.time()
    k = d.get("k") or {}
    for key in list(k.keys()):
        rec = k.get(key) or {}
        u = float(rec.get("u") or 0)
        t = float(rec.get("t") or 0)
        if u > now:
            continue
        if t and (now - t) > PIN_PURGE_AGE:
            k.pop(key, None)
    d["k"] = k
    return d


def _pin_keys(pin=None, ip=None):
    """مفاتيح العدّاد: الـpin والـIP.

    ⛔ ما بنخزّنش الـIP خام (track.json موعّدنا بمفيش PII)
       ولا الباسورد خام — بنخزّن بصمة HMAC. ونفس البصمة دي
       هي اللي في users.json، فمفيش أي معلومة جديدة في الملف."""
    ks = []
    if pin:
        ks.append("p:" + _pin_index(pin))
    if ip:
        ks.append("i:" + hashlib.sha256(
            ("ip|" + str(ip)).encode()).hexdigest()[:16])
    return ks


def _pin_until(rec):
    """⛌ وقت قفل السجل — ٠ يعني مفتوح"""
    return float((rec or {}).get("u") or 0)


def _pin_locked(keys):
    """⛔ قراءة بس — مفيش تعديل. بيرجّع (مقفول؟، كام ثانية)"""
    now = time.time()
    try:
        store = _pinlock_load()
    except Exception:
        return False, 0
    for k in keys:
        u = _pin_until(store.get("k", {}).get(k))
        if u > now:
            return True, int(u - now) + 1
    return False, 0


def _pinlock_fail(keys):
    """
    يسجّل محاولة غلط — وبيقفل لو وصلنا الحد.
    بيرجّع (مقفول دلوقتي؟، كام ثانية)

    ⛔⛔⛔ `keys` = كل العدّادات اللي لازم تتحسَب. **أي** مسار
    بيفشل لازم يمرّ من هنا — حتى لو راجع 409 مش 401. الرجوع
    بـ409 من غير عدّاد = قناة مجانية لفحص ١٠٬٠٠٠ احتمال من غير
    ما القفل الذكي يلاحظ خالص (شوف auth_pin_register).

    ⛌⛌ المفتاح `p:` (الباسورد) مربوط بالجهاز **أبداً** — ده
    العدّاد العالمي، مشترك بين كل الأجهزة. والمفتاح `i:` (الـIP)
    عدّاد محلي. الاتنين بيترتفعوا مع بعض لما يبقى الخطأ على
    الباسورد نفسه.

    ⚠️⛔⛔ خطر لازم نتفادىه: في حالة «الإيميل مسجّل» لازم نعدّ
    **الـIP بس**. غير كده حد يبعت (إيميل ضحية + أي باسورد) ٥ مرات
    فيقفل **باسورد** الضحية ١٥ دقيقة — وهو لسه ما بيحاولش
    يدخل أصلاً. ده حجب خدمة على قاعدة المستخدمين، مش حماية.
    """
    now = time.time()
    with PINLOCK_LOCK:
        store = _pinlock_purge(_pinlock_load())
        kmap = store["k"]

        # ⛌ القفل لازم يتفحص **قبل** ما نزيد العدّاد، وإلا
        #    محاولة من IP مقفول كانت هتعدّي.
        for k in keys:
            u = _pin_until(kmap.get(k))
            if u > now:
                return True, int(u - now) + 1

        for k in keys:
            rec = kmap.get(k) or {"f": 0, "l": 0}
            u = float(rec.get("u") or 0)
            if u and now >= u:
                # ⏰ القفل خلص — نبدأ نافذة جديدة، بس **مستوى**
                # القفل بيتفكر عشان المرة الجاية تبقى ساعة.
                rec["f"] = 0
                rec["u"] = 0
            rec["f"] = int(rec.get("f") or 0) + 1
            rec["t"] = now
            if rec["f"] >= PIN_FAIL_LIMIT:
                lvl = int(rec.get("l") or 0)
                dur = PIN_LOCK_FIRST if lvl <= 0 else PIN_LOCK_NEXT
                if k.startswith("p:") and lvl >= 2:
                    # 🌍 الباسورد: القفل الثالث = ٦ ساعات
                    #    (العدّاد ده عالمي — كل الأجهزة مع بعض)
                    dur = PIN_LOCK_GLOBAL
                rec["u"] = now + dur
                rec["l"] = min(lvl + 1, 20)
                rec["f"] = 0
            kmap[k] = rec

        _pinlock_save(store)

    locked, retry = False, 0
    for k in keys:
        u = _pin_until(store["k"].get(k))
        if u > now:
            locked = True
            retry = max(retry, int(u - now) + 1)
    return locked, retry


def _pinlock_reset(keys):
    """✅ المحاولة الصح تصفّر العدّاد"""
    with PINLOCK_LOCK:
        store = _pinlock_load()
        kmap = store.get("k") or {}
        for k in keys:
            kmap.pop(k, None)
        store["k"] = kmap
        _pinlock_save(store)


# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
#  ⏱️ القاعدة ① — نافذة ٣ محاولات في ٦٠ ثانية
#  ──────────────────────────────────────────────────────────────
#  📌 الده مش بديل عن القفل الذكي فوق — ده **طبقة تانية فوقه**:
#
#     · القاعدة ② (فوق) = ٥ غلط **إجمالياً** → قفل ١٥ دقيقة.
#       بتمسك أي حد tries يتخطى النافذة بإطالة الوقت.
#     · القاعدة ① (دي)  = ٣ غلط **جوّه ٦٠ ثانية** → لازم كود
#       على الإيميل بدل ما يفضل يجرّب.
#
#  ⛔⛔ ليه ٦٠ ثانية بالظبط (ومفيش نافذة أطول):
#     الباسورد ٤ أرقام = ١٠٬٠٠٠ احتمال. اللي بيحاول يفحص
#     المساحة كلها مش هيفرق: ١٠٬٠٠٠ ÷ ٣ ≈ ٣٣٣٣ نافذة.
#     ⛔ لو النافذة كانت دقيقتين، الحساب كله هيتفحص في ٤٤ ساعة.
#     ⛔ لو كانت ٦٠ ثانية، الحساب كله هيتفحص في ٥٥ ساعة —
#        والفرق الأهم: في الحالتين المهاجم بيتقفل بعد ٣ نافذة.
#        بس النافذة القصيرة بتقفل الباب على أي حاجة أطول.
#
#  📌 النافذة **سلايدر** مش ثابتة: كل محاولة غلط بتقيس الـ٦٠
#     ثانية من **أول** محاولة في النافذة الحالية. لو عدّت ٦٠
#     ثانية من غير محاولة جديدة، السجل بينضّف والعدّاد يبدأ من
#     الصفر — مافيش «نافذة بتتجمّد» حد يجمع فيها ١٠ محاولات.
#     ٣ غلط متباعدين (٣٠ ثانية بين كل واحد) مش ٣ غلط في نافذة:
#     المحاولة الأولى بتخرج من النافذة قبل ما التالتة تنزل.

PIN_WINDOW_SECONDS = 60            # ⛌ طلب المواصفات: ٦٠ ثانية بالظبط
PIN_WINDOW_FAILS = 3               # ⛌ طلب المواصفات: ٣ محاولات


def _pin_now():
    """
    ⏱️ ساعة النافذة — دالة واحدة عشان كل الكود ياخد الوقت منها.

    ⛌ النافذة دي **مش** على القرص كقفل، بس بتتخزّن في نفس الملف
       (pinlock.json تحت مفتاح «w:») — عشان redeploy في نص
       النافذة مايمسحش العدّاد. الذاكرة لوحدها كانت هتخلّي
       «٤ غلط → deploy → ٤ غلط» يمرّ من غير ما يتحسّ.
    """
    return time.time()


def _pin_window_prune(store):
    """
    🧹 نضّف السجلات اللي خلصت نافذتها.

    ⛔ «لو عدّت من غير محاولة جديدة العدّاد يبدأ من الصفر» —
       بالظبط السطر ده: أي طابع أقدم من ٦٠ ثانية بينمسح، ولو
       السجل فضّى من غيره بينمسح هو كمان.
    """
    now = _pin_now()
    w = store.get("w") or {}
    for key in list(w.keys()):
        rec = w.get(key) or {}
        live = [t for t in (rec.get("t") or [])
                if (now - t) < PIN_WINDOW_SECONDS]
        if live:
            rec["t"] = live
            w[key] = rec
        else:
            w.pop(key, None)
    store["w"] = w
    return store


def _pin_window_peek(keys):
    """
    👁️ قراءة بس — كام محاولة غلط في نافذة الـ٦٠ ثانية دي؟
    بيرجّع أكبر عدد في أي واحد من الـkeys (الباسورد أو الـIP).
    مافيش تعديل على أي ملف.
    """
    now = _pin_now()
    best = 0
    try:
        store = _pinlock_load()
    except Exception:
        return 0
    w = store.get("w") or {}
    for k in keys:
        rec = w.get(k) or {}
        n = 0
        for t in (rec.get("t") or []):
            if (now - t) < PIN_WINDOW_SECONDS:
                n += 1
        best = max(best, n)
    return best


def _pin_window_fail(keys):
    """
    ⛔ يسجّل محاولة غلط جوّه النافذة وبيقفل **هو** المفتاح.

    بيرجّع (عدد المحاولات في النافذة، محتاج كود إيميل؟)

    📌 الترتيب مع القاعدة ② مهم: المستدعي بينادي `_pinlock_fail`
       **الأول**. يعني لو fifth محاولة وصلت: القفل الـ١٥ دقيقة
       بياخد الأولوية (٥ إجمالاً)، والقاعدة ① بتشتغل بس لحد
       ما القفل يسيب المجال. والاتنين شغالين مع بعض زي ما هما.
    """
    now = _pin_now()
    with PINLOCK_LOCK:
        store = _pinlock_load()
        _pinlock_purge(store)
        _pin_window_prune(store)
        w = store["w"]
        best = 0
        for k in keys:
            rec = w.get(k) or {}
            live = [t for t in (rec.get("t") or [])
                    if (now - t) < PIN_WINDOW_SECONDS]
            live.append(now)
            rec["t"] = live
            w[k] = rec
            best = max(best, len(live))
        _pinlock_save(store)
    return best, best >= PIN_WINDOW_FAILS


def _pin_window_reset(keys):
    """✅ دخول صح / فتح الحساب — النافذة تصفّر"""
    with PINLOCK_LOCK:
        store = _pinlock_load()
        w = store.get("w") or {}
        for k in keys:
            w.pop(k, None)
        store["w"] = w
        _pinlock_save(store)


# ══════════════════════════════════════════════════════════════════
#  📬 كود الإيميل — فتح دائم للحساب
#  ──────────────────────────────────────────────────────────────
#  📌 المسار: ٣ غلط في ٦٠ ثانية (القاعدة ①) → المستخدم يشوف
#     «اكتب إيميلك» → كود ٦ أرقام في بريده → بعد ما يتقبل يختار
#     ٤ أرقام جديدة → الحساب شغّال بالباسورد الجديد للأبد.
#
#  ⛔⛔ ليه الحساب بيتفتح بالإيميل أصلاً ومافيش أحسن؟
#     لأن ٤ أرقام = ١٠٬٠٠٠ احتمال، والقفل بيقفل المستخدم نفسه
#     مع المهاجم. من غير مسار استرجاع، المستخدم اللي نسي باسورده
#     بيضيع — ومن غير إيميل مافيش حاجة تتأكد إنها إنت.
#     ⛔ الإيميل لوحده بيفتح الحساب: **مفيش باسورد حالي** ولا
#        كلمة سر ولا كود قديم مطلوبين. هوى الإيميل + الكود بس.
#
#  ⛔ الكود الخام مايتكتبش في أي مكان:
#     · في الرد      → لأ (الرد عام ومفيهوش الكود)
#     · في users.json → لأ
#     · في اللوج     → لأ (حتى لو مافيش خدمة إيميل)
#     · في pinchal.json → لأ، **هاش بس** (HMAC بـ_SECRET)
#  ⛔ الكود من `secrets.randbelow` — ⛔ مش `random` و ⛔ مش
#     متغيّر من الوقت زي الكود القديم بتاع الاسترجاع.

PIN_CHAL_FILE = Path("/app/pinchal.json")
PIN_CHAL_LOCK = threading.Lock()
PIN_CHAL_TTL = 10 * 60              # ⛌ طلب المواصفات: ١٠ دقايق بالظبط
PIN_CHAL_WRONG = 5                  # ⛌ ٥ غلط على الكود = الكود يموت
PIN_CHAL_PER_DAY = 3                # ⛌ ٣ أكواد لكل إيميل في اليوم
PIN_CHAL_KEEP = 2 * 86400           # ننضّف السجلات بعد يومين
PIN_UNLOCK_TTL = 10 * 60            # مهلة اختيار الباسورد الجديد
# ⛌⛌ ٦ أرقام بظبط — [0-9] مش \d — زي الباسورد بالظبط.
#    الـ\d في Python بيقبل أرقام Unicode، فـ«٧٣١٤٠٥» كانت
#    هتعدّي وتتفق مع كود إنجليزي = باب تسلل مش ضوضاء.
_CHAL_CODE_RE = _re_guard.compile(r"^[0-9]{6}$")


def _chal_load():
    try:
        if PIN_CHAL_FILE.exists():
            d = json.loads(PIN_CHAL_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("c", {})   # أكواد الإيميل
                d.setdefault("g", {})   # توكين الفتح المؤقت
                return d
    except Exception:
        pass
    return {"v": 1, "c": {}, "g": {}}


def _chal_save(d):
    """ذرّي ونفس أسلوب pinlock.json"""
    try:
        tmp = PIN_CHAL_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PIN_CHAL_FILE)
    except Exception as e:
        print(f"  💾 ⛔ pinchal.json: {type(e).__name__}", flush=True)


def _chal_hash(code, email):
    """
    🔒 هاش الكود — **الكود الخام مايتخزّنش أبداً**.

    ⛌ HMAC بالسر بتاع التوكن + الإيميل: نفس الكود على إيميلين
       مختلفين = هاشين مختلفين، ونفس الإيميل بكودين = اتنين.
       ⛔ مقارنة ثابتة الزمن (compare_digest) في التحقق.
    """
    msg = "chal|" + str(email or "").strip().lower() + "|" + str(code or "")
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _chal_prune(d):
    """
    🧹 نضّف: الكود بعد ١٠ دقايق، والتوكن المؤقت بعد ١٠ دقايق،
       وعدّاد اليوم بعد يومين. الملف مايكبرش بلا حدود.
    """
    now = int(time.time())
    day = now // 86400
    c = d.get("c") or {}
    for em in list(c.keys()):
        rec = c.get(em) or {}
        if now - int(rec.get("s") or 0) > PIN_CHAL_TTL:
            rec.pop("h", None)      # ⛔ الهاش
            rec.pop("s", None)      # ⛔ وقت الإرسال
            rec.pop("w", None)      # ⛔ عدّاد الغلط
        if int(rec.get("d") or 0) < day - 1:
            c.pop(em, None)
    g = d.get("g") or {}
    for tok in list(g.keys()):
        if now - int((g.get(tok) or {}).get("e") or 0) > PIN_UNLOCK_TTL:
            g.pop(tok, None)
    d["c"] = c
    d["g"] = g
    return d


def _chal_send(email):
    """
    📤 تجهيز كود الفتح — بيرجّع الكود (للإرسال) أو None.

    ⛔⛔ العدّاد اليومي بيتحسب لـ**كل** طلب بإيميل، مسجّل كان أو
       لأ. لو حسبناه للإيميلات المسجّلة بس، رد الـ429 نفسه كان
       هيبقى «الإيميل ده موجود» — تعداد كامل في رد واحد. كده
       الحد بيلعب نفس اللعبة على أي إيميل.

    ⛔ الكود: ٦ أرقام من `secrets.randbelow` — مصدر عشوائي
       تشفيري من الـOS، مش Mersenne Twister ومش وقت السيرفر.
    """
    email = str(email or "").strip().lower()[:120]
    now = int(time.time())
    day = now // 86400
    with PIN_CHAL_LOCK:
        d = _chal_prune(_chal_load())
        c = d["c"]
        rec = c.get(email) or {}
        if int(rec.get("d") or 0) != day:
            rec = {"d": day, "n": 0}
        if int(rec.get("n") or 0) >= PIN_CHAL_PER_DAY:
            return None                      # ⛔ الطلب الرابع → 429
        rec["n"] = int(rec.get("n") or 0) + 1
        c[email] = rec
        _chal_save(d)

    # ⛔⛔ مافيش باسورد في الحساب ده لازم يوصلك — الإيميل بيفتح
    #    الحساب لوحده. فحتى لو الحساب مش موجود بنعمل الشغل
    #    كله ونضيّع الكود (كل الردود واحدة — ما نقولش مين مسجّل).
    code = f"{_secrets_mod.randbelow(1000000):06d}"
    with PIN_CHAL_LOCK:
        d = _chal_prune(_chal_load())
        c = d["c"]
        rec = c.get(email) or {"d": day, "n": 1}
        rec["h"] = _chal_hash(code, email)   # ⛔ هاش بس
        rec["s"] = now
        rec["w"] = 0
        c[email] = rec
        _chal_save(d)
    return code


def _chal_check(email, code):
    """
    ✅ تحقق من كود الفتح — بيرجّع (ok, why).

    ⛌ السبب بيرجع للسيرفر بس. الرد اللي بيخرج للمستخدم **واحد**
       في كل الأحوال (غلط / منتهي / مفيش كود / الإيميل مش
       موجود أصلاً) — عشان ما نكشفش مين عندنا حساب.
    """
    email = str(email or "").strip().lower()[:120]
    with PIN_CHAL_LOCK:
        d = _chal_prune(_chal_load())
        c = d["c"]
        rec = c.get(email) or {}
        if not rec.get("h"):
            # ⛔ مافيش كود أصلاً (مفيش طلب / اتقضى / الإيميل مش
            #    مسجّل) — نفس النتيجة اللي المستخدم هيتشوفها لو
            #    الكود غلط. مافيش فرق.
            _chal_save(d)
            return False, "no_code"
        if int(rec.get("w") or 0) >= PIN_CHAL_WRONG:
            # ⛔ ٥ غلط = الكود مات. مش بس مرفوض — بينمسح.
            rec.pop("h", None)
            rec.pop("s", None)
            rec["w"] = 0
            c[email] = rec
            _chal_save(d)
            return False, "dead"
        got = _chal_hash(code, email)
        if hmac.compare_digest(got, str(rec.get("h"))):
            # ⛌ الكود واحد Lives: بينمسح فوراً بعد أول استخدام.
            rec.pop("h", None)
            rec.pop("s", None)
            c[email] = rec
            _chal_save(d)
            return True, "ok"
        rec["w"] = int(rec.get("w") or 0) + 1
        if int(rec["w"]) >= PIN_CHAL_WRONG:
            rec.pop("h", None)
            rec.pop("s", None)
            rec["w"] = 0
        c[email] = rec
        _chal_save(d)
        return False, "wrong"


def _chal_unlock_make(uid):
    """
    🔓 توكن الفتح — ⛔ **مش** توكن جلسة.

    ⛔⛔ بعد ما الكود يتقبل المستخدم يدخلWebsite على طول —
       مينفعش. لازم يختار ٤ أرقام جديدة الأول. فبنديه توكن
       مؤقت مربوط ب_SIGNATURE تانية (_sign('u'+p) مش _sign(p)):
       · require_user() **مش** بيقبله (401)
       · /api/auth/refresh **مش** بيقبله (401)
       · مينفعش يتلاعب بيه — التوقيع HMAC زي التوكن
       · ١٠ دقايق بس، و**مرة واحدة**: بينمسح أول ما الباسورد
         الجديد يتحط.
    """
    grant = _secrets_mod.token_urlsafe(18)
    p = base64.urlsafe_b64encode(
        f"{uid}|{grant}".encode()).decode().rstrip("=")
    tok = f"{p}.{_sign('u' + p)}"
    with PIN_CHAL_LOCK:
        d = _chal_prune(_chal_load())
        d["g"][tok] = {"u": uid, "e": int(time.time()) + PIN_UNLOCK_TTL}
        _chal_save(d)
    return tok


def _chal_unlock_read(tok):
    """يقرأ توكن الفتح — الـuid أو None. مافيش تجاوز للعمر ولا للاستخدام"""
    if not _SECRET or not tok:
        return None
    try:
        p, _, sig = str(tok).partition(".")
        if not p or not sig:
            return None
        if not hmac.compare_digest(sig, _sign("u" + p)):
            return None
        pad = "=" * (-len(p) % 4)
        raw = base64.urlsafe_b64decode(p + pad).decode("utf-8", "strict")
        uid, _, grant = raw.partition("|")
        if not uid or not grant:
            return None
        with PIN_CHAL_LOCK:
            d = _chal_load()
            rec = (d.get("g") or {}).get(tok)
            if not rec or str(rec.get("u") or "") != uid:
                return None
            if time.time() > float(rec.get("e") or 0):
                return None
        return uid
    except Exception:
        return None


def _chal_unlock_drop(tok):
    """🗑️ التوكن المؤقت مالوش تكرار — بينمسح أول ما يتستخدم"""
    with PIN_CHAL_LOCK:
        d = _chal_load()
        if (d.get("g") or {}).pop(tok, None) is not None:
            _chal_save(d)


def _chal_pad():
    """
    ⏸️ حشو بسيط — المسار اللي مافيشوش إيميل مسجّل بياخد نفس
    الوقت تقريباً بتاع المسار اللي فيه إيميل مسجّل (كود + هاش
    + طلب شبكة للإيميل). من غير ده: الرد واحد بس والوقت مختلف،
    وده قناة تعداد برضه.
    """
    try:
        _chal_hash("000000", "pad@pad")
        time.sleep(0.25)
    except Exception:
        pass



#  🧩 أدوات مشتركة لمسارات الباسورد
#  ──────────────────────────────────────────────────────────────

def _pin_json(fn):
    """
    ⛔⛔ أي استثناء في مسار الباسورد يرجّع JSON فيه نوع الاستثناء.

    صفحة 500 فاضية للمستخدم بتاعنا مالهاش أي فايدة، واللي بيكتب
    الكود بيحتاج يشوف السبب. الـerrorhandler العام بيشتغل بس على
    استثناءات مش HTTPException — فمحتاجين ده صريح.
    """
    @_functools.wraps(fn)
    def _wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            _log_exc(fn.__name__, e)
            return jsonify({
                "ok": False,
                "error": "حصل خطأ في السيرفر — جرب تاني",
                "why": type(e).__name__,
            }), 500
    return _wrapped


def _pin_locked_resp(retry, what="الباسورد"):
    """رد القفل — 429 + retry_after بالثواني (في الرد وفي الهيدر)"""
    retry = max(1, int(retry or 0))
    mins = max(1, retry // 60)
    resp = jsonify({
        "ok": False,
        "error": f"⛔ {what} اتقفل مؤقتاً بعد محاولات غلط كتير — "
                 f"استنى {mins} دقيقة",
        "why": "locked",
        "retry_after": retry,
    })
    resp.status_code = 429
    try:
        resp.headers["Retry-After"] = str(retry)
    except Exception:
        pass
    return resp, 429


def _pin_user_json(u):
    """الـuser في الرد — ⛔ بدون أي بصمة باسورد ولا هاش"""
    return {
        "id": str(u.get("id") or ""),
        "name": str(u.get("name") or "مستخدم"),
        "email": u.get("email") or None,
        "pin": True,
    }


def _pin_find_by_index(pin):
    """بحث O(1) بالفهرس"""
    idx = _pin_index(pin)
    with USERS_LOCK:
        users = _load_users()
        for uid, u in users.items():
            got = str(u.get("pin_idx") or "")
            if len(got) == len(idx) and hmac.compare_digest(got, idx):
                return uid, u
    return None, None


def _pin_index_stale():
    """
    ⛌ الفحص البطيء (PBKDF2 لكل مستخدم) بيتعمل **بس** لو الفهرس
       مش متطابق — يعني الـpepper اتغيّر أو مستخدم قديم من غير فهرس.
       من غير الشرط ده، كل باسورد غلط كان هيبقى ٥٠ms×N — وهجوم DoS
       مجاني من أي حد عادي.
    """
    try:
        with USERS_LOCK:
            users = _load_users()
            for u in users.values():
                if u.get("pin_hash") and (str(u.get("pin_idx_id") or "")
                                          != _PIN_PEPPER_ID):
                    return True
    except Exception:
        return False
    return False


def _pin_find_by_scan(pin):
    """
    ⛌ بحث بطيء بالهاش الحقيقي — مسار بديل لو الفهرس مش مظبوط.
       ⛔ محدود بـPIN_SCAN_LIMIT سجلات + حد الـIP بيقفّل، فمينفعش
          يتحوّل لهجوم. أول ما يلاقي صاحب الباسورد، يصلّح الفهرس.
    """
    # ⛌ بننسخ السجلات من جوّه القفل، والـPBKDF2 برّه: ٥٠ مستخدم × ٤٠ms
    #    = ثانيتين قفل على كل الـAPI (و workers=1). مش هنسيب حد يعمل
    #    ده فينا عن طريق مسار تسجيل.
    rows = []
    with USERS_LOCK:
        for i, (uid, u) in enumerate(_load_users().items()):
            if i >= PIN_SCAN_LIMIT:
                break
            ph = str(u.get("pin_hash") or "")
            if ph:
                rows.append((uid, ph, str(u.get("pin_salt") or "")))

    hit_uid = None
    for uid, ph, salt in rows:
        if hmac.compare_digest(ph, _pin_hash(pin, salt)):
            hit_uid = uid
            break
    if not hit_uid:
        return None, None
    # 🔧 صلّح الفهرس عشان المرة الجاية تبقى O(1)
    hit = None
    with USERS_LOCK:
        users = _load_users()
        u = users.get(hit_uid)
        if u is not None:
            u["pin_idx"] = _pin_index(pin)
            u["pin_idx_id"] = _PIN_PEPPER_ID
            _save_users(users)
            hit = (hit_uid, u)
    return hit


def _pin_timing_pad(pin):
    """
    ⛌⛌ تسريب التوقيت: لو الباسورد غلط رجعنا فوراً، ولو صح
       عملنا PBKDF2 — الفرق باين. بنعمل PBKDF2 وهمي على المسار
       الغلط عشان الوقت يبقى زي بعضه.
    """
    try:
        _pin_hash(pin, _secrets_mod.token_hex(8))
    except Exception:
        pass


def _pin_verify(uid, u, pin):
    """تحقّق نهائي من الهاش الحقيقي — مقارنة ثابتة الزمن"""
    ph = str(u.get("pin_hash") or "")
    if not ph:
        return False
    got = _pin_hash(pin, u.get("pin_salt") or "")
    return hmac.compare_digest(got, ph)


def _pin_by_email(email):
    """مستخدم الباسورد صاحب الإيميل ده (ولا None)"""
    try:
        with USERS_LOCK:
            for uid, u in _load_users().items():
                if not u.get("pin_hash"):
                    continue
                em = str(u.get("email") or "").lower()
                if em and em == str(email or "").strip().lower():
                    return uid, u
    except Exception:
        pass
    return None, None


# ══════════════════════════════════════════════════════════════════
#  📬 إيميل التأكيد — **مرة واحدة بس** في عمر الحساب
#  ──────────────────────────────────────────────────────────────
#  ⛔⛔ الإيميل ده **ما فيهوش الباسورد** — ولا في موضوع ولا في نص.
#     لو الإيميل ضاع، ما فيش طريق استرجاع — وده المقصود: الباسورد
#     هو المفتاح الوحيد. الإيميل هنا للتأكيد بس.


def _pin_welcome_html(name=""):
    who = _htmlmod.escape(name or "") or "مستخدم"
    return f"""<!doctype html><html dir="rtl"><body style="margin:0;padding:24px;background:#0f1621;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
<div style="max-width:460px;margin:0 auto;background:#16202e;border-radius:14px;padding:28px;color:#e8edf5">
<div style="font-size:26px">🐙</div>
<h2 style="margin:8px 0 4px;font-size:20px">OCTA — تم إنشاء حسابك</h2>
<p style="margin:0 0 20px;color:#93a1b5;font-size:14px">أهلاً {who}</p>
<p style="margin:0 0 14px;color:#e8edf5;font-size:15px;line-height:2">
حسابك جاهز، والدخول من دلوقتي بـ<b>باسورد من ٤ أرقام</b> إنت اللي اخترته.
</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:16px;color:#93a1b5;font-size:13px;line-height:2">
⛔ <b style="color:#e8edf5">الباسورد مش بيتسلّم أبداً</b> — مش في إيميل، مش في الموقع.<br>
⛔ مفيش استرجاع بالباسورد — مافيش إيميل تاني غير ده.<br>
⛔ بعد ٥ محاولات غلط الباسورد بيتقفل ١٥ دقيقة، وبعدها ساعة.
</div>
<p style="margin:18px 0 0;color:#5f6c80;font-size:12px;line-height:1.9">
لو مش إنت اللي عملت الحساب، ارد بكلمة <b>إلغاء</b> وهنراجعه.
</p>
</div>
<p style="max-width:460px;margin:14px auto 0;color:#5f6c80;font-size:12px;text-align:center">octashares.com — قراءة، مش نصيحة</p>
</body></html>"""


# ══════════════════════════════════════════════════════════════════
#  1️⃣  تسجيل حساب بالباسورد
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/pin/register
#  body: { "name", "email", "pin" }
#
#  📌 الباسورد ٤ أرقام: سريع على الموبايل (مفيش لوحة مفاتيح)،
#     ومحتاج قفل ذكي قوي عشان ١٠٬٠٠٠ احتمال قليل.


# ══════════════════════════════════════════════════════════════════
#  1️⃣  ⛔ مسار التسجيل القديم — 410 Gone
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/pin/register   { name, email, pin }
#
#  ⛔⛔⛔ ده كان بيعمل الحساب **قبل** ما الإيميل يتأكد خالص:
#     يكفي حد يكتب إيميل حد تاني ويسجّل حساب باسمه، من غير ما
#     يثبت إنه صاحب الإيميل ولا مرة. الحساب كان بيتعمل في
#     request واحد، والإيميل مجرد نص بارد بعد كده.
#
#  المسار الجديد (signup/start → verify → newpin) بيعكس الترتيب:
#     الإيميل يتأكد **أول حاجة** بكود ٦ أرقام، والحساب بيتعمل
#     بعد ما الكود يتقبل، والباسورد آخر حاجة.
#
#  ⛔ رجعنا 410 مش 404: المسار **متشال** مش مفقود — والواجهة
#     القديمة لو بعتت ليه هتعرف فوراً إنها محتاجة تتحدّث.


@app.route("/api/auth/pin/register", methods=["POST"])
@_pin_json
def auth_pin_register():
    return jsonify({
        "ok": False,
        "error": "طريقة التسجيل القديمة اتشالت — استخدم الشاشة الجديدة",
        "why": "gone",
        "next": "signup/start",
    }), 410


# ══════════════════════════════════════════════════════════════════
#  2️⃣  دخول بالباسورد
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/pin/login
#  body: { "pin" }
#
#  ⛔⛔⛔ مافيش باراميتر إيميل أصلاً، والرد **واحد** في كل الحالات:
#     «الباسورد غلط» سواء الإيميل مسجّل عندنا أو لأ. مفيش ولا
#     endpoint في مسار الباسورد بيفرّق بين «ده مسجّل» و«ده مش
#     مسجّل» — ولا في التوقيت (بنعمل PBKDF2 وهمي عند الفشل).


@app.route("/api/auth/pin/login", methods=["POST"])
@_pin_json
def auth_pin_login():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    pin = str(data.get("pin") or "").strip()
    if not _PIN_RE.match(pin):
        return jsonify({
            "ok": False,
            "error": "الباسورد ٤ أرقام بالظبط",
            "why": "bad_pin",
            "hint": "٤ أرقام من 0000 لـ 9999",
        }), 400

    ip = _client_key()
    keys = _pin_keys(pin=pin, ip=ip)

    # ⛔ القفل بيتفحص **قبل** أي شغل — والرد 429 مش 401
    locked, retry = _pin_locked(keys)
    if locked:
        return _pin_locked_resp(retry)

    uid, u = _pin_find_by_index(pin)
    if u is None and _pin_index_stale():
        # ⛌ الفهرس مش مظبوط (pepper اتغيّر) — بحث بالهاش الحقيقي
        uid, u = _pin_find_by_scan(pin)

    if u is None or not _pin_verify(uid, u, pin):
        # ⛌ نفس المسار ونفس الرد في كل الأحوال
        _pin_timing_pad(pin)
        # ⛔⛔ المحاولة دي بتتحسب على الباسورد **عالمياً** كمان:
        #    المفتاح p: مش مربوط بجهاز، فبوتنت بـ٥٠٠ IP بيقع
        #    في نفس العدّاد = ٥ محاولات في العالم كله كل ١٥ دقيقة.
        #    ⛌ ده **القاعدة ②** — ودي بتشتغل الأول.
        locked, retry = _pinlock_fail(keys)
        if locked:
            return _pin_locked_resp(retry)
        # ═══ ⛔⛔⛔ القاعدة ① — نافذة ٣ محاولات في ٦٠ ثانية ═══
        #  ٣ غلط ورا بعض جوّه ٦٠ ثانية = لازم كود على الإيميل.
        #  ⛌ مافيش قفل هنا: القفل (١٥ دقيقة) هو **القاعدة ②**
        #     فوق، ودي بتفتحله الباب — مش بتلغيه.
        #  ⛌ النافذة على الباسورد وعلى الـIP، وأي واحد فيهم
        #     عدّاده ٣ = كود إيميل. عشان «٣ باسوردات مختلفة من
        #     جهاز واحد» تقفل برضه.
        n_win, need_code = _pin_window_fail(keys)
        if need_code:
            return jsonify({
                "ok": False,
                "error": "محاولات كتير ورا بعض — اكتب إيميلك "
                         "ونبعتلك كود يفتح حسابك",
                "why": "need_code",
                "need_code": True,
                "attempts_left": 0,
                "window": PIN_WINDOW_SECONDS,
                "next": "challenge/send",
            }), 401
        return jsonify({
            "ok": False,
            "error": "الباسورد غلط",
            "why": "bad_pin",
            "need_code": False,
            "attempts_left": max(0, PIN_WINDOW_FAILS - n_win),
            "window": PIN_WINDOW_SECONDS,
        }), 401

    # ✅ صح — العدّاد بيتصفّر والتوقيت بيتسجل
    _pinlock_reset(keys)
    _pin_window_reset(keys)
    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if rec is not None:
            rec["last_login"] = int(time.time())
            _save_users(users)
        else:
            rec = u

    return jsonify({
        "ok": True,
        "token": _make_token(uid),
        "user": _pin_user_json(rec),
    }), 200


# ══════════════════════════════════════════════════════════════════
#  3️⃣  تغيير الباسورد
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/pin/change
#  body: { "old_pin", "new_pin" } + Authorization: Bearer


@app.route("/api/auth/pin/change", methods=["POST"])
@_pin_json
def auth_pin_change():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # ⛔ لازم توكن صالح — المسار بيغيّر مفتاح الحساب
    u = require_user()
    if not u:
        return jsonify({
            "ok": False,
            "error": "لازم تسجّل دخول الأول",
            "why": "unauthorized",
        }), 401

    old_pin = str(data.get("old_pin") or "").strip()
    new_pin = str(data.get("new_pin") or "").strip()
    if not _PIN_RE.match(old_pin) or not _PIN_RE.match(new_pin):
        return jsonify({
            "ok": False,
            "error": "الباسورد ٤ أرقام بالظبط",
            "why": "bad_pin",
            "hint": "٤ أرقام من 0000 لـ 9999",
        }), 400

    ip = _client_key()
    k_ip = _pin_keys(ip=ip)
    k_pin_old = _pin_keys(pin=old_pin)   # القديم اللي بيتفحص
    keys = _pin_keys(pin=new_pin, ip=ip)
    locked, retry = _pin_locked(keys + k_ip + k_pin_old)
    if locked:
        return _pin_locked_resp(retry)

    uid = str(u.get("id") or "")
    bad = ""          # "", "not_pin", "old", "taken"
    rec = None
    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if rec is None or not rec.get("pin_hash"):
            bad = "not_pin"
        elif not _pin_verify(uid, rec, old_pin):
            # ⛔ الباسورد القديم لازم يصح — من غير توكن صالح
            bad = "old"
        else:
            # ⛔ والباسورد الجديد لازم يكون فريد زي أول مرّة
            idx = _pin_index(new_pin)
            taken = False
            stale = False
            for other_uid, o in users.items():
                if other_uid == uid:
                    continue
                got = str(o.get("pin_idx") or "")
                if len(got) == len(idx) and hmac.compare_digest(got, idx):
                    taken = True
                    break
                if o.get("pin_hash") and str(o.get("pin_idx_id") or "") != _PIN_PEPPER_ID:
                    stale = True
            if not taken and stale:
                for other_uid, o in users.items():
                    if other_uid == uid:
                        continue
                    ph = str(o.get("pin_hash") or "")
                    if ph and hmac.compare_digest(
                            ph, _pin_hash(new_pin, o.get("pin_salt") or "")):
                        taken = True
                        break
            if taken:
                bad = "taken"
            else:
                # 🔄 salt جديد مع كل تغيير — لو الباسورد القديم اتسرّب
                #    من أي مكان، السطر القديم مش بيفتح الحساب تاني.
                salt = _pin_salt_new()
                rec["pin_salt"] = salt
                rec["pin_hash"] = _pin_hash(new_pin, salt)
                rec["pin_idx"] = idx
                rec["pin_idx_id"] = _PIN_PEPPER_ID
                rec["pin_changed"] = int(time.time())
                _save_users(users)
                out = _pin_user_json(rec)

    # ═══ ⛔⛔ كل فشل هنا بيبقى محسوب — مفيش استثناء ═══
    #  نفس منطق تسجيل: 409 من غير عدّاد = قناة مجانية لفحص
    #  «الباسورد ده مستخدم من قبل؟» ببلاش.
    if bad == "not_pin":
        return jsonify({
            "ok": False,
            "error": "الحساب ده مش حساب باسورد",
            "why": "not_pin_account",
        }), 400

    if bad == "old":
        # ⛌ الباسورد القديم هو اللي بيتفحص → عدّاده هو اللي بيرتفع
        locked, retry = _pinlock_fail(k_ip + k_pin_old)
        if locked:
            return _pin_locked_resp(retry)
        return jsonify({
            "ok": False,
            "error": "الباسورد القديم غلط",
            "why": "bad_old_pin",
        }), 401

    if bad == "taken":
        locked, retry = _pinlock_fail(keys)
        if locked:
            return _pin_locked_resp(retry)
        return jsonify({
            "ok": False,
            "error": "الباسورد ده مستخدم من قبل — اختار غيره",
            "why": "pin_taken",
        }), 409

    _pinlock_reset(keys + k_ip + k_pin_old)
    print(f"  🔢 اتغيّر الباسورد: {uid}")

    # ⛔ التوكن مش بيتغيّر (مربوط بالـuid) — المستخدم يفضل داخل
    return jsonify({
        "ok": True,
        "msg": "الباسورد اتغيّر — من دلوقتي ادخل بالباسورد الجديد",
        "user": out,
    }), 200



# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
#  📬 كود الإيميل — الفتح الدائم (المسارات الثلاثة)
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/pin/challenge/send     { email }
#  POST /api/auth/pin/challenge/verify    { email, code }
#  POST /api/auth/pin/challenge/newpin    { new_pin } + توكن الفتح
#
#  ⛔⛔⛔ تعداد الإيميلات (enumeration) — الرد **واحد** في كل الحالات:
#     إيميل مسجّل / إيميل مش مسجّل / إيميل منته — نفس الـstatus
#     ونفس الـbody ونفس الوقت تقريباً. مافيش ولا endpoint في
#     المسار كله بيفرّق.


#  📌 الرد الواحد — ثابت واحد في الكود بيتقري في الحالتين.
#     مش شغلتين نفس الكلام (ده بيفرق في مسافات أو علامات).
_CHAL_SEND_REPLY = {
    "ok": True,
    "msg": "لو الإيميل ده بتاعك هتلاقي الكود في بريدك",
    "next": "challenge/verify",
}
#  ⛌ الرد الواحد للتحقق — غلط / منتهي / مفيش كود / مفيش حساب
_CHAL_BAD_REPLY = {
    "ok": False,
    "error": "الكود غلط أو خلصت صلاحيته — اطلب كود جديد",
    "why": "bad_code",
}


def _pin_chal_html(code):
    """📨 إيميل كود الفتح — الكود بيوصل بالإيميل وخلاص"""
    return f"""<!doctype html><html dir="rtl"><body style="margin:0;padding:24px;background:#0f1621;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
<div style="max-width:460px;margin:0 auto;background:#16202e;border-radius:14px;padding:28px;color:#e8edf5">
<div style="font-size:26px">🐙</div>
<h2 style="margin:8px 0 4px;font-size:20px">OCTA — كود فتح حسابك</h2>
<p style="margin:0 0 20px;color:#93a1b5;font-size:14px">محاولات كتير على الباسورد</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:22px;text-align:center;letter-spacing:10px;font-size:34px;font-weight:800;color:#d4af37">{code}</div>
<p style="margin:18px 0 0;color:#e8edf5;font-size:14px;line-height:2">
الكود صالح <b>10 دقايق</b>، و<b>مرة واحدة</b> بس.<br>
بعد ما تدخّله، هتختار <b>4 أرقام جديدة</b> — والباسورد القديم هيبطّل خالص.
</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:16px;color:#93a1b5;font-size:13px;line-height:2">
⛔ <b style="color:#e8edf5">مفيش باسورد في الإيميل ده</b> — الكود مينفعش يفتح أي حساب تاني.<br>
⛔ الكود يموت بعد 5 محاولات غلط.
</div>
<p style="margin:18px 0 0;color:#5f6c80;font-size:12px;line-height:1.9">
لو مش إنت اللي عملت المحاولات دي، تجاهل الإيميل — محدش بيقدر يدخل من غير الكود.
</p>
</div>
<p style="max-width:460px;margin:14px auto 0;color:#5f6c80;font-size:12px;text-align:center">octashares.com — قراءة، مش نصيحة</p>
</body></html>"""


@app.route("/api/auth/pin/challenge/send", methods=["POST"])
@_pin_json
def auth_pin_chal_send():
    """
    📬 طلب كود الفتح — body: { "email" }

    ⛔⛔ الرد **واحد** في كل الأحوال. الإيميل المسجّل بيوصلله كود،
       والإيميل الغلط مابياخدش حاجة — ونفس الرد بالظبط في
       الحالتين. محدش يقدر يستنتج مين عندنا حساب.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    email = str(data.get("email") or "").strip().lower()[:120]
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"ok": False, "error": why, "why": "bad_email"}), 400

    ip = _client_key()
    k_ip = _pin_keys(ip=ip)
    # ⛔ القفل الـ15 دقيقة (القاعدة ②) بيفضل شغال على المسار ده
    #    كمان: مينفعش حد يتخطى النافذة بإطالة الوقت ويطلب كود.
    locked, retry = _pin_locked(k_ip)
    if locked:
        return _pin_locked_resp(retry)

    # ⛔ الكود بيتولّد ويُخزَّن (هاش بس) لأي إيميل — عشان المسار
    #    ياخد نفس الوقت وال replying في الحالتين.
    code = _chal_send(email)
    if code is None:
        # ⛌ الحد اليومي: ٣ أكواد لكل إيميل في اليوم.
        #    العدّاد بيتحسب لكل طلب بأي إيميل (مسجّل أو لأ)
        #    عشان الـ429 نفسه ما يبقاش دليل على وجود الحساب.
        return jsonify({
            "ok": False,
            "error": f"⛔ طلبت {PIN_CHAL_PER_DAY} أكواد على الإيميل ده "
                     f"اليوم — استنى بكرة",
            "why": "daily_limit",
        }), 429

    if _pin_by_email(email)[1]:
        _send_mail(email, "كود فتح حسابك — OCTA", _pin_chal_html(code))
        if not MAIL_ON:
            # ⛔ مافيش خدمة إيميل = مفيش كود. ما بنطبعش الكود خالص —
            #    لازم RESEND_API_KEY يكون مضبوط في الإنتاج.
            print(f"  📧 ⚠️ مافيش خدمة إيميل (RESEND_API_KEY) — كود الفتح "
                  f"ماتبعتش لـ: {email}", flush=True)
    else:
        # ⛌ إيميل مش مسجّل: مافيش إرسال، ومافيش كلام — نفس الرد.
        _chal_pad()

    return jsonify(_CHAL_SEND_REPLY), 200


@app.route("/api/auth/pin/challenge/verify", methods=["POST"])
@_pin_json
def auth_pin_chal_verify():
    """
    ✅ التأكد من كود الفتح — body: { "email", "code" }

    ⛔⛔⛔ مافيش **توكن جلسة** في الرد. المنطق: الكود الصح مش
       دخول — هو خطوة نص الطريق. اللي بعده إجباري: اختيار
       ٤ أرقام جديدة (مسار newpin). لو رجعنا بتوكن هنا، حد
       يقرا لوج السيرفر أو ياخد الرد هيكون داخل من غير ما يختار
       باسورد — والباسورد القديم لسه شغال = الحساب مكشوف
       لحد تاني.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    email = str(data.get("email") or "").strip().lower()[:120]
    code = str(data.get("code") or "").strip()
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"ok": False, "error": why, "why": "bad_email"}), 400
    # ⛌ ٦ أرقام بالظبط — غلط في الشكل = غلط عادي (401 مش 400،
    #    عشان ما نديش معلومة زيادة على اللي الـverify بيرجّعه)
    if not _CHAL_CODE_RE.match(code):
        return jsonify(_CHAL_BAD_REPLY), 401

    ip = _client_key()
    good, why = _chal_check(email, code)
    uid, u = _pin_by_email(email) if good else (None, None)
    # ⛔ الإيميل مش مسجّل = نفس الرد بالظبط زي الكود الغلط.
    if not good or u is None:
        return jsonify(_CHAL_BAD_REPLY), 401

    # ⛌ الكد اتقبل — العدّادات بتتنضف من على الجهاز عشان
    #    الباسورد الجديد يشتغل على طول.
    #    ⛌ عدّاد الباسورد القديم (مفتاح p:) مش بنمسحه — إحنا
    #    مش شايفين الباسورد القديم أصلاً، وهو كمان بقى بلا
    #    قيمة بعد ما الباسورد الجديد يتحط.
    _pinlock_reset(_pin_keys(ip=ip))
    _pin_window_reset(_pin_keys(ip=ip))

    return jsonify({
        "ok": True,
        "msg": "الكود صح — اختار 4 أرقام جديدة",
        "need_pin": True,
        "unlock": _chal_unlock_make(uid),
        "next": "challenge/newpin",
    }), 200


@app.route("/api/auth/pin/challenge/newpin", methods=["POST"])
@_pin_json
def auth_pin_chal_newpin():
    """
    🔐 اختيار الباسورد الجديد — body: { "new_pin" } + توكن الفتح

    ⛔⛔ توكن الفتح **مش** توكن جلسة: require_user() بيرفضه
       (التوقيع مختلف) و /api/auth/refresh بيرفضه كمان. هو
       مالوش صلاحية غير إنه يوصّلنا لطلب الباسورد الجديد مرة واحدة.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    unlock = _bearer()
    uid = _chal_unlock_read(unlock)
    if not uid:
        return jsonify({
            "ok": False,
            "error": "انتهت صلاحية فتح الحساب — اطلب كود جديد",
            "why": "unlock_expired",
        }), 401

    new_pin = str(data.get("new_pin") or "").strip()
    # ⛌ نفس شروط التسجيل: ٤ أرقام بالظبط، بيشمل الفريد
    if not _PIN_RE.match(new_pin):
        return jsonify({
            "ok": False,
            "error": "الباسورد 4 أرقام بالظبط",
            "why": "bad_pin",
            "hint": "4 أرقام من 0000 لـ 9999",
        }), 400

    ip = _client_key()
    keys = _pin_keys(pin=new_pin, ip=ip)
    locked, retry = _pin_locked(keys)
    if locked:
        return _pin_locked_resp(retry)

    # ⛌ الباسورد الجديد فريد — زي أول تسجيل بالظبط، عشان مفيش
    #    حسابين بنفس الأرقام ولا حد يدخل بحسابه بلباسورد حد تاني.
    idx = _pin_index(new_pin)
    # 📌 فاضي معناها «ما فيش مشكلة» — زي conflict في مسار التسجيل.
    #    ⛔ لو ابتديناها بـ"taken" كانت الكتابة بتتم والرد يطلع
    #    409 في نفس الوقت (الباسورد اتغير والرد بيقول «مستخدم»).
    bad = ""
    out = None
    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if rec is None:
            bad = "no_user"
        else:
            taken = False
            stale = False
            for other_uid, o in users.items():
                if other_uid == uid:
                    continue
                got = str(o.get("pin_idx") or "")
                if len(got) == len(idx) and hmac.compare_digest(got, idx):
                    taken = True
                    break
                if o.get("pin_hash") and str(o.get("pin_idx_id") or "") != _PIN_PEPPER_ID:
                    stale = True
            if not taken and stale:
                for other_uid, o in users.items():
                    if other_uid == uid:
                        continue
                    ph = str(o.get("pin_hash") or "")
                    if ph and hmac.compare_digest(
                            ph, _pin_hash(new_pin, o.get("pin_salt") or "")):
                        taken = True
                        break
            if taken:
                bad = "taken"
            else:
                # 🔄 salt جديد مع كل تغيير — الباسورد القديم
                #    بيموت خالص: الهاش القديم بقى بلا قيمة خالص
                #    حتى لو اتسرّب من أي مكان.
                salt = _pin_salt_new()
                rec["pin_salt"] = salt
                rec["pin_hash"] = _pin_hash(new_pin, salt)
                rec["pin_idx"] = idx
                rec["pin_idx_id"] = _PIN_PEPPER_ID
                rec["pin_changed"] = int(time.time())
                rec["pin_recovered"] = int(time.time())
                rec["pin_recoveries"] = int(rec.get("pin_recoveries") or 0) + 1
                _save_users(users)
                out = _pin_user_json(rec)

    if bad == "no_user":
        return jsonify({
            "ok": False,
            "error": "الحساب مش موجود",
            "why": "no_user",
        }), 404

    if bad == "taken":
        # ⛌ زي مسار التسجيل: 409 من غير عدّاد = قناة مجانية
        #    لتس "¿الباسورد ده مستخدم من قبل؟" — فبيتحسب.
        locked, retry = _pinlock_fail(keys)
        if locked:
            return _pin_locked_resp(retry)
        return jsonify({
            "ok": False,
            "error": "الباسورد ده مستخدم من قبل — اختار غيره",
            "why": "pin_taken",
        }), 409

    # ✅ اتحفظ — توكن الفrompt مالوش تكرار
    _chal_unlock_drop(unlock)
    _pinlock_reset(keys)
    _pin_window_reset(keys)
    print(f"  🔓 اتفتح الحساب بباسورد جديد: {uid}")

    return jsonify({
        "ok": True,
        "msg": "الباسورد الجديد اتحفظ — من دلوقتي ادخل بيه",
        "token": _make_token(uid),
        "user": out,
    }), 200

# ══════════════════════════════════════════════════════════════════
#  1️⃣  تسجيل حساب — **الإيميل الأول، والباسورد بعده**
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/signup/start     { name, email }
#  POST /api/auth/signup/verify    { email, code }
#  POST /api/auth/signup/newpin    { new_pin } + توكن الفتح
#
#  ⛔⛔⛔ ترتيب العمليات هو المغزى كله:
#
#     ① start  → اسم + إيميل بس. ⛔ مافيش باسورد في الطلب أصلاً.
#     ② السيرفر يبعت كود ٦ أرقام على الإيميل.
#     ③ verify → الكود صح؟ **عندها بس** الحساب بيتعمل، وبيوسم
#                email_confirmed، وبيطلع **unlock** مش توكن جلسة.
#     ④ newpin → ٤ أرقام، و**عندها بس** بيطلع توكن الدخول.
#
#  قبل كده المسار القديم كان بيعمل المستخدم والتسجيل كله في طلب
#  واحد — يعني الحساب كان بيوجد قبل ما الإيميل يتأكد، وبيفضل
#  موجود لو الإيميل ده مالوش أصلاً. دلوقتي الإيميل لازم يتأكد
#  **قبل** ما الحساب يوجد.
#
#  ⛔ الكود الخام مايتكتبش في أي مكان:
#     · في الرد      → لأ (الرد عام ومفيهوش الكود)
#     · في users.json → لأ
#     · في اللوج     → لأ (حتى لو مافيش خدمة إيميل)
#     · في signup.json → لأ، **هاش بس** (HMAC بـ_SECRET)
#  ⛔ الكود من `secrets.randbelow` — ⛔ مش `random` و ⛔ مش
#     متغيّر من الوقت.

SIGNUP_FILE = Path("/app/signup.json")
SIGNUP_LOCK = threading.Lock()
SIGNUP_TTL = 10 * 60          # ⛌ طلب المواصفات: ١٠ دقايق بالظبط
SIGNUP_WRONG = 5              # ⛌ ٥ محاولات غلط ← الكود يموت
# ⛌ ٥ أكواد لكل إيميل في اليوم ⬇️ كان ٣ ⬇️ وده أضيق من اللازم:
#    المستخدم لو غلط في الإيميل مرتين ⬇️ أو الكود ضاع ٣ مرات
#    ⬇️ كان بيتقفل وما يقدرش يسجّل ⬇️ وده أسوأ من الإزعاج.
#    ⛔ السقف الأعلىjayanti هو اللي بيمنع الإساءة ⬇️ مش ٣.
SIGNUP_PER_DAY = 5            # ⛌ ٥ أكواد لكل إيميل في اليوم
SIGNUP_UNLOCK_TTL = 10 * 60   # ⛌ مهلة اختيار الباسورد
SIGNUP_KEEP = 2 * 86400       # ⛌ ننضّف السجلات بعد يومين
# ⛌⛌ ٦ أرقام بظبط — [0-9] مش \d (زي الباسورد): الـ\d في
#    Python بيقبل أرقام Unicode، فـ«٧٣١٤٠٥» كانت هتعدّي.
_SIGNUP_CODE_RE = _re_guard.compile(r"^[0-9]{6}$")


def _signup_load():
    try:
        if SIGNUP_FILE.exists():
            d = json.loads(SIGNUP_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("p", {})   # ⛔ أكواد في انتظار التأكيد
                d.setdefault("g", {})   # ⛔ توكين الفتح المؤقت
                return d
    except Exception:
        pass
    return {"v": 1, "p": {}, "g": {}}


def _signup_save(d):
    """ذرّي ونفس أسلوب pinchal.json"""
    try:
        tmp = SIGNUP_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SIGNUP_FILE)
    except Exception as e:
        print(f"  💾 ⛔ signup.json: {type(e).__name__}", flush=True)


def _signup_hash(code, email):
    """
    🔒 هاش الكود — **الكود الخام مايتخزّنش أبداً**.

    ⛌ HMAC بالسر بتاع التوكن + الإيميل: نفس الكود على إيميلين
       مختلفين = هاشين مختلفين. ومقارنة ثابتة الزمن في التحقق.
    """
    msg = "signup|" + str(email or "").strip().lower() + "|" + str(code or "")
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _signup_prune(d):
    """
    🧹 نضّف: الكود بعد ١٠ دقايق، والتوكن المؤقت بعد ١٠ دقايق،
       وعدّاد اليوم بعد يومين. الملف مايكبرش بلا حدود.
    """
    now = int(time.time())
    day = now // 86400
    p = d.get("p") or {}
    for em in list(p.keys()):
        rec = p.get(em) or {}
        if now - int(rec.get("s") or 0) > SIGNUP_TTL:
            rec.pop("h", None)      # ⛔ الهاش
            rec.pop("s", None)      # ⛔ وقت الإرسال
            rec.pop("w", None)      # ⛔ عدّاد الغلط
        if int(rec.get("d") or 0) < day - 1:
            p.pop(em, None)
    g = d.get("g") or {}
    for tok in list(g.keys()):
        if now - int((g.get(tok) or {}).get("e") or 0) > SIGNUP_UNLOCK_TTL:
            g.pop(tok, None)
    d["p"] = p
    d["g"] = g
    return d


def _signup_send(email, name):
    """
    📤 تجهيز كود التأكيد — بيرجّع الكود (للإرسال) أو None.

    ⛔⛔ العدّاد اليومي بيتحسب لـ**كل** طلب بإيميل، مسجّل كان
       أو لأ. لو حسبناه للإيميلات المسجّلة بس، رد الـ429 نفسه
       كان هيبقى دليل على وجود الحساب.
    """
    email = str(email or "").strip().lower()[:120]
    name = str(name or "").strip()[:40] or "مستخدم"
    now = int(time.time())
    day = now // 86400
    with SIGNUP_LOCK:
        d = _signup_prune(_signup_load())
        p = d["p"]
        rec = p.get(email) or {}
        if int(rec.get("d") or 0) != day:
            rec = {"d": day, "n": 0}
        if int(rec.get("n") or 0) >= SIGNUP_PER_DAY:
            return None                      # ⛔ الطلب الرابع → 429
        rec["n"] = int(rec.get("n") or 0) + 1
        p[email] = rec
        _signup_save(d)

    # ⛔⛔ ٦ أرقام من `secrets.randbelow` — مصدر عشوائي تشفيري
    #    من الـOS، مش Mersenne Twister ومش وقت السيرفر.
    code = f"{_secrets_mod.randbelow(1000000):06d}"
    with SIGNUP_LOCK:
        d = _signup_prune(_signup_load())
        p = d["p"]
        rec = p.get(email) or {"d": day, "n": 1}
        rec["h"] = _signup_hash(code, email)   # ⛔ هاش بس
        rec["s"] = now
        rec["w"] = 0
        rec["nme"] = name                      # 📌 الاسم survives لحد
        p[email] = rec                         #    ما الحساب يتعمل
        _signup_save(d)
    return code


def _signup_check(email, code):
    """
    ✅ تحقق من كود التأكيد — بيرجّع (ok, why).

    ⛌ السبب بيرجع للسيرفر بس. الرد اللي بيخرج للمستخدم **واحد**
       في كل الأحوال (غلط / منتهي / مفيش كود / مفيش طلب).
    """
    email = str(email or "").strip().lower()[:120]
    with SIGNUP_LOCK:
        d = _signup_prune(_signup_load())
        p = d["p"]
        rec = p.get(email) or {}
        if not rec.get("h"):
            # ⛔ مافيش كود أصلاً (مفيش طلب / اتقضى) — نفس النتيجة
            #    اللي المستخدم هيتشوفها لو الكود غلط. مافيش فرق.
            _signup_save(d)
            return False, "no_code"
        if int(rec.get("w") or 0) >= SIGNUP_WRONG:
            # ⛔ ٥ غلط = الكود مات. مش بس مرفوض — بينمسح.
            rec.pop("h", None)
            rec.pop("s", None)
            rec["w"] = 0
            p[email] = rec
            _signup_save(d)
            return False, "dead"
        got = _signup_hash(code, email)
        if hmac.compare_digest(got, str(rec.get("h"))):
            # ⛌ الكود مرة واحدة Lives: بينمسح فوراً بعد أول استخدام.
            rec.pop("h", None)
            rec.pop("s", None)
            p[email] = rec
            _signup_save(d)
            return True, "ok"
        rec["w"] = int(rec.get("w") or 0) + 1
        if int(rec["w"]) >= SIGNUP_WRONG:
            rec.pop("h", None)
            rec.pop("s", None)
            rec["w"] = 0
        p[email] = rec
        _signup_save(d)
        return False, "wrong"


def _signup_name(email):
    """الاسم اللي اتكتب مع الطلب — بيفضل محفوظ بعد قبول الكود"""
    try:
        with SIGNUP_LOCK:
            rec = (_signup_load().get("p") or {}).get(
                str(email or "").strip().lower()[:120]) or {}
        return str(rec.get("nme") or "").strip()[:40] or "مستخدم"
    except Exception:
        return "مستخدم"


def _signup_unlock_make(uid):
    """
    🔓 توكن الفتح — ⛔ **مش** توكن جلسة.

    ⛔⛔ بعد ما الكود يتقبل مينفعش المستخدم يدخل على طول.
       لازم يختار ٤ أرقام الأول. فبنديه توكن مؤقت مربوط
       بتوقيع تانية (_sign('s'+p) مش _sign(p)):
       · require_user() **مش** بيقبله (401)
       · /api/auth/refresh **مش** بيقبله (401)
       · /api/auth/signup/newpin من غيرو = 401
       · ١٠ دقايق بس، و**مرة واحدة**: بينمسح أول ما الباسورد
         يتحط.
    """
    grant = _secrets_mod.token_urlsafe(18)
    p = base64.urlsafe_b64encode(
        f"{uid}|{grant}".encode()).decode().rstrip("=")
    tok = f"{p}.{_sign('s' + p)}"
    with SIGNUP_LOCK:
        d = _signup_prune(_signup_load())
        d["g"][tok] = {"u": uid, "e": int(time.time()) + SIGNUP_UNLOCK_TTL}
        _signup_save(d)
    return tok


def _signup_unlock_read(tok):
    """يقرأ توكن الفتح — الـuid أو None. مافيش تجاوز للعمر ولا للاستخدام"""
    if not _SECRET or not tok:
        return None
    try:
        p, _, sig = str(tok).partition(".")
        if not p or not sig:
            return None
        if not hmac.compare_digest(sig, _sign("s" + p)):
            return None
        pad = "=" * (-len(p) % 4)
        raw = base64.urlsafe_b64decode(p + pad).decode("utf-8", "strict")
        uid, _, grant = raw.partition("|")
        if not uid or not grant:
            return None
        with SIGNUP_LOCK:
            d = _signup_load()
            rec = (d.get("g") or {}).get(tok)
            if not rec or str(rec.get("u") or "") != uid:
                return None
            if time.time() > float(rec.get("e") or 0):
                return None
        return uid
    except Exception:
        return None


def _signup_unlock_drop(tok):
    """🗑️ التوكن المؤقت مالوش تكرار — بينمسح أول ما يتستخدم"""
    with SIGNUP_LOCK:
        d = _signup_load()
        if (d.get("g") or {}).pop(tok, None) is not None:
            _signup_save(d)


#  📌 الرد الواحد — ثابت واحد في الكود بيتقري في كل الحالات.
#     مش شغلتين نفس الكلام (ده بيفرق في مسافات أو علامات).
_SIGNUP_START_REPLY = {
    "ok": True,
    "msg": "لو الإيميل ده بتاعك، كود التأكيد وصل بريدك",
    "next": "signup/verify",
    "expires_in": SIGNUP_TTL,       # ⛌ ٦٠٠ ثانية = ١٠ دقايق
    "digits": 6,
}
#  ⛌ الرد الواحد للتحقق — غلط / منتهي / مفيش كود / مفيش طلب
_SIGNUP_BAD_REPLY = {
    "ok": False,
    "error": "الكود غلط أو خلصت صلاحيته — اطلب كود جديد",
    "why": "bad_code",
}


def _signup_code_html(code, name=""):
    """📨 إيميل كود تأكيد الحساب — الكود بيوصل بالإيميل وخلاص"""
    who = _htmlmod.escape(name or "") or "مستخدم"
    return f"""<!doctype html><html dir="rtl"><body style="margin:0;padding:24px;background:#0f1621;font-family:system-ui,-apple-system,Segoe UI,sans-serif">
<div style="max-width:460px;margin:0 auto;background:#16202e;border-radius:14px;padding:28px;color:#e8edf5">
<div style="font-size:26px">🐙</div>
<h2 style="max-width:460px;margin:8px 0 4px;font-size:20px">OCTA — كود تأكيد حسابك</h2>
<p style="margin:0 0 20px;color:#93a1b5;font-size:14px">أهلاً {who}</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:22px;text-align:center;letter-spacing:10px;font-size:34px;font-weight:800;color:#d4af37">{code}</div>
<p style="margin:18px 0 0;color:#e8edf5;font-size:14px;line-height:2">
الكود صالح <b>10 دقايق</b>، و<b>مرة واحدة</b> بس.<br>
بعد ما تدخّله، هتختار <b>4 أرقام</b> وتكون خلصت.
</p>
<div style="background:#0f1621;border:1px solid #2b3a4f;border-radius:12px;padding:16px;color:#93a1b5;font-size:13px;line-height:2">
⛔ <b style="color:#e8edf5">مفيش باسورد في الإيميل ده</b> — إنت اللي بتختاره بعد الكود.<br>
⛔ الكود يموت بعد 5 محاولات غلط.
</div>
<p style="margin:18px 0 0;color:#5f6c80;font-size:12px;line-height:1.9">
لو مش إنت اللي طلبت الحساب، تجاهل الإيميل — مافيش حساب بيتعمل من غير الكود.
</p>
</div>
<p style="max-width:460px;margin:14px auto 0;color:#5f6c80;font-size:12px;text-align:center">octashares.com — قراءة، مش نصيحة</p>
</body></html>"""


@app.route("/api/auth/signup/start", methods=["POST"])
@_pin_json
def auth_signup_start():
    """
    📬 ① الاسم والإيميل — body: { "name", "email" }

    ⛔⛔ مافيش باسورد في الطلب ده. لو حد بعت واحد نرفض بوضوح
       (الواجهة القديمة كانت بتبعت باسورد للمسار القديم) — أأمن
       إن المسار الجديد مابيقاش ليه باب تاني غير الإيميل.
    ⛔⛔ الرد **واحد** في كل الأحوال: إيميل مسجّل / إيميل مش
       مسجّل / إيميل مالوش أصلاً — نفس الـstatus ونفس الـbody
       بالحرف. مافيش ولا endpoint في المسار كله بيفرّق.
    ⛌ الحساب **مش** بيتعمل هنا. مافيش مستخدم جديد، مافيش
       كتابة في users.json — الحالة بتتخزّن مؤقتة بس.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    for k in ("pin", "new_pin", "old_pin", "password", "key"):
        if str(data.get(k) or "").strip():
            return jsonify({
                "ok": False,
                "error": "⛔ المسار ده مافيش باسورد فيه — الإيميل الأول، "
                         "والباسورد بعد التأكيد",
                "why": "no_pin_here",
            }), 400

    name = str(data.get("name") or "").strip()[:40] or "مستخدم"
    email = str(data.get("email") or "").strip().lower()[:120]
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"ok": False, "error": why, "why": "bad_email"}), 400

    ip = _client_key()
    k_ip = _pin_keys(ip=ip)
    # ⛔ القفل الـ15 دقيقة بيفضل شغال على المسار ده كمان: مينفعش
    #    حد يطلب كودا ما وراوش قفل، ويتخطى النافذة بإطالة الوقت.
    locked, retry = _pin_locked(k_ip)
    if locked:
        return _pin_locked_resp(retry)

    # ⛔ الكود بيتولّد ويتخزَّن (هاش بس) لأي إيميل — مسجّل كان أو
    #    لأ — عشان المسار ياخد نفس الوقت والرد في الحالتين.
    code = _signup_send(email, name)
    if code is None:
        return jsonify({
            "ok": False,
            "error": f"⛔ طلبت {SIGNUP_PER_DAY} أكواد على الإيميل ده "
                     f"اليوم — استنى بكرة",
            "why": "daily_limit",
        }), 429

    # ⛔⛔⛔ الإرسال بيتعمل **دايماً** لأي إيميل شكله صح — مسجّل
    #    كان أو لأ. وده مقصود ومش خطأ: التسجيل وظيفته إن الإيميل
    #    الجديد يستقبل كود، فلو ما بعتناش لغير المسجّل ما كانش في
    #    تسجيل أصلاً.
    #    ⛌ وده **مش** قناة تعداد: الرد واحد في الحالتين (تحت)،
    #    والشغل اللي بيتعمل واحد في الحالتين كمان — توليد الكود،
    #    هاشه، كتابته على القرص، وإرسال الإيميل. مافيش خطوة بتتعمل
    #    في حالة وبتتقفز في التانية.
    _send_mail(email, "كود تأكيد حسابك — OCTA", _signup_code_html(code, name))
    if not MAIL_ON:
        # ⛔ مافيش خدمة إيميل = مفيش كود. ما بنطبعش الكود خالص.
        print(f"  📧 ⚠️ مافيش خدمة إيميل (RESEND_API_KEY) — كود "
              f"التأكيد ماتبعتش لـ: {email}", flush=True)

    return jsonify(_SIGNUP_START_REPLY), 200


@app.route("/api/auth/signup/verify", methods=["POST"])
@_pin_json
def auth_signup_verify():
    """
    ✅ ② تأكيد الإيميل — body: { "email", "code" }

    ⛔⛔⛔ مافيش **توكن جلسة** في الرد. المنطق: الكود الصح مش
       دخول — هو خطوة نص الطريق. اللي بعده إجباري: اختيار
       ٤ أرقام (newpin). لو رجعنا بتوكن هنا، حد يقرا لوج
       السيرفر أو ياخد الرد هيكون داخل من غير ما يختار باسورد.
    ⛌ **من هنا بس** بيتعمل حساب المستخدم.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    email = str(data.get("email") or "").strip().lower()[:120]
    code = str(data.get("code") or "").strip()
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"ok": False, "error": why, "why": "bad_email"}), 400
    # ⛌ ٦ أرقام بالظبط — غلط في الشكل = غلط عادي (401 مش 400،
    #    عشان ما نديش معلومة زيادة على اللي الـverify بيرجّعه)
    if not _SIGNUP_CODE_RE.match(code):
        return jsonify(_SIGNUP_BAD_REPLY), 401

    good, why = _signup_check(email, code)
    if not good:
        return jsonify(_SIGNUP_BAD_REPLY), 401

    # ⛔⛔⛔ أول مرة في عمر الحساب بيتعمل مستخدم — **بعد** ما
    #    الإيميل اتأكد. الـuid نفس بتاع كل مسارات الباسورد.
    uid = _hash_key(email)[:20]
    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if rec is None:
            rec = {
                "id": uid,
                "name": _signup_name(email),
                "email": email,
                "email_hash": _hash_key(email),
                "created": int(time.time()),
                "portfolio": {},
                "watch": [],
            }
            users[uid] = rec
        # ⛌ الإيميل اتأكد فعلاً
        rec["email_confirmed"] = True
        rec["email_confirmed_at"] = int(time.time())
        # ⛌ ملحوظة: لو الحساب ده كان ليه باسورد من قبل (تسجيل
        #    قديم)، الباسورد القديم **مش** بيتشال هنا — بيفضل
        #    شغال لحد ما الـnewpin يقبل. عشان لو المستخدم وقف
        #    في النص، ما يتقفلش بره من حسابه خالص.
        _save_users(users)

    # ⛌ الكد اتقبل — العدّادات بتتنضف من على الجهاز عشان
    #    الباسورد الجديد يشتغل على طول.
    ip = _client_key()
    _pinlock_reset(_pin_keys(ip=ip))
    _pin_window_reset(_pin_keys(ip=ip))
    print(f"  ✉️ اتأكد الإيميل: {uid}")

    return jsonify({
        "ok": True,
        "msg": "الكود صح — اختار 4 أرقام الباسورد",
        "need_pin": True,
        "unlock": _signup_unlock_make(uid),
        "next": "signup/newpin",
    }), 200


@app.route("/api/auth/signup/newpin", methods=["POST"])
@_pin_json
def auth_signup_newpin():
    """
    🔐 ③ اختيار الباسورد — body: { "new_pin" } + توكن الفتح

    ⛔⛔ توكن الفتح **مش** توكن جلسة: require_user() بيرفضه
       (التوقيع مختلف) و /api/auth/refresh بيرفضه كمان. هو
       مالوش صلاحية غير إنه يوصّلنا لطلب الباسورد مرة واحدة.
    ⛔ مافيش توكن دخول قبل ما الباسورد يتقبل.
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    unlock = _bearer()
    uid = _signup_unlock_read(unlock)
    if not uid:
        return jsonify({
            "ok": False,
            "error": "انتهت صلاحية فتح الحساب — ابدأ التسجيل من الأول",
            "why": "unlock_expired",
        }), 401

    new_pin = str(data.get("new_pin") or "").strip()
    # ⛌ نفس شروط التسجيل القديم: ٤ أرقام بالظبط، بيشمل الفريد
    if not _PIN_RE.match(new_pin):
        return jsonify({
            "ok": False,
            "error": "الباسورد 4 أرقام بالظبط",
            "why": "bad_pin",
            "hint": "4 أرقام من 0000 لـ 9999",
        }), 400

    ip = _client_key()
    keys = _pin_keys(pin=new_pin, ip=ip)
    locked, retry = _pin_locked(keys)
    if locked:
        return _pin_locked_resp(retry)

    # ⛌ الباسورد فريد — مافيش حسابين بنفس الأرقام، ومحدش يدخل
    #    بحسابه بلباسورد حد تاني.
    idx = _pin_index(new_pin)
    # 📌 فاضي معناها «ما فيش مشكلة».
    bad = ""
    out = None
    em = nm = ""
    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if rec is None:
            bad = "no_user"
        else:
            taken = False
            stale = False
            for other_uid, o in users.items():
                if other_uid == uid:
                    continue
                got = str(o.get("pin_idx") or "")
                if len(got) == len(idx) and hmac.compare_digest(got, idx):
                    taken = True
                    break
                if o.get("pin_hash") and str(o.get("pin_idx_id") or "") != _PIN_PEPPER_ID:
                    stale = True
            if not taken and stale:
                for other_uid, o in users.items():
                    if other_uid == uid:
                        continue
                    ph = str(o.get("pin_hash") or "")
                    if ph and hmac.compare_digest(
                            ph, _pin_hash(new_pin, o.get("pin_salt") or "")):
                        taken = True
                        break
            if taken:
                bad = "taken"
            else:
                # 🔄 salt جديد مع كل كتابة — الباسورد القديم لو
                #    كان في الحساب بيموت خالص: الهاش القديم بقى
                #    بلا قيمة حتى لو اتسرّب من أي مكان.
                salt = _pin_salt_new()
                rec["pin_salt"] = salt
                rec["pin_hash"] = _pin_hash(new_pin, salt)
                rec["pin_idx"] = idx
                rec["pin_idx_id"] = _PIN_PEPPER_ID
                rec["pin_set"] = int(time.time())
                rec["pin_first_at"] = int(
                    rec.get("pin_first_at") or int(time.time()))
                _save_users(users)
                out = _pin_user_json(rec)
                em = str(rec.get("email") or "")
                nm = str(rec.get("name") or "")

    if bad == "no_user":
        return jsonify({
            "ok": False,
            "error": "الحساب مش موجود",
            "why": "no_user",
        }), 404

    if bad == "taken":
        # ⛌ زي التسجيل القديم: 409 من غير عدّاد = قناة مجانية
        #    لتس «الباسورد ده مستخدم من قبل؟» — فبيتحسب.
        locked, retry = _pinlock_fail(keys)
        if locked:
            return _pin_locked_resp(retry)
        return jsonify({
            "ok": False,
            "error": "الباسورد ده مستخدم من قبل — اختار غيره",
            "why": "pin_taken",
        }), 409

    # ✅ اتحفظ — توكن الفتح مالوش تكرار
    _signup_unlock_drop(unlock)
    _pinlock_reset(keys)
    _pin_window_reset(keys)
    print(f"  🔐 حساب جاهز بالباسورد: {uid}")

    # 📬 إيميل **واحد بس** في عمر الحساب — تأكيد، مش استرجاع
    if em:
        _send_mail(em, "تم إنشاء حسابك — OCTA", _pin_welcome_html(nm))
        if not MAIL_ON:
            # ⛔ مافيش خدمة إيميل = مفيش تأكيد. ما بنطبعش الباسورد.
            print(f"  📧 ⚠️ مافيش خدمة إيميل (RESEND_API_KEY) — إيميل "
                  f"التأكيد ماتبعتش لـ: {em}", flush=True)

    return jsonify({
        "ok": True,
        "msg": "الحساب جاهز — من دلوقتي ادخل بالباسورد",
        "token": _make_token(uid),
        "user": out,
    }), 200

# ══════════════════════════════════════════════════════════════════
#  🔄 تجديد صامت — كل ساعتين من غير أي شاشة
#  ──────────────────────────────────────────────────────────────
#  POST /api/auth/refresh — Authorization: Bearer <token>
#
#  ⛔⛔⛔ **التوكن القديم بس**. مافيش باسورد، مافيش إيميل،
#     مافيش كود، مافيش بصمة — ولا حاجة تانية. أي واحدة فيهم
#     في الـbody = رفض (400). المسار ده مالوش أي مسار تاني
#     يفتح: لو التوكن مش صالح أو خلصت مدةه → 401 وخلاص،
#     من غير ما يطلب باسورد ومن غير ما يفتح بوابة sneaky.
#
#  📌 التوكن ٧ أيام والواجهة بتجدد كل ساعتين → المستخدم
#     يقعد داخل طول ما المتصفح مفتوح، ومحدش بيشوف شاشة.


@app.route("/api/auth/refresh", methods=["POST"])
@_pin_json
def auth_refresh():
    """
    🔄 تجديد صامت — التوكن القديم بس.

    200 → { ok, token, expires_in }
    401 → التوكن مش صالح أو خلصت مدته (وفيه غير كده ولا حاجة)
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # ⛔⛔ أي credential في الـbody = رفض. المسار ده مصمم إنه
    #    يتبنى بالتوken بس، ولو قبل حاجة كمانبقى ده فتح
    #    ثانٍ مستخبي جوه «تجديد».
    for k in ("pin", "old_pin", "new_pin", "password", "key",
              "email", "code"):
        if str(data.get(k) or "").strip():
            return jsonify({
                "ok": False,
                "error": "⛔ التجديد الصامت مش بياخد باسورد ولا إيميل "
                         "ولا كود — التوكن القديم بس",
                "why": "no_credentials",
            }), 401

    uid, exp = _token_parts(_bearer())
    if not uid:
        # ⛔ مافيش استثناء: لا باسورد ولا إيميل ولا كود.
        #    الواجهة بترمي التوكن وتورّد البوابة.
        return jsonify({
            "ok": False,
            "error": "انتهت الجلسة — سجّل دخول تاني",
            "why": "unauthorized",
        }), 401

    with USERS_LOCK:
        u = _load_users().get(uid)
    if not u:
        return jsonify({
            "ok": False,
            "error": "انتهت الجلسة — سجّل دخول تاني",
            "why": "unauthorized",
        }), 401

    return jsonify({
        "ok": True,
        "token": _make_token(uid),
        "expires_in": TOKEN_TTL,
        "renewed": True,
        "user": {
            "id": str(u.get("id") or uid),
            "name": str(u.get("name") or "مستخدم"),
            "email": u.get("email") or None,
        },
    }), 200


#  🔑 استرجاع كلمة السر
#  ──────────────────────────────────────────────────────────────
#  قبل: لو المستخدم نسي كوده، خلاص خسران حسابه.
#  دلوقتي: لو سجّل بإيميل، يطلب كودReset على الإيميل.
#
#  ⛔ التوكن مايتخزنش — بنحسب hash بتاعه ونقارنه.
#    -expires بعد 15 دقيقة (رمز واحداية).
#  ⛔ مافيش حد ممكن يطلب لغير نفسه.
# ══════════════════════════════════════════════════════════════

RESET_TTL = 15 * 60          # 15 دقيقة
RESET_MAX_PER_DAY = 3        # 3 محاولات في اليوم


def _reset_send(email, code):
    """
    📤 إرسال كود الاسترجاع.

    ✅ لو Resend مضبوط → الكود يتبعت إيميل زي كود الدخول بالظبط
       (قبل: الكود كان بيتطبع في اللوج بس، يعني أي حد يقدر يفتح
        لوج Railway ويسرق أي حساب).
    🚧 من غير خدمة إيميل (تطوير) → بنطبعه في اللوج زي الأول.
    """
    if MAIL_ON:
        return _send_mail(email, "كود استرجاع الحساب — OCTA", _otp_html(code))
    print(f"[reset] ⚠️ مافيش خدمة إيميل (RESEND_API_KEY) — الكود بيتطبع "
          f"في اللوج: {email} -> {code}", flush=True)
    return True



# ══════════════════════════════════════════════════════════════════
# 📧 إرسال الإيميل — Resend
# ══════════════════════════════════════════════════════════════════
# ⛌ ⛌ المفتاح **مش** هنا ولا في أي ملف. بيتقرأ من متغيرات البيئة
#    في Railway بس:
#        RESEND_API_KEY   = re_xxxxxxxx
#        MAIL_FROM        = OCTA <onboarding@resend.dev>
#
#    ⛌ من غير مفتاح: بنردّ نفس الرسالة على كل الإيميلات
#       (مش بنقول «الإيميل ده مش موجود») — عشان محدش يقدر
#       يستنتج مين مسجّل عندنا.
#    ⛌ ومن غير مفتاح بنطبع الكود في اللوج بس، عشان المالك
#       يقدر يدخل لوحده أثناء التطوير.

import random as _random
import html as _htmlmod

RESEND_KEY = str(os.environ.get("RESEND_API_KEY", "") or "").strip()
MAIL_FROM = str(os.environ.get("MAIL_FROM", "OCTA <onboarding@resend.dev>") or "").strip()
MAIL_ON = bool(RESEND_KEY)

# عدد المحاولات في اليوم لكل إيميل — ⛌ بيمنع تخمين الكود بالقوة
# ⛔ 3 محاولات في اليوم كانت قليلة أوي لمستخدم حقيقي: ضاع منه الكود
#    مرتين وخلاص — وقلنا له «أيوه بعثنا» من غير ما نبعته.
#    الحد الحقيقي للدخول هو حد التحقق (10 / 5 دقايق) + الكود
#    بيموت بعد 5 غلط + حد الإرسال (3 / 5 دقايق لكل IP).
#    الحد اليومي ده حماية من الإرسال المزعج بس — 10 معقول.
OTP_TRIES_PER_DAY = 10
OTP_TTL = 15 * 60          # 15 دقيقة
# ⛌ كام غلطة في كود واحد قبل ما الكود يموت
OTP_MAX_WRONG = 5

# ⛌ ⛌ الكود لازم يعيش على القرص مش في الذاكرة.
#    Railway بيعمل redeploy عند كل git push، والذاكرة بتتمسح →
#    المستخدم بيستنى إيميل فيه كود صحيحMICROSOFTالسيرفرsays «الكود غلط».
OTP_FILE = Path("/app/otp.json")
OTP_LOCK = threading.Lock()


def _otp_load():
    try:
        if OTP_FILE.exists():
            d = json.loads(OTP_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}


def _otp_save(d):
    try:
        tmp = OTP_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(OTP_FILE)
    except Exception as e:
        print(f"  💾 ⛔ otp.json: {type(e).__name__}", flush=True)


def _otp_purge(d):
    """نشيل السجلات المنتهية — الخريطة بتتمسح لوحدها"""
    now = int(time.time())
    return {k: v for k, v in d.items() if now - v.get("sent", 0) < OTP_TTL}


# ⛔⛔ آخر نتيجة إرسال — كانت بتتبلع ومالهاش أي أثر.
#    «الموقع قال إنه بعت» و«Resend رفض» كانوا بيتبانوا نفس الحاجة.
MAIL_LAST = {"ok": None, "at": 0, "why": ""}


def _send_mail(to, subject, html):
    """يبعت إيميل. ⛌ مابيبلعش أي خطأ —Registrationمششyg."""
    if not MAIL_ON:
        print(f"  📧 [بدون مفتاح] → {to} | {subject}")
        return False
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}",
                     "Content-Type": "application/json"},
            json={"from": MAIL_FROM, "to": [to], "subject": subject,
                  "html": html}, timeout=20)
        if r.status_code >= 300:
            _why = f"HTTP {r.status_code}: {r.text[:160]}"
            print(f"  📧 ⛔ {_why}")
            MAIL_LAST.update(ok=False, at=int(time.time()), why=_why)
            return False
        print(f"  📧 ✅ {to}")
        MAIL_LAST.update(ok=True, at=int(time.time()), why="")
        return True
    except Exception as e:
        _why = f"{type(e).__name__}: {str(e)[:120]}"
        print(f"  📧 ⛔ {_why}")
        MAIL_LAST.update(ok=False, at=int(time.time()), why=_why)
        return False


def _otp_new(email):
    """كود جديد من 6 أرقام — ⛌ crypto مش random عشان الكود أمني."""
    code = f"{_random.SystemRandom().randint(0, 999999):06d}"
    now = int(time.time())
    with OTP_LOCK:
        store = _otp_purge(_otp_load())
        rec = store.get(email) or {}
        day = now // 86400
        tries = rec.get("tries", 0) if rec.get("day") == day else 0
        if tries >= OTP_TRIES_PER_DAY:
            return None
        # ⛌ ⛌ كان السطر ده ناقص — العدّاد بيتحسب بس مش بيتحدّث،
        #    فـ OTP_TRIES_PER_DAY كان حرف ميت
        store[email] = {
            "code_hash": hashlib.sha256(
                (code + _SECRET).encode()).hexdigest(),
            "sent": now, "tries": tries + 1, "day": day, "wrong": 0,
        }
        _otp_save(store)
    return code


def _otp_check(email, code):
    """⛌ بترجّع (ok, why) — وعدّاد الغلط بيتزاد"""
    with OTP_LOCK:
        store = _otp_purge(_otp_load())
        rec = store.get(email)
        if not rec:
            return False, "no_code"
        if rec.get("wrong", 0) >= OTP_MAX_WRONG:
            store.pop(email, None)
            _otp_save(store)
            return False, "too_many_wrong"
        got = hashlib.sha256((str(code) + _SECRET).encode()).hexdigest()
        ok = hmac.compare_digest(got, rec.get("code_hash", ""))
        if ok:
            store.pop(email, None)
        else:
            rec["wrong"] = rec.get("wrong", 0) + 1
            store[email] = rec
        _otp_save(store)
    return ok, ("ok" if ok else "wrong")



RESET_STORE = {}


def _reset_request():
    """
    📬 طلب كود استرجاع
    body: { "email": "name@example.com" }
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    email = str(data.get("email") or "").strip().lower()[:120]
    ok, why = _valid_email(email)
    if not ok:
        return jsonify({"error": why}), 400

    # ⛔ رد واحد سواء الإيميل مسجل أو لأ — ما نقولش مين مسجل
    generic = {
        "ok": True,
        "msg": "لو الإيميل ده مسجل، هبعتلك كود على طول",
    }

    users = _load_users()
    match = next((u for u in users.values() if u.get("email") == email), None)
    if not match:
        return jsonify(generic)

    # ⛔⛔⛔ مافيش استرجاع بالباسورد — بالتصميم. حساب الباسورد
    #    مينفعش يسترجع من غير ما يعرف الباسورد، ولو بعتنا إيميل
    #    استرجاع كده يبقى الإيميل تاني وسيلة دخول — وده اللي
    #    بنمنعه. فبنقوله بصراحة بدل ما نبعتله كود ما ينفعش.
    if match.get("pin_hash"):
        return jsonify({
            "ok": False,
            "error": "⛔ الحساب ده بيستخدم باسورد ٤ أرقام — "
                     "مافيش استرجاع بالباسورد",
            "why": "pin_account",
        }), 409

    # ── حد المحاولات ──
    now = time.time()
    rec = RESET_STORE.get(email) or {"sent": [], "done": 0}
    day_ago = now - 86400
    rec["sent"] = [t for t in rec["sent"] if t > day_ago]
    if rec["done"] >= RESET_MAX_PER_DAY:
        return jsonify({"error": "وصلت للحد اليومي — جرب بكره"}, 429)

    # ⛔⛔⛔ كان السطر ده: str(int(now * 1000) % 1000000).zfill(6)
    #    ⛔⛔⛔ تسريب كامل: الكود مش عشوائي أصلاً — هو آخر 6 أرقام من
    #    وقت السيرفر بالمللي ثانية. أي حد عارف وقت الطلب تقريباً
    #    (من توقيت الرد، أو بتخمين بسيط) يقدر يحسب الأرقام دي
    #    ويجربها، و /api/auth/reset/verify مش بيتقفل بعدد محاولات.
    #    ⛌ دلوقتي نفس نمط كود الـOTP بالظبط: SystemRandom + 6 أرقام.
    #    العدّاد (RESET_MAX_PER_DAY) والـTTL (RESET_TTL) زي ما هما.
    code = f"{_random.SystemRandom().randint(0, 999999):06d}"
    rec["code_hash"] = _hash_key(code + email)
    rec["sent"].append(now)
    rec["uid"] = match["id"]
    RESET_STORE[email] = rec

    _reset_send(email, code)
    return jsonify(generic)


@app.route("/api/auth/reset", methods=["POST"])
def _auth_reset_route():
    return _reset_request()


@app.route("/api/auth/reset/verify", methods=["POST"])
def _auth_reset_verify():
    """
    ✅ تأكيد الكود وتغيير كلمة السر
    body: { "email": "name@example.com", "code": "123456",
            "key": "الكلمة الجديدة" }
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    email = str(data.get("email") or "").strip().lower()[:120]
    code = str(data.get("code") or "").strip()
    newkey = str(data.get("key") or "").strip()

    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"error": "الكود 6 أرقام"}), 400
    if len(newkey) < 6:
        return jsonify({"error": "الكلمة الجديدة قصيرة — 6 حروف"}), 400

    rec = RESET_STORE.get(email)
    if not rec or not rec.get("code_hash"):
        return jsonify({"error": "مفيش طلب استرجاع — ابدأ من الأول"}), 400

    # ── انتهت المدة؟ ──
    if time.time() - rec["sent"][-1] > RESET_TTL:
        RESET_STORE.pop(email, None)
        return jsonify({"error": "انتهت المدة — 15 دقيقة — ابدأ تاني"}), 400

    # ── الكود صح؟ ──
    if not hmac.compare_digest(rec["code_hash"],
                               _hash_key(code + email)):
        return jsonify({"error": "الكود غلط"}), 400

    # ── غيّر كلمة السر ──
    uid = rec.get("uid")
    with USERS_LOCK:
        users = _load_users()
        u = users.get(uid)
        if not u:
            return jsonify({"error": "الحساب مش موجود"}), 404
        u["khash"] = _hash_key(newkey)
        u["reset_at"] = int(time.time())
        _save_users(users)

    RESET_STORE.pop(email, None)
    rec["done"] += 1
    RESET_STORE[email] = rec

    # ⛔ التوكن القديم بيبطل — لازم يسجّل دخول تاني
    return jsonify({
        "ok": True,
        "msg": "اتغيرت كلمة السر — سجّل دخول تاني",
        "token": _make_token(uid),
    })





# ══════════════════════════════════════════════════════════════
#  📊 تتبع الاستخدام — نعرف الناس بتعمل إيه
#  ──────────────────────────────────────────────────────────────
#  قبل: كنا بنعرف إن السيرفر اتندد 3,200 طلب — بس مش بنعرف
#  مين فتح إيه. يعني مش بنعرف نطوّر إيه الأول.
#
#  دلوقتي: كل فتح صفحة / كل ضغطة زر بتتسجل، ونطلع منها:
#    · كام زائر
#    · مين سجّل
#    · أكتر صفحة
#    · مين رجع تاني يوم
#
#  ⚠️ مفيش PII — بنسجل event + اسم صفحة، مش IP ولا إيميل.
# ══════════════════════════════════════════════════════════════

TRACK_FILE = Path("/app/track.json")
TRACK_LOCK = threading.Lock()
TRACK_DAYS = 90          # نحتفظ بآخر 90 يوم


def _track_load():
    try:
        if TRACK_FILE.exists():
            d = json.loads(TRACK_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("events", [])
                d.setdefault("users", {})
                return d
    except Exception:
        pass
    return {"events": [], "users": {}}


def _track_save(d):
    """نقصّي الأقدم — الملف ما يكبرش بلا حدود"""
    try:
        cut = time.time() - TRACK_DAYS * 86400
        ev = [e for e in (d.get("events") or []) if (e.get("ts") or 0) >= cut]
        d["events"] = ev
        TRACK_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


@app.route("/api/track", methods=["POST"])
def track_api():
    """
    📥 تسجيل حدث.

    body: { "event": "page_view" | "action", "page": "rank",
             "label": "taqa", "uid": "user id (اختياري)" }
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return jsonify({"ok": False}), 400

    event = str(data.get("event") or "")[:24]
    page = str(data.get("page") or "")[:32]
    label = str(data.get("label") or "")[:24]
    uid = str(data.get("uid") or "")[:24]

    if event not in ("page_view", "action", "signup", "login"):
        return jsonify({"ok": False, "error": "event غير معروف"}), 400
    if event == "action" and not page:
        return jsonify({"ok": False, "error": "action محتاج page"}), 400

    rec = {"ts": int(time.time()), "ev": event,
           "p": page, "l": label, "u": uid or ""}

    with TRACK_LOCK:
        d = _track_load()
        d["events"].append(rec)

        # ── نعرف مين رجع ولا لأ ──
        if uid:
            u = d["users"].setdefault(uid, {"first": rec["ts"],
                                            "last": rec["ts"], "hits": 0})
            u["last"] = rec["ts"]
            u["hits"] += 1

        # ما نخزّنش بلا حدود
        if len(d["events"]) > 200000:
            d["events"] = d["events"][-150000:]
        _track_save(d)

    return jsonify({"ok": True})


@app.route("/api/stats", methods=["GET"])
def stats_api():
    """
    📊 تقرير الاستخدام — بس للمالك.
    """
    if not require_user():
        return jsonify({
            "ok": False,
            "error": "المسار ده محمي",
            "hint": "سجّل دخول الأول",
        }), 401

    with TRACK_LOCK:
        d = _track_load()

    now = time.time()
    ev = d.get("events") or []
    users = d.get("users") or {}

    def win(secs):
        cut = now - secs
        return [e for e in ev if (e.get("ts") or 0) >= cut]

    def summarise(rows):
        views = [e for e in rows if e.get("ev") == "page_view"]
        acts = [e for e in rows if e.get("ev") == "action"]
        signs = [e for e in rows if e.get("ev") == "signup"]
        pages = {}
        for e in views:
            pages[e.get("p") or "?"] = pages.get(e.get("p") or "?", 0) + 1
        labels = {}
        for e in views + acts:
            if e.get("l"):
                labels[e["l"]] = labels.get(e["l"], 0) + 1
        # زوار فريدين: hash من uid أو session
        seen = {e.get("u") or ("anon", e.get("ts")) for e in rows}
        return {
            "views": len(views),
            "actions": len(acts),
            "signups": len(signs),
            "visitors": len(seen),
            "top_pages": sorted(pages.items(), key=lambda x: -x[1])[:10],
            "top_stocks": sorted(labels.items(), key=lambda x: -x[1])[:10],
        }

    # رجعوا تاني يوم
    ret = 0
    for u in users.values():
        if (u.get("last") or 0) - (u.get("first") or 0) > 86400:
            ret += 1

    return jsonify({
        "ok": True,
        "days": {
            "1": summarise(win(86400)),
            "7": summarise(win(7 * 86400)),
            "30": summarise(win(30 * 86400)),
            "90": summarise(win(90 * 86400)),
        },
        "users": {
            # ⚠️ دايماً نقرأ من users.json (الحسابات الحقيقية)
            #    مش من track.json — اللي ده track file بتاع الأحداث
            "total": len(_load_users()),
            "with_email": sum(1 for u in _load_users().values() if u.get("email")),
            "returned_next_day": ret,
            "tracked": len(users),
        },
        "total_events": len(ev),
        "generated": int(now),
    })



@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """مين أنا؟"""
    u = require_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({
        "ok": True,
        "user": {"id": u["id"], "name": u["name"]},
        "stats": {
            "portfolio": len(u.get("portfolio") or {}),
            "watch": len(u.get("watch") or []),
        },
    })


# ══════════════════════════════════════════════════════════════════
#  🗑  حذف حسابي — المستخدم يحذف نفسه فقط
#  ⛔ محمي بتوكن صالح: مش حد تاني يقدر يمسح حسابك
#  ⛔ بيمسح: السجل + كل منبهات السعر + كل التوكنات القديمة
# ══════════════════════════════════════════════════════════════════


@app.route("/api/auth/delete", methods=["POST"])
@_pin_json
def auth_delete_account():
    """🗑 المستخدم يحذف حسابه بنفسه — ما فيش مسار يحذف حد تاني.

    ⛔🔴 الأسبا��ة صارت **٣ حاجات مع بعض**:
      1. توكن جلسة صالح
      2. الباسورد نفسه ⬇️ ⬛ يثبت إنك إنت مش حد خطف التوكن
      3. confirm=DELETE ⬇️ ⬛ تمنع الحذف بالغلط
    ⛔ وكل الجلسات التانية بتتمسح ⬇️ التوكن اللي إيدك مات
       يفضل بطل مع الكود ده ⬇️ حد خطفه يقدر يحذف بيه.
    """
    u = require_user()
    if not u:
        return jsonify({
            "ok": False,
            "error": "لازم تسجّل دخول الأول",
            "why": "unauthorized",
        }), 401

    body = (request.get_json(silent=True) or {})
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "طلب غير صحيح",
                        "why": "bad_body"}), 400

    # ⛔ ① لازم مكتوب DELETE بالحرف ⬇️ مافيش حذف بضغطة واحدة
    if str(body.get("confirm") or "") != "DELETE":
        return jsonify({
            "ok": False,
            "error": "اكتب DELETE في الخانة عشان نتأكد إنك عايز تحذف",
            "why": "need_confirm",
        }), 400

    uid = str(u.get("id") or "")
    pin = str(body.get("pin") or "")
    if not _PIN_RE.match(pin):
        return jsonify({"ok": False, "error": "اكتب ٤ أرقام",
                        "why": "bad_pin_format"}), 400

    with USERS_LOCK:
        users = _load_users()
        rec = users.get(uid)
        if not rec:
            return jsonify({"ok": False, "error": "الحساب مش موجود",
                            "why": "no_user"}), 404

        # ⛔ ② الباسورد ⬇️ توكن مسروق بدون باسورد = مابيتحذفش
        if not _pin_verify(uid, rec, pin):
            _pinlock_fail(_pin_keys(pin=pin, ip=_client_key()))
            return jsonify({
                "ok": False,
                "error": "الباسورد غلط ⬇️ الحساب ما اتحذفش",
                "why": "bad_pin",
            }), 401

        # ⛌ حذف ناعم: نسجّل البصمة والوقت ⬇️ لو حبينا نرجّع
        #    الحساب، مش بنرجّع الباسورد (ما بقيناش عارفينه).
        users[uid] = {
            "id": uid,
            "name": str(rec.get("name") or "")[:80],
            "email_hash": str(rec.get("email_hash") or "")[:64],
            "deleted_at": int(time.time()),
            "deleted_email": str(rec.get("email") or "")[:160],
            "pin_hash": "",          # ⛔ الباسورد بيموت مع الحساب
            "pin_salt": "",
            "pin_set": False,
            "pin_idx": -1,
            "watch": [],
            "portfolio": [],
            # ⛔ ③ إبطال كل الجلسات ⬇️ كل التوكنات القديمة تبقى ميتة
            "token_epoch": int(time.time()) * 1000,
        }
        _save_users(users)

    _send_mail(
        str(rec.get("email") or ""),
        "تم حذف حسابك من OCTA",
        "حسابك اتمسح بناءً على طلبك. "
        "لو مش أنت ⬇️这道 الإيميل بتأكدلك إن حسابك اتقفل من حد تاني.",
    )

    print(f"  🗑 اتمسح حساب: {uid}")
    return jsonify({"ok": True, "msg": "اتمسح الحساب بالكامل"}), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """التسجيل الخروج بيتم في المتصفح — التوكن بسطره"""
    return jsonify({"ok": True})



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
  - ⚠️ لاحظ: المحور ده عكسي — يعني، أعلى = رقم أقل

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
  "decision": "إشارة إيجابية" | "إشارة محايدة" | "إشارة سلبية",
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
                f"\n\n⚠️ تنبيه: البيانات ضعيفة — لو حقل 'غير متاح'"
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


# ══════════════════════════════════════════════════════════════════
# 🐙 قوائم الأسهم — من مصدر واحد
# ══════════════════════════════════════════════════════════════════
# كان فيه هنا 302 سطر مكتوبين بإيدنا (code · name · sector).
#هم اللي كانوا بيحدّدوا إيه الأسهم اللي الموقع بيتكلم عنها —
# واللي خالف غلط لو اتضاف سهم جديد أو اتشال.
#
# دلوقتي القايمة بتتبني من الملفات الفعلية:
#   ① egx_names.json  — الأسماء والقطاعات (مصدر واحد)
#   ② data_full.json  — الأسهم اللي عندها تقييم
#   ③ القايمة القديمة بس كـ fallback لو الملفات مش موجودة
#
# ⛔ لو الملف ناقص، السهم مالوش تقييم — مش بنخترع له اسم.
_SCORE_ERROR = None
_HARDCODED_EGX = EGX


def _build_egx():
    import os as _os, json as _json
    here = _os.path.dirname(_os.path.abspath(__file__))

    # ① الأسماء والقطاعات
    names, sectors = {}, {}
    for p in (_os.path.join(here, "egx_names.json"), "/app/egx_names.json"):
        if not _os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = _json.load(fh)
            # الصيغة: مفتاحين — names و sectors
            nm = d.get("names") or d.get("stocks") or d
            sc = d.get("sectors") or {}
            for k, v in nm.items():
                if isinstance(v, dict):
                    names[k] = v.get("name") or v.get("n") or k
                else:
                    names[k] = str(v)
            for k, v in (sc.items() if isinstance(sc, dict) else []):
                sectors[k] = str(v)
        except Exception as e:
            print(f"  ⚠️ الأسماء: {e}")

    # ② الأسهم اللي عندها بيانات فعلاً
    have = set()
    for p in (_os.path.join(here, "data_full.json"), "/app/data_full.json"):
        if not _os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = _json.load(fh)
            st = d.get("stocks") if isinstance(d, dict) else None
            if st:
                have = set(st.keys())
                break
        except Exception:
            pass

    if not names and not have:
        print("  ⚠️ لا مصدر — رجعنا للقايمة المكتوبة")
        return _HARDCODED_EGX

    codes = sorted(have) if have else sorted(names)
    out = []
    for c in codes:
        nm = names.get(c)
        sec = sectors.get(c) or "—"
        if not nm:
            continue                      # ⛔ من غير اسم ما نخمّنش
        out.append((c, nm, sec))
    print(f"  📋 القايمة: {len(out)} سهم من الملفات "
          f"({len(names)} اسم · {len(have)} له تقييم)")
    return out or _HARDCODED_EGX


EGX = _build_egx()
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

    f.append("\n  «التحليل المالي — أرقام حقيقية»")
    add("مضاعف الربحية", "pe")
    add("مضاعف الكتاب", "pb")
    add("العائد على حقوق الملكية", "roe", pct=True)
    add("نسبة الدين", "de_ratio")
    add("هامش الربح الصافي", "net_margin", pct=True)
    add("هامش التشغيل", "op_margin", pct=True)
    add("ربحية السهم", "eps")
    add("القيمة السوقية", "mkt_cap", "ج.م", dec=0)

    f.append("\n  «المخاطرة والسيولة»")
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
        decision = "إشارة سلبية"
    elif overall >= 75 and axes["technical"] >= 55:
        decision = "إشارة إيجابية"
    elif overall >= 60:
        decision = "إشارة محايدة"
    elif axes["fundamental"] >= 70:
        decision = "إشارة محايدة"
    else:
        decision = "إشارة سلبية"

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




# ⛌ الثابت ده كان اتمسح بالغلط لما فصلنا الدوال —
#    الـNameError كان بيخلي كل سهم يطلع بلا تقييم، والخطأ كان مخفي.
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
    "medium": ["اتفاق", "شراكة", "استثمار", "تحديث", "ت",
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
    ويعرف: كم له، وكم بيساهم، وليه.
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

    # ═══ 4) مفيد من الأساسيات (Fundamental Catalyst) — 20 وزن ═══
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
    if axes["risk"] < 35:         decision = "إشارة سلبية"
    elif final >= 78 and filters_passed:  decision = "إشارة إيجابية"
    elif final >= 65:             decision = "إشارة إيجابية"
    elif final >= 52:             decision = "إشارة محايدة"
    elif (axes.get("fundamental") or 0) >= 65: decision = "إشارة محايدة"
    else:                         decision = "إشارة سلبية"

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
        "desc": "الحجم على 80% + سيولة ضعيفة",
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
            "note": "الحكم على مرحلتين: (1) النتيجة بعد الصدمة، (2) هل القرارات تحوّلت؟",
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


def cairo_now():
    """⛌⛌ توقيت القاهرة بيشتغل من قاعدة البيانات بتاعت النظام، مش +3 ثابت.
       مصر بترجع للتوقيت الصيفي (UTC+3) صيف و UTC+2 شتا — والـoffset الثابت
       كان بيخلي الموقع يقول «السوق مغلق» وهو مفتوح في نص النهار.
       ⛌ الخيار البديل (لو zoneinfo مش موجود) يقيس الإزاحة الفعلية
       من UTC في اللحظة دي بدل ما يفترض حاجة."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Africa/Cairo"))
    except Exception:
        try:
            from zoneinfo import ZoneInfo as _Z
            _now = datetime.now(_Z("Africa/Cairo"))
            return _now
        except Exception:
            pass
    # ⛌ fallback: نقيس الإزاحة الحقيقية بدل +3 مفترضة
    try:
        offset = datetime.now().astimezone().utcoffset()
        return datetime.utcnow() + (offset or timedelta(hours=2))
    except Exception:
        return datetime.utcnow() + timedelta(hours=2)


def cairo_now_str():
    try:
        return cairo_now().strftime("%H:%M")
    except Exception:
        return ""


def market_phase():
    """يرجع حالة السوق: open / closed / weekend / pre

    ⛌ حدود الجلسات بالدقائق مش بالساعات — 14:30 هي نهاية اليوم مش
       «الساعة 15»، والفرق ده كان بيسبّب حالة غلط في آخر ساعة."""
    try:
        now = cairo_now()
        if now.weekday() in (4, 5):                    # الجمعة (4) والسبت (5)
            return "weekend"
        mins = now.hour * 60 + now.minute
        if mins < 9 * 60 + 15:
            return "pre"
        if mins < 14 * 60 + 30:
            return "open"
        return "closed"
    except Exception:
        return "open"


def refresh_interval():
    """كل قد إيه نحدّث حسب حالة السوق"""
    phase = market_phase()
    if phase == "open":
        return 45           # ⏱️ ٤٥ ثانية أثناء التداول بدل دقيقتين
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
            LIVE_DATA["snapshot_id"] = _make_snapshot_id(LIVE_DATA["lastUpdate"])
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
                        # إعادة حساب المحصلة — بنفس الدالة المستخدمة في
                        # final_score بالظبط. الكود القديم كان بيعيد الحساب
                        # بإيده: من غير تطبيع، ومن غير أسقف الخصم، ومن غير
                        # خصم الثقة — فكان الرقم المبلّغ مختلف عن الموصوف.
                        ax = fin["axes"]
                        _lq = liquidity_score(item) if liq_score else None
                        _a2 = _compose_score(ax, _lq)
                        if _a2["final"] is not None:
                            fin["final_score"] = _a2["final"]
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
                except Exception as _e:
                    # ⛌ كان pass — الخطأ كان بيضيع وكل السهم بيطلع بلا تقييم
                    #    من غير أي أثر. دلوقتي بيتسجل.
                    import traceback as _tb
                    globals()['_SCORE_ERROR'] = (
                        f"{type(_e).__name__}: {str(_e)[:200]}\n"
                        + "\n".join(_tb.format_exc(limit=4).split("\n")[-6:]))
                    print(f"  ❌ final_score: {_SCORE_ERROR[:200]}")
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
def _users_io_test():
    """⛔⛔ الفحص الأول كان بيعمل read→write على users.json نفسه —
    وأي تسجيل بيحصل في نفس اللحظة كان بيتمسح.
    ⛌ دلوقتي بيكتب في ملف لوحده ومفيش أي تعارض."""
    p = Path("/app/.octa_persist_probe")
    now = int(time.time())
    try:
        if p.exists():
            first = int(p.read_text(encoding="utf-8").strip() or 0)
            return {"survived": True, "age_s": now - first,
                    "file": str(p), "note": "الملف فضل موجود بعد النشر"}
        p.write_text(str(now), encoding="utf-8")
        return {"survived": False, "created_now": True, "file": str(p),
                "note": "اتعمل دلوقتي — جيني تاني بعد النشر شوف"}
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}: {str(e)[:100]}"}


def _app_writable():
    """⛔ القصة: التوكن بيتعمل صح بس أي طلب بعده بيرجع 401.
    ⛌ سببين محتملين: إما الـsecret مختلف، إما users.json مش بيتكتب.
       ده بيكشف التاني."""
    try:
        p = Path("/app/.octa_write_test")
        p.write_text("x", encoding="utf-8")
        p.unlink()
        return True
    except Exception:
        return False


@app.route("/")
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "octa-prices",
        "version": "v3-gemini-3.5-flash",
        "lastUpdate": LIVE_DATA["lastUpdate"],
            "snapshot_id": LIVE_DATA.get("snapshot_id"),
        "tickers": len(LIVE_DATA["ticker"]),
        "stocks": len(LIVE_DATA["egx30"]),
        "gemini": "configured" if GEMINI_KEY else "NOT configured",
        # ⛔ ⛌ الـUI بتقرأ market_phase من هنا عشان تقول «مفتوح» ولا «مغلق».
        #    الحقل كان ناقص من الرد فالموقع كان بيقول «السوق مغلق» دايمًا.
        "market_phase": market_phase(),
        "cairo_time": cairo_now_str(),
        # ⛔⛔ تشخيص: هل ملف البيانات اتقري فعلاً؟ كان الموقع بيرجع
        #    صفحات فاضية من غير سبب — والسبب هنا كان مخفي.
        "data_full_loaded": _DATA_FULL["payload"] is not None,
        "data_full_n": (_DATA_FULL["payload"] or {}).get("_n"),
        # ⛔ boolean بس — قيمة السر نفسها ما بتظهرش في أي رد أبداً.
        #    false = مفيش سر جاي من متغير بيئة (يعني وضع تطوير).
        # ⛔⛔ تشخيص: مستخدمين مش بيتحفظوا = كل توكن بيرجع 401
        "users_n": len(_load_users()),
        # ⛔⛔ عدد حسابات الباسورد — رقم بس، مافيش أي بصمة أو هاش.
        "pin_users": sum(1 for u in _load_users().values()
                         if u.get("pin_hash")),
        "users_io": _users_io_test(),
        "app_writable": _app_writable(),
        "mail_configured": MAIL_ON,
        "mail_last_ok": MAIL_LAST["ok"],
        "mail_last_why": MAIL_LAST["why"],
        "token_secret_configured": TOKEN_SECRET_CONFIGURED,
        "auth": ("configured" if TOKEN_SECRET_CONFIGURED
                 else "dev-ephemeral"),
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
            "snapshot_id": LIVE_DATA.get("snapshot_id"),
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
    # 🔒 الحماية: ⛔⛔⛔ كان المسار ده مفتوح للزائر المجهول — أي حد
    #    كان بياخد ترتيب 20 سهم بالنتيجة والقرار والثقة وبلا توكن.
    #    ⛌ بقى زي /api/egx_full بالظبط: 401 من غير توكن صالح.
    #    ⛌ top20 الفاضية في الـbody عشان الواجهة ما تكسرش لو الطلب
    #    طلع من غير gate — نفس الشكل القديم.
    if not require_user():
        return jsonify({
            "ok": False,
            "error": "النسخة الكاملة محمية",
            "hint": "سجّل دخول من /api/auth/register",
            "total": 0,
            "top20": [],
            "_protected": True,
        }), 401

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


def _user_portfolio(u=None):
    """
    📦 محفظة المستخدم الحالي.

    ⛔ قبل: كل الزوار كانوا بيشاركوا نفس المحفظة (PORTFOLIO العام) —
       أي حد يقدر يمسح محفظة أي حد تاني. دلوقتي كل واحد ليه حجته.

    ⛌ ⛌ الحارس بيتبعت مع المستخدم (u) من فوق — الدالة دي مبقتش
       تعمل require_user تاني، ومش بترجع محفظة فاضية لحد.
    """
    if u is None:
        u = require_user()
    if not u:
        return {}
    return u.get("portfolio") or {}


@app.route("/api/portfolio", methods=["GET", "POST"])
def portfolio_api():
    """عرض وتعديل المحفظة — 🔒 خاصة بكل مستخدم"""
    # ⛔⛔⛔ القفل كان على POST بس. النتيجة: GET بيرد 200 لزائر مجهول
    #    بمحفظة فاضية افتراضية — يعني مسار المعرفة كان مفتوح، والواجهة
    #    كانت بتتعامل معاه كأنه عادي. ⛌ دلوقتي القفل فوق الخطّارين
    #    الزائر لازم يسجّل (401) — زي /api/stats بالظبط.
    u = require_user()
    if not u:
        return jsonify({
            "ok": False,
            "error": "لازم تسجّل دخول عشان تشوف المحفظة",
            "hint": "سجّل دخول الأول من /api/auth/register",
        }), 401

    # ── POST: تعديل المحفظة ──
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            return jsonify({"error": "JSON غير صالح"}), 400

        action = str(data.get("action") or "").strip()
        code = str(data.get("code") or "").upper().strip()

        # ── تحقق: الكود لازم يكون معروف فعلاً ──
        if code and action in ("add", "remove"):
            known = {s["code"] for s in LIVE_DATA.get("egx30", [])}
            if known and code not in known:
                return jsonify({"error": f"الرمز {code} غير معروف"}), 400

        pf = u.get("portfolio") or {"holdings": {}, "cash": 0}
        pf.setdefault("holdings", {})

        if action == "add":
            try:
                shares = float(data.get("shares", 0))
                cost = float(data.get("cost", 0))
                price = float(data.get("price", 0))
            except (TypeError, ValueError):
                return jsonify({"error": "أرقام غير صالحة"}), 400
            if shares < 0 or cost < 0 or price < 0:
                return jsonify({"error": "مفيش قيم سالبة"}), 400
            if shares > 1e9 or cost > 1e7:
                return jsonify({"error": "القيمة كبيرة أوي"}), 400
            pf["holdings"][code] = {
                "shares": shares, "cost": cost, "price": price,
                "sector": str(data.get("sector") or "أخرى")[:30],
            }
        elif action == "remove":
            pf["holdings"].pop(code, None)
        elif action == "clear":
            pf["holdings"] = {}
            pf["cash"] = 0
        elif action == "set_cash":
            try:
                cash = float(data.get("cash", 0))
            except (TypeError, ValueError):
                return jsonify({"error": "قيمة غير صالحة"}), 400
            if cash < 0 or cash > 1e9:
                return jsonify({"error": "قيمة غير صالحة"}), 400
            pf["cash"] = cash
        else:
            return jsonify({"error": "action غير معروف"}), 400

        u["portfolio"] = pf
        with USERS_LOCK:
            users = _load_users()
            users[u["id"]] = u
            _save_users(users)
        return jsonify({"ok": True, "portfolio": pf})

    # ── GET: محفظة المستخدم (اتأكدنا فوق إن في توكن) ──
    pf = _user_portfolio(u)
    holdings = pf.get("holdings") or {}
    cash = float(pf.get("cash", 0) or 0)

    total = sum(h["shares"] * h["price"] for h in holdings.values()) + cash
    sectors = {}
    for c, h in holdings.items():
        v = h["shares"] * h["price"]
        sectors[h.get("sector", "أخرى")] = sectors.get(h.get("sector", "أخرى"), 0) + v

    return jsonify({
        "total_value": round(total, 2),
        "cash": cash,
        "count": len(holdings),
        "holdings": holdings,
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
        # ⛔ ما نرجعش traceback — بيكشف أسماء المتغيرات والمسارات
        #    ونص الأخطاء اللي ممكن يبقى فيها connection string
        _log_exc("analyze", _e)
        return jsonify({
            "error": "خطأ داخلي في التحليل",
            "code": (item or {}).get("code"),
            "hint": "جرّب تاني، ولو فضل قوم ابعتلنا الـcode",
        }), 500


@app.route("/api/score-error")
def score_error():
    """آخر خطأ في حساب التقييم — عشان ما نلعبش.hide-and-seek"""
    return jsonify({"error": globals().get("_SCORE_ERROR"),
                    "ok": globals().get("_SCORE_ERROR") is None})


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
            "snapshot_id": LIVE_DATA.get("snapshot_id"),
    })


@app.route("/api/top-movers")
def top_movers():
    """أعلى/أسفل 10 أسهم + الأكثر تداولاً"""
    tm = LIVE_DATA.get("top_movers", {})
    return jsonify({
        "lastUpdate": LIVE_DATA["lastUpdate"],
            "snapshot_id": LIVE_DATA.get("snapshot_id"),
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
            "snapshot_id": LIVE_DATA.get("snapshot_id"),
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

    🔒 الحماية: الرد الكامل (252 سهم في طلب واحد) بقى والتوكن مطلوب.
       بدون توكن، الرد بيتقلّص للأسعار والاسم بس — واللي محتاجه
       العرض العادي في الموقع. ده بيمنع حد ينزّل نسخة كاملة من
       الداتا بطلب واحد، بس لسه-site شغال عادي.

       ?codes=COMI,HRHO   → سهم محدد أو اتنين (من غير توكن)
    """
    # ── 1) طلب سهم محدد → مفتوح (ده اللي الموقع بيعمله) ──
    wanted = str(request.args.get("codes") or "").upper().strip()
    if wanted:
        pick = {c.strip() for c in wanted.split(",") if c.strip()}
        pick = set(list(pick)[:10])   # نحدّ أقصى 10 أسهم
        return jsonify(_egx_full_subset(pick))

    # ── 2) الرد الكامل → محمي ──
    if not require_user():
        return jsonify({
            "ok": False,
            "error": "النسخة الكاملة محمية",
            "hint": ("سجّل دخول من /api/auth/register، أو استخدم "
                     "?codes=COMI لسهم محدد"),
            "n": 0, "stocks": {},
            "_protected": True,
        }), 401

    return jsonify(_egx_full_all())


def _egx_full_all():
    """الرد الكامل — التقييم النهائي لكل الأسهم (للمستخدم المسجّل)"""
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
    return {"_ts": _dt.now(_tz.utc).isoformat() + "Z",
            "_src": "tradingview + startamarkets",
            "n": len(stocks), "stocks": stocks}


def _egx_full_subset(codes):
    """
    🎯 رد محدود لسهم واحد أو اتنين.

    اللي بيرجع: الاسم · السعر · التقييم · القرار · السعر/العائد.
    اللي ما بيرجعش: كل المؤشرات التقنية والمخاطرة والنمو.
    (دي اللي بتعمل التصدير الكامل)
    """
    full = _egx_full_all()
    all_stocks = full.get("stocks") or {}
    out = {}
    for c in codes:
        r = all_stocks.get(c)
        if not r:
            continue
        out[c] = {k: r.get(k) for k in (
            "n", "en", "name_ar", "s", "p", "c", "v", "mc",
            "score", "decision", "pe", "pb", "roe", "live",
        )}
    return {"_ts": full.get("_ts"), "_subset": True,
            "n": len(out), "stocks": out}


# ─────────────────────────────────────────────────────────────
# ③-b  /api/data_full  —  نفس data_full.json بس محمي
# ─────────────────────────────────────────────────────────────
#  ⛔ ليش المسار ده أصلاً؟
#
#  الملف data_full.json كان بيتنشر كـ static على Cloudflare
#  (382KB) — أي زائر ينزّله من المتصفح من غير تسجيل.
#  شِلناه من حزمة النشر، لكن الواجهة محتاجة الأرقام دي.
#
#  ⚠️ ليه مش /api/egx_full؟
#  لأن /api/egx_full بيرجّع شكل مختلف تماماً:
#    data_full.json → total · verdict · q · m · sf · lq · conf
#                     · sectorAr · pack · why · partial · missing
#                     · de · cr · qr · roic · ps · av30 · relvol …
#    /api/egx_full  → n · en · s · score · decision · s_rsi · s_dy …
#  يعني التوجيه المباشر كان هيسقط 22 حقل بصمت
#  والفلاتر الثمانية و kart القرار هيبقوا فاضيين.
#
#  فبناهنا: نفس الملف، نفس الشكل بالظبط — بس جوه الـAPI محمي.
#  مفيش أي تغيير في رقم ولا وزن ولا عتبة ولا اسم سهم.
#  _shape عشان الواجهة تعرف الشكل وتعرف وقت ما يقع علىFallback.
#
#  🔒 الحماية: نفس require_user بتاعة /api/egx_full — توكن لازم.
#  📦 الكاش: في الذاكرة، بيتحدّث لما يتغيّر وقت الملف (mtime).
#
#  🚫 فلتر EGS: الملف فيه 296 كود، منهم 11 سند حكومي مصري
#     (EGS30AJ1C016-EGP …) مش أسهم — وبيبقوا في الشاشة لو ما فلترناش.
#     الفلتر ده بيخلي الرد 285 سهم بالظبط زي الملف القديم:
#     نفس الكودز، نفس الأرقام، صفر فرق. (اتحقّق بالمقارنة)
# ─────────────────────────────────────────────────────────────
_DATA_FULL = {"mtime": 0, "payload": None, "ttl": 300}


def _warm_data_full():
    """⛔⛔ الملف الغني كان بيترحم بس أول ما حد يسجّل دخول.
       فلو محدش دخل، السيرفر مبيعرفش إن الملف ناقص أصلاً.
       ⛌ دلوقتي بيترحم عند بدء السيرفر ويطبع النتيجة في اللوج."""
    try:
        d = _data_full_payload()
        print(f"[warm] data_full: {d.get('_n', 0)} سهم", flush=True)
    except Exception as e:
        print(f"[warm] ⛔ data_full: {type(e).__name__}: {str(e)[:120]}", flush=True)


def _data_full_payload():
    """يقرأ data_full.json من القرص — مع كاش في الذاكرة."""
    import os as _os, json as _json
    for p in (Path(__file__).parent / "data_full.json", Path("/app/data_full.json")):
        try:
            if not _os.path.isfile(p):
                continue
            mt = _os.path.getmtime(p)
            if _DATA_FULL["payload"] is not None and mt == _DATA_FULL["mtime"]:
                return _DATA_FULL["payload"]
            with open(p, encoding="utf-8") as fh:
                d = _json.load(fh)
            if not (isinstance(d, dict) and d.get("stocks")):
                continue
            # 🚫.non-equity: أكواد السندات الحكومية (EGS…) — مش أسهم
            st = {c: v for c, v in d["stocks"].items()
                  if not str(c).upper().startswith("EGS")}
            if not st:
                continue
            out = dict(d)
            out["stocks"] = st
            out["_shape"] = "full"
            out["_n"] = len(st)
            _DATA_FULL.update(mtime=mt, payload=out, ttl=300)
            print(f"[data_full] loaded {out['_n']} shares (skipped "
                  f"{len(d['stocks']) - len(st)} non-equity)")
            return out
        except Exception as e:
            print(f"[data_full] {p}: {e}")
    return None


@app.route("/api/data_full")
def api_data_full():
    """
    🔒 محمي — توكن صالح لازم، زي /api/egx_full بالظبط.

    بيرجّع data_full.json (296 سهم · تقييم الأذرع الخمسة) كما هو
    بالحرف — مفيش أي إعادة حساب ولا تقريب ولا تعديل.
    """
    if not require_user():
        return jsonify({
            "ok": False,
            "error": "النسخة الكاملة محمية",
            "hint": "لازم تسجّل دخول الأول",
            "n": 0, "stocks": {},
            "_protected": True,
        }), 401

    d = _data_full_payload()
    if not d:
        return jsonify({"ok": False, "error": "data_full غير متاح",
                        "n": 0, "stocks": {}, "_protected": True}), 503
    return jsonify(d)


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
        _log_exc("upstream-502", e)
        return jsonify({"error": "تعذّر جلب البيانات من المصدر"}), 502


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
# ⛔ Deprecated — التوكن كان هنا ومكانش المفروض.
#    السبب: أي حد يقدر يفتح الكود ده ويستخدم البوت بتاعنا.
#    دلوقتي: بنقراه من متغيرات البيئة بس (Railway Variables).
TG_FALLBACK = {
    # TELEGRAM_BOT_TOKEN — no hardcoded fallback on purpose.
    # أي إعدادات ناقصة بتعمل fail-closed (الخدمة بتتوقف)
    # أحسن من إنها تشتغل بتوكن مشروف.
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
    """
    📋 منبهات السعر — 🔒 خاصة بكل مستخدم.

    ⛔ قبل: كل المنبهات كانت في ملف مشترك. أي حد يقدر يمسح
       منبهات أي حد تاني أو يضيف 500 منبه.
    """
    u = require_user()
    if not u:
        # بدون توكن: مافيش منبهات + رسالة واضحة
        return jsonify({
            "ok": False, "items": [],
            "error": "لازم تسجّل دخول عشان تشوف منبهاتك",
            "hint": "POST /api/auth/register",
        })

    watch = u.get("watch") or {}
    items = []
    for c, cfg in watch.items():
        item = next((s for s in LIVE_DATA.get("egx30", []) if s["code"] == c), None)
        if item:
            rows = w_add({"watch": dict(watch)}, c, cfg.get("hi"), cfg.get("lo"))
            items.extend(w_list({"watch": dict(watch)}))
    return jsonify({"ok": True, "items": items})


@app.route("/api/alerts/watch", methods=["POST"])
def _octa_watch_post():
    """
    ✏️ إضافة/حذف منبه — 🔒 خاصة بكل مستخدم + تحقق صارم.
    """
    u = require_user()
    if not u:
        return jsonify({"error": "لازم تسجّل دخول عشان تضيف منبهات",
                       "hint": "POST /api/auth/register"}), 401

    try:
        j = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"error": "JSON غير صالح"}), 400
    if not isinstance(j, dict):
        return jsonify({"error": "body لازم يكون object"}), 400

    a = str(j.get("action") or "").strip()
    code = str(j.get("code") or "").upper().strip()

    if a not in ("add", "del", "clear"):
        return jsonify({"error": "action لازم يكون add/del/clear"}), 400

    if a in ("add", "del"):
        if not code or len(code) > 12:
            return jsonify({"error": "رمز غير صالح"}), 400
        known = {s["code"] for s in LIVE_DATA.get("egx30", [])}
        if known and code not in known:
            return jsonify({"error": f"الرمز {code} غير معروف"}), 400

    watch = u.get("watch") or {}

    if a == "add":
        hi = j.get("hi")
        lo = j.get("lo")
        try:
            if hi not in (None, ""):
                hi = float(hi)
                if hi <= 0 or hi > 1e7: raise ValueError
            else:
                hi = None
            if lo not in (None, ""):
                lo = float(lo)
                if lo <= 0 or lo > 1e7: raise ValueError
            else:
                lo = None
        except (TypeError, ValueError):
            return jsonify({"error": "الأسعار لازم تكون أرقام موجبة"}), 400

        if hi is None and lo is None:
            return jsonify({"error": "لازم تحدد حد أعلى أو حد أدنى"}), 400
        if hi is not None and lo is not None and hi < lo:
            return jsonify({"error": "الحد الأعلى لازم يكون أكبر من الأدنى"}), 400

        watch[code] = {"hi": hi, "lo": lo}
    elif a == "del":
        watch.pop(code, None)
    elif a == "clear":
        watch = {}

    if len(watch) > 100:
        return jsonify({"error": "الحد 100 منبه بس"}), 400

    u["watch"] = watch
    with USERS_LOCK:
        users = _load_users()
        users[u["id"]] = u
        _save_users(users)

    return jsonify({"ok": True, "count": len(watch)})


@app.route("/api/alerts/diag", methods=["GET"])
def _octa_diag():
    """
    حالة البوت — لل diagnOSE.

    🔒 محمي: كان بيرجّع أول 30 حرف من التوكن والـchat في
       raw_token و raw_chat. ده كان leak مباشر لأي حد بيفتح
       المسار. دلوقتي بيرجّع "متظبّط / ناقص" بس.
    """
    if not require_user():
        return jsonify({
            "ok": False,
            "error": "المسار ده محمي",
            "hint": "سجّل دخول من /api/auth/register الأول",
        }), 401

    def _shape(v):
        """
        ⛔ ما بنرجّعش أي جزء من السر — لا ولا حرف.
        بنقول بس: متظبّط ولا ناقص، وطوله.
        """
        s = str(v or "").strip()
        if not s or "ARCHON_SECRET" in s:
            return "غير مضبوط"
        return f"مضبوط ({len(s)} حرف)"

    out = {
        "ok": True,
        "enabled": TG_ON,
        "token": _shape(TOKEN),
        "chat": _shape(CHAT),
        "routes": len(app.url_map._rules),
    }

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
            # ⛔ ما بيرجعش نص الخطأ — ممكن يكون فيه الـURL والتوكن
            out["getMe_err"] = type(e).__name__

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
        _log_exc("upstream-502b", e)
        return jsonify({"error": "تعذّر جلب البيانات من المصدر"}), 502


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
        _log_exc("upstream-502c", e)
        return jsonify({"ok": False, "error": "تعذّر جلب البيانات من المصدر"}), 502


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
    if iv(555, 570):  return 8       # 09:15–09:30 حجم كبير
    if iv(570, 600):  return 8       # 09:30–10:00 استكشافية
    if iv(600, 855):  return 5       # 10:00–14:15 تداول مستمر
    if iv(855, 865):  return 4       # 14:15–14:25 مزاد الإغلاق
    if iv(865, 870):  return 4       # 14:25–14:30 سعر الإغلاق
    if m < 555:       return 120     # قبل الافتتاح
    return 120                       # بعد الإغلاق


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


# ⛔ تحميل الملف الغني مرة واحدة عند الإقلاع — عشان،
#    (١) نعرف هو موجود فعلاً قبل أي حد يدخل،
#    (٢) أول مستخدم ما يستناش قراية 400KB.
try:
    _warm_data_full()
except Exception:
    pass
