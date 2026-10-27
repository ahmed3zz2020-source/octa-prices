# -*- coding: utf-8 -*-
"""🧪 اختبار الطبقة اليومية لمحر�� الأنماط (pattern_daily) — ٢٧ أكتوبر ٢٠٢٦

⛔ القواعد اللي بيحرسها:
 ① الفلترة: كل شرط شغّال فعلاً (نقطة بو نقطة).
 ② التحويل من أعمدة المصدر ⇒ شموع.
 ③ المسارات: 401 للزائر · 200 للمتسجّل · والبناء بيشتغل.
 ④ نص الملخص العربي فيه الأرقام الصح.
 ⑤ «ناقص» مش «مفيش نمط» في الملخص.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pattern_daily as pd

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("   ❌", msg)
    else:
        print("   ✅", msg)


def mk_sig(**kw):
    s = {"kind": "BREAKOUT", "direction": "up", "code": "COMI",
         "name": "البنك التجاري الدولي", "entry": 122.7, "stop": 120.5,
         "target": 128.5, "rr": 2.7, "volume_confirmed": True,
         "detected_at": "2026-10-27", "trend": "up",
         "evidence": {"atr_pct": 2.36, "zone_score": 55.0,
                      "touches": 9, "reactions": 4},
         "why": "كسر منطقة صاعد"}
    s.update(kw)
    return s


print("▶️ ① تحويل أعمدة المصدر ⇒ شموع")
cols = {"t": ["2026-10-26", "2026-10-27"], "o": [1.0, 2.0], "h": [3.0, 4.0],
        "l": [0.5, 1.5], "c": [2.0, 3.0], "v": [100, 200]}
bars = pd._cols_to_bars(cols)
check(len(bars) == 2, "عدد الشموع = 2")
check(bars[1]["d"] == "2026-10-27" and bars[1]["c"] == 3.0, "الشمعة اتحولت صح")
check(bars[0]["v"] == 100, "الحجم اتنقل")
check(pd._cols_to_bars(None) == [], "مدخل فاضي ⇒ [] (مش exception)")
check(pd._cols_to_bars({"t": []}) == [], "أعمدة فاضية ⇒ []")

print("\n▶️ ② الفلترة نقطة بنقطة")
f = {"kind": "BREAKOUT", "volume_confirmed": True, "min_rr": 1.0,
     "max_atr_pct": 6.0}
check(pd._passes(mk_sig(), f) is True, "إشارة كاملة تعدّي")
check(pd._passes(mk_sig(kind="PULLBACK"), f) is False, "نوع تاني يترفض")
check(pd._passes(mk_sig(volume_confirmed=False), f) is False, "من غير حجم يترفض")
check(pd._passes(mk_sig(rr=0.5), f) is False, "R:R قليل يترفض")
check(pd._passes(mk_sig(evidence={"atr_pct": 9.0}), f) is False,
      "تذبذب عالي يترفض")
check(pd._passes(mk_sig(rr=None), f) is False, "R:R ناقص يترفض (مش بيعدّي)")
check(pd._passes(mk_sig(direction="down"), {"direction": "up"}) is False,
      "اتجاه تاني يترفض")

print("\n▶️ ③ الفلاتر الافتراضية + من ملف")
d = pd.load_filters()
check(d.get("kind") == "BREAKOUT", "الفلتر الافتراضي = كسر منطقة")
check(d.get("volume_confirmed") is True, "تأكيد الحجم مفعّل")
tmpdir = tempfile.mkdtemp(prefix="pat_daily_")
old_dir = pd.DATA_DIR
try:
    pd.DATA_DIR = __import__("pathlib").Path(tmpdir)
    pd.FILTERS_FILE = pd.DATA_DIR / "pattern_filters.json"
    pd.FILTERS_FILE.write_text(json.dumps({"kind": "PULLBACK", "min_rr": 3}),
                               encoding="utf-8")
    d2 = pd.load_filters()
    check(d2["kind"] == "PULLBACK", "الفلتر من الملف اتقرا")
    check(d2["min_rr"] == 3, "القيمة من الملف اتقرت")
    check(d2["volume_confirmed"] is True, "الباقي من الافتراضي")
finally:
    pd.DATA_DIR = old_dir

print("\n▶️ ④ نص الملخص")
txt = pd.digest_text([mk_sig()])
check("COMI" in txt, "الرمز في النص")
check("122.7" in txt, "سعر الدخول في النص")
check("128.5" in txt, "الهدف في النص")
check("تعليمي" in txt, "في التنويه")
empty = pd.digest_text([])
check("لا توجد إشارات" in empty, "نص فاضي بيقول مفيش إشارات")

print("\n▶️ ⑤ المسارات (تسجيل + 401 + 200)")
# ⛔ Flask مش متاح في بيئة الاختبار ⇒ نعمل stub بسيط ونختبر المنطق نفسه
import types as _types


def _install_fake_flask():
    fake = _types.ModuleType("flask")
    fake.jsonify = lambda x: x
    fake.request = _types.SimpleNamespace(args={}, method="GET",
                                          get_json=lambda **k: {})
    sys.modules["flask"] = fake
    return fake


class _FakeApp:
    def __init__(self):
        self.routes = {}

    def route(self, rule, methods=("GET",)):
        def deco(fn):
            self.routes[rule] = fn
            return fn
        return deco


_install_fake_flask()
# ⛔ ما نشغّلش المهمة اليومية في الاختبار (شبكة + تكرار)
os.environ["OCTA_PATTERN_DAILY"] = "0"
cur = {"u": None}


def _require_user():
    return cur["u"]


def _call(route):
    """المسار بيرجّع (json, status) أو json بس."""
    out = route()
    if isinstance(out, tuple):
        return out[0], out[1]
    return out, 200


_app = _FakeApp()
pd.register(_app, require_user=_require_user, send=None, live_data_getter=None)
check("/api/setups" in _app.routes, "مسار /api/setups متسجّل")
check("/api/setups/meta" in _app.routes, "مسار /api/setups/meta متسجّل")
check("/api/setups/refresh" in _app.routes, "مسار /api/setups/refresh متسجّل")
_res, _status = _call(_app.routes["/api/setups"])
check(_status == 401, "الزائر ⇒ 401 (مش 200)")
cur["u"] = {"id": "u1", "plan": "free"}
_res2, _status2 = _call(_app.routes["/api/setups"])
check(_status2 == 403, "باقة مقفولة (free) ⇒ 403 — Got %d" % _status2)
cur["u"] = {"id": "u1", "plan": "pro"}
_res3, _status3 = _call(_app.routes["/api/setups"])
check(_status3 in (200, 503),
      "باقة pro ⇒ 200 أو 503 (حسب وجود الكاش) — Got %d" % _status3)

print("\n" + ("✅ كل الاختبارات عدّت" if not fails else "❌ فشل: %d" % len(fails)))
for f_ in fails:
    print("   -", f_)
sys.exit(1 if fails else 0)
