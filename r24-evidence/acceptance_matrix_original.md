# OCTA Round 24 - Original acceptance register (parsed verbatim)

Source of truth: the owner-supplied text appendix of OCTA_Final_Acceptance_Center.xlsx (sha256 b60b0c5651b8df44fd0f64fcc8bb6100841f5ce0731d4b67f51e7d1bd379df46).
No criterion was added, removed, reworded, or invented.
Scopes: 36. Items: 144. Points per scope: 100. Total points: 3600.

## 01 - خريطة المشروع والمستودعات ونقاط الدخول

Prior review: تمت المراجعة

- AC-01-1 | وظيفة وحسابات | weight 35
  - success: خريطة المستودعات تطابق مكونات الواجهة والباك وWorker وكل نقاط الدخول مع SHA وmanifest.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-028/029; R17-V2-03
- AC-01-2 | أمان واستثناءات | weight 30
  - success: أزل bundle أو غيّر ref؛ يجب رفض المرشح وعدم تسجيل نجاح.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-028/029; R17-V2-03
- AC-01-3 | تكامل وتجربة | weight 25
  - success: استخرج الحزم في مجلد نظيف وتحقق من تطابق الشجرة والبناء واعتمادياتها دون نشر.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-028/029; R17-V2-03
- AC-01-4 | انحدار وتوثيق | weight 10
  - success: وثق أوامر الاسترجاع، الفروق والملفات المشمولة ونتيجة الحارس قبل وبعد.
  - verification: انحدار + دليل مستقل
  - reference: SEC-028/029; R17-V2-03

## 02 - أمان البوابة وتوثيق الجلسة

Prior review: تمت المراجعة

- AC-02-1 | وظيفة وحسابات | weight 35
  - success: الدخول إلى صفحة وأداة محمية يتطلب جلسة موقعة وصالحة وتتحقق API من السلطة.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-001/002/009
- AC-02-2 | أمان واستثناءات | weight 30
  - success: كوكي فارغ/مزور/منتهي أو طلب مباشر بلا proxy صالح يرفض بلا بيانات داخلية.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-001/002/009
- AC-02-3 | تكامل وتجربة | weight 25
  - success: Worker + Flask حقيقيان: دخول صناعي ثم طلب محمي عبر المسار الصحيح؛ اختبر الرفض المباشر.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-001/002/009
- AC-02-4 | انحدار وتوثيق | weight 10
  - success: سجل HTTP منقح واختبارات انحدار لمسارات التشخيص والبوابة.
  - verification: انحدار + دليل مستقل
  - reference: SEC-001/002/009

## 03 - التسجيل وPIN وOTP والبصمة

Prior review: تمت المراجعة

- AC-03-1 | وظيفة وحسابات | weight 35
  - success: تسجيل واسترجاع PIN وOTP صناعيان يعملان حسب السياسة المعتمدة؛ البصمة القديمة تظل مغلقة.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-003/004/005; UX-LOGIN-01
- AC-03-2 | أمان واستثناءات | weight 30
  - success: OTP خاطئ أو منتهي أو مستخدم سابقًا لا يعمل؛ PIN جديد يبطل التوكن القديم؛ لا أكواد خام في التخزين.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-003/004/005; UX-LOGIN-01
- AC-03-3 | تكامل وتجربة | weight 25
  - success: رحلة حساب جديد ثم استرجاعه في متصفح حقيقي ومزود رسائل صناعي دون إرسال فعلي.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-003/004/005; UX-LOGIN-01
- AC-03-4 | انحدار وتوثيق | weight 10
  - success: أرفق اختبار فشل/نجاح ومراجعة سياسة الاسترجاع؛ لا تغير المسار المؤجل دون قرار.
  - verification: انحدار + دليل مستقل
  - reference: SEC-003/004/005; UX-LOGIN-01

## 04 - توكنات الجلسات والكوكي وتسجيل الخروج

Prior review: تمت المراجعة

- AC-04-1 | وظيفة وحسابات | weight 35
  - success: إصدار جلسة بمدة صحيحة وخصائص كوكي مناسبة والتأكد من إبطالها عند الخروج.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-006/007/008/010/022
- AC-04-2 | أمان واستثناءات | weight 30
  - success: إعادة استخدام توكن قديم بعد logout أو تغيير epoch أو PIN مرفوضة؛ فشل الإبطال لا يعرض نجاحًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-006/007/008/010/022
- AC-04-3 | تكامل وتجربة | weight 25
  - success: اختبر تبويبين ومتصفحًا حقيقيًا وAPI عبر Worker؛ تحقق من صلاحيات الجلسة بعد الخروج.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-006/007/008/010/022
- AC-04-4 | انحدار وتوثيق | weight 10
  - success: وثق خصائص الكوكي دون قيمة سرية واختبارات المدة وفشل التخزين.
  - verification: انحدار + دليل مستقل
  - reference: SEC-006/007/008/010/022

## 05 - عزل المستخدم والصلاحيات والاشتراكات

Prior review: تمت المراجعة

- AC-05-1 | وظيفة وحسابات | weight 35
  - success: Free/Pro/expired/admin يكتسبون فقط الأذونات وفق جدول باقات معتمد.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-011/012/013/015/016/017
- AC-05-2 | أمان واستثناءات | weight 30
  - success: حساب A لا يقرأ أو يغير حساب B؛ UID مزيف أو خطة منتهية أو مجهولة لا ترفع الصلاحية.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-011/012/013/015/016/017
- AC-05-3 | تكامل وتجربة | weight 25
  - success: حسابان صناعيان على Flask وWorker: عرض المحفظة والتنبيه والإدارة لكل دور.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-011/012/013/015/016/017
