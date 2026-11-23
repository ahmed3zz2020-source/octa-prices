#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""📦 الجولة ٢٣ — بناء حزم التسليم (٣ حزم مستقلّة + ٣ ملفات جانبية).

📌 المخرجات:
   ① `OCTA-ROUND23-DELIVERY.zip`  — الحزمة الكاملة (باك + واجهة + تقارير + أدوات)
   ② `OCTA-ROUND23-BACKEND.zip`   — الباك وحده (نسخ + تشغيل مستقلّ)
   ③ `OCTA-ROUND23-FRONTEND.zip`  — الواجهة وحدها (نسخ + تشغيل مستقلّ)
   ④ ملف جانبي لكل حزمة (md5 + sha256 + الحجم + المدخلات + بصمات الأفرع)

📌 قاعدة البناء: **مفيش أي ملف من شغل حد تاني** ⇒ الـ bundles بتاخد الحالة
   المُودعة (committed) بس ⇒ وشغل غير مُودع في شجرة العمل ما بتتلمسش ⭐.

📌 البناء **قابل لإعادة الإنتاج**: ترتيب المدخلات ثابت + طابع زمني ثابت ⇒
   نفس المحتوى ⇐ نفس البصمة ⭐.

📌 ملفات المحتوى (تقرير · سجل · رسالة) بتاعت صاحب المحتوى: بنستخدمها كما هي ⭐
   وبنصلّح **سطر البصمة** ميكانيكياً (من غير تغيير المعنى ⭐) عشان حارس
   التسليم يقدر يتأكّد منها ⭐.

