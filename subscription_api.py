# -*- coding: utf-8 -*-
"""
🌐 الجولة ٢٦ (R26) — واجهة API لنظام الاشتراكات
==================================================
📌 المسارات (كلها تحت /api/billing — منفصلة عن /api/subscriptions القديمة):

   GET  /api/billing/plans · كتالوج الباقات (عام)
   GET  /api/billing/me · حالة اشتراك المستخدم (تسجيل دخول)
   GET  /api/billing/entitlements · صلاحيات المستخدم (تسجيل دخول)
   GET  /api/billing/opportunities · الفرص المسموح بها حسب الباقة
   GET  /api/billing/payments · سجل مدفوعات المستخدم (تسجيل دخول)
   POST /api/billing/subscribe · تسجيل اشتراك (مفتاح تفرّد إجباري)
   POST /api/billing/renew · تجديد (مفتاح تفرّد إجباري)
   POST /api/billing/cancel · إلغاء
   POST /api/billing/refund · استرداد (مفتاح تفرّد إجباري)
   POST /api/billing/settlement · محاكاة إشعار المزوّد (أدمن)
   GET  /api/billing/support · سجل تذاكر الدعم (أدمن)
   POST /api/billing/support · إنشاء تذكرة دعم (تسجيل دخول)
   GET  /api/billing/support/template · قوالب رسائل الدعم (عام)
   POST /api/billing/retention/sweep · تنظيف دوري (أدمن)

⛔⛔⛔ قواعد الجولة ٢٦ (هارد) ⬇️ ⬇️ ⬇️
   ⛔ المزوّد **صناعي** — محاكاة محلية، مافيش شبكة ولا تحصيل حقيقي.
   ⛔ مافيش أسرار ولا أرقام بطاقات ولا مفاتيح API.
   ⛔ الكتابة (POST) بتطلب مفتاح تفرّد ⇒ تكرار الطلب ما يكرّرش التحصيل.
   ⛔ المسارات المحمية بتتأكد من التوكن (تسجيل دخول) أو توكن الأدمن.
   ⛔ مافيش تعديل على أوزان المحرك ولا حدود القبول ولا سياسة الاستثمار.
   ⛔ fail-soft: أي خطأ في التسجيل ما يوقعش السيرفر.

📌 المسارات المحمية بـ OCTA_ADMIN_TOKEN (زي /api/subscriptions/log):
   /api/billing/settlement · /api/billing/support (GET) ·
   /api/billing/retention/sweep
"""

import hmac
import os
import time

ENV_ADMIN_TOKEN = "OCTA_ADMIN_TOKEN"


