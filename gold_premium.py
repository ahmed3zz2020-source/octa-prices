"""
═══════════════════════════════════════════════════════════════
 gold_premium.py — العلاوة المحلية + تفكيك حركة السعر
═══════════════════════════════════════════════════════════════
 📌 السؤال: «سعر الجرام المصري بيتحرك عشان إيه — الذهب ولا الدولار؟»

 ⛔⛔⛔ القواعد (ممنوع نكسرها):
 ① **مفيش سببية من الاحتمالات.** إحنا بنقول «ال.erase ارتباط حسابي» مش «الذهب هو السبب».
 ② **العلاوة بتتحسب بس لما السلسلةين قابلين للمقارنة**:
    نفس الوحدة (جرام) · نفس العيار (24) · فرق زمني صغير.
    ⛔ لو السعر المحلي مش معروف ⇒ مفيش علاوة (مش 0).
 ③ **التفكيك بـ log returns** لأن:
        log(نظري) = log(XAU) + log(USD/EGP)
    ⇒ بالضبط (مش تقريب) والجمع بيبقى صح.
    ⚠️ وبالأسس (simple) مش بيبقى بالضبط ⇒ بنقرا الاتنين.
 ④ **مفيش look-ahead:** الفترة بتتقفل على تاريخ محدد.

 📌 طبقة ٣ (السوق المحلي):
    السعر المرصود (iSagha) − السعر النظري (XAU × دولار ÷ 31.1035) = علاوة/خصم محلي.
    العلاوة ممكن تعني: عرض/طلب محلي · هامش التاجر · فروق التوقيت · اختلاف المصدر.
    ⛔ **مفيش استنتاج «العرض ناقص» من العلاوة لوحدها.**
═══════════════════════════════════════════════════════════════
"""
import math
import datetime

TROY_OUNCE_GRAMS = 31.1035


def _log(a, b):
    """log(b/a) — والعائد البسيط (b/a - 1)."""
    if not a or not b or a <= 0 or b <= 0:
        return None, None
    lr = math.log(b / a)
    sr = (b / a - 1.0) * 100.0
    return lr, sr


def theoretical_gram(xau_usd, egp_per_usd, purity=1.0):
    """
    السعر النظري لجرام الذهب عيار 24 بالجنيه.
      = (XAU USD/oz × EGP لكل دولار ÷ 31.1035) × معامل النقاء
    ⛔ الأونصة **تروي** (31.1035 جرام) — مش الأونصة العادية (28.3495).
    ⛔⛔ الحارس: EGP لكل دولار دايماً > 1 ⇒ لو حد مرّر USD/EGP (0.0174)
       ⇒ بنرجّع None مش رقم غلط ×3300 (نور-الكوانت).
    """
    if not xau_usd or not egp_per_usd:
        return None
    try:
        _e = float(egp_per_usd)
        _x = float(xau_usd)
    except Exception:
        return None
    if _e <= 0 or _x <= 0:
        return None
    if _e < 1:
        # ⛔ ده شكل USD/EGP (0.0174) — غلط ⇒ None مش رقم مخترع
        return None
    return (_x * _e / TROY_OUNCE_GRAMS) * float(purity or 1.0)


def premium(observed_gram, theo_gram):
    """
    العلاوة/الخصم المحلي = (السعر المرصود ÷ النظري) − 1
    ⛔ بترجع None لو أي واحد فيهم ناقص (مفيش صفرات كاذبة).
    """
    if observed_gram is None or theo_gram is None:
        return None
    if theo_gram <= 0:
        return None
    return {
        "premium_pct": round((float(observed_gram) / float(theo_gram) - 1.0) * 100.0, 3),
        "observed_gram": round(float(observed_gram), 2),
        "theoretical_gram": round(float(theo_gram), 2),
        "difference": round(float(observed_gram) - float(theo_gram), 2),
        "label": ("علاوة على السعر النظري" if observed_gram >= theo_gram
                  else "خصم على السعر النظري"),
        "note": ("الفرق بين السعر المرصود والسعر النظري. ممكن يكون عرض/طلب محلي أو "
                 "هامش التاجر أو فرق في توقيت التسعير — مش دليل قاطع على حاجة واحدة."),
    }


def implied_egp_per_usd(observed_gram, xau_usd):
    """
    ⛔ «سعر الدولار الضمني» (جنيه لكل دولار) — لو السعر المحلي مرصود
       ومعروف سعر الذهب العالمي: (الجرام × 31.1035) ÷ XAU.
    📌 ده **مش** سعر صرف رسمي — ده فحص اتساق: لو قرب من سعر الصرف الرسمي
       ⇒ السعر المحلي **محسوب** من الذهب العالمي × الصرف (مش «علاوة»).
    """
    if not observed_gram or not xau_usd:
        return None
    return round(float(observed_gram) * TROY_OUNCE_GRAMS / float(xau_usd), 4)


