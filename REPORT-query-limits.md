# 🛡️ الجولة ١٦ — حماية معاملات الطلب (حدود الـquery + رفض آمن)

📌 **الفرع**: `fix/round16-query-limits` · **الأساس**: `93b1988` (الجولة ١٥)
📌 **المعدّل**: `update_prices.py` · **الجديد**: `test_round16_query_limits.py`

---

## ① الخلاصة (سطرين)

قبل التعديل كان الـquery بيتقبل **بلا حدود حجم ولا عدد**، وكان فشل
«كتابة `request.query_string`» أو «إبطال كاش `request.args`» بيتبلع
سكات (`except: pass`) ⇒ الـroute يكمّل شايف **القيمة الخام**.
دلوقتي: **حدود تُفحص قبل أي parse** (رفض ٤٠٠ صريح + كود سبب)،
و**أي فشل في تطبيق التنظيف ⇒ رفض ٤٠٠ صريح** (fail-closed) — مافيش
قيمة خام واحدة بتعدّي.

---

## ② جدول الحدود

| # | الحد (الثابت) | القيمة | الموضع | السبب (ليه الحد ده) | الرد |
|---|---|---|---|---|---|
| ① | `QUERY_MAX_TOTAL_BYTES` | ١٦٣٨٤ بايت | `update_prices.py:887` | طول الـquery الكلي (DoS في التحليل) | ٤٠٠ · `why=query_too_long` |
| ② | `QUERY_MAX_PARAMS` | ٦٤ | `update_prices.py:888` | عدد المعاملات في الطلب | ٤٠٠ · `why=too_many_params` |
| ③ | `QUERY_MAX_NAME_CHARS` | ١٢٨ | `update_prices.py:889` | طول اسم المعاملة | ٤٠٠ · `why=param_name_too_long` |
| ④ | `QUERY_MAX_VALUE_CHARS` | ٨١٩٢ | `update_prices.py:890` | طول قيمة المعاملة الواحدة | ٤٠٠ · `why=param_value_too_long` |
| ⑤ | fail-closed (مفيش ثابت) | — | `update_prices.py:1022-1050` | فشل الكتابة **أو** فشل إبطال الكاش | ٤٠٠ · `why=query_sanitize_failed` |

📌 **ترتيب الفحص (الأسبقية)**: الطول الكلي ⇒ عدد المعاملات ⇒ طول الاسم ⇒
طول القيمة. كلهم **قبل** `parse_qsl` و**قبل** أي استخدام للقيمة.

📌 **ليه السقوف مش ٤٠٩٦ / ١٠٢٤؟** (انظر §⑦ — قيد صريح من الجولة ١٥)

---

## ③ المواضع (file:line)

| العنصر | الموضع | الوظيفة |
|---|---|---|
| ثوابت الحدود + أكواد الأسباب | `update_prices.py:874-907` | **مكان واحد** لكل حدود الـquery |
| `_query_raw_string()` | `update_prices.py:910-927` | يقرأ الـquery الخام (نص) من البيئة — من غير تحليل |
| `_query_limits_check()` | `update_prices.py:928-962` | ⛔ الفحص **قبل** أي parse ⇒ `(ok, why)` |
| `_build_clean_query()` | `update_prices.py:963-1003` | المعالج الأساسي (نفس قواعد الجولة ١٣/١٤/١٥) |
| `_strict_safe_query()` | `update_prices.py:1004-1021` | التنظيف الاحتياطي الصارم (الجولة ١٤) |
| `_apply_clean_query()` | `update_prices.py:1022-1050` | ⛔ الكتابة + إبطال الكاش — **أي فشل ⇒ False ⇒ رفض** |
| `_clear_request_query()` | `update_prices.py:1051-1071` | fail-closed: يفرّغ الـquery من الـrequest |
| `_reject_query()` | `update_prices.py:1072-1095` | ⛔ الرفض ٤٠٠ الصريح (رسالة ثابتة + كود سبب) |
| `_safe_log_text()` | `update_prices.py:1096-1106` | نص اللوج — بدون أي حرف من الـquery الخام |
| `_sanitize_request()` | `update_prices.py:1107-1158` | ⛔ الطبقة ⓪ (الحدود) ⇒ ① (أساسي) ⇒ ② (احتياطي) ⇒ ③ (رفض) |
| `hide_recipe()` | `update_prices.py:503-514` | ⚠️ تعديل لازم: يرجّع كود سبب الحارس للمستخدم |
| الاختبار الجديد | `test_round16_query_limits.py` | ١٧ اختبار (٢ ثوابت + ٦ عقد + ٧ رد نهائي + ٢ نظافة) |

