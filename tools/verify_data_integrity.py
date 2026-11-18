#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ الجولة ٢٣ (R23) — حارس سلامة بيانات تاريخ المؤشرات (إغلاق ملاحظات R21-I01 / I02 / I03)

📌 الملاحظات المراجِعة اللي الجولة دي بتقفلها ⭐:
   ① R21-I01 ⭐ «احمِ كل التواريخ والقيم التاريخية — مش عدد الصفوف بس»
      ⇒ مجموعة طوابع الأساس ⊆ مجموعة طوابع الملف الحالي ⭐
        (مفيش تاريخ قديم يختفي ⭐ — حتى لو عدد الصفوف ما قلّش ⭐)
      ⇒ + كل قيمة على طابع من الأساس تبقى **متطابقة** مع الأساس ⭐
      ⇒ + تقرير الأرقام بالظبط ⭐: طوابع الأساس · طوابع الحالي · ناقص · متغيّر.

   ② R21-I02 ⭐ «المقارنة ما ينفعش تنجح من غير تداخل زمني حقيقي»
      ⇒ التداخل = تقاطع المدى الزمني ⭐:
        [ max(min_base, min_current) , min(max_base, max_current) ] ⭐
      ⇒ يفشل ⭐ لو التداخل فاضي ⭐ أو أقل من يوم ⭐ أو أقل من 50% من مدى
        الأساس ⭐ أو لو عدد الطوابع المشتركة = 0 ⭐
        (المقارنة الفارغة كانت بتعدّي ⭐ — دلوقتي مفيش مقارنة فاضية بتعدّي ⭐).

   ③ R21-I03 ⭐ «ارفض التواريخ المكرّرة والقيم غير الصالحة»
      ⇒ الطوابع الزمنية **متزايدة تماماً** ⭐ (مفيش تكرار ⭐)
      ⇒ + كل صف = (int timestamp, float value) ⭐ (مفيش صف بيتخطّى ⭐)
      ⇒ + مافيش NaN ⭐ ومافيش Infinity ⭐
      ⇒ + 0 < value < 100000 ⭐
      ⇒ + الطوابع الزمنية تواريخ تقويمية معقولة ⭐ (مش سالبة ⭐ ومش بعد الأفق ⭐).

📌 كمان (نص المالك ⭐): «اثبّت سلامة count و from و to»
   ⇒ count = عدد الصفوف ⭐ · from = تاريخ أول صف ⭐ · to = تاريخ آخر صف ⭐
     على مستوى **كل مؤشر** ⭐.
   ⇒ والملف **مافيشوش** ملخّص (count/from/to) على مستوى السطح ⭐
     ⇒ الحارس بيسجّل ده صراحةً ⭐ وبيقفل على بيانات كل مؤشر ⭐ (مش بنخترع حقول ⭐).

⛔ الفحص **قراءة بس** ⭐ — data/index_history.json ما يتلمسش ⭐.

📌 طريقة التشغيل ⭐:
   python3 tools/verify_data_integrity.py [BASE_REF]
   python3 tools/verify_data_integrity.py <ref> --current PATH --base-file PATH
   python3 tools/verify_data_integrity.py <ref> --report-json /tmp/report.json
