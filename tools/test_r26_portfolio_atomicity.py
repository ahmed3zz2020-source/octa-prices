#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
\U0001f41e\U0001f6e1\ufe0f \u0627\u0644\u062c\u0648\u0644\u0629 \u0662\u0666 (R26) \u2014 \u0630\u0631\u064a\u0629 \u0627\u0644\u0645\u062d\u0641\u0638\u0629 \u0628\u064a\u0646 \u0627\u0644\u0639\u0645\u0644\u064a\u0627\u062a

\U0001f4d7 \u0627\u0644\u0639\u064a\u0628 \u0627\u0644\u0645\u0642\u064a\u0633 \U0001f41e:
   `threading.RLock` \u2b50 \u064a\u062d\u0645\u064a **\u0627\u0644\u062e\u064a\u0648\u0637 \u0641\u064a \u0646\u0641\u0633 \u0627\u0644\u0639\u0645\u0644\u064a\u0629** \u2b50 \u0628\u0633 \u21d2
   \u26d4\u26d4 \u0645\u0627\u0628\u064a\u0634 \u064a\u0639\u0645\u0644 \u0634\u064a \u0628\u064a\u0646 **\u062c\u0631\u064a\u062a\u064a\u0646 \u0645\u062e\u062a\u0644\u0641\u0627\u062a** \u2b50 \u0639\u0644\u0649 \u0646\u0641\u0633
   `users.json` \u2b50 \u21d2 \u26d4\u26d4 **lost update** \u2b50 \u21d2 \u26d4\u26d4 \u0645\u0633\u0627\u062d\u0629 \u0628\u064a\u0627\u0646\u0627\u062a \u0623\u062e\u0631\u0649.

\u2705 \u0627\u0644\u062d\u0644 \U0001f41e: \u0642\u0641\u0644 **\u0645\u0644\u0641** \U0001f41e (`fcntl.flock` \U0001f41e) \u2b50 reentrant \u2b50 \u21d2 \u2b50 \u0627\u0644\u0625\u0628\u0637\u0627\u0631 \u064a\u0642\u064a\u064a \u0628\u064a\u0646
   \u0627\u0644\u062e\u064a\u0648\u0637 \u0648\u0627\u0644\u0639\u0645\u0644\u064a\u0627\u062a \u2b50 \u0645\u0639\u0627 \u2b50.

\U0001f4d7 \u0627\u0644\u0642\u064a\u0627\u0633 \U0001f41e:
   \u2460 \u0630\u0631\u064a\u0629 \u0628\u064a\u0646 \u0639\u0645\u0644\u064a\u062a\u064a\u0646 \U0001f41e \u2014 \u0639\u0645\u0644\u0627\u0646 \u0639\u0627\u0644\u0645 \u2b50 \u00d7 \u0662\u0660 \u0639\u0645\u0644\u0629 \u2b50 \u064a\u0643\u062a\u0628\u0648\u0627 \u0645\u062d\u0631\u0643\u0629 \u2b50
   \u2461 \u0645\u0644\u0641 `users.json` \u0644\u0627 \u064a\u062d\u062a\u0641\u0638 \u0639\u0644\u0649 NaN / Infinity \u2b50 (\u0627\u0644\u062e\u0631\u0627\u0621 \u064a\u0643\u062a\u0628 `NaN` \u2b50 \u21d2 \u26d4\u26d4 JSON \u063a\u064a\u0631 \u0635\u062d\u064a\u062d)
   \u2462 \u0645\u062f\u0627\u062e\u0644 \u0627\u0644\u0645\u062d\u0641\u0638\u0629 \u2b50 \u064a\u0631\u0641\u0636 NaN / Infinity \u2b50 (\u26d4\u26d4 \u0643\u0627\u0646 \u0628\u064a\u0643\u0634\u0641 \u0647\u0645 \u2b50)
   \u2463 \u062d\u0630\u0641 \u062d\u0633\u0627\u0628 \u0627\u0644\u0623\u062f\u0645\u0646 \u2b50 \u0627\u0644\u0642\u0631\u0627\u0621\u0629 \u0648\u0627\u0644\u062d\u0630\u0641 \u2b50 \u0643\u0644\u0647\u0645 \u062c\u0648\u0647 \u0627\u0644\u0642\u0641\u0644 \u2b50

\U0001f4d7 \u0627\u0644\u062a\u0634\u063a\u064a\u0644: python3 tools/test_r26_portfolio_atomicity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

RESULTS = []


def _record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        ("  ::  " + detail) if detail else ""))
    return bool(ok)


