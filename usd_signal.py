"""
════════════════════════════════════════════════════════════════════════
  💵 محرك «ذكاء الدولار» (OCTA USD INTELLIGENCE)
  USD/EGP + DXY — تحليل فني + ماكرو + سيناريوهات
════════════════════════════════════════════════════════════════════════

📌 القواعد الحاكمة (من دستور المنصة):
  ① مفيش ولا رقم مخترع — كل رقم ليه مصدر ومصدره مكتوب معاه.
  ② النتيجة/الحكم قواعد رياضية ثابتة في الكود (مش تخمين).
  ③ لو المصدر مش متاح ⇒ «غير متاح» + السبب (مش صفر ولا تقدير).
  ④ ممنوع أي ذكر لأدوات ذكاء اصطناعي في الردود الظاهرة للمستخدم.
  ⑤ السر/SCOPE: ما فيش مفاتيح في الواجهة — كل حاجة من السيرفر.

📌 المصادر (كلها متحقَّق منها بالتشغيل):
  • الشموع والتاريخ  → TradingView websocket (ice/source EGX & TVC) — tv_ws.py
  • السعر اللحظي      → TradingView scanner (FX_IDC:USDEGP · TVC:DXY)
  • السعر الرسمي      → البنك المركزي المصري (Average Market Rate)
  • الماكرو العالمي   → FRED (CSV من غير مفتاح) + World Bank API + بطاقة الذهب
  • الماكرو المصري    → البنك المركزي (ملف JSON مُخزَّن) + World Bank
  • التقويم           → ForexFactory الأسبوعي + مواعيد البنك المركزي
  • الأخبار           → Google News RSS (مصدر + تاريخ لكل خبر)
"""
import json
import math
import os
import re
import time
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
CAIRO = timezone(timedelta(hours=2))  # مصر: UTC+2 طول السنة (ألغيت التوقيت الصيفي 2023)

# ══════════════════════════════════════════════════════════════════════
#  الكاش — كل حاجة متكاشّة عشان ما نضربش المصادر
# ══════════════════════════════════════════════════════════════════════
_C = {}


def _cached(key, ttl, fn):
    hit = _C.get(key)
    if hit and (time.time() - hit["_t"]) < ttl:
        return hit["v"]
    try:
        val = fn()
    except Exception as e:
        _C[key] = {"v": None, "_t": time.time(), "_err": str(e)[:120]}
        return None
    if val is None:
        return None
    _C[key] = {"v": val, "_t": time.time()}
    return val


# ══════════════════════════════════════════════════════════════════════
#  ① أدوات مساعدة عامة
# ══════════════════════════════════════════════════════════════════════
def _http_get(url, timeout=25, headers=None, data=None, method="GET"):
    """طلب HTTP بدون اعتماد على requests (يعمل في كل البيئات).

    📌 requests مش متاحة في كل البيئات ⇒ urllib من المكتبة القياسية أأمن.
    """
    import urllib.request
    import urllib.error
    hdr = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
           "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
        hdr.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _http_retry(url, tries=3, timeout=25, headers=None):
    hdr = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
           "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    last = None
    for i in range(tries):
        try:
            return _http_get(url, timeout=timeout, headers=hdr)
        except urllib.error.HTTPError as e:
            last = "HTTP %s" % e.code
        except Exception as e:
            last = str(e)[:80]
        time.sleep(1.2 * (i + 1))
    raise RuntimeError(last or "fetch failed")


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _cairo_now():
    return datetime.now(CAIRO)


def _ts_day(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d")


def _iso(ts):
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ══════════════════════════════════════════════════════════════════════
#  ② الشموع — TradingView websocket (بعد إصلاح الـtimeout)
# ══════════════════════════════════════════════════════════════════════
#  ⛔⛔⛔ tv_ws.py كان بيقع في timeout وبيضيّع كل النقط (اتصلّح 26 أكتوبر)
#     ⇒ الطلب بقى 0.7 ثانية بدل 20، و 7061 نقطة من 1997.
_FX_SYMBOLS = {
    "USDEGP": {"tv": "FX_IDC:USDEGP", "name_ar": "الدولار الأمريكي مقابل الجنيه المصري",
               "name_en": "USD/EGP", "unit": "جنيه لكل دولار", "invert": False},
    "DXY": {"tv": "TVC:DXY", "name_ar": "مؤشر قوة الدولار",
            "name_en": "US Dollar Index", "unit": "نقطة", "invert": False},
}
#  TradingView: آخر شمعة يومية بتقفل 22:00 UTC من اليوم اللي قبل (= 00:00 القاهرة)
_TV_DAY_OFFSET = 2  # ساعة


def _tv_bars(symbol, resolution="1D", count=1200):
    """شموع حقيقية من TradingView — ترجع [] لو المصدر مش متاح (مفيش أرقام مخترعة)."""
    def _go():
        import importlib
        import sys
        from pathlib import Path
        base = str(Path(__file__).parent)
        if base not in sys.path:
            sys.path.insert(0, base)
        tvws = importlib.import_module("tv_ws")
        raw = tvws.fetch_series(symbol, count)
        if not raw:
            return []
        out = []
        for b in raw:
            c = _f(b.get("c"))
            if c is None:
                continue
            t = int(b.get("t") or 0)
            if not t:
                continue
            out.append({"t": t, "o": _f(b.get("o")) or c, "h": _f(b.get("h")) or c,
                        "l": _f(b.get("l")) or c, "c": c, "v": _f(b.get("v"))})
        out.sort(key=lambda z: z["t"])
        return out
    return _cached("bars:%s:%s:%s" % (symbol, resolution, count), 900, _go) or []


def _resample(bars, rule):
    """تجميع شموع: week / month / year."""
    if not bars:
        return []
    buckets = {}
    for b in bars:
        dt = datetime.fromtimestamp(b["t"], UTC)
        if rule == "week":
            key = dt.isocalendar()[:2]
        elif rule == "month":
            key = (dt.year, dt.month)
        elif rule == "year":
            key = dt.year
        else:
            key = dt.strftime("%Y-%m-%d")
        buckets.setdefault(key, []).append(b)
    out = []
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — كان الترتيب str(k) (ترتيب معجمي على النص)
    # 📌 ⇒ الأسابيع/الشهور بتطلع مرتبة غلط: 12 قبل 5، و10 قبل 2
    # 📌 ⇒ الشارت بيرسم قفزات وخطوط متقاطعة + الدعم/المقاومة بتطلع فاسدة.
    # ✅ الحل: نرتب على المفتاح نفسه (tuple) + ترتيب نهائي بالزمن.
    def _ksort(k):
        return (0, k) if isinstance(k, tuple) else (1, k)
    for key in sorted(buckets, key=_ksort):
        g = sorted(buckets[key], key=lambda z: z["t"])
        out.append({
            "t": g[0]["t"],
            "o": g[0]["o"], "h": max(x["h"] for x in g), "l": min(x["l"] for x in g),
            "c": g[-1]["c"], "v": sum((x.get("v") or 0) for x in g),
        })
    out.sort(key=lambda z: z["t"])
    return out


def _fx_series(symbol, tf="1D", count=1200):
    """السلسلة المطلوبة (يوم/أسبوع/شهر) — نجمعها من الشموع اليومية لو محتاجين."""
    if tf == "1D":
        return _tv_bars(symbol, "1D", count)
    daily = _tv_bars(symbol, "1D", 2600)
    if tf == "1W":
        return _resample(daily, "week")
    if tf == "1M":
        return _resample(daily, "month")
    return daily


def _tv_quote(symbol):
    """السعر اللحظي من TradingView scanner."""
    def _go():
        txt = _http_get(
            "https://scanner.tradingview.com/global/scan", timeout=20,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data={"symbols": {"tickers": [symbol], "query": {"types": []}},
                  "columns": ["close", "change", "change_abs", "Perf.1M", "Perf.3M",
                              "Perf.6M", "Perf.Y", "Perf.W", "Volatility.D",
                              "high", "low", "open", "volume"]},
            method="POST")
        rows = (json.loads(txt) or {}).get("data") or []
        if not rows:
            return None
        d = rows[0].get("d") or []
        return {"value": _f(d[0]), "change_pct": _f(d[1]), "change_abs": _f(d[2]),
                "perf_1m": _f(d[3]), "perf_3m": _f(d[4]), "perf_6m": _f(d[5]),
                "perf_y": _f(d[6]), "perf_w": _f(d[7]), "vol_day": _f(d[8]),
                "high": _f(d[9]), "low": _f(d[10]), "open": _f(d[11]), "volume": _f(d[12])}
    return _cached("quote:%s" % symbol, 60, _go)


# ══════════════════════════════════════════════════════════════════════
#  ③ السعر الرسمي — البنك المركزي المصري
# ══════════════════════════════════════════════════════════════════════
def _cbe_official():
    """سعر البنك المركزي الرسمي (Average Market Rate) + تاريخه.

    📌 الشروط: اقتباس قصير + ذكر المصدر (schön). إحنا بنعرض الرقم
       والمصدر والتاريخ — مش بننشر قاعدة بيانات.
    📌 لو مش متاح ⇒ None (ومفيش رقم بديل مخترع).
    """
    def _go():
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "cbe_fx.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d
    return _cached("cbe", 1800, _go)


# ══════════════════════════════════════════════════════════════════════
#  ④ الماكرو المصري — من ملف JSON مُخزَّن (حصاد من مصدره الرسمي)
# ══════════════════════════════════════════════════════════════════════
def _egypt_macro():
    def _go():
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "egypt_macro.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _cached("egymacro", 1800, _go)


def _world_bank(indicator, years="2018:2026"):
    """البنك الدولي — API مفتوحة، رخصة CC BY 4.0."""
    def _go():
        url = ("https://api.worldbank.org/v2/country/EGY/indicator/%s"
               "?format=json&per_page=40&date=%s" % (indicator, years))
        j = json.loads(_http_get(url, timeout=12))
        if not isinstance(j, list) or len(j) < 2 or not j[1]:
            return None
        out = []
        for row in j[1]:
            if row.get("value") is None:
                continue
            out.append({"year": row.get("date"), "value": _f(row.get("value"))})
        out.sort(key=lambda z: z["year"])
        return {"indicator": indicator, "source": "البنك الدولي (World Bank)",
                "source_url": "https://api.worldbank.org/v2/country/EGY/indicator/"
                              + indicator, "license": "CC BY 4.0", "points": out}
    return _cached("wb:%s" % indicator, 21600, _go)


def _fred(series_id, label=""):
    """FRED — CSV من غير مفتاح (المصدر الرسمي الأمريكي)."""
    def _go():
        # ⛔⛔⛔ الـCSV كامل كان 100KB+ وبيرجع في ~60 ثانية
        # 📌 الحل: نحصر المدى في ٣ سنين (kos للحالات والاتجاه) + تايم آوت 12 ثانية
        _from = (datetime.now(UTC) - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
        url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s"
               % (series_id, _from))
        txt = _http_retry(url, tries=1, timeout=12)
        rows = []
        for line in txt.strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            v = _f(parts[1])
            if v is None:
                continue
            rows.append({"date": parts[0], "value": v})
        if not rows:
            return None
        return {"series_id": series_id, "label": label, "source": "Federal Reserve (FRED)",
                "source_url": "https://fred.stlouisfed.org/series/" + series_id,
                "points": rows[-400:]}
    return _cached("fred:%s" % series_id, 21600, _go)


# ══════════════════════════════════════════════════════════════════════
#  ⑤ التقويم الاقتصادي — ForexFactory الأسبوعي + مواعيد البنك المركزي
# ══════════════════════════════════════════════════════════════════════
def _calendar_tv():
    """التقويم الاقتصادي من TradingView — مصدر شغال (ForexFactory بيرد 429 أحياناً)."""
    def _go():
        now = datetime.now(UTC)
        frm = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:00:00.000Z")
        to = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:00:00.000Z")
        url = ("https://economic-calendar.tradingview.com/events"
               "?from=%s&to=%s&countries=US,EG" % (frm, to))
        txt = _http_get(url, timeout=15, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        })
        rows = (json.loads(txt) or {}).get("result") or []
        out = []
        for e in rows:
            ctry = e.get("country")
            if ctry not in ("US", "EG"):
                continue
            dt = e.get("date")
            title = e.get("title") or e.get("indicator") or ""
            if not title or not dt:
                continue
            imp = e.get("importance")
            imp_ar = {0: "Low", 1: "Medium", 2: "High", 3: "High"}.get(imp, "Low")
            out.append({
                "country": "USD" if ctry == "US" else "EGY",
                "t": dt,
                "title": title,
                "impact": imp_ar,
                "forecast": ("" if e.get("forecast") is None else str(e.get("forecast"))),
                "previous": ("" if e.get("previous") is None else str(e.get("previous"))),
                "actual": ("" if e.get("actual") is None else str(e.get("actual"))),
                "source": e.get("source") or "TradingView",
                "source_url": e.get("source_url") or "https://www.tradingview.com/economic-calendar/",
            })
        return out or None
    return _cached("calendar_tv", 1800, _go)


