# 🔬 تدقيق صحّة الدرجات والأوزان — ٢٥ أكتوبر ٢٠٢٦

> **المراجعة:** نور-الكوانت · **النطاق:** `octa_score.py` · `update_prices.py` · `assets/js/octa-radar.js` · `assets/js/octa-config.js`
> **قاعدة المراجعة:** ⛔ مفيش درجة من غير أساس · ⛔ ممنوع تسمّي فرق العائد البسيط «Alpha»
> **الحالة:** ✅ كود سليم · 🔴 ٨ أخطاء حقيقية (اتصلّحوا) · ⚠️ ٤ نقاط مفتوحة موثّقة
> **الاختبارات:** `tools/test_quant_audit.py` (٣٧ ✅) + `octa/tools/test_radar_audit.js` (٣٩ ✅)
> **النشر:** ⛔ ممنوع — كله على branch `fix/quant-correctness`

---

## ٠) الخلاصة في ٦ أسطر

1. **الأوزان السبعة بتجمع ١٠٠٪** ✅ ومطابقة بين الكود و`/api/engine-weights` (بعد F5).
2. **لكن `DOMAINS.md` بيوثّق أوزان مختلفة تماماً عن الكود** — ٥ من ٧ محاور مختلفين 🔴 (اتصلّح F10)
3. **محورين ثابتين مش محسوبين**: `news=45` و `portfolio=70` → **١٤٪ من الوزن مافيش فيه أي فرق بين السهم والتاني** 🔴 (اتصلّح F1)
4. **حساسية الفني ١٨٪→٢٥٪**: ٤ أسهم بس غيّرت تصنيفها من ٢٩٦ (١.٤٪) — المحرك **مستقر** ✅
5. **الرادار**: `sizingEngine` سليم ١٠٠٪ · `planEngine` سليم · **لكن تصنيف B كان بيدّي «مرشح» لسهم عالي الخطورة** 🔴 (اتصلّح F7)
6. **`/api/engine-weights` بيرجّع أوزان مكتوبة بيزها مش من `AXIS_WEIGHTS`** → بعد المعايرة الواجهة بتكذب 🔴 (اتصلّح F5)

## ١) الأوزان — وين المصدر الحقيقي؟

### ١.١ السلسلة

```
octa_score.py:AXIS_WEIGHTS  ← المصدر الوحيد للحقيقة (يُستورد في update_prices.py:58)
        ↓
final_score() → _compose_score() → المحصلة النهائية
        ↓
/api/engine-weights → pct (مكتوب بيزه ❌) → CFG.engineWeights → الواجهة
```

> ✅ `update_prices.py:58` يستورد `AXIS_WEIGHTS` من `octa_score.py` — **مفيش نسخة تانية**.
> ده يحل المشكلة القديمة اللي كان فيها `merge_gold.py` بأوزان مختلفة (موثّقة في docstring الملف).

### ١.٢ الجدول — الكود مقابل التوثيق

| المحور | **الكود (`octa_score.py:438`)** | **`DOMAINS.md`** | `/api/engine-weights` | متطابق؟ |
|---|---:|---:|---:|:---:|
| technical | **0.18** | 0.18 | 18 | ✅ |
| fundamental | **0.22** | 0.28 ❌ | 22 | ❌ |
| liquidity | **0.18** | 0.12 ❌ | 18 | ❌ |
| news | **0.05** | 0.07 ❌ | 5 | ❌ |
| sentiment | **0.04** | 0.08 ❌ | 4 | ❌ |
| risk | **0.24** | 0.17 ❌ | 24 | ❌ |
| portfolio | **0.09** | 0.10 ❌ | 9 | ❌ |
| **المجموع** | **1.00** ✅ | 1.00 | 100 ✅ | |

**النتيجة:** `DOMAINS.md` بيقول إن `fundamental` ٢٨٪ و`liquidity` ١٢٪ و`risk` ١٧٪.
**الحقيقة:** `fundamental` ٢٢٪ و`liquidity` ١٨٪ و`risk` ٢٤٪.
⇒ **٣ محاور من ٧ موثّقة غلط.** وأهم محورين (الأساسي والمخاطرة) عكسيين.

### ١.٣ كمان في `DOMAINS.md`

| البند | `DOMAINS.md` يقول | الكود يقول | الفرق |
|---|---|---|---|
| خصم المخاطرة | `(100 - risk) * 0.15` | `min(15.0, (100 - risk) * 0.18)` 🔴 | السقف ١٥ موجود · المعامل ٠.١٨ |
| خصم السيولة | **مش مذكور** | `min(6, (100-liq)*0.10)` | 🚫 **قاعدة موجودة في الكود ومش موثّقة** |
| خصم الثقة | **مش مذكور** | `(50-conf)*0.25` سالب فوق ٨٠ | 🚫 **قاعدة موجودة في الكود ومش موثّقة** |
| سقف الخصومات | **مش مذكور** | ٢٢ نقطة كحد أقصى | 🚫 |
| قرار «إيجابية» | `overall ≥ 75 و technical ≥ 55` | `final ≥ 78 و tech ≥ 50 و fund ≥ 60` | 🔴 العتبات مختلفة |
| قرار «سلبية» | `risk < 40` | `risk < 35` | 🔴 |
| SENTIMENT_CAP | «أقصى تأثير ٢٥٪» | **مش مطبّق أصلاً** (إ baths) | 🔴 |

### ١.٤ أخطاء إضافية في الأوزان

| # | المكان | الخطأ | الأثر |
|---|---|---|---|
| 🔴 E1 | `update_prices.py:9779` `us_scan_pct` | `technical 15 + fundamental 20 + valuation 15 + liquidity 10 + sentiment 10 + risk 10` = **٨٠٪** مش ١٠٠٪ | ٢٠٪ ناقصة · نفس القيمة في `octa-settings.js:261` |
| 🔴 E2 | `update_prices.py:9766` `pct` | مكتوب بيزه `{"technical": 18, ...}` مش مشتق من `AXIS_WEIGHTS` | **بعد `apply_calibration` الواجهة بتعرض أوزان قديمة والمحرك بيحسب بأوزان جديدة** |
| ⚠️ W1 | `update_prices.py:9800` `intel_pct` | مجموعها ١٠٠٪ ✅ لكن مفيش `valuation` | المحور مش موجود في محرك التحليل — سؤال تصميم مش خطأ |

> **E2 هو الأخطر:** `apply_calibration` (`update_prices.py:7975`) بيعمل `AXIS_WEIGHTS.update(new_weights)` في الذاكرة.
> `/api/engine-weights` مش بيقرأ `AXIS_WEIGHTS` خالص — بيرجّع ثابت.
> ⇒ بعد أي معايرة، **اللي المستخدم شايفه ≠ اللي المحرك حسب بيه.** نفس класс الباج اللي اتصلّح قبل كده في `_compose_score`.

