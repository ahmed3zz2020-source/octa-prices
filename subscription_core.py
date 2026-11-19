# -*- coding: utf-8 -*-
"""
💳 الجولة ٢٦ (R26) — نواة نظام الاشتراكات (مزوّد دفع **صناعي**)
========================================================================
📌 الهدف: نظام اشتراكات كامل شغّال **من غير** تعاقد مع مزوّد دفع حقيقي،
   ومن غير تحصيل مالي حقيقي، ومن غير بيانات عملاء حقيقية.

⛔⛔⛔ قواعد الجولة ٢٦ (هارد) ⬇️ ⬇️ ⬇️
   ⛔ مافيش أي اتصال بشبكة خارجية — المزوّد محاكاة محلية 100%.
   ⛔ مافيش أرقام بطاقات ولا أسرار ولا مفاتيح API في الكود ولا في الملفات.
   ⛔ مافيش بيانات عملاء حقيقية — كل المعرفات معرّفات اصطناعية.
   ⛔ التخزين **منفصل** عن users.json (مجلد مستقل: subscriptions_v2).
   ⛔ مافيش أي تعديل على أوزان المحرك ولا حدود القبول ولا سياسة الاستثمار.

📦 محتويات الملف:
   · MockProvider — مزوّد دفع صناعي (نجاح/رفض/تعطّل/مهلة) — بلا شبكة.
   · Store — تخزين داخلي منفصل (JSON ذرّي + قفل + نسخة احتياطية).
   · Billing — محرك دورة الاشتراك:
                          اشتراك · تجديد · انتهاء · إلغاء · استرداد.
   · تفرّد الطلبات — نفس idempotency-key ⇒ نفس النتيجة، بلا تحصيل مكرر.
   · التسوية — محاكاة إشعار المزوّد ⇒ تطبّق الحالة مرة واحدة فقط.
   · الصلاحيات — الاشتراك بيحدد ما يشوفه المستخدم (فرص/تنبيهات/RealView).
   · الحذف — purge_user_data: بيانات الاشتراك + المحفظة + التنبيهات.
   · الاحتفاظ — sweep: تنظيف دوري متسق مع وثيقة الخصوصية.

📌 مصدر الحقيقة الوحيد لالباقات: `data/subscription_plans.json`.
📌 وثيقة الخصوصية والاحتفاظ: `docs/privacy_and_retention.md`.
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── مسارات التخزين ────────────────────────────────────────────────────────
STORE_DIRNAME = "subscriptions_v2"
PLAN_FILE_NAME = "subscription_plans.json"
ENV_DATA_DIR = "OCTA_DATA_DIR"
ENV_PLANS_FILE = "OCTA_SUBSCRIPTION_PLANS_FILE"

# ⛔⛔⛔ سياسات الاحتفاظ — **نفس الأرقام** موثّقة في
#    docs/privacy_and_retention.md ⬇️ (أي تعديل هنا = تعديل في الوثيقة)
RETENTION = {
    "idempotency_days": 2,             # مفتاح التفرّد: ٤٨ ساعة
    "failed_payment_days": 90,         # محاولة دفع فاشلة: ٩٠ يوم
    "payment_days": 730,               # عملية دفع: سنتان
    "subscription_days": 730,          # اشتراك منتهي أو ملغى: سنتان
    "settlement_days": 730,            # حدث تسوية: سنتان
    "support_closed_days": 365,        # تذكرة دعم مغلقة: سنة
    "deletion_receipt_days": 365,      # إيصال حذف الحساب: سنة
    "pending_checkout_days": 30,       # سلة دفع لم تُسدّد: ٣٠ يوم
}

# ── قوالب الدعم الفني (نقطة الدخول + قالب رسالة) ──────────────────────────
SUPPORT_TEMPLATES = {
    "payment_failed": {
        "title": "مشكلة في الدفع أو الاشتراك",
        "body": ("السلام عليكم\n\n"
                 "حصل عندي مشكلة في الدفع:\n"
                 "- رقم العملية: {reference}\n"
                 "- الباقة: {plan}\n"
                 "- الرسالة اللي ظهرت: {message}\n\n"
                 "من فضلكم راجعوا العملية وقولوا لي الحالة,\n"
                 "وإيه اللي أعمله عشان أكمّل اشتراكي.\n\n"
                 "شكراً لكم."),
    },
    "refund_request": {
        "title": "طلب استرداد",
        "body": ("السلام عليكم\n\n"
                 "أنا بطلب استرداد اشتراكي:\n"
                 "- رقم العملية: {reference}\n"
                 "- الباقة: {plan}\n"
                 "- سبب الطلب: {message}\n\n"
                 "من فضلكم راجعوا العملية وقولوا لي الحالة،\n"
                 "وإيه المدة المتوقعة للاسترداد.\n\n"
                 "شكراً لكم."),
    },
    "general": {
        "title": "استفسار عام",
        "body": ("السلام عليكم\n\n"
                 "عندي استفسار بخصوص اشتراك OCTA:\n"
                 "- الموضوع: {subject}\n"
                 "- التفاصيل: {message}\n\n"
                 "وشكراً لكم."),
    },
}


class SubscriptionError(Exception):
    """خطأ في محرك الاشتراكات ⇐ بيتجم لرد HTTP."""

    def __init__(self, status, message, why="", extra=None):
        super().__init__(message)
        self.status = int(status)
        self.message = str(message)
        self.why = str(why or "")
        self.extra = extra or {}


class PlanFileError(Exception):
    """ملف الباقات ناقص أو تالف ⇐ مافيش تخمين (fail-closed)."""
    pass


# ══════════════════════════════════════════════════════════════════════════
#  ① المزوّد الصناعي — مافيش شبكة، مافيش أسرار، مافيش بطاقات
# ══════════════════════════════════════════════════════════════════════════

class MockProvider:
    """💳 مزوّد دفع **صناعي** — محاكاة محلية بالكامل.

    📌 سيناريو الدفع بيتحسب من **معرّف اصطناعي** مش بيتصل بأي شبكة:
       · لاحقة ``decline``  ⇒ بطاقة مرفوضة.
       · لاحقة ``down``      ⇒ المزوّد معطّل (٥٠٣).
       · لاحقة ``timeout``   ⇒ مهلة (٥٠٤).
       · أي توكن تاني        ⇒ عملية ناجحة.
    📌 `outage=True` يعطّل المزوّد بالكامل (عطل عام).
    ⛔ التوكن هنا **مش رقم بطاقة** — مجرد سلسلة اختبار اصطناعية.
    """

    NAME = "mock"

    def __init__(self, outage=False):
        self.outage = bool(outage)
        self.attempts = 0
        self.approved = 0
        self.declined = 0
        self.timeouts = 0
        self.outages = 0
        self.refunds = 0

    def _scenario(self, token):
        t = str(token or "").strip().lower()
        if self.outage:
            return "provider_down"
        if "down" in t or "unavailable" in t or "outage" in t:
            return "provider_down"
        if "timeout" in t:
            return "timeout"
        if "decline" in t or "reject" in t or "fail" in t:
            return "declined"
        return "succeeded"

    def charge(self, token, amount, currency="EGP", meta=None):
        """⛔ مافيش شبكة ⇐ قرار محلي بحت حسب التوكن."""
        self.attempts += 1
        outcome = self._scenario(token)
        charge_id = ""
        reason = ""
        if outcome == "succeeded":
            self.approved += 1
            charge_id = _rid("chg")
        elif outcome == "declined":
            self.declined += 1
            reason = "card_declined"
        elif outcome == "timeout":
            self.timeouts += 1
            reason = "provider_timeout"
        else:
            self.outages += 1
            reason = "provider_unavailable"
        return {
            "provider": self.NAME,
            "status": outcome,
            "charge_id": charge_id,
            "failure_reason": reason,
            "amount": float(amount or 0),
            "currency": str(currency or "EGP"),
            "meta": dict(meta or {}),
        }

    def refund(self, charge_id, amount=None):
        """⛔ استرداد محلي — مافيش شبكة."""
        self.refunds += 1
        return {
            "provider": self.NAME,
            "status": "succeeded",
            "refund_id": _rid("ref"),
            "charge_id": str(charge_id or ""),
            "amount": float(amount or 0),
            "failure_reason": "",
        }

    def stats(self):
        return {
            "provider": self.NAME,
            "attempts": self.attempts,
            "approved": self.approved,
            "declined": self.declined,
            "timeouts": self.timeouts,
            "outages": self.outages,
            "refunds": self.refunds,
        }


# ══════════════════════════════════════════════════════════════════════════
#  ② التخزين الداخلي المنفصل (مستقل تماماً عن users.json)
# ══════════════════════════════════════════════════════════════════════════

_FILES = {
    "subscriptions": "subscriptions.json",
    "payments": "payments.json",
    "wallet": "wallet.json",
    "support": "support.json",
    "idempotency": "idempotency.json",
    "settlement": "settlement.json",
    "receipts": "receipts.json",
}
_LIST_FILES = ("subscriptions", "payments", "wallet", "support",
               "settlement", "receipts")


class Store:
    """📦 تخزين الاشتراكات — مجلد مستقل عن users.json.

    ⛔ الكتابة ذرّية (ملف مؤقت + fsync + rename) مع نسخة احتياطية.
    ⛔ لو الملف تالف ⇒ **مابنتكتبش فوقه** (لا مسح بيانات) والكتابة ترجع False.
    """

    def __init__(self, base_dir=None):
        self.base = Path(base_dir) if base_dir else _default_data_dir()
        self.dir = self.base / STORE_DIRNAME
        self.lock = threading.RLock()
        self.error = ""
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.error = "%s: %s" % (type(e).__name__, str(e)[:120])

    def path(self, name):
        return self.dir / _FILES[name]

    def read(self, name):
        """⛔ خطأ في القراءة = قائمة/قاموس فاضية + تسجيل السبب (fail-closed)."""
        with self.lock:
            p = self.path(name)
            try:
                raw = p.read_text(encoding="utf-8")
            except FileNotFoundError:
                return {} if name == "idempotency" else []
            except Exception as e:
                self.error = "%s: %s" % (type(e).__name__, str(e)[:120])
                return {} if name == "idempotency" else []
            try:
                data = json.loads(raw)
            except Exception:
                self.error = "ملف %s تالف (مش JSON صالح)" % _FILES[name]
                return {} if name == "idempotency" else []
            if name == "idempotency":
                return data if isinstance(data, dict) else {}
            return data if isinstance(data, list) else []

    def write(self, name, data):
        """⛔ كتابة ذرّية. بترجع True/False — مافيش «نجاح» كاذب."""
        with self.lock:
            p = self.path(name)
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                if p.exists():
                    try:
                        cur = json.loads(p.read_text(encoding="utf-8"))
                        if not isinstance(cur, (dict, list)):
                            raise ValueError("not-a-container")
                    except Exception:
                        # ⛔ ملف تالف ⇒ مرفوض الكتابة فوقه (مافيش مسح بيانات)
                        self.error = "ملف %s تالف — مرفوض الكتابة فوقه" % _FILES[name]
                        return False
                tmp = p.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False))
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                try:
                    if p.exists():
                        bak = p.with_suffix(".bak")
                        bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass
                tmp.replace(p)
                return True
            except Exception as e:
                self.error = "%s: %s" % (type(e).__name__, str(e)[:120])
                return False

    def broken(self):
        return bool(self.error)


# ══════════════════════════════════════════════════════════════════════════
#  ③ محرك الاشتراكات
# ══════════════════════════════════════════════════════════════════════════

class Billing:
    """💠 محرك دورة الاشتراك — مصدر الحقيقة الوحيد لحالة الاشتراك."""

    def __init__(self, base_dir=None, plans_path=None, provider=None, clock=None):
        self.store = Store(base_dir)
        self._plans_path = Path(plans_path) if plans_path else None
        self._plans_cache = None
        self.provider = provider if provider is not None else MockProvider()
        self.clock = clock if callable(clock) else (lambda: int(time.time()))

    # ── الباقات ─────────────────────────────────────────────────────────
    def plans(self):
        """📖 كتالوج الباقات من ملف الإعدادات (مافيش قيم مخترعة)."""
        if self._plans_cache is not None:
            return self._plans_cache
        p = self._plans_path or _plans_path()
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            raise PlanFileError("ملف الباقات مش موجود (%s)" % p.name)
        try:
            d = json.loads(raw)
        except Exception:
            raise PlanFileError("ملف الباقات تالف (مش JSON صالح)")
        if not isinstance(d, dict) or not isinstance(d.get("plans"), dict) \
                or not d.get("plans"):
            raise PlanFileError("ملف الباقات ناقص (مافيش plans)")
        for code, pdef in d["plans"].items():
            _validate_plan(code, pdef)
        self._plans_cache = d
        return d

    def plan_or_fail(self, code):
        """⛔ الباقة المجهولة ⇒ خطأ (مافيش باقة افتراضية مخترعة)."""
        code = str(code or "").strip().lower()
        pdef = (self.plans().get("plans") or {}).get(code)
        if not isinstance(pdef, dict):
            raise SubscriptionError(404, "الباقة دي مش موجودة",
                                    "unknown_plan", {"plan": code})
        return pdef

    def period_or_fail(self, pdef, period):
        """⛔ الفترة المجهولة ⇒ الخطأ الأول في قائمة الفترات."""
        periods = pdef.get("periods") or []
        want = str(period or "monthly").strip().lower()
        for pr in periods:
            if str(pr.get("code") or "").lower() == want:
                return pr
        raise SubscriptionError(400, "الفترة دي مش متاحة للباقة دي",
                                "unknown_period", {"period": want})

    def price_of(self, pdef, period):
        pr = self.period_or_fail(pdef, period)
        try:
            return float(pr.get("price") or 0)
        except Exception:
            raise SubscriptionError(500, "سعر غير صالح في ملف الباقات",
                                    "bad_plan_file")

    def _plan_code(self, uid, now=None):
        """🎯 كود الباقة السارية للمستخدم."""
        return self.entitlements_for(uid, now).get("plan")

    def _limits_of(self, uid, now=None):
        """🎯 حدود الصلاحيات السارية للمستخدم (من الباقة النشطة بس)."""
        return self.entitlements_for(uid, now).get("entitlements") or {}

    def entitlements_of(self, plan_code):
        """🎯 صلاحيات باقة معيّنة (من ملف الباقات)."""
        plans = self.plans()
        pdef = (plans.get("plans") or {}).get(str(plan_code or "").strip().lower())
        if not isinstance(pdef, dict):
            pdef = (plans.get("plans") or {}).get(
                str(plans.get("default_plan") or "free"))
        ent = dict((pdef or {}).get("entitlements") or {})
        return ent

    def catalog(self):
        """📦 الكتالوج public — بلا أي بيانات مستخدمين."""
        plans = self.plans()
        out = []
        for code, pdef in (plans.get("plans") or {}).items():
            out.append({
                "code": code,
                "name": pdef.get("name") or code,
                "tagline": pdef.get("tagline") or "",
                "sellable": bool(pdef.get("sellable")),
                "periods": pdef.get("periods") or [],
                "features": pdef.get("features") or [],
                "entitlements": pdef.get("entitlements") or {},
            })
        return {
            "version": plans.get("version") or "",
            "currency": plans.get("currency") or "EGP",
            "default_plan": plans.get("default_plan") or "free",
            "provider": plans.get("provider") or MockProvider.NAME,
            "provider_note": plans.get("provider_note") or "",
            "plans": out,
        }

    # ── أدوات داخلية ────────────────────────────────────────────────────
    def _subs(self):
        return self.store.read("subscriptions")

    def _find_sub(self, uid, subscription_id=None):
        subs = self._subs()
        uid = str(uid or "")
        if subscription_id:
            for s in subs:
                if str(s.get("id") or "") == str(subscription_id):
                    return s
            return None
        cands = [s for s in subs if str(s.get("uid") or "") == uid]
        cands.sort(key=lambda s: int(s.get("created_at") or 0), reverse=True)
        return cands[0] if cands else None

    def _active_subscription(self, uid, now=None):
        """⛔ خطة واحدة نشطة بس لكل مستخدم."""
        now = now or self.clock()
        actives = [s for s in self._subs()
                   if str(s.get("uid") or "") == str(uid or "")
                   and str(s.get("status") or "") == "active"
                   # ⛔⛔⛔ الفترة خلصت ⇒ صفر صلاحيات حتى لو الحالة
                   #    لسه ما اتطبّقتش (fail-closed وقت القراءة)
                   and int(s.get("period_end") or 0) > int(now or 0)]
        if not actives:
            return None
        actives.sort(key=lambda s: int(s.get("period_end") or 0), reverse=True)
        return actives[0]

    def _guard_single_active(self, uid, keep_id, now):
        """⛔⛔⛔ منع التفعيل المزدوج.

        📌 خطة مدفوعة جديدة + خطة قديمة نشطة ⇒ المسموح **واحد بس**.
        📌 الخطة القديمة بتتحوّل لـ superseded (ماتفريش — أثر للتدقيق).
        """
        subs = self._subs()
        changed = False
        for s in subs:
            if str(s.get("uid") or "") != str(uid or ""):
                continue
            if str(s.get("id") or "") == str(keep_id):
                continue
            if str(s.get("status") or "") == "active":
                s["status"] = "superseded"
                s["superseded_at"] = now
                s["superseded_by"] = str(keep_id or "")
                s["ended_reason"] = "superseded"
                changed = True
        if changed:
            self.store.write("subscriptions", subs)
        return changed

    def _mask_failure(self, sub, result, now):
        """⛔⛔⛔ فشل الدفع ⇒ الحالة masked (failed) والاشتراك **ما يتفعّلش**.

        📌 period_end = 0 و activated_payment_id فاضي ⇒ صفر صلاحيات.
        """
        sub["status"] = "failed"
        sub["failure_reason"] = str(result.get("failure_reason") or "payment_failed")
        sub["failed_at"] = now
        sub["period_end"] = 0
        sub["activated_payment_id"] = ""
        sub["updated_at"] = now
        return sub

    def _idem_key(self, scope, uid, key):
        return "%s:%s:%s" % (scope, str(uid or ""), str(key or ""))

    def _idem_lookup(self, scope, uid, key):
        """⛔⛔⛔ تفرّد الطلبات — نفس المفتاح ⇒ نفس النتيجة."""
        if not key:
            return None
        rec = self.store.read("idempotency").get(self._idem_key(scope, uid, key))
        if not isinstance(rec, dict):
            return None
        return rec

    def _idem_save(self, scope, uid, key, fingerprint, status, body):
        if not key:
            return
        data = self.store.read("idempotency")
        data[self._idem_key(scope, uid, key)] = {
            "scope": scope,
            "uid": str(uid or ""),
            "key": str(key or "")[:80],
            "fingerprint": fingerprint,
            "status": int(status or 200),
            "response": body,
            "created_at": self.clock(),
        }
        self.store.write("idempotency", data)

    @staticmethod
    def _fingerprint(scope, uid, payload):
        raw = json.dumps({"scope": scope, "uid": str(uid or ""),
                          "payload": payload}, sort_keys=True,
                         ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _ledger(self, uid, kind, amount, payment_id, note=""):
        entries = self.store.read("wallet")
        entries.append({
            "id": _rid("wal"),
            "uid": str(uid or ""),
            "kind": kind,
            "amount": float(amount or 0),
            "payment_id": str(payment_id or ""),
            "note": str(note or "")[:120],
            "at": self.clock(),
        })
        self.store.write("wallet", entries)

    def _record_payment(self, uid, sub, plan, amount, currency, period, result,
                        idem_key):
        payments = self.store.read("payments")
        rec = {
            "id": _rid("pay"),
            "uid": str(uid or ""),
            "subscription_id": str(sub.get("id") or ""),
            "plan": str(plan or ""),
            "amount": float(amount or 0),
            "currency": str(currency or "EGP"),
            "period": str(period or ""),
            "status": str(result.get("status") or "failed"),
            "failure_reason": str(result.get("failure_reason") or ""),
            "charge_id": str(result.get("charge_id") or ""),
            "provider": MockProvider.NAME,
            "idempotency_key": str(idem_key or "")[:80],
            "created_at": self.clock(),
            "settled_at": 0,
        }
        payments.append(rec)
        self.store.write("payments", payments)
        return rec

    def _expire_due(self, now):
        """⛔⛔⛔ انتهاء الاشتراك — يُطبَّق عند القراءة (بلا مهمة دورية).

        📌 ended_at بيحصل عند حلول period_end (أو عند الإلغاء بنهاية الفترة).
        """
        subs = self._subs()
        changed = False
        for s in subs:
            if str(s.get("status") or "") != "active":
                continue
            end = int(s.get("period_end") or 0)
            if end <= now:
                if s.get("cancel_at_period_end"):
                    s["status"] = "canceled"
                    s["ended_reason"] = "canceled_at_period_end"
                else:
                    s["status"] = "expired"
                    s["ended_reason"] = "period_ended"
                s["ended_at"] = now
                s["updated_at"] = now
                changed = True
        if changed:
            self.store.write("subscriptions", subs)
        return changed

    def _activate(self, sub, payment_id, days, now):
        """⛔ التفعيل — يمدّد الفترة ويفرض خطة واحدة نشطة."""
        prev_end = int(sub.get("period_end") or 0)
        base = prev_end if prev_end > now else now
        sub["period_end"] = base + int(days or 30) * 86400
        sub["status"] = "active"
        sub["activated_payment_id"] = str(payment_id or "")
        sub["activated_at"] = now
        sub["updated_at"] = now
        sub["failure_reason"] = ""
        self._guard_single_active(sub.get("uid"), sub.get("id"), now)
        return sub

    # ══════════════════════════════════════════════════════════════════
    #  ④ دورة الاشتراك
    # ══════════════════════════════════════════════════════════════════

    def subscribe(self, uid, plan, idem_key, token="tok_mock_ok",
                  period="monthly", defer_settlement=False):
        """🆕 تسجيل اشتراك جديد.

        📌 الترتيب: التحقق ⇒ تفرّد ⇒ تحصيل (مزوّد صناعي) ⇒ تفعيل/تعليق.
        ⛔ الفشل ⇒ masked، والاشتراك ما يتفعّلش، وصفر تحصيل في المحفظة.
        """
        uid = str(uid or "").strip()
        if not uid:
            raise SubscriptionError(400, "لازم حساب مسجّل", "no_user")
        idem_key = str(idem_key or "").strip()[:80]
        if not idem_key:
            raise SubscriptionError(400, "لازم مفتاح تفرّد للطلب",
                                    "idempotency_key_required")
        pdef = self.plan_or_fail(plan)
        if not pdef.get("sellable"):
            raise SubscriptionError(400, "الباقة دي مش قابلة للشراء",
                                    "plan_not_sellable", {"plan": plan})
        pr = self.period_or_fail(pdef, period)
        days = int(pr.get("days") or 30)
        price = float(pr.get("price") or 0)
        currency = str(self.plans().get("currency") or "EGP")

        fingerprint = self._fingerprint("subscribe", uid, {
            "plan": str(plan or "").lower(),
            "period": str(pr.get("code") or period),
            "defer_settlement": bool(defer_settlement),
        })

        with self.store.lock:
            prev = self._idem_lookup("subscribe", uid, idem_key)
            if prev is not None:
                if prev.get("fingerprint") != fingerprint:
                    raise SubscriptionError(
                        409, "مفتاح التفرّد ده مستخدم لطلب مختلف",
                        "idempotency_conflict")
                body = dict(prev.get("response") or {})
                body["idempotent_replay"] = True
                return int(prev.get("status") or 200), body

            now = self.clock()
            sub = {
                "id": _rid("sub"),
                "uid": uid,
                "plan": str(plan or "").lower(),
                "period": str(pr.get("code") or period),
                "period_days": days,
                "amount": price,
                "currency": currency,
                "status": "pending",
                "started_at": now,
                "period_end": 0,
                "created_at": now,
                "updated_at": now,
                "cancel_at_period_end": False,
                "canceled_at": 0,
                "activated_payment_id": "",
                "failure_reason": "",
            }
            subs = self._subs()
            subs.append(sub)
            self.store.write("subscriptions", subs)

            result = self.provider.charge(token, price, currency, {
                "plan": sub["plan"], "subscription_id": sub["id"]})
            pay = self._record_payment(uid, sub, sub["plan"], price, currency,
                                       sub["period"], result, idem_key)
            sub["payment_id"] = pay["id"]

            if result.get("status") != "succeeded":
                # ⛔⛔⛔ فشل الدفع ⇒ masked، بدون تفعيل، بدون تحصيل
                self._mask_failure(sub, result, now)
                subs = self._subs()
                self._replace_sub(subs, sub)
                body = {
                    "ok": False,
                    "status": "failed",
                    "reason": sub["failure_reason"],
                    "subscription": dict(sub),
                    "payment": dict(pay),
                    "plan": self._plan_code(uid, now),
                    "entitlements": self._limits_of(uid, now),
                    "message": _fail_message(sub["failure_reason"]),
                }
                self._idem_save("subscribe", uid, idem_key, fingerprint,
                                _fail_status(sub["failure_reason"]), body)
                return _fail_status(sub["failure_reason"]), body

            if defer_settlement:
                # 📌 مسار التسوية المتأخر (webhook) ⇒ الاشتراك يفضل pending
                pay["status"] = "authorized"
                self._update_payment(pay)
                body = {
                    "ok": True,
                    "status": "pending",
                    "subscription": dict(sub),
                    "payment": dict(pay),
                    "plan": self._plan_code(uid, now),
                    "entitlements": self._limits_of(uid, now),
                    "message": "تم تسجيل العملية — التفعيل بعد إشعار المزوّد.",
                }
            else:
                self._activate(sub, pay["id"], days, now)
                pay["status"] = "succeeded"
                pay["settled_at"] = now
                self._update_payment(pay)
                self._ledger(uid, "charge", price, pay["id"], sub["plan"])
                subs = self._subs()
                self._replace_sub(subs, sub)
                body = {
                    "ok": True,
                    "status": "active",
                    "subscription": dict(sub),
                    "payment": dict(pay),
                    "plan": self._plan_code(uid, now),
                    "entitlements": self._limits_of(uid, now),
                    "message": "الاشتراك اتفعّل.",
                }
            self._idem_save("subscribe", uid, idem_key, fingerprint, 200, body)
            return 200, body

    def renew(self, uid, idem_key, token="tok_mock_ok", subscription_id=None,
              period=None):
        """🔁 تجديد اشتراك — يمدّد من تاريخ الانتهاء الحالي لو لسه ساري."""
        uid = str(uid or "").strip()
        idem_key = str(idem_key or "").strip()[:80]
        if not idem_key:
            raise SubscriptionError(400, "لازم مفتاح تفرّد للطلب",
                                    "idempotency_key_required")
        with self.store.lock:
            sub = self._find_sub(uid, subscription_id)
            if sub is None:
                raise SubscriptionError(404, "مافيش اشتراك للتجديد",
                                        "no_subscription")
            if str(sub.get("status") or "") == "canceled":
                raise SubscriptionError(409, "الاشتراك ملغي — اشترك من جديد",
                                        "subscription_canceled")
            pdef = self.plan_or_fail(sub.get("plan"))
            pr = self.period_or_fail(pdef, period or sub.get("period"))
            days = int(pr.get("days") or 30)
            price = float(pr.get("price") or 0)
            currency = str(self.plans().get("currency") or "EGP")
            fingerprint = self._fingerprint("renew", uid, {
                "subscription_id": str(sub.get("id") or ""),
                "period": str(pr.get("code") or ""),
            })
            prev = self._idem_lookup("renew", uid, idem_key)
            if prev is not None:
                if prev.get("fingerprint") != fingerprint:
                    raise SubscriptionError(
                        409, "مفتاح التفرّد ده مستخدم لطلب مختلف",
                        "idempotency_conflict")
                body = dict(prev.get("response") or {})
                body["idempotent_replay"] = True
                return int(prev.get("status") or 200), body

            now = self.clock()
            result = self.provider.charge(token, price, currency, {
                "plan": sub.get("plan"), "subscription_id": sub.get("id")})
            pay = self._record_payment(uid, sub, sub.get("plan"), price,
                                       currency, pr.get("code"), result,
                                       idem_key)
            if result.get("status") != "succeeded":
                self._mask_failure(sub, result, now)
                self._replace_sub(self._subs(), sub)
                body = {
                    "ok": False,
                    "status": "failed",
                    "reason": sub["failure_reason"],
                    "subscription": dict(sub),
                    "payment": dict(pay),
                    "plan": self._plan_code(uid, now),
                    "entitlements": self._limits_of(uid, now),
                    "message": _fail_message(sub["failure_reason"]),
                }
                self._idem_save("renew", uid, idem_key, fingerprint,
                                _fail_status(sub["failure_reason"]), body)
                return _fail_status(sub["failure_reason"]), body

            self._activate(sub, pay["id"], days, now)
            pay["status"] = "succeeded"
            pay["settled_at"] = now
            self._update_payment(pay)
            self._ledger(uid, "charge", price, pay["id"], sub.get("plan"))
            self._replace_sub(self._subs(), sub)
            body = {
                "ok": True,
                "status": "active",
                "subscription": dict(sub),
                "payment": dict(pay),
                "plan": self._plan_code(uid, now),
                "entitlements": self._limits_of(uid, now),
                "message": "تم تجديد الاشتراك.",
            }
            self._idem_save("renew", uid, idem_key, fingerprint, 200, body)
            return 200, body

    def cancel(self, uid, subscription_id=None, at_period_end=True,
               reason=""):
        """✋ إلغاء اشتراك — فوري أو بنهاية الفترة."""
        uid = str(uid or "").strip()
        with self.store.lock:
            sub = self._find_sub(uid, subscription_id)
            if sub is None:
                raise SubscriptionError(404, "مافيش اشتراك لإلغائه",
                                        "no_subscription")
            now = self.clock()
            status = str(sub.get("status") or "")
            if status in ("canceled", "refunded"):
                body = {"ok": True, "status": status,
                        "subscription": dict(sub),
                        "plan": self._plan_code(uid, now),
                        "entitlements": self._limits_of(uid, now),
                        "message": "الاشتراك ملغي بالفعل."}
                return 200, body
            if at_period_end:
                sub["cancel_at_period_end"] = True
                sub["cancel_requested_at"] = now
                sub["cancel_reason"] = str(reason or "")[:200]
                sub["updated_at"] = now
                self._replace_sub(self._subs(), sub)
                body = {"ok": True, "status": status,
                        "effective": "period_end",
                        "subscription": dict(sub),
                        "plan": self._plan_code(uid, now),
                        "entitlements": self._limits_of(uid, now),
                        "message": "الإلغاء اتسجل — هيفضل شغّال لحد نهاية الفترة."}
                return 200, body
            # ⛔⛔⛔ إلغاء فوري ⇒ الصلاحيات تترفع فوراً (ما تفضلش شغّالة)
            sub["status"] = "canceled"
            sub["canceled_at"] = now
            sub["cancel_at_period_end"] = False
            sub["period_end"] = 0
            sub["ended_reason"] = "canceled_by_user"
            sub["updated_at"] = now
            self._replace_sub(self._subs(), sub)
            body = {"ok": True, "status": "canceled", "effective": "now",
                    "subscription": dict(sub),
                    "plan": self._plan_code(uid, now),
                    "entitlements": self._limits_of(uid, now),
                    "message": "الاشتراك اتلغى."}
            return 200, body

    def refund(self, uid, idem_key, subscription_id=None, reason=""):
        """↩️ استرداد — يرجّع التحصيل و**يرفع الصلاحيات**."""
        uid = str(uid or "").strip()
        idem_key = str(idem_key or "").strip()[:80]
        if not idem_key:
            raise SubscriptionError(400, "لازم مفتاح تفرّد للطلب",
                                    "idempotency_key_required")
        with self.store.lock:
            sub = self._find_sub(uid, subscription_id)
            if sub is None:
                raise SubscriptionError(404, "مافيش اشتراك للاسترداد",
                                        "no_subscription")
            fingerprint = self._fingerprint("refund", uid, {
                "subscription_id": str(sub.get("id") or ""),
                "reason": str(reason or "")[:200],
            })
            # ⛔⛔⛔ فحص التفرّد **قبل** أي فحص تاني ⬇️ ⬇️ ⬇️
            # ⛔ إعادة نفس الطلب بنفس المفتاح ⇒ نفس النتيجة بالظبط
            #    (مش 409 «اتسترد قبل كده» — دي نتيجة مختلفة!).
            prev = self._idem_lookup("refund", uid, idem_key)
            if prev is not None:
                if prev.get("fingerprint") != fingerprint:
                    raise SubscriptionError(
                        409, "مفتاح التفرّد ده مستخدم لطلب مختلف",
                        "idempotency_conflict")
                body = dict(prev.get("response") or {})
                body["idempotent_replay"] = True
                return int(prev.get("status") or 200), body
            if str(sub.get("status") or "") == "refunded":
                raise SubscriptionError(409, "الاشتراك ده اتسترد قبل كده",
                                        "already_refunded")

            now = self.clock()
            pay = self._last_successful_payment(sub.get("id"))
            if pay is None:
                raise SubscriptionError(409, "مافيش عملية دفع ناجحة للاسترداد",
                                        "no_successful_payment")
            res = self.provider.refund(pay.get("charge_id"), pay.get("amount"))
            # ⛔⛔⛔ الاسترداد ⇒ الاشتراك refunded والصلاحيات بترتفع فوراً
            sub["status"] = "refunded"
            sub["refunded_at"] = now
            sub["refund_id"] = res.get("refund_id")
            sub["refund_reason"] = str(reason or "")[:200]
            sub["period_end"] = 0
            sub["ended_reason"] = "refunded"
            sub["updated_at"] = now
            self._replace_sub(self._subs(), sub)
            pay["status"] = "refunded"
            pay["settled_at"] = now
            self._update_payment(pay)
            self._ledger(uid, "refund", pay.get("amount"), pay.get("id"),
                         sub.get("plan"))
            body = {
                "ok": True,
                "status": "refunded",
                "subscription": dict(sub),
                "payment": dict(pay),
                "plan": self._plan_code(uid, now),
                "entitlements": self._limits_of(uid, now),
                "message": "الاسترداد اتنفّذ.",
            }
            self._idem_save("refund", uid, idem_key, fingerprint, 200, body)
            return 200, body

    # ══════════════════════════════════════════════════════════════════
    #  ⑤ التسوية (محاكاة إشعار المزوّد) — تطبّق الحالة مرة واحدة
    # ══════════════════════════════════════════════════════════════════

    def apply_settlement(self, event_id, etype, subscription_id,
                         payment_id=None, occurred_at=None):
        """📨 Settlement/webhook — **مرة واحدة** لكل event_id.

        ⛔ نفس event_id تاني ⇒ مافيش أي تغيير في الحالة (duplicate=True).
        ⛔ نفس الدفعة في event_id مختلف ⇒ مافيش تمديد تاني للفترة.
        """
        event_id = str(event_id or "").strip()[:120]
        if not event_id:
            raise SubscriptionError(400, "لازم معرّف حدث", "no_event_id")
        etype = str(etype or "").strip()
        allowed = ("payment.succeeded", "payment.failed", "refund.succeeded",
                   "subscription.expired", "subscription.canceled")
        if etype not in allowed:
            raise SubscriptionError(400, "نوع الحدث مش معروف", "bad_event_type",
                                    {"type": etype})
        with self.store.lock:
            events = self.store.read("settlement")
            for ev in events:
                if str(ev.get("event_id") or "") == event_id:
                    body = {"ok": True, "applied": False, "duplicate": True,
                            "event_id": event_id,
                            "message": "الحدث ده اتطبّق قبل كده — مافيش تغيير."}
                    return 200, body
            sub = None
            for s in self._subs():
                if str(s.get("id") or "") == str(subscription_id or ""):
                    sub = s
                    break
            if sub is None:
                raise SubscriptionError(404, "مافيش اشتراك للحدث ده",
                                        "no_subscription")
            now = self.clock()
            applied = False
            reason = ""
            pid = str(payment_id or "")
            if etype == "payment.succeeded":
                # ⛔⛔⛔ تطبيق مرة واحدة: لو الاشتراك نشط أصلاً أو الدفعة
                #    دي اتطبّقت قبل ⇒ متغيّرش حاجة ومافيش تمديد تاني.
                if sub.get("status") == "active" or sub.get("activated_payment_id") == pid:
                    applied = False
                    reason = "already_applied"
                else:
                    self._activate(sub, pid or sub.get("payment_id") or "",
                                   int(sub.get("period_days") or 30), now)
                    applied = True
            elif etype == "payment.failed":
                sub["status"] = "failed"
                sub["failure_reason"] = "provider_reported_failure"
                sub["period_end"] = 0
                sub["activated_payment_id"] = ""
                sub["updated_at"] = now
                applied = True
            elif etype == "refund.succeeded":
                sub["status"] = "refunded"
                sub["period_end"] = 0
                sub["ended_reason"] = "refunded"
                sub["updated_at"] = now
                applied = True
            elif etype == "subscription.expired":
                sub["status"] = "expired"
                sub["ended_reason"] = "provider_reported_expiry"
                sub["updated_at"] = now
                applied = True
            elif etype == "subscription.canceled":
                sub["status"] = "canceled"
                sub["period_end"] = 0
                sub["ended_reason"] = "provider_reported_cancel"
                sub["updated_at"] = now
                applied = True
            self._replace_sub(self._subs(), sub)
            events.append({
                "event_id": event_id,
                "type": etype,
                "subscription_id": str(subscription_id or ""),
                "payment_id": pid,
                "uid": str(sub.get("uid") or ""),
                "applied": applied,
                "reason": reason,
                "at": now,
                "occurred_at": int(occurred_at or now),
            })
            self.store.write("settlement", events)
            body = {"ok": True, "applied": applied, "duplicate": False,
                    "event_id": event_id, "type": etype,
                    "subscription": dict(sub),
                    "entitlements": self.entitlements_for(sub.get("uid"), now),
                    "message": "الحدث اتطبّق." if applied
                               else "مافيش تغيير (الحدث متكرر أو الحالة اتغيّرت قبله)."}
            return 200, body

    # ══════════════════════════════════════════════════════════════════
    #  ⑥ الحالة والصلاحيات
    # ══════════════════════════════════════════════════════════════════

    def entitlements_for(self, uid, now=None):
        """🎯 صلاحيات المستخدم — من الاشتراك النشط بس.

        ⛔ مافيش اشتراك نشط ⇒ صلاحيات الباقة المجانية (fail-closed).
        """
        now = now or self.clock()
        active = self._active_subscription(uid, now)
        if active:
            plan = str(active.get("plan") or "")
            ent = self.entitlements_of(plan)
            return {
                "plan": plan,
                "source": "subscription",
                "subscription_id": str(active.get("id") or ""),
                "status": "active",
                "period_end": int(active.get("period_end") or 0),
                "entitlements": ent,
            }
        default_plan = str(self.plans().get("default_plan") or "free")
        return {
            "plan": default_plan,
            "source": "default",
            "subscription_id": "",
            "status": "none",
            "period_end": 0,
            "entitlements": self.entitlements_of(default_plan),
        }

    def status_of(self, uid, now=None):
        """📊 حالة اشتراك المستخدم (للواجهة)."""
        now = now or self.clock()
        uid = str(uid or "")
        self._expire_due(now)
        subs = [s for s in self._subs() if str(s.get("uid") or "") == uid]
        subs.sort(key=lambda s: int(s.get("created_at") or 0), reverse=True)
        active = self._active_subscription(uid, now)
        payments = [p for p in self.store.read("payments")
                    if str(p.get("uid") or "") == uid]
        payments.sort(key=lambda p: int(p.get("created_at") or 0), reverse=True)
        tickets = [t for t in self.store.read("support")
                   if str(t.get("uid") or "") == uid
                   and str(t.get("status") or "") == "open"]
        ent = self.entitlements_for(uid, now)
        return {
            "uid": uid,
            "plan": ent["plan"],
            "status": ("active" if active else
                       (subs[0].get("status") if subs else "none")),
            "subscription": dict(active) if active else None,
            "subscriptions": [dict(s) for s in subs],
            "entitlements": ent["entitlements"],
            "entitlements_source": ent["source"],
            "period_end": int(active.get("period_end") or 0) if active else 0,
            "days_left": (max(0, int((int(active.get("period_end") or 0) - now)
                                      / 86400.0)) if active else 0),
            "last_payment": dict(payments[0]) if payments else None,
            "payments_count": len(payments),
            "support_open": len(tickets),
        }

    def gate(self, uid, resource, count=0, now=None):
        """🚦 بوابة الصلاحيات — بتحدد المستخدم يشوف كام."""
        now = now or self.clock()
        ent = self.entitlements_for(uid, now)
        limits = ent["entitlements"]
        res = str(resource or "").strip().lower()
        if res == "realview":
            allowed = bool(limits.get("realview"))
            return {"allowed": allowed, "resource": res,
                    "limit": 1 if allowed else 0,
                    "plan": ent["plan"], "entitlements": limits}
        key = {"opportunities": "max_opportunities",
               "alerts": "max_alerts",
               "watchlist": "max_watchlist"}.get(res)
        if key is None:
            raise SubscriptionError(400, "المورد ده مش معروف", "bad_resource")
        limit = int(limits.get(key) or 0)
        try:
            used = int(count or 0)
        except Exception:
            used = 0
        return {"allowed": used <= limit, "resource": res, "limit": limit,
                "used": used, "remaining": max(0, limit - used),
                "plan": ent["plan"], "entitlements": limits}

    # ══════════════════════════════════════════════════════════════════
    #  ⑦ الدعم الفني
    # ══════════════════════════════════════════════════════════════════

    def support_templates(self):
        return {k: dict(v) for k, v in SUPPORT_TEMPLATES.items()}

    def support_render(self, template_id, reference="", plan="", message="",
                       subject=""):
        """📄 يبني نص الرسالة من القالب (بدون أي بيانات مستخدم حقيقية)."""
        tpl = SUPPORT_TEMPLATES.get(str(template_id or "general"))
        if tpl is None:
            tpl = SUPPORT_TEMPLATES["general"]
        body = tpl.get("body") or ""
        try:
            body = body.format(reference=str(reference or "-")[:60],
                               plan=str(plan or "-")[:40],
                               message=str(message or "-")[:400],
                               subject=str(subject or "-")[:120])
        except Exception:
            body = tpl.get("body") or ""
        return {"template_id": str(template_id or "general"),
                "title": tpl.get("title") or "",
                "body": body}

    def support_create(self, uid, subject, message, template_id="general",
                       reference=""):
        """🎧 تذكرة دعم — بتتسجّل في السجل (مع نص القالب)."""
        uid = str(uid or "").strip()
        if not uid:
            raise SubscriptionError(400, "لازم حساب مسجّل", "no_user")
        msg = str(message or "").strip()[:2000]
        if not msg:
            raise SubscriptionError(400, "لازم تكتب رسالة", "empty_message")
        rendered = self.support_render(template_id, reference, "", msg, subject)
        now = self.clock()
        tickets = self.store.read("support")
        rec = {
            "id": _rid("tkt"),
            "uid": uid,
            "template_id": rendered["template_id"],
            "subject": str(subject or rendered["title"])[:200],
            "message": msg,
            "body": rendered["body"],
            "reference": str(reference or "")[:60],
            "status": "open",
            "created_at": now,
            "closed_at": 0,
        }
        tickets.append(rec)
        if not self.store.write("support", tickets):
            raise SubscriptionError(503, "فشل حفظ تذكرة الدعم", "store_failed")
        return rec

    def support_list(self, limit=100, status=""):
        tickets = self.store.read("support")
        if status:
            tickets = [t for t in tickets
                       if str(t.get("status") or "") == str(status)]
        tickets.sort(key=lambda t: int(t.get("created_at") or 0), reverse=True)
        try:
            lim = int(limit or 100)
        except Exception:
            lim = 100
        return tickets[:max(1, min(lim, 500))]

    # ══════════════════════════════════════════════════════════════════
    #  ⑧ الحذف — بيانات الاشتراك + المحفظة + التنبيهات
    # ══════════════════════════════════════════════════════════════════

    def purge_user_data(self, uid, now=None):
        """🗑 حذف كل بيانات المستخدم من مخزن الاشتراكات.

        ⛔ بيمسح: الاشتراكات · المدفوعات · محفظة المعاملات · تذاكر الدعم ·
           مفاتيح التفرّد · أحداث التسوية.
        📌 بيسيب **إيصال حذف** بس: هاش المعرّف + الوقت + العدادات
           (من غير بريد ولا اسم ولا باقة ولا مبلغ).
        """
        uid = str(uid or "").strip()
        if not uid:
            raise SubscriptionError(400, "لازم معرّف مستخدم", "no_user")
        now = now or self.clock()
        removed = {}
        with self.store.lock:
            for name in ("subscriptions", "payments", "wallet", "support"):
                items = self.store.read(name)
                kept = [x for x in items if str(x.get("uid") or "") != uid]
                removed[name] = len(items) - len(kept)
                if removed[name]:
                    self.store.write(name, kept)
            idem = self.store.read("idempotency")
            ikeys = [k for k, v in idem.items()
                     if str((v or {}).get("uid") or "") == uid]
            removed["idempotency"] = len(ikeys)
            for k in ikeys:
                idem.pop(k, None)
            if ikeys:
                self.store.write("idempotency", idem)
            events = self.store.read("settlement")
            kept_ev = [e for e in events if str(e.get("uid") or "") != uid]
            removed["settlement"] = len(events) - len(kept_ev)
            if removed["settlement"]:
                self.store.write("settlement", kept_ev)
            receipt = {
                "uid_hash": hashlib.sha256(uid.encode("utf-8")).hexdigest(),
                "deleted_at": now,
                "removed": removed,
                "policy": "r26-privacy-v1",
            }
            receipts = self.store.read("receipts")
            receipts.append(receipt)
            self.store.write("receipts", receipts)
        return receipt

    def deletion_receipts(self, limit=100):
        receipts = self.store.read("receipts")
        receipts.sort(key=lambda r: int(r.get("deleted_at") or 0), reverse=True)
        try:
            lim = int(limit or 100)
        except Exception:
            lim = 100
        return receipts[:max(1, min(lim, 500))]

    # ══════════════════════════════════════════════════════════════════
    #  ⑨ الاحتفاظ والتنظيف الدوري
    # ══════════════════════════════════════════════════════════════════

    def sweep(self, now=None):
        """🧹 تنظيف دوري — متسق مع docs/privacy_and_retention.md.

        📌 بيشيل: مفاتيح التفرّد المنتهية · المدفوعات القديمة · الاشتراكات
           المنتهية · أحداث التسوية · التذاكر المغلقة · إيصالات الحذف.
        📌 وبيحوّل سلة الدفع المعلّقة القديمة لحالة expired.
        """
        now = now or self.clock()
        removed = {}
        with self.store.lock:
            idem = self.store.read("idempotency")
            old_keys = [k for k, v in idem.items()
                        if _age_days(v, now) > RETENTION["idempotency_days"]]
            removed["idempotency"] = len(old_keys)
            for k in old_keys:
                idem.pop(k, None)
            if old_keys:
                self.store.write("idempotency", idem)

            payments = self.store.read("payments")
            kept_p = []
            removed_p = 0
            for p in payments:
                days = RETENTION["payment_days"]
                if str(p.get("status") or "") in ("declined", "provider_down",
                                                  "timeout", "failed"):
                    days = RETENTION["failed_payment_days"]
                if _age_days(p, now) > days:
                    removed_p += 1
                    continue
                kept_p.append(p)
            removed["payments"] = removed_p
            if removed_p:
                self.store.write("payments", kept_p)

            subs = self._subs()
            kept_s = []
            removed_s = 0
            expired_pending = 0
            for s in subs:
                st = str(s.get("status") or "")
                if st == "pending" and _age_days(s, now) > RETENTION["pending_checkout_days"]:
                    s["status"] = "expired"
                    s["ended_reason"] = "checkout_expired"
                    s["ended_at"] = now
                    expired_pending += 1
                if st in ("expired", "canceled", "refunded", "superseded") \
                        and _age_days(s, now) > RETENTION["subscription_days"]:
                    removed_s += 1
                    continue
                kept_s.append(s)
            removed["subscriptions"] = removed_s
            if removed_s or expired_pending:
                self.store.write("subscriptions", kept_s)

            events = self.store.read("settlement")
            kept_e = [e for e in events
                      if _age_days(e, now) <= RETENTION["settlement_days"]]
            removed["settlement"] = len(events) - len(kept_e)
            if removed["settlement"]:
                self.store.write("settlement", kept_e)

            tickets = self.store.read("support")
            kept_t = []
            removed_t = 0
            for t in tickets:
                closed = str(t.get("status") or "") == "closed"
                if closed and _age_days(t, now) > RETENTION["support_closed_days"]:
                    removed_t += 1
                    continue
                kept_t.append(t)
            removed["support"] = removed_t
            if removed_t:
                self.store.write("support", kept_t)

            receipts = self.store.read("receipts")
            kept_r = [r for r in receipts
                      if _age_days(r, now) <= RETENTION["deletion_receipt_days"]]
            removed["deletion_receipts"] = len(receipts) - len(kept_r)
            if removed["deletion_receipts"]:
                self.store.write("receipts", kept_r)

            wallet = self.store.read("wallet")
            kept_w = [w for w in wallet
                      if _age_days(w, now) <= RETENTION["payment_days"]]
            removed["wallet"] = len(wallet) - len(kept_w)
            if removed["wallet"]:
                self.store.write("wallet", kept_w)
        return {"removed": removed, "at": now, "retention": dict(RETENTION)}

    # ── أدوات داخلية صغيرة ─────────────────────────────────────────────
    def _replace_sub(self, subs, sub):
        """⛔ تستبدل السجل في الذاكرة **وتحفظه** (مافيش تغيير ضائع)."""
        changed = False
        for i, s in enumerate(subs):
            if str(s.get("id") or "") == str(sub.get("id") or ""):
                subs[i] = sub
                changed = True
                break
        if not changed:
            subs.append(sub)
        if not self.store.write("subscriptions", subs):
            raise SubscriptionError(503, "فشل حفظ الاشتراك — من غير تغيير اتحفظ",
                                    "store_failed")
        return changed

    def _update_payment(self, pay):
        payments = self.store.read("payments")
        for i, p in enumerate(payments):
            if str(p.get("id") or "") == str(pay.get("id") or ""):
                payments[i] = pay
                self.store.write("payments", payments)
                return True
        payments.append(pay)
        self.store.write("payments", payments)
        return False

    def _last_successful_payment(self, subscription_id):
        for p in self.store.read("payments"):
            if str(p.get("subscription_id") or "") != str(subscription_id or ""):
                continue
            if str(p.get("status") or "") in ("succeeded", "refunded"):
                return p
        return None

    def provider_stats(self):
        return self.provider.stats()


# ══════════════════════════════════════════════════════════════════════════
#  ⑩ أدوات مساعدة عامة
# ══════════════════════════════════════════════════════════════════════════

def _rid(prefix):
    """🆔 معرّف اصطناعي — مافيش بيانات عميل فيه."""
    raw = "%s|%d|%s" % (prefix, int(time.time() * 1000), os.urandom(6).hex())
    return "%s_%s" % (prefix, hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16])


def _age_days(rec, now):
    """⏱ عمر السجل بالأيام — بيقرأ أي خانة وقت معروفة."""
    rec = rec or {}
    at = 0
    for key in ("created_at", "at", "deleted_at", "closed_at", "updated_at"):
        try:
            val = int(rec.get(key) or 0)
        except Exception:
            val = 0
        if val:
            at = val
            break
    if not at:
        return 0
    return max(0, int((now - at) / 86400.0))


def _fail_status(reason):
    """⛔ ترجمة سبب الفشل ⇐ حالة HTTP (402/503/504)."""
    r = str(reason or "")
    if r == "card_declined":
        return 402
    if r == "provider_timeout":
        return 504
    if r in ("provider_unavailable", "provider_reported_failure"):
        return 503
    return 402


def _fail_message(reason):
    r = str(reason or "")
    if r == "card_declined":
        return "البطاقة اترفضت — الاشتراك ما اتفعّلش."
    if r == "provider_timeout":
        return "المزوّد مردّش في الوقت — الاشتراك ما اتفعّلش."
    if r in ("provider_unavailable", "provider_reported_failure"):
        return "المزوّد معطّل — الاشتراك ما اتفعّلش."
    return "فشل الدفع — الاشتراك ما اتفعّلش."


def _validate_plan(code, pdef):
    """⛔ تحقق صارم من ملف الباقات — مافيش قيم مخترعة."""
    if not isinstance(pdef, dict):
        raise PlanFileError("الباقة %s ناقصة" % code)
    if not str(pdef.get("name") or "").strip():
        raise PlanFileError("الباقة %s بلا اسم" % code)
    ent = pdef.get("entitlements")
    if not isinstance(ent, dict) or not ent:
        raise PlanFileError("الباقة %s بلا صلاحيات" % code)
    for key in ("max_opportunities", "max_alerts", "max_watchlist"):
        try:
            if int(ent.get(key)) < 0:
                raise ValueError
        except Exception:
            raise PlanFileError("الباقة %s: صلاحية %s غير صالحة" % (code, key))
    for key in ("realview", "export", "api_access"):
        if key not in ent or not isinstance(ent.get(key), bool):
            raise PlanFileError("الباقة %s: صلاحية %s غير صالحة" % (code, key))
    periods = pdef.get("periods")
    if not isinstance(periods, list) or not periods:
        raise PlanFileError("الباقة %s بلا فترات" % code)
    for pr in periods:
        if not isinstance(pr, dict):
            raise PlanFileError("الباقة %s: فترة غير صالحة" % code)
        try:
            if int(pr.get("days")) <= 0 or float(pr.get("price")) < 0:
                raise ValueError
        except Exception:
            raise PlanFileError("الباقة %s: سعر أو مدة غير صالحة" % code)


def _default_data_dir():
    d = str(os.environ.get(ENV_DATA_DIR, "") or "").strip()
    if d:
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".subs_probe"
            probe.write_text("1", encoding="utf-8")
            probe.unlink()
            return p
        except Exception:
            return HERE
    return HERE


def _plans_path():
    env = str(os.environ.get(ENV_PLANS_FILE, "") or "").strip()
    if env:
        return Path(env)
    return HERE / "data" / PLAN_FILE_NAME


_DEFAULT = {}


def get_default(base_dir=None, plans_path=None):
    """♻️ نسخة واحدة مشتركة (مهم: عدّادات المزوّد لازم تبقى ثابتة)."""
    key = str(base_dir or "") + "|" + str(plans_path or "")
    if key not in _DEFAULT:
        _DEFAULT[key] = Billing(base_dir=base_dir, plans_path=plans_path)
    return _DEFAULT[key]