def _child_env(data_dir, repo):
    env = dict(os.environ)
    env["OCTA_DATA_DIR"] = str(data_dir)
    env["OCTAD_DEV"] = "1"
    env["OCTA_BG_TASKS"] = "off"
    env["OCTA_REPO"] = str(repo)
    env["PYTHONPATH"] = str(repo)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# \u26a0 \u0627\u0644\u0639\u0645\u0644\u0629 \u0627\u0644\u0623\u062e\u0631\u0649 \u21d2 \u064a\u0643\u062a\u0628 \u0627\u0644\u062d\u0642\u0648\u0644 \u0648\u064a\u0643\u062a\u0628 \u0641\u064a \u0646\u0641\u0633 \u0627\u0644\u0645\u0644\u0641 \u2b50
CHILD_SRC = r'''
import os, sys
sys.path.insert(0, os.environ["OCTA_REPO"])
import update_prices as up
uid = os.environ["OCTA_TEST_UID"]
n = int(os.environ["OCTA_TEST_N"])
prefix = os.environ["OCTA_TEST_PREFIX"]
for i in range(n):
    up._patch_user(uid, **{("%s%04d" % (prefix, i)): i})
print("CHILD_DONE", prefix)
'''


def _seed(data_dir, uid):
    data_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        "id": uid,
        "name": "synthetic-r26",
        "email": "r26-synthetic@example.invalid",
        "token_epoch": 1,
        "created_at": 1700000000,
    }
    (data_dir / "users.json").write_text(
        json.dumps({uid: rec}, ensure_ascii=False), encoding="utf-8")


def _atomicity_case(writes_per_child, repo=REPO):
    uid = "r26_atomic_user"
    tmp = Path(tempfile.mkdtemp(prefix="r26_atomic_"))
    try:
        _seed(tmp, uid)
        procs = []
        for prefix in ("a", "b"):
            e = _child_env(tmp, repo)
            e["OCTA_TEST_UID"] = uid
            e["OCTA_TEST_PREFIX"] = prefix
            e["OCTA_TEST_N"] = str(writes_per_child)
            procs.append(subprocess.Popen(
                [sys.executable, "-c", CHILD_SRC], env=e,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        outs = []
        for p in procs:
            out, err = p.communicate(timeout=900)
            outs.append((p.returncode, out.decode("utf-8", "replace"),
                         err.decode("utf-8", "replace")[-400:]))
        bad = [o for o in outs if o[0] != 0 or "CHILD_DONE" not in o[1]]
        data = json.loads((tmp / "users.json").read_text(encoding="utf-8"))
        rec = data.get(uid) or {}
        got_a = len([k for k in rec if k.startswith("a")])
        got_b = len([k for k in rec if k.startswith("b")])
        expected = writes_per_child * 2
        actual = got_a + got_b
        ok = (not bad) and actual == expected
        detail = "expected %d writes, got %d (a=%d b=%d)" % (
            expected, actual, got_a, got_b)
        if bad:
            detail += " | child failure: " + bad[0][2].replace("\n", " ")[-200:]
        return ok, detail, tmp
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:200]), tmp


def test_cross_process_atomicity_100():
    ok, detail, tmp = _atomicity_case(100)
    shutil.rmtree(tmp, ignore_errors=True)
    return _record("R26-ATOM-01: 100 + 100 writes on two processes => zero lost",
                   ok, detail)


def test_cross_process_atomicity_1000():
    ok, detail, tmp = _atomicity_case(1000)
    shutil.rmtree(tmp, ignore_errors=True)
    return _record("R26-ATOM-02: 1000 + 1000 writes on two processes => zero lost",
                   ok, detail)


# \u26a0 \u0627\u0644\u0641\u062d\u0635 \u0646\u0646\u0631\u064d \u0628\u0627\u0633\u062a\u0645\u0644 \u0645\u0641\u0631\u0648\u0632 \u0628\u0639\u062f \u0627\u0644\u0625\u0633\u062a\u064a\u0631\u0627\u062f \u21d2 \u26d4\u26d4 \u0645\u0643\u0633\u0648\u0628\u0627 \u0639\u0645\u0644\u0629
NAN_SRC = r'''
import json, os, sys
sys.path.insert(0, os.environ["OCTA_REPO"])
import update_prices as up
out = {}

# 1) the numeric guard
ok = True
for bad in (float("nan"), float("inf"), float("-inf")):
    if up._num_finite(bad) is not None:
        ok = False
if up._num_finite(2.5) != 2.5:
    ok = False
if up._num_finite("abc") is not None:
    ok = False
out["num_finite"] = ok

# 2) the file never holds NaN / Infinity
payload = {"u1": {"id": "u1", "portfolio": {
    "cash": float("nan"), "holdings": {"X": {"shares": float("inf")}}}}}
up._save_users(payload)
raw = open(os.path.join(os.environ["OCTA_DATA_DIR"], "users.json"),
           encoding="utf-8").read()
out["no_nan_text"] = ("NaN" not in raw) and ("Infinity" not in raw)

# 3) strict JSON (a standards-compliant parser must accept it)
try:
    json.loads(raw, parse_constant=lambda c: (_ for _ in ()).throw(
        ValueError("non-strict constant: %s" % c)))
    out["strict_json"] = True
except Exception as e:
    out["strict_json"] = False
    out["strict_err"] = str(e)[:120]
print("RESULT_JSON:" + json.dumps(out))
'''


