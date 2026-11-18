#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٤ (R24 · المرحلة ٥) — براهين PEG: «غير متاح» بدل رقم مخترع

📌 السؤال اللي البراهين دي بتجاوبه ⭐:
   PEG = P/E ÷ نمو الأرباح(٪) ⭐ — بس **مصدر `ni_growth` مش موجود**
   في أي مصدر فعلي ⭐ ⇒ فالسؤال الحقيقي هو ⭐:
   ① هل الكود بيخترع نمواً (من رابع سالب، أو من EPS/سعر) ⭐؟
   ② هل بيستبدل `ni_growth` بـ **proxy** (نمو الإيرادات · أداء 3 شهور) ⭐؟
   ③ ولا بيقول «غير متاح» (null) وبيصفر نقاط PEG ⭐؟
   ④ والأوزان المعتمدة (PEG + المحاور) **ما اتغيّرتش** ⭐.

📌 البراهين ⭐:
   ① مفيش مصدر فعلي بيقدّم `ni_growth` ⭐ (أعمدة الـscanner · ملفات
      البيانات · الكود نفسه ما بيكتبنش الحقل ⭐).
   ② سلوك الكود على item **من غير** `ni_growth` ⇐ peg = null ⇐
      «غير متاح» ⇐ 0 نقطة ⇐ ومفيش نص PEG في الإيجابيات ⭐.
   ③ ضابط سلبي: لو حطّينا proxy (نمو إيرادات · أداء 3 شهور) ⇐
      PEG لسه null ⇐ ⇒ مفيش استبدال ⭐.
   ④ ضابط موجب: لو `ni_growth` موجود فعلاً ⇐ PEG بيتحسب ⭐
      ⇒ «غير متاح» مش رقم ثابت مكتوب ⭐.
   ⑤ الأوزان: مقارنة قيمة‑بيمة مع الأساس (review/round23-backend) ⭐
      ⇒ PEG_POINTS_MAX · PEG_BANDS · سقف بند «القيمة» · أوزان المحاور
        · عتبة التغطية ⭐.

📌 مافيش أي طلب شبكي ⇐ مافيش لمس لبيانات الإنتاج ⭐.

📌 طريقة التشغيل ⭐:
   python3 tools/test_peg_availability_r24.py
   python3 tools/test_peg_availability_r24.py --report-json /tmp/peg.json
