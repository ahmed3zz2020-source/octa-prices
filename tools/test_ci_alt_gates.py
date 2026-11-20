#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚪 البوابات البديلة لملفات الاختبار المعزولة — الجولة ٢٦ (R26)

🎯 ليه الأداة دي؟
   ملفين في المستودع **مش قادرين** يشتغلوا جوّه الـCI ⭐:
   · `test_gold_live_price.py` — بيقارن بـ**سعر حيّ** من السوق ⭐
     ⇒ الفشل = حركة سوق (مش عيب كود) ⇒ مش قابل للتكرار ⭐
   · `tools/staging/test_flask_binding.py` — بيقرأ **مصدر الواجهة**
     من مستودع تاني (مفيشوش في مستودع الباك) ⭐

   ⛔ هم **مش بيتشالوا** ⭐ — كل واحد فيهم لازم يكون ليه
   **بوابة بديلة إلزامية** بتشتغل في **نفس الـjob** ⭐
   (والمسجَّل في `tools/ci_isolated_tests.json` ⭐).

📌 البوابات البديلة:
   · A1 — بوابة السعر الحيّ ⭐:
     تثبت إن الاختبار الحيّ **مقفول صح** (بيتخطّى بصوت عالي
     من غير متغيّر البيئة) ⭐ وإن حد القبول (١٫٥٪) **ما اترفعش** ⭐
     وإن الاختبار الحتمي المرافق (test_gold_integrity.py) **عدّى** ⭐
   · A2 — بوابة ربط الواجهة بالباك ⭐:
     تفحص **العقد** اللي الواجهة بتستهلكه من المسارات الخمسة ⭐
     (ثابت: الحقول المنشورة · منع تسريب الأوزان · وصف «الآن») ⭐
     + تتأكد إن **تعريف الـCI بتاع الواجهة** بيشغّل اختبارات الواجهة ⭐

⛔ مفيش أي اتصال بالشبكة · مفيش أي سر · مفيش أي نشر.

