#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R28 · أداة بناء سجل الاعتماد (١٤٤ بندًا) — **جزء ثابت في المستودع**.

📌 المطلوب من المالك (الجولة ٢٨ · أولوية ٥ ⭐):
   ① «المصفوفة الأصلية ١٤٤ بندًا متوفرة لدى المراجع» ⭐
   ② «المطلوب إعادة بناء سجل الاعتماد باستخدام المعايير والأوزان الأصلية» ⭐
   ③ «لا ترث نسبة ٩٢٫٥٠٪ تلقائيًا» ⭐
   ④ «اجعل أداة بناء سجل الاعتماد جزءاً ثابتاً من المستودع» ⭐
   ⑤ «لكل بند: حالة التنفيذ · نتيجة فعلية · دليل مرتبط بالمرشح ·
      نقاط مستحقة · سبب التعذر» ⭐
   ⑥ «لا تغيير للأوزان أو حد القبول أو السياسات الاستثمارية» ⭐

📌 كيف بتشتغل ⭐:
   ① بتقرأ **معايير وأوزان** البنود الأصلية ⭐ من `tools/r28_acceptance_items.csv`
      ⭐ (نسخة السجل الأصلي ⭐ — الأوزان: ٣٥ / ٣٠ / ٢٥ / ١٠ ⭐).
   ② بتقارن **دليل كل بند** (المذكور في السجل الأصلي ⭐) ⭐ مع **نتائج قياس R28** ⭐:
      · سجل اختبارات الواجهة (TAP ⭐) ⭐
      · سجل اختبارات الباك (مُصنِّف الـCI ⭐)
   ③ الحالة **مش موروثة** ⭐:
      · ✅ ناجح ⭐ = كل الملفات المذكورة في الدليل اتقاست في R28 ⭐ ونجحت ⭐.
      · ❌ فشل ⭐ = ملف من ملفات الدليل اتقاس وفشل ⭐.
      · ⛔ متعذر ⭐ = الدليل **ما اتقاسش** في R28 ⭐ ⇒ ⭐ صفر نقاط ⭐
        (ومعاها سبب التعذر ⭐ بالاسم ⭐).
   ④ النسبة **محسوبة من الحالات ⭐** ⇒ ⭐ مفيش نسبة موروثة ⭐.

⛔ الأداة **ما بتخترعش** ولا بتعدّل الأوزان ⭐ · ⛔ مافيش سر ⭐ · ⛔ مافيش شبكة ⭐.

── التشغيل ─────────────────────────────────────────────────────────────
   python3 tools/r28_build_acceptance_log.py \
     --fe-log /path/fe_suite_r28.log \
     --be-results /path/backend_results_r28.json \
     --fe-sha <40 hex> --be-sha <40 hex> \
     --out-json acceptance_r28.json --out-md acceptance_r28.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ITEMS_CSV = os.path.join(HERE, "r28_acceptance_items.csv")

TEST_FILE_RE = re.compile(r"([A-Za-z0-9_./-]+\.(?:py|test\.js))")


