# -*- coding: utf-8 -*-
"""
🐙 OCTA — محرك إشارة الذهب (XAU/USD)
═════════════════════════════════════════════════════════════════════════

📌 مبدأ المشروع: النتيجة = قواعد رياضية ثابتة. الشرح = جملة عربية.
   مفيش ذكاء اصطناعي بيختار لون. اللون بيخرج من رقم.

🎯 بيقرأ؟ signal, deep, learn, health, reset

🧠 التعلم المحدود (Bounded Learning)
─────────────────────────────────────
كل إشارة ملوّنة بتتسجل مع قيمة كل عامل. بعد ما الإشارة تتحل
(هدف اتقبل / وقف خسارة / انتهت المدة) بنحسب R، ومنه بنعدّل
الأوزان بمعامل تحديث **محدود**:

    w_i' = clamp( w_i × (1 + lr × edge_i), 0.5·w_i0, 1.5·w_i0 )

قواعد صلبة — مفيش استثناء:
  • أقل عدد عينات قبل أي تعديل     = 30 إشارة متحلّة
  • أقصى تغيير للوزن الواحد/دورة   = 5%
  • سقف/ أرضية الوزن               = 0.5× و 1.5× من الوزن الأول
  • قاطع أمان                      : لو دقة آخر 30 < 38% ← تجميد + أزرق
  • كل تغيير بيتسجل في سجل تدقيق   : gold_learn.json → log[]
  • الأوزان بتتثبت في نسخة         : كل دورة ليها version

❌ مش بيعمل: تعديل منطق الكود، أو إعادة كتابة قواعد القرار.
   اللي بيتعلم أرقام (أوزان) جوه إطار ثابت — وده الفرق بين
   «إحصاء» و«كود بيعيد كتابة نفسه» (والأخير خطر على فلوس حقيقية).

🗄️ الملفات: /app/gold_learn.json  (persistence — تعيش بعد restart)
"""

import json, os, math, time, threading, statistics
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    import requests
except Exception:                                    # pragma: no cover
    requests = None

try:
    import urllib.request as _urlreq
    import urllib.parse as _urlparse
except Exception:                                    # pragma: no cover
    _urlreq = _urlparse = None

CAIRO = ZoneInfo("Africa/Cairo")
UTC = timezone.utc

LEARN_FILE = Path(os.environ.get("GOLD_LEARN_PATH", "/app/gold_learn.json"))
SIGNAL_TTL = int(os.environ.get("GOLD_SIGNAL_TTL", "60"))       # ثانية
DEEP_TTL = int(os.environ.get("GOLD_DEEP_TTL", "300"))          # 5 دقايق
CONF_MIN = float(os.environ.get("GOLD_CONF_MIN", "2.5"))        # أقصى فرق بين المصادر

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
       "Accept": "application/json,text/plain,*/*"}

# ══════════════════════════════════════════════════════════════════════
#  ① الأوزان — دي اللي بتتعلم (أرقام جوه حدود) — منطق القرار ثابت
# ══════════════════════════════════════════════════════════════════════
FACTORS = ["htf_bias", "mtf_align", "sweep", "shift", "retest",
           "session", "macro", "volregime"]

BASE_W = {
    "htf_bias":   1.30,
    "mtf_align":  1.15,
    "sweep":      1.00,
    "shift":      1.00,
    "retest":     0.80,
    "session":    0.70,
    "macro":      0.90,
    "volregime":  0.60,
}

#_factor floor / ceiling كنسبة من الوزن الأول
W_FLOOR, W_CEIL = 0.50, 1.50
MIN_SAMPLES_FOR_UPDATE = 30
MAX_STEP = 0.05                 # 5% أقصى تغيير لوزن واحد في دورة
LR = 0.15                       # معامل التعلم
BREAKER_ACC = 0.38              # لو الدقة نزلت تحت كده ← تجميد
BREAKER_WIN = 30

# عتبة الت turning: الدرجة المطلقة المطلوبة لونه ≠ أزرق
TURN_BASE = 0.34                # من 1.0 (= 34 درجة من 100)
TURN_NEWS_PENALTY = 0.10        # كل ماBearne كتر ← العتبة أعلى
TURN_VOL_PENALTY = 0.08

SIGNAL_TTL_SLOTS = {}           # كاش في الذاكرة
LOCK = threading.Lock()

# ══════════════════════════════════════════════════════════════════════
#  ② أدوات عامة
# ══════════════════════════════════════════════════════════════════════
def _r2(x, n=2):
    try:
        return round(float(x), n)
    except Exception:
        return None


def _now_cairo():
    return datetime.now(CAIRO)


def _http_json(url, timeout=12, method="GET", headers=None, body=None):
    """ يطلب JSON — الطلب راجعت لـ requests لو موجود، وإلا urllib.

    ⛔ urllib مفيش TLS verify option على كل الإصدارات، فبنستعمل
    requests لو موجود (Railway عنده)FallBack محلي/Testing.
    """
    h = dict(_UA)
    if headers:
        h.update(headers)
    if requests is not None:
        r = requests.request(method, url, headers=h, timeout=timeout,
                             data=body if body is not None else None)
        r.raise_for_status()
        return r.json()
    if _urlreq is None:
        raise RuntimeError("مفيش HTTP client متاح")
    req = _urlreq.Request(url, headers=h, method=method,
                          data=body.encode() if isinstance(body, str) else body)
    with _urlreq.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _http_retry(url, timeout=12, tries=3, backoff=1.1, **kw):
    """ إعادة محاولة مع تراجع أُسّي.

    ⛔ OKX بيرجع 503 لما نطلب كتير أوي في الثانية. من غير ده،
    التحليل كله يقع لو اتنين طلبات اتworkingوا مع بعض.
    """
    last = None
    for i in range(tries):
        try:
            return _http_json(url, timeout=timeout, **kw)
        except Exception as e:
            last = e
            msg = str(e)
            retriable = any(k in msg for k in
                            ("503", "502", "504", "429", "timed out",
                             "Connection", "reset", "Remote end closed"))
            if not retriable or i == tries - 1:
                raise
            time.sleep(backoff * (2 ** i))
    raise last


def _ema(vals, n):
    if not vals or len(vals) < n:
        return None
    e = sum(vals[:n]) / n
    k = 2.0 / (n + 1)
    for x in vals[n:]:
        e = x * k + e * (1 - k)
    return e


def _atr(bars, n=14):
    if not bars or len(bars) < n + 1:
        return None
    tr = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr[-n:]) / float(n)


def _rsi(closes, n=14):
    if not closes or len(closes) < n + 1:
        return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        g += max(d, 0.0)
        l += max(-d, 0.0)
    g /= n
    l /= n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = (g * (n - 1) + max(d, 0.0)) / n
        l = (l * (n - 1) + max(-d, 0.0)) / n
    return 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)


# ══════════════════════════════════════════════════════════════════════
#  ③ جلب البيانات — 4 مصادر مستقلة + تقويم
# ══════════════════════════════════════════════════════════════════════
OKX_BAR = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "1H", "H4": "4H", "D1": "1D"}

# ⛔ كاش الشموع: الشمعة ماتتغيرش غير أول ما تقفل.
#    M15 بيقفل كل ١٥ دقيقة → مفيش داعي نطلبه كل ٦٠ ثانية.
#    ده بيقلّل طلبات OKX بنسبة ٩٠٪ وبيمنع الـ 503.
CANDLE_TTL = {"M5": 90, "M15": 300, "H1": 660, "H4": 1800, "D1": 3600}
_CANDLE_CACHE = {}