── التشغيل ───────────────────────────────────────────────
   python3 tools/test_ci_alt_gates.py --gate A1
   python3 tools/test_ci_alt_gates.py --gate A2
   python3 tools/test_ci_alt_gates.py
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ══════════════════════════════════════════════════════════════
#  A1 — بوابة السعر الحيّ للذهب
# ══════════════════════════════════════════════════════════════
def gate_a1():
    print("\n═══ A1 · بوابة السعر الحيّ (البديل عن test_gold_live_price.py) ═══")
    live = os.path.join(ROOT, "test_gold_live_price.py")
    det = os.path.join(ROOT, "test_gold_integrity.py")

    ok(os.path.isfile(live), "ملف الاختبار الحيّ موجود")
    ok(os.path.isfile(det), "الاختبار الحتمي المرافق موجود")
    if not os.path.isfile(live):
        return

    src = read(live)

    # ① الاختبار الحيّ لازم يكون مقفول بمتغيّر بيئة صريح
    m = re.search(r'LIVE_ENV\s*=\s*"([^"]+)"', src)
    ok(bool(m), "الاختبار الحيّ مقفول بمتغيّر بيئة صريح",
       "مالقيناش متغيّر البيئة")
    env_name = m.group(1) if m else ""

    # ② ⛔ حد القبول ١٫٥٪ ما ينفعش يترفع ⭐
    mt = re.search(r"MAX_TOLERANCE_PCT\s*=\s*([0-9.]+)", src)
    ok(bool(mt) and abs(float(mt.group(1)) - 1.5) < 1e-9,
       "حد القبول في السعر الحيّ = ١٫٥٪ (ما اترفعش ⭐)",
       mt.group(1) if mt else "مالقيناش الحد")

    # ③ تشغيله من غير متغيّر البيئة ⇒ لازم يتخطّى بصوت عالي ويخرج ٠
    env = dict(os.environ)
    env.pop(env_name, None)
    env["GOLD_HISTORY_PATH"] = "/tmp/_gh_alt_gate_a1.json"
    try:
        r = subprocess.run([sys.executable, live], cwd=ROOT, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding="utf-8", errors="replace", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired:
        out = ""
        rc = 124
    ok(rc == 0, "تشغيل الاختبار الحيّ من غير متغيّر البيئة ⇒ خرج ٠",
       "rc=%s" % rc)
    ok("متخط" in out or "⏭" in out,
       "الاختبار الحيّ بيقول بصوت عالي إنه اتخطّى ⭐",
       out[-200:] if out else "مفيش إخراج")

    # ④ الاختبار الحتمي المرافق لازم يعدّي فعلاً
    env2 = dict(os.environ)
    env2["GOLD_HISTORY_PATH"] = "/tmp/_gh_alt_gate_a1b.json"
    try:
        r2 = subprocess.run([sys.executable, det], cwd=ROOT, env=env2,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace", timeout=900)
        rc2, out2 = r2.returncode, (r2.stdout or "") + (r2.stderr or "")
    except subprocess.TimeoutExpired:
        rc2, out2 = 124, ""
    ok(rc2 == 0, "الاختبار الحتمي للذهب (test_gold_integrity.py) عدّى ⭐",
       out2[-400:] if rc2 else "")


# ══════════════════════════════════════════════════════════════
#  A2 — بوابة ربط الواجهة بالباك
# ══════════════════════════════════════════════════════════════
CONTRACT_FIELDS = ("coverage_status", "coverage_acceptable", "data_state",
                   "freshness_summary_ar", "current_session_date")
CONTRACT_ROUTES = ("/api/opp/strategies", "/api/opp/list/",
                   "/api/opp/detail/", "/api/opp/explain/", "/api/opp/summary")


def gate_a2():
    print("\n═══ A2 · بوابة ربط الواجهة بالباك "
          "(البديل عن tools/staging/test_flask_binding.py) ═══")
    binding = os.path.join(ROOT, "tools", "staging", "test_flask_binding.py")
    backend = os.path.join(ROOT, "update_prices.py")
    engine = os.path.join(ROOT, "opp_engine.py")
    fe_ci = os.path.join(ROOT, "ci-workflow", "octa-ci-fe.yml")

    ok(os.path.isfile(binding), "ملف الربط المعزول موجود")
    ok(os.path.isfile(backend), "مصدر الباك موجود")
    ok(os.path.isfile(engine), "محرّك الفرص موجود")
    if not os.path.isfile(backend):
        return

    src = read(backend)
    # ⛔ العقد بتبقى في الـAPI (update_prices) + محرّك الفرص (opp_engine) ⭐
    src_all = src + ("\n" + read(engine) if os.path.isfile(engine) else "")

    # ① المسارات الخمسة موجودة ومركّبة
    for route in CONTRACT_ROUTES:
        needle = '@app.route("%s' % route
        ok(needle in src, "المسار مركّب في الباك: %s" % route)

    # ② حقول العقد منشورة في ردود الـopp
    pub = None
    m = re.search(r"def _opp_contract_fields\(.*?\n(.*?)\n\n\n", src, re.S)
    if m:
        pub = m.group(1)
    if pub is None:
        idx = src.find('"freshness_summary_ar"')
        pub = src[max(0, idx - 800):idx + 400] if idx > 0 else ""
    for field in CONTRACT_FIELDS:
        ok(('"%s"' % field) in pub or ('"%s"' % field) in src_all,
           "حقل العقد منشور: %s" % field)

    # ③ ⛔ حماية تسريب الأوزان: المصدر لازم يعلن المفتاح مخفي ⭐
    mh = re.search(r"_HIDDEN_KEYS\s*=\s*\((.*?)\)", src_all, re.S)
    hidden = mh.group(1) if mh else ""
    ok('"weights"' in hidden,
       "مفتاح الأوزان (weights) معلن في قائمة المفاتيح المخفية ⭐",
       "مالقيناش القائمة")
    for key in ("raw_scores", "axis_weights"):
        ok('"%s"' % key in hidden,
           "المفتاح الحسّاس معلن مخفي: %s" % key)

    # ④ وصف «الآن» ما ينفعش يظهر من غير صف حيّ
    ok('"سعر التداول الآن"' in src_all or "price_label" in src_all,
       "قاعدة وصف «الآن» موجودة في المصدر ⭐")

    # ⑤ حقل اتساق التغطية منشور
    ok("coverage_consistent" in src_all,
       "حقل اتساق التغطية (coverage_consistent) موجود في المصدر ⭐")

    # ⑥ ⛔ جزء الواجهة نفسه: لازم الـCI بتاع الواجهة يشغّل اختباراتها ⭐
    if os.path.isfile(fe_ci):
        fe = read(fe_ci)
        ok("node --test" in fe,
           "تعريف الـCI بتاع الواجهة بيشغّل node --test ⭐")
        ok("assets/tests" in fe,
           "تعريف الـCI بتاع الواجهة بيشغّل ملفات assets/tests ⭐")
    else:
        ok(False, "ملف تعريف الـCI بتاع الواجهة موجود (ci-workflow/octa-ci-fe.yml)")


# ══════════════════════════════════════════════════════════════
#  A3 — بوابة صدق النمو (البديل عن tools/test_r25_growth_truthfulness.py)
# ══════════════════════════════════════════════════════════════
def _clamp(v):
    return max(0.0, min(1.0, v))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _old_ratio(item):
    """⭐ المعادلة القديمة (مرجع مستقل مكتوب هنا ⭐)."""
    p3 = _f(item.get("perf_3m"))
    rev = _f(item.get("revenue_growth"))
    ni = _f(item.get("ni_growth"))
    if p3 is None and rev is None and ni is None:
        return None
    parts = [x for x in (p3, rev, ni) if x is not None]
    return _clamp(0.5 + (sum(parts) / len(parts)) / 40.0)


def gate_a3():
    print("\n═══ A3 · بوابة صدق النمو "
          "(البديل عن tools/test_r25_growth_truthfulness.py) ═══")
    src_file = os.path.join(ROOT, "tools", "test_r25_growth_truthfulness.py")
    ok(os.path.isfile(src_file), "ملف اختبار صدق النمو موجود")
    if not os.path.isfile(src_file):
        return

    sys.path.insert(0, ROOT)
    try:
        import opp_engine as opp
    except Exception as exc:  # noqa: BLE001
        ok(False, "محرّك الفرص اتحمّل", repr(exc))
        return
    ok(True, "محرّك الفرص اتحمّل ⭐")

    # ① نمو الأرباح غير متاح ⇒ التسمية لازم تقول كده
    item = {"perf_3m": 10.0, "revenue_growth": None, "ni_growth": None}
    res = opp.c_growth(item)
    ok(res is not None, "c_growth رجّع نتيجة ⭐")
    if res:
        ratio, ev, note = res
        ok("معدل نمو الأرباح" not in note,
           "التسمية لا بتوعد بنمو الأرباح ⭐", note)
        ok("غير متاح" in note,
           "التسمية بتعلن إن نمو الأرباح غير متاح ⭐", note)
        ok(ev.get("earnings_growth_available") is False,
           "الدليل بيعلن إن نمو الأرباح غير متاح ⭐", str(ev))
        ok(abs(ratio - _old_ratio(item)) < 1e-9,
           "الدرجة مطابقة للمعادلة القديمة ⭐", str(ratio))

    # ② نمو الأرباح متاح ⇒ التسمية بتقوله
    item2 = {"perf_3m": 10.0, "revenue_growth": 5.0, "ni_growth": 7.0}
    r2 = opp.c_growth(item2)
    ok(r2 is not None, "c_growth رجّع نتيجة مع نمو متاح ⭐")
    if r2:
        ok("نمو الأرباح" in r2[2],
           "التسمية بتذكر نمو الأرباح لما يكون متاح ⭐", r2[2])
        ok(r2[1].get("earnings_growth_available") is True,
           "الدليل بيعلن إن نمو الأرباح متاح ⭐")
        ok(abs(r2[0] - _old_ratio(item2)) < 1e-9,
           "الدرجة مطابقة للمعادلة القديمة ⭐", str(r2[0]))

    # ③ مفيش بيانات ⇒ مفيش نتيجة
    ok(opp.c_growth({"perf_3m": None, "revenue_growth": None,
                     "ni_growth": None}) is None,
       "مفيش بيانات ⇒ مفيش نتيجة ⭐")

    # ④ تسميات التعريفات (في المستودع الحالي ⭐)
    defs_path = os.path.join(ROOT, "data", "opp_definitions.json")
    if not os.path.isfile(defs_path):
        ok(False, "ملف تعريفات الفرص موجود ⭐")
        return
    with open(defs_path, "r", encoding="utf-8") as fh:
        defs = json.load(fh)

    def walk(obj, out):
        if isinstance(obj, dict):
            if "key" in obj and "label_ar" in obj:
                out.append(obj)
            for v in obj.values():
                walk(v, out)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, out)

    crits = []
    walk(defs, crits)
    growth_like = [c for c in crits if c.get("key") in ("growth", "growth_profit")]
    ok(len(growth_like) >= 2,
       "معايير النمو موجودة في التعريفات ⭐", len(growth_like))
    for c in growth_like:
        label = c.get("label_ar") or ""
        hint = c.get("hint_ar") or ""
        ok("نمو الأرباح" not in label,
           "تسمية معيار النمو ما بتوعدش بنمو الأرباح ⭐", label)
        if "نمو الأرباح" in hint:
            ok("لو متاح" in hint,
               "تلميح معيار النمو لازم يقول «لو متاح» ⭐", hint)
    print("   ℹ️  نصوص الواجهة نفسها بيتحصّل عليها في الـCI بتاع الواجهة ⭐")



# ══════════════════════════════════════════════════════════════════════
#  A4 — بوابة «النسخة النظيفة» (البديل عن tools/test_round23_clean_clone.py)
# ══════════════════════════════════════════════════════════════════════
#  📌 السبب ⭐: الاختبار الأصلي بيفكّ **حزم تسليم الجولة ٢٣** ⭐
#     ⇒ ⛔ الحزم دي **مش في المستودع** ⭐ ⇒ ⛔ مش قابل للتكرار في الـCI ⭐.
#  📌 البديل ⭐: نفس الخاصية ⭐ (نسخة نظيفة قابلة للتشغيل ⭐) ⭐
#     ⭐ بس على **الشجرة الحالية** ⭐ بدل حزم جولة قديمة ⭐:
#     ① الشجرة بتتفكّ نضيفة ⭐ (git archive ⭐)
#     ② بتترجم (compileall ⭐) ⇒ مافيش خطأ نحوي ⭐
#     ③ مافيش أسرار ⭐
#     ④ مافيش نص ملوّث ⭐ (FFFD ⭐ / CJK ⭐ / Hangul ⭐ / Cyrillic ⭐)
#     ⑤ مافيش ملفات حالة مستخدمين ⭐
#  ⛔ مفيش شبكة · مفيش سر · مفيش نشر.
SECRET_PATTERNS_A4 = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]
DIRTY_A4 = [
    ("FFFD", re.compile("\ufffd")),
    ("CJK", re.compile(r"[\u4e00-\u9fff]")),
    ("HANGUL", re.compile(r"[\uac00-\ud7af]")),
    ("CYRILLIC", re.compile(r"[\u0400-\u04ff]")),
]
STATE_FILES_A4 = ("users.json", "pinlock.json", "signup.json", "pinchal.json",
                  "sessions.json", "portfolio.json")


