# -*- coding: utf-8 -*-
"""🎯 opp_engine.py — محرّك الفرص الحي (OPP-002).

📌 الهدف: حساب الفرص **من البيانات الحيّة** بدل اللقطة الثابتة.
📌 nine strategies: التسع استراتيجيات المعرّفة في data/opp_definitions.json
   (نفس تعريفات الواجهة — مش السبعة القديمة).

⛔⛔⛔ السرّية (١٥ نوفمبر ٢٠٢٦):
   الأوزان والعتبات (weight · points_max · min_coverage · min_liquidity_value)
   **سرّية** ⇒ ما بتترجعش في أي رد عام. الردود العامة فيها:
   · تعريف الاستراتيجية بالعربي (accept/reject/risk/invalidation)
   · نسبة المطابقة لكل معيار (ratio 0..1) والسبب المبسّط
   · التغطية والبيانات الناقصة
   ⛔ الأوزان الحقيقية ما بتظهرش.

⛔ مافيش شبكة · مافيش فلاس · الملف ده مستقل ⇒ يتختبر لوحده.
"""
import datetime
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEF_FILE = HERE / "data" / "opp_definitions.json"

# ⛔ سياسات الباقات (قرار المالك — ١٦/١٧ نوفمبر ٢٠٢٦):
#    · الاستراتيجيات التسع **كلها** ظاهرة لـFree وPro.
#    · Free ⇒ أفضل ٥ فرص في كل استراتيجية + أسباب مختصرة.
#    · Pro  ⇒ أفضل ٢٠ فرصة في كل استراتيجية + تفاصيل أوسع.
#    · ⛔ مافيش اختلاف في دقة الحساب أو معايير الأهلية بين الباقتين.
#    · ⛔ ⛔ السعر التجاري **مش مفعّل ومش معتمد** ⇒ بره منطق حساب الفرص.
#    · ⛔ العدد قابل للضبط (قرار المالك لسه نهائيش) ⇒ constant في ملف واحد.
OPP_PRO_STRATEGIES = ()
OPP_FREE_LIMIT_PER_STRATEGY = 5      # ⛔ قابل للضبط — قرار المالك
OPP_PRO_LIMIT_PER_STRATEGY = 20     # ⛔ أفضل ٢٠ (مش «كل المؤهل») — قابل للضبط
                                     # ⛔ رفعه = payload أكبر ⇒ يتقاس بعد التغيير

# ⛔ حدود التشغيل (اختيارية) — الافتراضي: كل الأسهم
OPP_LIMIT_PER_STRATEGY = 20

# ⛔⛔⛔ عقد الحداثة (١٦ نوفمبر ٢٠٢٦ · معدّل الجولة ١٦):
#    «السوق مغلق» ⇏ «البيانات حديثة». الاتنين منفصلين.
#    · source_as_of   = توقيت بيانات المصدر نفسها
#    · last_success_at = آخر جلب **ناجح** (ما بيتحدّثش لو الجلب فشل)
#    · age_seconds     = الفرق بين دلوقتي وآخر جلب ناجح (⛔ بيتحسب **دايماً**)
#    · freshness       = fresh | stale | unavailable
#      (⛔ الحداثة = **عمر آخر جلب ناجح** — مش التغطية)
#    · coverage_status = complete | partial | unavailable
#      (⛔ التغطية = **نسبة السهم اللي اتجلب** — مش الحداثة)
#    ⛔⛔⛔ الجولة ١٦: قبل كنا بنخلط التغطية بالحداثة — تغطية أقل من ٩٠٪
#       كانت بتعمل freshness="partial" وبتصفّر age_seconds ⇒ المستخدم ماعرفش
#       إن البيانات قديمة **و** إن التغطية ناقصة في نفس الوقت.
FRESH_MAX_AGE_OPEN = 900             # ١٥ دقيقة وقت السوق
FRESH_MAX_AGE_CLOSED = 86400         # يوم وقت الإغلاق
FRESH_MIN_COVERAGE = 90.0            # ⛔ عتبة التغطية (الجولة ١٤)

# ⛔⛔⛔ الجولة ١٦ — حدود **عمر السعر نفسه** (مش عمر آخر جلب):
#    · PRICE_MAX_AGE_OPEN   = أقصى عمر سعر مسموح بوسمه «سعر التداول الآن»
#    · PRICE_MAX_AGE_CLOSED = أقصى عمر سعر يفضل «سعر الإغلاق»
PRICE_MAX_AGE_OPEN = 900             # ١٥ دقيقة — نفس حدّ حداثة البيانات
PRICE_MAX_AGE_CLOSED = 86400         # يوم — بعده ⇒ «آخر سعر معروف»


