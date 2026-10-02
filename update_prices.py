import json, time, requests, os, threading
from flask import Flask, jsonify
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

CACHE_FILE = Path("/app/cache.json")
LIVE_DATA = {
    "lastUpdate": None, "market": "EGX", "status": "open",
    "ticker": [], "egx30": []
}

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
        r = requests.get(f"https://www.tradingview-widget.com/api/v1/quote?symbol={sym}", timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            v = r.json().get("v")
            if v and v.get("lp"):
                return float(v["lp"]), float(v.get("ch", 0))
    except Exception as e:
        print(f"TV err {sym}: {e}")
    return None

def get(sym):
    p = tv(sym)
    return p if p else (0.0, 0.0)

def update_loop():
    while True:
        try:
            print("OCTA Update:", datetime.utcnow().isoformat())
            tk = []
            for tid, label, sym in TICKER:
                p, c = get(sym)
                tk.append({"id":tid,"label":label,"value":round(p,2),"change":round(c,2),"trend":"up" if c>=0 else "down","unit":"EGP" if "EGP" in tid else ""})
                print(f"  {label}: {p} ({c:+.2f}%)")
                time.sleep(0.4)
            st = []
            for code, name, sec in EGX:
                p, c = get(f"EGX:{code}")
                if p > 0:
                    st.append({"code":code,"name":name,"price":round(p,2),"change":round(c,2),"sector":sec})
                    print(f"  {code}: {p} ({c:+.2f}%)")
                time.sleep(0.4)
            LIVE_DATA["lastUpdate"] = datetime.utcnow().isoformat() + "Z"
            LIVE_DATA["ticker"] = tk
            LIVE_DATA["egx30"] = st
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(LIVE_DATA, f, ensure_ascii=False, indent=2)
            except: pass
            print(f"SAVED: {len(tk)} tickers, {len(st)} stocks")
        except Exception as e:
            print(f"Loop err: {e}")
        time.sleep(300)

threading.Thread(target=update_loop, daemon=True).start()

@app.route("/")
def health():
    return jsonify({"status":"ok","service":"octa-prices","version":"v2","lastUpdate":LIVE_DATA["lastUpdate"],"tickers":len(LIVE_DATA["ticker"]),"stocks":len(LIVE_DATA["egx30"])})

@app.route("/api/prices")
def prices():
    return jsonify(LIVE_DATA)

@app.route("/api/ticker")
def ticker():
    return jsonify({"ticker": LIVE_DATA["ticker"]})

@app.route("/api/stocks")
def stocks():
    return jsonify({"egx30": LIVE_DATA["egx30"]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting OCTA on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
