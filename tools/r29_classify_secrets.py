#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R29 · تصنيف نتائج المسح الأمني ⭐ — كل نتيجة لها سبب بالاسم ⭐.

⭐ القاعدة ⭐: النتيجة «تسريب حقيقي» ⇦ **قيمة سرّية حرفية** ⭐ في الكود ⭐.
   ⛔ مش تسريب ⭐: اسم متغيّر ⭐ · مرجع متغيّر بيئة ⭐ · placeholder ⭐ · تعريف regex ⭐
   · فحص منطقي ⭐ · قيمة داخل ملف اختبار ⭐ · قيمة مولّدة وقت التشغيل ⭐.

⭐⭐⭐ (R29) ⭐⭐⭐ الأداة **داخل المستودع** ⭐ ⭐ ⇒ ⭐ ⭐ تُعاد بنفس البصمة ⭐ ⭐ في كل جولة ⭐ ⭐ ⭐.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO_ROOTS = ["/workspace/.wt_r28_be", "/workspace/.wt_r28_fe", "/workspace/.wt_r28_ci"]
EVIDENCE_ROOTS = ["/workspace/output/r29"]
ZIP_ROOTS = ["/workspace/output/OCTA-ROUND29-DELIVERY",
             "/workspace/output/packs_scan", "/workspace/output"]

ENV_REF = [
    re.compile(r"os\.environ"), re.compile(r"os\.getenv"), re.compile(r"process\.env"),
    re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*"), re.compile(r"env\.[A-Z][A-Z0-9_]{2,}"),
    re.compile(r"getenv|environ"),
]
PLACEHOLDER = re.compile(
    r"(?i)example|your[-_ ]|your\b|xxxx|changeme|change-me|placeholder|dummy|fake|"
    r"redacted|\*\*\*|<[a-z_-]+>|TODO|FIXME|test-only|sample|demo|"
    r"\u0636\u0639\u064a|\u062a\u0648\u0643\u0646|\u062e\u0635\u0627\u0635\u064a|"
    r"\u0627\u062e\u062a\u0628\u0627\u0631|\u0627\u0644\u062a\u0648\u0643\u0646|\u0645\u062e\u062c\u0648\u0644")
REGEX_DEF = re.compile(r"re\.compile|re\.(match|search|findall|finditer)|\bRX\s*=|\bRX_|regex")
BOOLEAN = re.compile(r"!!|\bhas_\w+\s*[:=]|= *False\b|= *True\b|\bNone\b|\bbool\(|len\(|str\(|int\(|json\.loads|urllib|request\(|getenv")
TESTFILE = re.compile(r"(^|/)(tests?|__tests__|fixtures?|examples?|docs?)(/|$)|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]*\.py$|(^|/)[^/]*_test\.py$", re.I)


# ⭐⭐⭐ (R32) ⭐⭐⭐ بصمات المستودعات وقت المسح ⭐ ⭐ (من تقرير المسح ⭐) ⭐
PINNED_REPOS = []


def load_pinned(scan: dict) -> None:
    """يقرأ `scanned_repos` ⭐ من تقرير المسح ⭐ ⇒ ⭐ (المستودع ⭐، الـsha ⭐) ⭐."""
    global PINNED_REPOS
    PINNED_REPOS = []
    for item in (scan.get("summary") or {}).get("scanned_repos") or []:
        root = str(item.get("path") or "")
        sha = str(item.get("sha") or "")
        if root and sha:
            PINNED_REPOS.append((root, sha))


def read_git_line(sha: str, line_no):
    """⭐⭐⭐ (R32) ⭐⭐⭐ سطر من **كائن git** ⭐ ⭐ (مش من الشجرة الحالية ⭐) ⭐.
    📌 السبب ⭐: ⛔ مواضع «git-history» ⭐ ⭐ كانت بتتقرا ⭐ ⭐ من **الشجرة الحالية** ⭐ ⭐
       ⭐ ⭐ ⇒ ⛔ السطر ⭐ ⭐ مختلف ⭐ ⭐ ⇒ ⛔ التصنيف ⭐ ⭐ على **نص تاني** ⭐ ⭐
       ⭐ ⭐ ⇒ ⛔ تسرّب مخفي ⭐ ⭐ أو ⛔ إنذار كاذب ⭐ ⭐.
    ✅ دلوقتي ⭐: ⭐ `git cat-file blob` ⭐ ⭐ على نفس الـsha ⭐ ⭐ ⇒ ⭐ نفس السطر ⭐ ⭐."""
    for root in REPO_ROOTS:
        try:
            proc = subprocess.run(["git", "-C", root, "cat-file", "blob", sha],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=120)
            if proc.returncode == 0 and proc.stdout:
                lines = proc.stdout.decode("utf-8", "replace").split("\n")
                if isinstance(line_no, int) and 0 < line_no <= len(lines):
                    return window(lines, line_no)
        except Exception:  # noqa: BLE001
            continue
    return ""


