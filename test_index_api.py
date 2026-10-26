# -*- coding: utf-8 -*-
"""🧪 اختبار ذكاء المؤشرات — ٢٦ أكتوبر ٢٠٢٦ (تشغيل حقيقي للمسارات)"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _stub_env
_stub_env.install()
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
import update_prices as U

# ⛔ دخول وهمي — الاختبار بيفحص الحسابات مش المصادقة
U.require_user = lambda: {"uid": "testuser", "email": "t@t.com"}
app = U.app

import flask as _fl
_req = _fl.request

def call(path, query=None, ix_id=None):
    """ننداء المسار — والـstub مافيشوش path params ⇒ بننادي الـhandler مباشرة."""
    if ix_id is not None:
        rule = next(r for r in app.url_map if r.path == path)
        _req.reset()
        _req.path = path
        _req.method = "GET"
        _req.headers = {}
        _req.args = dict(query or {})
        r = rule.handler(ix_id)
    else:
        r = app.dispatch(path, "GET", query=query)
    # ⛔ الـstub بيرجّع tuple (body, status) في حالة 404 ⇒ نطبّع
    status, body = getattr(r, "status_code", 200), getattr(r, "body", r)
    if isinstance(r, tuple):
        body = r[0]; status = r[1] if len(r) > 1 else status
    if isinstance(body, (bytes, str)):
        try: body = json.loads(body)
        except Exception: pass
    return status, body

fails = []
def check(cond, msg):
    if not cond:
        fails.append(msg); print("   ❌", msg)

print("=== 1) قائمة المؤشرات ===")
st, d = call("/api/indices")
check(st == 200, f"status {st}")
check(d.get("ok"), "ok false")
for ix in d["indices"]:
    cov = ix["coverage"]
    print(f"   {ix['id']:7s} {ix['name_ar']:26s} رسمي={ix['live_official']['value']} "
          f"TV={ix['live_now'].get('value')} تغطية={cov['from']}→{cov['to']} ({cov['count']})")
    check(ix["live_official"]["value"] is not None, f"{ix['id']}: مفيش قيمة رسمية")
    check(cov["count"] and cov["count"] > 100, f"{ix['id']}: تغطية ضعيفة")
print("   market_status:", d["market_status"]["status_ar"], d["market_status"]["as_of"])

print("\n=== 2) تحليل EGX30 سنة ===")
st, d = call("/api/indices/<ix_id>/analysis", {"period": "1Y"}, ix_id="EGX30")
check(st == 200 and d.get("ok"), f"status {st}")
print("   period:", d["period"]["label"], "| observations:", d["period"]["observations"])
s = d["stats"]
print("   return:", s["return_pct"], "| high:", s["high"], "| low:", s["low"], "| avg:", s["avg"])
print("   max_dd:", s["max_drawdown"])
print("   volatility:", s["volatility"])
print("   recovery:", {k: s["recovery"][k] for k in ("recovered","days_to_recover","drawdown_pct")})
print("   regime:", d["regime"]["regime"], d["regime"]["confidence"])
for rr in d["regime"]["reasons"][:3]: print("      -", rr)
print("   phases:", len(d["phases"]), [p["kind"] for p in d["phases"][:6]])
print("   series:", len(d["series"]["values"]), "norm:", len(d["series"]["normalized"]), "dd:", len(d["series"]["drawdown"]))
print("   coverage:", d["coverage"]["note"] or "كاملة", "| complete:", d["coverage"]["complete"])
check(d["series"]["values"], "السلسلة فاضية")
check(s["return_pct"] is not None, "العائد None")
check(d["regime"]["regime"], "مفيش regime")

print("\n=== 3) كل المؤشرات × كل الفترات ===")
for ix in ("EGX30","EGX70","EGX100","EGX33"):
    for per in ("1M","3M","6M","YTD","1Y","3Y","5Y","10Y","MAX"):
        st, dd = call("/api/indices/<ix_id>/analysis", {"period": per}, ix_id=ix)
        check(st == 200 and dd.get("ok"), f"{ix}/{per} st={st}")
        if dd.get("ok"):
            check(dd["stats"]["return_pct"] is not None, f"{ix}/{per} return None")
            check(len(dd["series"]["values"]) >= 2, f"{ix}/{per} سلسلة قصيرة")
    st, dd = call("/api/indices/<ix_id>/analysis", {"period": "MAX"}, ix_id=ix)
    print(f"   ✅ {ix}: MAX → {dd['period']['observations']} يوم، {len(dd['phases'])} مرحلة، "
          f"return={dd['stats']['return_pct']}%, dd={dd['stats']['max_drawdown']['pct']}%")

print("\n=== 4) المقارنة ===")
st, d = call("/api/indices/compare", {"ids": "EGX30,EGX70,EGX100,EGX33", "period": "1Y"})
check(st == 200 and d.get("ok"), f"status {st}")
for i in d["indices"]:
    print(f"   {i['id']:7s} return={i['return_pct']}% dd={i['max_drawdown']}% vol={i['volatility']}% pts={len(i['normalized'])}")
    check(i["normalized"], f"{i['id']} مفيش normalized")
print("   summary:", d["summary"])

print("\n=== 5) المكونات ===")
st, d = call("/api/indices/<ix_id>/analysis", {"period": "1Y"}, ix_id="EGX30")
cons = d["constituents"]
print("   EGX30 components:", len(cons))
for c in cons[:5]:
    print(f"      {c['code']:7s} وزن={c['weight']}% نتيج��={c['score']} قرار={c['decision']} قطاع={c['sector']}")
check(cons, "مفيش مكونات")

print("\n=== 6) أخطاء ===")
st, d = call("/api/indices/<ix_id>/analysis", {}, ix_id="NOPE")
check(st == 404, f"مؤشر مش موجود رجّع {st}")
print("   ✅ كل الاختبارات نجحت" if not fails else f"   ❌ {len(fails)} فشل: {fails[:5]}")
sys.exit(1 if fails else 0)
