#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""✅ فحص حزم التسليم — الجولة ٢٣ (٩ فحوص في مكان واحد).

📌 الفحوص:
   ① سلامة الـZIP (testzip) للحزم الثلاث
   ② صفر سر: إعادة مسح كل ملف في كل حزمة
   ③ تطابق MANIFEST (SHA256 لكل ملف) في الحزم الثلاث
   ④ `git clone` لحزمة الباك من حزمة الباك المستقلّة + حزمة الواجهة من
      حزمة الواجهة المستقلّة ⇒ الفرع والـSHA مطابقين لـ ENVIRONMENT.json
   ⑤ برهان المراجع المستقل من **الحزم المستقلّة المستخرجة**:
      الباك `evidence/independent_regression.py` (٦/٦) · الواجهة node:test (٤/٤)
   ⑥ حارس التسليم (`test_delivery_consistency_guard.py --package`) ⇒ ٣/٣
   ⑦ بصمة كل حزمة تطابق ملفها الجانبي
   ⑧ اختبار النسخ النظيف: clone + تثبيت اعتماديات + تشغيل مجموعة اختبارات
      الباك و `npm test` للواجهة من الكlon نفسه
   ⑨ برهان سالب: ٣ حزم معطوبة عمداً ⇒ لازم الفاحص يكتشف كل واحدة

📌 وضع `--probe`: يفحص حزمة واحدة ويعمل BRIEF ⇒ بيستخدَم في البرهان السالب ⑨
   (بيتشغّل على نفس الكود ⇒ الدليل حقيقي مش وهمي ⭐).

