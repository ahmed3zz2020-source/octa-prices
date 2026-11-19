# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
 gold_parity.py — قياس تكافؤ الذهب بمصادر **مستقلة** (الجولة ٢٥ · المرحلة ٧)
═══════════════════════════════════════════════════════════════
 📌 العيب المقفول (R24-I14): تفسير انحراف سعر الذهب كان **دائري**:
    · سعر الدولار «الضمني» كان بيتحسب من سعر الذهب نفسه:
      (الجرام المرصود × 31.1035) ÷ سعر الأونصة
    · وبعدين **نفس** الرقم ده كان بيتستخدم عشان «يثبت» إن
      هامش السوق المحلي = صفر.
    ⇒ النتيجة كانت **بالضرورة** صفر مهما كان السعر المرصود
      فعلاً (برهان على الكود القديم: جرام محلي = ٦٠٠٠ أو ٩٠٠٠
      ⇒ الهامش المحلي = ٠٫٠٠٠٠٪ في الحالتين).
    ⛔ ده استنتاج بيفترض إجابته — مش قياس.

 ✅ الإصلاح: **ثلاث قراءات مستقلة** في نفس اللحظة:
    ① سعر الذهب العالمي (دولار لكل أونصة تروي) من مزوّد **مختلف**
       عن مزوّد السلسلة (Yahoo Finance · GC=F) ⇒ مش مشتقّ من
       السعر المحلي ومش مشتقّ من الذهب المحلي.
    ② سعر الصرف (جنيه لكل دولار) من مصدر **عملة بحت**
       (Yahoo Finance · EGP=X) ⇒ مش مشتقّ من الذهب إطلاقاً.
    ③ السعر المحلي المصري (جنيه لكل جرام · عيار ٢٤ و٢١) من مرجع
       سوق مصري (iSagha) + مصدر تاني للمقارنة (goldbullioneg).

    وبعدين بنقارن الثلاثة في **نفس اللحظة** (فرق التوقيت بيتقاس
    ويتوثّق) وبنفكّك الانحراف إلى: **أثر السعر** · **أثر العملة** ·
    **العلاوة/الخصم المحلي** · **قدم البيانات**.

 ⛔⛔⛔ قواعد (ممنوع نكسرها):
    ① **مفيش رقم مخترع**: لو المصدر رجّع فاضي ⇒ None + سبب مكتوب.
    ② ⛔ الرقم **المشتقّ من سعر الذهب** (سعر الصرف الضمني) **مش**
       سعر صرف مستقل — لازم يتوسم `derived_from_gold: True`
       ومينفعش يُستخدم لإثبات إن الهامش = صفر.
       ⛔ `detect_circular_fx` بيكشف الاشتقاق الدائري برفض صريح.
    ③ **مفيش سببية مُثبتة**: بنقول «رجل/أثر حسابي» مش «سبب مؤكد».
    ④ كل قراءة بتوثّق: المزوّد · الرابط · الحقل · الوحدة · العيار ·
       وقت المصدر (مش وقت سحبنا).
    ⑤ ⛔ مفيش كتابة جوه المشروع — الكاش على /tmp بس.
