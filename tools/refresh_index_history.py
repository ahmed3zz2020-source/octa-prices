#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 تحديث سلسلة التاريخ الرسمية لمؤشرات البورصة المصرية — ٢٦ أكتوبر ٢٠٢٦
═══════════════════════════════════════════════════════════════════════════

📌 ليه الملف ده موجود:
   صفحة «ذكاء المؤشرات» محتاجة تاريخ **سنوي** لكل مؤشر (مش بس سعر اليوم).
   والمصدر الوحيد اللي بيدّي تاريخ طويل هو TradingView websocket
   (الـscanner بيدّي السعر الحالي بس).

📌 ليه ما بنجيبهاش أوتوماتيك من السيرفر؟
   الـwebsocket بيسيب Origin = tradingview.com بس ⇒
   المتصفح والـworker مش قادرين يفتحوه (403).
   ⇒ التحديث بيتعمل من بيئة التطوير (هنا) والملف بيتبعت مع git.
   (نفس نمط data/egx30_history.json)

📌 التغطية الفعلية (٢٠٢٦-١٠-٢٦):
   EGX30        ١٩٩٨-٠١-٠١ → اليوم   (٧٠٢٥ يوم)  ✅ كامل (أساس المؤشر 4/1/1998)
   EGX70 EWI    ٢٠١٧-٠١-٠٢ → اليوم   (٢٣٧٩ يوم)  ⚠️ ناقص (الاحتساب الرسمي بدأ 2008)
   EGX100 EWI   ٢٠٢٠-٠٥-١٠ → اليوم   (١٥٦٥ يوم)  ⚠️ ناقص (الاحتساب الرسمي بدأ 2006)
   EGX 33 Shariah ٢٠٢٢-٠١-٠٢ → اليوم (١١٦٥ يوم)  ✅ كامل (تاريخ الأساس 1/1/2022)

📌 طريقة التشغيل:
   cd octa-prices
   python3 tools/refresh_index_history.py
   git add data/index_history.json && git commit -m "..."

📌 ⛔ ممنوع نخترع أي رقم — لو الـwebsocket رجّع غلط، الملف بيتكتب ناقص
   (والباك هيقول «غير متاح» بدل ما يعرض رقم مش حقيقي).
"""
import json
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "data", "index_history.json")

# (id, tv symbol, name_ar, name_en, official_inception, note)
INDICES = [
    ("EGX30", "EGX:EGX30", "مؤشر البورصة المصرية", "EGX 30",
     "1998-01-04", "أساس المؤشر 4/1/1998 بقيمة 1000 نقطة (صفحة EGX الرسمية)"),
    ("EGX70", "EGX:EGX70EWI", "مؤشر الأسهم الصغيرة والمتوسطة", "EGX 70 EWI",
     "2008-01-02", "الاحتساب الرسمي بدأ 2/1/2008 بقيمة 1000 نقطة (EGX)"),
    ("EGX100", "EGX:EGX100EWI", "مؤشر السوق الأوسع", "EGX 100 EWI",
     "2006-01-02", "الاحتساب الرسمي بدأ 2/1/2006 بقيمة 1000 نقطة (EGX)"),
    ("EGX33", "EGX:SHARIAH", "مؤشر الشريعة", "EGX 33 Shariah",
     "2022-01-01", "تاريخ الأساس 1/1/2022 بقيمة 1000 نقطة (EGX)"),
]

COUNT = 12000  # TradingView بيرجّع كل المتاح


def main():
    try:
        import tv_ws
    except Exception as e:
        print("❌ مش قادرين نعمل import لـtv_ws: %s" % str(e)[:120])
        print("   شغّل السكربت من جوه مجلد octa-prices")
        return 1

    out = {
        "version": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "source": "TradingView websocket (data.tradingview.com) — الإغلاقات اليومية",
        "source_note": (
            "سلسلة إغلاقات يومية لمؤشرات البورصة المصرية. المصدر: TradingView websocket. "
            "تواريخ الأساس والمكونات والمنهجية الرسمية من موقع البورصة المصرية الرسمي (egx.com.eg)."
        ),
        "coverage_note": (
            "⚠️ التغطية مختلفة بين المؤشرات: EGX30 و EGX33 كاملين من تاريخ الأساس، "
            "بينما EGX70 و EGX100 المتاح عندنا يبدأ متأخراً عن تاريخ احتسابهما الرسمي. "
            "الباك بي disclose التغطية الفعلية لكل مؤشر — مفيش أي ادعاء بتغطية غير موجودة."
        ),
        "indices": {},
    }

    for idx_id, sym, name_ar, name_en, inception, note in INDICES:
        t0 = time.time()
        try:
            bars = tv_ws.fetch_series(sym, COUNT)
        except Exception as e:
            print("❌ %s فشل: %s" % (sym, str(e)[:120]))
            bars = []
        if not bars:
            print("❌ %s — مفيش بيانات" % sym)
            continue

        # تنظيف: نزيل تكرار نفس اليوم (لوwebsocket رجّع أكتر من شمعة لنفس اليوم)
        by_day = {}
        for b in bars:
            c = b.get("c")
            if c is None:
                continue
            day = datetime.datetime.utcfromtimestamp(b["t"]).strftime("%Y-%m-%d")
            # آخر قيمة في نفس اليوم هي الأصح (الشمعة جارية)
            by_day[day] = [int(b["t"]), round(float(c), 4)]
        rows = [by_day[d] for d in sorted(by_day.keys())]

        out["indices"][idx_id] = {
            "symbol": sym,
            "name_ar": name_ar,
            "name_en": name_en,
            "official_inception": inception,
            "official_note": note,
            "from": rows[0][0] and datetime.datetime.utcfromtimestamp(rows[0][0]).strftime("%Y-%m-%d"),
            "to": datetime.datetime.utcfromtimestamp(rows[-1][0]).strftime("%Y-%m-%d"),
            "count": len(rows),
            "rows": rows,
        }
        print("✅ %-9s %5d يوم  %s → %s  (%.0fs)" % (
            idx_id, len(rows), out["indices"][idx_id]["from"],
            out["indices"][idx_id]["to"], time.time() - t0))
        time.sleep(0.4)

    if not out["indices"]:
        print("❌ مفيش أي مؤشر اتجلب — مش هنكتب ملف فاضي")
        return 1

    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print("\n💾 اتكتب: %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
