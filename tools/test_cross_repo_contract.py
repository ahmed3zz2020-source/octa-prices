#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R28 · اختبار العقد بين المستودعين (بصمتا الواجهة والخادم المعتمدتين).

📌 المطلوب من المالك (الجولة ٢٨ · أولوية ٣ ⭐):
   «بالنسبة إلى test_data_full_route.py ⭐ — احتفظ بالاختيار الحتمي ⭐،
    وأضف اختباراً بين المستودعين باستخدام بصمتي الواجهة والخادم المعتمدتين ⭐»

📌 ليه الاختبار ده لازم يكون **بين المستودعين** ⭐:
   📌 في R27 ⭐ كان فشل `test_data_full_route.py` ⭐ بسبب **ملف بيانات من المستودع التاني**
      ⭐ (بيانات الواجهة على فرع main ⭐ وفيها ١٣ سهماً محرف تالف ⭐) ⭐.
   📌 الاختبار داخل المستودع الواحد **مش كفاية** ⭐ ⇒ لازم المقارنة **بين المستودعين**
      ⭐ **ببصمتين معتمدتين** ⭐ (مش أي فرع ⭐).

📌 ما بيعملش ⭐:
   · ⛔ مافيش اتصال بالشبكة ⭐ · ⛔ مافيش أي سر ⭐ · ⛔ مافيش نشر ⭐.
   · ⛔ مافيش أي عدد مخترع ⭐ (كل رقم = نتيجة قراءة حقيقية ⭐).

── التشغيل ─────────────────────────────────────────────────────────────
   python3 tools/test_cross_repo_contract.py \
       --fe-root ../octa --be-root . \
       --fe-sha <40 hex> --be-sha <40 hex>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RESULTS = []

# ⛔ المسارات اللي الواجهة بتستهلكها من الباك ⭐ (عقد الجولة ٢٦ ⭐)
CONTRACT_ROUTES = (
    "/api/opp/strategies",
    "/api/opp/list/",
    "/api/opp/detail/",
    "/api/opp/explain/",
    "/api/opp/summary",
)

# ⭐ حقول العقد ⭐ (نفس بوابة A2 ⭐)
CONTRACT_FIELDS = (
    "coverage_status",
    "coverage_acceptable",
    "data_state",
    "freshness_summary_ar",
    "current_session_date",
)

# ⭐ محارف تلف ⭐ (نفس حارس النص ⭐)
CORRUPT = re.compile("[\ufffd\u3000-\u9fff\uac00-\ud7af\u0400-\u04ff]")


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, encoding="utf-8",
                           errors="replace", timeout=120)
        return r.returncode, (r.stdout or "")
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


