# WAF-RULES — تسدّ تسريب اللقطات على الحافة (بلا نشر)

> **حزمة الاحتواء · الجولة ٢٤ ⭐ · الخطوة ①**
> النطاق: منطقة `octashares.com` ⭐ · الطور: `http_request_firewall_custom` ⭐
> التكلفة: **٠$** ⭐ · مفيش نشر ⭐ · مفيش تعديل كود ⭐.
> ⛔ **الخطوات دي كتابة حيّة على حسابك ⭐** — ينفّذها المالك ⭐.

---

## ١. ليه القاعدة دي إجبارية ⭐

النسخة المنشورة رقم **٢٣٦** فيها حارس المسار في كود الـWorker ⭐
(يرجّع ٤٠٤ ⭐ لكل صيغ التسريب ⭐). بس الحارس ده **كود** ⭐:

* أي نشر جديد ممكن يفقده ⭐.
* أي **تراجع** لنسخة **٢٣٥** بيشيله ⭐ ⇒ ⛔ التسريب بيرجع ⭐.
* القاعدة على **الحافة** ⇒ مش جزء من الحزمة ⭐ ⇒ **مستحيل** أي تراجع يغيّرها ⭐.

⇒ القاعدة هي اللي بيحوّل «التراجع آمن» من كلام لواقع ⭐.

---

## ٢. التحقق من الخطة ⭐ (لأنها بتغيّر التعبير ⭐)

```bash
export CLOUDFLARE_API_TOKEN='<token: Zone Read + Zone WAF Read>'
export ZONE_ID='<zone id of octashares.com>'

curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('plan=',d['result']['plan']['name'])"
```

* `Free` أو `Pro` ⭐ ⇒ استخدم تعبير `wildcard` ⭐ (§٣ ⭐).
* `Business` أو `Enterprise` ⭐ ⇒ تقدر تستخدم `matches` (ريجكس ⭐) ⭐ (§٤ ⭐).

---

## ٣. التعبير الجاهز (خطة Free ⭐ — بدون ريجكس ⭐)

```
(http.request.uri.path wildcard "*/data/*opp_snapshot.json*") or (http.request.uri.path wildcard "*/data/*alpha_snapshot.json*")
```

**انسخ السطر ده كما هو ⭐** — كل حاجة بين القوسين ⭐ (الاقتباس المزدوج ⭐
والشرطتين بــ `or` ⭐).

 ليه بيسدّ كل الصيغ المقاسة ⭐:

| الصيغة | ليه بتتقفل |
|---|---|
| `/data/opp_snapshot.json` | `*` الأول فاضي ⭐ |
| `/data/./opp_snapshot.json` | `*` الوسط بيبلع `.` ⭐ |
| `/data/x/../opp_snapshot.json` | `*` الوسط بيبلع `x/../` ⭐ |
| `/data//opp_snapshot.json` | `*` الوسط بيبلع `/` ⭐ |
| `/data/%6fpp_snapshot.json` | بترد ٣٠٧ ⭐ على المسار القياسي ⭐ ⇒ والمسار القياسي مقفول ⭐ |
| `/data/OPP_SNAPSHOT.JSON` | `wildcard` مش حسّاس لحالة الحروف ⭐ |
| `/data/opp_snapshot.json/` | `*` الأخير بيبلع `/` ⭐ |
| `/data/opp_snapshot.json?x=1` | الـquery مش جزء من المسار ⭐ |
| `/data/egx30_history.json` ⭐ | مفيش `*_snapshot.json` ⭐ ⇒ مش متأثر ⭐ |

---

## ٤. التعبير بالريجكس (Business / Enterprise ⭐ — اختياري ⭐)

```
((http.request.uri.path matches "(?i)^/data/(?:[^/]*/)*(?:opp|alpha)_snapshot\.json/?$") or (url_decode(http.request.uri.path) matches "(?i)^/data/(?:[^/]*/)*(?:opp|alpha)_snapshot\.json/?$"))
```

