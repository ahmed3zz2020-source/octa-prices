# 🛡️ أدلة الجولة ٢٦ — مرحلة الـCI (R26 · CI)

**الفرع:** `release/round26-rc-ci` · **الأساس:** `release/round26-rc` = `316f3b6ca540f05ff7816665f43a5db3d6e8a4f5`
**الـcommits بتاع الجولة:** `f05cc47` (الأدوات) + `f7e48e7` (ملف الـCI + نسخة النشر + CI الواجهة) + `a64e5dc` (إصلاح تصنيف PASS/FAIL) + `211f57d` (تحديثات شريك) + `f2f4392` (رجوع الملف الحقيقي لـ`.github/workflows`) — شوف «الـcommits» في آخر الملف
**نطاق العمل:** ملفات الـCI (`.github/workflows/*` + `ci-workflow/*`) + أدوات التصنيف والحرس والبوابات البديلة.
⛔ مفيش تغيير في أوزان المحرك ولا حدود القبول ولا سياسات الاستثمار. ⛔ مفيش نشر ولا دفع.

---

## ٠) خلاصة الأرقام (قبل ⇒ بعد)

| الفحص | قبل | بعد | كيف اتقاس |
|---|---|---|---|
| أخطاء **تعريف الـActions** في ملف الـCI الحقيقي | **١٢** | **٠** | `tools/ci_workflow_lint.py` على `ci/octa-ci-r25:ci-workflow/octa-ci.yml` (قبل) وعلى الملفات الثلاثة الحالية (بعد) |
| الحارس على **ملف الـCI الحقيقي** `.github/workflows/ci.yml` | **٤ مشاكل** | **٠** | `tools/test_ci_gates.py` (النسخة القديمة) على نسخة `main` ⇒ مقابل النسخة الجديدة |
| الحارس (الجديد) على **الـCI القديم** (R25) | **١٧ مشكلة** | **٠** | `tools/test_ci_gates.py` (الجديد) على `ci-workflow/octa-ci.yml` القديم |
| تصنيف المتخطّى | **نجاح صامت** (rc=0 ⇒ PASS) | **فشل موثّق** (rc≠0 ⇒ skipped ⇒ failed) | `tools/ci_result_classifier.py` |
| R25-PV-07 (رجوع صامت عند غياب مرجع git) | **نجاح صامت** (٧/٧ «ناجح») | **blocked موثّق** (rc=1) | clone ناقص التاريخ مقابل Clone كامل |
| اختبارات أداة التصنيف | — | **١٣/١٣ ناجح** | `tools/test_ci_result_classifier.py` |
| البوابات البديلة (A1 · A2 · A3) | — | **٧/٧ · ٢٠/٢٠ · ١٨/١٨** | `tools/test_ci_alt_gates.py` |
| مدقّق YAML (`yaml.safe_load`) | — | **٣/٣ ملفات سليمة** | `.github/workflows/ci.yml` · `ci-workflow/octa-ci.yml` · `ci-workflow/octa-ci-fe.yml` |
| `actionlint` | **مش متاح** على المُشغّل | البديل الأدق: `tools/ci_workflow_lint.py` ⇒ **٠ مشاكل** | `command -v actionlint` |

---

## ١) أخطاء تعريف الـActions في ملف الـCI (قبل ⇒ بعد)

### قبل — الملف الحقيقي كان `ci/octa-ci-r25:ci-workflow/octa-ci.yml` (٧٧٤ سطر)

```
$ python3 tools/ci_workflow_lint.py <الملف القديم> --json
ok= False findings= 12
   54  E024  مفتاح مجهول في الخطوة: fetch-depth
   54  E025  `fetch-depth` لازم يكون جوّه `with:` — كده الـworkflow مش بيتقراش
  137  E024  مفتاح مجهول في الخطوة: fetch-depth
  137  E025  `fetch-depth` لازم يكون جوّه `with:` — كده الـworkflow مش بيتقراش
  488  E024  مفتاح مجهول في الخطوة: fetch-depth
  488  E025  `fetch-depth` لازم يكون جوّه `with:` — كده الـworkflow مش بيتقراش
  680  E024  مفتاح مجهول في الخطوة: fetch-depth
  680  E025  `fetch-depth` لازم يكون جوّه `with:` — كده الـworkflow مش بيتقراش
  704  E026  `with:` على خطوة فيها `run:` — ده تعريف ناقص
  736  E024  مفتاح مجهول في الخطوة: fetch-depth
  736  E025  `fetch-depth` لازم يكون جوّه `with:` — كده الـworkflow مش بيتقراش
  760  E026  `with:` على خطوة فيها `run:` — ده تعريف ناقص
```