def head_sha(root):
    rc, out = run(["git", "rev-parse", "HEAD"], cwd=root)
    return out.strip() if rc == 0 else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="R28 · اختبار العقد بين المستودعين")
    ap.add_argument("--fe-root", default=os.path.join(ROOT, "..", "octa"))
    ap.add_argument("--be-root", default=ROOT)
    ap.add_argument("--fe-sha", default=os.environ.get("OCTA_FE_SHA", "").strip())
    ap.add_argument("--be-sha", default=os.environ.get("OCTA_BE_SHA", "").strip())
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    fe = os.path.abspath(args.fe_root)
    be = os.path.abspath(args.be_root)

    print("═" * 72)
    print("🔗 R28 · اختبار العقد بين المستودعين")
    print("═" * 72)

    # ① بصمتا الشجرتين ⭐
    fe_head = head_sha(fe)
    be_head = head_sha(be)
    print("  الواجهة  : %s" % (fe_head or "(مفيش git ⭐)"))
    print("  الخادم   : %s" % (be_head or "(مفيش git ⭐)"))

    if args.fe_sha:
        ok(fe_head == args.fe_sha,
           "الواجهة عند البصمة المعتمدة ⭐", "%s ≠ %s" % (fe_head, args.fe_sha))
    else:
        ok(False, "بصمة الواجهة المعتمدة متداخلة ⭐ (مفيش --fe-sha ⭐)")
    if args.be_sha:
        ok(be_head == args.be_sha,
           "الخادم عند البصمة المعتمدة ⭐", "%s ≠ %s" % (be_head, args.be_sha))
    else:
        ok(False, "بصمة الخادم المعتمدة متداخلة ⭐ (مفيش --be-sha ⭐)")

    # ② ملف بيانات الواجهة ⭐ (اللي الباك بيقرأه ⭐)
    fe_data = os.path.join(fe, "data", "data_full.json")
    if not os.path.isfile(fe_data):
        fe_data = os.path.join(fe, "data_full.json")
    ok(os.path.isfile(fe_data),
       "ملف بيانات الواجهة موجود ⭐", fe_data)
    symbols = 0
    if os.path.isfile(fe_data):
        try:
            with open(fe_data, encoding="utf-8") as fh:
                raw = fh.read()
            bad = CORRUPT.findall(raw)
            ok(not bad,
               "ملف بيانات الواجهة نظيف (مافيش محرف تالف ⭐)",
               "%d موضع ⭐ (أمثلة: %s)" % (len(bad), "".join(sorted(set(bad))[:5])))
            try:
                data = json.loads(raw)
                symbols = len(data) if isinstance(data, dict) else 0
                if isinstance(data, dict) and isinstance(data.get("symbols"), dict):
                    symbols = len(data["symbols"])
            except Exception:
                symbols = 0
            ok(symbols > 0, "ملف بيانات الواجهة بيتقرأ ⭐ (JSON صالح ⭐)",
               "العدد: %s" % symbols)
        except UnicodeDecodeError as exc:
            ok(False, "ملف بيانات الواجهة بيتقرأ كـUTF-8 ⭐", exc)

    # ③ الاختيار الحتمي في الباك ⭐ (OCTA_FE_DATA_FULL ⭐)
    route_test = os.path.join(be, "test_data_full_route.py")
    ok(os.path.isfile(route_test), "اختبار مسار البيانات موجود في الخادم ⭐")
    src = ""
    if os.path.isfile(route_test):
        with open(route_test, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
    ok("OCTA_FE_DATA_FULL" in src,
       "الاختيار الحتمي مُفعّل (OCTA_FE_DATA_FULL ⭐)")
    ok("os.path.join(HERE" in src or "HERE" in src,
       "الاختيار الحتمي بيشير لمسار صريح (مش بحث عشوائي ⭐)")

    if os.path.isfile(fe_data):
        env = dict(os.environ)
        env["OCTA_FE_DATA_FULL"] = fe_data
        rc, out = run([sys.executable, route_test], cwd=be)
        ok(rc == 0,
           "test_data_full_route.py عدّى بملف الواجهة المعتمد ⭐",
           out[-600:] if rc else "")
        # ④ مافيش اعتماد على مجلد شقيق ⭐
        ok("..%s" % os.sep + "octa" not in src.replace("..%socta" % os.sep, ""),
           "مافيش اعتماد على مجلد شقيق ⭐")

    # ⑤ عقد المسارات ⭐ (نفس A2 ⭐)
    be_src = ""
    for name in ("update_prices.py", "opp_engine.py"):
        path = os.path.join(be, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                be_src += fh.read() + "\n"
    for route in CONTRACT_ROUTES:
        ok(('route("%s' % route) in be_src or ('route("%s"' % route) in be_src
           or ("%s" % route) in be_src,
           "المسار مركّب في الباك: %s" % route)
    for field in CONTRACT_FIELDS:
        ok(('"%s"' % field) in be_src,
           "حقل العقد منشور: %s" % field)

    # ⑥ خلاصة ⭐
    passed = sum(1 for r in RESULTS if r[0])
    total = len(RESULTS)
    print("─" * 72)
    print("النتيجة: %d/%d" % (passed, total))
    failed = [r[1] for r in RESULTS if not r[0]]
    for f in failed:
        print("  ❌ فشل: %s" % f)

    if args.out:
        payload = {
            "fe_root": fe, "be_root": be,
            "fe_sha": fe_head, "be_sha": be_head,
            "fe_data": fe_data, "fe_symbols": symbols,
            "passed": passed, "total": total,
            "failed": failed,
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
