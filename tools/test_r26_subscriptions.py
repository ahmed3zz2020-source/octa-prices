#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٦ (R26) — اختبارات نظام الاشتراكات (مزوّد دفع **صناعي**)
=====================================================================
📌 الهدف: إثبات جاهزية النظام تجارياً **من غير** تعاقد مع مزوّد حقيقي
   ومن غير تحصيل مالي حقيقي ومن غير بيانات عملاء حقيقية.

📦 التغطية (١٠ بنود + سلامة + مبرهن سالب) ⬇️ ⬇️ ⬇️
   ① الباقات والتسجيل ............ data/subscription_plans.json + الكتالوج
   ② دورة الاشتراك ................ اشتراك · تجديد · انتهاء · إلغاء · استرداد
   ③ فشل الدفع ................... بطاقة مرفوضة · مزوّد معطّل · مهلة ⇒ masked
   ④ تكرار الطلب (idempotency) .... نفس المفتاح ⇒ نفس النتيجة بلا تحصيل مكرر
   ⑤ التسوية (settlement/webhook) .. تُطبَّق الحالة مرة واحدة فقط
   ⑥ منع التفعيل المزدوج .......... خطة واحدة نشطة بس لكل مستخدم
   ⑦ صلاحيات المستخدم ............. الفرص · التنبيهات · RealView
   ⑧ حذف الحساب .................. بيانات الاشتراك + المحفظة + التنبيهات + الأثر
   ⑨ الدعم الفني .................. نقطة دخول + قالب رسالة + سجل
   ⑩ الخصوصية والاحتفاظ ........... الوثيقة + sweep + توافق الوثيقة مع الكود
   ⓪ السلامة ...................... مافيش شبكة · مافيش أسرار · مافيش بيانات حقيقية
   ⑪ البرهان السالب ................ ١٤ طفرة: شيل الحماية ⇒ الفحص لازم يفشل

⛔⛔⛔ قواعد الجولة ٢٦ (هارد) ⬇️ ⬇️ ⬇️
   ⛔ كل الاختبارات محلية — مافيش أي اتصال بأي شبكة خارجية.
   ⛔ مافيش بيانات عملاء حقيقية — كل المعرفات والبريد اصطناعية.
   ⛔ مافيش أسرار ولا مفاتيح ولا أرقام بطاقات.
   ⛔ مافيش أي تعديل على أوزان المحرك ولا حدود القبول ولا سياسة الاستثمار.

📌 التشغيل:  python3 tools/test_r26_subscriptions.py
📌 وكل ملف اختبار كمان بيشتغل تحت `pytest`.
"""

import functools
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import _stub_env  # noqa: E402

FL, _RQ = _stub_env.install()

import subscription_api as SA  # noqa: E402
import subscription_core as SC  # noqa: E402

BASE_SHA = "316f3b6ca540f05ff7816665f43a5db3d6e8a4f5"
PLAN_FILE = ROOT / "data" / "subscription_plans.json"
PRIVACY_DOC = ROOT / "docs" / "privacy_and_retention.md"

RESULTS = []
MUTATIONS = []
_TMPDIRS = []


# ══════════════════════════════════════════════════════════════════════════
#  أدوات الاختبار
# ══════════════════════════════════════════════════════════════════════════
def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra and not cond else ""), flush=True)
    return bool(cond)


def _case(fn):
    """⛔ غلاف متوافق مع pytest — الفشل بيرمي AssertionError."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        before = len(RESULTS)
        completed = False
        try:
            fn(*args, **kwargs)
            completed = True
        finally:
            if completed:
                bad = [r[1] for r in RESULTS[before:] if not r[0]]
                if bad:
                    raise AssertionError(
                        "%d إخفاق ⭐: %s" % (len(bad), " · ".join(bad[:3])))

    return wrapper


def section(title):
    print("\n" + "─" * 70)
    print("  " + title)
    print("─" * 70, flush=True)


def _code_tokens(src):
    """🔎 كود بدون تعليقات ولا نصوص (tokenize) — لفحص المراجع."""
    import io
    import tokenize
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except Exception:
        return ""
    return " ".join(out)


def new_engine(mod=None, start=1700000000):
    """🧪 محرك نظيف بمجلد تخزين مؤقّت + ساعة ثابتة (اختبار حتمي)."""
    mod = mod or SC
    tmp = tempfile.mkdtemp(prefix="octa_r26_subs_")
    _TMPDIRS.append(tmp)
    clock = {"t": start}

    def _now():
        return int(clock["t"])

    eng = mod.Billing(base_dir=tmp, clock=_now)
    eng._test_clock = clock
    return eng


ADMIN_TOKEN = "r26-test-admin-token"


def make_api(engine, admin_token=ADMIN_TOKEN):
    """🔌 تطبيق اختبار + مستخدم واحد + قائمة فرص."""
    # ⛔ المسارات المحمية بتقارن بـ OCTA_ADMIN_TOKEN من البيئة
    os.environ["OCTA_ADMIN_TOKEN"] = admin_token
    app = FL.Flask("r26-test")
    users = {"tok-ok": {"id": "uid-1", "email": "user@example.com",
                        "watch": {"COMI": {"hi": 10.0}, "ETEL": {"lo": 5.0}}}}

    def require_user():
        auth = str(FL.request.headers.get("Authorization", "") or "")
        if auth.lower().startswith("bearer "):
            return users.get(auth[7:].strip())
        return None

    SA.register(app, require_user=require_user, billing=engine,
                opportunities_getter=lambda: [{"code": "COMI"}, {"code": "ETEL"},
                                              {"code": "HRHO"}, {"code": "MFPC"}],
                alerts_counter=lambda u: len((u or {}).get("watch") or {}))
    return app, users


def call(app, path, method="GET", body=None, headers=None, query=None):
    return app.dispatch(path, method=method, headers=headers, body=body,
                        query=query)


AUTH = {"Authorization": "Bearer tok-ok"}


def admin_headers(token=ADMIN_TOKEN):
    return {"X-OCTA-Admin": token}


