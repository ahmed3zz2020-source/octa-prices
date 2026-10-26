#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📸 لقطة رسمية من البورصة المصرية — ٢٦ أكتوبر ٢٠٢٦
═══════════════════════════════════════════════════════════════════════════

📌 ليه الملف ده موجود:
   صفحة «ذكاء المؤشرات» لازم تعرض أرقام **رسمية** (وزن كل مكون + لقطة
   المؤشر + حالة السوق) مش أرقام متجمّعة من جهات تانية.

📌 ليه بنجيبه من المتصفح مش من السيرفر؟
   موقع البورصة (beta.egx.com.eg) محمي بـF5/TSPD ⇒ أي طلب مش من
   متصفح حقيقي بيرجّع 404. ⇒ الجلب من بيئة التطوير (هنا) والملف
   بيتخزّن مع git (نفس نمط data/egx30_history.json).

📌 طريقة التشغيل:
   cd octa-prices
   node tools/fetch_egx_official.js
   git add data/index_official.json && git commit -m "..."

📌 ⛔ لو البورصة مش رادّة ⇒ الملف مش بيتكتب (مفيش أرقام مخترعة).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "index_official.json")
NODE_SCRIPT = os.path.join(HERE, "fetch_egx_official.js")

INDEXES = ["CASE30", "EGX70_EWI", "EGX100_EWI", "EGX_SHARIAH"]


def main():
    if not os.path.exists(NODE_SCRIPT):
        print("❌ مش موجود: %s" % NODE_SCRIPT)
        return 1
    r = subprocess.run(["node", NODE_SCRIPT], capture_output=True, text=True, timeout=600)
    sys.stdout.write(r.stdout or "")
    sys.stderr.write(r.stderr or "")
    if r.returncode != 0:
        print("❌ سكربت الـnode فشل")
        return 1
    if not os.path.exists(OUT):
        print("❌ مفيش ملف ناتج")
        return 1
    d = json.load(open(OUT, encoding="utf-8"))
    print("\n💾 %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))
    print("   market_status:", json.dumps(d.get("market_status"), ensure_ascii=False))
    for k, v in (d.get("indices") or {}).items():
        print("   %-10s live=%s weights=%d constituents=%d" % (
            k,
            (v.get("live") or {}).get("indexClose"),
            len(v.get("weights") or []),
            len(v.get("constituents") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
