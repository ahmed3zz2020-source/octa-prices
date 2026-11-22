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
import hashlib
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
    # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ تطبيع المفاتيح ⭐⭐⭐ ⇒ ⭐ ⭐ **اسم الملف** ⭐ ⭐
    # 📌 السبب ⭐: ⛔ البحث ⭐ ⭐ بيستعمل `os.path.basename` ⭐ ⭐ ⇒ ⛔ ومفتاح
    #    ⭐ ⭐ فيه مسار ⭐ ⭐ (مثل `tools/x.py` ⭐ ⭐) ⭐ ⭐ **مش هيلاقي** ⭐ ⭐
    #    ⇒ ⛔ التصنيف بيتجاهل ⭐ ⭐ بصمت ⭐ ⭐ ⇒ ⛔ «فشل» ⭐ ⭐ مكان «متعذر» ⭐ ⭐.
    files = {str(k).split("/")[-1]: v for k, v in files.items()}
    meta = {k: doc.get(k) for k in ("why", "base_sha", "base_proof", "base_results")}
    return files, meta



# ═══════════════════════════════════════════════════════════════════
# ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ دليل **لكل بند** ⭐⭐⭐
# 📌 السبب ⭐: ⛔ الأداة كانت بتقيّم البند بـ**نطاقه** ⭐ (SCOPE_MAP ⭐)
#    ⇒ ⛔ بند في نفس النطاق ⭐ ممكن يكون دليله **مختلف** ⭐
#    ⇒ ⛔ ⇒ النقاط بتتوزّع على أساس خاطئ ⭐.
# ✅ دلوقتي ⭐: ⭐ كل بند ليه دليل صريح ⭐ (ITEM_EVIDENCE ⭐)
#    ⇒ ⭐ والافتراضي = نطاق البند ⭐ ⭐ والنقطة فوق ⭐ بتشرح السبب ⭐.
# 📌 البنود المسرودة ⭐ (فوق ⭐) ⇒ ⛔ متعذر ⭐ بصفر نقاط ⭐ وسبب بالاسم ⭐.
# ═══════════════════════════════════════════════════════════════════
ITEM_EVIDENCE = {
    # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ AC-10-3 ⭐⭐⭐ — ⭐⭐⭐ مسار ⭐⭐⭐ الكتابة ⭐⭐⭐ ⭐⭐⭐
    # 📌 (R32 · e) ⭐: ⭐ اتقاس ⭐⭐⭐ عيب ⭐⭐⭐ كتابة ⭐⭐⭐ في ⭐⭐⭐ مجلد ⭐⭐⭐ الكود ⭐⭐⭐
    #    ⭐⭐⭐ (بوابة ⭐⭐⭐ سلامة ⭐⭐⭐ البيانات ⭐⭐⭐ المرجعية ⭐⭐⭐ في ⭐⭐⭐ الـCI ⭐⭐⭐) ⭐⭐⭐
    #    ⭐⭐⭐ ⇒ دلوقتي ⭐⭐⭐ البند ⭐⭐⭐ مربوط ⭐⭐⭐ بالحارس ⭐⭐⭐ الجديد ⭐⭐⭐ + سلسلة ⭐⭐⭐ السبب ⭐⭐⭐ ⭐⭐⭐.
    "AC-10-3": [("be", "tools/test_r25_storage_durability.py"),
                ("be", "tools/test_r26_portfolio_atomicity.py"),
                ("be", "tools/test_r32_index_history_store.py"),
                ("art", "index_history_fix")],
    # ⭐ ٠٧ ⭐ — XSS + المتصفح الحقيقي + تدقيق الـdist ⭐
    "AC-07-1": [("fe", "xss.test.js"), ("fe", "sec024-xss-fixes.test.js"),
                ("fe", "sec025-cache-user-scope.test.js"), ("fe", "worker.test.js")],
    "AC-07-2": [("fe", "xss.test.js"), ("fe", "sec024-xss-fixes.test.js"),
                ("fe", "sec025-cache-user-scope.test.js"), ("fe", "worker.test.js")],
    # ⭐ ٠٧-٣ ⭐ — التكامل الحقيقي ⭐ ⇒ رحلة Chromium ⭐
    "AC-07-3": [("fe", "xss.test.js"), ("art", "browser_journey")],
    "AC-07-4": [("fe", "xss.test.js"), ("art", "dist_audit")],
    # ⭐ ٢٦ ⭐ — رحلة المستخدم ⭐
    "AC-26-1": [("fe", "r26-ux-perf.test.js"), ("art", "browser_journey")],
    "AC-26-2": [("fe", "r26-ux-perf.test.js"), ("art", "browser_journey")],
    "AC-26-3": [("fe", "r26-ux-perf.test.js"), ("art", "browser_journey")],
    "AC-26-4": [("fe", "r26-ux-perf.test.js"), ("art", "browser_journey")],
    # ⭐ ٢٨ ⭐ — الشارتات والفلترة وأداة الذهب ⭐
    "AC-28-1": [("fe", "radar.test.js"), ("fe", "radar-ui.test.js"),
                ("fe", "smartmoney.test.js"), ("be", "test_charts_api.py")],
    "AC-28-2": [("fe", "radar.test.js"), ("be", "test_charts_api.py")],
    # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ AC-28-3 ⭐⭐⭐
    # 📌 المطلوب ⭐: ⭐ ربط AC-28-3 ⭐ برحلة الذهب **الفعلية** ⭐ في المتصفح ⭐
    #    ⇒ ⭐ الشارت الخطي ⭐ + ⭐ الفترات ⭐ + ⭐ التكبير ⭐ + ⭐ ملء الشاشة ⭐
    #       + ⭐ الدعم والمقاومة ⭐ + ⭐ الأحداث ⭐ ⇒ ⭐ كلهم في رحلة Chromium ⭐.
    # ⭐⭐⭐ (R32) ⭐⭐ ⭐ فحصات مودال الذهب ⭐⭐ ⭐ اتقاست ⭐⭐ ⭐ فعلاً ⭐⭐ ⭐
    #    ⭐⭐ ⭐ (رحلة 32/32 ⭐⭐ ⭐: شارت ⭐⭐ ⭐ canvas=7 ⭐⭐ ⭐ + سعر 6,343 ج.م ⭐⭐ ⭐
    #    ⭐⭐ ⭐ + ٩ فترات ⭐⭐ ⭐ + منطقتان ⭐⭐ ⭐ + ١٩٩٣ حرف عوامل ⭐⭐ ⭐ + ٦ أحداث ⭐⭐ ⭐).
    "AC-28-3": [("art", "journey_preview_r32"), ("be", "test_gold_integrity.py")],
    "AC-28-4": [("be", "test_charts_api.py"), ("be", "test_gold_integrity.py")],
    # ⭐⭐⭐ (R31) ⭐⭐⭐ AC-29-4 ⭐⭐⭐
    # 📌 المطلوب ⭐: ⭐ لقطات ⭐ + أدلة وصول واضحة ⭐ + تقرير تحقق التباين ⭐
    #    ⭐ ⭐ و ⭐ ⭐ «محاكاة JS ⭐ غير كافية» ⭐ ⭐.
    # ✅ R31 ⭐: ⭐ تدقيق Chromium حقيقي ⭐ (9 عروض ⭐) ⭐ + 9 لقطات ⭐
    #    ⭐ + تباين محسوب لكل نص ظاهر ⭐ + شجرة وصولية حقيقية ⭐
    #    ⭐ (locator.ariaSnapshot ⭐) ⭐ + العيوب اللي اتصلحت ⭐
    #    ⭐ (أزرار الفترات 31px ⭐ ⇒ 44px ⭐ + تباين 2.69:1 ⭐ ⇒ >= 4.5 ⭐) ⭐.
    # ⭐⭐⭐ (R32) ⭐⭐ ⭐ تدقيق الوصولية ⭐⭐ ⭐ اتقاس ⭐⭐ ⭐ على بصمة R32 ⭐⭐ ⭐
    #    ⭐⭐ ⭐ (٩ عروض ⭐⭐ ⭐ 320..1280 ⭐⭐ ⭐ · لمس<44 = 0 ⭐⭐ ⭐ · تباين فاشل = 0 ⭐⭐ ⭐
    #    ⭐⭐ ⭐ · لوحة المفاتيح 10/10 ⭐⭐ ⭐ · تركيز 10/10 ⭐⭐ ⭐ · Escape PASS ⭐⭐ ⭐).
    "AC-29-4": [("art", "a11y_audit"), ("fe", "r31-preview-security.test.js"),
                ("fe", "r32-preview-counter.test.js"), ("fe", "r20-a11y.test.js"),
                ("fe", "mgmt-error-matrix.test.js")],
    # ⭐⭐⭐ (R31) ⭐⭐⭐ AC-26 ⭐⭐⭐
    # 📌 السبب ⭐: ⭐ رحلة المعاينة الحيّة ⭐ (32/32 ⭐) ⭐ اتقست على بصمة R29 ⭐
    #    ⭐ ⭐ وبصمة R31 ⭐ ⭐ ما اتقستش ⭐ ⭐ ⇒ ⛔ ⭐ «مفتاح صندوق المعاينة» ⭐ ⭐
    #    ⭐ ⭐ (PREVIEW_CONSOLE_KEY ⭐) ⭐ ⭐ مش متاح ⭐ ⭐ ⇒ ⛔ مفيش كود ⭐ ⭐.
    # ✅ البديل ⭐ (مقيس ⭐ على نفس البصمة ⭐) ⭐:
    #    ⭐ ① تدقيق الوصولية ⭐ (9 عروض ⭐ + لقطات ⭐ + لمس ⭐ + تباين ⭐) ⭐
    #    ⭐ ② رحلة التنقل المحلية ⭐ (Chromium حقيقي ⭐ + الواجهة ⭐ + الباك ⭐) ⭐
    #    ⭐    (الأسهم ⭐ · الفرص ⭐ · المقارنة ⭐ · الرجوع ⭐ + 10 عروض ⭐) ⭐.
    # ⭐⭐⭐ (R32) ⭐⭐⭐ رحلة المعاينة ⭐⭐⭐ = 32/32 ⭐⭐⭐ على بصمة R32 ⭐⭐⭐
    # 📌 (R31) ⭐⭐ ⭐ كانت الرحلة ⭐⭐ ⭐ محلية ⭐⭐ ⭐ (تنقّل ⭐⭐ ⭐ فقط ⭐⭐ ⭐)
    #    ⭐⭐ ⭐ ⇒ ⭐⭐ ⭐ البنود دي ⭐⭐ ⭐ كانت ناقصة ⭐⭐ ⭐.
    # ✅ (R32) ⭐⭐ ⭐ رحلة كاملة ⭐⭐ ⭐: البوابة ⭐⭐ ⭐ + مودال الذهب ⭐⭐ ⭐ ببيانات حقيقية ⭐⭐ ⭐
    #    ⭐⭐ ⭐ + الشارت ⭐⭐ ⭐ + ٩ فترات ⭐⭐ ⭐ + مناطق ⭐⭐ ⭐ + العوامل ⭐⭐ ⭐ + الأحداث ⭐⭐ ⭐
    #    ⭐⭐ ⭐ + المحفظة ⭐⭐ ⭐ + التنبيهات ⭐⭐ ⭐ + التنقّل ⭐⭐ ⭐ + ١٠ عروض ⭐⭐ ⭐
    #    ⭐⭐ ⭐ على بصمة الواجهة bd3ae0a ⭐⭐ ⭐ وبصمة الباك 14363e2 ⭐⭐ ⭐.
    "AC-26-1": [("fe", "r26-ux-perf.test.js"), ("art", "journey_preview_r32"),
                ("art", "a11y_audit")],
    "AC-26-2": [("fe", "r26-ux-perf.test.js"), ("art", "journey_preview_r32"),
                ("art", "a11y_audit")],
    "AC-26-3": [("fe", "r26-ux-perf.test.js"), ("art", "journey_preview_r32")],
    "AC-26-4": [("fe", "r26-ux-perf.test.js"), ("art", "journey_preview_r32"),
                ("art", "a11y_audit")],
    # ⭐ ٣١ ⭐ — الـCI ⭐
    # 📌 (R29) ⭐ ⭐ `tools/test_ci_gates.py` ⭐ ⭐ **مش اختبار** ⭐ ⭐ ⇒ ⛔ مستثنى ⭐ ⭐
    #    ⭐ من اكتشاف الـCI ⭐ ⭐ بالتصميم ⭐ ⭐ ⇒ ⛔ كمدخل «be» ⭐ ⭐ ⇒ ⛔ «ما اتقاسش» ⭐ ⭐
    #    ⭐ ⭐ ⇒ ⭐ ⭐ الدليل الصحيح ⭐ ⭐ = **تشغيله** ⭐ ⭐ على ملفي الـworkflow ⭐ ⭐ ⭐
    # ⭐⭐⭐ (R32) ⭐⭐ ⭐ بوابة بصمة أدوات القياس ⭐⭐ ⭐ + محاكاة كاملة ⭐⭐ ⭐
    "AC-31-1": [("art", "ci_definitions"), ("art", "ci_gates_local"),
                ("art", "ci_digest_gate"), ("art", "ci_workflow_sim")],
    "AC-31-2": [("art", "ci_definitions"), ("art", "ci_gates_local"),
                ("art", "ci_digest_gate"), ("art", "ci_workflow_sim")],
    # ⭐ ٣١-٣ ⭐ — تجربة CI على GitHub ⭐ ⇒ ⛔ متعذر ⭐ (مانع صلاحيات ⭐)
    "AC-31-3": [("art", "ci_runs")],
    "AC-31-4": [("art", "ci_definitions"), ("art", "ci_runs")],
    # ⭐⭐⭐ (R32) ⭐⭐⭐ نطاق ٣٣ ⭐⭐⭐ (العزل والنشر والرجوع ⭐⭐⭐) ⭐⭐⭐
    # 📌 (R31) ⭐⭐⭐ البنود دي ⭐⭐⭐ كانت موروثة ⭐⭐⭐ من نطاق ٣٣ ⭐⭐⭐ العام ⭐⭐⭐.
    # ✅ (R32) ⭐⭐⭐ drill الرجوع ⭐⭐⭐ اتنفّذ ⭐⭐⭐ فعلاً ⭐⭐⭐:
    #    ⭐⭐⭐ ① رجوع الـworker ⭐⭐⭐ ( octa-preview ⭐⭐⭐) ⭐⭐⭐ ⇒ fingerprint ⭐⭐⭐ + live checks ⭐⭐⭐.
    #    ⭐⭐⭐ ② رجوع الباك ⭐⭐⭐ على بيئة الاختبار ⭐⭐⭐ (نفس مجلد البيانات ⭐⭐⭐) ⭐⭐⭐ ⇒ health ⭐⭐⭐ + quotes ⭐⭐⭐.
    "AC-33-1": [("be", "test_round14_release.py"), ("art", "live_preview_deploy"),
                ("art", "rollback_drill")],
    "AC-33-2": [("be", "test_round14_release.py"), ("art", "live_preview_deploy"),
                ("art", "rollback_drill")],
    # ⭐⭐⭐ (R32) ⭐⭐⭐ AC-33-3 ⭐⭐⭐ ⇒ drill الرجوع ⭐⭐⭐ اتنفّذ ⭐⭐⭐ ⇒ **يقيس** ⭐⭐⭐
    "AC-33-3": [("art", "rollback_drill"), ("art", "journey_preview_r32"),
                ("be", "test_round14_release.py")],
    # ⭐⭐⭐ (R32) ⭐⭐⭐ إصلاح ⭐⭐⭐ detector ⭐⭐⭐ التسرّب ⭐⭐⭐ المتذبذب ⭐⭐⭐ ⭐⭐⭐
    # 📌 (R32) ⭐⭐⭐ حارس ⭐⭐⭐ detector ⭐⭐⭐ التسرّب ⭐⭐⭐ (tools/test_r32_leak_detector.py ⭐⭐⭐)
    #    ⭐⭐⭐ = ⭐⭐⭐ ١٦ ⭐⭐⭐ حالة ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ ١٦/١٦ ⭐⭐⭐ على ⭐⭐⭐ المرشح ⭐⭐⭐ ⭐⭐⭐
    #    ⭐⭐⭐ (بصمة ⭐⭐⭐ ecfc50a ⭐⭐⭐) ⭐⭐⭐ ⭐⭐⭐⇢ ⭐⭐⭐ و ⭐⭐⭐ ٦/١٦ ⭐⭐⭐ **تفشل** ⭐⭐⭐
    #    ⭐⭐⭐ على ⭐⭐⭐ الأساس ⭐⭐⭐ 14363e2 ⭐⭐⭐ ⭐⭐⭐ (برهان ⭐⭐⭐ سلبي ⭐⭐⭐).
    # 📌 السبب ⭐⭐⭐: ⛔ detector ⭐⭐⭐ القديم ⭐⭐⭐ (substring ⭐⭐⭐ خام ⭐⭐⭐) ⭐⭐⭐ كان ⭐⭐⭐
    #    ⭐⭐⭐ بيعتبر ⭐⭐⭐ ٦ ⭐⭐⭐ أرقام ⭐⭐⭐ جوه ⭐⭐⭐ هاش ⭐⭐⭐ ٦٤ ⭐⭐⭐ خانة ⭐⭐⭐ أو ⭐⭐⭐ طابع ⭐⭐⭐
    #    ⭐⭐⭐ زمني ⭐⭐⭐ ١٣ ⭐⭐⭐ خانة ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ **تسرّب** ⭐⭐⭐ ⭐⭐⭐⇒ ⭐⭐⭐ إيجابية ⭐⭐⭐ كاذبة ⭐⭐⭐
    #    ⭐⭐⭐ ⇒ ⭐⭐⭐ فشل ⭐⭐⭐ متذبذب ⭐⭐⭐ (نفس ⭐⭐⭐ SHA ⭐⭐⭐: ⭐⭐⭐ فشل ⭐⭐⭐ مرة ⭐⭐⭐ ونجح ⭐⭐⭐ مرة ⭐⭐⭐).
    "AC-21-1": [("be", "test_signup_flow.py"), ("be", "test_r32_leak_detector.py"),
                ("be", "test_security_p0.py"), ("be", "test_security_batch02.py"),
                ("be", "test_auth_holes.py")],
}

# ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ شروط القبول **الإلزامية** ⭐⭐⭐
# 📌 دي البنود اللي لازم تنجح ⭐ ⇒ ⛔ لو واحدة مش ناجحة ⭐ ⇒ ⛔ المرشح **مش جاهز** ⭐
#    مهما كانت النسبة ⭐ (حد 90% ⭐ لوحده مش كفاية ⭐).
MANDATORY_ITEMS = [
    "AC-01-1", "AC-03-1", "AC-05-1", "AC-06-1", "AC-07-1", "AC-09-1",
    "AC-11-1", "AC-16-1", "AC-18-1", "AC-21-1", "AC-26-1", "AC-27-1",
    "AC-28-1", "AC-29-1", "AC-31-1", "AC-33-1", "AC-34-1", "AC-35-1",
]

# ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ حد القبول ⭐⭐⭐
ACCEPT_THRESHOLD_PCT = 90.0

BASE_FAILING_FILE = os.path.join(HERE, "r29_base_failing.json")

ITEM_OVERRIDE = {
    "AC-07-3": ("قِيس جزئياً في R28 ⭐ — رحلة Chromium حقيقية ⭐ (البوابة ⭐ أداة الذهب ⭐ التنقل ⭐ "
                "١٠ عروض ⭐) ⭐ ⇒ ⛔ ما فيش ٢٥ مسار × ٣ عروض ⭐ ⇒ متعذر بصفر نقاط ⭐"),
    "AC-07-4": ("تطبيق CSP الفعلي قرار منفصل ⭐ — أدلة الـdist موجودة ⭐ لكن القرار ما اتاخدش ⭐ "
                "⇒ متعذر بصفر نقاط ⭐"),
    "AC-29-3": ("R31 ⭐ — Chromium حقيقي ⭐ + شجرة وصولية ⭐ (9 عروض ⭐ 360..1280 ⭐) ⭐ "
                "⇒ لوحة المفاتيح 10/10 ⭐ + تركيز مرئي 10/10 ⭐ + لمس<44 = 0 ⭐ + تباين فاشل = 0 ⭐ "
                "⇒ ⛔ ما فيش قارئ شاشة بشري ⭐ (الشرط نفسه ⭐) ⭐ ⇒ متعذر بصفر نقاط ⭐"),
    "AC-31-3": "الـCI على GitHub غير مفعّل ⭐ (توكن بلا صلاحية workflow ⭐) — البوابات تعمل محليًا ⭐",
    "AC-33-4": "سجل rollback ومصفوفة HTTP يطلبان موافقة منفصلة ⭐",
    "AC-33-4": "سجل rollback ومصفوفة HTTP يطلبان موافقة منفصلة ⭐",
    # ⭐⭐⭐ (R32) ⭐⭐⭐ تصحيح تاريخي ⭐⭐⭐: ⛔ النصّ القديم ⭐⭐⭐ كان يقول ⭐⭐⭐
    #    ⭐⭐⭐ «تغيير حيّ للوحة الإدارة تم في هذه الجولة» ⭐⭐⭐ ⭐⭐⭐ ⇒ ⛔ كذب ⭐⭐⭐
    #    ⭐⭐⭐ لأن التغيير الحقيقي ⭐⭐⭐ حصل في **٢٠ نوفمبر ٢٠٢٦** ⭐⭐⭐
    #    ⭐⭐⭐ (تدوير APP_PASSWORD ⭐⭐ ⭐ للعامل octa-mgmt ⭐⭐ ⭐) ⭐⭐⭐
    #    ⭐⭐⭐ ⇒ مش في R31 ⭐⭐⭐ ولا R32 ⭐⭐⭐ ⇒ ⛔ متعذر ⭐⭐⭐ بصفر نقاط ⭐⭐⭐
    #    ⭐⭐⭐ لأن **سجل الموافقة المنفصلة** ⭐⭐⭐ لسه مش موجود ⭐⭐⭐.
    "AC-35-4": "تغيير حيّ للوحة الإدارة ⭐ ⭐ ⭐ حصل في ٢٠ نوفمبر ٢٠٢٦ ⭐ ⭐ ⭐ "
               "(تدوير APP_PASSWORD ⭐ ⭐ ⭐ للعامل octa-mgmt ⭐ ⭐ ⭐) ⭐ ⭐ ⭐ "
               "⇐ مش في R31 ⭐ ⭐ ⭐ ولا R32 ⭐ ⭐ ⭐ ⇒ ⛔ سجل الموافقة المنفصلة ⭐ ⭐ ⭐ "
               "لسه مش موجود ⭐ ⭐ ⭐ ⇒ متعذر بصفر نقاط ⭐ ⭐ ⭐",
    "AC-36-3": "موانع الإطلاق ⭐ ⭐ ⭐ ( actions ⭐⭐ + تيليجرام ⭐⭐ + سرّيّة ⭐⭐ + "
               "CSP ⭐⭐ + قارئ شاشة ⭐⭐ ) ⭐⭐ ⭐ ما زالت مفتوحة ⭐⭐ ⇒ الرحلة الكاملة ⭐⭐ "
               "غير مغلقة ⭐⭐",
    "AC-36-4": "موافقة المالك على الباقات والتسعير والشروط وخطة النشر ⭐",
}

# ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ مخرجات **مانعها المالك** ⭐⭐⭐ ⇒ ⭐ ⭐ متعذر ⭐ ⭐
# 📌 السبب ⭐: ⛔ «فشل» ⭐ ⭐ معناها ⭐ ⭐ **عيب في المرشح** ⭐ ⭐ ⇒ ⭐ ⭐ والمانع
#    ⭐ ⭐ اللي في إيد المالك ⭐ ⭐ (صلاحية توكن ⭐ ⭐ / حساب ⭐ ⭐ / قرار ⭐ ⭐)
#    ⭐ ⭐ **مش عيب المرشح** ⭐ ⭐ ⇒ ⭐ ⭐ لازم يتصنّف «متعذر» ⭐ ⭐ بصفر نقاط ⭐ ⭐.
OWNER_BLOCKED_ARTIFACTS = {
    "ci_runs": "المانع ⭐ ⭐: توكن ⭐ ⭐ بدون صلاحية «workflow» ⭐ ⭐ ⇒ ⛔ نشر تعريف الـCI ⭐ ⭐ "
               "وتشغيله ⭐ ⭐ على Actions ⭐ ⭐ راجع المالك ⭐ ⭐",
    # ⭐⭐⭐ (R31) ⭐⭐⭐
    # 📌 السبب ⭐: ⭐ «مفتاح صندوق المعاينة» ⭐ (PREVIEW_CONSOLE_KEY ⭐) ⭐ **سرّ** ⭐
    #    ⭐ ⇒ ⛔ مش موجود ⭐ في جلسة المراجعة ⭐ ⇒ ⛔ كود التأكيد ⭐ ما ينقرأش ⭐
    #    ⭐ ⇒ ⛔ رحلة المعاينة الحيّة ⭐ ما تتقاش ⭐ على بصمة R31 ⭐.
    # ✅ البديل ⭐: ⭐ رحلة محلية مقيسة ⭐ (journey_nav_r31 ⭐) ⭐ + ⭐ تدقيق الوصولية ⭐
    #    ⭐ (a11y_audit ⭐) ⭐ ⇒ متعذر بصفر نقاط ⭐ (مش عيب في المرشح ⭐).
    "browser_journey": "المانع ⭐ ⭐: مفتاح صندوق المعاينة ⭐ ⭐ (PREVIEW_CONSOLE_KEY ⭐ ⭐) ⭐ ⭐ "
                       "مش متاح ⭐ ⭐ ⇒ ⛔ رحلة المعاينة الحيّة ⭐ ⭐ ما اتقستش ⭐ ⭐ على بصمة R31 ⭐ ⭐ "
                       "⇒ متعذر بصفر نقاط ⭐ ⭐ (القياس الموجود ⭐ ⭐ 32/32 ⭐ ⭐ على بصمة R29 ⭐ ⭐)",
    "gold_journey": "المانع ⭐ ⭐: نفس مفتاح صندوق المعاينة ⭐ ⭐ ⇒ ⛔ فحصات مودال الذهب ⭐ ⭐ "
                    "اللي محتاجة بيانات ⭐ ⭐ ما اتقاستش ⭐ ⭐ ⇒ ⛔ والبيئة المعزولة ⭐ ⭐ مافيش فيها "
                    "بيانات سوق ⭐ ⭐ ⇒ متعذر بصفر نقاط ⭐ ⭐",
    "packages_scan": "المسح ⭐ ⭐ ناتج **بعد** بناء السجل ⭐ ⭐ ⇒ ⛔ مراجعة ⭐ ⭐ في تقرير R29 ⭐ ⭐",
}


