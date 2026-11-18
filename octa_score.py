"""🐙 octa_score.py — محرك التقييم، مقطوع عن أي شبكة.

    ⛌ قبل التعديل كان الحساب متلخبط في update_prices.py (7000 سطر) مع
    نسخة ثانية في merge_gold.py — كل واحدة بأوزان مختلفة. الموقع كان
    بيشتغل بنسخة والـAPI بنسخة تانية.

    الملف ده هو المحرك الوحيد. أي حد عايز يحسب تقييم لازم يستدعي
    final_score من هنا.

    ✅ مفيش requests · مفيش flask · مفيش شبكة — عشان يتشغّل في أي مكان
       ويتختبر لوحده. الأرقام مش هتتغير من هنا ولا هناك.

    الاستعمال:
        from octa_score import final_score, build_sector_stats
        stats = build_sector_stats(records)
        r = final_score(item, tech_score(item), fund, liq, stats)
"""


def _confidence_value(raw, default=60.0):
    """⛔⛔⛔ ١٥ نوفمبر ٢٠٢٦ — الثقة: الصفر يبقى صفر (F-20-13).

    ⛌ العيب: `float(item.get("data_confidence") or 60)` ⇒ الصفر كان
       بيتحول لـ60 ⇒ ثقة مزيفة (٦٠٪) + خصم ثقة مش موجود أصلاً.
    📌 السياسة المعتمدة:
       · الحقل غائب أو فارغ ⇒ الافتراضي الموثّق (60)
       · القيمة 0 ⇒ تبقى 0 (صفر ثقة مش هو 60!)
       · خارج النطاق ⇒ مقصوص على 0..100
       · قيمة غير صالحة ⇒ الافتراضي
    """
    if raw is None or raw == "":
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if v != v:                       # NaN
        return default
    return max(0.0, min(100.0, v))


