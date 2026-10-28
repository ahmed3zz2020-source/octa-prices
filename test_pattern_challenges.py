# -*- coding: utf-8 -*-
"""🧪 اختبار محرك «تحدي اليوم» — ٢٨ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① **مفيش look-ahead**: مستويات التحدي لازم تتفصل عن أي شمعة بعد يوم
    التوليد (نغيّر الشموع بعد D ⇒ المستويات ما تتغيرش).
 ② **مفيش اختراع**: شموع ناقصة ⇒ pending + سبب (مش نتيجة متخيّلة).
 ③ **قواعد النتيجة**: الهدف قبل الوقف ⇒ صعود · الوقف قبل الهدف ⇒ هبوط ·
    المستويين في نفس الشمعة ⇒ متعادل · مفيش لمس ⇒ متعادل.
 ④ **النقاط**: الصحيحة +1 · الغلط 0 · المتعادل 0.
 ⑤ **الخصوصية**: مفيش إيميل ولا uid في لوحة المتصدرين.
 ⑥ **الحتمية**: نفس المدخلات ⇒ نفس المخرجات.

▶️ التشغيل: python3 test_pattern_challenges.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pattern_challenges as pc  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


# ═══════════════ شموع وهمية ═══════════════
def mk_bars(n=200, start="2026-01-01"):
    """سلسلة فيها **منResistance فوق + دعم تحت** (سوق عرضي).

    📌 الهدف: نتحقق إن التحدي = أقرب مستوى فوق + أقرب مستوى تحت،
       وأن الحل بيتحسب على مستويات اتحسبت يوم D بس.
    """
    from datetime import date, timedelta
    y, m, d = [int(x) for x in start.split("-")]
    out = []
    day = date(y, m, d)
    n_rise = 60
    n_band = 100
    for i in range(n):
        if i < n_rise:
            p = 92.0 + (100.0 - 92.0) * (i / float(n_rise))
        elif i < n_rise + n_band:
            k = (i - n_rise)
            p = 100.0 + 1.5 * ((k // 7) % 2)
        else:
            k = (i - (n_rise + n_band))
            p = 97.5 + 1.0 * (k % 2)
        out.append({"d": day.isoformat(), "o": p, "h": p * 1.006, "l": p * 0.994,
                    "c": p, "v": 1_000_000})
        day += timedelta(days=1)
    return out


def bars_with_tail(base, tail):
    """نسخة من الشموع + ذيل بعدها (للاختبار)."""
    return list(base) + list(tail)


UNIVERSE = {"TEST": {"name": "سهم اختبار", "sector": "اختبار"}}


print("▶️ ① ⛔ مفيش look-ahead: المستويات ما بتلمسش شموع بعد يوم التوليد")
base = mk_bars(n=200)
d_day = base[-1]["d"]
uni = UNIVERSE
ch1, err1 = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                                  bars_by_code={"TEST": base})
check(ch1 is not None, "التحدي اتولّد (%s)" % (err1 or ""))
if ch1:
    # ⛔ نغيّر كل الشموع **بعد** يوم التوليد (بقيت أشد صعوداً)
    tail = []
    from datetime import date, timedelta
    dd = date(*[int(x) for x in d_day.split("-")]) + timedelta(days=1)
    for i in range(30):
        p = 500.0 + i * 10
        tail.append({"d": dd.isoformat(), "o": p, "h": p * 1.01, "l": p * 0.99,
                     "c": p, "v": 9_000_000})
        dd += timedelta(days=1)
    ch2, err2 = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                                      bars_by_code={"TEST": bars_with_tail(base, tail)})
    check(ch2 is not None, "التحدي اتولّد تاني (%s)" % (err2 or ""))
    if ch2:
        same = (ch1["entry"] == ch2["entry"] and ch1["stop"] == ch2["stop"]
                and ch1["target"] == ch2["target"] and ch1["level"] == ch2["level"])
        check(same, "المستويات ما اتغيرتش لما الشموع بعد D اتغيرت "
                    "(%s/%s/%s ⇒ %s/%s/%s)" % (ch1["entry"], ch1["stop"], ch1["target"],
                                               ch2["entry"], ch2["stop"], ch2["target"]))
        check(ch1["entry"] == round(base[-1]["c"], 4),
              "الدخول = إغلاق شمعة D الحقيقي (%s)" % ch1["entry"])
        if ch1["direction"] == "up":
            check(ch1["stop"] < ch1["entry"] < ch1["target"],
                  "اتجاه صعود: وقف < دخول < هدف")
        else:
            check(ch1["target"] < ch1["entry"] < ch1["stop"],
                  "اتجاه هبوط: هدف < دخول < وقف")
        check(ch1["stop"] != ch1["target"], "الهدف والوقف مختلفين")
        check(abs(ch1["rr"] - (abs(ch1["target"] - ch1["entry"])
                               / abs(ch1["entry"] - ch1["stop"]))) < 0.02,
              "ع/م محسوب صح: %s" % ch1["rr"])

print("\n▶️ ② الحتمية")
a1, _ = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                              bars_by_code={"TEST": base})
a2, _ = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                              bars_by_code={"TEST": base})
check(a1 == a2, "نفس المدخلات ⇒ نفس المخرجات بالظبط")

print("\n▶️ ③ ⛔ مفيش اختراع: شموع ناقصة ⇒ مفيش تحدي + سبب")
short, e_short = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                                       bars_by_code={"TEST": base[:20]})
check(short is None, "سلسلة قصيرة ⇒ مفيش تحدي")
check(bool(e_short), "فيه سبب مكتوب: %s" % e_short)
empty, e_empty = pc.generate_for_date(d_day, codes=["TEST"], universe=uni,
                                       bars_by_code={})
check(empty is None and bool(e_empty), "مفيش شموع ⇒ مفيش تحدي + سبب")

print("\n▶️ ④ ⛔ الحل لازم ينتظر ١٠ جلسات (مفيش نتيجة提前)")
if ch1:
    ch_short = dict(ch1)
    ch_short["resolved"] = None
    res, err = pc.resolve_challenge(ch_short, base)
    check(res is None, "٩ شموع أقل من الأفق ⇒ مفيش نتيجة")
    check(bool(err), "فيه سبب: %s" % err)

print("\n▶️ ⑤ قواعد النتيجة")
if ch1:
    entry = ch1["entry"]
    stop = ch1["stop"]
    target = ch1["target"]
    up = (ch1["direction"] == "up")
    d0 = base[-1]["d"]

    def mk_tail(rows):
        from datetime import date, timedelta
        dd = date(*[int(x) for x in d0.split("-")]) + timedelta(days=1)
        out = []
        for r in rows:
            out.append({"d": dd.isoformat(), "o": r[0], "h": r[1], "l": r[2],
                        "c": r[3], "v": 1_000_000})
            dd += timedelta(days=1)
        return out

    # ⭐ نبني الصفوف من الهندسة نفسها (الهدف والوقف على طرفين)
    lo = min(target, stop)
    hi = max(target, stop)
    mid = (lo + hi) / 2.0
    span = (hi - lo) / 2.0
    target_is_hi = (target == hi)

    def hit_target_row():
        """لمس الهدف بس (من غير ما يلمس الوقف)."""
        if target_is_hi:
            return (hi + 0.1 * span, hi + 0.1 * span, mid + 0.2 * span, hi)
        return (lo - 0.1 * span, mid - 0.2 * span, lo - 0.1 * span, lo)

    def hit_stop_row():
        """لمس الوقف بس (من غير ما يلمس الهدف)."""
        if target_is_hi:
            return (lo - 0.1 * span, mid - 0.2 * span, lo - 0.1 * span, lo)
        return (hi + 0.1 * span, hi + 0.1 * span, mid + 0.2 * span, hi)

    def both_row():
        """المستويين في نفس الشمعة."""
        return (hi + 0.1 * span, hi + 0.1 * span, lo - 0.1 * span, mid)

    def none_row():
        """بين المستويين من غير لمس."""
        return (mid, mid + 0.2 * span, mid - 0.2 * span, mid)

    c = dict(ch1); c["resolved"] = None
    res, err = pc.resolve_challenge(c, base + mk_tail([hit_target_row()] + [none_row()] * 9))
    check(res and res["outcome"] == ch1["direction"],
          "الهدف قبل الوقف ⇒ %s (المتوقع %s)" % ((res or {}).get("outcome"), ch1["direction"]))

    c = dict(ch1); c["resolved"] = None
    res, err = pc.resolve_challenge(c, base + mk_tail([hit_stop_row()] + [none_row()] * 9))
    check(res and res["outcome"] == pc._opp(ch1["direction"]),
          "الوقف قبل الهدف ⇒ %s (المتوقع %s)" % ((res or {}).get("outcome"), pc._opp(ch1["direction"])))

    c = dict(ch1); c["resolved"] = None
    res, err = pc.resolve_challenge(c, base + mk_tail([both_row()] + [none_row()] * 9))
    check(res and res["outcome"] == "neutral",
          "المستويين في نفس الشمعة ⇒ متعادل (%s)" % (res or {}).get("outcome"))

    c = dict(ch1); c["resolved"] = None
    res, err = pc.resolve_challenge(c, base + mk_tail([none_row()] * 10))
    check(res and res["outcome"] == "neutral",
          "مفيش لمس ⇒ متعادل (%s)" % (res or {}).get("outcome"))

print("\n▶️ ⑥ النقاط: صحيحة +1 · غلط 0 · متعادل 0")
store = {
    "CH-1": {"date": "2026-01-01", "code": "A", "resolved": {"outcome": "up"}},
    "CH-2": {"date": "2026-01-02", "code": "B", "resolved": {"outcome": "down"}},
    "CH-3": {"date": "2026-01-03", "code": "C", "resolved": {"outcome": "neutral"}},
}
votes = {"votes": {
    "CH-1": {"u1": {"vote": "up", "at": 1}},
    "CH-2": {"u1": {"vote": "up", "at": 2}},
    "CH-3": {"u1": {"vote": "up", "at": 3}},
    "CH-1": {"u1": {"vote": "up", "at": 1}, "u2": {"vote": "down", "at": 1}},
}}
st = pc.user_stats("u1", store, votes["votes"])
check(st["points"] == 1, "نقطة واحدة (صحيحة واحدة) ⇒ %s" % st["points"])
check(st["correct"] == 1 and st["wrong"] == 1 and st["neutral"] == 1,
      "العدّ: صح %s · غلط %s · متعادل %s" % (st["correct"], st["wrong"], st["neutral"]))
check(abs(st["accuracy"] - 0.5) < 1e-6, "الدقة = ٠٫٥ (1 من 2 قرروا): %s" % st["accuracy"])
st2 = pc.user_stats("u2", store, votes["votes"])
check(st2["points"] == 0, "الغلط = 0 نقاط: %s" % st2["points"])
st3 = pc.user_stats("u3", store, votes["votes"])
check(st3["points"] == 0 and st3["accuracy"] is None,
      "مستخدم ما صوّتش ⇒ 0 نقاط ودقة None (مش صفر): %s" % st3["accuracy"])

print("\n▶️ ⑦ ⛔ الخصوصية: مفيش إيميل ولا uid في المتصدرين")


def _getter(uid):
    return {"name": "أحمد محمد", "email": "ahmed3zz2020@gmail.com", "uid": uid}


votes2 = {"votes": {
    "CH-1": {"u1": {"vote": "up", "at": 1}, "u2": {"vote": "up", "at": 1},
             "u3": {"vote": "up", "at": 1}},
}}
lb = pc.leaderboard(store, votes2["votes"], user_getter=_getter)
check(lb["status"] == "ok", "اللوحة مفتوحة (٣ مصوّتين): %s" % lb["status"])
blob = repr(lb["rows"])
check("ahmed3zz2020" not in blob, "مفيش إيميل في اللوحة")
check("u1" not in blob and "u2" not in blob and "u3" not in blob, "مفيش uid في اللوحة")
if lb["rows"]:
    check(len(lb["rows"][0]["alias"]) <= 3,
          "الاسم مقنّع (أول حرفين): %r" % lb["rows"][0]["alias"])

print("\n▶️ ⑧ ⛔ لوحة فاضية = hidden")
lb_small = pc.leaderboard(store, {"CH-1": {"u1": {"vote": "up", "at": 1}}},
                          user_getter=_getter)
check(lb_small["status"] == "hidden", "مصوّت واحد ⇒ hidden")
check(bool(lb_small.get("reason")), "فيه سبب: %s" % lb_small.get("reason"))

print("\n▶️ ⑨ ⛔ الاسم المستعار: مفيش بيانات ⇒ «مستخدم»")
check(pc._alias({}) == "مستخدم", "بلا اسم ولا إيميل ⇒ مستخدم")
check(pc._alias({"name": "أحمد"}) == "أح…", "من الاسم (أول حرفين): %r" % pc._alias({"name": "أحمد"}))
check(pc._alias({"email": "ahmed3zz2020@gmail.com"}) == "ah…",
      "من الإيميل (أول حرفين): %r" % pc._alias({"email": "ahmed3zz2020@gmail.com"}))

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f in fails:
    print("   -", f)
sys.exit(1 if fails else 0)