═══════════════════════════════════════════════════════════════
"""
import datetime
import json
import os
import time

TROY_OUNCE_GRAMS = 31.1035
# ⛔ عتبة اعتبار سعر الصرف «مشتقّ من الذهب» (تطابق مع الرقم المشتق)
CIRCULAR_TOL_PCT = 0.01

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ════════════════════════════════════════════════════════════════
#  سجل المصادر — كل مصدر: مزوّد · رابط · حقل · وحدة · عيار
#  ⛔ «مستقل عن سعر الذهب» = مصدر ما بيحسبش قيمته من سعر الذهب
# ════════════════════════════════════════════════════════════════
WORLD_GOLD_SOURCE = {
    "id": "yahoo_gc_f",
    "name": "Yahoo Finance — ذهب آجل COMEX (GC=F)",
    "provider": "Yahoo Finance / CME (COMEX)",
    "url": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
    "field": "chart.result[0].meta.regularMarketPrice",
    "unit": "دولار لكل أونصة تروي (31.1035 جرام)",
    "karat": None,
    "instrument": "COMEX Gold Futures (GC=F)",
    "independent_of_gold_price": True,
    "note": ("عقد آجل — أساسه (basis) بيختلف قليلاً عن السعر الفوري "
             "(spot)؛ الفرق بيتقاس بالمقارنة مع القراءة الفورية."),
}

FX_OFFICIAL_SOURCE = {
    "id": "yahoo_egp_x",
    "name": "Yahoo Finance — سعر الصرف EGP=X (مرجع رسمي)",
    "provider": "Yahoo Finance",
    "url": "https://query1.finance.yahoo.com/v8/finance/chart/EGP=X",
    "field": "chart.result[0].meta.regularMarketPrice",
    "unit": "جنيه مصري لكل دولار أمريكي",
    "karat": None,
    "independent_of_gold_price": True,
    "note": ("اقتباس عملة بحت — بيتم من سوق العملات، مش من سعر الذهب "
             "ولو مرّة."),
}

# 📌 مصادر صرف **أخرى مستقلة** — بتستخدم كتقاطع (تشتّت المصدر) وبتختار
#    أحدث قراءة عشان القياسات تكون في نفس اللحظة قدر الإمكان.
FX_EXTRA_PROVIDERS = (
    {"id": "exchangerate_api",
     "name": "exchangerate-api — سعر الصرف المرجعي (USD → EGP)",
     "provider": "exchangerate-api.com (open.er-api.com)",
     "url": "https://open.er-api.com/v6/latest/USD",
     "field": "rates.EGP",
     "time_field": "time_last_update_unix",
     "unit": "جنيه مصري لكل دولار أمريكي",
     "independent_of_gold_price": True,
     "note": "اقتباس مرجع عملة — مش مشتقّ من الذهب."},
    {"id": "fxratesapi",
     "name": "fxratesapi — سعر الصرف المرجعي (USD → EGP)",
     "provider": "fxratesapi.com",
     "url": "https://api.fxratesapi.com/latest?base=USD&currencies=EGP",
     "field": "rates.EGP",
     "time_field": "timestamp",
     "unit": "جنيه مصري لكل دولار أمريكي",
     "independent_of_gold_price": True,
     "note": "اقتباس مرجع عملة — مش مشتقّ من الذهب."},
)

WORLD_GOLD_SPOT_CROSSCHECK = {
    "id": "tradingview_xauusd",
    "name": "TradingView — XAU/USD فوري (نفس مزوّد السلسلة)",
    "provider": "TradingView",
    "url": "https://www.tradingview.com/symbols/XAUUSD/",
    "field": "آخر شمعة يومية · close",
    "unit": "دولار لكل أونصة تروي (31.1035 جرام)",
    "karat": None,
    "independent_of_gold_price": False,
    "note": ("⛔ **مش** مصدر مستقل عن السلسلة — بيتستخدم بس لقياس **أساس** "
             "العقد الآجل (futures) عن الفوري (spot)."),
}

LOCAL_GOLD_SOURCE = {
    "id": "isagha",
    "name": "iSagha — مرجع سوق ذهب مصري",
    "provider": "iSagha (سوق تجاري)",
    "url": "https://market.isagha.com/prices",
    "field": "سعر الجرام عيار ٢٤ (الكارت الرئيسي) + أسعار العيارات",
    "unit": "جنيه مصري لكل جرام",
    "karat": "24 (مرجع) · 21/18/14 (بيع وشراء)",
    "independent_of_gold_price": True,
    "note": "مرجع تجاري — مش سعر رسمي حكومي.",
}

LOCAL_FX_SOURCE = {
    "id": "goldbullioneg",
    "name": "goldbullioneg — اقتباس الدولار من سوق الصياغة",
    "provider": "goldbullioneg (سوق تجاري)",
    "url": "https://goldbullioneg.com/",
    "field": "بطاقة «الدولار» (سعر الشراء / سعر البيع)",
    "unit": "جنيه مصري لكل دولار أمريكي",
    "karat": None,
    "independent_of_gold_price": True,
    "note": ("اقتباس **عملة** من سوق صياغة مصري — مش مشتقّ من سعر "
             "الذهب (هو اقتباس سوق مستقل عن الذهب)."),
}

_MEM = {}


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _http_get_text(url, timeout=20):
    """⛔ urllib (stdlib) — مفيش تبعيات."""
    import urllib.request
    import gzip
    import io as _io
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "ar,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.GzipFile(fileobj=_io.BytesIO(raw)).read()
        return raw.decode("utf-8", errors="ignore")


def _http_get_json(url, timeout=20):
    return json.loads(_http_get_text(url, timeout=timeout))


def _epoch_iso(ts):
    try:
        return datetime.datetime.fromtimestamp(float(ts),
                                              datetime.timezone.utc).isoformat()
    except Exception:
        return None


def _reading(source, value, source_timestamp, extra=None):
    """شكل موحّد لكل قراءة: مزوّد · رابط · حقل · وحدة · عيار · وقت."""
    out = {
        "ok": value is not None,
        "id": source.get("id"),
        "name": source.get("name"),
        "provider": source.get("provider"),
        "url": source.get("url"),
        "field": source.get("field"),
        "unit": source.get("unit"),
        "karat": source.get("karat"),
        "instrument": source.get("instrument"),
        "value": value,
        "source_timestamp": source_timestamp,
        "fetched_at": _now_iso(),
        "independent_of_gold_price": bool(source.get("independent_of_gold_price")),
        "note": source.get("note"),
    }
    if extra:
        out.update(extra)
    if value is None:
        out["error"] = "المصدر رجّع فاضي — مفيش رقم"
    return out


# ════════════════════════════════════════════════════════════════
#  القراءات الحيّة (شبكة) — مفيش قراءة من غير نتيجة موثّقة
# ════════════════════════════════════════════════════════════════
def yahoo_quote(symbol, range_="5d", interval="1d", timeout=20):
    """قراءة Yahoo Finance: القيمة + وقت المصدر + بيانات العقد."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
           "?range=%s&interval=%s" % (symbol, range_, interval))
    try:
        j = _http_get_json(url, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": "فشل الوصول للمصدر: " + str(e)[:120],
                "url": url, "fetched_at": _now_iso()}
    res = ((j or {}).get("chart") or {}).get("result") or []
    if not res:
        return {"ok": False, "error": "المصدر رجّع نتيجة فاضية", "url": url,
                "fetched_at": _now_iso()}
    meta = res[0].get("meta") or {}
    val = meta.get("regularMarketPrice")
    if val is None:
        closers = (((res[0].get("indicators") or {}).get("quote") or [{}])[0]
                   .get("close") or [])
        closers = [c for c in closers if c is not None]
        val = closers[-1] if closers else None
    ts = meta.get("regularMarketTime")
    if ts is None:
        stamps = res[0].get("timestamp") or []
        ts = stamps[-1] if stamps else None
    return {"ok": val is not None,
            "value": float(val) if val is not None else None,
            "source_timestamp": _epoch_iso(ts),
            "url": url,
            "meta": {"currency": meta.get("currency"),
                     "exchange": meta.get("fullExchangeName"),
                     "symbol": meta.get("symbol"),
                     "market_state": meta.get("marketState"),
                     "previous_close": meta.get("previousClose"),
                     "chartPreviousClose": meta.get("chartPreviousClose")},
            "fetched_at": _now_iso()}