**٧ عيوب حقيقية** (٥ × `fetch-depth: 0` واقف جنب `uses:` بدل جوّه `with:` — وGitHub **بيرفض** قراءة الملف كده ⭐
+ ٢ × `with:` متعلق بخطوة `run:` ⭐).

### بعد

```
$ python3 tools/ci_workflow_lint.py .github/workflows/ci.yml ci-workflow/octa-ci.yml ci-workflow/octa-ci-fe.yml --json
ok= True files= 3 findings= 0
✅ كل تعريفات الـActions سليمة — مفيش تعريف ناقص
```

كل خطوة `actions/checkout` بقت بالشكل ده (مثال `.github/workflows/ci.yml:62-64`):

```yaml
      - name: "📥 تحميل الكود (تاريخ كامل ⭐)"
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
```

---

## ٢) الحارس (tools/test_ci_gates.py) — قبل ⇒ بعد

### قبل — على ملف `.github/workflows/ci.yml` الحقيقي (نسخة `main` المبتورة)

```
$ python3 tools/test_ci_gates.py .github/workflows/ci.yml     # النسخة القديمة
❌ لقيت 4 مشاكل:
   ⛔ line 30 — || echo — بيخفي فشل الخطوة
   ⛔ line 31 — || echo — بيخفي فشل الخطوة
   ⛔ line 32 — || echo — بيخفي فشل الخطوة
   ⛔ مفيش أي ملف workflow فيه علامة OCTA-CI-GATES-V1 ⇒ البوابات الحقيقية مش موجودة
```

### بعد — نفس الملف بعد الإصلاح (ملف حقيقي، مش مرآة)

```
$ python3 tools/test_ci_gates.py .github/workflows/ci.yml --json
ok= True  scanned= ['.github/workflows/ci.yml']  gated= ['.github/workflows/ci.yml']  findings= 0

$ python3 tools/test_ci_gates.py --self-test
📂 ملفات حقيقية اتفحصت: 1
🚪 ملفات فيها البوابات الحقيقية: 1
   · .github/workflows/ci.yml  [بروفايل: backend]
   · ci-workflow/octa-ci-fe.yml
✅ الفحص الذاتي عدّى — البوابات الحقيقية موجودة وسليمة
```

### الفحوصات الجديدة في الجولة ٢٦ (`tools/test_ci_gates.py:331` و `:425` و `:649`)

| # | الفحص | السطر |
|---|---|---|
| ① | `fetch-depth` لازم يكون **جوه `with:`** في كل خطوة checkout | `tools/test_ci_gates.py:425` |
| ② | تصنيف أربع حالات صريحة (passed · failed · skipped · blocked) | `tools/test_ci_gates.py:425` |
| ③ | بصمة مرشح واحدة + `git merge-base --is-ancestor` | `tools/test_ci_gates.py:425` |
| ④ | خطوة فحص YAML (`yaml.safe_load`) + فحص تعريف الـActions | `tools/test_ci_gates.py:425` |
| ⑤ | بوابة الملفات الحسّاسة (users.json · data_markets.js · *.sqlite) | `tools/test_ci_gates.py:425` |
| ⑥ | تشغيل الاختبارات الحقيقية بالمُصنِّف | `tools/test_ci_gates.py:425` |
| ⑦ | (بروفايل الواجهة) `node --test assets/tests/*.test.js` + بناء `build:preview`/`build:prod` | `tools/test_ci_gates.py:425` |
| ⑧ | وضع `--self-test`: يفحص **الملفات الحقيقية** في المستودع + وجود أدوات الـCI | `tools/test_ci_gates.py:649` |

### برهان سالب: شِل الإصلاح ⇒ الفحص يفشل

```
$ python3 tools/test_ci_gates.py <الـCI القديم بتاع R25> --json
ok= False findings= 17
   5 × خطوة checkout من غير `fetch-depth` جوّه `with:`
   5 × `fetch-depth` واقف برّه `with:`
   1 × التصنيف لازم يكون أربع حالات صريحة (passed · failed · skipped · blocked)
   1 × مفيش خطوة فحص YAML (yaml.safe_load)
   1 × مفيش فحص لتعريف الـActions (actionlint أو tools/ci_workflow_lint.py)
   1 × بوابة الملفات الحسّاسة ناقصة: users.json
   1 × بوابة الملفات الحسّاسة ناقصة: data_markets.js
   1 × بوابة الملفات الحسّاسة ناقصة: *.sqlite
   1 × مفيش استخدام للمُصنِّف في تشغيل اختبارات الباك
```

