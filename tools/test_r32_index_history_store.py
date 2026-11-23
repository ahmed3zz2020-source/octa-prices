# -*- coding: utf-8 -*-
"""🔒 R32 · ⭐⭐⭐ حارس ⭐⭐⭐ مصدر ⭐⭐⭐ تاريخ ⭐⭐⭐ المؤشرات ⭐⭐⭐

📌 العيب اللي بيحرسه ⭐:
   `_maybe_refresh_index_history()` كانت بتكتب `data/index_history.json`
   ⭐ — وده **ملف متتبَّع في المستودع** ⭐ ⇒
   ① شجرة الشغل بتتلبّث أثناء أي اختبار ⭐
   ② بوابة «سلامة البيانات المرجعية» في الـCI (مقارنة `data/*.json` قبل/بعد الجولة ⭐)
      بتفشل ⭐ — والدعوة بتاشي حسب الوقت ⭐ (بتشتغل بعد قفل السوق ⭐ ويوم الجمعة ⭐)
   ③ البيانات كانت بتضيع مع كل إعادة نشر ⭐ (الكتابة في مجلد الكود ⭐).

📌 الإصلاح ⭐: البذرة (ملف المستودع ⭐) للقراءة فقط ⭐
   ⭐ والكتابة ⇒ النسخة التشغيلية ⭐ `DATA_DIR/index_history.json` ⭐.

📌 البرهان ⭐: الاختبار ده **بيشغّل الدالة نفسها** في صندوق معزول ⭐
   ⭐ (كود وهمي ⭐ + مصدر أسعار وهمي ⭐ + مجلد تشغيل مؤقت ⭐)
   ⭐ وبيقيس: هل البذرة في مجلد الكود اتغيّرت ⭐ ولا لأ ⭐.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("✅" if ok else "⛔") + " " + name + ((" ⭐ " + detail) if detail else ""))
    return bool(ok)


def sha256(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return ""


def load_store():
    try:
        import index_history_store  # noqa
        return index_history_store
    except Exception:
        return None


# ── ① وحدة: محلّل المصدر ⭐ ───────────────────────────────────────────────
def unit_store(store, tmp: Path):
    if store is None:
        check("محلّل المصدر موجود ⭐", False, "index_history_store مش موجود ⭐")
        return
    ok = True
    ok &= check("البذرة داخل data/ ⭐", store.SEED_FILE.parent.name == "data"
                and (store.SEED_FILE.parent.parent == ROOT),
                str(store.SEED_FILE))
    rt = store.runtime_file()
    ok &= check("النسخة التشغيلية برّه شجرة الكود ⭐", str(rt) != str(store.SEED_FILE)
                and not str(rt).startswith(str(ROOT / "data")),
                str(rt))
    ok &= check("النسخة التشغيلية داخل DATA_DIR ⭐", rt.parent == store.data_dir(),
                "%s vs %s" % (rt.parent, store.data_dir()))

    # ⭐ النسخة الأحدث تاريخاً ⭐ + ⭐ الاتحاد ⭐ (مفيش تاريخ يضيع ⭐)
    seed = {"version": "2026-11-21",
            "indices": {"EGX30": {"rows": [[1700000000, 1.0], [1700086400, 2.0]],
                                  "series": [[1700000000, 1.0], [1700086400, 2.0]],
                                  "count": 2}}}
    runtime = {"version": "2026-11-22",
               "indices": {"EGX30": {"rows": [[1700086400, 2.0], [1700172800, 3.0]],
                                     "series": [[1700086400, 2.0], [1700172800, 3.0]],
                                     "count": 2}}}
    real_seed = store.SEED_FILE      # ⭐ نحفظ البذرة الحقيقية ⭐
    store.SEED_FILE = tmp / "seed.json"          # ⭐ بذرة وهمية ⭐
    (tmp / "seed.json").write_text(json.dumps(seed), encoding="utf-8")
    store._DATA_DIR = tmp / "run"
    (tmp / "run").mkdir(parents=True, exist_ok=True)
    try:
        p = store.effective_payload()
        ok &= check("من غير نسخة تشغيلية ⭐ ⇒ البذرة ⭐",
                    p is not None and p.get("version") == "2026-11-21")
        (tmp / "run" / "index_history.json").write_text(json.dumps(runtime),
                                                         encoding="utf-8")
        p = store.effective_payload()
        ok &= check("النسخة الأحدث ⭐ ⇒ هي اللي تتقرا ⭐",
                    p is not None and p.get("version") == "2026-11-22")
        rows = (((p or {}).get("indices") or {}).get("EGX30") or {}).get("rows") or []
        ok &= check("الاتحاد ⭐ ⇒ مفيش تاريخ قديم ضاع ⭐",
                    len(rows) == 3 and rows[0][0] == 1700000000,
                    "%d صف ⭐" % len(rows))
        ok &= check("الاتحاد ⭐ ⇒ `series` مرآة لـ`rows` ⭐",
                    (((p or {}).get("indices") or {}).get("EGX30") or {}).get("series")
                    == rows)
        # ⭐ البذرة الأحدث ⭐ ⇒ هي اللي تتقرا ⭐
        newer_seed = dict(seed)
        newer_seed["version"] = "2026-11-25"
        (tmp / "seed.json").write_text(json.dumps(newer_seed), encoding="utf-8")
        p = store.effective_payload()
        ok &= check("البذرة الأحدث ⭐ ⇒ هي اللي تتقرا ⭐",
                    p is not None and p.get("version") == "2026-11-25")
        # ⭐ الكتابة ⭐ ⇒ في النسخة التشغيلية ⭐ وال بذرة ما اتغيّرتش ⭐
        before = sha256(tmp / "seed.json")
        # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ مؤشر ⭐⭐⭐ موجود ⭐⭐⭐ في ⭐⭐⭐ نسخة ⭐⭐⭐ وحدها ⭐⭐⭐ ⇒ ⭐⭐⭐ بينحفظ ⭐⭐⭐
        split = {"version": "2026-11-22",
                 "indices": {"EGX70": {"rows": [[1700000000, 7.0]],
                                       "series": [[1700000000, 7.0]], "count": 1}}}
        (tmp / "run" / "index_history.json").write_text(json.dumps(split), encoding="utf-8")
        (tmp / "seed.json").write_text(json.dumps(seed), encoding="utf-8")
        p = store.effective_payload()
        idx = (p or {}).get("indices") or {}
        ok &= check("مؤشر ⭐⭐ موجود ⭐⭐ في ⭐⭐ نسخة ⭐⭐ وحدها ⭐⭐ ⇒ ⭐⭐ بينحفظ ⭐⭐",
                    "EGX30" in idx and "EGX70" in idx,
                    "المؤشرات ⭐: %s ⭐" % sorted(idx.keys()))
        # ⭐⭐⭐ المجلد ⭐⭐⭐ التشغيلي ⭐⭐⭐ المعطوب ⭐⭐⭐ ⇒ ⭐⭐⭐ ممنوع ⭐⭐⭐ الكتابة ⭐⭐⭐ ⭐⭐⭐
        old_env = os.environ.get("OCTA_DATA_DIR")
        os.environ["OCTA_DATA_DIR"] = "/proc/1/nope-does-not-exist"
        store._DATA_DIR = None
        store._DATA_DIR_OK = False
        code_probe = ROOT / "index_history.json"
        existed_before = code_probe.exists()
        wrote = store.write_runtime({"version": "x", "indices": {}})
        ok &= check("مجلد ⭐⭐ البيانات ⭐⭐ المعطوب ⭐⭐ ⇒ ⭐⭐ الكتابة ⭐⭐ مرفوضة ⭐⭐",
                    wrote is False and store.runtime_dir_ok() is False)
        ok &= check("مجلد ⭐⭐ الكود ⭐⭐ ما ⭐⭐ اتلوّثش ⭐⭐",
                    code_probe.exists() == existed_before)
        if old_env is None:
            os.environ.pop("OCTA_DATA_DIR", None)
        else:
            os.environ["OCTA_DATA_DIR"] = old_env
        store._DATA_DIR = None
        store._DATA_DIR_OK = False
        before = sha256(tmp / "seed.json")   # ⭐⭐ بعد ⭐⭐ إعادة ⭐⭐ كتابة ⭐⭐ البذرة ⭐⭐ ⭐
        ok &= check("الكتابة ⭐ ⇒ رجعت true ⭐", store.write_runtime({"version": "x"}))
        ok &= check("الكتابة ⭐ ⇒ البذرة ما اتغيّرتش ⭐",
                    sha256(tmp / "seed.json") == before)
        leftovers = [p.name for p in (tmp / "run").iterdir() if p.name != "index_history.json"]
        ok &= check("الكتابة ⭐ ⇒ مفيش ملف مؤقت فاضل ⭐", not leftovers,
                    ",".join(leftovers[:3]))
    finally:
        store._DATA_DIR = None
        store.SEED_FILE = real_seed   # ⭐ نرجّع البذرة الحقيقية ⭐


# ── ② سلوك حقيقي ⭐: الدالة نفسها في صندوق معزول ⭐ ──────────────────────
def _extract_refresh():
    src = (ROOT / "update_prices.py").read_text(encoding="utf-8")
    i = src.find("def _maybe_refresh_index_history(")
    if i < 0:
        return None
    j = src.find("\ndef ", i + 10)
    return src[i:j if j > 0 else len(src)]


class _StoreStub:
    """⭐⭐⭐ stub ⭐⭐⭐ ⭐ حفظ ⭐⭐⭐ ⭐ يفشل ⭐⭐⭐ ⭐ (لاختبار ⭐⭐⭐ إعادة ⭐⭐⭐ المحاولة ⭐⭐⭐) ⭐⭐⭐."""

    def __init__(self, fail=False):
        self.fail = fail

    def effective_payload(self):
        return {"version": "2026-11-21",
                "indices": {"EGX30": {"rows": [[1700000000, 1.0]],
                                      "series": [[1700000000, 1.0]], "count": 1}}}

    def write_runtime(self, payload, attempts=2):
        return not self.fail

    def runtime_file(self):
        return Path("/nonexistent/index_history.json")

    def runtime_dir_ok(self):
        return True


def _fake_tv_ws():
    m = importlib.import_module("types")
    mod = m.ModuleType("tv_ws")
    now = int(time.time())

    def fetch_series(sym, n=120):
        base_ts = (now // 86400) * 86400 - 86400
        return [{"t": base_ts, "c": 100.0}, {"t": base_ts + 86400, "c": 101.5}]
    mod.fetch_series = fetch_series
    return mod


def behavioral_refresh(store, tmp: Path):
    src = _extract_refresh()
    if not src:
        check("دالة التحديث موجودة ⭐", False)
        return
    code = tmp / "code"
    (code / "data").mkdir(parents=True, exist_ok=True)
    seed_file = code / "data" / "index_history.json"
    payload = {"version": "2026-11-21",
               "indices": {"EGX30": {"rows": [[1700000000, 1.0]],
                                     "series": [[1700000000, 1.0]],
                                     "count": 1, "from": "2023-11-14", "to": "2023-11-14"},
                           "EGX70": {"rows": [[1700000000, 1.0]],
                                     "series": [[1700000000, 1.0]],
                                     "count": 1, "from": "2023-11-14", "to": "2023-11-14"},
                           "EGX100": {"rows": [[1700000000, 1.0]],
                                      "series": [[1700000000, 1.0]],
                                      "count": 1, "from": "2023-11-14", "to": "2023-11-14"},
                           "EGX33": {"rows": [[1700000000, 1.0]],
                                     "series": [[1700000000, 1.0]],
                                     "count": 1, "from": "2023-11-14", "to": "2023-11-14"}}}
    seed_file.write_text(json.dumps(payload), encoding="utf-8")
    before = sha256(seed_file)

    run_dir = tmp / "runtime"
    run_dir.mkdir(parents=True, exist_ok=True)
    old_env = os.environ.get("OCTA_DATA_DIR")
    os.environ["OCTA_DATA_DIR"] = str(run_dir)
    if store is not None:
        store._DATA_DIR = None
    old_tv = sys.modules.get("tv_ws")
    sys.modules["tv_ws"] = _fake_tv_ws()

    ns = {
        "__name__": "octa_r32_fake", "__file__": str(code / "update_prices.py"),
        "Path": Path, "json": json, "os": os, "sys": sys, "time": time,
        "datetime": datetime.datetime, "print": print,
        "cairo_now": lambda: datetime.datetime(2026, 11, 22, 16, 0),
        "market_phase": lambda: "closed",
        "_IDX_HIST": {}, "_IDX_HIST_REFRESH_DAY": None,
        "index_history_store": store,
    }
    try:
        exec(compile(src, "<r32-refresh>", "exec"), ns)
        ns["_maybe_refresh_index_history"]()
    except Exception as e:
        print("ℹ️ استثناء أثناء التشغيل ⭐: %s: %s" % (type(e).__name__, str(e)[:120]))
    finally:
        if old_tv is not None:
            sys.modules["tv_ws"] = old_tv
        else:
            sys.modules.pop("tv_ws", None)
        if old_env is None:
            os.environ.pop("OCTA_DATA_DIR", None)
        else:
            os.environ["OCTA_DATA_DIR"] = old_env
        if store is not None:
            store._DATA_DIR = None

    # ⭐⭐⭐ (R32-e2) ⭐⭐⭐ **تعافي ⭐⭐⭐** ⭐⭐⭐ بعد ⭐⭐⭐ تعطل ⭐⭐⭐ مؤقت ⭐⭐⭐ ⭐⭐⭐
    # 📌 الفحص ⭐⭐⭐: ⭐⭐⭐ المجلد ⭐⭐⭐ التشغيلي ⭐⭐⭐ ينكسر ⭐⭐⭐ ⇒ ⭐⭐⭐ كتابة ⭐⭐⭐ مرفوضة ⭐⭐⭐ ⭐⭐⭐
    #    ⭐⭐⭐ ومجلد ⭐⭐⭐ الكود ⭐⭐⭐ ما ⭐⭐⭐ اتلوّثش ⭐⭐⭐ ⭐⭐⭐ ⇒ ⭐⭐⭐ بعد ما ⭐⭐⭐ يرجع ⭐⭐⭐ ⭐⭐⭐
    #    ⭐⭐⭐ ⇒ ⭐⭐⭐ الكتابة ⭐⭐⭐ تنجح ⭐⭐⭐ تاني ⭐⭐⭐ ⭐⭐⭐.
    ok_recovery = False
    try:
        if store is not None:
            real_env = os.environ.get("OCTA_DATA_DIR")
            os.environ["OCTA_DATA_DIR"] = "/proc/1/nope-temp-break"
            store._DATA_DIR = None
            store._DATA_DIR_OK = False
            broke = store.write_runtime({"version": "x", "indices": {}}) is False
            code_probe2 = ROOT / "index_history.json"
            clean2 = (not code_probe2.exists())
            if real_env is None:
                os.environ.pop("OCTA_DATA_DIR", None)
            else:
                os.environ["OCTA_DATA_DIR"] = real_env
            store._DATA_DIR = None
            store._DATA_DIR_OK = False
            healed = store.write_runtime({"version": "healed", "indices": {}}) is True
            ok_recovery = bool(broke and clean2 and healed)
    except Exception:
        ok_recovery = False
    check("تعافي ⭐⭐ المجلد ⭐⭐ بعد ⭐⭐ تعطل ⭐⭐ مؤقت ⭐⭐ (رفض ⭐⭐ ⭐ ⭐ ⇒ ⭐⭐ رفض ⭐⭐ ⭐ ⭐ ⇒ ⭐⭐ نجاح ⭐⭐ ⭐ ⭐)",
          ok_recovery)

    # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ فشل ⭐⭐⭐ الحفظ ⭐⭐⭐ ⇒ ⭐⭐⭐ إعادة ⭐⭐⭐ المحاولة ⭐⭐⭐ ⭐⭐⭐
    ns_fail = dict(ns)
    ns_fail["_IDX_HIST_REFRESH_DAY"] = None   # ⭐⭐⭐ نبدأ ⭐⭐⭐ من ⭐⭐⭐ الصفر ⭐⭐⭐ ⭐ (العلامة ⭐⭐⭐ بتوقف ⭐⭐⭐ التحديث ⭐⭐⭐) ⭐⭐⭐
    ns_fail["index_history_store"] = _StoreStub(fail=True)
    try:
        exec(compile(src, "<r32-refresh-fail>", "exec"), ns_fail)
        ns_fail["_maybe_refresh_index_history"]()
        retried = ns_fail.get("_IDX_HIST_REFRESH_DAY") is None
    except Exception:
        retried = False
    check("فشل ⭐⭐ الحفظ ⭐⭐ ⇒ ⭐⭐ إعادة ⭐⭐ المحاولة ⭐⭐ (العلامة ⭐⭐ اتصفّرت ⭐⭐)",
          retried)

    after = sha256(seed_file)
    check("التحديث ما كتبش في مجلد الكود ⭐ (البذرة زي ما هي ⭐)", after == before,
          ("البذرة اتغيّرت ⭐ ⇒ الخلل لسه موجود ⭐" if after != before else ""))
    rt_file = run_dir / "index_history.json"
    ok = rt_file.exists()
    check("التحديث كتب في النسخة التشغيلية ⭐ (DATA_DIR ⭐)", ok, str(rt_file))
    if ok:
        try:
            d = json.loads(rt_file.read_text(encoding="utf-8"))
            n = len((((d.get("indices") or {}).get("EGX30") or {}).get("rows")) or [])
            check("النسخة التشغيلية فيها التاريخ المدمج ⭐", n >= 2,
                  "%d صف ⭐" % n)
        except Exception as e:
            check("النسخة التشغيلية صالحة ⭐", False, str(e)[:80])


# ── ③ ساكن ⭐: الكود ما ينمّش أي مسار كتابة في مجلد الكود ⭐ ───────────────
def static_checks():
    src = (ROOT / "update_prices.py").read_text(encoding="utf-8")
    body = _extract_refresh() or ""
    check("ما فيش كتابة في مجلد الكود ⭐ (with_suffix .json.tmp ⭐)",
          ".json.tmp" not in body)
    check("التحديث بيكتب عن طريق محلّل المصدر ⭐",
          "index_history_store.write_runtime" in body)
    check("القراءة بتستخدم نفس المحلّل ⭐",
          "index_history_store.effective_payload" in src)
    psrc = (ROOT / "pattern_daily.py").read_text(encoding="utf-8")
    check("نظام السوق بيستخدم نفس المحلّل ⭐",
          "index_history_store.effective_payload" in psrc)


def main():
    print("═" * 72)
    print("🔒 R32 · ⭐⭐⭐ حارس ⭐⭐⭐ مصدر ⭐⭐⭐ تاريخ ⭐⭐⭐ المؤشرات ⭐⭐⭐")
    print("═" * 72)
    tmp = Path(tempfile.mkdtemp(prefix="r32-idxhist-"))
    store = load_store()
    try:
        unit_store(store, tmp)
        behavioral_refresh(store, tmp)
        if store is not None:
            static_checks()
        else:
            print("ℹ️ الفحوص الساكنة اتخطّت ⭐ (مفيش محلّل ⭐ ⇒ الأساس ⭐)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print("─" * 72)
    if bad:
        print("⛔ فشل %d فحص ⭐ من %d ⭐" % (len(bad), len(RESULTS)))
        for n, _, d in bad:
            print("   · %s ⭐ %s" % (n, d))
        return 1
    print("✅ كل %d فحص ناجح ⭐" % len(RESULTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