def world_gold(force=False, ttl=300):
    """① سعر الذهب العالمي — دولار لكل أونصة تروي (مزوّد مستقل)."""
    key = "world_gold"
    now = time.time()
    if (not force and key in _MEM and (now - _MEM[key][0]) < ttl):
        return _MEM[key][1]
    q = yahoo_quote("GC=F")
    if not q.get("ok"):
        out = _reading(WORLD_GOLD_SOURCE, None, None)
        out["error"] = q.get("error") or "مفيش قيمة"
        out["url"] = q.get("url")
    else:
        out = _reading(WORLD_GOLD_SOURCE, q.get("value"),
                       q.get("source_timestamp"),
                       {"instrument": WORLD_GOLD_SOURCE.get("instrument"),
                        "market": q.get("meta")})
    _MEM[key] = (now, out)
    return out


def _fx_provider_reading(spec):
    """قراءة سعر الصرف من مزوّد واحد (fail-soft)."""
    try:
        j = _http_get_json(spec.get("url"), timeout=20)
    except Exception as e:
        out = _reading(spec, None, None)
        out["error"] = "فشل الوصول للمصدر: " + str(e)[:120]
        return out
    val = None
    ts = None
    if spec.get("id") == "yahoo_egp_x":
        q = yahoo_quote("EGP=X")
        if not q.get("ok"):
            out = _reading(spec, None, None)
            out["error"] = q.get("error") or "مفيش قيمة"
            return out
        val = q.get("value")
        ts = q.get("source_timestamp")
    else:
        rates = j.get("rates") or {}
        val = rates.get("EGP")
        raw_ts = j.get(spec.get("time_field"))
        ts = _epoch_iso(raw_ts)
    out = _reading(spec, float(val) if val is not None else None, ts)
    if out["value"] is None:
        out["error"] = "المصدر رجّع فاضي — مفيش رقم"
    return out