def read_line(loc: dict) -> str:
    where = loc.get("location", "")
    line_no = loc.get("line")
    scope = loc.get("scope")
    path = None
    # ⭐⭐⭐ (R32) ⭐⭐⭐ السطر من كائن الـgit ⭐ ⭐ (لو ده git-history ⭐) ⭐
    if scope == "git-history" and re.fullmatch(r"[0-9a-f]{40}", str(where or "")):
        got = read_git_line(str(where), line_no)
        if got:
            return got
    if scope == "zip" and "::" in where:
        zip_name, inner = where.split("::", 1)
        cand = os.path.join(ZIP_ROOTS[0], zip_name)
        if os.path.isfile(cand):
            try:
                import zipfile
                with zipfile.ZipFile(cand) as zf:
                    data = zf.read(inner).decode("utf-8", "replace")
                lines = data.split("\n")
                if isinstance(line_no, int) and 0 < line_no <= len(lines):
                    return window(lines, line_no)
            except Exception:  # noqa: BLE001
                return ""
        return ""
    # ⭐⭐⭐ (R29) ⭐⭐⭐ مجلد الأدلة ⭐⭐⭐ ⇒ ⭐ ⭐ المسارات النسبية ⭐ ⭐ بتتحل ⭐ ⭐
    for root in EVIDENCE_ROOTS:
        cand = os.path.join(root, where)
        if os.path.isfile(cand):
            try:
                with open(cand, encoding="utf-8", errors="replace") as fh:
                    lines = fh.read().split("\n")
                if isinstance(line_no, int) and 0 < line_no <= len(lines):
                    return window(lines, line_no)
            except Exception:  # noqa: BLE001
                return ""
            return ""
    # ⭐⭐⭐ (R32) ⭐⭐⭐ الأول: ⭐ نفس **بصمة** المستودع وقت المسح ⭐ ⭐⭐
    #    ⇒ ⭐ أرقام الأسطر بتطابق ⭐ ⇒ ⭐ ⭐ التصنيف قابل لإعادة الإنتاج ⭐ ⭐
    for root, sha in PINNED_REPOS:
        if not sha:
            continue
        try:
            proc = subprocess.run(["git", "-C", root, "show", "%s:%s" % (sha, where)],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=120)
            if proc.returncode == 0 and proc.stdout:
                lines = proc.stdout.decode("utf-8", "replace").split("\n")
                if isinstance(line_no, int) and 0 < line_no <= len(lines):
                    return window(lines, line_no)
        except Exception:  # noqa: BLE001
            continue
    for root in REPO_ROOTS:
        cand = os.path.join(root, where)
        if os.path.isfile(cand):
            try:
                with open(cand, encoding="utf-8", errors="replace") as fh:
                    lines = fh.read().split("\n")
                if isinstance(line_no, int) and 0 < line_no <= len(lines):
                    return window(lines, line_no)
            except Exception:  # noqa: BLE001
                return ""
            return ""
    return ""


def window(lines, line_no):
    if not isinstance(line_no, int) or not lines:
        return ""
    lo = max(0, line_no - 4)
    hi = min(len(lines), line_no + 3)
    return "\n".join(lines[lo:hi])