def _known_number(v):
    """رقم معروف ومحدود — بيفرّق بين «الصفر الحقيقي» و«مش موجود».

    ⛔ الجولة ٢٤ (R24) — ليش الدالة دي؟
       · الصفر (0.0) = **قيمة حقيقية** (سهم مالوش تداول) ⇒ لازم يفضل
         0.0 معروف — مش يتحوّل لـNone (مش «ناقص»).
       · `None` / نص / `NaN` / `±Inf` = **مش بيانات** ⇒ None (ناقص).

    📌 العلّتين اللي كانت بتضيّع الفكرة:
       ① `0.0 or None` ⇒ None ⇒ الصفر الحقيقي بيختفي من القياس.
       ② `float('nan')` بيمرّ من كل المقارنات (False) ⇒ «محايد» في
          المحرك الفني و«ضعيف» في محرك السيولة، والمقسومة بتطلع NaN
          في ردود الـAPI ⇒ رقم مش صالح أصلاً.
    ⛔ مفيش تغيير في أي وزن ولا عتبة ولا سقف — التطبيع بس.
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


AXIS_WEIGHTS = {
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — إعادة توزيع الأوزان بعد شيل الأرقام الثابتة
    # 📌 «محور المحفظة» كان رقم ثابت 70 لكل سهم (مفيش محفظة عامة)
    # 📌   ⇒ ٩٪ من النتيجة كانت وهمية ⇒ بقى وزنه ٠ (المحور مستبعد).
    # 📌 «محور الأخبار» كان 45 ثابت لكل سهم ⇒ دلوقتي رقم حقيقي
    # 📌   (نتيجة محرك الأخبار) أو مستعد لو مفيش أحداث مسجّلة.
    # 📌 الـ٩٪ اتوزعت على المحاور الستة الحقيقية (متساوية النسبة):
    "technical":    0.20,
    "fundamental":  0.24,
    "liquidity":    0.20,
    "news":         0.05,
    "sentiment":    0.04,
    "risk":         0.27,
    "portfolio":    0.00,   # ⛔ مستبعد — رقم ثابت كان بيوهم
}

def tech_score(item):
    def _n(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d
    """
    يحوّل 43 مؤشر فني → نتيجة 0-100 مع تفسير كامل.
    المبدأ: كل نقطة ليها وزن وليها سبب — مفيش رقم بلا مبرر.
    """
    if not item or not item.get("price"):
        return None
    # 🛡️ الجولة ٢٠ (R20) — ⛔ حماية من القيم غير الصالحة ⬇️
    # 📌 العيب المقاس: `rsi` (وغيره) كان بيتقرا **خام** ⬇️
    #   ⛔ لو القيمة جت نصًّا ("abc") ⇒ `rsi > 70` ⇒ TypeError ⬇️
    #   ⛔⇒ 500 على صفحة السهم كله ⭐ (مش كل السهم) ⭐
    # ✅ الحل: كل رقم بيعدّي على `_n()` ⇒ النص/الـNaN يبقى None ⭐
    #   ⭐ والمنطق كله (الأوزان · الحدود) ما اتغيّرش ⭐
    price = _n(item.get("price"), None)
    if price is None:
        return None
    facts = {"positives": [], "negatives": [], "neutral": []}

    # ─────────── 1) الاتجاه (35 نقطة) ───────────
    trend = 0.0
    # ترتيب المتوسطات: Golden alignment؟
    ema20 = _n(item.get("ema20"), None)
    ema50 = _n(item.get("ema50"), None)
    ema200 = _n(item.get("ema200"), None)
    sma50 = _n(item.get("sma50"), None)

    ma_above = 0  # كام متوسط تحت السعر
    for name, v in (("EMA20", ema20), ("EMA50", ema50), ("EMA200", ema200), ("SMA50", sma50)):
        if v is not None:
            if price > v:
                ma_above += 1
                facts["positives"].append(f"السعر فوق {name} ({v:.2f})")
            else:
                facts["negatives"].append(f"السعر تحت {name} ({v:.2f})")
    trend += (ma_above / 4) * 20   # 20 نقطة

    # ترتيب المتوسطات (EMA20 > EMA50 > EMA200 = صاعد)
    if ema20 and ema50 and ema200:
        if ema20 > ema50 > ema200:
            trend += 10
            facts["positives"].append("ترتيب المتوسطات صاعد (EMA20 > EMA50 > EMA200)")
        elif ema20 < ema50 < ema200:
            trend += 0
            facts["negatives"].append("ترتيب المتوسطات هابط (اتجاه bearish)")
        else:
            trend += 5
            facts["neutral"].append("المتوسطات متشابكة — اتجاه عرضي")

    # قوة الاتجاه (ADX) — فوق 25 = اتجاه قوي
    adx = _n(item.get("adx"), None)
    di_p = _n(item.get("di_plus"), None)
    di_m = _n(item.get("di_minus"), None)
    if adx is not None:
        if adx > 40:
            trend += 5
            facts["positives"].append(f"قوة اتجاه عالية ({adx:.0f})")
        elif adx < 20:
            trend += 0
            facts["neutral"].append(f"اتجاه ضعيف/عرضي ({adx:.0f})")
    if di_p is not None and di_m is not None:
        if di_p > di_m:
            trend += 3
            facts["positives"].append("الحركة الصاعدة أقوى من الهابطة")
        elif di_m > di_p:
            facts["negatives"].append("الحركة الهابطة أقوى من الصاعدة")

    trend_score = max(0, min(35, trend))

    # ─────────── 2) الزخم (25 نقطة) ───────────
    mom = 0.0
    rsi = _n(item.get("rsi"), None)
    rsi_prev = _n(item.get("rsi_prev"), None)
    if rsi is not None:
        if rsi > 70:
            mom += 8
            facts["negatives"].append(f"القوة النسبية {rsi:.0f} — منطقة تشبع شرائي")
        elif rsi > 55:
            mom += 15
            facts["positives"].append(f"القوة النسبية {rsi:.0f} — زخم صاعد")
        elif rsi > 45:
            mom += 10
        elif rsi > 30:
            mom += 12
            facts["positives"].append(f"القوة النسبية {rsi:.0f} — منطقة تشبع بيعي (فرصة شراء)")
        else:
            mom += 6
            facts["negatives"].append(f"القوة النسبية {rsi:.0f} — زخم هابط قوي")
        # RSI اتجاه
        if rsi_prev is not None:
            if rsi > rsi_prev + 2:
                mom += 4
                facts["positives"].append("الزخم بيتسارع")
            elif rsi < rsi_prev - 2:
                mom -= 2
                facts["negatives"].append("الزخم بيتباطأ")

    # التقارب والانحراف
    macd = _n(item.get("macd"), None)
    sig = _n(item.get("macd_signal"), None)
    if macd is not None and sig is not None:
        if macd > sig:
            mom += 8
            facts["positives"].append("التقارب فوق خط الإشارة")
        else:
            mom += 2
            facts["negatives"].append("التقارب تحت خط الإشارة")
        if macd > 0:
            mom += 3
            facts["positives"].append("التقارب موجب")

    # ستوكاستك
    k = _n(item.get("stoch_k"), None)
    d = _n(item.get("stoch_d"), None)
    if k is not None and d is not None:
        if k > d and k < 80:
            mom += 5
            facts["positives"].append("الستوكاستك صاعد")
        elif k < d and k > 20:
            mom -= 2
            facts["negatives"].append("الستوكاستك هابط")

    # التذبذبurzugs (momentum oscillator)
    mo = _n(item.get("momentum"), None)
    if mo is not None:
        mom += max(-3, min(3, mo / 3))
    ao = _n(item.get("awesome"), None)
    if ao is not None:
        mom += 3 if ao > 0 else -2

    mom_score = max(0, min(25, mom))

    # ─────────── 3) الموقع من النطاق (20 نقطة) ───────────
    pos_score = 10.0
    hi1m = _n(item.get("high_1m"), None)
    lo1m = _n(item.get("low_1m"), None)
    if hi1m and lo1m and hi1m > lo1m:
        where = (price - lo1m) / (hi1m - lo1m) * 100  # 0 = قاع الشهر، 100 = قمته
        if where > 85:
            pos_score = 3
            facts["negatives"].append(f"السهم قرب قمة الشهر ({where:.0f}% من النطاق)")
        elif where > 65:
            pos_score = 12
            facts["positives"].append(f"السهم في الجزء العلوي من نطاق الشهر ({where:.0f}%)")
        elif where > 40:
            pos_score = 16
            facts["neutral"].append(f"السهم في منتصف نطاق الشهر ({where:.0f}%)")
        elif where > 20:
            pos_score = 18
            facts["positives"].append(f"السهم في الجزء السفلي — فرصة أفضل ({where:.0f}%)")
        else:
            pos_score = 15
            facts["positives"].append(f"السهم قرب قاع الشهر ({where:.0f}%)")

    # نطاقات بولنجر
    bbu = _n(item.get("bb_upper"), None)
    bbl = _n(item.get("bb_lower"), None)
    if bbu and bbl and bbu > bbl:
        bw = (bbu - bbl) / price * 100
        pos_score = max(0, min(20, pos_score + 2))
        if bw < 8:
            facts["positives"].append(f"نطاق بولنجر ضيق ({bw:.1f}%) — ضغط قبل اختراق")
    pos_score = max(0, min(20, pos_score))

    # ─────────── 4) الحجم والتأكيد (10 نقاط) ───────────
    vol_score = 5.0
    # ⛔ R24: التطبيع بيفرّق الصفر الحقيقي (0.0 ⇒ ضعيف 3 نقاط) عن
    #    القيم الناقصة (None/NaN/Inf ⇒ محايد 5 نقاط). الصفر قبل كده
    #    كان بيفضل 3 نقاط (سلوك صحيح) — والـNaN كان بيعدّي كأنه محايد
    #    والـInf كان بياخد أعلى شريحة (10) ⇒ رقم مش حقيقي.
    rv = _known_number(item.get("rel_volume"))
    if rv is not None:
        if rv > 1.5:
            vol_score = 9
            facts["positives"].append(f"حجم تداول أعلى من المعتاد ({rv:.1f}×)")
        elif rv > 1.0:
            vol_score = 7
        elif rv < 0.5:
            vol_score = 3
            facts["neutral"].append(f"حجم تداول ضعيف ({rv:.1f}×) — مفيش تأكيد")
    # تأكيد الاتجاه بالحجم: لو السعر طالع والحجم عالي = مؤكد
    perf1m = _n(item.get("perf_1m"), None)
    if perf1m is not None and rv is not None:
        if perf1m > 3 and rv > 1.2:
            vol_score = min(10, vol_score + 3)
            facts["positives"].append("الصعود مؤكّد بحجم تداول")
        elif perf1m < -3 and rv > 1.2:
            vol_score = max(0, vol_score - 3)
            facts["negatives"].append("الهبوط مؤكّد بحجم تداول")

    # ─────────── 5) تقييم المصدر الفني (10 نقاط) ───────────
    tv_all = _n(item.get("tv_all"), None)
    tv_ma = _n(item.get("tv_ma"), None)
    tv_osc = _n(item.get("tv_osc"), None)
    tv_score = 5.0
    if tv_all is not None:
        tv_score = max(0, min(10, 5 + tv_all * 10))
        label = "شراء قوي" if tv_all > 0.3 else ("شراء" if tv_all > 0.1 else
                ("محايد" if tv_all > -0.1 else ("بيع" if tv_all > -0.3 else "بيع قوي")))
        if tv_all > 0.15:
            facts["positives"].append(f"التقييم الفني: {label} ({tv_all:+.2f})")
        elif tv_all < -0.15:
            facts["negatives"].append(f"التقييم الفني: {label} ({tv_all:+.2f})")
        else:
            facts["neutral"].append(f"التقييم الفني محايد ({tv_all:+.2f})")

    # ─────────── 6) المخاطرة الفنية (الخصم) ───────────
    atr = _n(item.get("atr"), None)
    atr_pct = 0.0
    if atr and price:
        atr_pct = atr / price * 100
        if atr_pct > 6:
            facts["negatives"].append(f"تذبذب عالي جداً ({atr_pct:.1f}% يومياً) — مخاطرة عالية")
        elif atr_pct > 3.5:
            facts["negatives"].append(f"تذبذب عالي ({atr_pct:.1f}% يومياً)")
        elif atr_pct < 1.5:
            facts["positives"].append(f"سهم مستقر (تذبذب {atr_pct:.1f}%)")

    # ─────────── النتيجة النهائية ───────────
    total = trend_score + mom_score + pos_score + vol_score + tv_score
    total = max(0, min(100, total))

    # ⚠️ مبدأ: بيانات فنية ناقصة جداً → محايد مش ضعيف
    #    نحسب كام مؤشر متاح قبل ما نحكم
    _tech_avail = sum(1 for k in ("ema20","ema50","ema200","rsi","macd","adx","atr",
                                 "bb_upper","stoch_k","tv_all","perf_1m","rel_volume")
                      if item.get(k) is not None)
    if _tech_avail <= 2:
        total = 50.0   # محايد — مش نعرف
        trend_score = mom_score = pos_score = vol_score = tv_score = 10.0
        facts["neutral"].append(f"بيانات فنية ناقصة ({_tech_avail}/12) — التقييم محايد")

    # مستوى الثقة الفني: كام مؤشر متاح فعلاً
    avail = sum(1 for k in ("ema20","ema50","ema200","rsi","macd","macd_signal","adx",
                            "atr","bb_upper","stoch_k","tv_all","perf_1m")
                if item.get(k) is not None)
    tech_conf = min(100, avail / 12 * 100)

    # التوصية
    if total >= 70 and trend_score >= 20:
        signal = "إيجابي قوي"
    elif total >= 55:
        signal = "إيجابي"
    elif total >= 42:
        signal = "محايد"
    elif total >= 28:
        signal = "سلبي"
    else:
        signal = "سلبي قوي"

    return {
        "score": round(total, 1),
        "signal": signal,
        "breakdown": {
            "الاتجاه": round(trend_score, 1),
            "الزخم": round(mom_score, 1),
            "الموقع من النطاق": round(pos_score, 1),
            "الحجم": round(vol_score, 1),
            "تقييم المصدر": round(tv_score, 1),
        },
        "confidence": round(tech_conf, 1),
        "atr_pct": round(atr_pct, 2),
        "positives": facts["positives"][:5],
        "negatives": facts["negatives"][:5],
        "neutral": facts["neutral"][:3],
        "levels": {
            "دعم_1": item.get("pivot_s1"),
            "مقاومة_1": item.get("pivot_r1"),
            "نقطة_محايدة": item.get("pivot_m"),
            "أعلى_شهر": item.get("high_1m"),
            "أدنى_شهر": item.get("low_1m"),
        }
    }



# ════════════════════════════════════════════════════════════
# PHASE 3: محرك التحليل الأساسي — مقارنة بالقطاع + قيمة عادلة
# ════════════════════════════════════════════════════════════
SECTOR_STATS = {}


def liquidity_score(item):
    """
    السيولة مش بس الحجم — هي: هل أقدر أدخل وأخرج بسرعة بدون ما السعر يزحلق؟
    المبدأ: مستثمر بيشتري سهم مش سائل = يخسر في نقطة الدخول والخروج
    """
    if not item or not item.get("price"):
        return None
    px = item["price"]
    def num(v, default=0):
        try: return float(v) if v is not None else default
        except (TypeError, ValueError): return default

    # ⛔⛔⛔ ١٥ نوفمبر ٢٠٢٦ — F-20-12: السيولة غير المعروفة ≠ السيولة الضعيفة.
    # ⛌ العيب: مافيش بيانات سيولة خالص ⇒ الكود كان بيحسب 50 (نص الدرجة)
    #    و«مرتفع» و0% ثقة ⇒ رقم موهم بيقول «سيولة متوسطة» من غير أي دليل.
    # 📌 الحل: مافيش ولا مؤشر سيولة ⇒ الدرجة None + حالة صريحة.
    # ⛔ صفر حجم التداول قيمة حقيقية (سيولة ضعيفة) — مش «ناقصة».
    _liq_avail = sum(1 for k in ("volume", "mkt_cap", "rel_volume", "vol_5", "vol_60")
                     if item.get(k) is not None)
    if _liq_avail == 0:
        return {
            "score": None,
            "confidence": 0.0,
            "risk_level": "غير متاح",
            "risk_note": "مفيش بيانات سيولة",
            "score_status": "insufficient_liquidity_data",
            "breakdown": {"عمق السوق": 0.0, "النشاط": 0.0,
                          "سهولة التسييل": 0.0, "الاستقرار": 0.0},
            "metrics": {"القيمة السوقية": None, "حجم اليوم": None,
                        "متوسط 5 أيام": None, "متوسط 60 يوم": None,
                        "الحجم النسبي": None, "أيام لبيع 1% من السوق": None},
            "max_safe_position_egp": None,
            "positives": [], "negatives": [],
            "neutral": ["مفيش بيانات سيولة"],
        }

    vol = num(item.get("volume"))         # حجم اليوم
    vol5 = num(item.get("vol_5"))         # متوسط 5 أيام
    vol60 = num(item.get("vol_60"))       # متوسط 60 يوم
    mc = num(item.get("mkt_cap")) or None # القيمة السوقية
    # ⛔ الجولة ٢٤ (R24) — تمييز الصفر الحقيقي من القيم الناقصة:
    #    · `rv_known` = الرقم الحقيقي للنشر: الصفر يفضل 0.0 (معلوم
    #      كصفر) · وNone/NaN/Inf/نص ⇒ None (مش متاح).
    #    · `rv` = متغيّر الدرجة: **مطابق للمرجع** (صفر ⇒ ناقص ⇒ محايد 15)
    #      ⛔ تغيير درجة الصفر من محايد إلى أسوأ = تغيير سياسة ⇒
    #        محتاج إذن المالك ⇒ مسجّل كاقتراح في أدلة الجولة ٢٤.
    rv_known = _known_number(item.get("rel_volume"))   # الحجم النسبي
    rv = rv_known if rv_known else None
    atr = num(item.get("atr")) or None    # المدى الحقيقي

    pos, neg, neu = [], [], []

    # ═══ 1) عمق السوق (40 نقطة) — من القيمة السوقية ═══
    depth = 0.0
    if mc is not None:
        # القيمة السوقية أكبر = سيولة أعمق
        if   mc > 100e9: depth = 40; pos.append(f"عمق سوق ضخم ({mc/1e9:.0f} مليار)")
        elif mc > 50e9:  depth = 35; pos.append(f"عمق سوق كبير ({mc/1e9:.0f} مليار)")
        elif mc > 20e9:  depth = 29
        elif mc > 5e9:   depth = 22
        elif mc > 1e9:   depth = 14; neg.append(f"عمق سوق محدود ({mc/1e9:.1f} مليار)")
        elif mc > 300e6: depth = 8;  neg.append("سهم صغير — سيولة ضعيفة")
        else:            depth = 3;  neg.append("سهم ضئيل — مخاطرة سيولة عالية")
    else:
        depth = 20
        neu.append("القيمة السوقية غير متاحة")

    # ═══ 2) النشاط (30 نقطة) — من الحجم النسبي ═══
    activity = 15.0
    if rv is not None:
        if   rv > 2.0: activity = 28; pos.append(f"حجم تداول عالي جداً ({rv:.1f}× المتوسط)")
        elif rv > 1.3: activity = 24; pos.append(f"حجم تداول فوق المعتاد ({rv:.1f}×)")
        elif rv > 0.8: activity = 18
        elif rv > 0.4: activity = 11; neg.append(f"حجم تداول أقل من المعتاد ({rv:.1f}×)")
        else:          activity = 5;  neg.append(f"حجم تداول ضعيف جداً ({rv:.1f}×) — صعب الدخول")
    else:
        activity = 15

    # تأكيد: نشط = حجم متوسط كافي
    if vol60 and vol > 0:
        if vol60 > 1_000_000:
            activity = min(30, activity + 3)
            pos.append("حجم يومي ثابت ومريح")

    # ═══ لو متوسط 60 يوم مش موجود، نستنتجه ═══
    if not vol60 and vol and rv:
        vol60 = int(vol / rv) if rv > 0 else 0
    if not vol5 and vol and rv:
        vol5 = int(vol / rv * 1.1)   # تقدير معقول
    if not vol60:
        vol60 = vol                  # آخر resort

    # ═══ 3) سهولة التسييل (20 نقطة) — كم يوم لبيع حجم معيّن؟ ═══
    ease = 10.0
    days_to_liq = None
    if mc is not None and px and vol60:
        # نسبة حجم التداول اليومي من القيمة السوقية (Turnover)
        daily_value = vol60 * px              # قيمة التداول اليومي بالجنيه
        turnover = (daily_value / mc * 100) if mc > 0 else 0
        if turnover > 3.0: ease = 19; pos.append(f"معدل دوران مرتفع ({turnover:.1f}%)")
        elif turnover > 1.5: ease = 16
        elif turnover > 0.8: ease = 13
        elif turnover > 0.4: ease = 9;  neg.append(f"معدل دوران منخفض ({turnover:.2f}%)")
        elif turnover > 0.15: ease = 5; neg.append(f"دوران ضعيف ({turnover:.2f}%) — الخروج صعب")
        else: ease = 2; neg.append("الدوران شبه معدوم — مخاطرة سيولة عالية جداً")

        # كم يوم نبيع فيه 1% من السوق؟
        if daily_value > 0:
            days_to_liq = round((mc * 0.01) / daily_value, 1)

    # ═══ 4) استقرار السيولة (10 نقاط) — فروق الحجم ═══
    stability = 5.0
    if vol5 and vol60 and vol60 > 0:
        ratio = vol5 / vol60
        if   0.7 <= ratio <= 1.4: stability = 9; pos.append("حجم التداول مستقر")
        elif ratio < 0.5: stability = 3; neg.append("الحجم بيريد — لا أحد بيتداول")
        else: stability = 6

    # ═══ النتيجة ═══
    total = round(max(0, min(100, depth + activity + ease + stability)), 1)

    # ═══ ثقة التحليل ═══
    # 📌 نفس عدّاد المؤشرات المستخدم في فحص «مفيش بيانات سيولة» فوق.
    avail = _liq_avail
    conf = round(min(100, (avail / 5) * 100), 1)

    # ═══ مستوى المخاطر ═══
    if total >= 75:   risk = "منخفض"; risk_note = "سيولة ممتازة — تدخل وخروج سهل"
    elif total >= 55: risk = "متوسط"; risk_note = "سيولة مقبولة"
    elif total >= 35: risk = "مرتفع"; risk_note = "حذر عند الدخول"
    else:             risk = "مرتفع جداً"; risk_note = "سيولة ضعيفة — قد لا تقدر تبيع"

    # ═══ التوصية العملية ═══
    max_position = None
    if mc is not None and px and vol60:
        daily_value = vol60 * px
        if daily_value > 0:
            # ما نقدر نشتريه في يوم واحد = 10% من حجم اليوم
            safe_daily = daily_value * 0.10
            max_position = round(min(safe_daily, mc * 0.02))  # حد أقصى 2% من السوق

    return {
        "score": total,
        "confidence": conf,
        "risk_level": risk,
        "risk_note": risk_note,
        "breakdown": {
            "عمق السوق": round(depth, 1),
            "النشاط": round(activity, 1),
            "سهولة التسييل": round(ease, 1),
            "الاستقرار": round(stability, 1),
        },
        "metrics": {
            "القيمة السوقية": mc,
            "حجم اليوم": vol,
            "متوسط 5 أيام": vol5,
            "متوسط 60 يوم": vol60,
            # ⛔ R24: الرقم الحقيقي (صفر = 0.0 · مش موجود = None)
            "الحجم النسبي": rv_known,
            "أيام لبيع 1% من السوق": days_to_liq,
        },
        "max_safe_position_egp": max_position,
        "positives": pos[:5],
        "negatives": neg[:5],
        "neutral": neu[:3],
    }



# ════════════════════════════════════════════════════════════
# PHASE 9: المحرك النهائي — يدمج كل المحاور مع تعديلات
# ════════════════════════════════════════════════════════════

# الأوزان الأساسية (قابلة للتعديل في Phase 17)
# ════════════════════════════════════════════════════════════
# PHASE 17: الأوزان المعايرة (v1.1 — 2026-10-07)
# ════════════════════════════════════════════════════════════
# السبب: اختبار الضغط كشف إن السيولة والمخاطرة underrepresented.
# في السوق المصري: السيولة أهم مما هي في الأسواقdeveloped.
# سعر التحديث v1.0 → v1.1
AXIS_WEIGHTS = {
    # ⛔⛔⛔ ٢٦ أكتوبر ٢٠٢٦ — إعادة توزيع الأوزان بعد شيل الأرقام الثابتة
    # 📌 «محور المحفظة» كان رقم ثابت 70 لكل سهم (مفيش محفظة عامة)
    # 📌   ⇒ ٩٪ من النتيجة كانت وهمية ⇒ بقى وزنه ٠ (المحور مستبعد).
    # 📌 «محور الأخبار» كان 45 ثابت لكل سهم ⇒ دلوقتي رقم حقيقي
    # 📌   (نتيجة محرك الأخبار) أو مستعد لو مفيش أحداث مسجّلة.
    # 📌 الـ٩٪ اتوزعت على المحاور الستة الحقيقية (متساوية النسبة):
    "technical":    0.20,
    "fundamental":  0.24,
    "liquidity":    0.20,
    "news":         0.05,
    "sentiment":    0.04,
    "risk":         0.27,
    "portfolio":    0.00,   # ⛔ مستبعد — رقم ثابت كان بيوهم
}




def build_sector_stats(all_stocks):
    """متوسط كل قطاع — لأن 'رخيص' معناها رخيص مقارنة بالقطاع"""
    def _f(v, d=None):
        try: return float(v) if v is not None else d
        except (TypeError, ValueError): return d

    stats, by_sec = {}, {}
    for s in all_stocks:
        by_sec.setdefault(s.get("sector") or "أخرى", []).append(s)
    def med(xs):
        if not xs: return None
        xs = sorted(xs); n = len(xs)
        return xs[n//2] if n % 2 else (xs[n//2-1] + xs[n//2]) / 2
    for sec, st in by_sec.items():
        pes  = [v for v in (_f(x.get("pe")) for x in st) if v is not None and v > 0]
        roes = [v for v in (_f(x.get("roe")) for x in st) if v is not None]
        pbs  = [v for v in (_f(x.get("pb")) for x in st) if v is not None and v > 0]
        nms  = [v for v in (_f(x.get("net_margin")) for x in st) if v is not None]
        des  = [v for v in (_f(x.get("de_ratio")) for x in st) if v is not None]
        # وسائط تاريخ المخاطرة — لأن «تقلب 60%» رقم مطلق،
        # وقطاع واحد ممكن يكون كله متقلب. المقارنة النسبية هي الصح.
        vols = [v for v in (_f(x.get("vol1y")) for x in st) if v is not None and v > 0]
        # ⭐ التقلب من الـscanner (Volatility.D) — متاح لكل سهم
        #   (التاريخ السنوي vol1y مش موجود في اللوب الرئيسي).
        volsc = [v for v in (_f(x.get("volatility")) for x in st) if v is not None and v > 0]
        mdds = [v for v in (_f(x.get("mdd1y")) for x in st) if v is not None and v > 0]
        shps = [v for v in (_f(x.get("sharpe3y")) for x in st) if v is not None]
        stats[sec] = {
            "count": len(st), "with_pe": len(pes),
            "median_vol1y": round(med(vols), 2) if vols else None,
            "median_volatility": round(med(volsc), 3) if volsc else None,
            "median_mdd1y": round(med(mdds), 2) if mdds else None,
            "median_sharpe3y": round(med(shps), 2) if shps else None,
            "n_risk_hist": len(vols),
            "median_pe": round(med(pes), 2) if pes else None,
            "median_roe": round(med(roes), 2) if roes else None,
            "median_pb": round(med(pbs), 2) if pbs else None,
            "median_de_ratio": round(med(des), 2) if des else None,
            "pe_range": [round(min(pes),1), round(max(pes),1)] if pes else None,
        }
    return stats



def _compose_score(axes, liq=None, reasons=None, conf=None):
    """محصلة واحدة في مكان واحد.

    ⛌ كان في إعادة حساب في السطر ~4922 بتعملها بإيدها:
         · من غير تطبيع على الأوزان المتاحة  ⇒ بتعيد وزن محور ناقص
         · من غير سقف الخصم (min 15)          ⇒ الرقم المبلّغ ≠ موصوف الكود
         · ومن غير خصم الثقة                    ⇒ الرقم أرقام تانية خالص
       وكل ده بعد ما final_score حسبت صح — فالموقع بيعرض رقم مش
       اللي الكود بيقوله بيه. الدالة دي بقت المصدر الواحد للكل.
    """
    if reasons is None:
        reasons = []
    avail = {k: w for k, w in AXIS_WEIGHTS.items() if axes.get(k) is not None}
    wsum = sum(avail.values())
    if not wsum:
        return {"final": None, "base": 0.0, "risk_pen": 0.0,
                "liq_pen": 0.0, "conf_pen": 0.0, "contributions": []}
    # ⛔⛔⛔ ١٥ نوفمبر ٢٠٢٦ — F-20-04: محور المخاطرة الناقص بيتعامل
    #    على أنه **الأسوأ** (0 في المحصلة + خصم كامل) بدل ما وزنه
    #    يتوزّع على المحاور التانية.
    # ⛌ العيب المقاس: التوزيع كان بيعطي للسهم الناقص +28.1 نقطة ⇒
    #    كان بيتقدّم على السهم اللي بياناته كاملة وبياخد «إشارة إيجابية».
    # 📌 القاعدة: نفس البيانات + محور ناقص ⇒ لازم يطلع أسوأ أو مساوي.
    scored_axes = dict(axes)
    risk_missing = axes.get("risk") is None
    if risk_missing:
        scored_axes["risk"] = 0.0
        avail = {k: w for k, w in AXIS_WEIGHTS.items() if scored_axes.get(k) is not None}
        wsum = sum(avail.values())
    base = sum(scored_axes[k] * (avail[k] / wsum) for k in avail)

    # 📌 المساهمات الفعلية (نفس الأرقام اللي بتتوزن في النتيجة).
    # ⛔ MD-052 / AZ22-EXPLAIN-DIVERGES: الشرح كان بيعيد حساب المساهمات
    #    بإيده (أوزان غير موزّعة + 50 مخترع للمحاور الناقصة) ⇒ المجموع
    #    50.9 والرقم المنشور 75. 📌 المساهمة دي بتطلع من المحرك نفسه
    #    ⇒ إعادة تركيب الشرح = الرقم المنشور بالظبط.
    # 📌 إضافة فقط — مافيش تغيير في أي وزن أو عتبة أو رقم.
    contributions = []
    for k in avail:
        contrib = scored_axes[k] * (avail[k] / wsum)
        contributions.append({
            "axis": k,
            "score": round(scored_axes[k], 1),
            # الوزن **الفعلي** بعد التوزيع على المحاور المتاحة
            "axis_weight": round(avail[k] / wsum * 100, 1),
            "contribution": round(contrib, 1),
        })
    contributions.sort(key=lambda c: -c["contribution"])

    if risk_missing:
        risk_pen = 15.0
    else:
        risk_pen = min(15.0, (100 - axes["risk"]) * 0.18)
    liq_pen = 0.0
    if liq and liq.get("risk_level") in ("مرتفع جداً", "مرتفع"):
        liq_pen = min(6.0, (100 - liq["score"]) * 0.10)

    # الثقة بالبيانات: خصم لو ضعيفة، مكافأة صغيرة لو ممتازة
    conf_pen = 0.0
    if conf is not None:
        if conf < 50:
            conf_pen = (50 - conf) * 0.25
            reasons.append(f"البيانات ضعيفة ({conf:.0f}/100) — خصم {conf_pen:.1f}")
        elif conf > 80:
            conf_pen = -(conf - 80) * 0.05      # سالب = مكافأة

    total_penalty = max(0.0, risk_pen + liq_pen + conf_pen)
    if total_penalty > 22:                 # سقف إجمالي الخصومات
        scale = 22 / total_penalty
        risk_pen *= scale
        liq_pen *= scale
        conf_pen *= scale

    final = round(max(0, min(100, base - risk_pen - liq_pen - conf_pen)), 1)
    return {"final": final, "base": base, "risk_pen": risk_pen,
            "liq_pen": liq_pen, "conf_pen": conf_pen,
            "contributions": contributions}


def final_score(item, tech=None, fund=None, liq=None, sector_stats=None):
    """
    النتيجة النهائية = مرجّحة ثم مُعدّلة بالمخاطرة والثقة والمحفظة.
    المبدأ: ما نبغاش متوسط بسيط — الأرقام لازم تعكس الواقع.
    """
    if not item: return None

    def _n(v, d=50.0):
        """يحوّل أي قيمة لرقم — حماية كاملة من القيم النصية والقيمة الفارغة"""
        if v is None:
            return None if d is None else float(d)
        try: return float(v)
        except (TypeError, ValueError): return None if d is None else float(d)

    axes = {}
    reasons = []
    missing = []

    # ── مبدأ مهم ──
    # لو السهم مالوش بيانات في محور، ما بنحطّش له رقم وسط
    # (زي 50). الرقم ده بيكذب على المستخدم: بيقول "الجودة 50"
    # وده غلط، إحنا مش عارفين أصلاً.
    # بدل كده: بنستبعد المحور وبنقسم على اللي اتوفر بس.

    # ⚠ كل محور بيتقفل في 0-100.
    #    الفني والأساسي كانوا بياخدوا الدرجة زي ما هي من غير حدّ —
    #    ده خلّى 20 قراءة من 1480 تعدّي 100، والصفحة بتقول «من 100».
    #    ⛔ مش بنقصّ الأرقام عشان نخفي المشكلة — بنصلّح المصدر.

    # 1) الفني
    v = _n(tech["score"], None) if tech else None
    axes["technical"] = round(max(0.0, min(100.0, v))) if v is not None else None
    if v is None: missing.append("الفني")

    # 2) الأساسي
    v = _n(fund["score"], None) if fund else None
    axes["fundamental"] = round(max(0.0, min(100.0, v))) if v is not None else None
    if v is None: missing.append("الأساسي")

    # 3) السيولة
    v = _n(liq["score"], None) if liq else None
    axes["liquidity"] = round(max(0.0, min(100.0, v))) if v is not None else None
    if v is None: missing.append("السيولة")

    # 4) الأخبار — رقم حقيقي من محرك الأحداث، أو مستبعد
    #    (كان 45 ثابت لكل السهم ⇒ ٥٪ من النتيجة وهمية)
    v = _n(item.get("news_score"), None)
    if v is None:
        axes["news"] = None
        missing.append("الأخبار")
    else:
        axes["news"] = round(max(0, min(100, v)))

    # 5) المعنويات — من أداء الشهر (بحد أقصى 25% تأثير)
    p1m = _n(item.get("perf_1m"), None)
    s = 50.0
    if p1m is not None:
        s += max(-25, min(25, p1m / 2))
    axes["sentiment"] = round(max(0, min(100, s)))

    # 6) المخاطرة — أكبر محور (24%)
    #    بيتحسب من 5 مؤشرات: بيتا · نسبة الدين · التقلب · أكبر هبوط · العائد/المخاطرة
    #
    #    ⚠ ليه تاريخ السعر؟ لأن عندنا 4996 شمعة لكل سهم ومحدش كان بيستخدمها.
    #       سطر 5865-5873: vol1y · mdd1y · sharpe3y
    #
    #    ⚠ ليه مقارنة نسبية؟ «تقلب 60%» رقم مطلق. قطاع صناعي كله متقلب
    #       بيطلع رديء في رقم مطلق، وهو طبيعي. فبنقارن بوسيط القطاع
    #       (median_vol1y من build_sector_stats).
    #
    #    ⚠ ليه نسب جوه محور واحد؟ لو كل مؤشر لوحده 0-100 وبنجمع، السهم اللي
    #       كل مؤشراته متوسطة بيطلع متوسط.AlternوAlternنجمع نحن الوزن النسبي
    #       وبنطبّع على المحاور المتاحة — زي باقي المحاور بالظبط.
    risk_n = 0          # ⛔ يتعرّف قبل كل return — كان هيفصل في الفرع الناقص
    beta, de = _n(item.get("beta"), None), _n(item.get("de_ratio"), None)
    vol1y = _n(item.get("vol1y"), None)
    mdd1y = _n(item.get("mdd1y"), None)
    shp   = _n(item.get("sharpe3y"), None)

    sec_key = None
    if sector_stats:
        for k in (item.get("sector"), item.get("sectorAr")):
            if k and k in sector_stats:
                sec_key = k; break
    ss = sector_stats.get(sec_key, {}) if sec_key else {}

    # كل مؤشر بيبقى درجة 0-100 جوّه نفسه
    parts = {}
    if beta is not None:
        parts["beta"] = max(0.0, min(100.0, 100.0 - (beta - 0.3) * 125.0))
    if de is not None:
        parts["debt"] = max(0.0, min(100.0, 100.0 - min(60.0, de * 22.0)))

    # المؤشرات التاريخية — نسبية للقطاع
    def _rel(v, med, invert=True, span=None):
        """درجة 0-100 من مقارنة النسبة بالوسيط. med=None ⇒ ما فيش أساس للمقارنة."""
        if v is None or med in (None, 0): return None
        ratio = v / med
        if invert:
            # كل ما النسبة أكبر عن 1 كل ما الدرجة أقل
            return max(0.0, min(100.0, 100.0 - (ratio - 0.6) * 100.0))
        return max(0.0, min(100.0, 50.0 + (ratio - 1.0) * 100.0))

    # ⛔⛔⛔ إصلاح ٢٦ أكتوبر ٢٠٢٦ — المحور كان بيقرأ `vol1y` بس، وده
    #   مش موجود في اللوب الرئيسي (بينتج من تاريخ الشموع) ⇒ محور
    #   المخاطرة كان بيتحسب من البيتا والدين بس ⇒ ١٢١ سهم (٤٢٪) بلا
    #   محور أصلاً (لأن ما عندهمش دين) ⇒ و٣٧٪ من الوزن ناقص.
    # ✅ الحل: لو التاريخ مش موجود ⇒ نستخدم تقلب الـscanner (Volatility.D)
    #   ومقارنته بوسيط القطاع — نفس المنطق بالظبط.
    _vol_v, _vol_med = vol1y, ss.get("median_vol1y")
    if _vol_v is None:
        _vol_v = _n(item.get("volatility"), None)
        _vol_med = ss.get("median_volatility")
    a = _rel(_vol_v, _vol_med, True)
    if a is not None: parts["vol"] = a
    a = _rel(mdd1y, ss.get("median_mdd1y"), True)
    if a is not None: parts["drawdown"] = a
    a = _rel(shp, ss.get("median_sharpe3y"), False)
    if a is not None: parts["sharpe"] = a

    # ⛔⛔⛔ إصلاح ٢٦ أكتوبر ٢٠٢٦ — محور المخاطرة كان بيتحسب من مؤشر واحد
    #   (البيتا بس) ⇒ النتيجة ٠ أو ١٠٠ بالظبط (٠/١ ثنائية).
    #   ⇒ مثال حي: LUTS (بيتا سالب) ⇒ «أمان ١٠٠» وهو نزل ٣٤٪ في ٩
    #   جلسات وتذبذبه اليومي ٢٥٪! ⇒ رقم بيوهم إنه آمن.
    #   ⛔ الإصلاح: لازم **مؤشران على الأقل** يبقى المحور متاح.
    #   لو أقل ⇒ المحور مش متاح (None) ⇒ final_score بيستبعده
    #   وبيعيد توزيع الوزن على المحاور التانية (مفيش رقم وهمي).
    MIN_RISK_PARTS = 2
    if not parts:
        # ⛔ مافيش أي مؤشر مخاطرة — ما بنخمنش رقم
        axes["risk"] = None
        missing.append("المخاطرة")
    elif len(parts) < MIN_RISK_PARTS:
        axes["risk"] = None
        missing.append("المخاطرة (بيانات ناقصة)")
        reasons.append(
            "مؤشرات المخاطرة المتاحة " + str(len(parts)) +
            " بس ⇒ المحور استُبعد من النتيجة بدل ما يطلع ٠ أو ١٠٠"
        )
    else:
        # الأوزان النسبية — البيتا والدين أساس ثابت، التاريخ مكمل
        RW = {"beta": 0.22, "debt": 0.18, "vol": 0.26,
              "drawdown": 0.22, "sharpe": 0.12}
        num = sum(parts[k] * RW[k] for k in parts)
        den = sum(RW[k] for k in parts)      # ⛔ مش 1.0 — تطبيع زي باقي المحاور
        axes["risk"] = round(max(0, min(100, num / den)))
        risk_n = len(parts)   # كم مؤشر دخل فعلاً — للتقارير

    # 7) ملاءمة المحفظة — ⛔ مستبعد
    #    (كان 70 ثابت لكل السهم ⇒ ٩٪ من النتيجة وهمية)
    #    المحورDepend على محفظة المستخدم ⇒ ما ينفعش يدخل في نتيجة
    #    عامة. لو عايزينه يرجع: طبّقه كطبقة فوق النتيجة، مش جواها.
    axes["portfolio"] = None
    missing.append("المحفظة")

    # ═══ المحصلة المرجّحة ═══
    # ⚠️ لو محور ناقص، ما بنحسبوش بإيده — بنحسب على المتاح بس
    #    وبنعدّل الأوزان عشان المجموع يفضل 100%.
    avail = {k: w for k, w in AXIS_WEIGHTS.items() if axes.get(k) is not None}
    wsum = sum(avail.values())

    if wsum <= 0:
        # ⛔ مافيش ولا محور واحد متاح — مش من حقنا نطلع تقييم
        return {
            "code": item.get("code"), "name": item.get("name"),
            "score": None, "noData": True,
            "noDataNote": "مفيش بيانات كافية لحساب التقييم",
            "score_status": "no_data",
            "rank_eligible": False,
            "axes": {k: v for k, v in axes.items() if v is not None},
            "missing_axes": missing,
            "reasons": reasons, "decision": "غير كافٍ للقرار",
        }

    # ═══ المحصلة — كلها في الدالة الواحدة ═══
    # الثقة بتدخل جوه الدالة كمان عشان متبقاش زيادة برّه
    # ⛔⛔⛔ ١٥ نوفمبر ٢٠٢٦ — F-20-13: الصفر يبقى صفر (مش 60).
    conf = _confidence_value(item.get("data_confidence"), 60.0)
    adj = _compose_score(axes, liq, reasons, conf)
    final = adj["final"]

    # ═══ الثقة الإجمالية ═══
    # الثقة = (جودة البيانات + تغطية المحاور) / 2
    # ⚠ كان مكتوب `axes[k] != 50` كاختصار لـ«فيه بيانات».
    #   ده غلط: السهم اللي درجته الحقيقية 50 بالظبط بيتحسب ناقص،
    #   فبيقلل ثقته. الشرط الصح هو None مش رقم.
    axis_coverage = sum(1 for k in ("technical", "fundamental", "liquidity", "risk")
                        if axes.get(k) is not None)
    coverage_pct = (axis_coverage / 4) * 100
    overall_conf = round((conf * 0.6) + (coverage_pct * 0.4), 1)

    # ═══ القرار ═══
    # ⚠️ قاعدة: "بيع" لازم يكون بسبب واضح من الأرقام
    #    لو البيانات ناقصة → القرار "غير كافي" مش "بيع"
    # ⛔⛔⛔ إصلاح ٢٦ أكتوبر ٢٠٢٦ — خلط بين «مفيش بيانات» و«بيانات ضعيفة»
    #   كان الشرط (الأساسي ≥ 40) ⇒ أي سهم بياناته **موجودة بس ضعيفة**
    #   كان بيطلع «بيانات غير كافية» ⇒ و196 من 284 سهم قالوا كده!
    #   ⇒ دلوقتي: «غير كافية» = البيانات **ناقصة** بس.
    #   والبيانات الضعيفة بتأثر في الدرجة (وزن 24%) وفي القرار نفسه.
    fund_missing = axes.get("fundamental") is None
    tech_missing = axes.get("technical") is None
    risk_v = axes.get("risk")

    # ⛔⛔⛔ ١٥ نوفمبر ٢٠٢٦ — F-20-04: سياسة نقص البيانات (الخيار A).
    # ⛌ العيب المقاس: محور المخاطرة الناقص كان بيوزّع_weight على
    #    المحاور التانية ⇒ السهم الناقص بياخد +28.1 نقطة و«إشارة
    #    إيجابية» وبيترتب فوق السهم الحقيقي.
    # 📌 السياسة المعتمدة (الخيار A): الرقم يبقى مؤشراً تشخيصياً
    #    محسوباً على المتاح، لكن:
    #      · القرار = «بيانات غير كافية» (مش إشارة إيجابية)
    #      · rank_eligible = False (ما يدخلش قوائم الفرص/الترتيب المؤهل)
    #      · score_status = «insufficient_risk» (السبب واضح للمستخدم)
    # ⛔ ملاحظة: قيمة المخاطرة 0 قيمة حقيقية (مخاطرة شديدة) — مش نقص.
    risk_missing = (risk_v is None)
    rank_eligible = not (risk_missing or fund_missing or tech_missing)

    if risk_missing:
        decision = "بيانات غير كافية"
        decision_why = "بيانات المخاطرة غير كافية — لا يمكن الحكم على السهم"
    elif risk_v < 35:
        decision = "إشارة سلبية"
        decision_why = "مخاطرة عالية جداً"
    elif fund_missing or tech_missing:
        decision = "بيانات غير كافية"
        decision_why = "البيانات ناقصة — لا يمكن الحكم على السهم بثقة"
    elif final >= 78 and (axes.get("technical") or 0) >= 50 and (axes.get("fundamental") or 0) >= 60:
        decision = "إشارة إيجابية"
        decision_why = "أساسيات قوية واتجاه إيجابي"
    elif final >= 65:
        decision = "إشارة إيجابية"
        decision_why = "نتيجة جيدة عموماً"
    elif final >= 52:
        decision = "إشارة محايدة"
        decision_why = "محايد — في انتظار"
    elif (axes.get("fundamental") or 0) >= 65:
        decision = "إشارة محايدة"
        decision_why = "أساسيات كويسة"
    else:
        decision = "إشارة سلبية"
        decision_why = "نتيجة ضعيفة ومخاطرة عالية"

    if missing:
        # reason بدون ما نكسر أي حاجة موجودة
        reasons.append(
            f"محاور ناقصة ({', '.join(missing)}) — التقييم محسوب على المتاح بس"
        )

    # ═══ مستوى المخاطرة ═══
    # ⛌ الكود القديم كان يعمل مقارنة على axes["risk"] مباشرة.
    #    لو المحور None (كل المؤشرات ناقصة) ⇒ TypeError بيقع،
    #    والـtry/except في الإنتاج كان بيبلعه صامت — فالسهم
    #    كان بيطلع من غير تقييم نهائي ومن غير رسالة خطأ.
    _rv = axes.get("risk")
    if _rv is None:
        risk_level = "غير متاح"      # ⛔ مش رقم مخترع
    elif _rv >= 70: risk_level = "منخفض"
    elif _rv >= 50: risk_level = "متوسط"
    elif _rv >= 30: risk_level = "مرتفع"
    else: risk_level = "مرتفع جداً"

    return {
        "final_score": final,
        "confidence": overall_conf,
        "axes": axes,
        "weights": AXIS_WEIGHTS,
        # ⛔⛔⛔ حالة التقييم (F-20-04) — بتتقرأ في كل مسارات الترتيب.
        # 📌 «ok» = البيانات الجوهرية صالحة · «insufficient_risk» =
        # 📌 محور المخاطرة ناقص ⇒ الرقم تشخيصي بس مش مؤهل للترتيب.
        "score_status": ("insufficient_risk" if risk_missing
                         else ("insufficient_data" if not rank_eligible else "ok")),
        "rank_eligible": rank_eligible,
        "adjustments": {
            "أساسي مرجّح": round(adj["base"], 1),
            "خصم المخاطرة": round(-adj["risk_pen"], 1),
            "خصم السيولة": round(-adj["liq_pen"], 1),
            "خصم الثقة": round(-adj["conf_pen"], 1),
        },
        # كم مؤشر دخل في محور المخاطرة — 5 (بيتا·دين·تقلب·هبوط·شارپ)
        "risk_inputs": risk_n,
        "decision": decision,
        "decision_why": decision_why,
        "risk_level": risk_level,
        "reasons": reasons,
    }



# ════════════════════════════════════════════════════════════
# PHASE 6: محرك المعنويات — مع قاعدة صارمة: ما يتحكمش في القرار
# ════════════════════════════════════════════════════════════
SENTIMENT_CAP = 25   # أقصى تأثير للمعنويات على النتيجة النهائية (%)
