# R24 · المرحلة ٢ — إثبات I04/I05/I06 (أدلة)

## النتيجة لكل معرف

| المعرف | قبل | بعد | مقفول |
|---|---|---|---|
| R22-I04 | 5/7 | 7/7 | نعم ⭐ |
| R22-I05 | 2/5 | 5/5 | نعم ⭐ |
| R22-I06 | 2/6 | 6/6 | نعم ⭐ |

### R22-I04

- المتطلب: فشل كتابة الإبطال (الـKV أو الـDO) لا ينتج نجاحاً وهمياً ⭐ ⭐
- ملف الاختبار: `assets/tests/r24-session-i04.test.js` ⭐
- الاختبار السالب: R24-I04-01 ⭐ (مزوّد معزول ⭐: كتابة الـKV ترمي ⭐ والـDO يرد ٥٠٠ ⭐) ⭐ ⭐
- قبل: 5/7 ⭐ (فشل: not ok 1 - R24-I04-01: a broken revocation write must NOT produce a false success; not ok 3 - R24-I04-03: a SILENT revocation write failure is also not a success) ⭐
- بعد: 7/7 ⭐ (فشل: —) ⭐

### R22-I05

- المتطلب: مدة صلاحية التخزين (TTL) تغطي العمر المتبقي للجلسة بهامش ⭐ + بطلان الحالة القديمة ⭐ ⭐
- ملف الاختبار: `assets/tests/r24-session-i05.test.js` ⭐
- الاختبار السالب: R24-I05-01 ⭐ (TTL = باقي العمر + هامش ⭐) ⭐ و R24-I05-02 ⭐ (العلامة بتفضل موجودة ⭐ بعد ساعة ⭐) ⭐ و R24-I05-03 ⭐ (علامة الـDO لازم صلاحية ⭐) ⭐ ⭐
- قبل: 2/5 ⭐ (فشل: not ok 1 - R24-I05-01: the KV marker TTL covers the remaining session lifetime + margin; not ok 2 - R24-I05-02: an hour later the marker must still be there (no fail-open); not ok 3 - R24-I05-03: the Durable Object marker carries an expiration (session end + margin)) ⭐
- بعد: 5/5 ⭐ (فشل: —) ⭐

### R22-I06

- المتطلب: التحقق من التوقيع وانتهاء الصلاحية يسبق أي نداء إلى DO/KV ⭐ ⭐
- ملف الاختبار: `assets/tests/r24-session-i06.test.js` ⭐
- الاختبار السالب: R24-I06-01 ⭐ (كوكي مزوّر ⭐ ⇒ صفر نداءات ⭐) ⭐ و R24-I06-02 ⭐ (كوكي منتهٍ ⭐ ⇒ صفر نداءات ⭐) ⭐ ⭐
- قبل: 2/6 ⭐ (فشل: not ok 1 - R24-I06-01: a FORGED cookie never reaches the storage (zero calls); not ok 2 - R24-I06-02: an EXPIRED cookie never reaches the storage (zero calls); not ok 3 - R24-I06-03: a MALFORMED cookie never reaches the storage (zero calls); not ok 6 - R24-I06-06: a forged cookie is refused on a protected API too) ⭐
- بعد: 6/6 ⭐ (فشل: —) ⭐

## Durable Object (معاينة معزولة ⭐)

- المشغّل: wrangler 3.114.14 ⭐ + workerd/miniflare محلي ⭐ ⭐ ⭐
- phase1_storage_fault: 9/9 ⭐
- phase2_healthy: 15/15 ⭐
- phase3_after_restart: 15/15 ⭐
- ⛔ مفيش مورد سحابي ⭐ ⭐
- ⚠️ ⛔ لو فشل **كتابة** الإتباط ⭐ ⇒ النسخة اللي حاولت ⭐ رفضت الجلسة ⭐ لكن **النسخ التانية** ⭐ ممكن تقبلها ⭐ (لأن العلامة ما اتكتبتش ⭐) ⭐ ⇒ ده حدّ مادي ⭐ (مش فيه مخزن شغّال ⭐) ⭐ ⇒ الحل ⭐: إما Storage ⭐ يعمل ⭐ أو تدوير SESSION_SECRET ⭐ ⭐