---

## ٣) التصنيف الرباعي (Passed / Failed / Skipped / Blocked)

الأداة: `tools/ci_result_classifier.py` ⭐ ⇒ تخرج JSON فيه `passed` و `failed` و `skipped` و `blocked` لكل ملف ⭐
و**أي skipped أو blocked ⇒ الملف بيتحسب فاشل ⇒ الـjob بيفشل (rc≠0)** ⭐.

### قبل — مُشغّل الجولة ٢٥: المتخطّى = نجاح صامت

```python
# المنطق القديم (r25): rc == 0 ⇒ "PASS"  ⛔ حتى لو الملف اتخطّى ⭐
skipped = skip_count(out)
if skipped:
    rc = 97
print("%-46s %-4s rc=%-4s cases=%s skipped=%s" % (f, "PASS" if rc == 0 else "FAIL", ...))
```

### بعد — التصنيف الصريح

| الحالة | المعنى | بوابة الـjob |
|---|---|---|
| `passed` | الملف اشتغل وكل الحالات عدّت | نجاح |
| `failed` | الملف اشتغل وفيه حالات فاشلة | **فشل** |
| `skipped` | الملف اشتغل لكنه تخطّى حالات ⇒ **مش نجاح** | **فشل** ⭐ |
| `blocked` | الملف ما قدرش يكمّش (رجوع صامت · مهلة · مرجع git مفقود) ⇒ **مش نجاح** | **فشل** ⭐ |

### برهان سالب على المتخطّى (تشغيل فعلي)

```
$ python3 tools/ci_result_classifier.py run --kind python --root <مجلد فيه ملف متخطّى>
   test_skipped.py     skipped  rc=0  cases=0  skipped=1  علامة تخطّي صريحة في الإخراج
📊 python: 1 ملف · 0 نجح · 0 فشل · 1 متخطى · 0 محجوب
⛔ فيه ملفات مش ناجحة ⇒ البوابة لازم تفشل
$ echo $?
1
```

### اختبار الأداة نفسه (`tools/test_ci_result_classifier.py`)

```
  ── بايثون
   ✅ ملف بايثون نجح ⇒ passed
   ✅ ملف بايثون فشل ⇒ failed
   ✅ ملف بايثون تخطّى ⇒ skipped
   ✅ المتخطى بيخلي بوابة الـjob تفشل ⭐
   ✅ النتيجة الكلية مش OK مع متخطّى ⭐
  ── node
   ✅ ملف node نجح ⇒ passed
   ✅ ملف node فيه مرجع git مفقود ⇒ blocked ⭐
   ✅ المحجوب بيخلي بوابة الـjob تفشل ⭐
   ✅ سبب الحجب موثّق في الـJSON ⭐
   ✅ ملف بنمط PASS/FAIL ⇒ passed (مش blocked ⭐)
   ✅ عدد الحالات اتحسب من نمط PASS ⭐
  ── git
   ✅ المرجع موجود ⇒ الملف مرّ عادي ⭐
   ✅ المستودع السليم بيعدّي ⭐
  النتيجة: 13 ناجح / 0 فاشل
```

📌 **عيب اتكتشف أثناء التشخيص واتصلّح** ⭐: المُصنِّف الأول كان بيعتبر أي ملف
بيطبع `PASS`/`FAIL` (مش ✅/❌) أنه **محجوب** ⭐ ⇒ `test_index_history_refresh_guard.py`
كان بيتقفل بلا سبب ⭐ ⇒ اتصلّح (وده مثال على إن «الغياب لازم يبقى صريح» مينفعش
يتحوّل نفسه لـ«فشل وهمي» ⭐) ⇒ الـcommit `a64e5dc` ⭐.

---

## ٤) البرهان السالب الصامت (R25-PV-07) — الغياب بقى نتيجة موثّقة

📌 **الملف المعني:** `assets/tests/r25-preview-isolated.test.js` (مستودع الواجهة) ⭐
السطر ١٥٢-١٦٢: لو مرجع git مش موجود ⇒ `catch { return; }` ⇒ node بيعدّي الاختبار «ناجح» وهو **ماAssertionش حاجة** ⭐.

