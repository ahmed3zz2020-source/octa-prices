#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔒 R32 · e · ⭐⭐⭐ اختبار ⭐⭐⭐ **الرفض** ⭐⭐⭐ ⭐ (AC-01-1 ⭐⭐ ⭐ AC-01-2 ⭐⭐) ⭐⭐⭐

📌 الشرط ⭐⭐⭐ (AC-01-2 ⭐⭐⭐): ⭐⭐⭐ «أزل ⭐⭐ bundle ⭐⭐ أو ⭐⭐ غيّر ⭐⭐ ref ⭐⭐؛ ⭐⭐⭐ يجب ⭐⭐⭐
   ⭐⭐⭐ رفض ⭐⭐⭐ المرشح ⭐⭐⭐ وعدم ⭐⭐⭐ تسجيل ⭐⭐⭐ نجاح ⭐⭐⭐» ⭐⭐⭐ ⭐⭐⭐.

📌 الاختبار ⭐⭐⭐ ده ⭐⭐⭐ بياخد ⭐⭐⭐ حزم ⭐⭐⭐ R32 ⭐⭐⭐ الحقيقية ⭐⭐⭐ (لو موجودة ⭐⭐⭐) ⭐⭐⭐
   ⭐⭐⭐ وبيعمل ⭐⭐⭐ ٣ ⭐⭐⭐ حالات ⭐⭐⭐ ⭐⭐⭐:
   ① ⭐⭐⭐ الحزم ⭐⭐⭐ سليمة ⭐⭐⭐ ⇒ ⭐⭐⭐ لازم ⭐⭐⭐ تنجح ⭐⭐⭐ ⭐⭐⭐.
   ② ⭐⭐⭐ **حزمة ⭐⭐⭐ محذوفة** ⭐⭐⭐ ⇒ ⭐⭐⭐ لازم ⭐⭐⭐ **ترفض** ⭐⭐⭐ ⭐⭐⭐ (مش ⭐⭐⭐ نجاح ⭐⭐⭐) ⭐⭐⭐.
   ③ ⭐⭐⭐ **بصمة ⭐⭐⭐ حزمة ⭐⭐⭐ مختلفة** ⭐⭐⭐ ⇒ ⭐⭐⭐ لازم ⭐⭐⭐ **ترفض** ⭐⭐⭐ ⭐⭐⭐.
   ⭐⭐⭐ ولو ⭐⭐⭐ الحزم ⭐⭐⭐ مش ⭐⭐⭐ موجودة ⭐⭐⭐ ⇒ ⭐⭐⭐ بيعمل ⭐⭐⭐ نفس ⭐⭐⭐ الحالات ⭐⭐⭐ على ⭐⭐⭐
   ⭐⭐⭐ حزمة ⭐⭐⭐ صناعية ⭐⭐⭐ في ⭐⭐⭐ مجلد ⭐⭐⭐ مؤقت ⭐⭐⭐ ⭐⭐⭐ (يبقى ⭐⭐⭐ قابل ⭐⭐⭐ للتشغيل ⭐⭐⭐ في ⭐⭐⭐ الـCI ⭐⭐⭐) ⭐⭐⭐.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MANIFEST = "/workspace/output/OCTA-ROUND32-PACKAGES.json"
DEFAULT_PACKDIR = "/workspace/output/OCTA-ROUND32-DELIVERY"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("✅" if ok else "⛔") + " " + name + ((" ⭐ " + detail) if detail else ""))
    return bool(ok)


def digests(path):
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
            n += 1
    return md5.hexdigest(), sha.hexdigest()