def test_nan_inf_guard():
    tmp = Path(tempfile.mkdtemp(prefix="r26_nan_"))
    try:
        env = _child_env(tmp, REPO)
        proc = subprocess.run([sys.executable, "-c", NAN_SRC], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=600)
        text = proc.stdout.decode("utf-8", "replace")
        payload = None
        for line in text.splitlines():
            if line.startswith("RESULT_JSON:"):
                payload = json.loads(line[len("RESULT_JSON:"):])
        if payload is None:
            _record("R26-NAN-01..03: the numeric guards hold", False,
                    (proc.stderr.decode("utf-8", "replace")[-300:] or text[-300:]))
            return
        _record("R26-NAN-01: _num_finite rejects NaN / Infinity",
                payload.get("num_finite"))
        _record("R26-NAN-02: users.json never contains NaN / Infinity",
                payload.get("no_nan_text"))
        _record("R26-NAN-03: users.json is strict JSON (no NaN constants)",
                payload.get("strict_json"), payload.get("strict_err", ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ⚠ المسار الواجه ⇒ رقض مع محرك المحفظة أصل معول نقاط المعايرة
API_SRC = r'''
import json, os, sys
sys.path.insert(0, os.environ["OCTA_REPO"])
import update_prices as up
uid = "r26_api_user"
up._save_users({uid: {"id": uid, "name": "synthetic",
                      "email": "r26-api@example.invalid", "token_epoch": 1}})
tok = up._make_token(uid)
client = up.app.test_client()
hdr = {"Authorization": "Bearer " + tok}
out = {}
cases = (
    ("add_nan", {"action": "add", "code": "X", "shares": "NaN", "cost": 1, "price": 1}),
    ("add_inf", {"action": "add", "code": "X", "shares": "Infinity", "cost": 1, "price": 1}),
    ("cash_nan", {"action": "set_cash", "cash": "NaN"}),
    ("cash_inf", {"action": "set_cash", "cash": "Infinity"}),
)
for label, payload in cases:
    res = client.post("/api/portfolio", json=payload, headers=hdr)
    out[label] = res.status_code
res = client.post("/api/portfolio", json={"action": "set_cash", "cash": 1234.5},
                   headers=hdr)
out["normal"] = res.status_code
print("RESULT_JSON:" + json.dumps(out))
'''


def test_portfolio_api_rejects_non_finite():
    tmp = Path(tempfile.mkdtemp(prefix="r26_api_"))
    try:
        env = _child_env(tmp, REPO)
        proc = subprocess.run([sys.executable, "-c", API_SRC], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=600)
        text = proc.stdout.decode("utf-8", "replace")
        payload = None
        for line in text.splitlines():
            if line.startswith("RESULT_JSON:"):
                payload = json.loads(line[len("RESULT_JSON:"):])
        if payload is None:
            _record("R26-NAN-04: the portfolio endpoint refuses NaN / Infinity (400)",
                    False, proc.stderr.decode("utf-8", "replace")[-300:])
            return
        bad_cases = {k: v for k, v in payload.items() if k != "normal"}
        ok = all(v == 400 for v in bad_cases.values())
        _record("R26-NAN-04: the portfolio endpoint refuses NaN / Infinity (400)",
                ok, json.dumps(bad_cases, ensure_ascii=False))
        _record("R26-NAN-05: a normal value still saves (200)",
                payload.get("normal") == 200, "status=%s" % payload.get("normal"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    t0 = time.time()
    test_cross_process_atomicity_100()
    test_cross_process_atomicity_1000()
    test_nan_inf_guard()
    test_portfolio_api_rejects_non_finite()
    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)
    print("\n==== R26 portfolio atomicity ====")
    print("passed %d / %d   (%.1fs)" % (passed, total, time.time() - t0))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
