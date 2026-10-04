"""
🖼️ لوجوهات الأسهم — من TradingView
التدفق: السيرفر يجيب اللوجو → يحفظه في /app/logos/ → الموقع بيقرأه من السيرفر
(لأن s3.tradingview.com بيمنع المتصفح مباشرة — CORS 403)
"""

import json, os, requests
from datetime import datetime, timezone

LOGOS_DIR = "/app/logos" if os.path.isdir("/app") else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logos"
)
os.makedirs(LOGOS_DIR, exist_ok=True)

# أسماء لوجوهات TradingView المعروفة (logoid من الـ scanner)
TV_LOGO_HOST = "https://s3.tradingview.com/logos/logos/{}.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}

CACHE = {}


def scan_logoids(tickers):
    """يجيب logoid لكل سهم من TradingView scanner"""
    try:
        body = json.dumps({
            "symbols": {"tickers": list(tickers), "query": {"types": []}},
            "columns": ["close", "name", "description", "logo"]
        }).encode()
        r = requests.post(
            "https://scanner.tradingview.com/global/scan",
            data=body,
            headers={"Content-Type": "application/json", **HEADERS},
            timeout=30
        )
        r.raise_for_status()
        out = {}
        for row in r.json().get("data", []):
            code = row["s"].split(":")[-1]
            d = row.get("d") or []
            logo = d[3] if len(d) > 3 else None
            if isinstance(logo, dict) and logo.get("logoid"):
                out[code] = logo["logoid"]
        return out
    except Exception as e:
        print(f"[LOGOS] scan error: {e}")
        return {}


def fetch_logo(code, logoid):
    """يجيب اللوجو ويحفظه — يرجع اسم الملف"""
    if not logoid:
        return None
    if code in CACHE:
        return CACHE[code]

    fn = os.path.join(LOGOS_DIR, f"{code}.png")
    if os.path.exists(fn) and os.path.getsize(fn) > 100:
        CACHE[code] = f"{code}.png"
        return CACHE[code]

    try:
        r = requests.get(TV_LOGO_HOST.format(logoid), headers=HEADERS, timeout=15)
        if r.status_code == 200 and len(r.content) > 100:
            with open(fn, "wb") as f:
                f.write(r.content)
            CACHE[code] = f"{code}.png"
            return CACHE[code]
    except Exception:
        pass
    return None


def refresh_logos(tickers):
    """يجيب كل اللوجوهات — مرة واحدة"""
    ids = scan_logoids(tickers)
    ok = 0
    for code, logoid in ids.items():
        if fetch_logo(code, logoid):
            ok += 1
    print(f"[LOGOS] {ok}/{len(ids)} logo cached")
    return {"count": ok, "total": len(ids)}


def logos_payload():
    """قائمة اللوجوهات المتاحة"""
    try:
        files = [f for f in os.listdir(LOGOS_DIR) if f.endswith(".png")]
        return sorted(files)
    except Exception:
        return []


def start_logo_loop(tickers, interval=24 * 3600):
    """background thread — يحدّث اللوجوهات مرة في اليوم"""
    import threading, time

    def loop():
        while True:
            try:
                refresh_logos(tickers)
            except Exception as e:
                print(f"[LOGOS] loop error: {e}")
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