⛔ على Free ⭐ الـ`matches` **مش متاح** ⭐ ⇒ استخدم §٣ ⭐.

---

## ٥. الإجراء اليدوي من لوحة التحكم ⭐ (من غير أي توكن ⭐)

> ⛔ المسار والقوائم **ممكن تتغيّر** بين النسخ ⭐ — لو لقيت زقّة مختلفة ⭐
> وقّف ⭐ وارجع لتوثيق Cloudflare ⭐.

```
①  dash.cloudflare.com ⭐ → تسجيل الدخول ⭐
②  اختار المنطقة ⭐ (octashares.com ⭐) ⭐ من قائمة الحساب ⭐
③  من الشريط الجانبي ⭐:  Security ⭐ →  WAF ⭐ →  Custom rules ⭐
④  زقّة ⭐:  Create rule ⭐
⑤  الحقل ①:  Rule name ⭐  ⭐  اكتب ⭐:
        R24: block snapshot files under /data/ (path-normalisation safe) ⭐
⑥  الحقل ②:  Expression ⭐  ⭐ (Expression builder ⭐):
        Field     ⭐ :  URI Path ⭐
        Operator  ⭐ :  Wildcard ⭐
        Value     ⭐ :  */data/*opp_snapshot.json* ⭐
⑦  زقّة ⭐:  Add expression ⭐ ⭐ (أو  or  ⭐) ⭐ ⇒ شرط تاني ⭐:
        Field     ⭐ :  URI Path ⭐
        Operator  ⭐ :  Wildcard ⭐
        Value     ⭐ :  */data/*alpha_snapshot.json* ⭐
⑧  الحقل ③:  Action ⭐  ⭐ اختار ⭐:  Block ⭐
⑨  (اختياري ⭐):  Configure custom response ⭐ ⭐:
        Status code ⭐ :  404 ⭐
        Content type ⭐ :  application/json ⭐
        Content ⭐      :  {"ok":false,"error":"not-found","why":"snapshot_assets_blocked"} ⭐
⑩  زقّة ⭐:  Deploy ⭐
```

⛔ لو الـdashboard **مش** بيقبل الرد المخصّص ⭐ ⇒ سيب الرد الافتراضي ⭐
(٤٠٣ ⭐ مقبول ⭐ — المهم إن **المحتوى** راح ⭐) ⭐.

⛔ **لا** تفعل «Block with custom response» بإعداد مختلف ⭐ — الرد لازم
يكون **نفس بايتات** رد الـWorker ⭐ (حتى ما يعرف المهاجم ⭐ إن
البلوك من الحافة ولا من الكود ⭐) ⭐.

---

## ٦. الإجراءات بالـAPI ⭐ (اختياري ⭐ — محتاج توكن ⭐)

> ⛔ **ممنوع** في الجولة دي ⭐ — دي إجراءات المالك ⭐ لما يقدّم التوكن ⭐.

### ٦.١ أقل صلاحية ⭐

| العملية | الـ endpoint | أقل صلاحية | النطاق |
|---|---|---|---|
| إنشاء القاعدة ⭐ | `POST /zones/{zone_id}/rulesets/{ruleset_id}/rules` ⭐ | `Zone WAF Write` ⭐ | `zone_id` ⭐ |
| إنشاء ruleset ⭐ | `POST /zones/{zone_id}/rulesets` ⭐ | `Zone WAF Write` ⭐ | `zone_id` ⭐ |
| قراءة الـentry point ⭐ | `GET /zones/{zone_id}/rulesets/phases/http_request_firewall_custom/entrypoint` ⭐ | `Zone WAF Read` ⭐ | `zone_id` ⭐ |
| مسح الكاش ⭐ | `POST /zones/{zone_id}/purge_cache` ⭐ | `Cache Purge` ⭐ | `zone_id` ⭐ |
| تفعيل Access ⭐ | `POST /accounts/{account_id}/access/apps` ⭐ | `Access: Apps and Policies Write` ⭐ | `account_id` ⭐ |

