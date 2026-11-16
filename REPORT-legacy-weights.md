# 🔐 الجولة ١٦ — منع كشف أوزان المحرك القديم (Legacy)

📌 **الفرع**: `fix/round16-legacy-weights` · **الأساس**: `93b1988` (الجولة ١٥)
📌 **المعدّل**: `update_prices.py` · **الجديد**: `test_round16_legacy_weights.py`
📌 **الـSHA**: `ef64156` (كوميت واحد · بلا push · بلا merge · بلا deploy)

---

## ① الخلاصة (سطرين)

المساران القديمان `/api/strategies` و `/api/strategy/<code>/<strategy>` كانا **مفتوحين
بدون جلسة** ⇒ زائر مجهول ياخد:
* **بنية أوزان المحرك كاملة** (`weights` = مجموع أوزان المعايير) من المسار الأول،
* **مخرجات التقييم الكاملة** (محاور + المجموع قبل الخصم + خصم المخاطرة) من المسار الثاني
  ⇒ وباستنتاج ردود متعددة لصنفس الاستراتيجية كان **ممكن استخراج بنية الأوزان**.

⇒ الإصلاح: **جلسة مطلوبة** (401 للزائر) + **قائمة حقول صريحة (whitelist)** على نتيجة
التقييم ⇒ «weights» مش متبني خالص، مش بس متخفّي بالاسم.

---

## ② المواضع (file:line)

| العنصر | الموضع | الوظيفة |
|---|---|---|
| `/api/strategies` + قفل الجلسة | `update_prices.py:11348` | 401 لغير المسجّل · حذف `weights` من الرد |
| `_STRATEGY_PUBLIC_KEYS` | `update_prices.py:11365` | قائمة الحقول المسموحة (whitelist) |
| `_public_strategy_result()` | `update_prices.py:11380` | نسخة عامة من نتيجة الاستراتيجية |
| `/api/strategy/<code>/<strategy>` + قفل الجلسة | `update_prices.py:11400` | 401 لغير المسجّل |
| `all_strategies` | `update_prices.py:11416` | شكله محدود أصلاً (`name`/`score`/`decision`/`filters_passed`/`score_status`/`rank_eligible`) ⇒ **مافيش أوزان** |

---

## ③ قبل / بعد

| السيناريو | قبل | بعد |
|---|---|---|
| زائر مجهول ⇒ `/api/strategies` | **200** + `weights` لكل استراتيجية ⛔ | **401** `auth_required` |
| زائر مجهول ⇒ `/api/strategy/S00/balanced` | **200** + `axes` + `base` + `risk_penalty` ⛔ | **401** `auth_required` |
| مستخدم مسجّل ⇒ `/api/strategies` | `weights` مكشوفة ⛔ | `key`·`name`·`desc`·`timeframe`·`focus` **بدون** `weights` |
| مستخدم مسجّل ⇒ `/api/strategy/...` | كل حقول `strategy_score` ⛔ | الـwhitelist فقط (١٥ حقل) · **مافيش** `weights` |
| توكن مزيّف | يمرّ ⛔ | **401** |
| المحرك ميت (لا بيانات) | 200 ببيانات قديمة ⛔ | **401** (القفل **قبل** أي جلب) |

---

## ④ الأرقام

### الاختبار الجديد — `test_round16_legacy_weights.py`
**٢٤ / ٢٤ ناجح** على الكود الجديد.

| الكلاس | العدد | وش بيCover |
|---|---|---|
| `TestAnonymousBlocked` | ٧ | 401 على كل المسارات · توكن مزيّف · القفل حتى لو المحرك ميت |
| `TestNoWeightsAnywhere` | ١ | مافيش كلمة `weights` في مصدر المسار القديم |
| `TestPositivePath` | ٦ | المستخدم المسجّل بياخد نفس الدرجة + الحقول اللي الواجهة بتقراها |
| `TestRecipeNotRecoverable` | ٦ | **بالرقم**: مافيش طريقة تسترجع الوصفة من الردود العامة |
| `TestMissingAxis` | ٣ | «المحور الناقص = الأسوأ» ما اتغيّرش |

