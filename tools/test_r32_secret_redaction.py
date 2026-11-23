#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔒 R32 · e · ⭐⭐⭐ حارس ⭐⭐⭐ تنقيح ⭐⭐⭐ مخرجات ⭐⭐⭐ مصنّف ⭐⭐⭐ الأسرار ⭐⭐⭐ ⭐⭐⭐

📌 العيب ⭐⭐⭐: ⭐⭐⭐ حقل ⭐⭐⭐ `source` ⭐⭐⭐ في ⭐⭐⭐ `real_leak_list` ⭐⭐⭐ ⭐⭐⭐ كان ⭐⭐⭐ بيطبع ⭐⭐⭐
   ⭐⭐⭐ السطر ⭐⭐⭐ كامل ⭐⭐⭐ ⭐⭐⭐ ⇒ ⭐⭐⭐ أي ⭐⭐⭐ **قيمة ⭐⭐⭐ سر ⭐⭐⭐** ⭐⭐⭐ بتتسرّب ⭐⭐⭐
   ⭐⭐⭐ للملف ⭐⭐⭐ ⭐⭐⭐ وللشاشة ⭐⭐⭐ ⭐⭐⭐ ⇒ ⭐⭐⭐ وفي ⭐⭐⭐ سجل ⭐⭐⭐ محاكاة ⭐⭐⭐ الـCI ⭐⭐⭐ ⭐⭐⭐
   ⭐⭐⭐ ⇒ ⭐⭐⭐ **تسرّب ⭐⭐⭐ حقيقي ⭐⭐⭐** ⭐⭐⭐ ⭐⭐⭐.

✅ الاختبار ⭐⭐⭐ ده ⭐⭐⭐ بيستعمل ⭐⭐⭐ **قيمة ⭐⭐⭐ صناعية ⭐⭐⭐** ⭐⭐⭐ (مش ⭐⭐⭐ توكن ⭐⭐⭐ حقيقي ⭐⭐⭐) ⭐⭐⭐
   ⭐⭐⭐ ⇒ ⭐⭐⭐ المسح ⭐⭐⭐ بيلاقيها ⭐⭐⭐ ⭐⭐⭐ والتصنيف ⭐⭐⭐ بيشوفها ⭐⭐⭐ ⭐⭐⭐
   ⭐⭐⭐ ⭐⭐⭐ والمخرج ⭐⭐⭐ **ما فيهش ⭐⭐⭐ أي ⭐⭐⭐ جزء ⭐⭐⭐ منها ⭐⭐⭐** ⭐⭐⭐ ⭐⭐⭐.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SCANNER = os.path.join(TOOLS, "r28_scan_secrets.py")
CLASSIFIER = os.path.join(TOOLS, "r29_classify_secrets.py")

# ⭐⭐⭐ قيمة ⭐⭐⭐ صناعية ⭐⭐⭐ ⭐ (مش ⭐⭐⭐ توكن ⭐⭐⭐ حقيقي ⭐⭐⭐ ⭐ — ⭐⭐⭐ اصطناعية ⭐⭐⭐ بالكامل ⭐⭐⭐) ⭐⭐⭐
SYNTH = "ghp_" + "Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0Qr1St2Uv3Wx4Yz5Qa7Bc9"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("✅" if ok else "⛔") + " " + name + ((" ⭐ " + detail) if detail else ""))
    return bool(ok)