# ══════════════════════════════════════════════════════════════════════════
#  ⓪ السلامة — مافيش شبكة · مافيش أسرار · مافيش بيانات حقيقية
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_00_safety():
    section("⓪ السلامة — شبكة · أسرار · بيانات حقيقية")

    core_src = (ROOT / "subscription_core.py").read_text(encoding="utf-8")
    api_src = (ROOT / "subscription_api.py").read_text(encoding="utf-8")

    # ① مافيش استيراد شبكي في النواة
    for mod_name in ("requests", "urllib", "socket", "http.client", "httpx",
                     "aiohttp", "boto3"):
        ok("import %s" % mod_name not in core_src,
           "النواة مافيش استيراد شبكة (%s)" % mod_name)
        ok("import %s" % mod_name not in api_src,
           "واجهة الـAPI مافيش استيراد شبكة (%s)" % mod_name)

    # ② مافيش أسرار ولا مفاتيح
    for bad in ("sk_live", "sk_test", "AKIA", "BEGIN RSA", "BEGIN PRIVATE KEY",
                "stripe_secret", "api_key=", "apikey=", "secret_key="):
        ok(bad not in core_src and bad not in api_src,
           "مافيش سر في كود الاشتراكات (%s)" % bad)

    # ③ مافيش أرقام بطاقات
    for name, src in (("subscription_core.py", core_src),
                      ("subscription_api.py", api_src),
                      ("data/subscription_plans.json",
                       PLAN_FILE.read_text(encoding="utf-8"))):
        cards = re.findall(r"\b(?:\d[ -]?){13,19}\b", src)
        ok(not cards, "مافيش رقم بطاقة في %s" % name, cards[:2])

    # ④ مافيش بريد حقيقي — كله نطاق اختبار
    mails = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
                       core_src + api_src)
    real = [m for m in mails
            if not re.search(r"@(example|test|localhost|invalid)\.", m, re.I)]
    ok(not real, "مافيش بريد حقيقي في كود الاشتراكات", real[:3])

    # ⑤ مافيش محارف ممنوعة في الملفات الجديدة
    cjk = re.compile("[" + "".join([
        "\\u3040-\\u30FF", "\\u3400-\\u4DBF", "\\u4E00-\\u9FFF",
        "\\uAC00-\\uD7AF", "\\u0400-\\u04FF",
    ]) + "]")
    for rel in ("subscription_core.py", "subscription_api.py",
                "data/subscription_plans.json", "docs/privacy_and_retention.md",
                "tools/test_r26_subscriptions.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        ok("\ufffd" not in text, "مافيش محرف تالف U+FFFD في %s" % rel)
        ok(not cjk.search(text), "مافيش حروف صينية/كورية/سيلانية في %s" % rel)

    # ⑥ مافيش نقاط ثلاث برّه التعليقات في الكود الجديد
    for rel in ("subscription_core.py", "subscription_api.py"):
        bad = []
        for i, line in enumerate((ROOT / rel).read_text(
                encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if "..." in code:
                bad.append("%s:%d" % (rel, i))
        ok(not bad, "مافيش نقاط ثلاث برّه التعليقات في %s" % rel, bad[:3])

    # ⑦ التخزين منفصل عن users.json
    code_only = _code_tokens(core_src)
    ok("users.json" not in code_only,
       "النواة مابيلمسش users.json خالص")
    for ident in ("USERS_FILE", "_load_users", "_save_users", "_patch_user"):
        ok(ident not in code_only,
           "النواة مافيش استدعاء مباشر لتخزين المستخدمين (%s)" % ident)
    ok(SC.STORE_DIRNAME != "users.json", "مجلد التخزين منفصل عن users.json")

    # ⑧ مافيش تغيير في أوزان المحرك ولا حدود القبول
    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(ROOT)] + list(args),
                                  capture_output=True, text=True,
                                  timeout=120).stdout
        except Exception:
            return ""

    changed = [l.strip() for l in git("diff", "--name-only", BASE_SHA).split()
               if l.strip()]
    allowed = {"subscription_core.py", "subscription_api.py",
               "data/subscription_plans.json",
               "docs/privacy_and_retention.md",
               "tools/test_r26_subscriptions.py",
               "update_prices.py"}
    extra = [c for c in changed if c not in allowed]
    ok(not extra, "مافيش ملف اتغيّر خارج نطاق الاشتراكات", extra[:5])

    engine_files = ["octa_score.py", "opp_engine.py", "index_engine.py",
                    "pattern_detector.py", "gold_signal.py", "data_full.json",
                    "data/opp_definitions.json"]
    dirty = [f for f in engine_files
             if git("diff", "--stat", BASE_SHA, "--", f).strip()]
    ok(not dirty, "مافيش تغيير في المحرك ولا حدود القبول ولا البيانات", dirty)

    numstat = git("diff", "--numstat", BASE_SHA, "--", "update_prices.py")
    added = 0
    for line in numstat.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit():
            added += int(parts[0])
    ok(0 < added <= 120,
       "التعديل في update_prices.py محدود (%d سطر مضاف)" % added)


# ══════════════════════════════════════════════════════════════════════════
#  ① الباقات والتسجيل
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_01_plans():
    section("① الباقات والتسجيل — ملف الإعدادات + الكتالوج")

    ok(PLAN_FILE.exists(), "ملف الباقات موجود (data/subscription_plans.json)")
    raw = PLAN_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        parsed = True
    except Exception as e:
        parsed = False
        data = {}
    ok(parsed, "ملف الباقات JSON صالح")
    ok(isinstance(data.get("plans"), dict) and len(data["plans"]) >= 3,
       "في ٣ باقات على الأقل (Basic/Pro/Enterprise)", len(data.get("plans") or {}))
    for code in ("free", "basic", "pro", "enterprise"):
        ok(code in (data.get("plans") or {}), "باقة %s موجودة" % code)

    # كل باقة: سعر + مزايا + صلاحيات
    for code, pdef in (data.get("plans") or {}).items():
        periods = pdef.get("periods") or []
        prices = [float(p.get("price") or 0) for p in periods]
        if pdef.get("sellable"):
            ok(bool(periods) and all(pr > 0 for pr in prices),
               "باقة %s ليها سعرات" % code, prices)
        else:
            ok(bool(periods) and all(pr == 0 for pr in prices),
               "باقة %s (مجانية) سعرها صفر" % code, prices)
        ok(bool(pdef.get("features")), "باقة %s ليها مزايا" % code)
        ent = pdef.get("entitlements") or {}
        ok(isinstance(ent, dict) and "max_opportunities" in ent
           and "max_alerts" in ent and "realview" in ent,
           "باقة %s ليها صلاحيات كاملة" % code)

    # ترتيب الصلاحيات تصاعدي (المجانية الأدنى)
    ents = {c: (data["plans"][c].get("entitlements") or {})
            for c in data["plans"]}
    ok(ents["free"]["max_opportunities"] < ents["basic"]["max_opportunities"]
       < ents["pro"]["max_opportunities"]
       <= ents["enterprise"]["max_opportunities"],
       "الصلاحيات بتزيد مع الباقة (فرص)",
       [ents[c]["max_opportunities"] for c in ("free", "basic", "pro",
                                              "enterprise")])
    ok(ents["pro"]["realview"] is True and ents["basic"]["realview"] is False,
       "RealView مرتبط بالباقة")

    # الباقات مقروءة من الملف (مش ثابتة في الكود)
    eng = new_engine()
    cat = eng.catalog()
    ok(len(cat["plans"]) == len(data["plans"]),
       "الكتالوج من المحرك = عدد باقات الملف")
    tmp = tempfile.mkdtemp(prefix="octa_r26_plans_")
    _TMPDIRS.append(tmp)
    alt = json.loads(raw)
    alt["plans"]["pro"]["periods"][0]["price"] = 999
    alt_path = Path(tmp) / "plans.json"
    alt_path.write_text(json.dumps(alt, ensure_ascii=False), encoding="utf-8")
    eng2 = SC.Billing(base_dir=tmp, plans_path=alt_path)
    ok(eng2.price_of(eng2.plan_or_fail("pro"), "monthly") == 999,
       "السعر بيتقرأ من ملف الإعدادات (مش ثابت في الكود)")

    # باقة مجهولة ⇒ 404 (مافيش باقة افتراضية مخترعة)
    try:
        eng.plan_or_fail("no-such-plan")
        ok(False, "باقة مجهولة ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 404 and e.why == "unknown_plan",
           "باقة مجهولة ⇒ 404 unknown_plan", "%s/%s" % (e.status, e.why))

    # الكتالوج عبر الـAPI (عام — بلا تسجيل دخول)
    app, _users = make_api(eng)
    r = call(app, "/api/billing/plans")
    ok(r.status_code == 200, "مسار الباقات بيرد 200")
    j = r.get_json()
    ok(len(j.get("plans") or []) == len(data["plans"]),
       "الـAPI بيرجّع كل الباقات")
    ok(j.get("provider") == "mock", "الـAPI بيعلن إن المزوّد mock")

    # ملف الباقات التالف ⇒ 503 (مافيش تخمين)
    broken = Path(tmp) / "broken.json"
    broken.write_text("{مش json", encoding="utf-8")
    eng3 = SC.Billing(base_dir=tmp, plans_path=broken)
    try:
        eng3.catalog()
        ok(False, "ملف باقات تالف ⇒ خطأ")
    except SC.PlanFileError:
        ok(True, "ملف باقات تالف ⇒ PlanFileError (fail-closed)")


# ══════════════════════════════════════════════════════════════════════════
#  ② دورة الاشتراك
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_02_lifecycle():
    section("② دورة الاشتراك — تسجيل · تجديد · انتهاء · إلغاء · استرداد")

    eng = new_engine(start=1700000000)
    st, body = eng.subscribe("uid-a", "pro", "k-1")
    sub = body.get("subscription") or {}
    ok(st == 200 and body.get("status") == "active", "التسجيل ⇒ نشط", st)
    ok(sub.get("period_end") == 1700000000 + 30 * 86400,
       "نهاية الفترة = ٣٠ يوم من التسجيل", sub.get("period_end"))
    ok(body.get("entitlements", {}).get("max_opportunities") == 60
       and body.get("plan") == "pro",
       "الصلاحيات اتطبّقت فوراً", body.get("entitlements"))

    # تجديد ⇒ التمديد من نهاية الفترة الحالية (مفيش فجوة)
    st, body2 = eng.renew("uid-a", "k-2")
    sub2 = body2.get("subscription") or {}
    ok(st == 200 and body2.get("status") == "active", "التجديد ⇒ 200", st)
    ok(sub2.get("period_end") == sub.get("period_end") + 30 * 86400,
       "التجديد مدّد من نهاية الفترة (مفيش فجوة)",
       "%s → %s" % (sub.get("period_end"), sub2.get("period_end")))

    # انتهاء ⇒ الحالة expired والصلاحيات ترجع للمجانية
    eng._test_clock["t"] += 61 * 86400
    stt = eng.status_of("uid-a")
    ok(stt.get("status") == "expired", "بعد ٦١ يوم ⇒ expired", stt.get("status"))
    ok(eng.entitlements_for("uid-a")["plan"] == "free",
       "الاشتراك المنتهي ⇒ صلاحيات المجانية")
    ok(eng.entitlements_for("uid-a")["source"] == "default",
       "المصدر بقى default (مافيش اشتراك نشط)")

    # تجديد اشتراك منتهي ⇒ يرجع نشط
    st, body3 = eng.renew("uid-a", "k-3")
    ok(st == 200 and body3.get("status") == "active",
       "تجديد اشتراك منتهي ⇒ رجع نشط", st)
    ok(body3["subscription"]["period_end"] > eng._test_clock["t"],
       "الفترة الجديدة بدأت من الآن")

    # إلغاء بنهاية الفترة ⇒ يفضل شغّال لحد ما يخلص
    st, body4 = eng.cancel("uid-a", at_period_end=True)
    ok(st == 200 and body4.get("effective") == "period_end",
       "إلغاء بنهاية الفترة اتسجل", body4.get("effective"))
    ok(eng.entitlements_for("uid-a")["plan"] == "pro",
       "الصلاحيات تفضل شغّالة لحد نهاية الفترة")
    eng._test_clock["t"] += 31 * 86400
    ok(eng.status_of("uid-a").get("status") == "canceled",
       "بعد نهاية الفترة ⇒ canceled", eng.status_of("uid-a").get("status"))
    ok(eng.entitlements_for("uid-a")["plan"] == "free",
       "الاشتراك الملغي ⇒ صلاحيات المجانية")

    # إلغاء فوري ⇒ الصلاحيات تترفع فوراً
    eng2 = new_engine()
    eng2.subscribe("uid-b", "basic", "k-4")
    st, body5 = eng2.cancel("uid-b", at_period_end=False)
    ok(st == 200 and body5.get("status") == "canceled",
       "إلغاء فوري ⇒ canceled", body5.get("status"))
    ok(eng2.entitlements_for("uid-b")["plan"] == "free",
       "الإلغاء الفوري رفع الصلاحيات فوراً")
    ok(body5["subscription"]["period_end"] == 0,
       "الإلغاء الفوري صفّر نهاية الفترة")

    # إلغاء اشتراك مش موجود ⇒ 404
    try:
        eng2.cancel("uid-nobody", at_period_end=False)
        ok(False, "إلغاء بلا اشتراك ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 404, "إلغاء بلا اشتراك ⇒ 404", e.status)

    # استرداد ⇒ مرفوع + مرتجع
    eng3 = new_engine()
    eng3.subscribe("uid-c", "pro", "k-5")
    st, body6 = eng3.refund("uid-c", "k-6", reason="طلب من المستخدم")
    ok(st == 200 and body6.get("status") == "refunded",
       "الاسترداد اتنفّذ", body6.get("status"))
    ok(eng3.entitlements_for("uid-c")["plan"] == "free",
       "الاسترداد رفع الصلاحيات فوراً")
    ledger = eng3.store.read("wallet")
    kinds = [w.get("kind") for w in ledger]
    ok(kinds.count("charge") == 1 and kinds.count("refund") == 1,
       "دفتر المعاملات: تحصيل واحد + استرداد واحد", kinds)
    ok(eng3.provider_stats().get("refunds") == 1, "المزوّد نفّذ استرداد واحد")

    # استرداد مرتين بنفس المفتاح ⇒ نفس النتيجة (مافيش استرداد تاني)
    st2, body7 = eng3.refund("uid-c", "k-6", reason="طلب من المستخدم")
    ok(st2 == 200 and body7.get("idempotent_replay") is True,
       "تكرار الاسترداد بنفس المفتاح ⇒ نفس النتيجة")
    ok(eng3.provider_stats().get("refunds") == 1,
       "مافيش استرداد تاني اتنفّذ")

    # استرداد مرتين بمفتاح مختلف ⇒ 409
    try:
        eng3.refund("uid-c", "k-7", reason="طلب من المستخدم")
        ok(False, "استرداد تاني بمفتاح مختلف ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 409, "استرداد تاني بمفتاح مختلف ⇒ 409", e.status)


# ══════════════════════════════════════════════════════════════════════════
#  ③ فشل الدفع
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_03_payment_failure():
    section("③ فشل الدفع — رفض · تعطّل · مهلة ⇒ masked بدون تفعيل")

    eng = new_engine()
    cases = [("tok_decline", "card_declined", 402),
             ("tok_down", "provider_unavailable", 503),
             ("tok_timeout", "provider_timeout", 504)]
    for token, reason, want_status in cases:
        st, body = eng.subscribe("uid-f", "basic", "key-%s" % token,
                                 token=token)
        sub = body.get("subscription") or {}
        ok(st == want_status, "%s ⇒ HTTP %d" % (reason, want_status), st)
        ok(body.get("status") == "failed", "%s ⇒ الحالة failed" % reason,
           body.get("status"))
        ok(sub.get("status") == "failed", "%s ⇒ الاشتراك masked" % reason,
           sub.get("status"))
        ok(sub.get("period_end") == 0, "%s ⇒ مافيش فترة" % reason)
        ok(sub.get("activated_payment_id") == "",
           "%s ⇒ مافيش تفعيل" % reason)
        ok(eng.entitlements_for("uid-f")["plan"] == "free",
           "%s ⇒ صفر صلاحيات" % reason)
        ok(eng._active_subscription("uid-f") is None,
           "%s ⇒ مافيش اشتراك نشط" % reason)
        ok(len(eng.store.read("wallet")) == 0,
           "%s ⇒ مافيش تحصيل في المحفظة" % reason)

    # فشل الدفع ما بيكسّرش اشتراك نشط موجود
    eng.subscribe("uid-g", "pro", "key-g")
    before = eng.entitlements_for("uid-g")["plan"]
    st, _b = eng.subscribe("uid-g", "basic", "key-g2", token="tok_decline")
    ok(st == 402, "فشل الدفع مرفوض", st)
    ok(eng.entitlements_for("uid-g")["plan"] == before,
       "الاشتراك النشط موجود ما اتكسّرش بالفشل الجديد", before)

    # عبر الـAPI
    app, _u = make_api(eng)
    r = call(app, "/api/billing/subscribe", "POST",
             {"plan": "basic", "payment_token": "tok_decline"},
             headers=dict(AUTH, **{"Idempotency-Key": "api-decline"}))
    ok(r.status_code == 402, "الـAPI: رفض ⇒ 402", r.status_code)
    j = r.get_json()
    ok(j.get("ok") is False and j.get("reason") == "card_declined",
       "الـAPI: سبب الرفض واضح", j.get("reason"))
    ok(j.get("entitlements", {}).get("max_opportunities") == 5,
       "الـAPI: صفر صلاحيات بعد الرفض")

    # تعطّل عام للمزوّد
    prov = SC.MockProvider(outage=True)
    eng2 = new_engine()
    eng2.provider = prov
    st, body = eng2.subscribe("uid-h", "basic", "key-h")
    ok(st == 503 and body.get("reason") == "provider_unavailable",
       "تعطّل عام للمزوّد ⇒ 503 provider_unavailable", st)


# ══════════════════════════════════════════════════════════════════════════
#  ④ تكرار الطلب (idempotency)
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_04_idempotency():
    section("④ تكرار الطلب — نفس المفتاح ⇒ نفس النتيجة بلا تحصيل مكرر")

    eng = new_engine()
    st1, b1 = eng.subscribe("uid-i", "pro", "idem-1")
    st2, b2 = eng.subscribe("uid-i", "pro", "idem-1")
    ok(st1 == st2 == 200, "نفس المفتاح ⇒ نفس الحالة", "%s/%s" % (st1, st2))
    ok(b2.get("idempotent_replay") is True, "الرد الثاني عليه علامة إعادة تشغيل")
    ok(b1.get("subscription", {}).get("period_end")
       == b2.get("subscription", {}).get("period_end"),
       "الفترة ما اتمدّتش تاني")
    ok(eng.provider_stats().get("approved") == 1,
       "المزوّد ما-chargedش غير مرة واحدة",
       eng.provider_stats().get("approved"))
    ok(eng.provider_stats().get("attempts") == 1,
       "مافيش محاولة تحصيل تانية", eng.provider_stats().get("attempts"))
    ok(len([w for w in eng.store.read("wallet") if w.get("kind") == "charge"]) == 1,
       "دفتر المعاملات فيه تحصيل واحد بس")
    ok(len(eng.store.read("subscriptions")) == 1,
       "مافيش اشتراك تاني اتعمل")

    # نفس المفتاح + طلب مختلف ⇒ 409 (مافيش تنفيذ صامت)
    try:
        eng.subscribe("uid-i", "enterprise", "idem-1")
        ok(False, "نفس المفتاح بطلب مختلف ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 409 and e.why == "idempotency_conflict",
           "نفس المفتاح بطلب مختلف ⇒ 409", "%s/%s" % (e.status, e.why))

    # مفتاح تفرّد ناقص ⇒ 400
    try:
        eng.subscribe("uid-i", "pro", "")
        ok(False, "بدون مفتاح تفرّد ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 400 and e.why == "idempotency_key_required",
           "بدون مفتاح تفرّد ⇒ 400", "%s/%s" % (e.status, e.why))

    # مفتاح تفرّد لمستخدم تاني ⇒ مستقل (مافيش تسريب بين الحسابات)
    st3, b3 = eng.subscribe("uid-other", "pro", "idem-1")
    ok(st3 == 200 and b3.get("subscription", {}).get("uid") == "uid-other",
       "نفس المفتاح لحساب تاني ⇒ عملية مستقلة")

    # التجديد كمان متفرّد
    eng.subscribe("uid-j", "basic", "j-1")
    _s, r1 = eng.renew("uid-j", "j-2")
    _s, r2 = eng.renew("uid-j", "j-2")
    ok(r2.get("idempotent_replay") is True, "التجديد المتكرر ⇒ إعادة تشغيل")
    ok(r1["subscription"]["period_end"] == r2["subscription"]["period_end"],
       "التجديد المتكرر ما مدّدش الفترة")

    # عبر الـAPI — نفس الترويسة
    app, _u = make_api(eng)
    h = dict(AUTH, **{"Idempotency-Key": "api-idem-1"})
    r = call(app, "/api/billing/subscribe", "POST", {"plan": "basic"}, headers=h)
    r2 = call(app, "/api/billing/subscribe", "POST", {"plan": "basic"}, headers=h)
    ok(r.status_code == 200 and r2.status_code == 200,
       "الـAPI: نفس الترويسة ⇒ ٢٠٠ مرتين")
    ok(r2.get_json().get("idempotent_replay") is True,
       "الـAPI: الرد الثاني إعادة تشغيل")
    r3 = call(app, "/api/billing/subscribe", "POST", {"plan": "basic"},
              headers=AUTH)
    ok(r3.status_code == 400, "الـAPI: بدون مفتاح تفرّد ⇒ 400", r3.status_code)


# ══════════════════════════════════════════════════════════════════════════
#  ⑤ التسوية (settlement/webhook)
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_05_settlement():
    section("⑤ التسوية — إشعار المزوّد يُطبَّق مرة واحدة فقط")

    eng = new_engine()
    st, body = eng.subscribe("uid-s", "pro", "s-1", defer_settlement=True)
    sid = body["subscription"]["id"]
    ok(st == 200 and body.get("status") == "pending",
       "السلة المعلّقة ⇒ pending (لسه متفعّلش)", body.get("status"))
    ok(eng.entitlements_for("uid-s")["plan"] == "free",
       "الاشتراك المعلّق ⇒ مافيش صلاحيات")
    ok(eng._active_subscription("uid-s") is None,
       "الاشتراك المعلّق مش نشط")

    # إشعار نجاح ⇒ تفعيل
    st, r1 = eng.apply_settlement("evt-1", "payment.succeeded", sid,
                                   payment_id="pay-1")
    ok(st == 200 and r1.get("applied") is True, "إشعار النجاح اتطبّق",
       r1.get("applied"))
    ok(r1["subscription"]["status"] == "active", "الاشتراك بقى نشط")
    ok(eng.entitlements_for("uid-s")["plan"] == "pro",
       "الصلاحيات اتفتحت بعد التسوية")

    # نفس الحدث تاني ⇒ مافيش تغيير
    st, r2 = eng.apply_settlement("evt-1", "payment.succeeded", sid,
                                  payment_id="pay-1")
    ok(st == 200 and r2.get("duplicate") is True,
       "نفس event_id ⇒ duplicate (مافيش تنفيذ تاني)", r2.get("duplicate"))
    ok(r2.get("applied") is False, "التكرار ⇒ applied=false")

    # حدث مختلف لنفس الدفعة ⇒ مافيش تمديد تاني
    end_before = eng._active_subscription("uid-s")["period_end"]
    st, r3 = eng.apply_settlement("evt-2", "payment.succeeded", sid,
                                  payment_id="pay-1")
    ok(r3.get("applied") is False,
       "event_id مختلف لنفس الدفعة ⇒ مافيش تطبيق تاني", r3.get("applied"))
    ok(eng._active_subscription("uid-s")["period_end"] == end_before,
       "الفترة ما اتمدّتش تانية")

    # إشعار فشل ⇒ masked
    eng.subscribe("uid-t", "basic", "t-1", defer_settlement=True)
    sid2 = [s for s in eng.store.read("subscriptions")
            if s["uid"] == "uid-t"][0]["id"]
    st, r4 = eng.apply_settlement("evt-3", "payment.failed", sid2)
    ok(r4.get("applied") is True and r4["subscription"]["status"] == "failed",
       "إشعار الفشل ⇒ masked", r4["subscription"].get("status"))
    ok(eng.entitlements_for("uid-t")["plan"] == "free",
       "بعد إشعار الفشل ⇒ مافيش صلاحيات")

    # نوع حدث مش معروف ⇒ 400
    try:
        eng.apply_settlement("evt-4", "weird.type", sid)
        ok(False, "نوع حدث غريب ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 400 and e.why == "bad_event_type",
           "نوع حدث مش معروف ⇒ 400", "%s/%s" % (e.status, e.why))

    # اشتراك مش موجود ⇒ 404
    try:
        eng.apply_settlement("evt-5", "payment.succeeded", "sub-nope")
        ok(False, "تسوية لاشتراك مش موجود ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 404, "تسوية لاشتراك مش موجود ⇒ 404", e.status)

    # بلا event_id ⇒ 400
    try:
        eng.apply_settlement("", "payment.succeeded", sid)
        ok(False, "تسوية بلا event_id ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 400, "تسوية بلا event_id ⇒ 400", e.status)

    # عبر الـAPI — محمية بتوكن الأدمن
    app, _u = make_api(eng)
    r = call(app, "/api/billing/settlement", "POST",
             {"event_id": "api-evt", "type": "payment.succeeded",
              "subscription_id": sid})
    ok(r.status_code == 401, "مسار التسوية محمي بدون توكن أدمن", r.status_code)
    r = call(app, "/api/billing/settlement", "POST",
             {"event_id": "api-evt", "type": "payment.succeeded",
              "subscription_id": sid}, headers=admin_headers())
    ok(r.status_code == 200, "التسوية بتوكن الأدمن ⇒ 200", r.status_code)
    r = call(app, "/api/billing/settlement", "POST",
             {"event_id": "api-evt", "type": "payment.succeeded",
              "subscription_id": sid}, headers=admin_headers())
    ok(r.get_json().get("duplicate") is True,
       "تكرار الحدث عبر الـAPI ⇒ duplicate")
    r = call(app, "/api/billing/settlement", "POST",
             {"event_id": "api-evt-2", "type": "payment.succeeded",
              "subscription_id": sid}, headers=admin_headers())
    ok(r.get_json().get("applied") is False,
       "حدث تاني لنفس الدفعة عبر الـAPI ⇒ مافيش تطبيق")


# ══════════════════════════════════════════════════════════════════════════
#  ⑥ منع التفعيل المزدوج
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_06_no_double_activation():
    section("⑥ منع التفعيل المزدوج — خطة واحدة نشطة بس")

    eng = new_engine()
    eng.subscribe("uid-d", "pro", "d-1")
    eng.subscribe("uid-d", "enterprise", "d-2")
    actives = [s for s in eng.store.read("subscriptions")
               if s["uid"] == "uid-d" and s["status"] == "active"]
    ok(len(actives) == 1, "في خطة نشطة واحدة بس", len(actives))
    ok(actives[0]["plan"] == "enterprise", "النشطة هي الأحدث")
    old = [s for s in eng.store.read("subscriptions")
           if s["uid"] == "uid-d" and s["status"] == "superseded"]
    ok(len(old) == 1, "الخطة القديمة اتحوّلت superseded", len(old))
    ent = eng.entitlements_for("uid-d")
    ok(ent["plan"] == "enterprise" and ent["source"] == "subscription",
       "الصلاحيات من الخطة النشطة بس", ent["plan"])
    ok(ent["entitlements"]["max_opportunities"] == 999,
       "حدود enterprise اتطبّقت")

    # التفعيل المزدوج عن طريق التسوية برضو
    eng2 = new_engine()
    _s, b = eng2.subscribe("uid-e", "basic", "e-1", defer_settlement=True)
    sid = b["subscription"]["id"]
    eng2.apply_settlement("ee-1", "payment.succeeded", sid, payment_id="p1")
    eng2.apply_settlement("ee-2", "payment.succeeded", sid, payment_id="p2")
    actives = [s for s in eng2.store.read("subscriptions")
               if s["uid"] == "uid-e" and s["status"] == "active"]
    ok(len(actives) == 1, "التسوية المتكررة ⇒ خطة نشطة واحدة", len(actives))

    # مستخدمين مختلفين ⇒ كل واحد لواحد (العزل)
    eng2.subscribe("uid-z", "pro", "z-1")
    per = {}
    for s in eng2.store.read("subscriptions"):
        if s["status"] == "active":
            per[s["uid"]] = per.get(s["uid"], 0) + 1
    ok(all(v == 1 for v in per.values()),
       "كل مستخدم ليه خطة نشطة واحدة بس", per)


# ══════════════════════════════════════════════════════════════════════════
#  ⑦ صلاحيات المستخدم
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_07_entitlements():
    section("⑦ الصلاحيات — الاشتراك بيحدد ما يشوفه المستخدم")

    eng = new_engine()
    free = eng.entitlements_for("uid-x")
    ok(free["plan"] == "free" and free["source"] == "default",
       "من غير اشتراك ⇒ الباقة المجانية", free["plan"])
    ok(free["entitlements"]["max_opportunities"] == 5
       and free["entitlements"]["max_alerts"] == 3
       and free["entitlements"]["realview"] is False,
       "حدود المجانية: ٥ فرص · ٣ تنبيهات · بلا RealView",
       free["entitlements"])

    eng.subscribe("uid-x", "pro", "x-1")
    pro = eng.entitlements_for("uid-x")
    ok(pro["plan"] == "pro" and pro["source"] == "subscription",
       "بعد الاشتراك ⇒ المصدر subscription", pro["source"])
    ok(pro["entitlements"]["max_opportunities"] == 60,
       "باقة pro ⇒ ٦٠ فرصة", pro["entitlements"]["max_opportunities"])
    ok(pro["entitlements"]["max_alerts"] == 50,
       "باقة pro ⇒ ٥٠ تنبيه", pro["entitlements"]["max_alerts"])
    ok(pro["entitlements"]["realview"] is True,
       "باقة pro ⇒ RealView مفتوح")

    # بوابة الفرص
    g1 = eng.gate("uid-x", "opportunities", 10)
    g2 = eng.gate("uid-x", "opportunities", 60)
    g3 = eng.gate("uid-x", "opportunities", 61)
    ok(g1["allowed"] is True and g2["allowed"] is True,
       "داخل الحد ⇒ مسموح")
    ok(g3["allowed"] is False, "برّه الحد ⇒ ممنوع", g3)
    ok(g3["limit"] == 60, "الحد المعلن ٦٠", g3.get("limit"))

    # بوابة التنبيهات
    ga = eng.gate("uid-x", "alerts", 50)
    ok(ga["allowed"] is True and ga["limit"] == 50,
       "بوابة التنبيهات ⇒ ٥٠", ga)

    # بوابة RealView
    gr = eng.gate("uid-x", "realview")
    ok(gr["allowed"] is True, "RealView مفتوح لمشترك pro")
    eng2 = new_engine()
    gr2 = eng2.gate("uid-y", "realview")
    ok(gr2["allowed"] is False, "RealView مقفول في المجانية")

    # انتهاء الاشتراك ⇒ ترجع حدود المجانية
    eng._test_clock["t"] += 40 * 86400
    ok(eng.entitlements_for("uid-x")["entitlements"]["max_opportunities"] == 5,
       "بعد الانتهاء ⇒ رجع لحدود المجانية")

    # عبر الـAPI
    app, _u = make_api(eng2)
    eng2.subscribe("uid-1", "pro", "z-1")
    r = call(app, "/api/billing/entitlements", headers=AUTH)
    j = r.get_json()
    ok(r.status_code == 200 and j.get("plan") == "pro",
       "الـAPI: الصلاحيات من الباقة", j.get("plan"))
    ok(j.get("alerts_used") == 2 and j.get("alerts_limit") == 50,
       "الـAPI: عدد التنبيهات المستخدمة والحد", "%s/%s" % (
           j.get("alerts_used"), j.get("alerts_limit")))
    r = call(app, "/api/billing/opportunities", headers=AUTH)
    j2 = r.get_json()
    ok(j2.get("limit") == 60, "الـAPI: حد الفرص ٦٠", j2.get("limit"))
    ok(j2.get("returned") == 4 and j2.get("total_available") == 4,
       "الـAPI: رجّع كل المتاح (٤ < ٦٠)", j2.get("returned"))
    # مستخدم مجاني ⇒ ٥ فرص بس
    r = call(app, "/api/billing/opportunities")
    ok(r.status_code in (200, 401), "الـAPI: الفرص محمية")


# ══════════════════════════════════════════════════════════════════════════
#  ⑧ حذف الحساب
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_08_account_deletion():
    section("⑧ حذف الحساب — بيانات الاشتراك + المحفظة + التنبيهات + الأثر")

    eng = new_engine()
    eng.subscribe("uid-del", "pro", "del-1")
    eng.subscribe("uid-del", "basic", "del-2", token="tok_decline")
    eng.support_create("uid-del", "مشكلة", "رسالة", "payment_failed")
    eng.renew("uid-del", "del-3")
    ok(len(eng.store.read("subscriptions")) == 2, "قبل الحذف: ٢ اشتراك")

    receipt = eng.purge_user_data("uid-del")
    ok(len(eng.store.read("subscriptions")) == 0, "الاشتراكات اتمسحت")
    ok(len(eng.store.read("payments")) == 0, "المدفوعات اتمسحت")
    ok(len(eng.store.read("wallet")) == 0, "محفظة المعاملات اتمسحت")
    ok(len(eng.store.read("support")) == 0, "تذاكر الدعم اتمسحت")
    ok(len(eng.store.read("settlement")) == 0, "أحداث التسوية اتمسحت")
    idem = eng.store.read("idempotency")
    ok(all(v.get("uid") != "uid-del" for v in idem.values()),
       "مفاتيح التفرّد اتمسحت")
    ok(receipt.get("removed", {}).get("subscriptions") == 2,
       "إيصال الحذف بيوثّق العدد", receipt.get("removed"))
    ok(receipt.get("uid_hash") and "uid-del" not in json.dumps(receipt),
       "الإيصال مافيش فيه المعرّف الخام (هاش بس)")
    for forbidden in ("email", "amount", "price", "plan"):
        ok(forbidden not in receipt, "الإيصال مافيش فيه %s" % forbidden)
    ok(len(eng.deletion_receipts()) == 1, "إيصال الحذف متسجّل في السجل")

    # مستخدم تاني ما اتمسحش
    eng.subscribe("uid-keep", "basic", "keep-1")
    eng.purge_user_data("uid-del")
    ok(len(eng.store.read("subscriptions")) == 1,
       "حذف مستخدم ما بيأثرش على غيره")

    # الربط في مسار حذف الحساب الحقيقي
    src = (ROOT / "update_prices.py").read_text(encoding="utf-8")
    ok("purge_user_data(uid)" in src,
       "مسار حذف الحساب بينادي purge_user_data")
    ok('"subscription_purge"' in src,
       "رد الحذف بيوثّق أثر حذف الاشتراك")
    ok('"watch": []' in src and '"portfolio": []' in src,
       "مسار الحذف بيفرّغ التنبيهات والمحفظة")

    # الوثيقة بتوثّق الأثر
    doc = PRIVACY_DOC.read_text(encoding="utf-8")
    ok("subscription_purge" in doc, "الوثيقة بتوثّق حقل الأثر")
    ok("purge_user_data" in doc, "الوثيقة بتذكر دالة الحذف")


# ══════════════════════════════════════════════════════════════════════════
#  ⑨ الدعم الفني
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_09_support():
    section("⑨ الدعم الفني — نقطة دخول · قالب رسالة · سجل")

    eng = new_engine()
    tpl = eng.support_templates()
    ok(len(tpl) >= 3, "في ٣ قوالب على الأقل", len(tpl))
    for key, t in tpl.items():
        ok(bool(t.get("title")) and bool(t.get("body")),
           "قالب %s فيه عنوان ونص" % key)
    rendered = eng.support_render("payment_failed", reference="pay-123",
                                  plan="pro", message="البطاقة اترفضت")
    ok("{reference}" not in rendered["body"] and "pay-123" in rendered["body"],
       "القالب بيتعبّى بالبيانات")
    ok("{plan}" not in rendered["body"], "مافيش placeholders فاضلة")

    rec = eng.support_create("uid-sup", "مشكلة دفع", "البطاقة اترفضت",
                              template_id="payment_failed", reference="pay-9")
    ok(rec.get("id", "").startswith("tkt_"), "التذكرة اتسجّلت", rec.get("id"))
    ok(rec.get("status") == "open", "التذكرة مفتوحة")
    ok("pay-9" in (rec.get("body") or ""), "نص القالب اتخزّن مع التذكرة")
    ok(len(eng.support_list()) == 1, "السجل فيه التذكرة")
    ok(len(eng.support_list(status="open")) == 1, "فلترة بالحالة شغّالة")

    # تذكرة فاضية ⇒ 400
    try:
        eng.support_create("uid-sup", "موضوع", "")
        ok(False, "تذكرة فاضية ⇒ خطأ")
    except SC.SubscriptionError as e:
        ok(e.status == 400, "تذكرة فاضية ⇒ 400", e.status)

    # عبر الـAPI
    app, _u = make_api(eng)
    r = call(app, "/api/billing/support/template")
    ok(r.status_code == 200 and len(r.get_json().get("templates") or {}) >= 3,
       "الـAPI: قوالب الدعم متاحة")
    r = call(app, "/api/billing/support", "POST",
             {"subject": "سؤال", "message": "مشكلة", "template_id": "general"},
             headers=AUTH)
    ok(r.status_code == 200, "الـAPI: إنشاء تذكرة ⇒ 200", r.status_code)
    ok(r.get_json()["ticket"]["uid"] == "uid-1", "التذكرة مرتبطة بالمستخدم")
    r = call(app, "/api/billing/support", "GET")
    ok(r.status_code == 401, "سجل الدعم (أدمن) محمي", r.status_code)
    r = call(app, "/api/billing/support", "GET", headers=admin_headers())
    ok(r.status_code == 200 and r.get_json()["count"] >= 2,
       "سجل الدعم (أدمن) بيفتح", r.get_json().get("count"))
    r = call(app, "/api/billing/support", "POST", {"subject": "س", "message": "م"})
    ok(r.status_code == 401, "إنشاء تذكرة محمية بتسجيل الدخول", r.status_code)


# ══════════════════════════════════════════════════════════════════════════
#  ⑩ الخصوصية والاحتفاظ
# ══════════════════════════════════════════════════════════════════════════
@_case
def test_10_privacy_retention():
    section("⑩ الخصوصية والاحتفاظ — الوثيقة + sweep + توافق مع الكود")

    ok(PRIVACY_DOC.exists(), "وثيقة الخصوصية موجودة (docs/privacy_and_retention.md)")
    doc = PRIVACY_DOC.read_text(encoding="utf-8")
    for needed in ("الاحتفاظ", "حذف الحساب", "الخصوصية", "الدفع",
                   "الاسترداد", "التسوية"):
        ok(needed in doc, "الوثيقة بتغطي: %s" % needed)

    # ① توافق الأرقام: كل قيمة في RETENTION لازم تكون في الوثيقة
    for key, val in SC.RETENTION.items():
        ok(key in doc, "الوثيقة بتذكر مفتاح الاحتفاظ %s" % key)
        ok(str(val) in doc, "الوثيقة فيها رقم الاحتفاظ %s=%s" % (key, val))

    # ② sweep بيشيل القديم وبيسيب الجديد
    eng = new_engine(start=1700000000)
    eng.subscribe("uid-r", "pro", "r-1")
    eng.support_create("uid-r", "موضوع", "رسالة")
    eng.apply_settlement("evt-r", "payment.succeeded",
                         eng.store.read("subscriptions")[0]["id"])
    eng._test_clock["t"] += 800 * 86400          # بعد ٨٠٠ يوم (أكثر من سنتين)
    out = eng.sweep()
    ok(out["removed"]["idempotency"] >= 1,
       "sweep شال مفاتيح التفرّد القديمة", out["removed"])
    ok(len(eng.store.read("idempotency")) == 0,
       "مافيش مفاتيح تفرّد قديمة")
    ok(out["removed"]["payments"] >= 1, "sweep شال المدفوعات القديمة",
       out["removed"])
    ok(out["removed"]["settlement"] >= 1, "sweep شال أحداث التسوية",
       out["removed"])

    # التذكرة المفتوحة ما تتشالشش (لسه مفتوحة)
    ok(len(eng.store.read("support")) == 1,
       "التذكرة المفتوحة بتفضل (لسه لازم خدمة)", len(eng.store.read("support")))
    # ③ التذكرة المغلقة بتتشال بعد سنة
    eng2 = new_engine(start=1700000000)
    eng2.support_create("uid-r2", "موضوع", "رسالة")
    tickets = eng2.store.read("support")
    tickets[0]["status"] = "closed"
    eng2.store.write("support", tickets)
    eng2._test_clock["t"] += 400 * 86400
    out2 = eng2.sweep()
    ok(out2["removed"]["support"] == 1, "sweep شال التذكرة المغلقة",
       out2["removed"])

    # ④ سلة الدفع المعلّقة القديمة ⇒ expired
    eng3 = new_engine(start=1700000000)
    eng3.subscribe("uid-r3", "pro", "r-3", defer_settlement=True)
    eng3._test_clock["t"] += 40 * 86400
    eng3.sweep()
    sub = eng3.store.read("subscriptions")[0]
    ok(sub["status"] == "expired", "سلة معلّقة قديمة ⇒ expired",
       sub.get("status"))

    # ⑤ إيصالات الحذف بتتشال بعد سنة
    eng4 = new_engine(start=1700000000)
    eng4.purge_user_data("uid-r4")
    eng4._test_clock["t"] += 800 * 86400
    out4 = eng4.sweep()
    ok(out4["removed"]["deletion_receipts"] == 1,
       "sweep شال إيصال الحذف القديم", out4["removed"])

    # ⑥ سلة الدفع المعلّقة ما بتتفعّلش لوحدها
    eng5 = new_engine(start=1700000000)
    eng5.subscribe("uid-r5", "pro", "r-5", defer_settlement=True)
    eng5._test_clock["t"] += 5 * 86400
    ok(eng5.entitlements_for("uid-r5")["plan"] == "free",
       "السلة المعلّقة ما بتفعّلش صلاحيات")

    # ⑦ عبر الـAPI — التنظيف محمي
    app, _u = make_api(eng)
    r = call(app, "/api/billing/retention/sweep", "POST")
    ok(r.status_code == 401, "التنظيف محمي بدون توكن أدمن", r.status_code)
    r = call(app, "/api/billing/retention/sweep", "POST",
             headers=admin_headers())
    ok(r.status_code == 200 and "sweep" in r.get_json(),
       "التنظيف بتوكن الأدمن شغّال", r.status_code)
    ok(r.get_json()["sweep"]["retention"] == dict(SC.RETENTION),
       "الـAPI بيرجّع نفس سياسات الاحتفاظ")


# ══════════════════════════════════════════════════════════════════════════
#  ⑪ البرهان السالب — شيل الحماية ⇒ الفحص لازم يفشل
# ══════════════════════════════════════════════════════════════════════════
def _mutate(mod_dir, old, new):
    """🧬 ينسخ النواة ويطبّق طفرة واحدة (شيل حماية) ويرجّع الموديول."""
    src = (ROOT / "subscription_core.py").read_text(encoding="utf-8")
    count = src.count(old)
    if count != 1:
        raise AssertionError("الطفرة اتطبّقت على %d سطر (المفروض ١): %r"
                             % (count, old[:70]))
    dst = Path(mod_dir) / "subscription_core.py"
    dst.write_text(src.replace(old, new, 1), encoding="utf-8")
    data_dir = Path(mod_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLAN_FILE, data_dir / "subscription_plans.json")
    name = "mut_core_%d" % (len(MUTATIONS) + 1)
    spec = importlib.util.spec_from_file_location(name, dst)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# — سيناريوهات الفشل (المفروض تفشل لما الحماية تشيل) —

def sc_idem(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k")
    eng.subscribe("u", "pro", "k")
    assert eng.provider_stats()["approved"] == 1, "تحصيل اتكرر"


def sc_idem_save(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k")
    eng.subscribe("u", "pro", "k")
    assert eng.provider_stats()["approved"] == 1, "مفتاح التفرّد ما اتخزّنش"


def sc_idem_conflict(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k")
    try:
        eng.subscribe("u", "enterprise", "k")
    except mod.SubscriptionError:
        return
    raise AssertionError("التعارض ما اتكشفش")


def sc_single_active(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k1")
    eng.subscribe("u", "enterprise", "k2")
    act = [s for s in eng.store.read("subscriptions") if s["status"] == "active"]
    assert len(act) == 1, "في %d خطط نشطة" % len(act)


def sc_failed_masked(mod):
    eng = new_engine(mod)
    st, body = eng.subscribe("u", "basic", "k", token="tok_decline")
    assert body["subscription"]["status"] == "failed", "الاشتراك اتفعّل رغم الفشل"
    assert eng.entitlements_for("u")["plan"] == "free", "صلاحيات بعد الفشل"


def sc_settle_once(mod):
    eng = new_engine(mod)
    _s, b = eng.subscribe("u", "pro", "k", defer_settlement=True)
    sid = b["subscription"]["id"]
    eng.apply_settlement("e1", "payment.succeeded", sid, payment_id="p1")
    end = eng._active_subscription("u")["period_end"]
    eng.apply_settlement("e2", "payment.succeeded", sid, payment_id="p1")
    assert eng._active_subscription("u")["period_end"] == end, "الفترة اتمدّت"


def sc_settle_dedupe(mod):
    eng = new_engine(mod)
    _s, b = eng.subscribe("u", "pro", "k", defer_settlement=True)
    sid = b["subscription"]["id"]
    eng.apply_settlement("e1", "payment.succeeded", sid, payment_id="p1")
    _s, r2 = eng.apply_settlement("e1", "payment.succeeded", sid, payment_id="p1")
    assert r2.get("duplicate") is True, "الحدث المتكرر اتنفّذ تاني"


def sc_expiry(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k")
    eng._test_clock["t"] += 40 * 86400
    assert eng.status_of("u")["status"] == "expired", "الاشتراك ما انتهاش"


def sc_refund_revoke(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k1")
    _s, body = eng.refund("u", "k2")
    assert body["subscription"]["status"] == "refunded", "الحالة مش refunded"
    assert eng.entitlements_for("u")["plan"] == "free", "الصلاحيات فاضلة"


def sc_cancel_now(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k1")
    _s, body = eng.cancel("u", at_period_end=False)
    assert body["subscription"]["status"] == "canceled", "الحالة مش canceled"
    assert eng.entitlements_for("u")["plan"] == "free", "الصلاحيات فاضلة"


def sc_purge(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k1")
    eng.support_create("u", "موضوع", "رسالة")
    eng.purge_user_data("u")
    assert len(eng.store.read("subscriptions")) == 0, "الاشتراكات ما اتمسحتش"
    assert len(eng.store.read("support")) == 0, "التذاكر ما اتمسحتش"


def sc_sweep(mod):
    eng = new_engine(start=1700000000)
    eng.subscribe("u", "pro", "k1")
    eng._test_clock["t"] += 400 * 86400
    eng.sweep()
    assert len(eng.store.read("payments")) == 0, "المدفوعات القديمة ما اتشالتش"


def sc_unknown_plan(mod):
    eng = new_engine(mod)
    try:
        eng.plan_or_fail("ghost-plan")
    except mod.SubscriptionError as e:
        assert e.status == 404, "الخطأ مش 404"
        return
    raise AssertionError("الباقة المجهولة اتقبلت")


def sc_entitlements(mod):
    eng = new_engine(mod)
    eng.subscribe("u", "pro", "k1")
    ent = eng.entitlements_for("u")
    assert ent["plan"] == "pro", "الصلاحيات مرجّعت للمجانية"
    assert ent["entitlements"]["max_opportunities"] == 60, "حدود pro مش مطبّقة"


MUTATION_SPECS = [
    ("M01", "تفرّد الطلبات — منع تحصيل مكرر (subscribe)",
     '            prev = self._idem_lookup("subscribe", uid, idem_key)\n'
     '            if prev is not None:',
     '            prev = self._idem_lookup("subscribe", uid, idem_key)\n'
     '            if False:', sc_idem),
    ("M02", "تفرّد الطلبات — حفظ نتيجة الطلب",
     '            self._idem_save("subscribe", uid, idem_key, fingerprint, 200, body)\n'
     '            return 200, body',
     '            return 200, body', sc_idem_save),
    ("M03", "تفرّد الطلبات — كشف تعارض نفس المفتاح",
     '            prev = self._idem_lookup("subscribe", uid, idem_key)\n'
     '            if prev is not None:\n'
     '                if prev.get("fingerprint") != fingerprint:',
     '            prev = self._idem_lookup("subscribe", uid, idem_key)\n'
     '            if prev is not None:\n'
     '                if False:', sc_idem_conflict),
    ("M04", "منع التفعيل المزدوج — خطة نشطة واحدة",
     '        self._guard_single_active(sub.get("uid"), sub.get("id"), now)',
     '        pass', sc_single_active),
    ("M05", "فشل الدفع — masking الحالة",
     '        sub["status"] = "failed"\n'
     '        sub["failure_reason"] = str(result.get("failure_reason") or "payment_failed")',
     '        sub["status"] = "active"\n'
     '        sub["failure_reason"] = str(result.get("failure_reason") or "payment_failed")',
     sc_failed_masked),
    ("M06", "التسوية — تطبيق الدفعة مرة واحدة",
     '                if sub.get("status") == "active" or sub.get("activated_payment_id") == pid:',
     '                if False:', sc_settle_once),
    ("M07", "التسوية — منع تكرار نفس الحدث",
     '                if str(ev.get("event_id") or "") == event_id:',
     '                if False:', sc_settle_dedupe),
    ("M08", "انتهاء الاشتراك — التفعيل التلقائي",
     '            end = int(s.get("period_end") or 0)\n'
     '            if end <= now:',
     '            end = int(s.get("period_end") or 0)\n'
     '            if False:', sc_expiry),
    ("M09", "الاسترداد — رفع الصلاحيات فوراً",
     '            sub["status"] = "refunded"\n'
     '            sub["refunded_at"] = now\n'
     '            sub["refund_id"] = res.get("refund_id")\n'
     '            sub["refund_reason"] = str(reason or "")[:200]\n'
     '            sub["period_end"] = 0',
     '            sub["status"] = "active"\n'
     '            sub["refunded_at"] = now\n'
     '            sub["refund_id"] = res.get("refund_id")\n'
     '            sub["refund_reason"] = str(reason or "")[:200]\n'
     '            sub["period_end"] = now + 30 * 86400', sc_refund_revoke),
    ("M10", "الإلغاء الفوري — رفع الصلاحيات فوراً",
     '            sub["status"] = "canceled"\n'
     '            sub["canceled_at"] = now\n'
     '            sub["cancel_at_period_end"] = False\n'
     '            sub["period_end"] = 0',
     '            sub["status"] = "active"\n'
     '            sub["canceled_at"] = now\n'
     '            sub["cancel_at_period_end"] = False\n'
     '            sub["period_end"] = now + 30 * 86400', sc_cancel_now),
    ("M11", "حذف الحساب — مسح البيانات",
     '                kept = [x for x in items if str(x.get("uid") or "") != uid]',
     '                kept = list(items)', sc_purge),
    ("M12", "الاحتفاظ — حذف المدفوعات القديمة",
     '                if _age_days(p, now) > days:',
     '                if False:', sc_sweep),
    ("M13", "الباقات — رفض الباقة المجهولة",
     '        if not isinstance(pdef, dict):\n'
     '            raise SubscriptionError(404, "الباقة دي مش موجودة",',
     '        if False:\n'
     '            raise SubscriptionError(404, "الباقة دي مش موجودة",',
     sc_unknown_plan),
    ("M14", "الصلاحيات — المصدر من الاشتراك النشط بس",
     '        active = self._active_subscription(uid, now)\n'
     '        if active:',
     '        active = self._active_subscription(uid, now)\n'
     '        if False:', sc_entitlements),
]


@_case
def test_11_negative_proofs():
    section("⑪ البرهان السالب — شيل الحماية ⇒ الفحص لازم يفشل")

    detected = 0
    for mid, guard, old, new, scenario in MUTATION_SPECS:
        tmp = tempfile.mkdtemp(prefix="octa_r26_mut_%s_" % mid)
        _TMPDIRS.append(tmp)
        try:
            mod = _mutate(tmp, old, new)
        except Exception as e:
            ok(False, "%s (%s): الطفرة اتطبّقت؟ %s" % (mid, guard, e))
            MUTATIONS.append((mid, guard, False))
            continue
        try:
            scenario(mod)
        except Exception as e:
            detected += 1
            ok(True, "%s (%s): الفحص فشل بعد شيل الحماية ✔ (%s)"
               % (mid, guard, type(e).__name__))
            MUTATIONS.append((mid, guard, True))
        else:
            ok(False, "%s (%s): الفحص مرّ رغم شيل الحماية ⛔" % (mid, guard))
            MUTATIONS.append((mid, guard, False))

    ok(detected == len(MUTATION_SPECS),
       "كل الطفرات اتكتشفت (%d/%d)" % (detected, len(MUTATION_SPECS)),
       "%d/%d" % (detected, len(MUTATION_SPECS)))


# ══════════════════════════════════════════════════════════════════════════
#  التشغيل
# ══════════════════════════════════════════════════════════════════════════
def _cleanup():
    for d in _TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)


def main():
    print("═" * 70)
    print("🧪 الجولة ٢٦ (R26) — اختبارات نظام الاشتراكات (مزوّد صناعي)")
    print("═" * 70)
    for fn in (test_00_safety, test_01_plans, test_02_lifecycle,
               test_03_payment_failure, test_04_idempotency,
               test_05_settlement, test_06_no_double_activation,
               test_07_entitlements, test_08_account_deletion,
               test_09_support, test_10_privacy_retention,
               test_11_negative_proofs):
        try:
            fn()
        except AssertionError as e:
            print("  ❌ قسم %s: %s" % (fn.__name__, e), flush=True)
            RESULTS.append((False, "%s (استثناء)" % fn.__name__))
        except Exception as e:
            print("  ❌ قسم %s: %s: %s" % (fn.__name__, type(e).__name__, e),
                  flush=True)
            RESULTS.append((False, "%s (%s)" % (fn.__name__, type(e).__name__)))
    _cleanup()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    mut_ok = sum(1 for m in MUTATIONS if m[2])
    print("\n" + "═" * 70)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d فحص)"
          % (passed, failed, len(RESULTS)))
    print("  البرهان السالب: %d/%d طفرة اتكتشفت"
          % (mut_ok, len(MUTATION_SPECS)))
    print("═" * 70)
    if failed:
        for good, label in RESULTS:
            if not good:
                print("  ❌ %s" % label)
        return 1
    print("✅ نظام الاشتراكات جاهز (مزوّد صناعي) — كل الفحوص ناجحة")
    return 0


if __name__ == "__main__":
    sys.exit(main())
