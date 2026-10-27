"""
═══════════════════════════════════════════════════════════════
 gold_history.py — سلسلة سعر جرام الذهب بالجنيه المصري (تاريخ طويل)
═══════════════════════════════════════════════════════════════
 📌 الفكرة: «لو ادخرت ذهب من سنة كذا، كام بقى؟» ⇒ لازم سلسلة
    سعر الجرام بالجنيه لسنوات طويلة — مش بس ٢٥٢ شمعة.

 ⛔⛔⛔ قواعد المصدر (مtronogram مخترع):
 ① كل رقم جوّه السلسلة مشتقّ من **مصدرين حقيقيين** فقط:
    · XAUUSD (الذهب بالدولار)  ← TradingView websocket
    · EGPUSD (جنيه لكل دولار)   ← TradingView websocket
 ② الحساب: سعر الأونصة بالجنيه = XAUUSD ÷ EGPUSD
    ⇒ سعر الجرام = (XAUUSD ÷ EGPUSD) ÷ 31.1035
    (الأونصة Troy = 31.1035 جرام — ثابت فيزيائي)
 ③ ⚠️ سلسلة EGPUSD بتبدأ **2009-12-06** ⇒ سلسلة الجرام بتبدأ من
    النهارده تاريخاً، مش من 1990. ده حدّ المصدر — بنقوله صراحة.
 ④ ⛔ ده **سعر مرجعي محسوب** مش سعر البيع في محلات الصياغة:
    · محلات الصياغة بتضيف هامش (صناعة + ربح + دمغة + ضريبة)
    · وسعر الدولار في السوق الموازي مختلف عن الرسمي
    ⇒ لازم الواجهة تقول «سعر مرجعي» وتشرح الفرق.

 📌 التاخد (intersection) بين السلسلتين:
    الذهب بيتداول 5 أيام/الأسبوع،工作组 ),
    وسوق الصرف فيه أيام تانية ⇒ بناخد **التقاطع** (يومexists في الاتنين)
    وبنقول القاعدة صراحة في الـmeta.
═══════════════════════════════════════════════════════════════
"""
import json
import os
import threading
import time
import datetime
from pathlib import Path

# ═══════════ إعدادات ═══════════
TROY_OUNCE_GRAMS = 31.1035          # ثابت فيزيائي: أونصة تروي = 31.1035 جرام
HIST_FILE = Path(os.environ.get("GOLD_HISTORY_PATH", "/app/gold_history.json"))
HIST_TTL = int(os.environ.get("GOLD_HISTORY_TTL", str(6 * 3600)))   # ٦ ساعات
TV_XAU = "FX_IDC:XAUUSD"
TV_EGP = "FX_IDC:EGPUSD"
COUNT_XAU = 9000          # ≈ ٣٦ سنة يومية
COUNT_EGP = 5000          # ≈ ٢٠ سنة يومية

_LOCK = threading.Lock()
_MEM = {"ts": 0, "data": None}


# ═══════════ أدوات ═══════════
def _tv_bars(symbol, count):
    """جلب شموع من TradingView (tv_ws) — مفيش fallback مخترع."""
    import importlib
    tws = importlib.import_module("tv_ws")
    bars = tws.fetch(symbol, count)
    out = []
    for b in (bars or []):
        t = b.get("t")
        c = b.get("c")
        if not t or c is None:
            continue
        try:
            d = datetime.datetime.utcfromtimestamp(float(t)).strftime("%Y-%m-%d")
            out.append((d, float(c)))
        except Exception:
            continue
    out.sort()
    # إزالة التكرار (آخر قيمة لليوم نفسه)
    dedup = {}
    for d, c in out:
        dedup[d] = c
    return sorted(dedup.items())


def _read_file():
    try:
        if HIST_FILE.exists():
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _write_file(data):
    """⛔ مش كل بيئة فيها /app (الساندوكس Sandbox مش فيها) ⇒ نجرّب مسارات."""
    for path in (HIST_FILE, Path("/tmp/gold_history.json")):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(str(tmp), str(p))
            return True
        except Exception as e:
            last = str(e)[:100]
    print("[goldhist] تعذر حفظ الملف:", last)
    return False


