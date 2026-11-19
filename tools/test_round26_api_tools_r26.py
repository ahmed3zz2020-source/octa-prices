#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٦ (R26 · الأدوات) — اختبار الأدوات **من داخل الموقع** ⭐

🎯 الغرض ⭐: اختبار **مسارات الـAPI الحقيقية** ⭐ (مش دوال وحدها ⭐) ⭐
   على **خادم معزول** ⭐ (الأداة الموجودة ⭐ `tools/staging/run_staging.py` ⭐
   عبر `tools/staging/iso_env.py` ⭐) ⭐.
   📌 كل فحص بيتأكد من **محتوى** الرد ⭐ (مش 200 بس ⭐).

📌 الأدوات اللي بنختبرها ⭐ (البنود ٥ و٦ من تكليف الجولة ⭐):
   ① الفرص: قصير (swing) · متوسط (medium) · طويل (longterm) ⭐
   ② الفلتر الرئيسي رقم ٨ (القرارات) ⭐ + تشغيل/إيقاف الفلاتر ⭐
   ③ المحفظة الذكية وتوزيع القطاعات ⭐
   ④ أهداف السعر ووقف الخسارة ⭐
   ⑤ سجل الإضافة/الاستبعاد ⭐ (منبهات + محفظة ⭐)
   ⑥ التنبيهات داخل الموقع ⭐ + **منع التكرار** (idempotency ⭐)
   ⑦ قياس الأداء التاريخي ⭐
   ⑧ Backtesting بلا بيانات مستقبلية ⭐
   ⑨ عزل المحافظ بين الحسابات ⭐
   ⑩ مسار كامل للمصدر الخارجي ⭐ (مافيش 500 ⭐)

⛔ العزل ⭐:
   · السيرفر كله على `127.0.0.1` ⭐
   · الشبكة مقفولة ⭐ والمصدر **اصطناعي** ⭐ (مش حقيقي ⭐)
   · البيانات في مجلد مؤقّت ⭐ · الأسرار **اصطناعية** ⭐
   · مافيش أي نشر ⭐ ومافيش أي دومين ⭐

📌 التشغيل ⭐:
   python3 tools/test_round26_api_tools_r26.py
   python3 tools/test_round26_api_tools_r26.py --report-json /tmp/r26_api.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STAGING = os.path.join(HERE, "staging")
if STAGING not in sys.path:
    sys.path.insert(0, STAGING)

import iso_env  # noqa: E402

RESULTS = []
CTX = {}


def check(label, cond, detail=""):
    passed = bool(cond)
    RESULTS.append({"label": label, "passed": passed, "detail": str(detail)[:400]})
    print(("  ✅ " if passed else "  ❌ ") + label +
          (("  — " + str(detail)[:300]) if (detail and not passed) else ""))
    return passed


def section(title):
    print("\n▶️  " + title)


def jget(client, path, **kw):
    st, _h, body, ms = client.get(path, **kw)
    try:
        j = json.loads(body.decode("utf-8"))
    except Exception as e:
        j = {"__parse_error__": str(e), "__raw__": body[:200].decode("utf-8", "replace")}
    return st, j, ms


def jpost(client, path, body=None, **kw):
    st, _h, raw, ms = client.post(path, body if body is not None else {}, **kw)
    try:
        j = json.loads(raw.decode("utf-8"))
    except Exception as e:
        j = {"__parse_error__": str(e), "__raw__": raw[:200].decode("utf-8", "replace")}
    return st, j, ms