def sha_of(root):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace", timeout=30)
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def parse_fe_log(path):
    """سجل TAP ⭐ ⇒ {اسم الملف: (نجح؟, عدد الاختبارات)} ⭐."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    current = None
    cur = {"pass": 0, "fail": 0}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = re.match(r"^# Subtest: (\S+\.test\.js)", line)
            if m:
                if current:
                    out[current] = cur
                current = m.group(1)
                cur = {"pass": 0, "fail": 0}
                continue
            if current:
                if line.startswith("ok ") or line.startswith("    ok "):
                    cur["pass"] += 1
                elif line.startswith("not ok ") or line.startswith("    not ok "):
                    cur["fail"] += 1
            if line.startswith("1..") and current:
                out[current] = cur
                current = None
    if current:
        out[current] = cur
    return out


def parse_be_results(path):
    """مُصنِّف الـCI ⭐ ⇒ {اسم الملف: حالة} ⭐."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001
        return out
    items = data.get("results") if isinstance(data, dict) else data
    for it in (items or []):
        name = os.path.basename(str(it.get("file") or it.get("name") or ""))
        status = str(it.get("status") or it.get("state") or "").lower()
        out[name] = status
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="R28 · بناء سجل الاعتماد (١٤٤ ⭐)")
    ap.add_argument("--fe-log", default="")
    ap.add_argument("--be-results", default="")
    ap.add_argument("--fe-sha", default=os.environ.get("OCTA_FE_SHA", "").strip())
    ap.add_argument("--be-sha", default=os.environ.get("OCTA_CANDIDATE_SHA", "").strip())
    ap.add_argument("--fe-root", default=os.path.join(ROOT, "..", "octa"))
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    ap.add_argument("--rc-id", default="RC-R28-001")
    args = ap.parse_args(argv)

    with open(ITEMS_CSV, encoding="utf-8") as fh:
        items = list(csv.DictReader(fh))

    fe = parse_fe_log(args.fe_log)
    be = parse_be_results(args.be_results)
    fe_sha = args.fe_sha or sha_of(os.path.abspath(args.fe_root))
    be_sha = args.be_sha or sha_of(ROOT)

    rows = []
    counts = {"ناجح": 0, "فشل": 0, "متعذر": 0}
    points = 0
    max_points = 0
    for it in items:
        weight = int(it.get("weight") or 0)
        max_points += weight
        evidence_text = (it.get("evidence") or "").strip()
        note = (it.get("note") or "").strip()
        cond = (it.get("success_condition") or "").strip()
        files = sorted(set(TEST_FILE_RE.findall(evidence_text)))
        found = []
        missing = []
        failed = []
        for f in files:
            base = os.path.basename(f)
            if base.endswith(".test.js"):
                key = next((k for k in fe if k.endswith(base)), None)
                if key is None:
                    missing.append(f)
                elif fe[key]["fail"]:
                    failed.append("%s (%d فاشل ⭐)" % (f, fe[key]["fail"]))
                else:
                    found.append("%s (%d ناجح ⭐)" % (f, fe[key]["pass"]))
            else:
                key = base if base in be else next(
                    (k for k in be if k.endswith(base)), None)
                if key is None:
                    missing.append(f)
                else:
                    st = be[key]
                    if st in ("passed", "pass", "ok"):
                        found.append("%s (ناجح ⭐)" % f)
                    elif st in ("failed", "fail", "error"):
                        failed.append("%s (فاشل ⭐)" % f)
                    else:
                        missing.append("%s (%s ⭐)" % (f, st))

        if failed:
            status = "فشل"
            reason = "ملف من ملفات الدليل اتقاس في R28 وفشل ⭐: " + " · ".join(failed)
        elif found and not missing:
            status = "ناجح"
            reason = ""
        elif found:
            status = "متعذر"
            reason = ("دليل R26 فيه ملفات ما اتقاستش في R28 ⭐: "
                      + " · ".join(missing))
        else:
            status = "متعذر"
            reason = ("دليل R26 (%s ⭐) ما اتقاسش في R28 ⭐ — مافيش قياس "
                      "جديد يثبّت البند ⭐" % (evidence_text[:80] or "بدون"))

        earned = weight if status == "ناجح" else 0
        points += earned
        counts[status] = counts.get(status, 0) + 1
        rows.append({
            "ac_id": it.get("ac_id"),
            "scope_no": it.get("scope_no"),
            "scope_title": it.get("scope_title"),
            "category": it.get("category"),
            "weight": weight,
            "status": status,
            "earned": earned,
            "actual_result": (note or evidence_text)[:300],
            "evidence": " · ".join(found) if found else "",
            "missing": " · ".join(missing),
            "blocking_reason": reason,
            "success_condition": cond,
            "candidate": {"fe_sha": fe_sha, "be_sha": be_sha},
        })

    pct = (points / max_points * 100.0) if max_points else 0.0
    payload = {
        "rc_id": args.rc_id,
        "fe_sha": fe_sha,
        "be_sha": be_sha,
        "items_total": len(rows),
        "points": points,
        "points_max": max_points,
        "percent": round(pct, 2),
        "counts": counts,
        "fe_files_measured": len(fe),
        "be_files_measured": len(be),
        "items": rows,
    }

    print("═" * 72)
    print("📊 R28 · سجل الاعتماد (%s ⭐)" % args.rc_id)
    print("═" * 72)
    print("البنود: %d" % len(rows))
    print("النقاط: %d من %d  (%.2f%%)" % (points, max_points, pct))
    print("الحالات: %s" % counts)
    print("الواجهة المقاسة: %d ملف · الباك المقاس: %d ملف"
          % (len(fe), len(be)))
    print("⛔ النسبة **محسوبة** من الحالات ⭐ (مفيش نسبة موروثة ⭐)")

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print("📄 JSON: %s" % args.out_json)
    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write("# OCTA %s · سجل الاعتماد (١٤٤ بندًا)\n\n" % args.rc_id)
            fh.write("- الباك: `%s`\n- الواجهة: `%s`\n" % (be_sha, fe_sha))
            fh.write("- النقاط: **%d من %d (%.2f%%)**\n" % (points, max_points, pct))
            fh.write("- الحالات: %s\n\n" % counts)
            fh.write("⛔ النسبة محسوبة من الحالات ⭐ · البند المتعذر = صفر نقاط ⭐\n\n")
            by_scope = {}
            for r in rows:
                by_scope.setdefault((r["scope_no"], r["scope_title"]), []).append(r)
            for (num, title), group in sorted(by_scope.items()):
                got = sum(r["earned"] for r in group)
                tot = sum(r["weight"] for r in group)
                fh.write("## %s - %s : %d/%d\n\n" % (num, title, got, tot))
                for r in group:
                    fh.write("- %s | %s | %d/%d | %s\n"
                             % (r["ac_id"], r["status"], r["earned"], r["weight"],
                                (r["blocking_reason"] or r["evidence"] or "-")[:200]))
                fh.write("\n")
        print("📄 MD: %s" % args.out_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
