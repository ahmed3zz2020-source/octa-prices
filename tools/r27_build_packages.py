#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📦 OCTA — باني الحزم الرقمي (الجولة ٢٧ · R27) ⭐

📌 الغرض ⭐: ⭐ بناء الحزم من **شجرة git** ⭐ (مش من مجلد الشغل ⭐)
   ⇒ ⭐ النتيجة **حتمية** ⭐ وقابلة لإعادة البناء ⭐ (نفس SHA ⇒ نفس الحزمة ⭐).

📌 قاعدة الاختيار ⭐ (موثّقة ⭐ · بتتسرّبش ⭐):
   ① BACKEND  ⭐ = كل ملفات الشجرة في SHA المرشّح للباك ⭐
   ② FRONTEND ⭐ = كل ملفات الشجرة في SHA المرشّح للواجهة ⭐
   ③ CI       ⭐ = ملفا الـworkflow ⭐ + أدوات الـCI ⭐ (باك + واجهة ⭐)
   ④ DELIVERY ⭐ = الأدلة ⭐ + ملف التسليم ⭐ + المربع ⭐ + ملف الحزم ⭐

⛔ ممنوع ⭐: أي سر ⭐ · أي اتصال بالشبكة ⭐ · أي نشر ⭐ · أي مورد مدفوع ⭐.
⛔ كل حزمة بتتمسح ضو ⭐:
   · مسح أسرار ⭐ (أنماط معروفة ⭐) ⇒ لازم 0 ⭐
   · مسح نص ملوّث ⭐ (FFFD ⭐ / CJK ⭐ / Hangul ⭐ / Cyrillic ⭐) ⇒ لازم 0 ⭐
   · بصمتين ⭐: md5 ⭐ + sha256 ⭐ + عدد الملفات ⭐ + الحجم ⭐

📌 التشغيل ⭐:
   BE_REPO=... FE_REPO=... BE_SHA=... FE_SHA=... CI_SHA=... CI_FE_SHA=... \
   EVIDENCE_DIR=... OUT_DIR=... python3 tools/r27_build_packages.py
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

BE_REPO = os.environ.get("BE_REPO", "/workspace/octa-prices")
FE_REPO = os.environ.get("FE_REPO", "/workspace/octa")
BE_SHA = os.environ.get("BE_SHA", "")
FE_SHA = os.environ.get("FE_SHA", "")
CI_SHA = os.environ.get("CI_SHA", "")
CI_FE_SHA = os.environ.get("CI_FE_SHA", "")
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "")
OUT_DIR = os.environ.get("OUT_DIR", "/workspace/output")
ROUND = os.environ.get("ROUND", "27")

# ⛔ أنماط الأسرار ⭐ (مسح ⇒ لازم صفر ⭐)
# ⭐ مواضع معروفة ⭐ (مش تلوّث ⭐) ⭐ — السبب مكتوب ⭐ (مراجعة يدوية ⭐)
KNOWN_DIRTY = {
    "assets/tests/radar.test.js":
        "نطاقات الحارس نفسه ⭐ (الكود اللي بيكشف الحروف ⭐) ⭐ — تلوّث مقصود ⭐",
    "data/data_markets.js":
        "اسم شركة كورية مدرجة في السعودية ⭐ (TADAWUL 8010 ⭐) ⭐ — اسم سوق صحيح ⭐",
    "data/market_names.js":
        "اسم شركة كورية مدرجة في السعودية ⭐ (TADAWUL 8010 ⭐) ⭐ — اسم سوق صحيح ⭐",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9/+_-]{24,}['\"]"),
]
# ⛔ محارف ممنوعة في الملفات العربية ⭐
DIRTY = [
    ("FFFD", re.compile("\ufffd")),
    ("CJK", re.compile(r"[一-鿿]")),
    ("HANGUL", re.compile(r"[가-힯]")),
    ("CYRILLIC", re.compile(r"[Ѐ-ӿ]")),
]


