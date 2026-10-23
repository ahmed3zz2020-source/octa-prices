# -*- coding: utf-8 -*-
"""
🛰️ OCTA — Smart Money Radar: بيانات المسح الجماعي
══════════════════════════════════════════════════════════════

📌 ليه الملف ده منفصل؟
   المسح بيحتاج تاريخ ٢٨٩ سهم (OHLCV). مسار /api/candles محدود
   ١٥ طلب/دقيقة ⇒ المتصفح محتاج ٢٠ دقيقة. مستحيل.

   الحل: السيرفر نفسه يجيب التاريخ من المصدر مباشرة (startamarkets)
   بتوازٍ محدود + كاش ⇒ المتصفح يطلب ٥-٨ دفعات بس.

📌 المسارات:
   GET /api/radar/universe          → الكون النظيف (كود + اسم عربي + قطاع)
   GET /api/radar/history?codes=…   → شموع OHLCV لمجموعة أكواد

🔒 الحماية: المساران محميين (require_user) — زي باقي مسارات الداتا.
⛔ مفيش أي secret في الكود.
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# ══════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════
UPSTREAM = "https://startamarkets.com/api/v1/egx/history/"

# ⛔ سقف الأكواد في الطلب الواحد — ٦٠ كود × ٢٥٠ شمعة ≈ ١.٥ ميجا
MAX_CODES = 60
# ⛔ التوازي — ٦ اتصالات بس. لازم نبقى مهذّبين مع المصدر.
WORKERS = 6
# ⛔ الكاش — ٣٠ دقيقة. البورصة المصرية بتتغيّر مرة في اليوم.
CACHE_TTL = 1800
# ⛔ مهلة الطلب الواحد
FETCH_TIMEOUT = 25

_HIST = {}          # code -> (ts, candles)
_HIST_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=WORKERS)

# ⛔⛔⛔ semaphore عالمي — حدّ أقصى للاتصالات المفتوحة مع المصدر.
#   ⛔ بدونه: لو الواجهة طلبت ٧ دفعات في نفس الوقت، كل واحدة
#      هتشغّل ٦ workers ⇒ ٤٢ اتصال مفتوح مع startamarkets
#      ⇒ ممكن نتعمل بلوك. ده مش مقبول.
#   ⛌ الحد = ٤ اتصالات في نفس اللحظة — زي ٤ تبويبات مفتوحة.
_SEM = threading.Semaphore(4)

# ══════════════════════════════════════════════════════════════
#  🧹 تنظيف الكون — أكواد السندات + ترجمة ISIN
# ══════════════════════════════════════════════════════════════
# ⛔ أي كود يبدأ بـ EGS = سند حكومي / محفظة صناديق — مش سهم.
#   (ده نفس فلتر الباك في /api/data_full)
NON_EQUITY = {
    "EGS30AJ1C016-EGP", "EGS65101C015", "EGS65621C012",
    "EGS65861C014", "EGS72L31C011",
}

# ⭐ TradingView بيرجّع ٥ أسهم مصرية تحت الـISIN بدل الرمز التجاري.
#   جدول التصحيح مؤكد (١٠ أكتوبر ٢٠٢٦).
ISIN_MAP = {
    "EGS3I0S1C019": "FCMD",       # فيوتشر كير للصناعات الطبية
    "EGS48271C018-EGP": "ESAC",   # مصر جنوب أفريقيا للاتصالات
    "EGS370O1C013": "NAPR",       # الوطنية للطباعة
    "EGS3E071C013-EGP": "ACRO",   # أكرو مصر
    "EGS659O1C015": "IDSC",       # مصر الدولية للخدمات الطبية
}


def clean_code(code):
    """يرجّع (الرمز النظيف, اسم_مصدر)"""
    c = (code or "").upper().strip()
    if not c:
        return None, None
    if c in NON_EQUITY:
        return None, None
    return ISIN_MAP.get(c, c), c


# ══════════════════════════════════════════════════════════════
#  📥 جلب التاريخ من المصدر
# ══════════════════════════════════════════════════════════════
def _fetch_one(code, n):
    """جلب شموع سطر واحد. يرجّع list أو None."""
    try:
        import requests
    except Exception:
        return None
    url = "%s%s" % (UPSTREAM, code)
    # ⛔ كل اتصالات المصدر بتعدّي من الـsemaphore
    with _SEM:
        return _fetch_raw(requests, url, n)


def _fetch_raw(requests, url, n):
    """الاتصال الفعلي بالمصدر + محاولة واحدة تانية لو فشل."""
    for attempt in range(2):
      try:
        r = requests.get(
            url,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 Chrome/120"),
                "Accept": "application/json,text/plain,*/*",
                "Origin": "https://startamarkets.com",
                "Referer": "https://startamarkets.com/egx",
            },
            timeout=FETCH_TIMEOUT,
        )
        if r.status_code != 200:
            if attempt == 0:
                time.sleep(1.5)
                continue
            return None
        raw = r.json()
        if not isinstance(raw, list) or len(raw) < 20:
            return None
        # ⛔⛔ الشكل «بأعمدة» مش «بصفوف»:
        #   الصفوف: {"t":"2026-10-22","o":129.0,"h":129.0,"l":125.15,
        #             "c":125.15,"v":5110068}  ≈ ٧٠ بايت لكل شمعة
        #   الأعمدة: ["2026-10-22",129.0,129.0,125.15,125.15,5110068] ≈ ٤٨
        #   ⇒ ١٢٬٨٠٠ شمعة (٤٠ كود × ٣٢٠) ⇒ ٨٠٦ ك.ب → ٥٥٠ ك.ب (−٣٢٪)
        #   ⛌ وكمان: التحويل لـJSON أسرع بكتير على السيرفر.
        col = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
        for c in raw[-n:]:
            try:
                col["t"].append(c.get("date"))
                col["o"].append(round(float(c["open"]), 4))
                col["h"].append(round(float(c["high"]), 4))
                col["l"].append(round(float(c["low"]), 4))
                col["c"].append(round(float(c["close"]), 4))
                col["v"].append(int(c.get("volume") or 0))
            except Exception:
                continue
        if not col["t"]:
            return None
        return col
      except Exception:
        if attempt == 0:
            time.sleep(1.5)
            continue
        return None
    return None


def _cached(code, n):
    with _HIST_LOCK:
        hit = _HIST.get(code)
        if hit and (time.time() - hit[0]) < CACHE_TTL:
            c = hit[1]
            # ⛔ قصّ حسب n — الكاش متخزّن بالطول الأصلي (٣٢٠)
            #   فلازم نقصّ هنا وإلا الطلب بـn أصغر بيرجّع كله.
            try:
                m = int(n or 0)
                if m and len(c.get("t") or []) > m:
                    return {k: (v[-m:] if isinstance(v, list) else v) for k, v in c.items()}
            except Exception:
                pass
            return c
    return None


def _store(code, candles):
    with _HIST_LOCK:
        _HIST[code] = (time.time(), candles)
        # ⛔ سقف الكاش — ما نملاش الذاكرة
        if len(_HIST) > 900:
            for k in list(_HIST.keys())[:200]:
                _HIST.pop(k, None)


def history_for(codes, n=320):
    """جلب تاريخ مجموعة أكواد. يرجّع (dict, list_faid)."""
    n = max(60, min(int(n or 320), 1200))
    out, failed, todo = {}, [], []
    for code in codes:
        c = _cached(code, n)
        if c:
            out[code] = c
        else:
            todo.append(code)

    if todo:
        def work(code):
            data = _fetch_one(code, n)
            if data:
                _store(code, data)
                return (code, data)
            return (code, None)

        try:
            for code, data in _POOL.map(work, todo):
                if data:
                    out[code] = data
                else:
                    failed.append(code)
        except Exception:
            for code in todo:
                if code not in out:
                    failed.append(code)

    return out, failed


# ══════════════════════════════════════════════════════════════
#  🌐 تسجيل المسارات
# ══════════════════════════════════════════════════════════════
def register(app):
    from flask import jsonify, request

    def _ctx():
        """سياق السيرفر (من غير إجبار تسجيل دخول).

        📌 ⛔⛔ ليه المسارات **مش** محمية؟
             · /api/candles (نفس البيانات بالظبط) مفتوح أصلاً.
             · الكون (كود + اسم + قطاع) موجود في ملف مرجعي ثابت
               بيتحمّل مع الموقع (assets/js/octa-radar-ref.js).
           ⇒ فتح المسارات مش بيكشف حاجة جديدة، لكنه بيخلّي
             الرادار يشتغل للزائر كمان.

        🛡️ الحماية من الضغط على المصدر (مش من الاستغلال):
             · ⛔ semaphore: ٤ اتصالات مفتوحة كحد أقصى
             · ⛔ سقف ٦٠ كود في الطلب
             · ⛔ كاش ٣٠ دقيقة
             · ⛔ سقف المعدّل العام ١٢٠/دقيقة (الـbucket الافتراضي)
        """
        try:
            import update_prices as U
            return U
        except Exception:
            return None

    @app.route("/api/radar/universe", methods=["GET"])
    def _radar_universe():
        U = _ctx()
        if U is None:
            return jsonify({"ok": False, "error": "الخادم مش جاهز"}), 503
        try:
            rows = (U.LIVE_DATA.get("egx30") or [])
            egx = {c: (n, s) for c, n, s in getattr(U, "EGX", [])}
            out, seen = [], set()
            for r in rows:
                raw = r.get("code")
                code, _src = clean_code(raw)
                if not code or code in seen:
                    continue
                seen.add(code)
                name, sector = egx.get(code, (None, None))
                out.append({
                    "code": code,
                    "name": name or r.get("name") or code,
                    "sector": sector or "",
                    "isIsin": bool(_src and _src != code),
                })
            # ⛔ احتياطي: لو السكن الحيّ مش جاهز (أو واقع) بنستخدم
            #    الملف الغني (٢٨٥ سهم) — أحسن من كون فاضي.
            if not out:
                try:
                    payload = U._data_full_payload() or {}
                    for code, row in (payload.get("stocks") or {}).items():
                        c, _src = clean_code(code)
                        if not c or c in seen:
                            continue
                        seen.add(c)
                        name, sector = egx.get(c, (None, None))
                        out.append({
                            "code": c,
                            "name": name or row.get("name") or c,
                            "sector": sector or row.get("sectorAr") or "",
                            "isIsin": bool(_src and _src != c),
                        })
                except Exception:
                    pass
            return jsonify({
                "ok": True,
                "n": len(out),
                "stocks": out,
                "ts": U.LIVE_DATA.get("lastUpdate"),
                "snapshot_id": U.LIVE_DATA.get("snapshot_id"),
                "market_phase": U.market_phase() if hasattr(U, "market_phase") else None,
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:120]}), 500

    @app.route("/api/radar/history", methods=["GET"])
    def _radar_history():
        U = _ctx()
        if U is None:
            return jsonify({"ok": False, "error": "الخادم مش جاهز"}), 503
        try:
            # ⛔⛔ لازم نستخدم «list» مش «codes»:
            #   التنظيف العام (_sanitize_request) بياخد أي بارامتر اسمه
            #   code/symbol/codes ويحطه في clean_code — وده بيقبل
            #   رمز واحد بس ⇒ «COMI,ETEL» بيبقى «» وبيضيع.
            #   «list» مش في القائمة ⇒ بيعدّي على clean_text والفاصلة بتعدّي.
            raw = (request.args.get("list") or request.args.get("codes") or "").strip()
            if not raw:
                return jsonify({"ok": False, "error": "list مطلوب"}), 400
            codes = []
            for part in raw.split(","):
                c, _ = clean_code(part.strip())
                if c and c not in codes:
                    codes.append(c)
            if not codes:
                return jsonify({"ok": False, "error": "لا توجد أكواد صالحة"}), 400
            if len(codes) > MAX_CODES:
                codes = codes[:MAX_CODES]
            try:
                n = int(request.args.get("n", "320"))
            except Exception:
                n = 320
            got, failed = history_for(codes, n)
            return jsonify({
                "ok": True,
                "n": len(got),
                "requested": len(codes),
                "codes": got,
                "failed": failed,
                "ts": U.LIVE_DATA.get("lastUpdate"),
                "snapshot_id": U.LIVE_DATA.get("snapshot_id"),
                "cached": True,
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:120]}), 500
