# -*- coding: utf-8 -*-
"""🗺️ خريطة المستويات — أقرب مستوى قدام كل سهم (٢٨ أكتوبر ٢٠٢٦)

📌 ليه ملف منفصل: كاش بناء Railway sometimes بيفدّي نسخة قديمة من
   الملفات ⇒ تغيير ملف = كاش جديد. وكمان عشان نتفادى أي تصادم مع
   محرك الأنماط الأساسي.

📌 القيمة اليومية: المستخدم يراقب المستوى الأقرب **قبل** الكسر يحصل
   (مش إنذار بعد الحدث) ⇒ سبب يدخل الموقع كل يوم.

⛔ مافيش look-ahead: المنطقة بتتبني من الشموع لحد الآن بس.
⛔ مافيش تخمين: لو البيانات ناقصة ⇒ status=insufficient.
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
    (DATA_DIR / ".probe_zones").write_text("1", encoding="utf-8")
except Exception:
    DATA_DIR = HERE
ZONES_FILE = DATA_DIR / "pattern_zones.json"
_INDEX_HIST = HERE / "data" / "index_history.json"
_NAMES_FILE = HERE / "egx_names.json"


def _log(msg):
    print("[zones] %s" % msg, flush=True)


def _detector():
    """pattern_detector — import كسول (عشان مفيش اعتماد دائري)."""
    import pattern_detector as _pd
    return _pd


def detect_zones(bars, code=None, cfg=None, max_zones=3):
    """🗺️ المناطق المهمة للسهم (مقاومة + دعم) — قبل الكسر.

    📌 الغرض: المستخدم يشوف المستويات **قبل** ما الكسر يحصل ⇒ يقدر
    يراقب المستوى الأقرب. ده الفرق بين منتج تفاعلي ومنتج «إنذار».

    ⛔ مافيش look-ahead: المنطقة بتتبني من الشموع لحد الآن بس.
    ⛔ مافيش تخمين: لو البيانات ناقصة ⇒ status=insufficient.
    """
    _pd = _detector()
    c = dict(_pd.DEFAULTS)
    if cfg:
        c.update(cfg)
    bs = [b for b in (bars or []) if isinstance(b, dict) and _pd._has_ohlc([b])]
    out = {
        "code": code, "status": "insufficient", "reason": "",
        "price": None, "atr": None, "atr_pct": None, "zones": [],
    }
    if len(bs) < c["min_bars"]:
        out["reason"] = "سلسلة قصيرة: %d < %d شمعة" % (len(bs), c["min_bars"])
        return out
    atr_val = _pd._gold_atr(bs, c["atr_len"])
    if not atr_val or atr_val <= 0:
        out["reason"] = "ATR غير متاح"
        return out
    price = bs[-1]["c"]
    zones = _pd._build_zones(bs, atr_val, c)
    res = [z for z in zones if z["kind"] == "resistance"]
    sup = [z for z in zones if z["kind"] == "support"]
    # ⛔ نستبعد المنطقة اللي السعر واقف عليها دلوقتي (مش «المستوى
    #    الجاي») — لازم المسافة حقيقية (نص ATR على الأقل).
    min_atr = 0.5
    res = [z for z in res
           if z["high"] > price
           and (z["high"] - price) / (atr_val or 1) >= min_atr][:max_zones]
    sup = [z for z in sup
           if z["low"] < price
           and (price - z["low"]) / (atr_val or 1) >= min_atr][:max_zones]

    def _pack(z):
        level = z["high"] if z["kind"] == "resistance" else z["low"]
        dist = ((level - price) / price) * 100.0
        return {
            "kind": z["kind"],
            "label": "مقاومة" if z["kind"] == "resistance" else "دعم",
            "level": round(level, 4),
            "zone_low": z["low"], "zone_high": z["high"],
            "distance_pct": round(dist, 2),
            "distance_atr": round(abs(level - price) / atr_val, 2),
            "touches": z["touches"], "reactions": z["reactions"],
            "last_test": z["last_test"], "age_days": z["age_days"],
            "score": z["score"], "score_parts": z.get("score_parts"),
            "why": z.get("why"),
        }

    out["status"] = "ok"
    out["price"] = price
    out["atr"] = round(atr_val, 4)
    out["atr_pct"] = round(atr_val / price * 100, 2) if price else None
    packed = [_pack(z) for z in (res + sup)]
    # ⭐ الترتيب بالأقرب للم��عر أولاً (هو اللي يهم المستخدم)
    packed.sort(key=lambda z: abs(z.get("distance_pct") or 0))
    out["zones"] = packed
    out["nearest"] = (min(out["zones"], key=lambda z: abs(z["distance_pct"]))
                      if out["zones"] else None)
    # ⛔ «الأقرب» = أقل مسافة (ماشي أول واحد في الترتيب) — مش أول
    #    مقاومة في القايمة (كانت بترجّع أبعد واحدة أحياناً).
    out["nearest_resistance"] = next(
        (z for z in out["zones"] if z["kind"] == "resistance"), None)
    out["nearest_support"] = next(
        (z for z in out["zones"] if z["kind"] == "support"), None)
    return out




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
    """أعمدة startamarkets ⇒ قائمة شموع (نفس تحويل pattern_daily)."""
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


def build_zones_map(codes=None, universe=None, max_codes=None,
                    max_zones=3, max_distance_pct=25.0):
    """🗺️ خريطة المستويات لكل الأسهم — «شنو أقرب مستوى قدامي؟»

    📌 القيمة اليومية: المستخدم يراقب المستوى الأقرب قبل الكسر
       يحصل (مش بعد ما يحصل).
    ⛔ مافيش تخمين: لو السهم مافيش شموع ⇒ مش بيتحط (والتقرير بيقول كام).
    """
    import radar_api

    uni = universe if universe is not None else _load_universe()
    if codes is None:
        codes = sorted(uni.keys())
    if max_codes:
        codes = codes[:int(max_codes)]

    got, failed = radar_api.history_for(codes, n=320)
    rows = []
    summary = {"codes": len(codes), "ok": 0, "insufficient": 0,
               "zones": 0, "failed_fetch": len(failed or [])}
    for code in codes:
        cols = got.get(code)
        bars = _cols_to_bars(cols) if cols else []
        if not bars:
            summary["insufficient"] += 1
            continue
        res = detect_zones(bars, code=code, max_zones=max_zones)
        if res.get("status") != "ok":
            summary["insufficient"] += 1
            continue
        summary["ok"] += 1
        meta = uni.get(code) or {}
        for z in res.get("zones") or []:
            if abs(z.get("distance_pct") or 0) > max_distance_pct:
                continue
            rows.append({
                "code": code,
                "name": meta.get("name") or code,
                "sector": meta.get("sector"),
                "price": res.get("price"),
                "atr": res.get("atr"),
                "atr_pct": res.get("atr_pct"),
                "kind": z.get("kind"),
                "label": z.get("label"),
                "level": z.get("level"),
                "zone_low": z.get("zone_low"),
                "zone_high": z.get("zone_high"),
                "distance_pct": z.get("distance_pct"),
                "distance_atr": z.get("distance_atr"),
                "touches": z.get("touches"),
                "reactions": z.get("reactions"),
                "last_test": z.get("last_test"),
                "age_days": z.get("age_days"),
                "score": z.get("score"),
                "why": z.get("why"),
            })
        summary["zones"] += len(res.get("zones") or [])
    # ⭐ الأقرب الأول (هو اللي يهم المستخدم)
    rows.sort(key=lambda r: (abs(r.get("distance_pct") or 0),
                              -(r.get("score") or 0)))
    return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(rows), "rows": rows, "summary": summary}




def _load_zones(max_age_hours=8):
    try:
        if not ZONES_FILE.exists():
            return None
        stale = False
        age = (time.time() - ZONES_FILE.stat().st_mtime) / 3600.0
        if max_age_hours and age > float(max_age_hours):
            stale = True
        with open(ZONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["stale"] = stale
        return data
    except Exception:
        return None


def _save_zones(payload):
    try:
        tmp = ZONES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(ZONES_FILE)
        return True
    except Exception as e:
        _log("⚠️ تعذّر حفظ الخريطة: %s" % e)
        return False


_ZONES_REBUILD = {"on": False}


def _rebuild_zones_in_background():
    if _ZONES_REBUILD["on"]:
        return False

    def _run():
        _ZONES_REBUILD["on"] = True
        try:
            payload = build_zones_map()
            _save_zones(payload)
            _log("✅ خريطة المستويات: %d مستوى" % payload.get("count", 0))
        except Exception as e:
            _log("⚠️ فشل تحديث الخريطة: %s" % e)
        finally:
            _ZONES_REBUILD["on"] = False

    try:
        threading.Thread(target=_run, daemon=True).start()
        return True
    except Exception:
        _ZONES_REBUILD["on"] = False
        return False


def register(app, require_user=None, plan_checker=None, universe=None):
    """🗺️ مسارات خريطة المستويات (محمية بالباقة)."""
    from flask import jsonify, request

    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    def _plan_of(user):
        if not user:
            return "free"
        try:
            if plan_checker:
                p = plan_checker(user)
                if p:
                    return str(p)
        except Exception:
            pass
        return str(user.get("plan") or "free")

    def _locked(user=None):
        return jsonify({"ok": False, "locked": True, "plan": _plan_of(user),
                        "error": "باقة «نماذجي» مدفوعة — محتاجة تفعيل"}), 403

    @app.route("/api/zones", methods=["GET"])
    def zones_api():
        """🗺️ خريطة المستويات — أقرب مستوى لكل سهم (محمية بالباقة)."""
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        if _plan_of(u) != "pro":
            return _locked(u)
        payload = _load_zones()
        stale = bool(payload and payload.get("stale"))
        if payload is None:
            try:
                payload = build_zones_map()
                _save_zones(payload)
                stale = False
            except Exception as e:
                return jsonify({"ok": False,
                                "error": "تعذّر بناء الخريطة: %s" % e}), 503
        elif stale:
            _rebuild_zones_in_background()
        # ⭐ أكواد مؤشر EGX30 (للتصفية في الواجهة — صفر تكلفة)
        _eg = []
        try:
            import pattern_daily as _pd
            _eg = _pd.egx30_codes()
        except Exception:
            _eg = []
        return jsonify({"ok": True, "rows": payload.get("rows") or [],
                        "count": payload.get("count"),
                        "generated_at": payload.get("generated_at"),
                        "summary": payload.get("summary"),
                        "egx30": _eg,
                        "stale": stale})

    @app.route("/api/zones/refresh", methods=["POST"])
    def zones_refresh():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "محمي"}), 401
        if _plan_of(u) != "pro":
            return _locked(u)
        try:
            payload = build_zones_map()
            _save_zones(payload)
            return jsonify({"ok": True, "count": payload.get("count"),
                            "summary": payload.get("summary")})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 503

    return True