- AC-05-4 | انحدار وتوثيق | weight 10
  - success: سجل مصفوفة الأدوار والمسارات ونتائج منع الوصول لكل حالة.
  - verification: انحدار + دليل مستقل
  - reference: SEC-011/012/013/015/016/017

## 06 - API والطلبات والمدخلات وCSRF وCORS

Prior review: تمت المراجعة

- AC-06-1 | وظيفة وحسابات | weight 35
  - success: API يطبق schema وحدود الحقول والأحجام وحالات HTTP لكل مسار.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-018/019/021/024
- AC-06-2 | أمان واستثناءات | weight 30
  - success: CSRF وorigin غير مسموح وNaN وJSON تالف وحمولة كبيرة ترفض دون أثر كتابة أو كشف بيانات.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-018/019/021/024
- AC-06-3 | تكامل وتجربة | weight 25
  - success: طلبات HTTP فعلية من Worker ومتصفح بأصول مسموحة وغير مسموحة؛ صفر اتصال مدفوع في الاختبار.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-018/019/021/024
- AC-06-4 | انحدار وتوثيق | weight 10
  - success: وثق مصفوفة CORS/CSRF ونتائج validation وحدود AI المعتمدة.
  - verification: انحدار + دليل مستقل
  - reference: SEC-018/019/021/024

## 07 - متصفح XSS/CSP والكاش والأكواد الخارجية

Prior review: تمت المراجعة

- AC-07-1 | وظيفة وحسابات | weight 35
  - success: محتوى المستخدم يعرض كنص آمن؛ الأصول العامة لا تحوي بيانات حساب أو snapshots محظورة.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-022/023/034; MGMT-001
- AC-07-2 | أمان واستثناءات | weight 30
  - success: نص XSS صناعي لا ينفذ؛ ذاكرة التخزين المشتركة لا تعرض بيانات مستخدم سابق أو ملفات محمية.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-022/023/034; MGMT-001
- AC-07-3 | تكامل وتجربة | weight 25
  - success: اختبر متصفحين وكاش وService Worker وmanifest الإنتاج في معاينة مصرح بها فقط.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-022/023/034; MGMT-001
- AC-07-4 | انحدار وتوثيق | weight 10
  - success: أدلة CSP والكاش وتدقيق dist؛ تطبيق CSP الفعلي يحتاج قرارًا منفصلًا.
  - verification: انحدار + دليل مستقل
  - reference: SEC-022/023/034; MGMT-001

## 08 - GitHub/Railway/Cloudflare والأسرار

Prior review: تمت المراجعة

- AC-08-1 | وظيفة وحسابات | weight 35
  - success: اعتماد خريطة GitHub/Railway/Cloudflare وسياسات أقل صلاحية وفصل الأسرار لكل بيئة.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-027/028/029; PROD-001..003
- AC-08-2 | أمان واستثناءات | weight 30
  - success: غياب سر مطلوب أو KV خطأ يمنع المرور؛ لا أسرار أو PII في الأدلة أو الأصول العامة.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-027/028/029; PROD-001..003
- AC-08-3 | تكامل وتجربة | weight 25
  - success: تحقق قراءة فقط من رؤوس الفروع وهوية الخدمة وفصل preview/prod؛ لا تغيير إعدادات.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-027/028/029; PROD-001..003
- AC-08-4 | انحدار وتوثيق | weight 10
  - success: وثق قائمة الأسرار بالأسماء فقط وملكية الحماية وخطة التعرض والتدوير المصرح بها.
  - verification: انحدار + دليل مستقل
  - reference: SEC-027/028/029; PROD-001..003

## 09 - اختبارات الأمان على Staging المعزول

Prior review: جزئي (اختبار حي)

- AC-09-1 | وظيفة وحسابات | weight 35
  - success: Flask/Werkzeug وWorker حقيقيان ببيانات صناعية ومجلد مؤقت وعزل شبكة.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-009; STG-09-01/02; BE-012
- AC-09-2 | أمان واستثناءات | weight 30
  - success: صفر محاولة Thread.start غير مصرح بها؛ منع egress؛ proxy مفقود/خاطئ يرفض حسب عقد البيئة.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-009; STG-09-01/02; BE-012
- AC-09-3 | تكامل وتجربة | weight 25
  - success: اختبر مصادقة وعزل A/B وCSRF وepoch وأدوار Free/Pro/expired في staging مستقل بلا tunnel.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-009; STG-09-01/02; BE-012
- AC-09-4 | انحدار وتوثيق | weight 10
  - success: أرفق نتائج HTTP وأدلة العزل ومنع الاتصال وقائمة المهام؛ المحاكي لا يكفي.
  - verification: انحدار + دليل مستقل
  - reference: SEC-009; STG-09-01/02; BE-012

## 10 - معمارية الباك والتخزين والتحمّل

Prior review: تمت المراجعة

- AC-10-1 | وظيفة وحسابات | weight 35
  - success: قراءة وكتابة متسقة من طبقة التخزين ومسارات الصحة مع نموذج أعطال موثق.
  - verification: اختبار وحدة / golden fixture
  - reference: BE-001..006
- AC-10-2 | أمان واستثناءات | weight 30
  - success: فشل كتابة أو قفل أو ملف ناقص لا يضيع آخر حالة صحيحة ولا يرجع نجاحًا كاذبًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: BE-001..006
- AC-10-3 | تكامل وتجربة | weight 25
  - success: تحميل صناعي متزامن من عاملين ثم إعادة تشغيل ومقارنة الحالة المرجعية.
  - verification: تكامل واقعي / UAT معزول
  - reference: BE-001..006