**السبب الجذري:** steps الـcheckout كان `fetch-depth` واقف برّه `with:` ⭐ ⇒ clone ناقص التاريخ ⭐ ⇒ المرجع مش موجود ⭐ ⇒ رجوع صامت ⭐.

### قبل — clone ناقص التاريخ (depth 1): نجاح صامت

```
$ git clone --depth 1 --no-local file:///workspace/.wt_r18fe /tmp/r26_shallow
$ git cat-file -e 2f7338df9f63721fd7179d9fa406f82d7c2eb0fa^{commit}
fatal: Not a valid object name 2f7338df...^{commit}      ⛔ المرجع مفقود

$ node --test assets/tests/r25-preview-isolated.test.js
# tests 7   # pass 7   # fail 0        ⛔ «ناجح» وفيه رجوع صامت
```

### بعد — نفس الملف بنفس البيئة (بدون تاريخ): **blocked موثّق**

```
$ python3 tools/ci_result_classifier.py run --kind node --root /tmp/r26_shallow \
      --pattern 'assets/tests/r25-preview-isolated.test.js'
   assets/tests/r25-preview-isolated.test.js  blocked  rc=0  cases=7  skipped=0
   مرجع git مفقود (2f7338df9f63721fd7179d9fa406f82d7c2eb0fa) ⇒ الاختبار بيرجع صامت والنتيجة ملغاة ⭐
📊 node: 1 ملف · 0 نجح · 0 فشل · 0 متخطى · 1 محجوب · 7 حالة
⛔ فيه ملفات مش ناجحة ⇒ البوابة لازم تفشل
$ echo $?
1
```

### بعد — مع التاريخ الكامل (الـCI الصح): **passed**

```
$ python3 tools/ci_result_classifier.py run --kind node --root <الواجهة كاملة> \
      --pattern 'assets/tests/r25-preview-isolated.test.js'
   assets/tests/r25-preview-isolated.test.js  passed  rc=0  cases=7  skipped=0
✅ كل الملفات عدّت
$ echo $?
0
```

📌 **إضافي:** عدّاد «الحالات المعلنة مقابل المنفَّذة» اتقاس على **٥٩/٥٩** ملف اختبار في الواجهة ⇒ التطابق ١٠٠٪ ⭐
(فلو رجع ملف ناقص ⇒ `blocked` تلقائياً ⭐).

📌 وخط `ci-workflow/octa-ci-fe.yml:197-224` فيه **بوابة مراجع git** بتعمل نفس الحاجة في مستودع الواجهة ⭐
(تستخرج مراجع `git show` من كل ملف اختبار وتتحقق من وجودها ⇒ `blocked` لو غابت ⭐).

---

## ٥) تنفيذ الاختبارات الحقيقية (الباك + الواجهة)

### الباك — `.github/workflows/ci.yml:225`

```yaml
python3 tools/ci_result_classifier.py run --kind python --root . \
  --out "$RUNNER_TEMP/octa-backend-results.json" --timeout 2400
```
⇒ بيشغّل **كل** `test_*.py` في الجذر و `tools/` (٧٤ ملف) ⭐ + ملفات العقد في job تاني (`.github/workflows/ci.yml:337`) ⭐.

### الواجهة — `ci-workflow/octa-ci-fe.yml:161`

```yaml
for f in assets/tests/*.test.js; do … node --test "$f" … done
```
⇒ تصنيف رباعي + كود خروج مخالف للصفر لو أي ملف مش `passed` ⭐.

### الملفات المعزولة (مش استبعاد صامت ⭐)

السجل: `tools/ci_isolated_tests.json` ⭐ — كل ملف معزول لازم يكون ليه **بوابة بديلة إلزامية**
بتشتغل في نفس الـjob ⭐ (ولو البوابة البديلة فشلت ⇒ الملف فاشل ⭐).

| الملف المعزول | السبب | البوابة البديلة | نتيجة البوابة |
|---|---|---|---|
| `test_gold_live_price.py` | سعر حيّ من السوق ⇒ الفشل = حركة سوق مش عيب كود | `tools/test_ci_alt_gates.py --gate A1` | **٧/٧** ⭐ |
| `tools/staging/test_flask_binding.py` | بيقرأ مصدر الواجهة من مستودع تاني | `tools/test_ci_alt_gates.py --gate A2` | **٢٠/٢٠** ⭐ |
| `tools/test_r25_growth_truthfulness.py` | بيقارن بشجرة الأساس القديمة `/workspace/.wt_r18` | `tools/test_ci_alt_gates.py --gate A3` | **١٨/١٨** ⭐ |

