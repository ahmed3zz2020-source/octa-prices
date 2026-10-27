# -*- coding: utf-8 -*-
"""🧪 اختبار محرك السيناريوهات + الادخار — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش احتمالات** — ولا حقل probability ولا نسبة مختلقة في أي سيناريو.
 ② **مفيش وعود** — لا «مضمون» ولا «ضمان» ولا توصية شراء/بيع.
 ③ **كل هدف = مستوى مرصود فعلاً** من محرك التحليل الفني (مش نسبة مفترضة).
 ④ **كل سيناريو ليه شرط قابل للقياس + شرط إبطال**.
 ⑤ **الادخار: الاسمي والتضخم على نفس النافذة** — والجديد: الحقيقي ≤ الاسمي
    (في السوق المصري التضخم موجب ⇒ العائد الحقيقي أقل).
 ⑥ **إحصاء البقع تاريخي مرصود** (مش احتمال مستقبلي).
 ⑦ **as_of**: مفيش look-ahead.
 ⑧ **الخلاصة**: لازم تكون أسطر حتمية فيها أرقام من المصدر.
"""
import os, sys, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("GOLD_HISTORY_PATH", "/tmp/_gh_scenarios.json")
import gold_scenarios as gs

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def section(t):
    print("\n── %s ──" % t)


d = gs.build()
check(d.get("ok"), "المحرك اشتغل")

scs = {s["key"]: s for s in (d.get("scenarios") or [])}
check(len(scs) >= 3, "السيناريوهات: %d" % len(scs))

# ═════════════ ① مفيش احتمالات ═════════════
section("① مفيش احتمالات ولا نسب مختلقة")
blob = json.dumps(d, ensure_ascii=False).lower()
# ⛔ الكلمة ممنوعة **كمشكلة** — لازم تيجي منفي (زي «مش احتمال»)
NEG = ("مش", "مفيش", "لا ", "بدون", "ما ", "غير", "مستبعد", "أوف")
def _word_ok(text, word):
    for m in re.finditer(re.escape(word), text):
        ctx = text[max(0, m.start() - 40):m.end() + 10]
        if not any(n in ctx for n in NEG):
            return False, ctx
    return True, None

for bad in ("probability", "confidence", "odds", "chance"):
    check(bad not in blob, "مفيش «%s» في المخرجات" % bad)
for bad in ("احتمال", "توصية"):
    ok, ctx = _word_ok(blob, bad)
    check(ok, "كل ذكر لـ«%s» منفي%s" % (bad, (" — سياق: " + ctx) if ctx else ""))
# مفيش نسب مختلقة: كل نسب من نوع ٪ لازم تتنبّع لرقم مصدره معروف
for s in scs.values():
    for t in (s.get("targets") or []):
        if t.get("level") is not None:
            check(isinstance(t["level"], (int, float)),
                  "هدف %s = رقم حقيقي (%s)" % (s["key"], t["level"]))

# ═════════════ ② مفيش وعود ═════════════
section("② مفيش وعود ولا توصيات")
# ⛔ «توصية» اتفحصت فوق بسياقها (بتيجي منفي: «مفيش توصية شراء/بيع»)
for bad in ("مضمون", "ضمان", "نضمن", "اشترِ", "بيع الآن", "مضمون العائد"):
    check(bad not in blob, "مفيش «%s»" % bad)

# ═════════════ ③ الأهداف = مستويات مرصودة ═════════════
section("③ الأهداف من محرك التحليل الفني")
try:
    import gold_history as gh
    import gold_technical as gt
    hist = gh.build()
    an = gt.analyze(gt.bars_from(hist["series"], "gram"), label="جرام")
    real_levels = set()
    for z in ((an.get("sr") or {}).get("support") or []):
        real_levels.add(round(float(z["center"]), 1))
    for z in ((an.get("sr") or {}).get("resistance") or []):
        real_levels.add(round(float(z["center"]), 1))
    for z in ((an.get("sr") or {}).get("support") or []):
        real_levels.add(round(float(z["low"]), 1))
        real_levels.add(round(float(z["high"]), 1))
    for z in ((an.get("sr") or {}).get("resistance") or []):
        real_levels.add(round(float(z["low"]), 1))
        real_levels.add(round(float(z["high"]), 1))
    check(len(real_levels) > 5, "المستويات المرصودة: %d" % len(real_levels))
    for key in ("bull", "bear", "range"):
        for t in (scs.get(key) or {}).get("targets") or []:
            lv = t.get("level")
            if lv is None:
                check(bool(t.get("note")), "هدف %s بدون رقم ⇒ لازم سبب" % key)
                continue
            check(round(float(lv), 1) in real_levels,
                  "%s: الهدف %s موجود في المستويات المرصودة" % (key, lv))
