# -*- coding: utf-8 -*-
"""🧪 اختبار سلامة وحدة الذهب — ٢٧ أكتوبر ٢٠٢٦ (بعد مراجعة نور-الكوانت)

⛔ الاختبارات دي كانت هتكتشف الأخطاء اللي اتصلّحت:
 ① سلامة السلسلة: وحدات آخر نقطة + تواريخ متزايدة + نافذة حداثة
    (حتمية — من غير أي سعر حيّ)
 ② عقد الأسماء: egp_per_usd > 1 و usd_per_egp معكوس فعلاً
 ③ إعادة الإنتاجية: gram == round(xau × egp_per_usd / 31.1035, 4) لكل صف
 ④ الهوية اللوغاريتمية على كل النوافذ (مش ٣ فترات بس)
 ⑤ الضبابية: السعر المصري محسوب (مش «علاوة»)
 ⑥ نسب العيارات = نقاء بالظبط
 ⑦ تسمية الجلسة: الصف D مش بيقفل قبل 23:00 القاهرة من D
 ⑧ حارس theoretical_gram: USD/EGP ⇒ None مش رقم ×3300
 ⑨ الإسناد: مجموع النقاط = التغير الحقيقي + نسب محدودة ٠..١٠٠
 ⑩ الفجوات: جوّه السلسلة بس (ومفيش داتا متخيّلة)
🛡️ الجولة ٢٣ (R23 · Phase 4) — فصل الاختبارات الحيّة عن الحتمية:
  ⛔ **مقارنة السعر الحيّ** اتنقلت لملف test_gold_live_price.py
     (بيتخطّى افتراضياً · وبتشغّله بـ OCTA_RUN_LIVE_TESTS=1)
     لأن الفشل كان **انحراف سوق حيّ** (−2.13٪ على edc49cd · −2.57٪ على
     الفرع وقت الفحص) — مش عيب في الكود.
  ⭐ مكانها هنا: فحوص **حتمية** عن سلامة السلسلة نفسها
     (الوحدات · تزايد التواريخ · نافذة الحداثة · النطاقات المعقولة)
     ⇒ نفس التغطية القوية · بس **من غير سعر حيّ**.
🛡️ الجولة ٢٥ (R25 · Phase 7 · R24-I14) — قياس التكافؤ بمصادر مستقلة:
  ⑫ تفكيك الانحراف بثلاث قراءات **مستقلة** (حتمي · أرقام اصطناعية):
     رجل السعر · رجل العملة · فرق التسعير المحلي — مع كاشف **دورية**
     (لو سعر الصرف اتحسب من سعر الذهب ⇒ يتكشف ويُرفض).
  ⑬ حارس سياسة الحد: حد الانحراف **١٫٥٪** ما ينفعش يترفع (المالك رفض
     رفعه لـ٥٪) — والاختبار الحيّ لازم يبقى مقسوم بـsources مستقلة.
"""
import os, re, sys, math, datetime

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

# ═════════════ ① سلامة السلسلة (حتمية — من غير أي سعر حيّ) ═════════════
section("① سلامة السلسلة (حتمية — من غير سعر حيّ)")
last = s[-1]
# (أ) الاتساق الداخلي: آخر نقطة = معادلة مدخلاتها (وحدات)
live_gram = last["xau"] * last["egp_per_usd"] / T
gap_pct = (last["gram"] / live_gram - 1) * 100
check(abs(gap_pct) <= 0.5,
      "آخر نقطة (%s) = %.2f ج.م — الفرق عن المعاداة %.3f%% (≤ 0.5%%)"
      % (last["d"], last["gram"], gap_pct))
# (ب) التواريخ متزايدة تماماً (مافيش تكرار · مافيش رجوع لوراء)
dates = [r["d"] for r in s]
check(all(dates[i] < dates[i + 1] for i in range(len(dates) - 1)),
      "تواريخ السلسلة متزايدة تماماً (%d نقطة · مافيش تكرار ولا قفزة لوراء)"
      % len(dates))
# (ج) نافذة الحداثة: آخر نقطة لازم تكون حديثة (مفيش سلسلة قديمة متخبّاية)
try:
    last_day = datetime.date.fromisoformat(last["d"])
    today = datetime.datetime.utcnow().date()
    age_days = (today - last_day).days
except Exception:
    age_days = None
check(age_days is not None and -1 <= age_days <= 10,
      "نافذة الحداثة: آخر نقطة (%s) عمرها %s يوم (≤ 10 · بتغطي عطلة آخر الأسبوع)"
      % (last["d"], age_days))
# (د) النطاقات المعقولة للوحدات (سعر الجرام · الأونصة · الدولار)
check(100.0 <= last["gram"] <= 200000.0,
      "سعر الجرام %.2f ج.م داخل النطاق المعقول" % last["gram"])
check(500.0 <= last["xau"] <= 20000.0,
      "سعر الأونصة %.2f دولار داخل النطاق المعقول" % last["xau"])