---

## ④ الطبقات (fail-closed بالترتيب)

```
⓪ حدود الـquery (قبل أي parse)   ⇒ ٤٠٠ (query_too_long · too_many_params
                                    · param_name_too_long · param_value_too_long)
① التنظيف الأساسي + تطبيقه       ⇒ الـrequest شايف query نظيف
② تنظيف احتياطي صارم (لو ① وقع)  ⇒ query نظيف + سقف ٦٠ محرف
③ لو ① و② وقعوا                 ⇒ ٤٠٠ query_sanitize_failed (تفريغ الـquery)
```

⛔ **الأسبقية**: ⓪ بتتحقق قبل `parse_qsl` وقبل ما أي قيمة تُستخدم —
يعني **مفيش قيمة خام واحدة** بتمشي لحد الـroute في أي حالة فشل.

⚠️ **تعديل جانبي لازم**: `hide_recipe` بيشيل مفتاح `why` من كل رد JSON
(لأنه مفتاح مخرجات المحرك) ⇒ كان كود سبب الرفض **مش بيوصل** للمستخدم
(ده كان بيأثر كمان على `query_sanitize_failed` بتاع الجولة ١٥). اتحلّت
باسترجاع **أكواد الحارس بالاسم فقط** (`QUERY_WHY_CODES`) — شرط نص من
القائمة بالظبط ⇒ **مافيش أي مخرج محرك بيتسرب**.

---

## ⑤ الأرقام

### الاختبار الجديد — `test_round16_query_limits.py`
**١٧ / ١٧ ناجح** (٧ + ٦ + ٧ + ٢).

| الكلاس | العدد | وش بيCover |
|---|---|---|
| `TestQueryLimitConstants` | ٢ | الثوابت في مكان واحد + قيمها سليمة |
| `TestQueryLimitContract` | ٦ | الرفض على مستوى الـsanitizer (قبل أي parse) |
| `TestQueryLimitEndToEnd` | ٧ | الرد النهائي على **مسار حقيقي** + إثبات إن الـroute ما شغّاش |
| `TestFileHygiene` | ٢ | قاعدة الـCI (ثلاث نقاط) + سلامة النص العربي |

### Negative proof (على الكود القديم `93b1988`)
شغّلنا الاختبار الجديد على الأساس (git stash) ⇒ **١٣ / ١٧ فاشل**
(الـ٤ الباقية هي اختبارات «السلوك الطبيعي» + «نظافة الملف» اللي ما
بتتأثرش بالتغيير). الـ١٣ الفاشل = كل اختبارات السلوك الجديد.

قياس إضافي على الأساس (٢٠٠ ⇒ رد فيه القيمة الخام):
* ٥٠٠ معاملة ⇒ **٢٠٠** والعلامة `R16-RAW-MARKER` **في الرد** (١١٩٠١ بايت).
* اسم ١٠٠٠ محرف ⇒ **٢٠٠** والعلامة **في الرد**.
* فشل كتابة `request.query_string` ⇒ **٢٠٠** ورد فيه
  `{"filters":{"sector":"<script>alert(1)</script>"}}`.

### الانحدار (بعد التعديل)
| الملف | قبل | بعد |
|---|---|---|
| `test_round15_query_guard.py` | ١٧/١٧ | **١٧/١٧** ✅ |
| `test_code_hygiene.py` | ٦/٦ | **٦/٦** ✅ |
| `test_round14_release.py` | ٢٧/٢٧ | **٢٧/٢٧** ✅ |
| `test_security_batch02.py` | ٦١/٦٢ | **٦١/٦٢** (فشل واحد **سبقه** التعديل) |
| `test_round16_query_limits.py` | — | **١٧/١٧** ✅ |