def _parse_timestamp(value):
    """⛔ يحوّل توقيت (ISO8601 أو epoch) ⇒ ثوانٍ بعد الحقبة (أو None).

    📌 بنقبل ISO8601 (مع Z أو +00:00 أو من غير منطقة) و epoch (رقم أو نص).
    ⛔ مافيش شبكة · مافيش افتراضات على المنطقة ⇒ أي توقيت بلا منطقة
       بيتقري UTC (توقيت البورصة المصرية بتتحوّل وقت المصدر).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    txt = s.replace("Z", "+00:00").replace("z", "+00:00")
    dt = None
    try:
        dt = datetime.datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def price_age_seconds_from(price_ts, now=None):
    """⛔⛔⛔ الجولة ١٦ — **عمر السعر نفسه** (مش عمر آخر جلب).

    📌 price_age_seconds = now - price_ts
    ⛔ توقيت في المستقبل ⇒ ساعة المصدر مش موثوقة ⇒ العمر **غير معروف**
       (مش «الآن»!) — حماية من انحراف الساعة.
    ⛔ مافيش price_ts ⇒ None (مش 0) ⇒ مافيش ادعاء لحظية.
    """
    ts = _parse_timestamp(price_ts)
    if ts is None:
        return None
    if now is None:
        now = time.time()
    try:
        now = float(now)
    except (TypeError, ValueError):
        return None
    if ts > now + 60:
        return None
    return int(max(0.0, now - ts))


def session_date_of(value):
    """⛔ تاريخ الجلسة (YYYY-MM-DD) من توقيت أو من نص تاريخ."""
    if value is None:
        return None
    ts = _parse_timestamp(value)
    if ts is None:
        s = str(value).strip()
        return s[:10] if len(s) >= 10 else None
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def format_age_ar(seconds):
    """⛔ نص عربي لعمر البيانات (ثواني · دقائق · ساعات · أيام)."""
    if seconds is None:
        return "غير معروف"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "غير معروف"
    if s < 0:
        s = 0
    if s < 60:
        return "منذ ثوانٍ"
    if s < 3600:
        return "منذ %d دقيقة" % (s // 60)
    if s < 86400:
        return "منذ %d ساعة" % (s // 3600)
    return "منذ %d يوم" % (s // 86400)


def freshness_state(last_success_at, market_phase="unknown", now=None,
                    max_age_open=None, max_age_closed=None,
                    coverage=None, requested=None, updated=None):
    """⛔⛔⛔ ١٦/١٨ نوفمبر ٢٠٢٦ — عقد الحداثة (**مفهومين منفصلين**).

    📌 **الحداثة** (freshness) = عمر آخر جلب **ناجح**:
         fresh | stale | unavailable
    📌 **التغطية** (coverage_status) = نسبة السهم اللي اتجلب:
         complete | partial | unavailable
    ⛔⛔⛔ الجولة ١٦: قبل كنا بنخلط التغطية بالحداثة — تغطية أقل من ٩٠٪
       كانت بتعمل freshness="partial" وبتصفّر age_seconds ⇒ المستخدم ماعرفش
       إن البيانات قديمة **و** إن التغطية ناقصة في نفس الوقت.
    📌 القواعد:
      · «السوق مغلق» ⇏ «البيانات حديثة» — الاتنين منفصلين.
      · last_success_at ما بيتحدّثش إلا بعد جلب **ناجح**.
      · age_seconds بيتحسب **دايماً** من آخر جلب ناجح (حتى مع تغطية جزئية).
      · مافيش جلب ناجح أصلاً ⇒ unavailable (مش «حالي») + age_seconds=None.
      · السوق مفتوح والبيانات أقدم من الحد ⇒ stale.
      · السوق مغلق والبيانات أقدم من يوم ⇒ stale.
    """
    max_age_open = FRESH_MAX_AGE_OPEN if max_age_open is None else max_age_open
    max_age_closed = FRESH_MAX_AGE_CLOSED if max_age_closed is None else max_age_closed
    now = now if now is not None else time.time()
    _cov_info = {
        "coverage_pct": (round(float(coverage), 2)
                         if coverage is not None else None),
        "requested": requested,
        "updated": updated,
        "missing": (int(requested) - int(updated)
                    if (requested is not None and updated is not None) else None),
    }
    # ⛔⛔⛔ مفهوم ١ — التغطية (مستقلّة تماماً عن الحداثة)
    # ⛔⛔⛔ الجولة ١٧ (R16-N2) — **«مقبولة» ≠ «كاملة»**:
    #    عتبة القبول (٩٠٪) اتفضلت زي ما هي، بس:
    #      · coverage_status = complete ⇔ مفيش سطر ناقص **اصلاً** (١٠٠٪)
    #      · coverage_acceptable = التغطية فوق عتبة القبول (٩٠٪)
    #    ⇒ ٩٠٪ من ١٠٠ = «مقبولة» مش «كاملة» ⇒ النصّ بيبقى صادق.
    _missing = _cov_info.get("missing")
    # ⛔⛔⛔ R17-V2-01 (مراجعة الجولة ١٧) — **نطاق الأعداد + مصدر الحقيقة**:
    #    ① نطاق الأعداد: المطلوب لازم أكبر من صفر · والمحدَّث بين الصفر والمطلوب.
    #    ② لما الأعداد موجودة ⇒ **هي مصدر الحقيقة**: النسبة = المحدَّث ÷ المطلوب
    #       والمقارنة بتقريب المصدر لرقمين عشريين (مش سماحية نقطة واحدة).
    #    ③ «كاملة» بس لو النسبة ١٠٠٪ صحيحة ومتسقة · «مقبولة» بس لو عدّت
    #       العتبة الفعلية (٩٠٪) — ⛔ العتبة نفسها ما بتتغيّرش.
    _req = requested
    _upd = updated
    try:
        _req = int(_req) if _req is not None else None
    except (TypeError, ValueError):
        _req = None
    try:
        _upd = int(_upd) if _upd is not None else None
    except (TypeError, ValueError):
        _upd = None
    _counts_ok = True
    if _req is not None and _req <= 0:
        _counts_ok = False          # ⛔ كون(The Universe) = 0 ⇒ مافيش تغطية أصلاً
    if _upd is not None and _upd < 0:
        _counts_ok = False          # ⛔ عدد سالب
    if _req is not None and _upd is not None and _upd > _req:
        _counts_ok = False          # ⛔ محدَّث أكبر من المطلوب
    _ratio_given = None
    if coverage is not None:
        try:
            _ratio_given = float(coverage)
        except (TypeError, ValueError):
            _ratio_given = None
    _ratio_valid = (_ratio_given is not None
                     and 0.0 <= _ratio_given <= 100.0)
    _implied_cov = None
    if _req and _upd is not None and _req > 0:
        _implied_cov = (float(_upd) / float(_req)) * 100.0
    _cov_consistent = True
    _coverage_pct = (round(_ratio_given, 2) if _ratio_given is not None else None)
    if coverage is None:
        coverage_status = "unavailable"
        coverage_acceptable = False
        _cov_consistent = False
    elif not _counts_ok:
        # ⛔ تناقض أو نطاق غير صالح ⇒ ممنوع «كاملة» وممنوع «مقبولة»
        coverage_status = "partial"
        coverage_acceptable = False
        _cov_consistent = False
    elif _implied_cov is not None:
        # ⛔ الأعداد هي مصدر الحقيقة
        _cov_consistent = (round(_ratio_given, 2) == round(_implied_cov, 2))
        if not _cov_consistent:
            coverage_status = "partial"
            coverage_acceptable = False
        else:
            _coverage_pct = round(_implied_cov, 2)
            coverage_status = ("complete" if _implied_cov >= 100.0 else "partial")
            coverage_acceptable = bool(_implied_cov >= FRESH_MIN_COVERAGE)
    elif not _ratio_valid:
        # ⛔ نسبة خارج المدى (٠..١٠٠) ⇒ ممنوع «كاملة»
        coverage_status = "partial"
        coverage_acceptable = False
        _cov_consistent = False
    else:
        coverage_status = "complete" if _ratio_given >= 100.0 else "partial"
        coverage_acceptable = bool(_ratio_given >= FRESH_MIN_COVERAGE)
    # ⛔⛔⛔ مفهوم ٢ — الحداثة (عمر آخر جلب ناجح · مستقلّ عن التغطية)
    ts = _parse_timestamp(last_success_at) if last_success_at else None
    if ts is None:
        freshness = "unavailable"
        age = None
    else:
        age = int(max(0.0, float(now) - ts))
        limit = max_age_open if str(market_phase) == "open" else max_age_closed
        freshness = "fresh" if age <= limit else "stale"
    return {
        # ⛔ الحداثة (مش التغطية)
        "freshness": freshness,
        # ⛔ التغطية (مش الحداثة)
        "coverage_status": coverage_status,
        # ⛔⛔⛔ الجولة ١٧ (R16-N2) — التغطية **مقبولة** (فوق عتبة القبول)
        #    بس **مش كاملة** ⇒ لازم التمييز يكون صريح في العقد.
        "coverage_acceptable": coverage_acceptable,
        "coverage_min_pct": FRESH_MIN_COVERAGE,
        # ⛔⛔⛔ R17-P2 — اتساق الأرقام (النسبة ↔ المطلوب ↔ المحدَّث)
        "coverage_consistent": _cov_consistent,
        # ⛔⛔⛔ R17-V2-01 — النسبة المنشورة = النسبة المعتمدة
        #    (المستنتجة من الأعداد لما تكون موجودة)
        "coverage_pct": _coverage_pct,
        "coverage_implied_pct": (round(_implied_cov, 2)
                                 if _implied_cov is not None else None),
        # ⛔ data_state = الحداثة — مافيش خلط مع التغطية
        "data_state": freshness,
        "is_fresh": freshness == "fresh",
        "is_stale": freshness == "stale",
        "age_seconds": age,
        "last_success_at": (last_success_at if ts is not None else None),
        "market_phase": market_phase,
        **_cov_info,
    }


def freshness_source(fresh_state=None):
    """⛔ مصدر البيانات كما بتظهر للمستخدم.

    📌 live       = بيانات محدّثة + تغطية كاملة
    📌 partial    = بيانات محدّثة + تغطية ناقصة (مش كل السوق)
    📌 cache      = البيانات قديمة (من كاش)
    📌 unavailable = مافيش بيانات صالحة
    """
    st = fresh_state or {}
    fr = str(st.get("freshness") or "unknown")
    cov = str(st.get("coverage_status") or "unknown")
    if fr == "fresh":
        return "live" if cov == "complete" else "partial"
    if fr == "stale":
        return "cache"
    return "unavailable"


def freshness_summary_ar(fresh_state=None):
    """⛔ جملة واحدة بتوضّح **الحداثة** و**التغطية** مع بعض."""
    st = fresh_state or {}
    fr = str(st.get("freshness") or "unknown")
    cov = str(st.get("coverage_status") or "unknown")
    age = st.get("age_seconds")
    if fr == "unavailable":
        return "البيانات غير متاحة"
    parts = ["البيانات حديثة" if fr == "fresh" else "البيانات قديمة"]
    if cov == "complete":
        parts.append("التغطية كاملة")
    elif cov == "partial":
        pct = st.get("coverage_pct")
        # ⛔⛔⛔ الجولة ١٧ (R16-N2) — **«مقبولة» مش «كاملة»**:
        #    فوق عتبة القبول (٩٠٪) بس مش ١٠٠٪ ⇒ نصّ صريح مختلف.
        ok = st.get("coverage_acceptable")
        if ok is None:
            ok = (pct is not None
                  and float(pct) >= FRESH_MIN_COVERAGE)
        if ok:
            parts.append("التغطية مقبولة%s"
                         % ((" (%s%%)" % pct) if pct is not None else ""))
        else:
            parts.append("التغطية جزئية%s"
                         % ((" (%s%%)" % pct) if pct is not None else ""))
        # ⛔⛔⛔ R17-P2 — تناقض الأرقام لازم يبان للمستخدم
        if st.get("coverage_consistent") is False:
            parts.append("أرقام التغطية غير متسقة")
    else:
        parts.append("التغطية غير معروفة")
    if age is not None:
        parts.append("عمر البيانات %s" % format_age_ar(age))
    return " · ".join(parts)


def price_label_for(market_phase="unknown", stale=False, data_state=None,
                     price_time_source="source", price_age_seconds=None,
                     price_session_date=None, session_date=None,
                     price_ts=None, now=None,
                     max_price_age_open=None, max_price_age_closed=None):
    """⛔⛔⛔ ١٧/١٨ نوفمبر ٢٠٢٦ (الجولة ١٦) — وصف السعر **الصادق**.

    📌 «سعر التداول الآن» = **ادعاء لحظي** ⇒ لازم **تلات** أدلة:
       ① السوق مفتوح
       ② سعر من **نفس الجلسة الحالية** (مش جلسة سابقة)
       ③ عمر السعر (`price_age_seconds`) ≤ `PRICE_MAX_AGE_OPEN`
    ⛔⛔⛔ `stale=False` **لوحده** ما بيخليش السعر لحظي (الجولة ١٦).
    ⛔⛔⛔ الجولة ١٧ (R16-N4): «الآن» محتاج **الجلسة الحالية + جلسة السعر**
       موجودين **ومتساويين** — لو أي واحد فيهم ناقص ⇒ مفيش دليل ⇒ ممنوع.
    ⛔⛔⛔ وجود `price_ts` **لوحده** كمان ما بيخليش السعر لحظي — لازم نعرف
       **عمره** (والا كان من جلسة سابقة).
    ⛔⛔⛔ عمر السعر المجهول (مافيش price_ts) ⇒ ممنوع أي ادعاء لحظية.
    📌 «سعر الإغلاق» = ادعاء عن **آخر جلسة** ⇒ بننقّصه بس لما يكون عندنا
       دليل إنه مش من آخر جلسة (عمره أكبر من يوم أو جلسة مختلفة).
    📌 «وقت استلام البيانات» (data_received_at) **مش** دليل على وقت آخر
       تداول ⇒ ما ينفعش نسمّي السعر «الآن» بناءً عليه.
    """
    max_price_age_open = (PRICE_MAX_AGE_OPEN if max_price_age_open is None
                          else max_price_age_open)
    max_price_age_closed = (PRICE_MAX_AGE_CLOSED if max_price_age_closed is None
                            else max_price_age_closed)
    if price_age_seconds is None and price_ts:
        price_age_seconds = price_age_seconds_from(price_ts, now)
    # ⛔⛔ ترتيب الأسبقية: «قديم» أقوى من «مافيش توقيت» ⇒
    #    السهم من الكاش (قديم) يُوصف قديم حتى لو مافيش توقيت من المصدر.
    # ⛔⛔⛔ R17-P1 — «unknown» (مافيش دليل حداثة) كمان بيمنع ادعاء «الآن».
    if stale or str(data_state or "") in ("stale", "unknown"):
        return "آخر سعر معروف"
    # ⛔ مافيش توقيت موثوق من المصدر ⇒ ممنوع أي ادعاء لحظية
    if str(price_time_source or "") != "source":
        return "آخر سعر متاح"
    ph = str(market_phase or "unknown").lower()
    # ⛔⛔ الجولة ١٦: لو السعر من **جلسة تانية** ⇒ ممنوع أي وسم لحظي
    _ps = str(price_session_date or "")[:10]
    _cs = str(session_date or "")[:10]
    _other_session = bool(_ps and _cs and _ps != _cs)
    if ph == "open":
        # ⛔⛔⛔ ادعاء لحظي ⇒ لازم **عمر معروف** وحديث ونفس الجلسة
        if price_age_seconds is None:
            return "آخر سعر متاح"
        if _other_session:
            return "آخر سعر معروف"
        # ⛔⛔⛔ الجولة ١٧ (R16-N4) — «الآن» محتاج **دليل تطابق الجلسات**:
        #    لازم تاريخ الجلسة الحالية **موجود** + تاريخ جلسة السعر **موجود**
        #    + **متساويين**. لو أي واحد ناقص ⇒ مفيش دليل ⇒ ممنوع «الآن».
        if not (_ps and _cs and _ps == _cs):
            return "آخر سعر معروف"
        if float(price_age_seconds) > float(max_price_age_open):
            return "آخر سعر معروف"
        return "سعر التداول الآن"
    if ph == "closed":
        if _other_session:
            return "آخر سعر معروف"
        if (price_age_seconds is not None
                and float(price_age_seconds) > float(max_price_age_closed)):
            return "آخر سعر معروف"
        return "سعر الإغلاق"
    if ph == "pre":
        return "سعر الإغلاق السابق"
    return "السعر الحالي"


def _f(v, d=None):
    try:
        if v is None:
            return d
        return float(v)
    except (TypeError, ValueError):
        return d


def _clamp(x, lo=0.0, hi=1.0):
    if x is None:
        return None
    return max(lo, min(hi, x))


def load_definitions(path=None):
    """يحمّل تعريفات الاستراتيجيات التسع (مرة واحدة)."""
    p = Path(path or os.environ.get("OCTA_OPP_DEFS") or DEF_FILE)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"model_version": "OPP-002.0", "strategies": []}
    d.setdefault("strategies", [])
    return d


# ════════════════════════════════════════════════════════════
#  ⭐ مقيّمو المعايير — كل واحد يرجّع (نسبة 0..1، دليل، ملاحظة)
#  ⛔ مافيش رقم مخترع: لو البيانات ناقصة ⇒ None (ناقص)
# ════════════════════════════════════════════════════════════

def _axis(item, key):
    ax = item.get("all_axes") or {}
    return _f(ax.get(key))


def c_trend(item):
    """الاتجاه الفني — من محور الفني + إشارة الاتجاه."""
    v = _axis(item, "technical")
    if v is None:
        return None
    r = v / 100.0
    sig = str(item.get("technical_signal") or "")
    if "هابط" in sig or "سالب" in sig:
        r *= 0.6
    return _clamp(r), {"technical": v, "signal": sig}, "موقع السعر من المتوسطات واتجاهها"


def c_momentum(item):
    """الزخم السعري — من أداء الشهر و٣ شهور."""
    p1 = _f(item.get("perf_1m"))
    p3 = _f(item.get("perf_3m"))
    if p1 is None and p3 is None:
        return None
    r = 0.5
    if p3 is not None:
        r += p3 / 40.0
    if p1 is not None:
        r += p1 / 60.0
    return _clamp(r), {"perf_1m": p1, "perf_3m": p3}, "قوة الحركة على الأفق الزمني"


def c_liquidity(item):
    """نشاط التداول والسيولة — من محور السيولة + الحجم النسبي."""
    v = _f(item.get("liquidity_score"))
    if v is None:
        return None
    rv = _f(item.get("rel_volume"))
    r = v / 100.0
    if rv is not None:
        r = r * 0.8 + _clamp(rv / 2.0) * 0.2
    return _clamp(r), {"liquidity_score": v, "rel_volume": rv}, "عمق التداول وحجمه النسبي"


def c_structure(item):
    """التكوين الفني والدعم والمقاومة — RSI + المحور الفني."""
    rsi = _f(item.get("rsi"))
    tech = _axis(item, "technical")
    if rsi is None and tech is None:
        return None
    r = 0.5
    if rsi is not None:
        if rsi < 30:
            r = 0.85
        elif rsi > 75:
            r = 0.35
        else:
            r = 0.6 + (50 - abs(rsi - 55)) / 100.0
    if tech is not None:
        r = r * 0.6 + (tech / 100.0) * 0.4
    return _clamp(r), {"rsi": rsi, "technical": tech}, "موقع السعر من مناطق الدعم والمقاومة"


def c_rr(item):
    """العائد مقابل المخاطرة — من محور المخاطرة."""
    v = _axis(item, "risk")
    if v is None:
        return None
    return _clamp(v / 100.0), {"risk": v}, "العائد المتوقع مقابل المخاطر"


def c_news(item):
    """الأخبار ومخاطر الأحداث — من محرك الأخبار."""
    v = _f(item.get("news_score"))
    if v is None:
        return None
    return _clamp(v / 100.0), {"news_score": v}, "قوة الأحداث الحالية ومخاطرها"


def c_fund_quality(item):
    """جودة الأعمال والنتائج المالية — من المحور الأساسي + ROE."""
    v = _axis(item, "fundamental")
    roe = _f(item.get("roe"))
    if v is None:
        return None
    r = v / 100.0
    if roe is not None:
        r = r * 0.7 + _clamp(roe / 30.0) * 0.3
    return _clamp(r), {"fundamental": v, "roe": roe}, "جودة الربحية والملاءة المالية"


def c_growth(item):
    """نمو الأرباح وتحسن الأداء."""
    p3 = _f(item.get("perf_3m"))
    rev = _f(item.get("revenue_growth"))
    ni = _f(item.get("ni_growth"))
    if p3 is None and rev is None and ni is None:
        return None
    parts = [x for x in (p3, rev, ni) if x is not None]
    r = 0.5 + (sum(parts) / len(parts)) / 40.0
    return _clamp(r), {"perf_3m": p3, "revenue_growth": rev, "ni_growth": ni}, \
        "معدل نمو الأرباح"


def c_catalyst(item):
    """المحفزات المتوقعة — من التغير اليومي والأخبار."""
    ch = _f(item.get("change"))
    news = _f(item.get("news_score"))
    if ch is None and news is None:
        return None
    r = 0.45
    if ch is not None:
        r += max(-0.25, min(0.35, ch / 20.0))
    if news is not None:
        r = r * 0.6 + (news / 100.0) * 0.4
    return _clamp(r), {"change": ch, "news_score": news}, "المحفزات المتوقعة والحركة الحالية"


def c_valuation(item):
    """جاذبية التقييم — PE/PB منخفضين أفضل."""
    pe = _f(item.get("pe"))
    pb = _f(item.get("pb"))
    up = _f(item.get("upside"))
    if pe is None and pb is None and up is None:
        return None
    r = 0.5
    if pe is not None and pe > 0:
        r = _clamp(1.0 - (pe - 6.0) / 54.0) * 0.6 + r * 0.4
    if pb is not None and pb > 0:
        r = r * 0.8 + _clamp(1.0 - (pb - 0.6) / 4.4) * 0.2
    if up is not None:
        r = r * 0.7 + _clamp(0.5 + up / 40.0) * 0.3
    return _clamp(r), {"pe": pe, "pb": pb, "upside": up}, "مساحة التقييم مقارنة بالسعر"


def c_funds(item):
    """استدامة نموذج الأعمال — ROE + هامش + دين."""
    roe = _f(item.get("roe"))
    nm = _f(item.get("net_margin"))
    de = _f(item.get("de_ratio"))
    if roe is None and nm is None and de is None:
        return None
    r = 0.5
    if roe is not None:
        r += (roe - 12.0) / 60.0
    if nm is not None:
        r += (nm - 8.0) / 40.0
    if de is not None:
        r -= max(0.0, (de - 40.0) / 60.0)
    return _clamp(r), {"roe": roe, "net_margin": nm, "de_ratio": de}, \
        "استدامة النموذج"


def c_returns(item):
    """جودة الربحية والعائد على رأس المال."""
    roe = _f(item.get("roe"))
    fund = _axis(item, "fundamental")
    if roe is None and fund is None:
        return None
    r = 0.5
    if roe is not None:
        r = _clamp(roe / 28.0)
    if fund is not None:
        r = r * 0.7 + (fund / 100.0) * 0.3
    return _clamp(r), {"roe": roe, "fundamental": fund}, "العائد على رأس المال"


def c_cfo(item):
    """التدفقات النقدية — من cfo/ni إن وُجدت."""
    cfo = _f(item.get("cfo"))
    ni = _f(item.get("ni"))
    if cfo is None or ni is None or ni == 0:
        return None
    ratio = cfo / ni
    return _clamp(ratio / 1.2), {"cfo": cfo, "ni": ni, "ratio": round(ratio, 2)}, \
        "التحويل من صافي الربح إلى نقد"


def c_safety_margin(item):
    """التقييم وهامش الأمان — من fair_value مقابل السعر."""
    fv = _f(item.get("fair_value"))
    px = _f(item.get("price"))
    up = _f(item.get("upside"))
    if fv is None or px is None or px <= 0:
        if up is None:
            return None
        return _clamp(0.5 + up / 40.0), {"upside": up}, "هامش الأمان التقديري"
    ratio = fv / px
    return _clamp((ratio - 0.7) / 0.9), {"fair_value": fv, "price": px, "ratio": round(ratio, 2)}, \
        "الفرق بين القيمة التقديرية والسعر"


def c_governance(item):
    """الحوكمة والمخاطر — من محور المخاطرة + أخبار السوء."""
    v = _axis(item, "risk")
    if v is None:
        return None
    return _clamp(v / 100.0), {"risk": v}, "استقرار الحوكمة ومخاطر المخاطر"


def c_debt(item):
    """المديونية — دين أقل أفضل."""
    de = _f(item.get("de_ratio"))
    if de is None:
        return None
    return _clamp(1.0 - max(0.0, (de - 15.0)) / 85.0), {"de_ratio": de}, "مستوى المديونية"


def c_growth_profit(item):
    """نمو الأرباح والتدفقات النقدية."""
    g = c_growth(item)
    cf = c_cfo(item)
    if g is None and cf is None:
        return None
    rs = [x[0] for x in (g, cf) if x is not None]
    r = sum(rs) / len(rs)
    ev = {}
    if g:
        ev.update(g[1])
    if cf:
        ev.update(cf[1])
    return _clamp(r), ev, "نمو الأرباح مدعوماً بالتدفق النقدي"


def c_reinvest(item):
    """كفاءة إعادة الاستثمار — ROE مع الاحتفاظ بالأرباح."""
    roe = _f(item.get("roe"))
    dy = _f(item.get("div_yield"))
    if roe is None:
        return None
    retention = 1.0 if dy is None else max(0.0, 1.0 - min(1.0, dy / 20.0))
    return _clamp((roe / 25.0) * (0.6 + 0.4 * retention)), {"roe": roe, "div_yield": dy}, \
        "العائد على المبلغ المُعاد استثماره"


def c_margins(item):
    """استدامة الهوامش."""
    nm = _f(item.get("net_margin"))
    if nm is None:
        return None
    return _clamp((nm + 5.0) / 35.0), {"net_margin": nm}, "هامش الربح الصافي"


def c_div_regular(item):
    """انتظام التوزيعات."""
    dy = _f(item.get("div_yield"))
    if dy is None:
        return None
    if dy <= 0:
        return 0.0, {"div_yield": dy}, "مفيش توزيعات"
    return _clamp(dy / 12.0), {"div_yield": dy}, "حجم العائد الموزّع"


def c_div_cover(item):
    """تغطية التوزيعات بالأرباح."""
    dy = _f(item.get("div_yield"))
    eps = _f(item.get("eps"))
    px = _f(item.get("price"))
    if dy is None or eps is None or px is None or px <= 0 or eps <= 0:
        return None
    payout = (dy / 100.0) * px / eps
    return _clamp(1.0 - max(0.0, payout - 0.4) / 0.6), \
        {"div_yield": dy, "eps": eps, "payout": round(payout, 2)}, \
        "نسبة الأرباح الموزّعة"


def c_balance(item):
    """القوة المالية — دين + حجم."""
    de = _f(item.get("de_ratio"))
    mc = _f(item.get("mkt_cap"))
    if de is None and mc is None:
        return None
    r = 0.5
    if de is not None:
        r += (50.0 - de) / 120.0
    if mc is not None:
        r += 0.15 if mc > 10e9 else (0.05 if mc > 2e9 else -0.1)
    return _clamp(r), {"de_ratio": de, "mkt_cap": mc}, "قوة الميزانية"


def c_div_yield_risk(item):
    """عائد التوزيع مقارنة بالمخاطرة."""
    dy = _f(item.get("div_yield"))
    risk = _axis(item, "risk")
    if dy is None or risk is None:
        return None
    r = _clamp(dy / 12.0) * 0.6 + _clamp(risk / 100.0) * 0.4
    return _clamp(r), {"div_yield": dy, "risk": risk}, "العائد مقابل مستوى المخاطر"


def c_div_events(item):
    """مخاطر الأحداث والاستحقاقات."""
    risk = _axis(item, "risk")
    news = _f(item.get("news_score"))
    if risk is None and news is None:
        return None
    r = 0.5
    if risk is not None:
        r = r * 0.6 + _clamp(risk / 100.0) * 0.4
    if news is not None:
        r = r * 0.7 + _clamp(news / 100.0) * 0.3
    return _clamp(r), {"risk": risk, "news_score": news}, "سلامة الأحداث والمستحقاقات"


def c_growth_mix(item):
    """مزيج النمو والدخل."""
    g = c_growth(item)
    dy = _f(item.get("div_yield"))
    if g is None and dy is None:
        return None
    rg = g[0] if g else 0.5
    rd = _clamp(dy / 12.0) if dy is not None else 0.3
    return _clamp(rg * 0.6 + rd * 0.4), {"growth": rg, "div_yield": dy}, \
        "توازن النمو والدخل"


def c_risk_stability(item):
    """استقرار المخاطر — من محور المخاطرة والتقلب."""
    risk = _axis(item, "risk")
    vol = _f(item.get("vol1y"))
    if risk is None and vol is None:
        return None
    r = 0.5
    if risk is not None:
        r = _clamp(risk / 100.0)
    if vol is not None:
        r = r * 0.7 + _clamp(1.0 - vol / 80.0) * 0.3
    return _clamp(r), {"risk": risk, "vol1y": vol}, "ثبات المخاطر عبر الوقت"


def c_cash_stability(item):
    """استقرار التدفقات النقدية."""
    cf = c_cfo(item)
    nm = _f(item.get("net_margin"))
    if cf is None and nm is None:
        return None
    rc = cf[0] if cf else 0.5
    rn = _clamp((nm + 5.0) / 35.0) if nm is not None else 0.5
    return _clamp(rc * 0.6 + rn * 0.4), {"cfo_ratio": rc, "net_margin": nm}, \
        "ثبات التدفق النقدي"


def c_volatility(item):
    """التقلبات والتراجعات التاريخية."""
    vol = _f(item.get("vol1y"))
    mdd = _f(item.get("mdd1y"))
    if vol is None and mdd is None:
        return None
    r = 0.5
    if vol is not None:
        r -= max(0.0, (vol - 20.0)) / 60.0
    if mdd is not None:
        r -= max(0.0, (abs(mdd) - 20.0)) / 60.0
    return _clamp(r), {"vol1y": vol, "mdd1y": mdd}, "التقلبات وأكبر تراجع"


def c_aggressive_momentum(item):
    m = c_momentum(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.1), m[1], "زخم مكثّف على أفق قصير"


def c_aggressive_catalyst(item):
    m = c_catalyst(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.1), m[1], "محفزات وأحداث مكثّفة"


def c_aggressive_liquidity(item):
    m = c_liquidity(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "سيولة تكفي لدخول وخروج سريع"


def c_aggressive_structure(item):
    m = c_structure(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "تكوين فني قوي"


def c_aggressive_rr(item):
    m = c_rr(item)
    if m is None:
        return None
    return _clamp(m[0] * 1.05), m[1], "عائد محتمل أعلى مقابل مخاطرة أعلى"


CRITERIA_SCORERS = {
    "trend": c_trend,
    "momentum": c_momentum,
    "liquidity": c_liquidity,
    "structure": c_structure,
    "rr": c_rr,
    "news": c_news,
    "fund_quality": c_fund_quality,
    "growth": c_growth,
    "catalyst": c_catalyst,
    "valuation": c_valuation,
    "funds": c_funds,
    "returns": c_returns,
    "cfo": c_cfo,
    "safety_margin": c_safety_margin,
    "governance": c_governance,
    "debt": c_debt,
    "growth_profit": c_growth_profit,
    "reinvest": c_reinvest,
    "margins": c_margins,
    "div_regular": c_div_regular,
    "div_cover": c_div_cover,
    "balance": c_balance,
    "div_yield_risk": c_div_yield_risk,
    "div_events": c_div_events,
    "growth_mix": c_growth_mix,
    "risk_stability": c_risk_stability,
    "cash_stability": c_cash_stability,
    "volatility": c_volatility,
    "aggressive_momentum": c_aggressive_momentum,
    "aggressive_catalyst": c_aggressive_catalyst,
    "aggressive_liquidity": c_aggressive_liquidity,
    "aggressive_structure": c_aggressive_structure,
    "aggressive_rr": c_aggressive_rr,
}

ARABIC_GRADES = (
    (85.0, "مطابقة مرتفعة"),
    (70.0, "مطابقة جيدة"),
    (55.0, "مطابقة متوسطة"),
    (0.0, "مطابقة ضعيفة"),
)


def _grade(score):
    for thr, name in ARABIC_GRADES:
        if score >= thr:
            return name
    return "مطابقة ضعيفة"


def _risk_label(item):
    rl = item.get("risk_level")
    if rl:
        return str(rl)
    v = _axis(item, "risk")
    if v is None:
        return "غير متاح"
    if v >= 70:
        return "منخفض"
    if v >= 50:
        return "متوسط"
    if v >= 30:
        return "مرتفع"
    return "مرتفع جداً"


def evaluate_item(item):
    """يحسب كل المعايير لسهم واحد ⇒ نتيجة مشتركة لكل الاستراتيجيات.

    ⛔ النتيجة: {criterion_key: {ratio, evidence, note_ar}} + ملخّص التغطية.
    """
    out = {}
    for key, fn in CRITERIA_SCORERS.items():
        try:
            res = fn(item)
        except Exception:
            res = None
        if res is None:
            out[key] = {"ratio": None, "evidence": {}, "note_ar": None}
        else:
            ratio, ev, note = res
            out[key] = {"ratio": ratio, "evidence": ev or {}, "note_ar": note}
    return out


def evaluate_strategy(item, strategy, crit):
    """يحسب نتيجة السهم في استراتيجية واحدة.

    📌 الأوزان والعتبات من ملف التعريفات (الخادم بس).
    📌 النتيجة: score (0..100) · coverage · missing · reasons مبسّطة.
    """
    crit_defs = strategy.get("criteria") or []
    total_w = sum(float(c.get("weight") or 0) for c in crit_defs) or 1.0
    got_w = 0.0
    pts = 0.0
    missing = []
    public_crit = []
    for c in crit_defs:
        k = c.get("key")
        w = float(c.get("weight") or 0)
        r = (crit.get(k) or {}).get("ratio")
        if r is None:
            missing.append(c.get("label_ar") or k)
            public_crit.append({"key": k, "label_ar": c.get("label_ar"),
                                "ratio": None, "note_ar": (crit.get(k) or {}).get("note_ar")})
            continue
        got_w += w
        pts += r * w
        public_crit.append({"key": k, "label_ar": c.get("label_ar"),
                            "ratio": round(r, 4),
                            "note_ar": (crit.get(k) or {}).get("note_ar")})
    coverage = round((got_w / total_w) * 100.0, 1)
    score = round((pts / total_w) * 100.0, 1)

    # ⛔Reasons مبسّطة — من غير الأوزان ولا نقاط Maximال (سرّية)
    reasons = []
    for pc in public_crit:
        if pc.get("ratio") is None:
            continue
        pct = round(pc["ratio"] * 100)
        label = pc.get("label_ar") or ""
        if pct >= 80:
            reasons.append(f"{label}: مطابقة قوية ({pct}٪).")
        elif pct >= 55:
            reasons.append(f"{label}: مطابقة مقبولة ({pct}٪).")
        else:
            reasons.append(f"{label}: مطابقة ضعيفة ({pct}٪).")
    reasons = reasons[:4]

    # ⛔ الأهلية: مخاطرة أساسية غير كافية ⇒ مش «فرصة مؤكدة»
    risk_ok = _axis(item, "risk") is not None
    # ⛔ min_liquidity_value **قيمة نقدية** (حجم تداول بالجنيه) — مش
    #    درجة السيولة 0..100. ⇒ نقارنها بقيمة التداول الفعلية.
    liq_min = float(strategy.get("min_liquidity_value") or 0)
    liq_value = None
    _vol = _f(item.get("vol_60"))
    if _vol is None:
        _vol = _f(item.get("volume"))
    _px = _f(item.get("price"))
    if _vol is not None and _px is not None:
        liq_value = _vol * _px
    if liq_min:
        liq_ok = (liq_value is not None and liq_value >= liq_min)
    else:
        liq_ok = True
    cov_min = float(strategy.get("min_coverage") or 0)
    cov_ok = coverage >= cov_min
    exclusion = None
    if not risk_ok:
        exclusion = "بيانات المخاطر غير كافية"
    elif not liq_ok:
        exclusion = "حجم التداول أقل من الحد المطلوب"
    elif not cov_ok:
        exclusion = "تغطية البيانات أقل من الحد المطلوب"
    return {
        "score": score,
        "coverage": coverage,
        "available_weight": round(got_w, 1),
        "missing": missing,
        "reasons": reasons,
        "criteria": public_crit,
        "eligible": exclusion is None,
        "exclusion": exclusion,
        "grade_ar": _grade(score),
        "risk_level_ar": _risk_label(item),
        "risk_score": _axis(item, "risk"),
        "hold_days": strategy.get("horizon_ar"),
        "state": "watch" if exclusion is None else "excluded",
    }


def public_strategy(strategy):
    """النسخة العامة من الاستراتيجية ⛔ بدون الأوزان والعتبات."""
    return {
        "key": strategy.get("key"),
        "name_ar": strategy.get("name_ar"),
        "group": strategy.get("group"),
        "icon": strategy.get("icon"),
        "horizon_ar": strategy.get("horizon_ar"),
        "horizon_days": strategy.get("horizon_days"),
        "definition_ar": strategy.get("definition_ar"),
        "looks_for_ar": strategy.get("looks_for_ar"),
        "accept_ar": strategy.get("accept_ar") or [],
        "reject_ar": strategy.get("reject_ar") or [],
        "risk_ar": strategy.get("risk_ar") or [],
        "invalidation_ar": strategy.get("invalidation_ar") or [],
        # ⛔ criteria بدون weight/points_max (سرّية)
        "criteria": [{"key": c.get("key"), "label_ar": c.get("label_ar"),
                      "hint_ar": c.get("hint_ar"), "not_ar": c.get("not_ar")}
                     for c in (strategy.get("criteria") or [])],
        "pro_only": strategy.get("key") in OPP_PRO_STRATEGIES,
    }


def build_payload(stocks, definitions=None, meta=None):
    """يبني payload الفرص الكامل من البيانات الحيّة.

    📌 stocks: قائمة عناصر فيها كل الحقول (من دورة التحديث).
    📌 meta: generated_at · source · freshness
    """
    defs = definitions or load_definitions()
    strategies = defs.get("strategies") or []
    meta = meta or {}
    # ⛔⛔⛔ الجولة ١٦ — الوقت المرجعي + **فصل الحداثة عن التغطية**
    _now = meta.get("now")
    if _now is None:
        _now = time.time()
    _fresh = meta.get("data_freshness") or {}
    _freshness_val = (meta.get("freshness")
                      or _fresh.get("freshness") or "unknown")
    _coverage_status = (meta.get("coverage_status")
                        or _fresh.get("coverage_status") or "unknown")
    # ⛔⛔⛔ الجولة ١٧ (R16-N2) — «مقبولة» (فوق العتبة) ≠ «كاملة»
    _coverage_acceptable = meta.get("coverage_acceptable")
    if _coverage_acceptable is None:
        _coverage_acceptable = _fresh.get("coverage_acceptable")
    if _coverage_acceptable is None:
        _coverage_acceptable = False
    _coverage_acceptable = bool(_coverage_acceptable)
    # ⛔ data_state = الحداثة (مش التغطية)
    _data_state = (_fresh.get("data_state") or _freshness_val)
    # ⛔ الجولة ١٧ (R16-N2) — النصّ بيتحسب من **الحالة المدمجة**
    #    (عشان «مقبولة» و«كاملة» يبانوا صح في كل الحالات).
    _merged_fresh = dict(_fresh)
    _merged_fresh["freshness"] = _freshness_val
    _merged_fresh["coverage_status"] = _coverage_status
    if _merged_fresh.get("coverage_acceptable") is None:
        _merged_fresh["coverage_acceptable"] = _coverage_acceptable
    _state_ar = freshness_summary_ar(_merged_fresh)
    _current_session_date = (str(meta.get("session_date") or "")[:10]
                              or (str(meta.get("trading_day") or "")[:10])
                              or (session_date_of(meta.get("generated_at")) or "")
                              or "")
    lists = {}
    for st in strategies:
        key = st.get("key")
        rows = []
        excluded = []
        for item in stocks:
            crit = item.get("_opp_criteria")
            if crit is None:
                crit = evaluate_item(item)
                item["_opp_criteria"] = crit
            ev = evaluate_strategy(item, st, crit)
            # ⛔⛔⛔ 16 نوفمبر 2026 — حالة بيانات السهم:
            #    «live» = اتجلب دلوقتي · «stale» = آخر سعر معروف
            #    (من الكاش) ⇒ ما يتحضرش كأنه لحظي.
            # ⛔⛔⛔ 17 نوفمبر 2026 (الجولة 14) — وصف السعر + فصل الأوقات:
            #    · price_label حسب حالة السوق (مافيش «سعر إغلاق» وسعر
            #      التداول أثناء الجلسة).
            #    · data_received_at = وقت استلام البيانات.
            #    · price_as_of = وقت السعر الفعلي من المصدر (أو null
            #      + price_time_source=not_provided ⇒ المصدر مابيعطيش وقت).
            _stale = bool(item.get("stale"))
            # ⛔⛔⛔ الجولة ١٧ (R16-N1) — **اتساق الحداثة**: صف «live» لازم
            #    يتagree مع الحداثة العامة على مستوى الدفعة.
            #    «بيانات قديمة» على مستوى الدفعة ⇒ مفيش صف يقدر يقول «live»
            #    (وإلا المستخدم يشوف «بيانات حديثة» و«سعر التداول الآن» مع
            #    إن آخر جلب ناجح من يومين ⇒ ادعاء كاذب).
            _dataset_state = str(_data_state or "unknown")
            _dataset_stale = _dataset_state in ("stale", "unavailable")
            # ⛔⛔⛔ R17-P1 (مراجعة الجولة ١٧) — **«live» لازم دليل صريح**:
            #    لو الحداثة العامة «unknown» (مافيش دليل) ⇒ الصف ما يقولش
            #    «live» ⇒ حالة آمنة «unknown» (مش قديم، ومش حيّ).
            _dataset_unknown = (_dataset_state not in ("fresh", "stale", "unavailable"))
            _row_stale = bool(_stale) or _dataset_stale
            _row_live = (not _row_stale) and (_dataset_state == "fresh")
            # ⛔⛔⛔ ترتيب الأولوية: «القديم» أقوى من «غير معروف» ⇒
            #    سهم من الكاش (أو دفعة قديمة) = stale حتى لو الدلّة ناقصة.
            _row_state = ("stale" if _row_stale else
                          ("live" if _dataset_state == "fresh" else "unknown"))
            _stale_reason = ("item_cache" if _stale else
                             ("dataset_stale" if _dataset_state == "stale"
                              else ("dataset_unavailable"
                                    if _dataset_state == "unavailable"
                                    else ("dataset_unknown"
                                          if _dataset_unknown else ""))))
            _src_ts = item.get("stale_ts") if _stale else (item.get("ts") or "")
            _phase = meta.get("market_phase") or "unknown"
            _price_ts = item.get("price_ts") or None
            _price_time_source = ("source" if _price_ts else "not_provided")
            # ⛔⛔⛔ الجولة ١٦ — **عمر السعر نفسه** (مش عمر آخر جلب)
            _price_age = (price_age_seconds_from(_price_ts, _now)
                          if _price_ts else None)
            # ⛔ جلسة السعر (المصدر) — عشان نعرف: نفس الجلسة ولا جلسة سابقة؟
            _price_session = (str(item.get("price_session_date") or "")[:10]
                              or (session_date_of(_price_ts) or "")
                              or "")
            # ⛔ الجلسة الحالية (من meta أو من وقت استلام البيانات)
            _current_session = (str(meta.get("session_date") or "")[:10]
                                or (str(meta.get("trading_day") or "")[:10])
                                or (session_date_of(meta.get("generated_at")) or "")
                                or (session_date_of(item.get("ts") if not _stale
                                                   else item.get("stale_ts")) or "")
                                or "")
            row = {
                "code": item.get("code"),
                "name": item.get("name"),
                "sector": item.get("sector") or "—",
                "price": item.get("price"),
                # ⛔⛔⛔ الجولة ١٦ — الوصف محسوب من **عمر السعر** وجلسة السعر
                "price_label": price_label_for(
                    _phase, _row_stale,
                    data_state=("stale" if _row_stale
                                else ("unknown" if _dataset_unknown else None)),
                    price_time_source=_price_time_source,
                    price_age_seconds=_price_age,
                    price_session_date=(_price_session or None),
                    session_date=(_current_session or None)),
                "session_date": str(item.get("session_date") or item.get("ts") or "")[:10],
                "change": item.get("change"),
                # ⛔⛔⛔ R17-P1 — live | stale | unknown (مافيش دليل ⇒ unknown)
                "data_state": _row_state,
                # ⛔⛔⛔ الجولة ١٧ (R16-N1) — **ليه** الصف مش حيّ
                # (item_cache = السهم من الكاش · dataset_stale = آخر جلب
                #  ناجح قديم · dataset_unavailable = مافيش جلب ناجح أصلاً ·
                #  dataset_unknown = مافيش دليل حداثة).
                "stale_reason": (_stale_reason or None),
                "source_as_of": _src_ts,
                "data_received_at": (item.get("ts") or "") if not _stale else None,
                "price_as_of": _price_ts,
                "price_time_source": _price_time_source,
                # ⛔⛔⛔ الجولة ١٦ — **عمر السعر لازم يبان للمستخدم** (مش بس جوا)
                "price_age_seconds": _price_age,
                "price_age_minutes": (round(_price_age / 60.0, 1)
                                      if _price_age is not None else None),
                "price_age_label_ar": format_age_ar(_price_age),
                "price_session_date": (_price_session or None),
                "current_session_date": (_current_session or None),
                "market_phase": _phase,
                "score": ev["score"],
                "coverage": ev["coverage"],
                # ⬜️ 17 نوفمبر 2026 (الجولة 15) — ⬜️ مافيش تسريب بنية الأوزان:
                # `available_weight` = مجموع أوزان المعايير المتاحة ⇒ جزء من بنية الأوزان.
                # ⬜️ المعلومات العامة سمي التقييم والنسبة «الدرجة محسوبة من X¥ من المعايير» ⇒ `coverage` كاشارة المعلومات.
                "missing": ev["missing"],
                "grade_ar": ev["grade_ar"],
                "risk_level_ar": ev["risk_level_ar"],
                "risk_score": ev["risk_score"],
                "hold_days": ev["hold_days"],
                "state": ev["state"],
                "reasons": ev["reasons"],
                "criteria": ev["criteria"],
                "eligible": ev["eligible"],
                "exclusion": ev["exclusion"],
            }
            if ev["eligible"]:
                rows.append(row)
            else:
                excluded.append({"code": row["code"], "exclusion": ev["exclusion"]})
        rows.sort(key=lambda r: -(r["score"] or 0))
        limit = OPP_LIMIT_PER_STRATEGY or len(rows)
        lists[key] = {
            "strategy": key,
            "strategy_name_ar": st.get("name_ar"),
            "model_version": defs.get("model_version"),
            "total": len(stocks),
            "eligible": len(rows),
            "excluded": len(excluded),
            "returned": min(len(rows), limit),
            "limit": limit,
            "excluded_codes": [e["code"] for e in excluded][:80],
            "exclusions": excluded[:80],
            "items": rows[:limit],
            "generated_at": meta.get("generated_at"),
            "source": meta.get("source") or "live",
            "freshness": _freshness_val,
            # ⛔⛔⛔ الجولة ١٦ — التغطية **منفصلة** عن الحداثة (في كل قائمة)
            "coverage_status": _coverage_status,
            # ⛔⛔⛔ الجولة ١٧ (R16-N2) — «مقبولة» ≠ «كاملة»
            "coverage_acceptable": _coverage_acceptable,
            "data_state": _data_state,
            "freshness_summary_ar": _state_ar,
            # ⛔ مصادر البيانات وتواخيها (الواجهة بتقراها)
            "sources": meta.get("sources") or [],
            # ⛔ عقد الحداثة
            "data_freshness": meta.get("data_freshness") or {},
        }
    return {
        "ok": True,
        "model_version": defs.get("model_version"),
        "generated_at": meta.get("generated_at"),
        "source": meta.get("source") or "live",
        # ⛔ ⛔⛔ ماينشر الحداثة أصل من عقد الحداثة (ولا من قيمة أخرى)
        "freshness": _freshness_val,
        # ⛔⛔⛔ الجولة ١٦ — **التغطية منفصلة عن الحداثة**
        "coverage_status": _coverage_status,
        # ⛔⛔⛔ الجولة ١٧ (R16-N2) — «مقبولة» (فوق عتبة القبول) ≠ «كاملة»
        "coverage_acceptable": _coverage_acceptable,
        # ⛔ data_state = الحداثة (مش التغطية)
        "data_state": _data_state,
        "freshness_summary_ar": _state_ar,
        "current_session_date": (_current_session_date or None),
        # ⛔⛔⛔ عقد الحداثة — «السوق مغلق» ≠ «البيانات حديثة»
        "market_phase": meta.get("market_phase") or "unknown",
        "source_as_of": meta.get("source_as_of"),
        "last_success_at": meta.get("last_success_at"),
        "age_seconds": _fresh.get("age_seconds"),
        "data_freshness": _fresh,
        "sources": meta.get("sources") or [],
        "note_ar": "محسوبة من البيانات الحيّة — بتتحدّث مع كل دورة تحديث.",
        "strategies": [public_strategy(s) for s in strategies],
        "lists": lists,
    }


def revalidate_payload(payload, now=None):
    """⛔⛔⛔ R17-V2-04 (مراجعة الجولة ١٧) — **صلاحية وقت الرد** (مش وقت الإنشاء).

    ⛔ المشكلة: النسخة المخزّنة كانت بتُقدَّم بحالة «fresh» طالما ما
       اتحدّثتش ⇒ لو دورة التحديث توقفت ⇒ الواجهة بتقول «بيانات حديثة»
       و«سعر التداول الآن» وبتار ساعات ⇒ **ادعاء كاذب للمستخدم**.

    ⛔ الإصلاح: إعادة تقييم الحداثة **وقت تقديم النسخة**:
       · بنحسب عمر آخر جلب ناجح (`last_success_at`) مقابل الوقت الحالي.
       · «fresh» ⇒ نرجّع النسخة كما هي (⛔ من غير ما نعمل نسخة).
       · «stale»/«unavailable» ⇒ **نسخة مشتقة** (⛔ الأصل ما بيتمسّش):
         `freshness` · `data_state` · `age_seconds` · وسم كل صف
         (`data_state` + `stale_reason`) · وصف السعر · ملخّص الحداثة.

    📌 النسخة المشتركة في الذاكرة (LIVE_DATA) ما بتتعدّلش أبداً.
    """
    if not isinstance(payload, dict):
        return payload
    _now = float(now) if now is not None else time.time()
    _df = dict(payload.get("data_freshness") or {})
    _phase = str(payload.get("market_phase")
                 or _df.get("market_phase") or "unknown")
    _ts = payload.get("last_success_at")
    if _ts is None:
        _ts = _df.get("last_success_at")
    try:
        _ts = float(_ts) if _ts is not None else None
    except (TypeError, ValueError):
        _ts = None
    _limit = (FRESH_MAX_AGE_OPEN if _phase == "open"
              else FRESH_MAX_AGE_CLOSED)
    if _ts is None:
        _state = "unavailable"
        _age = None
    else:
        _age = int(max(0.0, _now - _ts))
        _state = "fresh" if _age <= _limit else "stale"
    _cur = str(payload.get("freshness") or _df.get("freshness") or "unknown")
    if _state == "fresh" and _cur == "fresh":
        return payload          # ⛔ النسخة سليمة — من غير تعديل
    # ⛔ نسخة مشتقة — الأصل (المشترك) ما بيتمسّش
    out = dict(payload)
    out["freshness"] = _state
    out["data_state"] = _state
    out["age_seconds"] = _age
    _df2 = dict(_df)
    _df2["freshness"] = _state
    _df2["data_state"] = _state
    _df2["is_fresh"] = bool(_state == "fresh")
    _df2["is_stale"] = bool(_state == "stale")
    _df2["age_seconds"] = _age
    if _state != "fresh":
        _df2["stale_reason"] = ("dataset_unavailable"
                                if _state == "unavailable"
                                else "dataset_stale")
    out["data_freshness"] = _df2
    _lists = {}
    for _k, _v in (payload.get("lists") or {}).items():
        _items = []
        for _row in ((_v or {}).get("items") or []):
            _r = dict(_row)
            if str(_r.get("data_state") or "") == "live":
                _r["data_state"] = "stale"
                _r["stale_reason"] = "dataset_stale"
                # ⛔ عمر السعر بيتحسب **وقت الرد** (النسخة بقت أقدم)
                _pa = None
                if _r.get("price_as_of"):
                    try:
                        _pa = price_age_seconds_from(_r.get("price_as_of"), _now)
                    except Exception:
                        _pa = None
                if _pa is not None:
                    _r["price_age_seconds"] = _pa
                    _r["price_age_minutes"] = round(_pa / 60.0, 1)
                    _r["price_age_label_ar"] = format_age_ar(_pa)
                _r["price_label"] = price_label_for(
                    _phase, True, data_state="stale",
                    price_time_source=(_r.get("price_time_source")
                                       or "not_provided"),
                    price_age_seconds=_r.get("price_age_seconds"),
                    price_session_date=_r.get("price_session_date"),
                    session_date=_r.get("current_session_date"))
            _items.append(_r)
        _lv = dict(_v or {})
        _lv["items"] = _items
        _lists[_k] = _lv
    out["lists"] = _lists
    out["freshness_summary_ar"] = freshness_summary_ar(_df2)
    return out


def apply_tier(payload, plan="free"):
    """⛔ تطبيق حدود الباقة **من الباك** (قرار المالك — 16/17 نوفمبر 2026).

    📌 Free: أفضل 5 فرص في كل استراتيجية + تفاصيل مختصرة.
    📌 Pro : أفضل 20 فرصة في كل استراتيجية + تفاصيل أوسع.
    ⛔ مافيش اختلاف في دقة الحساب ولا في معايير الأهلية.
    ⛔ ⛔ السعر التجاري غير مفعّل ⇒ بره منطق حساب الفرص.
    """
    if not payload:
        return payload
    pro = str(plan or "free").lower() == "pro"
    limit = OPP_PRO_LIMIT_PER_STRATEGY if pro else OPP_FREE_LIMIT_PER_STRATEGY
    out = dict(payload)
    out["plan"] = "pro" if pro else "free"
    out["limit_per_strategy"] = limit
    out["limit_label_ar"] = ("أفضل %s فرصة لكل استراتيجية" % limit
                              if limit is not None else "كل الفرص المؤهلة")
    lists = {}
    for key, lst in (payload.get("lists") or {}).items():
        l = dict(lst)
        items = list(l.get("items") or [])
        if limit is not None:
            items = items[:limit]
        out_items = []
        for it in items:
            if pro:
                out_items.append(it)
                continue
            # ⛔ Free: تفاصيل مختصرة (بلا تحليل معياري تفصيلي ولا مخاطر)
            brief = {k: v for k, v in it.items()
                     if k not in ("criteria", "risks", "plan", "refs", "exclusions")}
            out_items.append(brief)
        l["items"] = out_items
        l["returned"] = len(out_items)
        l["eligible_total"] = lst.get("eligible")
        lists[key] = l
    out["lists"] = lists
    return out
