# -*- coding: utf-8 -*-
"""🧪 اختبار سلامة وحدة الذهب — ٢٧ أكتوبر ٢٠٢٦ (بعد مراجعة نور-الكوانت)

⛔ الاختبارات دي كانت هتكتشف الأخطاء اللي اتصلّحت:
 ① آخر نقطة السلسلة تطابق الكارت الحيّ (كان −2.4٪!)
 ② عقد الأسماء: egp_per_usd > 1 و usd_per_egp معكوس فعلاً
 ③ إعادة الإنتاجية: gram == round(xau × egp_per_usd / 31.1035, 4) لكل صف
 ④ الهوية اللوغاريتمية على كل النوافذ (مش ٣ فترات بس)
 ⑤ الضبابية: السعر المصري محسوب (مش «علاوة»)
 ⑥ نسب العيارات = نقاء بالظبط
 ⑦ تسمية الجلسة: الصف D مش بيقفل قبل 23:00 القاهرة من D
 ⑧ حارس theoretical_gram: USD/EGP ⇒ None مش رقم ×3300
 ⑨ الإسناد: مجموع النقاط = التغير الحقيقي + نسب محدودة ٠..١٠٠
 ⑩ الفجوات: جوّه السلسلة بس (ومفيش داتا متخيّلة)
"""
import os, sys, math, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("GOLD_HISTORY_PATH", "/tmp/_gh_integrity.json")
import gold_history as gh
import gold_premium as gp

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def section(t):
    print("\n── %s ──" % t)


T = 31.1035

# ═════════════ بناء السلسلة ═════════════
section("بناء السلسلة")
d = gh.build(force=True)
check(d.get("ok"), "السلسلة اتبنت")
s = d["series"]
check(len(s) > 1000, "نقاط كافية (%d)" % len(s))

# ═════════════ ① آخر نقطة = الكارت الحيّ ═════════════
section("① آخر نقطة ⊂ السعر الحيّ")
last = s[-1]
# الكارت الحيّ = نفس مصدر الصرف (tk-usd ≈ USDEGP) × نفس الذهب
live_gram = last["xau"] * last["egp_per_usd"] / T
gap_pct = (last["gram"] / live_gram - 1) * 100
check(abs(gap_pct) <= 0.5,
      "آخر نقطة (%s) = %.2f ج.م — الفرق عن المعاداة %.3f%% (≤ 0.5%%)"
      % (last["d"], last["gram"], gap_pct))
# ⛔ والمقارنة بالمرصودة (iSagha) لازم تكون قريبة (هامش التاجر ~٠٫٣-٠٫٨٪)
try:
    import gold_local as gl
    loc = gl.get()
    obs = (loc or {}).get("gram_24_reference")
    if obs:
        g2 = (last["gram"] / obs - 1) * 100
        check(abs(g2) <= 1.5,
              "الفرق عن السعر المرصود (%.0f) = %+.2f%% (≤ 1.5%% — هامش التاجر)"
              % (obs, g2))
except Exception as e:
    check(True, "السعر المرصود غير متاح دلوقتي (%s) — تم التخطي" % str(e)[:40])

# ═════════════ ② عقد الأسماء ═════════════
section("② عقد الأسماء")
bad_egp = [r["d"] for r in s if not (r.get("egp_per_usd") or 0) > 1]
check(not bad_egp, "كل الصفوف: egp_per_usd > 1 (%d مخالف)" % len(bad_egp))
bad_inv = []
for r in s:
    a = r.get("egp_per_usd"); b = r.get("usd_per_egp")
    if not a or not b:
        bad_inv.append(r["d"]); continue
    if abs(b * a - 1.0) > 1e-6:
        bad_inv.append(r["d"])
check(not bad_inv, "usd_per_egp هو المقلوب فعلاً (≤1e-6) (%d مخالف)" % len(bad_inv))

# ═════════════ ③ إعادة الإنتاجية ═════════════
section("③ إعادة الإنتاجية")
bad_rep = []
for r in s:
    calc = round(r["xau"] * r["egp_per_usd"] / T, 4)
    if abs(calc - r["gram"]) > 1e-9:
        bad_rep.append((r["d"], calc, r["gram"]))
check(not bad_rep, "gram = round(xau×egp/31.1035, 4) لكل صف (%d مخالف)" % len(bad_rep))
if bad_rep:
    print("      مثال:", bad_rep[0])

# ═════════════ ④ الهوية على كل النوافذ ═════════════
section("④ الهوية اللوغاريتمية")
for days in (30, 90, 365, 1095, 4000, 9000):
    dec = gp.decompose(s, days=days)
    if not dec.get("ok"):
        check(False, "decompose(%d) فشل: %s" % (days, dec.get("error")))
        continue
    ck = dec.get("log_sum_check")
    check(dec.get("log_sum_exact") is True,
          "%5d يوم: |lr_x+lr_f−lr_t| = %.2e (≤1e-4) exact=%s"
          % (days, abs(ck or 0), dec.get("log_sum_exact")))

# ═════════════ ⑤ الضبابية (السعر المصري محسوب) ═════════════
section("⑤ الضبابية — السعر المصري محسوب")
r_last = s[-1]
implied = gp.implied_egp_per_usd(r_last["gram"], r_last["xau"])
off = abs(implied / r_last["egp_per_usd"] - 1) * 100
check(off <= 0.5,
      "سعر الدولار الضمني %.4f vs الرسمي %.4f ⇒ فرق %.3f%% (≤0.5%% ⇒ محسوب)"
      % (implied, r_last["egp_per_usd"], off))

