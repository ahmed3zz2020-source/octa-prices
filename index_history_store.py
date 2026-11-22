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


def data_dir() -> Path:
    """📂 مجلد البيانات التشغيلية ⭐ — نفس قاعدة `update_prices.DATA_DIR` ⭐."""
    global _DATA_DIR
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
    except Exception:
        # ⛔ مفيش مجلد قابل للكتابة ⭐ ⇒ fallback لمجلد الكود ⭐
        #   (نفس سلوك `update_prices.DATA_DIR` ⭐ — فيهم بيانات التشغيل كلها ⭐).
        _DATA_DIR = HERE
    return _DATA_DIR


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
    """🔗 اتحاد الصفوف ⭐ — التاريخ القديم ما يضيعش ⭐ (القيم الموجودة ما بتتغيرش ⭐)."""
    p_idx = (primary.get("indices") or {}) if isinstance(primary, dict) else {}
    o_idx = (other.get("indices") or {}) if isinstance(other, dict) else {}
    for name, row in p_idx.items():
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


def write_runtime(payload) -> bool:
    """💾 كتابة ذرّية ⭐ للنسخة التشغيلية ⭐ — في DATA_DIR ⭐ (مش في شجرة الكود ⭐)."""
    p = runtime_file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    try:
        _sw.safe_write_text(p, json.dumps(payload, ensure_ascii=False))
        return True
    except Exception:
        return False
