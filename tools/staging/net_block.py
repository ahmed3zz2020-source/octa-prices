#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚧 حجب الشبكة + مصدر اصطناعي — الجولة ٢٥ (R25 · المرحلة ٩)

📌 ليه الأداة دي ⭐:
   بيئة الاختبار لازم **ما تتصلش** بأي مصدر خارجي ⭐
   (مافيش شبكة ⭐ · مافيش أي مورد مدفوع ⭐) ⭐.
   ⭐ والأداة دي بتشتغل مع **نسختين** من البيئة ⭐:
   · `requests` حقيقي ⭐ (بيئة الإنتاج/CI ⭐) ⭐
   · بديل مصغّر ⭐ (بيئة مافيش فيها شبكة ⭐) ⭐

📌 البنية ⭐:
   · `install()` ⭐ بيقفل كل النداءات الخارجية ⭐ (رمي استثناء ⭐).
   · `set_mode()` ⭐ بيحوّل المصدر لوضع معيّن ⭐:
     `blocked` · `timeout` · `http_500` · `garbage` · `ok` ⭐.
   · `ok` ⭐ بيرجّع **بيانات سوق اصطناعية** ⭐ (محسوبة ⭐ مش حقيقية ⭐)
     عشان التطبيق يعالج المسار الحقيقي ⭐ (مسح ⇒ تقييم ⇒ فرص ⭐).