- AC-10-4 | انحدار وتوثيق | weight 10
  - success: وثق نموذج البيانات وتتبع أخطاء القراءة/الكتابة واختبارات التراجع.
  - verification: انحدار + دليل مستقل
  - reference: BE-001..006

## 11 - تحديثات أسعار السوق وأعمار البيانات

Prior review: تمت المراجعة

- AC-11-1 | وظيفة وحسابات | weight 35
  - success: السعر يحمل زمن صفقة ومصدرًا وعمرًا صحيحًا؛ 100% فقط complete وعدد/نسبة متوافقان.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-001..010; R17-V2-01/04
- AC-11-2 | أمان واستثناءات | weight 30
  - success: دفعة قديمة/unknown أو مستقبلية أو متوقفة لا توصف live؛ 0/0 و110/100 و90% مع 895/1000 ترفض التعارض.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-001..010; R17-V2-01/04
- AC-11-3 | تكامل وتجربة | weight 25
  - success: ساعة صناعية عبر المسارات الخمسة ثم توقف التحديث؛ طابق الصف مع حالة الدفعة.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-001..010; R17-V2-01/04
- AC-11-4 | انحدار وتوثيق | weight 10
  - success: أرفق fixtures لحالات fresh/stale/unavailable والتغطية وحدود الزمن.
  - verification: انحدار + دليل مستقل
  - reference: MD-001..010; R17-V2-01/04

## 12 - نظام الطوابير والتزامن والمهام الخلفية

Prior review: تمت المراجعة

- AC-12-1 | وظيفة وحسابات | weight 35
  - success: المهام المصرح بها تعمل وفق الجدولة وبلا تنفيذ مكرر لنفس المفتاح.
  - verification: اختبار وحدة / golden fixture
  - reference: BE-007..013; STG-09-01
- AC-12-2 | أمان واستثناءات | weight 30
  - success: تزامن عمليتين وتهيئة مكررة وoff لا يسببان تكرار أو بدء مهمة غير مصرح بها.
  - verification: اختبار سلبي / حقن أعطال
  - reference: BE-007..013; STG-09-01
- AC-12-3 | تكامل وتجربة | weight 25
  - success: عاملان صناعيان، فشل مهمة ثم restart؛ تحقق من idempotency وأقفال البيانات.
  - verification: تكامل واقعي / UAT معزول
  - reference: BE-007..013; STG-09-01
- AC-12-4 | انحدار وتوثيق | weight 10
  - success: سجل عدد التنفيذ والمهام وحالات الانتقال دون تفاصيل حساسة.
  - verification: انحدار + دليل مستقل
  - reference: BE-007..013; STG-09-01

## 13 - أعطال النظام والمهلات وإعادة المحاولة والاستعادة

Prior review: تمت المراجعة

- AC-13-1 | وظيفة وحسابات | weight 35
  - success: مهلة وretry محدودان؛ فشل مصدر لا يحجب مصدرًا مستقلاً.
  - verification: اختبار وحدة / golden fixture
  - reference: BE-014..019; AZ30-RETRY
- AC-13-2 | أمان واستثناءات | weight 30
  - success: مهلة أو 429 أو 5xx أو رد تالف لا يسبب حلقة طلبات أو إعادة POST غير idempotent.
  - verification: اختبار سلبي / حقن أعطال
  - reference: BE-014..019; AZ30-RETRY
- AC-13-3 | تكامل وتجربة | weight 25
  - success: حقن أعطال متدرجة ثم عودة المصدر؛ تحقق من عدم مسح الحالة الصحيحة.
  - verification: تكامل واقعي / UAT معزول
  - reference: BE-014..019; AZ30-RETRY
- AC-13-4 | انحدار وتوثيق | weight 10
  - success: أرفق timeline وزمن الاستعادة وعدد الطلبات وسبب كل retry.
  - verification: انحدار + دليل مستقل
  - reference: BE-014..019; AZ30-RETRY

## 14 - التخزين الدائم والنسخ الاحتياطي وتماسك الحالة

Prior review: تمت المراجعة

- AC-14-1 | وظيفة وحسابات | weight 35
  - success: حفظ ذري ونسخ احتياطي صالح مع رقم نسخة ووقت متسق.
  - verification: اختبار وحدة / golden fixture
  - reference: BE-020..028; MD-039
- AC-14-2 | أمان واستثناءات | weight 30
  - success: اسقط العملية أثناء الحفظ أو قدم backup تالفًا؛ لا استبدال للنسخة الصحيحة أو نجاح كاذب.
  - verification: اختبار سلبي / حقن أعطال
  - reference: BE-020..028; MD-039
- AC-14-3 | تكامل وتجربة | weight 25
  - success: استرجع نسخة صناعية في بيئة مستقلة وطابق checksum والسجلات والحسابات.
  - verification: تكامل واقعي / UAT معزول
  - reference: BE-020..028; MD-039
- AC-14-4 | انحدار وتوثيق | weight 10
  - success: وثق زمن وفجوة الاسترجاع مقابل RTO/RPO المقترحين بعد اعتماد المالك.
  - verification: انحدار + دليل مستقل
  - reference: BE-020..028; MD-039

## 15 - مصداقية المصادر وترتيب الأولوية والإسناد

Prior review: تمت المراجعة

- AC-15-1 | وظيفة وحسابات | weight 35
  - success: لكل قيمة مالية مصدر وتوقيت ووحدة؛ ترتيب fallback حسب سياسة معتمدة.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-011..018
- AC-15-2 | أمان واستثناءات | weight 30
  - success: تعارض مصدرين أو غياب مصدر أو توقيت مزور لا يصنع قيمة حديثة أو مصدرًا وهميًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-011..018