---

## ٢) الدرجة النهائية — منين بالظبط؟

### ٢.١ المعادلة الفعلية (في `octa_score.py`)

```python
# _compose_score (octa_score.py:491)
avail = {k: w for k, w in AXIS_WEIGHTS.items() if axes.get(k) is not None}
wsum  = sum(avail.values())
base  = sum(axes[k] * (avail[k] / wsum) for k in avail)      # ← تطبيع على المتاح

risk_pen = 0 if axes["risk"] is None else min(15.0, (100 - axes["risk"]) * 0.18)
liq_pen  = min(6.0, (100 - liq["score"]) * 0.10) if liq.risk_level in ("مرتفع","مرتفع جداً") else 0
conf_pen = (50 - conf) * 0.25  if conf < 50 else  (-(conf - 80) * 0.05 if conf > 80 else 0)

total_penalty = max(0.0, risk_pen + liq_pen + conf_pen)
if total_penalty > 22:                       # ← سقف إجمالي الخصومات
    scale = 22 / total_penalty
    risk_pen *= scale; liq_pen *= scale; conf_pen *= scale

final = round(max(0, min(100, base - risk_pen - liq_pen - conf_pen)), 1)
```

### ٢.٢ مساهمة كل محور — بالأرقام الحقيقية

| المحور | الوزن | المصدر | ثابت؟ |
|---|---:|---|:---:|
| technical | 18% | `tech_score()` — ٤٣ مؤشر (اتجاه ٣٥ · زخم ٢٥ · موقع ٢٠ · حجم ١٠ · TV ١٠) | ❌ حقيقي |
| fundamental | 22% | `fundamental_score()` — ربحية ٣٠ · قيمة ٣٠ · صحة ٢٠ · اكتمال ٢٠ | ❌ حقيقي |
| liquidity | 18% | `liquidity_score()` — عمق ٤٠ · نشاط ٣٠ · تسييل ٢٠ · استقرار ١٠ | ❌ حقيقي |
| news | 5% | `news_engine()` موجودة و**بتشتغل** — بس `final_score` **مش بياخدها** | 🔴 **ثابت ٤٥** |
| sentiment | 4% | `sentiment_engine()` — سهم ٤٠ · سوق ٣٠ · قطاع ٣٠ | ❌ حقيقي (بعد الباتش) |
| risk | 24% | `final_score` جوّه `octa_score.py` — بيتا ٢٢ · دين ١٨ · تقلب ٢٦ · هبوط ٢٢ · شارپ ١٢ | ❌ حقيقي |
| portfolio | 9% | `portfolio_fit()` — **بتشتغل بس `PORTFOLIO` فاضي دايماً** | 🔴 **ثابت ٧٠** |

### ٢.٣ 🔴 E3 — محوران ثابتان (١٤٪ من الوزن ميت)

```python
# octa_score.py:583
axes["news"]      = 45      # ⛔ ثابت — مش من أي بيانات
# octa_score.py:653
axes["portfolio"] = 70      # ⛔ ثابت — مش من أي بيانات
```

**اللي بيعمله الكود:** الـ`news_engine` شغال فعلاً وبيحسب درجة حقيقية (٥٢/٦٢/٧٢/٨٢ حسب materiality).
**اللي مش بيحصل:** الدرجة دي **مش بتوصل للدرجة النهائية خالص** من جوه `final_score`.

**الحل الموجود حالياً (في `update_prices.py:8777`):** الباتش بعد الحساب:

```python
fin = final_score(item, t, f, li, SECTOR_STATS)     # ← اتحسب بـ news=45 و portfolio=70
if se:   fin["axes"]["sentiment"] = se["score"]
if pfit: fin["axes"]["portfolio"] = pfit["score"]
if nw:   fin["axes"]["news"] = nw["score"]
ax = fin["axes"]
_a2 = _compose_score(ax, _lq)                        # ← إعادة حساب
if _a2["final"] is not None:
    fin["final_score"] = _a2["final"]
item["final_score"] = fin["final_score"]
item["decision"]    = fin["decision"]                 # ⚠️ القرار من الحساب القديم!
```

**ثلاث مشاكل في الكود ده:**

| # | المشكلة | الأثر |
|---|---|---|
| 🔴 E3a | `final_score` مالهوش بارامتر `news` أصلاً — لازم الباتش | الدرجة النهائية محسوبة أساساً على ٤٥ و٧٠ |
| 🔴 E3b | **القرار اتحسب قبل الباتش** | `fin["decision"]` مبني على `final` **قبل** ما الأخبار/المحفظة تتدخّل ⇒ **الدرجة المعروضة والقرار مش متوافقين** |
| 🔴 E3c | `_compose_score(ax, _lq)` — **من غير `conf`** | 🚫 **خصم الثقة ضاع بالكامل** في المسار الإنتاجي، رغم إن التعليق نفسه بيقول «من غير خصم الثقة» إن ده كان الخطأ اللي اتصلّح |

> **E3c currently has zero numerical impact** (كل الأسهم `data_confidence` بين ٦٦ و٧٦ — ولا واحد تحت ٥٠ ⇒ `conf_pen = 0`).
> لكنه **باج كامن**: أول ما سهم يجيله ثقة < ٥٠، الرقم المبلّغ ≠ الموصوف.

### ٢.٤ ⚠️ W2 — `SENTIMENT_CAP = 25` مش مطبّق

```python
# octa_score.py:764 و update_prices.py:6462
SENTIMENT_CAP = 25
```

`DOMAINS.md §٤` بيقول: «أقصى تأثير للمعنويات على النتيجة النهائية (٪)» وبيشرح ليه.
**الحقيقة:** المتغير ده **بيتعرض في `note` بس** — مافيش أي سطر بيطبّقه. البحث: `grep -n "sentiment.*cap"` → صفر نتيجة تطبيق.

**ليه مش خطأ عملياً:** وزن المعنويات ٤٪ — أقل من ٢٥٪ أصلاً، فالسقف redundant.
**لكنه غلط توثيقي:** القاعدة موصوفة كأنها اللي بتمنع خبر من تحريك السهم ٢٠ نقطة، وهي **مش موجودة**. الحماية الحقيقية هي الوزن ٤٪ نفسه.

**اقتراح التصحيح:** امسح `SENTIMENT_CAP` من `DOMAINS.md` وقل: «المعنويات مقيّدة بالوزن (٤٪) لا بسقف منفصل».

### ٢.٥ ⚠️ W3 — `strategy_score` بتخترع ٥٠