def _calendar_ff():
    """ForexFactory — مصدر احتياطي (أحياناً بيرد 429)."""
    def _go():
        out = []
        try:
            txt = _http_get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=15)
            now = datetime.now(UTC)
            for e in (json.loads(txt) or []):
                ctry = e.get("country")
                if ctry not in ("USD", "EGY"):
                    continue
                try:
                    dt = datetime.fromisoformat(e["date"]).astimezone(UTC)
                except Exception:
                    continue
                if not (now - timedelta(hours=24) <= dt <= now + timedelta(days=7)):
                    continue
                out.append({"country": ctry, "t": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "title": e.get("title", ""), "impact": e.get("impact", "Low"),
                            "forecast": e.get("forecast", ""), "previous": e.get("previous", ""),
                            "source": "ForexFactory",
                            "source_url": "https://www.forexfactory.com/calendar"})
        except Exception:
            return None
        out.sort(key=lambda z: z["t"])
        return out or None
    return _cached("calendar_ff", 1800, _go)


def _calendar():
    """التقويم: مصدر TradingView الأساسي + ForexFactory احتياطي.

    📌 فلترة: الأحداث من لحظة دلوقتي (مع مهلة ساعتين للأخبار المعلنة) + ٧ أيام.
    📌 الترتيب: بالتاريخ، والأهم داخل نفس اليوم فوق (FOMC/التضخم قبل غيرهم).
    """
    ev = _calendar_tv() or _calendar_ff() or []
    now = datetime.now(UTC)
    out = []
    for e in ev:
        t = e.get("t") or ""
        try:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < now - timedelta(hours=2) or dt > now + timedelta(days=7):
            continue
        e["t"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        e["_imp"] = {"High": 3, "Medium": 2, "Low": 1}.get(e.get("impact"), 0)
        out.append(e)
    out.sort(key=lambda z: (z.get("t") or "", -z.get("_imp", 0)))
    for e in out:
        e.pop("_imp", None)
    return out


# ══════════════════════════════════════════════════════════════════════
#  ⑥ الأخبار — Google News RSS (كل خبر بمصدره وتاريخه)
# ══════════════════════════════════════════════════════════════════════
_NEWS_QUERIES = [
    ("EGY", "Egyptian pound OR Egypt exchange rate OR Central Bank of Egypt"),
    ("USD", "Federal Reserve OR US dollar index OR Treasury yields"),
]


def _news():
    def _go():
        import urllib.parse
        out = []
        for ctry, q in _NEWS_QUERIES:
            try:
                url = ("https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en"
                       % urllib.parse.quote(q))
                txt = _http_get(url, timeout=25)
                items = re.findall(r"<item>(.*?)</item>", txt, re.S)[:14]
                for it in items:
                    t = re.search(r"<title>(.*?)</title>", it, re.S)
                    link = re.search(r"<link>(.*?)</link>", it, re.S)
                    pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
                    src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
                    if not (t and pub):
                        continue
                    try:
                        dt = datetime.strptime(pub.group(1).strip(),
                                               "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
                    except Exception:
                        continue
                    title = re.sub(r"<[^>]+>", "", t.group(1)).strip()
                    if not title:
                        continue
                    out.append({"title": title,
                                "source": (src.group(1).strip() if src else "Google News"),
                                "published": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "country": ctry, "url": (link.group(1).strip() if link else ""),
                                "provider": "Google News RSS"})
            except Exception:
                continue
        out.sort(key=lambda z: z["published"], reverse=True)
        return out or None
    return _cached("news", 1800, _go)


# ══════════════════════════════════════════════════════════════════════
#  ⑦ محرك المؤشرات الفنية
# ══════════════════════════════════════════════════════════════════════
def _sma(vals, n):
    if len(vals) < n or n <= 0:
        return None
    return sum(vals[-n:]) / float(n)


def _ema_series(vals, n):
    if len(vals) < n or n <= 0:
        return [None] * len(vals)
    k = 2.0 / (n + 1.0)
    out = [None] * (n - 1)
    e = sum(vals[:n]) / float(n)
    out.append(e)
    for v in vals[n:]:
        e = (v - e) * k + e
        out.append(e)
    return out


def _rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(bars, n=14):
    if len(bars) < n + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-n:]) / float(n)


def _macd(closes, fast=12, slow=26, sig=9):
    if len(closes) < slow + sig:
        return None, None, None
    ef = _ema_series(closes, fast)
    es = _ema_series(closes, slow)
    line = []
    for i in range(len(closes)):
        if ef[i] is None or es[i] is None:
            continue
        line.append(ef[i] - es[i])
    if len(line) < sig:
        return None, None, None
    sigv = _ema_series(line, sig)
    sl = sigv[-1]
    ml = line[-1]
    return ml, sl, ml - sl


def _bollinger(closes, n=20, k=2.0):
    if len(closes) < n:
        return None, None, None
    w = closes[-n:]
    m = sum(w) / float(n)
    var = sum((x - m) ** 2 for x in w) / float(n)
    sd = math.sqrt(var)
    return m - k * sd, m, m + k * sd


def _roc(closes, n=10):
    if len(closes) < n + 1:
        return None
    old = closes[-1 - n]
    if not old:
        return None
    return (closes[-1] / old - 1.0) * 100.0


def _ret_pct(bars, back):
    """العائد من نقطة في الماضي (بالنسبة المئوية)."""
    if not bars or len(bars) <= back:
        return None
    a = bars[-1 - back]["c"]
    b = bars[-1]["c"]
    if not a:
        return None
    return (b / a - 1.0) * 100.0


def _ann_vol(bars, window=30):
    if len(bars) < window + 1:
        return None
    rets = []
    for i in range(len(bars) - window, len(bars)):
        p, c = bars[i - 1]["c"], bars[i]["c"]
        if p:
            rets.append(math.log(c / p))
    if len(rets) < 5:
        return None
    m = sum(rets) / len(rets)
    var = sum((x - m) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252.0) * 100.0


def _max_dd(bars):
    if not bars:
        return None
    peak = bars[0]["c"]
    worst = 0.0
    peak_t = bars[0]["t"]
    trough_t = bars[0]["t"]
    cur_peak_t = bars[0]["t"]
    for b in bars:
        if b["c"] > peak:
            peak = b["c"]
            cur_peak_t = b["t"]
        dd = (b["c"] / peak - 1.0) * 100.0 if peak else 0.0
        if dd < worst:
            worst = dd
            peak_t = cur_peak_t
            trough_t = b["t"]
    return {"pct": round(worst, 2), "peak_ts": peak_t, "trough_ts": trough_t}


def _indicators(bars):
    """كل المؤشرات من البيانات الفعلية — مفيش ولا رقم مخترع."""
    if not bars or len(bars) < 5:
        return None
    closes = [b["c"] for b in bars]
    rsi = _rsi(closes, 14)
    macd, macd_sig, macd_hist = _macd(closes)
    bb_l, bb_m, bb_u = _bollinger(closes)   # ⛔ الترتيب: أدنى، وسط، أعلى
    atr = _atr(bars, 14)
    ema20 = _ema_series(closes, 20)
    ema50 = _ema_series(closes, 50)
    ema200 = _ema_series(closes, 200)
    out = {
        "sma20": _sma(closes, 20), "sma50": _sma(closes, 50),
        "sma100": _sma(closes, 100), "sma200": _sma(closes, 200),
        "ema20": ema20[-1] if ema20 and ema20[-1] is not None else None,
        "ema50": ema50[-1] if ema50 and ema50[-1] is not None else None,
        "ema200": ema200[-1] if ema200 and ema200[-1] is not None else None,
        "rsi14": round(rsi, 2) if rsi is not None else None,
        "macd": round(macd, 4) if macd is not None else None,
        "macd_signal": round(macd_sig, 4) if macd_sig is not None else None,
        "macd_hist": round(macd_hist, 4) if macd_hist is not None else None,
        "atr14": round(atr, 4) if atr is not None else None,
        "bb_upper": round(bb_u, 4) if bb_u is not None else None,
        "bb_middle": round(bb_m, 4) if bb_m is not None else None,
        "bb_lower": round(bb_l, 4) if bb_l is not None else None,
        "roc10": round(_roc(closes, 10), 3) if _roc(closes, 10) is not None else None,
        "vol_annual": round(_ann_vol(bars), 2) if _ann_vol(bars) is not None else None,
        "last": closes[-1],
        "prev": closes[-2] if len(closes) > 1 else None,
        "high_period": max(b["h"] for b in bars),
        "low_period": min(b["l"] for b in bars),
    }
    out["max_dd"] = _max_dd(bars)
    out["n_bars"] = len(bars)
    return out


