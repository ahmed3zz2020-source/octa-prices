#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R29 · ماسح الحزم ⭐ — بصمة كل أرشيف + مسح محتواه ⭐.

⭐⭐⭐ القاعدة ⭐⭐⭐: ⛔ أي أرشيف ⭐ ⭐ ما فتحش ⭐ ⭐ أو بصمته ⭐ ⭐ اختلفت ⭐ ⭐
   ⇒ ⛔ النتيجة **ما تُعتمدش** ⭐ ⭐ (مش بس خطأ مطبوع ⭐ ⭐) ⭐ ⭐ ⇒ `ok=false` ⭐ ⭐
   ⭐ ⭐ وكود خروج ⭐ ⭐ 2 ⭐ ⭐ (FINDING-15 ⭐ ⭐ نفس القاعدة ⭐ ⭐) ⭐ ⭐.

الاستخدام:
    python3 tools/r29_scan_packages.py \
        --manifest /workspace/output/OCTA-ROUND29-PACKAGES.json \
        --dir /workspace/output/OCTA-ROUND29-DELIVERY \
        --out /workspace/output/r29/packages.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from r28_scan_secrets import Report, archive_fingerprint, scan_zip  # noqa: E402
from r29_classify_secrets import classify, read_line  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="R29 · ماسح الحزم ⭐")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dir", required=True, help="مجلد الحزم ⭐")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    expected = {p["zip"]: p for p in manifest.get("packages", [])}

    report = Report()
    archives = []
    blocking = []

    for name, exp in sorted(expected.items()):
        path = os.path.join(args.dir, name)
        if not os.path.isfile(path):
            # ⭐⭐⭐ حزمة التسليم ⭐⭐⭐ ⇒ ⭐ ⭐ في المجلد الأعلى ⭐ ⭐ ⭐
            alt = os.path.join(os.path.dirname(os.path.abspath(args.dir)), name)
            if os.path.isfile(alt):
                path = alt
        if not os.path.isfile(path):
            msg = "الأرشيف مش موجود ⭐: %s ⭐" % path
            blocking.append(msg)
            archives.append({"zip": name, "scanned": False, "scan_error": msg})
            continue
        try:
            info = archive_fingerprint(path)
        except Exception as exc:  # noqa: BLE001
            msg = "فشل قراءة الأرشيف ⭐ (%s) ⭐: %s ⭐" % (name, exc)
            blocking.append(msg)
            archives.append({"zip": name, "scanned": False, "scan_error": msg})
            continue
        actual = sha256_file(path)
        match = actual == exp.get("sha256")
        if not match:
            msg = "بصمة الأرشيف مختلفة ⭐: %s ⭐ (المتوقع %s ⭐ ⭐ الفعلي %s ⭐)" % (
                name, str(exp.get("sha256"))[:12], actual[:12])
            blocking.append(msg)
        archives.append({
            "zip": name,
            "bytes": info.get("bytes"),
            "files": info.get("files"),
            "sha256": actual,
            "manifest_sha256": exp.get("sha256"),
            "md5": exp.get("md5"),
            "sha256_matches_manifest": match,
            "scan_error": None,
        })

    # ⭐ مسح محتوى كل أرشيف ⭐ (بنفس قواعد الماسح ⭐)
    zips = [os.path.join(args.dir, n) for n in sorted(expected)]
    for z in zips:
        if os.path.isfile(z):
            scan_zip(z, report, siblings=zips)

    by_fp: dict[str, list] = {}
    for f in report.findings:
        by_fp.setdefault(f.fingerprint, []).append(f)
    distinct = len(by_fp)

    # ⭐⭐⭐ (R29) ⭐⭐⭐ التصفية ⭐⭐⭐ ⇒ ⭐ ⭐ «تسرّب حقيقي» ⭐ ⭐ ≠ ⭐ ⭐ أي تطابق ⭐ ⭐ ⭐
    # 📌 السبب ⭐: ⛔ النتيجة ⭐ ⭐ (زي `os.environ` ⭐ ⭐ أو placeholder ⭐ ⭐) ⭐ ⭐
    #    ⭐ ⭐ **مش سر** ⭐ ⭐ ⇒ ⛔ العدّ الخام ⭐ ⭐ بيكبّر الأرقام ⭐ ⭐ وبيوّهم ⭐ ⭐ ⭐
    real_leaks = []
    reasons: dict[str, int] = {}
    for f in report.findings:
        loc = {"location": f.location, "line": f.line, "scope": f.scope}
        line = read_line(loc)
        verdict, why = classify(line, f.location)
        reasons[why] = reasons.get(why, 0) + 1
        if verdict == "real_leak":
            real_leaks.append({"fingerprint": f.fingerprint, "pattern": f.pattern,
                               "location": f.location, "line": f.line,
                               "scope": f.scope})

    ok = ((not blocking) and (not report.blocking) and (not report.errors)
          and (not real_leaks))
    out = {
        "ok": ok,
        "note": ("مسح %d أرشيف ⭐ (بصمة SHA256 لكل واحد ⭐ مطابقة للمانيفست ⭐) ⭐ ⇒ %d قيمة مسرّبة ⭐ ⇒ %s ⭐"
                 % (len(archives), distinct,
                    "نظيف ⭐⭐" if ok else "فيه حاجب ⭐ ⇒ ما يُعتمدش ⭐")),
        "archives": archives,
        "blocking": blocking + report.blocking,
        "errors": report.errors,
        "scanned_zip_members": report.scanned_zip_members,
        "distinct_secrets": distinct,
        "real_leaks": len(real_leaks),
        "real_leak_list": real_leaks[:20],
        "reasons": reasons,
        "findings": [f.__dict__ for f in report.findings][:50],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": ok, "archives": len(archives),
                      "distinct_secrets": distinct,
                      "real_leaks": len(real_leaks),
                      "blocking": len(out["blocking"])}, ensure_ascii=False))
    for b in out["blocking"]:
        print("   ⛔", b)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