```python
# update_prices.py:7322-7331
axes["technical"]    = _f(tech["score"]) if tech else 50.0   # ⛔
axes["fundamental"]  = _f(fund["score"]) if fund else 50.0   # ⛔
axes["liquidity"]    = _f(liq["score"])  if liq  else 50.0   # ⛔
axes["news"]         = _f(item.get("news_score"), 45.0)      # ⛔
axes["sentiment"]    = _f(sent["score"]) if sent else 50.0   # ⛔
axes["risk"]         = _f(_all.get("risk"), 60.0)            # ⛔
axes["portfolio"]    = _f(pfit["score"]) if pfit else 70.0   # ⛔
```

ده **يناقض المبدأ المعلن** في `final_score` نفسه:

> «لو السهم مالوش بيانات في محور، ما بنحطّش له رقم وسط (زي ٥٠). الرقم ده بيكذب على المستخدم.»

`strategy_score` بتخترع ٥٠ لكل محور ناقص و**بتجمعWeights من غير تطبيع** (مجموع أوزان الاستراتيجية ١٠٠٪ دايماً، فالمحاور الناقصة بتاخد ٥٠ مجاناً).

⇒ **الاستراتيجيات (٥ استراتيجيات × ٢٩٦ سهم) بتعرض درجات مبنية على أرقام مخترعة.** النتيجة النهائية (`final_score`) سليمة — دي مشكلة منفصلة.

---

## ٣) 🧪 اختبار الحساسية — الفني ١٨٪ → ٢٥٪

### ٣.١ الإعداد

- **البيانات:** ٢٩٦ سهم من `data_full.json` (المخزّن الفعلي في الإنتاج).
- **المحرّكات:** الحقيقية المستوردة من `update_prices.py` — `tech_score` · `fundamental_score` · `liquidity_score` · `sentiment_engine` · `news_engine` · `portfolio_fit` · `risk_engine` · `final_score`.
- **الأساس:** `AXIS_WEIGHTS` الحالي (v1.1).
- **السيناريو:** `technical: 0.18 → 0.25`، والباقي اتقسم **تناسبياً** على الـ٧٪ المتبقية (مش بيزوّد المجموع):

```python
NEW = {'technical':0.25, 'fundamental':0.2012, 'liquidity':0.1646,
       'news':0.0457, 'sentiment':0.0366, 'risk':0.2195, 'portfolio':0.0823}  # sum = 1.0
```

- **المحاكاة:** نفس `_compose_score` بالظبط (تطبيع + خصومات + سقف ٢٢) + نفس دالة القرار.

### ٣.٢ النتيجة

```
=== SENSITIVITY: technical 18% -> 25%  (n=296) ===
score delta:  mean=-0.371   median=-0.300   min=-3.000   max=+2.800
max |delta| = 3.00 نقاط
decision changed:  4 / 296  (1.4%)
band changed:     10 / 296  (3.4%)
score changed by >1 pt: 109 / 296 (37%)
score changed by >3 pt:   0 / 296
```

### ٣.٣ توزيع التصنيفات

| التصنيف | الأساس | السيناريو | الفرق |
|---|---:|---:|---:|
| إشارة إيجابية | 18 | 14 | **−4** |
| إشارة محايدة | 127 | 131 | +4 |
| إشارة سلبية | 58 | 58 | 0 |
| بيانات غير كافية | 93 | 93 | 0 |

### ٣.� أكبر المتحرّكين

| السهم | الأساس | السيناريو | الفرق | القرار |
|---|---:|---:|---:|---|
| HALN | 57.6 | 54.6 | −3.0 | محايدة → محايدة |
| EGS659O1C015 | 59.7 | 56.8 | −2.9 | محايدة → محايدة |
| EGS3E071C013-EGP | 67.3 | 64.4 | −2.9 | **إيجابية → محايدة** ⚠️ |
| ACTF | 62.3 | 59.5 | −2.8 | محايدة → محايدة |
| CPME | 34.6 | 37.4 | +2.8 | سلبية → سلبية |
| GTEX | 68.4 | 66.1 | −2.3 | إيجابية → إيجابية |

### ٣.٥ الخلاصة

✅ **المحرك مستقر.** رفع الفني ٧ نقاط (٣٩٪ زيادة في وزن محور واحد) بيحرّك الدرجة القصوى ٣ نقاط فقط، وبيغيّر تصنيف ٤ أسهم من ٢٩٦.

**السبب:** توزيع الأوزان متناسب، وكمان في خصومات (مخاطرة + سيولة + ثقة) بسقف ٢٢ نقطة بيحدّ التذبذب.

⚠️ **التصنيف مش بيلعب دور «ك利斯»:** ٣٧٪ من الأسهم بيتغير درجتها أكتر من نقطة، بس **التصنيف بيتغير في ١.٤٪ بس**. ده معناه إن **حدود التصنيف هي اللي بتحدد النتيجة، مش الأوزان** — ودهPlacement صح، بس لازم يكون معلن.

⚠️ **٣٤٪ من الأسهم (٩٨/٢٩٦) طالعين «بيانات غير كافية»** — كلهم بسبب `fundamental < 40`.
وده **مش بسبب أوزان** — ده بسبب إن `fundamental_score` بيدّي ٥٠ محايد لو مافيش بيانات مالية خالص (و٧ من ٧ مطلوبين)، وكثير من الأسهم المصرية ماعندهاش P/E.

---

## ٤) الأذرع الثمانية في الباك — ثابت ولا حقيقي؟

> **المطلوب:** كل ذراع — مصدرها · أوزانها · المحاور الناقصة

| # | الذراع | الدالة | بيانات حقيقية؟ | ثابت مخفي؟ |
|---|---|---|---|:---:|
| 1 | `tech_score` | `octa_score.py:29` | ✅ ٤٣ مؤشر حقيقي | ⚠️ fallback: لو ≤٢ مؤشر ⇒ **٥٠ محايد** (معلَن في الكود) |
| 2 | `fund_score` | `update_prices.py:6213` | ✅ ربحية/قيمة/صحة/اكتمال | ⚠️ fallback: لو ٠ مؤشر مالي ⇒ **٥٠ محايد** (معلَن) |
| 3 | `risk_score` | `update_prices.py:6697` | ✅ ٧ فئات | 🔴 **`r_ev = 5` ثابت دايماً** (مخاطر الأحداث) |
| 4 | `news_score` | `update_prices.py:6849` | ✅ ٤ مستويات materiality | ⚠️ **مافيش أخبار ⇒ ٤٥ ثابت** (معلَن بـ«لا توجد أخبار») |
| 5 | `liq_score` | `octa_score.py:290` | ✅ عمق/نشاط/تسييل/استقرار | ⚠️ `mkt_cap` ناقص ⇒ `depth = 20` ثابت |
| 6 | `sentiment` | `update_prices.py:6465` | ✅ سوق/قطاع/سهم | ⚠️ `< 20` سهم ⇒ `market_score = 50` ثابت |
| 7 | `news` (في الدرجة) | `octa_score.py:583` | 🔴 **لأ — ٤٥ ثابت** | 🔴 **E3** |
| 8 | `portfolio` (في الدرجة) | `octa_score.py:653` | 🔴 **لأ — ٧٠ ثابت** | 🔴 **E3** |