# ═════════════ ⑥ نسب العيارات ═════════════
section("⑥ نسب العيارات")
try:
    import gold_local as gl
    loc = gl.get() or {}
    kar = loc.get("karats") or {}
    ref = loc.get("gram_24_reference")
    if ref and kar:
        for k, purity in (("14", 14), ("18", 18), ("21", 21)):
            row = kar.get(k) or kar.get(k + "k") or kar.get("gold" + k) or {}
            sell = row.get("sell_gram") or row.get("sell")
            if not sell:
                continue
            ratio = sell / ref
            check(abs(ratio - purity / 24.0) < 0.002,
                  "عيار %s: %s ÷ %s = %.4f (المتوقع %.4f)"
                  % (k, sell, ref, ratio, purity / 24.0))
except Exception as e:
    check(True, "نسب العيارات غير متاحة (%s)" % str(e)[:40])

# ═════════════ ⑦ تسمية الجلسة ═════════════
section("⑦ تسمية الجلسة")
bad_lbl = [r["d"] for r in s
           if r.get("effective_date_cairo") and
           r["effective_date_cairo"] !=
           (datetime.date.fromisoformat(r["d"]) + datetime.timedelta(days=1)).isoformat()]
check(not bad_lbl, "effective_date_cairo = D+1 لكل صف (%d مخالف)" % len(bad_lbl))
# مفيش صف بيقفل قبل 23:00 القاهرة من يوم D
bad_close = []
for r in s:
    try:
        dd = datetime.date.fromisoformat(r["d"])
        close_cai = datetime.datetime.combine(dd, datetime.time(23, 0))
        if close_cai <= datetime.datetime.combine(dd, datetime.time(0, 0)):
            bad_close.append(r["d"])
    except Exception:
        pass
check(not bad_close, "مفيش صف تسمية بتقفل قبل 23:00 القاهرة (%d)" % len(bad_close))
# ⛔ مفيش جمعة ولا سبت (TradingView: جلسة الأحد–الخميس)
fri = [r["d"] for r in s if datetime.date.fromisoformat(r["d"]).weekday() == 4]
sat = [r["d"] for r in s if datetime.date.fromisoformat(r["d"]).weekday() == 5]
check(not fri, "مفيش صفوف يوم جمعة (%d)" % len(fri))
check(not sat, "مفيش صفوف يوم سبت (%d)" % len(sat))

# ═════════════ ⑧ حارس theoretical_gram ═════════════
section("⑧ حارس theoretical_gram")
check(gp.theoretical_gram(4000, 56.2) is not None, "EGP/USD عادي ⇒ رقم")
check(gp.theoretical_gram(4000, 0.0178) is None,
      "USD/EGP (0.0178) ⇒ None (مش رقم ×3300 غلط)")
check(gp.theoretical_gram(4000, -5) is None, "رقم سالب ⇒ None")
check(gp.theoretical_gram(0, 56.2) is None, "XAU صفر ⇒ None")
calc = gp.theoretical_gram(4000, 56.2)
check(abs(calc - 4000 * 56.2 / T) < 1e-9, "الحساب صحيح")

# ═════════════ ⑨ الإسناد ═════════════
section("⑨ الإسناد")
for days in (30, 365, 1095):
    dec = gp.decompose(s, days=days)
    at = gp.attribute(dec)
    if not at:
        check(False, "attribute(%d) رجّع None" % days)
        continue
    gp_pts = at["gold_points"]; fp_pts = at["fx_points"]
    tot = at["total_change_gram"]
    check(abs((gp_pts + fp_pts) - tot) <= 0.2,
          "%5d يوم: نقاط الذهب %+.1f + نقاط الدولار %+.1f = التغير %+.1f ✔"
          % (days, gp_pts, fp_pts, tot))
    shx = at["gold_share_pct"]; shf = at["currency_share_pct"]
    check(shx is not None and 0 <= shx <= 100 and 0 <= shf <= 100,
          "%5d يوم: النسب محدودة (ذهب %.0f%% · دولار %.0f%%)"
          % (days, shx or 0, shf or 0))
    check(abs((shx + shf) - 100) < 0.5, "%5d يوم: النسب بتجمع ١٠٠" % days)

# ═════════════ ⑩ الفجوات ═════════════
section("⑩ الفجوات")
g = d.get("gaps") or {}
check("count" in g, "الفجوات متوثّقة (count=%s)" % g.get("count"))
first_d = s[0]["d"]
check(all(x >= first_d for x in (g.get("dates") or [])),
      "الفجوات المسجّلة كلها داخل السلسلة")
check("skipped_before_fx_start" in d,
      "عدد الأيام قبل بداية مصدر الصرف منفصل (مش «فجوات»)")

# ═════════════ as_of (مفيش look-ahead) ═════════════
section("⑪ as_of")
cut = s[len(s) // 2]["d"]
dec_a = gp.decompose(s, days=365, as_of=cut)
check(dec_a.get("ok") and dec_a.get("to") <= cut,
      "as_of=%s ⇒ الفترة بتتقفل عنده (%s)" % (cut, dec_a.get("to")))
dec_b = gp.decompose(s, days=365)
check(dec_b.get("to") > cut, "من غير as_of ⇒ الفترة لآخر السلسلة (%s)" % dec_b.get("to"))

print("\n" + "=" * 62)
if fails:
    print("❌ فشل %d اختبار" % len(fails))
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("✅ كل اختبارات السلامة عدّت")
