"""
═══════════════════════════════════════════════════════════════
 gold_macro.py — محرك العوامل: العالمي + المصري
═══════════════════════════════════════════════════════════════
 📌 الفكرة: «إيه اللي بيحرك الذهب؟» — بأرقام حقيقية من مصادر رسمية.

 ⛔⛔⛔ القواعد (ممنوع نكسرها):
 ① **كل عامل لازم يقول**: قيمته · قيمته السابقة · اتجاهه · تاريخ الرصد
    · مصدره · رابط المصدر · وحدته · **حالة الطزاجة** (لحظي/متأخر/قديم/مفقود).
 ② **العامل الناقص = «غير متاح» + سبب** — ممنوع نخترع ولا نصفر.
 ③ **ممنوع «تأثير» برقم مخترع** (مش بنقول «الدولار بيسبب ٤٠٪ من الحركة»
    من غير قياس). بنقول العلاقة **النوعية** + ب Clarify إن ده مش تنبؤ.
 ④ **التضارب بين العوامل** ينتقل للمستخدم — مش بندفنه.

 📌 المصادر (كلها مجانية/رسمية):
  · FRED (fredgraph.csv) — عوائد在美国 + عوائد حقيقية + CPI + PCE + توظيف + بطالة + فائدة الفيدرالي
  · TradingView (tv_ws) — DXY
  · البنك المركزي المصري — عبر ملف البيانات المحفوظ (data/egypt_macro.json)
  · البنك الدولي — CPI مصر + فائدة الإيداع (تاريخية)
═══════════════════════════════════════════════════════════════
"""
import json
import os
import re
import threading
import time
import datetime
from pathlib import Path

CACHE_TTL = int(os.environ.get("GOLD_MACRO_TTL", "1800"))   # ٣٠ دقيقة
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HERE = Path(os.path.dirname(os.path.abspath(__file__)))

_LOCK = threading.Lock()
_MEM = {"ts": 0, "data": None}