def fx_official(force=False, ttl=300):
    """
    ② سعر الصرف — جنيه لكل دولار (اقتباس عملة، **مش مشتقّ من الذهب**).
    📌 بنقرأ **أكثر من مزوّد** مستقل:
       · نختار **أحدث** قراءة (عشان القياسات تكون في نفس اللحظة)
       · وبنرجّع الباقي كـ«تقاطع» مع **تشتّت** بين المصادر.
    """
    key = "fx_official"
    now = time.time()
    if (not force and key in _MEM and (now - _MEM[key][0]) < ttl):
        return _MEM[key][1]
    readings = []
    for spec in (FX_OFFICIAL_SOURCE,) + tuple(FX_EXTRA_PROVIDERS):
        r = _fx_provider_reading(spec)
        if r.get("ok"):
            readings.append(r)
    if not readings:
        out = _reading(FX_OFFICIAL_SOURCE, None, None)
        out["error"] = "كل مصادر الصرف المستقلة رجعت فاضية"
        out["cross_checks"] = []
        _MEM[key] = (now, out)
        return out

    def _ts_key(r):
        try:
            t = datetime.datetime.fromisoformat(r["source_timestamp"])
            if t.tzinfo is None:
                t = t.replace(tzinfo=datetime.timezone.utc)
            return t
        except Exception:
            return datetime.datetime.fromtimestamp(0, datetime.timezone.utc)

    readings.sort(key=_ts_key, reverse=True)
    best = readings[0]
    out = dict(best)
    vals = [r["value"] for r in readings]
    out["cross_checks"] = [{
        "id": r.get("id"), "name": r.get("name"), "provider": r.get("provider"),
        "url": r.get("url"), "field": r.get("field"), "value": r.get("value"),
        "source_timestamp": r.get("source_timestamp"),
    } for r in readings[1:]]
    out["providers_count"] = len(readings)
    out["min_egp_per_usd"] = min(vals)
    out["max_egp_per_usd"] = max(vals)
    out["dispersion_pct"] = round((max(vals) / min(vals) - 1.0) * 100.0, 4)
    out["selection_rule"] = ("أحدث قراءة بالمزوّدات المستقلة (والتقاطع "
                             "بتوثّق معاها).")
    _MEM[key] = (now, out)
    return out


def world_gold_spot_crosscheck():
    """
    📌 تقاطع: الذهب **الفوري** من مزوّد السلسلة نفسه (TradingView).
    ⛔ مش مصدر مستقل — بيتستخدم بس لقياس أساس العقد الآجل عن الفوري.
    """
    try:
        import tv_ws
        bars = tv_ws.fetch("OANDA:XAUUSD", 3) or []
        if not bars:
            out = _reading(WORLD_GOLD_SPOT_CROSSCHECK, None, None)
            out["error"] = "مفيش شموع"
            return out
        b = bars[-1]
        out = _reading(WORLD_GOLD_SPOT_CROSSCHECK, float(b.get("c")),
                       _epoch_iso(b.get("t")))
        out["instrument"] = "OANDA:XAUUSD (فوري)"
        return out
    except Exception as e:
        out = _reading(WORLD_GOLD_SPOT_CROSSCHECK, None, None)
        out["error"] = "فشل الوصول للمصدر: " + str(e)[:120]
        return out



def local_gold(force=False):
    """③ السعر المحلي المصري — جنيه لكل جرام (عيار ٢٤ و٢١ …)."""
    try:
        import gold_local as gl
    except Exception as e:
        out = _reading(LOCAL_GOLD_SOURCE, None, None)
        out["error"] = "مشكلة في استيراد المصدر المحلي: " + str(e)[:100]
        return out
    try:
        d = gl.get(force=force) or {}
    except Exception as e:
        out = _reading(LOCAL_GOLD_SOURCE, None, None)
        out["error"] = "فشل السحب: " + str(e)[:120]
        return out
    if not d.get("ok"):
        out = _reading(LOCAL_GOLD_SOURCE, None, None)
        out["error"] = d.get("error") or "المصدر المحلي مش متاح"
        return out
    out = _reading(LOCAL_GOLD_SOURCE, d.get("gram_24_reference"),
                   d.get("updated_iso"),
                   {"karats": d.get("karats"),
                    "source_url": d.get("source_url"),
                    "source_type": d.get("source_type"),
                    "local_ounce_usd": d.get("ounce_usd"),
                    "gram_24_source": d.get("gram_24_source") or "headline_card"})
    out["url"] = d.get("source_url") or LOCAL_GOLD_SOURCE.get("url")
    out["name"] = d.get("source") or LOCAL_GOLD_SOURCE.get("name")
    return out


def local_fx_market(force=False):
    """②ب سعر الصرف المحلي المنشور — من سوق الصياغة (عملة، مش ذهب)."""
    try:
        import gold_local as gl
    except Exception as e:
        out = _reading(LOCAL_FX_SOURCE, None, None)
        out["error"] = "مشكلة في استيراد المصدر المحلي: " + str(e)[:100]
        return out
    try:
        d = gl.get_second(force=force) or {}
    except Exception as e:
        out = _reading(LOCAL_FX_SOURCE, None, None)
        out["error"] = "فشل السحب: " + str(e)[:120]
        return out
    if not d.get("ok"):
        out = _reading(LOCAL_FX_SOURCE, None, None)
        out["error"] = d.get("error") or "المصدر المحلي مش متاح"
        return out
    fx = d.get("usd_egp") or {}
    val = fx.get("buy") or fx.get("sell")
    out = _reading(LOCAL_FX_SOURCE, val, d.get("updated_iso"),
                   {"usd_egp": fx,
                    "source_url": d.get("source_url"),
                    "local_ounce_usd": (d.get("ounce_usd") or {}).get("buy"),
                    "karats": d.get("karats")})
    out["url"] = d.get("source_url") or LOCAL_FX_SOURCE.get("url")
    out["name"] = d.get("source") or LOCAL_FX_SOURCE.get("name")
    return out


