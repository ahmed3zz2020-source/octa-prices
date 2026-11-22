#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R31 · دفعة الإصلاح الواحدة — اختبارات قابلة للتكرار ⭐ (٣ بنود).

📌 البنود ⭐:
   ① ⭐ باقة Pro بلا تاريخ انتهاء ⭐ ⇒ ⛔ free ⭐ (fail-closed ⭐) ⭐ + التوثيق ⭐.
   ② ⭐ سباق فحص الكتابة ⭐ (FINDING-23 ⭐) ⭐ في ٦ وحدات ⭐ ⇒ ⭐ نفس مجلد البيانات ⭐.
   ③ ⭐ إصدار الجلسة بالبصمة وحدها ⭐ ⇒ ⛔ لازم توثيق بالرقم ⭐ **على نفس الجهاز** ⭐.

⛔ العزل ⭐: كل الملفات في مجلد مؤقت ⭐ · مافيش بيانات حقيقية ⭐ · مافيش أسرار ⭐.
📌 التشغيل ⭐: ⭐ python3 tools/test_r31_batch.py ⭐
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TMP = tempfile.mkdtemp(prefix="octa_r31_")

os.environ["OCTA_DATA_DIR"] = str(TMP)
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r31-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r31-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["MAIL_ON"] = "0"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"
sys.path.insert(0, str(REPO))

RESULTS = []


