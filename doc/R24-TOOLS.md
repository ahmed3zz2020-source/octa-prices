🧰 الجولة ٢٤ (R24) — أدوات الجولة ⭐ (باني الأدلة ⭐ + معاينة الـDO ⭐)

📌 `tools/r24_evidence.py` ⭐ ⭐
   باني الأدلة ⭐ (JSON ⭐ + MD ⭐) ⭐ في ٣ ملفات ⭐:
   ① phase1_safe_rollback ⭐ (نسخة التراجع الآمنة ⭐)
   ② phase1_cloudflare_permissions ⭐ (مصفوفة الصلاحيات ⭐)
   ③ phase2_session_proofs ⭐ (إثبات I04/I05/I06 ⭐ + الـDO ⭐)
   📌 التشغيل ⭐: /tmp/ci_r23_venv/bin/python tools/r24_evidence.py ⭐
   📌 المتغيّرات ⭐ (اختيارية ⭐): R24_FE_ROOT ⭐ · R24_BE_ROOT ⭐ ·
   R24_EVIDENCE_DIR ⭐ · R24_CONTAIN_DIR ⭐ · R24_DO_PREVIEW ⭐.
   ⛔ مافيش نشر ⭐ · مافيش سر ⭐ · مافيش مورد مدفوع ⭐.

📌 `tools/r24_do_preview.sh` ⭐ ⭐
   تشغيل معاينة الـDurable Object المعزولة ⭐ (wrangler محلي ⭐ = ٠$ ⭐):
   ① كسر كتابة التخزين ⭐ ⇒ لازم ٥٠٣ ⭐ (ممنوع نجاح وهمي ⭐)
   ② التشغيل السليم ⭐ ⇒ إبطال فوري ⭐ + ٢٥ طلب متوازي ⭐
   ③ إعادة تشغيل المشغّل ⭐ ⇒ المصدر القوي صامد ⭐
   ⛔ مافيش مورد سحابي ⭐.
