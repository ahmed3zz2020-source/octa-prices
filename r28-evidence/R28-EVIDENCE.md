# OCTA · RC-R28-001 · تقرير الجولة والإغلاق

المرشح: `release/round28-rc` (باك) + `release/round28-rc-fe` (واجهة) + `ci/octa-ci-r28` (الـCI).
الأساس: الباك `32cf8063a354af5dfcfb6fa02ab734ab6a9f920d` · الواجهة `4c65d7c325a908a04a8622fec91a89e39b271024`.
الفرع `main` لم يتغيّر في أي مستودع.

---

## 1) هوية المرشح (بصمات)

| العنصر | المستودع | الفرع | البصمة |
|---|---|---|---|
| الباك | `ahmed3zz2020-source/octa-prices` | `release/round28-rc` | `fbba2e27796bb46f1c6fd4bdd91b7be4fecd1b5f` |
| الواجهة | `ahmed3zz2020-source/octa` | `release/round28-rc-fe` | `e853f24cdb653d65d945930e0c9853d6b6e10c32` |
| الـCI | `ahmed3zz2020-source/octa-prices` | `ci/octa-ci-r28` | `d0eebb2ca5d9f3c64efaaa7956d75a6b33fff85d` |
| الأدلة | `ahmed3zz2020-source/octa-prices` | `review/round28-evidence` | يُحدَّث مع هذا التقرير |

المعاينة الحيّة: `https://octa-preview.ahmed3zz2020.workers.dev` (آخر نشر `v=202611201625`).
لوحة الإدارة: `https://octa-mgmt.ahmed3zz2020.workers.dev` (`/api/health` ⇒ 200 و`revocation_ready=true`).

---

## 2) جدول القياسات (كل رقم من ملف على القرص)

| القياس | النتيجة | الملف |
|---|---|---|
| واجهة (ملف-ملف على `e853f24`) | 66 ملف · 742 تأكيد · 0 فاشل | `output/r28b/fe_per_file.tsv` + `fe_per_file.log` |
| واجهة (المجموعة الكاملة) | 742/742 ناجح · 0 فاشل | `output/r28b/fe_suite_final3.log` |
| باك (pytest في venv معزول) | 77 ملف · 72 ناجح · 4 فاشل · 1 متخطّى · 2459 حالة | `output/r28be_venv2/backend_results.json` |
| ⛔ برهان سالب للفشل الـ4 | نفس الحالة على الأساس (32cf806) ⇒ صفر انحدار | `output/r28b/base_failing_proof.json` |
| الفحص الوظيفي للباك | 31/31 | `output/r28b/function_probe.json` |
| رحلة المتصفح الحقيقية (Chromium) | 12/16 | `output/r28b/journey/browser-journey.json` |
| الرحلة الصناعية للمعاينة | 18/18 | `output/r28b/preview_journey.json` |
| بوابة الشجرة النظيفة A5 | 11/11 | `output/r28b/gate_a5_final.log` |
| عقد المستودعين | 20/20 | `output/r28b/cross_repo_contract.json` |
| ملف اختبار الإصلاحات | 23/23 على المرشح · 18/23 فاشل على الأساس | `assets/tests/r28-review-fixes.test.js` |
| المسح الأمني | 9530 كائن git · 919 ملف شجرة · 964 عضو حزمة ⇒ 44 قيمة مسرّبة ⇒ **0 تسرّب حقيقي** (تصنيف محسوب) | `output/r28b/secrets-scan-final.json` + `secrets-classification.json` |
| سجل الاعتماد 144 | 119 ناجح · 15 فشل · 10 متعذر ⇒ 3050/3600 = **84.72% محسوبة** | `output/r28b/acceptance_r28.md` |

ملاحظة على بصمة قياس الباك: القياس تم على `fbba2e2` والفرق الوحيد بينه وبين البصمة النهائية `0d30c2e` هو سطر `.gitignore` (ملفات حالة الـstaging المحلية) ⇒ **لا فرق في كود المنتج**.

