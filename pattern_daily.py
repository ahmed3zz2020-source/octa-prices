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
# ⭐⭐⭐ الفلاتر المُقاسة (٢٨ أكتوبر ٢٠٢٦) — من ٦ سنين تاريخ + ضوابط
# 📌 الأرقام دي مش تخمين: ٣١٥٣ إشارة على ٢٠٢١-٢٠٢٦ (١٨٦ سهم)
#    · نجاح ٥٨.٢٪ (المحلولة) · R/صفقة +٠.٤٣ بعد التكلفة
#    · ٩٥٪ ثقة: +٠.٣٥ .. +٠.٥٠ (block bootstrap على مستوى السهم)
#    · الضابط (مستوى عشوائي في نفس التوقيت): −٠.٠٧ ⇒ الفرق +٠.٤٩
#    · الضابط (كسر أعلى ٢٠ شمعة): +٠.١٦ ⇒ إحنا أحسن
#    · التدريب ٢٠٢١-٢٣ = +٠.٤٣ · التحقق ٢٠٢٤-٢٦ = +٠.٤٢ (مفيش overfit)
# 📌Stat: القياس بـ«الدخول بافتتاح الشمعة التالية» (واقعي) — مش بالسعر المخطط.
DEFAULT_FILTERS = {
    "kind": "BREAKOUT",              # نمط واحد بس: كسر المنطقة (الارتداد خاسر)
    "direction": "up",               # ⭐ الكسور الصاعدة بس (٧٣٪ من الـedge)
    "volume_confirmed": True,        # حجم كسر ≥ ١٫٣ × متوسط ٢٠
    "market_above_ema200": True,     # ⭐ EGX30 فوق EMA200 (شرط مُقاس)
    "min_turnover": 5_000_000,       # سيولة ≥ ٥ مليون جنيه/يوم
    "max_atr_pct": 8.0,              # استبعاد التذبذب المجنون
}

# 📊 الأداء المُقاس (٢٨ أكتوبر ٢٠٢٦) — بيتبعت للواجهة كـ«مرجع»
#    عشان المستخدم يشوف الرقم ومصدره (مافيش كلام فاضي).
MEASURED_PERFORMANCE = {
    "measured_at": "2026-10-28",
    "window": "2021-01-01 .. 2026-10-27",
    "stocks": 186,
    "signals": 3153,
    "hit_rate": 0.582,
    "r_per_trade": 0.43,
    "r_per_trade_all": 0.20,
    "ci95": [0.35, 0.50],
    "train_r": 0.43,
    "validate_r": 0.42,
    "control_random_level_r": -0.07,
    "control_benchmark_r": 0.16,
    "cost_pct": 0.35,
    "entry": "افتتاح الشمعة التالية للتأكيد",
    "stop": "حافة المنطقة − ١ ATR",
    "target": "الدخول + ٤ ATR",
    "horizon": 10,
    "note": "القياس: walk-forward على شموع يومية حقيقية + ضوابط (مستوى عشوائي، "
            "كسر أعلى ٢٠ شمعة، والاتجاه المعاكس). الأرقام محسوبة على صفقات "
            "مُنفّذة بفاتورة عمولة ٠٫٣٥٪.",
}

# 📐 مستويات الـsetup المُقاسة (٢٨ أكتوبر ٢٠٢٦)
SETUP_STOP_ATR = 1.0     # الوقف: حافة المنطقة − ١ ATR
SETUP_TARGET_ATR = 4.0   # الهدف: الدخول + ٤ ATR

# ⭐ كل الرموز (من egx_names.json) — لو الملف مش موجود نستخدم اللي في
#   الـuniverse تاع الـbackend.
_NAMES_FILE = HERE / "egx_names.json"


def _log(msg):
    print("[pattern] %s" % msg, flush=True)


def egx30_codes():
    """📦 أكواد أسهم مؤشر EGX30 (من اللقطة الرسمية).

    📌 المصدر: `data/index_official.json` (البورصة المصرية).
    ⛔ لو الملف مش موجود ⇒ [] (يعني: مافيش تقييد) — مافيش تخمين.
    """
    try:
        p = HERE / "data" / "index_official.json"
        if not p.exists():
            return []
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        w = ((data.get("indices") or {}).get("EGX30") or {}).get("weights") or []
        out = []
        for row in w:
            code = str((row or {}).get("reuters") or "").replace(".CA", "").strip()
            if code:
                out.append(code)
        return sorted(set(out))
    except Exception:
        return []


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