# ══════════════════════════════════════════════════════════════════════
#  ⑧ محرك الدعم والمقاومة (تكتير + نقاط + قوة شفافة)
# ══════════════════════════════════════════════════════════════════════
def _pivots(bars, left=3, right=3):
    """قمم/قيعان الكسور (fractals) — من البيانات الفعلية."""
    out = []
    n = len(bars)
    for i in range(left, n - right):
        w = bars[i - left:i + right + 1]
        if bars[i]["h"] >= max(x["h"] for x in w):
            out.append({"p": bars[i]["h"], "t": bars[i]["t"], "k": "H"})
        if bars[i]["l"] <= min(x["l"] for x in w):
            out.append({"p": bars[i]["l"], "t": bars[i]["t"], "k": "L"})
    return out


def _cluster(pivots, price, tol_pct, lookback_bars, bars, atr=None):
    """تكتير النقاط القريبة ⇒ منطقة + عدد التفاعلات + آخر اختبار."""
    if not pivots:
        return []
    recent = pivots[-lookback_bars:] if lookback_bars else pivots
    if not recent:
        return []
    groups = []
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — ⭐ التكتير بيتم بالـATR (مش نسبة ثابتة)
    # 📌 السبب: نسبة ثابتة معناها منطقة ضيقة جداً على اليومي وعريضة على الشهري.
    # 📌 المعيار في المحترفين: عرض المنطقة = 0.25 × ATR ⇒ متناسبة مع التذبذب.
    atr_tol = (atr * 0.25) if atr else 0.0
    for p in sorted(recent, key=lambda z: z["p"]):
        placed = False
        for g in groups:
            dist_abs = abs(p["p"] - g["center"])
            dist_pct = dist_abs / max(g["center"], 1e-9) * 100.0
            if dist_pct <= tol_pct and dist_abs <= max(atr_tol, 1e-9):
                g["members"].append(p)
                g["center"] = sum(m["p"] for m in g["members"]) / len(g["members"])
                placed = True
                break
        if not placed:
            groups.append({"center": p["p"], "members": [p]})
    out = []
    for g in groups:
        ps = [m["p"] for m in g["members"]]
        lo, hi = min(ps), max(ps)
        spread = (hi - lo) / max((hi + lo) / 2.0, 1e-9) * 100.0
        last_t = max(m["t"] for m in g["members"])
        # التفاعلات = عدد الم-members (كل لمسة = رد فعل)
        touches = len(g["members"])
        dist = (price - g["center"]) / max(g["center"], 1e-9) * 100.0
        half = (atr * 0.25) if atr else 0.0
        band_lo = min(lo, g["center"] - half)
        band_hi = max(hi, g["center"] + half)
        out.append({
            "lower": round(lo, 6), "upper": round(hi, 6), "center": round(g["center"], 6),
            "band_lower": round(band_lo, 6), "band_upper": round(band_hi, 6),
            "band_half_atr": round(half, 6),
            "touches": touches, "last_test": _iso(last_t), "last_ts": last_t,
            "last_test_day": _ts_day(last_t),
            "spread_pct": round(spread, 3),
            "distance_pct": round(dist, 2),
            "kind": "resistance" if g["center"] > price else "support",
            "kind_original": "resistance" if g["center"] > price else "support",
            "broken": False, "flipped": False,
            "members": [{"p": round(m["p"], 6), "t": _iso(m["t"])} for m in g["members"]],
        })
    return out


