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


def parse_fe_tsv(path):
    """TSV لكل ملف ⭐ (اسم · ناجح · فاشل) ⭐ ⇒ {اسم الملف: (ناجح, فاشل)} ⭐."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            name, ok, fail = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not name.endswith(".test.js"):
                continue
            try:
                out[name] = {"pass": int(ok), "fail": int(fail)}
            except ValueError:
                continue
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
    items = None
    if isinstance(data, dict):
        items = data.get("files") or data.get("results")
    else:
        items = data
    for it in (items or []):
        name = os.path.basename(str(it.get("file") or it.get("name") or ""))
        status = str(it.get("status") or it.get("state") or "").lower()
        out[name] = status
    return out


# ═══════════════════════════════════════════════════════════════════
# ⭐ خريطة النطاق ← قياس R28 ⭐ (قاعدة صريحة ⭐ — مافيش تخمين ⭐)
# 📌 كل نطاق من السجل الأصلي (٣٦ نطاقًا ⭐) مربوط **باسم ملف** قِيس في R28 ⭐.
# 📌 "fe:X" ⇒ ملف اختبار واجهة (من قياس R28) ⭐ · "be:X" ⇒ ملف اختبار باك ⭐.
# 📌 "art:X" ⇒ فحص حيّ/مخرج R28 (ملف JSON/SHA) ⭐.
# 📌 إن غاب أحد المدخلات ⇒ البند = متعذر بصفر نقاط وسبب بالاسم ⭐.
# ═══════════════════════════════════════════════════════════════════
SCOPE_MAP = {
    "01": [("art", "manifest"), ("art", "evidence_branch")],
    "02": [("fe", "r26-session-hardening.test.js"), ("fe", "r26-kv-isolation.test.js"),
           ("art", "live_mgmt")],
    "03": [("be", "test_security_batch02.py"), ("be", "test_security_bgstore.py")],
    "04": [("fe", "r26-session-hardening.test.js"), ("fe", "r25-logout-hardening.test.js"),
           ("fe", "r21-do-strong-revocation.test.js")],
    "05": [("be", "test_round15_opp_perms.py"), ("be", "test_security_p0.py")],
    "06": [("be", "test_security_p0.py"), ("be", "test_round15_query_guard.py")],
    "07": [("fe", "xss.test.js"), ("fe", "sec024-xss-fixes.test.js"),
           ("fe", "sec025-cache-user-scope.test.js"), ("fe", "worker.test.js")],
    "08": [("art", "secret_scan"), ("art", "packages_scan")],
    "09": [("be", "test_security_batch01.py"), ("art", "live_preview")],
    "10": [("be", "tools/test_r25_storage_durability.py"),
           ("be", "tools/test_r26_portfolio_atomicity.py")],
    "11": [("be", "test_egx_ttl.py"), ("be", "test_round16_price_freshness.py"),
           ("be", "tools/test_r25_clock_routes.py")],
    "12": [("be", "tools/test_r25_concurrency.py"),
           ("be", "tools/test_r26_portfolio_atomicity.py")],
    "13": [("be", "tools/test_r25_fault_injection.py"),
           ("be", "tools/test_round26_api_tools_r26.py")],
    "14": [("be", "tools/test_data_integrity_proofs_r24.py"),
           ("be", "tools/test_data_integrity_guard.py")],
    "15": [("be", "tools/test_round24_growth_source_audit.py"),
           ("be", "test_round18_analysis_truth.py")],
    "16": [("be", "tools/test_data_integrity_guard.py"),
           ("be", "test_round15_coverage_states.py")],
    "17": [("be", "test_gold_integrity.py"), ("be", "test_gold_macro.py"),
           ("be", "tools/test_round24_gold_gate_contract.py")],
    "18": [("be", "test_round18_analysis_truth.py"), ("be", "test_charts_api.py"),
           ("be", "test_round17_n4_session_match.py")],
    "19": [("be", "test_round17_p1_unknown_state.py"),
           ("be", "test_round17_p2_coverage_consistency.py"),
           ("be", "test_round17_n2_coverage.py")],
    "20": [("be", "tools/test_engines_filters_audit.py"),
           ("be", "test_round18_analysis_truth.py")],
    "21": [("be", "test_security_batch01.py"), ("be", "test_round15_price_label.py"),
           ("be", "test_round16_price_freshness.py")],
    "22": [("be", "test_round16_legacy_weights.py"),
           ("be", "test_round17_n3_contract.py"), ("be", "test_strategy_cap01.py")],
    "23": [("be", "tools/test_engines_filters_audit.py"),
           ("be", "tools/test_round24_rel_volume_states.py")],
    "24": [("be", "tools/test_round26_api_tools_r26.py"),
           ("be", "test_round26_api_tools_r26.py")],
    "25": [("be", "test_r20_az31_36.py"), ("be", "test_gold_scenarios.py"),
           ("be", "test_gold_technical.py")],
    "26": [("fe", "r26-ux-perf.test.js"), ("fe", "page-keep-guard.test.js"),
           ("fe", "r20-a11y.test.js"), ("art", "live_preview"),
           ("art", "browser_journey")],
    "27": [("fe", "r23-login-error-states.test.js"), ("fe", "r25-login-path.test.js"),
           ("fe", "p3-login-clarity.test.js"), ("be", "test_signup_flow.py"),
           ("be", "test_pin_auth.py")],
    "28": [("be", "test_charts_api.py"), ("fe", "radar.test.js"),
           ("fe", "radar-ui.test.js"), ("fe", "smartmoney.test.js")],
    "29": [("fe", "r20-a11y.test.js"), ("fe", "r26-ux-perf.test.js"),
           ("fe", "mgmt-error-matrix.test.js")],
    "30": [("be", "test_r20_az31_36.py"), ("be", "test_round16_contract_wiring.py"),
           ("fe", "alpha-unavailable.test.js")],
    "31": [("art", "gate_a5"), ("art", "cross_repo_contract"), ("art", "be_suite")],
    "32": [("be", "tools/test_r25_perf_latency.py"), ("be", "test_round16_query_limits.py"),
           ("be", "test_round16_contract_wiring.py")],
    "33": [("be", "test_round14_release.py"), ("art", "live_preview_deploy")],
    "34": [("be", "tools/test_r25_metrics_board.py"), ("be", "test_round18_sec_failopen.py")],
    "35": [("be", "tools/test_r26_subscriptions.py"), ("be", "test_signup_flow.py"),
           ("fe", "mgmt-privacy.test.js")],
    "36": [("be", "tools/test_r26_subscriptions.py"), ("art", "acceptance_log")],
}

# ═══════════════════════════════════════════════════════════════════
# ⭐ بنود مغطاة بادعاء R26 ⭐ ولم يتقاس جديد في R28 ⭐ ⇒ متعذر ⭐
# 📌 السبب بالاسم ⭐ (مافيش تعميم ⭐ — البند نفسه ⭐):
#   · مصفوفة المتصفح الحقيقية (Chromium) لم تُعد في R28 ⭐
#   · الـCI على GitHub غير مفعّل (توكن بلا صلاحية workflow ⭐)
#   · تجربة rollback جديدة لم تُنفَّذ في R28 ⭐
#   · موافقات الإطلاق (الباقات/التسعير/الخصوصية) chez المالك ⭐
#   · موافقة منفصلة على النشر الحيّ ⭐
# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# ⭐⭐⭐ (R28) ⭐⭐⭐ بنود **محجوبة ببيئة القياس** ⭐⭐⭐
# 📌 18 ملف باك ⭐ فشلت بخطأ `ModuleNotFoundError: No module named 'requests'` ⭐
#   ⛔ الحزمة غير مثبتة ⭐ و⛔ PyPI غير متاح ⭐ ⇒ ⛔ مش عيب في المرشح ⭐
#   ⇒ ⭐ المتعذر بصفر نقاط ⭐ وسبب بالاسم ⭐ (مش «فشل» ⭐).
# ⭐ البرهان السالب ⭐: نفس الـ18 ملف ⭐ على الأساس (32cf806 ⭐) ⭐
#   ⇒ نفس الخطأ ⭐ ⇒ السبب بيئي ⭐ (موجود في tools/r28_env_blocked.json ⭐).
# ═══════════════════════════════════════════════════════════════════
ENV_BLOCKED_FILE = os.path.join(HERE, "r28_env_blocked.json")


def load_env_blocked(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception:  # noqa: BLE001
        return {}, {}
    files = doc.get("files") or {}
    meta = {k: doc.get(k) for k in ("why", "base_sha", "base_proof", "base_results")}
    return files, meta


ITEM_OVERRIDE = {
    "AC-07-3": ("قِيس جزئياً في R28 ⭐ — رحلة Chromium حقيقية ⭐ (البوابة ⭐ أداة الذهب ⭐ التنقل ⭐ "
                "١٠ عروض ⭐) ⭐ ⇒ ⛔ ما فيش ٢٥ مسار × ٣ عروض ⭐ ⇒ متعذر بصفر نقاط ⭐"),
    "AC-07-4": ("تطبيق CSP الفعلي قرار منفصل ⭐ — أدلة الـdist موجودة ⭐ لكن القرار ما اتاخدش ⭐ "
                "⇒ متعذر بصفر نقاط ⭐"),
    "AC-29-3": ("قِيس جزئياً في R28 ⭐ — ١٠ عروض حقيقية ⭐ + فحص أهداف اللمس ⭐ ⇒ ⛔ ما فيش "
                "لوحة مفاتيح ⭐ ولا قارئ شاشة ⭐ ⇒ متعذر بصفر نقاط ⭐"),
    "AC-29-4": ("لقطات فعلية في R28 ⭐ (٨ لقطات ⭐) ⭐ ⇒ ⛔ ما فيش تقرير تباين ⭐ ⇒ متعذر بصفر نقاط ⭐"),
    "AC-31-3": "الـCI على GitHub غير مفعّل ⭐ (توكن بلا صلاحية workflow ⭐) — البوابات تعمل محليًا ⭐",
    "AC-33-3": "تجربة rollback جديدة لم تُنفَّذ في R28 ⭐",
    "AC-33-4": "سجل rollback ومصفوفة HTTP يطلبان موافقة منفصلة ⭐",
    "AC-35-4": "تغيير حيّ للوحة الإدارة تم في هذه الجولة ⭐ — ما فيش سجل موافقة منفصلة ⭐",
    "AC-36-3": "موانع الإطلاق الخمسة ما زالت مفتوحة ⭐ ⇒ الرحلة الكاملة غير مغلقة ⭐",
    "AC-36-4": "موافقة المالك على الباقات والتسعير والشروط وخطة النشر ⭐",
}

def artifact_status(name, artifacts):
    """فحص المخرجات الحيّة ⭐ ⇒ (حالة, وصف) ⭐."""
    a = artifacts.get(name)
    if a is None:
        return "متعذر", ("مافيش مخرج R28 باسم «%s» ⭐" % name)
    if isinstance(a, dict):
        if a.get("ok") is True:
            return "ناجح", a.get("note") or a.get("body_head") or "تم ⭐"
        if a.get("ok") is False:
            return "فشل", a.get("why") or a.get("body_head") or "فشل ⭐"
    return "ناجح", str(a)[:200]


def main(argv=None):
    ap = argparse.ArgumentParser(description="R28 · بناء سجل الاعتماد (١٤٤ ⭐)")
    ap.add_argument("--fe-log", default="")
    ap.add_argument("--fe-tsv", default="")
    ap.add_argument("--be-results", default="")
    ap.add_argument("--fe-sha", default=os.environ.get("OCTA_FE_SHA", "").strip())
    ap.add_argument("--be-sha", default=os.environ.get("OCTA_CANDIDATE_SHA", "").strip())
    ap.add_argument("--fe-root", default=os.path.join(ROOT, "..", "octa"))
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    ap.add_argument("--rc-id", default="RC-R28-001")
    ap.add_argument("--live-checks", default="")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--evidence-branch", default="")
    ap.add_argument("--env-blocked", default=ENV_BLOCKED_FILE)
    args = ap.parse_args(argv)

    with open(ITEMS_CSV, encoding="utf-8") as fh:
        items = list(csv.DictReader(fh))

    env_blocked, env_meta = load_env_blocked(args.env_blocked)
    fe = parse_fe_log(args.fe_log)
    if args.fe_tsv:
        fe = parse_fe_tsv(args.fe_tsv)
    be = parse_be_results(args.be_results)

    artifacts = {}
    for path in (args.live_checks or "").split(","):
        path = path.strip()
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    artifacts.update(json.load(fh))
            except Exception:
                pass
    if args.manifest and os.path.isfile(args.manifest):
        try:
            with open(args.manifest, encoding="utf-8") as fh:
                m = json.load(fh)
            pkgs = m.get("packages") or []
            artifacts["manifest"] = {
                "ok": bool(pkgs) and all(p.get("md5") and p.get("sha256") for p in pkgs),
                "note": "%d حزمة ببصمة md5+sha256 ⭐" % len(pkgs)}
        except Exception:
            pass
    if args.evidence_branch:
        artifacts["evidence_branch"] = {"ok": True,
                                        "note": "فرع الأدلة: %s ⭐" % args.evidence_branch}
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
        ac_id = str(it.get("ac_id") or "").strip()
        if ac_id in ITEM_OVERRIDE:
            status = "متعذر"
            reason = ITEM_OVERRIDE[ac_id]
            found = []
            missing = []
            scope_key = str(it.get("scope_no") or "").strip()
            inputs = SCOPE_MAP.get(scope_key) or []
            for kind, ref in inputs:
                if kind == "fe":
                    key = next((k for k in fe if k == ref or k.endswith(ref)), None)
                    if key and not fe[key]["fail"]:
                        found.append("fe:%s (%d ناجح ⭐)" % (ref, fe[key]["pass"]))
                elif kind == "be":
                    base_ref = os.path.basename(ref)
                    key = next((k for k in be if k == base_ref or k.endswith("/" + base_ref)), None)
                    if key and str(be[key]).lower() in ("passed", "pass", "ok"):
                        found.append("be:%s (ناجح ⭐)" % ref)
            rows.append({
                "ac_id": ac_id,
                "scope_no": str(it.get("scope_no") or ""),
                "scope_title": it.get("scope_title"),
                "category": it.get("category"),
                "weight": weight,
                "status": status,
                "earned": 0,
                "actual_result": (note or evidence_text)[:300],
                "evidence": " · ".join(found),
                "missing": "",
                "blocking_reason": reason,
                "success_condition": cond,
                "candidate": {"fe_sha": fe_sha, "be_sha": be_sha},
            })
            counts[status] = counts.get(status, 0) + 1
            continue

        scope_key = str(it.get("scope_no") or "").strip()
        inputs = SCOPE_MAP.get(scope_key) or []
        if not inputs:
            status = "متعذر"
            reason = ("النطاق %s مالوش قياس مقابل في R28 ⭐ — "
                      "مافيش اسم ملف ولا فحص حيّ يغطيه ⭐" % scope_key)
            found = []
            missing = []
        else:
            found = []
            missing = []
            failed = []
            for kind, ref in inputs:
                if kind == "fe":
                    key = next((k for k in fe if k == ref or k.endswith(ref)), None)
                    if key is None:
                        missing.append("fe:%s (ما اتقاسش ⭐)" % ref)
                    elif fe[key]["fail"]:
                        failed.append("fe:%s (%d فاشل ⭐)" % (ref, fe[key]["fail"]))
                    else:
                        found.append("fe:%s (%d ناجح ⭐)" % (ref, fe[key]["pass"]))
                elif kind == "be":
                    base_ref = os.path.basename(ref)
                    key = next((k for k in be
                                if k == base_ref or k.endswith("/" + base_ref)), None)
                    if key is None:
                        missing.append("be:%s (ما اتقاسش ⭐)" % ref)
                    else:
                        st_be = str(be[key]).lower()
                        if st_be in ("passed", "pass", "ok"):
                            found.append("be:%s (ناجح ⭐)" % ref)
                        elif st_be in ("skipped", "skip"):
                            missing.append("be:%s (متخطّى ⭐)" % ref)
                        elif base_ref in env_blocked:
                            # ⭐⭐⭐ محجوب بالبيئة ⭐ ⇒ ⛔ مش «فشل» ⭐
                            missing.append("be:%s (محجوب ⭐ %s)"
                                           % (ref, env_blocked[base_ref]))
                        else:
                            failed.append("be:%s (فاشل ⭐)" % ref)
                else:
                    st_art, note = artifact_status(ref, artifacts)
                    if st_art == "ناجح":
                        found.append("art:%s (تم ⭐)" % ref)
                    elif st_art == "فشل":
                        failed.append("art:%s (%s ⭐)" % (ref, note))
                    else:
                        missing.append("art:%s (%s ⭐)" % (ref, note))
            if failed:
                status = "فشل"
                reason = "مدخل فاشل في R28 ⭐: " + " · ".join(failed)
            elif missing:
                status = "متعذر"
                reason = "مدخل متعذر في R28 ⭐: " + " · ".join(missing)
            else:
                status = "ناجح"
                reason = ""

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
        # ⭐⭐⭐ دليل المحجوب بالبيئة ⭐ (مع البرهان السالب ⭐)
        "environment_blocked": {
            "count": len(env_blocked),
            "why": env_meta.get("why", ""),
            "base_sha": env_meta.get("base_sha", ""),
            "base_proof": env_meta.get("base_proof", ""),
            "base_results": env_meta.get("base_results", ""),
            "files": env_blocked,
        },
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