except Exception as e:
    check(False, "فحص المستويات: %s" % str(e)[:80])

# ═════════════ ④ شرط + إبطال ═════════════
section("④ شرط قابل للقياس + شرط إبطال")
for key in ("bull", "bear", "range"):
    s = scs.get(key) or {}
    trig = s.get("trigger") or {}
    inv = s.get("invalidation") or {}
    check(bool((trig.get("text") or "").strip()), "%s: ليه شرط" % key)
    check(bool((inv.get("text") or "").strip()), "%s: ليه شرط إبطال" % key)
    check(bool((s.get("horizon") or "").strip()), "%s: ليه أفق زمني" % key)
    check(bool((s.get("what_to_watch") or [])), "%s: ليه قائمة متابعة" % key)
    check(bool((s.get("caveat") or "").strip()), "%s: ليه تحفّظ" % key)
    if trig.get("level") is not None:
        check(isinstance(trig["level"], (int, float)), "%s: شرطه رقم" % key)

# ═════════════ ⑤ الادخار: الاسمي والتضخم على نفس النافذة ═════════════
section("⑤ الادخار")
sv = d.get("savings") or {}
check(sv.get("ok"), "الادخار اتحسب")
rows = sv.get("rows") or []
check(len(rows) >= 4, "صفوف الادخار: %d" % len(rows))
for r in rows:
    rl = r.get("real") or {}
    if rl.get("real_pct") is None:
        check(bool(rl.get("note")) or bool(rl.get("inflation_note")),
              "%s سنة: الحقيقي مش متاح ⇒ لازم سبب" % r["years"])
        continue
    check(rl.get("window_from") and rl.get("window_to"),
          "%s سنة: نافذة الحقيقي معروفة" % r["years"])
    check(rl.get("inflation_pct") is not None,
          "%s سنة: فيه تضخم" % r["years"])
    # ⛔⛔ نافذة الحقيقي لازم تكون على نفس نافذة التضخم المتعلنة
    _last_cpi = (sv.get("inflation_last_year") or "") + "-12-31"
    check(rl.get("window_to") and _last_cpi and rl["window_to"] <= _last_cpi,
          "%s سنة: نافذة الحقيقي بتقفل مع آخر سنة تضخم (%s ≤ %s)"
          % (r["years"], rl.get("window_to"), _last_cpi))
    check(rl.get("nominal_pct") is not None and rl.get("window_from"),
          "%s سنة: العائد الاسمي للنافذة نفسها موجود" % r["years"])
    check(rl["real_pct"] <= rl["nominal_pct"] + 0.01,
          "%s سنة: الحقيقي (%.1f%%) ≤ الاسمي (%.1f%%) — لأن التضخم موجب"
          % (r["years"], rl["real_pct"], rl["nominal_pct"]))
    ex = r.get("example") or {}
    check(ex.get("value_now_egp") is not None,
          "%s سنة: مثال الـ١٠٠ ألف موجود" % r["years"])
    if rl.get("real_pct") is not None:
        check(ex.get("value_now_real_egp") is not None,
              "%s سنة: القيمة الحقيقية موجودة" % r["years"])
        check(ex["value_now_real_egp"] <= ex["value_now_egp"] + 0.01,
              "%s سنة: القيمة الحقيقية ≤ الاسمية" % r["years"])

# ═════════════ ⑥ إحصاء البقع (مرصود) ═════════════
section("⑥ إحصاء البقع")
rng = scs.get("range") or {}
hist_st = rng.get("historical") or {}
check(hist_st.get("sessions_checked", 0) > 100,
      "عدد الجلسات المفحوصة: %s" % hist_st.get("sessions_checked"))
ip = hist_st.get("inside_pct")
check(ip is not None and 0 <= ip <= 100, "نسبة البقاء جوّه النطاق: %s%%" % ip)
check("مش احتمال" in (hist_st.get("note") or ""),
      "التوضيح بيقول إنه تكرار تاريخي مش احتمال")