## 3) إغلاق الملاحظات (FINDING-01..10)

### FINDING-01 · عقد الـDurable Object الحقيقي — مُغلق
- المشكلة: `preview-store.js` كان يتعامل مع `storage.list()` كأنه مصفوفة كائنات، بينما Cloudflare ترجّع **Map**.
- التعديل: `preview-store.js:20` (`nowSec`) · `:53` (حذف المنتهي عند `get`) · `:65` (`ttl_too_short` ⇦ رفض TTL أقل من 60 ثانية) · `:75-96` (قراءة `Map` مع تحمّل الشكل القديم ⭐ + `count` ⭐ + فرز ⭐).
- التحقق: `assets/tests/r28-preview-isolation.test.js` + `preview-api.test.js` + `r25-preview-isolated.test.js` + `r26-preview-self-api.test.js` محدثة ⇒ 45/45.

### FINDING-02 · إبطال جلسات المعاينة — مُغلق
- المشكلة: الخروج/التجديد كانا يبدوان «نجاحاً» حتى لو لم يُبطَل شيء.
- التعديل: `preview-api.js:683` (`/api/auth/refresh` ⇦ إبطال القديم **أولاً** ثم إصدار الجديد، بلا توكن بديل عند الفشل) · `:712` (`/api/auth/logout` ⇦ 401 بلا جلسة و503 `revoke_failed` عند تعذّر الإبطال) · `:504`/`:643`/`:664` (`issue_failed` ⇦ لا جلسة تُصدر إذا فشل `storePut`).
- التحقق: اختبارات `r25-logout-hardening` + `r26-session-hardening` + `r24-session-i06` محدثة ⇒ ضمن الـ742/742.

### FINDING-03 · جلسة الإدارة مربوطة بنسخة الاعتماد — مُغلق
- المشكلة: `mgmt/worker.js` كان يصدر جلسة حتى لو تعذّرت قراءة حالة كلمة المرور.
- التعديل: `mgmt/worker.js:264` (`TAG_UNVERIFIED`) · `:682` (`credentialTagFromState` ⇦ وسم `nostate`/`nodostate`/النسخة) · `:797` (`verifyPanelPasswordWithTag` ⇦ قراءة واحدة للتحقق والوسم) · `:844` (`makeSession` يرفض الإصدار بلا وسم مؤكَّد ⇒ 503) · `validSession` يرفض فوراً لو الوسم الحالي مستحيل.
- التحقق: `assets/tests/r28-review-fixes.test.js` ⇦ 23/23 على المرشح و18/23 فاشل على `4c65d7c` (البرهان السالب).

### FINDING-04 · إعادة بناء سجل الـ144 من الشروط والأوزان الأصلية — مُغلق
- الأداة داخل المستودع: `tools/r28_build_acceptance_log.py` + `tools/r28_acceptance_items.csv` (٣٦ نطاقاً · ١٤٤ بنداً · أوزان 35/30/25/10).
- البنية: خريطة صريحة `SCOPE_MAP` (نطاق ← مدخلات مُقاسة) + `ITEM_OVERRIDE` (بنود متعذرة بصفر نقاط وسبب بالاسم) + `ENV_BLOCKED` (بنود محجوبة بالبيئة).
- ⛔ النسبة الموروثة 92.50% غير مستخدمة ⭐ ⇒ كل نسبة محسوبة من (ناجح × وزن) ÷ مجموع الأوزان ⭐.
- النتيجة: انظر §5.

