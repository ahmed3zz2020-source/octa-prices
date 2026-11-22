#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 بيئة Staging معزولة لـOCTA — بيانات وهمية ١٠٠٪

⛔⛔⛔ قواعد صارمة (ما تتكسرش) ⬇️ ⬇️
  ⛔ ⬇️ مافيش أي اتصال بالإنتاج ⬇️ ⬇️ (ولا Railway · ولا Cloudflare · ولا Telegram)
  ⛔ ⬇️ مافيش أي سر إنتاج ⬇️ ⬇️ (الأسرار دي بتتولّد هنا لحظياً)
  ⛔ ⬇️ مافيش أي بيانات مستخدمين حقيقية ⬇️ ⬇️ (كل الحسابات وهمية)
  ⛔ ⬇️ البيانات في مجلد منفصل ⬇️ ⬇️ (STAGE_DIR — مش /data)
  ⛔ ⬇️ الإيميل = Mock ⬇️ ⬇️ (يتكتب في ملف — مفيش إرسال حقيقي)

📌 التشغيل:
   python3 tools/staging/run_staging.py            # بيشتغل على 8099
   STAGE_PORT=9000 python3 tools/staging/run_staging.py
"""
import os
import sys
import json
import time
import secrets
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # ⭐ R32 · أداة الكتابة ⭐
import safe_write as _sw   # ⭐ R32 · كتابة ذرّية ⭐

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent          # /workspace/repos/octa-prices
sys.path.insert(0, str(REPO))

STAGE_DIR = Path(os.environ.get("STAGE_DIR", "/workspace/.staging"))
STAGE_DIR.mkdir(parents=True, exist_ok=True)
PORT = int(os.environ.get("STAGE_PORT", "8099"))

# ══════════════════════════════════════════════════════════════════
#  ⛔ أسرار خاصة بالاختبار — بتتولّد هنا (مش من أي مكان تاني)
# ══════════════════════════════════════════════════════════════════
# ⛔⛔⛔ الأسرار لازم **ثابتة** بين مرات التشغيل ⬇️ ⬇️
# 📌 ⬇️ السبب: ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ لو تولّدت من جديد ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ سر Cloudflare (المتسجّل في عامل المعاينة) ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ بقى قديم ⇒ 403 على كل طلب ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ الفحص الحيّ يفشل والنشر يتراجع ⬇️ ⬇️ ⬇️
# ⛔ لو تولّدت من جديد ⇒ سر الـCloudflare (اللي متسجّل في عامل
# ⛔ المعاينة) بقى قديم ⇒ 403 على كل طلب ⬇️ ⇒ الفحص الحيّ يفشل ⬇️
# ⛔ الجولة ٢٥ (R25 · المرحلة ٩) — مسار ملف الأسرار قابل للتوجيه ⭐
# 📌 السبب: كل تشغيل معزول لازم يكون ليه أسرار ** synthetics خاصة بيه** ⭐
# 📌 ⇒ ما نكتبش فوق ملف الأسرار المشترك ⭐ (عزل كامل ⭐)
SECRETS_FILE = Path(os.environ.get(
    "STAGE_SECRETS_FILE", "/workspace/.staging-secrets.json"))
try:
    _prev = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
except Exception:
    _prev = {}
SECRET = os.environ.get("STAGE_TOKEN_SECRET") or _prev.get("secret") or ("STG-" + secrets.token_urlsafe(32))
PROXY = os.environ.get("STAGE_PROXY_SECRET") or _prev.get("proxy") or ("PRX-" + secrets.token_urlsafe(32))
PEPPER = _prev.get("pepper") or ("STG-" + secrets.token_urlsafe(16))
ADMIN = os.environ.get("STAGE_ADMIN_TOKEN") or _prev.get("admin") or ("ADM-" + secrets.token_urlsafe(24))
try:
    SECRETS_FILE.write_text(json.dumps(
        {"secret": SECRET, "proxy": PROXY, "pepper": PEPPER, "admin": ADMIN},
        ensure_ascii=False, indent=2), encoding="utf-8")
except Exception:
    pass

os.environ["OCTA_DATA_DIR"] = str(STAGE_DIR)
os.environ["OCTAD_TOKEN_SECRET"] = SECRET
os.environ["OCTA_PIN_PEPPER"] = PEPPER
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"        # ⛔ staging فقط
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"     # ⛔ البصمة مقفولة
os.environ["OCTA_PROXY_SECRET"] = PROXY
os.environ["OCTA_WARMUP"] = "0"                   # ⛔ مافيش إيقاظ للسيرفر
# 🐞 ١٥ نوفمبر ٢٠٢٦ (دفعة الأمان ٠٢) — ⛔ حدود الطلبات ⬇️
# 📌 ⬇️ الاختبارات بتعمل مئات الطلبات ⬇️ ⬇️
# 📌 ⬇️ ⇒ من غير المعامل ده بتفشل بسبب 429 (مش بسبب عيب أمني) ⬇️ ⬇️
# ⛔ الإنتاج: مافيش متغيّر ⇒ الافتراضي 1 (مافيش تغيير) ⬇️
os.environ.setdefault("OCTA_RATE_MULT", "300")
os.environ["MAIL_ON"] = "0"                       # ⛔ هنعمل mock
# ⛔ توكن أدمن **خاص بالاختبار** (مش إنتاجي) ⬇️
os.environ["OCTA_ADMIN_TOKEN"] = ADMIN

MINI = None
# ⛔ الجولة ٢٥ (R25 · المرحلة ٩) — وضع المصدر ⭐
# 📌 "blocked" (الافتراضي ⭐) ⇒ مافيش أي اتصال ⭐
# 📌 "ok" ⇒ مصدر **اصطناعي** ⭐ (بيانات محسوبة ⭐ مش حقيقية ⭐)
# 📌 ⛔ الاختيار بيتم **قبل** استيراد التطبيق ⭐ (عشان أول تحديث يشوفه ⭐)
SOURCE_MODE = str(os.environ.get("STAGE_SOURCE_MODE", "blocked") or "blocked")
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import net_block  # noqa: E402
try:
    import flask  # noqa: E402
except ImportError:
    # ⛔⛔⛔ بيئة الاختبار المعزولة مافيش فيها `flask` ⬇️ ⬇️ ⬇️
    # 📌 فبنستخدم طبقة النقل المصغّرة (مكتبة قياسية بس ⭐) ⭐
    # 📌 ⛔ الكود اللي بيتنفّذ هو **نفس** `update_prices.py` ⭐
    # 📌 ⛔ وبنقفل الشبكة ⇒ مافيش أي اتصال خارجي ⭐
    # 📌 ⛔ لازم يحصل **قبل** استيراد التطبيق ⭐ (إوّل import ليه flask ⭐)
    sys.path.insert(0, str(HERE))
    import mini_http  # noqa: E402
    MINI = mini_http
    flask = mini_http.install_shims()

# ⛔ الجولة ٢٥ (R25 · المرحلة ٩) — التقاط نسخة الفرص **الحقيقية** ⭐
# 📌 لازم يحصل **قبل** `import update_prices` ⭐
# 📌 (عشان نمسك أول نسخة يبنيها المحرّك الحقيقي ⭐)
HARNESS_ON = str(os.environ.get("STAGE_HARNESS", "0") or "0") == "1"
CAPTURED = {"opp": None, "stocks": None}
if HARNESS_ON:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    try:
        import opp_engine as _oe
        _orig_build = _oe.build_payload

        def _build_capture(stocks, definitions=None, meta=None):
            out = _orig_build(stocks, definitions, meta)
            try:
                if isinstance(out, dict) and out.get("ok") \
                        and CAPTURED.get("opp") is None:
                    CAPTURED["opp"] = json.loads(json.dumps(out,
                                                           ensure_ascii=False))
                    CAPTURED["stocks"] = stocks
            except Exception:
                pass
            return out

        _oe.build_payload = _build_capture
    except Exception as _e:
        print("  ⚠️ harness: %s" % type(_e).__name__, flush=True)

# ⛔ قفل الشبكة ⭐ — **قبل** استيراد التطبيق ⭐
# 📌 (التطبيق بيستورد `requests` وقت الاستيراد ⭐
# 📌  وبيشغّل المهام الخلفية أول ما يستورد ⭐)
# 📌 ⇒ لازم نرقّع `requests` قبله ⭐ عشان نغطّي أول نداء ⭐
# ⛔⛔⛔ **اختياري** ⭐: `STAGE_ISOLATED=1` ⭐
# 📌 السبب ⭐: behaviour أداة الـstaging العادية ما يتغيّرش ⭐
# 📌 (هي بتجيب بيانات حقيقية ⭐) ⭐ ⇒ العزل للاختبارات بس ⭐
if str(os.environ.get("STAGE_ISOLATED", "0") or "0") == "1":
    net_block.set_mode(SOURCE_MODE)
    try:
        import requests as _rq  # noqa: E402,F401
    except Exception:
        pass
    net_block.install()

import update_prices as up  # noqa: E402
import hmac  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  📮 Mock الإيميل — يتكتب في ملف (مفيش إرسال حقيقي)
# ══════════════════════════════════════════════════════════════════
MAIL_FILE = STAGE_DIR / "outbox.jsonl"
# ⛔ الجولة ٢٤ (R24) — الصندوق **بإضافة فقط** (append-only) ⭐
#  📌 قبل كده: الملف كان بيتمسح كل ما السيرفر يقوم ⇐ فلو السيرفر
#  📌 عمل restart في نص الاختبار ⇐ الكود اللي اتسلّم ضاع ⇐
#  📌 والاختبار قفل بـ unlock_expired ⇐ وده مش عيب في الإنتاج ⭐
#  ✅ الحل: ما بنمسحش الملف عند الإقلاع ⇐ والاختبار يقرأ **الجديد**
#  📌 بس (من بعد الطلب اللي طلب الكود) ⇐ فالكود القديم ما يقدرش
#  📌 يخدع أي assertion ⭐
MAIL_SEQ = 0


def _mock_send(to, subject, html):
    """يكتب الرسالة في صندوق البريد المحاكى (سطر واحد · كتابة ذرّية)."""
    global MAIL_SEQ
    MAIL_SEQ += 1
    rec = {"to": to, "subject": subject, "html": html,
           "seq": MAIL_SEQ, "sent_at": int(time.time())}
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        fd = os.open(str(MAIL_FILE),
                     os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            view = memoryview(line)
            while view:
                n = os.write(fd, view)
                view = view[n:]
            try:
                os.fsync(fd)
            except Exception:
                pass
        finally:
            os.close(fd)
    except Exception:
        return False
    return True


up._send_mail = _mock_send
up.MAIL_ON = True


# ══════════════════════════════════════════════════════════════════
#  🔎 نشر بيئة التشغيل — للاختبارات بس (الجولة ٢٤ · R24)
# ══════════════════════════════════════════════════════════════════
#  📌 المشكلة الجذرية (الجولة ٢٤) ⭐
#  📌 الاختبار كان ياخد مسار صندوق البريد ومجلد البيانات من **ملف
#  📌 الإعدادات** (STAGE_CONFIG) ⇐ والسيرفر ياخدهم من **متغيّر
#  📌 البيئة** بتاعه (STAGE_DIR) ⇐ ومفيش حاجة تربط الاتنين ⇐
#  📌 ⇒ لو ملف الإعدادات قديم أو بيوجّه لنسخة تانية ⇐ الكود بيوصل
#  📌 لصندوق mails ما بيقراش ⇐ والاختبار بيفشل بـ unlock_expired ⇐
#  📌 وprobe الملف التالف بيفحص ملف ما السيرفرش بيقراه ⇐ 200 مش 503 ⇐
#  ✅ الحل: السيرفر هو المرجع ⇐ ينشر بيئته الحقيقية هنا ⇐ والاختبار
#  📌 بياخد المسارات من السيرفر نفسه ⇐ مش من ملف ممكن يكون قديم ⭐
#
#  ⛔ المسار ده موجود في **بيئة الـstaging بس** ⇐ الإنتاج مافيشش المسار
#  ⛔ ده خالص (المسار بيتسجّل من الملف ده بس) ⇐
#  ⛔ ومقفول بسر الـproxy (مقارنة constant-time) ⇐
@up.app.route("/__staging__/env", methods=["GET"])
def _staging_env():
    got = str(flask.request.headers.get("X-OCTA-Proxy", "") or "").strip()
    secret = str(getattr(up, "PROXY_SECRET", "") or "").strip()
    if (not secret or not got
            or not hmac.compare_digest(got.encode("utf-8", "replace"),
                                       secret.encode("utf-8", "replace"))):
        return flask.jsonify({
            "ok": False,
            "error": "المسار ده للاختبارات المعزولة بس",
            "why": "proxy_secret_required",
        }), 403
    return flask.jsonify({
        "ok": True,
        "data_dir": str(STAGE_DIR),
        "mailbox": str(MAIL_FILE),
        "mail_on": True,
        "port": PORT,
        "pid": os.getpid(),
        "started_at": int(time.time()),
    })


# ══════════════════════════════════════════════════════════════════
#  📊 لوحة القياس + خطة التنبيه — الجولة ٢٥ (R25 · المرحلة ٩)
# ⛔⛔⛔ **للاختبارات المعزولة بس** ⬇️ ⬇️ ⬇️
# 📌 ⛔ المسار ده مش موجود في الإنتاج ⭐ (مش مسجّل ⭐).
# 📌 ⛔ وهو مقفول بسر البروبزي ⭐ (زي `/__staging__/env` ⭐).
# 📌 ⛔ مافيش أي تفعيل خارجي ⭐ (مافيش بريد ولا تيليجرام ⭐).
# 📌 الهدف: «لوحة قياس» **قابلة للتشغيل والاختبار** ⭐ (AC-34-3 · AC-34-4 ⭐).
# ══════════════════════════════════════════════════════════════════
if str(os.environ.get("STAGE_HARNESS", "0") or "0") == "1":
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from metrics_board import MetricsBoard, AlertPlan, filter_log  # noqa: E402

    BOARD = MetricsBoard(service="octa-prices")
    PLAN = AlertPlan()

    # ⏱️ ساعة صناعية ⭐ — حقن الوقت ⭐ (AC-11-3 ⭐)
    # 📌 ⛔ الحقن بيحصل في **عملية الاختبار المعزولة** ⭐
    # 📌 ⛔ مافيش أي تأثير على الإنتاج ⭐ (المسار ده مش موجود فيه ⭐)
    CLOCK = {"offset": 0.0, "frozen": None, "patched": False}
    _REAL_TIME = time.time
    # ⛔ وقت القاهرة المحقون ⭐ (للتحكم في حالة السوق ⭐)
    CAIRO = {"epoch": None}
    _ORIG_CAIRO = up.cairo_now

    def _patched_cairo_now():
        ep = CAIRO.get("epoch")
        if ep is None:
            return _ORIG_CAIRO()
        try:
            from datetime import datetime as _dt
            from zoneinfo import ZoneInfo
            return _dt.fromtimestamp(float(ep), ZoneInfo("Africa/Cairo"))
        except Exception:
            return _ORIG_CAIRO()

    up.cairo_now = _patched_cairo_now

    def _patched_time():
        """⏱️ الوقت المزاح ⭐ — `frozen` ⇒ وقت ثابت ⭐ · `offset` ⇒ إزاحة ⭐."""
        fz = CLOCK.get("frozen")
        if fz is not None:
            return float(fz)
        return _REAL_TIME() + float(CLOCK.get("offset") or 0.0)

    def _install_clock():
        try:
            if not CLOCK["patched"]:
                time.time = _patched_time      # ⛔ العملية المعزولة بس ⭐
                CLOCK["patched"] = True
        except Exception:
            pass

    def _harness_guard():
        """⛔ نفس حراسة `/__staging__/env` ⭐ — المقارنة constant-time ⭐."""
        got = str(flask.request.headers.get("X-OCTA-Proxy", "") or "").strip()
        secret = str(getattr(up, "PROXY_SECRET", "") or "").strip()
        if (not secret or not got
                or not hmac.compare_digest(got.encode("utf-8", "replace"),
                                           secret.encode("utf-8", "replace"))):
            return flask.jsonify({
                "ok": False,
                "error": "المسار ده للاختبارات المعزولة بس",
                "why": "proxy_secret_required",
            }), 403
        return None

    def _harness_t0():
        try:
            flask.g._octa_r25_t0 = time.perf_counter()
        except Exception:
            pass
        return None

    def _harness_measure(resp):
        try:
            t0 = getattr(flask.g, "_octa_r25_t0", None)
            if t0 is not None:
                BOARD.record(flask.request.path,
                             (time.perf_counter() - t0) * 1000.0,
                             int(getattr(resp, "status_code", 0) or 0))
        except Exception:
            pass
        return resp

    up.app.before_request(_harness_t0)
    up.app.after_request(_harness_measure)

    def _harness_state():
        guard = _harness_guard()
        if guard is not None:
            return guard
        try:
            rss = 0.0
            try:
                import resource
                rss = resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss / 1024.0
            except Exception:
                rss = 0.0
            broken = bool(up._users_store_broken())
            return flask.jsonify({
                "ok": True,
                "pid": os.getpid(),
                "port": PORT,
                "data_dir": str(STAGE_DIR),
                "mailbox": str(MAIL_FILE),
                "users_n": len(up._load_users()),
                "storage_broken": broken,
                "storage_why": up._users_store_broken(),
                "rss_mb": round(rss, 2),
                "started_at": int(time.time()),
            })
        except Exception as exc:
            return flask.jsonify({"ok": False, "error": type(exc).__name__}), 500

    def _harness_metrics():
        guard = _harness_guard()
        if guard is not None:
            return guard
        snap = BOARD.snapshot()
        try:
            rss = 0.0
            try:
                import resource
                rss = resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss / 1024.0
            except Exception:
                rss = 0.0
            extra = {
                "rss_mb": round(rss, 2),
                "ready": True,
                "storage_broken": bool(up._users_store_broken()),
                "mail_down": not bool(getattr(up, "MAIL_ON", False)),
            }
            try:
                extra["data_unavailable"] = (
                    up._DATA_FULL["payload"] is None)
            except Exception:
                extra["data_unavailable"] = True
            fired = PLAN.evaluate(snap, extra=extra)
            BOARD.alerts = fired
            snap["alerts"] = fired
            snap["app"] = extra
        except Exception as exc:
            snap["error"] = type(exc).__name__
        return flask.jsonify(snap)

    def _harness_alerts():
        guard = _harness_guard()
        if guard is not None:
            return guard
        return flask.jsonify({
            "ok": True,
            "limits": dict(PLAN.limits),
            "rules": PLAN.rules(),
            "fired": list(PLAN.fired.values()),
            "history_n": len(PLAN.history),
        })

    def _harness_log():
        guard = _harness_guard()
        if guard is not None:
            return guard
        raw = []
        try:
            for _lf in sorted(STAGE_DIR.glob("server*.log")):
                raw.extend(_lf.read_text(
                    encoding="utf-8", errors="replace").splitlines()[-400:])
        except Exception:
            raw = []
        clean, hidden = filter_log(raw)
        return flask.jsonify({"ok": True, "lines": clean[-120:],
                              "hidden": hidden})

    def _harness_reset():
        guard = _harness_guard()
        if guard is not None:
            return guard
        BOARD.reset()
        PLAN.history = []
        PLAN.fired = {}
        return flask.jsonify({"ok": True})

    # ── ⏱️ الساعة الصناعية ⭐ ──
    def _harness_clock():
        """⏱️ حقن الوقت ⭐ — GET للقراءة · POST للضبط ⭐."""
        guard = _harness_guard()
        if guard is not None:
            return guard
        if flask.request.method == "POST":
            body = flask.request.get_json(silent=True) or {}
            try:
                if body.get("frozen") is not None:
                    CLOCK["frozen"] = float(body.get("frozen"))
                else:
                    CLOCK["frozen"] = None
                CLOCK["offset"] = float(body.get("offset") or 0.0)
                CAIRO["epoch"] = (float(body["cairo_epoch"])
                                  if body.get("cairo_epoch") is not None
                                  else None)
                _install_clock()
            except Exception as exc:
                return flask.jsonify({"ok": False,
                                      "error": type(exc).__name__}), 400
        try:
            import opp_engine as _oe
            limits = {"open": _oe.FRESH_MAX_AGE_OPEN,
                      "closed": _oe.FRESH_MAX_AGE_CLOSED,
                      "min_coverage": _oe.FRESH_MIN_COVERAGE}
        except Exception:
            limits = {}
        return flask.jsonify({
            "ok": True,
            "now": _patched_time(),
            "real_now": _REAL_TIME(),
            "offset": CLOCK["offset"],
            "frozen": CLOCK["frozen"],
            "patched": CLOCK["patched"],
            "cairo_epoch": CAIRO["epoch"],
            "market_phase": up.market_phase(),
            "fresh_limits": limits,
        })

    # ── 🌱 بذر نسخة الفرص (لاختبار الساعة) ⭐ ──
    def _harness_opp():
        """🌱 بذر/قراءة نسخة الفرص ⭐ — بعمر متحكم ⭐."""
        guard = _harness_guard()
        if guard is not None:
            return guard
        cur = up.LIVE_DATA.get("opp")
        if flask.request.method == "POST":
            body = flask.request.get_json(silent=True) or {}
            age = body.get("age_seconds")
            src = CAPTURED.get("opp")
            if not isinstance(src, dict) or not src.get("ok"):
                return flask.jsonify({"ok": False,
                                      "error": "مافيش نسخة جاهزة للبذر",
                                      "why": "no_source_payload"}), 409
            payload = json.loads(json.dumps(src, ensure_ascii=False))
            ts = _patched_time() - float(age or 0)
            payload["last_success_at"] = ts
            payload["generated_at"] = ts
            payload["market_phase"] = up.market_phase()
            payload["freshness"] = "fresh"
            payload["data_state"] = "fresh"
            payload["age_seconds"] = 0
            df = dict(payload.get("data_freshness") or {})
            df["last_success_at"] = ts
            df["age_seconds"] = 0
            df["freshness"] = "fresh"
            df["data_state"] = "fresh"
            df["is_fresh"] = True
            df["is_stale"] = False
            payload["data_freshness"] = df
            up.LIVE_DATA["opp"] = payload
            cur = payload
        lists = cur.get("lists") if isinstance(cur, dict) else None
        if not isinstance(lists, dict):
            lists = {}
        return flask.jsonify({
            "ok": True,
            "has_payload": bool(isinstance(cur, dict) and cur.get("ok")),
            "captured": bool(CAPTURED.get("opp")),
            "freshness": (cur or {}).get("freshness"),
            "data_state": (cur or {}).get("data_state"),
            "last_success_at": (cur or {}).get("last_success_at"),
            "age_seconds": (cur or {}).get("age_seconds"),
            "market_phase": (cur or {}).get("market_phase"),
            "lists_n": len(lists),
            "lists": sorted(list(lists.keys())),
        })

    up.app.route("/__harness__/state")(  _harness_state)
    up.app.route("/__harness__/metrics")(_harness_metrics)
    up.app.route("/__harness__/alerts")( _harness_alerts)
    up.app.route("/__harness__/log")(    _harness_log)
    up.app.route("/__harness__/reset")(  _harness_reset)
    up.app.route("/__harness__/clock", methods=["GET", "POST"])(_harness_clock)
    up.app.route("/__harness__/opp", methods=["GET", "POST"])(_harness_opp)

    # ── 💥 حقن الأعطال (متدرّج) ⭐ ──
    # ⛔⛔⛔ الحقن **في العملية المعزولة بس** ⭐ (مافيش إنتاج ⭐)
    # 📌 الهدف: بند القبول AC-13-3 ⭐ «حقن أعطال متدرجة ثم عودة المصدر» ⭐
    # 📌 وكمان ده آليّة **البرهان السالب** ⭐ (نشيل الحماية ⭐ ونشوف الفرق ⭐).
    FAULTS = {"source_mode": "blocked", "rate_limit": "on", "mail": "on",
              "data": "ok", "bg_lock": "on", "users_lock": "on",
              "revalidate": "on", "ipo_cache": "keep"}
    _ORIG = {"limits": None, "users_lock": None, "opp_payload": None,
             "data_payload": None, "mail_on": None, "save_users": None,
             "store_broken": None}

    def _harness_fault():
        """💥 حقن/إزالة عطل ⭐ — GET للحالة · POST للتغيير ⭐."""
        guard = _harness_guard()
        if guard is not None:
            return guard
        if flask.request.method == "POST":
            body = flask.request.get_json(silent=True) or {}
            kind = str(body.get("kind") or "")
            value = body.get("value")
            try:
                if kind == "source_mode":
                    mode = str(value or "blocked")
                    FAULTS["source_mode"] = mode
                    net_block.set_mode(mode, delay=float(body.get("delay") or 0.0))
                    net_block.install()
                elif kind == "rate_limit":
                    if str(value) == "off":
                        if _ORIG["limits"] is None:
                            _ORIG["limits"] = dict(up.LIMITS)
                        up.LIMITS = {
                            k: [(10 ** 9, w) for (_m, w) in v]
                            for k, v in _ORIG["limits"].items()}
                    else:
                        if _ORIG["limits"] is not None:
                            up.LIMITS = _ORIG["limits"]
                    FAULTS["rate_limit"] = str(value)
                elif kind == "mail":
                    if _ORIG["mail_on"] is None:
                        _ORIG["mail_on"] = getattr(up, "MAIL_ON", False)
                    up.MAIL_ON = (str(value) == "on")
                    FAULTS["mail"] = str(value)
                elif kind == "data":
                    if str(value) == "unavailable":
                        if _ORIG["data_payload"] is None:
                            _ORIG["data_payload"] = up._DATA_FULL["payload"]
                        up._DATA_FULL["payload"] = None
                    else:
                        if _ORIG["data_payload"] is not None:
                            up._DATA_FULL["payload"] = _ORIG["data_payload"]
                    FAULTS["data"] = str(value)
                elif kind == "bg_lock":
                    FAULTS["bg_lock"] = str(value)
                elif kind == "users_lock":
                    if str(value) == "off":
                        if _ORIG["users_lock"] is None:
                            _ORIG["users_lock"] = up.USERS_LOCK

                        class _NoLock:
                            def __enter__(self):
                                return self

                            def __exit__(self, *_a):
                                return False
                        up.USERS_LOCK = _NoLock()
                    else:
                        if _ORIG["users_lock"] is not None:
                            up.USERS_LOCK = _ORIG["users_lock"]
                    FAULTS["users_lock"] = str(value)
                elif kind == "revalidate":
                    if str(value) == "off":
                        if _ORIG["opp_payload"] is None:
                            _ORIG["opp_payload"] = up._opp_payload

                        def _raw_payload():
                            d = up.LIVE_DATA.get("opp")
                            return d if isinstance(d, dict) else None
                        up._opp_payload = _raw_payload
                    else:
                        if _ORIG["opp_payload"] is not None:
                            up._opp_payload = _ORIG["opp_payload"]
                    FAULTS["revalidate"] = str(value)
                elif kind == "atomic_off":
                    # ⛔⛔⛔ محاكاة الكتابة **غير الذرّية** ⭐
                    # 📌 (السلوك القديم ⭐ ⇒ الملف ممكن يتقري نصّه ⭐)
                    if str(value) == "off":
                        if _ORIG["save_users"] is None:
                            _ORIG["save_users"] = up._save_users

                        def _unsafe_save(d):
                            try:
                                with open(up.USERS_FILE, "w",
                                          encoding="utf-8") as f:
                                    f.write(json.dumps(d, ensure_ascii=False))
                                    f.flush()
                                return True
                            except Exception:
                                return False
                        up._save_users = _unsafe_save
                    else:
                        if _ORIG["save_users"] is not None:
                            up._save_users = _ORIG["save_users"]
                    FAULTS["atomic"] = str(value)
                elif kind == "storage_overwrite":
                    # ⛔⛔⛔ محاكاة الكتابة **فوق ملف تالف** ⭐
                    # 📌 (السلوك القديم ⭐ ⇒ فقد بيانات ⭐)
                    if str(value) == "off":
                        if _ORIG["save_users"] is None:
                            _ORIG["save_users"] = up._save_users

                        def _overwrite_save(d):
                            try:
                                tmp = _sw.tmp_path(up.USERS_FILE)
                                tmp.write_text(json.dumps(d, ensure_ascii=False),
                                               encoding="utf-8")
                                tmp.replace(up.USERS_FILE)
                                return True
                            except Exception:
                                return False
                        up._save_users = _overwrite_save
                    else:
                        if _ORIG["save_users"] is not None:
                            up._save_users = _ORIG["save_users"]
                    FAULTS["storage_overwrite"] = str(value)
                elif kind == "storage_guard_off":
                    # ⛔⛔⛔ تعطيل حماية «مافيش كتابة فوق بيانات تالفة» ⭐
                    # 📌 (السلوك القديم ⭐ ⇒ مسح بيانات ⭐)
                    if str(value) == "off":
                        if _ORIG["save_users"] is None:
                            _ORIG["save_users"] = up._save_users
                        if _ORIG["store_broken"] is None:
                            _ORIG["store_broken"] = up._users_store_broken

                        def _overwrite_save2(d):
                            try:
                                tmp = _sw.tmp_path(up.USERS_FILE)
                                tmp.write_text(json.dumps(d, ensure_ascii=False),
                                               encoding="utf-8")
                                tmp.replace(up.USERS_FILE)
                                return True
                            except Exception:
                                return False
                        up._save_users = _overwrite_save2
                        up._users_store_broken = lambda: None
                    else:
                        if _ORIG["save_users"] is not None:
                            up._save_users = _ORIG["save_users"]
                        if _ORIG["store_broken"] is not None:
                            up._users_store_broken = _ORIG["store_broken"]
                    FAULTS["storage_guard"] = str(value)
                elif kind == "store_detect_off":
                    # ⛔⛔⛔ محاكاة تعطّل كشف تلف المخزن ⭐
                    if str(value) == "off":
                        if _ORIG["store_broken"] is None:
                            _ORIG["store_broken"] = up._users_store_broken
                        up._users_store_broken = lambda: None
                    else:
                        if _ORIG["store_broken"] is not None:
                            up._users_store_broken = _ORIG["store_broken"]
                    FAULTS["store_detect"] = str(value)
                elif kind == "ipo_cache":
                    try:
                        up._IPO.update(at=0, list=[], ttl=0)
                    except Exception:
                        pass
                    FAULTS["ipo_cache"] = "clear"
                else:
                    return flask.jsonify({"ok": False,
                                          "error": "نوع عطل مش معروف",
                                          "kind": kind}), 400
            except Exception as exc:
                return flask.jsonify({"ok": False, "error": type(exc).__name__,
                                      "message": str(exc)[:160]}), 400
        return flask.jsonify({"ok": True, "faults": dict(FAULTS),
                              "source": net_block.current_mode()})

    up.app.route("/__harness__/fault", methods=["GET", "POST"])(_harness_fault)

# ══════════════════════════════════════════════════════════════════
#  👥 حسابات وهمية — واحد Free وواحد Pro
# ══════════════════════════════════════════════════════════════════
DEV_FREE = "f" * 64
DEV_PRO = "p" * 64
FREE_MAIL = "staging.free@example.test"
PRO_MAIL = "staging.pro@example.test"


def _mk(uid, email, pin, dev, plan, until=0):
    salt = up._pin_salt_new()
    dh = up._device_key_hash(dev)
    rec = {
        "id": uid, "name": "Staging " + plan, "email": email,
        "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
        "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": int(time.time()),
        "bio_hash": dh, "bio_hashes": [dh],
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
        "plan": plan, "plan_until": int(until or 0),
    }
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = rec
        up._save_users(users)
    return rec


def seed():
    _mk("stg_free_user", FREE_MAIL, "1111", DEV_FREE, "free", 0)
    _mk("stg_pro_user", PRO_MAIL, "2222", DEV_PRO, "pro",
        int(time.time()) + 30 * 86400)
    # ⛔ حساب Pro منتهي (للاختبار) ⬇️
    _mk("stg_expired_pro", "staging.expired@example.test", "3333",
        "e" * 64, "pro", int(time.time()) - 86400)


if __name__ == "__main__":
    seed()
    # ⛔ ملف إعدادات الـstaging (للـworker) ⬇️
    cfg = {
        "api_url": "http://127.0.0.1:%d" % PORT,
        "proxy_secret": PROXY,
        "admin_token": ADMIN,
        "free": {"email": FREE_MAIL, "pin": "1111", "device": DEV_FREE},
        "pro": {"email": PRO_MAIL, "pin": "2222", "device": DEV_PRO},
        "expired_pro": {"email": "staging.expired@example.test",
                        "pin": "3333", "device": "e" * 64},
        "data_dir": str(STAGE_DIR),
        # ⛔ الجولة ٢٤ — الملف بقى **مكتفي بنفسه**: بيقول مسار صندوق
        # ⛔ البريد المحاكى كمان ⇐ فالاختبار مابقاش محتاج يستنتجه ⭐
        "mailbox": str(MAIL_FILE),
    }
    (STAGE_DIR / "staging-config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[staging] ✅ جاهز · البورت %d · الداتا: %s" % (PORT, STAGE_DIR))
    print("[staging] ✅ proxy_secret متسجّل في %s" % (STAGE_DIR / "staging-config.json"))
    print("[staging] ⚠️ مافيش أي سر إنتاج اتستخدم — كله متولّد هنا")
    up.app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False,
               use_reloader=False)
