# -*- coding: utf-8 -*-
"""💳 الاشتراكات وبوابة الباقة — مصدر واحد للحقيقة (٢٨ أكتوبر ٢٠٢٦)

📌 الباقات المتاحة: **free** و **pro** فقط ⭐ (مفيش باقة تالتة ⭐).
📌 التفعيل: **يدوي إداري** ⭐ — ⛔ مفيش بوابة دفع ⭐ ولا Stripe ⭐ ولا PayPal ⭐
   ⭐ ولا checkout ⭐ ⇒ ⭐ كل تفعيل = (١) الأدمن يحدّد plan ⭐
   ⭐ (٢) `log_subscription` ⭐ بيسجّل العملية ⭐.
📌 السعر المعتمد ⭐: **٣٥٠ جنيه/شهر** ⭐ · **٣٥٠٠ جنيه/سنة** ⭐
   ⭐ (٣٠ يوم ⭐ · ٣٦٥ يوم ⭐).
📌 حقول السجل ⭐ (ملف `DATA_DIR/subscriptions.json` ⭐):
   `uid` · `email` · `plan` · `days` · `price` · `method` · `note` · `at` ⭐.

⛔ **قاعدة الاشتراك** ⭐ (fail-closed ⭐):
   ⛔ `plan` مش pro ⭐ ⇒ **free** ⭐.
   ⛔ ⭐ **مافيش تاريخ انتهاء** ⭐ (`plan_until` ناقص ⭐ أو مش رقم ⭐)
      ⭐ ⇒ **free** ⭐ ⭐ ⇒ ⭐ ⭐ الغياب ما بيبقىش ميزة ⭐ ⭐ (R31 ⭐).
   ⛔ تاريخ الانتهاء خلص ⭐ ⇒ **free** ⭐ (والسجل بيفضل موجود ⭐ للأدمن ⭐).
⛔ الكتابة ذرّية (ملف مؤقت + rename) + قفل على مستوى العملية.
"""
import json
import os
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OCTA_DATA_DIR", "/data"))
# 🐞🛡️ ٢١ نوفمبر ٢٠٢٦ (R29 · FINDING-23) ⭐⭐⭐ فحص الكتابة **آمن ضد السباق** ⭐⭐⭐
# 📌 العيب ⭐: ⛔ اسم ملف الفحص كان **ثابت** ⭐ ⇒ ⛔ عمليتين مع بعض ⭐ ⇒
#    ⛔ واحدة بتمسح الملف ⭐ ⭐ والالتانية ⭐ ⭐ `unlink()` ⭐ ⭐ بترمي ⭐ ⭐
#    ⭐ ⇒ ⛔ ⭐ ⭐ فتقع في الـfallback ⭐ ⭐ ⇒ ⛔ ⭐ ⭐ وبتكتب في **مجلد الكود** ⭐ ⭐
#    ⭐ ⭐ ⇒ ⛔ مجلدين مختلفين ⭐ ⭐ ⇒ ⛔ قفل مختلف ⭐ ⭐ ⇒ ⛔ lost update ⭐ ⭐ ⭐
# ✅ الحل ⭐: ⭐ اسم فريد بيلـpid ⭐ ⇒ ⭐ مافيش ملف مشترك ⭐ ⭐ + ⭐ ⭐ فشل الحذف ⭐ ⭐
#    ⭐ **مش** ⭐ ⭐ سبب للرجوع ⭐ ⭐ (الكتابة نفسها نجحت ⭐ ⭐) ⭐ ⭐.
DATA_DIR_PROBE_ERROR = None   # ⭐ سبب الفشل ⭐ (لو حصل ⭐) ⭐ — للتشخيص ⭐
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _probe = DATA_DIR / (".w-%d" % os.getpid())   # ⭐⭐ اسم فريد ⭐⭐ ⇒ ⭐ مافيش سباق ⭐
    _probe.write_text("1", encoding="utf-8")
    try:
        _probe.unlink()
    except OSError:
        # ⭐ الملف اتمسح من عملية تانية ⭐ ⇒ ⭐ ده **مش** فشل كتابة ⭐ ⇒ ⭐ نكمّل ⭐
        pass
except Exception as _probe_exc:
    DATA_DIR_PROBE_ERROR = "%s: %s" % (type(_probe_exc).__name__, str(_probe_exc)[:120])
    DATA_DIR = HERE

SUBS_FILE = DATA_DIR / "subscriptions.json"
_LOCK = threading.Lock()

# 📌 أسعار الباقة (٣٥٠ جنيه/شهر — قرار أحمد ٢٨ أكتوبر ٢٠٢٦)
PRICE_MONTH = 350
PRICE_YEAR = 3500
PLAN_MONTH_DAYS = 30
PLAN_YEAR_DAYS = 365


def _now():
    return int(time.time())