- AC-15-3 | تكامل وتجربة | weight 25
  - success: قارن عينة ثابتة من مصادر موثوقة مصرح بها مع العرض والـAPI في الوقت نفسه.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-011..018
- AC-15-4 | انحدار وتوثيق | weight 10
  - success: أرفق جدول المصدر/التوقيت والفروق مع حدود التقريب المعتمدة.
  - verification: انحدار + دليل مستقل
  - reference: MD-011..018

## 16 - سلامة الجداول والأسهم والمطابقة بين الأسواق

Prior review: تمت المراجعة

- AC-16-1 | وظيفة وحسابات | weight 35
  - success: رموز الأسهم وأسماء الشركات ومكونات المؤشرات تطابق مرجعًا بتاريخ سريان واضح.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-019..026
- AC-16-2 | أمان واستثناءات | weight 30
  - success: رمز محذوف/مكرر/مشابه أو سهم موقوف لا يعين إلى شركة خاطئة أو يختفي بلا تفسير.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-019..026
- AC-16-3 | تكامل وتجربة | weight 25
  - success: مطابقة عينة وقائمة الكون المرجعية مع البحث والفلاتر والمقارنة بنفس تاريخ البيانات.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-019..026
- AC-16-4 | انحدار وتوثيق | weight 10
  - success: أرفق diff قائمة الرموز والمكونات والاستثناءات الموثقة.
  - verification: انحدار + دليل مستقل
  - reference: MD-019..026

## 17 - المؤشرات والعملات والذهب ودقة الوحدات والتحويل

Prior review: تمت المراجعة

- AC-17-1 | وظيفة وحسابات | weight 35
  - success: المؤشرات والعملات والذهب تستخدم EGP/USD الصحيح وعيار 21/24 وسعر جرام موثق.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-027..031; AZ28-SIGN
- AC-17-2 | أمان واستثناءات | weight 30
  - success: انعكاس زوج العملة أو اختلاف وحدة الأونصة/الجرام أو قيمة غائبة لا ينتج رقمًا مضللًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-027..031; AZ28-SIGN
- AC-17-3 | تكامل وتجربة | weight 25
  - success: طابق عينة من الأسعار والحسابات المرجعية مع البطاقة والشارت ووقت الجلسة.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-027..031; AZ28-SIGN
- AC-17-4 | انحدار وتوثيق | weight 10
  - success: أرفق golden fixtures وتحويلات وحدات مستقلة وحدود التقريب.
  - verification: انحدار + دليل مستقل
  - reference: MD-027..031; AZ28-SIGN

## 18 - الفترات التاريخية ومقارنة الأداء وRealView

Prior review: تمت المراجعة

- AC-18-1 | وظيفة وحسابات | weight 35
  - success: RealView يقارن العوائد بالجنيه والدولار على نافذة وتواريخ مشتركة وبتركيب صحيح.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-032..038/041/042
- AC-18-2 | أمان واستثناءات | weight 30
  - success: تاريخ ناقص أو صفر سعر أساس أو split بلا معالجة لا يولد عائدًا وهميًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-032..038/041/042
- AC-18-3 | تكامل وتجربة | weight 25
  - success: بيانات صناعية: سهم 100→120 ودولار 50→60، عائد بالجنيه 20% وبالدولار 0%؛ تحقق API والشارت.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-032..038/041/042
- AC-18-4 | انحدار وتوثيق | weight 10
  - success: أرفق حسابًا مستقلًا وفترات المقارنة ومصدر تقويم الجلسات.
  - verification: انحدار + دليل مستقل
  - reference: MD-032..038/041/042

## 19 - البيانات الناقصة والقديمة ومنع القيم المُختلقة

Prior review: تمت المراجعة

- AC-19-1 | وظيفة وحسابات | weight 35
  - success: حالات fresh/stale/unknown/unavailable ظاهرة بالتوقيت الصحيح في كل الأدوات.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-040/043/044; R17-V2-04
- AC-19-2 | أمان واستثناءات | weight 30
  - success: NaN أو missing أو مستقبل زمني أو توقف دورة لا يتحول لصفر أو ختم حديث.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-040/043/044; R17-V2-04
- AC-19-3 | تكامل وتجربة | weight 25
  - success: توقف دورة الأسعار مع ساعة متحكم بها؛ راجع الواجهة والـAPI لكل حالة.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-040/043/044; R17-V2-04
- AC-19-4 | انحدار وتوثيق | weight 10
  - success: أرفق مصفوفة الحالات والحقول ومسارات freshness الخمسة.
  - verification: انحدار + دليل مستقل
  - reference: MD-040/043/044; R17-V2-04

## 20 - المحاور التقنية والأساسية وتفسير الأرقام

Prior review: تمت المراجعة

- AC-20-1 | وظيفة وحسابات | weight 35
  - success: المؤشرات الفنية والأساسية تطابق أمثلة مستقلة ومقارنة تعريفات EPS وP/E وPEG.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-045..055
- AC-20-2 | أمان واستثناءات | weight 30
  - success: خسارة أو EPS صفري أو فترة ناقصة لا يظهر مضاعفًا صالحًا أو توصية مضللة.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-045..055
- AC-20-3 | تكامل وتجربة | weight 25
  - success: قارن fixtures حسابية عبر محرك التحليل وبطاقة التفسير لنفس السهم والفترة.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-045..055
- AC-20-4 | انحدار وتوثيق | weight 10
  - success: وثق المعادلة والمدخلات والتقريب؛ لا تغير المنهجية دون قرار.
  - verification: انحدار + دليل مستقل
  - reference: MD-045..055