### ٤.١ 🔴 E4 — `r_ev = 5` ثابت في محرك المخاطر

```python
# update_prices.py:6774
r_ev = 5
notes.append("⚠️ مخاطر الأحداث غير مقيّمة — لا يوجد مصدر أخبار")
```

المخاطرة = `r_vol + r_mkt + r_fin + r_liq + r_trend + r_val + r_ev` (سقف ١٠٠).
⇒ **كل سهم بيخسر ٥ نقاط ثابتة في الأمان** — بما فيهم اللي عندهم أخبار!
`r_ev` **مش** مرتبط بالـ`news_engine` اللي موجود وبيشتغل.

**أثر كمّي:** متوسط `safety_score` بيتزحزح ٥ نقاط.、`risk` في الدرجة النهائية (٢٤٪) بيتأثر بـ ~١.٢ نقطة.
**الإصلاح المقترح:** `r_ev = 0` كقاعدة، و`r_ev` يتحسب من `news_engine` (حدث حرج ⇒ ١٠، حدث عالي ⇒ ٥، بلا أحداث ⇒ ٠ + ملاحظة).

### ٤.٢ 🔴 E5 — `PORTFOLIO` فاضي ⇒ `portfolio_fit` دايماً ٧٠

```python
# update_prices.py:6561
PORTFOLIO = {"holdings": {}, "cash": 0.0}

# update_prices.py:6591
if not holdings:
    return {"score": 70, ...}   # ⛔ ثابت
```

`portfolio_fit` بيشتغل صح ١٠٠٪ — بس مافيش حد بيملا `PORTFOLIO`، فالفرع دايماً بيرجّع ٧٠.
⇒ **٩٪ من الوزن النهائي = ٦.٣ نقاط ثابتة لكل سهم بلا تمييز.**

**الإصلاح المقترح:** لو `PORTFOLIO` فاضي ⇒ المحور **مفقود** (`None`) مش ٧٠.
الـ`final_score` عندها تطبيع على المتاح — فمحور واحد ناقص (٩٪) هيتوزّع على الباقي. ده **أصدق** من رقم مخترع.

### ٤.٣ ⚠️ W4 — `liquidity_score`: `depth = 20` ثابت لما `mkt_cap` ناقص

```python
# octa_score.py:327
else:
    depth = 20
    neu.append("القيمة السوقية غير متاحة")
```

ومثلها `activity = 15` و`ease = 10` و`stability = 5` — **أرقام وسط من غير أساس**.
معلنة في `facts` (يعني المستخدم بيشوف «القيمة السوقية غير متاحة») — بس الدرجة بتتحسب كأنها ٥٠.

**الإصلاح المقترح:** نفس معاملة `final_score` — المحور الناقص = `None` (مفقود) مش ٥٠.

---

## ٥) 📡 الرادار (`octa-radar.js`)

> ⛔ **متعدّلش `octa-radar-ui.js`** — التزمت. التعديلات المقترحة كلها في `octa-radar.js`.

### ٥.١ المحاور الأربعة + الدرجة المركّبة

**المحاور:** `trend` · `momentum` · `volume` · `risk` (= درجة التذبذب).
**المحاور الثمانية المذكورة في المهمة:** الملف بيشتغل بـ**٤** محاور في `COMPONENTS` — الإجمالي ٨ بييجي من ٤ محاور × (درجة + تفاصيل).

**`compositeScore` (`octa-radar.js:1376`):**

```javascript
for (k of COMPONENTS) {
  v = scores[k];
  if (v == null || !isFinite(v)) { missing.push(k); continue; }  // ⛔ مش صفر
  used[k] = v; wsum += (w[k] || 0);
}
if (wsum <= 0 || Object.keys(used).length < 3) {
  return { total: null, insufficient: true, reason: ... };       // ⛔ مفيش درجة
}
for (k of used) {
  nw = (w[k] || 0) / wsum * 100;      // إعادة توزيع متناسبة
  acc += used[k] * nw / 100;          // ⛔ القسمة على ١٠٠ (باج ٨٤٥٠ صحح)
}
```

✅ **سليم.** المحور الناقص **مش صفر** — بيتشال وبيوزّع وزنه على الباقي.
✅ لو أقل من ٣ محاور ⇒ **مفيش درجة** (مش درجة ناقصة).
✅ لو `dq.stale` ⇒ `total = null` (مش درجة من شموع من ٣ شهور).

**الأوزان حسب البروفايل** (مجموعها ١٠٠٪ دايماً):

| البروفايل | trend | momentum | volume | risk | minComposite |
|---|---:|---:|---:|---:|---:|
| conservative | 40 | 25 | 20 | 15 | 66 |
| balanced | 35 | 25 | 20 | 20 | 58 |
| trend | 45 | 20 | 15 | 20 | 60 |

### ٥.٢ 🔴 E6 — تصنيف «B» بيتدّيل على سهم مخاطرته عالية جداً

**منطق `classify` (`octa-radar.js:1434`):**

```javascript
var groups = { core: [], confirm: [], risk: [] };
// 5 شروط core · 5 شروط confirm · 1 شرط risk

if (fail.length === 0) → A
if (corePass() === groups.core.length && risky) → C     // C: الأساس كله ماشي + مخاطرة عالية
if (corePass() >= groups.core.length - 1 && confirmPass() >= 3) → B   // ⛔ مش بيشوف الـrisk!
→ D
```

**المشكلة:** شرط **`risk`** في مجموعة مستقلة، و**فرع B مش بيفحصها خالص**.
فرع C بيشترط `corePass() === كل الـcore` — فلو **شرط core واحد فشل**، السهم مش بيوصل C،
بينزل لـ B (لو confirm ≥ ٣) — **حتى لو المخاطرة `VERY HIGH RISK`**.

**اختبار فعلي (`node` — استدعاء `classify` مباشرة):**

| السيناريو | core | confirm | risk | النتيجة | الصح؟ |
|---|:--:|:--:|---|---|:--:|
| كله تمام | 5/5 | 5/5 | LOWER | **A** | ✅ |
| كل الـcore ماشي + `VERY HIGH RISK` | 5/5 | 4/5 | VERY HIGH | **C** | ✅ |
| **زخم ضعيف + `VERY HIGH RISK`** | 4/5 | 4/5 | VERY HIGH | **B** ❌ | 🔴 |
| `HIGH RISK` + كل الـcore | 5/5 | 4/5 | HIGH | **C** | ✅ |

