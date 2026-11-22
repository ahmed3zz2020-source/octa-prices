#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R32 · اختبار «جذور التصنيف الثابتة» ⭐ — عيب حقيقي في الماسح ⭐.

⭐ العيب ⭐⭐ (اكتُشف في R32 ⭐⭐): ⛔ المصنِّف ⭐⭐ كان بيقرأ سطر الأرشيف ⭐⭐
   ⭐⭐ من **جذور ثابتة** ⭐⭐ (مجلد جولة R29 ⭐⭐) ⭐⭐ ⇒ ⛔ في أي جولة تانية ⭐⭐
   ⭐⭐ السطر **ما بيتقراش** ⭐⭐ ⇒ ⛔ السطر الفاضي ⭐⭐ كان بيروح ⭐⭐ ⭐⭐
   ⭐⭐ للافتراضي ⭐⭐ ⇒ ⛔ **اتهام** ⭐⭐ كود إنتاج ⭐⭐ بتسرّب ⭐⭐ وهو ب innocent ⭐⭐.
   ⭐⭐ ⭐ مثال مقيس ⭐⭐ ⭐: مسح حزم R32 ⭐⭐ ⭐ ⇒ **52** ⭐⭐ تسرّب «حقيقي» ⭐⭐ ⭐
   ⭐⭐ ⭐ كلهم **إنذار كاذب** ⭐⭐ ⭐ ⇒ ⭐⭐ ⭐ صفر تسرّب حقيقي ⭐⭐ ⭐ بعد الإصلاح ⭐⭐ ⭐.

⭐ الاختبار ⭐: ⭐
   ①  الأرشيف ⭐⭐ في مجلد **مش** مثبّت ⭐⭐ ⇒ لازم المصنِّف **يلاقي السطر** ⭐⭐
       ⇒ ⭐⭐ الحكم على النص الصحيح ⭐⭐ (مش نص تاني ⭐⭐).
   ②  السطر الحقيقي ⭐⭐ ⇒ تسرّب حقيقي ⭐⭐ ⭐ (م Walnut مجرّب ⭐⭐ ⭐).
   ③  سطر **مش متاح** ⭐⭐ ⇒ لازم الحكم ⭐⭐ «غير متاح ⭐» ⭐⭐
       ⭐⭐ ⭐ (مش «تسرّب حقيقي» ⭐⭐ ⭐) ⭐⭐ ⇒ ⭐⭐ ⭐ ما بيّتلمش حد ببراء ⭐⭐ ⭐.
   ④  المسح ⭐⭐ ما يبارحش ⭐⭐ ⭐⇒ ok ⭐⭐ ⭐=false ⭐⭐ ⭐ (fail-closed ⭐⭐ ⭐) ⭐⭐ ⭐.

⭐ التشغيل ⭐: python3 tools/test_r32_scan_roots.py ⭐
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLF = os.path.join(ROOT, "tools", "r29_classify_secrets.py")

# ⭐ قيمة سرّية **حرفية** ⭐ ⇒ لازم تتصنّف تسرّب حقيقي ⭐ ⭐ (البرهان السلبي ⭐)
REAL_SECRET_LINE = 'ADMIN_TOKEN = "8f3c9d2e7a1b4f6c0d5e4a3b2c1d0f9ab"'
# ⭐ سطر **مرجع متغيّر بيئة** ⭐ ⇒ مش سر ⭐ ⭐
ENV_LINE = 'PROXY_SECRET = str(os.environ.get("OCTA_PROXY_SECRET", "") or "").strip()'