# ════════════════════════════════════════════════════════════════
# Part 2: الدوال الصافية — تفكيك وقياس بلا أي شبكة (حتمية)
# ════════════════════════════════════════════════════════════════
def implied_fx_from_gold(local_gram, xau_usd):
    """
    ⛔ سعر الصرف «الضمني» — **مشتقّ من سعر الذهب**.
    📌 مينفعش يُستخدم كسعر صرف مستقل (ده بالضبط العيب R24-I14):
      استخدامه هيطلّع هامش السوق المحلي صفر **بالبناء** مش بالقياس.
    """
    if not local_gram or not xau_usd:
        return None
    try:
        return float(local_gram) * TROY_OUNCE_GRAMS / float(xau_usd)
    except Exception:
        return None


def detect_circular_fx(fx_egp_per_usd, local_gram, xau_usd,
                       tol_pct=CIRCULAR_TOL_PCT):
    """
    ⛔ كاشف الاشتقاق الدائري: لو سعر الصرف المتاح مطابق (داخل تسامح)
       للرقم المشتقّ من سعر الذهب ⇒ يبقى **مش مستقل** ⇒ يُرفض
       استخدامه في إثبات إن الهامش المحلي = صفر.
    """
    implied = implied_fx_from_gold(local_gram, xau_usd)
    out = {"implied_from_gold": round(implied, 6) if implied is not None else None,
           "tolerance_pct": tol_pct, "circular": False,
           "fx_value": fx_egp_per_usd, "diff_pct": None, "reason": None}
    if implied is None or not fx_egp_per_usd:
        out["reason"] = "مفيش أرقام كافية للحكم"
        return out
    diff = (float(fx_egp_per_usd) / implied - 1.0) * 100.0
    out["diff_pct"] = round(diff, 6)
    if abs(diff) <= tol_pct:
        out["circular"] = True
        out["reason"] = ("سعر الصرف المتاح مطابق للرقم المشتقّ من سعر الذهب "
                         "(فرق %.4f%% ≤ %.2f%%) ⇒ **مش مصدر مستقل** — "
                         "استخدامه هيخلّي هامش السوق المحلي صفر **بالبناء** "
                         "مش بالقياس." % (diff, tol_pct))
    return out


def _pct(a, b):
    """نسبة التغيّر من a إلى b (بالمية)."""
    if not a or not b:
        return None
    try:
        return (float(b) / float(a) - 1.0) * 100.0
    except Exception:
        return None


