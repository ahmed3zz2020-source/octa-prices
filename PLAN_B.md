# خطة الطوارئ — لو Railway وقع
# ══════════════════════════════════════════════════════════════

# 🔴 معلومة مهمة: Railway مش مجاني دلوقتي
Railway بقى التجربة بس ($5 لمدة 30 يوم) — بعد كده لازم تدفع
الوقت ده مش بسهل.

# ✅ البديل المجاني الحقيقي

## 1) Render — الأفضل ليك
- مجاني **بدون كارت ائتمان**
- 750 ساعة في الشهر (/service continuous يكفي)
- 512 MB RAM
- ⚠️ ينام بعد 15 دقيقة خمول
- ⚠️ أول زائر بعد النوم يستنى ~1 دقيقة
- ⭐ **لأن OCTA بيتحدث كل دقيقة، النوم مش هيفرق**

## 2) Koyeb
- ⚠️ قفل الخطة المجانية على المستخدمين الجدد (فبراير 2026)
- بديل مدفوع $29/شهر

## 3) Fly.io
- ⚠️ مفيش خطة مجانية (من أكتوبر 2024)
- تجربة 2 ساعة بس

## 4) PythonAnywhere
- مجاني **للأبد**
- ⚠️ مقيّد — مينفعش يتصل بأي مصدر خارجي (يعني مش هينفع لـOCTA)

---

# 🛠️ خطة النشر على Render (لو احتجنا)

## الخطوة 1️⃣ — الحساب
https://render.com — سجّل بـGitHub (متوقع بلاش كارت)

## الخطوة 2️⃣ — الربط
New → Web Service → اختار المستودع:
https://github.com/ahmed3zz2020-source/octa-prices

## الخطوة 3️⃣ — الإعدادات

| الحقل | القيمة |
|-------|--------|
| Environment | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn update_prices:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| Instance Type | Free |

## الخطوة 4️⃣ — المتغيرات
Settings → Environment Variables
- `TELEGRAM_BOT_TOKEN` = التوكن
- `TELEGRAM_CHAT_ID` = 2073907990

## الخطوة 5️⃣ — الدومين
بعد النشر هيدّيك رابط زي:
`octa-prices.onrender.com`

# وفيه namespace لك — بعدها نعدّل الـfront-end

---

# 🛡️ الاحتياطي المحلي

الكود كله محفوظ في GitHub ✅
نسخة احتياطية على الجهاز: `/workspace/octa_package.zip` ✅
الـ front-end: `/workspace/octa5/` ✅

**لو كل حاجة وقعت:**
1. ينزل الكود من GitHub
2. ينزل الداتا من `data_egx.json`
3. الموقع بيشتغل ب/files الثابتة

# ✅ يعني الموقع **مش بيقع أبداً** — بيعملServ فقط