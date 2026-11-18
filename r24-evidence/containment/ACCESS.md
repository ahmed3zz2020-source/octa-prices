# ACCESS — قفل لوحة الإدارة خلف Cloudflare Access

> **حزمة الاحتواء · الجولة ٢٤ ⭐ · الخطوة ③**
> الهدف: لوحة الإدارة (مضيف `octa-mgmt`) ما تفتحش لزائر ⭐.
> التكلفة: **٠$** ⭐ · مفيش نشر ⭐.

---

## ١. الحالة المقاسة ⭐

| الفحص | النتيجة |
|---|---|
| لوحة الإدارة بدون جلسة ⭐ | **200** ⭐ ⇒ **مكشوفة** ⭐ ⭐ |
| نداء الـAPI بتطبيق Access ⭐ | مرفوض بـ **«not_enabled»** ⭐ ⭐ |

⛔ **«not_enabled» مش مشكلة توكن** ⭐ — الحساب نفسه **مش مفعّل** Access ⭐
⇒ ⛔ توكن جديد **مش هيعالج** الموضوع ده ⭐ ⇒ لازم تهيئة الحساب ⭐ (§٣ ⭐).

⛔ لما تتبعت نداءات الـAPI بتوكن فيه صلاحية `Access: Apps and Policies
Write` ⭐ ⇒ **403** ⭐ + رمز **10000** ⭐ ⇒ ساعتها بس تهيئة الحساب ⭐.

---

## ٢. التطبيق (إجراء يدوي ⭐ — من غير أي توكن ⭐)

```
①  dash.cloudflare.com ⭐ →  Zero Trust ⭐
②  لو ظهرت شاشة "Get started" ⭐ ⭐ ⇒ الحساب مش مفعّل ⭐ ⇒ كمّل §٣ ⭐
③  من الشريط الجانبي ⭐:  Access ⭐ →  Applications ⭐
④  زقّة ⭐:  Add an application ⭐
⑤  اختار ⭐:  Self-hosted ⭐
⑥  الحقول ⭐:
        Application name (domain) ⭐ :  octa-mgmt.ahmed3zz2020.workers.dev ⭐
        Session duration ⭐            :  24 hours ⭐ (أو أقل ⭐)
⑦  زقّة ⭐:  Add a policy ⭐
⑧  Policy name ⭐ :  only-me ⭐
⑨  Action ⭐      :  Allow ⭐
⑩  Include ⭐     :  Emails ⭐ ⭐ ⇒  اكتب بريدك ⭐ (بريد واحد ⭐)
⑪  (اختياري ⭐):  Add a second rule ⭐ ⭐:
        Action ⭐ :  Deny ⭐
        Include ⭐:  Everyone ⭐ ⭐ ⇒ ده يمنع أي حد تاني ⭐
⑫  زقّة ⭐:  Save ⭐
```

⛔ **عمل سياستين أهم من سياستة واحدة** ⭐:Allow لإيميلك ⭐ + Deny
للجمهور ⭐. سياستة Allow وحدها معناها أي زائر بياخد Challenge ⭐ — مش
قفل ⭐.

⛔ **ما تفتحش** صفحة تسجيل الدخول أو التطبيقات العامة ⭐ — الـAccess
على **مضيف لوحة الإدارة** ⭐ بس ⭐.

---

## ٣. تهيئة الحساب (لو «Get started» ظهر ⭐)

```
①  Zero Trust ⭐ →  Get started ⭐
②  اختار الخطة ⭐ (مجانية ⭐) ⭐
③  Team name ⭐ :  octa ⭐  (أو أي اسم ⭐)
④  كمّل الخطوات ⭐ (الدفع ⭐ = ٠$ ⭐ على الخطة المجانية ⭐)
⑤  بعد التهيئة ⭐ ⇒ ارجع لـ§٢ ⭐
```

⛔ التهيئة **مش** تنشر كود ⭐ ومش بتغيّر الموقع ⭐ — بتغيّر حساب فقط ⭐.

---

## ٤. التحقق ⭐

```
①  افتحIncognito ⭐ (متصفح نظيف ⭐) ⭐
②  افتح ⭐:  https://octa-mgmt.ahmed3zz2020.workers.dev ⭐
③  المتوقع ⭐:  صفحة تسجيل الدخول بتطبيق Access ⭐ ⭐
     (مش لوحة الإدارة ⭐ ⭐)
④  سجّل دخول ببريدك ⭐ ⇒Expected ⭐:  لوحة الإدارة ⭐
```

⛔ **ما تفتحش** النتيجة بمجرد الـChallenge ⭐ — لازم denies ⭐.

---

## ٥. الاختيار بالـAPI ⭐ (اختياري ⭐)

| العملية | الـ endpoint | أقل صلاحية | النطاق |
|---|---|---|---|
| إنشاء تطبيق ⭐ | `POST /accounts/{account_id}/access/apps` ⭐ | `Access: Apps and Policies Write` ⭐ | `account_id` ⭐ |
| إنشاء سياسة ⭐ | `POST /accounts/{account_id}/access/apps/{app_id}/policies` ⭐ | `Access: Policies Write` ⭐ | `account_id` ⭐ |
| قراءة التطبيقات ⭐ | `GET /accounts/{account_id}/access/apps` ⭐ | `Access: Apps and Policies Read` ⭐ | `account_id` ⭐ |

⛔ **النطاق هنا الحساب ⭐ مش المنطقة** ⭐ — وده فرق مهم ⭐: صلاحية
`Zone WAF Write` ⭐ **مش** بتدي صلاحية Access ⭐ ⭐.

⛔ تصحيح على الجولة ٢٣ ⭐: «Account Access Write» ⭐ **مش اسم صلاحية
موجود** ⭐ ⇒ الاسم الرسمي ⭐ `Access: Apps and Policies Write` ⭐
(والواجهة بتعرضه ⭐ `Edit` ⭐) ⭐.

---

## ٦. ما لا يُتراجع ⭐

⛔ **ممنوع** حذف تطبيق Access ⭐ ⭐ (ده بيعيد فتح اللوحة ⭐).
⛔ **ممنوع** حذف سياسة Deny ⭐ ⭐.
⛔ لو محتاج طوارئ ⭐ ⇒ أضف إيميل تاني ⭐ (قابل للتراجع ⭐) ⭐ — مش
تحذف القفل ⭐.
