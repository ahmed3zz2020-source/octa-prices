#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R32 · e · حارس الكتابة الذرّية ⭐ — يفحص كل كتابة مؤقتة في المستودع ⭐.

⭐ العيب ⭐ (اللي هذا الحارس بيقفله ⭐): ⛔ **اسم مؤقت ثابت** ⭐ ⭐
   (`.tmp` ⭐ أو `.t` ⭐ أو أي لاحقة ⭐⭐ تنتهي ⭐⭐ بيهم ⭐⭐) ⭐ ⇒ ⛔ عمليتين ⭐
   ⇒ ⛔ lost update ⭐ ⇒ ⛔ وفي `pinlock.json` ⭐ ⭐ ⇒ ⛔ **عدّاد المحاولات** ⭐ ⭐ بيطيع ⭐ ⭐.
⭐ وكل **فحص تشخيصي** ⭐ (probe ⭐) ⭐ لازم يكون باسم **فريد** ⭐ (pid ⭐) ⭐.

⭐⭐⭐ (R32 · e) ⭐⭐⭐ التغطية ⭐⭐⭐ اتوسّعت ⭐⭐⭐ ⭐⭐⭐
   ① لاحقة ⭐⭐⭐ أي ⭐⭐⭐ اسم ⭐⭐⭐ مؤقت ⭐⭐⭐ ثابت ⭐⭐⭐ بـ`with_suffix` ⭐⭐⭐ ⭐ (منها ⭐⭐⭐ `.json.tmp` ⭐⭐⭐) ⭐⭐⭐
   ② ربط ⭐⭐⭐ بـ`+` ⭐⭐⭐ لأي ⭐⭐⭐ لاحقة ⭐⭐⭐ ثابتة ⭐⭐⭐ ⭐ (منها ⭐⭐⭐ `+ ".tmp"` ⭐⭐⭐) ⭐⭐⭐
   ③ نفس ⭐⭐⭐ القواعد ⭐⭐⭐ في ⭐⭐⭐ جافاسكريبت ⭐⭐⭐ (`writeFileSync` ⭐⭐⭐) ⭐⭐⭐
   ④ استثناء ⭐⭐⭐ **صريح** ⭐⭐⭐ ⭐: ⭐⭐⭐ سطور ⭐⭐⭐ فحص ⭐⭐⭐ الوجود ⭐⭐⭐ ⭐ — ⭐⭐⭐ دي ⭐⭐⭐
      ⭐⭐⭐ فحوص ⭐⭐⭐ (بتتأكد ⭐⭐⭐ إن ⭐⭐⭐ مفيش ⭐⭐⭐ ملف ⭐⭐⭐ مؤقت ⭐⭐⭐ فاضل ⭐⭐⭐) ⭐⭐⭐ مش ⭐⭐⭐ كتابة ⭐⭐⭐ ⭐⭐⭐
   ⑤ واجهة ⭐⭐⭐ الجافاسكريبت ⭐⭐⭐ بتتشغّل ⭐⭐⭐ في ⭐⭐⭐ الـCI ⭐⭐⭐ ⭐ (ك&&\⭐⭐ مسارات ⭐⭐⭐
      ⭐⭐⭐ `fe` ⭐⭐⭐ ⭐⭐⭐ `../fe` ⭐⭐⭐ ⭐⭐⭐ `../octa` ⭐⭐⭐ ⭐⭐⭐) ⭐⭐⭐ ⭐⭐⭐

⭐ التشغيل ⭐: python tools/test_r32_safe_writes.py ⭐
⭐ المخرج ⭐: rc=0 ⭐ ⇒ مفيش اسم ثابت ⭐ · rc≠0 ⭐ ⇒ ⛔ فيه ⭐ (مع السطر ⭐).
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "r29-evidence", "r30-evidence", "r31-evidence", "r32-evidence"}
SELF = os.path.basename(__file__)

# ⭐⭐⭐ (R32 · e) ⭐⭐⭐ أي ⭐⭐⭐ لاحقة ⭐⭐⭐ مؤقتة ⭐⭐⭐ ثابتة ⭐⭐⭐ (`.tmp` ⭐ · `.t` ⭐ · `.json.tmp` ⭐ …) ⭐⭐⭐
RE_TMP_SUFFIX = re.compile(r"\.with_suffix\(\s*[\"'][^\"']*\.t(mp)?[\"']\s*\)")
# ⭐⭐⭐ (R32 · e) ⭐⭐⭐ أي ⭐⭐⭐ ربط ⭐⭐⭐ ثابت ⭐⭐⭐ (`+ ".tmp"` ⭐ · `+ ".t"` ⭐ …) ⭐⭐⭐
RE_TMP_CONCAT = re.compile(r"\+\s*[\"'][^\"']*\.t(mp)?[\"']")
# ⭐⭐⭐ استثناء ⭐⭐⭐ صريح ⭐⭐⭐: ⭐⭐⭐ سطور ⭐⭐⭐ الفحص ⭐⭐⭐ (موجود ⭐⭐⭐ ولا ⭐⭐⭐ لأ ⭐⭐⭐) ⭐⭐⭐
RE_EXISTS_CHECK = re.compile(r"os\.path\.exists\(")
# ⭐ قاعدة ② ⭐ فحص تشخيصي ⭐ (probe ⭐) ⭐ باسم **ثابت** ⭐ ⭐
RE_PROBE_WRITE = re.compile(r"(?i)(probe[^\n=]*=\s*[^\n]*|write_text\([^\n]*probe)")
RE_PID = re.compile(r"(?i)pid|getpid|uuid|rand")