def decompose_drift(series_row, gold_usd_oz, fx_egp_per_usd, local_gram_egp,
                    fx_market_egp_per_usd=None):
    """
    تفكيك انحراف **مستقل** بين نقطة السلسلة المحسوبة والسعر المحلي المرصود.

      السلسلة   : gram_s = xau_s × fx_s ÷ 31.1035   (محسوبة · مرجع رسمي)
      المرصود   : gram_l                            (سوق محلي · جنيه/جرام)

      الانحراف  : drift = gram_s ÷ gram_l − 1
      الهوية    : 1 ÷ (1 + drift) = (1 + الذهب) × (1 + العملة) × (1 + العلاوة)
                  لأن:  gram_l = gold × fx ÷ 31.1035 × (1 + علاوة)

    ⛔ كل رجل بيتقاس بمصدر **مستقل**:
      · الذهب    : gold_usd_oz (مزوّد مستقل) ÷ xau_s
      · العملة   : fx_egp_per_usd (اقتباس عملة) ÷ fx_s
      · العلاوة : gram_l ÷ (gold × fx ÷ 31.1035) − 1
    ⛔ لو سعر الصرف المتاح طلع **مشتقّ من الذهب** ⇒ العلاوة تُترك
       `None` مع سبب (مش صفر كاذب).
    """
    out = {"ok": False, "identity_holds": None, "identity_error_pp": None,
           "local_premium_pct": None, "premium_reason": None,
           "circular_fx": None, "legs": {}}
    try:
        xau_s = float(series_row["xau"])
        fx_s = float(series_row["egp_per_usd"])
        gram_s = float(series_row["gram"])
    except Exception:
        out["error"] = "صف السلسلة ناقص (xau / egp_per_usd / gram)"
        return out
    if not gold_usd_oz or not fx_egp_per_usd or not local_gram_egp:
        out["error"] = "قراءات ناقصة (الذهب أو الصرف أو السعر المحلي)"
        return out
    gold_usd_oz = float(gold_usd_oz)
    fx_egp_per_usd = float(fx_egp_per_usd)
    local_gram_egp = float(local_gram_egp)

    out["ok"] = True
    out["series"] = {"date": series_row.get("d"), "xau_usd_per_oz": xau_s,
                     "egp_per_usd": fx_s, "gram_egp": gram_s}
    # ① الاتساق الداخلي للسلسلة (وحدة الجرام) — مستقل عن كل حاجة
    recomputed = xau_s * fx_s / TROY_OUNCE_GRAMS
    out["series_internal_consistency_pct"] = round(
        (gram_s / recomputed - 1.0) * 100.0, 6)

    # ② الانحراف المقاس
    drift = (gram_s / local_gram_egp - 1.0) * 100.0
    out["drift_pct"] = round(drift, 4)

    # ③ رجل السعر (الذهب العالمي)
    gold_leg = _pct(xau_s, gold_usd_oz)
    out["gold_leg_pct"] = round(gold_leg, 4)
    # ④ رجل العملة (سعر الصرف المستقل)
    fx_leg = _pct(fx_s, fx_egp_per_usd)
    out["fx_leg_pct"] = round(fx_leg, 4)

    # ⑤ فحص الدورية: هل سعر الصرف المتاح مستقل فعلاً؟
    circ = detect_circular_fx(fx_egp_per_usd, local_gram_egp, gold_usd_oz)
    out["circular_fx"] = circ
    out["fx_is_independent"] = (not circ.get("circular"))

    # ⑥ العلاوة/الخصم المحلي — بتتحسب **بس** لو الصرف مستقل
    parity_official = gold_usd_oz * fx_egp_per_usd / TROY_OUNCE_GRAMS
    out["parity_egp_per_gram"] = round(parity_official, 4)
    if circ.get("circular"):
        out["local_premium_pct"] = None
        out["premium_reason"] = circ.get("reason")
        premium_leg = None
    else:
        premium_leg = (local_gram_egp / parity_official - 1.0) * 100.0
        out["local_premium_pct"] = round(premium_leg, 4)
        out["premium_reason"] = None

    # ⑦ الهوية: (1+ذهب)(1+عملة)(1+علاوة) = 1 ÷ (1 + انحراف)
    #    ⛔ بالـقيم غير المدوّرة عشان الخطأ يبقى تحت 1e-9 (مش 1e-4)
    if premium_leg is not None:
        recon = ((1 + gold_leg / 100.0) * (1 + fx_leg / 100.0)
                 * (1 + premium_leg / 100.0))
        implied = 1.0 / (1.0 + drift / 100.0)
        out["reconstructed_ratio"] = round(recon, 12)
        out["implied_ratio"] = round(implied, 12)
        out["identity_error_ratio"] = abs(recon - implied)
        # 📌 الخطأ المتبقي = تقريب جرام السلسلة لأربع منازل فقط
        out["identity_error_pp"] = round(out["identity_error_ratio"] * 100.0, 12)
        out["identity_holds"] = out["identity_error_ratio"] <= 1e-8

    # ⑧ سطر Currency: سعر الصرف المضمّن في السعر المحلي (مشتقّ — للتوثيق بس)
    implied_fx = implied_fx_from_gold(local_gram_egp, gold_usd_oz)
    out["implied_egp_per_usd_from_local_price"] = round(implied_fx, 4) if implied_fx else None
    out["implied_fx_is_derived_from_gold"] = True
    if implied_fx:
        out["implied_fx_vs_official_pct"] = round(
            (implied_fx / fx_egp_per_usd - 1.0) * 100.0, 4)

    # ⑨ مقارنة مع سعر الصرف المحلي المنشور (عملة من سوق الصياغة)
    if fx_market_egp_per_usd:
        fx_market_egp_per_usd = float(fx_market_egp_per_usd)
        out["fx_market_egp_per_usd"] = fx_market_egp_per_usd
        out["fx_market_vs_official_pct"] = round(
            (fx_market_egp_per_usd / fx_egp_per_usd - 1.0) * 100.0, 4)
        parity_market = gold_usd_oz * fx_market_egp_per_usd / TROY_OUNCE_GRAMS
        out["parity_market_egp_per_gram"] = round(parity_market, 4)
        out["local_premium_vs_market_fx_pct"] = round(
            (local_gram_egp / parity_market - 1.0) * 100.0, 4)
        if implied_fx:
            out["implied_fx_vs_market_pct"] = round(
                (implied_fx / fx_market_egp_per_usd - 1.0) * 100.0, 4)

    out["legs"] = {"gold": out.get("gold_leg_pct"),
                   "fx": out.get("fx_leg_pct"),
                   "local_premium": out.get("local_premium_pct")}
    return out