## 21 - السيولة والمخاطر والمعنويات والأخبار

Prior review: تمت المراجعة

- AC-21-1 | وظيفة وحسابات | weight 35
  - success: السيولة والمخاطر والمعنويات والأخبار لها تعريف ومصدر ودرجة قابلة للتفسير.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ21-LIQ-MISSING/LIQ-ZERO/NEWS-CRITICAL/RISK-SHARPE
- AC-21-2 | أمان واستثناءات | weight 30
  - success: سيولة صفر ليست missing؛ خبر خطر أو معنويات سلبية أو مخاطر مجهولة لا تزيد التقييم بلا مبرر.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ21-LIQ-MISSING/LIQ-ZERO/NEWS-CRITICAL/RISK-SHARPE
- AC-21-3 | تكامل وتجربة | weight 25
  - success: قارن عينة أخبار صناعية ومدخلات سيولة ومخاطر مع المحرك والواجهة.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ21-LIQ-MISSING/LIQ-ZERO/NEWS-CRITICAL/RISK-SHARPE
- AC-21-4 | انحدار وتوثيق | weight 10
  - success: أرفق golden cases للحدود والبيانات الناقصة وسياسة الخبر والمخاطر.
  - verification: انحدار + دليل مستقل
  - reference: AZ21-LIQ-MISSING/LIQ-ZERO/NEWS-CRITICAL/RISK-SHARPE

## 22 - الدرجات النهائية والثقة والوزن ومنع ازدواج الحساب

Prior review: تمت المراجعة

- AC-22-1 | وظيفة وحسابات | weight 35
  - success: إعادة تركيب الدرجة والثقة من المكونات تطابق الناتج والأوزان المعتمدة.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ22-DECISION-RECOMPOSE/EXPLAIN-DIVERGES/STRATEGY-MISSING
- AC-22-2 | أمان واستثناءات | weight 30
  - success: مكوّن غائب أو NaN أو مكرر لا يرفع الدرجة أو يخلق يقينًا غير مستحق.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ22-DECISION-RECOMPOSE/EXPLAIN-DIVERGES/STRATEGY-MISSING
- AC-22-3 | تكامل وتجربة | weight 25
  - success: اعرض نفس العينة في الترتيب والتفسير والقرار النهائي؛ تطابق الحساب والشرح.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ22-DECISION-RECOMPOSE/EXPLAIN-DIVERGES/STRATEGY-MISSING
- AC-22-4 | انحدار وتوثيق | weight 10
  - success: وثق نسخة الأوزان ومنهج الثقة وحالات التعارض دون تعديل سياسة الاستثمار.
  - verification: انحدار + دليل مستقل
  - reference: AZ22-DECISION-RECOMPOSE/EXPLAIN-DIVERGES/STRATEGY-MISSING

## 23 - محرك الفرص والفلتر 8 وفلاتر كل الأفق الزمني

Prior review: تمت المراجعة

- AC-23-1 | وظيفة وحسابات | weight 35
  - success: فلتر 8 لكل تبويب يطبق شروطه وأفقه الصحيحين ويشرح أهلية السهم وترتيبه.
  - verification: اختبار وحدة / golden fixture
  - reference: R17-V2-01..04; AZ23-CFO-LOSS/GROWTH-PROXY/INNER-MISSING/NONFINITE
- AC-23-2 | أمان واستثناءات | weight 30
  - success: CFO وربح سالبان، حجم نسبي صفر، عائد سعر دون نمو ربح وNaN لا يمنحون تطابقًا خاطئًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: R17-V2-01..04; AZ23-CFO-LOSS/GROWTH-PROXY/INNER-MISSING/NONFINITE
- AC-23-3 | تكامل وتجربة | weight 25
  - success: قارن المسارات الخمسة والبطاقات ومعايير الفلتر حول 90% و100% وتوقف التحديث.
  - verification: تكامل واقعي / UAT معزول
  - reference: R17-V2-01..04; AZ23-CFO-LOSS/GROWTH-PROXY/INNER-MISSING/NONFINITE
- AC-23-4 | انحدار وتوثيق | weight 10
  - success: أرفق اختبار قبل/بعد لكل عيب R17، وإثبات تفسير التعارض بعرض 390px.
  - verification: انحدار + دليل مستقل
  - reference: R17-V2-01..04; AZ23-CFO-LOSS/GROWTH-PROXY/INNER-MISSING/NONFINITE

## 24 - المحفظة الذكية والتوزيع والتنبيهات والقياس

Prior review: تمت المراجعة

- AC-24-1 | وظيفة وحسابات | weight 35
  - success: المحفظة الخاصة والملاءمة والقيم السوقية والتنبيه توافق عقد الحساب الواحد.
  - verification: اختبار وحدة / golden fixture
  - reference: SEC-015; AZ24-PF-MARK/PF-NAN/PF-PERSIST/WATCH-DUP
- AC-24-2 | أمان واستثناءات | weight 30
  - success: NaN أو حفظ فاشل أو تكرار إضافة لا ينتج نجاحًا أو صفوفًا مضاعفة أو تسريبًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: SEC-015; AZ24-PF-MARK/PF-NAN/PF-PERSIST/WATCH-DUP
- AC-24-3 | تكامل وتجربة | weight 25
  - success: A/B مع 10 أسهم/تبويب عند اعتماد الخاصية؛ إضافة وحذف وTP/SL عبر Telegram صناعي.
  - verification: تكامل واقعي / UAT معزول
  - reference: SEC-015; AZ24-PF-MARK/PF-NAN/PF-PERSIST/WATCH-DUP
