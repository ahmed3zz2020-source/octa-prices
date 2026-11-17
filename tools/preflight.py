#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🩺 فحص الجاهزية قبل النشر — الجولة ١٨ · المرحلة ٧ (تشغيل)
============================================================
📌 الغرض: **قرار واحد** قبل أي نشر — «ينفع أنشر ولا لأ؟».
   مش بدل الفحوص المتفرقة ⇒ ١٠ فحوص في مكان واحد برمز خروج واحد.

⛔ القواعد:
   · مافيش اتصال بالإنتاج (مفيش fetch خارجي).
   · مافيش كتابة على بيانات الإنتاج (قراءة فقط + تقرير).
   · مافيش سر في التقرير — بس «مضبوط / مش مضبوط».

📌 الاستخدام:
   python3 tools/preflight.py                       # فحص الكود (بلا خادم)
   python3 tools/preflight.py --base-url http://127.0.0.1:8099   # + فحص حيّ
   python3 tools/preflight.py --json /tmp/preflight.json

📌 رمز الخروج:
   0 = كله تمام (فيها تحذيرات بس)
   1 = فيه فحص فاشل ⛔
   2 = خطأ في الأداة نفسها
"""
import argparse
import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

OK, WARN, FAIL = "PASS", "WARN", "FAIL"

# ⛔ قاعدة الـCI: مافيش «ثلاث نقاط» برّه التعليقات ⇒ نبنيها بدل ما نكتبها حرفي
_DOTS = "." * 3


class Check:
    def __init__(self, cid, title):
        self.id = cid
        self.title = title
        self.state = OK
        self.detail = ""
        self.evidence = []

    def fail(self, detail, *evidence):
        self.state = FAIL
        self.detail = detail
        self.evidence = list(evidence)

    def warn(self, detail, *evidence):
        if self.state == OK:
            self.state = WARN
        self.detail = (self.detail + " · " + detail).strip(" ·")
        self.evidence += list(evidence)

    def ok(self, detail, *evidence):
        self.detail = detail
        self.evidence = list(evidence)

    def as_dict(self):
        return {"id": self.id, "title": self.title, "state": self.state,
                "detail": self.detail, "evidence": self.evidence}


# ══════════════════════════════════════════════════════════════
#  ① السر
# ══════════════════════════════════════════════════════════════
def c1_secret():
    c = Check("secret", "سر التوقيع مضبوط (fail-closed)")
    secret = str(os.environ.get("OCTAD_TOKEN_SECRET")
                 or os.environ.get("SECRET_KEY") or "").strip()
    dev = str(os.environ.get("OCTAD_DEV", "") or "").strip().lower() in {
        "1", "true", "yes", "on", "dev", "local"}
    if secret:
        c.ok("مضبوط (طول %d حرف · القيمة مش متظهرة)" % len(secret))
    elif dev:
        c.warn("وضع تطوير (OCTAD_DEV=1) — سر مؤقت لكل تشغيل")
    else:
        c.fail("⛔ OCTAD_TOKEN_SECRET مش مضبوط — التطبيق هيرفض يشتغل")
    return c


# ══════════════════════════════════════════════════════════════
#  ② مافيش سر مكتوب في الكود
# ══════════════════════════════════════════════════════════════
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9]{20,}|PRX-[A-Za-z0-9_-]{20,}|ADM-[A-Za-z0-9_-]{20,}"
    r"|STG-[A-Za-z0-9_-]{20,}"
    r"|OCTAD_TOKEN_SECRET\s*=\s*[\"'](?!TEST-ONLY\b)[^\"']{8,})")


def c2_no_hardcoded_secret():
    c = Check("hardcoded-secret", "مافيش سر مكتوب في الكود")
    hits = []
    for p in sorted(REPO.rglob("*.py")):
        if ".git" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in SECRET_PAT.finditer(t):
            hits.append("%s :: %s" % (p.relative_to(REPO), m.group(0)[:20]))
    if hits:
        c.fail("⛔ %d سر في الكود" % len(hits), *hits[:8])
    else:
        c.ok("صفر — كل الأسرار من متغيرات البيئة")
    return c


# ══════════════════════════════════════════════════════════════
#  ③ سلامة الصياغة
# ══════════════════════════════════════════════════════════════
def c3_syntax():
    c = Check("syntax", "كل ملفات Python بتعمل parse")
    bad = []
    n = 0
    for p in sorted(REPO.rglob("*.py")):
        if ".git" in p.parts or "tools/staging" in str(p):
            continue
        n += 1
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="ignore"), filename=str(p))
        except SyntaxError as e:
            bad.append("%s:%s %s" % (p.relative_to(REPO), e.lineno, e.msg))
    if bad:
        c.fail("⛔ %d ملف فيه خطأ صياغة" % len(bad), *bad[:8])
    else:
        c.ok("%d ملف سليم" % n)
    return c


# ══════════════════════════════════════════════════════════════
#  ④ حارس الـCI (نقاط التTTT برّه كومنت)
# ══════════════════════════════════════════════════════════════
def c4_ci_guard():
    """⛔ نفس شرط الـCI بالظبط (grep على update_prices.py)
    + فحص دقيق (tokenize) على كل ملفات الـrepo ⇒ مافيش إنذار كاذب."""
    c = Check("ci-guard", "حارس الـCI: مافيش «ثلاث نقاط» برّه كومنت")
    # ① شرط الـCI الحقيقي — نفس الأمر اللي بيرفض الـpush
    ci_bad = []
    main_py = REPO / "update_prices.py"
    if main_py.exists():
        for i, ln in enumerate(main_py.read_text(encoding="utf-8",
                                                 errors="ignore").splitlines(), 1):
            if _DOTS in ln and not ln.strip().startswith("#"):
                ci_bad.append("update_prices.py:%d" % i)
    # ② فحص دقيق على كل الملفات (tokenize ⇒ الكومنت والنصوص مش محسوبين)
    import io
    import tokenize
    tok_bad = []
    for p in sorted(REPO.rglob("*.py")):
        if ".git" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.OP and tok.string == _DOTS:
                    tok_bad.append("%s:%d" % (p.relative_to(REPO), tok.start[0]))
                    break
        except Exception:
            continue
    if ci_bad:
        c.fail("⛔ شرط الـCI هيفشل ⇒ الـpush هيت رفض", *ci_bad[:8])
    elif tok_bad:
        c.warn("«ثلاث نقاط» كـoperator في %d ملف (مش في شرط الـCI)" % len(tok_bad),
               *tok_bad[:8])
    else:
        c.ok("نضيف — شرط الـCI مستوفى ومافيش ellipsis كـoperator")
    return c


# ══════════════════════════════════════════════════════════════
#  ⑤ ملف المستخدمين سليم
# ══════════════════════════════════════════════════════════════
def c5_users_store():
    c = Check("users-store", "ملف المستخدمين سليم (مش تالف)")
    d = Path(os.environ.get("OCTA_DATA_DIR", "") or (REPO / "data"))
    uf = d / "users.json"
    if not uf.exists():
        c.ok("مافيش ملف بعد (عادي على بيئة جديدة) · %s" % uf.parent)
        return c
    try:
        data = json.loads(uf.read_text(encoding="utf-8"))
    except Exception as e:
        c.fail("⛔ users.json تالف — أي كتابة هتترفض (fail-closed): %s" % e)
        return c
    if not isinstance(data, dict):
        c.fail("⛔ users.json مش dict ⇒ _load_users هيعتبره تالف")
        return c
    c.ok("سليم · %d حساب" % len(data))
    return c


# ══════════════════════════════════════════════════════════════
#  ⑥ ملفات البيانات المرجعية
# ══════════════════════════════════════════════════════════════
def c6_data_files():
    c = Check("data-files", "ملفات البيانات المرجعية سليمة")
    d = Path(os.environ.get("OCTA_DATA_DIR", "") or (REPO / "data"))
    if not d.is_dir():
        c.fail("⛔ مجلد البيانات مش موجود: %s" % d)
        return c
    files = sorted(p for p in d.glob("*.json"))
    if not files:
        c.warn("مافيش ملفات JSON في %s" % d)
        return c
    bad = []
    for p in files:
        try:
            t = p.read_text(encoding="utf-8").strip()
            if not t:
                bad.append("%s (فاضي)" % p.name)
                continue
            json.loads(t)
        except Exception as e:
            bad.append("%s (%s)" % (p.name, str(e)[:50]))
    if bad:
        c.fail("⛔ %d ملف تالف" % len(bad), *bad[:8])
    else:
        c.ok("%d ملف سليم" % len(files))
    return c


# ══════════════════════════════════════════════════════════════
#  ⑦ ملفات النشر
# ══════════════════════════════════════════════════════════════
def c7_deploy_files():
    c = Check("deploy-files", "Procfile و requirements.txt")
    problems = []
    pf = REPO / "Procfile"
    if not pf.exists():
        problems.append("Procfile مفقود")
    elif "web:" not in pf.read_text(encoding="utf-8"):
        problems.append("Procfile مافيهوش web:")
    if not (REPO / "requirements.txt").exists():
        problems.append("requirements.txt مفقود")
    if problems:
        c.fail("⛔ " + " · ".join(problems))
    else:
        c.ok("Procfile فيه web: · requirements.txt موجود")
    return c


# ══════════════════════════════════════════════════════════════
#  ⑧ ⑨ الفحص الحيّ
# ══════════════════════════════════════════════════════════════
def _get(url, timeout=15, proxy=None):
    h = {"Accept": "application/json"}
    if proxy:
        h["X-OCTA-Proxy"] = proxy
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(20000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(20000).decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def c8_health(base, proxy):
    c = Check("api-health", "الـAPI شغّال (GET /api/health)")
    if not base:
        c.warn("مافيش --base-url ⇒ الفحص الحيّ اتخطّى")
        return c
    code, body = _get(base.rstrip("/") + "/api/health", proxy=proxy)
    if code is None:
        c.fail("⛔ مفيش رد: %s" % body[:120])
        return c
    if code != 200:
        c.fail("⛔ http %s" % code)
        return c
    try:
        j = json.loads(body)
    except Exception:
        c.fail("⛔ الرد مش JSON")
        return c
    keys = sorted(j.keys())
    c.ok("http 200 · الحقول: %s" % ", ".join(keys[:8]))
    return c


def c9_fail_closed(base, proxy):
    """⛔ الطبقتين: الشبكة (403 من غير سر الوسيط) + المصادقة (401 من غير جلسة)."""
    c = Check("api-fail-closed", "الطبقتان مقفولتان: شبكة 403 + مصادقة 401")
    if not base:
        c.warn("مافيش --base-url ⇒ الفحص الحيّ اتخطّى")
        return c
    # ① طبقة الشبكة: وصول مباشر (من غير سر الوسيط) ⇒ لازم 403
    code_a, body_a = _get(base.rstrip("/") + "/api/health", proxy=None)
    # ② طبقة المصادقة: مسار محمي + سر الوسيط صح + من غير جلسة ⇒ لازم 401
    code_b, body_b = _get(base.rstrip("/") + "/api/admin/users", proxy=proxy)
    ok = True
    if code_a == 200:
        c.fail("⛔ الوصول المباشر مكشوف — /api/health رجّع 200 من غير سر الوسيط")
        ok = False
    elif code_a is None:
        c.fail("⛔ مفيش رد على الطلب المباشر: %s" % body_a[:100])
        ok = False
    elif code_a != 403:
        c.warn("الوصول المباشر رجّع %s (المتوقّع 403)" % code_a)
    if code_b == 200:
        c.fail("⛔ /api/admin/users رجّع 200 من غير جلسة!")
        ok = False
    elif code_b is None:
        c.fail("⛔ مفيش رد: %s" % body_b[:100])
        ok = False
    elif code_b != 401:
        c.warn("المسار المحمي رجّع %s (المتوقّع 401)" % code_b)
    if ok:
        c.ok("شبكة: %s (بلا سر) · مصادقة: %s (بلا جلسة) ⇒ مقفول ✅"
             % (code_a, code_b))
    return c


# ══════════════════════════════════════════════════════════════
#  ⑩ مافيش افتراضي بيشاور على الإنتاج
# ══════════════════════════════════════════════════════════════
PROD_PAT = re.compile(
    r"(api[_-]?url|API_URL|BASE_URL)\s*=\s*[\"'](https?://[^\"']+)[\"']",
    re.IGNORECASE)


def c10_no_prod_default():
    c = Check("no-prod-default", "مافيش افتراضي بيشاور على الإنتاج")
    hits = []
    for p in sorted(REPO.rglob("*.py")):
        if ".git" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in PROD_PAT.finditer(t):
            url = m.group(2)
            if "127.0.0.1" in url or "localhost" in url or "example.test" in url:
                continue
            hits.append("%s :: %s" % (p.relative_to(REPO), url[:60]))
    if hits:
        c.fail("⛔ %d افتراضي بيشاور على عنوان خارجي" % len(hits), *hits[:8])
    else:
        c.ok("مافيش افتراضي خارجي")
    return c


# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--proxy-secret", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    # ⛔ سر الوسيط: من المتغير أو من ملف أسرار الـstaging (مش مكتوب في الكود)
    proxy = a.proxy_secret or str(os.environ.get("OCTA_PROXY_SECRET", "") or "").strip()
    if not proxy:
        try:
            sf = Path("/workspace/.staging-secrets.json")
            if sf.exists():
                proxy = str(json.loads(sf.read_text(encoding="utf-8")).get("proxy", "") or "")
        except Exception:
            proxy = ""

    checks = [
        c1_secret(), c2_no_hardcoded_secret(), c3_syntax(), c4_ci_guard(),
        c5_users_store(), c6_data_files(), c7_deploy_files(),
        c8_health(a.base_url, proxy), c9_fail_closed(a.base_url, proxy),
        c10_no_prod_default(),
    ]

    lines = ["🩺 فحص الجاهزية — OCTA (المرحلة ٧)", ""]
    n_fail = n_warn = 0
    for c in checks:
        icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "⛔"}[c.state]
        lines.append("%s %-26s %s" % (icon, c.id, c.title))
        if c.detail:
            lines.append("      %s" % c.detail)
        for e in c.evidence[:6]:
            lines.append("      · %s" % e)
        if c.state == FAIL:
            n_fail += 1
        elif c.state == WARN:
            n_warn += 1
    lines.append("")
    lines.append("═══ الخلاصة: %d فاشل · %d تحذير · %d فحص ═══"
                 % (n_fail, n_warn, len(checks)))
    out = "\n".join(lines)
    print(out)

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"checks": [c.as_dict() for c in checks],
             "failed": n_fail, "warnings": n_warn, "total": len(checks)},
            ensure_ascii=False, indent=2), encoding="utf-8")

    return 1 if n_fail else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("⛔ خطأ في الأداة: %s" % e, file=sys.stderr)
        sys.exit(2)