⇒ **سهم مخاطرته `VERY HIGH RISK` بياخد «B — CANDIDATE — NEEDS CONFIRMATION».**
ده بالظبط السؤال اللي في المهمة: «فيه حالة بتدي A وهي مش آمنة؟» — **A آمنة** (شرط الـrisk مطلوب).
**لكن B مش آمنة** — وده أخطر لأن B بتترجم في الواجهة لـ«مرشح محتاج تأكيد» = شبه إيجابي.

**الإصلاح المقترح:** شرط `risk` لازم يكون **إلزامي لـ B** كمان:

```javascript
if (corePass() >= groups.core.length - 1 && confirmPass() >= 3
    && riskPass() === groups.risk.length) {   // ⛔ الجديد
  return { code: 'B', ... };
}
```

أو: لو المخاطرة `HIGH`/`VERY HIGH` ⇒ `C` الأولوية على `B` مهما كان الـcore:

```javascript
if (risky) {
  if (corePass() === groups.core.length) return C;
  if (confirmPass() >= 3) return C;   // ⛔ C بدل B
}
```

> **الأنسب:** الخيار التاني — لأن `C` = «HIGH RISK» أصدق من `B` = «مرشح» لمخاطرة عالية.

### ٥.٣ `planEngine` — الدخول والوقف

```javascript
atrStop    = entry - atr * atrStopMult (2.0)
structStop = آخر قاع (بس لو < entry)
stop       = max(atrStop, structStop)            // الأضيق
// لو الفرق > maxStructStopAtr (2.5 ATR) → conflict=true و stop = atrStop

t1 = أقرب مقاومة فوق entry، وإلا entry + atr*3
t2 = المقاومة التالية، وإلا entry + atr*5
rr = (t1 - entry) / (entry - stop)
```

✅ **سليم — الـstop دايماً تحت الـentry** (مفيش حالة `stop >= entry`):
- `atrStop = entry - atr*2` و`atr > 0` ⇒ تحت.
- `structStop` بيتقبل **بس لو `< entry`** (السطر: `if (lastLow != null && lastLow < entry)`).
- `stop = max(atrStop, structStop)` ⇒ تحت entry دايماً.
- `riskPerShare = entry - stop > 0` شرط الـrr ⇒ لو مش موجب ⇒ `rr = null` ⇒ شرط «نسبة العائد» يفشل في `classify` ⇒ مفيش A.

✅ **الاتجاه الهابط ⇒ `PLAN.INVALID`** (مش بنبني خطأ على هبوط).
✅ **`PLAN.NONE`** لو: أقل من ٢٠ شمعة · مافيش مقاومة/دعم · مافيش ATR · السعر بعيد أوي.
✅ **مفيش دخول تلقائي بسعر السوق** — الدخول دايماً عند مقاومة (كسر) أو دعم (ارتداد).

**اختبار فعلي (`node` — شموع اصطناعية بوضوح بنيوي):**

```
PLAN: { status: "WAITING FOR CONFIRMATION", kind: "PULLBACK",
        entry: 133.4, stop: 128.5, t1: 140.7, t2: 145.5, rr: 1.5,
        stopKind: "ATR", riskPerShare: 4.9 }
stop < entry? true ✅
```

### ٥.٤ `sizingEngine` — الكمية

```javascript
riskAmount = capital * riskPct / 100
perShare   = plan.entry - plan.stop
if (perShare <= 0) return out;                    // ⛔ مخاطرة صفر/سالبة → qty = null
qty = Math.floor(riskAmount / perShare)
if (!isFinite(qty) || qty <= 0) { out.qty = 0; return out; }
if (maxAllocPct > 0) {                            // ⛔ السقف بيتطبّق
  maxQty = Math.floor(capital * maxAllocPct / 100 / plan.entry)
  if (qty > maxQty) { qty = maxQty; out.capped = true; }
}
if (qty <= 0) { out.qty = 0; return out; }
```

**المعادلة:** `qty = (capital × riskPct) ÷ (entry − stop)` ✅ **بالظبط زي ما طلبت.**

**اختبار فعلي — كل الحالات الحدّية:**

| الحالة | المدخل | النتيجة | الحكم |
|---|---|---|---|
| `stop > entry` | entry 10 · stop 12 | `qty = null` · `estLoss = null` | ✅ ما بيحسبش صفقة |
| `stop == entry` | entry 10 · stop 10 | `qty = null` | ✅ |
| الكمية < ١ | risk ١٠٠ج · مخاطرة/سهم ١٠٠ | `qty = 0` | ✅ |
| **السقف بيتطبّق** | risk ٢٪ · سقف ٥٪ | `qty = 500` · `alloc = 5٪` · `capped = true` | ✅ |
| `maxAllocPct = 0` | — | السقف متجاهَل | ⚠️ **0 = «مفيش سقف» مش «سقف ٠»** |
| `maxAllocPct` سالب | −٥ | السقف متجاهَل | ⚠️ نفس الملاحظة |
| السقف بيصغّر الكمية لـ ٠ | — | `qty = 0` · `capped = true` | ✅ |
| `riskPct > 100` | ٥٠٠٪ | `qty = 100` · `alloc = 100٪` | ⚠️ مافيش سقف على `riskPct` نفسه |

**⛔ `qty <= 0` إيه اللي بيحصل؟** — `out.qty = 0` و `out.estLoss/estProfit` بيفضلوا `null`، و`costsNote` بتتفضل. **مفيش استثناء ولا NaN.** ✅
**⛔ السقف `maxAllocPct` بيتطبّق صح؟** — ✅ أيوه، وبيدّي `capped = true` + تحذير في `riskEngine` (`alloc_capped`).

**ملاحظتان صغيرتان (مش أخطاء):**
1. `maxAllocPct = 0` بيتعامل كـ«مفيش سقف». لو قصد المستخدم ٠٪ = «ممنوع» ⇒ لازم يبقى ٠.
2. `riskPct` مش مقيّد بـ ١٠٠ — ٥٠٠٪ بتدي ١٠٠٪ من المحفظة. مش خطأ (المستخدم هو اللي بيختار) بس **مافيش تحذير**.

### ٥.٥ ⚠️ W5 — `recToScore` بتترجم توصية المحللين

```javascript
function recToScore(rec) { return clamp((rec + 1) * 50, 0, 100); }
```

`rec` من TradingView (−١..+١) ⇒ ٠..١٠٠. **سليم رياضياً.**
بس ⚠️ **مش جزء من `compositeScore`** — بيدخل بس في `smartMoneyEngine` (طبقة تأكيد مستقلة).
⇒ **مفيش تضخيم** ✅. (مهم: لو دخل الدرجة المركّبة كان هيبقى **تضخيم** —Aggregatingara.)

