# تقرير الجولة ١٦ — حداثة السعر + فصل التغطية عن الحداثة

⛔ الشغل كله داخل `/tmp/wt_price` (worktree معزول) · مافيش push · مافيش merge · مافيش deploy · مافيش شبكة إنتاج.
✅ الفرع: `fix/round16-price-freshness` (٢ كوميت · آخر SHA: `c00385b`).

---

## ١) الملفات المعدّلة + المواضع

| الملف | الموضع | التغيير |
|---|---|---|
| `opp_engine.py` | `:61-62` | ثوابت جديدة: `PRICE_MAX_AGE_OPEN=900` (١٥ د) · `PRICE_MAX_AGE_CLOSED=86400` (يوم) |
| `opp_engine.py` | `:65` | `_parse_timestamp()` — تحويل ISO8601/epoch ⇒ ثوانٍ |
| `opp_engine.py` | `:101` | **`price_age_seconds_from()`** — `price_age_seconds = now - price_ts` (عمر السعر نفسه) |
| `opp_engine.py` | `:123` | `session_date_of()` — تاريخ الجلسة (YYYY-MM-DD) |
| `opp_engine.py` | `:135` | `format_age_ar()` — نص عربي للعمر (ثواني/دقائق/ساعات/أيام) |
| `opp_engine.py` | `:154` | `freshness_state()` — **فصل** `freshness` عن `coverage_status` + `age_seconds` دايماً |
| `opp_engine.py` | `:217` | `freshness_source()` — live / partial / cache / unavailable |
| `opp_engine.py` | `:235` | `freshness_summary_ar()` — جملة واحدة فيها **الحداثة + التغطية** |
| `opp_engine.py` | `:256` | `price_label_for()` — «الآن» محتاجة: سوق مفتوح + نفس الجلسة + عمر ≤ ١٥ د |
| `opp_engine.py` | `:941` | `build_payload()` — `_now` المرجعي (من `meta["now"]`) |
| `opp_engine.py` | `:984-993` | حساب `_price_age` · `_price_session` · `_current_session` لكل صف |
| `opp_engine.py` | `:1003` | `price_label` بقى يتحسب من **العمر + الجلسة** |
| `opp_engine.py` | `:1018-1023` | حقول الصف الجديدة: `price_age_seconds` · `price_age_minutes` · `price_age_label_ar` · `price_session_date` · `current_session_date` |
| `opp_engine.py` | `:1063-1065` | كل قائمة: `coverage_status` · `data_state` · `freshness_summary_ar` |
| `opp_engine.py` | `:1079-1083` | مستوى الـpayload: `coverage_status` · `data_state` · `freshness_summary_ar` · `current_session_date` |
| `update_prices.py` | `:10232` | `"source": _opp.freshness_source(_fresh)` (بعد ما `freshness` مبقاش فيه `partial`) |
| `update_prices.py` | `:10235` | `coverage_status` اتنشر في `meta` |
| `update_prices.py` | `:10249` | `now` المرجعي اتنشر في `meta` (عمر السعر = نفس وقت الفحص) |
| `test_round16_price_freshness.py` | `:1` (جديد) | ٢٠ اختبار — فيها الاختباران السالبان الإلزاميان |
| `test_round15_price_label.py` | `:50` · `:111` · `:123` · `:130` · `:177` · `:220` | تحديث للعقد الجديد — السبب موثّق جوه كل اختبار |
| `test_round15_coverage_states.py` | `:88` · `:97` | تحديث التغطية الجزئية ⇒ `coverage_status` |
| `test_round14_release.py` | `:119` · `:137` · `:163` · `:224` · `:267` | تحديث ٤ اختبارات + helper `_epoch` — السبب موثّق |

---

## ٢) السلوك قبل/بعد

### العيب ١ — وصف السعر كاذب

| السيناريو | قبل (الجولة ١٥) | بعد (الجولة ١٦) |
|---|---|---|
| سوق مفتوح + سعر من **جلسة سابقة** + `stale=False` | «سعر التداول الآن» ⛔ كاذب | «آخر سعر معروف» |
| سوق مفتوح + `stale=False` **لوحده** (بلا أي دليل) | «سعر التداول الآن» ⛔ | «آخر سعر متاح» |
| سوق مفتوح + سعر **حديث** من **نفس الجلسة** | «سعر التداول الآن» ✅ | «سعر التداول الآن» ✅ (زي ما هو) |
| سعر قديم (ساعتين) + سوق مفتوح | «سعر التداول الآن» ⛔ | «آخر سعر معروف» |
| صف في الـpayload لسعر من جلسة سابقة | «سعر التداول الآن» ⛔ | «آخر سعر معروف» + `price_age_seconds=70800` · `price_age_minutes=1180` · `price_age_label_ar=«منذ 19 ساعة»` |
| صف من غير `price_ts` | «آخر سعر متاح» | «آخر سعر متاح» + `price_age_seconds=None` (مش صفر) |

### العيب ٢ — خلط التغطية بالحداثة

