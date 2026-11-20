#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📎 OCTA — باني أدلة الجولة ٢٧ (R27) ⭐

📌 بيولّد ⭐ من **نتائج القياس الفعلية** ⭐ (مش من أرقام مكتوبة ⭐):
   ① fe_suite_r27.md ⭐ — ملخص مجموعة اختبارات الواجهة ⭐ (من سجل TAP ⭐)
   ② backend_suite_r27.md ⭐ — ملخص مجموعة اختبارات الباك ⭐ (من JSON المصنِّف ⭐)
   ③ ينسخ السجلات الخام ⭐ (fe_suite_r27.log ⭐ · backend_suite_r27.json ⭐)

⛔ ممنوع ⭐: أي رقم مش traced ⭐ · أي سر ⭐ · أي نشر ⭐.
⛔ كل رقم في المخرجات مصدره ملف القياس ⭐ (باسمه ⭐ وبصمته ⭐).

📌 التشغيل ⭐:
   FE_LOG=... BE_JSON=... OUT_DIR=... python3 tools/r27_build_evidence.py
"""
import hashlib
import json
import os
import re
import shutil
import sys

FE_LOG = os.environ.get("FE_LOG", "")
BE_JSON = os.environ.get("BE_JSON", "")
OUT_DIR = os.environ.get("OUT_DIR", "")
ROUND = os.environ.get("ROUND", "27")
BE_SHA = os.environ.get("BE_SHA", "")
FE_SHA = os.environ.get("FE_SHA", "")
BE_CI_SHA = os.environ.get("BE_CI_SHA", "")
FE_CI_SHA = os.environ.get("FE_CI_SHA", "")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fe_summary(path):
    """⭐ يحلّل سجل TAP ⭐ (مصدر الأرقام الوحيد ⭐)."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    out = {"tests": 0, "pass": 0, "fail": 0, "skipped": 0, "duration_ms": 0}
    for key, field in (("tests", "tests"), ("pass", "pass"), ("fail", "fail"),
                       ("skipped", "skipped"), ("duration_ms", "duration_ms")):
        m = re.search(r"^# %s (\d+(?:\.\d+)?)$" % key, raw, re.M)
        if m:
            out[field] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    # ⭐ الفاشلين ⭐ (باسم الملف ⭐ + العنوان ⭐)
    fails = []
    cur = None
    for line in raw.splitlines():
        m = re.match(r"^not ok (\d+) - (.*)$", line)
        if m:
            cur = {"no": int(m.group(1)), "title": m.group(2).strip(), "file": None}
            fails.append(cur)
            continue
        if cur is not None and cur["file"] is None:
            m2 = re.search(r"location: '([^']+)'", line)
            if m2:
                mm = re.search(r"/assets/tests/([^:]+):", m2.group(1))
                cur["file"] = mm.group(1) if mm else m2.group(1)
    out["fails"] = fails
    return out


def be_summary(path):
    doc = json.load(open(path, encoding="utf-8"))
    files = doc.get("files") or []
    rows = []
    for f in files:
        rows.append({
            "file": f.get("file"),
            "status": f.get("status"),
            "gate_status": f.get("gate_status"),
            "rc": f.get("rc"),
            "cases": f.get("cases"),
            "skipped_cases": f.get("skipped_cases"),
            "duration_s": f.get("duration_s"),
            "reason": f.get("reason"),
            "isolated": f.get("isolated"),
            "gate": f.get("gate"),
        })
    return doc.get("summary") or {}, rows


