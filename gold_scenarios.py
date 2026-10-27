# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
محرك السيناريوهات لذهب الادخار — OCTA (٢٧ أكتوبر ٢٠٢٦)
═══════════════════════════════════════════════════════════════════════
📌 الهدف: يجاوب على سؤال المستخدم الحقيقي:
   «لو أنا بادخّر، السعر رايح فين وإيه اللي يخلّيني أعرف إن سؤالي اتغيّر؟»

⛔⛔⛔ القواعد الحاكمة (من产品规格 + مراجعة نور-الكوانت):
 ① **مفيش احتمالات ولا نسب مختلقة** — ولا «احتمال ٦٠٪ الصعود».
    بدلها: **شرط Trigger قابل للقياس** (إغلاق فوق/تحت مستوى محدد ومرصود).
 ② **مفيش «ضمان» ولا «مضمون» ولا توصية شراء/بيع** — تحليل مش نصيحة.
 ③ **كل هدف = مستوى مرصود فعلي** (دعم/مقاومة من ٥٠٠ شمعة) — مش نسبة مختلقة.
 ④ **كل رقم ليه مصدر** — واللي مش متاح ⇒ `None` + سبب (مش صفر).
 ⑤ **مفيش look-ahead**: كل الإحصا��ات محسوبة على نافذة **قبل** اللحظة دي.
 ⑥ **العلاقة بين الذهب والدولار آلية** (هوية لوغاريتمية) ⇒ أي رقم ليه
    المصدر ده مش توقّع.
 ⑦ **الادخار بالحقيقة**: العائد الاسمي + العائد **الحقيقي بعد التضخم**،
    والإanner إن “×١٩ اسمي” ممكن يبقى “×٥ حقيقي” — وده اللي المستخدم لازم يعرفه.
