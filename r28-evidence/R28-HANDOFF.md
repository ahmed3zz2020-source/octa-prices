# OCTA · RC-R28-001 · ملف التسليم والمراجعة

- الباك: `ahmed3zz2020-source/octa-prices` · فرع `release/round28-rc` · `0d30c2e`
- الواجهة: `ahmed3zz2020-source/octa` · فرع `release/round28-rc-fe` · `e853f24`
- الـCI: `ahmed3zz2020-source/octa-prices` · فرع `ci/octa-ci-r28` · `0b7a787` · فرع الأدلة `review/round28-evidence`
- المعاينة: `https://octa-preview.ahmed3zz2020.workers.dev` · لوحة الإدارة: `https://octa-mgmt.ahmed3zz2020.workers.dev`

---

## المربع الجاهز للنسخ (نسخة المراجع)

```
أنت مراجع مُستقل لمشروع OCTA (منصة تحليل أسهم مصريّة: تقييم + فرص + محفظة + ذهب + تنبيهات).
الفرز: RC-R28-001 = إغلاق ملاحظات R26/R27 + إصلاحات أمنية جديدة (01..10).
الواجهة (octa) والباك (octa-prices) منفصلان، ومعاينة Cloudflare منفصلة عن الإنتاج.

الفرعان المرشحان (لا تدمج في main):
- octa-prices · release/round28-rc · 0d30c2e
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/r28_build_acceptance_log.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/r28_scan_secrets.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/r28_function_probe.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/r28_acceptance_items.csv
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/r28_env_blocked.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0d30c2e/tools/test_ci_gates.py
- octa · release/round28-rc-fe · e853f24
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/mgmt/worker.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/preview-store.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/preview-api.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/worker.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/assets/tests/r28-review-fixes.test.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/assets/tests/r28-preview-isolation.test.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/e853f24/tools/r28_browser_journey.mjs
- الـCI: octa-prices · ci/octa-ci-r28 · 0b7a787
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0b7a787/ci-workflow/octa-ci.yml
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/0b7a787/ci-workflow/octa-ci-fe.yml
- الأدلة: octa-prices · review/round28-evidence · r28-evidence/
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/R28-EVIDENCE.md
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/acceptance_r28.md
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/backend_results.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/browser_journey.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/secrets-scan.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/live_checks.json

ما أُنجز في R28 (الأرقام كما قِيست، لا كما وُعد):
1) FINDING-01 عقد الـDO الحقيقي: preview-store.js — storage.list() يرجّع Map لا مصفوفة، مع تحمّل الشكل القديم + count + فرز، ورفض TTL أقل من 60 ثانية صراحة (ttl_too_short)، وحذف السجلات المنتهية عند القراءة.
2) FINDING-02 إبطال جلسات المعاينة: preview-api.js — /api/auth/logout ⇒ 401 بلا جلسة و503 revoke_failed عند تعذّر الإبطال، و/api/auth/refresh ⇒ إبطال القديم أولاً ثم إصدار الجديد (وإن فشل الإصدار ⇒ لا جلسة بديلة)، وissue_failed إذا لم يُحفظ التوكن.
3) FINDING-03 جلسة الإدارة مربوطة بنسخة الاعتماد: mgmt/worker.js — credentialTagFromState + verifyPanelPasswordWithTag (قراءة واحدة ⇒ تحقق + وسم)، وmakeSession يرفض الإصدار بلا وسم مؤكَّد ⇒ 503، وTAG_UNVERIFIED عند فشل قراءة الحالة.
4) FINDING-08 عقد مصادقة المعاينة = عقد الإنتاج: preview-api.js — توكن فتح عشوائي (600 ثانية، مرة واحدة) + {new_pin} + Authorization: Bearer؛ القالب القديم بالإيميل والكود مغلق (401) ⇒ fail-closed.
5) FINDING-09 جلسة Bearer: readSession يقرأ الكوكي أو ترويسة Authorization ⇒ التطبيق يوثّق نفسه ⇒ البوابة ما تظهرش دايمدائما.
6) FINDING-10 حكم بوابة الصفحات في المعاينة: worker.js — في وضع المعاينة الحكم من handlePreviewApi (نفس الـDO والسر) لا من الباك ⇒ التطبيق بقى داخل المعاينة فعلياً (تنقّل #stocks/#bestpick/#pick + /api/rank بعدد 297).
7) FINDING-04 سجل الاعتماد 144 مبني من الشروط والأوزان الأصلية (35/30/25/10) بأداة داخل المستودع + خريطة نطاق ← قياس + طبقة بنود متعذرة + طبقة محجوب بالبيئة ⇒ النسبة محسوبة من (ناجح × وزن) ÷ مجموع الأوزان، لا نسبة موروثة.
8) FINDING-05 التليجرام: التوكن الميت (بصمة d35e73e78acf) في main فقط و getMe = 401، والتوكن الحيّ (بصمة a1c71d495133) أُرسلت به رسالة اختبار مصرَّح بها (200)؛ والكود يقرأ التوكن بالأسماء فقط.
9) FINDING-06 الـCI: بصمتا المرشح النهائيتين في الملفين + job بديل منفصل + التقاط سبب الفشل في السجل + انتظار 200 حقيقي بعد تصفير الـstaging (403 يمرّ ⇒ فشل وهمي).
10) FINDING-07 الفحص الوظيفي مُصحَّح (31/31) + عزل المعاينة مع ربط القراءة للباك (أي مسار آخر ⇒ 501) + رحلة صناعية 18/18 + رحلة متصفح حقيقية 12/16.

القياسات: واجهة 742/742 · باك 77 ملف (72 ناجح · 4 فاشل · 1 متخطّى · 2459 حالة) · بوابة A5 11/11 · عقد المستودعين 20/20 · الفحص الوظيفي 31/31 · رحلة المتصفح 12/16.

القواعد الممنوعة (لا تكسرها):
- لا تدمج في main، ولا تنشر على octashares.com، ولا موارد مدفوعة، ولا بيانات عملاء حقيقية.
- لا أسرار في الملفات أو السجلات أو التقرير؛ لا تعِد كتابة تاريخ Git.
- لا تغيّر أوزان المحرك ولا حدود القبول ولا السياسات الاستثمارية.
- لا ترث نسبة 92.50% ولا أي نسبة جاهزة — كل نسبة تُحسب من قياس جديد.
- 401/403/404/501 ليست نجاحًا وظيفيًا؛ المتعذر = صفر نقاط.
- ممنوع "..." خارج التعليقات؛ ممنوع U+FFFD وCJK/Hangul/Cyrillic في أي نص عربي.

المطلوب منك:
راجع المرشح RC-R28-001 مقابل سجل الاعتماد والأدلة، وابحث عن عيوب لم تُمسّ: إبطال الجلسة في preview-api.js (هل يوجد مسار يُصدر جلسة بعد فشل الإبطال؟)، عقد توكن الفتح في preview-api.js (هل يمكن إعادة استخدامه؟)، وسم الاعتماد في mgmt/worker.js (هل يمكن إصدار جلسة بوسم غير قابل للتحقق؟)، خريطة النطاق ← القياس في tools/r28_build_acceptance_log.py (هل هناك بند بلا قياس؟)، تسرّب سر في أي فرع أو حزمة، أو أي ادعاء في التقرير بلا قياس.

صيغة المخرجات المطلوبة (قائمة واحدة، كل بند: معرّف · الملف:السطر · العيب · البرهان (أمر + رقم قبل/بعد) · الخطورة):
FINDING-11 | preview-api.js:683 | <العيب> | <command + before/after> | critical|high|medium|low
```