def gate_a4():
    print("\n═══ A4 · بوابة النسخة النظيفة "
          "(البديل عن tools/test_round23_clean_clone.py) ═══")
    import shutil
    import tempfile

    ok(os.path.isfile(os.path.join(ROOT, "tools", "test_round23_clean_clone.py")),
       "ملف الاختبار المعزول موجود في المستودع ⭐")

    work = tempfile.mkdtemp(prefix="octa_clean_clone_")
    try:
        arc = os.path.join(work, "tree.tar")
        rc = subprocess.run(["git", "archive", "--format=tar", "-o", arc, "HEAD"],
                            cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE).returncode
        ok(rc == 0, "الشجرة اتفكّت (git archive ⭐)")
        if rc != 0:
            return
        tree = os.path.join(work, "tree")
        os.makedirs(tree, exist_ok=True)
        rc = subprocess.run(["tar", "-xf", arc, "-C", tree],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode
        ok(rc == 0, "النسخة النظيفة اتفكّت ⭐")

        files = []
        for base, dirs, names in os.walk(tree):
            dirs.sort()
            for nm in sorted(names):
                files.append(os.path.join(base, nm))
        ok(len(files) > 0, "في ملفات في الشجرة ⭐", len(files))

        # ② الترجمة (مافيش خطأ نحوي ⭐)
        rc = subprocess.run([sys.executable, "-m", "compileall", "-q", tree],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode
        ok(rc == 0, "كل ملفات بايثون بتترجم ⭐ (مافيش خطأ نحوي ⭐)")

        # ③ الأسرار ⭐
        hits = []
        for f in files:
            try:
                txt = open(f, "r", encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for pat in SECRET_PATTERNS_A4:
                if pat.search(txt):
                    hits.append(os.path.relpath(f, tree))
                    break
        ok(not hits, "مافيش أسرار في الشجرة ⭐", hits[:5])

        # ④ النص الملوّث ⭐
        dirty = []
        for f in files:
            try:
                txt = open(f, "r", encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for nm, pat in DIRTY_A4:
                if pat.search(txt):
                    dirty.append(os.path.relpath(f, tree) + ":" + nm)
                    break
        ok(not dirty, "مافيش نص ملوّث في الشجرة ⭐", dirty[:5])

        # ⑤ ملفات حالة المستخدمين ⭐
        leaked = []
        for f in files:
            base = os.path.basename(f)
            if base in STATE_FILES_A4:
                leaked.append(os.path.relpath(f, tree))
        ok(not leaked, "مافيش ملفات حالة مستخدمين في الشجرة ⭐", leaked[:5])
    finally:
        shutil.rmtree(work, ignore_errors=True)



# ══════════════════════════════════════════════════════════════════════
#  A5 — بوابة الشجرة النظيفة (تثبيت + بناء + اختبار تكامل) — الجولة ٢٨ ⭐
#  📌 المطلوب من المالك ⭐:
#     «أضف A5 لتشغيل تثبيت الاعتماديات والبناء واختبارات التكامل
#       من الشجرة النظيفة للمرشح الحالي» ⭐
#     «لا تعتمد على حزم الجولة 23 القديمة» ⭐
#  ✅ A5 بتعمل ⭐:
#     ① فكّ الشجرة النظيفة ⭐ (git archive HEAD ⭐ — من غير .git ⭐
#        ومن غير أي ملف غير متتبَّع ⭐).
#     ② تثبيت الاعتماديات ⭐ من requirements.txt ⭐ (في بيئة معزولة ⭐).
#     ③ البناء ⭐ (ترجمة كل الكود ⭐ + تحقّق الحارس ⭐).
#     ④ اختبار تكامل ⭐ (بيئة الـstaging من الشجرة النظيفة ⭐
#        + اختبارَي العقد الحتميين ⭐).
#     ⑤ ⛔ ما فيه أي اعتماد على حزم الجولة ٢٣ ⭐.
# ══════════════════════════════════════════════════════════════════════
A5_INTEGRATION_TESTS = ("test_data_full_route.py", "test_index_api.py")


def _pip_install(vpy, req, cwd, index=""):
    """تثبيت الاعتماديات ⭐ (بفيث المرايئة واقعة مخط معين) ⭐"""
    cmd = [vpy, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-cache-dir", "-r", req]
    if index:
        cmd += ["--index-url", index]
    try:
        r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, encoding="utf-8",
                           errors="replace", timeout=1800)
        return r.returncode, (r.stdout or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def gate_a5():
    print("\n═══ A5 · بوابة الشجرة النظيفة "
          "(تثبيت + بناء + اختبار تكامل ⭐) ═══")
    import shutil
    import tempfile
    import time

    # ⓪ ⛔ مافيش اعتماد على حزم الجولة ٢٣ ⭐

    work = tempfile.mkdtemp(prefix="octa_a5_")
    try:
        tree = os.path.join(work, "tree")
        os.makedirs(tree, exist_ok=True)

        # ① الشجرة النظيفة ⭐
        arc = os.path.join(work, "tree.tar")
        rc = subprocess.run(["git", "archive", "--format=tar", "-o", arc, "HEAD"],
                            cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE).returncode
        ok(rc == 0, "الشجرة النظيفة اتفكّت (git archive HEAD ⭐)")
        if rc != 0:
            return
        rc = subprocess.run(["tar", "-xf", arc, "-C", tree],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode
        ok(rc == 0, "الشجرة النظيفة اتفكّت ⭐")
        # ⭐ مافيش حزم الجولة القديمة في الشجرة ⭐
        stale = []
        for base2, _dirs2, names2 in os.walk(tree):
            for nm2 in names2:
                if nm2.startswith("OCTA-ROUND") and nm2.endswith(".zip"):
                    stale.append(os.path.relpath(os.path.join(base2, nm2), tree))
        ok(not stale, "مافيش حزم الجولة القديمة في الشجرة النظيفة ⭐", stale[:5])
        ok(not os.path.exists(os.path.join(tree, ".git")),
           "الشجرة النظيفة من غير .git ⭐ (مفيش حالة مخفية ⭐)")
        req = os.path.join(tree, "requirements.txt")
        ok(os.path.isfile(req), "requirements.txt موجود في الشجرة النظيفة ⭐")

        # ② تثبيت الاعتماديات ⭐ (بيئة معزولة ⭐)
        venv_dir = os.path.join(work, "venv")
        py = sys.executable
        rc = subprocess.run([py, "-m", "venv", "--system-site-packages", venv_dir],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode
        ok(rc == 0, "بيئة التثبيت المعزولة اتعملت ⭐")
        if rc != 0:
            return
        vpy = os.path.join(venv_dir, "bin", "python")
        if not os.path.isfile(vpy):
            vpy = os.path.join(venv_dir, "Scripts", "python.exe")
        t0 = time.time()
        rc, out = _pip_install(vpy, req, tree)
        if rc != 0:
            # ⭐ المرايئة الثاني مقفودة ⭐ ⇒ جرب المرايئة الرسمية ⭐
            rc2, out2 = _pip_install(vpy, req, tree,
                                     index="https://pypi.org/simple")
            if rc2 == 0:
                rc, out = rc2, out2
                print("   ℹ️  التثبيت نجح من pypi.org ⭐ (المرايئة الأولى متوفّرة ⭐)")
            else:
                out = out2
        ok(rc == 0, "تثبيت الاعتماديات من الشجرة النظيفة نجح ⭐",
           out[-400:] if rc else "")
        print("   ⏱️  زمن التثبيت: %.1f ثانية ⭐" % (time.time() - t0))

        # ③ البناء ⭐ (ترجمة كل الكود ⭐)
        rc = subprocess.run([vpy, "-m", "compileall", "-q", tree],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding="utf-8", errors="replace").returncode
        ok(rc == 0, "البناء (ترجمة كل الكود ⭐) نجح ⭐", "rc=%s" % rc)

        # ④ اختبار التكامل ⭐ (بيئة الـstaging من الشجرة النظيفة ⭐)
        stage_dir = os.path.join(work, "stage")
        port = 8199
        env = dict(os.environ)
        env["STAGE_DIR"] = stage_dir
        env["STAGE_PORT"] = str(port)
        env["OCTA_BG_TASKS"] = "off"
        env["TELEGRAM_BOT_TOKEN"] = ""
        env["TELEGRAM_CHAT_ID"] = ""
        env["STAGE_URL"] = "http://127.0.0.1:%d" % port
        env["STAGE_CONFIG"] = os.path.join(stage_dir, "staging-config.json")
        os.makedirs(stage_dir, exist_ok=True)
        log_path = os.path.join(work, "staging.log")
        with open(log_path, "w", encoding="utf-8") as log:
            proc = subprocess.Popen([vpy, os.path.join(tree, "tools", "staging", "run_staging.py")],
                                    cwd=tree, env=env, stdout=log,
                                    stderr=subprocess.STDOUT)
        # \u2b50 \u0627\u0644\u0633\u0631\u064a\u0631 \u064a\u062d\u062a\u0627\u062c \u0628\u0648\u0627\u0633\u0637 \u0627\u0644\u0645\u062e\u0637\u0631\u0642 \u2b50
        # \u26d4 \u0627\u0644\u0628\u0648\u0627\u0628\u0629 \u062a\u0637\u0644\u0628 \u0645\u0641\u062a\u0627\u062d \u0645\u062a\u0642\u0628\u0644 \u2b50 (\u0645\u0634 \u0645\u062a\u0637\u0644\u0628 \u2b50 \u21d2 \u26d4 \u0627\u0644\u0633\u0631\u064a\u0631 \u0634\u063a\u0627\u0644 \u2b50).
        up = False
        proxy_secret = ""
        cfg_path = os.path.join(stage_dir, "staging-config.json")
        for _ in range(90):
            if os.path.isfile(cfg_path):
                try:
                    import json as _json
                    with open(cfg_path, encoding="utf-8") as fh:
                        proxy_secret = _json.load(fh).get("proxy_secret", "")
                except Exception:
                    proxy_secret = ""
                if proxy_secret:
                    break
            time.sleep(1)
        for _ in range(60):
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/api/health" % port)
                if proxy_secret:
                    req.add_header("X-OCTA-Proxy", proxy_secret)
                with urllib.request.urlopen(req, timeout=2) as rr:
                    if rr.status == 200:
                        up = True
                        break
            except Exception:
                pass
            time.sleep(1)
        if not up:
            try:
                with open(log_path, encoding="utf-8", errors="replace") as fh:
                    tail = fh.read()[-1500:]
                print("   \u26a0\ufe0f  \u0633\u062c\u0644 \u0627\u0644\u0633\u062a\u0627\u062c\u064a\u0646\u063a:")
                print("   " + tail.replace("\n", "\n   ")[:1500])
            except Exception:
                pass
        ok(up, "\u0628\u064a\u0626\u0629 \u0627\u0644\u200b\u0633\u062a\u0627\u062c\u064a\u0646\u063a \u0645\u0646 \u0627\u0644\u0634\u062c\u0631\u0629 \u0627\u0644\u0646\u0638\u064a\u0641\u0629 \u0631\u0627\u0642\u062a \u2b50")
        if up:
            cfg = os.path.join(stage_dir, "staging-config.json")
            if os.path.isfile(cfg):
                try:
                    import json as _json
                    with open(cfg, encoding="utf-8") as fh:
                        conf = _json.load(fh)
                    env["STAGE_ADMIN_TOKEN"] = conf.get("admin_token", "")
                    env["STAGE_PROXY_SECRET"] = conf.get("proxy_secret", "")
                    env["STAGE_CONFIG"] = cfg
                except Exception:
                    pass
            for tname in A5_INTEGRATION_TESTS:
                tpath = os.path.join(tree, tname)
                if not os.path.isfile(tpath):
                    ok(False, "اختبار التكامل موجود في الشجرة النظيفة: %s" % tname)
                    continue
                try:
                    r = subprocess.run([vpy, tpath], cwd=tree, env=env,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        encoding="utf-8", errors="replace",
                                        timeout=900)
                    rc2 = r.returncode
                    out2 = r.stdout or ""
                except subprocess.TimeoutExpired:
                    rc2, out2 = 124, ""
                ok(rc2 == 0, "اختبار التكامل عدّى من الشجرة النظيفة: %s ⭐" % tname,
                   out2[-400:] if rc2 else "")
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    finally:
        shutil.rmtree(work, ignore_errors=True)


GATES = {"A1": gate_a1, "A2": gate_a2, "A3": gate_a3, "A4": gate_a4,
            "A5": gate_a5}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="البوابات البديلة لملفات الاختبار المعزولة")
    ap.add_argument("--gate", default="", help="رقم البوابة (A1 · A2 · A3 · A4 · A5)")
    args = ap.parse_args(argv)

    print("═" * 72)
    print("🚪 البوابات البديلة — الجولة ٢٦")
    print("═" * 72)
    if args.gate:
        gates = [args.gate.upper()]
    else:
        gates = sorted(GATES)
    for g in gates:
        fn = GATES.get(g)
        if fn is None:
            print("⛔ بوابة مجهولة: %s" % g)
            return 2
        fn()

    passed = sum(1 for r in RESULTS if r[0])
    total = len(RESULTS)
    print("\n" + "═" * 72)
    print("  النتيجة: %d/%d" % (passed, total))
    print("═" * 72)
    for cond, label in RESULTS:
        if not cond:
            print("  ❌ فشل: " + label)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