- AC-24-4 | انحدار وتوثيق | weight 10
  - success: وثق توزيع الأصول والأسباب وتطابق المخزن الخاص والتنبيهات وعدم التكرار.
  - verification: انحدار + دليل مستقل
  - reference: SEC-015; AZ24-PF-MARK/PF-NAN/PF-PERSIST/WATCH-DUP

## 25 - الباك تيست والسيناريوهات والذهب والتحليل المتقدم

Prior review: تمت المراجعة

- AC-25-1 | وظيفة وحسابات | weight 35
  - success: Backtest يستخدم نافذة فعلية ومعيارًا مشتركًا وبيانات point-in-time دون نظر للمستقبل.
  - verification: اختبار وحدة / golden fixture
  - reference: MD-032/034; AZ25-BACKTEST-DAYS/INELIGIBLE/STALE-STATS/BENCH-MISSING
- AC-25-2 | أمان واستثناءات | weight 30
  - success: 3 أيام لا تعيد 50 يومًا؛ غير المؤهل لا يدخل اللقطة؛ benchmark غائب ليس 0%.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MD-032/034; AZ25-BACKTEST-DAYS/INELIGIBLE/STALE-STATS/BENCH-MISSING
- AC-25-3 | تكامل وتجربة | weight 25
  - success: قارن حالات تاريخية صناعية لمراحل 1M/3M/6M/1Y ومخرجات API والشارت والإحصاء.
  - verification: تكامل واقعي / UAT معزول
  - reference: MD-032/034; AZ25-BACKTEST-DAYS/INELIGIBLE/STALE-STATS/BENCH-MISSING
- AC-25-4 | انحدار وتوثيق | weight 10
  - success: أرفق منهج التكاليف والانحياز والبيانات والنتائج المرجعية؛ لا ادعاء عائد حقيقي بلا دليل.
  - verification: انحدار + دليل مستقل
  - reference: MD-032/034; AZ25-BACKTEST-DAYS/INELIGIBLE/STALE-STATS/BENCH-MISSING

## 26 - هيكل التنقل والوضوح والبساطة

Prior review: تمت المراجعة

- AC-26-1 | وظيفة وحسابات | weight 35
  - success: الأدوات الأساسية والبحث والتنقل واضحة دون عناصر وهمية وإشارات تحميل مضللة.
  - verification: اختبار وحدة / golden fixture
  - reference: UX-HOME-01; AZ26-PLACEHOLDERS
- AC-26-2 | أمان واستثناءات | weight 30
  - success: لا طريق مسدود أو زر يوحي بوظيفة غير متاحة أو كشف خصائص مدفوعة دون حق.
  - verification: اختبار سلبي / حقن أعطال
  - reference: UX-HOME-01; AZ26-PLACEHOLDERS
- AC-26-3 | تكامل وتجربة | weight 25
  - success: رحلة مستخدم من الرئيسية إلى الأسهم والذهب والفرص والمقارنة ثم العودة على الموبايل.
  - verification: تكامل واقعي / UAT معزول
  - reference: UX-HOME-01; AZ26-PLACEHOLDERS
- AC-26-4 | انحدار وتوثيق | weight 10
  - success: لقطات فعلية لكل حالة ومراجعة عدم تغيير الهوية والوظائف المعتمدة.
  - verification: انحدار + دليل مستقل
  - reference: UX-HOME-01; AZ26-PLACEHOLDERS

## 27 - تجربة تسجيل الدخول والحسابات والاشتراك

Prior review: تمت المراجعة

- AC-27-1 | وظيفة وحسابات | weight 35
  - success: التسجيل والدخول والحساب والاشتراك تعرض نتيجة HTTP المصادق عليها فقط.
  - verification: اختبار وحدة / golden fixture
  - reference: UX-LOGIN-01; AZ27-429/MALFORMED; SEC-013
- AC-27-2 | أمان واستثناءات | weight 30
  - success: 429 أو 200 HTML تالف لا يمسح الجلسة ولا يظهر نجاحًا؛ اشتراك منتهي لا يمر.
  - verification: اختبار سلبي / حقن أعطال
  - reference: UX-LOGIN-01; AZ27-429/MALFORMED; SEC-013
- AC-27-3 | تكامل وتجربة | weight 25
  - success: تجربة تسجيل صناعية حقيقية ثم logout واسترجاع وPro/Free وفشل الشبكة.
  - verification: تكامل واقعي / UAT معزول
  - reference: UX-LOGIN-01; AZ27-429/MALFORMED; SEC-013
- AC-27-4 | انحدار وتوثيق | weight 10
  - success: HAR منقح ولقطات وزمن الدخول؛ لا تعديل مسار الدخول المؤجل بغير موافقة.
  - verification: انحدار + دليل مستقل
  - reference: UX-LOGIN-01; AZ27-429/MALFORMED; SEC-013

## 28 - تجربة الشارتات والفلترة وأداة الذهب

Prior review: تمت المراجعة

- AC-28-1 | وظيفة وحسابات | weight 35
  - success: شارت الذهب المصري خطي عيار/جرام مع فترات يومية/أسبوعية/شهرية وزمن ومصدر.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ28-SIGN/SIBLING/DIFF/TILE/CHART-RETRY
- AC-28-2 | أمان واستثناءات | weight 30
  - success: 100→110 يعرض +10%، السعر الأقل يوصف أقل، فشل مصدر شقيق لا يحجب الذهب.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ28-SIGN/SIBLING/DIFF/TILE/CHART-RETRY
- AC-28-3 | تكامل وتجربة | weight 25
  - success: متصفح حقيقي: تبديل الفترات وملء الشاشة والـzoom وS/R والأحداث التاريخية وفشل المصدر.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ28-SIGN/SIBLING/DIFF/TILE/CHART-RETRY
