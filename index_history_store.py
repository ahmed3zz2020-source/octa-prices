# -*- coding: utf-8 -*-
"""📚 R32 · ⭐⭐⭐ مصدر ⭐⭐⭐ تاريخ ⭐⭐⭐ المؤشرات ⭐⭐⭐ ⭐⭐⭐ (بذرة ⭐ + نسخة ⭐ تشغيلية ⭐)

📌 ليه الملف ده موجود؟
   ⭐ ملف `data/index_history.json` كان بيتبعت من كود التطبيق (مجلد الكود) ⭐
   ⇒ ⭐ ده نفس عيب FINDING-23 ⭐ (كتابة بيانات تشغيلية جوّه شجرة المستودع) ⭐
   ⇒ ⭐ وأخطر: بوابة «سلامة البيانات المرجعية» في الـCI بتقارن `data/*.json` قبل الجولة وبعدها ⭐
   ⇒ ⭐ فأي كتابة جوايه بتكسر الـCI ⭐ (وكمان بتلوّث شجرة الشغل ⭐).

📌 القاعدة (مكتوبة صراحة ⭐):
   ① البذرة (seed) = `data/index_history.json` ⭐ — ملف متتبَّع في المستودع ⭐ — للقراءة فقط ⭐.
   ② النسخة التشغيلية (runtime) = `<DATA_DIR>/index_history.json` ⭐ — نفس اسم ومكان
      `users.json` وباقي بيانات التشغيل ⭐ ⇒ تعيش بعد كل إعادة نشر ⭐.
   ③ الكتابة الذرّية (اسم مؤقت فريد ⭐) عن طريق `safe_write` ⭐ — مفيش اسم ثابت ⭐.
   ④ القراءة = النسخة الأحدث تاريخاً ⭐ (`version`) ⇒ النسخة التشغيلية لو موجودة ⭐
      وإلا البذرة ⭐ ⇒ ومفيش تاريخ قديم يضيع ⭐ (اتحاد الصفوف ⭐).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import safe_write as _sw  # ⭐ R32 · كتابة ذرّية باسم مؤقت فريد ⭐

HERE = Path(__file__).resolve().parent
# 📌 البذرة ⭐ — متتبَّعة في المستودع ⭐ — للقراءة فقط ⭐ (ممنوع الكتابة فيها ⭐).
SEED_FILE = HERE / "data" / "index_history.json"

__all__ = ["SEED_FILE", "data_dir", "runtime_file", "load_seed", "load_runtime",
           "effective_payload", "write_runtime"]

_DATA_DIR = None  # ⭐ كاش واحد ⭐ (مش بنعمل فحص في كل نداء ⭐).
_DATA_DIR_OK = False  # ⭐⭐⭐ (R32 · e) ⭐⭐⭐ هل المجلد ⭐⭐⭐ قابل ⭐⭐⭐ للكتابة ⭐⭐⭐ فعلاً ⭐⭐⭐ ⭐⭐⭐


def data_dir() -> Path:
    """📂 مجلد البيانات التشغيلية ⭐ — نفس قاعدة `update_prices.DATA_DIR` ⭐."""
    global _DATA_DIR, _DATA_DIR_OK
    if _DATA_DIR is not None:
        return _DATA_DIR
    raw = (os.environ.get("OCTA_DATA_DIR") or "/data").strip() or "/data"
    d = Path(raw)
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / (".w-%d" % os.getpid())   # ⭐ اسم فريد ⭐ (pid ⭐)
        probe.write_text("ok", encoding="utf-8")
        try:
            os.unlink(probe)
        except OSError:
            pass
        _DATA_DIR = d
        _DATA_DIR_OK = True
    except Exception:
        # ⛔⛔⛔ (R32 · e) ⛔⛔⛔ مفيش مجلد تشغيلي قابل للكتابة ⭐
        # 📌 ⭐ الـfallback ⭐ ده **للقراءة فقط** ⭐ ⇒ ⭐ ممنوع ⭐ أي كتابة ⭐ فيه ⭐
        #    ⭐ (مجلد الكود ⭐ ⭐ ما ينفعش ⭐⭐ يتلوّث ⭐⭐ ببيانات تشغيل ⭐⭐) ⭐⭐.
        #    ⭐ ⇒ `write_runtime` ⭐ بيرفض ⭐ وبيعيد ⭐ False ⭐ ⭐.
        _DATA_DIR = HERE
        _DATA_DIR_OK = False
    return _DATA_DIR


def runtime_dir_ok() -> bool:
    """✅ هل مجلد البيانات التشغيلي قابل للكتابة فعلاً ⭐.

    ⛔ False ⭐ ⇒ ⭐ **ممنوع** ⭐ الكتابة ⭐ ⭐ (مفيش fallback ⭐ لمجلد الكود ⭐⭐) ⭐⭐.
    """
    data_dir()   # ⭐ يخلّي الـresolve ⭐ يتنفّذ ⭐
    return bool(_DATA_DIR_OK)


def runtime_file() -> Path:
    """📄 النسخة التشغيلية ⭐ — `DATA_DIR/index_history.json` ⭐."""
    return data_dir() / "index_history.json"


def _read(p: Path):
    try:
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def load_seed():
    """🌱 البذرة ⭐ (ملف المستودع ⭐) — أو None ⭐."""
    return _read(SEED_FILE)


def load_runtime():
    """⚙️ النسخة التشغيلية ⭐ (ملف DATA_DIR ⭐) — أو None ⭐."""
    return _read(runtime_file())


def _version(payload) -> str:
    try:
        return str((payload or {}).get("version") or "")
    except Exception:
        return ""


def _rows_of(row):
    out = {}
    try:
        for r in (row.get("rows") or []):
            out[int(r[0])] = float(r[1])
    except Exception:
        return {}
    return out


def _union(primary, other):
    """🔗 اتحاد الصفوف ⭐ — التاريخ القديم ما يضيعش ⭐ (القيم الموجودة ما بتتغيرش ⭐).

    ⭐⭐⭐ (R32 · e) ⭐⭐⭐ **مؤشر ⭐⭐⭐ موجود ⭐⭐⭐ في ⭐⭐⭐ نسخة ⭐⭐⭐ وحدها ⭐⭐⭐** ⭐⭐⭐
    ⭐⭐⭐ ⇒ ⭐⭐⭐ بينحفظ ⭐⭐⭐ ⭐ (قبل ⭐⭐⭐: ⭐⭐⭐ كان ⭐⭐⭐ بيضيع ⭐⭐⭐ ⭐ ⭐ لأن ⭐⭐⭐
    ⭐⭐⭐ الحلقة ⭐⭐⭐ كانت ⭐⭐⭐ على ⭐⭐⭐ مفاتيح ⭐⭐⭐ النسخة ⭐⭐⭐ الأساسية ⭐⭐⭐ بس ⭐⭐⭐) ⭐⭐⭐.
    """
    if not isinstance(primary, dict):
        return primary
    p_idx = primary.get("indices")
    if not isinstance(p_idx, dict):
        p_idx = {}
        primary["indices"] = p_idx
    o_idx = (other.get("indices") or {}) if isinstance(other, dict) else {}
    for name, orow in list(o_idx.items()):
        if name in p_idx:
            continue
        # ⭐⭐⭐ المؤشر ⭐⭐⭐ ده ⭐⭐⭐ موجود ⭐⭐⭐ في ⭐⭐⭐ النسخة ⭐⭐⭐ الأخرى ⭐⭐⭐ بس ⭐⭐⭐
        # ⭐⭐⭐ ⇒ ⭐⭐⭐ بينحفظ ⭐⭐⭐ بنسخة ⭐⭐⭐ مستقلة ⭐⭐⭐ (مش ⭐⭐⭐ نفس ⭐⭐⭐ المرجع ⭐⭐⭐) ⭐⭐⭐.
        try:
            p_idx[name] = json.loads(json.dumps(orow))
        except Exception:
            p_idx[name] = orow
    for name, row in list(p_idx.items()):
        if not isinstance(row, dict):
            continue
        orow = o_idx.get(name)
        if not isinstance(orow, dict):
            continue
        pm = _rows_of(row)
        om = _rows_of(orow)
        if not om:
            continue
        added = [t for t in om if t not in pm]
        if not added:
            continue
        merged = dict(pm)
        for t in added:
            merged[t] = om[t]
        pts = sorted(merged.items())
        out = [[int(t), round(float(v), 4)] for t, v in pts]
        row["rows"] = out
        row["series"] = [list(x) for x in out]   # ⭐ `series` مرآة لـ`rows` ⭐
        row["count"] = len(out)
        row["from"] = time.strftime("%Y-%m-%d", time.gmtime(out[0][0]))
        row["to"] = time.strftime("%Y-%m-%d", time.gmtime(out[-1][0]))
    return primary


def effective_payload():
    """📦 الحمولة الفعلية ⭐ = الأحدث بين التشغيلية والبذرة ⭐ + اتحاد الصفوف ⭐."""
    seed = load_seed()
    runtime = load_runtime()
    if runtime is None:
        return seed
    if seed is None:
        return runtime
    if _version(runtime) >= _version(seed):
        return _union(runtime, seed)
    return _union(seed, runtime)


def write_runtime(payload, attempts: int = 2) -> bool:
    """💾 كتابة ذرّية ⭐ للنسخة التشغيلية ⭐ — في DATA_DIR ⭐ (مش في شجرة الكود ⭐).

    ⛔⛔⛔ (R32 · e) ⛔⛔⛔ لو ⭐⭐⭐ مجلد ⭐⭐⭐ البيانات ⭐⭐⭐ التشغيلي ⭐⭐⭐ مش ⭐⭐⭐ قابل ⭐⭐⭐
       ⭐⭐⭐ للكتابة ⭐⭐⭐ ⇒ ⭐⭐⭐ **ممنوع** ⭐⭐⭐ نكتب ⭐⭐⭐ في ⭐⭐⭐ مجلد ⭐⭐⭐ الكود ⭐⭐⭐ ⭐⭐⭐
       ⭐⭐⭐ ⇒ ⭐⭐⭐ نرجّع ⭐⭐⭐ False ⭐⭐⭐ ⭐ (fail-closed ⭐⭐) ⭐⭐⭐.
    ⭐ إعادة المحاولة ⭐: ⭐ لو ⭐ الحفظ ⭐ فشل ⭐ ⇒ ⭐ بنعيد ⭐ ⭐ مرتين ⭐ ⭐ ⭐.
    """
    if not runtime_dir_ok():
        return False
    p = runtime_file()
    last = None
    for _ in range(max(1, int(attempts or 1))):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            last = exc
            continue
        try:
            _sw.safe_write_text(p, json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as exc:
            last = exc
            continue
    try:
        print("[idxhist] ⛔ runtime write failed ⭐ (%s) ⭐" % str(last)[:80])
    except Exception:
        pass
    return False