⛔ مافيش شبكة · مافيش نشر · مافيش دمج · مافيش تكلفة.
"""

import glob
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROUND = "23"
OUT_DIR = pathlib.Path("/workspace/output")
TOOLS_DIR = pathlib.Path("/workspace/tools")

MAIN_ZIP = OUT_DIR / ("OCTA-ROUND%s-DELIVERY.zip" % ROUND)
BACKEND_ZIP = OUT_DIR / ("OCTA-ROUND%s-BACKEND.zip" % ROUND)
FRONTEND_ZIP = OUT_DIR / ("OCTA-ROUND%s-FRONTEND.zip" % ROUND)
ZIPS = [MAIN_ZIP, BACKEND_ZIP, FRONTEND_ZIP]

SIDE_NAMES = {
    MAIN_ZIP: "OCTA-ROUND%s-DELIVERY.md5" % ROUND,
    BACKEND_ZIP: "OCTA-ROUND%s-BACKEND.md5" % ROUND,
    FRONTEND_ZIP: "OCTA-ROUND%s-FRONTEND.md5" % ROUND,
}

SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}"
    r"|PRX-[A-Za-z0-9_-]{20,}|ADM-[A-Za-z0-9_-]{20,}"
    r"|OCTAD_TOKEN_SECRET\s*=\s*[\"'](?!TEST-ONLY\b)[^\"']{8,}"
    r"|STG-[A-Za-z0-9_-]{20,})")
SCAN_SUFFIXES = (".js", ".md", ".txt", ".json", ".patch", ".py", ".log", ".sh", "")
MAX_PLAIN_BYTES = 5_000_000

RESULTS = []


# ── أدوات ──────────────────────────────────────────────────────────────────
def record(idx, label, ok, detail):
    RESULTS.append({"id": idx, "check": label, "ok": bool(ok), "detail": detail})
    print("%s %-42s %s" % ("✅" if ok else "⛔", "%s %s" % (idx, label), detail))
    return ok


def run(cmd, cwd=None, env=None, timeout=1800):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -9, "TIMEOUT"
    except Exception as exc:
        return -1, "%s: %s" % (type(exc).__name__, exc)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_tree(root):
    hits = []
    scanned = 0
    for p in sorted(pathlib.Path(root).rglob("*")):
        if not p.is_file() or p.name == "SECRET-SCAN.txt":
            continue
        if p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if p.suffix == "" and p.stat().st_size > MAX_PLAIN_BYTES:
            continue
        scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in SECRET_PAT.finditer(text):
            hits.append("%s :: %s" % (p.relative_to(root), m.group(0)[:20]))
    return scanned, hits


def extract(zip_path, dest):
    dest = pathlib.Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    return dest


def resolve_branch(clone_dir, branch):
    """بصمة الفرع بعد الـclone: محلي أو تتبّع بعيد ⭐.

    📌 ليه: `git clone` من حزمة Git بيخلّي الفروع **تتبّع بعيد** (origin/*)
       إلا الفرع الافتراضي ⇒ لازم نجرّب الاتنين ⭐.
    """
    for ref in (branch, "origin/" + branch):
        rc, out = run(["git", "-C", str(clone_dir), "rev-parse", "--verify",
                       ref], timeout=120)
        if rc == 0 and out.strip():
            return out.strip()
    return ""


def branch_exists(clone_dir, branch):
    rc, out = run(["git", "-C", str(clone_dir), "branch", "-a", "--list",
                   "*" + branch], timeout=120)
    return rc == 0 and branch in out


# ── وضع الـprobe (بيستخدَم في البرهان السالب ⑨) ───────────────────────────
def probe_package(zip_path):
    """(ok, reason, detail) — فحص BRIEF لحزمة واحدة.

    reason ∈ {OK, ZIP_CORRUPT, MANIFEST_BROKEN, MANIFEST_MISMATCH,
               BUNDLE_MISSING, BUNDLE_CLONE_FAILED, SHA_MISMATCH, ENV_MISSING}
    """
    zip_path = pathlib.Path(zip_path)
    if not zip_path.is_file():
        return False, "ZIP_MISSING", "ملف الحزمة مش موجود: %s" % zip_path
    try:
        with zipfile.ZipFile(zip_path) as z:
            broken = z.testzip()
            if broken is not None:
                return False, "ZIP_CORRUPT", "testzip() => %s" % broken
            tmp = pathlib.Path(tempfile.mkdtemp(prefix="r23_probe_"))
            z.extractall(tmp)
    except zipfile.BadZipFile as exc:
        return False, "ZIP_CORRUPT", "BadZipFile: %s" % exc
    try:
        # ① البيئة (لازم ⇒ عشان نعرف اسم الفرع والبصمة ⭐)
        env_path = tmp / "ENVIRONMENT.json"
        if not env_path.is_file():
            return False, "ENV_MISSING", "ENVIRONMENT.json مش موجود"
        env = json.loads(env_path.read_text(encoding="utf-8"))

        # ② وجود حزم Git (قبل الـMANIFEST ⇒ سبب واضح ⭐)
        bundles = {}
        for group, prefix in (("backend", "backend"), ("frontend", "frontend")):
            node = env.get(group) or {}
            want_branch = node.get("review_branch")
            want_sha = node.get("review_sha")
            cands = sorted(glob.glob(str(tmp / "bundles" / (prefix + "*.bundle"))))
            if not cands:
                return False, "BUNDLE_MISSING", "مفيش حزمة git للـ%s" % group
            bundles[group] = (cands[0], want_branch, want_sha)

        # ③ الـMANIFEST ( موجود ⭐ · سليم ⭐ · مطابق ⭐)
        man_path = tmp / "MANIFEST.json"
        if not man_path.is_file():
            return False, "MANIFEST_BROKEN", "MANIFEST.json مش موجود"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, "MANIFEST_BROKEN", "JSON تالف: %s" % exc
        if not isinstance(man.get("files"), list):
            return False, "MANIFEST_BROKEN", "المفتاح files مش قائمة"
        for rec in man["files"]:
            rel = rec.get("path")
            if not rel:
                return False, "MANIFEST_BROKEN", "سجل بلا مسار"
            f = tmp / rel
            if not f.is_file():
                return False, "MANIFEST_MISMATCH", "ملف ناقص: %s" % rel
            if sha256_file(f) != rec.get("sha256"):
                return False, "MANIFEST_MISMATCH", "محتوى مختلف: %s" % rel

        # ④ النسخ والبصمة
        for group, (bundle, want_branch, want_sha) in bundles.items():
            clone_dir = tmp / ("probe_clone_" + group)
            rc, out = run(["git", "clone", "--quiet", bundle, str(clone_dir)],
                          timeout=600)
            if rc != 0:
                return False, "BUNDLE_CLONE_FAILED", out.strip()[:160]
            got = resolve_branch(clone_dir, want_branch)
            if got != want_sha:
                return False, "SHA_MISMATCH", "%s: المتوقّع %s · الموجود %s" % (
                    group, str(want_sha)[:8], got[:8])
        return True, "OK", "الحزمة سليمة ⭐"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe_cli(argv):
    if not argv:
        print("PROBE_RESULT: FAIL reason=NO_ARGUMENT")
        return 2
    ok, reason, detail = probe_package(argv[0])
    print("PROBE_RESULT: %s reason=%s details=%s"
          % ("PASS" if ok else "FAIL", reason, detail.replace("\n", " ")[:220]))
    return 0 if ok else 1


# ── الفحوص ─────────────────────────────────────────────────────────────────
def check_01_integrity():
    detail_bits = []
    all_ok = True
    for z in ZIPS:
        if not z.is_file():
            record("①", "سلامة الـZIP", False, "%s مش موجود" % z.name)
            return False
        with zipfile.ZipFile(z) as zf:
            broken = zf.testzip()
            n = len(zf.namelist())
        if broken is None:
            detail_bits.append("%s (%d مدخل)" % (z.name, n))
        else:
            all_ok = False
            detail_bits.append("%s تالف في %s" % (z.name, broken))
    return record("①", "سلامة الـZIP (testzip)", all_ok,
                  " · ".join(detail_bits))


def check_02_secrets(tmp):
    total_scanned = 0
    all_hits = []
    for z in ZIPS:
        root = tmp / ("scan_" + z.stem)
        extract(z, root)
        scanned, hits = scan_tree(root)
        total_scanned += scanned
        all_hits.extend("%s :: %s" % (z.name, h) for h in hits)
    if all_hits:
        return record("②", "فحص الأسرار (كل ملفات الحزم)", False,
                      "%d hit · %s" % (len(all_hits), all_hits[:3]))
    return record("②", "فحص الأسرار (كل ملفات الحزم)", True,
                  "%d ملف · صفر hit ⭐" % total_scanned)


def check_03_manifest(tmp):
    bits = []
    all_ok = True
    for z in ZIPS:
        root = tmp / ("scan_" + z.stem)
        man_path = root / "MANIFEST.json"
        if not man_path.is_file():
            all_ok = False
            bits.append("%s: MANIFEST ناقص" % z.name)
            continue
        man = json.loads(man_path.read_text(encoding="utf-8"))
        bad = []
        for rec in man["files"]:
            f = root / rec["path"]
            if not f.is_file():
                bad.append(rec["path"] + " (ناقص)")
                continue
            if sha256_file(f) != rec["sha256"]:
                bad.append(rec["path"])
        if bad:
            all_ok = False
            bits.append("%s: %d مختلف" % (z.name, len(bad)))
        else:
            bits.append("%s: %d ملف مطابق" % (z.name, len(man["files"])))
    return record("③", "تطابق MANIFEST (SHA256)", all_ok, " · ".join(bits))


def check_04_clone(tmp):
    bits = []
    all_ok = True
    pairs = [(BACKEND_ZIP, "backend"), (FRONTEND_ZIP, "frontend")]
    for zip_path, group in pairs:
        root = tmp / ("clone_src_" + group)
        extract(zip_path, root)
        env = json.loads((root / "ENVIRONMENT.json").read_text(encoding="utf-8"))
        node = env[group]
        want_branch = node["review_branch"]
        want_sha = node["review_sha"]
        cands = sorted(glob.glob(str(root / "bundles" / (group + "*.bundle"))))
        if not cands:
            all_ok = False
            bits.append("%s: مفيش حزمة git" % group)
            continue
        dest = tmp / ("clone_" + group)
        rc, out = run(["git", "clone", "--quiet", cands[0], str(dest)], timeout=600)
        if rc != 0:
            all_ok = False
            bits.append("%s: clone فشل" % group)
            continue
        got = resolve_branch(dest, want_branch)
        branch_ok = branch_exists(dest, want_branch)
        if got == want_sha and branch_ok:
            bits.append("%s: %s = %s ✅" % (group, want_branch, got[:8]))
        else:
            all_ok = False
            bits.append("%s: المتوقّع %s · الموجود %s%s" % (
                group, want_sha[:8], got[:8],
                "" if branch_ok else " (الفرع مش موجود ⭐)"))
    return record("④", "git clone من الحزم المستقلّة", all_ok, " · ".join(bits))


def check_05_proofs(tmp):
    bits = []
    all_ok = True

    # ⑤-أ برهان الباك من حزمة الباك المستقلّة
    root = tmp / "clone_src_backend"
    ev = root / "evidence"
    script = ev / "independent_regression.py"
    if not script.is_file():
        all_ok = False
        bits.append("الباك: السكربت مش موجود")
    else:
        rc, out = run([sys.executable, "independent_regression.py"], cwd=str(ev),
                       timeout=1800)
        m = re.search(r"Ran (\d+) tests?", out)
        n = int(m.group(1)) if m else 0
        if rc == 0 and n >= 6:
            bits.append("الباك %d/%d ✅" % (n, n))
        else:
            all_ok = False
            bits.append("الباك rc=%s (%s)" % (rc, out.strip().splitlines()[-1][:80]
                                              if out.strip() else "?"))

    # ⑤-ب برهان الواجهة من حزمة الواجهة المستقلّة
    fe_root = tmp / "clone_src_frontend"
    cands = sorted(glob.glob(str(fe_root / "bundles" / "frontend*.bundle")))
    if not cands:
        all_ok = False
        bits.append("الواجهة: مفيش حزمة git")
    else:
        dest = tmp / "proof_frontend"
        rc, out = run(["git", "clone", "--quiet", cands[0], str(dest)], timeout=600)
        if rc != 0:
            all_ok = False
            bits.append("الواجهة: clone فشل")
        else:
            test_file = dest / "assets" / "tests" / "independent_r17_coverage_warning.test.js"
            if not test_file.is_file():
                all_ok = False
                bits.append("الواجهة: ملف الاختبار مش موجود")
            else:
                rc, out = run(["node", "--test", str(test_file)], cwd=str(dest),
                               timeout=900)
                mp = re.search(r"# pass (\d+)", out)
                mf = re.search(r"# fail (\d+)", out)
                npass = int(mp.group(1)) if mp else 0
                nfail = int(mf.group(1)) if mf else 0
                if rc == 0 and npass >= 4:
                    bits.append("الواجهة %d/%d ✅" % (npass, npass + nfail))
                else:
                    all_ok = False
                    bits.append("الواجهة pass=%s fail=%s" % (npass, nfail))
    return record("⑤", "برهان المراجع من الحزم المستقلّة", all_ok, " · ".join(bits))


def check_06_guard(tmp):
    root = tmp / ("scan_" + MAIN_ZIP.stem)
    guard_test = root / "tools" / "test_delivery_consistency_guard.py"
    if not guard_test.is_file():
        return record("⑥", "حارس التسليم (٣/٣)", False, "السكربت مش موجود")
    rc, out = run([sys.executable, str(guard_test), "--package", str(root)],
                  timeout=1800)
    m = re.search(r"cases behaving as expected\s*:\s*(\d+)/(\d+)", out)
    passed = int(m.group(1)) if m else 0
    total = int(m.group(2)) if m else 0
    if rc == 0 and total == 3 and passed == 3:
        return record("⑥", "حارس التسليم (٣/٣)", True, "%d/%d (rc=0)" % (passed, total))
    return record("⑥", "حارس التسليم (٣/٣)", False,
                  "%d/%d rc=%s" % (passed, total, rc))


def check_07_sidecars():
    bits = []
    all_ok = True
    for z in ZIPS:
        side = OUT_DIR / SIDE_NAMES[z]
        if not side.is_file():
            all_ok = False
            bits.append("%s: الملف الجانبي مش موجود" % z.name)
            continue
        text = side.read_text(encoding="utf-8")
        m5 = re.search(r"md5\s*:\s*([0-9a-f]{32})", text)
        ms = re.search(r"sha256\s*:\s*([0-9a-f]{64})", text)
        me = re.search(r"المدخلات:\s*(\d+)", text)
        mz = re.search(r"الحجم:\s*(\d+)", text)
        if not (m5 and ms):
            all_ok = False
            bits.append("%s: بصمة ناقصة في الملف الجانبي" % z.name)
            continue
        real5 = md5_file(z)
        reals = sha256_file(z)
        with zipfile.ZipFile(z) as zf:
            real_entries = len(zf.namelist())
        real_size = z.stat().st_size
        problems = []
        if m5.group(1) != real5:
            problems.append("md5")
        if ms.group(1) != reals:
            problems.append("sha256")
        if me and int(me.group(1)) != real_entries:
            problems.append("entries")
        if mz and int(mz.group(1)) != real_size:
            problems.append("size")
        if problems:
            all_ok = False
            bits.append("%s: اختلاف في %s" % (z.name, ",".join(problems)))
        else:
            bits.append("%s: md5+sha256+size+%d ✅" % (z.name, real_entries))
    return record("⑦", "مطابقة البصمة للملف الجانبي", all_ok, " · ".join(bits))


def check_08_clean_clone():
    script = TOOLS_DIR / "test_round23_clean_clone.py"
    if not script.is_file():
        return record("⑧", "اختبار النسخ النظيف", False, "السكربت مش موجود")
    out_json = pathlib.Path(tempfile.mkdtemp(prefix="r23_clone_")) / "result.json"
    rc, out = run([sys.executable, str(script), "--json-out", str(out_json),
                   "--backend-zip", str(BACKEND_ZIP),
                   "--frontend-zip", str(FRONTEND_ZIP)], timeout=3600)
    if rc != 0 and not out_json.is_file():
        return record("⑧", "اختبار النسخ النظيف", False,
                      out.strip().splitlines()[-1][:120] if out.strip() else "rc=%s" % rc)
    data = json.loads(out_json.read_text(encoding="utf-8"))
    be = data.get("backend", {})
    fe = data.get("frontend", {})
    be_txt = "الباك %s" % be.get("summary", "?")
    fe_txt = "الواجهة %s" % fe.get("summary", "?")
    notes = list(be.get("notes") or []) + list(fe.get("notes") or [])
    detail = "%s · %s" % (be_txt, fe_txt)
    if notes:
        detail += " · " + " | ".join(n.replace("\n", " ") for n in notes)
    ok = bool(data.get("ok"))
    return record("⑧", "اختبار النسخ النظيف (clone + اختبارات)", ok, detail)


def check_09_negative(tmp):
    """٣ حزم معطوبة عمداً + حزمة سليمة (ضبط) ⇒ لازم الفاحص يكتشف كل واحدة."""
    work = pathlib.Path(tempfile.mkdtemp(prefix="r23_negative_"))
    cases = []

    # (٠) حزمة سليمة (ضبط) ⇒ لازم تعدّي
    ctrl = work / "control.zip"
    shutil.copy2(MAIN_ZIP, ctrl)
    cases.append(("control", ctrl, "OK", True))

    # (١) بايت مقلوب في ملف جوّه الحزمة ⇒ MANIFEST_MISMATCH
    src = work / "flip"
    extract(MAIN_ZIP, src)
    target = src / "00-READ-ME-FIRST.md"
    data = bytearray(target.read_bytes())
    data[len(data) // 2] = data[len(data) // 2] ^ 0xFF
    target.write_bytes(bytes(data))
    z1 = work / "broken_flip.zip"
    with zipfile.ZipFile(z1, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src))
    cases.append(("flipped byte in a file", z1, "MANIFEST_MISMATCH", False))

    # (٢) MANIFEST معطوب ⇒ MANIFEST_BROKEN
    src2 = work / "man"
    extract(MAIN_ZIP, src2)
    (src2 / "MANIFEST.json").write_text("{ this is not json",
                                        encoding="utf-8")
    z2 = work / "broken_manifest.zip"
    with zipfile.ZipFile(z2, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src2.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src2))
    cases.append(("broken MANIFEST", z2, "MANIFEST_BROKEN", False))

    # (٣) حزمة git محذوفة ⇒ BUNDLE_MISSING
    src3 = work / "nobundle"
    extract(MAIN_ZIP, src3)
    for b in (src3 / "bundles").glob("*.bundle"):
        b.unlink()
    z3 = work / "broken_nobundle.zip"
    with zipfile.ZipFile(z3, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src3.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(src3))
    cases.append(("deleted bundle", z3, "BUNDLE_MISSING", False))

    # (٤) بايت مقلوب جوّه الأرشيف نفسه ⇒ ZIP_CORRUPT
    z4 = work / "broken_archive.zip"
    raw = bytearray(MAIN_ZIP.read_bytes())
    raw[len(raw) // 2] = raw[len(raw) // 2] ^ 0xFF
    z4.write_bytes(bytes(raw))
    cases.append(("corrupted archive", z4, "ZIP_CORRUPT", False))

    bits = []
    all_ok = True
    for label, path, want_reason, want_ok in cases:
        ok, reason, detail = probe_package(path)
        good = (ok == want_ok) and (reason == want_reason)
        if not good:
            all_ok = False
        bits.append("%s ⇒ %s%s" % (label, reason,
                                   "" if good else " ⛔ (المتوقّع %s)" % want_reason))
    shutil.rmtree(work, ignore_errors=True)
    return record("⑨", "برهان سالب (٤ حالات معطوبة + ضبط)", all_ok,
                  " · ".join(bits))


def print_table():
    print()
    print("═" * 104)
    print("جدول التحقق — حزم التسليم · الجولة %s" % ROUND)
    print("═" * 104)
    print("%-4s %-46s %-8s %s" % ("#", "الفحص", "النتيجة", "التفصيل"))
    print("─" * 104)
    for r in RESULTS:
        print("%-4s %-46s %-8s %s" % (r["id"], r["check"],
                                       "PASS" if r["ok"] else "FAIL", r["detail"]))
    print("─" * 104)
    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)
    print("النتيجة: %d/%d فحص نجح · %s" % (passed, total,
                                            "✅" if passed == total else "⛔ FAIL"))
    print("═" * 104)


def write_fingerprints():
    out_dir = OUT_DIR / ("OCTA-ROUND%s-EVIDENCE" % ROUND) / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    packages = {}
    for z in ZIPS:
        with zipfile.ZipFile(z) as zf:
            entries = len(zf.namelist())
            broken = zf.testzip()
        packages[z.name] = {
            "md5": md5_file(z),
            "sha256": sha256_file(z),
            "bytes": z.stat().st_size,
            "entries": entries,
            "testzip": "None" if broken is None else str(broken),
            "sidecar": SIDE_NAMES[z],
        }
    # البصمات بتوصف **الملفات المُتحقَّق منها** (من جوّه الـZIP) ⭐
    #    مش المجلد على القرص (ممكن يكون بيتكتب فيه في نفس الوقت ⭐).
    env = {}
    try:
        with zipfile.ZipFile(MAIN_ZIP) as zf:
            env = json.loads(zf.read("ENVIRONMENT.json").decode("utf-8"))
    except Exception:
        env = {}
    doc = {
        "round": ROUND,
        "generated_utc": env.get("generated_utc"),
        "packages": packages,
        "commits": {
            "backend": {
                "branch": (env.get("backend") or {}).get("review_branch"),
                "sha": (env.get("backend") or {}).get("review_sha"),
            },
            "frontend": {
                "branch": (env.get("frontend") or {}).get("review_branch"),
                "sha": (env.get("frontend") or {}).get("review_sha"),
            },
        },
        "checks": RESULTS,
        "summary": {
            "passed": sum(1 for r in RESULTS if r["ok"]),
            "total": len(RESULTS),
            "result": "PASS" if all(r["ok"] for r in RESULTS) else "FAIL",
        },
    }
    path = out_dir / "r23_package_fingerprints.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv):
    if argv and argv[0] == "--probe":
        return probe_cli(argv[1:])

    for z in ZIPS:
        if not z.is_file():
            print("⛔ الحزمة مفقودة: %s" % z)
            print("RESULT: FAIL")
            return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r23_verify_"))
    try:
        check_01_integrity()
        check_02_secrets(tmp)
        check_03_manifest(tmp)
        check_04_clone(tmp)
        check_05_proofs(tmp)
        check_06_guard(tmp)
        check_07_sidecars()
        check_08_clean_clone()
        check_09_negative(tmp)
    finally:
        keep = os.environ.get("R23_KEEP_TMP")
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)

    print_table()
    fp = write_fingerprints()
    print("بصمات الآلة: %s" % fp)
    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)
    if passed != total:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