def register(app, require_user=None, billing=None, opportunities_getter=None,
             alerts_counter=None):
    """🔌 تسجيل المسارات — fail-soft (بيبلع أي خطأ في التسجيل)."""

    from flask import jsonify, request

    import subscription_core as _core

    engine = billing if billing is not None else _core.get_default()

    # ── أدوات داخلية ────────────────────────────────────────────────────
    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    def _uid_of(user):
        if not isinstance(user, dict):
            return ""
        return str(user.get("id") or user.get("uid") or "")

    def _admin_ok():
        want = str(os.environ.get(ENV_ADMIN_TOKEN, "") or "").strip()
        got = str(request.headers.get("X-OCTA-Admin", "") or "").strip()
        if not want or not got:
            return False
        return hmac.compare_digest(got.encode("utf-8", "replace"),
                                   want.encode("utf-8", "replace"))

    def _idem_key():
        """🔑 مفتاح التفرّد — من الترويسة أو من Body (إجباري في الكتابة)."""
        key = ""
        try:
            key = str(request.headers.get("Idempotency-Key", "") or "").strip()
        except Exception:
            key = ""
        if not key:
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict):
                key = str(body.get("idempotency_key") or "").strip()
        return key[:80]

    def _body():
        try:
            body = request.get_json(silent=True) or {}
        except Exception:
            body = {}
        return body if isinstance(body, dict) else {}

    def _err(exc):
        """⛔ ترجمة الاستثناء ⇐ رد HTTP (مافيش 500 عشوائي)."""
        if isinstance(exc, _core.SubscriptionError):
            out = {"ok": False, "error": exc.message, "why": exc.why}
            out.update(exc.extra or {})
            return jsonify(out), exc.status
        if isinstance(exc, _core.PlanFileError):
            return jsonify({"ok": False, "error": str(exc),
                            "why": "plans_file_broken"}), 503
        return jsonify({"ok": False, "error": str(exc)[:200],
                        "why": "internal_error"}), 500

    def _need_user():
        """🚪 بوابة تسجيل الدخول."""
        u = _guard()
        if require_user is not None and not u:
            return None, (jsonify({"ok": False, "error": "لازم تسجّل دخول",
                                   "why": "unauthorized"}), 401)
        return u, None

    # ══════════════════════════════════════════════════════════════════
    #  ① الباقات (عام)
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/plans", methods=["GET"])
    def billing_plans():
        try:
            cat = engine.catalog()
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "plans": cat["plans"],
                        "currency": cat["currency"],
                        "default_plan": cat["default_plan"],
                        "provider": cat["provider"],
                        "provider_note": cat["provider_note"],
                        "version": cat["version"]})

    # ══════════════════════════════════════════════════════════════════
    #  ② حالة الاشتراك + الصلاحيات
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/me", methods=["GET"])
    def billing_me():
        u, fail = _need_user()
        if fail:
            return fail
        try:
            st = engine.status_of(_uid_of(u))
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "subscription": st,
                        "at": time.strftime("%Y-%m-%d %H:%M")})

    @app.route("/api/billing/entitlements", methods=["GET"])
    def billing_entitlements():
        u, fail = _need_user()
        if fail:
            return fail
        uid = _uid_of(u)
        try:
            ent = engine.entitlements_for(uid)
            out = {"ok": True, "plan": ent["plan"], "source": ent["source"],
                   "status": ent["status"],
                   "subscription_id": ent["subscription_id"],
                   "period_end": ent["period_end"],
                   "entitlements": ent["entitlements"]}
            if alerts_counter is not None:
                try:
                    used = int(alerts_counter(u) or 0)
                except Exception:
                    used = 0
                out["alerts_used"] = used
                out["alerts_limit"] = int(
                    ent["entitlements"].get("max_alerts") or 0)
                out["alerts_allowed"] = used <= out["alerts_limit"]
            return jsonify(out)
        except Exception as e:
            return _err(e)

    @app.route("/api/billing/opportunities", methods=["GET"])
    def billing_opportunities():
        """🚦 الفرص اللي المستخدم مسموح له يشوفها حسب باقته."""
        u, fail = _need_user()
        if fail:
            return fail
        uid = _uid_of(u)
        try:
            gate = engine.gate(uid, "opportunities", 0)
            rows = []
            if opportunities_getter is not None:
                try:
                    rows = list(opportunities_getter() or [])
                except Exception:
                    rows = []
            limit = int(gate.get("limit") or 0)
            items = rows[:limit] if limit >= 0 else rows
            return jsonify({
                "ok": True,
                "plan": gate.get("plan"),
                "limit": limit,
                "total_available": len(rows),
                "returned": len(items),
                "items": items,
            })
        except Exception as e:
            return _err(e)

    @app.route("/api/billing/payments", methods=["GET"])
    def billing_payments():
        u, fail = _need_user()
        if fail:
            return fail
        uid = _uid_of(u)
        try:
            items = [p for p in engine.store.read("payments")
                     if str(p.get("uid") or "") == uid]
            items.sort(key=lambda p: int(p.get("created_at") or 0), reverse=True)
            try:
                lim = int(request.args.get("limit") or 50)
            except Exception:
                lim = 50
            items = items[:max(1, min(lim, 200))]
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "items": items, "count": len(items)})

    # ══════════════════════════════════════════════════════════════════
    #  ③ دورة الاشتراك
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/subscribe", methods=["POST"])
    def billing_subscribe():
        u, fail = _need_user()
        if fail:
            return fail
        body = _body()
        try:
            status, out = engine.subscribe(
                _uid_of(u),
                body.get("plan"),
                _idem_key(),
                token=str(body.get("payment_token") or "tok_mock_ok"),
                period=str(body.get("period") or "monthly"),
                defer_settlement=bool(body.get("defer_settlement")),
            )
        except Exception as e:
            return _err(e)
        return jsonify(out), status

    @app.route("/api/billing/renew", methods=["POST"])
    def billing_renew():
        u, fail = _need_user()
        if fail:
            return fail
        body = _body()
        try:
            status, out = engine.renew(
                _uid_of(u),
                _idem_key(),
                token=str(body.get("payment_token") or "tok_mock_ok"),
                subscription_id=body.get("subscription_id"),
                period=body.get("period"),
            )
        except Exception as e:
            return _err(e)
        return jsonify(out), status

    @app.route("/api/billing/cancel", methods=["POST"])
    def billing_cancel():
        u, fail = _need_user()
        if fail:
            return fail
        body = _body()
        at_end = body.get("at_period_end", True)
        try:
            status, out = engine.cancel(
                _uid_of(u),
                subscription_id=body.get("subscription_id"),
                at_period_end=bool(at_end),
                reason=str(body.get("reason") or ""),
            )
        except Exception as e:
            return _err(e)
        return jsonify(out), status

    @app.route("/api/billing/refund", methods=["POST"])
    def billing_refund():
        u, fail = _need_user()
        if fail:
            return fail
        body = _body()
        try:
            status, out = engine.refund(
                _uid_of(u),
                _idem_key(),
                subscription_id=body.get("subscription_id"),
                reason=str(body.get("reason") or ""),
            )
        except Exception as e:
            return _err(e)
        return jsonify(out), status

    # ══════════════════════════════════════════════════════════════════
    #  ④ التسوية (محاكاة إشعار المزوّد) — أدمن
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/settlement", methods=["POST"])
    def billing_settlement():
        if not _admin_ok():
            return jsonify({"ok": False, "error": "المسار ده محمي",
                            "why": "admin_required"}), 401
        body = _body()
        try:
            status, out = engine.apply_settlement(
                body.get("event_id"),
                body.get("type"),
                body.get("subscription_id"),
                payment_id=body.get("payment_id"),
                occurred_at=body.get("occurred_at"),
            )
        except Exception as e:
            return _err(e)
        return jsonify(out), status

    # ══════════════════════════════════════════════════════════════════
    #  ⑤ الدعم الفني
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/support/template", methods=["GET"])
    def billing_support_template():
        try:
            tpl = engine.support_templates()
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "templates": tpl})

    @app.route("/api/billing/support", methods=["GET", "POST"])
    def billing_support():
        if request.method == "GET":
            if not _admin_ok():
                return jsonify({"ok": False, "error": "المسار ده محمي",
                                "why": "admin_required"}), 401
            try:
                try:
                    lim = int(request.args.get("limit") or 100)
                except Exception:
                    lim = 100
                items = engine.support_list(lim)
            except Exception as e:
                return _err(e)
            return jsonify({"ok": True, "items": items, "count": len(items)})

        u, fail = _need_user()
        if fail:
            return fail
        body = _body()
        try:
            rec = engine.support_create(
                _uid_of(u),
                body.get("subject"),
                body.get("message"),
                template_id=str(body.get("template_id") or "general"),
                reference=str(body.get("reference") or ""),
            )
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "ticket": rec,
                        "at": time.strftime("%Y-%m-%d %H:%M")})

    # ══════════════════════════════════════════════════════════════════
    #  ⑥ الاحتفاظ والتنظيف
    # ══════════════════════════════════════════════════════════════════
    @app.route("/api/billing/retention/sweep", methods=["POST"])
    def billing_retention_sweep():
        if not _admin_ok():
            return jsonify({"ok": False, "error": "المسار ده محمي",
                            "why": "admin_required"}), 401
        try:
            out = engine.sweep()
        except Exception as e:
            return _err(e)
        return jsonify({"ok": True, "sweep": out,
                        "at": time.strftime("%Y-%m-%d %H:%M")})

    return True
