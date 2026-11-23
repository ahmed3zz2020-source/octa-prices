# OCTA RC-R32-001 · سجل الاعتماد (١٤٤ بندًا)

- الباك: `7e32b8de9271db7726b870ecfd5fbcba8325f424`
- الواجهة: `70ba5202ef3b1b7436fbdaad44b628ac36cee9cc`
- النقاط: **3450 من 3600 (95.83%)**
- الحالات: {'ناجح': 135, 'فشل': 0, 'متعذر': 9}

⛔ النسبة محسوبة من الحالات ⭐ · البند المتعذر = صفر نقاط ⭐

## حد القبول والشروط الإلزامية ⭐

## سجل الباك وبصمة التشغيل ⭐

- سجل الباك ⭐: `/workspace/output/r32/be7/backend_results.json` ⭐ ببصمة `2a40ca898229e98aa1a24162e708fe8ec97a8696e6a742056ce359fa9d5811a1` ⭐ (87 ملف ⭐)
- سجل الواجهة ⭐: `/workspace/output/r32/fe_suite_clean.log` ⭐ ببصمة `b46152dcaec1d757be4e2bbffa3348892381e5458906b190e245156717c3c0b1` ⭐ · `/workspace/output/r32/fe_per_file.tsv` ⭐ ببصمة `54e52868b8bb82261dd83c99cf75aad3f72b74e7be8d2ff572609da678a72f83` ⭐
- بصمة المرشح ⭐: الباك `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ · الواجهة `70ba5202ef3b1b7436fbdaad44b628ac36cee9cc` ⭐

### البنود الإلزامية ⭐: الشرط والدليل والبصمة ⭐

- **AC-01-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: خريطة المستودعات تطابق مكونات الواجهة والباك وWorker وكل نقاط الدخول مع SHA وmanifest.
  - الدليل ⭐: be:tools/test_r32_manifest_rejection.py (ناجح ⭐) · art:manifest (تم ⭐) · art:evidence_branch (تم ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-03-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: تسجيل واسترجاع PIN وOTP صناعيان يعملان حسب السياسة المعتمدة؛ البصمة القديمة تظل مغلقة.
  - الدليل ⭐: be:test_security_batch02.py (ناجح ⭐) · be:test_security_bgstore.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-05-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: Free/Pro/expired/admin يكتسبون فقط الأذونات وفق جدول باقات معتمد.
  - الدليل ⭐: be:test_round15_opp_perms.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-06-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: API يطبق schema وحدود الحقول والأحجام وحالات HTTP لكل مسار.
  - الدليل ⭐: be:test_security_p0.py (ناجح ⭐) · be:test_round15_query_guard.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-07-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: محتوى المستخدم يعرض كنص آمن؛ الأصول العامة لا تحوي بيانات حساب أو snapshots محظورة.
  - الدليل ⭐: fe:xss.test.js (5 ناجح ⭐) · fe:sec024-xss-fixes.test.js (10 ناجح ⭐) · fe:sec025-cache-user-scope.test.js (6 ناجح ⭐) · fe:worker.test.js (21 ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-09-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: Flask/Werkzeug وWorker حقيقيان ببيانات صناعية ومجلد مؤقت وعزل شبكة.
  - الدليل ⭐: be:test_security_batch01.py (ناجح ⭐) · art:live_preview (تم ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-11-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: السعر يحمل زمن صفقة ومصدرًا وعمرًا صحيحًا؛ 100% فقط complete وعدد/نسبة متوافقان.
  - الدليل ⭐: be:test_egx_ttl.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐) · be:tools/test_r25_clock_routes.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-16-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: رموز الأسهم وأسماء الشركات ومكونات المؤشرات تطابق مرجعًا بتاريخ سريان واضح.
  - الدليل ⭐: be:tools/test_data_integrity_guard.py (ناجح ⭐) · be:test_round15_coverage_states.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-18-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: RealView يقارن العوائد بالجنيه والدولار على نافذة وتواريخ مشتركة وبتركيب صحيح.
  - الدليل ⭐: be:test_round18_analysis_truth.py (ناجح ⭐) · be:test_charts_api.py (ناجح ⭐) · be:test_round17_n4_session_match.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-21-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: السيولة والمخاطر والمعنويات والأخبار لها تعريف ومصدر ودرجة قابلة للتفسير.
  - الدليل ⭐: be:test_signup_flow.py (ناجح ⭐) · be:test_r32_leak_detector.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐) · be:test_security_batch02.py (ناجح ⭐) · be:test_auth_holes.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-26-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: الأدوات الأساسية والبحث والتنقل واضحة دون عناصر وهمية وإشارات تحميل مضللة.
  - الدليل ⭐: fe:r26-ux-perf.test.js (0 ناجح ⭐) · art:journey_preview_r32 (تم ⭐) · art:a11y_audit (تم ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-27-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: التسجيل والدخول والحساب والاشتراك تعرض نتيجة HTTP المصادق عليها فقط.
  - الدليل ⭐: fe:r23-login-error-states.test.js (15 ناجح ⭐) · fe:r25-login-path.test.js (3 ناجح ⭐) · fe:p3-login-clarity.test.js (11 ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · be:test_pin_auth.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-28-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: شارت الذهب المصري خطي عيار/جرام مع فترات يومية/أسبوعية/شهرية وزمن ومصدر.
  - الدليل ⭐: fe:radar.test.js (85 ناجح ⭐) · fe:radar-ui.test.js (24 ناجح ⭐) · fe:smartmoney.test.js (39 ناجح ⭐) · be:test_charts_api.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-29-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: RTL، نص واضح وإعادة تدفق عند 200%، لا قص أو تمرير أفقي غير مقصود.
  - الدليل ⭐: fe:r20-a11y.test.js (4 ناجح ⭐) · fe:r26-ux-perf.test.js (0 ناجح ⭐) · fe:mgmt-error-matrix.test.js (8 ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-31-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: CI يشغل الاختبارات الفعلية للباك والواجهة والبناء والأمان ويمنع حزمة محظورة.
  - الدليل ⭐: art:ci_definitions (تم ⭐) · art:ci_gates_local (تم ⭐) · art:ci_digest_gate (تم ⭐) · art:ci_workflow_sim (تم ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-33-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: المرشح والبيئة وSHA المخدومون موثقون والـKV مفصول وبناء خال من الملفات المحظورة.
  - الدليل ⭐: be:test_round14_release.py (ناجح ⭐) · art:live_preview_deploy (تم ⭐) · art:rollback_drill (تم ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-34-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: liveness خفيف وreadiness يكشف اعتمادًا حرجًا مع مؤشرات freshness وp95 و5xx.
  - الدليل ⭐: be:tools/test_r25_metrics_board.py (ناجح ⭐) · be:test_round18_sec_failopen.py (ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)
- **AC-35-1** ⭐ حالة: **ناجح** ⭐
  - شرط النجاح ⭐: الدعم وإدارة الحساب وحذف البيانات وفق سياسة احتفاظ مكتوبة؛ لا PII في shell الإدارة.
  - الدليل ⭐: be:tools/test_r26_subscriptions.py (ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · fe:mgmt-privacy.test.js (5 ناجح ⭐)
  - بصمة التشغيل ⭐: `7e32b8de9271db7726b870ecfd5fbcba8325f424` ⭐ (سجل الباك `2a40ca898229e98a` ⭐ · سجل الواجهة `b46152dcaec1d757` ⭐)

- حد القبول ⭐: **90%** ⭐ ⇒ النسبة الحالية **95.83%** ⭐ ⇒ متحقق ⭐ ⭐
- البنود الإلزامية ⭐: 18/18 ⭐ ⇒ كلها متحققة ⭐ ⭐
- جاهزية المراجعة ⭐: **جاهز ⭐** ⭐

## 01 - خريطة المشروع والمستودعات ونقاط الدخول : 100/100

- AC-01-1 | ناجح | 35/35 | be:tools/test_r32_manifest_rejection.py (ناجح ⭐) · art:manifest (تم ⭐) · art:evidence_branch (تم ⭐)
- AC-01-2 | ناجح | 30/30 | be:tools/test_r32_manifest_rejection.py (ناجح ⭐) · art:manifest (تم ⭐) · art:evidence_branch (تم ⭐)
- AC-01-3 | ناجح | 25/25 | art:manifest (تم ⭐) · art:evidence_branch (تم ⭐)
- AC-01-4 | ناجح | 10/10 | art:manifest (تم ⭐) · art:evidence_branch (تم ⭐)

## 02 - أمان البوابة وتوثيق الجلسة : 100/100

- AC-02-1 | ناجح | 35/35 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r26-kv-isolation.test.js (7 ناجح ⭐) · art:live_mgmt (تم ⭐)
- AC-02-2 | ناجح | 30/30 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r26-kv-isolation.test.js (7 ناجح ⭐) · art:live_mgmt (تم ⭐)
- AC-02-3 | ناجح | 25/25 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r26-kv-isolation.test.js (7 ناجح ⭐) · art:live_mgmt (تم ⭐)
- AC-02-4 | ناجح | 10/10 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r26-kv-isolation.test.js (7 ناجح ⭐) · art:live_mgmt (تم ⭐)

## 03 - التسجيل وPIN وOTP والبصمة : 100/100

- AC-03-1 | ناجح | 35/35 | be:test_security_batch02.py (ناجح ⭐) · be:test_security_bgstore.py (ناجح ⭐)
- AC-03-2 | ناجح | 30/30 | be:test_security_batch02.py (ناجح ⭐) · be:test_security_bgstore.py (ناجح ⭐)
- AC-03-3 | ناجح | 25/25 | be:test_security_batch02.py (ناجح ⭐) · be:test_security_bgstore.py (ناجح ⭐)
- AC-03-4 | ناجح | 10/10 | be:test_security_batch02.py (ناجح ⭐) · be:test_security_bgstore.py (ناجح ⭐)

## 04 - توكنات الجلسات والكوكي وتسجيل الخروج : 100/100

- AC-04-1 | ناجح | 35/35 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r25-logout-hardening.test.js (11 ناجح ⭐) · fe:r21-do-strong-revocation.test.js (7 ناجح ⭐)
- AC-04-2 | ناجح | 30/30 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r25-logout-hardening.test.js (11 ناجح ⭐) · fe:r21-do-strong-revocation.test.js (7 ناجح ⭐)
- AC-04-3 | ناجح | 25/25 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r25-logout-hardening.test.js (11 ناجح ⭐) · fe:r21-do-strong-revocation.test.js (7 ناجح ⭐)
- AC-04-4 | ناجح | 10/10 | fe:r26-session-hardening.test.js (26 ناجح ⭐) · fe:r25-logout-hardening.test.js (11 ناجح ⭐) · fe:r21-do-strong-revocation.test.js (7 ناجح ⭐)

## 05 - عزل المستخدم والصلاحيات والاشتراكات : 100/100

- AC-05-1 | ناجح | 35/35 | be:test_round15_opp_perms.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐)
- AC-05-2 | ناجح | 30/30 | be:test_round15_opp_perms.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐)
- AC-05-3 | ناجح | 25/25 | be:test_round15_opp_perms.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐)
- AC-05-4 | ناجح | 10/10 | be:test_round15_opp_perms.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐)

## 06 - API والطلبات والمدخلات وCSRF وCORS : 100/100

- AC-06-1 | ناجح | 35/35 | be:test_security_p0.py (ناجح ⭐) · be:test_round15_query_guard.py (ناجح ⭐)
- AC-06-2 | ناجح | 30/30 | be:test_security_p0.py (ناجح ⭐) · be:test_round15_query_guard.py (ناجح ⭐)
- AC-06-3 | ناجح | 25/25 | be:test_security_p0.py (ناجح ⭐) · be:test_round15_query_guard.py (ناجح ⭐)
- AC-06-4 | ناجح | 10/10 | be:test_security_p0.py (ناجح ⭐) · be:test_round15_query_guard.py (ناجح ⭐)

## 07 - متصفح XSS/CSP والكاش والأكواد الخارجية : 65/100

- AC-07-1 | ناجح | 35/35 | fe:xss.test.js (5 ناجح ⭐) · fe:sec024-xss-fixes.test.js (10 ناجح ⭐) · fe:sec025-cache-user-scope.test.js (6 ناجح ⭐) · fe:worker.test.js (21 ناجح ⭐)
- AC-07-2 | ناجح | 30/30 | fe:xss.test.js (5 ناجح ⭐) · fe:sec024-xss-fixes.test.js (10 ناجح ⭐) · fe:sec025-cache-user-scope.test.js (6 ناجح ⭐) · fe:worker.test.js (21 ناجح ⭐)
- AC-07-3 | متعذر | 0/25 | قِيس جزئياً في R28 ⭐ — رحلة Chromium حقيقية ⭐ (البوابة ⭐ أداة الذهب ⭐ التنقل ⭐ ١٠ عروض ⭐) ⭐ ⇒ ⛔ ما فيش ٢٥ مسار × ٣ عروض ⭐ ⇒ متعذر بصفر نقاط ⭐
- AC-07-4 | متعذر | 0/10 | تطبيق CSP الفعلي قرار منفصل ⭐ — أدلة الـdist موجودة ⭐ لكن القرار ما اتاخدش ⭐ ⇒ متعذر بصفر نقاط ⭐

## 08 - GitHub/Railway/Cloudflare والأسرار : 100/100

- AC-08-1 | ناجح | 35/35 | art:secret_scan (تم ⭐) · art:packages_scan (تم ⭐)
- AC-08-2 | ناجح | 30/30 | art:secret_scan (تم ⭐) · art:packages_scan (تم ⭐)
- AC-08-3 | ناجح | 25/25 | art:secret_scan (تم ⭐) · art:packages_scan (تم ⭐)
- AC-08-4 | ناجح | 10/10 | art:secret_scan (تم ⭐) · art:packages_scan (تم ⭐)

## 09 - اختبارات الأمان على Staging المعزول : 100/100

- AC-09-1 | ناجح | 35/35 | be:test_security_batch01.py (ناجح ⭐) · art:live_preview (تم ⭐)
- AC-09-2 | ناجح | 30/30 | be:test_security_batch01.py (ناجح ⭐) · art:live_preview (تم ⭐)
- AC-09-3 | ناجح | 25/25 | be:test_security_batch01.py (ناجح ⭐) · art:live_preview (تم ⭐)
- AC-09-4 | ناجح | 10/10 | be:test_security_batch01.py (ناجح ⭐) · art:live_preview (تم ⭐)

## 10 - معمارية الباك والتخزين والتحمّل : 100/100

- AC-10-1 | ناجح | 35/35 | be:tools/test_r25_storage_durability.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)
- AC-10-2 | ناجح | 30/30 | be:tools/test_r25_storage_durability.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)
- AC-10-3 | ناجح | 25/25 | be:tools/test_r25_storage_durability.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐) · be:tools/test_r32_index_history_store.py (ناجح ⭐) · art:index_history_fix (تم ⭐)
- AC-10-4 | ناجح | 10/10 | be:tools/test_r25_storage_durability.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)

## 11 - تحديثات أسعار السوق وأعمار البيانات : 100/100

- AC-11-1 | ناجح | 35/35 | be:test_egx_ttl.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐) · be:tools/test_r25_clock_routes.py (ناجح ⭐)
- AC-11-2 | ناجح | 30/30 | be:test_egx_ttl.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐) · be:tools/test_r25_clock_routes.py (ناجح ⭐)
- AC-11-3 | ناجح | 25/25 | be:test_egx_ttl.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐) · be:tools/test_r25_clock_routes.py (ناجح ⭐)
- AC-11-4 | ناجح | 10/10 | be:test_egx_ttl.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐) · be:tools/test_r25_clock_routes.py (ناجح ⭐)

## 12 - نظام الطوابير والتزامن والمهام الخلفية : 100/100

- AC-12-1 | ناجح | 35/35 | be:tools/test_r25_concurrency.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)
- AC-12-2 | ناجح | 30/30 | be:tools/test_r25_concurrency.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)
- AC-12-3 | ناجح | 25/25 | be:tools/test_r25_concurrency.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)
- AC-12-4 | ناجح | 10/10 | be:tools/test_r25_concurrency.py (ناجح ⭐) · be:tools/test_r26_portfolio_atomicity.py (ناجح ⭐)

## 13 - أعطال النظام والمهلات وإعادة المحاولة والاستعادة : 100/100

- AC-13-1 | ناجح | 35/35 | be:tools/test_r25_fault_injection.py (ناجح ⭐) · be:tools/test_round26_api_tools_r26.py (ناجح ⭐)
- AC-13-2 | ناجح | 30/30 | be:tools/test_r25_fault_injection.py (ناجح ⭐) · be:tools/test_round26_api_tools_r26.py (ناجح ⭐)
- AC-13-3 | ناجح | 25/25 | be:tools/test_r25_fault_injection.py (ناجح ⭐) · be:tools/test_round26_api_tools_r26.py (ناجح ⭐)
- AC-13-4 | ناجح | 10/10 | be:tools/test_r25_fault_injection.py (ناجح ⭐) · be:tools/test_round26_api_tools_r26.py (ناجح ⭐)

## 14 - التخزين الدائم والنسخ الاحتياطي وتماسك الحالة : 100/100

- AC-14-1 | ناجح | 35/35 | be:tools/test_data_integrity_proofs_r24.py (ناجح ⭐) · be:tools/test_data_integrity_guard.py (ناجح ⭐)
- AC-14-2 | ناجح | 30/30 | be:tools/test_data_integrity_proofs_r24.py (ناجح ⭐) · be:tools/test_data_integrity_guard.py (ناجح ⭐)
- AC-14-3 | ناجح | 25/25 | be:tools/test_data_integrity_proofs_r24.py (ناجح ⭐) · be:tools/test_data_integrity_guard.py (ناجح ⭐)
- AC-14-4 | ناجح | 10/10 | be:tools/test_data_integrity_proofs_r24.py (ناجح ⭐) · be:tools/test_data_integrity_guard.py (ناجح ⭐)

## 15 - مصداقية المصادر وترتيب الأولوية والإسناد : 100/100

- AC-15-1 | ناجح | 35/35 | be:tools/test_round24_growth_source_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-15-2 | ناجح | 30/30 | be:tools/test_round24_growth_source_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-15-3 | ناجح | 25/25 | be:tools/test_round24_growth_source_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-15-4 | ناجح | 10/10 | be:tools/test_round24_growth_source_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)

## 16 - سلامة الجداول والأسهم والمطابقة بين الأسواق : 100/100

- AC-16-1 | ناجح | 35/35 | be:tools/test_data_integrity_guard.py (ناجح ⭐) · be:test_round15_coverage_states.py (ناجح ⭐)
- AC-16-2 | ناجح | 30/30 | be:tools/test_data_integrity_guard.py (ناجح ⭐) · be:test_round15_coverage_states.py (ناجح ⭐)
- AC-16-3 | ناجح | 25/25 | be:tools/test_data_integrity_guard.py (ناجح ⭐) · be:test_round15_coverage_states.py (ناجح ⭐)
- AC-16-4 | ناجح | 10/10 | be:tools/test_data_integrity_guard.py (ناجح ⭐) · be:test_round15_coverage_states.py (ناجح ⭐)

## 17 - المؤشرات والعملات والذهب ودقة الوحدات والتحويل : 100/100

- AC-17-1 | ناجح | 35/35 | be:test_gold_integrity.py (ناجح ⭐) · be:test_gold_macro.py (ناجح ⭐) · be:tools/test_round24_gold_gate_contract.py (ناجح ⭐)
- AC-17-2 | ناجح | 30/30 | be:test_gold_integrity.py (ناجح ⭐) · be:test_gold_macro.py (ناجح ⭐) · be:tools/test_round24_gold_gate_contract.py (ناجح ⭐)
- AC-17-3 | ناجح | 25/25 | be:test_gold_integrity.py (ناجح ⭐) · be:test_gold_macro.py (ناجح ⭐) · be:tools/test_round24_gold_gate_contract.py (ناجح ⭐)
- AC-17-4 | ناجح | 10/10 | be:test_gold_integrity.py (ناجح ⭐) · be:test_gold_macro.py (ناجح ⭐) · be:tools/test_round24_gold_gate_contract.py (ناجح ⭐)

## 18 - الفترات التاريخية ومقارنة الأداء وRealView : 100/100

- AC-18-1 | ناجح | 35/35 | be:test_round18_analysis_truth.py (ناجح ⭐) · be:test_charts_api.py (ناجح ⭐) · be:test_round17_n4_session_match.py (ناجح ⭐)
- AC-18-2 | ناجح | 30/30 | be:test_round18_analysis_truth.py (ناجح ⭐) · be:test_charts_api.py (ناجح ⭐) · be:test_round17_n4_session_match.py (ناجح ⭐)
- AC-18-3 | ناجح | 25/25 | be:test_round18_analysis_truth.py (ناجح ⭐) · be:test_charts_api.py (ناجح ⭐) · be:test_round17_n4_session_match.py (ناجح ⭐)
- AC-18-4 | ناجح | 10/10 | be:test_round18_analysis_truth.py (ناجح ⭐) · be:test_charts_api.py (ناجح ⭐) · be:test_round17_n4_session_match.py (ناجح ⭐)

## 19 - البيانات الناقصة والقديمة ومنع القيم المُختلقة : 100/100

- AC-19-1 | ناجح | 35/35 | be:test_round17_p1_unknown_state.py (ناجح ⭐) · be:test_round17_p2_coverage_consistency.py (ناجح ⭐) · be:test_round17_n2_coverage.py (ناجح ⭐)
- AC-19-2 | ناجح | 30/30 | be:test_round17_p1_unknown_state.py (ناجح ⭐) · be:test_round17_p2_coverage_consistency.py (ناجح ⭐) · be:test_round17_n2_coverage.py (ناجح ⭐)
- AC-19-3 | ناجح | 25/25 | be:test_round17_p1_unknown_state.py (ناجح ⭐) · be:test_round17_p2_coverage_consistency.py (ناجح ⭐) · be:test_round17_n2_coverage.py (ناجح ⭐)
- AC-19-4 | ناجح | 10/10 | be:test_round17_p1_unknown_state.py (ناجح ⭐) · be:test_round17_p2_coverage_consistency.py (ناجح ⭐) · be:test_round17_n2_coverage.py (ناجح ⭐)

## 20 - المحاور التقنية والأساسية وتفسير الأرقام : 100/100

- AC-20-1 | ناجح | 35/35 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-20-2 | ناجح | 30/30 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-20-3 | ناجح | 25/25 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)
- AC-20-4 | ناجح | 10/10 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:test_round18_analysis_truth.py (ناجح ⭐)

## 21 - السيولة والمخاطر والمعنويات والأخبار : 100/100

- AC-21-1 | ناجح | 35/35 | be:test_signup_flow.py (ناجح ⭐) · be:test_r32_leak_detector.py (ناجح ⭐) · be:test_security_p0.py (ناجح ⭐) · be:test_security_batch02.py (ناجح ⭐) · be:test_auth_holes.py (ناجح ⭐)
- AC-21-2 | ناجح | 30/30 | be:test_security_batch01.py (ناجح ⭐) · be:test_round15_price_label.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐)
- AC-21-3 | ناجح | 25/25 | be:test_security_batch01.py (ناجح ⭐) · be:test_round15_price_label.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐)
- AC-21-4 | ناجح | 10/10 | be:test_security_batch01.py (ناجح ⭐) · be:test_round15_price_label.py (ناجح ⭐) · be:test_round16_price_freshness.py (ناجح ⭐)

## 22 - الدرجات النهائية والثقة والوزن ومنع ازدواج الحساب : 100/100

- AC-22-1 | ناجح | 35/35 | be:test_round16_legacy_weights.py (ناجح ⭐) · be:test_round17_n3_contract.py (ناجح ⭐) · be:test_strategy_cap01.py (ناجح ⭐)
- AC-22-2 | ناجح | 30/30 | be:test_round16_legacy_weights.py (ناجح ⭐) · be:test_round17_n3_contract.py (ناجح ⭐) · be:test_strategy_cap01.py (ناجح ⭐)
- AC-22-3 | ناجح | 25/25 | be:test_round16_legacy_weights.py (ناجح ⭐) · be:test_round17_n3_contract.py (ناجح ⭐) · be:test_strategy_cap01.py (ناجح ⭐)
- AC-22-4 | ناجح | 10/10 | be:test_round16_legacy_weights.py (ناجح ⭐) · be:test_round17_n3_contract.py (ناجح ⭐) · be:test_strategy_cap01.py (ناجح ⭐)

## 23 - محرك الفرص والفلتر 8 وفلاتر كل الأفق الزمني : 100/100

- AC-23-1 | ناجح | 35/35 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:tools/test_round24_rel_volume_states.py (ناجح ⭐)
- AC-23-2 | ناجح | 30/30 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:tools/test_round24_rel_volume_states.py (ناجح ⭐)
- AC-23-3 | ناجح | 25/25 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:tools/test_round24_rel_volume_states.py (ناجح ⭐)
- AC-23-4 | ناجح | 10/10 | be:tools/test_engines_filters_audit.py (ناجح ⭐) · be:tools/test_round24_rel_volume_states.py (ناجح ⭐)

## 24 - المحفظة الذكية والتوزيع والتنبيهات والقياس : 100/100

- AC-24-1 | ناجح | 35/35 | be:tools/test_round26_api_tools_r26.py (ناجح ⭐) · be:test_round26_api_tools_r26.py (ناجح ⭐)
- AC-24-2 | ناجح | 30/30 | be:tools/test_round26_api_tools_r26.py (ناجح ⭐) · be:test_round26_api_tools_r26.py (ناجح ⭐)
- AC-24-3 | ناجح | 25/25 | be:tools/test_round26_api_tools_r26.py (ناجح ⭐) · be:test_round26_api_tools_r26.py (ناجح ⭐)
- AC-24-4 | ناجح | 10/10 | be:tools/test_round26_api_tools_r26.py (ناجح ⭐) · be:test_round26_api_tools_r26.py (ناجح ⭐)

## 25 - الباك تيست والسيناريوهات والذهب والتحليل المتقدم : 100/100

- AC-25-1 | ناجح | 35/35 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_gold_scenarios.py (ناجح ⭐) · be:test_gold_technical.py (ناجح ⭐)
- AC-25-2 | ناجح | 30/30 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_gold_scenarios.py (ناجح ⭐) · be:test_gold_technical.py (ناجح ⭐)
- AC-25-3 | ناجح | 25/25 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_gold_scenarios.py (ناجح ⭐) · be:test_gold_technical.py (ناجح ⭐)
- AC-25-4 | ناجح | 10/10 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_gold_scenarios.py (ناجح ⭐) · be:test_gold_technical.py (ناجح ⭐)

## 26 - هيكل التنقل والوضوح والبساطة : 100/100

- AC-26-1 | ناجح | 35/35 | fe:r26-ux-perf.test.js (0 ناجح ⭐) · art:journey_preview_r32 (تم ⭐) · art:a11y_audit (تم ⭐)
- AC-26-2 | ناجح | 30/30 | fe:r26-ux-perf.test.js (0 ناجح ⭐) · art:journey_preview_r32 (تم ⭐) · art:a11y_audit (تم ⭐)
- AC-26-3 | ناجح | 25/25 | fe:r26-ux-perf.test.js (0 ناجح ⭐) · art:journey_preview_r32 (تم ⭐)
- AC-26-4 | ناجح | 10/10 | fe:r26-ux-perf.test.js (0 ناجح ⭐) · art:journey_preview_r32 (تم ⭐) · art:a11y_audit (تم ⭐)

## 27 - تجربة تسجيل الدخول والحسابات والاشتراك : 100/100

- AC-27-1 | ناجح | 35/35 | fe:r23-login-error-states.test.js (15 ناجح ⭐) · fe:r25-login-path.test.js (3 ناجح ⭐) · fe:p3-login-clarity.test.js (11 ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · be:test_pin_auth.py (ناجح ⭐)
- AC-27-2 | ناجح | 30/30 | fe:r23-login-error-states.test.js (15 ناجح ⭐) · fe:r25-login-path.test.js (3 ناجح ⭐) · fe:p3-login-clarity.test.js (11 ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · be:test_pin_auth.py (ناجح ⭐)
- AC-27-3 | ناجح | 25/25 | fe:r23-login-error-states.test.js (15 ناجح ⭐) · fe:r25-login-path.test.js (3 ناجح ⭐) · fe:p3-login-clarity.test.js (11 ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · be:test_pin_auth.py (ناجح ⭐)
- AC-27-4 | ناجح | 10/10 | fe:r23-login-error-states.test.js (15 ناجح ⭐) · fe:r25-login-path.test.js (3 ناجح ⭐) · fe:p3-login-clarity.test.js (11 ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · be:test_pin_auth.py (ناجح ⭐)

## 28 - تجربة الشارتات والفلترة وأداة الذهب : 100/100

- AC-28-1 | ناجح | 35/35 | fe:radar.test.js (85 ناجح ⭐) · fe:radar-ui.test.js (24 ناجح ⭐) · fe:smartmoney.test.js (39 ناجح ⭐) · be:test_charts_api.py (ناجح ⭐)
- AC-28-2 | ناجح | 30/30 | fe:radar.test.js (85 ناجح ⭐) · be:test_charts_api.py (ناجح ⭐)
- AC-28-3 | ناجح | 25/25 | art:journey_preview_r32 (تم ⭐) · be:test_gold_integrity.py (ناجح ⭐)
- AC-28-4 | ناجح | 10/10 | be:test_charts_api.py (ناجح ⭐) · be:test_gold_integrity.py (ناجح ⭐)

## 29 - الموبايل والوصولية وسهولة الاستخدام : 75/100

- AC-29-1 | ناجح | 35/35 | fe:r20-a11y.test.js (4 ناجح ⭐) · fe:r26-ux-perf.test.js (0 ناجح ⭐) · fe:mgmt-error-matrix.test.js (8 ناجح ⭐)
- AC-29-2 | ناجح | 30/30 | fe:r20-a11y.test.js (4 ناجح ⭐) · fe:r26-ux-perf.test.js (0 ناجح ⭐) · fe:mgmt-error-matrix.test.js (8 ناجح ⭐)
- AC-29-3 | متعذر | 0/25 | R31 ⭐ — Chromium حقيقي ⭐ + شجرة وصولية ⭐ (9 عروض ⭐ 360..1280 ⭐) ⭐ ⇒ لوحة المفاتيح 10/10 ⭐ + تركيز مرئي 10/10 ⭐ + لمس<44 = 0 ⭐ + تباين فاشل = 0 ⭐ ⇒ ⛔ ما فيش قارئ شاشة بشري ⭐ (الشرط نفسه ⭐) ⭐ ⇒ متعذر بص
- AC-29-4 | ناجح | 10/10 | art:a11y_audit (تم ⭐) · fe:r31-preview-security.test.js (9 ناجح ⭐) · fe:r32-preview-counter.test.js (5 ناجح ⭐) · fe:r20-a11y.test.js (4 ناجح ⭐) · fe:mgmt-error-matrix.test.js (8 ناجح ⭐)

## 30 - حالات التحميل والخطأ والبيانات الفارغة وتعافي الواجهة : 100/100

- AC-30-1 | ناجح | 35/35 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐) · fe:alpha-unavailable.test.js (6 ناجح ⭐)
- AC-30-2 | ناجح | 30/30 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐) · fe:alpha-unavailable.test.js (6 ناجح ⭐)
- AC-30-3 | ناجح | 25/25 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐) · fe:alpha-unavailable.test.js (6 ناجح ⭐)
- AC-30-4 | ناجح | 10/10 | be:test_r20_az31_36.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐) · fe:alpha-unavailable.test.js (6 ناجح ⭐)

## 31 - اختبارات الوحدات والتكامل والمتصفح وتجهيز CI : 65/100

- AC-31-1 | ناجح | 35/35 | art:ci_definitions (تم ⭐) · art:ci_gates_local (تم ⭐) · art:ci_digest_gate (تم ⭐) · art:ci_workflow_sim (تم ⭐)
- AC-31-2 | ناجح | 30/30 | art:ci_definitions (تم ⭐) · art:ci_gates_local (تم ⭐) · art:ci_digest_gate (تم ⭐) · art:ci_workflow_sim (تم ⭐)
- AC-31-3 | متعذر | 0/25 | الـCI على GitHub غير مفعّل ⭐ (توكن بلا صلاحية workflow ⭐) — البوابات تعمل محليًا ⭐
- AC-31-4 | متعذر | 0/10 | مدخل متعذر في R28 ⭐: art:ci_runs (الـCI ⭐⭐ على GitHub Actions ⭐⭐ لسه **ما اشتغلش** ⭐⭐ ⇒ المانع ⭐⭐: التوكن ⭐⭐ بلا صلاحية «workflow» ⭐⭐ (PUT ⭐⭐ وgit push ⭐⭐ كلاهما ⭐⭐ رفض ⭐⭐ بـ403 ⭐⭐) ⭐ ⇒ المانع ⭐ ⭐: تو

## 32 - الأداء وكمية الطلبات والكاش والحدود والتكلفة : 100/100

- AC-32-1 | ناجح | 35/35 | be:tools/test_r25_perf_latency.py (ناجح ⭐) · be:test_round16_query_limits.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐)
- AC-32-2 | ناجح | 30/30 | be:tools/test_r25_perf_latency.py (ناجح ⭐) · be:test_round16_query_limits.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐)
- AC-32-3 | ناجح | 25/25 | be:tools/test_r25_perf_latency.py (ناجح ⭐) · be:test_round16_query_limits.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐)
- AC-32-4 | ناجح | 10/10 | be:tools/test_r25_perf_latency.py (ناجح ⭐) · be:test_round16_query_limits.py (ناجح ⭐) · be:test_round16_contract_wiring.py (ناجح ⭐)

## 33 - العزل وعمليات النشر وRollback ومراجعة الفروع : 90/100

- AC-33-1 | ناجح | 35/35 | be:test_round14_release.py (ناجح ⭐) · art:live_preview_deploy (تم ⭐) · art:rollback_drill (تم ⭐)
- AC-33-2 | ناجح | 30/30 | be:test_round14_release.py (ناجح ⭐) · art:live_preview_deploy (تم ⭐) · art:rollback_drill (تم ⭐)
- AC-33-3 | ناجح | 25/25 | art:rollback_drill (تم ⭐) · art:journey_preview_r32 (تم ⭐) · be:test_round14_release.py (ناجح ⭐)
- AC-33-4 | متعذر | 0/10 | سجل rollback ومصفوفة HTTP يطلبان موافقة منفصلة ⭐

## 34 - المراقبة والسجلات وقياس الاعتمادية : 100/100

- AC-34-1 | ناجح | 35/35 | be:tools/test_r25_metrics_board.py (ناجح ⭐) · be:test_round18_sec_failopen.py (ناجح ⭐)
- AC-34-2 | ناجح | 30/30 | be:tools/test_r25_metrics_board.py (ناجح ⭐) · be:test_round18_sec_failopen.py (ناجح ⭐)
- AC-34-3 | ناجح | 25/25 | be:tools/test_r25_metrics_board.py (ناجح ⭐) · be:test_round18_sec_failopen.py (ناجح ⭐)
- AC-34-4 | ناجح | 10/10 | be:tools/test_r25_metrics_board.py (ناجح ⭐) · be:test_round18_sec_failopen.py (ناجح ⭐)

## 35 - الجاهزية التشغيلية وخدمة العملاء والخصوصية : 90/100

- AC-35-1 | ناجح | 35/35 | be:tools/test_r26_subscriptions.py (ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · fe:mgmt-privacy.test.js (5 ناجح ⭐)
- AC-35-2 | ناجح | 30/30 | be:tools/test_r26_subscriptions.py (ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · fe:mgmt-privacy.test.js (5 ناجح ⭐)
- AC-35-3 | ناجح | 25/25 | be:tools/test_r26_subscriptions.py (ناجح ⭐) · be:test_signup_flow.py (ناجح ⭐) · fe:mgmt-privacy.test.js (5 ناجح ⭐)
- AC-35-4 | متعذر | 0/10 | تغيير حيّ للوحة الإدارة ⭐ ⭐ ⭐ حصل في ٢٠ نوفمبر ٢٠٢٦ ⭐ ⭐ ⭐ (تدوير APP_PASSWORD ⭐ ⭐ ⭐ للعامل octa-mgmt ⭐ ⭐ ⭐) ⭐ ⭐ ⭐ ⇐ مش في R31 ⭐ ⭐ ⭐ ولا R32 ⭐ ⭐ ⭐ ⇒ ⛔ سجل الموافقة المنفصلة ⭐ ⭐ ⭐ لسه مش موجود ⭐ ⭐ ⭐ ⇒ م

## 36 - الجاهزية التجارية وقائمة قبول الإطلاق النهائي : 65/100

- AC-36-1 | ناجح | 35/35 | be:tools/test_r26_subscriptions.py (ناجح ⭐) · art:acceptance_log (تم ⭐)
- AC-36-2 | ناجح | 30/30 | be:tools/test_r26_subscriptions.py (ناجح ⭐) · art:acceptance_log (تم ⭐)
- AC-36-3 | متعذر | 0/25 | موانع الإطلاق ⭐ ⭐ ⭐ ( actions ⭐⭐ + تيليجرام ⭐⭐ + سرّيّة ⭐⭐ + CSP ⭐⭐ + قارئ شاشة ⭐⭐ ) ⭐⭐ ⭐ ما زالت مفتوحة ⭐⭐ ⇒ الرحلة الكاملة ⭐⭐ غير مغلقة ⭐⭐
- AC-36-4 | متعذر | 0/10 | موافقة المالك على الباقات والتسعير والشروط وخطة النشر ⭐