⛔ الخطأ المتوقع لو الصلاحية ناقصة ⭐: **HTTP 403** ⭐ + رمز الخطأ
**10000** ⭐ (رسالة `Forbidden` ⭐) ⭐ — والرد الجديد فيه
`documentation_url` ⭐ بيقول بالظبط المسار المتروّض ⭐.
ورمز **9109** ⭐ (`Unauthorized to access requested resource` ⭐) ممكن
يظهر بدل 10000 ⭐ ⭐.

⛔ **تصحيح على حزمة الجولة ٢٣** ⭐:
* كان `/rulesets/phases/.../entry` ⭐ ⇒ الصحيح **`/entrypoint`** ⭐.
* كان `Zone Cache Purge` ⭐ ⇒ الاسم الرسمي **`Cache Purge`** ⭐.
* كان `Account Access Write` ⭐ ⇒ الصحيح **`Access: Apps and Policies Write`** ⭐.

### ٦.٢ التحقق بدون نشر (dry run ⭐)

```bash
RULESET_ID=$(curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rulesets/phases/http_request_firewall_custom/entrypoint" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['result']['id'])")

curl -sS -X POST \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rulesets/$RULESET_ID/rules?dry_run=true" \
  --data @rule.json
```

* المتوقع ⭐: HTTP 200 ⭐ و `success: true` ⭐ و **`result: null`** ⭐
  (لأن دي عملية تحقق ⭐ مش كتابة ⭐) ⭐.
* ⛔ أي خطأ في التعبير ⭐ ⇒ 4xx ⭐ ⇒ راجع §٣ ⭐ (على Free ⭐ متستخدمش
  `matches` ⭐ ولا `url_decode` ⭐ ⭐).

---

## ٧. التحقق بعد التفعيل ⭐ (قراءة فقط ⭐)

```bash
for p in /data/opp_snapshot.json /data/./opp_snapshot.json /data//opp_snapshot.json \
         /data/%6fpp_snapshot.json /data/x/../opp_snapshot.json \
         /data/opp_snapshot%2ejson /%64ata/opp_snapshot.json \
         /data/alpha_snapshot.json /data/./alpha_snapshot.json \
         /data/egx30_history.json /data/market_names.js /data/sahm_names_ar.json ; do
  printf "%-40s " "$p"
  curl -sS -o /dev/null -w "%{http_code} %{size_download}\n" "https://octashares.com$p"
done
```

* المتوقع ⭐: كل صيغ التسريب ⭐ ⇒ **404** ⭐ (أو 403 ⭐ — مقبول ⭐
  المهم إن المحتوى راح ⭐) ⭐.
* المتوقع ⭐: `/data/egx30_history.json` ⭐ و `/data/market_names.js` ⭐
  و `/data/sahm_names_ar.json` ⭐ ⇒ **200** ⭐.

⛔ لو أي صيغة رجّعت 200 ⭐ ⇒ **وقّف** ⭐ — القاعدة ما اتطبّقتش ⭐.

---

## ٨. التراجع عن **القاعدة** (ممنوع ⭐)

⛔ **ممنوع** حذف القاعدة ⭐ — حذفها = فتح التسريب ⭐.
لو القاعدة اتقفلت على حاجة مش مفروض ⭐ ⇒ **وسّع القاعدة** ⭐ (استثناء ⭐)
مش تحذفها ⭐. التفاصيل في `rollback-safe.md` ⭐ §٥ ⭐.

---

## ٩. الملفات ⭐

| الملف | الفكرة |
|---|---|
| `WAF-RULES.md` | هذا الملف ⭐ |
| `DATA-INVENTORY.md` (جولة ٢٣ ⭐) | إثبات إن التعبير ما بيلمسش ملف لازم ⭐ |
| `evidence/phase1_cloudflare_permissions.json` ⭐ | مصفوفة الصلاحيات ⭐ |