def ok(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": detail})
    print("%s  %s%s" % ("PASS" if cond else "FAIL", name,
                        ("  ::  " + detail) if detail else ""))
    return bool(cond)


def section(title):
    print("\n=== %s ===" % title)


# ══════════════════════════════════════════════════════════════════
#  ① — الباقة: Pro بلا تاريخ انتهاء ⇒ free (fail-closed)
# ══════════════════════════════════════════════════════════════════
section("① — سياسة الباقة Pro عند غياب تاريخ الانتهاء")
import plan_gate as pg  # noqa: E402

now = int(time.time())
ok("Pro بلا تاريخ انتهاء ⇒ free",
   pg.plan_of({"plan": "pro"}) == "free", "plan_of=%s" % pg.plan_of({"plan": "pro"}))
ok("Pro بتاريخ انتهاء غير رقمي ⇒ free",
   pg.plan_of({"plan": "pro", "plan_until": "abc"}) == "free")
ok("Pro بتاريخ انتهاء = صفر ⇒ free",
   pg.plan_of({"plan": "pro", "plan_until": 0}) == "free")
ok("Pro بتاريخ انتهاء منتهٍ ⇒ free",
   pg.plan_of({"plan": "pro", "plan_until": now - 10}) == "free")
ok("Pro بتاريخ انتهاء صالح ⇒ pro",
   pg.plan_of({"plan": "pro", "plan_until": now + 3600}) == "pro")
ok("resolve_plan (بلا checker) ⇒ free عند غياب التاريخ",
   pg.resolve_plan({"plan": "pro"}) == "free")
st = pg.status_of({"plan": "pro"})
ok("status_of ⇒ plan=free عند غياب التاريخ", st.get("plan") == "free",
   "status=%s" % json.dumps(st, ensure_ascii=False))
ok("resolve_plan مع checker شلط ⇒ free",
   pg.resolve_plan({"plan": "pro"}, checker=lambda u: "nonsense") == "free")
doc = (pg.__doc__ or "")
ok("التوثيق بيذكر قاعدة «مافيش تاريخ انتهاء ⇒ free»",
   "مافيش تاريخ انتهاء" in doc)
ok("التوثيق بيذكر إن التفعيل يدوي (مفيش بوابة دفع)",
   "يدوي إداري" in doc and "Stripe" in doc)
ok("التوثيق بيذكر حقول السجل",
   all(k in doc for k in ("uid", "email", "plan", "days", "price", "method", "note", "at")))

# ══════════════════════════════════════════════════════════════════
#  ② — سباق فحص الكتابة في ٦ وحدات (FINDING-23)
# ══════════════════════════════════════════════════════════════════
section("② — سباق فحص قابلية الكتابة (٦ وحدات)")
CHILD = r'''
import os, sys
sys.path.insert(0, os.environ["OCTA_REPO"])
name = os.environ["OCTA_MOD"]
m = __import__(name)
if name == "subscription_core":
    d = m._default_data_dir()
else:
    d = m.DATA_DIR
print("DIR=%s" % d)
print("PROBE_ERR=%s" % getattr(m, "DATA_DIR_PROBE_ERROR", None))
'''

MODULES = ["pattern_challenges", "pattern_daily", "pattern_studio",
           "pattern_zones", "plan_gate", "subscription_core"]

# ⭐⭐⭐ (R31) ⭐⭐⭐ برهان **حتمي** ⭐⭐⭐ — محاكاة «حذف من عملية تانية» ⭐⭐⭐
# 📌 السبب ⭐: ⛔ السباق الحقيقي ⭐ (زي R29 ⭐ 4/15 ⭐) بيحصل لما ⭐ ⭐
#    ⭐ عملية تانية ⭐ ⭐ تمسح ملف الفحص ⭐ ⭐ قبل ما ⭐ ⭐ `unlink()` ⭐ ⭐
#    ⭐ ⭐ بتنفّذ ⭐ ⭐ ⇒ ⭐ ⭐ `FileNotFoundError` ⭐ ⭐ ⇒ ⭐ ⭐ الـfallback ⭐ ⭐.
# 📌 المحاكاة ⭐: ⭐ نخلي `unlink` ⭐ ⭐ يرمي ⭐ ⭐ (زي ما كان هيحصل ⭐ ⭐)
#    ⭐ ⭐ ⇒ ⭐ ⭐ النتيجة **حتمية** ⭐ ⭐ (مش احتمالية ⭐ ⭐) ⭐ ⭐.
CHILD_SYNC = r'''
import os, sys, pathlib
sys.path.insert(0, os.environ["OCTA_REPO"])
_target = os.environ["OCTA_DATA_DIR"]
_orig = pathlib.PosixPath.unlink
def _patched(self, *a, **kw):
    _same = False
    try:
        _same = (str(self.parent) == _target)
    except Exception:
        _same = False
    if _same:
        raise FileNotFoundError("simulated concurrent delete")
    return _orig(self, *a, **kw)
pathlib.PosixPath.unlink = _patched
name = os.environ["OCTA_MOD"]
m = __import__(name)
d = m._default_data_dir() if name == "subscription_core" else m.DATA_DIR
print("DIR=%s" % d)
'''

for mod in ["subscription_core"]:
    tmp = Path(tempfile.mkdtemp(prefix="r31_sync_"))
    env = dict(os.environ)
    env["OCTA_DATA_DIR"] = str(tmp)
    env["OCTA_REPO"] = str(REPO)
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONIOENCODING"] = "utf-8"
    env["OCTA_MOD"] = mod
    proc = subprocess.run([sys.executable, "-c", CHILD_SYNC], env=env,
                          capture_output=True, text=True, timeout=300)
    got = ""
    for line in (proc.stdout or "").splitlines():
        if line.startswith("DIR="):
            got = line[4:].strip()
    ok("%s ⇒ حذف متزامن محاكى ⇒ بيفضل في مجلد البيانات (مش fallback)"
       % mod, got == str(tmp), "dir=%s" % got)

for mod in MODULES:
    dirs = []
    errs = []
    tmp = Path(tempfile.mkdtemp(prefix="r31_probe_"))
    procs = []
    for _ in range(8):
        env = dict(os.environ)
        env["OCTA_DATA_DIR"] = str(tmp)
        env["OCTA_REPO"] = str(REPO)
        env["PYTHONPATH"] = str(REPO)
        env["PYTHONIOENCODING"] = "utf-8"
        env["OCTA_MOD"] = mod
        procs.append(subprocess.Popen([sys.executable, "-c", CHILD], env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    for p in procs:
        out, _err = p.communicate(timeout=300)
        for line in (out or "").decode("utf-8", "replace").splitlines():
            if line.startswith("DIR="):
                dirs.append(line[4:].strip())
            if line.startswith("PROBE_ERR="):
                errs.append(line[10:].strip())
    same = len(dirs) == 8 and len(set(dirs)) == 1 and set(dirs) == {str(tmp)}
    ok("%s ⇒ نفس مجلد البيانات في ٨ عمليات متوازية" % mod, same,
       "dirs=%s" % sorted(set(dirs)))
    ok("%s ⇒ مافيش خطأ فحص (fallback)" % mod,
       all(e in ("None", "") for e in errs), "errs=%s" % sorted(set(errs)))

# ══════════════════════════════════════════════════════════════════
#  ③ — إصدار الجلسة بالبصمة وحدها (لازم توثيق بالرقم على نفس الجهاز)
# ══════════════════════════════════════════════════════════════════
section("③ — إصدار الجلسة بالبصمة وحدها")
import update_prices as up  # noqa: E402

up.USERS_FILE = Path(TMP) / "users.json"
up.PINLOCK_FILE = Path(TMP) / "pinlock.json"
up.PIN_PEPPER_FILE = Path(TMP) / "pin_pepper.txt"
up.FINGERPRINT_LOGIN_ON = True

client = up.app.test_client()
DEV = "r31-device-key-0123456789abcdef"
uid = "u_r31_fp"
with up.USERS_LOCK:
    _u = up._load_users()
    _u[uid] = {"id": uid, "name": "r31", "email": "r31@example.test",
               "token_epoch": 0,
               "bio_hash": up._device_key_hash(DEV),
               "bio_hashes": [up._device_key_hash(DEV)],
               "pin_ok_at": int(time.time())}
    up._save_users(_u)

r = client.post("/api/auth/pin/fingerprint", json={"device": DEV})
ok("بصمة + توثيق بالرقم على **جهاز تاني** ⇒ 401", r.status_code == 401,
   "status=%s" % r.status_code)
ok("السبب need_pin", (r.get_json() or {}).get("why") == "need_pin")
ok("مافيش توكن في الرد", not (r.get_json() or {}).get("token"))

with up.USERS_LOCK:
    _u = up._load_users()
    _u[uid]["pin_ok_dev"] = up._device_key_hash(DEV)
    up._save_users(_u)

r = client.post("/api/auth/pin/fingerprint", json={"device": DEV})
ok("بصمة + توثيق بالرقم على **نفس الجهاز** ⇒ 200", r.status_code == 200,
   "status=%s" % r.status_code)
ok("فيه توكن جلسة", bool((r.get_json() or {}).get("token")))

# ⛔ توثيق قديم (خارج النافذة) ⇒ 401
with up.USERS_LOCK:
    _u = up._load_users()
    _u[uid]["pin_ok_at"] = int(time.time()) - 100000
    up._save_users(_u)
r = client.post("/api/auth/pin/fingerprint", json={"device": DEV})
ok("بصمة + توثيق قديم ⇒ 401", r.status_code == 401,
   "status=%s" % r.status_code)

# ══════════════════════════════════════════════════════════════════
#  الخلاصة
# ══════════════════════════════════════════════════════════════════
passed = sum(1 for x in RESULTS if x["ok"])
failed = len(RESULTS) - passed
print("\n=== R31: %d/%d ناجح · %d فاشل ===" % (passed, len(RESULTS), failed))
sys.exit(1 if failed else 0)
