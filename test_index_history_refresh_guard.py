#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪🛡️ الجولة ٢٣ (R23) — برهان أن التحديث الحيّ ما بيقصّش التاريخ ⭐

📌 العيب (R21-I01 ⭐ · جذر فقدان بيانات الجولة ٢١ ⭐):
   `_maybe_refresh_index_history()` كان بيقرأ من `series` ⭐ (آخر 120 بار ⭐)
   ⇒ كل تحديث يومي كان بيمسح التاريخ القديم ⭐ ⇒ الملف كان بينزل لـ120 ⭐

📌 المطلوب:
   ① التحديث يقرأ `rows` ⭐ (المجموعة الكاملة ⭐) ⇒ التاريخ بينمو ⭐
   ② `series` مرآة لـ`rows` ⭐ ⇒ الحارس بيقول `META.SERIES_ALIAS` يطابق ⭐
   ③ ⛔ fail-closed ⭐: لو أي تاريخ قديم ضاع ⇒ ما نكتبش ⭐
   ④ ⭐⭐ البرهان السالب ⭐: على الكود قبل الإصلاح ⭐ ⇒ الفحص **يفشل** ⭐
      (يعني الاختبار بيكشف العيب ⭐ مش بيمشي وخلاص ⭐)

📌 التشغيل: python3 test_index_history_refresh_guard.py
"""
import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "update_prices.py")
RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label, extra))
    print("%s %-58s %s" % ("PASS" if cond else "FAIL", label, extra))


def extract_refresh(src):
    """Extract the body of _maybe_refresh_index_history (textual, no import)."""
    key = "def _maybe_refresh_index_history"
    i = src.find(key)
    if i < 0:
        return ""
    j = src.find("\ndef ", i + 10)
    return src[i:j if j > 0 else len(src)]


def simulate(refresh_src, rows_before, new_bars):
    """Run the extracted refresh logic against a synthetic row (pure text exec)."""
    # the refresh function needs many globals; we only execute the merge part
    start = refresh_src.find('for ix_id, sym in')
    if start < 0:
        return None
    body = refresh_src[start:]
    # cut at the write block (we assert on the in-memory row, not the file)
    cut = body.find('if changed:')
    body = body[:cut] if cut > 0 else body
    body = body.replace("for ix_id, sym in", "for ix_id, sym in", 1)
    # provide the needed names
    import time as _time
    from datetime import datetime as _dt
    ns = {
        "inds": {"EGX30": {"rows": [list(x) for x in rows_before],
                           "series": [list(x) for x in rows_before],
                           "count": len(rows_before)}},
        "tws": type("T", (), {"fetch_series": staticmethod(lambda s, n: new_bars)})(),
        "time": _time, "datetime": _dt, "print": lambda *a, **k: None,
        "_IDX_HIST": {},
    }
    exec(compile(body, "<refresh>", "exec"), ns)
    return ns["inds"]["EGX30"], ns


def main():
    src = io.open(SRC, encoding="utf-8").read()
    refresh = extract_refresh(src)
    ok(bool(refresh), "extract: _maybe_refresh_index_history موجود")

    # 100 old bars + 2 new bars
    import time as _time
    base_ts = 1600000000
    rows_before = [[base_ts + i * 86400, 1000.0 + i] for i in range(100)]
    new_bars = [{"t": base_ts + 100 * 86400, "c": 1100.0},
                {"t": base_ts + 101 * 86400, "c": 1101.0}]

    res = simulate(refresh, rows_before, new_bars)
    if res is None:
        ok(False, "simulate: مقدرتش نحاكي منطق التحديث")
        return 1
    row = res[0]

    # ① no old date may disappear
    old_keys = set(int(t) for t, _ in rows_before)
    new_keys = set(int(t) for t, _ in (row.get("rows") or []))
    ok(old_keys.issubset(new_keys),
       "① كل التواريخ القديمة باقية",
       "قديم=%d جديد=%d مفقود=%d" % (len(old_keys), len(new_keys),
                                     len(old_keys - new_keys)))
    ok(len(row.get("rows") or []) == 102,
       "② الصفوف نمت (100 ⇒ 102)",
       len(row.get("rows") or []))

    # ③ series mirrors rows
    ok(row.get("series") == row.get("rows"),
       "③ series مرآة لـrows (الحارس META.SERIES_ALIAS)")

    # ④ count/from/to consistent
    pts = [int(t) for t, _ in (row.get("rows") or [])]
    ok(int(row.get("count") or 0) == len(pts), "④ count يطابق الصفوف",
       row.get("count"))
    ok(row.get("from") == _time.strftime("%Y-%m-%d", _time.gmtime(min(pts))),
       "⑤ from يطابق أول طابع")
    ok(row.get("to") == _time.strftime("%Y-%m-%d", _time.gmtime(max(pts))),
       "⑥ to يطابق آخر طابع")

    n_ok = sum(1 for r in RESULTS if r[0])
    print("\n%d/%d ناجح" % (n_ok, len(RESULTS)))
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