- AC-28-4 | انحدار وتوثيق | weight 10
  - success: أرفق fixtures وإعادة التحميل والكاش واللقطات؛ لا تعارض مع تطوير الذهب المستقل.
  - verification: انحدار + دليل مستقل
  - reference: AZ28-SIGN/SIBLING/DIFF/TILE/CHART-RETRY

## 29 - الموبايل والوصولية وسهولة الاستخدام

Prior review: جزئي (اختبار حي)

- AC-29-1 | وظيفة وحسابات | weight 35
  - success: RTL، نص واضح وإعادة تدفق عند 200%، لا قص أو تمرير أفقي غير مقصود.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ29-DRAWER/GOLD-FOCUS; UX-A11Y-01
- AC-29-2 | أمان واستثناءات | weight 30
  - success: القائمة تغلق عند 900/1024/1099 بعد الاختيار؛ inert/aria وEscape وfocus trap صحيحة.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ29-DRAWER/GOLD-FOCUS; UX-A11Y-01
- AC-29-3 | تكامل وتجربة | weight 25
  - success: متصفح حقيقي 360/390/768/899/900/1024/1099/1100/1280، لمس ولوحة مفاتيح وقارئ شاشة.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ29-DRAWER/GOLD-FOCUS; UX-A11Y-01
- AC-29-4 | انحدار وتوثيق | weight 10
  - success: لقطات وأدلة وصول واضحة وتقرير تحقق التباين؛ محاكاة JS غير كافية.
  - verification: انحدار + دليل مستقل
  - reference: AZ29-DRAWER/GOLD-FOCUS; UX-A11Y-01

## 30 - حالات التحميل والخطأ والبيانات الفارغة وتعافي الواجهة

Prior review: تمت المراجعة

- AC-30-1 | وظيفة وحسابات | weight 35
  - success: التحميل والخطأ والفراغ والتعافي صريحة، ونتيجة السهم الحالي فقط تظهر.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ30-RACE/CONC/STATUS/RETRY
- AC-30-2 | أمان واستثناءات | weight 30
  - success: رد متأخر لسهم سابق يهمل؛ حد التزامن 6 لا يتجاوز؛ 204 لا يصنع 200.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ30-RACE/CONC/STATUS/RETRY
- AC-30-3 | تكامل وتجربة | weight 25
  - success: محاكاة شبكة بطيئة/منقطعة بمتصفح حقيقي؛ تبديل الأسهم وإلغاء الطلبات والعودة.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ30-RACE/CONC/STATUS/RETRY
- AC-30-4 | انحدار وتوثيق | weight 10
  - success: HAR منقح وعداد التزامن واستجابات HTTP الأصلية ونتائج التراجع.
  - verification: انحدار + دليل مستقل
  - reference: AZ30-RACE/CONC/STATUS/RETRY

## 31 - اختبارات الوحدات والتكامل والمتصفح وتجهيز CI

Prior review: تمت المراجعة

- AC-31-1 | وظيفة وحسابات | weight 35
  - success: CI يشغل الاختبارات الفعلية للباك والواجهة والبناء والأمان ويمنع حزمة محظورة.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ31-CI-BACKEND/FRONTEND/DIST-TESTS; SEC-028/029
- AC-31-2 | أمان واستثناءات | weight 30
  - success: اختبار فاشل عمدًا أو snapshot/test/fixture في dist يفشل بوابة المرشح.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ31-CI-BACKEND/FRONTEND/DIST-TESTS; SEC-028/029
- AC-31-3 | تكامل وتجربة | weight 25
  - success: تجربة CI معزولة لكل SHA ونتائج فشل/نجاح؛ تحقق required checks دون تغيير الإعدادات.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ31-CI-BACKEND/FRONTEND/DIST-TESTS; SEC-028/029
- AC-31-4 | انحدار وتوثيق | weight 10
  - success: سجل passed/failed/skipped وmanifest والبصمات والأسباب؛ لا اعتماد skips إلزامية.
  - verification: انحدار + دليل مستقل
  - reference: AZ31-CI-BACKEND/FRONTEND/DIST-TESTS; SEC-028/029

## 32 - الأداء وكمية الطلبات والكاش والحدود والتكلفة

Prior review: تمت المراجعة

- AC-32-1 | وظيفة وحسابات | weight 35
  - success: قياس p95 وطلبات الصفحة والذاكرة والتكلفة بالنسبة للأهداف المقترحة المعتمدة.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ32-RATE-EVICT; SEC-020; UX-PERF-01
- AC-32-2 | أمان واستثناءات | weight 30
  - success: 5001 مفتاح اصطناعي منتهٍ تنظف بالـTTL وتلتزم بسقف؛ تجاوز الحد يرجع 429 بلا انهيار.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ32-RATE-EVICT; SEC-020; UX-PERF-01
- AC-32-3 | تكامل وتجربة | weight 25
  - success: اختبار حمل صناعي محلي بعد اعتماد ملف الحمل والسقف؛ اختبر عدة عمال دون موارد مدفوعة.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ32-RATE-EVICT; SEC-020; UX-PERF-01
- AC-32-4 | انحدار وتوثيق | weight 10
  - success: قدم نتائج cold/warm وذاكرة وزمن واستجابة وتكلفة تقديرية منفصلة عن الفعلية.
  - verification: انحدار + دليل مستقل
  - reference: AZ32-RATE-EVICT; SEC-020; UX-PERF-01

## 33 - العزل وعمليات النشر وRollback ومراجعة الفروع

Prior review: تمت المراجعة