def sh(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def sh_bytes(cmd, cwd=None):
    """⛔ نسخة **ثنائية** ⭐ (git show ⭐ بملفات ثنائية ⭐ ⇒ مافيش ترميز ⭐)."""
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                       capture_output=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def tree_files(repo, sha):
    rc, out, err = sh(["git", "ls-tree", "-r", "--name-only", sha], cwd=repo)
    if rc != 0:
        raise SystemExit("git ls-tree failed in %s: %s" % (repo, err[:200]))
    return [x for x in out.splitlines() if x.strip()]


def read_bytes(repo, sha, path):
    """⛔ القراءة من **كائن git** بس ⭐ (مش من شجرة العمل ⭐).

    📌 السبب ⭐ (درس مقيس ⭐): القراءة من الملفات على القرح ⭐ كانت بتجيب
    ⭐ محتوى **الفرع الافتراضي** (main ⭐) ⭐ مش محتوى الـSHA المطلوب ⭐
    ⭐ ⇒ ⭐ الحزمة كانت هتتبني من كود تاني ⭐ ⇒ ⭐ بصمة غلط ⭐.
    ⛔⇒ القراءة من git show ⭐ ⇒ ⭐ النتيجة مربوطة بالـSHA ⭐ دائماً ⭐."""
    rc, out, err = sh_bytes(["git", "show", "%s:%s" % (sha, path)], cwd=repo)
    if rc != 0:
        return None
    return out


def scan(data, path=""):
    """⛔ رجّع (سرّ؟ · نص ملوّث؟) ⭐

    📌 الملفات الثنائية ⭐ (صور ⭐ خطوط ⭐) ⭐ ⇒ ⛔ ما تتحقّقش عليها ⭐
       (مش سرّ ⭐ ومش نص ⭐) ⇒ ⭐ بتتخطّى ⭐ (مش بتتوسم ⭐).
    📌 اللي بيتسجّل ⭐: أسماء الملفات ⭐ ⇒ ⭐ نقدر نراجع كل موضع ⭐."""
    secret = False
    dirty = []
    if b"\x00" in data[:4096]:
        return False, []          # ⛔ ملف ثنائي ⭐ ⇒ يتخطّى ⭐
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False, []
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            secret = True
            break
    if path in KNOWN_DIRTY:
        return secret, []          # ⭐ موضع معروف ⭐ (السبب في KNOWN_DIRTY ⭐)
    for name, pat in DIRTY:
        if pat.search(text):
            dirty.append(name)
    return secret, dirty


def build_zip(path, entries):
    """entries = [(arcname, bytes)] ⭐"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, data in entries:
            info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return path


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if not (BE_SHA and FE_SHA and CI_SHA and CI_FE_SHA):
        raise SystemExit("BE_SHA/FE_SHA/CI_SHA/CI_FE_SHA مطلوبين ⭐")
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {"round": "R" + ROUND, "packages": []}

    # ── ① BACKEND ⭐
    be_files = tree_files(BE_REPO, BE_SHA)
    be_entries, be_hits, be_dirty = [], 0, set()
    be_secret_files, be_dirty_files = [], []
    for f in be_files:
        data = read_bytes(BE_REPO, BE_SHA, f)
        if data is None:
            continue
        s, d = scan(data, f)
        if s:
            be_hits += 1
            be_secret_files.append(f)
        if d:
            be_dirty.update(d)
            be_dirty_files.append("%s:%s" % (f, "/".join(d)))
        be_entries.append(("octa-prices/" + f, data))

    # ── ② FRONTEND ⭐
    fe_files = tree_files(FE_REPO, FE_SHA)
    fe_entries, fe_hits, fe_dirty = [], 0, set()
    fe_secret_files, fe_dirty_files = [], []
    for f in fe_files:
        data = read_bytes(FE_REPO, FE_SHA, f)
        if data is None:
            continue
        s, d = scan(data, f)
        if s:
            fe_hits += 1
            fe_secret_files.append(f)
        if d:
            fe_dirty.update(d)
            fe_dirty_files.append("%s:%s" % (f, "/".join(d)))
        fe_entries.append(("octa/" + f, data))

    # ── ③ CI ⭐ (باك + واجهة ⭐)
    ci_entries, ci_hits, ci_dirty = [], 0, set()
    ci_secret_files, ci_dirty_files = [], []
    ci_files = [
        (BE_REPO, CI_SHA, ".github/workflows/ci.yml"),
        (BE_REPO, CI_SHA, "ci-workflow/octa-ci.yml"),
        (FE_REPO, CI_FE_SHA, ".github/workflows/ci.yml"),
        (FE_REPO, CI_FE_SHA, "ci-workflow/octa-ci-fe.yml"),
    ]
    for repo, sha, path in ci_files:
        data = read_bytes(repo, sha, path)
        if data is None:
            continue
        s, d = scan(data, path)
        if s:
            ci_hits += 1
            ci_secret_files.append(path)
        if d:
            ci_dirty.update(d)
            ci_dirty_files.append("%s:%s" % (path, "/".join(d)))
        ci_entries.append((os.path.basename(os.path.dirname(path)) + "/" + path, data))
    for tool in ["tools/ci_result_classifier.py", "tools/ci_reset_staging.sh",
                 "tools/ci_candidate_gate.sh", "tools/ci_isolated_tests.json",
                 "tools/ci_workflow_lint.py", "tools/test_ci_gates.py",
                 "tools/staging/run_staging.py", "tools/staging/iso_env.py",
                 "tools/staging/pytest_lite.py", "tools/staging/mini_http.py"]:
        data = read_bytes(BE_REPO, CI_SHA, tool)
        if data is None:
            continue
        s, d = scan(data, tool)
        if s:
            ci_hits += 1
            ci_secret_files.append(tool)
        if d:
            ci_dirty.update(d)
            ci_dirty_files.append("%s:%s" % (tool, "/".join(d)))
        ci_entries.append((tool, data))

    # ── ④ DELIVERY ⭐ (الأدلة ⭐)
    dv_entries, dv_hits, dv_dirty = [], 0, set()
    dv_secret_files, dv_dirty_files = [], []
    if EVIDENCE_DIR and os.path.isdir(EVIDENCE_DIR):
        for root, dirs, files in os.walk(EVIDENCE_DIR):
            dirs.sort()
            for fn in sorted(files):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, EVIDENCE_DIR)
                with open(full, "rb") as fh:
                    data = fh.read()
                s, d = scan(data, rel)
                if s:
                    dv_hits += 1
                    dv_secret_files.append(rel)
                if d:
                    dv_dirty.update(d)
                    dv_dirty_files.append("%s:%s" % (rel, "/".join(d)))
                dv_entries.append((rel, data))

    specs = [
        ("OCTA-ROUND%s-BACKEND.zip" % ROUND, be_entries, be_hits, be_dirty,
         be_secret_files, be_dirty_files),
        ("OCTA-ROUND%s-FRONTEND.zip" % ROUND, fe_entries, fe_hits, fe_dirty,
         fe_secret_files, fe_dirty_files),
        ("OCTA-ROUND%s-CI.zip" % ROUND, ci_entries, ci_hits, ci_dirty,
         ci_secret_files, ci_dirty_files),
        ("OCTA-ROUND%s-DELIVERY.zip" % ROUND, dv_entries, dv_hits, dv_dirty,
         dv_secret_files, dv_dirty_files),
    ]
    for name, entries, hits, dirty, sfiles, dfiles in specs:
        path = os.path.join(OUT_DIR, name)
        build_zip(path, entries)
        report["packages"].append({
            "zip": name,
            "bytes": os.path.getsize(path),
            "md5": md5_file(path),
            "sha256": sha256_file(path),
            "files": len(entries),
            "scanned": len(entries),
            "secret_hits": hits,
            "secret_files": sfiles[:40],
            "dirty_text": sorted(dirty),
            "dirty_files": dfiles[:60],
        })
        print("📦 %s · %d ملف · %d بايت · md5=%s · أسرار=%d · نص ملوّث=%s"
              % (name, len(entries), os.path.getsize(path), md5_file(path),
                 hits, sorted(dirty) or "لا شيء"))
    report["backend_sha"] = BE_SHA
    report["frontend_sha"] = FE_SHA
    report["ci_sha"] = CI_SHA
    report["ci_frontend_sha"] = CI_FE_SHA
    total_hits = sum(p["secret_hits"] for p in report["packages"])
    total_dirty = sorted({x for p in report["packages"] for x in p["dirty_text"]})
    report["secret_hits_total"] = total_hits
    report["known_dirty_allowed"] = KNOWN_DIRTY
    report["dirty_text_total"] = total_dirty
    with open(os.path.join(OUT_DIR, "OCTA-ROUND%s-PACKAGES.json" % ROUND), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("\nRESULT: %s" % ("CLEAN" if (total_hits == 0 and not total_dirty) else "DIRTY"))
    return 0 if (total_hits == 0 and not total_dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