def sha256_file(path):
    """بصمة محتوى المخرج ⭐ ⇒ تُربط كل بند بالقياس اللي أنتجه ⭐."""
    if not path or not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_sha(name, artifacts):
    """بصمة المخرج الحيّ ⭐ (لو اتسجّلت ⭐) ⭐ ⇒ '' ⭐ لو مفيش ⭐."""
    a = artifacts.get(name)
    if isinstance(a, dict):
        return a.get("sha256") or ""
    return ""


def item_fingerprint(inputs, fe, be, artifacts, fe_log_sha, fe_tsv_sha, be_results_sha):
    """⭐⭐⭐ (R32) ⭐⭐⭐ بصمة التشغيل ⭐⭐⭐ لكل بند ⭐⭐⭐.
    📌 المطلوب ⭐⭐⭐ (R32 ⭐⭐⭐ بند ٤ ⭐⭐⭐): ⭐⭐⭐ «ربط سجل الباك ⭐⭐⭐ وكل بند إلزامي ⭐⭐⭐
       ببصمة التشغيل ⭐⭐⭐ ودليل شرطه ⭐⭐⭐» ⭐⭐⭐
    ⇒ ⭐⭐⭐ كل مدخل ⭐⭐⭐ (ملف اختبار ⭐⭐⭐ · مخرج حيّ ⭐⭐⭐) ⭐⭐⭐ بيتربط ⭐⭐⭐
       ببصمة المحتوى ⭐⭐⭐ (sha256 ⭐⭐⭐) ⭐⭐⭐ اللي أنتجه ⭐⭐⭐.
    """
    out = []
    for kind, ref in inputs or []:
        rec = {"kind": kind, "ref": ref}
        if kind == "fe":
            key = next((k for k in fe if k == ref or k.endswith(ref)), None)
            if key is None:
                rec["status"] = "متعذر"
                rec["why"] = "ما اتقاسش ⭐"
            elif fe[key]["fail"]:
                rec["status"] = "فشل"
                rec["pass"] = fe[key]["pass"]
                rec["fail"] = fe[key]["fail"]
            else:
                rec["status"] = "ناجح"
                rec["pass"] = fe[key]["pass"]
                rec["fail"] = 0
            rec["log_sha256"] = fe_log_sha
            rec["tsv_sha256"] = fe_tsv_sha
        elif kind == "be":
            base_ref = os.path.basename(ref)
            key = next((k for k in be if k == base_ref or k.endswith("/" + base_ref)), None)
            if key is None:
                rec["status"] = "متعذر"
                rec["why"] = "ما اتقاسش ⭐"
            else:
                st = str(be[key]).lower()
                if st in ("passed", "pass", "ok"):
                    rec["status"] = "ناجح"
                elif st in ("skipped", "skip"):
                    rec["status"] = "متخطّى"
                else:
                    rec["status"] = "فشل"
            rec["results_sha256"] = be_results_sha
        else:
            st_art, note = artifact_status(ref, artifacts)
            rec["status"] = st_art
            rec["sha256"] = artifact_sha(ref, artifacts)
            rec["note"] = note[:400]
        out.append(rec)
    return out


