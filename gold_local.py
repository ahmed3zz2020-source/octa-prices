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
 ③ **لازم نوثّق وقت آخر تحديث** من `<time datetime="...">` بتاع المصدر
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
    البنية: <li data-unit="24" ...> ... شراء <span data-testid="price-figure">7240</span> ...
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
    # كل بلوك: <li ... data-unit="NN" ...> ... </li>
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
    gm = re.search(r'<bdi[^>]*current\.growth[^>]*>([^<]*)</bdi>', html)
    if gm:
        v = _num(str(gm.group(1)).replace("%", "").replace("٪", ""))
        if v is not None:
            out["growth_pct"] = v
            out["growth_period"] = "السنة الماضية"   # الـchart الافتراضي
    g5 = re.search(r'معدل النمو خلال آخر خمس سنوات\s*:\s*([0-9.]+)\s*%', html)
    if g5:
        out["growth_5y_pct"] = _num(g5.group(1))

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
        print("   грамات:", gram_prices(d))
        print("   الطزاجة:", freshness(d))


# ════════════════════════════════════════════════════════════════
# 🔎 مصدر تاني للمرصود — goldbullioneg (صاغة تانية) للمقارنة
# ════════════════════════════════════════════════════════════════
# 📌 ليش مهم: البرومبت بيقول «Cross-check local quotations when possible».
#    مصدرين مستقلين بيقولوا الفرق = نطاق أسعار الصاغة (مش رقم واحد).
# ⛔ ملاحظة: عمود السعر الأول = **بيع** · التاني (td-arrow) = **شراء**
#    (اتأكدنا من صف الدولار: 56.35 بيع / 56.25 شراء).
BULLION_URL = "https://goldbullioneg.com/"


def _parse_bullion(html):
    if not html or "data-val" not in html:
        return None
    out = {"source": "goldbullioneg — صاغة مصرية (مرجع سوق)",
           "source_url": BULLION_URL,
           "source_type": "commercial_market_reference",
           "karats": {}, "rows": []}
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


def get_second():
    """المصدر التاني — لو فشل ⇒ None (مش أرقام مخترعة)."""
    try:
        html = _http_get(BULLION_URL, timeout=20)
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
    d = _parse_bullion(html)
    if not d:
        return {"ok": False, "error": "الصفحة رجعت من غير أسعار مفهومة"}
    d["ok"] = True
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
