#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R29 · FINDING-23 · ⭐⭐⭐ سباق فحص `DATA_DIR` ⭐⭐⭐ ⇒ ⭐⭐ lost update ⭐⭐ ⭐.

📌 العيب ⭐⭐: ⛔ `update_prices.py` ⭐ ⭐ كان بيعمل فحص قابلية الكتابة ⭐ ⭐ بملف
   ⭐ ⭐ **اسمه ثابت** ⭐ ⭐ (`.w` ⭐ ⭐) ⭐ ⭐ ⇒ ⛔ عمليتين بتبدأ مع بعض ⭐ ⭐
   ⭐ ⭐ ⇒ ⛔ واحدة بتمسح الملف ⭐ ⭐ والتانية ⭐ ⭐ `unlink()` ⭐ ⭐ بترمي ⭐ ⭐
   ⭐ ⭐ ⇒ ⛔ العملية التانية ⭐ ⭐ تقع في الـfallback ⭐ ⭐ ⇒ ⛔ وبتكتب في
   ⭐ ⭐ **مجلد الكود** ⭐ ⭐ مش مجلد البيانات ⭐ ⭐ ⇒ ⛔ مجلدين مختلفين ⭐ ⭐
   ⭐ ⭐ ⇒ ⛔ وملف قفل مختلف ⭐ ⭐ ⇒ ⛔ ⭐⭐ lost update ⭐⭐ ⭐.

✅ المعيار ⭐⭐: ⭐⭐ كل العمليات ⭐⭐ ⇒ ⭐⭐ **نفس** مجلد البيانات ⭐⭐ ⭐.

📌 التشغيل ⭐: ⭐ python3 tools/test_r29_data_dir_probe_race.py ⭐
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

CHILD = r'''
import os, sys
sys.path.insert(0, os.environ["OCTA_REPO"])
import update_prices as up
print("DIR=%s" % up.DATA_DIR)
print("PROBE_ERR=%s" % getattr(up, "DATA_DIR_PROBE_ERROR", None))
'''

RESULTS = []


def _record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        ("  ::  " + detail) if detail else ""))
    return bool(ok)


def _run_child(data_dir):
    env = dict(os.environ)
    env["OCTA_DATA_DIR"] = str(data_dir)
    env["OCTA_REPO"] = str(REPO)
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONIOENCODING"] = "utf-8"
    env["OCTAD_DEV"] = "1"
    env["OCTA_BG_TASKS"] = "off"
    proc = subprocess.run([sys.executable, "-c", CHILD], env=env,
                          capture_output=True, text=True, timeout=300)
    dirs, err = [], None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("DIR="):
            dirs.append(line[4:].strip())
        if line.startswith("PROBE_ERR="):
            err = line[10:].strip()
    return dirs, err, proc.returncode, (proc.stderr or "")[-300:]


def test_data_dir_probe_is_race_free():
    """⭐⭐ عمليتين مع بعض ⭐⭐ ⇒ ⭐⭐ نفس مجلد البيانات ⭐⭐ ⭐."""
    failures = []
    for attempt in range(4):
        tmp = Path(tempfile.mkdtemp(prefix="r29_probe_race_"))
        try:
            procs = [subprocess.Popen(
                [sys.executable, "-c", CHILD],
                env={**os.environ, "OCTA_DATA_DIR": str(tmp),
                     "OCTA_REPO": str(REPO), "PYTHONPATH": str(REPO),
                     "PYTHONIOENCODING": "utf-8", "OCTAD_DEV": "1",
                     "OCTA_BG_TASKS": "off"},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)]
            outs = []
            for p in procs:
                o, e = p.communicate(timeout=300)
                outs.append((p.returncode, o.decode("utf-8", "replace"),
                             e.decode("utf-8", "replace")[-200:]))
            dirs = []
            for rc, o, e in outs:
                if rc != 0:
                    failures.append("child rc=%d: %s" % (rc, e))
                    continue
                for line in o.splitlines():
                    if line.startswith("DIR="):
                        dirs.append(line[4:].strip())
            if len(dirs) != 2:
                failures.append("attempt %d ⇒ {%d} الردود ⭐" % (attempt, len(dirs)))
                continue
            wrong = [d for d in dirs if d != str(tmp)]
            if wrong:
                failures.append("attempt %d ⇒ مجلد غلط ⭐: %s ⭐ (المتوقع %s ⭐)"
                                % (attempt, wrong, tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _record("R29-DDR-01: عمليتين مع بعض ⭐ ⇒ نفس مجلد البيانات ⭐ (بلا fallback ⭐)",
                   not failures,
                   ("; ".join(failures[:4]) if failures
                    else "٤ محاولات ⭐ × عمليتين ⭐ ⇒ مجلد واحد ⭐"))


def test_probe_file_name_is_unique_per_process():
    """⭐⭐⭐ ملف الفحص ⭐⭐⭐ لازم يكون **بيلpid** ⭐⭐⭐ مش اسم ثابت ⭐⭐⭐."""
    src = (REPO / "update_prices.py").read_text(encoding="utf-8")
    fixed = 'DATA_DIR / ".w"'
    per_pid = '.w-%d' % os.getpid() in src or '(".w-%d" % os.getpid())' in src
    return _record("R29-DDR-02: اسم ملف الفحص ⭐ فريد ⭐ (بيلpid ⭐) ⭐ مش ثابت ⭐",
                   (fixed not in src) and per_pid,
                   "اسم ثابت موجود ⭐: %s ⭐" % fixed if fixed in src else "الاسم فريد ⭐")


def main() -> int:
    test_data_dir_probe_is_race_free()
    test_probe_file_name_is_unique_per_process()
    passed = sum(1 for r in RESULTS if r["ok"])
    print("==== R29 · FINDING-23 · سباق فحص DATA_DIR ====")
    print("passed %d / %d" % (passed, len(RESULTS)))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