# ═══════════ جلب ═══════════
def _http(url, timeout=20, headers=None, tries=3):
    """
    ⛔⛔⛔ إعادة محاولة (3 مرات) — لأن بعض المصادر (FRED) بتعمل timeouts
    متقطعة و World Bank كمان. ⛔ لو كل المحاولات فشلت ⇒ exception.
    """
    import urllib.request
    import gzip
    import io as _io
    h = {"User-Agent": _UA, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    last = None
    for i in range(max(1, tries)):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.GzipFile(fileobj=_io.BytesIO(raw)).read()
                return raw.decode("utf-8", errors="ignore")
        except Exception as e:
            last = e
            if i < max(1, tries) - 1:
                time.sleep(1.2 * (i + 1))
    raise last if last else RuntimeError("http-failed")


def _csv_rows(txt):
    """CSV بسيط ⇒ صفوف (كل سطر قائمة حقول)."""
    import csv
    import io as _io
    return list(csv.reader(_io.StringIO(txt)))


# ═══════════ الخزانة الأمريكية (مصدر رسمي) ═══════════
TREASURY_CSV = ("https://home.treasury.gov/resource-center/data-chart-center/"
                "interest-rates/daily-treasury-rates.csv/{year}/all?"
                "type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
TREASURY_REAL_XML = ("https://home.treasury.gov/resource-center/data-chart-center/"
                      "interest-rates/pages/xml?data=daily_treasury_real_yield_curve"
                      "&field_tdr_date_value={year}")


def treasury_nominal(year=None):
    """منحنى العوائد الاسمية للخزانة (٢ و١٠ سنين) — مصدر رسمي."""
    year = year or datetime.date.today().year
    try:
        txt = _http(TREASURY_CSV.format(year=year), timeout=25, tries=2,
                     headers={"Accept": "text/csv,*/*"})
    except Exception as e:
        return {"error": "فشل الخزانة: " + str(e)[:80], "points": []}
    rows = _csv_rows(txt)
    if len(rows) < 2:
        return {"error": "رد فارغ", "points": []}
    head = [h.strip() for h in rows[0]]
    try:
        i2 = head.index("2 Yr")
        i10 = head.index("10 Yr")
    except ValueError:
        return {"error": "أعمدة غير متوقعة", "points": []}
    pts = []
    for r in rows[1:]:
        if len(r) <= max(i2, i10):
            continue
        m = r[0].strip()
        try:
            mm, dd, yy = m.split("/")
            iso = "%s-%s-%s" % (yy, mm, dd)
        except Exception:
            continue
        # ⛔⛔⛔ كان بنقرأ r[1] و r[2] (يعني 1 Mo و 1.5 Month!) بدل
        #    الأعمدة الصح (2 Yr و 10 Yr). الأعمدة من الهيدر.
        try:
            v2 = float(r[i2].strip())
            v10 = float(r[i10].strip())
        except Exception:
            continue
        pts.append((iso, v2, v10))
    pts.sort()
    return {"points": pts, "source": "خزانة America — U.S. Treasury",
            "source_url": "https://home.treasury.gov/resource-center/data-chart-center/"
                          "interest-rates/TextView?type=daily_treasury_yield_curve"}


def treasury_real(year=None):
    """منحنى العوائد الحقيقية (TIPS) — ٥/٧/١٠/٢٠/٣٠ سنة."""
    year = year or datetime.date.today().year
    try:
        txt = _http(TREASURY_REAL_XML.format(year=year), timeout=25, tries=2)
    except Exception as e:
        return {"error": "فشل الخزانة (العوائد الحقيقية): " + str(e)[:80], "points": []}
    out = []
    for m in re.finditer(r"<m:properties>(.*?)</m:properties>", txt, re.S):
        blk = m.group(1)
        dm = re.search(r"<d:NEW_DATE[^>]*>([^<]+)</d:NEW_DATE>", blk)
        tm = re.search(r"<d:TC_10YEAR[^>]*>([^<]+)</d:TC_10YEAR>", blk)
        if not dm or not tm:
            continue
        try:
            d = dm.group(1)[:10]
            v = float(tm.group(1))
        except Exception:
            continue
        out.append((d, v))
    out.sort()
    return {"points": out, "source": "خزانة America — U.S. Treasury (TIPS)",
            "source_url": "https://home.treasury.gov/resource-center/data-chart-center/"
                          "interest-rates/TextView?type=daily_treasury_real_yield_curve"}


def fed_h15(series="RIFLGFCY10_N.B", lastobs=60):
    """الفيدرالي — H.15 (منحنى العوائد). ⛔ بعض السلاسل تحتاج مفتاح."""
    url = ("https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&series=%s"
           "&lastobs=%d&from=&to=&filetype=csv&label=include&layout=seriescolumn"
           % (series, lastobs))
    try:
        txt = _http(url, timeout=12, tries=tries, headers={"Accept": "text/csv,*/*"})
    except Exception as e:
        return {"error": "فشل الفيدرالي: " + str(e)[:80], "points": []}
    pts = []
    started = False
    for line in txt.splitlines():
        if line.startswith("Time Period"):
            started = True
            continue
        if not started:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            pts.append((parts[0].strip(), float(parts[1])))
        except Exception:
            continue
    return {"points": pts, "source": "الاحتياطي الفيدرالي — H.15",
            "source_url": "https://www.federalreserve.gov/releases/h15/"}


def first_ok(*fetchers):
    """⛔ بيجرّب المصادر بالترتيب — أول واحد رجّع بيانات بيتبنى."""
    errs = []
    for f in fetchers:
        try:
            r = f()
            if r and r.get("points"):
                r["fallback_note"] = None
                return r
            errs.append((f.__name__, (r or {}).get("error")))
        except Exception as e:
            errs.append((f.__name__, str(e)[:80]))
    return {"points": [], "error": "كل المصادر فشلت: " + "; ".join(
        "%s(%s)" % (n, e) for n, e in errs)[:200]}


def tv_fred(series_id, count=400):
    """
    📌 FRED عن طريق TradingView (`FRED:<ID>`) — **شغّال وسريع**
    (الفRED الأصلي مقفول/بطيء من بيئتنا).
    ⛔ نفس البيانات (نفس المصدر) ⇒ لازم يتحدّث مع http FRED.
    """
    try:
        import importlib
        gh = importlib.import_module("gold_history")
        bars = gh._tv_bars("FRED:" + str(series_id), int(count))
        return {"points": [(d, v) for d, v in (bars or [])],
                "source": "FRED (عبر TradingView)",
                "source_url": "https://fred.stlouisfed.org/series/" + str(series_id),
                "error": None}
    except Exception as e:
        return {"points": [], "error": "فشل FRED عبر TradingView: " + str(e)[:70]}


def fred(series_id, years=None, tries=2):
    """
    FRED بدون مفتاح: fredgraph.csv?id=<ID>
    📌 ⛔ ملاحظة مهمة: بعض السلاسل بتتأخر (يوم-يومين) — وده متعلن.
    ⛔ بيرجّع {"points": [(date, value)], ...} أو None مع سبب.
    """
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s"
           % series_id)
    try:
        txt = _http(url, timeout=25, headers={"Accept": "text/csv,*/*"})
    except Exception as e:
        return {"error": "فشل الوصول لـFRED: " + str(e)[:90], "points": []}
    pts = []
    for line in txt.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        d, v = parts[0].strip(), parts[1].strip()
        if not v or v in (".", "NA"):
            continue
        try:
            pts.append((d, float(v)))
        except Exception:
            continue
    if not pts:
        return {"error": "FRED رجّع فاضي", "points": []}
    if years:
        cutoff = (datetime.date.today() - datetime.timedelta(days=int(years * 372))).isoformat()
        pts = [p for p in pts if p[0] >= cutoff]
    return {"points": pts, "source": "FRED — Federal Reserve Bank of St. Louis",
            "source_url": "https://fred.stlouisfed.org/series/" + series_id,
            "series_id": series_id}


def world_bank(indicator, years="2015:2026"):
    """البنك الدولي — JSON نضيف. ⛔ لازم http1.1 + UA (وإلا timeout صفر بايت)."""
    url = ("https://api.worldbank.org/v2/country/EGY/indicator/%s"
           "?format=json&per_page=60&date=%s" % (indicator, years))
    try:
        txt = _http(url, timeout=20, headers={"Accept": "application/json"})
        j = json.loads(txt)
    except Exception as e:
        return {"error": "فشل البنك الدولي: " + str(e)[:90], "points": []}
    if not isinstance(j, list) or len(j) < 2 or not j[1]:
        return {"error": "رد غير متوقع", "points": []}
    pts = []
    for row in j[1]:
        if row.get("value") is None:
            continue
        try:
            _y = str(row.get("date") or "")
            if len(_y) == 4 and _y.isdigit():
                # ⛔ البنك الدولي بيرجّع السنة بس ("2024") ⇒ نخليها تاريخ كامل
                #    وإلا date.fromisoformat يفشل ⇒ الطزاجة "unknown" دايمًا.
                _iso = "%s-12-31" % _y
            else:
                _iso = _y
            pts.append((_iso, float(row["value"])))
        except Exception:
            continue
    pts.sort()
    return {"points": pts, "source": "البنك الدولي (World Bank)",
            "source_url": "https://api.worldbank.org/v2/country/EGY/indicator/" + indicator,
            "license": "CC BY 4.0", "lastupdated": (j[0] or {}).get("lastupdated")}


def egypt_macro():
    """بيانات البنك المركزي المحفوظة (data/egypt_macro.json) — حصاد يومي."""
    p = HERE / "data" / "egypt_macro.json"
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def dxy_bars(count=700):
    """مؤشر الدولار (DXY) من TradingView."""
    try:
        import importlib
        tws = importlib.import_module("tv_ws")
        bars = tws.fetch("TVC:DXY", count)
        out = []
        for b in (bars or []):
            t, c = b.get("t"), b.get("c")
            if not t or c is None:
                continue
            out.append({"d": datetime.datetime.utcfromtimestamp(float(t)).strftime("%Y-%m-%d"),
                        "c": float(c)})
        return out
    except Exception:
        return []


# ═══════════ أدوات ═══════════
def _freshness(obs_date, now=None, daily=True):
    """⛔ الطزاجة من تاريخ **الرصد** (مش وقت السحب)."""
    if not obs_date:
        return {"status": "unknown", "age_days": None}
    # ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ — صيغ متعددة (نور-الكوانت): تواريخ البنك المركزي
    #    المصري مش ISO ("26 Oct 2026" · "12 Feb 2026") ⇒ الطزاجة unknown
    d = None
    _raw = str(obs_date).strip()
    # ⛔⛔ القصّ [:10] كان بيقطع السنة من «26 Oct 2026» ⇒ «26 Oct 202» ⇒ فشل!
    #    ⇒ ISO بيقصّ ١٠ حروف، والباقي بياخد النص كامل.
    for _f, _v in (("%Y-%m-%d", _raw[:10]), ("%d %b %Y", _raw), ("%d %B %Y", _raw),
                   ("%Y/%m/%d", _raw), ("%d/%m/%Y", _raw)):
        try:
            d = datetime.datetime.strptime(_v, _f).date()
            break
        except Exception:
            continue
    if d is None:
        try:
            d = datetime.date.fromisoformat(_raw[:10])
        except Exception:
            return {"status": "unknown", "age_days": None}
    n = now or datetime.date.today()
    age = (n - d).days
    if age <= (2 if daily else 45):
        st = "delayed" if age > 1 else "live"
    elif age <= (120 if daily else 400):
        st = "recent"
    else:
        st = "stale"
    return {"status": st, "age_days": age}


def _series_stats(pts, unit=""):
    """قيمة · سابقة · اتجاه · تاريخ الرصد من سلسلة (date, value)."""
    if not pts:
        return None
    last = pts[-1]
    prev = pts[-2] if len(pts) > 1 else None
    direction = "unknown"
    if prev and prev[1]:
        if last[1] > prev[1]:
            direction = "up"
        elif last[1] < prev[1]:
            direction = "down"
        else:
            direction = "flat"
    return {"value": last[1], "date": last[0], "previous": prev[1] if prev else None,
            "previous_date": prev[0] if prev else None,
            "direction": direction, "unit": unit, "points": len(pts)}


# ═══════════ سجل العوامل ═══════════
# 📌 كل عامل: الاسم · المصدر · ليه مهم · العلاقة النوعية بالذهب
FACTOR_META = {
    # ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ (حيدر-البيانات): الرقم **مؤشر (نقطة) أساس ١٩٧٣=١٠٠**
    #    مش نسبة ⇒ الوحدة كانت «%» وبتظهر للمستخدم غلط.
    "dxy": {"name_ar": "مؤشر الدولار (DXY)", "cat": "الدولار الأمريكي",
            "why": "الدولار القوي بيضغط على الذهب المقوّم بالدولار (لأن الذهب غالي بالم dolar بيبقى أقل جاذبية).",
            "relation": "عادة علاقة عكسية — بس مش دايماً، وبنتكلم عن الملاحظة مش القاعدة.",
            "freq": "daily"},
    "us10y": {"name_ar": "عائد الخزانة الأمريكي ١٠ سنين", "cat": "الفائدة الأمريكية",
              "why": "سعر الفائدة بيمثل تكلفة الفرصة البديلة賈لذهب اللي مش بياخد عائد.",
              "relation": "الفوائد العالية بتضغط على الذهب — بس الارتباط مش مثالي.",
              "freq": "daily"},
    "us10y_real": {"name_ar": "العائد الحقيقي ١٠ سنين (معدّل التضخم)", "cat": "العوائد الحقيقية",
                   "why": "ده القياس الحقيقي لتكلفة الفرصة البديلة للذهب (مش العائد الاسمي).",
                   "relation": "ارتفاع العائد الحقيقي ضغط على الذهب تاريخياً.",
                   "freq": "daily"},
    "us2y": {"name_ar": "عائد الخزانة ٢ سنين", "cat": "الفائدة الأمريكية",
             "why": "بيعكس توقعات الفيدرالي على المدى القريب.",
             "relation": "ارتفاعه = السوق متوقع فائدة أعلى = ضغط على الذهب غالباً.",
             "freq": "daily"},
    # ⛔⛔ (حيدر): الرقم **مؤشر أسعار** مش نسبة تضخم + أساسه ١٩٨٢-٨٤=١٠٠
    "cpi_us": {"name_ar": "مؤشر أسعار المستهلك الأمريكي", "cat": "التضخم الأمريكي",
               "why": "التضخمaga يخلّي الذهب وسيلة حفظ القيمة جذابة — بس الأثر بييجي عبر الفيدرالي.",
               "relation": "تضخم أعلى = توقع فائدة أعلى = ضغط على الذهب غالباً (مش مضمون).",
               "freq": "monthly"},
    "pce_us": {"name_ar": "مؤشر أسعار الاستهلاك الشخصي (PCE)", "cat": "التضخم الأمريكي",
               "why": "المؤشر اللي الفيدرالي بيهتم بيه أكتر من CPI.",
               "relation": "زي CPI — بيمرّ على Expectations الفيدرالي.",
               "freq": "monthly"},
    "payrolls": {"name_ar": "التوظيف غير الزراعي", "cat": "التوظيف والنمو",
                 "why": "قوة سوق العمل بتغيّر توقعات الفيدرالي على الفائدة.",
                 "relation": "توظيف أقوى = فائدة أعلى = ضغط على الذهب غالباً.",
                 "freq": "monthly"},
    "unrate": {"name_ar": "معدل البطالة", "cat": "التوظيف والنمو",
               "why": "ارتفاعه = اقتصاد أضعف = احتمال خفض فائدة = دعم للذهب.",
               "relation": "بطالة أعلى = دعم للذهب غالباً — مع تحليل alfabra.",
               "freq": "monthly"},
    "fed_funds": {"name_ar": "سعر فائدة الفيدرالي (الليلي)", "cat": "الفائدة الأمريكية",
                  "why": "السعر الفعلي中对لبنان — بيعكس توقعات السوق.",
                  "relation": "الفائدة أعلى = تكلفة فرصة أعلى = ضغط على الذهب.",
                  "freq": "daily"},
    # ⛔⛔ (حيدر): **مؤشر** أسعار مش نسبة تضخم
    "cpi_eg": {"name_ar": "مؤشر أسعار المستهلك المصري (البنك الدولي)", "cat": "التضخم المصري",
               "why": "التضخم بيقلل القوة الشرائية للجنيه ⇒ الذهب بيبقى ملاذ.",
               "relation": "تضخم محلي أعلى = ضغط على الجنيه = دعم لأسعار الذهب بالجنيه.",
               "freq": "annual"},
    "eg_deposit": {"name_ar": "متوسط سعر فائدة الإيداع في مصر", "cat": "الفائدة المصرية",
                   "why": "المقارنة الحقيقية: هل أحسن أ ادخّر في البنك ولا في الذهب؟",
                   "relation": "فائدة عالية = بديل ادخار قوي = ضغط على الطلب على الذهب.",
                   "freq": "annual"},
    "cbe_policy": {"name_ar": "فائدة الإيداع الليلي (البنك المركزي المصري)", "cat": "الفائدة المصرية",
                   "why": "الرقم الرسمي.bi角落里.",
                   "relation": "فائدة أعلى = تكلفة سيولة أعلى = ضغط على الذهب.",
                   "freq": "current"},
    # ⛔⛔ (حيدر): الرقم ١٣٫٩٪ = **سنوي (y/y)** مش شهري ⇒ لازم mousom
    "cbe_inflation": {"name_ar": "التضخم المصري — سنوي (البنك المركزي)", "cat": "التضخم المصري",
                      "why": "الرقم الرسمي الأحدث (شهري/سنوي).",
                      "relation": "كل ما التضخم أعلى، كل ما ضغط الجنيه زاد.",
                      "freq": "current"},
    "usd_egp": {"name_ar": "سعر الدولار مقابل الجنيه", "cat": "الدولار مقابل الجنيه",
                 "why": "بيحوّل سعر الذهب العالمي بالجنيه. أقوى عامل في السوق المصري.",
                 "relation": "جنيه أضعف = سعر الذهب بالجنيه أعلى — علاقة حسابية مباشرة.",
                 "freq": "daily"},
    "xau": {"name_ar": "الذهب العالمي (XAU/USD)", "cat": "الذهب العالمي",
            "why": "الأساس العالمي لسعر الذهب في كل العالم.",
            "relation": "الأساس — كل حاجة محلية بتبني عليه.",
            "freq": "daily"},
}


def build(force=False):
    """يبني كل العوامل. ⛔ أي عامل فاشل ⇒ status='missing' + سبب (مش crash)."""
    with _LOCK:
        now = time.time()
        if not force and _MEM["data"] and (now - _MEM["ts"]) < CACHE_TTL:
            return _MEM["data"]
        # ── كاش القرص (٦ ساعات) —_sources بطيئة/متقطعة_ ──
        if not force:
            _d = _load_disk()
            if _d and (now - float(_d.get("built_at") or 0)) < DISK_TTL:
                _MEM["data"] = _d
                _MEM["ts"] = now
                return _d

        F = {}

        def add(key, stats, source, source_url, unit="", extra=None):
            meta = FACTOR_META.get(key, {})
            if not stats:
                F[key] = {"key": key, "name_ar": meta.get("name_ar", key),
                          "cat": meta.get("cat"), "status": "missing",
                          "error": (extra or {}).get("error", "المصدر رجّع فاضي"),
                          "why": meta.get("why"), "relation": meta.get("relation"),
                          "value": None, "date": None}
                return
            fr = _freshness(stats.get("date"), daily=(meta.get("freq") == "daily"))
            F[key] = {
                "key": key, "name_ar": meta.get("name_ar", key),
                "cat": meta.get("cat"), "status": fr["status"],
                "value": stats.get("value"), "date": stats.get("date"),
                "previous": stats.get("previous"),
                "previous_date": stats.get("previous_date"),
                "direction": stats.get("direction"),
                "unit": unit or stats.get("unit"),
                "source": source, "source_url": source_url,
                "points": stats.get("points"),
                "why": meta.get("why"), "relation": meta.get("relation"),
                "caveat": ("علاقة نوعية موصوفة — مش رقم تأثير وبيسلف causal."
                           if meta.get("relation") else None),
            }
            if extra:
                F[key].update(extra)

        # ══════════ كل النداءات الشبكية **بالتوازي** ══════════
        # 📌 كان بالترتيب ⇒ ٢:٤٠ دقيقة (!) — دلوقتي ~٢٠ ثانية.
        from concurrent.futures import ThreadPoolExecutor

        # ⛔⛔ FRED معلّق/محبوب من بيئتنا (بيقعد ٧٨ ثانية ويطلّع ٠ نقطة).
        #    ⇒ افتراضياً مقفول؛ فعّله بس لو الشبكة سليمة: GOLD_FRED=1
        _use_fred = str(os.environ.get("GOLD_FRED", "")).strip() in ("1", "true", "yes")

        def _t_nominal():
            return ("nominal", treasury_nominal())

        def _t_real():
            return ("real", treasury_real())

        def _t_effr():
            return ("effr", nyfed("effr"))

        def _t_dxy():
            return ("dxy", dxy_bars())

        def _t_fred(sid):
            # ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ — FRED عبر TradingView (شغّال وسريع) أولاً
            _r = tv_fred(sid)
            if not _r.get("points") and _use_fred:
                _r = fred(sid, tries=1)
            return ("fred:" + sid, _r)

        def _t_wb(ind):
            return ("wb:" + ind, world_bank(ind))

        _FRED_IDS = ("CPIAUCSL", "PCEPI", "PAYEMS", "UNRATE")
        _WB_IDS = ("FP.CPI.TOTL", "FR.INR.DPST")

        with ThreadPoolExecutor(max_workers=10) as _ex:
            _futs = [_ex.submit(_t_nominal), _ex.submit(_t_real),
                     _ex.submit(_t_effr), _ex.submit(_t_dxy)]
            # ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ — FRED عبر TradingView شغّال وسريع
            #    ⇒ المجموعة بتشتغل دايماً (مش بس مع GOLD_FRED).
            _futs += [_ex.submit(_t_fred, s) for s in _FRED_IDS]
            _futs += [_ex.submit(_t_wb, i) for i in _WB_IDS]
            R = {}
            for _f in _futs:
                try:
                    _k, _v = _f.result()
                    R[_k] = _v
                except Exception as _e:
                    R["err"] = str(_e)[:80]

        # ── العوائد الاسمية: الخزانة أولاً (مصدر رسمي) ثم FRED ──
        _nom = R.get("nominal") or {"points": [], "error": "فشل"}

        def _nom_pick(idx):
            # ⛔ الصفوف 3 قيم (iso, y2, y10) — فكّك 3 مش 2
            return [(d, row[idx]) for d, *row in (_nom.get("points") or [])
                    if len(row) >= 2]

        def _from_nom(idx, sid):
            pts = _nom_pick(idx)
            if pts:
                return {"points": pts, "source": _nom.get("source"),
                        "source_url": _nom.get("source_url"), "error": None}
            r = R.get("fred:" + sid) or {}
            return {"points": r.get("points", []), "source": r.get("source"),
                    "source_url": r.get("source_url"), "error": r.get("error")}

        # ⛔ بعد فكّك (d, *row) بقى row[0]=y2 و row[1]=y10
        _r2 = _from_nom(0, "DGS2")
        _r10 = _from_nom(1, "DGS10")
        _real = R.get("real") or {}
        if not (_real.get("points") or []):
            _rf = R.get("fred:DFII10") or {}
            _real = {"points": _rf.get("points", []), "source": _rf.get("source"),
                     "source_url": _rf.get("source_url"), "error": _rf.get("error")}
        _effr = R.get("effr") or {}

        for key, r, unit in (("us2y", _r2, "%"), ("us10y", _r10, "%"),
                             ("us10y_real", _real, "%"), ("fed_funds", _effr, "%")):
            st = _series_stats(r.get("points"), unit)
            add(key, st, r.get("source"), r.get("source_url"), unit,
                {"error": r.get("error")})

        # ── عوامل الفيدرالي (FRED) ──
        for key, sid, unit in (("cpi_us", "CPIAUCSL", "مؤشر (1982-84=100) — موسمي"),
                               ("pce_us", "PCEPI", "مؤشر (2017=100) — موسمي"),
                               ("payrolls", "PAYEMS", "ألف شخص"),
                               ("unrate", "UNRATE", "%")):
            r = R.get("fred:" + sid) or {}
            _pts = r.get("points") or []
            # ⛔⛔ PAYEMS من FRED **بالأفراد** (159,044,000) ومن BLS **بالآلاف**
            #    (159,044) ⇒ لازم نطبّع لوحدة واحدة (آلاف) عشان ما يتقارنوش غلط.
            if key == "payrolls":
                _pts = [(d, (v / 1000.0 if v and v > 1e6 else v)) for d, v in _pts]
            st = _series_stats(_pts, unit)
            # ⛔⛔ سبب واضح لو المصدر رجع فاضي (مش error فاضي!)
            _err = r.get("error")
            if not st and not _err:
                _err = ("مصدر FRED مقفول في هذه البيئة (GOLD_FRED=1 بيفتحه) — "
                        "والبديل BLS." if not _use_fred else "المصدر رجّع فاضي")
            add(key, st, r.get("source"), r.get("source_url"), unit,
                {"error": _err})

        # ── BLS كبديل للسلاسل اللي FRED رجّعها فاضية ──
        _need = [k for k in ("cpi_us", "unrate", "payrolls")
                 if not (F.get(k) or {}).get("value")]
        if _need:
            # ⛔ BLS CUUR0000SA0 = غير موسمي (NSA) وأساسه 1982-84=100
            _BLS_MAP = {"cpi_us": ("CUUR0000SA0", "مؤشر (1982-84=100) — غير موسمي"),
                        "unrate": ("LNS14000000", "%"),
                        "payrolls": ("CES0000000001", "ألف شخص")}
            _ids = [_BLS_MAP[k][0] for k in _need if k in _BLS_MAP]
            if _ids:
                rb = bls(_ids)
                ser = rb.get("series") or {}
                for k in _need:
                    if k not in _BLS_MAP:
                        continue
                    sid, unit = _BLS_MAP[k]
                    pts = ser.get(sid) or []
                    st = _series_stats(pts, unit)
                    if st:
                        add(k, st, rb.get("source"), rb.get("source_url"), unit,
                            {"error": None,
                             "note": "من مصدر بديل (BLS) لأن FRED لم يستجب."})
                    else:
                        # ⛔ سبب واضح: BLS فاشل (سقف يومي/شبكة)
                        add(k, None, rb.get("source"), rb.get("source_url"), unit,
                            {"error": rb.get("error") or "البديل (BLS) رجّع فاضي"})

        # ── البنك الدولي (مصر) ──
        for key, ind, unit in (("cpi_eg", "FP.CPI.TOTL", "مؤشر (2010=100)"),  # ✅ صح
                               ("eg_deposit", "FR.INR.DPST", "%")):
            r = R.get("wb:" + ind) or {}
            st = _series_stats(r.get("points"), unit)
            add(key, st, r.get("source"), r.get("source_url"), unit,
                {"error": r.get("error"), "lastupdated": r.get("lastupdated")})

        # ── DXY (TradingView) ──
        _dxy = R.get("dxy") or []
        st = _series_stats([(b["d"], b["c"]) for b in _dxy]) if _dxy else None
        # ⛔⛔ (حيدر): DXY **نقطة مؤشر** (أساس 1973=100) مش نسبة
        add("dxy", st, "TradingView TVC:DXY",
            "https://www.tradingview.com/symbols/TVC-DXY/", "نقطة (أساس 1973=100)",
            {"error": None if _dxy else "فشل جلب DXY"})

        # ── البنك المركزي المصري (ملف محفوظ) ──
        eg = egypt_macro()
        if eg:
            fx = ((eg.get("extra") or {}).get("fx") or {})
            factors = eg.get("factors") or {}
            st = _series_stats([(fx.get("last_updated") or "", fx.get("sell"))],
                               "جنيه/دولار") if fx.get("sell") else None
            add("usd_egp", st, "البنك المركزي المصري (ملف البيانات المحفوظ)",
                fx.get("source_url", "https://www.cbe.org.eg/en/economic-research/statistics/exchange-rates"),
                "جنيه/دولار", {"error": None,
                                "note": "سعر بيع البنك المركزي — الأساس اللي بتتحسب بيه أسعار الصاغة."})
            pol = factors.get("policy_rate") or {}
            st2 = _series_stats([(pol.get("published") or "", pol.get("value"))], "%") \
                if pol.get("value") is not None else None
            add("cbe_policy", st2, pol.get("source", "البنك المركزي المصري"),
                pol.get("source_url", ""), "%", {"error": None})
            inf = factors.get("inflation_headline") or {}
            st3 = _series_stats([(inf.get("published") or "", inf.get("value"))], "%") \
                if inf.get("value") is not None else None
            add("cbe_inflation", st3, inf.get("source", "البنك المركزي المصري"),
                inf.get("source_url", ""), "%", {"error": None})
        else:
            for key in ("usd_egp", "cbe_policy", "cbe_inflation"):
                add(key, None, "البنك المركزي المصري", "", "", {"error": "ملف البيانات مش موجود"})

        # ── الذهب العالمي (للمرجع) ──
        try:
            import importlib
            gh = importlib.import_module("gold_history")
            series = gh.build().get("series") or []
            st = _series_stats([(r["d"], r["xau"]) for r in series], "دولار/أونصة")
            add("xau", st, "TradingView FX_IDC:XAUUSD",
                "https://www.tradingview.com/symbols/XAUUSD/", "دولار/أونصة",
                {"error": None})
        except Exception as e:
            add("xau", None, "TradingView", "", "", {"error": str(e)[:80]})

        out = {
            "ok": True,
            "built_at": now,
            "built_iso": datetime.datetime.utcnow().isoformat() + "Z",
            "factors": F,
            "available": [k for k, v in F.items() if v.get("status") != "missing"],
            "missing": [k for k, v in F.items() if v.get("status") == "missing"],
            "caveat": ("العوامل دي **مشтие** (توصيف) — مفيش أي عامل بنحسبله «تأثير %» "
                       "من غير قياس. وكمان العوامل ممكن تتضارب مع بعض."),
        }
        _MEM["data"] = out
        _MEM["ts"] = now
        # ── كاش القرص (بيتحفظ بعد البناء الناجح بس) ──
        try:
            _save_disk(out)
        except Exception:
            pass
        return out


def factors_list():
    """العوامل مرتبة حسب الفئة — للعرض في «محرك العوامل»."""
    d = build()
    if not d or not d.get("ok"):
        return {"ok": False, "error": (d or {}).get("error"), "categories": []}
    cats = {}
    for k, v in (d.get("factors") or {}).items():
        c = v.get("cat") or "أخرى"
        cats.setdefault(c, []).append(v)
    order = ["الدولار الأمريكي", "الفائدة الأمريكية", "العوائد الحقيقية", "التضخم الأمريكي",
             "التوظيف والنمو", "الدولار مقابل الجنيه", "الفائدة المصرية", "التضخم المصري",
             "الذهب العالمي", "أخرى"]
    out = []
    for c in order:
        if c in cats:
            out.append({"category": c, "factors": cats[c]})
    return {"ok": True, "categories": out,
            "available": d.get("available"), "missing": d.get("missing"),
            "caveat": d.get("caveat"), "built_iso": d.get("built_iso")}


# ═══════════ BLS (مكتب إحصاءات العمل الأمريكي) ═══════════
# 📌 بديل لـFRED للسلسلة earmajal: CPI · البطالة · التوظيف.
# ⛔ v1 بدون مفتاح (حد ٥ سلاسل و١٠ سنوات لكل نداء).
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"


def _http_post_json(url, payload, timeout=20, tries=2):
    import urllib.request
    import gzip
    import io as _io
    data = json.dumps(payload).encode("utf-8")
    last = None
    for i in range(max(1, tries)):
        try:
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": _UA, "Content-Type": "application/json",
                "Accept": "application/json", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.GzipFile(fileobj=_io.BytesIO(raw)).read()
                return json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception as e:
            last = e
            if i < max(1, tries) - 1:
                time.sleep(1.0 * (i + 1))
    raise last if last else RuntimeError("post-failed")


def bls(series_ids, startyear=None, endyear=None):
    """سلاسل BLS ⇒ {series_id: [(date, value)]}."""
    y0 = startyear or (datetime.date.today().year - 6)
    y1 = endyear or datetime.date.today().year
    try:
        j = _http_post_json(BLS_URL, {"seriesid": list(series_ids),
                                      "startyear": str(y0), "endyear": str(y1)})
    except Exception as e:
        return {"error": "فشل BLS: " + str(e)[:80], "series": {}}
    out = {}
    for s in (j.get("Results") or {}).get("series") or []:
        sid = s.get("seriesID")
        pts = []
        for d in s.get("data") or []:
            try:
                pts.append(("%s-%s-01" % (d.get("year"), (d.get("period") or "").replace("M", "").zfill(2)), float(d["value"])))
            except Exception:
                continue
        pts.sort()
        if pts:
            out[sid] = pts
    if not out:
        st = (j.get("status") or "")
        if "NOT_PROCESSED" in st.upper():
            return {"error": "تجاوز الحد اليومي لطلبات BLS (٢٥ طلب/يوم/IP) — "
                             "المصدر هيتعافى بعد إعادة ضبط الحصة.", "series": {}}
        return {"error": "BLS رجّع فاضي", "series": {}}
    return {"series": out, "source": "مكتب إحصاءات العمل الأمريكي (BLS)",
            "source_url": "https://api.bls.gov/publicAPI/v1/timeseries/data/"}


# ═══════════ بنك نيويورك الفيدرالي (EFFR/SOFR) ═══════════
# 📌 المصدر الرسمي لفائدة الفيدرالي الفعلية.
NYFED_EFFR = ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
              "?startDate={d1}&endDate={d2}&type=rate")