def implied_usd_egp(observed_gram, xau_usd):
    """⚠️ اسم قديم (مقلوب) — اتحفظ للتوافق. استخدم implied_egp_per_usd."""
    return implied_egp_per_usd(observed_gram, xau_usd)


def decompose(series, days=365, observed_series=None, as_of=None):
    """
    تفكيك حركة السعر النظري لجرام الذهب على طول فترة.
      log(نظري) = log(XAU) + log(EGP_per_USD)   (بالضبط)
      simple(نظري) ≠ simple(XAU) + simple(FX)     (بسبب الهامش الضرب)
    📌 series: [{d, xau, egp_per_usd, gram}] مرتّبة تصاعدياً (من gold_history).
    ⛔ لو السلسلة أقصر من الفترة المطلوبة ⇒ بنستخدم أطول فترة متاحة
       وبنقول كده بصراحة (مش بنكمّل برقم مخترع).
    ⛔ as_of: لو اتحدّد ⇒ الفترة بتتقفل على تاريخ محدد (مفيش look-ahead).
    """
    s = [r for r in (series or []) if r.get("xau") and r.get("egp_per_usd") and r.get("gram")]
    if as_of:
        _cut = str(as_of)[:10]
        s = [r for r in s if str(r.get("d"))[:10] <= _cut]
    if len(s) < 30:
        return {"ok": False, "error": "السلسلة قصيرة جداً للتحليل"}
    last = s[-1]
    # ن找到 أول نقطة قبل target
    try:
        target = (datetime.datetime.strptime(last["d"], "%Y-%m-%d").date()
                  - datetime.timedelta(days=int(days)))
    except Exception:
        target = None
    first = s[0]
    for r in s:
        if target and r["d"] >= target.isoformat():
            first = r
            break
    n_days = (datetime.datetime.strptime(last["d"], "%Y-%m-%d").date()
              - datetime.datetime.strptime(first["d"], "%Y-%m-%d").date()).days
    if n_days < 1:
        return {"ok": False, "error": "الفترة قصيرة جداً"}

    lr_x, sr_x = _log(first["xau"], last["xau"])
    # ⛔ لازم EGP لكل دولار (مش دولار لكل جنيه) ⇒ الهوية تبقى:
    #    log(نظري) = log(XAU) + log(EGP_per_USD)  ✔ (مجموع، مش طرح)
    lr_f, sr_f = _log(first["egp_per_usd"], last["egp_per_usd"])
    lr_t, sr_t = _log(first["gram"], last["gram"])
    # ⛔ التحقق: مجموع اللوغاريتمات لازم يساوي لوغاريتم النظري
    check = None
    if lr_t is not None and lr_x is not None and lr_f is not None:
        check = round((lr_x + lr_f) - lr_t, 10)

    out = {
        "ok": True,
        "from": first["d"], "to": last["d"], "days": n_days,
        "start_gram": first["gram"], "end_gram": last["gram"],
        "xau": {"start": first["xau"], "end": last["xau"],
                "ret_pct": round(sr_x, 2) if sr_x is not None else None,
                "log_ret": round(lr_x, 6) if lr_x is not None else None},
        "egp": {"start": first["egp_per_usd"], "end": last["egp_per_usd"],
                "ret_pct": round(sr_f, 2) if sr_f is not None else None,
                "log_ret": round(lr_f, 6) if lr_f is not None else None},
        "theoretical": {"start": first["gram"], "end": last["gram"],
                        "ret_pct": round(sr_t, 2) if sr_t is not None else None,
                        "log_ret": round(lr_t, 6) if lr_t is not None else None},
        "log_sum_check": check,
        # ⛔ التسامح 1e-4: تدوير الجرام لخانتين بيدي خطأ تراكمي بسيط
        "log_sum_exact": (check is not None and abs(check) < 1e-4),
    }

    # 📌 لو عندنا سعر محلي مرصود في نفس الفترة ⇒ نقارن
    if observed_series:
        # ⛔⛔⛔ المقارنة لازم تكون على **نفس نقطة البداية والنهاية** —
        #    الكود القديم كان بيطرح عائد فترة المرصود (كله) من عائد فترة
        #    النظري (أقصر) ⇒ رقم مش صحيح (نور-الكوانت).
        o = [r for r in observed_series if r.get("gram") and r.get("d") <= last["d"]]
        o = [r for r in o if r.get("d") >= first["d"]]
        if o:
            o_first = o[0]
            o_last = o[-1]
            if o_first["d"] >= first["d"] and o_last["d"] >= first["d"]:
                lr_o, sr_o = _log(o_first["gram"], o_last["gram"])
                out["observed_local"] = {
                    "from": o_first["d"], "to": o_last["d"],
                    "start_gram": o_first["gram"], "end_gram": o_last["gram"],
                    "ret_pct": round(sr_o, 2) if sr_o is not None else None,
                    "log_ret": round(lr_o, 6) if lr_o is not None else None,
                    "source": "السعر المحلي المرصود",
                }
                # ⛔⭐ الأصح: فرق **العلاوة** بين نقطتين (مش طرح عائدين)
                def _theo_at(dd):
                    cand = [r for r in s if r["d"] <= dd]
                    return cand[-1] if cand else None
                _ts, _te = _theo_at(o_first["d"]), _theo_at(o_last["d"])
                if _ts and _te and _ts.get("gram") and _te.get("gram"):
                    p_s = o_first["gram"] / _ts["gram"] - 1.0
                    p_e = o_last["gram"] / _te["gram"] - 1.0
                    out["observed_local"]["premium_start_pct"] = round(p_s * 100, 3)
                    out["observed_local"]["premium_end_pct"] = round(p_e * 100, 3)
                    out["observed_local"]["premium_change_pp"] = round((p_e - p_s) * 100, 3)
                    out["observed_local"]["note"] = (
                        "الفرق عن النظري عند بداية الفترة وعند نهايتها (نفس النقطتين) "
                        "— مش طرح عائد فترتين مختلفتين.")
                if sr_o is not None and sr_t is not None:
                    out["observed_local"]["vs_theoretical_pct"] = round(sr_o - sr_t, 2)
    return out


