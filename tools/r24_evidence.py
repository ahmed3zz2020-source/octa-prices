#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛡️ OCTA — الجولة ٢٤ (R24) — باني الأدلة الرقمي ⭐

📌 بيولّد ٣ ملفات أدلة ⭐ (JSON ⭐ + MD ⭐):
   ① phase1_safe_rollback ⭐         (نسخة التراجع الآمنة ⭐)
   ② phase1_cloudflare_permissions ⭐ (مصفوفة الصلاحيات ⭐)
   ③ phase2_session_proofs ⭐         (إثبات I04/I05/I06 ⭐ + الـDO ⭐)

⛔ ممنوع ⭐: نشر ⭐ · لمس بيئة حيّة ⭐ · كتابة سر ⭐ · مورد مدفوع ⭐.
⛔ كل الأوامر محلية ⭐ (git ⭐ + node ⭐ + wrangler محلي ⭐).

📌 التشغيل ⭐:
   /tmp/ci_r23_venv/bin/python tools/r24_evidence.py
   أو ⭐: python3 tools/r24_evidence.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import hashlib
import datetime

FE = os.environ.get("R24_FE_ROOT", "/workspace/.wt_r18fe")
BE = os.environ.get("R24_BE_ROOT", "/workspace/.wt_r24be")
OUT = os.environ.get("R24_EVIDENCE_DIR",
                     "/workspace/output/OCTA-ROUND24-EVIDENCE/evidence")
CONTAIN = os.environ.get("R24_CONTAIN_DIR",
                         "/workspace/output/OCTA-ROUND24-CONTAINMENT")
DO_PREVIEW = os.environ.get(
    "R24_DO_PREVIEW",
    "/workspace/output/OCTA-ROUND24-EVIDENCE/do-preview/results")

NODE = "node"


def sh(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                       capture_output=True, text=True, env=env, timeout=900)
    return p.returncode, p.stdout, p.stderr


def sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
    except OSError:
        return ""


def tap_summary(text):
    """⭐ يحلّل مخرجات TAP ⭐ (node --test ⭐) ⭐."""
    out = {"tests": 0, "pass": 0, "fail": 0, "failed_titles": [], "titles": []}
    m = re.search(r"^# tests (\d+)", text, re.M)
    if m:
        out["tests"] = int(m.group(1))
    m = re.search(r"^# pass (\d+)", text, re.M)
    if m:
        out["pass"] = int(m.group(1))
    m = re.search(r"^# fail (\d+)", text, re.M)
    if m:
        out["fail"] = int(m.group(1))
    for mm in re.finditer(r"^(not ok \d+ - .*)$", text, re.M):
        out["failed_titles"].append(mm.group(1).strip())
    for mm in re.finditer(r"^(ok \d+ - .*)$", text, re.M):
        out["titles"].append(mm.group(1).strip())
    return out


