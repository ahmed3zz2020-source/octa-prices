# OCTA — ملف التسليم (للشات الجديد) — الجولة 27

هذا الملف نقطة البداية للشات الجديد. فيه الحالة الكاملة.
الصورة: المشروع = منصة تحليل أسهم عربية (EGX). الواجهة = `octa`. الباك = `octa-prices`.

## 1) المستودعات والفروع والبصمات (مؤكدة بـ git ls-remote بعد الدفع)

`ahmed3zz2020-source/octa-prices` (الباك):
- release/round27-rc      fe45d683a9156f599fefe3b98753f4e62a760193
- ci/octa-ci-r27          4e5b6160ac2c6806301c7de8df7dc6dd00cb9054
- review/round27-evidence (فرع الأدلة — شوف القسم 9)
- release/round26-rc      ea93e90c718c175c588df33d6de1cf75130fd0ee (لم يتغير)
- main                    9c27f565d22fe1d126c5670de2070a66e980988c (لم يتغير)

`ahmed3zz2020-source/octa` (الواجهة):
- release/round27-rc-fe   5ec4e2574c91c209fe43a4815ca2cabacac822f4
- ci/octa-ci-r27-fe       ae5ff0831ba0269e76ef9fa1bdf389fcf0d410a2
- release/round26-rc-fe   0bbbd75b5a57a739fd175694ecd185331e7cb2c2 (لم يتغير)
- main                    4b9742130406c2341f63286ccc849813369394ff (لم يتغير)

## 2) البيئة الحيّة (كما هي — لم ينشر شيء)

- لوحة الإدارة: https://octa-mgmt.ahmed3zz2020.workers.dev/login.html
  `GET /api/health` ⇒ ok:true · has_admin:true · has_password:true · revoke_shared:true ·
  revoke_strong:true · revocation_ready:true
- المعاينة المعزولة: https://octa-preview.ahmed3zz2020.workers.dev
  `GET /api/health` ⇒ source: preview-isolated
  للمعاينة KV مستقل (68e1d82a57f94344a051bcfd9dfd81ed) + سر جلسات خاص. صفر اتصال بالإنتاج.
- الإنتاج (octashares.com): ممنوع النشر عليه بلا عبارة صريحة من المالك.

## 3) أرقام القياس (كلها traced)

| المجموعة | النتيجة | المصدر |
|---|---|---|
| الواجهة | 688 اختبار · 688 ناجح · 0 فاشل · 474 ثانية | `r27-evidence/fe_suite_r27.log` |
| الباك | 78 ملف · 78 ناجح · 0 فاشل · 2491 حالة · 217 ثانية | `r27-evidence/backend_suite_r27.json` |
| بوابات الـCI | كل البوابات سليمة | `python3 tools/test_ci_gates.py` |
| الحزم | 4 حزم · 0 سر · 0 نص ملوث | `r27-evidence/OCTA-ROUND27-PACKAGES.json` |

قياس الباك = نفس خطوات الـCI بالظبط: staging معزول على 127.0.0.1:8099، تصفير قبل
كل ملف، بيانات مرجعية على نسخة مؤقتة، بدون تيليجرام، بدون مهام خلفية.

قياس الواجهة اتعمل منفرداً (من غير منافسة) لأن فيه تأكيدات توقيت (LCP < 4000ms)
⇒ دي بتقيس الجهاز مش الكود.

## 4) حزمة الأدلة (فرع review/round27-evidence)

- `r27-evidence/R27-EVIDENCE.md` — التقرير الكامل.
- `r27-evidence/fe_suite_r27.log` + `fe_suite_r27.md` — سجل TAP الخام + ملخصه.
- `r27-evidence/backend_suite_r27.json` + `backend_suite_r27.md` — نتائج المصنِّف + ملخصه.
- `r27-evidence/OCTA-ROUND27-PACKAGES.json` — بصمات الحزم.
- `r27-evidence/OCTA-ROUND27-HANDOFF.md` — الملف ده.
- `r27-evidence/OCTA-ROUND27-REVIEW-BOX.txt` — المربع الجاهز للنسخ.
- `r27-evidence/OCTA-ROUND27-NEW-CHAT.txt` — مربّع بدء الشات الجديد.

## 5) الأدوات (داخل الريبو)

- `tools/r27_build_packages.py` — يبني الحزم من شجرة git (حتمي) + مسح أسرار ونص.
- `tools/r27_build_evidence.py` — يبني ملخصات المجموعات من سجلات القياس.
- `tools/test_ci_alt_gates.py` — البوابات البديلة A1..A4 (A4 جديدة في R27).
- `tools/ci_isolated_tests.json` — سجل الملفات المعزولة (4 ملفات) وبواباتها.
- `tools/ci_result_classifier.py` — المصنِّف الرباعي (passed/failed/skipped/blocked).
- `tools/ci_reset_staging.sh` — تصفير البيئة قبل كل ملف.
- `tools/ci_candidate_gate.sh` — بوابة بصمة المرشح.
- `tools/test_ci_gates.py` — حارس نقاء ملف الـCI (يفحص المرآة الحقيقية).
- `tools/deploy-mgmt.js` (الواجهة) — نشر لوحة الإدارة مع الحفاظ على الأسرار.
  `NAME=octa-mgmt MGMT_DIR=mgmt node tools/deploy-mgmt.js` — يرفض النشر على الإنتاج.