⚠️ **الفشل الواحد** في `test_security_batch02.py` سببه إن
`STAGE_ADMIN_TOKEN` **مش متظبطلوش** في البيئة (`test_security_batch02.py:381`
⇒ `ok(False, "STAGE_ADMIN_TOKEN مش متظبطلوش ⇒ تعذّر فحص جلسة الأدمن")`).
عيب بيئي **مش متعلق** بالتعديل — نفس النتيجة قبله وبعده بالظبط.

⚠️ **ملاحظة أمانة عن تذبذب الأرقام**: `test_security_batch02.py` اختبار
**تكامل حيّ** (بيطلب `http://127.0.0.1:8099` — سيرفر staging؛ الـconfig
من `/workspace/.staging/staging-config.json`) ⇒ نتايجه بتتذبذب مع حالة
السيرفر: شفنا ٦١/١ (المستقر) و٤٤/١٧ و٥٦/٦ في لحظات السيرفر كان واقع
أو بيتبدّل. **المقارنة الآمنة** (نفس اللحظة): شغّلناه على الأساس
`93b1988` (بـ`git checkout 93b1988 -- update_prices.py`) ⇒ **٦١/١**،
وعلى الكود الجديد ⇒ **٦١/١**. ⇒ الفارق صفر.

### مسح شامل لكل ملفات الاختبار (base vs new)
شغّلنا **كل** ملفات `test_*.py` (٣٩ ملف) على الأساس وعلى الكود الجديد
⇒ الفرق **ملف واحد بس**: `test_round16_query_limits.py`
(FAILED على الأساس ⇒ OK على الجديد). كل الملفات التانية: **نفس النتيجة
حرفياً** — منها `test_security_p0.py` (٣٠/٣) و`test_security_batch02.py`
(٦١/١) في الحالتين ⇒ أي عيوب موجودة **سبقت** التعديل وما اتغيّرتش.

---

## ⑥ سياق الاستغلال (بدقة — ⛔ مش «XSS»)

⛔ **الوصف الصحيح**: **انعكاس نص داخل JSON** (content-type
`application/json`) ⇒ **مش تنفيذ HTML في المتصفح**.
مافيش أي مسار في `update_prices.py` بيرجّع `text/html` ولا فيه
`render_template`؛ الـbackend بيرجّع JSON فقط (+ بايتات صور على
`/api/tvlogo/<logoid>` و`/logos/<fn>`). صفحة الواجهة HTML بيقدّمها
الـWorker/proxy مش التطبيق ده.

**قبل الإصلاح** (`93b1988`) — الفشل في الكتابة/إبطال الكاش كان
مبتلوع صامت (`except: pass` حوالين `request.query_string = ...` و
`request.__dict__.pop("args", None)`) ⇒:

```
GET /api/rank?sector=<script>alert(1)</script>
⇒ 200 · content-type: application/json
   {"count":0,"filters":{"sector":"<script>alert(1)</script>"},"results":[]}
```

* **المسار**: `update_prices.py` → `_sanitize_request` (الكتابة/إبطال
  الكاش) ⇒ ثم route `/api/rank` اللي بيعكس `request.args` في `filters`.
* **النوع**: انعكاس **نص** جوه JSON. المتصفح بيحمّل الرد كـJSON
  (مش HTML) والرد كمان عليه `X-Content-Type-Options: nosniff` ⇒
  **مافيش تنفيذ HTML**. الأثر الحقيقي كان: **مدخل غير متحقق منه
  بيوصل للـroute وبيرجع للمستخدم** (تلويث رد / تلاعب بمنطق الـroute).

**بعد الإصلاح**: نفس السيناريو ⇒ **٤٠٠** · `application/json` ·
`{"ok": false, "error": "…", "why": "query_sanitize_failed"}` —
**مافيش** أي جزء من الـquery الخام، والـroute **ما شغّاش** (مُثبَت
بـprobe route في الاختبار).

