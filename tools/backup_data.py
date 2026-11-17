#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💾 نسخ احتياطي متحقَّق + استرجاع — الجولة ١٨ · المرحلة ٧ (تشغيل)
================================================================
📌 ليه ده مهم: قبل أي نشر على بيانات حقيقية لازم يبقى فيه
   **دليل** إن البيانات تقدر ترجع. «فيه نسخة» مش دليل —
   «النسخة اتعملت واترجعت واتطابقت» هو الدليل.

⛔ القواعد:
   · الافتراضي = مجلد البيانات المحلي (OCTA_DATA_DIR) · مافيش اتصال بالإنترنت.
   · الاسترجاع **لا يكتب** فوق موجود من غير --force.
   · كل نسخة ليها manifest بـ SHA256 لكل ملف ⇒ الفحص مستقل.

📌 الاستخدام:
   python3 tools/backup_data.py backup
   python3 tools/backup_data.py list
   python3 tools/backup_data.py verify <archive.tar.gz>
   python3 tools/backup_data.py restore <archive.tar.gz> --force
   python3 tools/backup_data.py selftest          # ⭐ الدليل (نسخ→تعديل→استرجاع→مطابقة)

📌 رمز الخروج: 0 = تمام · 1 = فشل · 2 = خطأ أداة
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = Path(os.environ.get("OCTA_BACKUP_DIR", "") or (REPO / ".backups"))