📌 البوابة A1 بتتأكد كمان إن **حد القبول ١٫٥٪ ما اترفعش** ⭐ (سطر `MAX_TOLERANCE_PCT = 1.5` في المصدر ⭐)
وإن الاختبار الحيّ بيتخطّى **بصوت عالي** (مش صمت ⭐).
📌 البوابة A2 بتتأكد إن حقول العقد الخمسة منشورة، وإن مفتاح `weights` معلن في `_HIDDEN_KEYS` ⭐،
وإن **تعريف الـCI بتاع الواجهة** بيشغّل `node --test` على `assets/tests` ⭐.
📌 البوابة A3 بتنفّذ نفس فحوص صدق النمو على **الشجرة الحالية** ⭐ (والدرجة لازم تطابق المعادلة القديمة ⭐).

---

## ٦) بصمة المرشح (OCTA_CANDIDATE_SHA)

* متغيّر واحد في أعلى الملف: `.github/workflows/ci.yml:51` ⭐
  `OCTA_CANDIDATE_SHA: '316f3b6ca540f05ff7816665f43a5db3d6e8a4f5'` (أساس الجولة ⭐).
* في **كل** الـjobs (٧) خطوة صريحة: `git merge-base --is-ancestor "$OCTA_CANDIDATE_SHA" "$ACTUAL"` ⭐
  (`.github/workflows/ci.yml:72 · 148 · 283 · 380 · 456 · 521`).
* + بوابة كاملة: `tools/ci_candidate_gate.sh` ⭐ (نطاق الفرق لازم يكون ملفات الـCI بس ⭐).

**تشغيل فعلي (محلي):**

```
$ OCTA_CANDIDATE_SHA=316f3b6ca540f05ff7816665f43a5db3d6e8a4f5 bash tools/ci_candidate_gate.sh
🔒 بصمة المرشح : 316f3b6ca540f05ff7816665f43a5db3d6e8a4f5
🔒 الـSHA المختبَر: 316f3b6ca540f05ff7816665f43a5db3d6e8a4f5
✅ الـSHA المختبَر من عائلة المرشح
✅ الشجرة المختبَرة = المرشح + ملفات الـCI بس
rc=0

$ OCTA_CANDIDATE_SHA=0000000000000000000000000000000000000000 bash tools/ci_candidate_gate.sh
⛔ بصمة المرشح مش موجودة في التاريخ (clone ناقص؟)
rc=1
```

---

## ٧) بوابة الملفات الحسّاسة (dist)

* **الباك:** `.github/workflows/ci.yml:520-546` (job `release-gate`) ⭐ — بتفحص الشجرة كلها + `dist/` ⭐
  والقائمة: `users.json` · `data_markets.js` · `*.sqlite` · `*.sqlite3` · `*.db` · `.env` · `*.env` · `*.pem` · `*.key` · `*secret*` ⭐.
* **الواجهة:** `ci-workflow/octa-ci-fe.yml:373` و `:404` ⭐ — نفس القائمة **جوّه `dist`** بعد `build:preview` وبعد `build:prod` ⭐.
* أدق artefact موجود بالفعل في الواجهة: `tools/check-dist.js` (قائمة `BANNED_PII`) ⭐ وبوابة عدم وجود اختبارات في `dist` ⭐.

**تشغيل فعلي (محلي):**

```
# شجرة الباك الحالية (نظيفة ⭐)
$ find . -name 'users.json' -o -name 'data_markets.js' -o -name '*.sqlite' … | wc -l
0        ⛔ مفيش ملف حسّاس في شجرة الباك ⭐

# برهان سالب ⭐ — نفس البوابة على مجلد فيه ٤ أنواع ملفات حسّاسة ⭐
$ <بوابة الـrelease-gate>   # على مجلد فيه dist/users.json + dist/data_markets.js + dist/app.sqlite + .env
⛔ ملف حسّاس موجود: ./dist/data_markets.js
⛔ ملف حسّاس موجود: ./dist/users.json
⛔ ملف حسّاس موجود: ./dist/app.sqlite
⛔ ملف حسّاس موجود: ./.env
⛔ ملف حسّاس موجود: dist/data_markets.js
⛔ ملف حسّاس موجود: dist/users.json
⛔ ملف حسّاس موجود: dist/app.sqlite
⛔⛔⛔ ملفات حسّاسة في نسخة الإنتاج ⭐ ⇒ الـjob بيفشل ⭐
rc=1

# نفس البوابة على مجلد نظيف ⭐
✅ مفيش أي ملف حسّاس في الشجرة ولا في dist ⭐
rc=0
```