# ══════════════════════════════════════════════════════════════════════
#  📈 regime السوق (EGX30 فوق EMA200) — شرط مُقاس (٢٨ أكتوبر ٢٠٢٦)
# ══════════════════════════════════════════════════════════════════════
# 📌 المصدر: data/index_history.json (EGX30 · ٧٠٢٦ شمعة) — نفس المصدر
#    بتستخدمه صفحة «ذكاء المؤشرات».
# ⛔ لو الملف مش موجود ⇒ الفلتر مايتطبّقش (مافيش تخمين).
_REGIME_CACHE = {"at": 0.0, "data": None}
_INDEX_HIST = HERE / "data" / "index_history.json"


def _ema(vals, n):
    if len(vals) < n or n <= 0:
        return None
    k = 2.0 / (n + 1.0)
    e = sum(vals[:n]) / float(n)
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e


def market_regime(max_age_hours=6):
    """{تاريخ: True/False} — EGX30 فوق EMA200؟"""
    now = time.time()
    if (_REGIME_CACHE["data"] is not None
            and now - _REGIME_CACHE["at"] < max_age_hours * 3600):
        return _REGIME_CACHE["data"]
    out = {}
    try:
        if not _INDEX_HIST.exists():
            return {}
        with open(_INDEX_HIST, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rows = ((payload.get("indices") or {}).get("EGX30") or {}).get("rows") or []
        closes, dates = [], []
        for r in rows:
            try:
                ts = int(r[0]); c = float(r[1])
            except Exception:
                continue
            closes.append(c)
            dates.append(time.strftime("%Y-%m-%d", time.gmtime(ts)))
        e200 = None
        for i, c in enumerate(closes):
            if i >= 199:
                if e200 is None:
                    e200 = _ema(closes[:i + 1], 200)
                else:
                    k = 2.0 / 201.0
                    e200 = c * k + e200 * (1 - k)
            if e200:
                out[dates[i]] = bool(c > e200)
    except Exception as e:
        _log("⚠️ regime: %s" % e)
        return {}
    _REGIME_CACHE["at"] = now
    _REGIME_CACHE["data"] = out
    return out


def regime_asof(date_str, regime=None):
    """قيمة الـregime «كما كانت» في تاريخ معيّن.

    ⛔ لازم «آخر قيمة معروفة قبل التاريخ» — مش تاريخ مطابق: المؤشر
       بيتقفل في أيام راحة السهم (السبت) ⇒ البحث بالتاريخ المطابق
       بيرجّع None وبيقفل الفلتر على كل الإشارات.
    """
    reg = regime if regime is not None else market_regime()
    if not reg:
        return None
    d = str(date_str or "")
    if d in reg:
        return reg[d]
    best = None
    for k in reg:
        if k <= d and (best is None or k > best):
            best = k
    return reg.get(best) if best else None


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
    # ⭐ regime السوق: EGX30 فوق EMA200 (مُقاس — بيفرق +0.4R)
    if flt.get("market_above_ema200") is not None:
        m = sig.get("market_above_ema200")
        if m is None:
            return False
        if bool(m) != bool(flt["market_above_ema200"]):
            return False
    return True


def _apply_setup(item):
    """يضبط مستويات الـsetup المُقاسة: الوقف تحت حافة المنطقة والهدف +٤ ATR.

    📌 السبب: مستويات الكاشف الأصلية (المدى الحقيقي للمنطقة) كانت بتطلع
       ضعيفة لأن الدخول بفتتاح الشمعة الجاية بيبعد عن المستوى.
       الإعداد المقيس: وقف = حافة − ١ ATR · هدف = الدخول + ٤ ATR.
    ⛔ القيم القديمة بتفضل في evidence (مافيشLost information).
    """
    ev = item.get("evidence") or {}
    atr = ev.get("atr")
    direction = item.get("direction")
    zone_high = item.get("zone_high")
    zone_low = item.get("zone_low")
    entry = item.get("entry")
    if not atr or not entry:
        return item
    try:
        atr = float(atr)
        entry = float(entry)
    except Exception:
        return item
    if direction == "up":
        level = zone_high if zone_high is not None else entry
        stop = level - SETUP_STOP_ATR * atr
        target = entry + SETUP_TARGET_ATR * atr
    else:
        level = zone_low if zone_low is not None else entry
        stop = level + SETUP_STOP_ATR * atr
        target = entry - SETUP_TARGET_ATR * atr
    item["setup"] = {
        "level": round(float(level), 4),
        "entry_ref": round(entry, 4),
        "stop": round(float(stop), 4),
        "target": round(float(target), 4),
        "rr": round(abs(target - entry) / max(1e-9, abs(entry - stop)), 2),
        "stop_atr": SETUP_STOP_ATR,
        "target_atr": SETUP_TARGET_ATR,
        "entry_note": "الدخول الفعلي: افتتاح الشمعة التالية للتأكيد",
        # ⭐ مستويات الرسم الاحترافي (إدارة الصفقة — **مش جزء من القياس**)
        # 📌 الدخول الأعمق = نص النطاق (سعر أحسن بس أضعف تأكيداً)
        # 📌 الهدف الأول = نصف المسافة للهدف (تقسيم على مرحلتين)
        # ⚠️ دي مش الإعداد المُقاس (٥٨٪/+0.43R) — لازم الواجهة تقول كده.
        "entry_deep": round(float((item.get("zone_high") if direction == "up"
                                    else item.get("zone_low")) or level), 4),
        "target_partial": round(float(entry + (2.0 * atr) * (1 if direction == "up" else -1)), 4),
        "measured": True,
    }
    return item


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
    regime = market_regime()
    summary = {"codes": len(codes), "ok": 0, "insufficient": 0, "no_pattern": 0,
               "signals": 0, "filtered_out": 0, "failed_fetch": len(failed or [])}
    lookback = int(flt.get("lookback_days") or 5)
    # نسخة من الفلاتر من غير شرط الـregime (لعرض «غير مُقاس»)
    loose_flt = dict(flt)
    loose_flt.pop("market_above_ema200", None)
    for code in codes:
        cols = got.get(code)
        bars = _cols_to_bars(cols) if cols else []
        if not bars:
            summary["insufficient"] += 1
            continue
        # ⭐ نفحص آخر ٥ أيام تداول — كل يوم على حدة (السلسلة مقصوصة)
        #    ⇒ مافيش look-ahead + المستخدم بيلقى setups حتى لو اليوم مفيش كسر.
        sigs = []
        for k in range(min(lookback, max(0, len(bars) - 1))):
            sub = bars[:len(bars) - k] if k else bars
            res = pd.detect(sub, code=code, cfg=cfg)
            if res.get("status") != "ok":
                if k == 0:
                    summary["insufficient"] += 1
                continue
            if k == 0:
                summary["ok"] += 1
            got_sigs = res.get("signals") or []
            if k == 0 and not got_sigs:
                summary["no_pattern"] += 1
            for sg in got_sigs:
                sg["days_ago"] = k
                sigs.append(sg)
        if not sigs:
            continue
        seen = set()
        for s in sigs:
            # ⭐ regime السوق (EGX30 فوق EMA200) — شرط مُقاس
            s["market_above_ema200"] = regime_asof(s.get("detected_at"),
                                                    regime)
            # ⛔ نفس الكسر ممكن يتأكد على أكتر من يوم (تأكيد ٣ إغلاقات)
            #    ⇒ نخلي أول ظهور بس (تاريخ الكسر الحقيقي).
            # ⛔ نستخدم حافة المنطقة (للي كسر) مش midpoint — عشان نفس
            #    الكسر ممكن يتعرّف بمنطقتين مختلفتين للمنطقة.
            _edge = s.get("zone_high") if s.get("direction") == "up" else s.get("zone_low")
            key = (s.get("direction"), round(float(_edge or 0), 2))
            if key in seen:
                summary["filtered_out"] += 1
                continue
            seen.add(key)
            # ⭐⭐ المطابقة الكاملة = «مُقاس» (اللي عنده إحصا��ة ونتايج
            #    تاريخية). اللي بيمر بغير شرط الـregime بيظهر برضه بس
            #    موسوم «مش مُقاس» — عشان المستخدم مايفتكرش إنه مدروس.
            if _passes(s, flt):
                s["measured_fit"] = True
            elif _passes(s, loose_flt):
                s["measured_fit"] = False
            else:
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
            # ⭐ مستويات الـsetup المُقاسة (٢٨ أكتوبر ٢٠٢٦)
            _apply_setup(item)
            items.append(item)
        summary["signals"] += len(sigs)

    # ⭐ الترتيب: المُقاس (مطابق للشرط المقاس) الأول، ثم الأحدث
    items.sort(key=lambda s: (0 if s.get("measured_fit") else 1,
                               -(s.get("days_ago") or 0),
                               s.get("detected_at") or "",
                               -((s.get("setup") or {}).get("rr") or 0)),
               reverse=False)
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
    """بيقرأ القائمة المحفوظة.

    ⛔ لو قديمة ⇒ بنرجّعها **مع** stale=True (مش None) — عشان الواجهة
       ما تفضلش فاضية، والبناء الجديد يgetting يتم في الخلفية.
    """
    try:
        if not SHORTLIST_FILE.exists():
            return None
        stale = False
        if max_age_hours:
            age = (time.time() - SHORTLIST_FILE.stat().st_mtime) / 3600.0
            stale = age > float(max_age_hours)
        with open(SHORTLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["stale"] = stale
        return data
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


def _p(v):
    """تنسيق السعر في نص الإنذار (رقمان عشريان)."""
    try:
        return ("%.2f" % float(v))
    except Exception:
        return "—"


def digest_text(items, limit=12):
    """نص الملخص العربي للإنذار."""
    if not items:
        return ("🌙 <b>لا توجد إشارات اليوم</b>\n\n"
                "مفيش كسر منطقة عدّى الفلاتر.\n"
                "⚠️ محتوى تعليمي — القرار قرارك.")
    lines = ["🛰️ <b>نماذجي — كسر منطقة</b>",
             "%s · %d نمط" % (items[0].get("detected_at") or "", len(items)),
             "━" * 20]
    for s in items[:limit]:
        direction = "صاعد ▲" if s.get("direction") == "up" else "هابط ▼"
        lines.append("<b>%s</b> %s — %s"
                     % (s.get("code"), s.get("name") or "", direction))
        lines.append("   دخول %s · وقف %s · هدف %s · ع/م %s"
                     % (_p(s.get("entry")), _p(s.get("stop")),
                        _p(s.get("target")), s.get("rr")))
        why = (s.get("why") or "").strip()
        if len(why) > 150:
            why = why[:150] + "…"
        lines.append("   %s%s" % (why, " · حجم مؤكد" if s.get("volume_confirmed") else ""))
    if len(items) > limit:
        lines.append("... وفي %d نمط تاني في التطبيق." % (len(items) - limit))
    lines.append("⚠️ محتوى تعليمي — القرار قرارك.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  المسجّل (API) + المهمة اليومية
# ══════════════════════════════════════════════════════════════════════

_REBUILDING = {"on": False}


def _rebuild_in_background(live_data_getter=None):
    """يعيد بناء القائمة في الخلفية (مرة واحدة في نفس الوقت)."""
    if _REBUILDING["on"]:
        return False

    def _run():
        _REBUILDING["on"] = True
        try:
            live = live_data_getter() if live_data_getter else None
            payload = build_shortlist(live_data=live)
            save_shortlist(payload)
            _log("✅ تحديث الخلفية: %d نمط" % payload.get("count", 0))
        except Exception as e:
            _log("⚠️ فشل التحديث في الخلفية: %s" % e)
        finally:
            _REBUILDING["on"] = False

    try:
        threading.Thread(target=_run, daemon=True).start()
        return True
    except Exception:
        _REBUILDING["on"] = False
        return False


def register(app, require_user=None, send=None, live_data_getter=None,
             plan_checker=None, plan_setter=None):
    """بيسجّل المسارات + يشغّل المهمة اليومية (fail-soft)."""
    from flask import jsonify, request

    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    def _plan_of(user):
        """خطة المستخدم — 'pro' يعني إن باقة «نماذجي» مفتوحة."""
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

    def _locked_response(user):
        return jsonify({"ok": False, "locked": True,
                        "plan": _plan_of(user),
                        "error": "باقة «نماذجي» مدفوعة — محتاجة تفعيل"}), 403

    @app.route("/api/setups", methods=["GET"])
    def setups_api():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False,
                            "error": "لازم تسجّل دخول عشان تشوف الأنماط"}), 401
        if _plan_of(u) != "pro":
            return _locked_response(u)
        payload = load_shortlist(max_age_hours=12)
        stale = bool(payload and payload.get("stale"))
        if payload is None and _REBUILDING["on"]:
            # ⛔ في بناء شغال بالفعل ⇒ نستنى شوية بدل ما نبني اتنين
            for _ in range(30):
                time.sleep(1)
                payload = load_shortlist(max_age_hours=12)
                if payload:
                    break
        if payload is None:
            # ⛔ مفيش كاش خالص ⇒ نبنيه دلوقتي (أول طلب بعد النشر)
            try:
                live = live_data_getter() if live_data_getter else None
                payload = build_shortlist(live_data=live)
                save_shortlist(payload)
                stale = False
            except Exception as e:
                return jsonify({"ok": False,
                                "error": "تعذّر بناء المسح: %s" % e}), 503
        elif stale:
            # ⛔ الكاش قديم ⇒ نبني نسخة جديدة في **الخلفية** ونرجّع القديم
            _rebuild_in_background(live_data_getter)
        # ⭐ النطاق: مؤشر EGX30 (الافتراضي) أو كل الأسهم
        # 📌 التصفية على الكاش ⇒ صفر تكلفة زيادة والرد فوري.
        # ⚠️ الأرقام المقاسة (measured) محسوبة على كل الأسهم — وده
        #    مكتوب صراحة في الرد عشان ميفهمش المستخدم إن المقاس لمؤشر.
        all_items = payload.get("items") or []
        scope = str((request.args.get("scope") or "egx30")).strip().lower()
        eg = egx30_codes()
        items = all_items
        if scope == "egx30" and eg:
            _egset = set(eg)
            items = [it for it in all_items if str(it.get("code")) in _egset]
        return jsonify({"ok": True, "items": items,
                        "asof": payload.get("asof"),
                        "generated_at": payload.get("generated_at"),
                        "summary": payload.get("summary"),
                        "stale": stale,
                        "measured": MEASURED_PERFORMANCE,
                        "filters": payload.get("filters"),
                        "scope": scope if scope in ("egx30", "all") else "egx30",
                        "scope_label": ("أسهم مؤشر EGX30" if scope != "all" else "كل الأسهم"),
                        "scope_count": len(items),
                        "scope_total": len(all_items),
                        "scope_codes": eg})

    @app.route("/api/setups/meta", methods=["GET"])
    def setups_meta():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "محمي"}), 401
        payload = load_shortlist(max_age_hours=12) or {}
        return jsonify({"ok": True, "filters": load_filters(),
                        "summary": payload.get("summary"),
                        "plan": _plan_of(u),
                        "measured": MEASURED_PERFORMANCE,
                        "generated_at": payload.get("generated_at")})

    @app.route("/api/setups/refresh", methods=["POST"])
    def setups_refresh():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "محمي"}), 401
        if _plan_of(u) != "pro":
            return _locked_response(u)
        try:
            live = live_data_getter() if live_data_getter else None
            payload = build_shortlist(live_data=live)
            save_shortlist(payload)
            return jsonify({"ok": True, "count": payload.get("count"),
                            "summary": payload.get("summary")})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 503

    @app.route("/api/setups/plan", methods=["POST"])
    def setups_plan():
        """🔐 تفعيل/إلغاء باقة «نماذجي» لحساب — أدمن بس.
        ⛔ fail-closed: مفيش OCTA_ADMIN_TOKEN ⇒ 503 (مش 200)."""
        import hmac
        import os as _os
        want = str(_os.environ.get("OCTA_ADMIN_TOKEN", "") or "").strip()
        if not want:
            return jsonify({"ok": False, "error": "الأدمن مش متظبط"}), 503
        got = str(request.headers.get("X-OCTA-Admin", "") or "").strip()
        if not got or not hmac.compare_digest(got.encode("utf-8", "replace"),
                                              want.encode("utf-8", "replace")):
            return jsonify({"ok": False, "error": "المسار ده محمي"}), 401
        body = request.get_json(silent=True) or {}
        uid = str(body.get("uid") or "").strip()
        email = str(body.get("email") or "").strip()
        plan = str(body.get("plan") or "").strip().lower()
        # ⭐ التفعيل بالإيميل كمان (الأسهل للأدمن — الـuid مش ظاهر)
        if not uid and email:
            uid = email
        if not uid or plan not in ("free", "pro"):
            return jsonify({"ok": False,
                            "error": "لازم uid أو email و plan (free/pro)"}), 400
        if not plan_setter:
            return jsonify({"ok": False,
                            "error": "تعديل الخطة غير متاح"}), 501
        try:
            rec = plan_setter(uid, plan)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500
        if not rec:
            return jsonify({"ok": False, "error": "مفيش حساب ببالمعرّف ده"}), 404
        return jsonify({"ok": True, "uid": uid, "plan": plan})

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
