# -*- coding: utf-8 -*-
"""🧪 اختبار تاريخ الذهب الطويل — ٢٧ أكتوبر ٢٠٢٦

📌 الفكرة: «لو ادخرت ذهب من سنة كنا، كام بقى؟» محتاجة سلسلة
   سعر الجرام بالجنيه المصري لسنوات طويلة ⇒ series من gold_history.py.

⛔ القواعد اللي الاختبار بيحرسها:
   ① مفيش look-ahead: value_on(date) ترجع تاريخ **قبل** أو = التاريخ المطلوب
   ② المعادلة صح: gram = (xau / egp) / 31.1035
   ③ الملخص متسق: times = last/first · القمة = أعلى جرام فعلاً
   ④ السلسلة طويلة (أكتر من ١٠ سنوات) ومصدرها موثّق
   ⑤ مفيش قيم مخترعة: لو المصدر فشل ⇒ ok=False وسبب مكتوب (مفيش صفرات كاذبة)
"""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _stub_env
_stub_env.install()
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ.setdefault("GOLD_HISTORY_PATH", "/tmp/gold_history_test.json")

import update_prices as U
import gold_history as gh

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def call(path, query=None):
    r = U.app.dispatch(path, "GET", query=query or {})
    status, body = getattr(r, "status_code", 200), getattr(r, "body", r)
    if isinstance(r, tuple):
        body = r[0]
        status = r[1] if len(r) > 1 else status
    if isinstance(body, (bytes, str)):
        try:
            body = json.loads(body)
        except Exception:
            pass
    return status, body


print("▶️ بناء السلسلة (مرة واحدة — الكاش بيخلي الباقي سريع)…")
data = gh.build()
print("   ok:", data.get("ok"), "| count:", data.get("count"),
      "|", data.get("from"), "→", data.get("to"))

print("\n▶️ ① شكل السلسلة ومصدرها")
check(data.get("ok") is True, "السلسلة اتبنت بنجاح")
s = data.get("series") or []
check(len(s) > 1500, f"السلسلة طويلة (>1500 يوم) — {len(s)}")
check(data.get("from", "") <= "2016-10-27", "بتبدأ من يوم تعويم الجنيه (٢٠١٦-١٠-٢٦) أو قبله")
# ⛔⛔ ٢٧ أكتوبر ٢٠٢٦ — مصدر الصرف بقى USDEGP (الرسمي).
# 📌 السبب: EGPUSD = سعر السوق الموازي (+2.4٪) ⇒ كان بيعمل خطأ ٢.٤٪
#    في آخر نقطة. USDEGP = الرسمي = نفس tk-usd في الـscanner.
_fx = (data.get("sources", {}).get("fx") or {})
check(_fx.get("id") in ("tradingview_usdegp", "yahoo_egpx"),
      "مصدر الصرف موسوم: " + str(_fx.get("id")))
check(_fx.get("id") != "tradingview_egpusd",
      "⛔ مش السوق الموازي (EGPUSD) — ده الرسمي")
# ⛔ التحقق الحسابي: جرام = ذهب × جنيه/دولار ÷ 31.1035 (على أول وآخر صف)
for _r in (s[0], s[-1]):
    _calc = round(_r["xau"] * _r["egp_per_usd"] / 31.1035, 4)
    check(abs(_calc - _r["gram"]) <= 1e-6,
          "الجرام = ذهب × رسمي ÷ 31.1035 (%s) ⇒ %.4f" % (_r["d"], _calc))
    check(_r["egp_per_usd"] > 1,
          "جنيه/دولار > 1 (%s ⇒ %.2f)" % (_r["d"], _r["egp_per_usd"]))
    check(abs(_r["usd_per_egp"] * _r["egp_per_usd"] - 1.0) < 1e-6,
          "usd_per_egp هو المقلوب فعلاً (%s)" % _r["d"])