def fetch_okx(bar, limit=300, pages=1, ttl=None):
    """PAXG/USDT — ٢٤ ساعة، تتبّع السبوت، كل الفريمات. كاش + إعادة محاولة."""
    ck = "%s:%d:%d" % (bar, limit, pages)
    hit = _CANDLE_CACHE.get(ck)
    eff = ttl if ttl is not None else CANDLE_TTL.get(
        {"1m": "M5", "5m": "M5", "15m": "M15", "1H": "H1",
         "4H": "H4", "1D": "D1"}.get(bar, "M15"), 120)
    if hit and (time.time() - hit["_t"]) < eff:
        return hit["v"]
    out, after = [], None
    for _ in range(pages):
        url = ("https://www.okx.com/api/v5/market/candles"
               "?instId=PAXG-USDT&bar=%s&limit=%d" % (bar, limit))
        if after:
            url += "&after=%d" % after
        d = _http_retry(url).get("data") or []
        if not d:
            break
        out += d
        after = int(d[-1][0])
    seen, bars = set(), []
    for b in sorted(out, key=lambda z: int(z[0])):
        ts = int(b[0]) // 1000
        if ts in seen:
            continue
        seen.add(ts)
        try:
            bars.append({"t": ts, "o": float(b[1]), "h": float(b[2]),
                         "l": float(b[3]), "c": float(b[4]),
                         "v": float(b[5]), "done": b[8] == "1"})
        except Exception:
            continue
    if not bars:
        # ⛔ الشبكة وقعت — نرجّع آخر Known Good بدل ما نرجّع فاضي ونكسر
        #    التحليل كله. الخطأ في Freshness gate بيمنع الإشارة، وده صح.
        if hit:
            return hit["v"]
        raise RuntimeError("OKX: مفيش شموع (%s)" % bar)
    _CANDLE_CACHE[ck] = {"_t": time.time(), "v": bars}
    return bars