"""
import argparse
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# ⛔ العزل: كل الملفات في مجلد مؤقّت ⇐ مافيش لمس لبيانات الإنتاج ⭐
# ⛔ ومافيش أي اتصال شبكي ⇐ مافيش مهام خلفية ⇐ مافيش تيليجرام ⭐
TMP = tempfile.mkdtemp(prefix="octa_r24_peg_")
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r24-peg-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r24-peg-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["MAIL_ON"] = "0"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

# ⛔ الأساس: فرع الجولة ٢٣ ⭐ (قبل تغييرات الجولة ٢٤ ⭐)
BASE_REF = "5681ab9c838c2888f25cf59e218c9000a83d4dd7"

# ⛔ ملفات الـdata الفعلية ⭐ (هي مصادر الأرقام ⭐)
DATA_FILES = ["data_full.json"] + [
    os.path.join("data", name) for name in sorted(os.listdir(os.path.join(ROOT, "data")))
    if name.endswith(".json")
] if os.path.isdir(os.path.join(ROOT, "data")) else ["data_full.json"]

# ⛔ الكود اللي بيقرأ الحقل (مش بيكتبه ⭐)
READERS = ["update_prices.py", "opp_engine.py"]

RESULTS = []


def ok(cond, label, extra=""):
    passed = bool(cond)
    RESULTS.append({"label": label, "passed": passed, "detail": str(extra)})
    print(("  ✅ " if passed else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not passed else ""))
    return passed


def git_show(ref, path):
    try:
        return subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                              capture_output=True, text=True, timeout=300).stdout
    except Exception:
        return ""


def const_from_source(source, name):
    """بيستخرج قيمة ثابتة من مصدر بايثون (ast ⭐) — None لو مش موجودة ⭐"""
    try:
        tree = ast.parse(source)
    except Exception:
        return None
    found = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        found = ast.literal_eval(node.value)
                    except Exception:
                        found = None
    return found


def json_has_key(node, key):
    """Does the JSON tree have this key anywhere? (recursive ⭐)"""
    if isinstance(node, dict):
        if key in node:
            return True
        return any(json_has_key(v, key) for v in node.values())
    if isinstance(node, list):
        return any(json_has_key(v, key) for v in node)
    return False


def section(title):
    print("\n" + "-" * 74)
    print("  " + title)
    print("-" * 74)


# ────────────────────────────────────────────────────────────────────────────
# ⭐ ① مفيش مصدر فعلي لـ ni_growth ⭐
# ────────────────────────────────────────────────────────────────────────────
def check_no_source():
    section("① مفيش مصدر فعلي بيقدّم `ni_growth` ⭐")

    import update_prices as up

    # ①أ أعمدة الـscanner (المصدر الحقيقي للأرقام ⭐)
    columns = [str(col[1]) for col in getattr(up, "TV_COLUMNS", [])]
    growth_cols = [c for c in columns if "growth" in c]
    ok("ni_growth" not in columns,
       "①أ `ni_growth` مش في أعمدة الـscanner ⭐", columns[:6])
    ok(not growth_cols,
       "①ب مفيش عمود نمو الأرباح في الـscanner ⭐ (لا growth ولا غيره ⭐)",
       growth_cols)

    # ①ج ملفات البيانات الفعلية ⭐
    hits = []
    for rel in DATA_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        try:
            with io.open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            continue
        if json_has_key(payload, "ni_growth"):
            hits.append(rel)
    ok(not hits,
       "①ج مفيش مفتاح `ni_growth` في أي ملف بيانات بالمستودع ⭐ (%d ملف ⭐)"
       % len(DATA_FILES), hits)

    # ①د الكود ما بيكتبش الحقل ⭐ (قراءة بس ⭐)
    # 📌 «ni_growth» اللي بيظهر في قاموس التفاصيل (محور النمو ⭐) هو
    # 📌 **echo** للقيمة المقروءة ⇐ مش مصدر ⇐ فبنعتبره مش كاتب ⭐
    echo_values = ("ni", "ni_growth", "_f(item.get(\"ni_growth\"))",
                   "item.get(\"ni_growth\")")
    writers = []
    for rel in READERS + ["octa_score.py"]:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        with io.open(path, encoding="utf-8") as handle:
            for num, line in enumerate(handle, 1):
                if "ni_growth" not in line or '"ni_growth":' not in line:
                    continue
                value = line.split('"ni_growth":', 1)[1]
                value = value.split(",")[0].split("}")[0].strip().rstrip(",").strip()
                if value in echo_values:
                    continue
                writers.append("%s:%d ⇒ %s" % (rel, num, value[:40]))
    ok(not writers,
       "①د الكود بيقرأ `ni_growth` بس ⇐ مافيش سطر بيكتب الحقل ⭐", writers)

    # ①ه الـitem اللي الباك بيبنيه من أعمدة الـscanner ⇐ مافيش ni_growth ⭐
    item = {}
    for col in getattr(up, "TV_COLUMNS", []):
        item[str(col[1])] = None
    ok("ni_growth" not in item,
       "①ه الـitem المبني من أعمدة المصدر ⇐ مافيش `ni_growth` ⭐",
       sorted(item.keys())[:6])


# ────────────────────────────────────────────────────────────────────────────
# ⭐ ② الكود بيقول «غير متاح» ⇐ ومابيخترعش ولا بيستعمل proxy ⭐
# ────────────────────────────────────────────────────────────────────────────
def check_behaviour():
    section("② سلوك الكود: «غير متاح» بدل رقم مخترع ⭐")

    import update_prices as up
    import opp_engine as opp

    peers = {"الاختبار": {"median_pe": 10.0, "median_pb": 1.0, "median_roe": 12.0,
                           "with_pe": 5, "pe_range": [5, 20]}}

    base_item = {"price": 100.0, "pe": 10.0, "pb": 1.2, "roe": 15.0,
                 "net_margin": 12.0, "de_ratio": 0.4, "eps": 3.0,
                 "sector": "الاختبار"}

    # ②أ مفيش ni_growth ⇐ peg = None (غير متاح ⭐) ⇐ 0 نقطة ⭐
    res = up.fundamental_score(dict(base_item), peers)
    ok(res.get("peg") is None,
       "②أ مفيش `ni_growth` ⇐ `peg` = null (غير متاح ⭐)", res.get("peg"))
    ok(float(res.get("peg_points") or 0) == 0.0,
       "②ب مفيش `ni_growth` ⇐ نقاط PEG = 0 (مش «رخيص») ⭐",
       res.get("peg_points"))
    text = " ".join(list(res.get("positives") or []) + list(res.get("neutral") or [])
                     + list(res.get("negatives") or []))
    ok("PEG" not in text,
       "②ج مفيش `ni_growth` ⇐ مافيش نص PEG في المبررات ⭐", text[:120])

    # ②د الـJSON بيطلع null (مش 0 ⇐ مش inf) ⭐
    dumped = json.dumps({"peg": res.get("peg"), "peg_points": res.get("peg_points")},
                         ensure_ascii=False)
    ok('"peg": null' in dumped,
       "②د الرد بيطلع `peg: null` ⇐ الواجهة بتعرض «غير متاح» ⭐", dumped)

    # ②ه proxy: نمو الإيرادات + أداء 3 شهور ⇐ PEG لسه null ⭐
    proxied = dict(base_item)
    proxied["revenue_growth"] = 55.0
    proxied["perf_3m"] = 55.0
    proxied["earnings_growth"] = 55.0
    res_proxy = up.fundamental_score(proxied, peers)
    ok(res_proxy.get("peg") is None,
       "②ه proxy (نمو إيرادات · أداء 3 شهور · نمو-earnings) ⇐ PEG لسه null ⭐",
       res_proxy.get("peg"))

    # ②و ضابط موجب: لو `ni_growth` موجود فعلاً ⇐ PEG بيتحسب ⭐
    real = dict(base_item)
    real["ni_growth"] = 20.0
    res_real = up.fundamental_score(real, peers)
    ok(res_real.get("peg") is not None and abs(float(res_real["peg"]) - 0.5) < 1e-9,
       "②و ضابط موجب: `ni_growth` = 20 و P/E = 10 ⇐ PEG = 0.5 ⭐",
       res_real.get("peg"))
    ok(float(res_real.get("peg_points") or 0) == 8.0,
       "②ز ضابط موجب: PEG = 0.5 ⇐ 8 نقاط (سقف PEG_POINTS_MAX ⭐)",
       res_real.get("peg_points"))

    # ②ح قيم حدّية ⇐ null ⇐ مافيش قسمة على صفر ⭐
    edge = []
    for value in (None, 0, -5.0, "N/A", float("nan"), float("inf")):
        item = dict(base_item)
        item["ni_growth"] = value
        out = up.fundamental_score(item, peers)
        edge.append((repr(value), out.get("peg")))
    ok(all(peg is None for _v, peg in edge),
       "②ح قيم حدّية (None · 0 · سالب · نص · NaN · inf) ⇐ PEG = null ⭐", edge)

    # ②خ محور النمو في محرك الفرص ⇐ مافيش ni_growth ⇐ محور غير متاح ⭐
    axis = opp.c_growth({"perf_3m": None, "revenue_growth": None,
                          "ni_growth": None})
    ok(axis is None,
       "②خ محرك الفرص: مافيش أي نمو ⇐ المحور «غير متاح» ⭐", axis)

    # ②د المحور بيستخدم المتاح بس ⇐ وبيقول اللي استخدمه ⭐
    axis2 = opp.c_growth({"perf_3m": 10.0, "revenue_growth": None,
                           "ni_growth": None})
    ok(axis2 is not None and axis2[1].get("ni_growth") is None,
       "②د محرك الفرص: بيستخدم المتاح بس ⇐ `ni_growth` = null ⭐",
       axis2[1] if axis2 else None)


# ────────────────────────────────────────────────────────────────────────────
# ⭐ ③ الأوزان لم تتغير ⭐
# ────────────────────────────────────────────────────────────────────────────
def check_weights():
    section("③ الأوزان المعتمدة ما اتغيّرتش عن الأساس (%s) ⭐" % BASE_REF[:7])

    import update_prices as up
    import opp_engine as opp
    import octa_score as score

    pairs = [
        ("update_prices.py", "PEG_POINTS_MAX", getattr(up, "PEG_POINTS_MAX", None)),
        ("update_prices.py", "PEG_PE_MAX", getattr(up, "PEG_PE_MAX", None)),
        ("update_prices.py", "PEG_GROWTH_MIN", getattr(up, "PEG_GROWTH_MIN", None)),
        ("update_prices.py", "PEG_GROWTH_MAX", getattr(up, "PEG_GROWTH_MAX", None)),
        ("update_prices.py", "PEG_BANDS", getattr(up, "PEG_BANDS", None)),
        ("opp_engine.py", "FRESH_MIN_COVERAGE", getattr(opp, "FRESH_MIN_COVERAGE", None)),
        ("octa_score.py", "AXIS_WEIGHTS", getattr(score, "AXIS_WEIGHTS", None)),
    ]
    for rel, name, current in pairs:
        base_src = git_show(BASE_REF, rel)
        base_val = const_from_source(base_src, name)
        ok(base_val is not None and base_val == current,
           "③ `%s.%s` زي الأساس ⭐" % (rel, name),
           "الأساس=%r · الحالي=%r" % (base_val, current))

    # ③ب سقف بند «القيمة» (30 نقطة ⭐) في الـbreakdown ⭐
    import update_prices as up2
    peers = {"الاختبار": {"median_pe": 10.0, "median_pb": 1.0, "median_roe": 12.0,
                           "with_pe": 5, "pe_range": [5, 20]}}
    item = {"price": 100.0, "pe": 10.0, "pb": 1.2, "roe": 15.0,
            "net_margin": 12.0, "de_ratio": 0.4, "eps": 3.0,
            "sector": "الاختبار", "ni_growth": 20.0}
    res = up2.fundamental_score(item, peers)
    breakdown = res.get("breakdown") or {}
    ok(float(breakdown.get("القيمة") or 0) <= 30.0,
       "③ب سقف بند «القيمة» لسه 30 نقطة ⭐", breakdown)

    # ③ج أوزان المحاور = 100 ⭐
    weights = getattr(score, "AXIS_WEIGHTS", {}) or {}
    total = sum(float(v) for v in weights.values())
    ok(abs(total - 1.0) < 1e-9,
       "③ج مجموع أوزان المحاور = 1.00 ⭐", total)

    # ③د سطور الـPEG نفسها ما اتغيّرتش ⭐
    base_src = git_show(BASE_REF, "update_prices.py")
    cur_src = io.open(os.path.join(ROOT, "update_prices.py"), encoding="utf-8").read()

    def block(source, name):
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.dump(node)
        return ""

    for fn in ("peg_value", "peg_score"):
        ok(block(base_src, fn) == block(cur_src, fn) and bool(block(cur_src, fn)),
           "③د دالة `%s` مطابقة للأساس ⭐" % fn)


def main(argv=None):
    parser = argparse.ArgumentParser(description="براهين PEG (R24) ⭐")
    parser.add_argument("--report-json", default="",
                        help="يكتب تقرير الحالات كـ JSON ⭐")
    args = parser.parse_args(argv)

    print("\n" + "=" * 78)
    print("  🧪 براهين PEG ⭐ — «غير متاح» بدل رقم مخترع (الجولة ٢٤)")
    print("  الأساس للمقارنة: %s ⭐" % BASE_REF)
    print("=" * 78)

    check_no_source()
    check_behaviour()
    check_weights()

    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print("\n" + "=" * 78)
    print("  النتيجة: %d/%d ⭐" % (passed, total))
    if passed != total:
        print("  ❌ فيه براهين مش سليمة ⭐")
        for r in RESULTS:
            if not r["passed"]:
                print("     - %s  (%s)" % (r["label"], r["detail"]))
    else:
        print("  ✅ كل البراهين سليمة ⭐")
    print("=" * 78)

    if args.report_json:
        payload = {"ok": passed == total, "passed": passed, "total": total,
                   "base_ref": BASE_REF, "checks": RESULTS}
        try:
            with io.open(args.report_json, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            print("  📄 التقرير: %s" % args.report_json)
        except Exception as exc:
            print("  ⚠️ مقدرتش أكتب التقرير: %s" % str(exc)[:120])

    return 0 if passed == total else 1


if __name__ == "__main__":
    _code = main()
    shutil.rmtree(TMP, ignore_errors=True)
    # ⛔ os._exit ⇐ عشان الخيوط الخلفية ما تعملش انهيار وقت الإغلاق ⭐
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