### Negative proof (على الأساس `93b1988`)
**٩ / ٢٤ فاشل** (كلهم اختبارات السلوك الجديد):

```
FAIL: test_anonymous_gets_401_on_legacy_strategies_list
FAIL: test_anonymous_gets_401_on_legacy_strategy_detail
FAIL: test_anonymous_gets_401_even_when_engine_is_down
FAIL: test_anonymous_gets_401_on_every_strategy_path
FAIL: test_forged_token_gets_401_on_legacy_paths
FAIL: test_route_guard_blocks_with_global_gate_on_and_off
FAIL: test_anonymous_response_has_no_evaluation_internals
FAIL: test_legacy_route_source_has_no_weights_literal
FAIL: test_anonymous_cannot_recover_anything
  ⇒ AssertionError: {'axes','base','risk_penalty','liquidity_penalty',
                      'filter_penalty','confidence','filters_passed',
                      'filter_notes','missing_axes'} is not false
     : /api/strategy/S00/balanced
```

### الانحدار (بعد التعديل)

| الملف | النتيجة |
|---|---|
| `test_round16_legacy_weights.py` | **٢٤/٢٤** ✅ |
| `test_round15_query_guard.py` | ١٧/١٧ ✅ |
| `test_round15_price_label.py` | ١٣/١٣ ✅ |
| `test_round15_coverage_states.py` | ٥/٥ ✅ |
| `test_round15_opp_perms.py` | ٣٢/٣٢ ✅ |
| `test_round14_release.py` | ٢٧/٢٧ ✅ |
| `test_code_hygiene.py` | ٦/٦ ✅ |

---

## ⑤ فحص اعتماد الواجهة (قراءة فقط)

| الموضع | بيقرا إيه | الحكم |
|---|---|---|
| `assets/js/octa-pages.js:825` (`loadStrategies`) | `key` + `name` | ✅ شغّال |
| `assets/js/octa-pages.js:840` (`renderStrategies`) | `strategy_name`·`timeframe`·`focus`·`score`·`axes`·`base`·`risk_penalty`·`filter_notes`·`confidence` | ✅ كلهم في الـwhitelist |
| `assets/js/octa-pages.js:2997` | `key` + `name` | ✅ شغّال |

📌 `octaFetch` (`assets/js/octa-api.js:711`) بيضيف `credentials: 'include'` + `Bearer`
⇒ المستخدم المسجّل بيعدّي القفل عادي. لو المستخدم مش مسجّل ⇒ الواجهة بتعرض
«تعذر تحميل الاستراتيجيات» (سلوك موجود أصلاً في `catch`) ⇒ **مافيش كسر**.

---

## ⑥ ⛔ ملاحظات متبقية (موثّقة · مش مؤجّلة)

1. **تسريب متبقٍ (للمستخدم المسجّل)**: اختباران بيستخرجا **عتبة السيولة** و**معامل
   خصم المخاطرة** من الحقول المكشوفة (`axes` + `liquidity_penalty` + `risk_penalty`).
   ⇒ ده **بطبيعته** بيحصل مع أي تقييم شفاف. العقد المتفق عليه هو **سرّية الأوزان
   (weights)** لا سرّية كل عتبة. ⛔ لو المالك عايز كتم العتبات ⇒ لازم نخفي
   `axes`/`base`/الخصومات ⇒ وده قرار تصميم (يؤثر على شفافية التقييم).
2. **`all_strategies`**: شكله محدود أصلاً ⇒ مافيش أوزان ⇒ مافيش إجراء.
3. **`/api/ranking` و `/api/opportunities`**: بيكشفوا **الدرجة** لا الأوزان ⇒ خارج النطاق.

---

## ⑦ التشغيل

```bash
cd /tmp/wt_weights
/workspace/.venv-sec/bin/python test_round16_legacy_weights.py   # ٢٤/٢٤
/workspace/.venv-sec/bin/python test_round15_query_guard.py    # ١٧/١٧
/workspace/.venv-sec/bin/python test_round14_release.py        # ٢٧/٢٧
/workspace/.venv-sec/bin/python test_code_hygiene.py           # ٦/٦
```

⛔ مافيش شبكة · مافيش نشر · مافيش تعديل على `main`.