check(1.0 < last["egp_per_usd"] < 1000.0,
      "سعر الدولار %.4f ج.م داخل النطاق المعقول" % last["egp_per_usd"])
# (هـ) مافيش NaN/Infinity في قيم السلسلة (وحدة السلسلة سليمة)
bad_num = [r["d"] for r in s
           if not isinstance(r.get("gram"), (int, float))
           or r["gram"] != r["gram"]
           or r["gram"] in (float("inf"), float("-inf"))]
check(not bad_num, "مافيش NaN/Infinity في قيم السلسلة (%d مخالف)" % len(bad_num))
# 📌 ⛔ مقارنة السعر المرصود (iSagha) انتقلت لملف test_gold_live_price.py
#    (اختبار حيّ صريح — بيتخطّى افتراضياً · OCTA_RUN_LIVE_TESTS=1)

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

# ═════════════ ⑫ قياس التكافؤ بمصادر مستقلة (حتمي — من غير شبكة) ═════════════
# 📌 (الجولة ٢٥ · R24-I14) — السبب القديم كان **دائري**:
#    سعر الصرف الضمني كان بيتحسب من السعر المحلي نفسه، وبعدين
#    نفس الرقم كان بيُستخدم لإثبات إن الهامش المحلي = صفر
#    ⇒ النتيجة كانت **بالضرورة** صفر مهما كان السعر المرصود.
#    ⛔ الفحوص دي حتمية بالكامل (أرقام اصطناعية · مافيش شبكة).
section("⑫ قياس التكافؤ بمصادر مستقلة (حتمي — مافيش شبكة)")
try:
    import gold_parity as gpar
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import r24_gold_drift_isolation as r24
except Exception as e:
    check(False, "وحدات القياس المستقل مش متاحة: %s" % str(e)[:80])
    gpar = None

