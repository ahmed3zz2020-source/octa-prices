#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪🛡️ اختبارات ارتدادية — المراجعة المستقلة (١٥ نوفمبر ٢٠٢٦)

⛔⛔⛔ كل الطلبات على الـStaging المعزول ⬇️ ⬇️ ⬇️
   ⛔ الحسابات وهمية · ⛔ مافيش أي طلب على الإنتاج · ⛔ الإيميل Mock

🔴Three-Er-Bugs fix:
   ①Tasks الخلفية: القرار لازم يتحسب **مرة واحدة** ⇒ القائد يشغّل الـ5 كلهم
     (القديم: [false×5] ⇒ مهمة واحدة بس هي اللي بتشتغل)
   ②Tasks الخلفية: أي تعذّر في القفل ⇒ **fail-closed** + سبب في اللوج
     (القديم: بيرجّع True ⇒ المهام بتشتغل من غير ضمان القفل)
   ③users.json: ملف تالف ⇒ **مفيش نجاح مضلّل** (503 مش 200/401)
     و**مفيش فقد بيانات** (الملف التالف ما بيتكتبش فوقه)

🧪 كل حالة هنا **برهان سالب**: لازم تفشل على الكود القديم.
"""
import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import staging_probe  # noqa: E402

ROOT = Path(__file__).resolve().parent
CFG = json.loads(Path(os.environ.get(
    "STAGE_CONFIG", "/workspace/.staging/staging-config.json")).read_text("utf-8"))
BASE = os.environ.get("STAGE_URL", "http://127.0.0.1:8099").rstrip("/")
PROXY = CFG["proxy_secret"]

# ⛔ الجولة ٢٤ (R24) — مجلد البيانات من **السيرفر** مش من ملف قديم ⇐
#  📌 probe «users.json تالف» لازم يفحص الملف اللي **السيرفر بيقراه**
#  📌 فعلاً ⇐ وإلا الرجوع 200 بدل 503 ⇐ والاختبار يفشل ⇐ سبب بيئي
DATA_DIR, OUTBOX, ENV_SOURCE = staging_probe.resolve_paths(BASE, PROXY, CFG)
USERS_FILE = DATA_DIR / "users.json"

RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""))
    return bool(cond)


def section(t):
    print("\n" + "─" * 64)
    print("  " + t)
    print("─" * 64)


def H(extra=None, proxy=True):
    h = {"Content-Type": "application/json"}
    if proxy:
        h["X-OCTA-Proxy"] = PROXY
    if extra:
        h.update(extra)
    return h


def post(path, body=None, headers=None, proxy=True):
    return requests.post(BASE + path, json=body or {}, headers=H(headers, proxy),
                         timeout=45)


# ─────────────────────────────────────────────────────────────────────────────
# 🧪 وحدة: تشغيل كود تبعز في عملية منفصلة ⇒ مافيش استيراد جانبي
# ─────────────────────────────────────────────────────────────────────────────
CHILD_PRE = """import json, os, sys, tempfile, pathlib
d = pathlib.Path(os.environ.get('BG_DATA_DIR') or tempfile.mkdtemp(prefix='octa_bg_'))
d.mkdir(parents=True, exist_ok=True)
os.environ['OCTA_DATA_DIR'] = str(d)
os.environ['OCTAD_TOKEN_SECRET'] = 'STG-unit-test'
os.environ['OCTA_PIN_PEPPER'] = 'STG-unit-test-pepper'
os.environ['OCTA_WARMUP'] = '0'
os.environ['OCTA_BG_TASKS'] = os.environ.get('BG_TASKS', '')
sys.path.insert(0, %r)
os.chdir(%r)
import update_prices as up
""" % (str(ROOT), str(ROOT))


def run_child(code, env=None, timeout=180):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-c", CHILD_PRE + code],
                       capture_output=True, text=True, timeout=timeout, env=e)
    return p.stdout, p.stderr


def child_json(stdout, key="BG_RESULT"):
    for line in stdout.splitlines():
        if line.startswith(key + " "):
            try:
                return json.loads(line[len(key) + 1:])
            except Exception:
                return None
    return None


def main():
    print("🧪 اختبارات ارتدادية — القائد + fail-closed + سلامة users.json")
    print("   ⛔ القاعدة: %s" % BASE)
    # ⛔ الجولة ٢٤ — تشخيص مصدر المسارات (معلومة · مش assertion)
    print("   📍 مجلد البيانات: %s (%s)" % (DATA_DIR, ENV_SOURCE))
    print("   📍 users.json: %s" % USERS_FILE)

    # ─────────────────────────────────────────────────────────────────────────
    section("① القائد: قرار واحد ⇒ الـ5 مهام كلها تشتغل")
    out, err = run_child(
        "res = [up._bg_tasks_allowed() for _ in range(5)]\n"
        "print('BG_RESULT ' + json.dumps({'calls': res}))\n")
    j = child_json(out) or {}
    calls = j.get("calls") or []
    ok(len(calls) == 5 and all(calls),
       "①Leader:five calls in one process⇒all true",
       calls)
    ok(calls.count(True) == 5,
       "①Leader:none of the five tasks was blocked",
       calls)

    # ─────────────────────────────────────────────────────────────────────────
    section("② القائد: نسخة تانية ⇒ مش هي اللي تشغّل المهام")
    shared = Path("/tmp/octa_bg_shared_%d" % int(time.time()))
    shared.mkdir(parents=True, exist_ok=True)
    e = dict(os.environ)
    e["BG_DATA_DIR"] = str(shared)
    holder = subprocess.Popen(
        [sys.executable, "-c", CHILD_PRE +
         "up._bg_tasks_allowed()\nprint('BG_LOCKED', flush=True)\n"
         "import time; time.sleep(30)\n"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=e)
    try:
        locked = False
        for _ in range(120):
            line = holder.stdout.readline()
            if "BG_LOCKED" in line:
                locked = True
                break
        ok(locked, "②second process:the lock was taken by the first process")
        out2, err2 = run_child(
            "res = [up._bg_tasks_allowed() for _ in range(5)]\n"
            "print('BG_RESULT ' + json.dumps({'calls': res}))\n",
            env={"BG_DATA_DIR": str(shared)})
        j2 = child_json(out2) or {}
        calls2 = j2.get("calls") or []
        ok(len(calls2) == 5 and not any(calls2),
           "②second process:all five calls are false", calls2)
        ok("نسخة تانية" in out2 or "نسخة تانية" in err2,
           "②second process:a clear reason was logged",
           (out2 + err2)[-200:])
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=10)
        except Exception:
            holder.kill()
        shutil.rmtree(shared, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────────────
    section("③ fail-closed: القفل مش متاح ⇒ مفيش مهام + سبب واضح")
    blocked = Path("/tmp/octa_bg_blocked_%d" % int(time.time()))
    blocked.mkdir(parents=True, exist_ok=True)
    (blocked / ".bg_tasks.lock").mkdir()      # ⛔ ملف القفل مستحيل يُفتح
    out3, err3 = run_child(
        "res = [up._bg_tasks_allowed() for _ in range(5)]\n"
        "print('BG_RESULT ' + json.dumps({'calls': res}))\n",
        env={"BG_DATA_DIR": str(blocked)})
    j3 = child_json(out3) or {}
    calls3 = j3.get("calls") or []
    ok(len(calls3) == 5 and not any(calls3),
       "③fail-closed:the tasks did not run", calls3)
    ok("ملف القفل مش متاح" in (out3 + err3),
       "③fail-closed:a clear reason was logged", (out3 + err3)[-200:])
    shutil.rmtree(blocked, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────────────
    section("④ kill-switch: OCTA_BG_TASKS=off ⇒ مفيش مهام")
    out4, err4 = run_child(
        "res = [up._bg_tasks_allowed() for _ in range(5)]\n"
        "print('BG_RESULT ' + json.dumps({'calls': res}))\n",
        env={"BG_TASKS": "off"})
    j4 = child_json(out4) or {}
    calls4 = j4.get("calls") or []
    ok(len(calls4) == 5 and not any(calls4),
       "④kill-switch:all calls are false", calls4)

    # ─────────────────────────────────────────────────────────────────────────
    section("⑤ users.json تالف ⇒ مفيش نجاح مضلّل ولا فقد بيانات")
    backup = USERS_FILE.read_bytes()
    original_login_ok = False
    try:
        USERS_FILE.write_text("{ this is not json", encoding="utf-8")

        # ⑤أ التسجيل: لازم يرجّع خطأ صريح (503) مش «نجاح»
        r = post("/api/auth/register", {"name": "t", "key": "482913",
                                        "email": "corrupt.test@example.test"})
        j5 = r.json() if r.headers.get("content-type", "").startswith(
            "application/json") else {}
        ok(r.status_code == 503,
           "⑤aRegister:a clear 503 instead of a fake success",
           "%s %s" % (r.status_code, j5))
        ok(j5.get("ok") is False,
           "⑤aRegister:ok=false", j5)

        # ⑤ب الدخول: لازم 503 مش 401 «كود غلط»
        r2 = post("/api/auth/pin/login",
                  {"pin": CFG["free"]["pin"], "device": CFG["free"]["device"]})
        j6 = r2.json() if r2.headers.get("content-type", "").startswith(
            "application/json") else {}
        ok(r2.status_code != 401,
           "⑤bLogin:not a misleading 401 (wrong PIN)", r2.status_code)
        ok(r2.status_code == 503,
           "⑤bLogin:a clear 503", "%s %s" % (r2.status_code, j6))

        # ⑤ج الملف التالف ما اتكتبش فوقه (مفيش فقد بيانات)
        after = USERS_FILE.read_bytes()
        ok(after == b"{ this is not json",
           "⑤cNo overwrite:the corrupt file was left untouched", after[:60])

        # ⑤د الملف مش متغيّرSized (ما اتفتحش للكتابة)
        ok(len(after) == len(b"{ this is not json"),
           "⑤cNo data loss:the file size is unchanged", len(after))
    finally:
        USERS_FILE.write_bytes(backup)

    # ─────────────────────────────────────────────────────────────────────────
    section("⑥ بعد الإصلاح: البيانات سليمة والدخول شغّال تاني")
    ok(USERS_FILE.read_bytes() == backup,
       "⑥Restore:the file is byte-identical to the backup")
    r3 = post("/api/auth/pin/login",
              {"pin": CFG["free"]["pin"], "device": CFG["free"]["device"]})
    j7 = r3.json() if r3.headers.get("content-type", "").startswith(
        "application/json") else {}
    original_login_ok = bool(j7.get("token"))
    ok(original_login_ok, "⑥Restore:login works again", j7)

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("=" * 64)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)" % (passed, failed, len(RESULTS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