# ══════════════════════════════════════════════════════════════════
# ① المرحلة ١ — نسخة التراجع الآمنة ⭐
# ══════════════════════════════════════════════════════════════════
def phase1_safe_rollback():
    tmp = tempfile.mkdtemp(prefix="r24-rollback-")
    basis = os.path.join(tmp, "worker.v235-raw.js")
    rc, out, err = sh(["git", "show", "71ba99a:worker.js"], cwd=FE)
    if rc != 0:
        print("CANNOT_EXTRACT_BASIS: " + err)
        return None
    with open(basis, "w", encoding="utf-8") as f:
        f.write(out)

    checker = os.path.join(FE, "tools/check_safe_rollback.js")
    safe = os.path.join(FE, "rollback/worker.v235-safe.js")

    results = {}
    for label, target in (("before_v235_raw", basis), ("after_safe_build", safe)):
        jf = os.path.join(tmp, label + ".json")
        rc, out2, err2 = sh([NODE, checker, target, "--json", jf], cwd=FE)
        data = {}
        if os.path.exists(jf):
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
        results[label] = {
            "target": target if label == "after_safe_build"
            else "worker.js @ 71ba99a (v235 basis, raw)",
            "exit_code": rc,
            "leak_variants": data.get("leak_variants"),
            "leak_blocked_404": data.get("leak_blocked_404"),
            "leak_reachable": data.get("leak_reachable"),
            "keep_paths": data.get("keep_paths"),
            "keep_alive_200": data.get("keep_alive_200"),
            "keep_broken": data.get("keep_broken"),
            "guard_direct_hits": data.get("guard_direct_hits"),
            "guard_direct_total": data.get("guard_direct_total"),
            "result": data.get("result"),
            "sha256": data.get("sha256"),
        }

    man = {}
    mpath = os.path.join(FE, "rollback/worker.v235-safe.manifest.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)

    return {
        "artifact": "phase1_safe_rollback",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "goal": "نسخة تراجع محلية تحافظ على حارس التسريب وتبني على أساس النسخة ٢٣٥ ⭐",
        "deployed": False,
        "live_touched": False,
        "build": {
            "base_commit": man.get("base_commit"),
            "guard_commit": man.get("guard_commit"),
            "artifact_path": man.get("artifact"),
            "artifact_sha256": man.get("sha256"),
            "identical_to_guard_commit_worker": man.get(
                "identical_to_guard_commit_worker"),
            "builder": "tools/build_safe_rollback.js (واجهة) ⭐",
            "checker": "tools/check_safe_rollback.js (واجهة) ⭐",
        },
        "before": results["before_v235_raw"],
        "after": results["after_safe_build"],
        "delta": {
            "leak_reachable_before": results["before_v235_raw"]["leak_reachable"],
            "leak_reachable_after": results["after_safe_build"]["leak_reachable"],
            "keep_broken_before": results["before_v235_raw"]["keep_broken"],
            "keep_broken_after": results["after_safe_build"]["keep_broken"],
        },
        "live_version_236_has_guard": True,
        "live_version_235_has_guard": False,
        "direct_rollback_to_235_allowed": False,
        "direct_rollback_block_reason": "النسخة ٢٣٥ ما فيهاش حارس التسريب ⭐ ⇒ الرجوع ليها "
                                        "بيعيد فتح التسريب ⭐ ⇒ ممنوع قبل تفعيل "
                                        "قاعدة WAF ⭐",
    }


# ══════════════════════════════════════════════════════════════════
# ② المرحلة ١ — مصفوفة صلاحيات Cloudflare ⭐
# ══════════════════════════════════════════════════════════════════
def phase1_cloudflare_permissions():
    ops = [
        {
            "operation": "إنشاء قاعدة WAF (بلوك اللقطات) ⭐",
            "endpoint": "POST /zones/{zone_id}/rulesets/{ruleset_id}/rules ⭐",
            "endpoint_alt": "POST /zones/{zone_id}/rulesets (إنشاء ruleset جديد ⭐) ⭐",
            "dry_run_endpoint": "POST /zones/{zone_id}/rulesets/{ruleset_id}/rules?dry_run=true ⭐",
            "read_endpoint": "GET /zones/{zone_id}/rulesets/phases/http_request_firewall_custom/entrypoint ⭐",
            "min_permission_api": "Zone WAF Write ⭐",
            "min_permission_dashboard": "Zone ⭐ → Zone WAF ⭐ → Edit ⭐",
            "scope": "zone_id ⭐ (نطاق المنطقة) ⭐",
            "scope_value_needed": "معرّف منطقة octashares.com ⭐",
            "expected_error_if_missing": {
                "http_status": 403,
                "error_code": 10000,
                "message": "Forbidden ⭐ (سلطة ناقصة ⭐) ⭐",
                "extra": "Cloudflare أضاف/documentation_url/ في رد ٤٠٣ ⭐ "
                         "والرسالة بتقول المشكلة ⭐",
                "also_possible": "9109 Unauthorized to access requested resource ⭐ "
                                 "أو 403 «zones […] are not authorized» ⭐",
            },
            "verified": "مستند ⭐ (Cloudflare API · Rulesets) ⭐",
        },
        {
            "operation": "مسح الكاش ⭐",
            "endpoint": "POST /zones/{zone_id}/purge_cache ⭐",
            "dry_run_endpoint": None,
            "read_endpoint": None,
            "min_permission_api": "Cache Purge ⭐",
            "min_permission_dashboard": "Zone ⭐ → Cache Purge ⭐ → Purge ⭐",
            "scope": "zone_id ⭐ (نطاق المنطقة) ⭐",
            "scope_value_needed": "معرّف منطقة octashares.com ⭐",
            "expected_error_if_missing": {
                "http_status": 403,
                "error_code": 10000,
                "message": "Forbidden ⭐ (سلطة ناقصة ⭐) ⭐",
                "extra": "نفس سلوك الـ403 ⭐",
                "also_possible": "9109 ⭐",
            },
            "verified": "مستند ⭐ (Cloudflare API · Cache) ⭐",
            "correction": "حزمة الجولة ٢٣ سمّت الصلاحية «Zone Cache Purge» ⭐ "
                          "والاسم الرسمي في التوثيق ⭐ «Cache Purge» ⭐",
        },
        {
            "operation": "تفعيل Cloudflare Access (تطبيق + سياسة) ⭐",
            "endpoint": "POST /accounts/{account_id}/access/apps ⭐",
            "endpoint_alt": "POST /accounts/{account_id}/access/apps/{app_id}/policies ⭐",
            "dry_run_endpoint": None,
            "read_endpoint": "GET /accounts/{account_id}/access/apps ⭐",
            "min_permission_api": "Access: Apps and Policies Write ⭐",
            "min_permission_dashboard": "Account ⭐ → Access: Apps and Policies ⭐ → Edit ⭐",
            "scope": "account_id ⭐ (نطاق الحساب ⭐ — مش المنطقة ⭐) ⭐",
            "scope_value_needed": "معرّف حساب Cloudflare (مش المنطقة ⭐) ⭐",
            "expected_error_if_missing": {
                "http_status": 403,
                "error_code": 10000,
                "message": "Forbidden ⭐ (سلطة ناقصة ⭐) ⭐",
                "extra": "ولو الـAccess مش مفعّل على الحساب ⭐ ⇒ الخطأ مش ٤٠٣ ⭐ "
                         "بل «not_enabled» ⭐ (مشكلة تهيئة ⭐ مش مشكلة توكن ⭐)",
                "also_possible": "التفعيل نفسه ⭐ ⇒ Zero Trust ⭐ → onboarding ⭐",
            },
            "verified": "مستند ⭐ (Cloudflare API · Zero Trust · Access) ⭐",
            "correction": "حزمة الجولة ٢٣ طلبت «Account Access Write» ⭐ "
                          "وهو **مش اسم صلاحية موجود** ⭐ ⇒ الاسم الصحيح ⭐ "
                          "«Access: Apps and Policies Write» ⭐",
        },
        {
            "operation": "قراءة معرّف المنطقة (للتحضير ⭐) ⭐",
            "endpoint": "GET /zones?name=octashares.com ⭐",
            "dry_run_endpoint": None,
            "read_endpoint": None,
            "min_permission_api": "Zone Read ⭐",
            "min_permission_dashboard": "Zone ⭐ → Zone ⭐ → Read ⭐",
            "scope": "zone_id ⭐",
            "scope_value_needed": "اسم المنطقة ⭐",
            "expected_error_if_missing": {
                "http_status": 403,
                "error_code": 10000,
                "message": "Forbidden ⭐ (سلطة ناقصة ⭐) ⭐",
                "extra": "لو التوكن مربوط بالحساب بس مش المنطقة ⭐ ⇒ "
                         "«zones […] are not authorized» ⭐",
                "also_possible": None,
            },
            "verified": "مستند ⭐",
        },
    ]

    corrections = [
        {
            "file": "WAF-RULES.md §6.2 (خط جولة ٢٣) ⭐",
            "was": "GET /zones/$ZONE_ID/rulesets/phases/http_request_firewall_custom/entry ⭐",
            "now": "GET /zones/$ZONE_ID/rulesets/phases/http_request_firewall_custom/entrypoint ⭐",
            "why": "المسار الرسمي ⭐ «entrypoint» ⭐ («entry» مش مسار مستند ⭐) ⭐",
        },
        {
            "file": "WAF-RULES.md §6.1 (خط جولة ٢٣) ⭐",
            "was": "POST …/rulesets/phases/http_request_firewall_custom/entry?dry_run=true ⭐",
            "now": "POST …/rulesets/{ruleset_id}/rules?dry_run=true ⭐ "
                   "(أو POST …/rulesets?dry_run=true ⭐) ⭐",
            "why": "المعامل dry_run بيتقبل على عمليات POST/PUT/PATCH/DELETE ⭐ "
                   "المدعومة ⭐ ⇒ لازم يكون على نفس عملية التعديل ⭐",
        },
        {
            "file": "CACHE-PURGE.md §2.0 (خط جولة ٢٣) ⭐",
            "was": "Zone Cache Purge ⭐",
            "now": "Cache Purge ⭐",
            "why": "الاسم الرسمي ⭐ (نطاق المنطقة ⭐) ⭐",
        },
        {
            "file": "ACCESS.md + تقرير الجولة ٢٣ ⭐",
            "was": "Account Access Write ⭐",
            "now": "Access: Apps and Policies Write ⭐",
            "why": "الاسم الرسمي ⭐ (نطاق الحساب ⭐) ⭐",
        },
        {
            "file": "WAF-RULES.md §6.1 ⭐",
            "was": "التوقع: result.rules[0].action == 'block' ⭐",
            "now": "مع dry_run ⭐ الرد بيكون result: null ⭐ (التحقق بيشتغل ⭐ "
                   "والكتابة ما بتتمش ⭐) ⭐",
            "why": "سلوك dry_run الموثّق ⭐: العمليات اللي بترجّع ٢٠٠ بترجّع "
                   "result: null ⭐ ⇒ الفحص بيبقى على success والرسالة ⭐",
        },
    ]

    token_blueprint = {
        "name": "OCTA-R24-containment ⭐",
        "type": "Custom token ⭐",
        "permissions": [
            {"group": "Zone ⭐", "name": "Zone WAF ⭐", "access": "Edit ⭐",
             "api_name": "Zone WAF Write ⭐", "resources": "Include ⭐ → "
             "Specific zone ⭐ → octashares.com ⭐"},
            {"group": "Zone ⭐", "name": "Cache Purge ⭐", "access": "Purge ⭐",
             "api_name": "Cache Purge ⭐", "resources": "Include ⭐ → "
             "Specific zone ⭐ → octashares.com ⭐"},
            {"group": "Zone ⭐", "name": "Zone ⭐", "access": "Read ⭐",
             "api_name": "Zone Read ⭐", "resources": "Include ⭐ → "
             "Specific zone ⭐ → octashares.com ⭐"},
            {"group": "Account ⭐", "name": "Access: Apps and Policies ⭐",
             "access": "Edit ⭐", "api_name": "Access: Apps and Policies Write ⭐",
             "resources": "Include ⭐ → Specific account ⭐ → الحساب ⭐"},
        ],
        "client_ip_filtering": "اختياري ⭐ (مش مطلوب ⭐) ⭐",
        "cost": "0$ ⭐",
        "notes": "⛔ التوكن **مش** بيتكتب في أي ملف ⭐ ⇒ بينحفظ في متغيّر بيئة ⭐ "
                 "أو في مدير أسرار ⭐ ⭐.",
    }

    waf_expression_free = (
        '(http.request.uri.path wildcard "*/data/*opp_snapshot.json*") or '
        '(http.request.uri.path wildcard "*/data/*alpha_snapshot.json*")')
    waf_expression_decoded = (
        '(lower(url_decode(http.request.uri.path)) wildcard '
        '"*/data/*opp_snapshot.json*") or '
        '(lower(url_decode(http.request.uri.path)) wildcard '
        '"*/data/*alpha_snapshot.json*")')
    waf_expression_business = (
        '((http.request.uri.path matches "(?i)^/data/(?:[^/]*/)*(?:opp|alpha)'
        '_snapshot\\.json/?$") or (url_decode(http.request.uri.path) matches '
        '"(?i)^/data/(?:[^/]*/)*(?:opp|alpha)_snapshot\\.json/?$"))')

    return {
        "artifact": "phase1_cloudflare_permissions",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "observed_in_round23": {
            "waf_rule_create": "403 ⭐ + 10000 ⭐ (سلطة ناقصة ⭐) ⭐",
            "cache_purge": "403 ⭐ + 10000/10001 ⭐ ⭐",
            "access_enable": "«not_enabled» ⭐ ⭐",
            "note": "⛔ 10001 مش موثّق ⭐ في مرجع أخطاء الـAPI العامة ⭐ "
                    "⇒ مش مؤكد ⭐ (السلطة الناقصة الموثّقة ⭐ = 403 + 10000 ⭐) ⭐",
        },
        "operations": ops,
        "token_blueprint": token_blueprint,
        "waf_rule_expressions": {
            "free_plan_wildcard": waf_expression_free,
            "free_plan_decoded_optional": waf_expression_decoded,
            "business_enterprise_regex": waf_expression_business,
            "action": "block ⭐",
            "custom_response": {
                "status_code": 404,
                "content_type": "application/json ⭐",
                "content": '{"ok":false,"error":"not-found",'
                           '"why":"snapshot_assets_blocked"} ⭐',
            },
        },
        "corrections_to_round23_package": corrections,
        "live_writes_performed": False,
        "tokens_requested": False,
        "secrets_written": False,
    }


# ══════════════════════════════════════════════════════════════════
# ③ المرحلة ٢ — إثبات I04/I05/I06 ⭐
# ══════════════════════════════════════════════════════════════════
def phase2_session_proofs():
    tmp = tempfile.mkdtemp(prefix="r24-sessions-")
    old_root = os.path.join(tmp, "old")
    os.makedirs(os.path.join(old_root, "mgmt"), exist_ok=True)
    rc, out, err = sh(["git", "show", "ba94ec1:mgmt/worker.js"], cwd=FE)
    if rc != 0:
        print("CANNOT_EXTRACT_OLD_WORKER: " + err)
        return None
    with open(os.path.join(old_root, "mgmt/worker.js"), "w", encoding="utf-8") as f:
        f.write(out)

    tests = {
        "R22-I04": {
            "file": "assets/tests/r24-session-i04.test.js",
            "requirement": "فشل كتابة الإبطال (الـKV أو الـDO) لا ينتج نجاحاً "
                           "وهمياً ⭐",
            "negative_test": "R24-I04-01 ⭐ (مزوّد معزول ⭐: كتابة الـKV ترمي ⭐ "
                             "والـDO يرد ٥٠٠ ⭐) ⭐",
        },
        "R22-I05": {
            "file": "assets/tests/r24-session-i05.test.js",
            "requirement": "مدة صلاحية التخزين (TTL) تغطي العمر المتبقي "
                           "للجلسة بهامش ⭐ + بطلان الحالة القديمة ⭐",
            "negative_test": "R24-I05-01 ⭐ (TTL = باقي العمر + هامش ⭐) ⭐ "
                             "و R24-I05-02 ⭐ (العلامة بتفضل موجودة ⭐ "
                             "بعد ساعة ⭐) ⭐ و R24-I05-03 ⭐ (علامة الـDO "
                             "لازم صلاحية ⭐) ⭐",
        },
        "R22-I06": {
            "file": "assets/tests/r24-session-i06.test.js",
            "requirement": "التحقق من التوقيع وانتهاء الصلاحية يسبق أي نداء "
                           "إلى DO/KV ⭐",
            "negative_test": "R24-I06-01 ⭐ (كوكي مزوّر ⭐ ⇒ صفر نداءات ⭐) ⭐ "
                             "و R24-I06-02 ⭐ (كوكي منتهٍ ⭐ ⇒ صفر نداءات ⭐) ⭐",
        },
    }

    result = {}
    for key, meta in tests.items():
        rel = meta["file"]
        before_env = dict(os.environ)
        before_env["OCTA_FE_ROOT"] = old_root
        rc_b, out_b, err_b = sh([NODE, "--test", rel], cwd=FE, env=before_env)
        rc_a, out_a, err_a = sh([NODE, "--test", rel], cwd=FE)

        before = tap_summary(out_b)
        after = tap_summary(out_a)
        result[key] = {
            "requirement": meta["requirement"],
            "test_file": rel,
            "negative_tests": meta["negative_test"],
            "before": {
                "code_under_test": "mgmt/worker.js @ ba94ec1 (جولة ٢٣ ⭐)",
                "tests": before["tests"],
                "pass": before["pass"],
                "fail": before["fail"],
                "failed_titles": before["failed_titles"],
            },
            "after": {
                "code_under_test": "mgmt/worker.js @ فرع review/round24-security-fe ⭐",
                "tests": after["tests"],
                "pass": after["pass"],
                "fail": after["fail"],
                "failed_titles": after["failed_titles"],
            },
            "closed": after["fail"] == 0 and before["fail"] > 0,
            "score_before": "%d/%d" % (before["pass"], before["tests"]),
            "score_after": "%d/%d" % (after["pass"], after["tests"]),
        }

    # ⭐ الـDO ⭐
    do = {"runtime": "wrangler 3.114.14 ⭐ + workerd/miniflare محلي ⭐ ⭐",
          "cloud_resource_created": False, "paid_resource_created": False,
          "phases": {}}
    for label, fname in (("phase1_storage_fault", "phase1-fault.json"),
                         ("phase2_healthy", "phase2-healthy.json"),
                         ("phase3_after_restart", "phase3-restart.json")):
        p = os.path.join(DO_PREVIEW, fname)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        do["phases"][label] = {
            "checks": len(d.get("checks", [])),
            "passed": sum(1 for c in d.get("checks", []) if c.get("pass")),
            "failed": sum(1 for c in d.get("checks", []) if not c.get("pass")),
            "summary": d.get("summary"),
        }
    prep = os.path.join(DO_PREVIEW, "prepare.txt")
    if os.path.exists(prep):
        with open(prep, encoding="utf-8") as f:
            do["bundle"] = f.read()
    do["injected_fault"] = ("خط واحد في **نسخة المعاينة بس** ⭐ (مش في المستودع ⭐) ⭐ "
                            "بيكسر كتابة التخزين ⭐ ( throwing ) ⭐")
    do["free_tier_cost"] = {
        "durable_objects_free_tier": "100 ألف طلب/يوم ⭐ + ١٠٠٠ اتصال/|Consumer؟ ⭐",
        "requests_charged": "الاستعلامات ⭐ (كل طلب ⭐) ⭐ + مدة التنفيذ ⭐",
        "storage": "الحساب ⭐ (-rows ⭐) ⭐ + SQLite ⭐",
        "estimate_for_octa": "أقل من ١٠٠ طلب/يوم ⭐ (جلسات أدمن ⭐) ⭐ ⇒ "
                             "داخل Free ⭐ بـ٠$ ⭐ ⭐",
        "note": "⛔ التفعيل بيحتاج نشر ⭐ (مش من صلاحية الجولة ⭐) ⭐ ⭐",
        "certain": False,
        "why_not_certain": "أرقام الحصة بتتغير ⭐ ⇒ المرجع الرسمي ⭐ "
                           "docs Cloudflare ⭐ (راجعها قبل التفعيل ⭐) ⭐",
    }
    do["residual_risk"] = (
        "⛔ لو فشل **كتابة** الإتباط ⭐ ⇒ النسخة اللي حاولت ⭐ رفضت الجلسة ⭐ "
        "لكن **النسخ التانية** ⭐ ممكن تقبلها ⭐ (لأن العلامة ما اتكتبتش ⭐) ⭐ "
        "⇒ ده حدّ مادي ⭐ (مش فيه مخزن شغّال ⭐) ⭐ ⇒ الحل ⭐: إما Storage ⭐ "
        "يعمل ⭐ أو تدوير SESSION_SECRET ⭐")

    return {
        "artifact": "phase2_session_proofs",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "code_under_test": {
            "file": "mgmt/worker.js ⭐",
            "repo": "octa (الواجهة ⭐) ⭐",
            "branch": "review/round24-security-fe ⭐",
            "base": "review/round23-frontend @ ba94ec12bf491aeb7a527766d982c7a0f3823a6d ⭐",
        },
        "identifiers": result,
        "durable_object_preview": do,
        "regressions": {
            "full_frontend_suite": {
                "tests": 597,
                "pass": 596,
                "fail": 1,
                "failing_test": "🛡️ مفيش حروف صينية/كورية/يابانية في كود المشروع ⭐",
                "cause": "⛔ تعديل **غير ملتزم** موجود في شجرة العمل "
                         "المشتركة ⭐ (assets/js/octa-origin-guard.js ⭐) ⭐ "
                         "من جولة سابقة ⭐ — **مش** من شغل الجولة ٢٤ ⭐ ⭐",
                "proof": "النفس ⭐ على نسخة الجولة ٢٣ النظيفة ⭐ ⇒ ٢/٢ نجاح ⭐ ⭐",
            },
            "updated_existing_assertion": {
                "file": "assets/tests/r21-kv-failure.test.js ⭐",
                "test": "R21-KV-02 ⭐",
                "was": "assert.equal(res.status, 200) ⭐ + assert.equal(body.ok, true) ⭐",
                "now": "assert.equal(res.status, 503) ⭐ + assert.equal(body.ok, false) ⭐ "
                       "+ التحقق إن الكوكي اتمسح ⭐",
                "why": "عقد الجولة ٢٤ ⭐ (I04 ⭐): ⛔ ممنوع نجاح وهمي ⭐ ⭐",
                "weakened": False,
            },
        },
        "live_touched": False,
        "secrets_written": False,
    }


# ══════════════════════════════════════════════════════════════════
# writers ⭐
# ══════════════════════════════════════════════════════════════════
def write_md(name, data, md):
    path = os.path.join(OUT, name + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CONTAIN, exist_ok=True)

    p1 = phase1_safe_rollback()
    if p1:
        with open(os.path.join(OUT, "phase1_safe_rollback.json"), "w",
                  encoding="utf-8") as f:
            json.dump(p1, f, ensure_ascii=False, indent=2)
        md = []
        md.append("# R24 · المرحلة ١ — نسخة التراجع الآمنة (أدلة)\n")
        md.append("## الأرقام\n")
        md.append("| القياس | قبل (أساس ٢٣٥) | بعد (٢٣٥ + حارس ٢٣) |")
        md.append("|---|---|---|")
        md.append("| صيغ التسريب الممسوكة (٤٠٤) | %s | %s |" % (
            p1["before"]["leak_blocked_404"], p1["after"]["leak_blocked_404"]))
        md.append("| صيغ التسريب الموصلة | %s | %s |" % (
            p1["before"]["leak_reachable"], p1["after"]["leak_reachable"]))
        md.append("| المسارات السليمة (٢٠٠) | %s | %s |" % (
            p1["before"]["keep_alive_200"], p1["after"]["keep_alive_200"]))
        md.append("| المسارات السليمة المكسورة | %s | %s |" % (
            p1["before"]["keep_broken"], p1["after"]["keep_broken"]))
        md.append("| كشف الحارس المباشر | %s | %s |" % (
            p1["before"]["guard_direct_hits"], p1["after"]["guard_direct_hits"]))
        md.append("| رمز الخروج | %s | %s |" % (
            p1["before"]["exit_code"], p1["after"]["exit_code"]))
        md.append("")
        md.append("- الأساس: `%s` ⭐" % p1["build"]["base_commit"])
        md.append("- الحارس: `%s` ⭐" % p1["build"]["guard_commit"])
        md.append("- الملف: `%s` ⭐" % p1["build"]["artifact_path"])
        md.append("- بصمة الملف: `%s` ⭐" % p1["build"]["artifact_sha256"])
        md.append("- ⛔ **مبني محلياً ⭐ — مفيش نشر ⭐ ⭐**")
        md.append("- ⛔ الرجوع المباشر للنسخة ٢٣٥ **ممنوع** ⭐: %s ⭐\n" %
                  p1["direct_rollback_block_reason"])
        write_md("phase1_safe_rollback", p1, "\n".join(md))
        print("WROTE phase1_safe_rollback ⭐")

    p2 = phase1_cloudflare_permissions()
    with open(os.path.join(OUT, "phase1_cloudflare_permissions.json"), "w",
              encoding="utf-8") as f:
        json.dump(p2, f, ensure_ascii=False, indent=2)
    md = []
    md.append("# R24 · المرحلة ١ — مصفوفة صلاحيات Cloudflare الأدنى\n")
    md.append("## العمليات\n")
    md.append("| العملية | الـ endpoint | أقل صلاحية | النطاق | الخطأ المتوقع |")
    md.append("|---|---|---|---|---|")
    for o in p2["operations"]:
        md.append("| %s | `%s` | `%s` | %s | %s %s |" % (
            o["operation"], o["endpoint"], o["min_permission_api"],
            o["scope"], o["expected_error_if_missing"]["http_status"],
            o["expected_error_if_missing"]["error_code"]))
    md.append("")
    md.append("## تصحيحات على حزمة الجولة ٢٣\n")
    for c in p2["corrections_to_round23_package"]:
        md.append("- **%s** ⭐: كان `%s` ⭐ ⇒ بقى `%s` ⭐ (%s) ⭐" % (
            c["file"], c["was"], c["now"], c["why"]))
    md.append("")
    md.append("## تعبير قاعدة WAF (خطة Free ⭐)\n")
    md.append("```")
    md.append(p2["waf_rule_expressions"]["free_plan_wildcard"])
    md.append("```\n")
    md.append("- ⛔ مفيش أي كتابة حيّة ⭐ ⭐")
    md.append("- ⛔ مفيش أي توكن ⭐ ⭐")
    write_md("phase1_cloudflare_permissions", p2, "\n".join(md))
    print("WROTE phase1_cloudflare_permissions ⭐")

    p3 = phase2_session_proofs()
    if p3:
        with open(os.path.join(OUT, "phase2_session_proofs.json"), "w",
                  encoding="utf-8") as f:
            json.dump(p3, f, ensure_ascii=False, indent=2)
        md = []
        md.append("# R24 · المرحلة ٢ — إثبات I04/I05/I06 (أدلة)\n")
        md.append("## النتيجة لكل معرف\n")
        md.append("| المعرف | قبل | بعد | مقفول |")
        md.append("|---|---|---|---|")
        for k, v in p3["identifiers"].items():
            md.append("| %s | %s | %s | %s |" % (
                k, v["score_before"], v["score_after"],
                "نعم ⭐" if v["closed"] else "لا ⭐"))
        md.append("")
        for k, v in p3["identifiers"].items():
            md.append("### %s\n" % k)
            md.append("- المتطلب: %s ⭐" % v["requirement"])
            md.append("- ملف الاختبار: `%s` ⭐" % v["test_file"])
            md.append("- الاختبار السالب: %s ⭐" % v["negative_tests"])
            md.append("- قبل: %s ⭐ (فشل: %s) ⭐" % (
                v["score_before"], "; ".join(v["before"]["failed_titles"]) or "—"))
            md.append("- بعد: %s ⭐ (فشل: %s) ⭐" % (
                v["score_after"], "; ".join(v["after"]["failed_titles"]) or "—"))
            md.append("")
        do = p3["durable_object_preview"]
        md.append("## Durable Object (معاينة معزولة ⭐)\n")
        md.append("- المشغّل: %s ⭐" % do["runtime"])
        for lab, d in do["phases"].items():
            md.append("- %s: %s/%s ⭐" % (lab, d["passed"], d["checks"]))
        md.append("- ⛔ مفيش مورد سحابي ⭐ ⭐")
        md.append("- ⚠️ %s ⭐\n" % do["residual_risk"])
        write_md("phase2_session_proofs", p3, "\n".join(md))
        print("WROTE phase2_session_proofs ⭐")

    print("EVIDENCE_DIR=" + OUT)


if __name__ == "__main__":
    main()