⛔ مافيش أي سر إنتاج ⭐ · مافيش أي طلب لبرودكشن ⭐
"""
import json
import sys
import time

__all__ = ["install", "set_mode", "current_mode", "source_handler",
           "FakeResponse", "IPO_HTML", "synthetic_scan_response",
           "NetworkBlocked"]


class NetworkBlocked(RuntimeError):
    """محاولة اتصال خارجي والاختبار معزول ⭐."""


class FakeResponse:
    """رد وهمي ⭐ — عشان نحاكي سلوك مصدر خارجي ⭐ (بلا أي شبكة ⭐)."""

    def __init__(self, text="", status_code=200, json_data=None):
        self.text = text
        self.status_code = int(status_code)
        self._json = json_data
        self.content = text.encode("utf-8") if isinstance(text, str) else text
        self.headers = {"Content-Type": "application/json"}

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        if self._json is not None:
            return self._json
        return json.loads(self.text)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("HTTP %s" % self.status_code)
        return self

    def __repr__(self):
        return "<FakeResponse %s>" % self.status_code


# ⛔ نموذج HTML اصطناعي لصفحة الاكتتاب ⭐ (مش بيانات حقيقية ⭐)
IPO_HTML = (
    "<html><body><div class='ipo'>"
    "<h3>شركة الاختبار المعزولة</h3><span>قادم</span>"
    "<p>سعر الطرح</p><p>10.50 جنيه</p>"
    "<p>قيمة الطرح</p><p>100 مليون جنيه</p>"
    "<p>وصف طويل للتشغيل في بيئة الاختبار المعزولة فقط "
    "وكل الأرقام فيه اصطناعية ومكتوبة للاختبار.</p>"
    "</div><a href=\"/ar/stock/TSTX.CA\">تفاصيل</a></body></html>"
)

# ⛔ مولّد بيانات السوق الاصطناعية ⭐
# 📌 مفيش أي رقم حقيقي ⭐ — كل الأرقام **محسوبة** من ترتيب الصف ⭐
# 📌 والهدف إن التطبيق يعالج **مسار البيانات الحقيقي** ⭐ في بيئة معزولة ⭐.
def _synthetic_value(col, base, idx):
    """قيمة اصطناعية معقولة لعمود معيّن ⭐."""
    i = idx
    if col == "close":
        return round(base, 2)
    if col == "change":
        return round(((i % 17) - 8) * 0.83, 2)
    if col == "change_abs":
        return round(base * (((i % 17) - 8) * 0.83) / 100.0, 3)
    if col == "volume":
        return 250000 + (i % 900) * 3700
    if col == "Volatility.D":
        return round(12.0 + (i % 21) * 1.7, 2)
    if col == "relative_volume_10d_calc":
        return round(0.55 + (i % 13) * 0.16, 3)
    if col == "Recommend.All":
        return round(((i % 5) - 2) * 0.4, 2)
    if col == "Recommend.MA":
        return round(((i % 5) - 2) * 0.35, 2)
    if col == "Recommend.Other":
        return round(((i % 5) - 2) * 0.3, 2)
    if col == "beta_1_year":
        return round(0.55 + (i % 9) * 0.18, 3)
    if col == "dividends_yield_current":
        return round((i % 7) * 1.15, 2)
    if col == "market_cap_basic":
        return 1500000000 + (i % 500) * 9100000
    if col == "price_earnings_ttm":
        return round(6.0 + (i % 22), 2)
    if col == "price_book_fq":
        return round(0.75 + (i % 11) * 0.22, 3)
    if col == "return_on_equity":
        return round((i % 34) - 4.0, 2)
    if col == "debt_to_equity":
        return round((i % 46) * 1.1, 2)
    if col == "net_margin":
        return round((i % 29) - 3.0, 2)
    if col == "operating_margin":
        return round((i % 21) - 2.0, 2)
    if col == "earnings_per_share_diluted_ttm":
        return round(base * 0.045, 3)
    if col == "total_revenue":
        return 120000000 + (i % 400) * 1300000
    if col == "price_target_median":
        return round(base * 1.12, 2)
    if col == "price_target_low":
        return round(base * 0.88, 2)
    if col == "price_target_high":
        return round(base * 1.31, 2)
    if col.startswith("Perf."):
        return round(((i % 23) - 11) * 1.7, 2)
    if col in ("EMA10", "EMA20", "EMA50", "EMA200", "SMA20", "SMA50",
               "SMA200", "SMA30|1W", "HullMA9", "Ichimoku.BLine", "P.SAR",
               "BB.upper", "BB.lower", "BB.basis", "VWMA"):
        return round(base * (0.94 + (i % 9) * 0.015), 3)
    if col in ("RSI", "RSI[1]"):
        return round(28.0 + (i % 45), 2)
    if col in ("MACD.macd", "MACD.signal"):
        return round(((i % 21) - 10) * 0.35, 4)
    if col in ("Stoch.K", "Stoch.D"):
        return round(12.0 + (i % 76), 2)
    if col == "CCI20":
        return round(((i % 241) - 120), 2)
    if col in ("ADX", "ADX+DI", "ADX-DI"):
        return round(8.0 + (i % 33), 2)
    if col == "Mom":
        return round(((i % 19) - 9) * 0.8, 3)
    if col == "AO":
        return round(((i % 15) - 7) * 0.6, 4)
    if col == "UO":
        return round(18.0 + (i % 62), 2)
    if col == "W.R":
        return round(-(5.0 + (i % 88)), 2)
    if col == "ATR":
        return round(base * 0.035, 4)
    if col == "BBPower":
        return round(((i % 17) - 8) * 0.9, 4)
    if col.startswith("Pivot.M.Classic"):
        return round(base * (1.0 + ((i % 7) - 3) * 0.012), 3)
    if col.startswith("High."):
        return round(base * 1.18, 3)
    if col.startswith("Low."):
        return round(base * 0.82, 3)
    if col.startswith("volume|"):
        return 200000 + (i % 700) * 2900
    return None


def synthetic_scan_response(payload):
    """بيرجّع رد مسح اصطناعي ⭐ بنفس شكل الـTradingView ⭐."""
    payload = payload or {}
    cols = list(payload.get("columns") or [])
    tickers = list(((payload.get("symbols") or {}).get("tickers")) or [])
    rows = []
    for idx, tk in enumerate(tickers):
        base = 12.0 + (idx % 89) * 4.75
        d = [_synthetic_value(c, base, idx) for c in cols]
        rows.append({"s": str(tk), "d": d})
    return {"data": rows}


def source_handler(mode, delay=0.0):
    """بيرجّع يد وهمية للمصدر ⭐ — بأنماط أعطال متدرجة ⭐."""
    def handler(method, url, **kw):
        if delay:
            time.sleep(float(delay))
        low = str(url or "").lower()
        if mode == "timeout":
            raise TimeoutError("source timeout (synthetic)")
        if mode == "http_500":
            return FakeResponse("upstream error", status_code=500)
        if mode == "garbage":
            return FakeResponse("<html>garbage payload</html>", status_code=200)
        if mode == "ok":
            body = kw.get("json")
            if isinstance(body, dict) and body.get("symbols") \
                    and body.get("columns"):
                data = synthetic_scan_response(body)
                return FakeResponse(json.dumps(data), status_code=200,
                                    json_data=data)
            if "foudalens" in low or "/ipo" in low:
                return FakeResponse(IPO_HTML, status_code=200)
            return FakeResponse('{"ok": true}', status_code=200)
        raise NetworkBlocked("الشبكة مقفولة: %s %s" % (method, url))
    return handler


_STATE = {"mode": "blocked", "delay": 0.0, "installed": False}


def set_mode(mode, delay=0.0):
    """يغيّر وضع المصدر ⭐."""
    _STATE["mode"] = str(mode or "blocked")
    _STATE["delay"] = float(delay or 0.0)
    return current_mode()


def current_mode():
    """وضع المصدر الحالي ⭐."""
    return _STATE["mode"]


def _get(url, **kw):
    return source_handler(_STATE["mode"], _STATE["delay"])("GET", url, **kw)


def _post(url, **kw):
    return source_handler(_STATE["mode"], _STATE["delay"])("POST", url, **kw)


def install():
    """يقفل كل النداءات الخارجية ⭐ (على أي `requests` متاح ⭐)."""
    req = sys.modules.get("requests")
    if req is None:
        return False
    req.get = _get
    req.post = _post
    for name in ("put", "delete", "patch", "head"):
        if hasattr(req, name):
            try:
                setattr(req, name, _get)
            except Exception:
                pass
    _STATE["installed"] = True
    return True


if __name__ == "__main__":
    print("🚧 حجب الشبكة + المصدر الاصطناعي — الجولة ٢٥")
    print("   الوضع الحالي: %s ⭐" % current_mode())
    print("RESULT: CLEAN")
