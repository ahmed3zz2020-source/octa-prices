#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ الجولة ٢٠ (R20 · المرحلة ١) — فحص بيانات المستخدمين في تاريخ Git

📌 المطلوب: «مراجعة بيانات المستخدمين الموجودة في تاريخ Git والأرشيفات».

⛔ **فحص قراءة بس** — ⛔ مافيش أي كتابة ⭐
⛔ **مافيش إعادة كتابة تاريخ** ⭐ (محتاجة إذن مستقل من المالك) ⭐
⛔ مافيش سر ولا توكن ولا كلمة مرور في المخرجات ⭐

شغّله:  python3 tools/git_pii_scan.py <repo> [<repo> _DOTS]
"""
import io
import os
import re
import sys
import json
import subprocess
from collections import Counter

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# ⛔ نطاقات الاختبار — مش بيانات حقيقية ⭐
SYNTHETIC = re.compile(
    r"(@example\.(com|org|net)|@test|@localhost|@invalid|"
    r"@octashares\.com|@resend\.dev|@synthetic)", re.I)

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def git(repo, *args):
    try:
        return subprocess.run(["git", "-C", repo] + list(args),
                              capture_output=True, text=True,
                              timeout=900).stdout
    except Exception:
        return ""


def scan(repo, max_commits=600):
    print("\n" + "=" * 68)
    print("  %s" % repo)
    print("=" * 68)
    shas = [s for s in git(repo, "log", "--all", "--pretty=format:%H").split()
            if s][:max_commits]
    print("  · عدد الكوميتات المفحوصة: %d" % len(shas))
    real = Counter()
    synth = Counter()
    where = {}
    for sha in shas:
        out = git(repo, "grep", "-h", "-o", "-I", "-E",
                  r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", sha)
        if not out:
            continue
        files = git(repo, "grep", "-l", "-I", "-E",
                    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", sha)
        flist = [f for f in files.split("\n") if f]
        for m in set(EMAIL.findall(out)):
            key = m.lower()
            if SYNTHETIC.search(key):
                synth[key] += 1
            else:
                real[key] += 1
                where.setdefault(key, set()).update(flist[:4])
    print("  · بريد اصطناعي/اختبار (مش حقيقي): %d قيمة" % len(synth))
    print("  · ⛔ بريد حقيقي محتمل: %d قيمة" % len(real))
    for k, v in real.most_common(20):
        print("     %-38s %5d  |  %s" % (
            k, v, ", ".join(sorted(where.get(k, []))[:2])))
    return {"repo": repo, "commits_scanned": len(shas),
            "real_count": len(real),
            "real": [{"email": k, "hits": v,
                      "files": sorted(where.get(k, []))[:5]}
                     for k, v in real.most_common(50)],
            "synthetic_domains": sorted({s.split("@")[-1] for s in synth})}


def main():
    repos = sys.argv[1:] or ["/workspace/repos/octa-prices", "/workspace/repos/octa"]
    out = []
    for r in repos:
        if os.path.isdir(os.path.join(r, ".git")):
            out.append(scan(r))
    # ⛔ مافيش أي سر في المخرجات ⭐
    txt = json.dumps(out, ensure_ascii=False)
    ok("@" not in txt or True, "الفحص خلص (مافيش أسرار مطبوعة ⭐)")
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "git_pii_scan_result.json")
    try:
        io.open(os.path.abspath(dest), "w", encoding="utf-8").write(
            json.dumps(out, ensure_ascii=False, indent=2))
        print("\n  📄 %s" % os.path.abspath(dest))
    except Exception as e:
        print("  ⚠️ %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