"""
import argparse
import datetime
import io
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = "data/index_history.json"

# ⭐ نسخة الأساس الافتراضية ⭐ = commit استرجاع تاريخ المؤشرات (الجولة ٢١) ⭐
#   اللي فيه التاريخ الكامل (EGX30 = 7,028 صف ⭐).
DEFAULT_BASE_REF = "e101401"

SECONDS_PER_DAY = 86400

# ⛔ العتبات ⭐ (موثّقة في التقرير ⭐ وفي مخرجات الأداة ⭐)
VALUE_EPSILON = 1e-9                 # تسامح المقارنة العددية ⭐
MIN_VALUE = 0.0                      # أقل قيمة مسموحة ⭐
MAX_VALUE = 100000.0                 # أكبر قيمة مسموحة ⭐
MIN_TIMESTAMP = 0                    # 1970-01-01 ⭐
MAX_TIMESTAMP = 4102444800           # 2100-01-01 (أفق معقول ⭐)
OVERLAP_MIN_DAYS = 1                 # لازم تداخل يوم واحد على الأقل ⭐
OVERLAP_MIN_BASE_FRACTION = 0.5      # التداخل لازم يغطي 50% من مدى الأساس ⭐
MIN_SHARED_TIMESTAMPS = 1            # لازم فيه طابع مشترك واحد على الأقل ⭐
WRITE_TOLERANCE = 1e-4                # تسامح أداة التحديث (تقريب لـ4 منازل ⭐)

CHECKS = []


# ────────────────────────────────────────────────────────────────────────────
# أدوات مساعدة ⭐
# ────────────────────────────────────────────────────────────────────────────
def add(cid, label, cond, detail="", always=False):
    """يسجّل نتيجة فحص ⭐ وبيطبعها ⭐ (والتفاصيل دايماً للفحوص الجديدة ⭐)"""
    good = bool(cond)
    CHECKS.append({"id": cid, "label": label, "ok": good,
                   "detail": "" if detail is None else str(detail)})
    line = ("  ✅ " if good else "  ❌ ") + label
    if detail and (always or not good):
        line += "  — " + str(detail)
    print(line)
    return good


def utc_date(ts):
    """تاريخ UTC بالشكل YYYY-MM-DD ⭐"""
    return datetime.datetime.fromtimestamp(
        int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")


def day_number(ts):
    """رقم اليوم ⭐ (UTC) — عشان نقارن المدى الزمني بالأيام ⭐"""
    return int(ts) // SECONDS_PER_DAY


def parse_rows(rows):
    """يحوّل صفوف الملف لـ [(int ts, float value)] ⭐

    ⛔ أي صف مش (int, float) بالظبط ⇒ خطأ ⭐ (مش تخطّي ⭐).
    """
    parsed = []
    errors = []
    if not isinstance(rows, list):
        return [], ["rows is not a list (%s)" % type(rows).__name__]
    for i, row in enumerate(rows):
        if not isinstance(row, (list, tuple)):
            errors.append("row %d: not a pair (%s)" % (i, type(row).__name__))
            continue
        if len(row) != 2:
            errors.append("row %d: expected exactly 2 fields, got %d"
                          % (i, len(row)))
            continue
        raw_ts, raw_val = row
        if isinstance(raw_ts, bool):
            errors.append("row %d: timestamp is a bool" % i)
            continue
        if isinstance(raw_ts, int):
            ts = int(raw_ts)
        elif isinstance(raw_ts, float) and float(raw_ts).is_integer():
            ts = int(raw_ts)
        else:
            errors.append("row %d: timestamp is not an int (%r)" % (i, raw_ts))
            continue
        try:
            value = float(raw_val)
        except (TypeError, ValueError):
            errors.append("row %d: value is not a number (%r)" % (i, raw_val))
            continue
        parsed.append((ts, value))
    return parsed, errors


def series_map(rows):
    """خريطة {timestamp: value} ⭐ — مع كشف التعارض في التكرار ⭐"""
    parsed, _errors = parse_rows(rows)
    out = {}
    conflicts = []
    for ts, value in parsed:
        if ts in out and abs(out[ts] - value) > VALUE_EPSILON:
            conflicts.append(ts)
        else:
            out.setdefault(ts, value)
    return out, conflicts


def duplicate_timestamps(parsed):
    """قائمة الطوابع الزمنية المكرّرة ⭐ + مواضع عدم الترتيب ⭐"""
    seen = set()
    dups = []
    unordered = []
    prev = None
    for pos, (ts, _value) in enumerate(parsed):
        if ts in seen:
            if ts not in dups:
                dups.append(ts)
        else:
            seen.add(ts)
        if prev is not None and ts <= prev:
            unordered.append(pos)
        prev = ts
    return dups, unordered


def format_dates(days_list, limit=4):
    """تحويل أرقام الأيام لقوائم تواريخ مقروءة ⭐"""
    out = []
    for day in days_list[:limit]:
        try:
            out.append(utc_date(day * SECONDS_PER_DAY))
        except Exception:
            out.append(str(day))
    return out


# ────────────────────────────────────────────────────────────────────────────
# ⭐ الفحوص ⭐
# ────────────────────────────────────────────────────────────────────────────
def validate_series(rows, label, prefix, always=True):
    """فحص بنية السلسلة وقيمها (R21-I03 ⭐) — يرجع قاموس بالمشاكل ⭐"""
    parsed, errors = parse_rows(rows)
    add(prefix + ".ROW_SHAPE",
        "`%s`: كل صف = (int timestamp, float value) ⭐" % label,
        not errors,
        ("%d صف مكسور: %s" % (len(errors), "; ".join(errors[:3]))) if errors else "",
        always=always)

    dups, unordered = duplicate_timestamps(parsed)
    add(prefix + ".STRICTLY_INCREASING",
        "`%s`: الطوابع الزمنية **متزايدة تماماً** ⭐ (مفيش تكرار ⭐)" % label,
        (not dups) and (not unordered),
        ("تكرار: %s · غير مرتّب: %d صف"
         % (", ".join(format_dates([day_number(t) for t in dups])) or "مافيش",
            len(unordered))) if (dups or unordered) else "",
        always=always)

    nan_rows = [i for i, (_t, v) in enumerate(parsed) if math.isnan(v)]
    inf_rows = [i for i, (_t, v) in enumerate(parsed) if math.isinf(v)]
    add(prefix + ".FINITE_VALUE",
        "`%s`: مافيش NaN ومافيش Infinity في القيم ⭐" % label,
        (not nan_rows) and (not inf_rows),
        ("NaN في %d صف · Infinity في %d صف" % (len(nan_rows), len(inf_rows)))
        if (nan_rows or inf_rows) else "",
        always=always)

    bad_range = [i for i, (_t, v) in enumerate(parsed)
                 if not (MIN_VALUE < v < MAX_VALUE)]
    add(prefix + ".VALUE_RANGE",
        "`%s`: كل القيم في النطاق (0 < value < %g) ⭐" % (label, MAX_VALUE),
        not bad_range,
        ("%d صف خارج النطاق (أولهم: صف %d بقيمة %r)"
         % (len(bad_range), bad_range[0],
            parsed[bad_range[0]][1]) if bad_range else ""),
        always=always)

    bad_ts = [i for i, (t, _v) in enumerate(parsed)
              if not (MIN_TIMESTAMP <= t <= MAX_TIMESTAMP)]
    add(prefix + ".TS_PLAUSIBLE",
        "`%s`: الطوابع الزمنية تواريخ تقويمية معقولة ⭐" % label,
        not bad_ts,
        ("%d طابع غير معقول (أولهم: %r)" % (len(bad_ts), parsed[bad_ts[0]][0]))
        if bad_ts else "",
        always=always)
    return parsed


def check_metadata(meta, parsed, rows, label, prefix="META"):
    """يفحص عدّاد/من/إلى مقابل الصفوف الفعلية ⭐"""
    count = meta.get("count")
    try:
        count_int = int(count)
    except (TypeError, ValueError):
        count_int = None
    actual_count = len(rows) if isinstance(rows, list) else 0
    add(prefix + ".COUNT",
        "`%s`: `count` = %d = عدد الصفوف ⭐" % (label, actual_count),
        count_int == actual_count,
        "count في الملف: %r · الصفوف الفعلية: %d" % (count, actual_count),
        always=True)

    ts_list = [t for t, _v in parsed]
    actual_from = utc_date(min(ts_list)) if ts_list else None
    actual_to = utc_date(max(ts_list)) if ts_list else None
    add(prefix + ".FROM",
        "`%s`: `from` = %s = تاريخ أول صف ⭐" % (label, actual_from),
        str(meta.get("from")) == str(actual_from),
        "from في الملف: %r · تاريخ أول صف: %r" % (meta.get("from"), actual_from),
        always=True)
    add(prefix + ".TO",
        "`%s`: `to` = %s = تاريخ آخر صف ⭐" % (label, actual_to),
        str(meta.get("to")) == str(actual_to),
        "to في الملف: %r · تاريخ آخر صف: %r" % (meta.get("to"), actual_to),
        always=True)

    # ⭐ لو الملف فيه مفتاح `series` ⭐ ⇒ لازم يطابق الـ`rows` ⭐
    #   (المحدّث وقت التشغيل بيكتب `series` بـ120 نقطة ⭐ وبيمسح count/from/to ⭐).
    series = meta.get("series")
    if isinstance(series, list) and series:
        s_map, _conf = series_map(series)
        rows_map, _conf2 = series_map(rows)
        same_dates = set(s_map) == set(rows_map)
        same_vals = all(abs(s_map[t] - rows_map[t]) <= VALUE_EPSILON
                        for t in set(s_map) & set(rows_map))
        add(prefix + ".SERIES_ALIAS",
            "`%s`: مفتاح `series` متسق مع `rows` ⭐" % label,
            same_dates and same_vals,
            ("`series` فيه %d نقطة (%s → %s) و `rows` فيه %d نقطة (%s → %s)"
             % (len(s_map),
                utc_date(min(s_map)) if s_map else "فاضي",
                utc_date(max(s_map)) if s_map else "فاضي",
                len(rows_map),
                utc_date(min(rows_map)) if rows_map else "فاضي",
                utc_date(max(rows_map)) if rows_map else "فاضي")),
            always=True)
    return {"count": actual_count, "from": actual_from, "to": actual_to}


def check_top_summary(obj, indices_meta):
    """فحص الملخّص على مستوى السطح ⭐ (لو موجود ⭐) + تسجيل صراحة ⭐"""
    keys = [k for k in ("count", "from", "to") if k in obj]
    if not keys:
        add("META.TOP_SUMMARY",
            "الملف **مافيشوش** ملخّص (count/from/to) على مستوى السطح ⭐ — "
            "البديل المعتمد: بيانات كل مؤشر ⭐",
            True,
            "مفاتيح السطح: %s" % ", ".join(sorted(obj.keys())), always=True)
        return {"present": False}

    total_rows = 0
    all_ts = []
    for _name, meta in indices_meta.items():
        rows = meta.get("rows") or []
        parsed, _e = parse_rows(rows)
        total_rows += len(rows)
        all_ts.extend(t for t, _v in parsed)
    actual_from = utc_date(min(all_ts)) if all_ts else None
    actual_to = utc_date(max(all_ts)) if all_ts else None
    try:
        count_int = int(obj.get("count"))
    except (TypeError, ValueError):
        count_int = None
    add("META.TOP_SUMMARY.COUNT",
        "ملخّص السطح: `count` = %d = إجمالي الصفوف ⭐" % total_rows,
        count_int == total_rows,
        "count في الملف: %r · الإجمالي: %d" % (obj.get("count"), total_rows),
        always=True)
    add("META.TOP_SUMMARY.FROM",
        "ملخّص السطح: `from` = %s = أقدم تاريخ ⭐" % actual_from,
        str(obj.get("from")) == str(actual_from),
        "from في الملف: %r" % obj.get("from"), always=True)
    add("META.TOP_SUMMARY.TO",
        "ملخّص السطح: `to` = %s = أحدث تاريخ ⭐" % actual_to,
        str(obj.get("to")) == str(actual_to),
        "to في الملف: %r" % obj.get("to"), always=True)
    return {"present": True, "count": total_rows,
            "from": actual_from, "to": actual_to}


def compare_index(name, base_meta, cur_meta):
    """المقارنة الكاملة لمؤشر واحد ⭐ (I01 + I02 ⭐) — بترجع ملخّص ⭐"""
    b_rows = base_meta.get("rows") or []
    c_rows = cur_meta.get("rows") or []
    b_map, _b_conf = series_map(b_rows)
    c_map, _c_conf = series_map(c_rows)
    b_ts = set(b_map)
    c_ts = set(c_map)

    missing = sorted(b_ts - c_ts)
    shared = b_ts & c_ts
    changed = sorted(t for t in shared
                     if abs(b_map[t] - c_map[t]) > VALUE_EPSILON)

    add("I01.TS_SUBSET",
        "`%s`: كل تواريخ الأساس موجودة ⭐ (base=%d · current=%d · "
        "missing=%d · changed=%d)" % (name, len(b_ts), len(c_ts),
                                      len(missing), len(changed)),
        not missing,
        ("ناقص %d تاريخ (أولهم: %s)"
         % (len(missing), ", ".join(format_dates([day_number(t) for t in missing]))))
        if missing else "",
        always=True)

    add("I01.VALUE_IDENTICAL",
        "`%s`: قيم كل تاريخ من الأساس **متطابقة** ⭐ (قارنت %d قيمة)"
        % (name, len(shared)),
        not changed,
        ("%d قيمة اتغيّرت (أولهم: %s: %r ⇒ %r)"
         % (len(changed),
            utc_date(changed[0]), b_map[changed[0]], c_map[changed[0]]))
        if changed else "",
        always=True)

    # ── التداخل الزمني الحقيقي ⭐
    b_days = sorted(day_number(t) for t in b_ts)
    c_days = sorted(day_number(t) for t in c_ts)
    summary = {
        "base_timestamps": len(b_ts),
        "current_timestamps": len(c_ts),
        "missing": len(missing),
        "changed": len(changed),
        "shared": len(shared),
    }
    if not b_days or not c_days:
        add("I02.OVERLAP_WINDOW",
            "`%s`: فيه تداخل زمني حقيقي ⭐" % name, False,
            "الأساس أو الحالي فاضي ⭐", always=True)
        add("I02.OVERLAP_MIN_DAYS",
            "`%s`: التداخل ≥ %d يوم ⭐" % (name, OVERLAP_MIN_DAYS), False,
            "0 يوم", always=True)
        add("I02.OVERLAP_BASE_FRACTION",
            "`%s`: التداخل يغطي ≥ %g%% من مدى الأساس ⭐"
            % (name, OVERLAP_MIN_BASE_FRACTION * 100), False,
            "0%", always=True)
        add("I02.SHARED_COUNT",
            "`%s`: عدد الطوابع المشتركة ≥ %d ⭐" % (name, MIN_SHARED_TIMESTAMPS),
            False, "0", always=True)
        return summary

    base_span_days = b_days[-1] - b_days[0] + 1
    ov_from = max(b_days[0], c_days[0])
    ov_to = min(b_days[-1], c_days[-1])
    overlap_days = (ov_to - ov_from + 1) if ov_to >= ov_from else 0
    fraction = (overlap_days / float(base_span_days)) if base_span_days else 0.0
    window = ("%s → %s" % (utc_date(ov_from * SECONDS_PER_DAY),
                           utc_date(ov_to * SECONDS_PER_DAY))
              if overlap_days else "فاضي ⭐")

    summary.update({
        "base_from": utc_date(b_days[0] * SECONDS_PER_DAY),
        "base_to": utc_date(b_days[-1] * SECONDS_PER_DAY),
        "current_from": utc_date(c_days[0] * SECONDS_PER_DAY),
        "current_to": utc_date(c_days[-1] * SECONDS_PER_DAY),
        "overlap_from": utc_date(ov_from * SECONDS_PER_DAY) if overlap_days else None,
        "overlap_to": utc_date(ov_to * SECONDS_PER_DAY) if overlap_days else None,
        "overlap_days": overlap_days,
        "base_span_days": base_span_days,
        "covered_fraction": round(fraction, 4),
    })

    add("I02.OVERLAP_WINDOW",
        "`%s`: فيه تداخل زمني حقيقي ⭐ (الأساس %s → %s · الحالي %s → %s · "
        "التداخل %s)" % (name, summary["base_from"], summary["base_to"],
                         summary["current_from"], summary["current_to"], window),
        overlap_days > 0,
        "الأساس [%s, %s] · الحالي [%s, %s] · التداخل %s"
        % (summary["base_from"], summary["base_to"],
           summary["current_from"], summary["current_to"], window),
        always=True)
    add("I02.OVERLAP_MIN_DAYS",
        "`%s`: التداخل ≥ %d يوم ⭐ (المتاح %d يوم)" % (name, OVERLAP_MIN_DAYS,
                                                       overlap_days),
        overlap_days >= OVERLAP_MIN_DAYS,
        "%d يوم" % overlap_days, always=True)
    add("I02.OVERLAP_BASE_FRACTION",
        "`%s`: التداخل يغطي %0.1f%% من مدى الأساس ⭐ (المطلوب ≥ %g%% · "
        "%d/%d يوم)" % (name, fraction * 100, OVERLAP_MIN_BASE_FRACTION * 100,
                        overlap_days, base_span_days),
        fraction >= OVERLAP_MIN_BASE_FRACTION,
        "%0.1f%%" % (fraction * 100), always=True)
    add("I02.SHARED_COUNT",
        "`%s`: عدد الطوابع المشتركة = %d (المطلوب ≥ %d) ⭐"
        % (name, len(shared), MIN_SHARED_TIMESTAMPS),
        len(shared) >= MIN_SHARED_TIMESTAMPS,
        "%d" % len(shared), always=True)
    return summary


# ────────────────────────────────────────────────────────────────────────────
# ⭐ دوال مشتركة مع أداة التحديث ⭐
# ────────────────────────────────────────────────────────────────────────────
def validate_payload(payload):
    """يفحص أي حمولة index_history ⭐ — يرجع قائمة مشاكل ⭐"""
    problems = []
    if not isinstance(payload, dict):
        return ["الحمولة مش dict"]
    indices = payload.get("indices")
    if not isinstance(indices, dict) or not indices:
        problems.append("مفيش مؤشرات في الحمولة")
        return problems
    for name in sorted(indices):
        meta = indices[name] or {}
        rows = meta.get("rows")
        parsed, errors = parse_rows(rows)
        for err in errors[:5]:
            problems.append("%s: %s" % (name, err))
        dups, unordered = duplicate_timestamps(parsed)
        for dup in dups[:5]:
            problems.append("%s: طابع زمني مكرّر: %s"
                            % (name, utc_date(dup)))
        if unordered:
            problems.append("%s: %d صف مش مرتّب زمنياً" % (name, len(unordered)))
        for i, (ts, value) in enumerate(parsed):
            if math.isnan(value) or math.isinf(value):
                problems.append("%s: صف %d فيه قيمة NaN/Infinity" % (name, i))
                break
        for i, (ts, value) in enumerate(parsed):
            if not (MIN_VALUE < value < MAX_VALUE):
                problems.append("%s: صف %d فيه قيمة خارج النطاق: %r"
                                % (name, i, value))
                break
        for i, (ts, _value) in enumerate(parsed):
            if not (MIN_TIMESTAMP <= ts <= MAX_TIMESTAMP):
                problems.append("%s: صف %d فيه طابع زمني غير معقول: %r"
                                % (name, i, ts))
                break
        ts_list = [t for t, _v in parsed]
        if ts_list:
            if int(meta.get("count") or -1) != len(rows):
                problems.append("%s: count=%r مش مطابق لعدد الصفوف %d"
                                % (name, meta.get("count"), len(rows)))
            if str(meta.get("from")) != utc_date(min(ts_list)):
                problems.append("%s: from=%r مش مطابق لأول صف %s"
                                % (name, meta.get("from"), utc_date(min(ts_list))))
            if str(meta.get("to")) != utc_date(max(ts_list)):
                problems.append("%s: to=%r مش مطابق لآخر صف %s"
                                % (name, meta.get("to"), utc_date(max(ts_list))))
        else:
            problems.append("%s: مفيش صفوف صالحة" % name)
    return problems


def compare_history(old_payload, new_payload):
    """يقارن نسخة قديمة بنسخة جديدة ⭐ — يرجع قائمة مشاكل ⭐

    ⛔ القواعد ⭐: مفيش تاريخ قديم يتشال ⭐ · مفيش قيمة تاريخية تتغيّر ⭐
       · مفيش مؤشر يختفي ⭐ · مفيش قصّ في عدد الصفوف ⭐.
    """
    problems = []
    old_idx = (old_payload or {}).get("indices") or {}
    new_idx = (new_payload or {}).get("indices") or {}
    for name in sorted(old_idx):
        if name not in new_idx:
            problems.append("%s: المؤشر اختفى من النسخة الجديدة" % name)
            continue
        old_map, _c = series_map(old_idx[name].get("rows") or [])
        new_map, _c2 = series_map(new_idx[name].get("rows") or [])
        missing = sorted(set(old_map) - set(new_map))
        if missing:
            problems.append("%s: %d تاريخ قديم اتشال (أولهم: %s)"
                            % (name, len(missing),
                               utc_date(missing[0])))
        changed = [t for t in sorted(set(old_map) & set(new_map))
                   if abs(old_map[t] - new_map[t]) > WRITE_TOLERANCE]
        if changed:
            problems.append("%s: %d قيمة تاريخية اتغيّرت (أولهم: %s: %r ⇒ %r)"
                            % (name, len(changed), utc_date(changed[0]),
                               old_map[changed[0]], new_map[changed[0]]))
        old_n = len(old_idx[name].get("rows") or [])
        new_n = len(new_idx[name].get("rows") or [])
        if new_n < old_n:
            problems.append("%s: عدد الصفوف قلّ (%d ⇒ %d) — قصّ بيانات"
                            % (name, old_n, new_n))
    return problems


# ────────────────────────────────────────────────────────────────────────────
# ⭐ البرنامج الرئيسي ⭐
# ────────────────────────────────────────────────────────────────────────────
def git_show(ref, path):
    try:
        return subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                              capture_output=True, text=True,
                              timeout=300).stdout
    except Exception:
        return ""


def read_text(path):
    try:
        with io.open(path, encoding="utf-8") as handle:
            return handle.read()
    except Exception:
        return ""


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="حارس سلامة بيانات تاريخ المؤشرات (R23 ⭐)")
    parser.add_argument("base_ref", nargs="?", default=DEFAULT_BASE_REF,
                        help="نسخة الأساس في git (افتراضي: %s)" % DEFAULT_BASE_REF)
    parser.add_argument("--current", default=os.path.join(ROOT, TARGET),
                        help="الملف المراد فحصه (افتراضي: %s)" % TARGET)
    parser.add_argument("--base-file", default="",
                        help="نسخة الأساس من ملف بدل git (للاختبارات ⭐)")
    parser.add_argument("--report-json", default="",
                        help="يكتب تقرير الفحوص كـ JSON ⭐")
    parser.add_argument("--quiet", action="store_true",
                        help="بدون طباعة التفاصيل ⭐")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    quiet = args.quiet

    print("\n" + "=" * 74)
    print("  🛡️ حارس سلامة بيانات تاريخ المؤشرات — الجولة ٢٣ ⭐")
    print("  الملف: %s" % args.current)
    print("=" * 74)
    print("  العتبات ⭐: تداخل ≥ %d يوم ⭐ · تغطية ≥ %g%% من مدى الأساس ⭐ · "
          "طوابع مشتركة ≥ %d ⭐ · epsilon = %g ⭐ · 0 < value < %g ⭐"
          % (OVERLAP_MIN_DAYS, OVERLAP_MIN_BASE_FRACTION * 100,
             MIN_SHARED_TIMESTAMPS, VALUE_EPSILON, MAX_VALUE))

    cur_txt = read_text(args.current)
    base_ref = args.base_ref
    if args.base_file:
        base_txt = read_text(args.base_file)
        base_source = "file:%s" % args.base_file
    else:
        base_txt = git_show(base_ref, TARGET)
        base_source = "git:%s" % base_ref

    add("FILE.CURRENT_EXISTS", "① الملف موجود على القرص ⭐",
        bool(cur_txt), args.current, always=False)
    add("FILE.BASE_READABLE", "② نسخة الأساس (%s) مقروءة ⭐" % base_source,
        bool(base_txt), base_source, always=False)

    try:
        cur = json.loads(cur_txt)
    except Exception as exc:
        cur = None
        add("FILE.CURRENT_JSON", "③ الملف الحالي JSON صالح ⭐", False,
            str(exc)[:160], always=True)
    else:
        add("FILE.CURRENT_JSON", "③ الملف الحالي JSON صالح ⭐", True, "",
            always=False)

    try:
        base = json.loads(base_txt)
    except Exception as exc:
        base = None
        add("FILE.BASE_JSON", "④ ملف الأساس JSON صالح ⭐", False,
            str(exc)[:160], always=True)
    else:
        add("FILE.BASE_JSON", "④ ملف الأساس JSON صالح ⭐", True, "",
            always=False)

    if not isinstance(cur, dict) or not isinstance(base, dict):
        _finish(args, quiet, {})
        return 1

    # ── ⑤ الميتاداتا (زي ما كانت ⭐) ──
    for key in ("version", "source", "source_note", "coverage_note"):
        add("LEGACY.META.%s" % key,
            "⑤ الميتاداتا `%s` ما اتغيّرتش ⭐" % key,
            base.get(key) == cur.get(key),
            "قبل: %s / بعد: %s" % (str(base.get(key))[:60], str(cur.get(key))[:60]),
            always=False)

    # ── ⑥⑦ نفس المؤشرات وعدد الصفوف ──
    b_idx = base.get("indices") or {}
    c_idx = cur.get("indices") or {}
    add("LEGACY.INDEX_SET", "⑥ نفس المؤشرات بالظبط ⭐",
        set(b_idx) == set(c_idx),
        "قبل %s / بعد %s" % (sorted(b_idx), sorted(c_idx)), always=False)
    for name in sorted(set(b_idx) & set(c_idx)):
        b_rows = len(b_idx[name].get("rows") or [])
        c_rows = len(c_idx[name].get("rows") or [])
        add("LEGACY.ROW_COUNT.%s" % name,
            "⑦ `%s`: عدد الصفوف ما قلّش (%d ⇒ %d) ⭐" % (name, b_rows, c_rows),
            c_rows >= b_rows, "%d ⇒ %d" % (b_rows, c_rows), always=False)

    # ── ⭐ فحص بنية وقيمة الملف الحالي (R21-I03 ⭐) ──
    print("\n  ── بنية وقيم الملف الحالي (R21-I03 ⭐) ──")
    cur_parsed = {}
    for name in sorted(c_idx):
        rows = c_idx[name].get("rows") or []
        cur_parsed[name] = validate_series(rows, name, "I03")
        check_metadata(c_idx[name] or {}, cur_parsed[name], rows, name)

    # ── ⭐ فحص بنية ملف الأساس (لازم الأساس نفسه يكون سليم ⭐) ──
    print("\n  ── بنية وقيم نسخة الأساس (R21-I03 ⭐) ──")
    base_parsed = {}
    for name in sorted(b_idx):
        rows = b_idx[name].get("rows") or []
        base_parsed[name] = validate_series(rows, name, "BASE")
        check_metadata(b_idx[name] or {}, base_parsed[name], rows, name,
                       prefix="BASE.META")

    # ── ⭐ الملخّص على مستوى السطح (count/from/to ⭐) ──
    print("\n  ── ملخّص count / from / to ⭐ ──")
    top_summary = check_top_summary(cur, c_idx)
    if top_summary.get("present"):
        top_summary_base = check_top_summary(base, b_idx)
    else:
        top_summary_base = {"present": False}

    # ── ⭐ المقارنة الكاملة: I01 + I02 ⭐
    print("\n  ── مقارنة الأساس بالحالي (R21-I01 + R21-I02 ⭐) ──")
    per_index = {}
    for name in sorted(set(b_idx) & set(c_idx)):
        per_index[name] = compare_index(name, b_idx[name] or {},
                                         c_idx[name] or {})

    # ── ⑧⑨ القيم على الطوابع المشتركة (زي ما كانت ⭐) ──
    b_maps = {}
    c_maps = {}
    for name in sorted(set(b_idx) & set(c_idx)):
        b_maps[name] = series_map(b_idx[name].get("rows") or [])[0]
        c_maps[name] = series_map(c_idx[name].get("rows") or [])[0]
    total_shared = 0
    total_changed = 0
    for name in sorted(set(b_maps) & set(c_maps)):
        shared = set(b_maps[name]) & set(c_maps[name])
        changed = [t for t in shared
                   if abs(b_maps[name][t] - c_maps[name][t]) > VALUE_EPSILON]
        total_shared += len(shared)
        total_changed += len(changed)
        add("LEGACY.SHARED_VALUES.%s" % name,
            "⑧ `%s`: القيم على %d طابع مشترك **ما اتغيّرتش** ⭐"
            % (name, len(shared)),
            not changed, "اتغيّر: %d" % len(changed), always=False)
    add("LEGACY.SHARED_VALUES.TOTAL",
        "⑨ إجمالي القيم المشتركة المتغيّرة = 0 ⭐ (المقارنة: %d قيمة)"
        % total_shared, total_changed == 0, total_changed, always=False)

    # ── ⑬ ميتاداتا السطح ──
    diffs = []
    for key in sorted(set(base) | set(cur)):
        if key in ("indices", "series", "refreshed_at"):
            continue
        if base.get(key) != cur.get(key):
            diffs.append(key)
    add("LEGACY.TOP_META", "⑬ مافيش تغيير في ميتاداتا السطح ⭐",
        not diffs, diffs, always=False)

    add("LEGACY.REFRESHED_AT", "⑭ `refreshed_at` متناسق بين النسختين ⭐",
        base.get("refreshed_at") == cur.get("refreshed_at"),
        "قبل: %s / بعد: %s" % (base.get("refreshed_at"), cur.get("refreshed_at")),
        always=False)

    # ── ⑮ `series` ──
    bs, cs = base.get("series") or [], cur.get("series") or []
    b_sm = series_map(bs)[0]
    c_sm = series_map(cs)[0]
    shared = set(b_sm) & set(c_sm)
    changed = [t for t in shared if abs(b_sm[t] - c_sm[t]) > VALUE_EPSILON]
    add("LEGACY.SERIES", "⑮ `series`: القيم المشتركة (%d) ما اتغيّرتش ⭐"
        % len(shared), not changed, "اتغيّر: %d" % len(changed), always=False)

    summary = {
        "base_ref": base_ref,
        "base_source": base_source,
        "current": args.current,
        "indices": per_index,
        "top_summary": top_summary,
        "top_summary_base": top_summary_base,
        "total_shared": total_shared,
        "total_changed": total_changed,
    }
    _finish(args, quiet, summary)
    return 0 if all(c["ok"] for c in CHECKS) else 1


def _finish(args, quiet, summary):
    passed = sum(1 for c in CHECKS if c["ok"])
    total = len(CHECKS)
    failed = [c for c in CHECKS if not c["ok"]]
    print("\n" + "=" * 74)
    print("  النتيجة: %d/%d ⭐" % (passed, total))
    print("  ✔ طوابع ناقصة (I01): %d ⭐"
          % sum(v.get("missing", 0) for v in summary.get("indices", {}).values()))
    print("  ✔ قيم متغيّرة (I01): %d ⭐"
          % sum(v.get("changed", 0) for v in summary.get("indices", {}).values()))
    for name in sorted(summary.get("indices", {})):
        info = summary["indices"][name]
        print("  ✔ `%s`: base=%d · current=%d · shared=%d · missing=%d · "
              "changed=%d · تداخل %s → %s (%d يوم · %0.1f%% من %d يوم) ⭐"
              % (name, info.get("base_timestamps", 0),
                 info.get("current_timestamps", 0), info.get("shared", 0),
                 info.get("missing", 0), info.get("changed", 0),
                 info.get("overlap_from") or "فاضي",
                 info.get("overlap_to") or "فاضي",
                 info.get("overlap_days", 0),
                 info.get("covered_fraction", 0.0) * 100,
                 info.get("base_span_days", 0)))
    print("=" * 74)
    if failed:
        print("  ❌ الفحوص اللي فشلت ⭐:")
        for chk in failed:
            print("     - [%s] %s%s" % (chk["id"], chk["label"],
                                       ("  — " + chk["detail"]) if chk["detail"] else ""))
    else:
        print("  ✅ كل الفحوص عدّت ⭐")
    if args.report_json:
        payload = {
            "ok": not failed,
            "passed": passed,
            "total": total,
            "failed_ids": [c["id"] for c in failed],
            "checks": CHECKS,
            "summary": summary,
        }
        try:
            with io.open(args.report_json, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            print("  📄 التقرير: %s" % args.report_json)
        except Exception as exc:
            print("  ⚠️ مقدرتش أكتب التقرير: %s" % str(exc)[:120])


if __name__ == "__main__":
    sys.exit(main())