---

## ما تغيّر منذ التسليم السابق (R26/R27 ⇒ R28)

1. الباك: `32cf806` ⇦ `0d30c2e` — أداة سجل الاعتماد + أداة المسح + أداة الفحص الوظيفي + طبقة المحجوب بالبيئة + تجاهل ملفات الحالة المحلية.
2. الواجهة: `4c65d7c` ⇦ `e853f24` — إغلاق ثغرة كلمة مرور اللوحة + إصلاح عقد المعاينة (DO/الجلسات/البوابة) + اختبار الإصلاحات (23 حالة) + أداة رحلة المتصفح.
3. الـCI: `cb3165c` ⇦ `0b7a787` — ملفات workflow ببصمتين نهائيتين + حارس بوّابات + مصنّف نتائج + أداة تصفير الـstaging.
4. الأدلة: فرع `review/round28-evidence` أُعيد بناؤه على هذه القياسات.

## شجرة الدليل

```
octa-prices · release/round28-rc · 0d30c2e
  └─ tools/r28_build_acceptance_log.py · tools/r28_acceptance_items.csv · tools/r28_env_blocked.json
  └─ tools/r28_scan_secrets.py · tools/r28_function_probe.py · tools/test_ci_gates.py
octa · release/round28-rc-fe · e853f24
  └─ mgmt/worker.js · preview-api.js · preview-store.js · worker.js
  └─ assets/tests/r28-review-fixes.test.js · assets/tests/r28-preview-isolation.test.js
  └─ tools/r28_browser_journey.mjs
```

## الموانع (خطوات المالك)

1. Railway: نشر خدمة من `release/round28-rc` وضبط `OCTA_API_URL` + `OCTA_PROXY_SECRET` + `OCTA_API_DIRECT` على staging (لا الإنتاج) ⇒ بدونها تظل مسارات الذهب في المعاينة 503.
2. GitHub workflow: نسخ `ci-workflow/octa-ci.yml` ⇦ `.github/workflows/octa-ci.yml` و`ci-workflow/octa-ci-fe.yml` ⇦ `.github/workflows/octa-ci-fe.yml` (التوكن الحالي بلا صلاحية workflow).
3. تليجرام: تدوير التوكن من @BotFather ووضعه في Railway كـ`TELEGRAM_BOT_TOKEN` (لا يُرسل في الشات).
4. Cloudflare: تفعيل Secret Scanning وPush Protection + صلاحيات Access/WAF.

## حالة النشر

- `octa-preview` · آخر نشر `v=202611201625` (يشمل FINDING-08/09/10) · `/api/health` = 200.
- `octa-mgmt` · `/api/health` = 200 و`revocation_ready=true`.
- الإنتاج (`octa-prices-production-4ccb.up.railway.app`) حيّ (200) ولم يُلمس.