def classify_drift(dec, tolerance_pct=1.5):
    """
    ⛔ تصنيف **واقعي** للانحراف: بنقارنabsolute قيمة كل رجل (بالمساحة
       اللوغاريتمية عشان المقارنة عادلة) — ومش بنخترع تفسيراً.
    📌 الرجوع: (dict) فيه الرجل الغالب · هل الانحراف بنيوي (طبقة
       تسعير/عملة) · نصّ صريح بالمعنى المسموح.
    """
    out = {"ok": False, "dominant_leg": None, "structural": False,
           "statement": None, "within_tolerance": None, "tolerance_pct": tolerance_pct}
    if not dec or not dec.get("ok"):
        out["statement"] = "مفيش تفكيك — القراءات الناقصة"
        return out
    out["ok"] = True
    drift = dec.get("drift_pct")
    out["within_tolerance"] = (drift is not None
                               and abs(drift) <= tolerance_pct)
    legs = {"gold": dec.get("gold_leg_pct"), "fx": dec.get("fx_leg_pct"),
            "local_premium": dec.get("local_premium_pct")}
    # ⛔ لو العلاوة مرفوضة (دورية) ⇒ مينفعش نقارن أبطال
    ranked = sorted(((k, abs(v)) for k, v in legs.items()
                     if v is not None), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        out["statement"] = ("مفيش رجل متاح ⇒ الانحراف **مش مفسّر** "
                            "(مش هنخترع له تفسير).")
        return out
    out["dominant_leg"] = ranked[0][0]
    out["dominant_leg_pct"] = ranked[0][1]
    out["legs_abs_pct"] = {k: v for k, v in legs.items() if v is not None}
    # ⛔ «بنيوي» = الفرق أكبر من حدّ التسعير المعتاد (٠٫٥٪) ورجل العملة
    #    أو العلاوة هو الغالب ⇒ فرق **طبقة تسعير** مش خطأ بيانات.
    out["structural"] = bool(ranked[0][1] > 0.5
                             and ranked[0][0] in ("fx", "local_premium"))
    names = {"gold": "رجل الذهب العالمي",
             "fx": "رجل العملة (سعر الصرف)",
             "local_premium": "فرق التسعير المحلي (العلاوة/الخصم عند التوازي)"}
    out["statement"] = (
        "الانحراف المقاس %+.2f%% — أكثر مكوّناته أثراً: %s (%+.2f%%). "
        "الرصيد: %s. ⛔ ده **إسهام حسابي** — بنقول «أثر» مش «سبب مؤكد»، "
        "ومفيش استنتاج سببية من التطابق."
        % (drift or 0.0,
           names.get(out["dominant_leg"], out["dominant_leg"]),
           dec.get("legs", {}).get(out["dominant_leg"]) or 0.0,
           " · ".join("%s %+.2f%%" % (names.get(k, k), v)
                      for k, v in legs.items() if v is not None)))
    return out


def chain_staleness(series_row, measured_at_iso=None):
    """
    📌 **قدم بيانات السلسلة** — مقاس بالاتفاق المعلن مش بالتقدير:
      السلسلة بتسجّل الصف D = شمعة جلسة بدأت D (ختم TradingView
      22:00/23:00 UTC) ⇒ الإقفال الفعلي = D+1 الساعة 23:00 UTC
      ⇒ «effective_date_cairo» = D+1 (ده مثبّت في gold_history).
    ⛔ دي **اصطلاح توثيق** (مش طابع زمني من المزوّد) — بنقول كده.
    """
    out = {"ok": False, "series_date": series_row.get("d"),
           "effective_date_cairo": series_row.get("effective_date_cairo"),
           "convention": ("الصف D = شمعة جلسة بدأت D ⇒ الإقفال = D+1 "
                          "الساعة 23:00 UTC (اصطلاح gold_history)."),
           "age_minutes": None, "close_utc": None}
    measured_at_iso = measured_at_iso or _now_iso()
    try:
        d = datetime.date.fromisoformat(str(series_row.get("d"))[:10])
        close = datetime.datetime.combine(
            d + datetime.timedelta(days=1), datetime.time(23, 0),
            tzinfo=datetime.timezone.utc)
        measured = datetime.datetime.fromisoformat(measured_at_iso)
        if measured.tzinfo is None:
            measured = measured.replace(tzinfo=datetime.timezone.utc)
        out["close_utc"] = close.isoformat()
        out["age_minutes"] = round(
            (measured - close).total_seconds() / 60.0, 1)
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)[:100]
    return out


def staleness_report(timestamps, measured_at_iso=None):
    """
    ⛔ قياس «قدم البيانات» من التواريخ نفسها (مش تقدير):
      · عمر كل قراءة (من وقت المصدر لحد لحظة القياس)
      · فرق التوقيت بين القراءات (هل اتقريت في نفس اللحظة؟)
    """
    out = {"ages_minutes": {}, "spread_minutes": None,
           "measured_at": measured_at_iso or _now_iso()}
    try:
        measured = datetime.datetime.fromisoformat(out["measured_at"])
        if measured.tzinfo is None:
            measured = measured.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return out
    stamps = []
    for key, iso in (timestamps or {}).items():
        if not iso:
            continue
        try:
            t = datetime.datetime.fromisoformat(str(iso))
            if t.tzinfo is None:
                t = t.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            continue
        stamps.append(t)
        out["ages_minutes"][key] = round(
            (measured - t).total_seconds() / 60.0, 2)
    if len(stamps) >= 2:
        out["spread_minutes"] = round(
            (max(stamps) - min(stamps)).total_seconds() / 60.0, 2)
    out["simultaneous"] = (out["spread_minutes"] is not None
                           and out["spread_minutes"] <= 60.0)
    return out