# ═══════════ البناء ═══════════
def build(force=False):
    """
    ⛔ مفيش رقم مخترع: لو المصدر رجع فاضي ⇒ نرجّع None وسبب مكتوب.
    """
    with _LOCK:
        now = time.time()
        if (not force and _MEM["data"] and (now - _MEM["ts"]) < HIST_TTL):
            return _MEM["data"]
        disk = _read_file()
        if (disk and disk.get("schema") != 2):
            disk = None   # ⛔ كاش نسخة قديمة ⇒ نعيد البناء
        if (not force and disk and disk.get("built_at")
                and (now - float(disk.get("built_at", 0))) < HIST_TTL):
            _MEM["data"] = disk
            _MEM["ts"] = now
            return disk

        try:
            xau = _tv_bars(TV_XAU, COUNT_XAU)
        except Exception as e:
            return {"ok": False, "error": "فشل جلب الذهب: " + str(e)[:120],
                    "built_at": now, "series": []}
        try:
            egp = _tv_bars(TV_EGP, COUNT_EGP)
        except Exception as e:
            return {"ok": False, "error": "فشل جلب سعر الدولار: " + str(e)[:120],
                    "built_at": now, "series": []}
        if not xau:
            return {"ok": False, "error": "مفيش شموع ذهب من المصدر", "built_at": now, "series": []}
        if not egp:
            return {"ok": False, "error": "مفيش شموع دولار من المصدر", "built_at": now, "series": []}

        egp_map = dict(egp)
        series = []
        skipped = 0
        for d, x in xau:
            e = egp_map.get(d)
            if e is None or not e:
                skipped += 1
                continue
            # ⛔⛔⛔ ٢٧ أكتوبر ٢٠٢٦ — تصحيح تسمية (اكتشفه فحص الـlog)
            #   المصدر TradingView: FX_IDC:EGPUSD = **دولار لكل جنيه** (0.0174)
            #   يعني 1 دولار = 1/0.0174 = 57.47 جنيه.
            #   ⇒ سعر الأونصة بالجنيه = xau × (1 / usd_per_egp)
            #   ⚠️ قبل التصحيح كان الحقل اسمه «egp» وده معكوس ⇒ في حساب
            #      الـlog return الإشارة بتتقلب ⇒ إسناد فاسد («الذهب −58%»).
            egp_per_usd = 1.0 / e            # جنيه لكل دولار
            ounce_egp = x * egp_per_usd
            gram = ounce_egp / TROY_OUNCE_GRAMS
            series.append({
                "d": d,
                "xau": round(x, 4),
                "usd_per_egp": round(e, 8),   # دولار لكل جنيه (كما ورد من المصدر)
                "egp_per_usd": round(egp_per_usd, 4),  # جنيه لكل دولار (المستخدم في الحساب)
                "ounce_egp": round(ounce_egp, 2),
                "gram": round(gram, 2),
            })

        if not series:
            return {"ok": False, "error": "مفيش تقاطع بين سلسلتي الذهب والدولار",
                    "built_at": now, "series": []}

        data = {
            "ok": True,
            "schema": 2,          # ⛔ لو الحقول اتغيّرت ⇒ الكاش القديم يتبطل
            "built_at": now,
            "built_iso": datetime.datetime.utcnow().isoformat() + "Z",
            "count": len(series),
            "from": series[0]["d"],
            "to": series[-1]["d"],
            "skipped_no_fx": skipped,
            "sources": {
                "gold": {"provider": "TradingView", "symbol": TV_XAU, "points": len(xau),
                         "from": xau[0][0], "to": xau[-1][0]},
                "fx": {"provider": "TradingView", "symbol": TV_EGP, "points": len(egp),
                       "from": egp[0][0], "to": egp[-1][0]},
            },
            "method": {
                "formula": "gram_egp = (XAUUSD x EGP_per_USD) / 31.1035  |  EGP_per_USD = 1 / USD_per_EGP",
                "troy_ounce_grams": TROY_OUNCE_GRAMS,
                "alignment": "تقاطع يومي بين السلسلتين (يوم موجود في الاتنين)",
                "caveats": [
                    "سعر مرجعي محسوب — مش سعر البيع في محلات الصياغة (فيه هامش صناعة ودمغة وربح).",
                    "سعر الدولار هو السعر الرسمي المعروض — السوق الموازي مختلف.",
                    "سلسلة الجنيه تبدأ 2009-12-06 ⇒ كل ما قبل كده غير متاح في الجنيه.",
                ],
            },
            "series": series,
        }
        _MEM["data"] = data
        _MEM["ts"] = now
        _write_file(data)
        print(f"[goldhist] ✅ {len(series)} نقطة · {data['from']} → {data['to']} "
              f"(اتخطّى {skipped} يوم lacking سعر دولار)")
        return data


# ═══════════ مشتقّات ═══════════
def stats(data=None):
    """ملخص السلسلة — كل رقم مشتقّ من السلسلة نفسها."""
    d = data or build()
    if not d or not d.get("ok"):
        return {"ok": False, "error": (d or {}).get("error", "لا توجد سلسلة")}
    s = d["series"]
    first, last = s[0], s[-1]
    hi = max(s, key=lambda r: r["gram"])
    lo = min(s, key=lambda r: r["gram"])
    # أقوى وأضعف سنة (على أساس آخر قيمة كل سنة)
    by_year = {}
    for r in s:
        by_year[r["d"][:4]] = r
    years = []
    prev = None
    for y in sorted(by_year):
        r = by_year[y]
        ret = ((r["gram"] / prev["gram"]) - 1) * 100 if prev else None
        years.append({"year": y, "end_gram": r["gram"], "ret_pct": round(ret, 2) if ret is not None else None})
        prev = r
    return {
        "ok": True,
        "from": first["d"], "to": last["d"], "count": d["count"],
        "first_gram": first["gram"], "last_gram": last["gram"],
        "total_return_pct": round(((last["gram"] / first["gram"]) - 1) * 100, 2) if first["gram"] else None,
        "times": round(last["gram"] / first["gram"], 2) if first["gram"] else None,
        "all_time_high": {"gram": hi["gram"], "date": hi["d"]},
        "all_time_low": {"gram": lo["gram"], "date": lo["d"]},
        "from_high_pct": round(((last["gram"] / hi["gram"]) - 1) * 100, 2) if hi["gram"] else None,
        "years": years,
        "sources": d.get("sources"), "method": d.get("method"),
    }


def value_on(date_str, data=None):
    """سعر الجرام في تاريخ محدد (أقرب يوم سابق — markets closed)."""
    d = data or build()
    if not d or not d.get("ok"):
        return None
    s = d["series"]
    pick = None
    for r in s:
        if r["d"] <= date_str:
            pick = r
        else:
            break
    return pick


if __name__ == "__main__":
    d = build(force=True)
    print("ok:", d.get("ok"), "| count:", d.get("count"), "|", d.get("from"), "→", d.get("to"))
    st = stats(d)
    if st.get("ok"):
        print("أول جرام:", st["first_gram"], "| آخر جرام:", st["last_gram"],
              "| الضاعف:", st["times"], "| القمة:", st["all_time_high"])