### FINDING-05 · احتواء التليجرام + مسح الأرشيفات — مُغلق
- التسريب: توكن `TELEGRAM_BOT_TOKEN` الميت (بصمة `d35e73e78acf`) موجود في `origin/main:private-docs/SECURITY-PLAN.md` ⇒ `getMe` = 401 (ميت) ⇒ وليس في فرع R28.
- الحكم: `octa_app.py` + `update_prices.py` يقرآن التوكن **بالأسماء فقط** (لا قيمة سر في الكود).
- التوكن الحيّ `TELEGRAM_TOKEN` (بصمة `a1c71d495133`) ⇦ إرسال اختبار مصرَّح به نجح (HTTP 200 · `message_id:125`).
- الأدلة: `output/r28b/telegram_state.json` · `telegram_leaked_state.json` · `telegram_test_send.json`.
- أداة المسح: `tools/r28_scan_secrets.py` ⇦ بصمة SHA256 لكل أرشيف + بديل عند فشل المسار + مصفوفة `archives` (بلا أخطاء صامتة).

### FINDING-06 · الـCI بالبصمتين النهائيتين — مُغلق (مع مانع واحد)
- `ci-workflow/octa-ci.yml` ⇦ `OCTA_CANDIDATE_SHA: fbba2e2…` + `OCTA_FE_SHA: e853f24…`.
- `ci-workflow/octa-ci-fe.yml` ⇦ `OCTA_CANDIDATE_SHA: e853f24…`.
- أدوات: `tools/ci_result_classifier.py` (يلتقط **سبب** الفشل في السجل وJSON) + `tools/ci_reset_staging.sh` (ينتظر **200 حقيقي** بمفتاح الـproxy ⇦ 403 يمرّ ⇒ فشل وهمي).
- الحارس: `tools/test_ci_gates.py` ⇦ «كل البوابات سليمة» على الملفين.
- ⛔ المانع: التوكن بلا صلاحية `workflow` ⇒ 403 على `dispatch` وعلى دفع `.github/workflows/*` ⇒ الملفان جاهزان للنشر اليدوي من المالك (انظر §7).

### FINDING-07 · ربط المعاينة بباك Railway في بيئة معزولة — مُغلق جزئياً (مانع بيئي)
- الفحص الوظيفي مُصحَّح: `tools/r28_function_probe.py` ⇦ تحقق من **محتوى** الرد + قسم رفض مستقل + رحلة صناعية ⇒ 31/31 (`output/r28b/function_probe.json`).
- العزل: `preview-api.js:353` (`isBackendReadOnly`) ⇦ قراءات فقط تمرّ للباك الحقيقي؛ الحسابات/الجلسات/المحفظة/التنبيهات تبقى في DO المعاينة؛ أي مسار آخر ⇒ 501 fail-closed.
- `/api/alerts/state` ⇒ alias محلي (كان 501).
- الرحلة الصناعية: `tools/r28_preview_journey.py` ⇒ 18/18 (`output/r28b/preview_journey.json`): تسجيل · بريد · تفعيل · رقم جديد · دخول · `/me` · تنبيهات · محفظة · خروج ⇒ `/me` بعد الخروج 401 · CSRF 403.
- ⛔ المانع: `OCTA_API_URL` في المعاينة يؤشر إلى وجهة ميتة ⇒ 503 `api_unreachable` (الآلية تعمل والمثبت في `output/r28b/preview_backend_link.json`) ⇒ يلزم staging معزول من المالك (انظر §7). الإنتاج حيّ (200) ولا يُستخدم للمعاينة.

### FINDING-08 · عقد مصادقة المعاينة ≠ عقد الإنتاج — مُغلق
- المشكلة: المعاينة كانت تطلب `{email, code, pin}` ⇒ التسجيل عبر المتصفح مستحيل (400 `challenge_expired`).
- التعديل: `preview-api.js:26` (`UNLOCK_TTL_SEC = 600`) · `:180` (`bearerToken`) · `:190` (إصدار توكن فتح) · `:442`/`:536` (إرجاع `unlock` + `expires_in`) · `:464`/`:544` (`unlock_expired` ⇦ 401 بلا توكن الفتح) · القالب القديم بالإيميل والكود **مغلق** (401) ⇒ fail-closed.
- التحقق: `assets/tests/preview-api.test.js` (٩ مواقع + ②ب) + `r28-preview-isolation.test.js` ⇒ 45/45.

