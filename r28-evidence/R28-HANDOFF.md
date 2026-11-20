# OCTA · RC-R28-001 · ملف التسليم والمراجعة

- الباك: `ahmed3zz2020-source/octa-prices` · فرع `release/round28-rc` · `32cf806`
- الواجهة: `ahmed3zz2020-source/octa` · فرع `release/round28-rc-fe` · `4c65d7c`
- الـCI: فرع `ci/octa-ci-r28` · `cb3165c` · فرع الأدلة `review/round28-evidence`
- المعاينة: `https://octa-preview.ahmed3zz2020.workers.dev` · لوحة الإدارة: `https://octa-mgmt.ahmed3zz2020.workers.dev`

---

## المربع الجاهز للنسخ (نسخة المراجع ⭐)

```
أنت مراجع مُستقل لمشروع OCTA (منصة تحليل أسهم مصريّة: تقييم + فرص + محفظة + ذهب + تنبيهات).
الفرز: RC-R28-001 = الإغلاق الأمني النهائي + الإطلاق الوظيفي.
الواجهة (octa) والباك (octa-prices) منفصلان، ومعاينة Cloudflare منفصلة عن الإنتاج.

الفروع المرشحة (لا تدمج في main):
- octa-prices · release/round28-rc · 32cf806
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/32cf806/tools/r28_build_acceptance_log.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/32cf806/tools/r28_scan_secrets.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/32cf806/tools/r28_function_probe.py
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/32cf806/tools/r28_acceptance_items.csv
- octa · release/round28-rc-fe · 4c65d7c
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/mgmt/worker.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/preview-store.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/preview-api.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/worker-main.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/assets/tests/r28-admin-password.test.js
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa/4c65d7c/assets/tests/r28-preview-isolation.test.js
- الأدلة: octa-prices · review/round28-evidence · r28-evidence/
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/acceptance_r28.md
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/backend_results.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/secrets-scan.json
  https://raw.githubusercontent.com/ahmed3zz2020-source/octa-prices/review/round28-evidence/r28-evidence/live_checks.json

ما أُنجز في R28 (الأرقام كما قِيست، لا كما وُعد):
1) إغلاق ثغرة كلمة مرور لوحة الإدارة: mgmt/worker.js — قراءة حالة كلمة المرور صارت ثلاثية (ok/not_configured/no_state/read_failed)، والتوكن الجديد شكله exp.tag.sig، والتحقق من التوقيع قبل أي قراءة panel_state ⇒ الكوكي المزوّر = صفر نداءات DO/KV. مسار استرداد جديد POST /api/password/recover يعيد التعيين ولا يصدر جلسة. برهان: 18/18 على R28 و10 فاشل على كود R27.
2) إغلاق ملاحظات المعاينة R26-I01..I05: كل حالة المعاينة في Durable Object واحد (preview-store.js + worker-main.js)، والـKV للقططات فقط، ومساحة KV منفصلة للمعاينة (24f90783bedf4291b57705bbb2f51a88)، وصندوق المعاينة بمفتاح سري (X-Preview-Key) بلا كود في الرد. برهان: 13/13 على R28 و13/13 فاشل على R27.
3) القياسات: الواجهة 65 ملف · 719 ناجح · 0 فاشل. الباك 77 ملف · 74 ناجح · 2 فاشل بيئيان · 1 متخطّى · 2455 حالة. الفحص الوظيفي للباك الحقيقي 27/37. المسح الأمني: 7047 كائن git + 921 عضو حزمة · لا سر حقيقي واحد · التوكن الحيّ غير موجود في أي فرع أو حزمة. بوابة A5 11/11. عقد المستودعين 20/20.
4) سجل الاعتماد 144: 132 ناجح · 0 فشل · 12 متعذر ⇒ 3390/3600 = 94.17% محسوبة من الحالات (لا نسبة موروثة). 12 بندًا متعذرًا بأسبابها بالاسم في acceptance_r28.md.
5) النشر الحيّ: octa-preview (057b364b) وocta-mgmt (50a3959a) — فحص حيّ: health 200 + revocation_ready، login غلط 401 بلا كوكي، استرداد بلا مفتاح 401، كوكي مزوّر 401، الأصول سليمة.

القواعد الممنوعة (لا تكسرها):
- لا تدمج في main، ولا تنشر على octashares.com، ولا موارد مدفوعة، ولا بيانات عملاء حقيقية.
- لا أسرار في الملفات أو السجلات أو التقرير؛ لا تعِد كتابة تاريخ Git.
- لا تغيّر أوزان المحرك ولا حدود القبول ولا السياسات الاستثمارية.
- لا ترث نسبة 92.50% ولا أي نسبة جاهزة — كل نسبة تُحسب من قياس جديد.
- 401/403/404/501 ليست نجاحًا وظيفيًا؛ المتعذر = صفر نقاط.
- ممنوع "..." خارج التعليقات؛ ممنوع U+FFFD وCJK/Hangul/Cyrillic في أي نص عربي.

المطلوب منك:
راجع المرشح RC-R28-001 مقابل سجل الاعتماد والأدلة، وابحث عن عيوب لم تُمسّ: secret/state rotation في mgmt/worker.js، صحة عزل المعاينة (DO + KV + المفتاح)، خلل في خريطة النطاق ← قياس في tools/r28_build_acceptance_log.py، تسرّب سر في أي فرع أو حزمة، أو أي ادعاء في التقرير بلا قياس.

صيغة المخرجات المطلوبة (قائمة واحدة، كل بند: معرّف · الملف:السطر · العيب · البرهان (أمر + رقم قبل/بعد) · الخطورة):
FINDING-01 | mgmt/worker.js:1231 | <العيب> | <command + before/after> | critical|high|medium|low
```

---

##Changed since the previous delivery

- `mgmt/worker.js`: كلمة مرور الإدارة (قراءة حالة ثلاثية · توكن `exp.tag.sig` · مسار استرداد · 503 عند `state_unknown`).
- `preview-store.js` + `preview-api.js` + `worker-main.js`: حالة المعاينة في DO قوي · KV للقططات فقط · مفتاح صندوق.
- `wrangler.jsonc`: `PREVIEW_STORE` + migration `v1` + مساحة KV منفصلة (المعاينة ≠ الإنتاج).
- `tools/r28_build_acceptance_log.py` + `tools/r28_acceptance_items.csv`: سجل الاعتماد بأداة ثابتة.
- `tools/r28_scan_secrets.py` + `tools/r28_function_probe.py`: أدوات دائمة (بصمات فقط، بلا طباعة قيم).
- `assets/tests/r28-admin-password.test.js` + `assets/tests/r28-preview-isolation.test.js`: براهين قبل/بعد.