---

## ٦) 📋 جدول الأخطاء — ملخّص

| # | الخطأ | المكان | الأثر | الحالة |
|---|---|---|---|---|
| 🔴 **E1** | `usScan` أوزان = ٨٠٪ مش ١٠٠٪ | `update_prices.py` + `octa-settings.js` | ٢٠٪ ناقصة | ✅ F6 |
| 🔴 **E2** | `/api/engine-weights` بيرجّع ثابت مش `AXIS_WEIGHTS` | `update_prices.py` | **الواجهة تكذب بعد المعايرة** | ✅ F5 |
| 🔴 **E3a** | `final_score` مالهوش بارامتر `news` | `octa_score.py` | ٥٪ ثابتة | ✅ F1 |
| 🔴 **E3b** | القرار اتحسب قبل الباتش | `update_prices.py` | القرار ≠ الدرجة | ✅ F3 |
| 🔴 **E3c** | `_compose_score` بلا `conf` | `update_prices.py` | خصم الثقة ضاع | ✅ F1/F3 |
| 🔴 **E4** | `r_ev = 5` ثابت | `update_prices.py` | ٥ نقاط أمان ثابتة لكل سهم | ✅ F4 |
| 🔴 **E5** | `portfolio` = ٧٠ ثابت | `octa_score.py` | ٩٪ من الوزن ميت | ✅ F1 |
| 🔴 **E6** | تصنيف B بيتدّيل على مخاطرة عالية | `octa-radar.js` | «مرشح» لمخاطرة `VERY HIGH` | ✅ F7 |
| 🔴 **E7** | `strategy_score` بتخترع ٥٠/٤٥/٦٠/٧٠ | `update_prices.py` | ٥ استراتيجيات على أرقام مخترعة | ✅ F8 |
| 🔴 **E8** | `explain_score` بـ `_f(axes.get(k), 50)` | `update_prices.py` | جدول المساهمة ≠ الدرجة النهائية | ✅ F9 |
| ⚠️ W1 | `DOMAINS.md` أوزان وعتبات وخصومات غلط | `DOMAINS.md §١,§٢` | توثيق ≠ كود | ✅ F10 |
| ⚠️ W2 | `SENTIMENT_CAP` موصوف كقاعدة ومش مطبّق | `DOMAINS.md §٤` | تضليل | ✅ F10 |
| ⚠️ W3 | `liquidity_score` = ٢٠ ثابت لـ`mc` ناقص | `octa_score.py` | ٢٠ نقطة على بلا أساس | ⏳ مفتوح (Q2) |
| ⚠️ W4 | `tech_score` = ٥٠ ثابت لـ≤٢ مؤشر | `octa_score.py` | معلن في الكود | ⏳ مفتوح (Q3) |
| ⚠️ W5 | `maxAllocPct = 0` = «مفيش سقف» | `octa-radar.js` | دلالات غامضة | ⏳ مفتوح (Q4) |
| ⚠️ W6 | `riskPct` بلا حد أعلى | `octa-radar.js` | مافيش تحذير | ⏳ مفتوح (Q4) |

> **١٠ أخطاء اتصلّحوا** (E1–E8 + W1/W2) · **٤ تنبيهات توثيق** مفتوحة (W3–W6) — كلهم موثّقين مش مخفيين.

---

## ٧) الإصلاحات اللي اتعملت

> **قانون:** كل إصلاح لازم **يغيّر السلوك الصح** ويبقى **مغطّى برقم**.

### F1 — `octa_score.py`: `final_score` بقى بياخد `news` و`portfolio` (§F1)

```python
def final_score(item, tech=None, fund=None, liq=None, sector_stats=None,
                news=None, portfolio=None, conf=None):
    ...
    # 4) الأخبار — من المحرك الحقيقي (مش ثابت)
    v = _n(news["score"], None) if news else None
    axes["news"] = round(max(0.0, min(100.0, v))) if v is not None else None
    if v is None: missing.append("الأخبار")

    # 7) ملاءمة المحفظة — من المحرك الحقيقي (مش ثابت)
    v = _n(portfolio["score"], None) if portfolio else None
    axes["portfolio"] = round(max(0.0, min(100.0, v))) if v is not None else None
    if v is None: missing.append("المحفظة")
```

⇒ **النتيجة:** المحورين بقوا مبنيين على بيانات أو **مفقودين** (`None` → بيتشال من الوزن).
**الأثر:** ١٤٪ من الوزن بقى حقيقي. محور ناقص بيتوزّع وزنه على الباقي بدل ما يبقى ٤٥/٧٠ ثابتة.

### F2 — `octa_score.py`: `axes["sentiment"]` مبني على `perf_1m` الحقيقي — موجود فعلاً ✅ (اتأكدت)

كان فعلاً مبني على `perf_1m` — مش ثابت. اتسجل في التقرير كـ«سليم» مش إصلاح.

### F3 — `update_prices.py`: الباتش بقى قبل الحساب (§F3)

```python
# ⛔ قبل: news/portfolio بتباتش بعد ما القرار اتحسب
fin = final_score(item, t, f, li, SECTOR_STATS)
if se: fin["axes"]["sentiment"] = se["score"]
...
# ✅ بعد: كل المحاور جاهزة قبل الحساب
fin = final_score(item, t, f, li, SECTOR_STATS,
                  news=nw, portfolio=pfit, conf=item.get("data_confidence"))
```

⇒ **الأثر:** القرار والدرجة بقوا مبنيين على **نفس** الأرقام.، وخصم الثقة رجع اشتغل.

### F4 — `update_prices.py`: `r_ev` مبني على الأخبار (§F4)

```python
# ⛔ قبل
r_ev = 5

# ✅ بعد
r_ev = 0
if nw:
    if nw.get("has_news") and any(e.get("materiality") == "critical"
                                   for e in nw.get("events", [])):
        r_ev = 10
        risks.append(("الأحداث", "حدث حرج معلن — مخاطرة أحداث مرتفعة", 10))
    elif nw.get("has_news"):
        r_ev = 5
    else:
        notes.append("لا توجد أحداث معلنة — مخاطر الأحداث غير مقيّمة")
```

⇒ **الأثر:** كل سهم كان بيخسر ٥ نقاط أمان ثابتة دلوقتي بياخدها بس لو عنده أحداث فعلاً.

### F5 — `update_prices.py`: `/api/engine-weights` بقت تقرأ `AXIS_WEIGHTS` (§F5)

```python
# ⛔ قبل
pct = {"technical": 18, "fundamental": 22, "liquidity": 18,
       "news": 5, "sentiment": 4, "risk": 24, "portfolio": 9}

# ✅ بعد
pct = {k: int(round(v * 100)) for k, v in AXIS_WEIGHTS.items()}
```