- AC-33-1 | وظيفة وحسابات | weight 35
  - success: المرشح والبيئة وSHA المخدومون موثقون والـKV مفصول وبناء خال من الملفات المحظورة.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ33-SMOKE-401/ROLLBACK-ACTIVE/KV; SEC-027/034
- AC-33-2 | أمان واستثناءات | weight 30
  - success: 401 للصفحة العامة/health لا يمر كنجاح؛ اختر ACTIVE-OLD لا أحدث رفع غير نشط.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ33-SMOKE-401/ROLLBACK-ACTIVE/KV; SEC-027/034
- AC-33-3 | تكامل وتجربة | weight 25
  - success: تجربة smoke وrollback صناعية؛ تحقق عقد route والبصمة بعد الرجوع بلا نشر حي.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ33-SMOKE-401/ROLLBACK-ACTIVE/KV; SEC-027/034
- AC-33-4 | انحدار وتوثيق | weight 10
  - success: أرفق سجل rollback ومصفوفة HTTP وموافقة منفصلة لازمة لأي نشر حقيقي.
  - verification: انحدار + دليل مستقل
  - reference: AZ33-SMOKE-401/ROLLBACK-ACTIVE/KV; SEC-027/034

## 34 - المراقبة والسجلات وقياس الاعتمادية

Prior review: تمت المراجعة

- AC-34-1 | وظيفة وحسابات | weight 35
  - success: liveness خفيف وreadiness يكشف اعتمادًا حرجًا مع مؤشرات freshness وp95 و5xx.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ34-HEALTH-READY/IO/PUBLIC/OBSERVABILITY; BE-005
- AC-34-2 | أمان واستثناءات | weight 30
  - success: تعطل التخزين لا يعرض ready؛ health العام لا يعرض بيانات الحساب أو تشخيصًا داخليًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ34-HEALTH-READY/IO/PUBLIC/OBSERVABILITY; BE-005
- AC-34-3 | تكامل وتجربة | weight 25
  - success: حقن تعطل تخزين/مصدر/رسائل واختبار تنبيه صناعي وحالات degraded واعتماد حدودها.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ34-HEALTH-READY/IO/PUBLIC/OBSERVABILITY; BE-005
- AC-34-4 | انحدار وتوثيق | weight 10
  - success: أرفق لوحة قياس وسجلات منقحة وخطة تنبيه واستجابة؛ لا تفعيل خارجي تلقائي.
  - verification: انحدار + دليل مستقل
  - reference: AZ34-HEALTH-READY/IO/PUBLIC/OBSERVABILITY; BE-005

## 35 - الجاهزية التشغيلية وخدمة العملاء والخصوصية

Prior review: تمت المراجعة

- AC-35-1 | وظيفة وحسابات | weight 35
  - success: الدعم وإدارة الحساب وحذف البيانات وفق سياسة احتفاظ مكتوبة؛ لا PII في shell الإدارة.
  - verification: اختبار وحدة / golden fixture
  - reference: MGMT-001..006; AZ35-DELETE-CLAIM; BE-024
- AC-35-2 | أمان واستثناءات | weight 30
  - success: anonymous/Free لا يقرأ إدارة أو أصولًا حساسة؛ الحذف لا يدعي الإزالة الكاملة مع بقايا غير مصرح بها.
  - verification: اختبار سلبي / حقن أعطال
  - reference: MGMT-001..006; AZ35-DELETE-CLAIM; BE-024
- AC-35-3 | تكامل وتجربة | weight 25
  - success: اختبار حساب صناعي لحذف/تعمية وإبطال جلسة واستعادة مقيدة؛ إدارة وصول بدور مصرح.
  - verification: تكامل واقعي / UAT معزول
  - reference: MGMT-001..006; AZ35-DELETE-CLAIM; BE-024
- AC-35-4 | انحدار وتوثيق | weight 10
  - success: أدلة منقحة وسياسات اعتماد الاحتفاظ والدعم وتحقق الكاش؛ أي تعديل إنتاج بموافقة.
  - verification: انحدار + دليل مستقل
  - reference: MGMT-001..006; AZ35-DELETE-CLAIM; BE-024

## 36 - الجاهزية التجارية وقائمة قبول الإطلاق النهائي

Prior review: تمت المراجعة

- AC-36-1 | وظيفة وحسابات | weight 35
  - success: مسار اشتراك صناعي: طلب وتفعيل وتجديد وتسوية واسترداد متوافق مع الحقوق الفعلية.
  - verification: اختبار وحدة / golden fixture
  - reference: AZ36-SUB-PERSIST/ATOMIC; SEC-012; MGMT-001
- AC-36-2 | أمان واستثناءات | weight 30
  - success: فشل الحفظ في أي خطوة أو إعادة الطلب لا يخلق نجاحًا كاذبًا ولا تفعيلًا/تحصيلًا مضاعفًا.
  - verification: اختبار سلبي / حقن أعطال
  - reference: AZ36-SUB-PERSIST/ATOMIC; SEC-012; MGMT-001
- AC-36-3 | تكامل وتجربة | weight 25
  - success: رحلة قبول كاملة من التسجيل حتى الدعم والإلغاء مع مزود دفع صناعي فقط؛ كل موانع الإطلاق مغلقة.
  - verification: تكامل واقعي / UAT معزول
  - reference: AZ36-SUB-PERSIST/ATOMIC; SEC-012; MGMT-001
- AC-36-4 | انحدار وتوثيق | weight 10
  - success: موافقة منفصلة على الباقات والتسعير والشروط والخصوصية وخطة النشر والتراجع؛ لا دفع حقيقي.
  - verification: انحدار + دليل مستقل
  - reference: AZ36-SUB-PERSIST/ATOMIC; SEC-012; MGMT-001
