# R24 · المرحلة ١ — مصفوفة صلاحيات Cloudflare الأدنى

## العمليات

| العملية | الـ endpoint | أقل صلاحية | النطاق | الخطأ المتوقع |
|---|---|---|---|---|
| إنشاء قاعدة WAF (بلوك اللقطات) ⭐ | `POST /zones/{zone_id}/rulesets/{ruleset_id}/rules ⭐` | `Zone WAF Write ⭐` | zone_id ⭐ (نطاق المنطقة) ⭐ | 403 10000 |
| مسح الكاش ⭐ | `POST /zones/{zone_id}/purge_cache ⭐` | `Cache Purge ⭐` | zone_id ⭐ (نطاق المنطقة) ⭐ | 403 10000 |
| تفعيل Cloudflare Access (تطبيق + سياسة) ⭐ | `POST /accounts/{account_id}/access/apps ⭐` | `Access: Apps and Policies Write ⭐` | account_id ⭐ (نطاق الحساب ⭐ — مش المنطقة ⭐) ⭐ | 403 10000 |
| قراءة معرّف المنطقة (للتحضير ⭐) ⭐ | `GET /zones?name=octashares.com ⭐` | `Zone Read ⭐` | zone_id ⭐ | 403 10000 |

## تصحيحات على حزمة الجولة ٢٣

- **WAF-RULES.md §6.2 (خط جولة ٢٣) ⭐** ⭐: كان `GET /zones/$ZONE_ID/rulesets/phases/http_request_firewall_custom/entry ⭐` ⭐ ⇒ بقى `GET /zones/$ZONE_ID/rulesets/phases/http_request_firewall_custom/entrypoint ⭐` ⭐ (المسار الرسمي ⭐ «entrypoint» ⭐ («entry» مش مسار مستند ⭐) ⭐) ⭐
- **WAF-RULES.md §6.1 (خط جولة ٢٣) ⭐** ⭐: كان `POST .../rulesets/phases/http_request_firewall_custom/entry?dry_run=true ⭐` ⭐ ⇒ بقى `POST .../rulesets/{ruleset_id}/rules?dry_run=true ⭐ (أو POST .../rulesets?dry_run=true ⭐) ⭐` ⭐ (المعامل dry_run بيتقبل على عمليات POST/PUT/PATCH/DELETE ⭐ المدعومة ⭐ ⇒ لازم يكون على نفس عملية التعديل ⭐) ⭐
- **CACHE-PURGE.md §2.0 (خط جولة ٢٣) ⭐** ⭐: كان `Zone Cache Purge ⭐` ⭐ ⇒ بقى `Cache Purge ⭐` ⭐ (الاسم الرسمي ⭐ (نطاق المنطقة ⭐) ⭐) ⭐
- **ACCESS.md + تقرير الجولة ٢٣ ⭐** ⭐: كان `Account Access Write ⭐` ⭐ ⇒ بقى `Access: Apps and Policies Write ⭐` ⭐ (الاسم الرسمي ⭐ (نطاق الحساب ⭐) ⭐) ⭐
- **WAF-RULES.md §6.1 ⭐** ⭐: كان `التوقع: result.rules[0].action == 'block' ⭐` ⭐ ⇒ بقى `مع dry_run ⭐ الرد بيكون result: null ⭐ (التحقق بيشتغل ⭐ والكتابة ما بتتمش ⭐) ⭐` ⭐ (سلوك dry_run الموثّق ⭐: العمليات اللي بترجّع ٢٠٠ بترجّع result: null ⭐ ⇒ الفحص بيبقى على success والرسالة ⭐) ⭐

## تعبير قاعدة WAF (خطة Free ⭐)

```
(http.request.uri.path wildcard "*/data/*opp_snapshot.json*") or (http.request.uri.path wildcard "*/data/*alpha_snapshot.json*")
```

- ⛔ مفيش أي كتابة حيّة ⭐ ⭐
- ⛔ مفيش أي توكن ⭐ ⭐