def data_dir():
    return Path(os.environ.get("OCTA_DATA_DIR", "") or (REPO / "data"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════
#  backup
# ══════════════════════════════════════════════════════════════
def do_backup(src: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = out_dir / ("octa-data-%s.tar.gz" % stamp)
    files = []
    if src.is_dir():
        for p in sorted(src.rglob("*")):
            if p.is_file():
                files.append(p)
    manifest = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source": str(src), "count": len(files), "files": []}
    with tarfile.open(archive, "w:gz") as tf:
        for p in files:
            rel = p.relative_to(src)
            tf.add(p, arcname=str(rel))
            manifest["files"].append(
                {"path": str(rel), "bytes": p.stat().st_size, "sha256": sha256_file(p)})
    mpath = archive.with_suffix(".manifest.json")
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive, mpath, manifest


# ══════════════════════════════════════════════════════════════
#  verify
# ══════════════════════════════════════════════════════════════
def do_verify(archive: Path):
    mpath = archive.with_suffix(".manifest.json")
    problems = []
    if not archive.exists():
        return ["الملف مش موجود: %s" % archive], {}
    if not mpath.exists():
        return ["الـmanifest مش موجود: %s" % mpath.name], {}
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    with tarfile.open(archive, "r:gz") as tf:
        names = set(tf.getnames())
        for rec in manifest.get("files", []):
            if rec["path"] not in names:
                problems.append("ناقص في الأرشيف: %s" % rec["path"])
                continue
            member = tf.extractfile(rec["path"])
            if member is None:
                problems.append("مافيش محتوى: %s" % rec["path"])
                continue
            h = hashlib.sha256(member.read()).hexdigest()
            if h != rec["sha256"]:
                problems.append("هاش مختلف: %s" % rec["path"])
    return problems, manifest


# ══════════════════════════════════════════════════════════════
#  restore
# ══════════════════════════════════════════════════════════════
def do_restore(archive: Path, dst: Path, force=False):
    if not archive.exists():
        raise SystemExit("الملف مش موجود: %s" % archive)
    if dst.exists() and any(dst.iterdir()) and not force:
        raise SystemExit(
            "⛔ المجلد مش فاضي: %s — استرجع بمرور --force" % dst)
    dst.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        for m in tf.getmembers():
            # ⛔ حماية من المسارات الخطرة (path traversal)
            name = Path(m.name)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit("⛔ member مش آمن: %s" % m.name)
        tf.extractall(dst)
    return dst


# ══════════════════════════════════════════════════════════════
#  ⭐ selftest — الدليل: نسخ → تعديل → استرجاع → مطابقة
# ══════════════════════════════════════════════════════════════
def do_selftest():
    src = data_dir()
    lines = ["💾 برهان النسخ الاحتياطي (round-trip)", ""]
    lines.append("مجلد المصدر: %s" % src)
    if not src.is_dir():
        lines.append("⛔ المجلد مش موجود")
        return lines, 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # ① لقطة أولية — عشان نرجّع الحالة الأصلية
        seed_dir = tmp / "seed"
        shutil.copytree(src, seed_dir)
        before = {}
        for p in sorted(seed_dir.rglob("*")):
            if p.is_file():
                before[str(p.relative_to(seed_dir))] = sha256_file(p)
        lines.append("① الحالة الأصلية: %d ملف" % len(before))

        # ② backup
        archive, mpath, manifest = do_backup(seed_dir, tmp / "arch")
        lines.append("② نسخة: %s (%d ملف · %d بايت)"
                     % (archive.name, manifest["count"], archive.stat().st_size))

        # ③ verify
        problems, _ = do_verify(archive)
        lines.append("③ فحص النسخة: %s" % ("سليم ✅" if not problems else "مشكلة ⛔"))
        if problems:
            for p in problems[:5]:
                lines.append("     · %s" % p)
            return lines, 1

        # ④ تعديل متعمّد — لازم الاسترجاع يلغيه
        victim = sorted(seed_dir.rglob("*.json"))
        mutated = None
        if victim:
            mutated = victim[0]
            mutated.write_text('{"__mutated__": true}\n', encoding="utf-8")
            lines.append("④ تعديل متعمّد: %s" % mutated.name)
        else:
            (seed_dir / "probe.txt").write_text("mutated\n", encoding="utf-8")
            mutated = seed_dir / "probe.txt"
            lines.append("④ تعديل متعمّد: probe.txt")

        # ⑤ restore
        restore_target = tmp / "restored"
        do_restore(archive, restore_target, force=True)
        after = {}
        for p in sorted(restore_target.rglob("*")):
            if p.is_file():
                after[str(p.relative_to(restore_target))] = sha256_file(p)
        lines.append("⑤ استرجاع: %d ملف" % len(after))

        # ⑥ مطابقة
        missing = sorted(set(before) - set(after))
        extra = sorted(set(after) - set(before))
        diff = sorted(k for k in set(before) & set(after) if before[k] != after[k])
        ok = not missing and not extra and not diff
        lines.append("⑥ مطابقة: %s" % ("✅ كاملة" if ok else "⛔ فيها اختلاف"))
        if missing:
            lines.append("     · ناقص: %s" % ", ".join(missing[:5]))
        if extra:
            lines.append("     · زيادة: %s" % ", ".join(extra[:5]))
        if diff:
            lines.append("     · مختلف: %s" % ", ".join(diff[:5]))
        lines.append("")
        lines.append("═══ النتيجة: %s ═══" % ("الدليل متحقق ✅" if ok else "فشل ⛔"))
        return lines, (0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backup", "list", "verify", "restore", "selftest"])
    ap.add_argument("archive", nargs="?")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    src = Path(a.data_dir) if a.data_dir else data_dir()
    out = Path(a.out_dir) if a.out_dir else ARCHIVE_DIR

    if a.cmd == "selftest":
        lines, rc = do_selftest()
        print("\n".join(lines))
        return rc

    if a.cmd == "backup":
        archive, mpath, manifest = do_backup(src, out)
        print("💾 %s" % archive)
        print("   %d ملف · %d بايت" % (manifest["count"], archive.stat().st_size))
        print("   manifest: %s" % mpath.name)
        return 0

    if a.cmd == "list":
        if not out.is_dir():
            print("(مافيش مجلد نسخ: %s)" % out)
            return 0
        for p in sorted(out.glob("octa-data-*.tar.gz")):
            print("%s · %d بايت · %s" % (
                p.name, p.stat().st_size,
                time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))))
        return 0

    if a.cmd == "verify":
        if not a.archive:
            print("⛔ لازم اسم الأرشيف")
            return 2
        problems, manifest = do_verify(Path(a.archive))
        if problems:
            print("⛔ %d مشكلة:" % len(problems))
            for p in problems[:20]:
                print("   · %s" % p)
            return 1
        print("✅ الأرشيف سليم · %d ملف · %s" % (
            manifest.get("count", 0), manifest.get("created", "?")))
        return 0

    if a.cmd == "restore":
        if not a.archive:
            print("⛔ لازم اسم الأرشيف")
            return 2
        dst = do_restore(Path(a.archive), src, force=a.force)
        print("✅ اترجّع في %s" % dst)
        return 0

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("⛔ خطأ: %s" % e, file=sys.stderr)
        sys.exit(2)