def measure(series_row, force=False):
    """
    📌 القياس الكامل: قراءات مستقلة + تفكيك + تصنيف + قدم البيانات.
    ⛔ أي قراءة ناقصة ⇒ مافيش رقم مخترع: الحقل بيبقى None مع سبب.
    """
    gold = world_gold(force=force)
    gold_spot = world_gold_spot_crosscheck()
    fx = fx_official(force=force)
    loc = local_gold(force=force)
    fxm = local_fx_market(force=force)
    out = {"measured_at": _now_iso(), "gold": gold, "gold_spot": gold_spot,
           "fx": fx, "local": loc, "fx_market": fxm,
           "decomposition": None, "classification": None,
           "staleness": None, "ok": False, "error": None}
    if not (gold.get("ok") and fx.get("ok") and loc.get("ok")):
        missing = [n for n, r in (("gold", gold), ("fx", fx), ("local", loc))
                   if not r.get("ok")]
        out["error"] = "قراءة ناقصة: %s" % " · ".join(missing)
        return out
    dec = decompose_drift(series_row, gold.get("value"), fx.get("value"),
                          loc.get("value"),
                          fx_market_egp_per_usd=(fxm.get("value")
                                                 if fxm.get("ok") else None))
    out["decomposition"] = dec
    out["classification"] = classify_drift(dec)
    # 📌 تقاطعات: أساس الآجل عن الفوري · مصدر محلي تاني · تشتّت مصادر الصرف
    cross = {}
    if gold_spot.get("ok") and gold.get("value"):
        cross["futures_vs_spot_pct"] = round(
            (float(gold["value"]) / float(gold_spot["value"]) - 1.0) * 100.0, 4)
        cross["futures_vs_spot_note"] = (
            "أساس العقد الآجل عن الفوري — فرق **مصدر/عقد** مش حركة سعر.")
    if fxm.get("ok"):
        k24 = (fxm.get("karats") or {}).get("24") or {}
        if k24.get("sell") and loc.get("value"):
            cross["local_second_gram_24"] = k24.get("sell")
            cross["local_sources_spread_pct"] = round(
                (float(loc["value"]) / float(k24["sell"]) - 1.0) * 100.0, 4)
            cross["local_sources_note"] = (
                "الفرق بين مصدرين محليين مستقلين — ده **نطاق أسعار السوق** "
                "مش خطأ.")
    if fx.get("cross_checks"):
        cross["fx_dispersion_pct"] = fx.get("dispersion_pct")
        cross["fx_providers"] = [
            {"id": fx.get("id"), "value": fx.get("value"),
             "source_timestamp": fx.get("source_timestamp")}] + \
            fx.get("cross_checks")
    out["cross_checks"] = cross
    out["staleness"] = staleness_report({
        "gold": gold.get("source_timestamp"),
        "fx": fx.get("source_timestamp"),
        "local": loc.get("source_timestamp"),
    }, out["measured_at"])
    out["staleness_cross_checks"] = staleness_report({
        "gold_spot": gold_spot.get("source_timestamp"),
        "fx_market": fxm.get("source_timestamp"),
    }, out["measured_at"])
    out["chain_staleness"] = chain_staleness(series_row, out["measured_at"])
    out["ok"] = bool(dec.get("ok"))
    return out


if __name__ == "__main__":
    import gold_history as gh
    d = gh.build(force=True)
    if not d.get("ok"):
        print("⛔ السلسلة مبنيةش:", d.get("error"))
        raise SystemExit(2)
    res = measure(d["series"][-1], force=True)
    print("── القياس (%s) ──" % res["measured_at"])
    for key in ("gold", "fx", "local", "fx_market"):
        r = res.get(key) or {}
        print("   %-10s %-12s %s · %s · %s"
              % (key, r.get("value"), r.get("unit"), r.get("source_timestamp"),
                 r.get("name")))
    dec = res.get("decomposition") or {}
    print("   انحراف %s%% · ذهب %s%% · عملة %s%% · علاوة %s%%"
          % (dec.get("drift_pct"), dec.get("gold_leg_pct"),
             dec.get("fx_leg_pct"), dec.get("local_premium_pct")))
    print("   ", (res.get("classification") or {}).get("statement"))