def fetch_yahoo(sym, interval="15m", rng="1mo"):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
           "?interval=%s&range=%s" % (sym, interval, rng))
    d = _http_retry(url)["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    vol = d["indicators"].get("quote", [{}])[0].get("volume") or []
    bars = []
    for i, t in enumerate(d["timestamp"]):
        if q["close"][i] is None:
            continue
        bars.append({"t": t, "o": q["open"][i], "h": q["high"][i],
                     "l": q["low"][i], "c": q["close"][i],
                     "v": vol[i] if i < len(vol) else None})
    return d["meta"], bars


def fetch_spot():
    """ consensus من ٣ مصادر — لو اتفقوا، السعر موثوق."""
    mids, src = [], {}
    try:
        g = _http_retry("https://api.gold-api.com/price/XAU")
        src["gold-api"] = g.get("price")
        if isinstance(g.get("price"), (int, float)):
            mids.append(float(g["price"]))
    except Exception:
        pass
    try:
        t = _http_retry("https://www.okx.com/api/v5/market/ticker?instId=PAXG-USDT")["data"][0]
        mid = (float(t["bidPx"]) + float(t["askPx"])) / 2.0
        src["okx"] = _r2(mid)
        src["okx_spread"] = _r2(float(t["askPx"]) - float(t["bidPx"]))
        mids.append(mid)
    except Exception:
        pass
    try:
        s = _http_retry("https://forex-data-feed.swissquote.com/public-quotes/"
                           "bboquotes/instrument/XAU/USD")[0]["spreadProfilePrices"][0]
        mid = (float(s["bid"]) + float(s["ask"])) / 2.0
        src["swissquote"] = _r2(mid)
        mids.append(mid)
    except Exception:
        pass
    if not mids:
        return None
    return {"consensus": _r2(statistics.median(mids)),
            "min": _r2(min(mids)), "max": _r2(max(mids)),
            "spread": _r2(max(mids) - min(mids)),
            "n": len(mids), "src": src,
            "verified": len(mids) >= 2 and (max(mids) - min(mids)) <= CONF_MIN}


_CAL_CACHE = {}


def fetch_calendar(ttl=1800):
    """ تقويم ForexFactory الأسبوعي — USD بس.

    ⛔ الـ feed بيرجّع 429 لما نطالعه كتير. التقويم بيتغير أسبوعياً
       فكاش ٣٠ دقيقة مفيش أي خسارة في الدقة.
    """
    if _CAL_CACHE.get("v") and (time.time() - _CAL_CACHE["_t"]) < ttl:
        return _CAL_CACHE["v"]
    out = []
    cal = _http_retry("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    nw = datetime.now(UTC)
    for e in cal:
        if e.get("country") != "USD":
            continue
        try:
            dt = datetime.fromisoformat(e["date"]).astimezone(UTC)
        except Exception:
            continue
        if nw - timedelta(hours=12) <= dt <= nw + timedelta(hours=96):
            out.append({"t": dt, "title": e.get("title", ""),
                        "imp": e.get("impact", "Low"),
                        "f": e.get("forecast", ""), "p": e.get("previous", "")})
    out.sort(key=lambda z: z["t"])
    if out:
        _CAL_CACHE.update({"v": out, "_t": time.time()})
    return out


def fetch_macro():
    out = {}
    for name, sym in (("DXY", "DX-Y.NYB"), ("US10Y", "%5ETNX"),
                      ("US02Y", "%5EIRX"), ("Silver", "SI=F")):
        try:
            m, _ = fetch_yahoo(sym, "5m", "5d")
            out[name] = {"px": m.get("regularMarketPrice"),
                         "chg": m.get("regularMarketChangePercent")}
        except Exception:
            out[name] = None
    try:
        m, _ = fetch_yahoo("GC=F", "1m", "1d")
        out["Futures"] = {"px": m.get("regularMarketPrice"),
                          "prev": m.get("previousClose")}
    except Exception:
        out["Futures"] = None
    return out


# ══════════════════════════════════════════════════════════════════════
#  ④ الهيكل — BOS / CHoCH / السيولة / FVG
# ══════════════════════════════════════════════════════════════════════
def _swings(bars, a, left=2, right=2, bar_sec=300, max_gap_bars=60):
    """
    قمم/قيعان الكسور (fractals) مجمّعة = برك سيولة Equal Highs / Equal Lows.

    ⛔⛔ باج كان هنا وخلّى الإشارات البنيوية تطلع **فاضية**:
    التجميع كان شامل كل القمم اللي فاتت، من غير حد زمني. يعني
    قاع من امبارح عند 4143 وقاع النهارده عند 4145 بيتحدوا في
    «قاع واحد» متوسطه 4144 — ولما السعر ينزل تحت 4144 مفيش
    قاع جديد يسجَّل، فيبقى آخر قاع «مكسور» من زمان.

    النتيجة: 88 quitمة على ٢٠٢٨ شمعة وصفر حدث BOS/CHoCH.
    وده أسوأ من إننا مانعش雌 — صفر يعني إن كل المؤشرات
   历史上(Listo) مبنية على قراءة غلط.

    ✅ الحل: التجميع لازم يكون **زمنياً محلياً** — القمة الجديدة
    بتتحد مع القمة اللي قبلها بس (مش أي قمة في التاريخ).
    """
    sep = max(0.6 * (a or 1.0), 0.4)
    piv = []
    for i in range(left, len(bars) - right):
        w = bars[i - left:i + right + 1]
        if bars[i]["h"] >= max(x["h"] for x in w):
            piv.append({"p": bars[i]["h"], "t": bars[i]["t"], "k": "H", "n": 1})
        if bars[i]["l"] <= min(x["l"] for x in w):
            piv.append({"p": bars[i]["l"], "t": bars[i]["t"], "k": "L", "n": 1})
    out = []
    for x in sorted(piv, key=lambda z: z["t"]):
        cands = [y for y in out
                 if y["k"] == x["k"] and abs(y["p"] - x["p"]) <= sep]
        if cands:
            # ⛔ أقربMatchByTime — مش أيCluster في التاريخ
            m = min(cands, key=lambda y: abs(y["t"] - x["t"]))
            if abs(m["t"] - x["t"]) > max_gap_bars * bar_sec:
                out.append(dict(x))
                continue
            tot = m["n"] + 1
            m["p"] = (m["p"] * m["n"] + x["p"]) / tot
            m["n"] = tot
            m["t"] = x["t"]                     # آخر لمسة
        else:
            out.append(dict(x))
    return sorted(out, key=lambda z: z["t"])


def _structure(bars, a, lookback=20):
    """
    كسر الهيكل: BOS (استمرار) و CHoCH (تغيّر اتجاه).

    ⛔⛔ النسخة الأولى كانت بتدوّر على الكسر في **الشمعتين الجايبين
    بس** من القمة. النتيجة العملية: صفر حدث على ٢٠٢٨ شمعة.
    القمة اللي مش اتكسرت في دقيقتين مش معناها مش متكسورة —
    معناها إن النافذة ضيقة أوي. ده كان بيلغي الإشارة كلها.

    ✅ الصح: أول شمعة **في أي وقت بعد** القمة يقفل سعرها فوقها
       = الكسر اتأكد. وبيتسجل أول كسر بس (مش كل كسر متكرر).
    """
    ev, trend = [], 0
    n = len(bars)
    if n < lookback + 4:
        return {"pivots": _swings(bars, a), "events": [], "trend": 0,
                "last_hi": None, "last_lo": None}
    last_hi = last_lo = None
    broken_hi = broken_lo = None
    bar_sec = 0
    if n > 2:
        deltas = [bars[i + 1]["t"] - bars[i]["t"] for i in range(min(20, n - 1))]
        deltas = [d for d in deltas if d > 0]
        bar_sec = statistics.median(deltas) if deltas else 300
    piv = _swings(bars, a, bar_sec=bar_sec)
    for i in range(lookback, n):
        c = bars[i]["c"]
        win = bars[i - lookback:i]
        wh = max(x["h"] for x in win)
        wl = min(x["l"] for x in win)
        if last_hi is None or wh > last_hi:
            last_hi = wh
        if last_lo is None or wl < last_lo:
            last_lo = wl
        # كسر صاعد
        if c > wh and (broken_hi is None or wh > broken_hi):
            ev.append({"k": "BOS" if trend >= 0 else "CHoCH", "dir": "UP",
                       "lvl": wh, "t": bars[i]["t"], "i": i})
            broken_hi = wh
            broken_lo = None
            trend = 1
        # كسر هابط
        elif c < wl and (broken_lo is None or wl < broken_lo):
            ev.append({"k": "BOS" if trend <= 0 else "CHoCH", "dir": "DOWN",
                       "lvl": wl, "t": bars[i]["t"], "i": i})
            broken_lo = wl
            broken_hi = None
            trend = -1
    # ⛔ آخر القمة/القاع لازم يكون **القريب** مش الأطول عمراً.
    #    (النسخة الأولى رجّعت 4420 من ٢٠٢٨ شمعة — مش مستوى بيعناه)
    recent = [p for p in piv if p["t"] >= bars[max(0, n - lookback * 4)]["t"]]
    rhi = [p["p"] for p in recent if p["k"] == "H"]
    rlo = [p["p"] for p in recent if p["k"] == "L"]
    return {"pivots": piv, "events": ev[-8:], "trend": trend,
            "last_hi": (max(rhi) if rhi else last_hi),
            "last_lo": (min(rlo) if rlo else last_lo)}


def _fvg_open(bars, a, minf=0.18):
    """ فجوات القيمة العادلة لسه ما اتملأتش."""
    out = []
    for i in range(2, len(bars)):
        if bars[i]["l"] > bars[i - 2]["h"] and (bars[i]["l"] - bars[i - 2]["h"]) >= minf * a:
            out.append({"dir": "bull", "lo": bars[i - 2]["h"], "hi": bars[i]["l"], "t": bars[i]["t"]})
        if bars[i]["h"] < bars[i - 2]["l"] and (bars[i - 2]["l"] - bars[i]["h"]) >= minf * a:
            out.append({"dir": "bear", "lo": bars[i]["h"], "hi": bars[i - 2]["l"], "t": bars[i]["t"]})
    keep = []
    for f in out:
        idx = next((i for i, x in enumerate(bars) if x["t"] == f["t"]), None)
        if idx is None:
            continue
        mit = False
        for x in bars[idx + 1:]:
            if (f["dir"] == "bull" and x["l"] <= f["hi"]) or \
               (f["dir"] == "bear" and x["h"] >= f["lo"]):
                mit = True
                break
        if not mit:
            keep.append(f)
    return keep[-6:]


def _session_levels(bars):
    """أسيا (٠-٧) · لندن (٧-١١) · نيويورك (١١-١٨) بتوقيت القاهرة + PDH/PDL."""
    by = {}
    for b in bars:
        by.setdefault(_cd(b["t"]).strftime("%Y-%m-%d"), []).append(b)
    days = sorted(by)
    today = _cd(bars[-1]["t"]).strftime("%Y-%m-%d")
    out = {"today": {}, "prev": []}
    for nm, a, z in (("asia", 0, 7), ("london", 7, 11), ("ny", 11, 18), ("day", 0, 24)):
        g = [x for x in by.get(today, []) if a <= _cd(x["t"]).hour < z]
        if g:
            out["today"][nm] = {"o": _r2(g[0]["o"]), "h": _r2(max(x["h"] for x in g)),
                                "l": _r2(min(x["l"] for x in g)), "c": _r2(g[-1]["c"])}
    for d in [x for x in days if x < today][-3:]:
        r = by[d]
        out["prev"].append({"d": d, "h": _r2(max(x["h"] for x in r)),
                            "l": _r2(min(x["l"] for x in r)), "c": _r2(r[-1]["c"])})
    return out


def _cd(ts):
    return datetime.fromtimestamp(ts, UTC).astimezone(CAIRO)


def _hhmmss(ts):
    return _cd(ts).strftime("%m-%d %H:%M")


# ══════════════════════════════════════════════════════════════════════
#  ⑤ العوامل الثمانية — كل واحد بيدّي رقم من -1 لـ +1
# ══════════════════════════════════════════════════════════════════════
def _f_htf_bias(tf):
    """اتجاه الفريمات العالية. H1 + H4."""
    parts, detail = [], []
    for k in ("H4", "H1"):
        d = tf.get(k)
        if not d:
            continue
        c, e50, e200, tr = d["C"], d["ema50"], d["ema200"], d["trend"]
        s = 0.0
        if e50 and e200:
            s += 0.45 if c > e50 else -0.45
            s += 0.35 if e50 > e200 else -0.35
        if tr == 1:
            s += 0.20
        elif tr == -1:
            s -= 0.20
        s = _clamp(s, -1, 1)
        parts.append(s)
        detail.append({"tf": k, "score": _r2(s), "c": c,
                       "ema50": e50, "ema200": e200, "trend": tr})
    if not parts:
        return 0.0, detail
    return _clamp(sum(parts) / len(parts), -1, 1), detail


def _f_mtf_align(tf):
    """ توافق H1 مع M15 — لو اتفقوا الإشارة أقوى."""
    h1, m15 = tf.get("H1"), tf.get("M15")
    if not h1 or not m15:
        return 0.0, {}
    s = 0.0
    if h1["trend"] == m15["trend"] and h1["trend"] != 0:
        s = 0.6
    else:
        s = -0.2
    if h1["C"] > h1.get("ema50") and m15["C"] > m15.get("ema50"):
        s += 0.2
    elif h1["C"] < h1.get("ema50") and m15["C"] < m15.get("ema50"):
        s -= 0.2
    return _clamp(s, -1, 1), {"h1_trend": h1["trend"], "m15_trend": m15["trend"]}


def _f_sweep(tf, price):
    """ هل السعر مسح بركة سيولة حقيقية (Equal High/Low أو PDH/PDL)؟ """
    m15, m5 = tf.get("M15"), tf.get("M5")
    if not m15 or not m5:
        return 0.0, {}
    pools = [p for p in m15.get("pivots", []) if p.get("eq", 1) >= 2]
    sess = m15.get("sessions", {})
    pdh = sess.get("prev", [{}])[0].get("h") if sess.get("prev") else None
    pdl = sess.get("prev", [{}])[0].get("l") if sess.get("prev") else None
    lo5 = min(b["l"] for b in m5.get("raw", [])[-12:]) if m5.get("raw") else None
    hi5 = max(b["h"] for b in m5.get("raw", [])[-12:]) if m5.get("raw") else None
    hits = []
    for p in pools[-6:]:
        if p["k"] == "H" and hi5 and hi5 >= p["p"] >= (lo5 or 0):
            hits.append({"lvl": p["p"], "kind": "Equal Highs", "dir": "bearish_sweep",
                         "eq": p.get("eq", 1), "t": p.get("t")})
        if p["k"] == "L" and lo5 and lo5 <= p["p"] <= (hi5 or 1e9):
            hits.append({"lvl": p["p"], "kind": "Equal Lows", "dir": "bullish_sweep",
                         "eq": p.get("eq", 1), "t": p.get("t")})
    if pdh and hi5 and hi5 >= pdh:
        hits.append({"lvl": pdh, "kind": "Previous Day High", "dir": "bearish_sweep",
                     "eq": 1, "t": sess["prev"][0]["d"]})
    if pdl and lo5 and lo5 <= pdl:
        hits.append({"lvl": pdl, "kind": "Previous Day Low", "dir": "bullish_sweep",
                     "eq": 1, "t": sess["prev"][0]["d"]})
    if not hits:
        return 0.0, {"sweeps": []}
    bull = any(h["dir"] == "bullish_sweep" for h in hits)
    bear = any(h["dir"] == "bearish_sweep" for h in hits)
    if bull and not bear:
        s = 0.65
    elif bear and not bull:
        s = -0.65
    else:
        s = 0.0
    best = max(hits, key=lambda h: h.get("eq", 1))
    if best.get("eq", 1) >= 3:
        s = _clamp(s * 1.25, -1, 1)
    return _clamp(s, -1, 1), {"sweeps": hits[-4:], "pools": len(pools)}


def _f_shift(tf):
    """ CHoCH/BOS على M15 و M5 — تأكيد الهيكل."""
    ev, detail = [], []
    for k in ("M15", "M5"):
        d = tf.get(k)
        if not d:
            continue
        for e in d.get("events", [])[-3:]:
            ev.append(e)
            detail.append({"tf": k, "k": e["k"], "dir": e["dir"],
                           "lvl": e["lvl"], "t": e.get("t")})
    if not ev:
        return 0.0, []
    last = ev[-1]
    s = 0.55 if last["dir"] == "UP" else -0.55
    if last["k"] == "CHoCH":
        s = _clamp(s * 1.25, -1, 1)          # تغير الاتجاه أقوى من الاستمرار
    # لو M5 عكس M15 = إشارات متضادة
    d15 = [x for x in detail if x["tf"] == "M15"]
    d5 = [x for x in detail if x["tf"] == "M5"]
    if d15 and d5 and d15[-1]["dir"] != d5[-1]["dir"]:
        s *= 0.5
    return _clamp(s, -1, 1), detail[-4:]


def _f_retest(tf):
    """ retrace لمنطقةPrevious_Order_Block / FVG فيخصم/مFeaturesDiscount."""
    m15 = tf.get("M15")
    if not m15:
        return 0.0, {}
    px = m15["C"]
    rng = (m15.get("hi", px) - m15.get("lo", px)) or 1.0
    zones = []
    for f in m15.get("fvg", []):
        zones.append({"z": f["z"], "dir": f["dir"], "kind": "FVG", "t": f.get("t")})
    eq = m15.get("swing_hi"); lo = m15.get("swing_lo")
    if eq and lo:
        zones.append({"z": [lo, eq], "dir": "zone", "kind": "Range", "t": ""})
    near = None
    for z in zones:
        zl, zh = z["z"]
        if zl <= px <= zh:
            near = z
            break
    if not near:
        return 0.0, {"in_zone": False}
    pos = (px - m15.get("lo", px)) / rng          # 0 = قاع، 1 = قمة
    if near["dir"] == "bull":
        s = 0.7 if pos < 0.5 else -0.2           # الخصم أحسن للشراء
    else:
        s = -0.7 if pos > 0.5 else 0.2           # الكبريوم أحسن للبيع
    return _clamp(s, -1, 1), {"in_zone": True, "kind": near["kind"],
                              "zone": near["z"], "pos": _r2(pos, 3)}


def _f_session(now):
    """ سيولة الجلسة — لندن و نيويورك أعلى، آسيا أقل."""
    h = now.hour + now.minute / 60.0
    wd = now.weekday()
    if wd == 5 or (wd == 6 and h < 22) or (wd == 4 and h >= 20):
        return -1.0, {"phase": "مغلق", "liquidity": 0}
    if h < 7:
        return -0.35, {"phase": "آسيا", "liquidity": 0.3}
    if h < 9:
        return 0.25, {"phase": "مطلع لندن", "liquidity": 0.6}
    if h < 11:
        return 0.6, {"phase": "لندن", "liquidity": 0.85}
    if h < 13:
        return 0.45, {"phase": "تداخل لندن/نيويورك", "liquidity": 0.75}
    if h < 16:
        return 0.75, {"phase": "نيويورك", "liquidity": 1.0}
    if h < 18:
        return 0.35, {"phase": "آخر نيويورك", "liquidity": 0.5}
    return -0.2, {"phase": "بعد الجلسة", "liquidity": 0.25}


def _f_macro(macro):
    """ الدولار والعوائد ضد الذهب — عكسي."""
    s, det = 0.0, {}
    dxy = macro.get("DXY")
    if dxy and dxy.get("chg") is not None:
        c = float(dxy["chg"])
        s += _clamp(-c / 0.35, -1, 1) * 0.6
        det["DXY"] = {"px": dxy.get("px"), "chg": _r2(c)}
    y = macro.get("US10Y")
    if y and y.get("chg") is not None:
        c = float(y["chg"])
        s += _clamp(-c / 2.5, -1, 1) * 0.4
        det["US10Y"] = {"px": y.get("px"), "chg": _r2(c)}
    return _clamp(s, -1, 1), det


def _f_volregime(tf):
    """
    نظام التقلب — ميت (أزرق) ولا نشط (إشارة) ولا مفرط (خطر)؟

    ⛔ القياس من مصدر واحد بس (M15) بمقارنة ATR الحالي بـ ATR
    آخر ٦٠ شمعة. قبل كنا نقارن ATR الـ M5 بـ M15÷3 وده كان
    بيخلط مصدرين مختلفين في نفس النسبة — رقم مالوش معنى.
    """
    m15 = tf.get("M15")
    if not m15 or not m15.get("raw"):
        return 0.0, {}
    raw = m15["raw"]
    if len(raw) < 20:
        return 0.0, {}
    a_now = _atr(raw, 14)
    a_now = a_now or 0.0
    # نسبة التقلب الحالية لـ ATR السجل
    hist = []
    for i in range(14, len(raw)):
        a = _atr(raw[max(0, i - 40):i + 1], 14)
        if a:
            hist.append(a)
    if len(hist) < 10 or a_now <= 0:
        return 0.0, {"regime": "—", "atr": _r2(a_now)}
    hist.sort()
    rank = sum(1 for x in hist if x < a_now) / float(len(hist))
    if rank < 0.25:
        return -0.85, {"regime": "ميت — سوق راكد", "rank": _r2(rank, 3), "atr": _r2(a_now)}
    if rank < 0.45:
        return -0.40, {"regime": "ضعيف", "rank": _r2(rank, 3), "atr": _r2(a_now)}
    if rank <= 0.85:
        return 0.55, {"regime": "نشط — مناسب", "rank": _r2(rank, 3), "atr": _r2(a_now)}
    return -0.45, {"regime": "مفرط التقلب — خطر", "rank": _r2(rank, 3), "atr": _r2(a_now)}


# ══════════════════════════════════════════════════════════════════════
#  ⑥ باب الأخبار — ٣٠ قبل و ١٥ بعد أي خبر USD عالي التأثير
# ══════════════════════════════════════════════════════════════════════
def _news_gate(now, cal):
    blocked, upcoming, prev = None, [], None
    for e in cal:
        delta = (e["t"] - now).total_seconds() / 60.0
        if e["imp"] == "High":
            if -15 <= delta <= 30:
                blocked = e
            elif 30 < delta <= 240:
                upcoming.append(dict(e, in_min=int(delta)))
        elif 0 < delta <= 240:
            upcoming.append(dict(e, in_min=int(delta)))
    if blocked is None:
        for e in cal:
            delta = (e["t"] - now).total_seconds() / 60.0
            if e["imp"] == "High" and -120 <= delta < -15:
                prev = e
    return blocked, upcoming[:6], prev


# ══════════════════════════════════════════════════════════════════════
#  ⑦ التعلم المحدود — أوزان جوه حدود + سجل تدقيق + قاطع أمان
# ══════════════════════════════════════════════════════════════════════
def _default_state():
    return {
        "version": 1,
        "weights": dict(BASE_W),
        "samples": [],
        "log": [],
        "frozen": False,
        "learned_n": 0,     # ⛔ آخر عدد عيّنات اتعلّمنا منها
        "updated": None,
    }


def _load_state():
    try:
        if LEARN_FILE.exists():
            st = json.loads(LEARN_FILE.read_text(encoding="utf-8"))
            base = _default_state()
            base.update({k: st.get(k, base[k]) for k in base})
            for f in FACTORS:
                base["weights"].setdefault(f, BASE_W[f])
            return base
    except Exception:
        pass
    return _default_state()


def _save_state(st):
    try:
        LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
        LEARN_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _perf(signals):
    """ ذاكرتنا على كل العوامل: العينة المغلقة → edge لكل عامل."""
    per = {f: [] for f in FACTORS}
    for s in signals:
        r = s.get("R")
        if r is None:
            continue
        for f in FACTORS:
            v = (s.get("factors") or {}).get(f)
            if isinstance(v, (int, float)) and abs(v) > 0.05:
                per[f].append(r * (1 if v > 0 else -1))
    out = {}
    for f, arr in per.items():
        out[f] = {"n": len(arr), "edge": _r2(statistics.fmean(arr), 4) if arr else None,
                  "hit": _r2(sum(1 for x in arr if x > 0) / len(arr), 3) if arr else None}
    return out


def _run_learn(state, price_now):
    """
    بيشتغل مع كل تحديث. ٤ خطوات:
      ١) تحل الإشارات اللي عدّى عليها الوقت
      ٢) تتقيّم العوامل من الـ R المحقق
      ٣) تتعدّل الأوزان — بحدود صارمة
      ٤) يفحص قاطع الأمان
    """
    now = _now_cairo()
    changed = False

    # ① حل الإشارات
    for s in state["samples"]:
        if s.get("resolved"):
            continue
        b = s.get("bars_held", 0)
        px = price_now
        if px is None:
            continue
        hit_tp = (s["side"] == "BUY" and px >= s["tp"]) or \
                 (s["side"] == "SELL" and px <= s["tp"])
        hit_sl = (s["side"] == "BUY" and px <= s["sl"]) or \
                 (s["side"] == "SELL" and px >= s["sl"])
        s["bars_held"] = b + 1
        if hit_tp:
            s["R"] = 1.0
            s["resolved"] = "TP"
            changed = True
        elif hit_sl:
            s["R"] = -1.0
            s["resolved"] = "SL"
            changed = True
        elif s["bars_held"] >= s.get("max_bars", 24):
            s["R"] = _r2(((px - s["entry"]) if s["side"] == "BUY"
                          else (s["entry"] - px)) / abs(s["entry"] - s["sl"]), 3)
            s["resolved"] = "TIME"
            changed = True

    closed = [s for s in state["samples"] if s.get("resolved")]
    state["samples"] = state["samples"][-400:]

    # ② تقييم العوامل
    perf = _perf(closed)

    # ③ تعديل الأوزان — محدود
    seen_n = int(state.get("learned_n", 0) or 0)
    new_closed = len(closed) - seen_n
    # ⛔⛔ باج مهم: من غير الشرط ده، كل نداء لـ compute كان بيعدّل
    #    الأوزان تاني بنفس العينات القديمة → انزلاق مستمر على مدار
    #    اليوم كله، والإصدار بيزيد كل دقيقة. التعلّم لازم يكون
    #    مرتبط بعيّنات **جديدة** بس.
    if ((not state.get("frozen")) and len(closed) >= MIN_SAMPLES_FOR_UPDATE
            and new_closed >= 1):
        neww = {}
        for f in FACTORS:
            w = state["weights"][f]
            e = (perf.get(f) or {}).get("edge")
            if e is None:
                neww[f] = w
                continue
            step = LR * _clamp(e, -1.0, 1.0)
            cand = w * (1.0 + step)
            lo, hi = BASE_W[f] * W_FLOOR, BASE_W[f] * W_CEIL
            cand = _clamp(cand, max(lo, w * (1 - MAX_STEP)), min(hi, w * (1 + MAX_STEP)))
            neww[f] = round(cand, 6)
        state["learned_n"] = len(closed)
        if any(abs(neww[f] - state["weights"][f]) > 1e-9 for f in FACTORS):
            state["weights"] = neww
            state["version"] = int(state.get("version", 1)) + 1
            state["updated"] = now.isoformat()
            state["log"].append({"t": now.isoformat(), "v": state["version"],
                                 "n": len(closed),
                                 "w": dict(neww)})
            state["log"] = state["log"][-60:]
            changed = True

    # ④ قاطع الأمان
    recent = closed[-BREAKER_WIN:]
    if len(recent) >= BREAKER_WIN:
        acc = sum(1 for s in recent if s.get("R", 0) > 0) / float(len(recent))
        state["acc_recent"] = _r2(acc, 3)
        if acc < BREAKER_ACC and not state.get("frozen"):
            state["frozen"] = True
            state["log"].append({"t": now.isoformat(), "frozen": True,
                                 "acc": _r2(acc, 3)})
            changed = True
        elif acc >= BREAKER_ACC + 0.12 and state.get("frozen") and state.get("frozen_by") == "acc":
            state["frozen"] = False
            changed = True
    return state, perf, changed


# ══════════════════════════════════════════════════════════════════════
#  ⑧ بناء التحليل الكامل
# ══════════════════════════════════════════════════════════════════════
def _pack(bars):
    if not bars:
        return None
    c = [b["c"] for b in bars]
    a = _atr(bars)
    st = _structure(bars, a)
    sess = _session_levels(bars)
    return {"C": _r2(c[-1]), "O": _r2(bars[-1]["o"]), "H": _r2(bars[-1]["h"]),
            "L": _r2(bars[-1]["l"]),
            "ema50": _r2(_ema(c, 50)), "ema200": _r2(_ema(c, 200)),
            "atr14": _r2(a), "rsi": _r2(_rsi(c)),
            "hi": _r2(max(x["h"] for x in bars)),
            "lo": _r2(min(x["l"] for x in bars)),
            "trend": st["trend"],
            "swing_hi": _r2(st["last_hi"]), "swing_lo": _r2(st["last_lo"]),
            "pivots": [{"k": p["k"], "p": _r2(p["p"]),
                        "t": _hhmmss(p["t"]), "eq": p["n"]} for p in st["pivots"][-8:]],
            "events": [{"k": e["k"], "dir": e["dir"], "lvl": _r2(e["lvl"]),
                        "t": _hhmmss(e["t"])} for e in st["events"][-5:]],
            "fvg": [{"dir": f["dir"], "z": [_r2(f["lo"]), _r2(f["hi"])],
                     "t": _hhmmss(f["t"])} for f in _fvg_open(bars, a)],
            "sessions": sess,
            "raw": bars[-80:],
            "bar_t": _hhmmss(bars[-1]["t"]),
            "bar_age_min": int((now_ts() - bars[-1]["t"]) // 60),
            "bar_t_epoch": bars[-1]["t"],
            "n": len(bars)}


def now_ts():
    return int(datetime.now(UTC).timestamp())


def compute(force=False):
    """ التحليل الكامل — بيتكاش كل SIGNAL_TTL ثانية."""
    with LOCK:
        cached = SIGNAL_TTL_SLOTS.get("core")
        if cached and not force and (now_ts() - cached["_t"]) < SIGNAL_TTL:
            return cached["v"]

        now = _now_cairo()
        errors = []
        tf, raw = {}, {}
        # ══════════════════════════════════════════════════════════════
        # ⛔⛔⛔ قرار معماري: مصدر الهيكل الواحد = COMEX GC=F
        #
        # ليه مش OKX (PAXG)؟ لأنه سبوت رقيق: ٥٦٪ من شموع الـ M1
        # جوه نافذة التداول بتفضل واقف، والـ M5 بيقعد ١١ دقيقة
        # من غير تحديث. رقم مش مؤقت ده = إشارة على شموع ميتة.
        #
        # ليه مش نخلط؟ لأن مقارنة مستوى M5 (من مصدر) بمستوى M15
        # (من مصدر تاني) بتخلق مسحات وهمية.
        #
        # الحل: مصدر واحد سايل لكل الفريمات، ونرجّع الأرقام
        # لأسعار السبوت بـ basis واحد ثابت (وسيط متحرك).
        # ⛔ ولا كلمة «نحو» في الكود — التحويل constant واحد.
        # ══════════════════════════════════════════════════════════════
        def _age(bs):
            """عمر آخر شمعة بالثواني — 10^9 لو مفيش شموع."""
            try:
                return (now_ts() - bs[-1]["t"]) if bs else 10 ** 9
            except Exception:
                return 10 ** 9

        try:
            _, b5 = fetch_yahoo("GC=F", "5m", "5d")
            _, b15 = fetch_yahoo("GC=F", "15m", "1mo")
            _, b60 = fetch_yahoo("GC=F", "60m", "3mo")
            _, bh = fetch_yahoo("GC=F", "1h", "1y")
            _, bd = fetch_yahoo("GC=F", "1d", "2y")
        except Exception as e:
            errors.append("yahoo:%s" % e)
            b5 = b15 = b60 = bh = bd = []

        # ⛔⛔ Yahoo وقفت بتفصّل شموع الذهب — آخر M5 عندنا ١٦ أكتوبر
        # وبترجّعها كأنها سليمة. المحرك كان يسلّم شموع ميتة ⇒ بوابة
        # «الشموع واقفة» دايمة ⇒ الكارت أزرق على طول وبلا Levels ولا صفقات.
        #
        # ⛌ الحل: لو Yahoo رجعت فاضية أو متأخرة أكتر من ٣٠ دقيقة ننتقل
        # لـOKX (PAXG/USDT) لكل الفريمات — مصدر واحد زي المقصود، بس ده
        # اللي بيتحدث فعلاً. والـbasis يتحسب من الفارق مع **سعر السبوت
        # الحقيقي** بدل تقاطع شموع Yahoo الميتة.
        # ⚠️ مفيش ولا عتبة اتغيرت — إصلاح مصدر فقط.
        SRC = "yahoo"
        if _age(b5) > 1800:
            SRC = "okx"
            errors.append("yahoo_stale: آخر شمعة M5 عمرها %d دقيقة"
                          % (_age(b5) // 60))
            try:
                b5 = fetch_okx("5m", 300, 1)
                b15 = fetch_okx("15m", 300, 1)
                b60 = fetch_okx("1H", 300, 1)
                bh = fetch_okx("4H", 300, 1)
                bd = fetch_okx("1D", 300, 1)
            except Exception as e:
                errors.append("okx:%s" % e)

        # basis: وسيط متحرك لفروق آخر ٨ ساعات على شموع ١٥ دقيقة
        basis, basis_mad, basis_n = None, None, 0
        try:
            _ok_rows = _http_retry(
                "https://www.okx.com/api/v5/market/candles"
                "?instId=PAXG-USDT&bar=15m&limit=300").get("data") or []
            ok = {int(x[0]) // 1000: float(x[4]) for x in _ok_rows}
            if SRC == "okx":
                # ⛌ Yahoo ميتة ⇒ مفيش تقاطع نحسب منه basis.
                # نحسبه من الفارق الحقيقي بين OKX وسعر السبوت المتفق
                # عليه من ٣ مصادر (نفس المنطق، بس بمصدر طازج).
                _sp = fetch_spot()
                _cons = float(_sp.get("consensus") or 0) if _sp else 0.0
                _ok_sorted = [float(x[4]) for x in
                              sorted(_ok_rows, key=lambda z: int(z[0]))][-32:]
                diffs = ([c - _cons for c in _ok_sorted] if _cons > 0 else [])
            else:
                ym = {b["t"] - b["t"] % 900: b["c"] for b in b15}
                diffs = [ym[t] - ok[t] for t in sorted(set(ym) & set(ok))][-32:]
            if len(diffs) >= 8:
                basis = statistics.median(diffs)
                basis_mad = _r2(statistics.fmean([abs(d - basis) for d in diffs]))
                basis_n = len(diffs)
        except Exception as e:
            errors.append("basis:%s" % e)

        if basis is not None:
            def _to_spot(bs):
                return [dict(b, o=b["o"] - basis, h=b["h"] - basis,
                             l=b["l"] - basis, c=b["c"] - basis) for b in bs]
            for k, src in (("M5", b5), ("M15", b15), ("H1", b60), ("H4", bh), ("D1", bd)):
                try:
                    conv = _to_spot(src)
                    raw[k] = conv
                    p = _pack(conv)
                    if p:
                        p["basis"] = _r2(basis)
                        p["basis_mad"] = basis_mad
                        p["basis_n"] = basis_n
                        tf[k] = p
                except Exception as e:
                    errors.append("%s:%s" % (k, e))
        else:
            errors.append("basis_missing: مفيش ترجمة لأسعار السبوت")

        try:
            spot = fetch_spot()
        except Exception as e:
            spot, _ = None, errors.append("spot:%s" % e)
        try:
            macro = fetch_macro()
        except Exception as e:
            macro = {}
            errors.append("macro:%s" % e)
        try:
            cal = fetch_calendar()
        except Exception as e:
            cal = []
            errors.append("cal:%s" % e)

        price = spot["consensus"] if spot else None
        blocked, upcoming, prev_hi = _news_gate(now, cal)

        # العوامل
        f_h, htf_det = _f_htf_bias(tf)
        f_a, align_det = _f_mtf_align(tf)
        f_s, sweep_det = _f_sweep(tf, price)
        f_sh, shift_det = _f_shift(tf)
        f_r, retest_det = _f_retest(tf)
        f_se, sess_det = _f_session(now)
        f_m, macro_det = _f_macro(macro)
        f_v, vol_det = _f_volregime(tf)
        factors = {"htf_bias": f_h, "mtf_align": f_a, "sweep": f_s, "shift": f_sh,
                   "retest": f_r, "session": f_se, "macro": f_m, "volregime": f_v}

        # التعلم
        state = _load_state()
        state, perf, chg = _run_learn(state, price)
        if chg:
            _save_state(state)
        W = state["weights"]

        num = sum(W[f] * factors[f] for f in FACTORS)
        den = sum(W[f] for f in FACTORS) or 1.0
        score = _clamp(num / den, -1.0, 1.0)

        # العتبة الديناميكية
        turn = TURN_BASE
        if blocked:
            turn += TURN_NEWS_PENALTY * 2
        elif upcoming:
            turn += TURN_NEWS_PENALTY
        if vol_det.get("regime", "").startswith("مفرط"):
            turn += TURN_VOL_PENALTY
        if sess_det.get("liquidity", 1) < 0.4:
            turn += TURN_VOL_PENALTY

        m15 = tf.get("M15", {})
        m5 = tf.get("M5", {})
        a5 = (m5.get("atr14") or 4.0)
        a15 = (m15.get("atr14") or 7.0)
        entry = price
        levels = {}
        # ⛔ ترتيب مهم: الاتجاه المبدئي يتحدد من الدرجة الأول،
        #    وبعدين نحسب المستويات منه، وبعدين بوابة العائد
        #    تقدر ترجّعه أزرق. لولا الترتيب ده كان الـ RR gate
        #    هيتحسب على مستوى من الهوا.
        prov_side = ("HOLD" if abs(score) < turn
                     else ("BUY" if score >= turn else "SELL"))
        if entry:
            # ── مرشحو وقف الخسارة = أقرب مستوى هيكليInvalidating
            # ⛔ النسخة الأولى كانت بتعمل min() على كل المرشحين
            #    فبتاخد **أبعد** قاع (4131 بدل 4174) والنتيجة
            #    عائد 1:6 — إشارات خردة بتظهر على الموقع.
            if prov_side == "BUY":
                cands = []
                for lv in (m5.get("swing_lo"), m15.get("swing_lo")):
                    if lv and lv < entry - 0.35 * a5:
                        cands.append(lv)
                for e in (m5.get("events") or [])[-3:]:
                    if e.get("dir") == "UP" and e.get("lvl"):
                        cands.append(e["lvl"])
                sl = _r2(max(cands) - 0.2 * a5) if cands else _r2(entry - 1.1 * a5)
                ups = [p["p"] for p in (m15.get("pivots") or []) if p["k"] == "H" and p["p"] > entry]
                ups += [p["p"] for p in (m5.get("pivots") or []) if p["k"] == "H" and p["p"] > entry]
                tp1 = _r2(min(ups)) if ups else _r2(entry + 1.2 * a5)
            elif prov_side == "SELL":
                cands = []
                for lv in (m5.get("swing_hi"), m15.get("swing_hi")):
                    if lv and lv > entry + 0.35 * a5:
                        cands.append(lv)
                for e in (m5.get("events") or [])[-3:]:
                    if e.get("dir") == "DOWN" and e.get("lvl"):
                        cands.append(e["lvl"])
                sl = _r2(min(cands) + 0.2 * a5) if cands else _r2(entry + 1.1 * a5)
                dns = [p["p"] for p in (m15.get("pivots") or []) if p["k"] == "L" and p["p"] < entry]
                dns += [p["p"] for p in (m5.get("pivots") or []) if p["k"] == "L" and p["p"] < entry]
                tp1 = _r2(max(dns)) if dns else _r2(entry - 1.2 * a5)
            else:
                sl = tp1 = None
            if sl and entry:
                risk = abs(entry - sl)
                if risk <= 0:
                    risk = a5
                tp2 = _r2(entry + (tp1 - entry) * 2.0) if prov_side == "BUY" else _r2(entry - (entry - tp1) * 2.0)
                rr = abs(tp1 - entry) / risk
                levels = {"entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
                          "risk_usd": _r2(risk), "rr": _r2(rr),
                          "atr_m5": _r2(a5), "atr_m15": _r2(a15)}
                # ⛔ بوابة العائد — من غيرها الموقع هيعرض إشارات بلا قيمة
                if rr < 1.0:
                    levels["rr_fail"] = "العائد %.2f — أقل من 1.0" % rr


        # البوابات الصارمة
        gates = []
        if prov_side == "HOLD":
            gates.append({"g": "rr", "ok": True, "why": "مفيش اتجاه — مش محتاج"})
        else:
            _rr = levels.get("rr")
            gates.append({"g": "rr", "ok": bool(_rr and _rr >= 1.0),
                          "why": ("العائد 1:%.2f" % _rr) if _rr else "مفيش هدف محدد"})
        gates.append({"g": "price", "ok": bool(spot and spot.get("verified")),
                      "why": "اتفاق %d مصادر بفارق %s$" % (spot["n"], spot["spread"]) if spot else "مفيش سعر"})
        m5 = tf.get("M5")
        lag = (now_ts() - (m5["raw"][-1]["t"] + 300)) if (m5 and m5.get("raw")) else 9999
        gates.append({"g": "fresh", "ok": lag <= 480,
                      "why": "الشموع متأخرة %d ثانية" % max(0, lag) if lag <= 900 else "الشموع واقفة"})
        gates.append({"g": "news", "ok": blocked is None,
                      "why": (blocked["title"] + " — ممنوع") if blocked else "مفيش خبر عالي قريب"})
        gates.append({"g": "liquidity", "ok": sess_det.get("liquidity", 0) >= 0.3,
                      "why": sess_det.get("phase", "")})
        gates.append({"g": "vol", "ok": not vol_det.get("regime", "").startswith("ميت"),
                      "why": vol_det.get("regime", "—")})
        gates.append({"g": "learn", "ok": not state.get("frozen"),
                      "why": "مجمّد" if state.get("frozen") else "النسخة %d" % state["version"]})
        all_ok = all(x["ok"] for x in gates)

        if state.get("frozen") or not all_ok or abs(score) < turn:
            side, color = "HOLD", "blue"
        else:
            side, color = prov_side, ("green" if prov_side == "BUY" else "red")
        # ⛔ لو رجع أزرق بسبب العائد،levels-space ما ينفعش تتحسب
        if color == "blue" and side == "HOLD":
            levels = dict(levels or {})
            levels["note"] = "مفيش Levels — البوابات مش كاملة"

        # مستويات
        v = {"ts": now.isoformat(),
             "cairo": now.strftime("%Y-%m-%d %H:%M"),
             "side": side, "color": color,
             "score": int(round(score * 100)),
             "strength": abs(int(round(score * 100))),
             "turn": int(round(turn * 100)),
             "gates": gates, "all_ok": all_ok,
             "price": price, "spot": spot, "macro": macro,
             "basis": {"value": _r2(basis), "mad": basis_mad, "n": basis_n, "src": "GC=F → سبوت"},
             "tf": {k: {kk: vv for kk, vv in d.items() if kk != "raw"}
                    for k, d in tf.items()},
             "f": {k: _r2(val, 3) for k, val in factors.items()},
             "detail": {"htf": htf_det, "align": align_det, "sweep": sweep_det,
                        "shift": shift_det, "retest": retest_det,
                        "session": sess_det, "macro": macro_det, "vol": vol_det},
             "news": {"blocked": ({"t": blocked["t"].astimezone(CAIRO).strftime("%m-%d %H:%M"),
                                  "title": blocked["title"]} if blocked else None),
                      "upcoming": [{"t": e["t"].astimezone(CAIRO).strftime("%m-%d %H:%M"),
                                    "title": e["title"], "imp": e["imp"],
                                    "f": e.get("f"), "p": e.get("p"),
                                    "in_min": e.get("in_min")} for e in upcoming],
                      "prev_high": ({"t": prev_hi["t"].astimezone(CAIRO).strftime("%m-%d %H:%M"),
                                     "title": prev_hi["title"]} if prev_hi else None)},
             "levels": levels,
             "learn": {"version": state.get("version"), "frozen": state.get("frozen"),
                       "n": len([s for s in state["samples"] if s.get("resolved")]),
                       "acc": state.get("acc_recent"),
                       "w": {k: _r2(state["weights"][k], 4) for k in FACTORS},
                       "base": BASE_W, "perf": perf},
             "errors": errors}

        # تسجيل الإشارة (بس لو ملوّنة)
        if color != "blue" and levels.get("entry") and levels.get("sl") and not errors:
            state["samples"].append({
                "ts": now.isoformat(), "side": side,
                "entry": levels["entry"], "sl": levels["sl"],
                "tp": levels.get("tp1"), "score": v["score"],
                "factors": v["f"], "bars_held": 0, "max_bars": 24,
                "resolved": None, "R": None,
                "w": {k: _r2(state["weights"][k], 4) for k in FACTORS}})
            state["samples"] = state["samples"][-400:]
            _save_state(state)

        SIGNAL_TTL_SLOTS["core"] = {"_t": now_ts(), "v": v}
        return v


# ══════════════════════════════════════════════════════════════════════
#  ⑨ تسجيل المسارات (بيتستدعى من octa_app.py)
# ══════════════════════════════════════════════════════════════════════
def register(app):
    from flask import jsonify, request

    @app.route("/api/gold/signal")
    def _gs():
        try:
            v = compute()
            return jsonify({
                "side": v["side"], "color": v["color"],
                "score": v["score"], "strength": v["strength"],
                "turn": v["turn"], "price": v["price"],
                "all_ok": v["all_ok"], "cairo": v["cairo"],
                # ⛔ السوق مقفول حالة مستقلة عن «خامل»:
                # «خامل» = حلّلنا وما لقيناش حاجة.
                # «مقفول» = السوق مش شغال أصلاً ومفيش تحليل خالص.
                "closed": (v.get("session") or {}).get("phase") == "مغلق",
                "news_blocked": bool(v["news"]["blocked"]),
                "frozen": v["learn"]["frozen"],
                "gates": v["gates"],
                "n_samples": v["learn"]["n"], "acc": v["learn"]["acc"],
                "version": v["learn"]["version"],
            })
        except Exception as e:
            return jsonify({"side": "HOLD", "color": "blue", "score": 0,
                            "error": str(e)[:120], "cairo": _now_cairo().strftime("%H:%M")}), 200

    @app.route("/api/gold/deep")
    def _gd():
        try:
            v = compute()
            slim = dict(v)
            slim.pop("tf", None)
            return jsonify({
                "head": {k: v[k] for k in ("ts", "cairo", "side", "color", "score",
                                           "strength", "turn", "price", "levels",
                                           "all_ok", "gates")},
                "price": v["price"], "macro": v["macro"], "news": v["news"],
                "detail": v["detail"], "f": v["f"],
                "tf": v["tf"], "learn": v["learn"], "errors": v["errors"],
            })
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 200

    @app.route("/api/gold/learn")
    def _gl():
        st = _load_state()
        closed = [s for s in st["samples"] if s.get("resolved")]
        wins = [s for s in closed if (s.get("R") or 0) > 0]
        return jsonify({
            "version": st.get("version"), "frozen": st.get("frozen"),
            "weights": st["weights"], "base": BASE_W,
            "samples_n": len(closed),
            "acc": _r2(len(wins) / float(len(closed)), 3) if closed else None,
            "perf": _perf(closed),
            "log": st.get("log", [])[-12:],
            "recent": [{"ts": s.get("ts"), "side": s.get("side"), "score": s.get("score"),
                        "R": s.get("R"), "res": s.get("resolved")} for s in st["samples"][-25:]],
        })

    @app.route("/api/gold/reset-learn", methods=["POST"])
    def _gr():
        with LOCK:
            _save_state(_default_state())
            SIGNAL_TTL_SLOTS.pop("core", None)
        return jsonify({"ok": True, "note": "الأوزان رجعت للوضع الأول"})

    print("[gold_signal] مسجّل: /api/gold/signal · /deep · /learn", flush=True)
    return app
