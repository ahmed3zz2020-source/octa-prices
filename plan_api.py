# -*- coding: utf-8 -*-
"""💳 مسارات الاشتراكات — «اشتراكي» + التفعيل (أدمن) (٢٨ أكتوبر ٢٠٢٦)

  GET  /api/subscriptions/me      → حالة اشتراك المستخدم (مسجّل)
  GET  /api/subscriptions/log     → سجل المدفوعات (أدمن)
  POST /api/subscriptions/activate → تفعيل/تجديد باقة (أدمن)

⛔ fail-soft: أي خطأ في التسجيل ما يوقعش السيرفر.
"""
import hmac
import os
import time


def register(app, require_user=None, status_fn=None, activate_fn=None,
             log_fn=None):
    from flask import jsonify, request

    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    def _admin_ok():
        want = str(os.environ.get("OCTA_ADMIN_TOKEN", "") or "").strip()
        got = str(request.headers.get("X-OCTA-Admin", "") or "").strip()
        if not want or not got:
            return False
        return hmac.compare_digest(got.encode("utf-8", "replace"),
                                   want.encode("utf-8", "replace"))

    @app.route("/api/subscriptions/me", methods=["GET"])
    def subs_me():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        try:
            st = status_fn(u) if status_fn else {}
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 503
        return jsonify({"ok": True, "subscription": st or {}})

    @app.route("/api/subscriptions/log", methods=["GET"])
    def subs_log():
        if not _admin_ok():
            return jsonify({"ok": False, "error": "المسار ده محمي"}), 401
        try:
            lim = int(request.args.get("limit") or 100)
        except Exception:
            lim = 100
        items = log_fn(lim) if log_fn else []
        return jsonify({"ok": True, "items": items, "count": len(items)})

    @app.route("/api/subscriptions/activate", methods=["POST"])
    def subs_activate():
        if not _admin_ok():
            return jsonify({"ok": False, "error": "المسار ده محمي"}), 401
        body = request.get_json(silent=True) or {}
        who = str(body.get("email") or body.get("uid") or "").strip()
        plan = str(body.get("plan") or "pro").strip().lower()
        if plan != "pro":
            return jsonify({"ok": False, "error": "plan لازم يكون pro"}), 400
        try:
            days = int(body.get("days") or 30)
        except Exception:
            days = 30
        if days <= 0:
            return jsonify({"ok": False, "error": "لازم عدد أيام"}), 400
        try:
            price = float(body.get("price") or 0)
        except Exception:
            price = 0.0
        method = str(body.get("method") or "admin")
        note = str(body.get("note") or "")
        if not who:
            return jsonify({"ok": False, "error": "لازم email أو uid"}), 400
        if not activate_fn:
            return jsonify({"ok": False, "error": "التفعيل غير متاح"}), 501
        try:
            ok, msg, rec = activate_fn(who, plan, days, price, method, note)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500
        if not ok:
            return jsonify({"ok": False, "error": msg or "التفعيل فشل"}), 404
        return jsonify({"ok": True, "subscription": rec or {},
                        "at": time.strftime("%Y-%m-%d %H:%M")})

    return True
