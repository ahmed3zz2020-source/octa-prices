#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 مُشغّل على نمط `pytest` — الجولة ٢٥ (R25 · المرحلة ٩)

📌 ليه الأداة دي ⭐:
   بيئة الاختبار هنا **مفيش فيها** `pytest` ⭐ ولا شبكة تنزيل ⭐
   ⇒ فبنعمل مُشغّل **بنفس قواعد الاكتشاف** ⭐:
   · دوال على مستوى المودل باسم `test_*` ⭐
   · كل دالة مستقلة ⭐ · لو ترمي استثناء ⇒ الاختبار فاشل ⭐
   · مافيش ترتيب فرض ⭐ · مافيش fixtures ⭐

⛔ الأداة دي **مش بديل** عن `pytest` ⭐ — أداة تحقق ⭐.

📌 التشغيل:
   python3 tools/staging/pytest_lite.py tools/test_r25_perf_latency.py
"""
import importlib.util
import os
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def _load(path):
    path = Path(path).resolve()
    name = "r25case_" + path.stem
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(path.parent))
    sys.path.insert(0, str(path.parent / "staging"))
    spec.loader.exec_module(mod)
    return mod


def run(path):
    mod = _load(path)
    names = sorted(n for n in dir(mod)
                   if n.startswith("test_")
                   and callable(getattr(mod, n)))
    passed = 0
    failed = []
    print("\n" + "=" * 70)
    print("  🧪 %s — %d حالة ⭐" % (Path(path).name, len(names)))
    print("=" * 70)
    for name in names:
        fn = getattr(mod, name)
        try:
            fn()
        except Exception:
            failed.append(name)
            print("  ❌ %s ⭐" % name, flush=True)
            traceback.print_exc()
        else:
            passed += 1
            print("  ✅ %s ⭐" % name, flush=True)
    print("  النتيجة: %d ناجح / %d فاشل" % (passed, len(failed)))
    return passed, len(failed)


def main(argv):
    paths = argv[1:]
    if not paths:
        paths = sorted(str(p) for p in (REPO / "tools").glob("test_r25_*.py"))
    total_p = 0
    total_f = 0
    for p in paths:
        p_, f_ = run(p)
        total_p += p_
        total_f += f_
    print("\n" + "=" * 70)
    print("  الإجمالي: %d ناجح / %d فاشل ⭐" % (total_p, total_f))
    print("=" * 70)
    return 1 if total_f else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
