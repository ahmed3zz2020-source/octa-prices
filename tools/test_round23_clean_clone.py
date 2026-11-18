#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 اختبار النسخ النظيف — الجولة ٢٣ (من الحزم المستقلّة ⭐).

📌 الفكرة: الحزمة المستقلّة لازم تكون **قابلة للنسخ والتشغيل لوحدها** ⭐
   ⇒ من الـZIP المستخرج:
      ① `git clone` لحزمة Git (في مجلد جديد تماماً ⭐)
      ② تثبيت الاعتماديات (`pip install -r requirements.txt` · `npm test`)
      ③ تشغيل مجموعة اختبارات الباك من الـclone نفسه ⭐
      ④ تشغيل `npm test` للواجهة من الـclone بتاعها ⭐

📌 التصنيف: أي ملف فشل بيتقارن **بالأساس** (الفرع قبل الجولة) ⇒
   · فشل على الأساس ⇒ عيب سابق / بيئة (مش انحدار ⭐)
   · نجح على الأساس ⇒ انحدار حقيقي ⭐ (والحارس بيفشل ⭐)

📌 مافيش شبكة إجبارية · مافيش نشر · مافيش تكلفة.
⛔ لو اعتماد ماب installing ⇒ بيتقال صراحةً (مش بيتخطّى في صمت ⭐).
"""

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROUND = "23"
OUT_DIR = pathlib.Path("/workspace/output")
BE_BRANCH = "review/round%s-backend" % ROUND
FE_BRANCH = "review/round%s-frontend" % ROUND
BE_BASE_R22 = "d61f279a8d20f6f252dfea459cf8f9782469f552"
FE_BASE_R22 = "71ba99a9fb6595f1c80da2debabe222e8e1ab1b2"

# ⛔ اختبارات الباك اللي بتحتاج خادم حيّ (مش موجودة في البيئة المعزولة ⭐)
SERVER_TESTS = {
    "test_security_p0.py",
    "test_security_batch02.py",
    "test_security_bgstore.py",
    "test_pin_challenge.py",
    "test_signup_flow.py",
}

PYPI_INDEX = "https://pypi.org/simple"


def run(cmd, cwd=None, env=None, timeout=1200):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -9, "TIMEOUT"
    except Exception as exc:
        return -1, "%s: %s" % (type(exc).__name__, exc)


def extract_zip(zip_path, dest):
    dest = pathlib.Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    return dest


def clone_bundle(bundle, dest, branch):
    rc, out = run(["git", "clone", "--quiet", str(bundle), str(dest)], timeout=900)
    if rc != 0:
        return None, out.strip()[:200]
    rc, _ = run(["git", "-C", str(dest), "checkout", "--quiet", branch], timeout=300)
    if rc != 0:
        # ⛔ الفرع ممكن يكون تتبّع بعيد بس (من clone حزمة Git ⭐)
        rc, out2 = run(["git", "-C", str(dest), "checkout", "--quiet", "-b",
                        branch, "origin/" + branch], timeout=300)
        if rc != 0:
            return None, "checkout فشل: %s" % out2.strip()[:160]
    return dest, ""


def count_cases(out):
    m = re.findall(r"Ran (\d+) tests?", out)
    return int(m[-1]) if m else 0


def backend_suite(clone_dir, py, files, timeout=600):
    """يشغّل ملفات الاختبار واحد واحد ⇒ يعدّ النجاح/الفشل والحالات."""
    rows = []
    for rel in files:
        t0 = time.time()
        rc, out = run([py, rel], cwd=str(clone_dir), timeout=timeout)
        n = count_cases(out)
        ok = (rc == 0) and not re.search(r"(^FAILED\b|^ERROR:|❌)", out, re.M)
        last = out.strip().splitlines()[-1][:160] if out.strip() else ""
        rows.append({"file": rel, "ok": ok, "cases": n, "rc": rc,
                     "seconds": round(time.time() - t0, 1), "last": last})
    return rows


def install_backend_deps(clone_dir, work):
    """(ok, note) — تثبيت اعتماديات الباك في بيئة معزولة."""
    req = pathlib.Path(clone_dir) / "requirements.txt"
    if not req.is_file():
        return False, "requirements.txt مش موجود"
    venv = pathlib.Path(work) / "venv"
    rc, out = run([sys.executable, "-m", "venv", str(venv)], timeout=600)
    if rc != 0:
        return False, "venv فشل: %s" % out.strip().splitlines()[-1][:120]
    pip = venv / "bin" / "pip"
    cache = "/workspace/.home/.cache/pip"
    attempts = [
        ([str(pip), "install", "--disable-pip-version-check", "-q",
          "--cache-dir", cache, "-r", str(req)], "pip (الافتراضي + الكاش)"),
        ([str(pip), "install", "--disable-pip-version-check", "-q",
          "--index-url", PYPI_INDEX, "-r", str(req)], "pip (%s)" % PYPI_INDEX),
    ]
    notes = []
    for cmd, label in attempts:
        rc, out = run(cmd, timeout=1800)
        if rc == 0:
            return True, "%s ✅" % label
        notes.append("%s فشل: %s" % (label, out.strip().splitlines()[-1][:100]
                                     if out.strip() else "rc=%s" % rc))
    return False, " · ".join(notes)


def classify_backend_failures(clone_dir, base_clone, py, rows):
    """لكل ملف فاشل: هل بيفشل على الأساس كمان؟ ⇒ سابق ولا انحدار ⭐."""
    out_rows = []
    for r in rows:
        if r["ok"]:
            continue
        base_ok = None
        base_last = ""
        if base_clone is not None:
            rc, bout = run([py, r["file"]], cwd=str(base_clone), timeout=600)
            base_ok = (rc == 0) and not re.search(r"(^FAILED\b|^ERROR:|❌)", bout, re.M)
            base_last = bout.strip().splitlines()[-1][:120] if bout.strip() else ""
        kind = "regression"
        if r["file"] in SERVER_TESTS:
            kind = "server-dependent"
        elif base_ok is False:
            kind = "pre-existing (base)"
        elif base_ok is True:
            kind = "regression"
        out_rows.append({"file": r["file"], "kind": kind, "rc": r["rc"],
                         "last": r["last"], "base_last": base_last,
                         "server_dependent": r["file"] in SERVER_TESTS})
    return out_rows


def run_backend(zip_path, work):
    info = {"ok": False, "summary": "؟", "notes": [], "failures": [],
            "deps_ok": False, "deps_note": ""}
    src = extract_zip(zip_path, pathlib.Path(work) / "zip")
    bundles = sorted((src / "bundles").glob("backend*.bundle"))
    if not bundles:
        info["notes"].append("مفيش حزمة git في الحزمة")
        return info
    clone = pathlib.Path(work) / "clone"
    got, err = clone_bundle(bundles[0], clone, BE_BRANCH)
    if got is None:
        info["notes"].append("clone فشل: %s" % err)
        return info
    rc, sha = run(["git", "-C", str(clone), "rev-parse", "HEAD"], timeout=120)
    info["clone_sha"] = sha.strip()
    env = json.loads((src / "ENVIRONMENT.json").read_text(encoding="utf-8"))
    info["expected_sha"] = env["backend"]["review_sha"]

    deps_ok, deps_note = install_backend_deps(clone, work)
    info["deps_ok"] = deps_ok
    info["deps_note"] = deps_note
    if not deps_ok:
        info["notes"].append("⛔ اعتماديات الباك ماب installing ⭐: %s" % deps_note)
        return info
    py = str(pathlib.Path(work) / "venv" / "bin" / "python")

    files = sorted(p.name for p in clone.glob("test_*.py"))
    rows = backend_suite(clone, py, files)

    base_clone = None
    rc, _ = run(["git", "-C", str(clone), "checkout", "--quiet", BE_BASE_R22],
                timeout=300)
    if rc == 0:
        base_clone = pathlib.Path(work) / "clone_base"
        shutil.copytree(clone, base_clone, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".git"))
        run(["git", "-C", str(base_clone), "checkout", "--quiet", BE_BASE_R22],
            timeout=300)
    run(["git", "-C", str(clone), "checkout", "--quiet", BE_BRANCH], timeout=300)

    failures = classify_backend_failures(clone, base_clone, py, rows)
    passed = sum(1 for r in rows if r["ok"])
    cases = sum(r["cases"] for r in rows)
    regressions = [f for f in failures if f["kind"] == "regression"]
    info["files"] = len(rows)
    info["passed_files"] = passed
    info["failed_files"] = len(failures)
    info["cases"] = cases
    info["failures"] = failures
    info["regressions"] = [f["file"] for f in regressions]
    info["summary"] = "%d/%d ملف · %d حالة" % (passed, len(rows), cases)
    info["ok"] = not regressions
    if regressions:
        info["notes"].append("⛔ انحدار حقيقي: %s" % ", ".join(
            f["file"] for f in regressions))
    if not info["ok"]:
        env_note = [f for f in failures if f["kind"] == "server-dependent"]
        if env_note:
            info["notes"].append("فشل بيحتاج خادم حيّ (مش متاح ⭐): %s" % ", ".join(
                f["file"] for f in env_note))
        pre = [f for f in failures if f["kind"] == "pre-existing (base)"]
        if pre:
            info["notes"].append("فشل موجود على الأساس كمان ⭐: %s" % ", ".join(
                f["file"] for f in pre))
    return info


def run_frontend(zip_path, work):
    info = {"ok": False, "summary": "؟", "notes": [], "pass": 0, "fail": 0,
            "failed_files": [], "deps_ok": True, "deps_note": "مفيش اعتماديات خارجية ⭐"}
    src = extract_zip(zip_path, pathlib.Path(work) / "zip")
    bundles = sorted((src / "bundles").glob("frontend*.bundle"))
    if not bundles:
        info["notes"].append("مفيش حزمة git في الحزمة")
        return info
    clone = pathlib.Path(work) / "clone"
    got, err = clone_bundle(bundles[0], clone, FE_BRANCH)
    if got is None:
        info["notes"].append("clone فشل: %s" % err)
        return info
    rc, sha = run(["git", "-C", str(clone), "rev-parse", "HEAD"], timeout=120)
    info["clone_sha"] = sha.strip()
    env = json.loads((src / "ENVIRONMENT.json").read_text(encoding="utf-8"))
    info["expected_sha"] = env["frontend"]["review_sha"]

    rc, out = run(["npm", "test"], cwd=str(clone), timeout=2400)
    mp = re.search(r"# pass (\d+)", out)
    mf = re.search(r"# fail (\d+)", out)
    info["pass"] = int(mp.group(1)) if mp else 0
    info["fail"] = int(mf.group(1)) if mf else 0
    info["summary"] = "%d ناجح / %d فاشل" % (info["pass"], info["fail"])
    info["ok"] = (rc == 0) and info["fail"] == 0
    if info["ok"]:
        return info

    # ⛔ فشل ⇒ نحدّد الملفات ونقارن بالأساس ⭐
    files = sorted((clone / "assets" / "tests").glob("*.test.js"))
    bad = []
    for f in files:
        rc2, o2 = run(["node", "--test", str(f)], cwd=str(clone), timeout=600)
        if rc2 != 0 or re.search(r"# fail [1-9]", o2):
            bad.append(f.name)
    info["failed_files"] = bad
    base_clone = None
    rc, _ = run(["git", "-C", str(clone), "checkout", "--quiet", FE_BASE_R22],
                timeout=300)
    if rc == 0:
        base_clone = pathlib.Path(work) / "clone_base"
        shutil.copytree(clone, base_clone, symlinks=True,
                        ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
        run(["git", "-C", str(base_clone), "checkout", "--quiet", FE_BASE_R22],
            timeout=300)
    run(["git", "-C", str(clone), "checkout", "--quiet", FE_BRANCH], timeout=300)
    regressions = []
    for name in bad:
        if base_clone is None:
            regressions.append(name)
            continue
        rc3, o3 = run(["node", "--test", str(base_clone / "assets" / "tests" / name)],
                      cwd=str(base_clone), timeout=600)
        if rc3 == 0 and not re.search(r"# fail [1-9]", o3):
            regressions.append(name)
    info["regressions"] = regressions
    if regressions:
        info["notes"].append("⛔ انحدار حقيقي: %s" % ", ".join(regressions))
    else:
        info["notes"].append("الفشل موجود على الأساس كمان ⭐ (مش انحدار)")
    info["ok"] = not regressions
    return info


def main():
    ap = argparse.ArgumentParser(description="اختبار النسخ النظيف — الجولة ٢٣")
    ap.add_argument("--backend-zip",
                    default=str(OUT_DIR / ("OCTA-ROUND%s-BACKEND.zip" % ROUND)))
    ap.add_argument("--frontend-zip",
                    default=str(OUT_DIR / ("OCTA-ROUND%s-FRONTEND.zip" % ROUND)))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = pathlib.Path(tempfile.mkdtemp(prefix="r23_cleanclone_"))
    result = {"ok": False, "backend": {}, "frontend": {}}
    try:
        print("=== اختبار النسخ النظيف — الجولة %s ===" % ROUND)
        print("--- الباك ---")
        result["backend"] = run_backend(pathlib.Path(args.backend_zip),
                                         pathlib.Path(work) / "backend")
        print("--- الواجهة ---")
        result["frontend"] = run_frontend(pathlib.Path(args.frontend_zip),
                                          pathlib.Path(work) / "frontend")
        result["ok"] = bool(result["backend"].get("ok")) and \
            bool(result["frontend"].get("ok"))
    finally:
        if args.keep:
            print("temp kept: %s" % work)
        else:
            shutil.rmtree(work, ignore_errors=True)

    be = result["backend"]
    fe = result["frontend"]
    print()
    print("الباك   : %s · اعتماديات: %s · %s" % (be.get("summary"), be.get("deps_note"),
                                                  " · ".join(be.get("notes", []))))
    print("الواجهة: %s · %s" % (fe.get("summary"), " · ".join(fe.get("notes", []))))
    for f in be.get("failures", []):
        print("   ⛔ %s · %s · %s" % (f["file"], f["kind"], f["last"]))
    for f in fe.get("failed_files", []):
        print("   ⛔ %s" % f)
    print("النتيجة: %s" % ("✅" if result["ok"] else "⛔ FAIL"))

    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print("JSON: %s" % out)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
