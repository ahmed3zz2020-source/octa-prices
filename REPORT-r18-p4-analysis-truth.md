# مراجعة الجولة ١٨ — R18-P4: **صدق محرّك التحليل** (٧ بنود)

> نسخة مختصرة من التقرير الكامل: `/workspace/output/OCTA-ROUND18-EVIDENCE/reports/p4-analysis-truth.md`
> الشجرة: `/workspace/.wt_p4` — الفرع `review/r18-p4-analysis` — الأساس `235cc1b`
> ⛔ مافيش push · مافيش دمج · `main` ما اتمسش · مافيش نشر · مافيش شبكة · مافيش تكلفة

## البنود السبعة

| # | البند | الحالة | الأرقام (قبل ⇐ بعد) | المكان |
|---|---|---|---|---|
| ① | MD-049 / AZ21-RISK-UNKNOWN (P1) | ✅ مُصلَح | `safety_score` 95 ⇐ **None** · `risk_level` «منخفض» ⇐ **«غير متاح»** · `risk_status` (مافيش) ⇐ **`insufficient_data`** · ومع بيانات: 51/49/«مرتفع» ⇐ **نفس القيم** | `update_prices.py:7945` (`risk_engine`) |
| ② | MD-050 / AZ21-SENT-PCT (P2) | ✅ مُصلَح | «(200% مقابل 5%)» ⇐ **«(2% مقابل 5%)»** | `update_prices.py:7751` (`sentiment_engine`) |
| ③ | MD-054 / AZ24-WATCH-DUP (P1) | ✅ مُصلَح | ٣ منبهات ⇒ **٩ صفوف** ⇐ **٣ صفوف** · `w_add` في القراءة ٣ ⇐ **٠** | `update_prices.py:14528` (`_octa_watch_get`) |
| ④ | MD-054b / AZ24-WATCH-PERSIST (P1) | ✅ مُصلَح | `{ok:true}` ⇐ **`{ok:false,saved:false,error:…}` + 500** | `update_prices.py:14616` (`_octa_watch_post`) + `:11303` (شقيق `POST /api/portfolio`) |
| ⑤ | AZ24-PORTFOLIO-SHARED / SEC-015 (P1+أمني) | ✅ مُصلَح | زائر: ملاءمة على المحفظة العامة (`score=58`) ⇐ **401 بلا ملاءمة** · المستخدم: `global` ⇐ **`user`/`user_portfolio`** · مافيش محفظة: «70 محايد» ⇐ **رد صريح** | `update_prices.py:11340` (`portfolio_fit_api`) |
| ⑥ | MD-052 / AZ22-EXPLAIN-DIVERGES (P1) | ✅ مُصلَح | فجوة (الشرح − إعادة التركيب) **24.1** ⇐ **0.0** | `update_prices.py:8268` (`explain_score`) · `:11469` (`explain_api`) · `octa_score.py:553` (`_compose_score`) |
| ⑦ | MD-034 / AZ25-BACKTEST-DAYS (P1) | ✅ مُصلَح | `days_back=3` ⇒ نافذة **50 يوم** ⇐ **مافيش نافذة** · 30 ⇒ `[50,20]` ⇐ **`[20]`** · 90 ⇒ `[50,20]` ⇐ **`[50,20]`** | `update_prices.py:9100` (`bt_evaluate`) |

⛔ **مافيش بند «سليم أصلاً»** — السبعة كلهم عيوب مثبَتة على الأساس ومُصلَحة.

## المبادئ المحترمة

- ⛔ **مافيش تغيير في أي وزن أو عتبة** في محرّك التقييم ولا في محرّك المخاطر:
  `AXIS_WEIGHTS` · عتبات `_compose_score` (١٥ · ٦ · ٢٢) · أوزان المخاطر (٢٠/١٥/٢٠/١٥/١٥/١٠/٥) ·
  عتبات مستوى الخطورة (٢٥/٤٥/٦٥) — **كلها زي ما هي** (مُتحقَّق باختبار
  `TestRiskEngineTruth::test_weights_and_thresholds_unchanged`).
- ⛔ التعديل في **الحالة والوصف** (بنود ①②③④⑤⑦) + **استخدام نفس المحرك** مش إعادة كتابته (بند ⑥).
- 📌 البند ⑥: `octa_score._compose_score` بقى **بيرجّع المساهمات الفعلية** (إضافة للمفتاح
  `contributions` بس) — مافيش تغيير في أي رقم ولا عتبة ولا وزن.

## الدليل

- `test_round18_analysis_truth.py` — **٢٧ اختبار** (٧ بنود) — ✅ ٢٧/٢٧ بعد الإصلاح،
  و**٢٠ فشل** على الأساس (`evidence/p4_negative_base.log`).
- براهين المراجع المستقلة (AZ): **٦ براهين فاشلة قبل ⇒ ٠ بعد**
  (`evidence/p4_az_proofs_before.log` · `evidence/p4_az_proofs_after.log`).
- لا ارتجاع: كل ملفات الاختبار في الشجرة (٥٦ ملف) — الفشل الوحيد trio ملفات
  (batch02 · p0 · signup_flow) بيحصل **نفسه** على الأساس (متغيّر بيئة
  `STAGE_ADMIN_TOKEN` ناقص) — `evidence/p4_regression.log` · `evidence/p4_regression_base.log`.

## ⛔ توثيق لازم يتقرا (البند ٧)

`/api/backtest` بيعتمد **forward tracking** (نسجّل ترتيب اليوم ونقيس بعد ٣+ أيام على **بيانات
لحظية**) ⇒ ده **مش تقييم تاريخي شامل**: مافيش تاريخ أداء مُراجَع، والقياس نافذة واحدة بس.
الرقم بقى صح **من جوه النافذة المطلوبة** (بعد البند ⑦) بس هو مؤشر تشخيصي مش أداء تاريخي مُثبت.
اتضاف `caveat` صريح في رد `/api/backtest`.