---

## ⑦ ليه السقوف أعلى من المقترح (4096 / 1024) — قيد صريح من الجولة ١٥

📌 عقد الجولة ١٥ (`test_round15_query_guard.py`) بيقول إن قيمة
**٥٠٠٠ محرف لازم تترد (200) وتتقصّ** لحد ٣٠٠ — **مش ترفض**
(`test_long_value_is_truncated_in_response` و
`test_final_json_is_the_artifact_under_test`).
⇒ أي سقف قيمة ≤ ٥٠٠٠ (ومنه ١٠٢٤) **يكسر** اختبارين من الـ١٧
المنتفضين (ممنوع حسب تكليف الجولة: «ممنوع تكسر ١٧/١٧»).

⇒ السقوف اتاخدت **فوق** أطول حالة في عقد الجولة ١٥:
* القيمة: ٨١٩٢ (> ٥٠٠٠) — والسقف الفعلي اللي بيوصل للـroute لسه ٣٠٠
  (`clean_text`).
* الـquery الكلي: ١٦٣٨٤ (> ٥٠٠٥ بايت — طول `note=` + ٥٠٠٠ محرف).
* عدد المعاملات ٦٤ والاسم ١٢٨: **مافيش تعارض** مع أي اختبار قائم.

⛔ **النقطة المهمة**: السقوف دي **حماية DoS قبل التحليل** (حدود حجم
وعدد)، مش بديل عن التنظيف — التنظيف (تقصير ٣٠٠ + إزالة `<`/`>`)
لسه شغّال زي ما هو.

---

## ⑧ ملاحظات إضافية

* ⚠️ `_apply_clean_query` بقى **كله أو ولا حاجة**: فشل أي خطوة (كتابة
  `environ` / كتابة `request.query_string` / إبطال كاش `args`+`url`)
  ⇒ **رفض ٤٠٠**، مش إكمال في حالة ملتبسة. ده كان **أخطر** جزء في
  المراجعة: الكود القديم كان بيكمل بـ٢٠٠ بالقيمة الخام.
* ⛔ `_safe_log_text`: نص الخطأ في اللوج بيتنضّف (ASCII بس) ⇒
  مافيش جزء من الـquery الخام في اللوج. (رمز الفشل في الاختبار
  `R15-SIMULATED-FAILURE` بيفضل ظاهر ⇒ مافيش بلع صامت.)
* 📌 `_reject_query` بيردّ برسالة **ثابتة** + كود السبب بس ⇒
  مافيش سبب تسرّب من الـquery في الرد.

---

## ⑨ الـSHA + التأجيل

* **كود + اختبار**: `c6ef6e4` — `fix/round16-query-limits`
* **التقرير**: كوميت فوق الكود ⇒ `git log -1` (الـSHA النهائي في ردّي).

**تأجيل**: ⛔ مافيش تأجيل متعمّد في بند ٤ (كل الحالات الست اتنفّذت
واختُبرت). 🕐 **ملاحظة تصميمية** (مش تأجيل): السقوف **ثوابت كود**
مش متغيّرة بالبيئة — لوOwner عايز يظبططها من الـRailway environment
يتحوّل لـ`os.environ` بحدّ أدنى (floor) يحمي عقد الجولة ١٥.

---

## ⑩ التشغيل

```bash
cd /tmp/wt_query
/workspace/.venv-sec/bin/python test_round16_query_limits.py   # ١٧/١٧
/workspace/.venv-sec/bin/python test_round15_query_guard.py    # ١٧/١٧
/workspace/.venv-sec/bin/python test_code_hygiene.py           # ٦/٦
/workspace/.venv-sec/bin/python test_round14_release.py        # ٢٧/٢٧
/workspace/.venv-sec/bin/python test_security_batch02.py       # ٦١/٦٢ (فشل بيئي واحد)
```

⛔ مافيش شبكة · مافيش نشر · مافيش تعديل على `main`.
