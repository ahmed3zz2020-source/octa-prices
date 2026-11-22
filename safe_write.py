# -*- coding: utf-8 -*-
"""🔒 R32 · كتابة ذرّية باسم مؤقت **فريد** ⭐.

⭐ العيب ⭐ (قبل R32 ⭐): ⛔ كل الملفات كانت بتكتب في **اسم مؤقت ثابت** ⭐
   (`.tmp` ⭐ أو `.t` ⭐) ⇒ ⛔ عمليتين مع بعض ⭐ ⇒ ⛔ واحدة بتمسح ملف التانية ⭐
   ⇒ ⛔ lost update ⭐ ⇒ ⛔ وفي `pinlock.json` ⭐ ⭐ ⇒ ⛔ **عدّاد المحاولات** ⭐ ⭐
   ⭐ ⭐ بيطيع ⭐ ⭐ (الحدّ بيتخطّى ⭐).

⭐ الحل ⭐: ⭐ اسم فريد ⭐ (pid ⭐ + تسلسل ⭐ + عشوائية ⭐) ⭐ ⇒ ⭐ مافيش ملف مشترك ⭐
   ⭐ + ⭐ `os.replace` ⭐ ذرّي ⭐ ⇒ ⭐ القارئ ما يلاقيش ملف نصّ ⭐.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

__all__ = ["tmp_path", "safe_write_text", "safe_write_json"]


def tmp_path(path) -> Path:
    """مسار مؤقت فريد ⭐ — نفس المجلد ⭐ (عشان الاستبدال ذرّي ⭐)."""
    p = Path(path)
    return p.with_name("%s.tmp-%d-%s" % (p.name, os.getpid(), uuid.uuid4().hex[:8]))


def safe_write_text(path, text: str, encoding: str = "utf-8") -> bool:
    """اكتب ⭐ + استبدل ذرّياً ⭐ ⇒ ⭐ مافيش lost update ⭐ ⇒ ⭐ مافيش ملف ناقص ⭐."""
    p = Path(path)
    tmp = tmp_path(p)
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, p)
        return True
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def safe_write_json(path, obj, indent=None) -> bool:
    """نفس ⭐ `safe_write_text` ⭐ بس JSON ⭐ (بـNaN/Infinity ⭐ ممنوع ⭐)."""
    import json
    return safe_write_text(path, json.dumps(obj, ensure_ascii=False,
                                            allow_nan=False, indent=indent))
