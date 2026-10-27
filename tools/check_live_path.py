#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 فحص حيّ لمسار الإنتاج (٢٨ أكتوبر ٢٠٢٦)

⛔ ليه الملف ده موجود: في بيئة الاختبار مفيش `requests` (pip محجوب)
   ⇒ `radar_api._fetch_one` بيرجع None دايماً ⇒ كل المسارات اللي
   بتجلب شموع بتفشل في الاختبار (مش في الإنتاج).

✅ الحل: بنعمل stub بسيط لـ`requests` فوق `urllib` ⇒ نفس المسار
   بيشتغل في الاختبار ⇒ نقدر نتحقق من الكود الحقيقي (مش مزيف).

الاستخدام:  python3 tools/check_live_path.py
"""
import json
import os
import sys
import types
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_requests_stub():
    """stub لـrequests: get(url, headers=..., timeout=...) ⇒ response."""
    mod = types.ModuleType("requests")

    class Resp:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

        def json(self):
            return json.loads(self.text)

    def get(url, headers=None, timeout=20, **kw):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return Resp(r.getcode(), r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return Resp(e.code, "")
        except Exception as e:
            return Resp(0, str(e))

    def post(url, data=None, timeout=20, **kw):
        body = urllib.parse.urlencode(data or {}).encode()
        req = urllib.request.Request(url, data=body)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return Resp(r.getcode(), r.read().decode("utf-8", "replace"))
        except Exception as e:
            return Resp(0, str(e))

    mod.get = get
    mod.post = post
    mod.exceptions = types.SimpleNamespace(RequestException=Exception)
    sys.modules["requests"] = mod
    return mod


def main():
    _install_requests_stub()
    import pattern_daily as pd
    import radar_api

    print("=== ① جلب شموع حقيقي من المصدر ===")
    got, failed = radar_api.history_for(["COMI", "ETEL"], n=320)
    print("نجح: %d · فشل: %d %s" % (len(got), len(failed), failed or ""))
    for code, cols in got.items():
        t = cols.get("t") or []
        print("  %s: %d شمعة · آخرها %s · آخر إغلاق %s" % (
            code, len(t), t[-1] if t else "—", (cols.get("c") or [None])[-1]))

    print("\n=== ② بناء قائمة الأنماط (٢٠ سهم) ===")
    payload = pd.build_shortlist(max_codes=20)
    summary = payload.get("summary") or {}
    print("summary:", json.dumps(summary, ensure_ascii=False))
    print("عدد الأنماط:", payload.get("count"))
    for it in (payload.get("items") or [])[:5]:
        print("  · %s %s | %s | دخول %s وقف %s هدف %s | ع/م %s | حجم %s" % (
            it.get("code"), it.get("name"), it.get("direction"),
            it.get("entry"), it.get("stop"), it.get("target"),
            it.get("rr"), it.get("volume_confirmed")))
    if not payload.get("count"):
        print("\n⛔ مفيش أنماط — الفلاتر ممكن تكون قاسية. جرّب:")
        print("   فلاتر الحالية:", json.dumps(pd.load_filters(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
