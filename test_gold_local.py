# -*- coding: utf-8 -*-
"""🧪 اختبار.layer البيانات المحلية والعلاوة — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي الاختبار بيحرسها:
 ① مفيش رقم مخترع: لو المصدر فشل ⇒ ok=False + سبب (مش صفر)
 ② سعر الشراء ≠ سعر البيع — الاتنين لازم يكونوا موجودين ومستقلين
 ③ الطزاجة محسوبة من وقت **المصدر** مش وقت سحبنا
 ④ التحويل لازم يكون على أونصة **تروي** (31.1035 جرام)
 ⑤ الهوية اللوغاريتمية: log(نظري) = log(ذهب) + log(جنيه/دولار) — بالضبط
 ⑥ ⛔ مفيش look-ahead: value_on ترجع تاريخ ≤ المطلوب
 ⑦ العلاوة بتتحسب بس لو المرصود والنظري موجودين
"""
import os, sys, json, datetime, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _stub_env
_stub_env.install()
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ.setdefault("GOLD_HISTORY_PATH", "/tmp/gold_history_test2.json")

import gold_history as gh
import gold_local as gl
import gold_premium as gp

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


print("▶️ ① السعر المحلي المرصود")
d = gl.get(force=True)
check(d.get("ok") is True, "السحب نجح: " + str(d.get("error") or ""))
if d.get("ok"):
    check(bool(d.get("updated_iso")), "فيه وقت آخر تحديث من المصدر: " + str(d.get("updated_iso")))
    check(d.get("source_type") == "commercial_market_reference", "المصدر موسوم إنه مرجع تجاري (مش حكومي)")
    check(bool(d.get("source_url")), "فيه رابط المصدر")
    k = d.get("karats") or {}
    check(len(k) >= 3, f"عدد العيارات: {len(k)}")
    for kk in ("14", "18", "21"):
        row = k.get(kk) or {}
        check(row.get("buy") is not None and row.get("sell") is not None,
              f"{kk}K: شراء وبيع موجودين")
        if row.get("buy") and row.get("sell"):
            check(row["sell"] >= row["buy"], f"{kk}K: سعر البيع ≥ سعر الشراء")
    g24 = d.get("gram_24_reference")
    check(g24 is not None and g24 > 1000, f"سعر جرام 24 موجود: {g24}")
    fr = gl.freshness(d)
    check(fr.get("status") in ("live", "delayed", "stale", "unknown"),
          f"الطزاجة: {fr.get('status')} ({fr.get('age_minutes')} دقيقة)")

print("\n▶️ ② تحويل الجرام (أونصة تروي 31.1035)")
grams = gl.gram_prices(d)
check(grams is not None, "تحويل الجرام اشتغل")
if grams:
    for kk in ("14", "18", "21"):
        row = grams.get(kk) or {}
        exp = round((d["karats"][kk]["sell"]) / 31.1035, 2)
        check(abs(row.get("sell_gram", 0) - exp) < 0.02,
              f"{kk}K جرام = الأونصة ÷ 31.1035 ⇒ {row.get('sell_gram')}")
    sp = (grams.get("21") or {}).get("spread_pct")
    check(sp is not None and 0 < sp < 10, f"الفارق بين الشراء والبيع معقول: {sp}%")

print("\n▶️ ③ الطزاجة")
fr2 = gl.freshness({"ok": True, "updated_iso": (datetime.datetime.now(datetime.timezone.utc)
                                                - datetime.timedelta(hours=3)).isoformat()})
check(fr2.get("status") == "delayed", "ساعة ٣ ⇒ delayed")
fr3 = gl.freshness({"ok": True, "updated_iso": (datetime.datetime.now(datetime.timezone.utc)
                                                - datetime.timedelta(days=5)).isoformat()})
check(fr3.get("status") == "stale", "٥ أيام ⇒ stale")

print("\n▶️ ④ السلسلة التاريخية + الهوية اللوغاريتمية")
data = gh.build(force=True)
check(data.get("ok") is True, "السلسلة اتبنت")
s = data.get("series") or []
check(len(s) > 2000, f"السلسلة طويلة (>2000 يوم = 10 سنين): {len(s)}")
bad = 0
for r in s[:300] + s[-300:]:
    calc = (r["xau"] * r["egp_per_usd"]) / 31.1035
    if abs(calc - r["gram"]) > max(0.05, r["gram"] * 0.0006):
        bad += 1
check(bad == 0, f"كل الصفوف المتحقَّقة مطابقة للمعادلة (خطأ في {bad})")
check(all(r["egp_per_usd"] > 0 for r in s), "سعر الجنيه لكل دولار موجب في كل الصفوف")

for days in (30, 365, 1095):
    dec = gp.decompose(s, days=days)
    check(dec.get("ok") is True, f"تفكيك {days} يوم اتحسب")
    if dec.get("ok"):
        check(dec.get("log_sum_exact") is True,
              f"الهوية اللوغاريتمية بالظبط ({days} يوم) — فرق {dec.get('log_sum_check')}")
        a = gp.attribute(dec)
        check(a is not None, f"الإسناد اتحسب ({days} يوم)")
        if a:
            check(abs(a["gold_share_pct"] + a["currency_share_pct"] - 100) < 2,
                  f"نصيب الذهب + نصيب الدولار = ١٠٠٪ ({a['gold_share_pct']} + {a['currency_share_pct']})")
            check("مش إثبات" in a.get("caveat", ""), "فيها تحذير إن ده مش إثبات سببية")

print("\n▶️ ⑤ مفيش look-ahead")
for dt in ("2010-06-15", "2015-01-05", "2020-03-20", "2024-11-01"):
    row = gh.value_on(dt, data)
    check(row is not None and row["d"] <= dt, f"value_on({dt}) ⇒ {row['d'] if row else None}")

print("\n▶️ ⑥ العلاوة: لازم ترجع None لو مفيش مرصود")
check(gp.premium(None, 7000) is None, "مرصود ناقص ⇒ None (مش صفر)")
check(gp.premium(7000, None) is None, "نظري ناقص ⇒ None (مش صفر)")
check(gp.premium(7000, 0) is None, "نظري صفري ⇒ None")
p = gp.premium(7240, 7221.66)
check(p is not None and abs(p["premium_pct"] - 0.2538) < 0.01, f"علاوة صح: {p['premium_pct']}%")
check(p and "مش دليل قاطع" in p["note"], "فيها تحذير: العلاوة مش دليل قاطع")

print("\n▶️ ⑦ النظرية: الأونصة تروي")
check(abs(gp.theoretical_gram(4000, 56.3267) - (4000 * 56.3267 / 31.1035)) < 0.001,
      "النظري = XAU × جنيه/دولار ÷ 31.1035")
check(gp.theoretical_gram(None, 56) is None, "بدون ذهب ⇒ None")
check(abs(gp.theoretical_gram(4000, 56.3267, 0.75) - gp.theoretical_gram(4000, 56.3267) * 0.75) < 0.01,
      "معامل النقاء بيتطبّق")

print("\n▶️ ⑧ الدولار الضمني")
imp = gp.implied_usd_egp(7240, 3998.64)
check(imp is not None and abs(imp - 56.31) < 0.05, f"الدولار الضمني من السعر المحلي: {imp}")
check(gp.implied_usd_egp(None, 4000) is None, "بدون مرصود ⇒ None")

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
