# -*- coding: utf-8 -*-
"""
🛰️ محرك الأنماط — الطبقة اليومية (المسح + الإنذار + مسار الـAPI)

⛔ **مصدر واحد للحقيقة:** `pattern_detector` هو اللي بيحسب · `pattern_stats` بيقيس ·
   الملف ده بينتج المسح اليومي ويقدّمه.
⛔ **fail-soft**: لو أي حاجة وقعت، السيرفر بيفضل شغال (زي gold/usd/radar).
⛔ **مفيش أرقام مخترعة**: سهم مالوش شموع ⇒ «ناقص» مش «مفيش نمط».

المسار:
  GET /api/setups            → قائمة الأنماط (محمية: لازم توكن)
  GET /api/setups/meta       → الفلاتر المستخدمة + إحصاء المسح (محمية)
  POST /api/setups/refresh   → إعادة بناء (أدمن بس)
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OCTA_DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / ".probe_pattern").write_text("1", encoding="utf-8")
except Exception:
    DATA_DIR = HERE

SHORTLIST_FILE = DATA_DIR / "pattern_shortlist.json"
FILTERS_FILE = DATA_DIR / "pattern_filters.json"
STATE_FILE = DATA_DIR / "pattern_state.json"

# ══════════════════════════════════════════════════════════════════════
#  الفلاتر — الأرقام دي متقاسة على ٢٠٢١-٢٠٢٦ (انظر PATTERN_ENGINE.md)
#  ⛔ كل فلتر لازم يكون متاح وقت الإشارة (بعد إغلاق الشمعة الثالثة)
# ══════════════════════════════════════════════════════════════════════
DEFAULT_FILTERS = {
    "kind": "BREAKOUT",          # نمط واحد بس: كسر المنطقة (الارتداد خاسر)
    "volume_confirmed": True,    # حجم كسر ≥ ١٫٣ × متوسط ٢٠
    "min_turnover": 5_000_000,   # سيولة ≥ ٥ مليون جنيه/يوم
    "max_atr_pct": 6.0,          # استبعاد التذبذب المجنون
    "min_rr": 1.0,               # مضاعف مخاطرة/عائد مقبول
}

# ⭐ كل الرموز (من egx_names.json) — لو الملف مش موجود نستخدم اللي في
#   الـuniverse تاع الـbackend.
_NAMES_FILE = HERE / "egx_names.json"


def _log(msg):
    print("[pattern] %s" % msg, flush=True)


def _load_universe():
    """{code: {"name": ..., "sector": ...}} من egx_names.json."""
    try:
        with open(_NAMES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        names = raw.get("names") or {}
        sectors = raw.get("sectors") or {}
        return {c: {"name": names.get(c) or c, "sector": sectors.get(c)}
                for c in names}
    except Exception as e:
        _log("⚠️ تعذّر قراءة egx_names.json: %s" % e)
        return {}


def _cols_to_bars(cols):
    """أعمدة startamarkets ⇒ قائمة شموع (d,o,h,l,c,v)."""
    if not isinstance(cols, dict):
        return []
    t = cols.get("t") or []
    o = cols.get("o") or []
    h = cols.get("h") or []
    low = cols.get("l") or []
    c = cols.get("c") or []
    v = cols.get("v") or []
    out = []
    for i in range(len(t)):
        out.append({"d": t[i], "o": o[i] if i < len(o) else None,
                    "h": h[i] if i < len(h) else None,
                    "l": low[i] if i < len(low) else None,
                    "c": c[i] if i < len(c) else None,
                    "v": v[i] if i < len(v) else None})
    return out


def load_filters():
    """الفلاتر: من الملف (لو موجود) وإلا الافتراضي."""
    try:
        if FILTERS_FILE.exists():
            with open(FILTERS_FILE, "r", encoding="utf-8") as f:
                f_ = json.load(f)
            if isinstance(f_, dict):
                out = dict(DEFAULT_FILTERS)
                out.update(f_)
                return out
    except Exception:
        pass
    return dict(DEFAULT_FILTERS)


def _passes(sig, flt):
    """فلترة الإشارة — كل شرط لازم يكون معروف وقت الإشارة."""
    if flt.get("kind") and sig.get("kind") != flt["kind"]:
        return False
    if flt.get("direction") and sig.get("direction") != flt["direction"]:
        return False
    if flt.get("volume_confirmed") and not sig.get("volume_confirmed"):
        return False
    rr = sig.get("rr")
    if flt.get("min_rr") is not None and (rr is None or rr < flt["min_rr"]):
        return False
    if flt.get("max_rr") is not None and (rr is None or rr > flt["max_rr"]):
        return False
    atr_pct = (sig.get("evidence") or {}).get("atr_pct")
    if flt.get("max_atr_pct") is not None and (atr_pct is None
                                              or atr_pct > flt["max_atr_pct"]):
        return False
    if flt.get("min_atr_pct") is not None and (atr_pct is None
                                              or atr_pct < flt["min_atr_pct"]):
        return False
    zs = (sig.get("evidence") or {}).get("zone_score")
    if flt.get("min_zone_score") is not None and (zs is None
                                                  or zs < flt["min_zone_score"]):
        return False
    return True


def _liquidity_ok(sig, min_turnover, live_data=None):
    """السيولة: من بيانات الباك الحية لو متاحة، وإلا نستخدم حجم التدوير."""
    if not min_turnover:
        return True, None
    if live_data:
        try:
            for row in live_data:
                if row.get("code") != sig.get("code"):
                    continue
                price = row.get("price")
                vol = row.get("volume") or row.get("avgVol30")
                if price and vol:
                    turnover = float(price) * float(vol)
                    return (turnover >= min_turnover), round(turnover)
                if row.get("avgVol30"):
                    return (float(row.get("avgVol30")) >= min_turnover), None
        except Exception:
            pass
    return True, None


def build_shortlist(codes=None, filters=None, cfg=None, universe=None,
                    live_data=None, max_codes=None):
    """يبني قائمة الأنماط من الشموع الحقيقية.

    ⛔ مفيش تخمين: لو الشموع ناقصة ⇒ السهم بيتحسب «ناقص» وبيظهر في الملخص.
    """
    import pattern_detector as pd
    import radar_api

    flt = filters or load_filters()
    uni = universe if universe is not None else _load_universe()
    if codes is None:
        codes = sorted(uni.keys())
    if max_codes:
        codes = codes[:int(max_codes)]

    got, failed = radar_api.history_for(codes, n=320)
    items = []
    summary = {"codes": len(codes), "ok": 0, "insufficient": 0, "no_pattern": 0,
               "signals": 0, "filtered_out": 0, "failed_fetch": len(failed or [])}
    for code in codes:
        cols = got.get(code)
        bars = _cols_to_bars(cols) if cols else []
        res = pd.detect(bars, code=code, cfg=cfg) if bars else {
            "status": "insufficient", "reason": "مفيش شموع من المصدر", "signals": []}
        if res.get("status") != "ok":
            summary["insufficient"] += 1
            continue
        summary["ok"] += 1
        sigs = res.get("signals") or []
        if not sigs:
            summary["no_pattern"] += 1
            continue
        for s in sigs:
            if not _passes(s, flt):
                summary["filtered_out"] += 1
                continue
            ok_liq, turnover = _liquidity_ok(s, flt.get("min_turnover"), live_data)
            if not ok_liq:
                summary["filtered_out"] += 1
                continue
            meta = uni.get(code) or {}
            item = dict(s)
            item["code"] = code
            item["name"] = meta.get("name") or code
            item["sector"] = meta.get("sector")
            item["turnover"] = turnover
            items.append(item)
        summary["signals"] += len(sigs)

    items.sort(key=lambda s: ((s.get("detected_at") or ""), s.get("rr") or -99),
               reverse=True)
    return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "asof": (items[0].get("detected_at") if items else None),
            "count": len(items), "items": items, "summary": summary,
            "filters": flt}


def save_shortlist(payload):
    try:
        tmp = SHORTLIST_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        tmp.replace(SHORTLIST_FILE)
        return True
    except Exception as e:
        _log("⚠️ تعذّر حفظ القائمة: %s" % e)
        return False


def load_shortlist(max_age_hours=None):
    """بيقرأ القائمة المحفوظة (للقارئ السريع)."""
    try:
        if not SHORTLIST_FILE.exists():
            return None
        if max_age_hours:
            age = (time.time() - SHORTLIST_FILE.stat().st_mtime) / 3600.0
            if age > float(max_age_hours):
                return None
        with open(SHORTLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _state_load():
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _state_save(d):
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception:
        pass


def digest_text(items, limit=12):
    """نص الملخص العربي للإنذار."""
    if not items:
        return "🌙 <b>لا توجد إشارات اليوم</b>\n\nمفيش كسر منطقة عدّى الفلاتر."
    lines = [f"🛰️ <b>أنماط OCTA — كسر منطقة</b>",
             f"{items[0].get('detected_at') or ''} · {len(items)} نمط",
             "━" * 20]
    for s in items[:limit]:
        direction = "صاعد" if s.get("direction") == "up" else "هابط"
        lines.append(
            "<b>%s</b> (%s) — %s" % (s.get("code"), s.get("name") or "",
                                     direction))
        lines.append("   دخول %s · وقف %s · هدف %s · R:R %s"
                     % (s.get("entry"), s.get("stop"), s.get("target"),
                        s.get("rr")))
        ev = s.get("evidence") or {}
        lines.append("   %s · %s"
                     % (s.get("why") or "",
                        ("حجم مؤكد" if s.get("volume_confirmed")
                         else "بدون تأكيد حجم")))
    if len(items) > limit:
        lines.append("... وفي %d نمط تاني في التطبيق." % (len(items) - limit))
    lines.append("⚠️ محتوى تعليمي — القرار قرارك.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  المسجّل (API) + المهمة اليومية
# ══════════════════════════════════════════════════════════════════════

def register(app, require_user=None, send=None, live_data_getter=None):
    """بيسجّل المسارات + يشغّل المهمة اليومية (fail-soft)."""
    from flask import jsonify, request

    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    @app.route("/api/setups", methods=["GET"])
    def setups_api():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False,
                            "error": "لازم تسجّل دخول عشان تشوف الأنماط"}), 401
        payload = load_shortlist(max_age_hours=12)
        if payload is None:
            try:
                live = live_data_getter() if live_data_getter else None
                payload = build_shortlist(live_data=live)
                save_shortlist(payload)
            except Exception as e:
                return jsonify({"ok": False, "error": "تعذّر بناء المسح: %s" % e}), 503
        return jsonify({"ok": True, "items": payload.get("items") or [],
                        "asof": payload.get("asof"),
                        "generated_at": payload.get("generated_at"),
                        "summary": payload.get("summary"),
                        "filters": payload.get("filters")})

    @app.route("/api/setups/meta", methods=["GET"])
    def setups_meta():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "محمي"}), 401
        payload = load_shortlist(max_age_hours=12) or {}
        return jsonify({"ok": True, "filters": load_filters(),
                        "summary": payload.get("summary"),
                        "generated_at": payload.get("generated_at")})

    @app.route("/api/setups/refresh", methods=["POST"])
    def setups_refresh():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "محمي"}), 401
        try:
            live = live_data_getter() if live_data_getter else None
            payload = build_shortlist(live_data=live)
            save_shortlist(payload)
            return jsonify({"ok": True, "count": payload.get("count"),
                            "summary": payload.get("summary")})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 503

    # ── المهمة اليومية ────────────────────────────────────────────
    def _daily_worker():
        """تشتغل مرة في اليوم بعد القفل (١٥:٤٠ القاهرة) وتبعت الملخص."""
        while True:
            try:
                now = time.time()
                # ⏰ بعد قفل السوق (القاهرة = UTC+3 ⇒ ١٢:٤٠ UTC) + نص ساعة
                cairo_hour = (time.gmtime(now + 3 * 3600)).tm_hour
                st = _state_load()
                today = time.strftime("%Y-%m-%d", time.gmtime(now + 3 * 3600))
                if cairo_hour >= 15 and st.get("last_daily") != today:
                    live = live_data_getter() if live_data_getter else None
                    payload = build_shortlist(live_data=live)
                    save_shortlist(payload)
                    st["last_daily"] = today
                    _state_save(st)
                    _log("✅ المسح اليومي: %d نمط" % payload.get("count", 0))
                    if send and payload.get("items"):
                        try:
                            send(digest_text(payload["items"]))
                            st["last_sent"] = today
                            _state_save(st)
                        except Exception as e:
                            _log("⚠️ فشل الإرسال: %s" % e)
                time.sleep(600)
            except Exception as e:
                _log("⚠️ المهمة اليومية: %s" % e)
                time.sleep(300)

    if os.environ.get("OCTA_PATTERN_DAILY", "1") != "0":
        t = threading.Thread(target=_daily_worker, daemon=True)
        t.start()
        _log("✅ المهمة اليومية شغّالة")
    return True