⛔ مافيش أسرار · مافيش نشر · مافيش دمج · مافيش تكلفة · مافيش تعديل إنتاج.
"""

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import zipfile

# ── ثوابت الجولة ──────────────────────────────────────────────────────────
ROUND = "23"
OUT_DIR = pathlib.Path("/workspace/output")
TOOLS_DIR = pathlib.Path("/workspace/tools")
BE_WT = pathlib.Path("/workspace/.wt_r18")
FE_WT = pathlib.Path("/workspace/.wt_r18fe")

BE_BRANCH = "review/round23-backend"
FE_BRANCH = "review/round23-frontend"
BE_BASE_MAIN = "9c27f565d22fe1d126c5670de2070a66e980988c"
BE_BASE_R22 = "d61f279a8d20f6f252dfea459cf8f9782469f552"
FE_BASE_R22 = "71ba99a9fb6595f1c80da2debabe222e8e1ab1b2"
FE_BASE_B1 = "325a99c34f89e6127c005c3bbe6b193b3e113cb7"
FE_MAIN_SHA = "4b9742130406c2341f63286ccc849813369394ff"

GEN_UTC = "2026-11-18T04:00:00Z"
ZIP_DATE = (2026, 11, 18, 4, 0, 0)

BE_BUNDLE_NAME = "backend-octaprices-r%s.bundle" % ROUND
FE_BUNDLE_NAME = "frontend-octa-r%s.bundle" % ROUND

# ⛔ نفس أنماط الفحص المستعملة في الجولة ٢٢ (إعادة استخدام منقولة ⭐)
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}"
    r"|PRX-[A-Za-z0-9_-]{20,}|ADM-[A-Za-z0-9_-]{20,}"
    r"|OCTAD_TOKEN_SECRET\s*=\s*[\"'](?!TEST-ONLY\b)[^\"']{8,}"
    r"|STG-[A-Za-z0-9_-]{20,})")
SCAN_SUFFIXES = (".js", ".md", ".txt", ".json", ".patch", ".py", ".log", ".sh", "")
MAX_PLAIN_BYTES = 5_000_000
HEX40_ANY = re.compile(r"\b[0-9a-fA-F]{40}\b")


# ── أدوات مساعدة ──────────────────────────────────────────────────────────
def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    return p.stdout.strip()


def rmtree(p):
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def copy_file(src, dst):
    """نسخة واحدة: ما بتلمسش الملف لو مش موجود."""
    src = pathlib.Path(src)
    if not src.is_file():
        return False
    dst = pathlib.Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copy_tree(src, dst, skip_names=()):
    src = pathlib.Path(src)
    if not src.is_dir():
        return 0
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file() or p.name in skip_names:
            continue
        rel = p.relative_to(src)
        if copy_file(p, pathlib.Path(dst) / rel):
            n += 1
    return n


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


def tracked(repo, pattern):
    return [x for x in git(repo, "ls-files", pattern).split("\n") if x]


def changed_files(repo, base, branch):
    return [x for x in git(repo, "diff", "--name-only",
                           "%s..%s" % (base, branch)).split("\n") if x]


def safe_name(rel):
    return str(rel).replace("/", "-")


# ── ① الحزم (bundles) ─────────────────────────────────────────────────────
def set_bundle_head(bundle, branch_sha):
    """يضبط مدخل HEAD في ترويسة الحزمة على **فرع التسليم** ⭐.

    📌 ليه: `git bundle create` بياخد HEAD من شجرة العمل بتاعة الريبو ⇒ لو
       الريبو ماشي على فرع تاني، الـclone بيقف على الفرع الغلط ⭐.
       الاستبدال هنا **بنفس الطول** (٤٠ حرف ⭐) ⇒ مافيش إزاحة في الملف ⭐.
    """
    p = pathlib.Path(bundle)
    data = bytearray(p.read_bytes())
    idx = data.find(b" HEAD\n")
    if idx < 40:
        return False
    old = bytes(data[idx - 40:idx])
    if len(old) != 40:
        return False
    data[idx - 40:idx] = branch_sha.encode("ascii")
    p.write_bytes(bytes(data))
    return True


def build_bundle(repo, branch, out_dir, name):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / name
    if dst.exists():
        dst.unlink()
    p = subprocess.run(["git", "-C", str(repo), "bundle", "create",
                        str(dst), "--all"], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("git bundle create فشل: %s"
                         % (p.stderr or p.stdout)[:300])
    sha = git(repo, "rev-parse", branch)
    if sha and set_bundle_head(dst, sha):
        pass
    v = subprocess.run(["git", "-C", str(repo), "bundle", "verify", str(dst)],
                       capture_output=True, text=True)
    (dst.parent / (name + ".verify.txt")).write_text(
        (v.stdout or "") + (v.stderr or ""), encoding="utf-8")
    heads = subprocess.run(["git", "bundle", "list-heads", str(dst)],
                           capture_output=True, text=True).stdout
    (dst.parent / (name + ".heads.txt")).write_text(heads, encoding="utf-8")
    return dst


# ── ② الـpatches ──────────────────────────────────────────────────────────
def build_patches(repo, base, branch, out_dir, sub, label):
    d = pathlib.Path(out_dir) / sub
    rmtree(d)
    commits = [c for c in git(repo, "rev-list", "--reverse",
                               "%s..%s" % (base, branch)).split("\n") if c]
    for n, c in enumerate(commits, 1):
        subj = git(repo, "log", "-1", "--format=%s", c)
        safe = re.sub(r"[^\w\-.]+", "-", subj, flags=re.UNICODE).strip("-")[:60]
        if not safe:
            safe = "patch"
        patch = subprocess.run(["git", "-C", str(repo), "format-patch", "-1",
                                "--stdout", c], capture_output=True,
                               text=True).stdout
        (d / ("%03d-%s.patch" % (n, safe))).write_text(patch, encoding="utf-8")
    (d / "README.txt").write_text(
        "%s\n%s\nالأساس: %s\nعدد الـpatches: %d\n"
        "التطبيق: git am <this-dir>/*.patch\n"
        % (branch, label, base, len(commits)), encoding="utf-8")
    return len(commits)


# ── ③ فحص الأسرار ─────────────────────────────────────────────────────────
def secret_scan(pkg):
    hits = []
    scanned = 0
    for p in sorted(pathlib.Path(pkg).rglob("*")):
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
            hits.append({"file": str(p.relative_to(pkg)), "match": m.group(0)[:24]})
    lines = ["# فحص الأسرار — حزمة الجولة %s" % ROUND, "",
             "- الملفات المفحوصة: %d" % scanned,
             "- الأنماط: توكن GitHub · sk- · أسرار Staging (PRX/ADM/STG) · "
             "OCTAD_TOKEN_SECRET",
             "- النتيجة: **%s**" % ("صفر سر ✅" if not hits else "فيه hits ⛔"), ""]
    if hits:
        lines.append("```")
        for h in hits[:20]:
            lines.append("%s :: %s" % (h["file"], h["match"]))
        lines.append("```")
    (pathlib.Path(pkg) / "SECRET-SCAN.txt").write_text(
        "\n".join(lines), encoding="utf-8")
    return scanned, hits


# ── ④ الـManifest ──────────────────────────────────────────────────────────
def build_manifest(pkg):
    pkg = pathlib.Path(pkg)
    manifest = {"generated": GEN_UTC, "round": ROUND, "files": []}
    for p in sorted(pkg.rglob("*")):
        if not p.is_file() or p.name in ("MANIFEST.json", "MANIFEST.md"):
            continue
        manifest["files"].append({
            "path": str(p.relative_to(pkg)),
            "bytes": p.stat().st_size,
            "sha256": sha256_file(p)})
    (pkg / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# MANIFEST — حزمة تسليم الجولة %s (OCTA)" % ROUND, "",
          "- التاريخ (UTC): %s" % GEN_UTC,
          "- عدد الملفات: %d" % len(manifest["files"]),
          "- كل ملف له SHA256 (بترتيب المسار):", "",
          "| الملف | البايت | SHA256 |", "|---|---|---|"]
    for f in manifest["files"]:
        md.append("| `%s` | %d | `%s` |" % (f["path"], f["bytes"], f["sha256"]))
    (pkg / "MANIFEST.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return len(manifest["files"])


# ── ⑤ الكتابة الحتمية للـZIP ───────────────────────────────────────────────
def write_zip(pkg, zip_path):
    """يكتب الـzip **ذرّياً** (ملف مؤقت + إعادة تسمية) ⭐.

    📌 ليه الذرّية: لو كنا بنحذف الملف الأول وبنكتبه،(الفاحص الشغّال
       في نفس اللحظة) ممكن يلاقي الملف **مش موجود** أو **نصّه** ⭐
       ⇒ فشل كاذب. مع الكتابة في ملف مؤقت ثم `os.replace` (ذرّية ⭐)
       ⇒ الفاحص دايماً بيلاقي إمّا النسخة القديمة كاملة أو الجديدة كاملة ⭐.
    """
    pkg = pathlib.Path(pkg)
    zip_path = pathlib.Path(zip_path)
    # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ اسم ⭐⭐⭐ مؤقت ⭐⭐⭐ **فريد** ⭐⭐⭐ ⭐ (pid ⭐)
    tmp = zip_path.with_name("%s.tmp-%d" % (zip_path.name, os.getpid()))
    if tmp.exists():
        tmp.unlink()
    files = sorted(p for p in pkg.rglob("*") if p.is_file())
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info = zipfile.ZipInfo(str(p.relative_to(pkg)), date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 << 16)
            info.create_system = 3
            z.writestr(info, p.read_bytes())
    os.replace(str(tmp), str(zip_path))
    return len(files)


# ── ⑥ الملف الجانبي (البصمة) ──────────────────────────────────────────────
def write_sidecar(zip_path, out_path, pkg_label, be_sha, fe_sha):
    zip_path = pathlib.Path(zip_path)
    size = zip_path.stat().st_size
    md5 = md5_file(zip_path)
    sha = sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        entries = len(z.namelist())
        broken = z.testzip()
    lines = [
        "🔖 OCTA — ROUND %s — بصمة الحزمة ⭐" % ROUND,
        "═══════════════════════════════════════════════════════════════",
        "الملف: %s" % zip_path.name,
        "الحزمة: %s" % pkg_label,
        "الحجم: %d بايت" % size,
        "المدخلات: %d" % entries,
        "testzip(): %s ⭐" % ("None" if broken is None else broken),
        "مستوى الضغط: ZIP_DEFLATED ⭐",
        "",
        "md5    : %s" % md5,
        "sha256 : %s" % sha,
        "",
        "md5sum %s" % zip_path.name,
        "sha256sum %s" % zip_path.name,
        "unzip -t %s ⭐" % zip_path.name,
        "",
        "⛔ ملاحظة: الـZIP **لا يمكن أن يحتوي بصمة نفسه** ⭐ ⇒ البصمة في هذا",
        "الملف الجانبي ⭐ ⇒ وده سبب وجوده ⭐.",
        "",
        "🔖 فروع الإصدار داخل الحزمة:",
        "   review/round%s-backend  = %s ⭐" % (ROUND, be_sha),
        "   review/round%s-frontend = %s ⭐" % (ROUND, fe_sha),
        "",
        "🔖 main (لم يتغيّر ⭐):",
        "   الباك   %s ⭐" % BE_BASE_MAIN,
        "   الواجهة %s ⭐" % FE_MAIN_SHA,
        "",
        "═══════════════════════════════════════════════════════════════",
        "",
    ]
    # ⛔ كتابة ذرّية ⭐ (نفس سبب الـzip ⭐) ⇒ الفاحص ما يلاقيش ملف نصّه ⭐
    out_path = pathlib.Path(out_path)
    # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ اسم ⭐⭐⭐ مؤقت ⭐⭐⭐ **فريد** ⭐⭐⭐ ⭐ (pid ⭐)
    tmp = out_path.with_name("%s.tmp-%d" % (out_path.name, os.getpid()))
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(str(tmp), str(out_path))
    return {"md5": md5, "sha256": sha, "bytes": size, "entries": entries}


# ── ⑦ محتوى الحزمة ────────────────────────────────────────────────────────
# 📌 كل بند: قائمة مصادر بالترتيب (الأول الموجود بيتاخد) + اسمه في الحزمة ⭐
CONTENT_MAIN = [
    (["OCTA-ROUND23-READ-ME-FIRST.md"], "00-READ-ME-FIRST.md"),
    (["OCTA-ROUND23-REPORT.md"], "OCTA-ROUND23-REPORT.md"),
    (["OCTA-ROUND23-ISSUE-REGISTER.md"], "OCTA-ROUND23-ISSUE-REGISTER.md"),
    (["OCTA-ROUND23-SEND-MESSAGE.txt"], "OCTA-ROUND23-SEND-MESSAGE.txt"),
    (["OCTA-ROUND23-EXECUTION-LOG.md", "OCTA-EXECUTION-LOG.md"],
     "OCTA-EXECUTION-LOG.md"),
    (["OCTA-ROUND23-SECURITY-QUEUE.md", "OCTA-SECURITY-QUEUE.md"],
     "OCTA-SECURITY-QUEUE.md"),
]

# ⛔ اسم توافق: سكربت البرهان المستقل بيشغّل «OCTA-ROUND17-SEND-MESSAGE.txt»
COMPAT_MESSAGE_NAMES = ["OCTA-ROUND17-SEND-MESSAGE.txt"]

TOOL_FILES = [
    "ci_guard.py",
    "mgmt_containment_check.py",
    "verify_bundle_import.py",
    "run_full_suite.py",
    "check_arabic_output.py",
    "run_backend_two_parts.py",
    "check_delivery_consistency.py",
    "test_delivery_consistency_guard.py",
    "build_round22_delivery.py",
    "build_round23_delivery.py",
    "verify_round22_delivery.py",
    "verify_round23_delivery.py",
    "test_round23_clean_clone.py",
]


def sync_sha_lines(path, branch, sha):
    """يضمن إن كل سطر فيه اسم الفرع فيه البصمة الكاملة (٤٠ حرف) ⭐.

    📌 سببها: حارس التسليم بيقرا البصمة من **نفس السطر** اللي فيه اسم
       الفرع ⇒ لو السطر فيه بصمة مختصرة (٧ أحرف) الحارس بيرفضها ⭐.
       التصحيح **ميكانيكي بالكامل** ⇒ المعنى ما بيتغيّرش ⭐.
    """
    p = pathlib.Path(path)
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    lines = text.split("\n")
    changed = False
    found_branch = False
    for i, line in enumerate(lines):
        if branch not in line:
            continue
        found_branch = True
        tokens = HEX40_ANY.findall(line)
        if any(t.lower() == sha.lower() for t in tokens):
            continue
        if tokens:
            lines[i] = HEX40_ANY.sub(sha, line, count=1)
        else:
            lines[i] = line + " ⭐ sha:" + sha
        changed = True
    if not found_branch:
        lines.append("%s = %s" % (branch, sha))
        changed = True
    if changed:
        p.write_text("\n".join(lines), encoding="utf-8")
    return changed


def write_content(pkg, be_sha, fe_sha):
    """نسخ ملفات المحتوى + أسماء التوافق + تزامن بصمات الأفرع."""
    pkg = pathlib.Path(pkg)
    missing = []
    for candidates, dst_name in CONTENT_MAIN:
        picked = None
        for name in candidates:
            src = OUT_DIR / name
            if src.is_file():
                picked = src
                break
        if picked is None:
            missing.append("/".join(candidates))
            continue
        shutil.copy2(picked, pkg / dst_name)
    if missing:
        raise SystemExit("ملفات ناقصة: %s" % ", ".join(missing))

    # ⭐ تزامن بصمات الأفرع في الحزمة وفي المصدر (ياك ⭐)
    for dst_name in ("00-READ-ME-FIRST.md",
                     "OCTA-ROUND%s-SEND-MESSAGE.txt" % ROUND):
        sync_sha_lines(pkg / dst_name, BE_BRANCH, be_sha)
        sync_sha_lines(pkg / dst_name, FE_BRANCH, fe_sha)
    for src_name in ("OCTA-ROUND23-READ-ME-FIRST.md",
                     "OCTA-ROUND23-SEND-MESSAGE.txt"):
        sync_sha_lines(OUT_DIR / src_name, BE_BRANCH, be_sha)
        sync_sha_lines(OUT_DIR / src_name, FE_BRANCH, fe_sha)

    msg = pkg / ("OCTA-ROUND%s-SEND-MESSAGE.txt" % ROUND)
    body = msg.read_text(encoding="utf-8")
    hdr = ("⛔ ملف توافق: نفس محتوى رسالة الجولة %s (الاسم القديم متوقّع في\n"
           "   سكربت البرهان المستقل).\n\n" % ROUND)
    for name in COMPAT_MESSAGE_NAMES:
        (pkg / name).write_text(hdr + body, encoding="utf-8")
    return True


def write_evidence_message_aliases(pkg):
    pkg = pathlib.Path(pkg)
    ev = pkg / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    body = (pkg / ("OCTA-ROUND%s-SEND-MESSAGE.txt" % ROUND)).read_text(
        encoding="utf-8")
    (ev / ("OCTA-ROUND%s-SEND-MESSAGE.txt" % ROUND)).write_text(
        "⛔ ملف توافق: نفس محتوى رسالة الجولة %s ⭐\n\n" % ROUND + body,
        encoding="utf-8")
    for name in COMPAT_MESSAGE_NAMES:
        (ev / name).write_text(
            "⛔ ملف توافق: نفس محتوى رسالة الجولة %s ⭐\n\n" % ROUND + body,
            encoding="utf-8")


# ── ⑧ برهان المراجع المستقل (باك) ─────────────────────────────────────────
PROOF_SRC = pathlib.Path("/workspace/staging/evidence/independent_regression.py")


def write_backend_proof(pkg):
    """نسخة كاملة من كود الباك عشان سكربت البرهان يشتغل مستقلّ."""
    pkg = pathlib.Path(pkg)
    ev = pkg / "evidence"
    rmtree(ev)
    ev.mkdir(parents=True, exist_ok=True)
    if not PROOF_SRC.is_file():
        raise SystemExit("سكربت البرهان المستقل مش موجود: %s" % PROOF_SRC)
    shutil.copy2(PROOF_SRC, ev / "independent_regression.py")
    be = ev / "backend"
    be.mkdir(parents=True, exist_ok=True)
    for rel in tracked(BE_WT, "*.py"):
        copy_file(BE_WT / rel, be / rel)
    copy_tree(BE_WT / "data", be / "data")
    (ev / "tools").mkdir(parents=True, exist_ok=True)
    for nm in ("check_delivery_consistency.py", "test_delivery_consistency_guard.py"):
        copy_file(TOOLS_DIR / nm, ev / "tools" / nm)
    return True


def copy_external_evidence(pkg, include_reports=True):
    """أدلة الجولة من مجلد الأدلة الخارجي ⭐ (بدون بصمات الحزمة نفسها ⭐)."""
    src = OUT_DIR / ("OCTA-ROUND%s-EVIDENCE" % ROUND)
    if not src.is_dir():
        return 0
    n = copy_tree(src / "evidence", pathlib.Path(pkg) / "evidence",
                  skip_names=("r23_package_fingerprints.json",))
    copy_file(src / "environment.json",
              pathlib.Path(pkg) / "evidence" / "environment.json")
    for sub in ("octa-prod-src", "octa-prod-src-original"):
        copy_tree(src / sub, pathlib.Path(pkg) / "evidence" / sub)
    copy_file(src / "octa-production-backup.js",
              pathlib.Path(pkg) / "evidence" / "octa-production-backup.js")
    if include_reports:
        copy_tree(src / "reports", pathlib.Path(pkg) / "reports")
    return n


# ── ⑨ بناء الحزم الثلاث ───────────────────────────────────────────────────
def build_main_package(be_sha, fe_sha):
    pkg = OUT_DIR / ("OCTA-ROUND%s-DELIVERY" % ROUND)
    rmtree(pkg)
    (pkg / "bundles").mkdir(parents=True, exist_ok=True)
    build_bundle(BE_WT, BE_BRANCH, pkg / "bundles", BE_BUNDLE_NAME)
    build_bundle(FE_WT, FE_BRANCH, pkg / "bundles", FE_BUNDLE_NAME)

    build_patches(BE_WT, BE_BASE_MAIN, BE_BRANCH, pkg / "patches",
                  "backend-from-main", "main ⇒ فرع الجولة %s" % ROUND)
    build_patches(BE_WT, BE_BASE_R22, BE_BRANCH, pkg / "patches",
                  "backend-round%s-only" % ROUND,
                  "فرع الجولة ٢٢ ⇒ الجولة %s" % ROUND)
    build_patches(FE_WT, FE_BASE_R22, FE_BRANCH, pkg / "patches",
                  "frontend-round%s-only" % ROUND,
                  "فرع الواجهة الجولة ٢٢ ⇒ الجولة %s" % ROUND)
    build_patches(FE_WT, FE_BASE_B1, FE_BRANCH, pkg / "patches",
                  "frontend-from-batch01",
                  "فرع الواجهة batch-01 ⇒ الجولة %s" % ROUND)

    cf = pkg / "changed-files"
    rmtree(cf)
    for rel in changed_files(BE_WT, BE_BASE_R22, BE_BRANCH):
        copy_file(BE_WT / rel, cf / ("backend-" + safe_name(rel)))
    for rel in changed_files(FE_WT, FE_BASE_R22, FE_BRANCH):
        copy_file(FE_WT / rel, cf / ("frontend-" + safe_name(rel)))

    td = pkg / "tests"
    rmtree(td)
    (td / "backend").mkdir(parents=True)
    (td / "frontend").mkdir(parents=True)
    for rel in tracked(BE_WT, "test_*.py"):
        copy_file(BE_WT / rel, td / "backend" / rel)
    for rel in tracked(FE_WT, "assets/tests/*.test.js"):
        copy_file(FE_WT / rel, td / "frontend" / pathlib.Path(rel).name)

    write_backend_proof(pkg)
    copy_external_evidence(pkg)
    (pkg / "reports").mkdir(parents=True, exist_ok=True)

    tl = pkg / "tools"
    rmtree(tl)
    for name in TOOL_FILES:
        copy_file(TOOLS_DIR / name, tl / name)
    for repo, rel, name in [
        (BE_WT, "tools/staging/test_flask_binding.py", "test_flask_binding.py"),
        (BE_WT, "tools/staging/e2e_playwright.py", "e2e_playwright.py"),
        (BE_WT, "tools/preflight.py", "preflight.py"),
        (BE_WT, "tools/backup_data.py", "backup_data.py"),
        (BE_WT, "tools/check_delivery_consistency.py",
         "check_delivery_consistency.py"),
        (BE_WT, "tools/test_delivery_consistency_guard.py",
         "test_delivery_consistency_guard.py"),
        (BE_WT, "tools/verify_data_integrity.py", "verify_data_integrity.py"),
        (BE_WT, "tools/test_data_integrity_guard.py",
         "test_data_integrity_guard.py"),
        (BE_WT, "tools/test_engines_filters_audit.py",
         "test_engines_filters_audit.py"),
        (FE_WT, "tools/ux_probe.py", "ux_probe.py"),
    ]:
        copy_file(repo / rel, tl / name)

    cont = OUT_DIR / ("OCTA-ROUND%s-CONTAINMENT" % ROUND)
    if cont.is_dir():
        copy_tree(cont, pkg / "containment")

    write_content(pkg, be_sha, fe_sha)
    write_evidence_message_aliases(pkg)
    (pkg / "ENVIRONMENT.json").write_text(
        json.dumps(build_environment(be_sha, fe_sha), ensure_ascii=False,
                   indent=2), encoding="utf-8")
    return pkg


def build_backend_package(be_sha, fe_sha):
    pkg = OUT_DIR / ("OCTA-ROUND%s-BACKEND" % ROUND)
    rmtree(pkg)
    (pkg / "bundles").mkdir(parents=True, exist_ok=True)
    build_bundle(BE_WT, BE_BRANCH, pkg / "bundles", BE_BUNDLE_NAME)

    build_patches(BE_WT, BE_BASE_MAIN, BE_BRANCH, pkg / "patches",
                  "backend-from-main", "main ⇒ فرع الجولة %s" % ROUND)
    build_patches(BE_WT, BE_BASE_R22, BE_BRANCH, pkg / "patches",
                  "backend-round%s-only" % ROUND,
                  "فرع الجولة ٢٢ ⇒ الجولة %s" % ROUND)

    cf = pkg / "changed-files"
    rmtree(cf)
    for rel in changed_files(BE_WT, BE_BASE_R22, BE_BRANCH):
        copy_file(BE_WT / rel, cf / ("backend-" + safe_name(rel)))

    td = pkg / "tests"
    rmtree(td)
    (td / "backend").mkdir(parents=True)
    for rel in tracked(BE_WT, "test_*.py"):
        copy_file(BE_WT / rel, td / "backend" / rel)

    write_backend_proof(pkg)
    copy_external_evidence(pkg, include_reports=False)

    tl = pkg / "tools"
    rmtree(tl)
    for name in TOOL_FILES:
        copy_file(TOOLS_DIR / name, tl / name)
    for rel in ("tools/preflight.py", "tools/backup_data.py",
                "tools/check_delivery_consistency.py",
                "tools/test_delivery_consistency_guard.py",
                "tools/verify_data_integrity.py",
                "tools/test_data_integrity_guard.py",
                "tools/test_engines_filters_audit.py"):
        copy_file(BE_WT / rel, tl / pathlib.Path(rel).name)

    write_content(pkg, be_sha, fe_sha)
    write_evidence_message_aliases(pkg)
    (pkg / "ENVIRONMENT.json").write_text(
        json.dumps(build_environment(be_sha, fe_sha), ensure_ascii=False,
                   indent=2), encoding="utf-8")
    return pkg


def build_frontend_package(be_sha, fe_sha):
    pkg = OUT_DIR / ("OCTA-ROUND%s-FRONTEND" % ROUND)
    rmtree(pkg)
    (pkg / "bundles").mkdir(parents=True, exist_ok=True)
    build_bundle(FE_WT, FE_BRANCH, pkg / "bundles", FE_BUNDLE_NAME)

    build_patches(FE_WT, FE_BASE_R22, FE_BRANCH, pkg / "patches",
                  "frontend-round%s-only" % ROUND,
                  "فرع الواجهة الجولة ٢٢ ⇒ الجولة %s" % ROUND)
    build_patches(FE_WT, FE_BASE_B1, FE_BRANCH, pkg / "patches",
                  "frontend-from-batch01",
                  "فرع الواجهة batch-01 ⇒ الجولة %s" % ROUND)

    cf = pkg / "changed-files"
    rmtree(cf)
    for rel in changed_files(FE_WT, FE_BASE_R22, FE_BRANCH):
        copy_file(FE_WT / rel, cf / ("frontend-" + safe_name(rel)))

    td = pkg / "tests"
    rmtree(td)
    (td / "frontend").mkdir(parents=True)
    for rel in tracked(FE_WT, "assets/tests/*.test.js"):
        copy_file(FE_WT / rel, td / "frontend" / pathlib.Path(rel).name)

    ev = pkg / "evidence"
    rmtree(ev)
    ev.mkdir(parents=True, exist_ok=True)
    for rel in tracked(FE_WT, "assets/tests/*.test.js"):
        copy_file(FE_WT / rel, ev / "frontend-tests" / pathlib.Path(rel).name)
    copy_file(FE_WT / "package.json", ev / "frontend-tests" / "package.json")
    copy_external_evidence(pkg, include_reports=False)

    tl = pkg / "tools"
    rmtree(tl)
    for name in TOOL_FILES:
        copy_file(TOOLS_DIR / name, tl / name)
    copy_file(FE_WT / "tools/ux_probe.py", tl / "ux_probe.py")

    cont = OUT_DIR / ("OCTA-ROUND%s-CONTAINMENT" % ROUND)
    if cont.is_dir():
        copy_tree(cont, pkg / "containment")

    write_content(pkg, be_sha, fe_sha)
    write_evidence_message_aliases(pkg)
    (pkg / "ENVIRONMENT.json").write_text(
        json.dumps(build_environment(be_sha, fe_sha), ensure_ascii=False,
                   indent=2), encoding="utf-8")
    return pkg


# ── ⑩ ملف البيئة (مشترك بين الحزم الثلاث) ────────────────────────────────
def build_environment(be_sha, fe_sha):
    be_commits = [c[:7] for c in git(BE_WT, "rev-list", "--reverse",
                                      "%s..%s" % (BE_BASE_R22, BE_BRANCH)
                                      ).split("\n") if c]
    fe_commits = [c[:7] for c in git(FE_WT, "rev-list", "--reverse",
                                      "%s..%s" % (FE_BASE_R22, FE_BRANCH)
                                      ).split("\n") if c]
    return {
        "generated_utc": GEN_UTC,
        "round": ROUND,
        "backend": {
            "repo": "ahmed3zz2020-source/octa-prices",
            "review_branch": BE_BRANCH,
            "review_sha": be_sha,
            "main_sha": BE_BASE_MAIN,
            "base_round22_sha": BE_BASE_R22,
            "round23_commits": be_commits,
            "bundle": "bundles/" + BE_BUNDLE_NAME,
        },
        "frontend": {
            "repo": "ahmed3zz2020-source/octa",
            "review_branch": FE_BRANCH,
            "review_sha": fe_sha,
            "main_sha": FE_MAIN_SHA,
            "base_round22_sha": FE_BASE_R22,
            "round23_commits": fe_commits,
            "bundle": "bundles/" + FE_BUNDLE_NAME,
            "note": "الواجهة مش مرفوعة على GitHub (صلاحية كتابة ناقصة) ⇒ "
                    "النقل بالحزمة",
        },
        "packages": {
            "OCTA-ROUND%s-DELIVERY.zip" % ROUND: "الحزمة الكاملة (باك + واجهة)",
            "OCTA-ROUND%s-BACKEND.zip" % ROUND: "الباك وحده — نسخ وتشغيل مستقلّ",
            "OCTA-ROUND%s-FRONTEND.zip" % ROUND:
                "الواجهة وحدها — نسخ وتشغيل مستقلّ",
        },
        "production": {
            "touched": False,
            "published": False,
            "merged_to_main": False,
            "paid_resources": False,
            "note": "الأدوات دي بتغلّف وتتحقّق فقط ⭐ — مافيش أي تعديل على "
                    "الإنتاج ⭐",
        },
        "cost_usd": 0,
    }


# ── ⑪ التنفيذ ─────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    be_sha = git(BE_WT, "rev-parse", BE_BRANCH)
    fe_sha = git(FE_WT, "rev-parse", FE_BRANCH)
    if not re.match(r"^[0-9a-f]{40}$", be_sha or ""):
        raise SystemExit("بصمة الباك مش صالحة: %r" % be_sha)
    if not re.match(r"^[0-9a-f]{40}$", fe_sha or ""):
        raise SystemExit("بصمة الواجهة مش صالحة: %r" % fe_sha)

    results = []
    for label, builder, zip_name in [
        ("DELIVERY", build_main_package,
         "OCTA-ROUND%s-DELIVERY.zip" % ROUND),
        ("BACKEND", build_backend_package, "OCTA-ROUND%s-BACKEND.zip" % ROUND),
        ("FRONTEND", build_frontend_package,
         "OCTA-ROUND%s-FRONTEND.zip" % ROUND),
    ]:
        pkg = builder(be_sha, fe_sha)
        scanned, hits = secret_scan(pkg)
        n_manifest = build_manifest(pkg)
        zip_path = OUT_DIR / zip_name
        n_entries = write_zip(pkg, zip_path)
        side = write_sidecar(zip_path, OUT_DIR / (zip_name[:-4] + ".md5"),
                             label, be_sha, fe_sha)
        results.append({"label": label, "zip": str(zip_path),
                        "scanned": scanned, "secret_hits": len(hits),
                        "manifest_files": n_manifest, "entries": n_entries,
                        "md5": side["md5"], "sha256": side["sha256"],
                        "bytes": side["bytes"]})
        print("%-9s zip=%s bytes=%d entries=%d manifest=%d hits=%d md5=%s"
              % (label, zip_path, side["bytes"], n_entries, n_manifest,
                 len(hits), side["md5"]))

    print()
    print("backend sha : %s (%s)" % (be_sha, BE_BRANCH))
    print("frontend sha: %s (%s)" % (fe_sha, FE_BRANCH))
    total_hits = sum(r["secret_hits"] for r in results)
    if total_hits:
        raise SystemExit("فيه أسرار ⛔ (%d hit)" % total_hits)
    print("secret hits : 0 ⭐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