def main():
    if not (FE_LOG and BE_JSON and OUT_DIR):
        raise SystemExit("FE_LOG/BE_JSON/OUT_DIR مطلوبين ⭐")
    os.makedirs(OUT_DIR, exist_ok=True)

    fe = fe_summary(FE_LOG)
    be_sum, be_rows = be_summary(BE_JSON)

    # ── ① ملخص الواجهة ⭐
    lines = []
    lines.append("# مجموعة اختبارات الواجهة — الجولة ٢٧ (R27)")
    lines.append("")
    lines.append("المصدر: `fe_suite_r27.log` (سجل TAP الخام ⭐ · نفس الـcommit ⭐).")
    lines.append("")
    lines.append("## الأرقام")
    lines.append("")
    lines.append("- عدد الاختبارات: %s" % fe["tests"])
    lines.append("- ناجح: %s" % fe["pass"])
    lines.append("- فاشل: %s" % fe["fail"])
    lines.append("- متخطى: %s" % fe["skipped"])
    lines.append("- المدة: %.1f ثانية" % (fe["duration_ms"] / 1000.0))
    lines.append("")
    lines.append("## الفاشلين")
    lines.append("")
    if not fe["fails"]:
        lines.append("مفيش ⭐ (٠ فاشل ⭐).")
    else:
        lines.append("| الملف | الاختبار |")
        lines.append("|---|---|")
        for f in fe["fails"]:
            lines.append("| %s | %s |" % (f["file"] or "?", f["title"]))
    lines.append("")
    lines.append("## البصمات")
    lines.append("")
    lines.append("- ملف السجل: sha256 `%s`" % sha256_file(FE_LOG))
    lines.append("- SHA المرشح (الواجهة): `%s`" % FE_SHA)
    lines.append("- فرع الـCI (الواجهة): `%s`" % FE_CI_SHA)
    lines.append("")
    with open(os.path.join(OUT_DIR, "fe_suite_r27.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # ── ② ملخص الباك ⭐
    lines = []
    lines.append("# مجموعة اختبارات الباك — الجولة ٢٧ (R27)")
    lines.append("")
    lines.append("المصدر: `backend_suite_r27.json` (مُصنِّف الـCI ⭐ · نفس الـcommit ⭐).")
    lines.append("")
    lines.append("## الأرقام")
    lines.append("")
    lines.append("- عدد الملفات: %s" % be_sum.get("files"))
    lines.append("- ناجح: %s" % be_sum.get("passed"))
    lines.append("- فاشل: %s" % be_sum.get("failed"))
    lines.append("- متخطى: %s" % be_sum.get("skipped"))
    lines.append("- محجوب: %s" % be_sum.get("blocked"))
    lines.append("- عدد الحالات: %s" % be_sum.get("cases"))
    lines.append("- المدة: %s ثانية" % be_sum.get("duration_s"))
    lines.append("")
    lines.append("## الملفات المعزولة (بوابة بديلة إلزامية ⭐)")
    lines.append("")
    lines.append("| الملف | البوابة | السبب |")
    lines.append("|---|---|---|")
    iso = [r for r in be_rows if r.get("isolated")]
    if not iso:
        lines.append("مفيش ⭐.")
    for r in iso:
        lines.append("| %s | %s | %s |" % (r["file"], r.get("gate") or "?", r.get("reason") or ""))
    lines.append("")
    lines.append("## الملفات الفاشلة")
    lines.append("")
    bad = [r for r in be_rows if r.get("status") != "passed"]
    if not bad:
        lines.append("مفيش ⭐ (٠ فاشل ⭐).")
    else:
        lines.append("| الملف | الحالة | السبب |")
        lines.append("|---|---|---|")
        for r in bad:
            lines.append("| %s | %s | %s |" % (r["file"], r["status"], r.get("reason") or ""))
    lines.append("")
    lines.append("## البصمات")
    lines.append("")
    lines.append("- ملف النتائج: sha256 `%s`" % sha256_file(BE_JSON))
    lines.append("- SHA المرشح (الباك): `%s`" % BE_SHA)
    lines.append("- فرع الـCI (الباك): `%s`" % BE_CI_SHA)
    lines.append("")
    with open(os.path.join(OUT_DIR, "backend_suite_r27.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # ── ③ نسخ السجلات الخام ⭐
    shutil.copy2(FE_LOG, os.path.join(OUT_DIR, "fe_suite_r27.log"))
    shutil.copy2(BE_JSON, os.path.join(OUT_DIR, "backend_suite_r27.json"))

    print("FE: tests=%s pass=%s fail=%s" % (fe["tests"], fe["pass"], fe["fail"]))
    print("BE: %s" % json.dumps(be_sum, ensure_ascii=False))
    print("RESULT: %s" % ("CLEAN" if (fe["fail"] == 0 and not [r for r in be_rows if r.get("status") != "passed"]) else "HAS_FAILURES"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
