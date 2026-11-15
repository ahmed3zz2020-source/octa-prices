#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 بيئة Staging معزولة لـOCTA — بيانات وهمية ١٠٠٪

⛔⛔⛔ قواعد صارمة (ما تتكسرش) ⬇️ ⬇️
  ⛔ ⬇️ مافيش أي اتصال بالإنتاج ⬇️ ⬇️ (ولا Railway · ولا Cloudflare · ولا Telegram)
  ⛔ ⬇️ مافيش أي سر إنتاج ⬇️ ⬇️ (الأسرار دي بتتولّد هنا لحظياً)
  ⛔ ⬇️ مافيش أي بيانات مستخدمين حقيقية ⬇️ ⬇️ (كل الحسابات وهمية)
  ⛔ ⬇️ البيانات في مجلد منفصل ⬇️ ⬇️ (STAGE_DIR — مش /data)
  ⛔ ⬇️ الإيميل = Mock ⬇️ ⬇️ (يتكتب في ملف — مفيش إرسال حقيقي)

📌 التشغيل:
   python3 tools/staging/run_staging.py            # بيشتغل على 8099
   STAGE_PORT=9000 python3 tools/staging/run_staging.py
"""
import os
import sys
import json
import time
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent          # /workspace/repos/octa-prices
sys.path.insert(0, str(REPO))

STAGE_DIR = Path(os.environ.get("STAGE_DIR", "/workspace/.staging"))
STAGE_DIR.mkdir(parents=True, exist_ok=True)
PORT = int(os.environ.get("STAGE_PORT", "8099"))

# ══════════════════════════════════════════════════════════════════
#  ⛔ أسرار خاصة بالاختبار — بتتولّد هنا (مش من أي مكان تاني)
# ══════════════════════════════════════════════════════════════════
# ⛔⛔⛔ الأسرار لازم **ثابتة** بين مرات التشغيل ⬇️ ⬇️
# 📌 ⬇️ السبب: ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ لو تولّدت من جديد ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ سر Cloudflare (المتسجّل في عامل المعاينة) ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ بقى قديم ⇒ 403 على كل طلب ⬇️ ⬇️ ⬇️
# 📌 ⬇️ ⬇️ ⬇️ ⇒ الفحص الحيّ يفشل والنشر يتراجع ⬇️ ⬇️ ⬇️
# ⛔ لو تولّدت من جديد ⇒ سر الـCloudflare (اللي متسجّل في عامل
# ⛔ المعاينة) بقى قديم ⇒ 403 على كل طلب ⬇️ ⇒ الفحص الحيّ يفشل ⬇️
SECRETS_FILE = Path("/workspace/.staging-secrets.json")
try:
    _prev = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
except Exception:
    _prev = {}
SECRET = os.environ.get("STAGE_TOKEN_SECRET") or _prev.get("secret") or ("STG-" + secrets.token_urlsafe(32))
PROXY = os.environ.get("STAGE_PROXY_SECRET") or _prev.get("proxy") or ("PRX-" + secrets.token_urlsafe(32))
PEPPER = _prev.get("pepper") or ("STG-" + secrets.token_urlsafe(16))
ADMIN = os.environ.get("STAGE_ADMIN_TOKEN") or _prev.get("admin") or ("ADM-" + secrets.token_urlsafe(24))
try:
    SECRETS_FILE.write_text(json.dumps(
        {"secret": SECRET, "proxy": PROXY, "pepper": PEPPER, "admin": ADMIN},
        ensure_ascii=False, indent=2), encoding="utf-8")
except Exception:
    pass

os.environ["OCTA_DATA_DIR"] = str(STAGE_DIR)
os.environ["OCTAD_TOKEN_SECRET"] = SECRET
os.environ["OCTA_PIN_PEPPER"] = PEPPER
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_API_DENY_DEFAULT"] = "on"        # ⛔ staging فقط
os.environ["OCTA_FINGERPRINT_LOGIN"] = "off"     # ⛔ البصمة مقفولة
os.environ["OCTA_PROXY_SECRET"] = PROXY
os.environ["OCTA_WARMUP"] = "0"                   # ⛔ مافيش إيقاظ للسيرفر
# 🐞 ١٥ نوفمبر ٢٠٢٦ (دفعة الأمان ٠٢) — ⛔ حدود الطلبات ⬇️
# 📌 ⬇️ الاختبارات بتعمل مئات الطلبات ⬇️ ⬇️
# 📌 ⬇️ ⇒ من غير المعامل ده بتفشل بسبب 429 (مش بسبب عيب أمني) ⬇️ ⬇️
# ⛔ الإنتاج: مافيش متغيّر ⇒ الافتراضي 1 (مافيش تغيير) ⬇️
os.environ["OCTA_RATE_MULT"] = "300"
os.environ["MAIL_ON"] = "0"                       # ⛔ هنعمل mock
# ⛔ توكن أدمن **خاص بالاختبار** (مش إنتاجي) ⬇️
os.environ["OCTA_ADMIN_TOKEN"] = ADMIN

import update_prices as up  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  📮 Mock الإيميل — يتكتب في ملف (مفيش إرسال حقيقي)
# ══════════════════════════════════════════════════════════════════
MAIL_FILE = STAGE_DIR / "outbox.jsonl"
MAIL_FILE.write_text("", encoding="utf-8")


def _mock_send(to, subject, html):
    try:
        with MAIL_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "subject": subject, "html": html},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass
    return True


up._send_mail = _mock_send
up.MAIL_ON = True

# ══════════════════════════════════════════════════════════════════
#  👥 حسابات وهمية — واحد Free وواحد Pro
# ══════════════════════════════════════════════════════════════════
DEV_FREE = "f" * 64
DEV_PRO = "p" * 64
FREE_MAIL = "staging.free@example.test"
PRO_MAIL = "staging.pro@example.test"


def _mk(uid, email, pin, dev, plan, until=0):
    salt = up._pin_salt_new()
    dh = up._device_key_hash(dev)
    rec = {
        "id": uid, "name": "Staging " + plan, "email": email,
        "pin_hash": up._pin_hash(pin, salt), "pin_salt": salt,
        "pin_idx": up._pin_index(pin), "pin_idx_id": up._PIN_PEPPER_ID,
        "token_epoch": 0, "created": int(time.time()),
        "bio_hash": dh, "bio_hashes": [dh],
        "portfolio": {"holdings": {}, "cash": 0}, "watch": {},
        "plan": plan, "plan_until": int(until or 0),
    }
    with up.USERS_LOCK:
        users = up._load_users()
        users[uid] = rec
        up._save_users(users)
    return rec


def seed():
    _mk("stg_free_user", FREE_MAIL, "1111", DEV_FREE, "free", 0)
    _mk("stg_pro_user", PRO_MAIL, "2222", DEV_PRO, "pro",
        int(time.time()) + 30 * 86400)
    # ⛔ حساب Pro منتهي (للاختبار) ⬇️
    _mk("stg_expired_pro", "staging.expired@example.test", "3333",
        "e" * 64, "pro", int(time.time()) - 86400)


if __name__ == "__main__":
    seed()
    # ⛔ ملف إعدادات الـstaging (للـworker) ⬇️
    cfg = {
        "api_url": "http://127.0.0.1:%d" % PORT,
        "proxy_secret": PROXY,
        "admin_token": ADMIN,
        "free": {"email": FREE_MAIL, "pin": "1111", "device": DEV_FREE},
        "pro": {"email": PRO_MAIL, "pin": "2222", "device": DEV_PRO},
        "expired_pro": {"email": "staging.expired@example.test",
                        "pin": "3333", "device": "e" * 64},
        "data_dir": str(STAGE_DIR),
    }
    (STAGE_DIR / "staging-config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[staging] ✅ جاهز · البورت %d · الداتا: %s" % (PORT, STAGE_DIR))
    print("[staging] ✅ proxy_secret متسجّل في %s" % (STAGE_DIR / "staging-config.json"))
    print("[staging] ⚠️ مافيش أي سر إنتاج اتستخدم — كله متولّد هنا")
    up.app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False,
               use_reloader=False)
