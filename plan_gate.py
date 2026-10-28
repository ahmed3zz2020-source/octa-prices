# -*- coding: utf-8 -*-
"""💳 الاشتراكات وبوابة الباقة — مصدر واحد للحقيقة (٢٨ أكتوبر ٢٠٢٦)

📌 بيشمل:
   · حالة الباقة للمستخدم (free/pro) مع **تاريخ انتهاء**.
   · سجل المدفوعات (كل تفعيل بيتسجّل) — في `DATA_DIR/subscriptions.json`.
   · دوال مساعدة تشترك فيها كل الوحدات (نماذجي · الاستوديو · Challen…).

⛔ قاعدة: مافيش تخمين — لو الحقول ناقصة ⇒ free.
⛔ الكتابة ذرّية (ملف مؤقت + rename) + قفل على مستوى العملية.
"""
import json
import os
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OCTA_DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / ".probe_plans").write_text("1", encoding="utf-8")
except Exception:
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
        if until and until < (now or _now()):
            # ⛔ منتهي — السجل بيفضل موجود (الأدمن بيشوف التاريخ)
            return "free"
        return "pro"
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


def _clean(s, limit=200):
    return str(s or "").strip()[:limit]
