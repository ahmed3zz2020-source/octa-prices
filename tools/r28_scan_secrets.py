#!/usr/bin/env python3
"""R28 · ماسح الأسرار الشامل (كل الفروع + كامل التاريخ + الحزم + الأدلة).

الهدف: كشف أي سر (توكن، كلمة مرور، مفتاح) داخل:
  1. كل كائنات git في مستودع (كل الفروع + كل الـcommits + كل الـblobs).
  2. شجرة العمل (بما فيها الملفات غير المتتبَّعة).
  3. ملفات ZIP (الحزم) — بتفكيكها في الذاكرة.
  4. مجلدات الأدلة.

قاعدة الأمان: الماسح **لا يطبع القيمة** أبداً — بيطبع بصمة (sha256 بحد 12 حرف)
+ نوع النمط + رقم السطر. عشان التقرير يقدر يتحط في مستودع عام من غير تسريب.

الاستخدام:
  python3 tools/r28_scan_secrets.py --repo . --repo ../octa --out /tmp/secrets.json
  python3 tools/r28_scan_secrets.py --repo . --zip ../out/*.zip --out /tmp/secrets.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field, asdict
from typing import Iterable

# ── أنماط الأسرار ───────────────────────────────────────────────────────
# كل نمط: (الاسم, regex, درجة الخطورة)
PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("telegram_bot_token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,45}\b"), "critical"),
    ("github_pat_classic", re.compile(r"\bghp_[A-Za-z0-9]{30,45}\b"), "critical"),
    ("github_pat_fine", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,90}\b"), "critical"),
    ("github_oauth", re.compile(r"\bgho_[A-Za-z0-9]{30,45}\b"), "critical"),
    ("github_app", re.compile(r"\bghu_[A-Za-z0-9]{30,45}\b"), "critical"),
    ("github_refresh", re.compile(r"\bghr_[A-Za-z0-9]{30,45}\b"), "critical"),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "critical"),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,90}\b"), "critical"),
    ("stripe_secret", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,40}\b"), "critical"),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "critical"),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,80}\b"), "critical"),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,90}\b"), "critical"),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----"), "critical"),
    ("cloudflare_global_key", re.compile(r"\b[0-9a-f]{37}\b"), "high"),
    ("jwt_token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "high"),
    # تعيينات صريحة: الاسم = قيمة طويلة
    ("assigned_secret", re.compile(
        r"(?im)^\s*(?:export\s+)?(?:[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|APIKEY|API_KEY|APP_PASSWORD|APP_SECRET|PRIVATE_KEY)[A-Z0-9_]*)\s*[:=]\s*[\"']?([^\s\"'#,;]{8,200})[\"']?"
    ), "high"),
    ("bearer_literal", re.compile(r"(?i)\bauthorization\s*[:=]\s*[\"']?\s*(bearer\s+[A-Za-z0-9._-]{16,120})"), "high"),
]

# قيم معروفة أنها ليست أسراراً (تُستثنى بالاسم لا بالقيمة)
FALSE_POSITIVE_HINTS = (
    "example", "your-", "your_", "xxxx", "changeme", "change-me", "placeholder",
    "dummy", "fake-token", "redacted", "***", "<token>", "<password>", "TODO",
    "abcdefghijklmnop", "0123456789abcdef",
)

BINARY_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".woff",
    ".woff2", ".ttf", ".eot", ".mp4", ".webm", ".mp3", ".wav", ".so", ".dylib", ".dll",
    ".class", ".jar", ".pyc", ".wasm", ".sqlite", ".db",
)

MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_FINDINGS_PER_FILE = 40


@dataclass
class Finding:
    scope: str
    location: str
    pattern: str
    severity: str
    line: int
    fingerprint: str
    length: int
    hint: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    scanned_objects: int = 0
    scanned_files: int = 0
    scanned_zip_members: int = 0
    errors: list[str] = field(default_factory=list)
    # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ ⛔ حاجب ⭐⭐⭐
    # 📌 أي خطأ في قراءة عضو ⇒ ⛔ النتيجة **ما تُعتمدش** ⭐ (مش بس خطأ مطبوع ⭐).
    blocking: list[str] = field(default_factory=list)

    def block(self, msg: str) -> None:
        """⇦ خطأ يمنع اعتماد المسح ⭐ (لازم يتعالج ⭐)."""
        self.blocking.append(msg)
        self.errors.append(msg)

    def add(self, f: Finding) -> None:
        self.findings.append(f)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:12]


def is_probably_binary(data: bytes) -> bool:
    if b"\x00" in data[:4096]:
        return True
    try:
        data[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    if any(h in low for h in FALSE_POSITIVE_HINTS):
        return True
    # قيم قصيرة/متكررة مثل "test", "secret" المكتوبة مكشوفة
    if len(value) < 10:
        return True
    if len(set(value)) <= 3:
        return True
    return False


def scan_text(text: str, scope: str, location: str, report: Report) -> None:
    hits = 0
    for name, rx, severity in PATTERNS:
        for m in rx.finditer(text):
            if hits >= MAX_FINDINGS_PER_FILE:
                return
            raw = m.group(0)
            value = m.group(1) if (m.lastindex and name in ("assigned_secret", "bearer_literal")) else raw
            value = value.strip().strip('"').strip("'")
            if not value or looks_like_placeholder(value):
                continue
            line = text.count("\n", 0, m.start()) + 1
            report.add(Finding(
                scope=scope,
                location=location,
                pattern=name,
                severity=severity,
                line=line,
                fingerprint=fingerprint(value),
                length=len(value),
                hint=_hint(name),
            ))
            hits += 1


def _hint(name: str) -> str:
    """لمحة آمنة: اسم الخدمة فقط (بدون أي جزء من القيمة)."""
    prefixes = {
        "telegram_bot_token": "telegram",
        "github_pat_classic": "github",
        "github_pat_fine": "github",
        "github_oauth": "github",
        "github_app": "github",
        "github_refresh": "github",
        "aws_access_key": "aws",
        "slack_token": "slack",
        "stripe_secret": "stripe",
        "google_api_key": "google",
        "openai_key": "openai",
        "anthropic_key": "anthropic",
    }
    return prefixes.get(name, "")


def scan_repo(repo: str, report: Report) -> None:
    """يمسح كل كائنات git (كل الفروع + التاريخ) + شجرة العمل."""
    # 1) كل الكائنات في كل المراجع
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-list", "--all", "--objects"],
            capture_output=True, text=True, timeout=600, check=True).stdout
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"rev-list failed for {repo}: {exc}")
        out = ""
    shas: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        sha = line.split(" ", 1)[0].strip()
        if sha and sha not in seen:
            seen.add(sha)
            shas.append(sha)
    report.scanned_objects += len(shas)

    if shas:
        # \u2b50\u2b50 (R28) \u2b50 \u062a\u062b\u0628\u064a\u062a \u0645\u062a\u0633\u0642\u0644 \u0627\u0644\u0623\u0645\u0648\u0627\u0631 \u2b50
        # \u26d4 `cat-file --batch` \u0628\u0645\u062f\u062e\u0648\u0644 \u064a\u0642\u0641 \u0639\u0644\u0649 \u0627\u0644\u062e\u0631\u062c\u0645\u0629 \u2b50
        # \u26d4 `git cat-file --batch-all-objects --batch` \u2b50 (}\u0628\u0627\u0644\u0643\u0627\u062a\u0628 \u0645\u0627\u0641\u064a\u0634\u0642 \u062f\u0627\u062e\u0644\u0627 \u2b50).
        proc = subprocess.Popen(
            ["git", "-C", repo, "cat-file", "--batch-all-objects",
             "--batch", "--unordered"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        assert proc.stdout is not None
        for _ in shas:
            header = proc.stdout.readline()
            if not header:
                break
            parts = header.split()
            if len(parts) < 3:
                continue
            sha, _typ, size_s = parts[0], parts[1], parts[2]
            try:
                size = int(size_s)
            except ValueError:
                continue
            body = proc.stdout.read(size)
            proc.stdout.read(1)  # newline
            if _typ != "blob" or size > MAX_FILE_BYTES:
                continue
            if is_probably_binary(body):
                continue
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                continue
            scan_text(text, "git-history", f"{sha}", report)
        try:
            proc.wait(timeout=600)
        except Exception:  # noqa: BLE001
            proc.kill()

    # 2) شجرة العمل (متتبَّع + غير متتبَّع)
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
        for name in files:
            path = os.path.join(root, name)
            if name.endswith(BINARY_SUFFIXES):
                continue
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
                with open(path, "rb") as fh:
                    body = fh.read()
            except OSError:
                continue
            if is_probably_binary(body):
                continue
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                continue
            rel = os.path.relpath(path, repo)
            report.scanned_files += 1
            scan_text(text, "worktree", rel, report)


def archive_fingerprint(path: str) -> dict:
    """بصمة الأرشيف ⭐ (SHA256 + الحجم ⭐) — بدون قراءة أي سر ⭐."""
    h = hashlib.sha256()
    size = 0
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
                size += len(chunk)
    except Exception as exc:  # noqa: BLE001
        return {"path": path, "error": str(exc)[:120]}
    return {"path": path, "bytes": size, "sha256": h.hexdigest()}


def resolve_zip(path: str, siblings: list[str]) -> str:
    """لو المسار مش موجود ⭐ ⇒ ابحث عن نفس الاسم في مجلدات الحزم الأخرى ⭐."""
    if os.path.exists(path):
        return path
    base = os.path.basename(path)
    for other in siblings:
        cand = os.path.join(os.path.dirname(other), base)
        if os.path.exists(cand):
            return cand
    return path


def scan_zip(path: str, report: Report, siblings=None) -> None:
    path = resolve_zip(path, list(siblings or []))
    try:
        zf = zipfile.ZipFile(path)
    except Exception as exc:  # noqa: BLE001
        # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ ⛔ الأرشيف اللي ما اتفتحش ⭐ ⇒ ⛔ حاجب ⭐
        report.block(
            "zip open failed for %s: %s ⭐ (المسار غير موجود ⭐ — راجع المسار ⭐)"
            % (path, exc))
        return
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.filename.lower().endswith(BINARY_SUFFIXES):
                continue
            if info.file_size > MAX_FILE_BYTES:
                continue
            report.scanned_zip_members += 1
            try:
                body = zf.read(info)
            except Exception as exc:  # noqa: BLE001
                # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ ⛔ خطأ قراءة العضو ⭐
                # 📌 قبل ⭐: `continue` ⭐ ⇒ ⛔ العضو بيتسكت ⭐ ⇒ ⛔ المسح
                #    بيقول «نظيف» ⭐ مع إن جزء **ما اتقراش** ⭐ ⇒ ⛔ كذب ⭐.
                # ✅ دلوقتي ⭐: ⛔ الخطأ **ظاهر في النتيجة** ⭐
                #    ⭐ و ⛔ **يمنع اعتماد المسح** ⭐ لحد ما يتعالج ⭐.
                report.block("zip member read failed: %s :: %s (%s)"
                             % (os.path.basename(path), info.filename, exc))
                continue
            if is_probably_binary(body):
                continue
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                continue
            scan_text(text, "zip", f"{os.path.basename(path)}::{info.filename}", report)


def scan_dir(path: str, report: Report) -> None:
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for name in files:
            fpath = os.path.join(root, name)
            if name.endswith(BINARY_SUFFIXES):
                continue
            try:
                if os.path.getsize(fpath) > MAX_FILE_BYTES:
                    continue
                with open(fpath, "rb") as fh:
                    body = fh.read()
            except OSError as exc:
                # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ ⛔ ملف الدليل اللي ما اتقراش ⭐ ⇒ ⛔ حاجب ⭐
                report.block("evidence file read failed: %s (%s)" % (fpath, exc))
                continue
            if is_probably_binary(body):
                continue
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                continue
            report.scanned_files += 1
            scan_text(text, "evidence", os.path.relpath(fpath, path), report)


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R28 · ماسح الأسرار الشامل")
    ap.add_argument("--repo", action="append", default=[], help="مسار مستودع (يتكرر)")
    ap.add_argument("--zip", action="append", default=[], help="ملف حزمة (يتكرر)")
    ap.add_argument("--dir", action="append", default=[], help="مجلد أدلة (يتكرر)")
    ap.add_argument("--out", default="", help="مسار ملف JSON للنتائج")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    report = Report()
    for repo in args.repo:
        scan_repo(repo, report)
    archives = []
    for zpath in args.zip:
        resolved = resolve_zip(zpath, list(args.zip))
        info = archive_fingerprint(resolved)
        info["requested_path"] = zpath
        info["resolved"] = resolved != zpath
        archives.append(info)
        scan_zip(zpath, report, siblings=list(args.zip))
    for dpath in args.dir:
        scan_dir(dpath, report)

    # تجميع: نفس البصمة = نفس السر
    by_fp: dict[str, list[Finding]] = {}
    for f in report.findings:
        by_fp.setdefault(f.fingerprint, []).append(f)

    payload = {
        # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ ⛔ الاعتماد ⭐⭐⭐
        # 📌 `ok` ⭐ = مفيش أخطاء حاجبة ⭐ ⇒ ⛔ المسح ما يُعتمدش ⭐
        #    لو عضو في أرشيف أو ملف في الأدلة ما اتقراش ⭐.
        "ok": not report.blocking,
        "blocking": report.blocking,
        "summary": {
            "distinct_secrets": len(by_fp),
            "total_findings": len(report.findings),
            "scanned_git_objects": report.scanned_objects,
            "scanned_worktree_files": report.scanned_files,
            "scanned_zip_members": report.scanned_zip_members,
            "errors": report.errors,
            "blocking_count": len(report.blocking),
        },
        "archives": archives,
        "secrets": [
            {
                "fingerprint": fp,
                "pattern": items[0].pattern,
                "severity": items[0].severity,
                "length": items[0].length,
                "occurrences": len(items),
                "locations": [
                    {"scope": it.scope, "location": it.location, "line": it.line}
                    for it in items[:200]
                ],
            }
            for fp, items in sorted(by_fp.items(), key=lambda kv: -len(kv[1]))
        ],
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        s = payload["summary"]
        print(f"[R28-SEC] كائنات git: {s['scanned_git_objects']} · ملفات: {s['scanned_worktree_files']} · "
              f"أعضاء حزم: {s['scanned_zip_members']}")
        print(f"[R28-SEC] أسرار متمايزة: {s['distinct_secrets']} · إجمالي: {s['total_findings']}")
        if report.blocking:
            print(f"[R28-SEC] ⛔⛔⛔ {len(report.blocking)} حاجب ⭐ — المسح **ما يُعتمدش** ⭐:")
            for b in report.blocking[:20]:
                print("     ⛔ %s" % b[:160])
        for item in payload["secrets"][:40]:
            loc = item["locations"][0]
            print(f"  - {item['severity']:8s} {item['pattern']:24s} fp={item['fingerprint']} "
                  f"×{item['occurrences']}  أول موضع: {loc['scope']}:{loc['location']}:{loc['line']}")
    # ⭐⭐⭐ (R29 · FINDING-15) ⭐⭐⭐ كود خروج غير صفري ⭐ لو فيه حاجب ⭐
    return 2 if report.blocking else 0


if __name__ == "__main__":
    sys.exit(main())