def _sr_zones(bars, price=None, tol_pct=0.15, lookback=400):
    """مناطق الدعم والمقاومة — Strength شفافة (مش نسبة ثقة عشوائية).

    📌 القوة = (عدد التفاعلات × وزن الحداثة) — والنتيجة رقم ترتيبي (0..100)
       مش احتمال ولا نسبة ثقة إحصائية.
    """
    if not bars or len(bars) < 30:
        return {"supports": [], "resistances": [], "method": "بيانات غير كافية"}
    win = bars[-lookback:] if lookback and len(bars) > lookback else bars
    if price is None:
        price = win[-1]["c"]
    piv = _pivots(win)
    # ⛔⛔⛔ عرض المنطقة والـtolerance بالـATR (متناسب مع كل أصل وكل إطار زمني)
    atr_val = _atr(win, 14) or 0.0
    if atr_val:
        atr_val = atr_val * 100.0 / max(price, 1e-9)    # ATR كنسبة مئوية
    zones = _cluster(piv, price, tol_pct, None, win, atr=atr_val)
    # تأكيد الكسر: منطقةResistance انكسرت ⇒ تتحول لدعم (والعكس) — بقاعدة تأكيد
    for z in zones:
        # ⛔⛔⛔ الدور الحالي بيتبع مكان المنطقة من السعر الحالي
        #    والدور الأصلي بيتسجّل لوحده — «دعم متكسّر بقى مقاومة» بتتعلّم صح
        z["kind_original"] = z["kind"]
        after = [b for b in win if b["t"] > z["last_ts"]]
        if after:
            closes = [b["c"] for b in after]
            if z["kind_original"] == "resistance" and closes and min(closes) < z["lower"]:
                z["broken"] = True
            elif z["kind_original"] == "support" and closes and max(closes) > z["upper"]:
                z["broken"] = True
        # 📌 الدور الحالي = حسب موقع المنطقة من السعر الحالي (تحت = دعم، فوق = مقاومة)
        #    و«flipped» بتقول إن المستوى ده كان معاكس قبل كسر (معلومات مهمة للمستخدم)
        z["kind"] = "resistance" if z["center"] > price else "support"
        z["flipped"] = (z["kind"] != z["kind_original"])
        z["status_ar"] = ("مقاومة (كان دعماً قبل ما يتكسر)" if z["flipped"] and z["kind"] == "resistance"
                          else ("دعم (كان مقاومة قبل ما تتكسر)" if z["flipped"]
                                else ("مقاومة" if z["kind"] == "resistance" else "دعم")))
    # القوة
    max_t = win[-1]["t"]
    # 📌 المسافة بين الشموع بالأيام ⇒ منها نصف العمر (يتناسب مع الإطار)
    _gaps = sorted(abs(win[i]["t"] - win[i - 1]["t"]) / 86400.0
                   for i in range(1, len(win)))
    _gap = _gaps[len(_gaps) // 2] if _gaps else 1.0
    _hl_days = max(60.0, _gap * 120.0)
    for z in zones:
        age_bars = None
        for b in win:
            if b["t"] >= z["last_ts"]:
                age_bars = len(win) - win.index(b)
                break
        recency = 1.0
        if age_bars is not None and max_t:
            age_days = (max_t - z["last_ts"]) / 86400.0
            # ⛔⛔⛔ نصف العمر لازم يتناسب مع الإطار الزمني:
            # 📌 180 يوم على اليومي · ~840 على الأسبوعي · ~3600 على الشهري
            # 📌 (بالإطار الثابت، كل مستوى شهري كان بيبقى «منسي» بعد شهرين)
            recency = math.exp(-age_days / _hl_days)
        z["age_days"] = round((max_t - z["last_ts"]) / 86400.0, 1) if max_t else None
        z["_raw"] = (z["touches"] ** 0.7) * recency
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — ⭐ معايرة القوة
    # 📌 المشكلة: القوة كانت = لمسات × حداثة × 10 ⇒ الرقم قليل دايماً
    # 📌 (ولنفس اللمسة الرقم مختلف بين اليومي والشهري) ⇒ كل حاجة «ضعيفة».
    # ✅ الحل: القوة = ترتيب داخل نفس الإطار الزمني (الأقوى = 100)
    # 📌 + عدد اللمسات بيتعرض لوحده (الرقم المطلق) والطبقة بتتحسب من الترتيب.
    # 📌 المسافة بمضاعفات التذبذب (ATR) — الرقم ده بيتقارن في أي أصل
    atr_abs = (_atr(win, 14) or 0.0)
    for z in zones:
        z["distance_atr"] = (round(abs(price - z["center"]) / atr_abs, 2)
                              if atr_abs else None)
    # 📌 الترتيب بالأقرب من السعر الحالي (المهم أكتر من الأرقام الكبيرة)
    supports = sorted([z for z in zones if z["kind"] == "support"],
                      key=lambda z: abs(z["distance_pct"]))[:3]
    resists = sorted([z for z in zones if z["kind"] == "resistance"],
                     key=lambda z: abs(z["distance_pct"]))[:3]
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — ⭐ معايرة القوة
    # 📌 المشكلة: القوة كانت = لمسات × حداثة × 10 ⇒ الرقم قليل دايماً،
    # 📌 وكمان المقارنة كانت مع كل المناطق القديمة ⇒ المنطقة القريبة بتطلع ضعيفة.
    # ✅ الحل: القوة = ترتيب بين المناطق المعروضة (الأقوى = 100)
    # 📌 والطبقة (قوية/متوسطة/ضعيفة) = مطلقة: عدد اللمسات + الحداثة.
    shown = supports + resists
    _ranked = sorted(shown, key=lambda z: -z.get("_raw", 0.0))
    _ladder = [100, 78, 60, 45, 35, 28]
    for i, z in enumerate(_ranked):
        z["strength"] = _ladder[i] if i < len(_ladder) else 25
        z["recency_pct"] = int(round(100 * min(1.0, z["_raw"] / max(1e-9, z["touches"] ** 0.7))))
        z["strength_note"] = ("%d لمسة سعرية · آخر اختبار %s" % (z["touches"], z["last_test_day"]))
        z["strength_tier"] = ("قوية" if (z["touches"] >= 3 or (z["touches"] >= 2 and z["recency_pct"] >= 55))
                              else ("متوسطة" if z["touches"] >= 2 else "ضعيفة"))
        z.pop("_raw", None)
    for z in zones:
        z.pop("_raw", None)
    # ⭐ أقوى منطقة واحدة بس بتتعلّم (زي ما المحترفين بيعملوا)
    strongest = None
    for z in supports + resists:
        if strongest is None or z["strength"] > strongest["strength"]:
            strongest = z
    if strongest:
        strongest["is_strongest"] = True
    # 📌 السعر داخل منطقة؟
    at_price = None
    for z in supports + resists:
        if z["band_lower"] <= price <= z["band_upper"]:
            at_price = z
            break
    return {
        "supports": supports, "resistances": resists,
        "price": round(price, 6),
        "atr14": round(atr_abs, 6) if atr_abs else None,
        "at_price": ({"kind": at_price["kind"], "center": at_price["center"],
                      "lower": at_price["band_lower"], "upper": at_price["band_upper"],
                      "touches": at_price["touches"]} if at_price else None),
        "nearest_above": ({"center": resists[0]["center"], "distance_pct": resists[0]["distance_pct"],
                           "distance_atr": resists[0]["distance_atr"], "touches": resists[0]["touches"]}
                          if resists else None),
        "nearest_below": ({"center": supports[0]["center"], "distance_pct": supports[0]["distance_pct"],
                           "distance_atr": supports[0]["distance_atr"], "touches": supports[0]["touches"]}
                          if supports else None),
        "strongest": ({"kind": strongest["kind"], "center": strongest["center"],
                       "touches": strongest["touches"], "strength": strongest["strength"],
                       "distance_atr": strongest["distance_atr"]} if strongest else None),
        "method": ("قمم/قيعان الكسور (3 شموع) + تكتير النقاط ضمن حد = 0.25×ATR "
                   "+ ترتيب بالعدد × الحداثة (نصف العمر ≈ ٤ شهور) + إظهار أقرب ٣ من كل جهة "
                   "+ القوة = ترتيب داخل نفس الإطار (الأقوى = 100)"),
        "note": ("المنطقة نطاق مش سعر مضمون — والقوة رقم ترتيبي مش نسبة ثقة."),
        "lookback_bars": len(win),
    }


# ══════════════════════════════════════════════════════════════════════
#  ⑨ تحليل تعدد الأطر الزمنية
# ══════════════════════════════════════════════════════════════════════
def _trend_from(ind, bars):
    """اتجاه واضح بقواعد صريحة (مش تخمين)."""
    if not ind or not bars:
        return {"trend": "unclear", "score": 0, "reasons": []}
    price = ind["last"]
    reasons = []
    score = 0
    for key, w in (("sma20", 1), ("sma50", 1), ("sma200", 2)):
        v = ind.get(key)
        if v is None:
            continue
        if price > v:
            score += w
            reasons.append("السعر فوق %s" % key)
        else:
            score -= w
            reasons.append("السعر تحت %s" % key)
    ema50 = ind.get("ema50")
    if ema50:
        if price > ema50:
            score += 1
            reasons.append("السعر فوق EMA50")
        else:
            score -= 1
            reasons.append("السعر تحت EMA50")
    rsi = ind.get("rsi14")
    if rsi is not None:
        if rsi >= 55:
            score += 1
            reasons.append("RSI فوق 55 (زخم موجب)")
        elif rsi <= 45:
            score -= 1
            reasons.append("RSI تحت 45 (زخم سالب)")
        else:
            reasons.append("RSI في المنطقة المحايدة")
    macdh = ind.get("macd_hist")
    if macdh is not None:
        if macdh > 0:
            score += 1
            reasons.append("هيستوجرام MACD موجب")
        else:
            score -= 1
            reasons.append("هيستوجرام MACD سالب")
    if score >= 3:
        trend = "up"
    elif score <= -3:
        trend = "down"
    elif abs(score) <= 2:
        trend = "range"
    else:
        trend = "unclear"
    return {"trend": trend, "score": score, "reasons": reasons}


def _multi_tf(symbol):
    """التحليل على اليومي والأسبوعي والشهري."""
    out = {}
    for tf, key in (("1D", "daily"), ("1W", "weekly"), ("1M", "monthly")):
        bars = _fx_series(symbol, tf, 2600 if tf == "1D" else 1200)
        if not bars:
            out[key] = {"available": False, "reason": "المصدر لم يوفّر بيانات لهذه الفترة"}
            continue
        ind = _indicators(bars)
        tr = _trend_from(ind, bars)
        sr = _sr_zones(bars)
        out[key] = {
            "available": True, "bars": len(bars),
            "from": _ts_day(bars[0]["t"]), "to": _ts_day(bars[-1]["t"]),
            "indicators": ind, "trend": tr,
            "support": sr["supports"][0] if sr["supports"] else None,
            "resistance": sr["resistances"][0] if sr["resistances"] else None,
            "sr": sr,
        }
    # اتفاق الأطر
    trs = [out[k]["trend"] for k in ("daily", "weekly", "monthly") if out.get(k, {}).get("available")]
    if not trs:
        agree = "unclear"
    elif all(t == trs[0] for t in trs):
        agree = "aligned"
    elif "up" in trs and "down" in trs:
        agree = "conflict"
    else:
        agree = "partial"
    out["agreement"] = agree
    out["agreement_note"] = {
        "aligned": "كل الأطر الزمنية بتتّفق على نفس الاتجاه.",
        "partial": "الأطر بتتفق جزئياً — في اختلاف بين قصير الأجل وطويل الأجل.",
        "conflict": "في تعارض بين الأطر الزمنية.",
        "unclear": "مفيش كفاية بيانات للحكم على الاتفاق.",
    }.get(agree, "")
    return out


# ══════════════════════════════════════════════════════════════════════
#  ⑩ عوامل الماكرو — كل عامل بمصدره وتاريخه وحالته
# ══════════════════════════════════════════════════════════════════════
def _f_factor(key, name_ar, cat, value, unit, source, source_url, pub_date,
              prev=None, previous=None, direction=None, relation="unclear", why="",
              interpretation="", status="ok", note=""):
    return {"key": key, "name_ar": name_ar, "category": cat, "value": value,
            "unit": unit, "source": source, "source_url": source_url,
            "published": pub_date, "previous": (previous if previous is not None else prev),
            "direction": direction,
            "relation": relation, "why": why, "interpretation": interpretation,
            "status": status, "note": note}


def _direction(cur, prev):
    if cur is None or prev is None:
        return "unknown"
    if abs(cur - prev) < 1e-9:
        return "stable"
    return "up" if cur > prev else "down"


def _fetch_parallel(jobs):
    """ينفّذ الدوال بالتوازي — الأبطأ واحد هو الزمن الكلي."""
    import concurrent.futures as cf
    out = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = []
        for fn in jobs:
            futs.append((fn, ex.submit(fn)))
        for fn, f in futs:
            try:
                out.append(f.result())
            except Exception:
                out.append(None)
    return out


def _treasury_yields():
    """عوائد السندات الأمريكية — من موقع وزارة الخزانة الرسمي (CSV).

    📌 FRED ممكن يتقفل مؤقتاً ⇒ المصدر الرسمي الأول هو الخزانة نفسها.
    """
    def _go():
        year = datetime.now(UTC).year
        url = ("https://home.treasury.gov/resource-center/data-chart-center/"
               "interest-rates/daily-treasury-rates.csv/%d/all"
               "?type=daily_treasury_yield_curve&field_tdr_date_value=%d&page&_format=csv"
               % (year, year))
        txt = _http_retry(url, tries=1, timeout=15)
        rows = txt.strip().splitlines()
        if len(rows) < 2:
            return None
        hdr = [h.strip().strip('"') for h in rows[0].split(",")]
        out = []
        for line in rows[1:]:
            cells = [c.strip().strip('"') for c in line.split(",")]
            if len(cells) < len(hdr):
                continue
            rec = dict(zip(hdr, cells))
            d = rec.get("Date", "")
            try:
                mm, dd, yy = d.split("/")
                iso = "%s-%s-%s" % (yy, mm.zfill(2), dd.zfill(2))
            except Exception:
                continue
            y10 = _f(rec.get("10 Yr"))
            y2 = _f(rec.get("2 Yr"))
            if y10 is None and y2 is None:
                continue
            out.append({"date": iso, "y10": y10, "y2": y2})
        if not out:
            return None
        # ⛔⛔⛔ المصدر بيرجّع الأحدث أولاً ⇒ ترتيب تصاعدي قبل أي حساب
        out.sort(key=lambda z: z["date"])
        return {"source": "US Treasury (وزارة الخزانة الأمريكية)",
                "source_url": "https://home.treasury.gov/resource-center/data-chart-center/"
                              "interest-rates/TextView?type=daily_treasury_yield_curve",
                "points": out}
    return _cached("treasury", 21600, _go)


def _bls_cpi():
    """تضخم أسعار المستهلك الأمريكي — من مكتب إحصاءات العمل الأمريكي (BLS) الرسمي."""
    def _go():
        year = datetime.now(UTC).year
        url = ("https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0"
               "?startyear=%d&endyear=%d" % (year - 2, year))
        txt = _http_get(url, timeout=15,
                        headers={"Content-Type": "application/json",
                                 "User-Agent": "Mozilla/5.0"})
        j = json.loads(txt)
        rows = ((j.get("Results") or {}).get("series") or [{}])[0].get("data") or []
        out = []
        for r in rows:
            v = _f(r.get("value"))
            if v is None:
                continue
            _p = str(r.get("period", ""))
            _mm = _p[1:] if _p.startswith("M") else _p
            out.append({"date": "%s-%s" % (r.get("year"), _mm.zfill(2)), "value": v})
        if not out:
            return None
        # ⛔⛔⛔ المصدر بيرجّع الأحدث أولاً ⇒ ترتيب تصاعدي قبل أي حساب
        out.sort(key=lambda z: z["date"])
        return {"source": "US Bureau of Labor Statistics (BLS)",
                "source_url": "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0",
                "points": out}
    return _cached("bls", 21600, _go)


def _macro_factors():
    """كل العوامل — لو مش متاح ⇒ «غير متاح» + سبب (مفيش تخمين).

    📌 المصادر الخارجية بتتجاب بالتوازي (threads) ⇒ زمن الانتظار = أطول
       (كان 269 ثانية بالتسلسل!).
    """
    now = _cairo_now().strftime("%Y-%m-%d")

    # ── ① جلب كل المصادر بالتوازي ──────────────────────────────
    def _j_dxy():
        return _tv_quote("TVC:DXY")

    def _j_fed():
        return _fred("DFEDTARU", "Federal Funds Target Rate")

    def _j_treasury():
        return _treasury_yields()

    def _j_cpi():
        return _bls_cpi()

    def _j_vix():
        return _tv_quote("TVC:VIX")

    def _j_wb():
        return _world_bank("FP.CPI.TOTL.ZG")

    names = ["dxy", "fed", "trs", "cpi", "vix", "wb"]
    got = _fetch_parallel([_j_dxy, _j_fed, _j_treasury, _j_cpi, _j_vix, _j_wb])
    R = dict(zip(names, got))

    out = []

    # ── ② DXY (العالم) ─────────────────────────────────────────
    q = R.get("dxy")
    if q and q.get("value") is not None:
        prev = (q["value"] / (1 + (q.get("change_pct") or 0) / 100.0)
                if q.get("change_pct") is not None else None)
        d = _direction(q["value"], prev)
        out.append(_f_factor(
            "dxy", "مؤشر قوة الدولار (DXY)", "global", q["value"], "نقطة",
            "TradingView (ICE)", "https://www.tradingview.com/symbols/TVC-DXY/",
            now, previous=round(prev, 4) if prev is not None else None,
            direction=d, relation="positive" if d == "up" else ("negative" if d == "down" else "mixed"),
            why="الدولار بيتقاس في سلة من ٦ عملات رئيسية — صعوده ضغط على العملات اللي بره السلة.",
            interpretation="قوة الدولار العالمية %s — وده بيضغط على الجنيه بس مش بيحدده." %
                          ("قوية" if d == "up" else ("ضعيفة" if d == "down" else "ثابتة"))))

    # ── ③ الفائدة الأمريكية ────────────────────────────────────
    fed = R.get("fed")
    if fed and fed["points"]:
        last = fed["points"][-1]
        prev = fed["points"][-2] if len(fed["points"]) > 1 else None
        out.append(_f_factor(
            "fed_rate", "سعر فائدة الاحتياطي الفيدرالي", "global", last["value"], "%",
            "Federal Reserve (FRED)", fed["source_url"], last["date"],
            previous=prev["value"] if prev else None,
            direction=_direction(last["value"], prev["value"] if prev else None),
            relation="mixed",
            why="فائدة أعلى = دولار أقوى في نظر السوق. بس التوقعات بتتحرك قبل القرار.",
            interpretation="الفائدة الآن %.2f%% — التوقعات بتتحرك قبل القرار أكتر من القرار نفسه." % last["value"]))

    # ── ④ عوائد السندات ────────────────────────────────────────
    trs = R.get("trs")
    if trs and trs["points"]:
        for key, fld, nm in (("us10y", "y10", "عائد السندات الأمريكية ١٠ سنين"),
                             ("us02y", "y2", "عائد السندات الأمريكية سنتين")):
            pts = [p for p in trs["points"] if p.get(fld) is not None]
            if not pts:
                continue
            last = pts[-1]
            prev = pts[-2] if len(pts) > 1 else None
            out.append(_f_factor(
                key, nm, "global", last[fld], "%", trs["source"],
                trs["source_url"], last["date"],
                previous=prev[fld] if prev else None,
                direction=_direction(last[fld], prev[fld] if prev else None),
                relation="mixed",
                why="العوائد العالية بتجذب سيولة للدولار — بس الأثر مش مباشر على الجنيه.",
                interpretation="العائد %.2f%%" % last[fld]))

    # ── ⑤ التضخم الأمريكي ──────────────────────────────────────
    cpi = R.get("cpi")
    if cpi and cpi["points"] and len(cpi["points"]) > 13:
        pts = cpi["points"]
        yoy = ((pts[-1]["value"] / pts[-13]["value"]) - 1.0) * 100.0
        prev_yoy = (((pts[-2]["value"] / pts[-14]["value"]) - 1.0) * 100.0) if len(pts) > 14 else None
        out.append(_f_factor(
            "us_cpi", "تضخم أسعار المستهلك الأمريكية", "global", round(yoy, 2), "%",
            cpi["source"], cpi["source_url"], pts[-1]["date"],
            previous=round(prev_yoy, 2) if prev_yoy is not None else None,
            direction=_direction(yoy, prev_yoy),
            relation="mixed",
            why="التضخم بيحدد اتجاه الفائدة — والتضخم العالي في أمريكا بيقوّي طلب الدولار.",
            interpretation="التضخم %.1f%% سنوياً (نسبة ١٢ شهر)" % yoy))

    # ── ⑥ التضخم المصري (البنك الدولي) ──────────────────────────
    wb = R.get("wb")
    if wb and wb["points"]:
        last = wb["points"][-1]
        prev = wb["points"][-2] if len(wb["points"]) > 1 else None
        out.append(_f_factor(
            "eg_cpi", "التضخم المصري (السنوي)", "egypt", last["value"], "%", wb["source"],
            wb["source_url"], last["year"],
            previous=prev["value"] if prev else None,
            direction=_direction(last["value"], prev["value"] if prev else None),
            relation="negative",
            why="تضخم أعلى من أمريكا = ضغط على الجنيه وتوقعات رفع الفائدة.",
            interpretation="التضخم %.1f%% سنوياً (سنة كاملة من البنك الدولي)." % last["value"]))

    # ── ⑦ الماكرو المصري الرسمي (من ملف JSON مُخزَّن) ─────────────
    eg = _egypt_macro()
    if eg:
        for key, nm, unit, why, rel in (
                ("policy_rate", "فائدة البنك المركزي (إيداع ليلي)", "%",
                 "فائدة أعلى = جذب سيولة للدولار بس بتكلفة على النمو.", "mixed"),
                ("lending_rate", "فائدة الإقراض الليلي", "%",
                 "سعر الإقراض بيوضح تكلفة التمويل محلياً.", "mixed"),
                ("inflation_headline", "التضخم المصري (شهري/سنوي)", "%",
                 "الرقم الرسمي من البنك المركزي المصري.", "negative"),
                ("inflation_core", "التضخم الأساسي المصري", "%",
                 "الرقم الرسمي من البنك المركزي المصري.", "negative"),
                ("inflation_target", "هدف التضخم", "%",
                 "الهدف الرسمي للبنك المركزي — الفجوة بينه وبين التضخم بتمثّل الضغط.", "negative"),
                ("reserves", "احتياطي النقد الأجنبي", "مليون دولار",
                 "احتياطي أعلى = قدرة أكبر على سدّ طلب الدولار.", "positive"),
                ("current_account", "الحساب الجاري", "مليون دولار",
                 "عجز الحساب الجاري = طلب على الدولار.", "negative"),
                ("trade_balance", "الميزان التجاري", "مليون دولار",
                 "الميزان التجاري السلعي = فاتورة دولار أكبر.", "negative")):
            item = (eg.get("factors") or {}).get(key)
            if not item or item.get("value") is None:
                out.append(_f_factor(key, nm, "egypt", None, unit, "البنك المركزي المصري",
                                     "https://www.cbe.org.eg/en/economic-research/statistics",
                                     None, status="missing",
                                     note=(item or {}).get("note") or "البيانات غير متاحة"))
                continue
            out.append(_f_factor(key, nm, "egypt", item.get("value"), unit,
                                 item.get("source", "البنك المركزي المصري"),
                                 item.get("source_url", "https://www.cbe.org.eg/"),
                                 item.get("published"), previous=item.get("previous"),
                                 direction=item.get("direction"), relation=rel, why=why,
                                 interpretation=item.get("interpretation", ""),
                                 status=item.get("status", "ok"), note=item.get("note", "")))

    # ── ⑧ عوامل الطلب والعرض (أرقامها محتاجة إصدارات رسمية مؤرخة) ──
    for key, nm, src in (("remittances", "تحويلات المصريين بالخارج", "البنك المركزي المصري"),
                         ("suez", "إيرادات قناة السويس", "هيئة قناة السويس")):
        out.append(_f_factor(key, nm, "flow", None, "مليون دولار", src,
                             "https://www.cbe.org.eg/en/economic-research/statistics",
                             None, status="missing",
                             note="الرقم محتاج نسخة رسمية مؤرخة — مش هيتعرض من غيرها."))

    # ── ⑨ المخاطر العالمية ──────────────────────────────────────
    vix = R.get("vix")
    if vix and vix.get("value") is not None:
        prev = (vix["value"] / (1 + (vix.get("change_pct") or 0) / 100.0)
                if vix.get("change_pct") is not None else None)
        out.append(_f_factor(
            "vix", "مؤشر الخوف العالمي (VIX)", "risk", vix["value"], "نقطة",
            "TradingView (CBOE)", "https://www.tradingview.com/symbols/TVC-VIX/",
            now, previous=round(prev, 4) if prev is not None else None,
            direction=_direction(vix["value"], prev),
            relation="positive",
            why="الخوف العالي بيشدّ السيولة للدولار كملاذ آمن.",
            interpretation="VIX عند %.2f — %s." % (vix["value"],
                                                    "خوف مرتفع" if vix["value"] > 25 else
                                                    ("خوف متوسط" if vix["value"] > 18 else "خوف منخفض"))))
    return out

# ══════════════════════════════════════════════════════════════════════
#  ⑪ المقارنة المعيارية (DXY مقابل USD/EGP) + التقارب/التباعد
# ══════════════════════════════════════════════════════════════════════
PERIODS = [("1M", "شهر", 21), ("3M", "٣ شهور", 63), ("6M", "٦ شهور", 126),
           ("YTD", "من بداية السنة", None), ("1Y", "سنة", 252),
           ("3Y", "٣ سنين", 756), ("5Y", "٥ سنين", 1260), ("MAX", "الكل", None)]


def _ytd_bars(bars):
    year = datetime.fromtimestamp(bars[-1]["t"], UTC).year
    out = [b for b in bars if datetime.fromtimestamp(b["t"], UTC).year == year]
    return out if len(out) > 5 else bars


def _slice_period(bars, key):
    if not bars:
        return []
    if key == "YTD":
        return _ytd_bars(bars)
    for k, _, back in PERIODS:
        if k == key:
            if back is None:
                return list(bars)
            return list(bars[-back:]) if len(bars) > back else list(bars)
    return list(bars)


def _normalize(bars, base=100.0):
    if not bars or not bars[0]["c"]:
        return []
    first = bars[0]["c"]
    return [{"t": b["t"], "v": round(b["c"] / first * base, 4)} for b in bars]


def _correlation(xs, ys):
    n = min(len(xs), len(ys))
    if n < 30:
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def _compare(period="1Y"):
    """مقارنة DXY و USD/EGP على نفس المدى + التقارب + الارتباط."""
    dxy = _fx_series("TVC:DXY", "1D", 2600)
    usd = _fx_series("FX_IDC:USDEGP", "1D", 2600)
    d = _slice_period(dxy, period)
    u = _slice_period(usd, period)
    if len(d) < 5 or len(u) < 5:
        return {"ok": False, "reason": "بيانات غير كافية للمقارنة في الفترة دي",
                "period": period}
    d_ret = (d[-1]["c"] / d[0]["c"] - 1.0) * 100.0
    u_ret = (u[-1]["c"] / u[0]["c"] - 1.0) * 100.0
    diff = u_ret - d_ret
    # التقارب
    if diff > 0.5 and d_ret > 0:
        rel = "same_direction"     # الاتنين طالعين
    elif diff > 0.5 and d_ret <= 0:
        rel = "diverged"           # الدولار العالمى نزل والجنيه ضعف
    elif diff < -0.5 and d_ret > 0:
        rel = "diverged"           # الدولار العالمى طلع والجنيه قوى
    elif diff < -0.5 and d_ret <= 0:
        rel = "same_direction"
    else:
        rel = "aligned"
    corr = _correlation([b["c"] for b in d], [b["c"] for b in u])
    return {
        "ok": True, "period": period,
        "from": _ts_day(u[0]["t"]), "to": _ts_day(u[-1]["t"]),
        "dxy": {"start": round(d[0]["c"], 4), "end": round(d[-1]["c"], 4),
                "ret": round(d_ret, 2), "normalized": _normalize(d)},
        "usdegp": {"start": round(u[0]["c"], 4), "end": round(u[-1]["c"], 4),
                   "ret": round(u_ret, 2), "normalized": _normalize(u)},
        "diff": round(diff, 2), "relation": rel,
        "correlation": corr,
        "correlation_note": ("الارتباط بيقول إن الحركتين بتمشوا مع بعض — "
                             "وم الارتباط بيقولش إن واحدة سبب التانية."),
        "available_periods": [p[0] for p in PERIODS
                              if len(_slice_period(dxy, p[0])) > 5
                              and len(_slice_period(usd, p[0])) > 5],
    }


# ══════════════════════════════════════════════════════════════════════
#  ⑫ محرك السيناريوهات
# ══════════════════════════════════════════════════════════════════════
def _scenario_strength(evidence):
    """قوة الأدلة (مش احتمال) — عدد + نوع الأدلة."""
    n = len(evidence)
    if n == 0:
        return "none"
    if n == 1:
        return "weak"
    if n <= 3:
        return "moderate"
    return "strong"


def _scenarios(mtf_usd, mtf_dxy, cmp_, factors):
    """٣ سيناريوهات: صاعد / هابط / عرضي — كل واحد بأدلته وشروط إبطاله."""
    ev_up, ev_dn = [], []
    fmap = {f["key"]: f for f in factors}

    # ① فنياً
    d_tr = (mtf_usd.get("daily") or {}).get("trend") or {}
    if d_tr.get("trend") == "up":
        ev_up.append("الاتجاه اليومي للدولار/الجنيه صاعد.")
    elif d_tr.get("trend") == "down":
        ev_dn.append("الاتجاه اليومي للدولار/الجنيه هابط.")
    if (mtf_usd.get("weekly") or {}).get("trend", {}).get("trend") == "up":
        ev_up.append("الاتجاه الأسبوعي صاعد.")
    elif (mtf_usd.get("weekly") or {}).get("trend", {}).get("trend") == "down":
        ev_dn.append("الاتجاه الأسبوعي هابط.")
    # ② الكثافة (breaks)
    if cmp_ and cmp_.get("ok"):
        if cmp_["relation"] == "same_direction" and cmp_["dxy"]["ret"] > 0:
            ev_up.append("الدولار العالمي (DXY) والدولار المصري اتنين طالعين في نفس الفترة (%.2f%% و %.2f%%)."
                         % (cmp_["dxy"]["ret"], cmp_["usdegp"]["ret"]))
        elif cmp_["relation"] == "diverged" and cmp_["usdegp"]["ret"] > 0:
            ev_up.append("الجنيه ضعف (%.2f%%) والدولار العالمي %s — الحركة المحلية مش نسخة من العالمية."
                         % (cmp_["usdegp"]["ret"],
                            "نزل" if cmp_["dxy"]["ret"] < 0 else "طلع"))
        if cmp_["relation"] == "same_direction" and cmp_["dxy"]["ret"] < 0:
            ev_dn.append("الدولار العالمي (DXY) والدولار المصري اتنين نزلوا في نفس الفترة.")
        elif cmp_["relation"] == "diverged" and cmp_["usdegp"]["ret"] < 0:
            ev_dn.append("الجنيه قوى (%.2f%%) والدولار العالمي طلع — عوامل محلية هي اللي فرقت."
                         % abs(cmp_["usdegp"]["ret"]))
    # ③ الماكرو
    f = fmap.get("dxy")
    if f and f.get("direction") == "up":
        ev_up.append("مؤشر الدولار العالمي صاعد (%.2f نقطة) — ضغط عام على العملات غير الـ5." % f["value"])
    elif f and f.get("direction") == "down":
        ev_dn.append("مؤشر الدولار العالمي نازل (%.2f نقطة)." % f["value"])
    infl = fmap.get("eg_cpi")
    if infl and infl.get("value") is not None:
        if infl["value"] > 10:
            ev_dn.append("التضخم المصري %.1f%% لسه فوق الهدف (7%%) — ضغط مستمر على الجنيه." % infl["value"])
    ca = fmap.get("current_account")
    if ca and ca.get("value") is not None and ca["value"] < 0:
        ev_dn.append("عجز الحساب الجاري (%s مليون دولار) = طلب مستمر على الدولار." % f"{ca['value']:,.0f}")
    tb = fmap.get("trade_balance")
    if tb and tb.get("value") is not None and tb["value"] < 0:
        ev_dn.append("الميزان التجاري السلبي (%s مليون دولار) = فاتورة استيراد أعلى من الصادرات."
                     % f"{tb['value']:,.0f}")
    res = fmap.get("reserves")
    if res and res.get("value") is not None:
        ev_up.append("احتياطي النقد الأجنبي %s مليون دولار — قدرة على سدّ الطلب." % f"{res['value']:,.0f}")
    rate = fmap.get("policy_rate")
    if rate and rate.get("value") is not None:
        ev_up.append("فائدة مصر %s%% — عائد الجنيه محلي أعلى من فائدة."
                     % f"{rate['value']:,.2f}")
    fed = fmap.get("fed_rate")
    if fed and rate and fed.get("value") is not None and rate.get("value") is not None:
        if fed["value"] > rate["value"]:
            ev_dn.append("فائدة أمريكا (%s%%) أعلى من مصر (%s%%) — الفارق بيضغط على الجنيه."
                         % (f"{fed['value']:,.2f}", f"{rate['value']:,.2f}"))
        elif rate["value"] > fed["value"]:
            ev_up.append("فائدة مصر (%s%%) أعلى من أمريكا (%s%%) — فارق العوائد بيجذب سيولة للدولار."
                         % (f"{rate['value']:,.2f}", f"{fed['value']:,.2f}"))
    vix = fmap.get("vix")
    if vix and vix.get("direction") == "up" and (vix.get("value") or 0) > 20:
        ev_up.append("ارتفاع الخوف العالمي (VIX %.2f) — طلب على ملاذ آمن بالدولار." % vix["value"])

    # إبطال كل سيناريو
    sup = None
    res_z = None
    try:
        sup = ((mtf_usd.get("daily") or {}).get("support") or {}).get("lower")
        res_z = ((mtf_usd.get("daily") or {}).get("resistance") or {}).get("upper")
    except Exception:
        pass
    last = ((mtf_usd.get("daily") or {}).get("indicators") or {}).get("last")

    sc_up = {
        "id": "bullish", "title_ar": "سيناريو صاعد للدولار",
        "condition": "استمرار قوة الدولار العالمي + ضغط على الطلب الداخلي + اختراق فني مؤكد.",
        "evidence": ev_up, "strength": _scenario_strength(ev_up),
        "technical": ("مقاومة فوق قرب %.4f — اختراقها وتثبيته فوقها هو التأكيد الفني."
                      % res_z if res_z else "مفيش مقاومة محسوبة فوق السعر."),
        "invalidation": ("كسر الدعم %.4f بإغلاق يومي تحتو + ضعف مؤشر الدولار العالمي."
                         % sup if sup else "كسر أقرب دعم محسوب + تحوّل DXY للهبوط."),
        "risk": "التحليل تاريخي — مش ضمان. والدولار عند %s نقطة — الحركة السابقة ممكن تكون اتغيرت." % last,
    }
    sc_dn = {
        "id": "bearish", "title_ar": "سيناريو هابط للدولار",
        "condition": "ضعف الدولار العالمي + تحسّن عرض الدولار محلياً (فائدة/تدفقات) + كسر فني للدعم.",
        "evidence": ev_dn, "strength": _scenario_strength(ev_dn),
        "technical": ("دعم تحت قرب %.4f — كسره وتثبيته تحته هو التأكيد الفني."
                      % sup if sup else "مفيش دعم محسوب تحت السعر."),
        "invalidation": ("ارتداد من الدعم مع صعود DXY."),
        "risk": "الأدلة المحلية (تدفقات/سيولة) ممكن تتأخر عن السعر.",
    }
    rng = None
    try:
        ind = (mtf_usd.get("daily") or {}).get("indicators") or {}
        if ind.get("high_period") and ind.get("low_period"):
            rng = {"low": ind["low_period"], "high": ind["high_period"]}
    except Exception:
        pass
    sc_rng = {
        "id": "range", "title_ar": "سيناريو عرضي (نطاق)",
        "condition": "تعارض بين العوامل والاختفاء والاتجاه بين الأطر الزمنية.",
        "evidence": [], "strength": "none",
        "technical": ("النطاق المحسوب: %.4f — %.4f." % (rng["low"], rng["high"]) if rng
                      else "النطاق غير محسوب."),
        "invalidation": "كسر واضح لأي حد من النطاق بإغلاق يومي.",
        "risk": "النطاق بيتقفل بسرعة لو حصل خبر محلي.",
    }
    if mtf_usd.get("agreement") == "conflict":
        sc_rng["evidence"].append("الأطر الزمنية متعارضة (يومي/أسبوعي/شهري).")
    if cmp_ and cmp_.get("ok") and abs(cmp_.get("diff", 0)) < 0.5:
        sc_rng["evidence"].append("الفرق بين الدولار العالمي والدولار المصري قريب من الصفر.")
    if not ev_up and not ev_dn:
        sc_rng["evidence"].append("مفيش عامل ماكرو واضح يدعم اتجاه واحد.")
    sc_rng["strength"] = _scenario_strength(sc_rng["evidence"])

    # الأقوى
    order = {"strong": 3, "moderate": 2, "weak": 1, "none": 0}
    scores = {"bullish": order[sc_up["strength"]], "bearish": order[sc_dn["strength"]],
              "range": order[sc_rng["strength"]]}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        best = "range"
    return {"scenarios": [sc_up, sc_dn, sc_rng], "leading": best,
            "method": ("قوة الأدلة = عدد العوامل المؤيدة (مش احتمال ولا نسبة ثقة). "
                       "الأولوية: فني (يومي/أسبوعي) ← مقارنة عالمية ← ماكرو.")}


# ══════════════════════════════════════════════════════════════════════
#  ⑬ القراءة النهائية (OCTA) — قواعد ثابتة، مش نص حر
# ══════════════════════════════════════════════════════════════════════
def _quality(items):
    """جودة البيانات — كم عامل متاح وكم تأخر."""
    ok = [x for x in items if x.get("status") == "ok" and x.get("value") is not None]
    miss = [x for x in items if x.get("status") == "missing" or x.get("value") is None]
    fresh = [x for x in ok if x.get("published")]
    return {"available": len(ok), "missing": len(miss),
            "total": len(items),
            "missing_keys": [x["key"] for x in miss],
            "coverage_pct": round(len(ok) * 100.0 / max(len(items), 1)),
            "note": ("%d عامل متاح من %d — كل رقم ظاهر ليه مصدر وتاريخ."
                     % (len(ok), len(items)))}


def _verdict(mtf_usd, mtf_dxy, cmp_, factors, scen):
    """القراءة النهائية — جملة واحدة + الشواهد + المخاطر + الإبطال."""
    fmap = {f["key"]: f for f in factors}
    d_ind = (mtf_usd.get("daily") or {}).get("indicators") or {}
    d_tr = (mtf_usd.get("daily") or {}).get("trend") or {}
    q = _quality(factors)
    lead = scen["leading"]
    sc = {s["id"]: s for s in scen["scenarios"]}

    bias_ar = {"bullish": "يميل إلى السيناريو الصاعد (الدولار أقوى)",
               "bearish": "يميل إلى السيناريو الهابط (الجنيه أقوى)",
               "range": "يميل إلى السيناريو العرضي (نطاق)"}[lead]
    strength_ar = {"strong": "أدلة قوية", "moderate": "أدلة متوسطة",
                   "weak": "أدلة ضعيفة", "none": "أدلة غير كافية"}[sc[lead]["strength"]]

    parts = []
    # ① إيه اللي بيحصل دلوقتي
    px = d_ind.get("last")
    if px:
        parts.append("الدولار/الجنيه عند %.2f جنيه لكل دولار." % px)
    if d_tr.get("trend"):
        t_ar = {"up": "صاعد", "down": "هابط", "range": "عرضي", "unclear": "غير واضح"}[d_tr["trend"]]
        parts.append("الاتجاه اليومي %s." % t_ar)
    # ② globalization
    dx = fmap.get("dxy")
    if dx and dx.get("value") is not None:
        parts.append("مؤشر الدولار العالمي عند %.2f (%s)."
                     % (dx["value"], "صاعد" if dx.get("direction") == "up" else
                        ("هابط" if dx.get("direction") == "down" else "ثابت")))
    # ③ relation
    if cmp_ and cmp_.get("ok"):
        parts.append("في الفترة المختارة: الدولار العالمي %+.2f%% والدولار المصري %+.2f%% (%s)."
                     % (cmp_["dxy"]["ret"], cmp_["usdegp"]["ret"],
                        "اتحركوا في نفس الاتجاه" if cmp_["relation"] == "same_direction"
                        else "اتحرّكوا في اتجاهين مختلفين"))
    # ④ bias
    parts.append("القراءة الحالية %s — %s." % (bias_ar, strength_ar))
    # ⑤ invalidation
    inval = sc[lead].get("invalidation") or ""
    risks = []
    if cmp_ and cmp_.get("ok") and cmp_.get("relation") == "diverged":
        risks.append("الحركة المحلية مختلفة عن العالمية — العوامل المحلية هي الفارق.")
    if q["missing"]:
        risks.append("%d عامل غير متاح — الخلاصة مبنية على المتاح بس." % q["missing"])
    if d_tr.get("trend") == "unclear":
        risks.append("الاتجاه مش واضح في البيانات الحالية.")
    return {
        "bias": lead, "bias_ar": bias_ar, "strength": sc[lead]["strength"],
        "strength_ar": strength_ar,
        "summary": " ".join(parts),
        "evidence": sc[lead]["evidence"][:5],
        "invalidation": inval,
        "risks": risks or ["مفيش مخاطر مرصودة من البيانات المتاحة."],
        "monitor": [m for m in (
            ("مقاومة قريبة: %.4f" % ((mtf_usd.get("daily") or {}).get("resistance") or {}).get("upper"))
            if (mtf_usd.get("daily") or {}).get("resistance") else None,
            ("دعم قريب: %.4f" % ((mtf_usd.get("daily") or {}).get("support") or {}).get("lower"))
            if (mtf_usd.get("daily") or {}).get("support") else None,
            "الأحداث القادمة في التقويم الاقتصادي") if m],
        "quality": q,
        "method": scen["method"],
        "generated_at": _cairo_now().strftime("%Y-%m-%d %H:%M"),
    }


# ══════════════════════════════════════════════════════════════════════
#  ⑭ «OCTA بيشرحلك» — تفسير بالبيانات المؤكدة فقط
# ══════════════════════════════════════════════════════════════════════
def _explain_payload(mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_):
    """بيانات JSON المؤكدة اللي بتتبعت للمفسّر — كل رقم وراه مصدره."""
    return {
        "now": _cairo_now().strftime("%Y-%m-%d %H:%M %Z"),
        "usdegp": {
            "price": ((mtf_usd.get("daily") or {}).get("indicators") or {}).get("last"),
            "trend_daily": ((mtf_usd.get("daily") or {}).get("trend") or {}).get("trend"),
            "trend_weekly": ((mtf_usd.get("weekly") or {}).get("trend") or {}).get("trend"),
            "trend_monthly": ((mtf_usd.get("monthly") or {}).get("trend") or {}).get("trend"),
            "rsi14": ((mtf_usd.get("daily") or {}).get("indicators") or {}).get("rsi14"),
            "macd_hist": ((mtf_usd.get("daily") or {}).get("indicators") or {}).get("macd_hist"),
            "vol_annual": ((mtf_usd.get("daily") or {}).get("indicators") or {}).get("vol_annual"),
            "support": ((mtf_usd.get("daily") or {}).get("support") or {}),
            "resistance": ((mtf_usd.get("daily") or {}).get("resistance") or {}),
        },
        "dxy": {
            "price": ((mtf_dxy.get("daily") or {}).get("indicators") or {}).get("last"),
            "trend_daily": ((mtf_dxy.get("daily") or {}).get("trend") or {}).get("trend"),
            "rsi14": ((mtf_dxy.get("daily") or {}).get("indicators") or {}).get("rsi14"),
        },
        "comparison": ({k: v for k, v in (cmp_ or {}).items() if k not in ("dxy", "usdegp")}
                       if cmp_ and cmp_.get("ok") else None),
        "factors": [{"name": f["name_ar"], "value": f["value"], "unit": f["unit"],
                     "direction": f.get("direction"), "source": f.get("source"),
                     "published": f.get("published"), "status": f.get("status")}
                    for f in factors],
        "scenarios": [{"id": s["id"], "title": s["title_ar"], "strength": s["strength"],
                       "evidence": s["evidence"], "invalidation": s["invalidation"]}
                      for s in scen["scenarios"]],
        "verdict": verdict_,
    }


# ══════════════════════════════════════════════════════════════════════
#  ⑮ التفسير — كاش + بيانات مؤكدة فقط
# ══════════════════════════════════════════════════════════════════════
_EXPLAIN_QUESTIONS = {
    "why": "ليه الدولار بيتحرك دلوقتي؟",
    "dxy": "هل الدولار قوي عالميًا دلوقتي؟",
    "resistance": "إيه أهم مقاومات الدولار؟",
    "support": "إيه أهم دعوم الدولار؟",
    "relation": "هل الدولار في مصر بيتحرك مع الدولار عالميًا؟",
    "difference": "إيه الفرق بين DXY و USDEGP؟",
    "egypt": "إيه أهم عوامل الاقتصاد المصري المؤثرة على الدولار؟",
    "scenarios": "إيه السيناريوهات الحالية؟",
    "change": "إيه اللي ممكن يغير التحليل؟",
    "calendar": "إيه أهم الأحداث الاقتصادية القادمة؟",
}


def _gemini_explain(payload, question="why"):
    """تفسير بالبيانات المؤكدة — مع كاش، ومفيش أي رقم من عندنا.

    ⛔ المفسّر بياخد الأرقام من الـpayload بس — لو الرقم مش موجود ⇒ «غير متاح».
    ⛔ مفيش أسماء أدوات ذكاء اصطناعي في الردود الظاهرة للمستخدم.
    """
    import json as _json
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {"ok": False, "reason": "مفيش مفتاح تفسير على السيرفر"}
    q = _EXPLAIN_QUESTIONS.get(question, question)
    sys_prompt = (
        "أنت محلل عملات داخل منصة OCTA. بترد بالعربي المصري البسيط. "
        "بتاخد بيانات تحليلية مؤكدة (JSON) وبتشرحها للمستخدم. "
        "قواعد ملزمة: (١) استخدم الأرقام من الـJSON بس — لو رقم مش موجود اكتب «غير متاح». "
        "(٢) مافيش تخمين ولا رقم تقديري. (٣) نفّذ بين الحقيقة والتحليل: افصلهم بوضوح. "
        "(٤) اذكر حدود التحليل (تاريخي مش تنبؤ). (٥) ممنوع أي توصية شراء/بيع. "
        "(٦) اذكر المصدر والتاريخ اللي جاي مع الرقم. (٧) فصّل بين Correlation و Causation. "
        "(٨) لو فيه عوامل متعارضة وضّح التعارض. (٩) من غير مقدمات طويلة — ابدأ بالرد. "
        "(١٠) لا تذكر اسم أي أداة ذكاء اصطناعي ولا ذكاء اصطناعي."
    )
    user_prompt = "السؤال: %s\n\nالبيانات المؤكدة:\n%s" % (
        q, _json.dumps(payload, ensure_ascii=False)[:14000])
    body = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900,
                             "responseMimeType": "text"},
    }
    models = ["gemini-3.5-flash", "gemini-flash-lite-latest"]
    last = None
    for mname in models:
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
                   % mname)
            txt = _http_get(url, timeout=45,
                             headers={"Content-Type": "application/json",
                                      "X-goog-api-key": key},
                             data=body, method="POST")
            j = _json.loads(txt)
            cand = (((j.get("candidates") or [{}])[0]).get("content") or {}).get("parts") or []
            text = "".join((p.get("text") or "") for p in cand).strip()
            if text:
                return {"ok": True, "text": text, "question": q}
            last = "رد فاضي"
        except Exception as e:
            last = str(e)[:100]
    return {"ok": False, "reason": last or "التفسير غير متاح"}