### FINDING-09 · جلسة Bearer من الترويسة — مُغلق
- المشكلة: `readSession` كان يقرأ الكوكي فقط ⇒ التطبيق (يبعث `Authorization: Bearer`) لم يكن يوثّق نفسه ⇒ البوابة تظهر دائماً.
- التعديل: `preview-api.js:260` ⇦ `readCookie(...) || bearerToken(request)`.
- التحقق: فحص حيّ بـcurl (Bearer ⇒ 200) + اختبار.

### FINDING-10 · حكم بوابة الصفحات في المعاينة — مُغلق
- المشكلة: `worker.js` كان يسأل **الباك** عن الجلسة ⇒ جلسة المعاينة (في DO المعاينة) غير معروفة له ⇒ العامل كان يقدّم `market.html` بدل التطبيق.
- التعديل: `worker.js:89` + `:935` (`askSessionAuthority` ⇦ في وضع المعاينة الحكم من `handlePreviewApi`) · `:943` · `:1016` (`sessionVerdict` يمرّر `url`) · `:1554` · `:1591` · `:2345` · `:2364` · `:2708`.
- التحقق: بعد النشر `v=202611201625` ظهر التطبيق فعلياً (تنقّل `#stocks`/`#bestpick`/`#pick` + `/api/rank` 200 بعدد 297 + `/api/auth/me` 200) ⇦ رحلة المتصفح 12/16.

---

## 4) نتيجة رحلة المتصفح (12/16) — التفسير

نجح: الدخول من البوابة (البريد ⇦ الكود ⇦ الرقم ⇦ التطبيق) · مودال الذهب وتبويباه · زر ملء الشاشة · أداة الاختيار · زر اللقطة · تبويب الادخار · **رسالة خطأ واضحة** عند فشل المصدر (مش نجاح وهمي) · التنقل (أسهم ⭐ فرص ⭐ مقارنة ⭐) · الرجوع للرئيسية · **مافيش تمرير أفقي في ١٠ عروض** · مافيش قص أفقي في ١٠ عروض.

لم ينجح (٤):
1. الشارت موجود · 2. الدعم والمقاومة · 3. الأحداث — كلها `/api/gold*` ⇒ 503 `api_unreachable` ⇒ **مانع بيئي** (§7-أ) لا عيب في الواجهة؛ رسالة الخطأ ظهرت بدل بيانات مزيّفة.
4. هدف لمس واحد أصغر من 40px: `.dev-hidden-gate` (22×22، بلا نص) ⇒ **ملاحظة واجهة فعلية** للمراجع (لم تُعدَّل ⇒ خارج نطاق الإغلاق الأمني).

---

## 5) سجل الاعتماد 144

- **144 بنداً** · أوزان 35/30/25/10 (الأصلية، غير معدّلة) · مجموع الأوزان 3600.
- النتيجة: **119 ناجح · 15 فشل · 10 متعذر ⇒ 3050/3600 = 84.72%** (محسوبة من الحالات، لا نسبة موروثة).
- البنود الـ15 «الفاشلة» كلها مرتبطة بـ**ملفَّي باك اثنين**: `test_security_batch02.py` (تأكيدات الإبطال الثلاثة) و`test_security_p0.py` (ConnectionError) ⇒ و**كلاهما يفشل بنفس الحالة على الأساس** ⇒ ⇒ **صفر انحدار** (البرهان في `base_failing_proof.json`).
- البنود المتعذرة (10) بأسبابها بالاسم: 4 منها (07-3 · 07-4 · 29-3 · 29-4) = قياس جزئي (رحلة Chromium) أو قرار منفصل (CSP) · والباقي: الـCI على GitHub غير مفعّل · rollback لم يُنفَّذ · موافقات المالك · موانع الإطلاق.
- البند المحجوب بالبيئة (R23 zip ناقص · r25 storage durability حسّاس للزمن) منفصل عن «الفشل» في `tools/r28_env_blocked.json`.

## 6) المسح الأمني