def attribute(d):
    """
    ترجمة بسيطة: قد إيه من الحركة «من الذهب» وقد إيه «من الدولار»؟
    📌 على أساس **الأساس** (log) — وده اللي بيتجمع صح.
    ⛔ ده **إسهام حسابي** مش إثبات سببية.
    """
    if not d or not d.get("ok"):
        return None
    x = d.get("xau", {}).get("log_ret")
    f = d.get("egp", {}).get("log_ret")
    if x is None or f is None:
        return None
    th = d.get("theoretical") or {}
    g0, g1 = th.get("start"), th.get("end")
    if g0 is None or g1 is None:
        return None
    # 📌 ① المساهمة **بالجنيه/جرام** — المجموع = التغير الحقيقي بالظبط
    #    (الصيغة: g1 = g0·(1+rg)·(1+rf) ⇒ نقسم حدّ الضرب على الاتنين)
    try:
        total = g1 - g0
        rg, rf = math.expm1(x), math.expm1(f)
        cross = g0 * rg * rf
        gold_pts = g0 * rg + cross / 2.0
        fx_pts = g0 * rf + cross / 2.0
    except Exception:
        return None
    # 📌 ② قوة المساهمتين (نسب محدودة ٠..١٠٠ — من لوغاريتم العوائد)
    den = abs(x) + abs(f)
    sh_x = (abs(x) / den * 100.0) if den else None
    sh_f = (abs(f) / den * 100.0) if den else None
    driver = ("سعر الدولار مقابل الجنيه" if abs(fx_pts) >= abs(gold_pts)
              else "الذهب العالمي")
    dpts = fx_pts if abs(fx_pts) >= abs(gold_pts) else gold_pts
    return {
        "total_change_gram": round(total, 1),
        "total_change_pct": round((g1 / g0 - 1.0) * 100.0, 2) if g0 else None,
        "gold_points": round(gold_pts, 1),
        "fx_points": round(fx_pts, 1),
        "gold_share_pct": round(sh_x, 1) if sh_x is not None else None,
        "currency_share_pct": round(sh_f, 1) if sh_f is not None else None,
        "driver": driver,
        "text": ("الجرام %s %.0f ج.م (%.1f%%): %s contributing %+.0f ج.م، "
                 "والذهب العالمي %+.0f ج.م."
                 % ("ارتفع" if total >= 0 else "انخفض", abs(total),
                    (g1 / g0 - 1.0) * 100.0 if g0 else 0.0,
                    driver, dpts, gold_pts)),
        "caveat": ("ده إسهام حسابي على أساس لوغاريتم العوائد — مش إثبات إن العامل "
                   "ده سبّب الحركة. والنسب = قوة المساهمة (٠..١٠٠) مش نسبة من التغير."),
    }