def load_module(env=None):
    """تحميل المصنِّف ⭐⭐ ⇒ ⭐⭐ بتلاعب بجذوره ⭐⭐ ⭐ (بدون تعديل الكود ⭐⭐ ⭐)."""
    old = dict(os.environ)
    if env:
        os.environ.update(env)
    try:
        spec = importlib.util.spec_from_file_location("clf_r32_roots", CLF)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return mod


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="r32_roots_")
    zip_dir = os.path.join(tmp, "OCTA-ROUND99-DELIVERY")
    os.makedirs(zip_dir, exist_ok=True)
    zip_path = os.path.join(zip_dir, "OCTA-ROUND99-BACKEND.zip")
    inner = "app/secret_file.py"
    inner_env = "app/env_file.py"
    # ⭐ ملفان منفصلان ⭐⭐ ⇒ ⭐ نافذة السطر ⭐⭐ ما تخلطش ⭐⭐ والملفين ⭐⭐
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(inner, "%s\n" % REAL_SECRET_LINE)
        zf.writestr(inner_env, "%s\n" % ENV_LINE)

    # ⭐⭐⭐ الأهم ⭐⭐⭐: ⭐ الأرشيف في مجلد **مش** مثبّت ⭐⭐ ⇒ ⭐ الأداة لازم
    # ⭐⭐⭐ تشتغل من غير تعديل يدوي ⭐⭐⭐ (متغيّر بيئة ⭐⭐ ⭐) ⭐⭐⭐.
    mod = load_module({"OCTA_ZIP_ROOTS": zip_dir})

    print("═" * 72)
    print("🔍 R32 · اختبار جذور التصنيف (عيب الماسح ⭐)")
    print("═" * 72)
    ok = True

    # ① ⭐ السطر بيتقرا من الأرشيف الصح ⭐ ⭐
    loc_env = {"location": "OCTA-ROUND99-BACKEND.zip::%s" % inner_env,
               "line": 1, "scope": "zip"}
    line_env = mod.read_line(loc_env)
    verdict_env, why_env = mod.classify(line_env, loc_env["location"])
    print("① السطر 1 ⭐ ⇒ read_line: %s ⭐ ⇒ %s (%s)"
          % ("OK" if line_env else "فارغ ⭐", verdict_env, why_env))
    if not line_env:
        print("   ⛔ الأرشيف في مجلد غير مثبّت ⭐⭐ ⇒ السطر ما اتقراش ⭐⭐ ⇒ العيب لسه موجود ⭐")
        ok = False
    elif verdict_env == "real_leak":
        print("   ⛔ مرجع متغيّر بيئة اتصنّف تسرّب ⭐ ⇒ ⛔ إنذار كاذب ⭐")
        ok = False

    # ② ⭐ السطر الحقيقي ⭐ ⇒ تسرّب حقيقي ⭐ ⭐
    loc_real = {"location": "OCTA-ROUND99-BACKEND.zip::%s" % inner,
                "line": 2, "scope": "zip"}
    line_real = mod.read_line(loc_real)
    verdict_real, why_real = mod.classify(line_real, loc_real["location"])
    print("② السطر 2 ⭐ ⇒ read_line: %s ⭐ ⇒ %s (%s)"
          % ("OK" if line_real else "فارغ ⭐", verdict_real, why_real))
    if verdict_real != "real_leak":
        print("   ⛔ قيمة سرّية حرفية ⭐⭐ ما اتصنّفتش تسرّب ⭐ ⇒ ⛔ تسرّب مخفي ⭐")
        ok = False

    # ③ ⭐ سطر مش متاح ⭐ ⇒ مش تسرّب ⭐ ⭐
    verdict_none, why_none = mod.classify("", "app/whatever.py")
    print("③ سطر فارغ ⭐ ⇒ %s (%s)" % (verdict_none, why_none))
    if verdict_none == "real_leak":
        print("   ⛔ سطر فاضي اتصنّف تسرّب حقيقي ⭐ ⇒ ⛔ اتهام ببراء ⭐ ⇒ ⛔ العيب لسه موجود ⭐")
        ok = False
    elif verdict_none != "unverifiable":
        print("   ⛔ الحكم المتوقع «unverifiable» ⭐ ⇒ خرج %s ⭐" % verdict_none)
        ok = False

    # ④ ⭐ المسح ⭐⭐ ما يبارحش ⭐⭐ ⭐ ⇒ ok=false ⭐⭐ ⭐ (fail-closed ⭐⭐ ⭐) ⭐⭐ ⭐
    scan = {
        "ok": True,
        "summary": {"distinct_secrets": 1, "total_findings": 1,
                    "scanned_git_objects": 0, "scanned_worktree_files": 0,
                    "scanned_zip_members": 1, "errors": [], "blocking_count": 0},
        "secrets": [{
            "fingerprint": "fp-r32-roots",
            "pattern": "assigned_secret",
            "locations": [{"location": "app/missing_file.py", "line": 3,
                           "scope": "worktree"}],
        }],
    }
    scan_path = os.path.join(tmp, "scan.json")
    with open(scan_path, "w", encoding="utf-8") as fh:
        json.dump(scan, fh, ensure_ascii=False)
    out_path = os.path.join(tmp, "out.json")
    old_argv = sys.argv
    sys.argv = ["r29_classify_secrets.py", scan_path, out_path]
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        mod.main()
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv
    with open(out_path, encoding="utf-8") as fh:
        out = json.load(fh)
    print("④ موضع مش متاح ⭐ ⇒ ok=%s ⭐ · real_leaks=%s ⭐ · unverifiable=%s ⭐"
          % (out.get("ok"), out.get("real_leaks"), out.get("unverifiable")))
    if out.get("ok") is not False:
        print("   ⛔ الموضع المحجوب ⭐⭐ ما منعش الاعتماد ⭐ ⇒ ⛔ المسح قال «نظيف» ⭐ وهو مش كده ⭐")
        ok = False
    if out.get("real_leaks") != 0:
        print("   ⛔ اتهام ببراء ⭐ ⇒ real_leaks=%s ⭐" % out.get("real_leaks"))
        ok = False

    print("═" * 72)
    print("النتيجة ⭐: %s ⭐" % ("PASS ⭐" if ok else "FAIL ⭐"))
    print("═" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