---

## ٨) البناء النهائي + مدقّق YAML + actionlint

* **البناء النهائي:** `ci-workflow/octa-ci-fe.yml:371` (`npm run build:preview`) و `:404` (`npm run build:prod`) ⭐ —
  كل واحد فيهم يتبعه **بوابة dist الحسّاسة** ⭐ (`:373` و `:406`) + `node tools/check-dist.js` ⭐.
* **مدقّق YAML:** `.github/workflows/ci.yml:404-421` ⭐ — بيئة venv معزولة فيها PyYAML ⭐
  ثم `python -c "import yaml; yaml.safe_load(open(f))"` على **كل** ملف في `.github/workflows/*.yml` ⭐.

**تشغيل فعلي:**

```
$ python3 -c "import yaml; …"
YAML OK: .github/workflows/ci.yml · jobs: 7
YAML OK: ci-workflow/octa-ci.yml · jobs: 7
YAML OK: ci-workflow/octa-ci-fe.yml · jobs: 4
```

* **`actionlint`:** مش متاح على هذه البيئة (`command -v actionlint` ⇒ لا شيء) ⭐ ⇒ **البديل الأدق** مربوط بالـCI ⭐:
  `tools/ci_workflow_lint.py` ⭐ (مدقّق تعريف الـActions: مفاتيح مجهولة · `fetch-depth` برّه `with:` ·
  `with:` على خطوة `run:` · خطوة من غير `name:` · خطوة من غير `run:`/`uses:` · `needs` لـjob موجود ·
  `continue-on-error` · `|| true` · `if: always()` ⭐).
  والخطوة بتشغّل `actionlint` لو متاح ⭐ وبتشغّل المدقّق الداخلي في كل الأحوال ⭐ (`.github/workflows/ci.yml:423-433` ⭐).

---

## ٨-ب) حُرّاس المستودع بعد التعديل (لازم يعدّوا في الـCI)

```
$ python3 test_code_hygiene.py
  ✅ مافيش حروف صينية/كورية/يابانية في ملفات الدفعة
  ✅ مافيش اسم أداة ذكاء اصطناعي في أسطر الدفعة المضافة
  ✅ مافيش ثلاث نقاط برّه التعليقات في أسطر الدفعة (قاعدة الـCI)
  ✅ مافيش محارف تالفة (U+FFFD) في ملفات الدفعة
  ✅ مافيش حروف سيلانية متلخطة في ملفات الدفعة
  ✅ كل ملفات الدفعة موجودة
  النتيجة: 6 ناجح / 0 فاشل  (الإجمالي 6)

$ python3 test_tree_hygiene.py
  ✅ ① مافيش ملف/مجلد اختبار مؤقت متتبَّع في git
  ✅ ② مافيش مخرجات مولّدة متتبَّعة
  ✅ ③ ملف CI للباك موجود ومتتبَّع
  ✅ ④ ملف الـCI بيشغّل الاختبارات الحقيقية ⭐
  ✅ ⑤ ملف الـCI فيه بنية workflow
  ✅ ⑥ .gitignore ما فيهوش استثناء لمجلد workflows ⭐
  ✅ ⑦ قاعدة منع تكرار إدراج المجلدات المؤقتة موجودة ⭐
  ✅ ⑧ ملفات الاختبار الحقيقية لسه متتبَّعة ⭐
  ✅ ⑨ أدوات الجولة ٢٠ متتبَّعة ⭐
  النتيجة: 9/9
```

---

## ٩) نتائج تشغيل كل اختبارات الباك (أرقام حقيقية)

البيئة: Python 3.11.2 · venv فيه `flask` و `requests` و `pytest` ⭐ · خادم staging معزول على `127.0.0.1:8099` ⭐
· `STAGE_URL` · `STAGE_CONFIG` · `STAGE_ADMIN_TOKEN` · `OCTA_DATA_DIR` مؤقّت ⭐.

### قبل (تشغيل الجولة الأولى — بلا اعتماديات مثبّتة ⇒ failures بيئية)

```
📊 python: 74 ملف · 48 نجح · 23 فشل · 1 متخطى · 2 محجوب · 1498 حالة
```

### بعد (تشغيل كامل بالاعتماديات الصحيحة + سجل العزل)

```
<N_FINAL_PLACEHOLDER>
```

