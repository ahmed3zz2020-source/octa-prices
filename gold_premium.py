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


def theoretical_gram(xau_usd, usd_egp, purity=1.0):
    """
    السعر النظري لجرام الذهب عيار 24 بالجنيه.
      = (XAU/USD × USD/EGP ÷ 31.1035) × معامل النقاء
    ⛔ الأونصة **تروي** (31.1035 جرام) — مش الأونصة العادية (28.3495).
    """
    if not xau_usd or not usd_egp:
        return None
    return (float(xau_usd) * float(usd_egp) / TROY_OUNCE_GRAMS) * float(purity or 1.0)


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


def implied_usd_egp(observed_gram, xau_usd):
    """
    ⛔ «سعر الدولار الضمني» — لو السعر المحلي مرصود ومعروف سعر الذهب العالمي،
       السعر الضمني = (الجرام × 31.1035) ÷ XAU. ده **مؤشر** على فروق
       التوقيت/العلاوة/السوق الموازي — مش سعر صرف رسمي.
    """
    if not observed_gram or not xau_usd:
        return None
    return round(float(observed_gram) * TROY_OUNCE_GRAMS / float(xau_usd), 4)


def decompose(series, days=365, observed_series=None):
    """
    تفكيك حركة السعر النظري لجرام الذهب على طول فترة.
      log(نظري) = log(XAU/USD) + log(USD/EGP)   (بالضبط)
      simple(نظري) ≠ simple(XAU) + simple(FX)     (بسبب الهامش الضرب)
    📌 series: [{d, xau, egp, gram}] مرتّبة تصاعدياً (من gold_history).
    ⛔ لو السلسلة أقصر من الفترة المطلوبة ⇒ بنستخدم أطول فترة متاحة
       وبنقول كده بصراحة (مش بنكمّل برقم مخترع).
    """
    s = [r for r in (series or []) if r.get("xau") and r.get("egp_per_usd") and r.get("gram")]
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
        o = [r for r in observed_series if r.get("gram") and r.get("d") <= last["d"]]
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
    t = d.get("theoretical", {}).get("log_ret")
    if x is None or f is None or t is None or t == 0:
        return None
    sh_x = x / t * 100.0
    sh_f = f / t * 100.0
    return {
        "gold_share_pct": round(sh_x, 1),
        "currency_share_pct": round(sh_f, 1),
        "text": ("من الحركة تقريباً %.0f%% من الذهب العالمي و%.0f%% من سعر الدولار مقابل الجنيه."
                 % (sh_x, sh_f)),
        "caveat": ("ده إسهام حسابي على أساس لوغاريتم العوائد — مش إثبات إن العامل ده سبّب الحركة."),
    }
