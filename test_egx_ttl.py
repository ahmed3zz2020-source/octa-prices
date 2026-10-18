# -*- coding: utf-8 -*-
"""
⛔ باج يوم الأحد في كاش الأسعار + توقيت القاهرة الصيفي
=========================================================
① egx_ttl() كان بيقول:
       if d >= 4:  return 600       # «الجمعة والسبت»
   في بايثون weekday() = 0 الإثنين ... 6 الأحد
   يعني d >= 4 بيصطاد الأحد (6) كمان — وهو يوم تداول كامل في مصر.
   النتيجة: كل يوم أحد الكاش 600 ثانية بدل 5، والأسعار متأخرة 10 دقايق.
   (السطر 7494 في نفس الملف بيستخدم الشكل الصح in (4, 5) — عشان كده
    التقويم التجاري اتظبط صح والكاش لأ.)

② egx_now() كان固定的 UTC+2 — ومصر بترجع للتوقيت الصيفي (UTC+3)
   من أواخر أبريل لحد أواخر أكتوبر.
"""
import ast
import datetime as _dt
import sys

SRC = "update_prices.py"
FAIL = 0


def check(label, got, want):
    global FAIL
    ok = got == want
    if not ok:
        FAIL += 1
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: جاب {got} / المتوقّع {want}")


# ── ساعة وهمية: نحقنها جوّه الدوال عشان نختبر أي يوم/وقت ──────
class FakeClock(_dt.datetime):
    forced = _dt.datetime(2026, 10, 19, 8, 0)   # 08:00 UTC = 11:00 القاهرة

    @classmethod
    def utcnow(cls):
        return cls.forced

    @classmethod
    def now(cls, tz=None):
        return cls.forced.astimezone(tz) if tz else cls.forced


def load():
    """يسحب الدوال جوّه namespace مشترك وحقنه بساعة وهمية"""
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    want = {"egx_now", "egx_ttl", "cairo_now"}
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    assert len(fns) == 3, f"لقينا {[f.name for f in fns]} — ناقص"
    ns = {"datetime": FakeClock, "_dt": FakeClock,
          "timedelta": _dt.timedelta, "_td": _dt.timedelta}
    exec(compile(ast.fix_missing_locations(ast.Module(body=fns, type_ignores=[])),
                 SRC, "exec"), ns)
    return ns


NS = load()

# ══ ① يوم الأسبوع في كاش الأسعار ═══════════════════════════════
print("=== ① كاش الأسعار حسب يوم الأسبوع (الساعة 11:00 القاهرة) ===")
for day, ar, want_ttl in [(0, "الإثنين", 5), (1, "الثلاثاء", 5),
                          (2, "الأربعاء", 5), (3, "الخميس", 5),
                          (4, "الجمعة", 600), (5, "السبت", 600),
                          (6, "الأحد", 5)]:
    FakeClock.forced = _dt.datetime(2026, 10, 19 + day, 8, 0)  # → 11:00 Cairo
    check(ar, NS["egx_ttl"](), want_ttl)

# ══ ② توقيت القاهرة ═════════════════════════════════════════════
print("\n=== ② توقيت القاهرة (صيفي UTC+3 / شتي UTC+2) ===")
for when, utc_dt, ar, want_h in [
        ("٧ أكتوبر (صيفي)", _dt.datetime(2026, 10, 7, 8, 20), "11:20", "11:20"),
        ("١٨ أكتوبر (صيفي)", _dt.datetime(2026, 10, 18, 8, 20), "11:20", "11:20"),
        ("٥ يناير (شتي)", _dt.datetime(2026, 1, 5, 9, 20), "11:20", "11:20"),
        ("٣٠ يوليو (صيفي)", _dt.datetime(2026, 7, 30, 9, 20), "12:20", "12:20"),
        ("١٥ يناير (شتي)", _dt.datetime(2026, 1, 15, 9, 20), "11:20", "11:20"),
]:
    FakeClock.forced = utc_dt
    check(when, NS["egx_now"]().strftime("%H:%M"), want_h)

# ══ ③ أول ساعة تداول ترجع 5 ثواني مش 120 ══════════════════════
print("\n=== ③ الكاش ساعة الافتتاح (10:00 و 10:30 القاهرة) ===")
for utc_dt, label in [(_dt.datetime(2026, 10, 18, 7, 0), "10:00"),
                      (_dt.datetime(2026, 10, 18, 7, 30), "10:30")]:
    FakeClock.forced = utc_dt
    check(f"{label} (يوم الأحد)", NS["egx_ttl"](), 5)

# ══ ④ مزاد الإغلاق ═════════════════════════════════════════════
print("\n=== ④ الكاش وقت مزاد الإغلاق (14:20 القاهرة) ===")
FakeClock.forced = _dt.datetime(2026, 10, 18, 11, 20)   # → 14:20 Cairo
check("14:20", NS["egx_ttl"](), 4)

print()
if FAIL:
    print(f"❌ {FAIL} اختبار فشل")
    sys.exit(1)
print("✅ كل الاختبارات عدّت")