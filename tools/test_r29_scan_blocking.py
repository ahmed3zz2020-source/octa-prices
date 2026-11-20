#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ (R29 · FINDING-15) ⭐⭐⭐ حارس المسح الأمني ⭐⭐⭐

📌 العيب المقاس (من المراجع المستقل ⭐):
   `scan_zip` ⭐ كان فيه `except Exception: continue` ⭐ على قراءة عضو الـZIP ⭐
   ⇒ ⛔ العضو اللي ما اتقراش ⭐ كان بيتسكت ⭐ ⇒ ⛔ المسح بيقول «نظيف» ⭐
   ⇒ ⛔ مع إن جزء من الأرشيف **ما اتفحصش** ⭐ ⇒ ⛔ كذب ⭐.

✅ المطلوب (R29 ⭐):
   ① ⛔ خطأ قراءة العضو **ظاهر في النتيجة** ⭐.
   ② ⛔ و ⛔ **يمنع اعتماد المسح** ⭐ (ok=false ⭐ + كود خروج ⭐).

📌 التشغيل: python3 tools/test_r29_scan_blocking.py
⛔ مافيش شبكة ⭐ · ⛔ مافيش سر ⭐ · ⛔ بيبني أرشيفات صناعية ⭐ فقط ⭐.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCANNER = os.path.join(REPO, "tools", "r28_scan_secrets.py")

FAILURES: list[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print("  ✅ %s" % label)
    else:
        print("  ⛔⛔⛔ %s" % label)
        FAILURES.append(label)


def build_broken_zip(path: str) -> None:
    """⭐ أرشيف فيه عضو **تالف** ⭐ ⇒ القراءة لازم تفشل ⭐."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("good.txt", "hello")
        zf.writestr("bad.txt", "x" * 64)
    # ⭐ نكسر الـCRC بتاع العضو التاني ⭐ ⇒ `zf.read()` لازم يرمي ⭐
    with open(path, "r+b") as fh:
        data = bytearray(fh.read())
        # ⭐ آخر ٤ بايت من كل سجل ⭐ ⇒ الـCRC ⭐ ⇒ نغيّرها ⭐
        # (أسهل طريقة ⭐: نكسر بايت في وسط بيانات العضو ⭐).
        idx = data.find(b"x" * 64)
        if idx > 0:
            data[idx + 5] = (data[idx + 5] + 1) % 256
        fh.seek(0)
        fh.write(bytes(data))


def run_scan(zips, out_path):
    cmd = [sys.executable, SCANNER, "--quiet", "--out", out_path]
    for z in zips:
        cmd += ["--zip", z]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace", timeout=180)
    payload = {}
    if os.path.isfile(out_path):
        with open(out_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    return proc.returncode, payload


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="r29scan-")
    good = os.path.join(tmp, "good.zip")
    bad = os.path.join(tmp, "bad.zip")
    with zipfile.ZipFile(good, "w") as zf:
        zf.writestr("a.txt", "hello")
    build_broken_zip(bad)

    print("① الأرشيف السليم ⭐ ⇒ ⛔ لازم المسح ينجح ⭐")
    out1 = os.path.join(tmp, "ok.json")
    rc1, p1 = run_scan([good], out1)
    check(p1.get("ok") is True, "الأرشيف السليم ⇒ ok=true ⭐")
    check(rc1 == 0, "الأرشيف السليم ⇒ كود خروج 0 ⭐")
    check(not p1.get("blocking"), "الأرشيف السليم ⇒ مافيش حاجب ⭐")

    print("② الأرشيف التالف ⭐ ⇒ ⛔ لازم المسح ما يُعتمدش ⭐")
    out2 = os.path.join(tmp, "bad.json")
    rc2, p2 = run_scan([bad], out2)
    check(p2.get("ok") is False,
          "الأرشيف التالف ⇒ ok=false ⭐ (⛔ ما يُعتمدش ⭐)")
    check(bool(p2.get("blocking")),
          "الأرشيف التالف ⇒ فيه حاجب مذكور ⭐")
    check(rc2 == 2, "الأرشيف التالف ⇒ كود خروج 2 ⭐")

    print("③ المسار الغلط ⭐ ⇒ ⛔ لازم المسح ما يُعتمدش ⭐")
    out3 = os.path.join(tmp, "missing.json")
    rc3, p3 = run_scan([os.path.join(tmp, "nope.zip")], out3)
    check(p3.get("ok") is False, "المسار الغلط ⇒ ok=false ⭐")
    check(bool(p3.get("blocking")), "المسار الغلط ⇒ فيه حاجب ⭐")

    if FAILURES:
        print("\n⛔⛔⛔ %d فحص فاشل ⭐" % len(FAILURES))
        return 1
    print("\n✅ كل الفحوص سليمة ⭐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