def classify(line: str, where: str) -> tuple[str, str]:
    """⇦ (الحكم · السبب) ⭐ — كل سبب بالحرف ⭐."""
    if TESTFILE.search(where):
        return "false_positive", "قيمة داخل ملف اختبار"
    if REGEX_DEF.search(line):
        return "false_positive", "تعريف نمط المسح نفسه (re.compile)"
    if any(r.search(line) for r in ENV_REF):
        return "false_positive", "مرجع متغير بيئة (لا قيمة سر في الكود)"
    if re.search(r"\b[A-Z][A-Z0-9_]*(TOKEN|SECRET|PASSWORD|KEY)[A-Z0-9_]*\s*=\s*[\"'][A-Z][A-Z0-9_]{3,}[\"']", line):
        return "false_positive", "اسم متغير بيئة (لا قيمة سر)"
    if re.search(r"token_urlsafe|secrets\.(token|compare)|urandom\(", line):
        return "false_positive", "قيمة مولدة عند التشغيل (لا قيمة في الكود)"
    if re.search(r"findall|finditer|HEX40_ANY|SECRET_PAT|\.search\(", line):
        return "false_positive", "أداة مسح أمانة (لا قيمة سر)"
    if PLACEHOLDER.search(line):
        return "false_positive", "قيمة مثال (مكان خارج، لا قيمة في الكود)"
    if BOOLEAN.search(line):
        return "false_positive", "فحص منطقي (معمول متغير، لا قيمة سر)"
    # ⭐⭐⭐ (R29) ⭐⭐⭐ سطر **بيستدعي ملف بيئة** ⭐⭐⭐ ⇒ ⭐ ⭐ مش قيمة سر ⭐ ⭐
    # 📌 السبب ⭐: ⛔ السطر ده ⭐ ⭐ بيقرأ القيم من ملف محلي ⭐ ⭐ برّه الأدلة ⭐ ⭐
    #    ⭐ ⭐ ⇒ ⛔ مافيش قيمة حرفية ⭐ ⭐ في السطر ⭐ ⭐ ⇒ ⛔ ليس تسرّب ⭐ ⭐ ⭐
    if re.search(r"^\s*\.?\s+[\w./-]*\b(iso_env|\.env|env\.sh|secrets\.sh)\b", line):
        return "false_positive", "سطر استدعاء ملف بيئة (القيم في ملف محلي ⭐ برّه الأدلة ⭐)"
    if re.search(r"\bsource\s+[^\s]+\.sh\b|\.\s+[^\s]+_env\.sh", line):
        return "false_positive", "سطر استدعاء ملف بيئة (القيم في ملف محلي ⭐ برّه الأدلة ⭐)"
    return "real_leak", "قيمة حرفية في كود شجرة المساح"


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/workspace/output/r29/secrets-scan-final.json"
    with open(path, encoding="utf-8") as fh:
        scan = json.load(fh)
    # ⭐⭐⭐ (R32) ⭐⭐⭐ تثبيت بصمات المستودعات ⭐ ⭐ (من نفس التقرير ⭐) ⭐
    load_pinned(scan)
    real, reasons = [], {}
    scanned_locs = 0
    for s in scan.get("secrets", []):
        # ⭐⭐⭐ (R32) ⭐⭐⭐ فجوة التصنيف ⭐⭐⭐
        # 📌 قبل ⭐: ⛔ الـ`break` ⭐ ⭐ ⭐ كان بيوقف عند **أول موضع** ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⭐ ⇒ ⛔ لو نفس السر اتكرّر ⭐ ⭐ ⭐ (بصمة واحدة ⭐ ⭐ ⭐) ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⭐ في **ملف اختبار** ⭐ ⭐ ⭐ (⇦ حكمه ب_FALSE ⭐ ⭐ ⭐) ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⭐ وفي **كود الإنتاج** ⭐ ⭐ ⭐ ⇒ ⛔ المكان الثاني ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⭐ ما اتصنّفش ⭐ ⭐ ⭐ ⇒ ⛔ **تسرّب حقيقي مخفي** ⭐ ⭐ ⭐.
        # ✅ دلوقني ⭐: ⭐ **كل** المواضع بتتصنّف ⭐ ⭐ ⭐ ⇒ ⭐ ⭐ ⭐ السر تسرّب ⭐ ⭐ ⭐
        #    ⭐ ⭐ ⭐ لو **أي** موضع قال تسرّب ⭐ ⭐ ⭐ ⇒ ⭐ ⭐ ⭐ مفيش إخفاء ⭐ ⭐ ⭐.
        for loc in s.get("locations", []):
            scanned_locs += 1
            where = loc.get("location", "")
            line = read_line(loc)
            verdict, why = classify(line, where)
            reasons[why] = reasons.get(why, 0) + 1
            if verdict == "real_leak":
                real.append({"fingerprint": s.get("fingerprint"), "pattern": s.get("pattern"),
                             "location": where, "line": loc.get("line"),
                             "scope": loc.get("scope"), "source": line.strip()[:160]})
    out = {"ok": not real and not scan.get("summary", {}).get("errors"),
           "total_distinct": len(scan.get("secrets", [])),
           "locations_scanned": scanned_locs,
           "real_leaks": len(real),
           "real_leak_list": real,
           "reasons": reasons,
           "summary": scan.get("summary", {})}
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/workspace/output/r29/secrets-classification.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("distinct=%d  real_leaks=%d  ok=%s" % (out["total_distinct"], out["real_leaks"], out["ok"]))
    for k, v in out["reasons"].items():
        print("   · %-46s %d" % (k, v))
    for r in real[:10]:
        print("   ⛔", r["location"], r["line"], "|", r["source"][:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