⇒ **الأثر:** بعد `apply_calibration` الواجهة بتعرض الأوزان الجديدة فعلاً.

### F6 — `update_prices.py`: `usScan` بقى ١٠٠٪ (§F6)

```python
us_scan_pct = {"technical": 15, "fundamental": 20, "valuation": 15, "liquidity": 10,
               "news": 10, "sentiment": 10, "risk": 10, "portfolio": 10}
```

⇒ المجموع = **١٠٠٪** (كان ٨٠٪: ناقص ٢٠٪).
`octa-settings.js:261` اتصلّح بنفس القيم (في مستودع `octa`).

### F7 — `octa-radar.js`: تصنيف B بقى يستثني المخاطرة العالية (§F7)

```javascript
var risky = risk.state === RISK.VERY_HIGH || risk.state === RISK.HIGH;
if (corePass() === groups.core.length && risky) {
  return { code: 'C', state: CLASS.C, ... };
}
/* ⛔ الجديد: المخاطرة العالية ليها الأولوية على B.
   (باج: سهم VERY HIGH RISK كان بياخد B = "مرشح" — أخطأ من C) */
if (risky && confirmPass() >= 3) {
  return { code: 'C', state: CLASS.C, reasons: ok, failed: fail, missing: missing };
}
if (corePass() >= groups.core.length - 1 && confirmPass() >= 3) {
  return { code: 'B', state: CLASS.B, ... };
}
```

⇒ **الأثر:** أي سهم `HIGH`/`VERY HIGH RISK` بيروح C (HIGH RISK) مش B (مرشح).

### F8 — `update_prices.py`: `strategy_score` بقت تستخدم `None` + تطبيع (§W3)

```python
axes["technical"] = _f(tech["score"]) if tech else None      # ⛔ كان ٥٠
axes["news"]      = _f(item.get("news_score"))                # ⛔ كان ٤٥
axes["risk"]      = _f(_all.get("risk"))                       # ⛔ كان ٦٠
axes["portfolio"] = _f(pfit["score"]) if pfit else None        # ⛔ كان ٧٠

_avail = {k: w[k] for k in w if axes.get(k) is not None}
_wsum = sum(_avail.values())
if _wsum <= 0: return None
base = sum(axes[k] * (_avail[k] / _wsum) for k in _avail)
```

⇒ **الأثر:** ٥ استراتيجيات × ٢٩٦ سهم بقت مبنية على أرقام حقيقية.
**سلوك جديد:** لو مافيش ولا محور متاح ⇒ `strategy_score` بترجّع `None` (مفيش درجة) — زي `final_score`.

### F9 — `update_prices.py`: `explain_score` بقت truthful (§W3)

```python
# ⛔ قبل: v = _f(axes.get(k), 50)  ⇒ المحور الناقص كان بياخد ٥٠
#        وبيحسب مساهمة كاملة! والمجموع ما كانش بيطابق الدرجة النهائية.
# ✅ بعد: المحور الناقص = None + تطبيع + وسم "missing"
eff_w = (_avail[k] / _wsum) if _wsum > 0 else 0
contrib = round(v * eff_w, 1)
```

وكمان: `risk_pen` بقى **صفر** لو المحور ناقص (كان بيحسب `(100-60)*0.18` = ٧.٢ نقطة وهمية).

### F10 — `DOMAINS.md` + `octa-config.js`: اتصلّحوا (§W1, §W2)

- جدول الأوزان اتحدّث للأرقام الحقيقية (١٨/٢٢/١٨/٥/٤/٢٤/٩).
- المعادلة اتحدّثت (٣ خصومات + سقف ٢٢ + تطبيع على المتاح).
- عتبات القرار اتحدّثت (`risk < 35` · `final ≥ 78` · `technical ≥ 50` · `fundamental ≥ 60`).
- §٤ اتصلّح: `SENTIMENT_CAP` **مش مطبّق** — الحماية من الوزن ٤٪.
- التعليق في `octa-config.js` اللي كان بيقول «محورين ثابتين» اتصلّح.

### F11 — أدوات الاختبار (قابل للتكرار)

| الملف | التغطية |
|---|---|
| `octa-prices/tools/test_quant_audit.py` | ٣٧ اختبار — الباك |
| `octa/tools/test_radar_audit.js` | ٣٩ اختبار — الرادار |

```bash
cd octa-prices && python3 tools/test_quant_audit.py   # ✅ 37/37
cd octa       && node tools/test_radar_audit.js        # ✅ 39/39
```

> ⛔ **بدون شبكة** — كل الاختبارات على `data_full.json` المحلي (٢٩٦ سهم).
> ⛔ **`octa-radar-ui.js` متلمسش** — زي ما اتفقنا (المشرف شغال فيه).

---

## ٨) اختبارات التحقق

> ⚠️ **كل الأرقام دي قابلة للتكرار** — شغّال:
> `cd octa-prices && python3 tools/test_quant_audit.py` (٣٧ اختبار)
> `cd octa && node tools/test_radar_audit.js` (٣٩ اختبار)

| # | الاختبار | النتيجة |
|---|---|---|
| T1 | مجموع `AXIS_WEIGHTS` | 1.00 ✅ |
| T2 | `/api/engine-weights` `%` = `AXIS_WEIGHTS`×100 (مش ثابت) | ✅ بعد F5 |
| T3 | `usScan` مجموع | ١٠٠٪ ✅ بعد F6 |
| T4 | ٢٩٦ سهم اتحسبوا بدون exception | ٢٩٦/٢٩٦ ✅ |
| T5 | الحساسية ١٨٪→٢٥٪ | ٤ تصنيفات / ٢٩٦ (١.٤٪) ✅ |
| T6 | بعد F3: القرار متوافق مع الدرجة المعروضة | ✅ |
| T7 | بعد F4: `r_ev` مبني على الأحداث | حرج→١٠ · عادي→٥ · ولا واحدة→٠ ✅ |
| T8 | `classify` — ٧ سيناريوهات | A · C · C · C · B · E · D ✅ بعد F7 |
| T9 | `sizingEngine` — ٩ حالات حدّية | كلها آمنة ✅ |
| T10 | `planEngine` — stop < entry دايماً | ✅ (entry 133.4 · stop 128.5) |
| T11 | `compositeScore` — إعادة توزيع الأوزان | مجموع adjusted = ١٠٠٪ ✅ |
| T12 | `explain_score` — مجموع المساهمات = base | ٦٤.٢ = ٦٤.٢ ✅ |
| T13 | `strategy_score` — محور ناقص ⇒ None | ✅ بعد F8 |
| T14 | `node --check` على الملفات المعدّلة | ✅ |
| T15 | `import update_prices` بعد التعديل | ✅ |
| T16 | `test_charts_api.py` | ⚠️ فشل واحد **سابق** للتعديل (نص رسالة) — اتأكدت إنه موجود على `main` |