def plan_of(user, now=None):
    """حالة الباقة للمستخدم: 'free' أو 'pro'."""
    if not user:
        return "free"
    try:
        plan = str(user.get("plan") or "free").lower()
        if plan != "pro":
            return "free"
        until = user.get("plan_until") or 0
        try:
            until = int(until)
        except Exception:
            until = 0
        # ⭐⭐⭐ (R31) ⭐⭐⭐ مافيش تاريخ انتهاء ⭐ ⭐ ⇒ ⛔ **free** ⭐ ⭐ (fail-closed ⭐)
        # 📌 قبل ⭐: ⛔ `until` ⭐ صفر ⭐ ⭐ ⇒ ⭐ ⭐ ⭐ ⭐ الكود بيرجّع pro ⭐ ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⇒ ⭐ ⭐ باقة من غير حدّ ⭐ ⭐ ⇒ ⭐ ⭐ ⛔ Contradicts التوثيق ⭐ ⭐.
        # ✅ دلوقتي ⭐: ⭐ ⭐ ⭐ غياب التاريخ ⭐ ⭐ ⭐ ⇒ ⭐ ⭐ free ⭐ ⭐ ⭐
        #    ⭐ (زي باقي الحالات الناقصة ⭐) ⭐.
        if until <= 0:
            return "free"
        if until < (now or _now()):
            # ⛔ منتهي — السجل بيفضل موجود (الأدمن بيشوف التاريخ)
            return "free"
        return "pro"
    except Exception:
        return "free"


def resolve_plan(user, now=None, checker=None):
    """⛔ **القاعدة الواحدة** للباقة — fail-closed (الجولة ١٨ · SEC-011).

    📌 لو فيه `checker` (plan_checker):
       بنستدعيه ⬇️ ولو **وقع** (تعطّر سجل الاشتراكات ·Checker مكسور ·
       أي استثناء) ⇒ النتيجة ``'free'``.
    📌 لو مافيش checker ⇒ بنحسب من سجل المستخدم (نفس `plan_of`).
    ⛔ ممنوع ترجع `user['plan']` الخام ⬇️ ⬇️ ⇒ ده fail-open ⬇️
       (بيسمح بـPro منتهي أو بتلاعب في السجل).
    ⛔ أي قيمة مش معروفة (``''`` · ``None`` · قيمة غريبة) ⇒ ``'free'``.
    """
    if checker is not None:
        try:
            p = str(checker(user) or "").strip().lower()
        except Exception:
            return "free"
        return p if p in ("free", "pro") else "free"
    try:
        return plan_of(user, now)
    except Exception:
        return "free"


def plan_until(user):
    try:
        return int(user.get("plan_until") or 0)
    except Exception:
        return 0


def status_of(user, now=None):
    """تفاصيل الاشتراك للمستخدم (للواجهة)."""
    now = now or _now()
    plan = plan_of(user, now)
    until = plan_until(user)
    days_left = 0
    if plan == "pro" and until:
        days_left = max(0, int((until - now) / 86400.0))
    return {
        "plan": plan,
        "until": until,
        "until_date": (time.strftime("%Y-%m-%d", time.gmtime(until))
                       if until else None),
        "days_left": days_left,
        "expired": bool(until and until < now and
                        str((user or {}).get("plan") or "").lower() == "pro"),
        "price_month": PRICE_MONTH,
        "price_year": PRICE_YEAR,
    }


def _read_log():
    try:
        if not SUBS_FILE.exists():
            return []
        d = json.loads(SUBS_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _write_log(items):
    try:
        tmp = SUBS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SUBS_FILE)
        return True
    except Exception:
        return False


def log_subscription(uid, email, plan, days, price, method="admin", note=""):
    """يسجّل تفعيل/تجديد باقة. يرجّع (السجل, خطأ)."""
    if not uid:
        return None, "لازم uid"
    try:
        days = int(days or 0)
    except Exception:
        days = 0
    if days <= 0:
        return None, "لازم عدد أيام"
    now = _now()
    with _LOCK:
        items = _read_log()
        rec = {
            "uid": str(uid),
            "email": str(email or ""),
            "plan": str(plan or "pro"),
            "days": days,
            "price": float(price or 0),
            "method": str(method or "admin"),
            "note": _clean(note, 200),
            "at": now,
            "at_date": time.strftime("%Y-%m-%d %H:%M", time.gmtime(now)),
        }
        items.append(rec)
        items = items[-2000:]
        if not _write_log(items):
            return None, "مش قادر أسجّل"
        return rec, None


def subscription_log(limit=100):
    items = _read_log()
    items.sort(key=lambda x: x.get("at") or 0, reverse=True)
    return items[:int(limit or 100)]


def rollback_subscription(rec):
    """⛔ التراجع عن عملية تسجيل (الجولة ١٨ · SEC-012).

    📌 السبب: لو عملية التفعيل اتسجّلت وبعدين **فشل** تغيير
       الخطة ⬇️ ⇒ لازم السجل يرجع زي ما كان ⬇️ ⇒ الحالة النهائية
       ⬇️ متسقة دايمًا (مافيش «Pro من غير سجل» ولا «سجل من غير Pro»).
    📌 بيرجّع True/False (مافيش «نجاح» كاذب).
    """
    if not isinstance(rec, dict):
        return False
    try:
        uid = str(rec.get("uid") or "")
        at = int(rec.get("at") or 0)
        with _LOCK:
            items = _read_log()
            out = [x for x in items
                   if not (str(x.get("uid") or "") == uid
                           and int(x.get("at") or 0) == at)]
            if len(out) == len(items):
                return False        # ⛔ مافيش سجل بهذا الوصف
            return _write_log(out)
    except Exception:
        return False


def _clean(s, limit=200):
    return str(s or "").strip()[:limit]
