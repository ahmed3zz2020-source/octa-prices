"""
═══════════════════════════════════════════════════════════════
 gold_local.py — السعر المحلي للذهب في مصر (مرصود · مش محسوب)
═══════════════════════════════════════════════════════════════
 📌 الفكرة: «سعر الجرام» في الموقع لحد دلوقتي **محسوب** (ذهب عالمي ×
    دولار). ده **مش** السعر اللي المصري بيدفعه. الخدمة دي بتجيب
    السعر **المرصود** من مرجع سوق مصري + سعر الشراء والبيع.

 ⛔⛔⛔ قواعد (ممنوع نكسرها):
 ① **ممنوع نخترع رقم.** لو السحب أو التحليل فشل ⇒ None + سبب مكتوب.
 ② **لازم نفرّق بين سعر الشراء وسعر البيع** — دي مش نفس الرقم.
    (المستخدم بيدفع سعر البيع، والتاجر بيدفع سعر الشراء.)
 ③ **لازم نوثّق وقت آخر تحديث** من الوسم `<time datetime="ISO-8601">` بتاع المصدر
    (ISO + توقيت) — مش وقت السحب بتاعنا.
 ④ ⛔ **مصدر تجاري مش جهة حكومية.** لازم الواجهة تقول كده.
 ⑤ ⚠️ **سعر الجرام المعروض = سعر الجرام ÷ 31.1035** (أونصة تروي).
    مفيش «كرك» ولا «أونصة عادية» — التروية 31.1035 جرام بالظبط.

 📌 ليه scraping؟ مفيش API رسمي للمصدر ده. الصفحة **server-rendered**
    ⇒ `requests` + HTML parsing كفاية (مفيش متصفح ⇒ مفيش تكلفة).
    ⛔ بنخلي الـUA زين وبنجيب بهدوء (مرة كل ١٠ دقايق كاش).
═══════════════════════════════════════════════════════════════
"""
import json
import os
import re
import threading
import time
import datetime

ISAGHA_URL = "https://market.isagha.com/prices"
TROY_OUNCE_GRAMS = 31.1035

CACHE_TTL = int(os.environ.get("GOLD_LOCAL_TTL", "600"))   # ١٠ دقايق
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_LOCK = threading.Lock()
_MEM = {"ts": 0, "data": None}


def _http_get(url, timeout=20):
    """
    ⛔ urllib (stdlib) مش requests — عشان يشتغل في أي بيئة من غير تبعيات.
    ⛔ بنفكّ ضغط gzip لو السيرفر بعته.
    """
    import urllib.request
    import gzip
    import io as _io
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "gzip",
        "Accept-Language": "ar,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            raw = gzip.GzipFile(fileobj=_io.BytesIO(raw)).read()
        return raw.decode("utf-8", errors="ignore")