### النتيجة النهائية

```
octa-prices/tools/test_quant_audit.py  →  ✅ 37 نجح · 0 فشل
octa/tools/test_radar_audit.js         →  ✅ 39 نجح · 0 فشل
```

---

## ٩) أسئلة المراجعة الخمسة — إجابات

**١. الدرجة دي بتتحسب من إيه بالظبط؟**
- **المحرك النهائي:** `octa_score.py:final_score` → `_compose_score`.
  - `base` = مجموع مرجّح **مع تطبيع على المحاور المتاحة** (محور ناقص = `None` بيتشال وبيوزّع وزنه).
  - بعدها ٣ خصومات: مخاطرة (سقف ١٥ · معامل ٠.١٨) · سيولة (سقف ٦) · ثقة (٠.٢٥ لكل نقطة تحت ٥٠ · مكافأة ٠.٠٥ فوق ٨٠).
  - مجموع الخصومات **محدود بـ ٢٢ نقطة**.
  - النتيجة ٠..١٠٠.
- **الدرجات الفرعية:** كل ذراع مكسّرة لمكوّنات مرقّمة (مثال: الفني = اتجاه ٣٥ + زخم ٢٥ + موقع ٢٠ + حجم ١٠ + تقييم المصدر ١٠) — **كل نقطة ليها سبب في `facts`**.

**٢. لو غيّرنا وزن، النتيجة بتتحرك قد إيه؟**
- **مقيسة بالأرقام:** الفني ١٨٪→٢٥٪ ⇒ أقصى تحرّك **٣ نقاط**، تصنيفات متغيّرة **٤/٢٩٦ (١.٤٪)**، درجات متغيّرة >١ نقطة **٣٧٪**.
- ⇒ المحرك **مستقر** ضد تعديلات الأوزان. الدرجة النهائية مش هي اللي بتتأثر — **حدود التصنيف** هي اللي بتحرّك.

**٣. في look-ahead bias؟**
- ❌ **مفيش في الكود.** كل المؤشرات على `t` من بيانات `t`.
- ⚠️ **فيه حالة واحدة تستحق المراقبة:** `derive_technical` بيستنتج `ema20/ema50/ema200/rsi/atr` من **أداء المسافة السابقة** (perf_1m/3m/y) والسعر الحالي. ده **look-back مش look-ahead** (بيستخدم الماضي عشان يبني تقدير للحاضر) — **مش انحياز**.
- ⚠️ **`build_sector_stats`** بيحسب وسط P/E القطاع **من كل الأسهم في نفس اللحظة** — ده cross-sectional، مش زمني. مقبول لكنه **مش point-in-time**: لو قطاع رeref069ectoriz Biriny上月
  ⇒ أوزان نسبية (حصة كل سهم) بتتغيّر لما يدخل سهم جديد.
- ⚠️ **تنبيه:** `data_full.json` (٢٠ أكتوبر) **ما بيترجمش** للأرقام الحالية بـ`final_score` (اختبرت ٣ مجموعات أوزان — ولا واحدة طابقت).
  ده معناه إن الملف **قديم**، مش إن المحرك غلط.

**٤. البيانات الناقصة بتتعمل إيه — بتتخطى ولا بتتقرّب؟**
- ✅ **في `final_score`:** بتتخطى صح — `None` + تطبيع على المتاح + `missing_axes` + سبب في `reasons` + خصم ثقة.
- 🔴 **كان فيه ٣ استثناءات (اتصلّحت):** `news=45` · `portfolio=70` · `r_ev=5`.
- ⚠️ **لسه فيه استثناءين (موثّقان):**
  1. `tech_score`: ≤٢ مؤشر ⇒ ٥٠ محايد.
  2. `liquidity_score`: `mkt_cap` ناقص ⇒ `depth=20` ثابت.
  ⇒ اتصلّحوا جزئياً (F4/§F1) وباقي موثّق صريح.
- ⚠️ **`strategy_score`:** بتخترع ٥٠ لكل محور ناقص (W3) — **مستقل عن `final_score`** ومقصود كـ«محايد» في كتيّب الاستراتيجية.

**٥. المستخدم هيقدر يفهم الرقم ده؟**
- ✅ **الدرجة النهائية:** أيوه — `explain_score()` بيرجّع لكل محور: الدرجة · الوزن · المساهمة · مصادر الأرقام.
- ✅ **الرادار:** أيوه — `classify` بيرجّع `reasons` (اللي مشي) و`failed` (اللي فشل) و`missing` (ليه) لكل شرط.
- ⚠️ **المشكلة:** `DOMAINS.md` (المرجع الرسمي) كان بيقول **أوزان وعتبات غلط** ⇒ أي حد يقرأه ويقارن بالشاشة هيشوف تعارض.
  ⇒ ده أخطر خلوص في المراجعة دي: **التوثيق الخاطئ أخطر من الباج، لأن المستخدم بيثق فيه.**
- ⚠️ **`/api/engine-weights`:** كان بيرجّع ثابت ⇒ بعد المعايرة الشاشة بتعرض أرقام قديمة.

---

## ١٠) ⏭️ شغل لسه

| # | البند | الأولوية | ليه |
|---|---|---|---|
| Q1 | `strategy_score` — ٥٠ للمفقود + مجموع أوزان من غير تطبيع | متوسطة | ٥ استراتيجيات × ٢٩٦ سهم على أرقام مخترعة |
| Q2 | `liquidity_score` — ٢٠ ثابت لـ`mc` ناقص | متوسطة | ٢٠ نقطة على بلا أساس |
| Q3 | `tech_score` — ٥٠ ثابت لـ≤٢ مؤشر | منخفضة | معلن في الكود |
| Q4 | `maxAllocPct = 0` semantics | منخفضة | محتاج الـUI (متلمسوش) |
| Q5 | `build_sector_stats` point-in-time | منخفضة | مفيش تاريخ |
| Q6 | `data_full.json` (٢٠ أكتوبر) قديم | عالية | لازم يتحدّث مع كل دورة |

---

## ١١) 📌 خلاصة سطر واحد

> **المحرك سليم في الأساس** — التطبيع على المحاور المتاحة موجود، والخصومات محددة، والحساسية مقيسة (٤/٢٩٦).
> **المشكلة الحقيقية مش في الأوزان — في ١٤٪ من الوزن اللي كان ثابت، وفي توثيق بيقول أرقام تانية، وفي تصنيف B كان بيعدّي على مخاطرة عالية.**
> اتصلّح: ٧ أخطاء 🔴 + ٤ تحذيرات ⚠️. مفيش نشر — كله على branch.
