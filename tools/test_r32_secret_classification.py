#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R32 · اختبار «فجوة تصنيف الأسرار» ⭐.

⭐ العيب ⭐: ⛔ التصنيف كان بيقف عند **أول موضع** ⭐ ⭐ ⇒ ⛔ سر متكرر ⭐ ⭐
   (بصمة واحدة ⭐ ⭐) ⭐ ⭐ في **ملف اختبار** ⭐ ⭐ + في **كود الإنتاج** ⭐ ⭐
   ⇒ ⛔ المكان الثاني ما اتصنّفش ⭐ ⭐ ⇒ ⛔ **تسرّب حقيقي مخفي** ⭐ ⭐.

⭐ الاختبار ⭐: ⭐ سر واحد ⭐ ⭐ + موضعين ⭐ ⭐ ⇒ ⭐ لازم يطلع **تسرّب حقيقي** ⭐ ⭐.
⭐ التشغيل ⭐: python tools/test_r32_secret_classification.py ⭐
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLF = os.path.join(ROOT, "tools", "r29_classify_secrets.py")

VALUE = "8f3c9d2e7a1b4f6c0d5e4a3b2c1d0f9"


def load_module():
    spec = importlib.util.spec_from_file_location("r29_classify_secrets_r32", CLF)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="r32_cls_")
    repo = os.path.join(tmp, "repo")
    os.makedirs(os.path.join(repo, "tests"), exist_ok=True)
    with open(os.path.join(repo, "app.py"), "w", encoding="utf-8") as f:
        f.write('def call():\n    return "%s"\n' % VALUE)
    with open(os.path.join(repo, "tests", "test_x.py"), "w", encoding="utf-8") as f:
        f.write('def t():\n    return "%s"\n' % VALUE)

    scan = {
        "ok": True,
        "summary": {"distinct_secrets": 1, "total_findings": 2,
                    "scanned_git_objects": 0, "scanned_worktree_files": 2,
                    "scanned_zip_members": 0, "errors": [], "blocking_count": 0},
        "secrets": [{
            "fingerprint": "test-fingerprint-r32",
            "pattern": "hex40",
            "locations": [
                {"location": "tests/test_x.py", "line": 2, "scope": "worktree"},
                {"location": "app.py", "line": 2, "scope": "worktree"},
            ],
        }],
    }
    scan_path = os.path.join(tmp, "scan.json")
    with open(scan_path, "w", encoding="utf-8") as f:
        json.dump(scan, f, ensure_ascii=False)

    mod = load_module()
    mod.REPO_ROOTS = [repo]
    mod.EVIDENCE_ROOTS = []
    mod.ZIP_ROOTS = [tmp]

    out_path = os.path.join(tmp, "out.json")
    sys.argv = ["r29_classify_secrets.py", scan_path, out_path]
    mod.main()
    with open(out_path, encoding="utf-8") as f:
        out = json.load(f)

    print("═" * 72)
    print("🔐 R32 · اختبار فجوة تصنيف الأسرار")
    print("═" * 72)
    print("distinct=%s · locations_scanned=%s · real_leaks=%s"
          % (out.get("total_distinct"), out.get("locations_scanned", "—"),
             out.get("real_leaks")))
    ok = True
    if out.get("real_leaks") != 1:
        print("⛔ فشلت ⭐ — السر في كود الإنتاج لازم يتصنّف تسرّب حقيقي ⭐")
        print("   ⭐ (النتيجة %s ⭐ ⇒ ⭐ الموضع الثاني ما اتصنّفش ⭐ ⇒ ⭐ فجوة ⭐)"
              % out.get("real_leaks"))
        ok = False
    else:
        print("✅ السر في كود الإنتاج اتصنّف تسرّب حقيقي ⭐ (مفيش إخفاء ⭐)")
    if out.get("locations_scanned") not in (2, None):
        print("⛔ locations_scanned=%s ⭐ (المتوقع 2 ⭐)"
              % out.get("locations_scanned"))
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
