import threading
"""
📅 Dividend & Corporate Actions Fetcher
مصدر البيانات: foudalens.com/corporate-actions (مبني على إعلانات EGX الرسمية)
يتحدث مرة كل 6 ساعات
"""

import json, re, time, requests
from datetime import datetime, timezone

SOURCE_URL = "https://foudalens.com/en/corporate-actions"
CACHE = {
    "actions": [],
    "lastUpdate": None,
    "source": "foudalens.com (EGX disclosures)",
    "stats": {}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept": "text/html,application/xhtml+xml",
}

# نوع الحدث → التسمية بالعربي
KIND_AR = {
    "cash_dividend": "نقدي",
    "stock_dividend": "أسهم",
    "stock_split": "تقسيم",
    "rights_issue": "زيادة رأس مال",
    "capital_increase": "زيادة رأس مال",
}


def _decode_nextjs_chunks(html: str) -> str:
    """Next.js بيخزّن الداتا في __next_f.push chunks — نفكّها"""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    if not chunks:
        return ""
    blob = "".join(chunks)
    try:
        blob = blob.encode().decode("unicode_escape")
    except Exception:
        pass
    return blob


def _parse_headline(hl: dict) -> dict:
    """headline عندنا شكلين: cash (مبلغ) أو ratio (نسبة أسهم)"""
    if not hl:
        return {"mode": "unknown", "value": None, "currency": None, "ratio": None}
    if hl.get("type") == "cash":
        return {
            "mode": "cash",
            "value": hl.get("amount"),
            "currency": hl.get("currency") or "EGP",
            "ratio": None,
        }
    if hl.get("type") == "ratio":
        new_s = hl.get("newShares")
        per_s = hl.get("perShares")
        # النسبة المئوية = newShares / perShares × 100
        pct = None
        try:
            if new_s is not None and per_s:
                pct = round((float(new_s) / float(per_s)) * 100, 4)
        except Exception:
            pct = None
        return {
            "mode": "stock",
            "value": new_s,
            "currency": None,
            "ratio": {"newShares": new_s, "perShares": per_s, "pct": pct},
        }
    return {"mode": "unknown", "value": None, "currency": None, "ratio": None}


def fetch_corporate_actions(retries: int = 3) -> list:
    """يجيب كل الأحداث من الصفحة — مع retry لو الموقع رجّع 503"""
    last_err = ""
    for attempt in range(retries):
        try:
            r = requests.get(SOURCE_URL, headers=HEADERS, timeout=25)
            r.raise_for_status()
            blob = _decode_nextjs_chunks(r.text)
            if '"corporate_action:' not in blob:
                last_err = "no corporate_action records in payload"
                time.sleep(4 * (attempt + 1))
                continue
            return _parse_actions(blob)
        except Exception as e:
            last_err = str(e)[:150]
            print(f"[DIV] fetch attempt {attempt+1}/{retries} failed: {last_err}")
            time.sleep(4 * (attempt + 1))
    print(f"[DIV] all retries failed: {last_err}")
    return CACHE.get("actions", [])  # نرجّع الكاش القديمة بدل ما نخسر البيانات


def _parse_actions(blob: str) -> list:
    # نمط كل record
    pattern = re.compile(
        r'\{"id":"corporate_action:[^"]+",'
        r'"source":"corporate_action",'
        r'"kind":"(\w+)",'
        r'"date":"([\d-]+)",'
        r'"dateKind":"(\w+)",'
        r'"symbol":"([A-Z0-9.]+)",'
        r'"nameAr":(null|"[^"]*"),'
        r'"nameEn":(null|"[^"]*"),'
        r'"headline":(\{.*?\}),'
        r'"context":(\{.*?\}),'
        r'"href":"[^"]*"\}',
        re.S,
    )

    out = []
    seen = set()
    for m in pattern.finditer(blob):
        kind, date, date_kind, symbol, name_ar, name_en, headline, context = m.groups()

        key = f"{symbol}|{kind}|{date}"
        if key in seen:
            continue
        seen.add(key)

        try:
            hl = json.loads(headline)
        except Exception:
            hl = {}
        try:
            ctx = json.loads(context)
        except Exception:
            ctx = {}

        parsed_hl = _parse_headline(hl)

        code = symbol.replace(".CA", "")
        action = {
            "id": f"{code}|{kind}|{date}",
            "code": code,
            "kind": kind,
            "kindAr": KIND_AR.get(kind, kind),
            "date": date,
            "dateKind": date_kind,
            "nameAr": None if name_ar == "null" else name_ar.strip('"'),
            "nameEn": None if name_en == "null" else name_en.strip('"'),
            "mode": parsed_hl["mode"],       # cash | stock
            "value": parsed_hl["value"],
            "currency": parsed_hl["currency"],
            "ratio": parsed_hl["ratio"],
            "recordDate": ctx.get("recordDate"),
            "distributionDate": ctx.get("distributionDate") or date,
            "couponNumber": ctx.get("couponNumber"),
            "installments": ctx.get("installments"),
            "subscriptionPrice": ctx.get("subscriptionPrice"),
        }
        out.append(action)

    # ترتيب: الأجدد أولاً
    out.sort(key=lambda a: a["date"], reverse=True)
    return out


