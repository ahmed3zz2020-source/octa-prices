# OCTA · RC-R31-001 · تقرير الجولة ٣١ (دفعة الإصلاح الواحدة)

المرشح: `release/round28-rc` (باك) + `release/round28-rc-fe` (واجهة) + `ci/octa-ci-r28` (الـCI).
الأساس المقارن: الباك `0d30c2eec56d8d6a4a9db14b3450d7d32f0305da` · الواجهة `e853f24cdb653d65d945930e0c9853d6b6e10c32`.
الفرع `main` لم يتغيّر في أي مستودع · ولا نشر على الإنتاج · ولا دفع حقيقي · ولا سرّ في أي ملف.

---

## 1) هوية المرشح (بصمات)

| العنصر | المستودع | الفرع | البصمة |
|---|---|---|---|
| الباك | `ahmed3zz2020-source/octa-prices` | `release/round28-rc` | `975664d34e3e06ac87bf97dccfc7a5090d6838d9` |
| الواجهة | `ahmed3zz2020-source/octa` | `release/round28-rc-fe` | `7ac1ca272df9eb07afa0ee143c6310c51e77e174` |
| الـCI | `ahmed3zz2020-source/octa-prices` | `ci/octa-ci-r28` | `5a4d91aba59397620c9472e343d17cd7e5aae019` |
| الأدلة | `ahmed3zz2020-source/octa-prices` | `review/round29-evidence` | يتقدّم مع كل commit للأدلة |

المعاينة الحيّة: `https://octa-preview.ahmed3zz2020.workers.dev` (آخر نشر `v=202611220013` · Version ID `fd09a356-1a42-440f-9895-0fd4eedc2db7`).
الباك الحقيقي المعزول على البصمة الجديدة: `http://127.0.0.1:8097` (من `tools/staging/run_staging.py` على `975664d`).

---

## 2) جدول القياسات (كل رقم من ملف على القرص)

| القياس | النتيجة | الملف |
|---|---|---|
| واجهة (المجموعة الكاملة) | 768/768 ناجح · 0 فاشل · rc=0 | `output/r31/fe_suite2.log` |
| واجهة (ملف-ملف) | 70 ملف · 0 فاشل | `output/r31/fe_per_file.tsv` |
| باك (مُصنِّف الـCI على الـstaging المعزول) | 80 ملف · 77 ناجح · 2 فاشل · 1 متخطّى · 2480 حالة | `output/r31/be_cand/backend_results.json` |
| ⛔ برهان سالب (نفس الملفين على أساس R28) | النتيجة واحدة ⇒ ⛔ صفر انحدار ⭐ | `tools/r29_base_failing.json` |
| الفحص الوظيفي على الباك الحقيقي | 37/37 (وظائف 22/22 · رفض 6/6 · رحلة 9/9) | `output/r31/function_probe.json` |
| عقد المستودعين | 20/20 ببصمتي R31 | `output/r31/cross_repo_contract.json` |
| بوابة A5 (شجرة نظيفة) | 11/11 على `975664d` | `output/r31/gate_a5.log` |
| حارس بوّابات الـCI | rc=0 على ملفي الـworkflow ببصمة `5a4d91a` | `output/r31/live_checks.json` |
| تدقيق الوصولية (Chromium حقيقي · 9 عروض) | 9/9 · لمس<44 = 0 · تباين فاشل = 0 · بلا اسم = 0 · لوحة المفاتيح 10/10 · تركيز مرئي 10/10 · Escape PASS | `output/r31/a11y/a11y-audit.json` |
| اختبار دفعة R31 (باك) | 30/30 على المرشح · 18/30 على الأساس | `tools/test_r31_batch.py` |
| اختبار دفعة R31 (واجهة) | 9/9 على المرشح · 4/9 على الأساس | `assets/tests/r31-preview-security.test.js` |
| سجل الاعتماد 144 | جاهز (حد 90% متحقق · إلزاميات 18/18) | `output/r31/acceptance_r31.md` |
| تدقيق الـdist | نظيف · 118 ملف · 5.64 MB | `output/r31/live_checks.json` |
| المسح الأمني | شجرة العمل + الحزم + تاريخ الـgit (3 مستودعات) | `output/r31/secrets-scan.json` |

---

## 3) دفعة الإصلاح الواحدة (ما تغيّر بالضبط)

