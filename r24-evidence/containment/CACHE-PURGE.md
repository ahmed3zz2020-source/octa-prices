# CACHE-PURGE — إخراج النسخة المخزّنة من جسم التسريب

> **حزمة الاحتواء · الجولة ٢٤ ⭐ · الخطوة ②**
> الـ endpoint: `POST /zones/{zone_id}/purge_cache` ⭐
> التكلفة: **٠$** ⭐ · مفيش نشر ⭐ · ⛔ كتابة حيّة ⭐ (ينفّذها المالك ⭐).

---

## ١. ليه المسح ضروري ⭐

الردود كانت `cf-cache-status: HIT` ⭐ ⇒ جسم التسريب (١,٤٦٠,١٦٤ بايت ⭐)
قاعد في كاش كل مراكز Cloudflare ⭐.

* مسح الكاش **مش** ضابط أمني ⭐ (هو بيشيل نسخة ⭐).
* لكنه بيخلّي نسخة **قديمة** من كود التطبيق ما تقدرش ترجّع الجسم القديم ⭐
  من الكاش ⭐ بعد أي تراجع ⭐ ⭐.

⇒ **الترتيب مهم** ⭐: القاعدة على الحافة ⭐ **قبل** المسح ⭐، والمسح
**مرة ثانية** بعد أي نشر أو تراجع ⭐.

---

## ٢. الإجراء اليدوي من لوحة التحكم ⭐ (من غير أي توكن ⭐)

```
①  dash.cloudflare.com ⭐ →  اختار المنطقة ⭐ (octashares.com ⭐)
②  من الشريط الجانبي ⭐:  Caching ⭐ →  Configuration ⭐
③  زقّة ⭐:  Purge Cache ⭐
④  اختار ⭐:  Custom Purge ⭐
⑤  الحقل ⭐:  URLs ⭐ ⭐ ⇒  اكتب ⭐ (سطر لكل رابط ⭐):
        https://octashares.com/data/opp_snapshot.json ⭐
        https://octashares.com/data/alpha_snapshot.json ⭐
⑥  زقّة ⭐:  Purge ⭐
⑦  (اختياري ⭐):  نفس الزقّة ⭐ →  Purge Everything ⭐ ⭐
        ⛔ استخدمها مرة واحدة ⭐ وبس ⭐ ⭐
        ⛔ بتعمل الموقع بارد ⭐ وبتضغط على الأصل ⭐ ⭐
```

⛔ **الأفضل** تفضيل مسح الـURLs المحدّدة ⭐ على `Purge Everything` ⭐.

---

## ٣. المسح بالـAPI ⭐ (اختياري ⭐ — محتاج توكن ⭐)

| العملية | الـ endpoint | أقل صلاحية | النطاق | الخطأ لو ناقصة |
|---|---|---|---|---|
| مسح روابط ⭐ | `POST /zones/{zone_id}/purge_cache` ⭐ | **`Cache Purge`** ⭐ | `zone_id` ⭐ | **403** ⭐ + **10000** ⭐ |

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/purge_cache" \
  --data '{"files":["https://octashares.com/data/opp_snapshot.json","https://octashares.com/data/alpha_snapshot.json"]}'
```

* المتوقع ⭐: HTTP 200 ⭐ و `{"result":{"id":"<uuid>"},"success":true}` ⭐.
* ⛔ 200 ⭐ معناه Cloudflare **قبّل** الطلب ⭐ — مش إن جسم معيّن اتمسح ⭐.
  التحقق الحقيقي هو §٤ ⭐.

⛔ **تصحيح على الجولة ٢٣** ⭐: الصلاحية سُمّيت «Zone Cache Purge» ⭐ ⇒
الاسم الرسمي ⭐ **`Cache Purge`** ⭐ (ونطاقها المنطقة ⭐) ⭐.

---

## ٤. التحقق ⭐ (قراءة فقط ⭐)

```bash
for u in /data/opp_snapshot.json /data/alpha_snapshot.json /data/egx30_history.json ; do
  printf "%-34s " "$u"
  curl -sSI --max-time 25 "https://octashares.com$u" \
    | tr -d '\r' | grep -iE "^(HTTP/|cf-cache-status|content-length)" | tr '\n' ' '
  echo
done
```

| المسار | المتوقع بعد المسح (وقبل القاعدة ⭐) |
|---|---|
| `/data/opp_snapshot.json` ⭐ | `cf-cache-status` = **MISS** ⭐ أو DYNAMIC/BYPASS ⭐ — ⛔ مش HIT ⭐ |
| `/data/alpha_snapshot.json` ⭐ | نفس ⭐ |
| `/data/egx30_history.json` ⭐ | 200 ⭐ و MISS ⭐ (طبيعي ⭐ — بيرجع HIT ⭐ تاني ⭐) |

⛔ بعد تطبيق قاعدة WAF ⭐ ⇒ الرد 404 ⭐ ⭐ (والحالة مش HIT ⭐) ⭐.

---

## ٥. متى المسح يتكرر ⭐

| الحدث | مسح تاني ⭐ |
|---|---|
| تطبيق قاعدة WAF ⭐ | نعم ⭐ |
| نشر أي نسخة جديدة ⭐ | نعم ⭐ |
| أي تراجع ⭐ | **نعم ⭐ (إجباري ⭐)** ⭐ |
| لو صيغة تسريب لسه موصلية ⭐ | نعم ⭐ + `Purge Everything` ⭐ مرة ⭐ |

---

## ٦. الأثر ⭐

| البند | الأثر |
|---|---|
| سرعة الموقع ⭐ | تمريرة `cache miss` ⭐ بسيطة ⭐ (بيرجع يتخزّن ⭐) ⭐ |
| الملفات السليمة ⭐ | ما بتتأثرش ⭐ |
| `Purge Everything` ⭐ | الموقع بارد ⭐ + ضغط على الأصل ⭐ |

⛔ **المسح مش قابل للتراجع** ⭐ — بس كاش بيتعاد بناؤه لوحده ⭐.