def _status_of(a: dict) -> str:
    """حالة الحدث: upcoming / recent / past"""
    today = datetime.now(timezone.utc).date().isoformat()
    if a["date"] >= today:
        return "upcoming"
    # خلال 30 يوم فات = recent
    from datetime import date as _d, timedelta
    d = _d.fromisoformat(a["date"])
    delta = (_d.today() - d).days
    return "recent" if delta <= 30 else "past"


def _calc_yield(a: dict, prices: dict) -> float:
    """
    ⚠️ نحسب بشكل صحيح:
    - Cash فقط → value / last_price × 100  (اسمها "Distribution / Close")
    - Stock      → نسبة الأسهم نفسها (مش yield نقدي)

    🛡️ Guard: لو النسبة > 100% يبقى السعر غلط أو التوزيع مركّب على أقساط
    → نرجّع None بدل ما نعرض رقم مضلّل
    """
    if a["mode"] != "cash" or not a.get("value"):
        return None
    price = (prices or {}).get(a["code"])
    if not price or price <= 0:
        return None
    try:
        y = (float(a["value"]) / float(price)) * 100
        # التوزيعNAT Sobre سعر السهم نادراً ما بيكون > 50% في السوق المصري
        if y > 60:
            return None
        return round(y, 2)
    except Exception:
        return None


def build_snapshot(prices: dict) -> dict:
    """يبني اللقطة النهائية مع الحسابات والإحصائيات"""
    actions = CACHE["actions"]
    enriched = []
    for a in actions:
        a = dict(a)
        a["yieldPct"] = _calc_yield(a, prices)
        a["status"] = _status_of(a)
        enriched.append(a)

    upcoming = [a for a in enriched if a["status"] == "upcoming"]
    cash_up = [a for a in upcoming if a["mode"] == "cash"]
    stock_up = [a for a in upcoming if a["mode"] == "stock"]

    yields = [a["yieldPct"] for a in cash_up if a["yieldPct"] is not None]
    total_cash = sum(float(a["value"]) for a in cash_up if a.get("value"))

    today = datetime.now(timezone.utc).date()
    in_7 = (today.fromordinal(today.toordinal() + 7)).isoformat()
    in_30 = (today.fromordinal(today.toordinal() + 30)).isoformat()

    # أقرب توزيع
    soon = sorted(upcoming, key=lambda a: a["date"])
    next_up = soon[0] if soon else None

    # أعلى yield
    with_yield = sorted(
        [a for a in cash_up if a["yieldPct"] is not None],
        key=lambda a: a["yieldPct"], reverse=True
    )
    top_yield = with_yield[0] if with_yield else None

    # تقييم الأقرب
    buckets = {"d3": 0, "d7": 0, "d30": 0}
    for a in upcoming:
        if a["date"] <= in_7: buckets["d7"] += 1
        if a["date"] <= in_30: buckets["d30"] += 1
        d3 = (today.fromordinal(today.toordinal() + 3)).isoformat()
        if a["date"] <= d3: buckets["d3"] += 1

    stats = {
        "total": len(enriched),
        "upcomingCount": len(upcoming),
        "pastCount": len(enriched) - len(upcoming),
        "cashCount": len(cash_up),
        "stockCount": len(stock_up),
        "totalCashEGP": round(total_cash, 4),
        "avgYield": round(sum(yields) / len(yields), 2) if yields else None,
        "nextUpcoming": next_up,
        "topYield": top_yield,
        "in3Days": buckets["d3"],
        "in7Days": buckets["d7"],
        "in30Days": buckets["d30"],
        "cashSharePct": round((len(cash_up) / len(upcoming) * 100), 1) if upcoming else 0,
    }

    return {
        "actions": enriched,
        "stats": stats,
        "lastUpdate": CACHE["lastUpdate"],
        "source": CACHE["source"],
        "updatedAt": datetime.now(timezone.utc).isoformat() + "Z",
    }


def start_dividend_loop(prices_provider, interval=6 * 3600):
    """background thread: يجيب البيانات كل 6 ساعات"""
    def loop():
        while True:
            try:
                acts = fetch_corporate_actions()
                CACHE["actions"] = acts
                CACHE["lastUpdate"] = datetime.now(timezone.utc).isoformat() + "Z"
                print(f"[DIV] fetched {len(acts)} corporate actions")
            except Exception as e:
                print(f"[DIV] fetch error: {e}")
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