### 3.1 قفل الكتابة في جسر المعاينة — مُغلق
- قبل: `isBackendReadOnly(path)` كان يفحص المسار فقط ⇒ أي `POST/PUT/DELETE/PATCH` على مسار قراءة كان بيمرّ للباك الحقيقي.
- بعد: في نهاية `handlePreviewApi` أي كتابة على مسار قراءة ⇒ `405 {ok:false, error:'preview_read_only', why:'preview_write_blocked'}`، وحارس ثانٍ في `worker.js` قبل `if (!API) return apiUnavailable();` مربوط بـ`env.OCTA_PREVIEW_SELF_API === 'on'` (الإنتاج غير متأثر).
- دليل حيّ على النشر الجديد: `POST /api/gold` ⇒ `405 preview_read_only` · `PUT /api/charts/list` ⇒ `405 preview_read_only`.
- اختبار: `assets/tests/r31-preview-security.test.js` (4 إخفاقات على أساس الواجهة · 0 على المرشح).

### 3.2 إصدار الجلسة بالبصمة وحدها — مُغلق
- قبل: `POST /api/auth/pin/fingerprint` كان يُصدر جلسة بهيئة الجهاز فقط (بلا PIN وبلا نافذة) ⇒ البصمة = مفتاح.
- بعد (الإنتاج): `update_prices.py` ⇒ إثبات `pin_ok_at` + `pin_ok_dev` عند نجاح PIN، والشرط `same_device` بـ`hmac.compare_digest` ⇒ البصمة وحدها ⇒ `401 why:'need_pin'`.
- بعد (المعاينة): `preview-api.js` ⇒ نفس القاعدة بنافذة 600 ثانية + عملية ذرّية `acct_touch_pin` في `preview-store.js` (قراءة + تعديل + كتابة في عملية واحدة، بلا رفع الـepoch).
- اختبار: نفس ملف R31 ⇒ الفارق على الأساس: 200 بدل 401.

### 3.3 عدّاد المحاولات في المعاينة — مُغلق
- قبل: باسورد صحيح + جهاز غير مسجّل كان يُحسب محاولة فاشلة ⇒ قفل ذاتي 15 دقيقة على مستخدم صحيح.
- بعد: صفر خصم + رد `401 {why:'new_device', need_code:true, next:'challenge/send'}` (نفس سلوك الإنتاج) + الفهرس يمسك حالة «الباسورد صح + جهاز غريب».
- اختبار: نفس ملف R31 + تحديث توقع `assets/tests/preview-api.test.js` ⇒ 25/25 ناجح على المرشح.

### 3.4 قاعدة الباقة عند غياب تاريخ الانتهاء — مُغلق
- قبل: `plan_gate.plan_of` كان `if until and until < now` ⇒ `until = 0` (ناقص) ⇒ يرجع **pro** ⇒ «Pro بلا نهاية».
- بعد: `if until <= 0: return "free"` + `if until < now: return "free"` (fail-closed) + توثيق `plan_gate` (free/pro فقط · تفعيل يدوي إداري · 350 جنيه/شهر و3500/سنة · حقول السجل · مفيش Stripe ولا PayPal ولا checkout).
- الأثر: مسار التفعيل الإداري في `update_prices.py` بيكتب `plan_until` دايماً ⇒ ولا مستخدم Pro حقيقي بيفقد باقته.
- اختبار: `test_pattern_daily.py` اتحدّث ⇒ «Pro بلا تاريخ انتهاء ⇒ 403» (تأكيد صريح) + `tools/test_r31_batch.py`.

### 3.5 فحص قابلية الكتابة (نمط FINDING-23) — مُغلق
- نفس النمط (probe باسم ثابت) في 6 وحدات: `plan_gate.py` · `pattern_challenges.py` · `pattern_daily.py` · `pattern_studio.py` · `pattern_zones.py` · `subscription_core.py`.
- الإصلاح: اسم فريد `.w-%d` بالـpid + `except OSError: pass` عند فشل الحذف + `DATA_DIR_PROBE_ERROR` للتشخيص.
- برهان حتمي: محاكاة حذف متزامن (بتعديل `pathlib.PosixPath.unlink` خارج الـtry) ⇒ الأساس يقع في مجلد الكود والمرشح يبقى في مجلد البيانات ⇒ FAIL على الأساس · PASS على المرشح.

### 3.6 إصلاحا الوصولية — مُغلق
- `.mv-per` (أزرار الفترات) كانت 31px ⇒ `min-height:44px` + `padding:12px 15px` ⇒ هدف اللمس مطابق.
- `.mv-per.on` التباين 2.69:1 ⇒ خلفية `#1f2a3a` + نص `#ffffff` ⇒ ≥ 4.5.
- `Escape` كان ما بيقفلش القائمة الجانبية ⇒ مستمع Escape في `assets/js/octa-sidebar.js` ⇒ `OPEN=false` + `syncOpen()`.
- القياس: `locator.ariaSnapshot()` (شجرة المتصفح الحقيقية) + محرك المستودع `r26-audit.js` + Chromium حقيقي ⇒ 9/9 على 9 عروض + 9 لقطات.