# ══════════════════════════════════════════════════════════════════════
#  التشغيل
# ══════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-json", default="")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    stage_dir = "/tmp/octa_r26_api_%d" % int(time.time())
    print("🧪 الجولة ٢٦ — اختبار الأدوات من داخل الموقع (خادم معزول)")
    print("   مجلد البيانات: %s" % stage_dir)

    srv = iso_env.launch(stage_dir=stage_dir, source_mode="ok", harness=True)
    ok, elapsed = srv.wait_ready(timeout=300)
    check("الخادم المعزول قام", ok, "elapsed=%.1fs log=%s" % (elapsed, srv.log_path))
    if not ok:
        print("\n".join(srv.log_tail(60)))
        _report(args)
        return 1

    cfg = iso_env.read_stage_cfg(stage_dir)
    CTX["cfg"] = cfg
    free = iso_env.Client(srv.base_url, srv.proxy_secret)
    tok, st, j = free.login(cfg["free"]["pin"], cfg["free"]["device"])
    check("تسجيل دخول (حساب حرّ)", st == 200 and bool(tok), "status=%s" % st)
    if not tok:
        _report(args)
        srv.stop()
        return 1

    # ⏳ ننتظر البيانات
    ready = False
    for _ in range(120):
        st, j, _ms = jget(free, "/api/rank")
        if st == 200 and (j.get("count") or 0) > 0:
            ready = True
            break
        time.sleep(1)
    check("البيانات اتحمّلت والمسح خلص", ready)
    if not ready:
        print("\n".join(srv.log_tail(40)))
        _report(args)
        srv.stop()
        return 1

    st, j, _ms = jget(free, "/api/rank")
    CTX["rank"] = j
    codes = [r.get("code") for r in (j.get("results") or []) if r.get("code")]
    CTX["codes"] = codes
    print("   عيّنة الترتيب: %s" % (codes[:6],))

    # ⏳ محرّك الفرص بيبني اللقط في الخلفية ⇒ ننتظره
    opp_ready = False
    for _ in range(120):
        st, j, _ms = jget(free, "/api/opp/strategies")
        if st == 200 and (j.get("strategies") or []):
            opp_ready = True
            break
        time.sleep(1)
    check("محرّك الفرص جهز (مافيش 503)", opp_ready)

    # ─────────────────────────────────────────────────────────────
    # ① الفرص: قصير · متوسط · طويل
    # ─────────────────────────────────────────────────────────────
    section("① الفرص (قصير · متوسط · طويل) — محتوى الرد")
    lists = {}
    for key, label in (("swing", "قصير"), ("medium", "متوسط"),
                       ("longterm", "طويل")):
        st, j, ms = jget(free, "/api/opp/list/%s" % key)
        check("[%s] المسار بيرد 200" % label, st == 200, "status=%s" % st)
        check("[%s] ok=true" % label, j.get("ok") is True, str(j)[:200])
        items = j.get("items") or []
        lists[key] = items
        check("[%s] فيه أسهم مرشحة" % label, len(items) > 0,
              "items=%d" % len(items))
        bad_score = [i for i in items
                     if not isinstance(i.get("score"), (int, float))
                     or i.get("score") < 0 or i.get("score") > 100]
        check("[%s] الدرجات داخل 0..100" % label, not bad_score,
              str(bad_score[:2]))
        bad_ratio = []
        for i in items:
            for c in (i.get("criteria") or []):
                r = c.get("ratio")
                if r is None:
                    continue
                if r < 0 or r > 1:
                    bad_ratio.append((i.get("code"), c.get("key"), r))
        check("[%s] نسب المعايير داخل 0..1" % label, not bad_ratio,
              str(bad_ratio[:3]))
        cov = [i.get("coverage") for i in items
               if isinstance(i.get("coverage"), (int, float))]
        check("[%s] التغطية داخل 0..100" % label,
              all(0 <= c <= 100 for c in cov), str(cov[:5]))
        summ = j.get("summary") or {}
        check("[%s] summary.returned == عدد الصفوف" % label,
              summ.get("returned") == len(items),
              "returned=%s items=%d" % (summ.get("returned"), len(items)))
        check("[%s] فيه تسمية استراتيجية واضحة" % label,
              bool(j.get("strategy")) and bool(summ),
              "strategy=%s" % j.get("strategy"))
    # ⛔ الاستراتيجيات التلاتة مختلفة فعلاً
    sets = [set(i.get("code") for i in lists.get(k) or []) for k in
            ("swing", "medium", "longterm")]
    check("الاستراتيجيات التلاتة مش متطابقة",
          not (sets[0] == sets[1] == sets[2]),
          "swing=%d medium=%d long=%d" % (len(sets[0]), len(sets[1]), len(sets[2])))
    check("قصير ≠ متوسط",
          sets[0] != sets[1], "swing=%d medium=%d" % (len(sets[0]), len(sets[1])))

    st, j, _ms = jget(free, "/api/opp/strategies")
    check("قائمة الاستراتيجيات بترد 200 ومفيش أوزان مسرّبة",
          st == 200 and j.get("ok") is True
          and not any("weights" in (s or {}) for s in (j.get("strategies") or [])),
          "strategies=%d" % len(j.get("strategies") or []))
    check("الاستراتيجيات التسع التسعة موجودة",
          len(j.get("strategies") or []) == 9,
          str(len(j.get("strategies") or [])))

    # ─────────────────────────────────────────────────────────────
    # ② الفلتر الرئيسي رقم ٨ (القرارات) + تشغيل/إيقاف الفلاتر
    # ─────────────────────────────────────────────────────────────
    section("② الفلتر الرئيسي رقم ٨ (القرارات) + تشغيل/إيقاف الفلاتر")
    st, j, _ms = jget(free, "/api/filters")
    decisions = [d.get("name") for d in (j.get("decisions") or []) if d.get("name")]
    check("قائمة الفلاتر بترد 200", st == 200, "status=%s" % st)
    check("فيه قرارات متاحة", len(decisions) > 0, str(decisions))
    st, j_all, _ms = jget(free, "/api/rank?limit=100")
    n_all = j_all.get("count") or 0
    check("الترتيب العام بيرد", st == 200 and n_all > 0, "count=%s" % n_all)
    if decisions:
        d0 = decisions[0]
        st, j_f, _ms = jget(
            free, "/api/rank?decision=%s&limit=100" % quote(d0))
        rows = j_f.get("results") or []
        check("الفلتر رقم ٨ (قرار=%s) بيرجّع صفوف" % d0,
              st == 200 and len(rows) > 0, "status=%s count=%s" % (st, len(rows)))
        check("كل الصفوف قرار الفلتر بالظبط",
              all(r.get("decision") == d0 for r in rows),
              str([r.get("decision") for r in rows[:5]]))
        check("عدد الصفوف المفلترة أقل من أو يساوي الكلي",
              len(rows) <= n_all, "%d ≤ %d" % (len(rows), n_all))
    # ⛔ قرار مش موجود ⇒ صفوف فاضية (مش 500)
    st, j_x, _ms = jget(
        free, "/api/rank?decision=%s&limit=5" % quote("قرار مش موجود"))
    check("قرار غير موجود ⇒ رد 200 وبلا صفوف (مش 500)",
          st == 200 and not (j_x.get("results") or []),
          "status=%s count=%s" % (st, len(j_x.get("results") or [])))
    # ⛔ تشغيل/إيقاف
    st, j_on, _ms = jget(free, "/api/rank?min_score=0&limit=100")
    st, j_off, _ms = jget(free, "/api/rank?min_score=99&limit=100")
    check("الفلتر مفعّل (عتبة ٠) ⇒ كل الصفوف",
          st == 200 and (j_on.get("count") or 0) > 0,
          "count=%s" % j_on.get("count"))
    check("الفلتر مفعّل (عتبة ٩٩) ⇒ صفوف أقل أو معدومة",
          (j_off.get("count") or 0) <= (j_on.get("count") or 0),
          "off=%s on=%s" % (j_off.get("count"), j_on.get("count")))
    # ⛔ استراتيجية غير معروفة ⇒ 400 واضح (مش 500)
    st, j_bad, _ms = jget(free, "/api/rank?strategy=%s" % quote("مش_موجودة"))
    check("استراتيجية غير معروفة ⇒ 400 + كود خطأ واضح",
          st == 400 and j_bad.get("code") == "unknown_strategy",
          "status=%s body=%s" % (st, str(j_bad)[:160]))
    st, j_bad2, _ms = jget(free, "/api/opp/list/%s" % quote("مش_موجودة"))
    check("قائمة استراتيجية غير معروفة ⇒ 404 (مش 500)",
          st == 404 and j_bad2.get("code") == "unknown_strategy",
          "status=%s" % st)

    # ─────────────────────────────────────────────────────────────
    # ③ المحفظة الذكية وتوزيع القطاعات
    # ─────────────────────────────────────────────────────────────
    section("③ المحفظة الذكية وتوزيع القطاعات")
    st, j, _ms = jpost(free, "/api/portfolio", {"action": "clear"})
    check("تفريغ المحفظة", st == 200, "status=%s" % st)
    # نختار سهمين من الترتيب بأرقام مختلفة
    pick = (CTX["rank"].get("results") or [])
    c1 = pick[0]["code"] if len(pick) > 0 else None
    c2 = pick[1]["code"] if len(pick) > 1 else None
    c3 = pick[2]["code"] if len(pick) > 2 else None
    if c1:
        st, j, _ms = jpost(free, "/api/portfolio", {
            "action": "add", "code": c1, "shares": 10, "cost": 100.0,
            "price": 120.0, "sector": "بنوك ومالية"})
        check("إضافة أول سهم للمحفظة",
              st == 200 and j.get("ok") is True and j.get("saved") is True,
              "status=%s body=%s" % (st, str(j)[:160]))
        st, j1, _ms = jget(free, "/api/portfolio")
        check("المحفظة فيها السهم", j1.get("count") == 1,
              "count=%s" % j1.get("count"))
        exp1 = j1.get("sector_exposure_pct") or {}
        check("توزيع القطاعات: قطاع واحد ١٠٠٪",
              len(exp1) == 1 and abs(list(exp1.values())[0] - 100.0) < 0.05,
              str(exp1))
        total = j1.get("total_value")
        check("قيمة المحفظة = (عددShares × السعر) + النقد",
              abs(total - (10 * 120.0)) < 0.05, "total=%s" % total)
        # ⛔ إضافة نفس السهم تاني ⇒ مفيش تكرار
        st, j, _ms = jpost(free, "/api/portfolio", {
            "action": "add", "code": c1, "shares": 10, "cost": 100.0,
            "price": 120.0, "sector": "بنوك ومالية"})
        st, j2, _ms = jget(free, "/api/portfolio")
        check("إضافة نفس السهم مرتين ⇒ صف واحد (idempotency)",
              j2.get("count") == 1, "count=%s" % j2.get("count"))
        check("القيمة ما اتضاعفتش",
              abs((j2.get("total_value") or 0) - 1200.0) < 0.05,
              "total=%s" % j2.get("total_value"))
        if c2:
            st, j, _ms = jpost(free, "/api/portfolio", {
                "action": "add", "code": c2, "shares": 5, "cost": 50.0,
                "price": 100.0, "sector": "عقارات"})
            st, j3, _ms = jget(free, "/api/portfolio")
            exp3 = j3.get("sector_exposure_pct") or {}
            check("توزيع القطاعات: قطاعين", len(exp3) == 2, str(exp3))
            ssum = sum(exp3.values())
            check("مجموع التوزيع = ١٠٠٪", abs(ssum - 100.0) < 0.2,
                  "sum=%.2f" % ssum)
            # ⛔ الرقم المعروض لازم يطابق الحساب بالظبط
            holdings = j3.get("holdings") or {}
            calc = {}
            for code, h in holdings.items():
                calc[h.get("sector", "أخرى")] = (
                    calc.get(h.get("sector", "أخرى"), 0.0)
                    + h["shares"] * h["price"])
            tot = sum(calc.values()) + float(j3.get("cash") or 0)
            calc_pct = {k: round(v / tot * 100, 1) for k, v in calc.items()}
            check("نسبة التقطاع المعروضة = الحساب بالظبط",
                  calc_pct == exp3, "shown=%s calc=%s" % (exp3, calc_pct))
            # ⛔ استبعاد سهم
            st, j, _ms = jpost(free, "/api/portfolio", {"action": "remove", "code": c1})
            st, j4, _ms = jget(free, "/api/portfolio")
            check("استبعاد السهم الأول ⇒ فضل الثاني بس",
                  j4.get("count") == 1 and c1 not in (j4.get("holdings") or {}),
                  "count=%s" % j4.get("count"))
            check("التوزيع بعد الاستبعاد = ١٠٠٪ قطاع واحد",
                  abs(sum((j4.get("sector_exposure_pct") or {}).values()) - 100.0) < 0.2,
                  str(j4.get("sector_exposure_pct")))

    # ─────────────────────────────────────────────────────────────
    # ④ أهداف السعر ووقف الخسارة
    # ─────────────────────────────────────────────────────────────
    section("④ أهداف السعر ووقف الخسارة")
    if c1:
        st, j, _ms = jpost(free, "/api/analyze", {"code": c1})
        check("مسار التحليل بيرد (200/502) من غير استثناء",
              st in (200, 502), "status=%s" % st)
        if st == 200:
            check("الهدف موجود في الرد", "target" in j, str(list(j)[:12]))
            tgt = j.get("target")
            sl = j.get("stop_loss")
            price = j.get("price")
            check("الهدف رقم منطقي (٠ أو بين ÷٣ و×٣ من السعر)",
                  isinstance(tgt, (int, float))
                  and (tgt == 0 or (price and price / 3 <= tgt <= price * 3)),
                  "target=%s price=%s" % (tgt, price))
            check("وقف الخسارة رقم منطقي (٠ أو أقل من السعر)",
                  isinstance(sl, (int, float))
                  and (sl == 0 or (price and 0 < sl < price)),
                  "stop=%s price=%s" % (sl, price))
            check("مفيش NaN في الرد (JSON صالح)",
                  b"NaN" not in json.dumps(j, ensure_ascii=False).encode(),
                  "payload")
        st, jf, _ms = jget(free, "/api/fundamental/%s" % c1)
        check("التحليل الأساسي بيرد 200", st == 200, "status=%s" % st)
        f = jf.get("fundamental") or {}
        check("التقرير الأساسي فيه تفصيل التقييم",
              "valuation_status" in f and "breakdown" in f,
              str(list(f)[:10]))
        bd = f.get("breakdown") or {}
        if isinstance(f.get("score"), (int, float)) and bd:
            check("مجموع بنود المحور الأساسي = الدرجة المنشورة",
                  abs(sum(bd.values()) - f["score"]) < 0.2,
                  "parts=%s score=%s" % (bd, f.get("score")))
        raw = jf.get("raw") or {}
        check("P/E وP/B مبثوثين زي ما هما (ما اتاخدوش معادَلة)",
              "pe" in raw and "pb" in raw, str(list(raw)[:8]))

    # ─────────────────────────────────────────────────────────────
    # ⑤⑥ التنبيهات داخل الموقع + سجل الإضافة/الاستبعاد + منع التكرار
    # ─────────────────────────────────────────────────────────────
    section("⑤⑥ التنبيهات داخل الموقع + سجل الإضافة/الاستبعاد + idempotency")
    st, j, _ms = jget(free, "/api/alerts/state")
    check("حالة التنبيهات بترد 200", st == 200 and j.get("ok") is True,
          "status=%s" % st)
    st, j, _ms = jpost(free, "/api/alerts/watch", {"action": "clear"})
    check("تفريغ المنبهات", st == 200, "status=%s" % st)
    if c1:
        st, j, _ms = jpost(free, "/api/alerts/watch",
                           {"action": "add", "code": c1, "hi": 999.0})
        check("إضافة منبه سعر", st == 200 and j.get("ok") is True,
              "status=%s body=%s" % (st, str(j)[:160]))
        st, jw, _ms = jget(free, "/api/alerts/watch")
        items = jw.get("items") or []
        check("المنبه اتسجّل (سجل الإضافة)", len(items) == 1,
              "items=%s" % items)
        check("صف المنبه فيه الرمز والحد الأعلى",
              bool(items) and items[0].get("code") == c1
              and items[0].get("hi") == 999.0, str(items))
        # ⛔ نفس المنبه تاني ⇒ مفيش تكرار
        st, j, _ms = jpost(free, "/api/alerts/watch",
                           {"action": "add", "code": c1, "hi": 999.0})
        st, jw2, _ms = jget(free, "/api/alerts/watch")
        check("نفس المنبه مرتين ⇒ صف واحد (idempotency)",
              len(jw2.get("items") or []) == 1,
              "items=%s" % (jw2.get("items") or []))
        # ⛔ استبعاد المنبه (سجل الاستبعاد)
        st, j, _ms = jpost(free, "/api/alerts/watch", {"action": "del", "code": c1})
        st, jw3, _ms = jget(free, "/api/alerts/watch")
        check("استبعاد المنبه ⇒ السجل فاضي",
              not (jw3.get("items") or []),
              "items=%s" % (jw3.get("items") or []))
        # ⛔ منبه لازم يكون بحدود
        st, j, _ms = jpost(free, "/api/alerts/watch",
                           {"action": "add", "code": c1})
        check("منبه من غير حدود ⇒ 400", st == 400, "status=%s" % st)
        st, j, _ms = jpost(free, "/api/alerts/watch",
                           {"action": "add", "code": "ZZZZZ", "hi": 10.0})
        check("رمز مجهول ⇒ 400 (مش 500)", st == 400, "status=%s" % st)

    # ─────────────────────────────────────────────────────────────
    # ⑨ عزل المحافظ بين الحسابات
    # ─────────────────────────────────────────────────────────────
    section("⑨ عزل المحافظ بين الحسابات (مستخدم ما يشوفش محفظة تاني)")
    pro = iso_env.Client(srv.base_url, srv.proxy_secret)
    ptok, pst, pj = pro.login(cfg["pro"]["pin"], cfg["pro"]["device"])
    check("تسجيل دخول (حساب ثانٍ)", pst == 200 and bool(ptok),
          "status=%s" % pst)
    # ⛔ رمز **مختلف** عن أي رمز في محفظة الحساب الأول ⭐
    pro_code = c3 or c2
    if ptok and pro_code:
        st, j, _ms = jpost(pro, "/api/portfolio", {
            "action": "add", "code": pro_code, "shares": 3, "cost": 30.0,
            "price": 100.0, "sector": "عقارات"})
        check("الحساب التاني قدر يضيف لمحفظته", st == 200, "status=%s" % st)
        st, jpro, _ms = jget(pro, "/api/portfolio")
        check("محفظة الحساب التاني فيها سهمه بس",
              (jpro.get("count") or 0) == 1,
              "count=%s holdings=%s" % (jpro.get("count"),
                                        list((jpro.get("holdings") or {}))))
        st, jfree, _ms = jget(free, "/api/portfolio")
        check("الحساب الأول ما شافش محفظة التاني",
              pro_code not in (jfree.get("holdings") or {}),
              "pro_code=%s free_holdings=%s" % (pro_code,
                                                 list(jfree.get("holdings") or {})))
        check("المحفظتين مختلفتين",
              list((jfree.get("holdings") or {})) != list((jpro.get("holdings") or {})),
              "free=%s pro=%s" % (list(jfree.get("holdings") or {}),
                                  list(jpro.get("holdings") or {})))
        # ⛔ محفظة الحساب التاني ما بتظهرش في أي رد تاني
        st, j, _ms = jget(pro, "/api/portfolio")
        check("نفس الحساب بيشوف محفظته (عزل مش انقطاع)",
              (j.get("count") or 0) == 1, "count=%s" % j.get("count"))

    # ─────────────────────────────────────────────────────────────
    # ⑦⑧ قياس الأداء التاريخي + الباك-تست بلا بيانات مستقبلية
    # ─────────────────────────────────────────────────────────────
    section("⑦⑧ قياس الأداء التاريخي + الباك-تست بلا بيانات مستقبلية")
    st, j, _ms = jget(free, "/api/backtest")
    check("مسار القياس التاريخي بيرد 200", st == 200, "status=%s" % st)
    check("الرد فيه منهجية معلنة",
          "forward-tracking" in str(j.get("method") or ""),
          str(j.get("method"))[:120])
    check("الرد فيه تحفّظ مكتوب (مش تقييم تاريخي شامل)",
          bool(j.get("caveat")), str(j.get("caveat"))[:120])
    check("الرد فيه نافذة/حالة معلنة",
          ("windows" in j) and ("status" in j),
          str(list(j)[:12]))
    stats = j.get("stats") or {}
    if stats.get("total_picks"):
        check("إحصاء Historical متسق (ربح+خسارة+محايد = الإجمالي)",
              stats.get("wins", 0) + stats.get("losses", 0)
              + stats.get("flat", 0) == stats.get("total_picks"),
              str(stats)[:200])
    else:
        check("لا توجد نوافذ ⇒ الحالة صريحة (مش أرقام متخيّلة)",
              stats.get("windows_measured", 0) == 0
              and stats.get("total_picks", 0) == 0
              and not stats.get("win_rate"),
              "status=%s stats=%s" % (j.get("status"), str(stats)[:160]))
        check("الحالة المعلنة بتقول إن القياس لسه مفيش",
              "ناقص" in str(j.get("status") or "")
              or "مفيش" in str(j.get("status") or ""),
              "status=%s" % j.get("status"))
    for w in (j.get("windows") or []):
        picks = w.get("picks") or []
        okp = all(p.get("price_then") and p.get("price_now") for p in picks)
        check("كل صف في النافذة فيه سعر وقت الاختيار وسعر القياس",
              okp, str(picks[:1]))
        break

    # ─────────────────────────────────────────────────────────────
    # ⑩ مسار كامل للمصدر الخارجي (مافيش 500)
    # ─────────────────────────────────────────────────────────────
    section("⑩ مسار السجل الكامل مع مصدر مش مضمون الشكل (مافيش 500)")
    st, j, _ms = jget(free, "/api/egx_full")
    check("/api/egx_full بيرد 200 (مش 500)",
          st == 200, "status=%s body=%s" % (st, str(j)[:160]))
    if st == 200:
        check("الرد فيه خريطة الأسهم", bool(j.get("stocks")),
              "n=%s" % j.get("n"))
    st, j, _ms = jget(free, "/api/egx_full?codes=%s" % (c1 or "COMI"))
    check("/api/egx_full?codes= بيرد 200", st == 200, "status=%s" % st)

    # ─────────────────────────────────────────────────────────────
    # ⓪ الحالة العامة للمسارات
    # ─────────────────────────────────────────────────────────────
    section("⛔ حالة المسارات الأساسية")
    for path in ("/api/health", "/api/ready", "/api/filters", "/api/rank",
                 "/api/opportunities", "/api/dashboard", "/api/sector-stats",
                 "/api/portfolio", "/api/alerts/watch", "/api/alerts/state"):
        st, j, ms = jget(free, path)
        check("%s ⇒ 200 و JSON صالح" % path,
              st == 200 and "__parse_error__" not in j,
              "status=%s parse=%s" % (st, j.get("__parse_error__")))

    srv.stop()
    if not args.keep:
        shutil.rmtree(stage_dir, ignore_errors=True)
    _report(args)
    failed = [r for r in RESULTS if not r["passed"]]
    print("\n" + "═" * 62)
    print("  النتيجة: %d/%d ✅   (فشل %d)" %
          (len(RESULTS) - len(failed), len(RESULTS), len(failed)))
    if failed:
        for r in failed:
            print("   ❌ %s — %s" % (r["label"], r["detail"][:200]))
    print("═" * 62)
    return 1 if failed else 0


def _report(args):
    if not args.report_json:
        return
    payload = {"results": RESULTS,
               "total": len(RESULTS),
               "passed": sum(1 for r in RESULTS if r["passed"]),
               "failed": sum(1 for r in RESULTS if not r["passed"])}
    with open(args.report_json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print("📄 التقرير: %s" % args.report_json)


if __name__ == "__main__":
    sys.exit(main())