band = rng.get("band") or {}
if band.get("low") is not None and band.get("high") is not None:
    check(band["low"] < band["high"], "النطاق: أدنى < أعلى")
    check(abs(band["width_pct"] - (band["high"] / band["low"] - 1) * 100) < 0.2,
          "عرض النطاق متسق")

# ═════════════ ⑦ as_of (مفيش look-ahead) ═════════════
section("⑦ as_of")
try:
    import gold_history as gh
    s = gh.build()["series"]
    cut = s[len(s) // 2]["d"]
    d2 = gs.build(as_of=cut)
    check(d2.get("ok"), "البناء بـas_of اشتغل")
    att = ((d2.get("attribution") or {}).get("decompose") or {})
    check(att.get("to", "") <= cut, "الفترة بتتقفل عند as_of (%s ≤ %s)"
          % (att.get("to"), cut))
    # ⛔⛔ as_of لازم يقصّ **كل** المخرجات (مش التفكيك بس) — نور-الكوانت
    cur = d2.get("current") or {}
    check(cur.get("date", "") <= cut, "السعر الحالي قبل as_of (%s)" % cur.get("date"))
    for sc in (d2.get("scenarios") or []):
        for t in (sc.get("targets") or []):
            if t.get("level") is None:
                continue
        ev = json.dumps(sc, ensure_ascii=False)
        import re as _re
        _dates = _re.findall(r"20\d\d-\d\d-\d\d", ev)
        _bad = [x for x in _dates if x > cut]
        check(not _bad, "سيناريو %s: مفيش تاريخ بعد as_of (%s)"
              % (sc.get("key"), _bad[:2]))
    for r2 in ((d2.get("savings") or {}).get("rows") or []):
        check(r2.get("to", "") <= cut, "صف الادخار %s سنة قبل as_of" % r2.get("years"))
        rl2 = r2.get("real") or {}
        if rl2.get("window_to"):
            check(rl2["window_to"] <= cut, "نافذة الحقيقي قبل as_of")
except Exception as e:
    check(False, "as_of: %s" % str(e)[:80])

# ═════════════ ⑧ الخلاصة ═════════════
section("⑧ الخلاصة التحليلية")
sm = d.get("summary") or []
check(len(sm) >= 4, "أسطر الخلاصة: %d" % len(sm))
joined = " ".join(sm)
check(any(ch.isdigit() for ch in joined), "الخلاصة فيها أرقام")
for kw in ("الدولار", "الادخار"):
    check(kw in joined, "الخلاصة بتغطي «%s»" % kw)

# ═════════════ ⑧٫ب الإسناد: مفيش إنجليزي + المساهمتين الاتنين ═════════════
section("⑧٫ب نص الإسناد")
try:
    import gold_premium as _gp
    for _d in (30, 365, 1095):
        _dec = _gp.decompose(
            __import__("gold_history").build()["series"], days=_d)
        _at = _gp.attribute(_dec)
        if not _at:
            continue
        _txt = _at.get("text") or ""
        check("contributing" not in _txt.lower(),
              "%s يوم: مفيش كلمة إنجليزية في نص الإسناد" % _d)
        check(("الذهب" in _txt) and ("الدولار" in _txt),
              "%s يوم: المساهمتين الاتنين موجودين" % _d)
except Exception as e:
    check(False, "فحص نص الإسناد: %s" % str(e)[:70])

# ═════════════ ⑨ محرك العملة (آلي مش توقّع) ═════════════
section("⑨ محرك العملة")
cur_sc = scs.get("currency") or {}
check(bool(cur_sc), "سيناريو العملة موجود")
steps = [p for p in (cur_sc.get("steps") or []) if isinstance(p, dict)]
check(len(steps) >= 4, "خطوات العملة: %d" % len(steps))
for p in steps:
    _mv = p.get("fx_move_pct", 0)
    _dl = p.get("gram_delta_egp", 0)
    if _mv > 0:
        check(_dl > 0, "الدولار +%s%% ⇒ الجرام بيزيد (+%.0f ج.م)" % (_mv, _dl))
    if _mv < 0:
        check(_dl < 0, "الدولار %s%% ⇒ الجرام بينزل (%.0f ج.م)" % (_mv, _dl))
check("مش توقّع" in (cur_sc.get("note") or ""), "مكتوب إنه حسابي مش توقّع")

print("\n" + "=" * 62)
if fails:
    print("❌ فشل %d اختبار" % len(fails))
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("✅ كل اختبارات السيناريوهات عدّت")