- المسح يغطّي: **9530 كائن git** + **919 ملف شجرة** + **964 عضو حزمة** + مجلد الأدلة ⇒ `secrets-scan-final.json` (بدون أخطاء مسار).
- **0 نتيجة «حرجة»** (لا توكن تليجرام · لا GitHub PAT · لا مفتاح AWS · لا مفتاح خاص).
- 44 قيمة مسرّبة **اسمها فقط** ⇒ صُنِّفت آلياً (`classify_secrets.py`) ⇒ **0 تسرّب حقيقي**: 23 داخل ملفات اختبار · 12 مرجع متغيّر بيئة · 4 فحوص منطقية · 1 اسم متغيّر بيئة · 1 قيمة مثال · 1 تعريف نمط المسح · 1 قيمة مولّدة عند التشغيل · 1 أداة مسح أمانة.
- كل أرشيف بصمته SHA256 داخل `packages.json` (بصمة الأرشيف الذي فُحص = بصمة الأرشيف المسلَّم ⇒matched).
- **الحزم قابلة لإعادة الإنتاج**: نفس المحتوى ⇒ نفس md5+sha256 (تاريخ ZIP ثابت).

## 7) الموانع (خطوات المالك)

أ. **Railway (يوقف شارات الذهب في المعاينة)**: نشر خدمة من فرع `release/round28-rc` وضبط `OCTA_API_URL` + `OCTA_PROXY_SECRET` + `OCTA_API_DIRECT` على **staging** (لا الإنتاج).
ب. **GitHub workflow**: نسخ `ci-workflow/octa-ci.yml` ⇦ `.github/workflows/octa-ci.yml` في `octa-prices`، و`ci-workflow/octa-ci-fe.yml` ⇦ `.github/workflows/octa-ci-fe.yml` في `octa` (من محرر الموبايل) — أو إضافة توكن بصلاحية workflow **خارج الشات**.
ج. **تدوير تليجرام**: من الهاتف ⇒ @BotFather ⇒ بوت OCTA ⇒ `/token` ⇒ وضع التوكن الجديد في Railway كـ`TELEGRAM_BOT_TOKEN` ⇒ حذف القديم (ميت 401) ⇒ **لا ترسل التوكن في الشات**.
د. **Cloudflare**: تفعيل Secret Scanning وPush Protection من Settings ⇒ Code security؛ وصلاحيات Access/WAF (1010) للمالك.
هـ. **إعادة نشر المعاينة**: آخر نشر `v=202611201625` متضمّن كل الإصلاحات ⇒ لا حاجة لنشر جديد إلا إذا تغيّر الكود.

---

## 8) الحزم (بصمات قابلة لإعادة الإنتاج)

| الحزمة | md5 | sha256 (مبتور) | الملفات | الحجم |
|---|---|---|---|---|
| `OCTA-ROUND28-BACKEND.zip` | `58a9ffb7d4c3a5d9353848a69a280fa3` | `f394506e81c6b67b…` | 313 | 1,692,337 |
| `OCTA-ROUND28-FRONTEND.zip` | `34ca11f81b9ed95ebedabecb5784e754` | `186c6afe6598cbf4…` | 509 | 6,692,549 |
| `OCTA-ROUND28-CI.zip` | `81dce9c9fe649bd74047d80231433318` | `c8e33414444d2aa5…` | 194 | 1,595,758 |
| `OCTA-ROUND28-DELIVERY.zip` | ⭐ في `OCTA-ROUND28-PACKAGES.json` ⭐ | ⭐ في الملف نفس�� ⭐ | ⭐ | ⭐ |

البصمات الكاملة (md5 + sha256 + الحجم + عدد الملفات) في `OCTA-ROUND28-PACKAGES.json` ⭐ خارج الحزم ⭐ (وإلا ⇒ بصمة دائرية ⭐).
حزمة التسليم نفسها تضم الأدلة ⇒ بصمتها تتغيّر مع كل إضافة ⇒ لذلك تُقرأ من ملف المانيفست ⭐ لا من جدول هنا ⭐.