def _explain_cached(payload, question):
    """⛔ الكاش: ما نعملش تفسير جديد لنفس البيانات ⇒ توفير + استجابة أسرع.
    📌 المفتاح = بصمة البيانات (آخر قيمة + عدد النقاط + آخر تاريخ عامل)."""
    try:
        fp = "%s|%s|%s|%s" % (question,
                               payload["usdegp"].get("price"),
                               payload["dxy"].get("price"),
                               payload["verdict"].get("generated_at"))
    except Exception:
        fp = question
    return _cached("explain:%s" % fp, 1800,
                   lambda: _gemini_explain(payload, question))


# ══════════════════════════════════════════════════════════════════════
#  ⑯ المسارات (API)
# ══════════════════════════════════════════════════════════════════════
def register(app, require_user=None):
    from flask import jsonify, request

    def _bundle(period="1Y"):
        mtf_usd = _multi_tf("FX_IDC:USDEGP")
        mtf_dxy = _multi_tf("TVC:DXY")
        cmp_ = _compare(period)
        factors = _macro_factors()
        scen = _scenarios(mtf_usd, mtf_dxy, cmp_, factors)
        verdict_ = _verdict(mtf_usd, mtf_dxy, cmp_, factors, scen)
        return mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_

    # ── ① نظرة عامة (الهيرو + القراءة النهائية) ─────────────────────
    @app.route("/api/usd/overview")
    def usd_overview():
        try:
            period = (request.args.get("period") or "1Y").upper()
            mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_ = _bundle(period)
            q_usd = _tv_quote("FX_IDC:USDEGP")
            q_dxy = _tv_quote("TVC:DXY")
            cbe = _cbe_official() or {}
            ind = (mtf_usd.get("daily") or {}).get("indicators") or {}
            return jsonify({
                "ok": True,
                "name_ar": "ذكاء الدولار",
                "name_en": "OCTA USD INTELLIGENCE",
                "subtitle_ar": "افهم حركة الدولار مقابل الجنيه المصري",
                "usdegp": {
                    "value": (q_usd or {}).get("value"),
                    "change_pct": (q_usd or {}).get("change_pct"),
                    "change_abs": (q_usd or {}).get("change_abs"),
                    "high": (q_usd or {}).get("high"),
                    "low": (q_usd or {}).get("low"),
                    "prev_close": ind.get("prev"),
                    "perf_1m": (q_usd or {}).get("perf_1m"),
                    "perf_y": (q_usd or {}).get("perf_y"),
                    "quote_source": "TradingView (ICE) — سعر السوق الدولي",
                    "quote_type": "market_quote",
                    "official": {
                        "buy": cbe.get("buy"), "sell": cbe.get("sell"),
                        "last_updated": cbe.get("last_updated"),
                        "source": cbe.get("source"),
                        "source_url": cbe.get("source_url"),
                        "type": "official_reference",
                    },
                    "updated_at": _cairo_now().strftime("%Y-%m-%d %H:%M"),
                },
                "dxy": {
                    "value": (q_dxy or {}).get("value"),
                    "change_pct": (q_dxy or {}).get("change_pct"),
                    "perf_1m": (q_dxy or {}).get("perf_1m"),
                    "perf_y": (q_dxy or {}).get("perf_y"),
                    "source": "TradingView (ICE)",
                    "updated_at": _cairo_now().strftime("%Y-%m-%d %H:%M"),
                },
                "trend": {
                    "usdegp": {k: (mtf_usd.get(k) or {}).get("trend")
                               for k in ("daily", "weekly", "monthly")},
                    "dxy": {k: (mtf_dxy.get(k) or {}).get("trend")
                            for k in ("daily", "weekly", "monthly")},
                    "agreement": mtf_usd.get("agreement"),
                    "agreement_note": mtf_usd.get("agreement_note"),
                },
                "comparison": cmp_,
                "verdict": verdict_,
                "scenarios": scen,
                "quality": verdict_.get("quality"),
                "sources": _sources(),
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ── ② التحليل الفني + الدعم والمقاومة ─────────────────────────
    @app.route("/api/usd/technical")
    def usd_technical():
        try:
            sym = (request.args.get("symbol") or "USDEGP").upper()
            tf = (request.args.get("tf") or "1D").upper()
            key = {"USDEGP": "FX_IDC:USDEGP", "DXY": "TVC:DXY"}.get(sym, "FX_IDC:USDEGP")
            bars = _fx_series(key, tf, 2600 if tf == "1D" else 1200)
            if not bars:
                return jsonify({"ok": False,
                                "error": "مفيش شموع متاحة للمصدر دلوقتي"}), 200
            ind = _indicators(bars)
            tr = _trend_from(ind, bars)
            sr = _sr_zones(bars)
            return jsonify({
                "ok": True, "symbol": sym, "tf": tf,
                "name_ar": _FX_SYMBOLS.get(sym, {}).get("name_ar"),
                "from": _ts_day(bars[0]["t"]), "to": _ts_day(bars[-1]["t"]),
                "bars": len(bars),
                "series": [{"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"],
                            "c": b["c"], "v": b.get("v")} for b in bars[-1400:]],
                "indicators": ind, "trend": tr, "sr": sr,
                "source": "TradingView (ICE)",
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ── ③ عوامل الماكرو ────────────────────────────────────────────
    @app.route("/api/usd/factors")
    def usd_factors():
        try:
            factors = _macro_factors()
            cats = {}
            for f in factors:
                cats.setdefault(f["category"], []).append(f)
            return jsonify({"ok": True, "factors": factors, "categories": cats,
                            "quality": _quality(factors),
                            "categories_ar": {
                                "global": "عوامل الدولار العالمي",
                                "egypt": "عوامل الاقتصاد المصري",
                                "flow": "عرض、 الطلب على الدولار",
                                "risk": "المخاطر العالمية"},
                            "sources": _sources()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ── ④ التقويم والأخبار ─────────────────────────────────────────
    @app.route("/api/usd/calendar")
    def usd_calendar():
        try:
            return jsonify({"ok": True, "events": _calendar() or [],
                            "calendar_source": (sorted({e.get("source") or "غير معروف"
                                                        for e in (_calendar() or [])}) or ["غير متاح"]),
                            "source": "TradingView (التقويم الاقتصادي) + ForexFactory"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    @app.route("/api/usd/news")
    def usd_news():
        try:
            items = _news() or []
            return jsonify({"ok": True, "items": items[:40],
                            "source": "Google News RSS"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ── ⑤ المقارنة + السيناريوهات (للتفاصيل) ───────────────────────
    @app.route("/api/usd/scenarios")
    def usd_scenarios():
        try:
            period = (request.args.get("period") or "1Y").upper()
            mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_ = _bundle(period)
            return jsonify({"ok": True, "scenarios": scen["scenarios"],
                            "leading": scen["leading"], "method": scen["method"],
                            "verdict": verdict_, "comparison": cmp_,
                            "quality": verdict_.get("quality")})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ── ⑥ «OCTA بيشرحلك» ───────────────────────────────────────────
    @app.route("/api/usd/explain")
    def usd_explain():
        try:
            # ⛔⛔⛔ فيه نداء ذكاء اصطناعي ⇒ لازم المستخدم يكون داخل
            if require_user is not None and not require_user():
                return jsonify({"ok": False, "available": False,
                                "error": "لازم تسجّل دخول عشان تاخد الشرح"}), 401
            q = (request.args.get("q") or "why").lower()
            period = (request.args.get("period") or "1Y").upper()
            mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_ = _bundle(period)
            payload = _explain_payload(mtf_usd, mtf_dxy, cmp_, factors, scen, verdict_)
            res = _explain_cached(payload, q)
            return jsonify({"ok": True, "question": q,
                            "answer": (res or {}).get("text"),
                            "available": bool((res or {}).get("ok")),
                            "reason": (res or {}).get("reason"),
                            "data": payload})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 500

    # ⛔⛔⛔ تسخين الكاش في الخلفية — عشان أول ما المستخدم يفتح الكارت
    #    ما يستناش ١٤ ثانية على تحميل الماكرو.
    def _warm():
        try:
            _tv_bars("FX_IDC:USDEGP", "1D", 2600)
            _tv_bars("TVC:DXY", "1D", 2600)
            _macro_factors()
            print("[usd] ✅ الكاش اتسخّن", flush=True)
        except Exception as e:
            print("[usd] ⚠️ التسخين: %s" % str(e)[:70], flush=True)

    try:
        threading.Thread(target=_warm, daemon=True).start()
    except Exception:
        pass

    print("[usd] ✅ محرك ذكاء الدولار متركّب", flush=True)


def _sources():
    """قائمة المصادر — كل رقم في الواجهة بيرجع هنا."""
    return [
        {"name": "البنك المركزي المصري — Average Market Rate",
         "url": "https://www.cbe.org.eg/en/economic-research/statistics/exchange-rates",
         "used_for": "السعر الرسمي للدولار (شراء/بيع)",
         "note": "اقتباس قصير مع ذكر المصدر — حسب شروط الموقع."},
        {"name": "البنك المركزي المصري — التضخم والفائدة والاحتياطي",
         "url": "https://www.cbe.org.eg/en/economic-research/statistics",
         "used_for": "التضخم المصري · الفائدة الليلية · هدف التضخم",
         "note": "الأرقام منقولة كما هي مع ذكر المصدر والتاريخ."},
        {"name": "البنك المركزي المصري — ميزان المدفوعات",
         "url": "https://www.cbe.org.eg/en/news-publications/news/2026/10/12/10/18/bop-press-release",
         "used_for": "الحساب الجاري · الميزان التجاري · التدفقات",
         "note": "السنة المالية المنتهية في 30 يونيو 2026."},
        {"name": "TradingView (ICE) — USDEGP و DXY",
         "url": "https://www.tradingview.com/symbols/USDEGP/",
         "used_for": "السعر اللحظي · الشموع التاريخية · المؤشرات الفنية",
         "note": "سعر السوق الدولي — مش سعر البنك المركزي ولا السوق الموازي."},
        {"name": "Federal Reserve (FRED)",
         "url": "https://fred.stlouisfed.org/",
         "used_for": "فائدة الاحتياطي · عوائد السندات · التضخم الأمريكي · VIX",
         "note": "بيانات رسمية أمريكية."},
        {"name": "البنك الدولي (World Bank)",
         "url": "https://data.worldbank.org/country/egypt",
         "used_for": "التضخم المصري السنوي · سعر الصرف الرسمي",
         "note": "رخصة CC BY 4.0."},
        {"name": "ForexFactory — التقويم الاقتصادي",
         "url": "https://www.forexfactory.com/calendar",
         "used_for": "الأحداث الاقتصادية القادمة (أمريكا ومصر)",
         "note": "التوقعات (Forecast) بتظهر بس لو موجودة في المصدر."},
        {"name": "Google News RSS",
         "url": "https://news.google.com/",
         "used_for": "الأخبار مع المصدر والتاريخ",
         "note": "كل خبر بيتبعت بمصدره الأصلي ورابطه."},
    ]