"""
import math
import datetime
import importlib


# ═══════════════ أدوات ═══════════════
def _get(mod):
    return importlib.import_module(mod)


def _r(x, n=2):
    """تقريب آمن — None بيفضل None (مفيش صفرات كاذبة)."""
    if x is None:
        return None
    try:
        if isinstance(x, bool):
            return None
        return round(float(x), n)
    except Exception:
        return None


def _pct(a, b):
    """نسبة التغير من a إلى b."""
    if a is None or b is None or not a:
        return None
    try:
        return (float(b) / float(a) - 1.0) * 100.0
    except Exception:
        return None


def _mid(z):
    """منتصف منطقة الدعم/المقاومة."""
    for k in ("center", "mid"):
        v = (z or {}).get(k)
        if v is not None:
            return float(v)
    lo = (z or {}).get("low")
    hi = (z or {}).get("high")
    if lo is not None and hi is not None:
        return (float(lo) + float(hi)) / 2.0
    return None


def _fmt(v, dec=0):
    if v is None:
        return "—"
    try:
        return ("{:,.%df}" % dec).format(float(v))
    except Exception:
        return "—"


# ═══════════════ تجميع البيانات ═══════════════
def _levels(an):
    """
    📌 مستويات الدعم/المقاومة من محرك التحليل الفني (`sr`).
    ⛔ الشكل: {support:[...], resistance:[...], nearest_support, nearest_resistance,
       no_resistance_above, at_period_high, window}
    """
    sr = (an or {}).get("sr") or {}
    cur = sr.get("current") or (an or {}).get("current")
    sup = [z for z in (sr.get("support") or []) if isinstance(z, dict)]
    res = [z for z in (sr.get("resistance") or []) if isinstance(z, dict)]
    sup_b = sorted([z for z in sup if cur is not None and _mid(z) is not None
                    and _mid(z) <= cur], key=lambda z: -_mid(z))
    res_a = sorted([z for z in res if cur is not None and _mid(z) is not None
                    and _mid(z) >= cur], key=lambda z: _mid(z))
    return {"supports_below": sup_b, "resistances_above": res_a,
            "all_supports": sorted(sup, key=lambda z: -(_mid(z) or 0)),
            "all_resistances": sorted(res, key=lambda z: _mid(z) or 0),
            "nearest_support": sr.get("nearest_support"),
            "nearest_resistance": sr.get("nearest_resistance"),
            "no_resistance_above": sr.get("no_resistance_above"),
            "at_period_high": sr.get("at_period_high"),
            "no_resistance_note": sr.get("no_resistance_note"),
            "window": sr.get("window"), "window_note": sr.get("window_note"),
            "current": cur}


def _band_stays(series, lo, hi, lookback=500):
    """
    ⛔ إحصاء **مرصود**: في آخر N جلسة، كام مرة وكتير كان السعر **جوّه** النطاق
       [lo, hi]؟ وكمان متوسط مدة كل بقعة (أيام) والنسبة.
    📌 ده **تكرار تاريخي** (مش احتمال مستقبلي).
    """
    out = {"sessions": 0, "inside": 0, "inside_pct": None, "stays": 0,
           "avg_stay_days": None, "max_stay_days": None, "lookback": 0}
    if lo is None or hi is None or lo > hi:
        return out
    s = [r for r in (series or []) if r.get("gram") is not None]
    if len(s) < 30:
        return out
    win = s[-lookback:]
    out["sessions"] = len(win)
    out["lookback"] = len(win)
    inside = 0
    runs = []
    cur = 0
    for r in win:
        g = r["gram"]
        if lo <= g <= hi:
            inside += 1
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    out["inside"] = inside
    out["inside_pct"] = round(inside * 100.0 / len(win), 1) if win else None
    out["stays"] = len(runs)
    if runs:
        out["avg_stay_days"] = round(sum(runs) / float(len(runs)), 1)
        out["max_stay_days"] = max(runs)
    return out


def _cagr(start, end, years):
    if not start or not end or not years or years <= 0:
        return None
    try:
        return (math.pow(float(end) / float(start), 1.0 / float(years)) - 1.0) * 100.0
    except Exception:
        return None


def _cpi_eg():
    """تضخم مصر من البنك الدولي (سنوي) — لازم للعائد الحقيقي."""
    try:
        gm = _get("gold_macro")
        r = gm.world_bank("FP.CPI.TOTL")
        pts = [(str(d)[:4], float(v)) for d, v in (r.get("points") or [])]
        return {"series": sorted(pts), "source": "البنك الدولي (World Bank) — CPI مصر",
                "source_url": "https://api.worldbank.org/v2/country/EGY/indicator/FP.CPI.TOTL"}
    except Exception as e:
        return {"series": [], "error": str(e)[:80]}


# ═══════════════ السيناريوهات ═══════════════
def _sc_bull(an, lv, series, cur):
    """سيناريو صاعد — شرطه اختراق المقاومة المرصودة."""
    res = (lv.get("resistances_above") or [lv.get("nearest_resistance")])[0]
    sup = (lv.get("supports_below") or [lv.get("nearest_support")])[0]
    trig = None
    targets = []
    if res:
        trig = {"level": _r(res.get("high"), 2),
                "zone": [_r(res.get("low"), 2), _r(res.get("high"), 2)],
                "text": ("إغلاق يومي فوق %s ج.م (الحاجز العلوي لمنطقة المقاومة "
                         "المركزية %s)" % (_fmt(res.get("high")), _fmt(_mid(res)))),
                "evidence": res.get("why")}
    # الهدف: المقاومة اللي فوقها (أو القمة التاريخية لو مفيش)
    nxt = (lv.get("resistances_above") or [None])
    if len(nxt) > 1:
        z = nxt[1]
        targets.append({"level": _r(_mid(z), 2),
                        "basis": "المقاومة المرصودة الأعلى تالياً",
                        "pct_from_current": _r(_pct(cur, _mid(z)), 2)})
    else:
        targets.append({"level": None,
                        "basis": "مفيش مقاومة مرصودة فوق السعر",
                        "note": "المستوى الأعلى المرصود في النافذة هو %s ج.م" % _fmt(
                            max([r["gram"] for r in series[-500:]] or [None]))})
    inv = None
    if sup:
        inv = {"level": _r(sup.get("low"), 2),
               "text": ("إغلاق يومي تحت %s ج.م (قاع أقرب منطقة دعم)"
                        % _fmt(sup.get("low"))),
               "evidence": sup.get("why")}
    return {
        "key": "bull", "name_ar": "سيناريو صاعد",
        "state": ("السعر فوق المتوسطات القصيرة والمتوسطة، والاتجاه العام عرضي "
                  "والدعم %s ج.م تحته." % _fmt(_mid(sup) if sup else None)),
        "trigger": trig,
        "targets": targets,
        "invalidation": inv,
        "horizon": ("مش محدّد مسبقاً — بيتحدد بالمحرك: آخر اختبار لهذا المستوى "
                    "كان قبل %s يوم%s."
                    % (res.get("age_days") if res else "—",
                       "، ومفيش مقاومة مرصودة فوقه" if lv.get("no_resistance_above")
                       else "")),
        "what_to_watch": [
            "إغلاق يومي فوق حاجز المقاومة (مش لمسة)",
            "قوة الدولار مقابل الجنيه (المحرك الأقوى دلوقتي)",
            "استمرار البنية: قمة أعلى من اللي قبلها",
        ],
        "caveat": ("شرط مش توقّع — لو الإغلاق ما获得了ش فوق المستوى ده، "
                   "السيناريو ملغي."),
    }


def _sc_bear(an, lv, series, cur):
    """سيناريو هابط — شرطه كسر الدعم المرصود."""
    sup = (lv.get("supports_below") or [lv.get("nearest_support")])[0]
    res = (lv.get("resistances_above") or [lv.get("nearest_resistance")])[0]
    trig = None
    targets = []
    if sup:
        trig = {"level": _r(sup.get("low"), 2),
                "zone": [_r(sup.get("low"), 2), _r(sup.get("high"), 2)],
                "text": ("إغلاق يومي تحت %s ج.م (قاع أقرب منطقة دعم)"
                         % _fmt(sup.get("low"))),
                "evidence": sup.get("why")}
        nxt = [z for z in (lv.get("supports_below") or [])[1:]]
        if nxt:
            z = nxt[0]
            targets.append({"level": _r(_mid(z), 2),
                            "basis": "الدعم المرصود التالي",
                            "pct_from_current": _r(_pct(cur, _mid(z)), 2)})
        else:
            targets.append({"level": None,
                            "basis": "مفيش دعم مرصود تحت السعر",
                            "note": "أرضي�� مرصودة في النافذة %s ج.م" % _fmt(
                                min([r["gram"] for r in series[-500:]] or [None]))})
    inv = None
    if res:
        inv = {"level": _r(res.get("high"), 2),
               "text": ("إغلاق يومي فوق %s ج.م (المقاومة القريبة)"
                        % _fmt(res.get("high"))),
               "evidence": res.get("why")}
    return {
        "key": "bear", "name_ar": "سيناريو هابط",
        "state": ("السعر فوق الدعم %s ج.م. لو الكسر حصل، المسافة للهدف التالي "
                  "تتحدد من مستويات الدعم المرصودة." % _fmt(_mid(sup) if sup else None)),
        "trigger": trig,
        "targets": targets,
        "invalidation": inv,
        "horizon": ("بيتبع سرعة الكسر: آخر اختبار للدعم ده كان قبل %s يوم ⇒ "
                    "المستوى ده بيتفاعل مع السوق بسرعة."
                    % (sup.get("age_days") if sup else "—")),
        "what_to_watch": [
            "إغلاق يومي تحت قاع الدعم (مش لمسة)",
            "تراجع سعر الصرف (يرفع الجرام ⇒ يخفي الكسر)",
            "الدولار هو المحرك الأكبر دلوقتي (شوف تفكيك الحركة)",
        ],
        "caveat": ("شرط مش توقّع — الكسر لو获得了ش، السيناريو ملغي. "
                   "والدولار ممكن يعوّض جزء من كسر الذهب."),
    }


def _sc_range(an, lv, series, cur):
    """سيناريو عرضي — النطاق المرصود + إحصاء البقع داخله (مرصود)."""
    sup = (lv.get("supports_below") or [lv.get("nearest_support")])[0]
    res = (lv.get("resistances_above") or [lv.get("nearest_resistance")])[0]
    lo = sup.get("low") if sup else None
    hi = res.get("high") if res else None
    stays = _band_stays(series, lo, hi)
    width_pct = _pct(lo, hi)
    return {
        "key": "range", "name_ar": "سيناريو عرضي (نطاق)",
        "state": ("البنية الحالية نطاق عرضي (قمم أدنى وقيعان أعلى) — والدعم %s "
                  "والمقاومة %s." % (_fmt(_mid(sup) if sup else None),
                                     _fmt(_mid(res) if res else None))),
        "band": {"low": _r(lo, 2), "high": _r(hi, 2),
                 "width_egp": _r((hi - lo) if (hi is not None and lo is not None) else None, 2),
                 "width_pct": _r(width_pct, 2),
                 "current_inside": (lo is not None and hi is not None
                                    and lo <= cur <= hi)},
        "historical": {
            "sessions_checked": stays["sessions"],
            "inside_sessions": stays["inside"],
            "inside_pct": stays["inside_pct"],
            "stays_count": stays["stays"],
            "avg_stay_sessions": stays["avg_stay_days"],
            "max_stay_sessions": stays["max_stay_days"],
            "note": ("⛔ ده **تكرار تاريخي مرصود** (كام مرة كان السعر جوّه النطاق "
                     "في آخر %s جلسة) — مش احتمال إن الجاي هيبقى كده."
                     % stays["sessions"]),
        },
        "trigger": {"text": "السعر يفضل جوّه النطاق %s – %s ج.م" % (_fmt(lo), _fmt(hi))},
        "targets": [{"level": _r(hi, 2), "basis": "حاجز النطاق العلوي"},
                    {"level": _r(lo, 2), "basis": "حاجز النطاق السفلي"}],
        "invalidation": {"text": "إغلاق يومي خارج النطاق"},
        "horizon": ("بشكل تاريخي: البقع جوّه نطاق زي ده كانت بتبقى في المتوسط "
                    "%s جلسة." % stays["avg_stay_days"]),
        "what_to_watch": [
            "هل الاختراق حقيقي فوق المقاومة ولا كاذب؟",
            "التضخم المصري وسعر الفائدة (بيحددوا اتجاه الدولار)",
        ],
        "caveat": ("النطاق ده من ٥٠٠ شمعة — لو السعر كسره بإغلاق، النطاق بيبقى "
                   "قديم."),
    }


def _sc_currency(fx_an, cur_gram, cur_fx, attribution):
    """
    📌 سيناريو العملة: علاقة **آلية** مش توقّع.
       الهوية اللوغاريتمية: log(جرام) = log(ذهب) + log(جنيه/دولار)
       ⇒ لو الذهب ثابت ⇒ أي تغيّر في الدولار ينتقل للجرام بنسبة قريبة ١:١.
    """
    if not cur_gram or not cur_fx:
        return None
    out = {"key": "currency", "name_ar": "محرك العملة (الدولار)",
           "state": None, "steps": [], "note": None}
    lv = _levels(fx_an)
    sup = (lv.get("supports_below") or [lv.get("nearest_support")])[0]
    res = (lv.get("resistances_above") or [lv.get("nearest_resistance")])[0]
    parts = []
    if attribution:
        parts.append("من تفكيك الحركة: الذهب %+.0f ج.م والدولار %+.0f ج.م "
                     "(إجمالي %+.0f ج.م)."
                     % (attribution.get("gold_points") or 0,
                        attribution.get("fx_points") or 0,
                        attribution.get("total_change_gram") or 0))
    for pct_move in (-5.0, -2.0, 2.0, 5.0):
        new_fx = cur_fx * (1.0 + pct_move / 100.0)
        # ⛔ الجزء الميكانيكي فقط: Δlog(جرام) = Δlog(دولار) ⇒ جرام جديد
        new_gram = cur_gram * (1.0 + pct_move / 100.0)
        parts.append({
            "fx_move_pct": pct_move,
            "fx_new": _r(new_fx, 3),
            "gram_if_gold_flat": _r(new_gram, 1),
            "gram_delta_egp": _r(new_gram - cur_gram, 1),
            "pct_from_current": _r(_pct(cur_gram, new_gram), 2),
        })
    out["state"] = ("سعر الدولار %s جنيه/دولار. لو الذهب ما اتغيّرش، أي تغيّر "
                    "في الدولار بينتقل للجرام بنسبة ١:١ تقريباً (هوية لوغاريتمية)."
                    % _fmt(cur_fx, 3))
    out["steps"] = parts
    out["note"] = ("⛔ ده **حساب آلي** من الهوية log(جرام) = log(ذهب) + log(دولار) "
                   "— مش توقّع. والذهب ممكن يتحرك في الاتجاه المعاكس فيغطي "
                   "نص التغيّر أو كله (ده اللي happened في الـ30 يوم الأخيرة).")
    out["levels"] = {
        "support_egp_per_usd": _r(_mid(sup), 4) if sup else None,
        "resistance_egp_per_usd": _r(_mid(res), 4) if res else None,
        "support_note": sup.get("why") if sup else None,
        "resistance_note": res.get("why") if res else None,
    }
    return out


# ═══════════════ العائد الاسمي vs الحقيقي ═══════════════
def _savings(series, cpi):
    """
    📌 قلب تبويب «الادخار»: العائد الاسمي (من السلسلة) مقابل العائد **الحقيقي**
       بعد التضخم المصري (من البنك الدولي) + «فلوسك لو ادخرت X».
    ⛔⛔ **القاعدة الذهبية:** الاسمي والتضخم لازم يكونوا على **نفس الفترة
       بالظبط** — غير كده بتطلع أرقام سخيفة (زي ×٤٥ حقيقي!).
    📌 التضخم سنوي وآخر سنة متاحة ٢٠٢٥ ⇒ الحقيقي بيتحسب على **آخر سنة كاملة
       متاحة** (وليس على سنة ٢٠٢٦ اللي لسه موشورة) ⇒ ونعلن ده.
    """
    s = [r for r in (series or []) if r.get("gram") is not None]
    if len(s) < 30:
        return {"ok": False, "error": "السلسلة قصيرة"}
    last = s[-1]
    cpi_map = {y: v for y, v in (cpi.get("series") or [])}
    years = sorted(cpi_map.keys())
    if not years:
        return {"ok": False, "error": "تضخم مصر غير متاح ⇒ العائد الحقيقي مش متاح",
                "rows": [], "inflation_source": cpi.get("source")}
    y_last = years[-1]
    out = []
    for yrs in (1, 3, 5, 10, 20):
        # ── نافذة الاسمية: من (دلوقتي − N سنة) → النهارده ──
        target_d = (datetime.date.fromisoformat(last["d"]) -
                    datetime.timedelta(days=int(yrs * 365.25)))
        cand = [r for r in s if r["d"] <= target_d.isoformat()]
        if not cand:
            continue
        r0 = cand[-1]
        yrs_real = (datetime.date.fromisoformat(last["d"]) -
                    datetime.date.fromisoformat(r0["d"])).days / 365.25
        if yrs_real < 0.5:
            continue
        nom = _pct(r0["gram"], last["gram"])
        cagr_nom = _cagr(r0["gram"], last["gram"], yrs_real)

        # ── نافذة «الحقيقي»: لازم تتقابل مع الـCPI ──
        y0 = r0["d"][:4]
        note_real = None
        infl = None
        cpi_used = None
        nom_m = None
        yrs_m = None
        win_from = win_to = None
        if int(y_last) < int(y0):
            # ⛔ نافذة أقدم من آخر سنة تضخم ⇒ الحقيقي مش متاح
            note_real = ("سلسلة التضخم تبدأ %s ⇒ ما ينفعش نقيس العائد الحقيقي "
                         "على %s سنة" % (years[0], yrs))
        else:
            # ⛔ بداية نافذة التضخم = **نفس بداية نافذة الجنيه** (مش أول السلسلة!)
            def _first_row(d0, d1):
                c = [r for r in s if d0 <= r["d"] <= d1]
                return c[0] if c else None
            _win_end = y_last + "-12-31"
            r_start = _first_row(r0["d"], _win_end)
            if r_start:
                _span_days = (datetime.date.fromisoformat(_win_end) -
                              datetime.date.fromisoformat(r_start["d"])).days
                if _span_days < 300:
                    # ⛔ النافذة اقل من سنة ⇒ خد آخر سنة كاملة تانية
                    _prev = str(int(y_last) - 1)
                    # ⛔ نافذة سنة كاملة: من آخر يوم في السنة السابقة → آخر السنة
                    r_start = _first_row(_prev + "-12-31", _win_end)
                    y0 = _prev
                    note_real = ("محسوب على آخر سنة كاملة متاحة (%s) — "
                                 "سنة %s لسه موشورة."
                                 % (y_last, last["d"][:4]))
                base = cpi_map.get(y0)
                end = cpi_map.get(y_last)
                if not base:
                    note_real = (note_real or
                                 ("سلسلة التضخم المتاحة تبدأ %s ⇒ ما ينفعش نقيس "
                                  "العائد الحقيقي على نافذة تبدأ %s"
                                  % (years[0], y0)))
                # ⛔⛔ البسط لازم يكون على **نفس نافذة التضخم** (لحد آخر سنة
                #    تضخم) مش لآخر السلسلة — غير كده ٣٠٠ يوم بتتقسم على صفر
                #    تضخم والرقم الحقيقي بيطلع أعلى بـ~١٠٪ (نور-الكوانت).
                _ge = [r for r in s if r["d"] <= (y_last + "-12-31")]
                g_end = _ge[-1] if _ge else None
                if base and end and r_start["gram"] and g_end and g_end["gram"]:
                    infl = (end / base - 1.0) * 100.0
                    cpi_used = "%s → %s" % (y0, y_last)
                    win_from = r_start["d"]
                    win_to = g_end["d"]          # ⛔ تاريخ فعلي مش 31 ديسمبر
                    nom_m = _pct(r_start["gram"], g_end["gram"])
                    yrs_m = (datetime.date.fromisoformat(win_to) -
                             datetime.date.fromisoformat(r_start["d"])).days / 365.25
        real_ret = None
        cagr_real = None
        if infl is not None and nom_m is not None:
            real_ret = ((1.0 + nom_m / 100.0) / (1.0 + infl / 100.0) - 1.0) * 100.0
            if yrs_m and yrs_m > 0.5:
                cagr_real = ((1.0 + real_ret / 100.0) ** (1.0 / yrs_m) - 1.0) * 100.0
        # ── مثال «ادخرت ١٠٠ ألف» ──
        ex = None
        if r0["gram"]:
            g_buy = 100000.0 / r0["gram"]
            now_val = g_buy * last["gram"]
            real_val = None
            real_date = None
            if infl is not None and nom_m is not None and win_to:
                # ⛔ القيمة الحقيقية على **نفس نافذة التضخم** (مش لآخر السلسلة)
                _ge2 = [r for r in s if r["d"] <= win_to]
                if _ge2:
                    real_date = _ge2[-1]["d"]
                    real_val = (g_buy * _ge2[-1]["gram"]) / (1.0 + infl / 100.0)
            ex = {"amount_egp": 100000.0,
                  "grams_bought": _r(g_buy, 2),
                  "value_now_egp": _r(now_val, 0),
                  "value_now_real_egp": _r(real_val, 0),
                  "value_now_real_date": real_date,
                  "note": ("«القيمة الحقيقية» = القيمة الاسمية عند نهاية نافذة "
                           "التضخم (%s) ÷ تراكم التضخم المصري في نفس الفترة."
                           % (real_date or "—"))}
        out.append({
            "years": round(yrs_real, 1),
            "from": r0["d"], "to": last["d"],
            "gram_start": _r(r0["gram"], 2), "gram_end": _r(last["gram"], 2),
            "nominal_pct": _r(nom, 1),
            "nominal_cagr_pct": _r(cagr_nom, 2),
            "times": _r(last["gram"] / r0["gram"], 2),
            "real": {
                "window_from": win_from, "window_to": win_to,
                "years": _r(yrs_m, 1) if yrs_m else None,
                "nominal_pct": _r(nom_m, 1) if nom_m is not None else None,
                "inflation_pct": _r(infl, 1) if infl is not None else None,
                "inflation_window": cpi_used,
                "real_pct": _r(real_ret, 1) if real_ret is not None else None,
                "real_cagr_pct": _r(cagr_real, 2) if cagr_real is not None else None,
                "real_times": _r((1.0 + real_ret / 100.0), 2) if real_ret is not None else None,
                "note": note_real,
            },
            "example": ex,
        })
    return {
        "ok": True,
        "rows": out,
        "inflation_source": cpi.get("source"),
        "inflation_source_url": cpi.get("source_url"),
        "inflation_last_year": y_last,
        "inflation_years_available": len(years),
        "caveat": ("التضخم المصري من البنك الدولي (سنوي، آخر سنة %s). العائد "
                   "الحقيقي بيتحسب على نافذة **تتقابل** مع نافذة التضخم — "
                   "مش على نفس النافذة الاسمية (لأن آخر سنة تضخم موشورة)."
                   % y_last),
    }


# ═══════════════ الخلاصة التحليلية ═══════════════
def _summary(an, fx_an, attribution, savings, macro, local, cur, cur_fx):
    """الخلاصة: ٥ أسطر حتمية مبنية على الأرقام — مش نص إنشائي."""
    lines = []
    tr = ((an or {}).get("trend") or {})
    lines.append("الحالة: الاتجاه %s (قصير %s · متوسط %s · طويل %s) والجرام %s ج.م."
                 % (tr.get("overall") or "—", tr.get("short", {}).get("label") or "—",
                    tr.get("medium", {}).get("label") or "—",
                    tr.get("long", {}).get("label") or "—", _fmt(cur)))
    if attribution:
        lines.append("محركة الحركة: %s — الذهب %+.0f ج.م والدولار %+.0f ج.م "
                     "(إجمالي %+.0f ج.م)."
                     % (attribution.get("driver") or "—",
                        attribution.get("gold_points") or 0,
                        attribution.get("fx_points") or 0,
                        attribution.get("total_change_gram") or 0))
    ftr = ((fx_an or {}).get("trend") or {})
    lines.append("الدولار: %s جنيه/دولار — اتجاهه %s، وده أقوى محرك للجرام دلوقتي."
                 % (_fmt(cur_fx, 2), ftr.get("overall") or "—"))
    if savings.get("rows"):
        r10 = next((r for r in savings["rows"] if r["years"] >= 9), None)
        if r10:
            _rl = r10.get("real") or {}
            lines.append("الادخار: اسمي ×%s على %s سنة (لحتى %s) — والحقيقي بعد "
                         "التضخم %s على %s سنة (نافذة التضخم %s). النافذتين مختلفين: "
                         "آخر سنة تضخم متاحة %s."
                         % (r10.get("times"), r10.get("years"), r10.get("to"),
                            ("×%s" % _rl.get("real_times")) if _rl.get("real_times")
                            else "غير متاح",
                            _rl.get("years"), _rl.get("inflation_window"),
                            savings.get("inflation_last_year")))
    if local and local.get("gram_24_reference"):
        lines.append("السعر المرصود دلوقتي: %s ج.م — والسلسلة النظرية %s ج.م، "
                     "والفرق ده هامش التاجر (السعر المصري محسوب من الذهب العالمي "
                     "× سعر الصرف الرسمي، فمفيش «علاوة» حقيقية)."
                     % (_fmt(local.get("gram_24_reference")),
                        _fmt(cur)))
    if macro:
        av = len(macro.get("available") or [])
        ms = macro.get("missing") or []
        lines.append("الماكرو: %d عامل متاح و%d ناقص%s — العوامل بتوصّف الحالة "
                     "ومش بتحسب «تأثير%%»."
                     % (av, len(ms), (" (" + ", ".join(ms) + ")") if ms else ""))
    return lines


# ═══════════════ البناء ═══════════════
def build(as_of=None):
    """
    ⛔ مفيش استثناءات بتكسر: أي جزء فاشل ⇒ جزءه None + سبب، والباقي شغال.
    """
    out = {"ok": True, "as_of": as_of, "scenarios": [], "savings": None,
           "summary": [], "sources": {}, "caveats": []}

    # ── السلسلة ──
    try:
        gh = _get("gold_history")
        hist = gh.build()
        series = (hist or {}).get("series") or []
        out["sources"]["history"] = {
            "count": len(series), "from": (hist or {}).get("from"),
            "to": (hist or {}).get("to"),
            "fx": ((hist or {}).get("sources") or {}).get("fx"),
            "gaps": (hist or {}).get("gaps"),
        }
    except Exception as e:
        return {"ok": False, "error": "تعذّر تحميل السلسلة: " + str(e)[:90]}

    # ⛔⛔ as_of لازم يقصّ السلسلة **كلها** (مش decompose بس) ⇒ مفيش look-ahead
    #    (نور-الكوانت: كان التحليل الفني + الادخار + السعر الحالي بيشتغلوا
    #     على بيانات بعد as_of).
    if as_of:
        _cut = str(as_of)[:10]
        series = [r for r in series if str(r.get("d"))[:10] <= _cut]
        if len(series) < 60:
            return {"ok": False,
                    "error": "السلسلة قبل as_of قصيرة جداً للسيناريوهات"}
    if len(series) < 60:
        return {"ok": False, "error": "السلسلة قصيرة جداً للسيناريوهات"}

    # ── التحليل الفني للجرام والدولار ──
    gt = _get("gold_technical")
    try:
        an = gt.analyze(gt.bars_from(series, "gram"), label="جرام الذهب عيار ٢٤")
    except Exception as e:
        an = None
        out["caveats"].append("التحليل الفني للجرام: " + str(e)[:70])
    try:
        # ⛔ bars_from(rows, close_key) — المفتاح هو اسم الحقل مش اسم الأداة!
        fx_bars = gt.bars_from(series, "egp_per_usd")
        fx_an = gt.analyze(fx_bars, label="الدولار مقابل الجنيه")
    except Exception as e:
        fx_an = None
        out["caveats"].append("التحليل الفني للدولار: " + str(e)[:70])
    if not an:
        return {"ok": False, "error": "التحليل الفني غير متاح"}

    cur = an.get("current")
    lv = _levels(an)
    cur_fx = None
    if series and series[-1].get("egp_per_usd"):
        cur_fx = float(series[-1]["egp_per_usd"])

    # ── تفكيك الحركة ──
    attribution = None
    try:
        gp = _get("gold_premium")
        dec = gp.decompose(series, days=365, as_of=as_of)
        attribution = gp.attribute(dec)
        out["attribution"] = {"decompose": {k: dec.get(k) for k in
                                            ("from", "to", "days", "log_sum_check",
                                             "log_sum_exact")},
                              "attribute": attribution}
    except Exception as e:
        out["caveats"].append("تفكيك الحركة: " + str(e)[:70])

    # ── السعر المحلي المرصود ──
    local = None
    try:
        gl = _get("gold_local")
        loc = gl.get()
        if loc and loc.get("ok"):
            local = {"gram_24_reference": loc.get("gram_24_reference"),
                     "source": loc.get("source"),
                     "updated_iso": loc.get("updated_iso"),
                     "freshness": gl.freshness(loc)}
    except Exception as e:
        out["caveats"].append("السعر المحلي: " + str(e)[:70])

    # ── العوامل الماكرو ──
    macro = None
    try:
        gm = _get("gold_macro")
        macro = gm.factors_list()
    except Exception as e:
        out["caveats"].append("محرك العوامل: " + str(e)[:70])

    # ── السيناريوهات ──
    try:
        out["scenarios"] = [
            _sc_bull(an, lv, series, cur),
            _sc_bear(an, lv, series, cur),
            _sc_range(an, lv, series, cur),
        ]
        sc_fx = _sc_currency(fx_an, cur, cur_fx, attribution)
        if sc_fx:
            out["scenarios"].append(sc_fx)
    except Exception as e:
        out["caveats"].append("بناء السيناريوهات: " + str(e)[:90])

    # ── الادخار (اسمي vs حقيقي) ──
    try:
        out["savings"] = _savings(series, _cpi_eg())
    except Exception as e:
        out["savings"] = {"ok": False, "error": str(e)[:90]}

    # ── الخلاصة ──
    try:
        out["summary"] = _summary(an, fx_an, attribution, out.get("savings") or {},
                                  macro, local, cur, cur_fx)
    except Exception as e:
        out["caveats"].append("الخلاصة: " + str(e)[:70])

    out["current"] = {"gram": _r(cur, 2), "egp_per_usd": _r(cur_fx, 4),
                      "date": series[-1].get("d"),
                      "effective_date_cairo": series[-1].get("effective_date_cairo")}
    out["technical_gram"] = {
        "trend": (an.get("trend") or {}),
        "rsi14": an.get("rsi14"),
        "macd_state": (an.get("macd") or {}).get("state"),
        "ma": an.get("ma"),
        "hist_vol_annual_pct": an.get("hist_vol_annual_pct"),
        "structure_label": (an.get("structure") or {}).get("label"),
    }
    out["technical_fx"] = {"trend": ((fx_an or {}).get("trend") or {}),
                           "rsi14": (fx_an or {}).get("rsi14")}
    out["caveats"] = out["caveats"] + [
        "السيناريوهات **شروط مش توقّعات** — مفيش احتمال ولا نسبة متخيّلة.",
        "مفيش توصية شراء/بيع — ده تحليل بشروط قابلة للقياس.",
        "كل مستوى من ٥٠٠ شمعة؛ لو السعر كسره بإغلاق، المستوى القديم بيبقى مرجع تاريخي.",
    ]
    return out