### 3.7 توثيق الباقات — مُغلق
- `plan_gate.py` (docstring) + تقرير الجولة ⇒ reality واحد: free/pro · تفعيل يدوي إداري · مفيش الدفع الإلكتروني · مافيش invoice · مفيش شروط ولا إلغاء ولا قناة دعم.

---

## 4) سجل الاعتماد ١٤٤

- الملف: `output/r31/acceptance_r31.md` + `acceptance_r31.json` (144 بند · الأوزان الأصلية 35/30/25/10 · لا نسبة موروثة).
- البنود الإلزامية 18/18 · حد القبول 90% متحقق · `ready_for_review = true` · `acceptance_rc = 0`.
التغيير في الدليل: `AC-29-3` بقي متعذر (ما فيش قارئ شاشة بشري — السبب نفسه مكتوب) و`AC-29-4` بقي ناجح (لقطات + تدقيق تباين حقيقي + شجرة وصولية حقيقية + عيوب مُصلحة).

---

## 5) الموانع المتبقية (كل واحد بصاحبه)

1. رحلة المعاينة الحيّة (32/32 في R29) ما اتقستش على بصمة R31 ⇒ السبب: مفتاح صندوق المعاينة (سر) مش متاح ⇒ كود التأكيد ما ينقرأش ⇒ **متعذر بصفر نقاط** (البديل المقيس: رحلة محلية على Chromium + تدقيق الوصولية).
2. فحصات مودال الذهب اللي محتاجة بيانات ⇒ البيئة المعزولة مافيش فيها بيانات سوق ⇒ **متعذر بصفر نقاط**.
3. `ci_runs` ⇒ التوكن بلا صلاحية `workflow` ⇒ 403 ⇒ نشر تعريف الـCI وتشغيله على Actions **بصلاحية المالك**.
4. `packages_scan` ⇒ المسح ناتج بعد بناء السجل ⇒ مراجعة في هذا التقرير.
5. `AC-36-4` ⇒ موافقة المالك على الباقات والتسعير والشروط وخطة النشر.
6. `AC-33-3/4` و`AC-35-4` ⇒ سجل rollback وموافقات منفصلة.
7. `AC-07-4` ⇒ فرض CSP قرار منفصل (المعاينة ترسل `Content-Security-Policy-Report-Only` غير مفروض).

---

## 6) خطوة تيليجرام (للمالك · من غير أي قيمة سر في هذه التقرير)

1. في BotFather ⇒ `/revoke` للتوكن القديم ثم `/token` لتوكن جديد.
2. في Railway ⇒ المشروع `calm-mercy` ⇒ الخدمة `octa-prices` ⇒ المتغيّر `TELEGRAM_BOT_TOKEN` ⇒ قيمة التوكن الجديد.
3. `redeploy` إلزامي: التوكن يُقرأ مرة واحدة وقت الاستيراد (`update_prices.py` سطر 14768 · `octa_app.py` سطر 57) ⇒ تغيير المتغيّر بلا إعادة نشر ما أثرش.
4. اختبار صناعي: رسالة واحدة على `TELEGRAM_CHAT_ID` ⇒ لازم توصل.
5. التحقق: `/api/health` = 200 + `/api/alerts/state` ⇒ `enabled:true` · `tracked:219` · `watch:0` (الإنتاج مافيش فيه رصد للتليجرام ⇒ التحقق يدوي).

---

## 7) الأدلة على القرص

`output/r31/` ⇒ `fe_suite2.log` · `fe_per_file.tsv` · `be_cand/backend_results.json` · `be_suite_cand.log` · `function_probe.json` · `cross_repo_contract.json` · `gate_a5.log` · `a11y/a11y-audit.json` + 9 لقطات · `journey/browser-journey.json` · `live_checks.json` · `acceptance_r31.md` + `acceptance_r31.json` · `secrets-scan.json`.
الحزم: `OCTA-ROUND31-BACKEND.zip` · `OCTA-ROUND31-FRONTEND.zip` · `OCTA-ROUND31-CI.zip` · `OCTA-ROUND31-DELIVERY.zip` + `OCTA-ROUND31-PACKAGES.json` (بصمة md5+sha256 لكل حزمة).