NYFED_SOFR = ("https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
              "?startDate={d1}&endDate={d2}&type=rate")


def nyfed(kind="effr", years=2):
    """سلاسل EFFR/SOFR من بنك نيويورك — ⛔ points فاضية لو فشل."""
    d2 = datetime.date.today()
    d1 = d2 - datetime.timedelta(days=int(years * 372))
    url = (NYFED_EFFR if kind == "effr" else NYFED_SOFR).format(d1=d1.isoformat(), d2=d2.isoformat())
    try:
        j = json.loads(_http(url, timeout=20, tries=2, headers={"Accept": "application/json"}))
    except Exception as e:
        return {"error": "فشل بنك نيويورك: " + str(e)[:80], "points": []}
    pts = []
    for r in (j.get("refRates") or []):
        d = r.get("effectiveDate")
        v = r.get("percentRate")
        if not d or v is None:
            continue
        try:
            pts.append((d, float(v)))
        except Exception:
            continue
    pts.sort()
    if not pts:
        return {"error": "رد فاضي", "points": []}
    name = ("فائدة الفيدرالي الفعلية (EFFR)" if kind == "effr"
            else "معدل SOFR (بديل مرجعي)")
    return {"points": pts, "source": "بنك نيويورك الفيدرالي (New York Fed)",
            "source_url": "https://www.newyorkfed.org/markets/reference-rates/" +
                          ("effective-federal-funds-rate" if kind == "effr" else "sofr"),
            "name_ar": name}

# ═══════════ الكاش على القرص ═══════════
# 📌 ليه؟ مصادر الماكرو بطيئة ومتقطعة (FRED، BLS سقف يومي…).
#    ⇒ نبني مرة ونحفظ، والـendpoint يرد فوراً من الكاش.
# ⛔ الكاش بيخزّن القيم最后一次 الناجحة فقط — لو البناء فشل كله ما نورثش أرقام قديمة كأنها جديدة.
DATA_DIR = str(HERE / "data")
CACHE_FILE = os.path.join(DATA_DIR, "gold_factors.json")
DISK_TTL = 6 * 3600


def _load_disk():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or not d.get("factors"):
            return None
        return d
    except Exception:
        return None


def _save_disk(d):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    d = build(force=True)
    print("متاح:", len(d.get("available") or []), "| ناقص:", d.get("missing"))
    for k, v in (d.get("factors") or {}).items():
        print(f"  {k:14} {v.get('status'):8} {str(v.get('value')):>12} {v.get('unit','')} "
              f"| {v.get('date')} | {v.get('source','')[:38]}")