def artifact_status(name, artifacts):
    """فحص المخرجات الحيّة ⭐ ⇒ (حالة, وصف) ⭐."""
    a = artifacts.get(name)
    if a is None:
        return "متعذر", ("مافيش مخرج R28 باسم «%s» ⭐" % name)
    if isinstance(a, dict):
        if a.get("ok") is True:
            return "ناجح", a.get("note") or a.get("body_head") or "تم ⭐"
        if a.get("ok") is False:
            if name in OWNER_BLOCKED_ARTIFACTS:
                # ⭐⭐⭐ مانع المالك ⭐⭐⭐ ⇒ ⭐ ⭐ متعذر ⭐ ⭐ بصفر نقاط ⭐ ⭐ (مش فشل ⭐ ⭐)
                why = a.get("why") or a.get("note") or ""
                return "متعذر", ("%s ⭐ ⇒ %s" % (why, OWNER_BLOCKED_ARTIFACTS[name]))
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
    ap.add_argument("--base-failing", default=BASE_FAILING_FILE)
    args = ap.parse_args(argv)

    with open(ITEMS_CSV, encoding="utf-8") as fh:
        items = list(csv.DictReader(fh))

    env_blocked, env_meta = load_env_blocked(args.env_blocked)
    base_failing, base_meta = load_env_blocked(args.base_failing)
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
    # ⭐⭐⭐ (R32) ⭐⭐⭐ بصمات سجلات القياس ⭐⭐⭐ ⇒ بتتربط بكل بند ⭐⭐⭐
    fe_log_sha = sha256_file(args.fe_log)
    fe_tsv_sha = sha256_file(args.fe_tsv)
    be_results_sha = sha256_file(args.be_results)

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
            used_art = {}
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
                elif kind == "art":
                    used_art[ref] = artifact_sha(ref, artifacts)
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
                "run_fingerprint": {
                    "fe_sha": fe_sha, "be_sha": be_sha,
                    "fe_log_sha256": fe_log_sha, "fe_tsv_sha256": fe_tsv_sha,
                    "be_results_sha256": be_results_sha,
                    "inputs": item_fingerprint(inputs, fe, be, artifacts,
                                              fe_log_sha, fe_tsv_sha, be_results_sha),
                },
            })
            counts[status] = counts.get(status, 0) + 1
            continue

        scope_key = str(it.get("scope_no") or "").strip()
        inputs = SCOPE_MAP.get(scope_key) or []
        # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ دليل **البند نفسه** ⭐⭐⭐
        # 📌 الافتراضي = نطاق البند ⭐ ⭐ و ⭐ البنود اللي ليها دليل مختلف ⭐
        #    ⇒ ⭐ فوق ⭐ (مكتوب بالاسم ⭐ وبالسبب ⭐).
        if ac_id in ITEM_EVIDENCE:
            inputs = ITEM_EVIDENCE[ac_id]
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
                        elif base_ref in base_failing:
                            # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ فشل على الأساس ⭐
                            # ⇒ ⛔ مش عيب في المرشح ⭐ ⇒ ⛔ متعذر ⭐ بصفر نقاط ⭐
                            #    ⭐ و ⭐ السبب بالاسم ⭐ ⭐ والبرهان السالب ⭐.
                            missing.append("be:%s (فشل على الأساس ⭐ ⇒ متعذر ⭐ %s)"
                                           % (ref, base_failing[base_ref]))
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
            "run_fingerprint": {
                "fe_sha": fe_sha, "be_sha": be_sha,
                "fe_log_sha256": fe_log_sha, "fe_tsv_sha256": fe_tsv_sha,
                "be_results_sha256": be_results_sha,
                "inputs": item_fingerprint(inputs, fe, be, artifacts,
                                          fe_log_sha, fe_tsv_sha, be_results_sha),
            },
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
        "be_files_measured": len(be),
        # ⭐⭐⭐ (R32 · بند ٤) ⭐⭐⭐ سجل الباك ⭐⭐⭐ + بصمة كل سجل ⭐⭐⭐
        "measurement_runs": {
            "fe_log": {"path": args.fe_log, "sha256": fe_log_sha,
                       "files": len(fe)},
            "fe_tsv": {"path": args.fe_tsv, "sha256": fe_tsv_sha,
                       "files": len(fe)},
            "be_results": {"path": args.be_results, "sha256": be_results_sha,
                           "files": len(be)},
            "fe_sha": fe_sha,
            "be_sha": be_sha,
        },
        # ⭐⭐⭐ دليل المحجوب بالبيئة ⭐ (مع البرهان السالب ⭐)
        "environment_blocked": {
            "count": len(env_blocked),
            "why": env_meta.get("why", ""),
            "base_sha": env_meta.get("base_sha", ""),
            "base_proof": env_meta.get("base_proof", ""),
            "base_results": env_meta.get("base_results", ""),
            "files": env_blocked,
        },
        # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ شروط القبول الإلزامية ⭐ + حد الـ90% ⭐
        "acceptance_threshold_pct": ACCEPT_THRESHOLD_PCT,
        "percent_meets_threshold": bool(pct >= ACCEPT_THRESHOLD_PCT),
        "mandatory": [
            {"ac_id": mid,
             "status": next((r.get("status") for r in rows if r.get("ac_id") == mid), "متعذر"),
             "met": bool(next((r.get("status") == "ناجح" for r in rows if r.get("ac_id") == mid), False)),
             # ⭐⭐⭐ (R32) ⭐⭐⭐ دليل الشرط ⭐⭐⭐ + بصمة التشغيل ⭐⭐⭐
             "success_condition": next((r.get("success_condition") for r in rows
                                        if r.get("ac_id") == mid), ""),
             "evidence": next((r.get("evidence") for r in rows if r.get("ac_id") == mid), ""),
             "missing": next((r.get("missing") for r in rows if r.get("ac_id") == mid), ""),
             "blocking_reason": next((r.get("blocking_reason") for r in rows
                                       if r.get("ac_id") == mid), ""),
             "run_fingerprint": next((r.get("run_fingerprint") for r in rows
                                      if r.get("ac_id") == mid), {})}
            for mid in MANDATORY_ITEMS
        ],
        "mandatory_all_met": bool(all(
            next((r.get("status") == "ناجح" for r in rows if r.get("ac_id") == mid), False)
            for mid in MANDATORY_ITEMS)),
        "base_failing": {
            "count": len(base_failing),
            "why": base_meta.get("why", ""),
            "base_sha": base_meta.get("base_sha", ""),
            "base_proof": base_meta.get("base_proof", ""),
            "files": base_failing,
        },
        "items": rows,
    }
    # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ الجاهزية للمراجعة ⭐⭐⭐
    payload["ready_for_review"] = bool(
        payload["percent_meets_threshold"] and payload["mandatory_all_met"])
    payload["not_ready_reasons"] = [
        ("النسبة %.2f%% ⭐ أقل من الحد %.0f%% ⭐" % (pct, ACCEPT_THRESHOLD_PCT))
        if not payload["percent_meets_threshold"] else "",
    ] + [
        ("بند إلزامي مش ناجح ⭐: %s ⭐" % m["ac_id"])
        for m in payload["mandatory"] if not m["met"]
    ]
    payload["not_ready_reasons"] = [r for r in payload["not_ready_reasons"] if r]

    print("═" * 72)
    print("📊 R28 · سجل الاعتماد (%s ⭐)" % args.rc_id)
    print("═" * 72)
    print("البنود: %d" % len(rows))
    print("النقاط: %d من %d  (%.2f%%)" % (points, max_points, pct))
    print("الحالات: %s" % counts)
    print("الواجهة المقاسة: %d ملف · الباك المقاس: %d ملف"
          % (len(fe), len(be)))
    print("⛔ النسبة **محسوبة** من الحالات ⭐ (مفيش نسبة موروثة ⭐)")
    # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐ حد القبول + الإلزاميات ⭐⭐⭐
    print("⛔ حد القبول ⭐: %.0f%% ⭐ ⇒ %s ⭐"
          % (ACCEPT_THRESHOLD_PCT,
             "متحقق ⭐" if payload["percent_meets_threshold"] else "**مش متحقق** ⭐"))
    unmet = [m["ac_id"] for m in payload["mandatory"] if not m["met"]]
    print("⛔ البنود الإلزامية ⭐: %d/%d ⭐ ⇒ %s ⭐"
          % (len(payload["mandatory"]) - len(unmet), len(payload["mandatory"]),
             "كلها متحققة ⭐" if not unmet else "مش متحققة ⭐: " + " · ".join(unmet)))
    print("⛔ جاهزية المراجعة ⭐: %s ⭐" % ("جاهز ⭐" if payload["ready_for_review"] else "مش جاهز ⭐"))
    for r in payload["not_ready_reasons"]:
        print("     ⛔ %s" % r)

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
            # ⭐⭐⭐ (R29 · FINDING-17) ⭐⭐⭐
            fh.write("## حد القبول والشروط الإلزامية ⭐\n\n")
            # ⭐⭐⭐ (R32 · بند ٤) ⭐⭐⭐ سجل الباك ⭐⭐⭐ + بصمة كل سجل ⭐⭐⭐
            mr = payload["measurement_runs"]
            fh.write("## سجل الباك وبصمة التشغيل ⭐\n\n")
            fh.write("- سجل الباك ⭐: `%s` ⭐ ببصمة `%s` ⭐ (%d ملف ⭐)\n"
                     % (mr["be_results"]["path"] or "-", mr["be_results"]["sha256"] or "-",
                        mr["be_results"]["files"]))
            fh.write("- سجل الواجهة ⭐: `%s` ⭐ ببصمة `%s` ⭐ · `%s` ⭐ ببصمة `%s` ⭐\n"
                     % (mr["fe_log"]["path"] or "-", mr["fe_log"]["sha256"] or "-",
                        mr["fe_tsv"]["path"] or "-", mr["fe_tsv"]["sha256"] or "-"))
            fh.write("- بصمة المرشح ⭐: الباك `%s` ⭐ · الواجهة `%s` ⭐\n\n"
                     % (be_sha, fe_sha))
            fh.write("### البنود الإلزامية ⭐: الشرط والدليل والبصمة ⭐\n\n")
            for m in payload["mandatory"]:
                fh.write("- **%s** ⭐ حالة: **%s** ⭐\n" % (m["ac_id"], m["status"]))
                fh.write("  - شرط النجاح ⭐: %s\n" % (m["success_condition"] or "-"))
                fh.write("  - الدليل ⭐: %s\n" % (m["evidence"] or m["blocking_reason"] or "-"))
                fp = m.get("run_fingerprint") or {}
                fh.write("  - بصمة التشغيل ⭐: `%s` ⭐ (سجل الباك `%s` ⭐ · سجل الواجهة `%s` ⭐)\n"
                         % (fp.get("be_sha", "-"), (fp.get("be_results_sha256") or "-")[:16],
                            (fp.get("fe_log_sha256") or "-")[:16]))
            fh.write("\n")
            fh.write("- حد القبول ⭐: **%.0f%%** ⭐ ⇒ النسبة الحالية **%.2f%%** ⭐ ⇒ %s ⭐\n"
                     % (ACCEPT_THRESHOLD_PCT, pct,
                        "متحقق ⭐" if payload["percent_meets_threshold"] else "**مش متحقق** ⭐"))
            fh.write("- البنود الإلزامية ⭐: %d/%d ⭐ ⇒ %s ⭐\n"
                     % (len(payload["mandatory"]) - len(unmet), len(payload["mandatory"]),
                        "كلها متحققة ⭐" if not unmet else "مش متحققة ⭐: " + " · ".join(unmet)))
            fh.write("- جاهزية المراجعة ⭐: **%s** ⭐\n\n"
                     % ("جاهز ⭐" if payload["ready_for_review"] else "مش جاهز ⭐"))
            if payload["not_ready_reasons"]:
                for r in payload["not_ready_reasons"]:
                    fh.write("  - ⛔ %s\n" % r)
                fh.write("\n")
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
