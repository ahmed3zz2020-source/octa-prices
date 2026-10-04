"""
📋 أسماء الأسهم العربية — 271 سهم
مصدر البيانات: foudalens.com/ar/stocks (مصفحة stocks) + تصحيحات المستخدم
⚠️ لو الكود مش موجود هنا = نرجع للكود بدل ما نخمّن اسم غلط
"""

import json, os

_FALLBACK_URL = "https://ewo9h40jkd9co.space.minimax.io/data/egx-stocks.json"
_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "egx_names.json")

NAMES = {}
SECTORS = {}

def _load():
    global NAMES, SECTORS
    # 1) من الملف المحلي
    for p in (_LOCAL, "/app/egx_names.json"):
        try:
            if os.path.exists(p):
                d = json.load(open(p, encoding="utf-8"))
                if isinstance(d, dict):
                    NAMES = d.get("names", d)
                    SECTORS = d.get("sectors", {})
                    return
        except Exception:
            pass
    # 2) من الموقع
    try:
        import requests
        r = requests.get(_FALBACK_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok:
            for s in r.json().get("stocks", []):
                NAMES[s["c"]] = s["n"]
                SECTORS[s["c"]] = s.get("s", "")
    except Exception:
        pass

_load()


def name_of(code):
    """اسم السهم بالعربي، أو None لو مش معروف"""
    return NAMES.get(code)


def sector_of(code):
    return SECTORS.get(code, "")