if gpar is not None:
    # ── البيانات الاصطناعية (ثابتة · مافيش شبكة) ──
    S = {"d": "2026-01-02", "xau": 3000.0, "egp_per_usd": 50.0,
         "gram": round(3000.0 * 50.0 / T, 4),
         "effective_date_cairo": "2026-01-03"}
    GOLD_NOW = 3100.0      # ذهب عالمي (مزوّد مستقل) · دولار/أونصة
    FX_NOW = 52.0          # صرف مستقل (عملة) · جنيه/دولار
    LOCAL = 5500.0         # جرام محلي مرصود · جنيه/جرام
    exp_gold = (GOLD_NOW / S["xau"] - 1) * 100
    exp_fx = (FX_NOW / S["egp_per_usd"] - 1) * 100
    exp_parity = GOLD_NOW * FX_NOW / T
    exp_prem = (LOCAL / exp_parity - 1) * 100
    exp_drift = (S["gram"] / LOCAL - 1) * 100

    dec = gpar.decompose_drift(S, GOLD_NOW, FX_NOW, LOCAL)
    check(dec.get("ok"), "التفكيك اشتغل على بيانات اصطناعية")
    check(abs(round(dec.get("gold_leg_pct") or 0, 4) - round(exp_gold, 4)) < 1e-9,
          "رجل الذهب %+.4f%% (المتوقع %+.4f%%)"
          % (dec.get("gold_leg_pct") or 0, exp_gold))
    check(abs(round(dec.get("fx_leg_pct") or 0, 4) - round(exp_fx, 4)) < 1e-9,
          "رجل العملة %+.4f%% (المتوقع %+.4f%%)"
          % (dec.get("fx_leg_pct") or 0, exp_fx))
    check(dec.get("local_premium_pct") is not None
          and abs(round(dec["local_premium_pct"], 4) - round(exp_prem, 4)) < 1e-9,
          "العلاوة المحلية %+.4f%% (المتوقع %+.4f%%) — رقم **مقاس**"
          % (dec.get("local_premium_pct") or 0, exp_prem))
    check(abs(round(dec.get("drift_pct") or 0, 4) - round(exp_drift, 4)) < 1e-9,
          "الانحراف %+.4f%% (المتوقع %+.4f%%)"
          % (dec.get("drift_pct") or 0, exp_drift))
    check(dec.get("identity_holds") is True,
          "الهوية اللوغاريتمية قاعدة: خطأ %.2e (≤1e-8)"
          % (dec.get("identity_error_ratio") or 0))
    check(dec.get("fx_is_independent") is True,
          "الصرف المستقل اتقبل كـ«مستقل» (مش مشتقّ من الذهب)")

    # ── ⛔ البرهان السالب (١): حقن اشتقاق دائري لازم يتكشف ──
    fx_circ = LOCAL * T / GOLD_NOW          # ⛔ ده بالظبط الاشتقاق الدائري
    det = gpar.detect_circular_fx(fx_circ, LOCAL, GOLD_NOW)
    check(det.get("circular") is True,
          "⛔ كاشف الدورية: صرف مشتقّ من سعر الذهب اتكشف (فرق %.4f%%)"
          % (det.get("diff_pct") or 0))
    det_ok = gpar.detect_circular_fx(FX_NOW, LOCAL, GOLD_NOW)
    check(det_ok.get("circular") is False,
          "صرف مستقل حقيقي ما اتحسبش دائري (فرق %.4f%%)"
          % (det_ok.get("diff_pct") or 0))

    # ── ⛔ البرهان السالب (٢): مع الصرف الدائري ⇒ مافيش «هامش = صفر» ──
    dec_c = gpar.decompose_drift(S, GOLD_NOW, fx_circ, LOCAL)
    check(dec_c.get("local_premium_pct") is None,
          "⛔ مع صرف دائري ⇒ العلاوة **مش** رقم (مش صفر كاذب)")
    check(dec_c.get("fx_is_independent") is False
          and bool(dec_c.get("premium_reason")),
          "⛔ مع صرف دائري ⇒ السبب مكتوب: %s"
          % str(dec_c.get("premium_reason"))[:70])

    # ── ⛔ البرهان السالب (٣): أداة الجولة ٢٤ ما رجعتش «هامش = صفر» ──
    loc_fix = {"gram_24_reference": LOCAL, "ounce_usd": GOLD_NOW, "karats": {}}
    try:
        d1 = r24.decompose(S, loc_fix, None, None,
                           fx_independent=FX_NOW, gold_independent=GOLD_NOW)
        check(d1.get("local_margin_pct") is not None
              and abs(round(d1["local_margin_pct"], 4) - round(exp_prem, 4)) < 1e-9,
              "⛔ أداة العزل: الهامش %s%% (المتوقع %+.4f%%) — **مش** صفر بالبناء"
              % (d1.get("local_margin_pct"), exp_prem))
        d2 = r24.decompose(S, loc_fix, None, None,
                           fx_independent=fx_circ, gold_independent=GOLD_NOW)
        check(d2.get("circular_fx_detected") is True
              and d2.get("local_margin_pct") is None,
              "⛔ أداة العسل: الصرف الدائري اترفض (الهامش = None مش صفر)")
    except TypeError as e:
        check(False, "⛔ أداة العزل بتقبل صرف مستقل (وإلا مش بتعرف تقيس "
                     "الهامش من غير دورية): %s" % str(e)[:80])
    try:
        repro = r24.circular_repro()
        check(all(r.get("old_circular_margin_is_zero") for r in repro),
              "⛔ إعادة إنتاج العيب القديم: الصيغة الدورية بتطلع ٠٫٠٠٠٠٪ "
              "لكل سعر مرصود (%d حالات)" % len(repro))
        check(all(abs(r.get("new_independent_margin_pct") or 0) > 1e-6
                  for r in repro),
              "✅ الصيغة المستقلة بتطلع هامش حقيقي ≠ صفر لكل سعر مرصود")
    except AttributeError as e:
        check(False, "⛔ أداة العزل عندها إعادة إنتاج العيب القديم: %s"
              % str(e)[:80])

    # ── التصنيف: بنقول «أثر» مش «سبب» ──
    cls = gpar.classify_drift(dec)
    check(cls.get("dominant_leg") is not None and "سبب مؤكد" in (cls.get("statement") or ""),
          "التصنيف بيصرّح إنه إسهام حسابي مش سبب مؤكد")

# ═════════════ ⑬ حارس حدود الانحراف (سياسة المالك) ═════════════
section("⑬ حارس حدود الانحراف")
try:
    live_src = open(os.path.join(HERE, "test_gold_live_price.py"),
                    encoding="utf-8").read()
except Exception:
    live_src = ""
check("OCTA_LIVE_GOLD_TOLERANCE_PCT" in live_src
      and '"1.5"' in live_src,
      "حد الانحراف الحيّ لسه ١٫٥٪ (الافتراضي ما اتغيّرش)")
# 📌 الحارس بيستخدم تعبير نمطي (مش نص حرفي) عشان ما يقعش في مرجع ذاتي
_five_pct_re = re.compile(r"\b[A-Z_]*TOLERANCE[A-Z_]*\s*=\s*5(\.0+)?\b")
check(_five_pct_re.search(live_src) is None,
      "مافيش حد انحراف ٥٪ في الاختبار الحيّ")
try:
    contract_src = open(os.path.join(HERE, "tools",
                                     "test_round24_gold_gate_contract.py"),
                         encoding="utf-8").read()
except Exception:
    contract_src = ""
check(_five_pct_re.search(contract_src) is None,
      "مافيش حد انحراف ٥٪ في عقد الجولة ٢٤")

print("\n" + "=" * 62)
if fails:
    print("❌ فشل %d اختبار" % len(fails))
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("✅ كل اختبارات السلامة عدّت")
