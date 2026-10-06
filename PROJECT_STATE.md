# 🛡️ OCTA — سجل المشروع الدائم
**آخر تحديث:** 2026-10-07
**القاعدة:** الملف ده بيتقرأ **قبل** أي تعديل. لو فيه حاجة ناقصة — تمام نكمل. لو حاجة اتكسرت — نصلحها الأول.

---

## ✅ الحالة العامة

| | |
|:---|:---|
|.commit الحالي | `a52cd5a` |
| عدد الـ endpoints | 37 |
| أسطر الكود | ~4350 |
| الأسهم المحللة | 252 |
| المحاور الشغالة | 8 / 8 |
| نسبة الإنجاز | **85%** |

---

## ✅ المراحل المكتملة — **لا تعدل دي أبداً**

| # | المرحلة | الدالة | ملاحظة |
|:---:|---|---|:---|
| ١ | البيانات | `validate_value` · `_quality_of` · `facts_text` | 68 عمود، تحقق صارم |
| ٢ | الفني | `tech_score` · `derive_technical` | 43 مؤشر |
| ٣ | الأساسي | `fundamental_score` · `build_sector_stats` | مقارنة بالقطاع |
| ٤ | السيولة | `liquidity_score` | عمق/نشاط/تسييل/استقرار |
| ٥ | الأخبار | `news_engine` | 7 materiality levels |
| ٦ | المعنويات | `sentiment_engine` | CAP = 25% |
| ٧ | المخاطر | `risk_engine` | 7 فئات + عائد/خطر |
| ٨ | المحفظة | `portfolio_fit` | تركّز + تنويع |
| ٩ | النتيجة | `final_score` | مرجّح + خصومات بسقوف |
| ١١ | التفسير | `explain_score` | مساهمات + ناقص + باطل |
| ١٢ | الفرص | `opportunity_engine` | تراكم + ضغط |
| ١٣ | الترتيب | `rank_stocks` · `available_filters` | 8 فلاتر |
| ١٤ | الاستراتيجيات | `strategy_score` | 7 ملفات |
| ١٥ | الاختبار التاريخي | `bt_snapshot` · `bt_evaluate` | forward-tracking |
| ١٦ | اختبار الضغط | `stress_test` · `run_all_stress` | 7 سيناريوهات |
| ١٧ | المعايرة | `apply_calibration` | سجل كامل |

---

## 🎯 المرحلة ١٨ — اللي بنشتغل عليها دلوقتي

**لوحة التحكم الاحترافية:**
- صفحة واحدة فيها كل الأرقام
- توزيع المحاور على مستوى السوق
- أعلى/أسوأ الأداء
- حالة النظام (صحة البيانات، آخر تحديث)
- مقارنة مع السوق (alpha)
- نتيجة الاختبار التاريخي

**الهدف:** المستخدم يفتح الموقع ويشوف حالة النظام كلها فوراً.

---

## 📌 다음 المراحل

| # | المرحلة | الحالة |
|:---:|---|:---:|
| ١٨ | لوحة التحكم | 🔄 جاري |
| ١٩ | الفحص النهائي | ⬜ |

---

## 🚨 قواعد صارمة — ما تنكسرش

1. **قبل أي تعديل:** اقرأ هذا الملف
2. **قبل أي تعديل:** `cp update_prices.py update_prices.py.bak`
3. **بعد أي تعديل:** `python3 -c "import ast; ast.parse(open('update_prices.py').read())"`
4. **بعد أي تعديل:** تأكد إن الـ 15 دالة لسه موجودة
5. **مفيش amend متكرر** — كل تعديل في commit واحد
6. **لو في crash:** `git checkout update_prices.py` وارجع للنسخة الصح

---

## 🗂️ النسخ الاحتياطية المتاحة

| الملف | الحالة |
|:---|:---|
| `update_prices.py.bak_cal` | قبل المعايرة |
| `update_prices.py.bak_rank` | قبل المرحلة ١٣ |
| `update_prices.py.bak_opp` | قبل المرحلة ١٢ |
| `update_prices.py.bak4` | نسخة المرحلة الثانية |
| `git log` | كل الـ commits محفوظة |

---

## 📊 نقاط النهاية الـ 37

```
الأساسية:    /  ·  /api/prices  ·  /api/ticker  ·  /api/stocks
التحليل:     /api/technical/<code>  ·  /api/fundamental/<code>
             /api/risk/<code>  ·  /api/news/<code>  ·  /api/sentiment/<code>
             /api/intelligence/<code>  ·  /api/explain/<code>
             /api/opportunity/<code>  ·  /api/portfolio/fit/<code>
الترتيب:    /api/ranking  ·  /api/rank  ·  /api/filters  ·  /api/strategies
             /api/strategy/<code>/<strategy>  ·  /api/opportunities
الاختبار:    /api/backtest  ·  /api/stress  ·  /api/calibration
الأقسام:    /api/sector-stats  ·  /api/top-movers  ·  /api/heat
             /api/sector/<sector>  ·  /api/search/<q>
الأخرى:     /api/analyze  ·  /api/chat  ·  /api/dividends
             /api/dividends/stats  ·  /api/ai-status  ·  /api/diagnostic
             /api/portfolio
```

---

## 📌 معطيات المعايرة (v1.1)

```
فني        18%   أساسي      22%   سيولة      18%
أخبار      5%   معنويات     4%   أمان       24%   محفظة      9%
المجموع = 100% ✓
سقوف الخصومات: مخاطرة 15 · سيولة 6 · إجمالي 22
```

---

## ⚠️ آخر ٣ قرارات (مهمة — متغيرش إلا بدليل)

1. **لا نخترع بيانات** — لو المصدر ما رجعش، نقول "غير متاح"
2. **المعنويات ما تتحكمش** — الـ (CAP) عند 25% وما ينزلش
3. **forward-tracking مش backtest وهمي** — بنقيس من يوم الحاضر بصدق

---
*حدّثه مع كل commit جديد.*