RE_JS_FIXED_TMP = re.compile(r"writeFileSync\(\s*[\"'][^\"']*\.(tmp|t)[\"']")
RE_JS_FIXED_TMP_CONCAT = re.compile(r"writeFileSync\([^\n]*\+\s*[\"'][^\"']*\.t(mp)?[\"']")


def py_files():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith(".py") and n != SELF:
                yield os.path.join(base, n)


def fe_root():
    """📁 جذر الواجهة ⭐ — مسارات ⭐⭐ الـCI ⭐⭐ ⭐ (fe ⭐⭐ ../fe ⭐⭐ ../octa ⭐⭐) ⭐⭐."""
    env_root = (os.environ.get("OCTA_FE_ROOT") or "").strip()
    cands = ([env_root] if env_root else []) + [
        "fe", os.path.join("..", "fe"), os.path.join("..", "octa")]
    for cand in cands:
        p = os.path.abspath(os.path.join(ROOT, cand))
        if os.path.isdir(p) and os.path.abspath(p) != os.path.abspath(ROOT):
            return p
    return None


def js_files():
    fe = fe_root()
    if not fe:
        return
    for base, dirs, names in os.walk(fe):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith(".js"):
                yield os.path.join(base, n)


def main() -> int:
    bad = []

    # ── ① الباك: اسم مؤقت ثابت ⭐ ────────────────────────────────────────
    for p in py_files():
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if RE_EXISTS_CHECK.search(line):
                # ⭐⭐⭐ سطر ⭐⭐⭐ فحص ⭐⭐⭐ (موجود ⭐⭐⭐ ولا ⭐⭐⭐ لأ ⭐⭐⭐) ⭐⭐⭐ ⭐ — ⭐⭐⭐ مش ⭐⭐⭐ كتابة ⭐⭐⭐
                continue
            if RE_TMP_SUFFIX.search(line) or RE_TMP_CONCAT.search(line):
                bad.append(("اسم مؤقت ثابت", os.path.relpath(p, ROOT), i,
                            line.strip()[:110]))
            if "probe" in line.lower() and re.search(r"write_text|\.write\(|open\(",
                                                      line):
                # ⭐ لازم يكون فيه pid/uid ⇒ ⭐ ⇒ Check the line + the previous one ⭐
                ctx = "".join(lines[max(0, i - 3):i + 1])
                if not RE_PID.search(ctx):
                    bad.append(("فحص تشخيصي باسم ثابت", os.path.relpath(p, ROOT),
                                i, line.strip()[:110]))

    # ── ② الواجهة: كتابة باسم ثابت ⭐ ────────────────────────────────────
    fe = fe_root()
    for p in js_files():
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if RE_EXISTS_CHECK.search(line):
                continue
            if RE_JS_FIXED_TMP.search(line) or RE_JS_FIXED_TMP_CONCAT.search(line):
                bad.append(("اسم مؤقت ثابت (JS)", os.path.relpath(p, fe), i,
                            line.strip()[:110]))

    # ── ③ فحص وقت التشغيل ⭐: الأسماء فريدة فعلاً ⭐ ─────────────────────
    try:
        sys.path.insert(0, ROOT)
        import safe_write
        from pathlib import Path
        a = safe_write.tmp_path(Path("/tmp/x.json"))
        b = safe_write.tmp_path(Path("/tmp/x.json"))
        if str(a) == str(b):
            bad.append(("اسم مؤقت مش فريد وقت التشغيل", "safe_write.py", 0, str(a)))
    except Exception as e:
        bad.append(("safe_write مش متاح", "safe_write.py", 0,
                    "%s: %s" % (type(e).__name__, str(e)[:80])))

    print("═" * 72)
    print("🔒 R32 · e · حارس الكتابة الذرّية (اسم مؤقت فريد ⭐ + فحص تشخيصي فريد ⭐)")
    print("═" * 72)
    print("📁 جذر الواجهة ⭐: %s" % (fe or "(مش موجود ⭐ — سطور JS ما اتفحصتش ⭐)"))
    if bad:
        print("⛔ رُصد %d مخالفة ⭐" % len(bad))
        for why, rel, ln, txt in bad[:40]:
            print("   · %s ⭐ %s:%d ⭐ %s" % (why, rel, ln, txt))
        return 1
    print("✅ مافيش اسم مؤقت ثابت ⭐ ولا فحص تشخيصي باسم ثابت ⭐")
    print("✅ الأسماء وقت التشغيل فريدة ⭐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
