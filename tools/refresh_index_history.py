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
   git add data/index_history.json && git commit -m "رسالة Commit"

📌 ⛔ ممنوع نخترع أي رقم — لو الـwebsocket رجّع غلط، الملف بيتكتب ناقص
   (والباك هيقول «غير متاح» بدل ما يعرض رقم مش حقيقي).

🛡️ الجولة ٢٣ (R23) — الحارس بقى **fail-closed** ⭐:
   ⛔ ما ينفعش نكتب تاريخ **مبتور** ⭐ (تاريخ قديم يتشال ⭐).
   ⛔ ما ينفعش نكتب تاريخ **مكرّر** ⭐ (نفس اليوم مرتين ⭐).
   ⛔ ما ينفعش نكتب تاريخ **مُعاد كتابته** ⭐ (قيمة تاريخ قديم تتغيّر ⭐).
   ⛔ ما ينفعش نكتب ملف **ناقص الحقول** ⭐ (count/from/to لازم يطابقوا الصفوف ⭐).
   ⛔ الكتابة **ذرّية** ⭐: ملف مؤقّت + fsync + فحص الملف المؤقّت + rename ⭐
      ⇒ مافيش لحظة في الديسك فيها ملف نص مكتوب ⭐.
   ⇒ الفحص كله بيستخدم نفس دوال الحارس ⭐ (tools/verify_data_integrity.py ⭐).
"""
import io
import json
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

OUT = os.path.join(ROOT, "data", "index_history.json")

# ⭐ نفس الحارس ⭐ — دوال فحص البنية + المقارنة ⭐
from verify_data_integrity import (  # noqa: E402
    compare_history,
    utc_date,
    validate_payload,
)

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


def atomic_write_json(path, payload):
    """كتابة ذرّية fail-closed ⭐

    ⛔ مافيش ملف نص مكتوح في الديسك ⭐ (كله ملف مؤقّت ⭐).
    ⛔ لوanything فشل ⇒ الملف المؤقّت يتمسح ⭐ والملف القديم يفضل زي ما هو ⭐.
    """
    tmp = path + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        # ⭐ نفحص الملف المؤقّت نفسه قبل ما نعمله rename ⭐
        with io.open(tmp, encoding="utf-8") as handle:
            written = json.load(handle)
        problems = validate_payload(written)
        if problems:
            raise ValueError("الملف المؤقّت مش سليم: %s" % "; ".join(problems[:5]))
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise
    try:
        dir_fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


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
        if not rows:
            print("❌ %s — مفيش صفوف صالحة" % sym)
            continue

        out["indices"][idx_id] = {
            "symbol": sym,
            "name_ar": name_ar,
            "name_en": name_en,
            "official_inception": inception,
            "official_note": note,
            "from": utc_date(rows[0][0]),
            "to": utc_date(rows[-1][0]),
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

    # 🛡️ الجولة ٢١ (R21) — ⛔⛔ **حارس ضد القصّ** ⭐⭐
    # 📌 العيب المقاس (الجولة ٢٠): الملف اتكتب بـ**120 صف** بدل **7,028** ⭐
    #   ⇒ ⛔ تاريخ المؤشرات اتقصّ ⇒ ⛔ الـbacktesting|Price-action اتأثر ⭐
    # 📌 السبب: سكربت التحديث كتب نسخة **مبتورة** فوق نسخة **أ fullest** ⭐
    # ✅ القاعدة: ⛔ ما ينفعش نكتب بيانات **أقل** من الموجودة ⭐
    #   ⛔ أو ننسخ مؤشر معيّن من الملف القديم ⭐ (partial write ⭐).
    # 🛡️ الجولة ٢٣ (R23) — تشديد ⭐:
    #   ⛔ مفيش تاريخ قديم يتشال ⭐ (مش عدد الصفوف بس ⭐)
    #   ⛔ مفيش قيمة تاريخية تتغيّر ⭐ (تاريخ مُعاد كتابته ⭐)
    #   ⛔ مافيش تاريخ مكرّر ⭐ (structural check ⭐)
    #   ⛔ count/from/to لازم يطابقوا الصفوف ⭐
    old_payload = None
    try:
        with io.open(OUT, encoding="utf-8") as handle:
            old_payload = json.load(handle)
    except FileNotFoundError:
        print("ℹ️ مافيش ملف قديم — هنكتب أول نسخة ⭐")
    except Exception as exc:
        print("❌⛔ مقدرتش أقرأ الملف القديم: %s — ⛔ مش هكتب" % str(exc)[:120])
        return 1

    if old_payload is not None:
        problems = compare_history(old_payload, out)
        if problems:
            print("❌⛔ الحارس رفض الكتابة ⭐ (التاريخ الجديد مينفعش يكمّل القديم ⭐):")
            for problem in problems[:12]:
                print("   - %s" % problem)
            print("   ⛔ الملف القديم اتساب زي ما هو ⭐")
            return 1

    # ⭐ فحص البنية والسلامة للحمولة الجديدة ⭐ (قبل أي كتابة ⭐)
    problems = validate_payload(out)
    if problems:
        print("❌⛔ الحارس رفض الكتابة ⭐ (الحمولة الجديدة مش سليمة ⭐):")
        for problem in problems[:12]:
            print("   - %s" % problem)
        return 1

    # ⭐ كتابة ذرّية ⭐ (مافيش ملف نص مكتوح ⭐)
    try:
        atomic_write_json(OUT, out)
    except Exception as exc:
        print("❌⛔ الكتابة الذرّية فشل: %s — ⛔ الملف القديم اتساب زي ما هو ⭐"
              % str(exc)[:160])
        return 1

    print("\n💾 اتكتب: %s (%.1f KB) ⭐" % (OUT, os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