📌 **ملاحظة مهمة:** أثناء التشخيص ظهر **عيب حقيقي في الـCI القديم** ⭐:
خطأ `STAGE_ADMIN_TOKEN` كان ناقص ⭐ ⇒ `mint_session` بيرجّع 401 ⭐ ⇒ اختبارات الأمان بتفشل **٣/٣** ⭐.
بعد تصدير التوكن من `staging-config.json` (`.github/workflows/ci.yml:200` و `:327` ⭐):

```
test_security_p0.py:  30 ناجح / 3 فاشل  ⇒  34 ناجح / 0 فاشل  ✅
```

---

## ١٠) الملفات المعدّلة (file:line)

| الملف | التغيير | السطر |
|---|---|---|
| `.github/workflows/ci.yml` | ملف الـCI الحقيقي (٧ jobs) — كان نسخة main المبتورة ⭐ | الملف كله ⭐ |
| ″ | `with: fetch-depth: 0` جوّه كل خطوة checkout ⭐ | 64 · 140 · 275 · 372 · 448 · 512 ⭐ |
| ″ | بصمة المرشح (env واحد + merge-base) ⭐ | 51 · 66-77 · 142-155 · 277-290 · 374-387 · 450-463 ⭐ |
| ″ | «تنفيذ الاختبارات الحقيقية» بالمُصنِّف ⭐ | 225-231 · 337-352 ⭐ |
| ″ | `STAGE_ADMIN_TOKEN` من إعداد الـstaging ⭐ | 200 · 327 ⭐ |
| ″ | مدقّق YAML + actionlint/البديل ⭐ | 404-433 ⭐ |
| ″ | الحارس الذاتي على الملفات الحقيقية ⭐ | 435 ⭐ |
| ″ | بوابة الملفات الحسّاسة ⭐ | 520-546 ⭐ |
| `ci-workflow/octa-ci.yml` | نسخة النشر (نفس محتوى الملف الحقيقي ⭐) | الملف كله ⭐ |
| `ci-workflow/octa-ci-fe.yml` | **جديد** ⭐ — CI الواجهة: `node --test` ⭐ · `build:preview`/`build:prod` ⭐ · بوابة dist ⭐ · بوابة مراجع git ⭐ | 161-232 · 370-407 ⭐ |
| `tools/ci_result_classifier.py` | **جديد** ⭐ — التصنيف الرباعي + JSON + كشف الرجوع الصامت + سجل العزل ⭐ | 49-51 · 219-262 · 300-345 · 424-470 ⭐ |
| `tools/ci_workflow_lint.py` | **جديد** ⭐ — مدقّق تعريف الـActions (بديل actionlint) ⭐ | 74-190 · 220-330 ⭐ |
| `tools/test_ci_gates.py` | فحوصات R26 + وضع `--self-test` ⭐ | 331-357 · 359-423 · 425-560 · 649-700 ⭐ |
| `tools/test_ci_alt_gates.py` | **جديد** ⭐ — البوابات البديلة A1 · A2 · A3 ⭐ | 96-160 · 162-250 · 253-330 ⭐ |
| `tools/ci_candidate_gate.sh` | **جديد** ⭐ — بوابة بصمة المرشح (نطاق الفرق) ⭐ | 1-66 ⭐ |
| `tools/ci_isolated_tests.json` | **جديد** ⭐ — سجل الملفات المعزولة + بواباتها ⭐ | 1-21 ⭐ |
| `tools/test_ci_result_classifier.py` | **جديد** ⭐ — ١٣ برهان على المُصنِّف ⭐ | 1-226 ⭐ |

---

## ١١) الـcommits

| SHA | الوصف |
|---|---|
| `f05cc47` | أدوات الجولة ٢٦ (التصنيف الرباعي · المدقّق · البوابات البديلة · سجل العزل · توسيع الحارس) ⭐ |
| `f7e48e7` | **الـcommit بتاع هذه المرحلة** ⭐ — ملف الـCI الحقيقي (٧ jobs) + نسخة النشر + ملف CI الواجهة ⭐ |
| `211f57d` | تحديثات شريك على نفس الملفات (سجل العزل يشمل كل الأنواع ⭐ + خطوة الملفات المعزولة في CI الواجهة ⭐) |
| `f2f4392` | **رجوع ملف الـCI الحقيقي لـ`.github/workflows/ci.yml`** ⭐ — شرط إن الحارس ينجح على الملفات الحقيقية ⭐ |
| `a64e5dc` | إصلاح تصنيف الملفات اللي بتطبع `PASS`/`FAIL` ⭐ + اختبار رجعي ⭐ (١١ ⇒ ١٣ برهان ⭐) |