def verify(manifest, packdir, manifest_path=""):
    """⛔ الرفض ⭐: بترجع ⭐ (ok ⭐ · reason ⭐) ⭐ — ⛔ ما بتقبلش ⭐ نجاح ⭐ بإي ⭐."""
    pkgs = (manifest or {}).get("packages") or []
    if not pkgs:
        return False, "MANIFEST_MISSING"
    alt = os.path.dirname(os.path.abspath(manifest_path or "")) or packdir
    for p in pkgs:
        zp = os.path.join(packdir, p.get("zip") or "")
        if not os.path.isfile(zp):
            zp = os.path.join(alt, p.get("zip") or "")   # ⭐ حزمة ⭐ التوصيل ⭐ في ⭐ المجلد ⭐ الأعلى ⭐
        if not os.path.isfile(zp):
            return False, "BUNDLE_MISSING:%s" % (p.get("zip"))
        md5, sha = digests(zp)
        if md5 != p.get("md5") or sha != p.get("sha256"):
            return False, "SHA_MISMATCH:%s" % (p.get("zip"))
    return True, "OK"


def synth(tmp):
    """⭐⭐⭐ حزمة ⭐⭐⭐ صناعية ⭐⭐⭐ + ⭐⭐⭐ مانيفست ⭐⭐⭐ ⭐⭐⭐ (للتشغيل ⭐⭐⭐ بدون ⭐⭐⭐ حزم ⭐⭐⭐ R32 ⭐⭐⭐) ⭐⭐⭐."""
    packdir = os.path.join(tmp, "packs")
    os.makedirs(packdir, exist_ok=True)
    names = []
    for i in range(2):
        name = "SYNTH-%d.zip" % i
        zp = os.path.join(packdir, name)
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("file.txt", "synthetic %d" % i)
        md5, sha = digests(zp)
        names.append({"zip": name, "md5": md5, "sha256": sha})
    manifest = {"packages": names}
    mp = os.path.join(tmp, "manifest.json")
    with open(mp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return mp, packdir, manifest


def main() -> int:
    print("═" * 72)
    print("🔒 R32 · e · ⭐⭐⭐ اختبار ⭐⭐⭐ الرفض ⭐⭐⭐ (حزمة ⭐⭐ محذوفة ⭐⭐ / ⭐⭐ بصمة ⭐⭐ مختلفة ⭐⭐)")
    print("═" * 72)
    tmp = tempfile.mkdtemp(prefix="r32-reject-")
    try:
        manifest_path = os.environ.get("OCTA_MANIFEST", DEFAULT_MANIFEST)
        packdir = os.environ.get("OCTA_PACKDIR", DEFAULT_PACKDIR)
        if os.path.isfile(manifest_path) and os.path.isdir(packdir):
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            source = "حزم R32 الحقيقية ⭐"
        else:
            manifest_path, packdir, manifest = synth(tmp)
            source = "حزمة صناعية ⭐ (حزم R32 مش موجودة ⭐)"

        ok, why = verify(manifest, packdir, manifest_path)
        check("الحزم ⭐⭐ السليمة ⭐⭐ ⇒ ⭐⭐ القبول ⭐⭐", ok, "%s ⭐ %s ⭐" % (source, why))

        # ② حزمة محذوفة ⭐ ⇒ الرفض ⭐
        copy_dir = os.path.join(tmp, "copy_missing")
        shutil.copytree(packdir, copy_dir)
        victim = manifest["packages"][0]["zip"]
        os.remove(os.path.join(copy_dir, victim))
        ok2, why2 = verify(manifest, copy_dir, manifest_path)
        check("حزمة ⭐⭐ محذوفة ⭐⭐ ⇒ ⭐⭐ **الرفض** ⭐⭐ (مش ⭐⭐ نجاح ⭐⭐)",
              (not ok2) and why2.startswith("BUNDLE_MISSING"),
              why2)

        # ③ بصمة مختلفة ⭐ ⇒ الرفض ⭐
        copy_dir2 = os.path.join(tmp, "copy_mismatch")
        shutil.copytree(packdir, copy_dir2)
        target = os.path.join(copy_dir2, manifest["packages"][0]["zip"])
        with open(target, "ab") as fh:
            fh.write(b"\x00tamper")
        ok3, why3 = verify(manifest, copy_dir2, manifest_path)
        check("بصمة ⭐⭐ حزمة ⭐⭐ مختلفة ⭐⭐ ⇒ ⭐⭐ **الرفض** ⭐⭐",
              (not ok3) and why3.startswith("SHA_MISMATCH"),
              why3)
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