check(data.get("to", "") >= (datetime.datetime.utcnow() - datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
      "بتوصل لآخر几天")
check(bool(data.get("sources", {}).get("gold")), "مصدر الذهب موثّق")
check(bool(data.get("sources", {}).get("fx")), "مصدر سعر الدولار موثّق")
check(bool(data.get("method", {}).get("formula")), "المعادلة موثّقة")
check(bool(data.get("method", {}).get("caveats")), "القيود (caveats) موثّقة")
check(bool(data.get("fx_alternative")), "السلسلة البديلة (FX تاني) موجودة وموثّقة")

print("\n▶️ ② المعادلة صح على كل الصفوف")
bad = 0
for r in s[:200] + s[-200:]:
    calc = (r["xau"] * r["egp_per_usd"]) / 31.1035
    if abs(calc - r["gram"]) > max(0.05, r["gram"] * 0.0005):
        bad += 1
check(bad == 0, f"كل الصفوف المتحقَّقة مطابقة للمعادلة (خطأ في {bad})")
check(all(r["gram"] > 0 for r in s), "مفيش سعر صفري أو سالب")
check(all(r["egp_per_usd"] > 0 for r in s), "مفيش سعر دولار صفري")

print("\n▶️ ③ اتساق الملخص")
st = gh.stats(data)
check(st.get("ok") is True, "الملخص اتحسب")
if st.get("ok"):
    check(abs(st["times"] - st["last_gram"] / st["first_gram"]) < 0.02, "الض��اعف = آخر/أول")
    hi = max(r["gram"] for r in s)
    check(abs(st["all_time_high"]["gram"] - hi) < 0.05, "القمة = أعلى جرام في السلسلة")
    lo = min(r["gram"] for r in s)
    check(abs(st["all_time_low"]["gram"] - lo) < 0.05, "أدنى نقطة = أدنى جرام في السلسلة")
    check(len(st.get("years") or []) >= 10, f"سنوات مرصودة: {len(st.get('years') or [])}")
    years = st.get("years") or []
    bad_y = [y for y in years if y.get("ret_pct") is not None and (y["ret_pct"] < -99 or y["ret_pct"] > 100000)]
    check(not bad_y, "مفيش سنة بعائد معقول")

print("\n▶️ ④ مفيش look-ahead (value_on ترجع تاريخ سابق أوequal)")
for d in ("2010-06-15", "2015-01-05", "2020-03-20", "2024-11-01"):
    row = gh.value_on(d, data)
    check(row is not None and row["d"] <= d, f"value_on({d}) ⇒ {row['d'] if row else None} (مش بعد التاريخ)")

print("\n▶️ ⑤ المسارات")
st_code, body = call("/api/gold/history", {"stats": "1"})
check(st_code == 200, f"/api/gold/history?stats=1 ⇒ {st_code}")
check(isinstance(body, dict) and body.get("ok") is True, "الرد ok")
check(isinstance(body.get("stats"), dict), "الملخص في الرد")
st_code2, body2 = call("/api/gold/history")
check(st_code2 == 200 and len(body2.get("series") or []) == len(s),
      f"/api/gold/history (كاملة) ⇒ {st_code2} · {len(body2.get('series') or [])} نقطة")
st_code3, body3 = call("/api/gold/gram", {"date": "2015-06-01"})
check(st_code3 == 200, f"/api/gold/gram ⇒ {st_code3}")
check(isinstance(body3, dict) and body3.get("date", "") <= "2015-06-01",
      "سعر تاريخي رجع بتاريخ سابق/equal")
st_code4, body4 = call("/api/gold/gram", {"date": "مش-تاريخ"})
check(st_code4 == 400, f"تاريخ غلط ⇒ 400 (مش 500) — {st_code4}")
st_code5, body5 = call("/api/gold/gram", {"date": "1990-01-01"})
check(st_code5 == 404, f"تاريخ قبل السلسلة ⇒ 404 (مش 500) — {st_code5}")

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