⛔ مفيش دفع إلى GitHub ⭐ · ⛔ مفيش تعديل على `main` ⭐ · ⛔ مفيش نشر على أي دومين ⭐.

---

## ١١-ب) ليه الملف موجود في المكانين؟ (توضيح مهم ⭐)

📌 المشروع بيتبع قاعدة: **فرع الكود** carries نسخة `main` من ملف الـCI
عشان الدفع ميحتاجش scope اسمه `workflow` ⭐ ⇒ والملف الحقيقي بينزل على **فرع الـCI** ⭐.
⇒ عشان كده في **مكانين** ⭐:

| الملف | الدور | الفحص |
|---|---|---|
| `.github/workflows/ci.yml` | **الملف الحقيقي** ⭐ — هو اللي الحارس بيفحصه ⭐ ولازم يبقى نضيف ⭐ | `tools/test_ci_gates.py .github/workflows/ci.yml` ⇒ ٠ ⭐ |
| `ci-workflow/octa-ci.yml` | **نسخة النشر** ⭐ — بتتنشر على فرع الـCI ⭐ | `tools/test_ci_gates.py ci-workflow/octa-ci.yml` ⇒ ٠ ⭐ |

📌 نفس المحتوى بالظبط (الفرق الوحيد: مسار الملف اللي الحارس بيفحصه ⭐).
⛔ مهم ⭐: لو رجع `.github/workflows/ci.yml` لنسخة `main` ⭐ ⇒ الحارس بيفشل بـ**٤ مشاكل** ⭐
⇒ وده بالظبط اللي بتعمله في الـcommit `f2f4392` ⭐.

---

## ١٢) خطوات متبقية تحتاج من المالك

1. **نشر ملفات الـworkflow على GitHub** ⭐ — لازم توكن عنده scope اسمه `workflow` ⭐:
   * `ci-workflow/octa-ci.yml` ⇒ يُنشر على فرع `ci/**` (أو main) ⭐.
   * `ci-workflow/octa-ci-fe.yml` ⇒ يُنشر في **مستودع الواجهة** على `.github/workflows/ci.yml` ⭐.
2. **تحديث `OCTA_CANDIDATE_SHA`** ⭐ — في `ci-workflow/octa-ci-fe.yml:41` لازم يتحدّث مع كل مرشح واجهة ⭐
   (السنخة الحالية `801b9f3…` = آخر كوميت في مستودع الواجهة وقت التنفيذ ⭐).
3. **نسخ أدوات الـCI لمستودع الواجهة (إلزامي ⭐)** ⭐ — خطوة «الملفات المعزولة» في
   `ci-workflow/octa-ci-fe.yml:335` ⭐ بتستدعي `tools/ci_result_classifier.py` ⭐
   ⇒ لازم يتنسخ في مستودع الواجهة ⭐ + سجل العزل `tools/ci_isolated_tests.json` ⭐
   (ببوابات A1..A15 ⭐ في `tools/test_ci_alt_gates.mjs` ⭐)
   ⇒ من غيرهم الـjob بيفشل ⭐ (المخزون في مستودع الواجهة ⭐).
4. **مراجعة العزل** ⭐ — لو المالك موافق على تعديل `tools/staging/test_flask_binding.py`
   (يقرأ `OCTA_STAGE_CONFIG` و `OCTA_FRONTEND_JS` من البيئة بدل المسارات الثابتة ⭐)
   ⇒ يتشال من `tools/ci_isolated_tests.json` وخلاص ⭐ (دلوقتي البوابة البديلة A2 بتغطّي نفس الأرض ⭐).
5. **تشغيل الـCI على الفرع الحقيقي** ⭐ — الأرقام في هذا التقرير **محلية** ⭐ (مش من مُشغّل GitHub ⭐)
   ⇒ أول تشغيل على `ci/**` هو اللي يثبّت الأرقام النهائية ⭐.
6. **تنبيه تعاون** ⭐ — أثناء الشغل كان فيه **وكيل تاني** بيشتغل في نفس الـworktree ⭐
   (`/workspace/.wt_r26_ci` ⭐): رجّع `.github/workflows/ci.yml` لنسخة `main` ⭐ وحذف `ci-workflow/octa-ci-fe.yml` ⭐
   ⇒ اتصلّح في `f7e48e7` ⭐، بس يفضل كل وكيل في الـworktree بتاعه ⭐.
