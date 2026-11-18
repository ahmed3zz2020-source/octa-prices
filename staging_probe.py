#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔎 مساعد بيئة الـstaging — الاختبارات بتاخد paths من السيرفر نفسه

📌 المشكلة الجذرية (الجولة ٢٤ · R24):
   اختبارات الأمان كانت بتاخد مسار **صندوق البريد المحاكى** ومجلد
   **البيانات** من *ملف الإعدادات* (STAGE_CONFIG) ⇐ بينما السيرفر
   بياخدهم من *متغيّر البيئة* بتاعه (STAGE_DIR) ⇐ ومفيش حاجة تربط
   الاتنين ⇐ فلو ملف الإعدادات قديم (أو بيوجّه لنسخة تانية) ⇐
   الكود بيوصل لصندوق ما بيقراش ⇐ والاختبار بيقفل بـ unlock_expired
   ⇐ وprobe «users.json تالف» بيفحص ملف ما السيرفرش بيقراه ⇐ 200
   مش 503 ⇐ وده كله **سبب بيئي** مش عيب في الإنتاج.

✅ الحل: السيرفر هو المرجع.
   ① `server_env` بتسأل السيرفر عن بيئته الحقيقية (المسار المنشور في
      بيئة الـstaging بس · مقفول بسر الـproxy).
   ② `resolve_paths` بترجّع (مجلد البيانات · صندوق البريد · المصدر).
   ③ `read_code` بتقرأ **الجديد بس** بعد علامة (marker) ⇒ كود قديم
      من تشغيل سابق ما يقدرش يخدع أي assertion.

⛔ مافيش بريد حقيقي · مافيش حساب حقيقي · مافيش تجاوز للمصادقة.
"""
import json
import re
from pathlib import Path

import requests

# ⛔ المسار اللي بيئة الـstaging بتنشر بيه بيئتها (مش موجود في الإنتاج)
ENV_PATH = "/__staging__/env"

# ⛔ نمط الكود: 6 أرقام (زي ما السيرفر بيبعته في الإيميل)
CODE_RE = re.compile(r"([0-9]{6})")


def server_env(base, proxy, timeout=20):
    """تسأل السيرفر عن بيئته الحقيقية · بترجّع dict أو None."""
    try:
        r = requests.get(base.rstrip("/") + ENV_PATH,
                         headers={"X-OCTA-Proxy": proxy}, timeout=timeout)
    except Exception:
        return None
    if getattr(r, "status_code", 0) != 200:
        return None
    try:
        j = r.json() or {}
    except Exception:
        return None
    if not isinstance(j, dict) or not j.get("ok"):
        return None
    return j


def resolve_paths(base, proxy, cfg):
    """ترجّع (مجلد البيانات · صندوق البريد · مصدر المسارات).

    📌 الأولوية للسيرفر ⇐ لأنه المرجع الوحيد للحقيقة ⇐ ولو ماقدرناش
    📌 نوصله (سيرفر مش شغّال من الـharness) ⇐ نرجع لملف الإعدادات.
    """
    env = server_env(base, proxy)
    if env:
        dd = str(env.get("data_dir") or "").strip()
        mb = str(env.get("mailbox") or "").strip()
        if dd and mb:
            return Path(dd), Path(mb), "server"
    dd = Path(str((cfg or {}).get("data_dir") or ""))
    mb = str((cfg or {}).get("mailbox") or "").strip()
    if not mb:
        mb = str(dd / "outbox.jsonl")
    return dd, Path(mb), "config"


def mailbox_marker(mailbox):
    """علامة (إزاحة بالبايت) = نقطة بداية الرسائل الجديدة."""
    try:
        return Path(mailbox).stat().st_size
    except Exception:
        return 0


def read_code(mailbox, marker=0, to=None, kind=None):
    """ترجّع آخر كود ظاهر **بعد** العلامة · أو نص فاضي.

    ⛔ سطر مش مكتمل (كتابة اتقفلت في النص) ⇒ يتجاهل · مافيش exception.
    ⛔ كود قديم (قبل العلامة) ⇒ مش بيتقرأ · عشان ما يخدعش assertion.
    """
    try:
        with open(str(mailbox), "rb") as fh:
            fh.seek(int(marker or 0))
            blob = fh.read()
    except Exception:
        return ""
    recs = []
    for ln in blob.decode("utf-8", "replace").split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if isinstance(rec, dict):
            recs.append(rec)
    for rec in reversed(recs):
        if to and str(rec.get("to") or "") != str(to):
            continue
        if kind and kind not in str(rec.get("subject") or ""):
            continue
        found = CODE_RE.findall(str(rec.get("html") or ""))
        if found:
            return found[0]
    return ""
