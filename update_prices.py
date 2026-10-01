import json, time, requests, os
from pathlib import Path
from datetime import datetime

OUTPUT = Path("/app/assets/stocks-prices.json") if os.path.exists("/app") else Path(__file__).parent / "assets" / "stocks-prices.json"

EGX = [
    ("COMI","البنك التجاري الدولي","بنوك"),("TMGH","طلعت مصطفى","عقارات"),
    ("HRHO","إي إف جي القابضة","خدمات مالية"),("ETEL","المصرية للاتصالات","اتصالات"),
    ("EFIH","إي فاينانس","تكنولوجيا"),("FWRY","فوري","تكنولوجيا"),
    ("PHDC","بالم هيلز","عقارات"),("SWDY","السويدي إليكتريك","صناعة"),
    ("ABUK","أبو قير للأسمدة","أسمدة"),("AMOC","الإسكندرية للبترول","بترول"),
    ("ORAS","أوراسكوم","استثمار"),("CCAP","القلعة القابضة","استثمار"),
    ("CLHO","مستشفى كليوباترا","صحة"),("JUFO","جهينة","أغذية"),
    ("ISPH","إيبيكو للأدوية","أدوية"),("EMFD","إعمار مصر","عقارات"),
    ("MNHD","مصر الجديدة","عقارات"),("SKPC","سيدي كرير","بتروكيماويات"),
    ("EGCH","مصر للكيماويات","بتروكيماويات"),("MFPC","مصر لإنتاج الأسمدة","أسمدة"),
    ("OCDI","الإسكندرية للحاويات","نقل"),("EKHO","EK القابضة","صناعة"),
]

TICKER = [
    ("tk-egx","EGX30","EGX:EGX30"),("tk-gold","GOLD","OANDA:XAUUSD"),
    ("tk-oil","USOIL","TVC:USOIL"),("tk-ukoil","UKOIL","TVC:UKOIL"),
    ("tk-usd","USD/EGP","EGP=X"),("tk-eur","EUR/EGP","EUR=X"),
    ("tk-spx","S&P 500","SP:SPX"),("tk-silver","SILVER","OANDA:XAGUSD"),
]

def tv(sym):
    try:
        r = requests.get(f"https://www.tradingview-widget.com/api/v1/quote?symbol={sym}", timeout=8)
        if r.status_code == 200:
            v = r.json().get("v")
            if v: return float(v.get("lp",0)), float(v.get("ch",0))
    except: pass
    return None

def yh(sym):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}",
                         timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            res = r.json().get("quoteResponse",{}).get("result",[])
            if res:
                q = res[0]
                return float(q.get("regularMarketPrice",0)), float(q.get("regularMarketChangePercent",0))
    except: pass
    return None

def get(sym):
    p = tv(sym) or yh(sym)
    return p if p else (0.0, 0.0)

while True:
    print("="*40)
    print("OCTA Update:", datetime.utcnow())
    print("="*40)
    tk = []
    for tid, label, sym in TICKER:
        p, c = get(sym)
        tk.append({"id":tid,"label":label,"value":round(p,2),"change":round(c,2),
                   "trend":"up" if c>=0 else "down",
                   "unit":"EGP" if "EGP" in tid else ""})
        print(f"  {label}: {p} ({c:+.2f}%)")
        time.sleep(0.4)
    st = []
    for code, name, sec in EGX:
        p, c = get(f"EGX:{code}")
        if p > 0:
            st.append({"code":code,"name":name,"price":round(p,2),"change":round(c,2),"sector":sec})
            print(f"  {code}: {p} ({c:+.2f}%)")
        time.sleep(0.4)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT,"w",encoding="utf-8") as f:
        json.dump({"lastUpdate":datetime.utcnow().isoformat()+"Z","market":"EGX",
                   "status":"open","ticker":tk,"egx30":st}, f, ensure_ascii=False, indent=2)
    print("SAVED:", OUTPUT)
    time.sleep(300)