def main() -> int:
    print("═" * 72)
    print("🔒 R32 · e · ⭐ حارس ⭐ تنقيح ⭐ مخرجات ⭐ مصنّف ⭐ الأسرار ⭐")
    print("═" * 72)
    tmp = tempfile.mkdtemp(prefix="r32-redact-")
    try:
        src = os.path.join(tmp, "synthetic_secret.py")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("# ⭐ ملف ⭐ اصطناعي ⭐ ⭐ — ⭐ ⭐ قيمة ⭐ ⭐ مشبوهة ⭐ ⭐ ⭐\n")
            fh.write('SYNTHETIC_TOKEN = "%s"\n' % SYNTH)
        scan_out = os.path.join(tmp, "scan.json")
        cls_out = os.path.join(tmp, "classification.json")

        r1 = subprocess.run([sys.executable, SCANNER, "--dir", tmp, "--out", scan_out],
                            capture_output=True, text=True, timeout=300)
        check("المسح ⭐ اشتغل ⭐", r1.returncode == 0, (r1.stderr or "")[-90:])
        if not os.path.isfile(scan_out):
            check("ملف المسح ⭐ اتكتب ⭐", False)
            return 1
        scan = json.load(open(scan_out, encoding="utf-8"))
        # ⭐⭐⭐ مخرج ⭐⭐⭐ المسح ⭐⭐⭐ ما ⭐⭐⭐ بيخزّنش ⭐⭐⭐ القيمة ⭐⭐⭐ الخام ⭐⭐⭐ ⭐⭐⭐ (بصمة ⭐⭐⭐ + طول ⭐⭐⭐ فقط ⭐⭐⭐)
        #    ⭐⭐⭐ ⇒ ⭐⭐⭐ الدليل ⭐⭐⭐ على ⭐⭐⭐ الكشف ⭐⭐⭐ = ⭐⭐⭐ عدد ⭐⭐⭐ القيم ⭐⭐⭐ المشبوهة ⭐⭐⭐ + ⭐⭐⭐ الموضع ⭐⭐⭐ ⭐⭐⭐.
        found = len(scan.get("secrets", [])) >= 1
        check("المسح ⭐⭐ كشف ⭐⭐ القيمة ⭐⭐ الصناعية ⭐⭐", found,
              "%d قيمة مشبوهة ⭐" % len(scan.get("secrets", [])))
        raw_scan = open(scan_out, encoding="utf-8").read()
        check("مخرج المسح ⭐⭐ مفيهوش ⭐⭐ القيمة ⭐⭐ الخام ⭐⭐", SYNTH not in raw_scan)

        r2 = subprocess.run([sys.executable, CLASSIFIER, scan_out, cls_out],
                            capture_output=True, text=True, timeout=300)
        check("المصنّف ⭐ اشتغل ⭐", r2.returncode == 0, (r2.stderr or "")[-90:])
        if not os.path.isfile(cls_out):
            check("ملف التصنيف ⭐ اتكتب ⭐", False)
            return 1
        cls_txt = open(cls_out, encoding="utf-8").read()
        check("مخرج المصنّف ⭐⭐ مفيهوش ⭐⭐ القيمة ⭐⭐ الخام ⭐⭐", SYNTH not in cls_txt)
        check("سجل المصنّف ⭐⭐ مفيهوش ⭐⭐ القيمة ⭐⭐ الخام ⭐⭐", SYNTH not in (r2.stdout or ""))
        check("سجل المصنّف ⭐⭐ مفيهوش ⭐⭐ أي ⭐⭐ جزء ⭐⭐ من ⭐⭐ القيمة ⭐⭐",
              SYNTH[:8] not in (r2.stdout or "") and SYNTH[:8] not in cls_txt)
        data = json.loads(cls_txt)
        check("التصنيف ⭐⭐ لسه ⭐⭐ بيشوف ⭐⭐ التسرّب ⭐⭐",
              data.get("total_distinct", 0) >= 1,
              "distinct=%s ⭐ real_leaks=%s ⭐" % (data.get("total_distinct"),
                                                 data.get("real_leaks")))
        for item in data.get("real_leak_list", []):
            src_line = item.get("source") or ""
            check("السطر ⭐⭐ في ⭐⭐ المخرج ⭐⭐ **منقّح** ⭐⭐",
                  "<redacted:" in src_line, src_line[:70])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print("─" * 72)
    if bad:
        print("⛔ فشل %d فحص ⭐ من %d ⭐" % (len(bad), len(RESULTS)))
        for nm, _, d in bad:
            print("   · %s ⭐ %s" % (nm, d))
        return 1
    print("✅ كل %d فحص ناجح ⭐" % len(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