def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def parse(html):
    """
    ⛔ بترجع dict أو None. مفيش أرقام مخترعة.
    البنية: بلوك لكل عيار: <li data-unit="NN"> فيه سعر الشراء
    <span data-testid="price-figure">NUMBER</span> و سعر البيع
    """
    if not html or "prices-strip" not in html:
        return None

    out = {"karats": {}, "source": "iSagha — مرجع سوق ذهب مصري",
           "source_url": ISAGHA_URL,
           "source_type": "commercial_market_reference",
           "license_note": "مرجع تجاري — مش سعر رسمي حكومي، والتعبئة مش بتتعارض مع عدم نسخ النص."}

    # ① الوقت الرسمي للمصدر
    m = re.search(r'<time[^>]*datetime="([^"]+)"[^>]*data-testid="prices-updated"', html)
    if m:
        out["updated_iso"] = m.group(1)
        out["updated_text"] = re.sub(r"<[^>]+>", "", m.group(0)).strip() if False else None
    # ② بلوك التوقيت (نص)
    m2 = re.search(r'data-testid="prices-updated"[^>]*>\s*<bdi>([^<]+)</bdi>', html)
    if m2:
        out["updated_text"] = m2.group(1).strip()

    # ③ بلوكات العيارات
    # كل بلوك: <li data-unit="NN"> وبيقفل بـ </li>
    for blk in re.split(r'<li[^>]*data-unit="', html)[1:]:
        um = re.match(r'(\d+)', blk)
        if not um:
            continue
        unit = um.group(1)
        # قصّ البلوك عند أول </li> بعده
        seg = blk[:blk.find("</li>") + 5] if "</li>" in blk else blk[:4000]
        buy = sell = cur = None
        bm = re.search(r'prices-strip__price--buy.*?data-testid="price-figure"[^>]*>([^<]+)<.*?'
                       r'prices-strip__currency[^>]*>([^<]+)<', seg, re.S)
        sm = re.search(r'prices-strip__price--sell.*?data-testid="price-figure"[^>]*>([^<]+)<.*?'
                       r'prices-strip__currency[^>]*>([^<]+)<', seg, re.S)
        if bm:
            buy = _num(bm.group(1))
            cur = bm.group(2).strip()
        if sm:
            sell = _num(sm.group(1))
            cur = cur or sm.group(2).strip()
        if buy is None and sell is None:
            continue
        out["karats"][unit] = {"buy": buy, "sell": sell, "currency": cur}

    if not out["karats"]:
        return None

    # ④ سعر عيار 24 (الجرام) — من الكارت الرئيسي
    m24 = re.search(r'ذهب\s*عيار\s*24.{0,400}?data-testid="price-figure"[^>]*>([^<]+)<', html, re.S)
    if m24:
        v = _num(m24.group(1))
        if v:
            out["gram_24_reference"] = v
    if "gram_24_reference" not in out:
        k24 = out["karats"].get("24")
        if k24 and k24.get("sell"):
            out["gram_24_reference"] = k24["sell"]
            out["gram_24_source"] = "derived_from_strip_sell"
    # ⛔ 24K: المصدر بيعرض سعر الجرام في الكارت الرئيسي بس (من غير شراء/بيع)
    g24 = out.get("gram_24_reference")
    if g24:
        out["karats"].setdefault("24", {
            "buy": None, "sell": None, "currency": "ج.م",
            "gram_reference": g24,
            "note": "المصدر بيعرض سعر جرام عيار 24 كسعر مرجعي (من غير سعر شراء/بيع منفصل).",
        })

    # ⑤ أرقام النمو المنشورة (نسب حقيقية من المصدر)
    # ⛔ ملاحظة: القيمة موجودة في HTML الساكن (Alpine x-text) لكن مدة
    #    الفترة بتتغيّر مع الـchart ⇒ بنقرا الافتراضي (سنة) بس.
    #    أرقام الـ5 سنين بتتحصد بمتصفح (tools/harvest_gold_local.py).
    # ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ (حيدر-البيانات): الـregex القديم كان بياخد **أول**
    #    <bdi> فيه current.growth وده **العنوان** («معدل النمو خلال السنة الماضية :»)
    #    مش الرقم ⇒ النمو دايماً None. الرقم في:
    #    <span x-text="current.growth === null ? '' : current.growth + '%'">15%</bdi>
    gm = re.search(r"current\.growth\s*\+\s*'%'\"\s*>\s*([^<]*)<\/bdi>", html)
    if not gm:
        gm = re.search(r"current\.growth[^>]*>\s*([0-9][0-9.,]*)\s*%<\/bdi>", html)
    if gm:
        v = _num(str(gm.group(1)).replace("%", "").replace("٪", "").replace(",", ""))
        if v is not None:
            out["growth_pct"] = v
            out["growth_period"] = "السنة الماضية"   # الـchart الافتراضي
            # ⛔ المدة الافتراضية (سنة) — المصدر بيغيّرها مع الـchart
            out["growth_period"] = "السنة الماضية"
    g5 = re.search(r'معدل النمو خلال آخر خمس سنوات\s*:\s*([0-9.]+)\s*%', html)
    if g5:
        out["growth_5y_pct"] = _num(g5.group(1))
    else:
        # ⛔ الرقم مش في الـHTML الساكن (بيتحصد بمتصفح) ⇒ سبب صريح
        out["growth_5y_note"] = ("رقم النمو لـ5 سنين مش في الصفحة الساكنة — "
                                 "بيتحصد بمتصفح (أداة الحصاد).")

    # ⑥ الأونصة بالدولار (لو موجودة في الصفحة)
    om = re.search(r'أوقية الذهب.{0,300}?>\s*([0-9]{3,5}\.[0-9]{2})\s*<', html, re.S)
    if om:
        out["ounce_usd"] = _num(om.group(1))

    out["fetched_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    return out


def get(force=False):
    with _LOCK:
        now = time.time()
        if not force and _MEM["data"] and (now - _MEM["ts"]) < CACHE_TTL:
            return _MEM["data"]
        try:
            html = _http_get(ISAGHA_URL)
        except Exception as e:
            return {"ok": False, "error": "فشل الوصول للمصدر: " + str(e)[:100],
                    "fetched_at": now}
        d = parse(html)
        if not d:
            return {"ok": False, "error": "المصدر رجّع صفحة بدون أسعار مفهومة",
                    "fetched_at": now}
        d["ok"] = True
        _MEM["data"] = d
        _MEM["ts"] = now
        return d


def gram_prices(data=None):
    """
    ⛔ بيرجّع {karat: {buy_gram, sell_gram}} — قسمة على 31.1035.
    الأونصة بتروية (31.1035 جرام) — مش الأونصة العادية (28.35).
    """
    d = data or get()
    if not d or not d.get("ok"):
        return None
    out = {}
    for k, v in (d.get("karats") or {}).items():
        e = {}
        if v.get("buy") is not None:
            e["buy_gram"] = round(v["buy"] / TROY_OUNCE_GRAMS, 2)
        if v.get("sell") is not None:
            e["sell_gram"] = round(v["sell"] / TROY_OUNCE_GRAMS, 2)
        if v.get("currency"):
            e["currency"] = v["currency"]
        if e:
            e["spread"] = (round(e["sell_gram"] - e["buy_gram"], 2)
                           if "buy_gram" in e and "sell_gram" in e else None)
            e["spread_pct"] = (round((e["sell_gram"] / e["buy_gram"] - 1) * 100, 3)
                               if e.get("buy_gram") and e.get("sell_gram") else None)
            out[k] = e
    return out


def freshness(data=None):
    """
    ⛔ بصراحة: «طازج» / «متأخر» / «قديم» — على أساس وقت **المصدر** مش وقت سحبنا.
    """
    d = data or get()
    if not d or not d.get("ok"):
        return {"status": "missing", "age_minutes": None}
    iso = d.get("updated_iso")
    if not iso:
        return {"status": "unknown", "age_minutes": None}
    try:
        t = datetime.datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        age = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 60.0
    except Exception:
        return {"status": "unknown", "age_minutes": None}
    if age < 0:
        return {"status": "live", "age_minutes": round(age, 1), "updated_iso": iso}
    if age <= 90:
        st = "live"
    elif age <= 60 * 24:
        st = "delayed"
    else:
        st = "stale"
    return {"status": st, "age_minutes": round(age, 1), "updated_iso": iso}


if __name__ == "__main__":
    d = get(force=True)
    if not d.get("ok"):
        print("❌", d.get("error"))
    else:
        print("✅ آخر تحديث:", d.get("updated_text"), "|", d.get("updated_iso"))
        print("   النمو 1 سنة:", d.get("growth_1y_pct"), "% | 5 سنين:", d.get("growth_5y_pct"), "%")
        print("   جرام 24 (مرجعي):", d.get("gram_24_reference"))
        for k, v in sorted((d.get("karats") or {}).items()):
            print(f"   {k}K: شراء {v.get('buy')} / بيع {v.get('sell')} {v.get('currency')}")
        print("   الجرامات:", gram_prices(d))
        print("   الطزاجة:", freshness(d))


# ════════════════════════════════════════════════════════════════
# 🔎 مصدر تاني للمرصود — goldbullioneg (صاغة تانية) للمقارنة
# ════════════════════════════════════════════════════════════════
# 📌 ليش مهم: البرومبت بيقول «Cross-check local quotations when possible».
#    مصدرين مستقلين بيقولوا الفرق = نطاق أسعار الصاغة (مش رقم واحد).
# ⛔ ملاحظة: عمود السعر الأول = **بيع** · التاني (td-arrow) = **شراء**
#    (اتأكدنا من صف الدولار: 56.35 بيع / 56.25 شراء).
BULLION_URL = "https://goldbullioneg.com/"


def _parse_bullion_new(html):
    """
    📌 بنية الصفحة الحالية (٢٠٢٦-١١-١٩): بطاقات أسعار ببلاش-إرج.
       · كل عيار:  <span class="gbs-fp__kn">عيار ٢١</span>
                    <span class="gbs-fp__kb">٥٬٧٤٥</span>   ← «شراء» = سعر الشراء **من المحل**
                    <span class="gbs-fp__ks">٥٬٧٢٥</span>   ← «بيع» = سعر البيع **للمحل**
       · بطاقات المؤشرات: gbs-fp__tn (الاسم) · gbs-fp__tv (القيمة) · gbs-fp__kn (سعر البيع)
       ⛔ نفس اصطلاح iSagha: `sell` = السعر اللي العميل بيدفعه ·
          `buy` = السعر اللي العميل بيستلمه من المحل.
    """
    if not html or "gbs-fp__" not in html:
        return None
    out = {"source": "goldbullioneg — صاغة مصرية (مرجع سوق)",
           "source_url": BULLION_URL,
           "source_type": "commercial_market_reference",
           "karats": {}, "rows": [],
           "parse_layout": "cards_v2"}
    # ① بطاقات العيارات (الترتيب: اسم · شراء · بيع)
    for m in re.finditer(r'gbs-fp__kn"[^>]*>\s*([^<]{1,24}?)\s*</span>\s*'
                         r'<span class="gbs-fp__kb"[^>]*>([^<]+)</span>\s*'
                         r'<span class="gbs-fp__ks"[^>]*>([^<]+)</span>', html):
        label = m.group(1).strip()
        kb = _num(m.group(2))       # «شراء» = العميل بيشتري من المحل (هو اللي بيدفع)
        ks = _num(m.group(3))       # «بيع» = العميل بيبيع للمحل (هو اللي بيستلم)
        km = re.search(r"(?:عيار|جرام عيار)\s*(\d+)", label)
        if not km or kb is None or ks is None:
            continue
        out["karats"][km.group(1)] = {
            "buy": ks, "sell": kb, "currency": "ج.م",
            "note": ("المصدر بيعرض «شراء» (السعر اللي العميل بيدفعه) و«بيع» "
                     "(السعر اللي بيستلمه) — اتبنوا على نفس اصطلاح iSagha."),
        }
    if not out["karats"]:
        return None
    # ② بطاقات المؤشرات: الدولار · الأونصة · الجنيه الذهب
    for m in re.finditer(r'gbs-fp__tn"[^>]*>\s*([^<]{1,24}?)\s*</span>\s*'
                         r'<span class="gbs-fp__tv"[^>]*>([^<]+)</span>\s*'
                         r'<span class="gbs-fp__kn"[^>]*>([^<]{1,24}?)</span>', html):
        label = m.group(1).strip()
        pv = re.search(r"[0-9][0-9.,]*", m.group(2))
        primary = _num(pv.group(0)) if pv else None
        sell_txt = m.group(3).strip()
        sm = re.search(r"([0-9][0-9.,]*)", sell_txt)
        sell = _num(sm.group(1)) if sm else None
        if primary is None:
            continue
        if "الدولار" in label:
            out["usd_egp"] = {"buy": primary, "sell": sell,
                              "primary": primary, "sell_labeled": sell,
                              "note": ("الرقم الظاهر في البطاقة + سعر البيع "
                                       "المذكور تحته — الأرقام كما يعرضها "
                                       "المصدر بالظبط.")}
        elif "أونصة" in label:
            out["ounce_usd"] = {"buy": primary, "sell": sell,
                                "primary": primary, "sell_labeled": sell}
        else:
            out["rows"].append({"label": label[:40], "buy": primary, "sell": sell})
    # ③ الكارت الرئيسي (عيار ٢١) — تقاطع مع بطاقات العيارات
    mm = re.search(r'gbs-fp__pl"[^>]*>\s*شراء من المحل\s*</span>\s*'
                   r'<span class="gbs-fp__big"[^>]*>([^<]+)</span>', html)
    if mm:
        out["main_card_sell_21"] = _num(mm.group(1))
    ms = re.search(r'gbs-fp__pl"[^>]*>\s*بيع للمحل\s*</span>\s*'
                   r'<span class="gbs-fp__mid"[^>]*>([^<]+)</span>', html)
    if ms:
        out["main_card_buy_21"] = _num(ms.group(1))
    # ⛔ المصدر ما بيعرضش وقت تحديث ثابت ⇒ بنوثّق وقت السحب بس
    out["updated_iso"] = None
    out["updated_note"] = ("المصدر ما بيعرضش وقت تحديث ثابت في الصفحة "
                           "⇒ وقت المصدر غير متاح (وقت السحب هو المرجع).")
    out["fetched_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    return out


def _parse_bullion_legacy(html):
    """
    ⛔ بنية قديمة (جدول `data-val`) — kept كاحتياط لو الموقع رجع ليها.
       كل سطر: <td> اسم </td> <td class="num" data-val="بيع"> </td> <td class="num td-arrow" data-val="شراء"> </td>
    """
    if not html or "data-val" not in html:
        return None
    out = {"source": "goldbullioneg — صاغة مصرية (مرجع سوق)",
           "source_url": BULLION_URL,
           "source_type": "commercial_market_reference",
           "karats": {}, "rows": [],
           "parse_layout": "table_v1"}
    # كل سطر: <td> اسم </td> <td class="num" data-val="بيع"> </td> <td class="num td-arrow" data-val="شراء"> </td>
    for m in re.finditer(r'<tr>(.*?)</tr>', html, re.S):
        row = m.group(1)
        nums = re.findall(r'<td[^>]*class="num[^"]*"[^>]*data-val="([0-9.,]+)"', row)
        if len(nums) < 2:
            continue
        label = re.sub(r"<[^>]+>", " ", row.split("</td>")[0])
        label = re.sub(r"\s+", " ", label).strip()
        sell = _num(nums[0])
        buy = _num(nums[1])
        if sell is None or buy is None:
            continue
        km = re.search(r"(?:عيار|جرام عيار)\s*(\d+)", label)
        dm = re.search(r"(\d+)\s*ج\b", label)
        if km:
            out["karats"][km.group(1)] = {"buy": buy, "sell": sell, "currency": "ج.م"}
        elif "الدولار" in label:
            out["usd_egp"] = {"buy": buy, "sell": sell}
        elif "أونصة" in label:
            out["ounce_usd"] = {"buy": buy, "sell": sell}
        else:
            out["rows"].append({"label": label[:40], "buy": buy, "sell": sell})
    if not out["karats"]:
        return None
    tm = re.search(r"آخر تحديث[^0-9]{0,20}([0-9]{1,2}:[0-9]{2})", html)
    if tm:
        out["updated_text"] = tm.group(1)
    out["fetched_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    return out


_SECOND_MEM = {"ts": 0, "data": None}


def get_second(force=False):
    """المصدر التاني — لو فشل ⇒ None (مش أرقام مخترعة)."""
    with _LOCK:
        now = time.time()
        if (not force and _SECOND_MEM["data"]
                and (now - _SECOND_MEM["ts"]) < CACHE_TTL):
            return _SECOND_MEM["data"]
        try:
            html = _http_get(BULLION_URL, timeout=20)
        except Exception as e:
            return {"ok": False, "error": str(e)[:100],
                    "fetched_at": datetime.datetime.utcnow().isoformat() + "Z"}
        # 📌 البنية الحالية (بطاقات) الأول · البنية القديمة (جدول) احتياط
        d = _parse_bullion_new(html) or _parse_bullion_legacy(html)
        if not d:
            return {"ok": False, "error": "الصفحة رجعت من غير أسعار مفهومة",
                    "fetched_at": datetime.datetime.utcnow().isoformat() + "Z"}
        d["ok"] = True
        _SECOND_MEM["data"] = d
        _SECOND_MEM["ts"] = now
        return d


def cross_check():
    """
    ⛔ مقارنة بين مصدرين: لو المصدرين موجودين ⇒ بنحسب المدى.
    ⛔ لو واحد ناقص ⇒ بنرجّع الموجود بس (ومفيش استنتاج).
    """
    a = get()
    b = get_second()
    out = {"sources": [], "cross_check": None}
    if a and a.get("ok"):
        out["sources"].append({
            "name": a.get("source"), "url": a.get("source_url"),
            "updated": a.get("updated_text"), "gram_24": a.get("gram_24_reference"),
            "karats": a.get("karats"), "freshness": freshness(a),
        })
    if b and b.get("ok"):
        out["sources"].append({
            "name": b.get("source"), "url": b.get("source_url"),
            "updated": b.get("updated_text"),
            "gram_24": (b.get("karats") or {}).get("24", {}).get("sell"),
            "karats": b.get("karats"), "usd_egp": b.get("usd_egp"),
            "ounce_usd": b.get("ounce_usd"),
        })
    g = [s.get("gram_24") for s in out["sources"] if s.get("gram_24")]
    if len(g) >= 2:
        out["cross_check"] = {
            "gram_24_values": g,
            "spread_egp": round(max(g) - min(g), 2),
            "spread_pct": round((max(g) / min(g) - 1) * 100, 3),
            "note": ("الفرق بين سعر عيار ٢٤ عند الصاغتين — ده نطاق أسعار السوق "
                     "المحلي، مش خطأ في مصدر."),
        }
    else:
        out["cross_check"] = None
        out["cross_check_note"] = ("مصدر واحد بس متاح دلوقتي ⇒ مفيش مقارنة. "
                                   "مفيش استنتاج من مصدر واحد.")
    return out