| السيناريو | قبل | بعد |
|---|---|---|
| تغطية 89.9٪ + آخر جلب من ٣ أيام | `freshness=partial` · `age_seconds=None` ⛔ (القديم اتغطّى) | `freshness=stale` · `age_seconds=259200` · `coverage_status=partial` ✅ (الاتنين يبانوا) |
| تغطية 89.9٪ + آخر جلب من ٣٠ ثانية | `freshness=partial` · `age_seconds=None` ⛔ | `freshness=fresh` · `age_seconds=30` · `coverage_status=partial` ✅ |
| تغطية 100٪ + آخر جلب من ٣ أيام | `stale` · `age=259200` | `stale` · `age=259200` · `coverage_status=complete` ✅ (زي ما هو) |
| مافيش جلب ناجح | `unavailable` · `age=None` | `unavailable` · `age=None` · `coverage_status=partial` ✅ |
| الـpayload | مافيش `coverage_status` · مافيش `data_state` · مافيش ملخّص | `coverage_status` · `data_state` · `freshness_summary_ar` («البيانات قديمة · التغطية جزئية · عمر البيانات منذ 3 أيام») |

⛔ ثوابت **ما اتغيّرتش**: «المحور الناقص = الأسوأ» (تغطية ودرجة أقل) · «نفس الدرجة بين Free وPro» (٥/٢٠) · حدود الباقات Free=5 / Pro=20 · سرّية الأوزان.

---

## ٣) أرقام الاختبارات

| الملف | على الكود الجديد | على كود الجولة ١٥ (negative proof) |
|---|---|---|
| `test_round16_price_freshness.py` (جديد) | **٢٠ ناجح / ٠ فاشل** | **٤ ناجح / ١٦ فاشل** (كلهم فشل ادعاء نظيف — مافيش error) |
| `test_round15_price_label.py` | ١٥ / ٠ | — |
| `test_round15_coverage_states.py` | ٥ / ٠ | — |
| `test_round15_opp_perms.py` | ٣٢ / ٠ | — |
| `test_round14_release.py` | ٢٧ / ٠ | — |
| **كل ملفات المستودع (٣٩ ملف / ٢٠٢ حالة)** | **٣٩ ملف · ٢٠٢ حالة ناجحة / ٠ فاشل** | — |
| حارس النظافة `test_code_hygiene.py` | ٦ / ٠ | — |

### الـnegative proof (على الكود القديم — نسخة `/tmp/neg_proof` بكود الجولة ١٥)

⛔ **الاختبار السالب الإلزامي ①** — `test_negative_open_market_previous_session_is_not_now` (`test_round16_price_freshness.py:133`):
```
AssertionError: 'سعر التداول الآن' == 'سعر التداول الآن' : وصف كاذب: سعر من جلسة سابقة اتسمّى «الآن»
```
⇒ بعد الإصلاح: `آخر سعر معروف` (ناجح).

⛔ **الاختبار السالب الإلزامي ②** — `test_negative_partial_coverage_and_old_fetch_shows_both` (`test_round16_price_freshness.py:244`):
```
AssertionError: 'partial' != 'stale' : العيب: البيانات القديمة اتغطت التغطية
```
⇒ بعد الإصلاح: `freshness=stale` + `coverage_status=partial` + `age_seconds=259200` (ناجح).

⚠️ الـnegative proof اتعمل في **نسخة منفصلة** `/tmp/neg_proof` (كود الجولة ١٥) — الـworktree الأصلي ما اتمسّش.

---

## ٤) الـSHA النهائي

- `c00385b` — 🧪 الجولة ١٦ — اختبارات حداثة السعر + فصل التغطية (negative proof)
- `6f2b117` — 🔧 الجولة ١٦ — حداثة السعر (عمر السعر نفسه) + فصل التغطية عن الحداثة

الفرع: `fix/round16-price-freshness` (فرع محلي بس · مافيش push).

---

## ٥) ⛔ ما اتحلّش / اتأجّل + السبب

1. **الواجهة (JS/HTML) مش في المستودع** ⇒ مستهلكو الـpayload لازم يتحدّثوا مع العقد الجديد:
   `freshness` مبقاش بياخد `"partial"` (بقى `coverage_status`)، و`data_state`/`coverage_status`/`price_age_*`/`freshness_summary_ar` حقول جديدة. الملف الوحيد اللي بيرجّع الرد (`update_prices.py`) اتحدّث ✓.
2. **`price_ts` لسه مفيش مصدر بيعطيه في الإنتاج** — الـscanner بتاع TradingView ميعطيش وقت آخر تداول ⇒ في الإنتاج `price_time_source=not_provided` والوصف «آخر سعر متاح» (زي الجولة ١٥). منطق الفحص الجديد **جاهز** أول ما المصدر يضيف `price_ts` (من غير ما نخمّن وقت من وقت الاستلام — ممنوع).
3. **`source` في `update_prices.py`**: تغطية جزئية + بيانات حديثة ⇒ `"partial"` (زي قبل) · بيانات قديمة + تغطية جزئية ⇒ `"cache"` (قبلها كانت `"partial"`). السبب: `source` صار يعكس **الحداثة** والتغطية بتظهر في `coverage_status`.
4. **`docs/REVIEW-LOG.md` / `PROJECT_STATE.md` ما اتحدّثوش** — مش مطلوبين في التسليم (التسليم = كود + اختبارات + تقرير).
5. **حدّ عمر السعر (١٥ دقيقة) قرار مؤقت** — `PRICE_MAX_AGE_OPEN` في `opp_engine.py:61` (ثابت واحد) لو المالك عايز رقم تاني.
6. **مافيش نشر (deploy) ولا push** — حسب القيد الصريح.