- `mgmt/tests/lib/domock.js` — موك الـDurable Object.

## 6) ما اتغيّر في R27 (ملخص)

الواجهة:
- 9 دعامات اختبار: تشيل كل أسطر الـimport + تحمّل preview-api.js في نطاق منفصل.
- 3 ملفات لوحة إدارة: وسم الاعتماد بقى يطابق كود R26 + فصل namespace الإبطال.
- موك الـDO: الـPOST اللي يثبت الإبطال لازم يكون على namespace الإبطال بس.
- R23-G4: التوقع الجديد (نفس الأصل) + تأكيدات أقوى.
- R22-DO-07: التحقق محصور في namespace الإبطال + قائمة مسموحة.
- ملف جديد: `assets/tests/r26-preview-self-api.test.js` (9 اختبارات).
- اختباران جديدان: R26-S-26 و R26-S-27 (تدوير كلمة المرور).

الباك:
- `test_data_full_route.py`: اختيار حتمي لملف بيانات الواجهة (أولوية لمسار صريح).
- `tools/test_ci_alt_gates.py`: بوابة A4 (بديل test_round23_clean_clone.py).
- `tools/ci_isolated_tests.json`: تسجيل الملف المعزول ببوابته.
- `tools/test_ci_gates.py`: يفحص مرآة الـworkflow الحقيقية.

فرع الـCI:
- بصمة المرشح محدّثة (الباك fe45d68 · الواجهة c520591).
- الحارس يفحص المرآة، والنطاق يسمح بمرآة الـCI و `.gitignore`.
- مرآة الـCI للواجهة صارت بايت-ببايت مع نسخة مستودع الواجهة.
- بوابة بصمة المرشح اتصلّحت (كانت هتفشل على فرع الـCI نفسه).

## 7) المتبقي (بترتيب الأولوية)

1. الـCI على GitHub Actions لسه مش شغّال فعلياً: التوكن بلا صلاحية `workflow` ⇒
   فرع الـCI فيه نسخة main من `.github/workflows/ci.yml` ⇒ اللي بيتنفّذ مش
   البوابات الحقيقية. الحل: توكن بصلاحية workflow.
2. نشر الإنتاج (octashares.com): محتاج `project_id` أو توكن account-level.
3. EGX Live: المفتاح الناقص الوحيد (`/api/obdepth` ⇒ `no_key`).
4. `main` في الواجهة فيه `data_full.json` ملوّث (13 سهماً فيها U+FFFD في
   `sectorAr`). المرشح نظيف، بس أي نشر من main هيطلع بنص تالف.
5. سجل الاعتماد 144: أداة بنائه مفقودة والمصدر (xlsx) غير موجود ⇒ محتاج إعادة بناء.
6. لوحة الإدارة: بعد أي نشر، التأكد من بقاء الأسرار الثلاثة
   (`GET /workers/scripts/octa-mgmt/settings`).

## 8) قواعد ثابتة (لا تخالفها)

- لا دمج في main · لا نشر على octashares.com · لا موارد مدفوعة · لا بيانات عملاء حقيقية.
- لا تغيّر أوزان المحرك أو حدود القبول (المحرك والحد 90% ثابتان).
- لا تُعتبر 401/403/404/501 نجاحاً وظيفياً. المتخطى ليس نجاحاً.
- كل رقم في أي تقرير لازم يكون traced لمصدر. المتعذر = صفر نقاط.
- الأسرار ما تظهرش في الشات ولا في الملفات ولا في التقارير ولا في الحزم.
- ملفات العربية: `python3 tools/check_arabic_output.py <file>` ⇒ لازم RESULT: CLEAN.
- ممنوع `...` (ثلاث نقاط ASCII) خارج التعليقات في كود المشروع.
- محارف FFFD / CJK / Hangul / Cyrillic ممنوعة في الملفات العربية.
- كل استبدال نصي: assert على عدد التطابقات + repr + سطر كامل.
- الكتابة بالعربي: ملف أو أداة، مش heredoc.
- الرد: أول سطر = الإجابة · آخر سطر = طلب واحد واضح من المالك · جمل قصيرة ·
  بلا جداول طويلة.

## 9) حالة الفروع في هذه البيئة

`.wt_r26_be` (الباك · المرشح) · `.wt_r26_ci` (الباك · فرع الـCI) ·
`.wt_r26_fe` (الواجهة · المرشح) · `.wt_r27_fe_ci` (الواجهة · فرع الـCI) ·
`.wt_r26_ev` (فرع الأدلة).

## 10) أول مهمة مقترحة للشات الجديد

البند 1 من المتبقي: تشغيل الـCI فعلياً على GitHub Actions. يحتاج توكن بصلاحية
`workflow` أو موافقة صريحة على نشر ملف الـworkflow الحقيقي على
`.github/workflows/ci.yml` قبل الدفع.
