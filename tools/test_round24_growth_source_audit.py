#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 الجولة ٢٤ (R24 · المرحلة ٥) — مصدر نمو الأرباح: هل مPEG مفعَّل فعلاً؟

🎯 الغرض: **إثبات بالمصدر** إن حقل نمو الأرباح (`ni_growth`) — اللي PEG
   بيحسب منه — **مش موجود في أي مصدر فعلي وقت التشغيل**، وإن المحرك
   بيعرض «غير متاح» (`None`) بدل ما يخترع نمواً أو proxy، وإن الأوزان
   المعتمدة ما اتغيّرتش.

📌 مصادر وقت التشغيل اللي بتتفحص (كلها):
   ① كل ملفات البيانات في المستودع (`data/*.json` · `data_full.json` · ...)
   ② أعمدة الـscanner في `update_prices.TV_COLUMNS` + `TV_TECH_COLUMNS`
   ③ كل سطور المحركات (قراءة بس — مافيش أي سطر **يكتب** `ni_growth`)
   ④ مصدر الأساسيات الحيّ (`startamarkets`) — ظاهر في الرد كـ`s_pg`
      بس **مش** موصول بالحقل `ni_growth` اللي PEG بيقراه

⛔ مافيش أي تعديل على:
   · الأوزان المعتمدة (`octa_score.AXIS_WEIGHTS`)
   · حد التغطية 90٪ (`opp_engine.FRESH_MIN_COVERAGE` · `update_prices`)
   · منهجية التقييم (تركيبة المحور الأساسي 30+30+20+20)

📌 التشغيل:
   python3 tools/test_round24_growth_source_audit.py
   python3 -m unittest tools.test_round24_growth_source_audit -v
"""
from __future__ import annotations

import ast
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r24_growth_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

# ⛔ كل التخزين يروح على /tmp — مافيش أي كتابة في المشروع
os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-token-secret"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-pin-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_ADMIN_TOKEN"] = "TEST-ONLY-admin-token"

BASELINE = "edc49cd"
ENGINE_FILES = ("update_prices.py", "octa_score.py", "opp_engine.py",
                "index_engine.py")


# ══════════════════════════════════════════════════════════════════════
#  فيكسات — شكل السهم وقت التشغيل (الحقول كما يطلعها الـscanner)
# ══════════════════════════════════════════════════════════════════════
RUNTIME_ITEM = {
    "code": "TEST", "name": "سهم اختبار", "sector": "أخرى",
    "price": 100.0, "change": 1.0, "volume": 250000,
    "perf_w": 2.0, "perf_1m": 4.0, "perf_3m": 8.0, "perf_6m": 10.0, "perf_y": 12.0,
    "volatility": 25.0, "rel_volume": 1.2, "tv_rating": 0.1,
    "beta": 0.9, "div_yield": 2.0, "mkt_cap": 5e9,
    "pe": 12.0, "pb": 1.6, "roe": 18.0, "de_ratio": 35.0,
    "net_margin": 12.0, "op_margin": 15.0, "eps": 4.2, "revenue": 4.5e9,
    "ema20": 98.0, "ema50": 96.0, "ema200": 90.0, "rsi": 52.0,
    "macd": 1.0, "macd_signal": 0.8, "adx": 22.0, "atr": 2.4,
    "bb_upper": 104.0, "bb_lower": 95.0, "stoch_k": 55.0, "stoch_d": 50.0,
    "vol_5": 240000, "vol_60": 230000, "data_confidence": 80,
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _baseline_source(name):
    try:
        return subprocess.run(
            ["git", "-C", REPO, "show", "%s:%s" % (BASELINE, name)],
            capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return ""


def _extract_function(src, fname):
    """مصدر دالة واحدة من نص بايثون (بدون تنفيذ الملف كله)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == fname:
            return ast.get_source_segment(src, node)
    return None


def _deep_keys(obj, prefix=""):
    """كل مفاتيح أي كائن JSON (بعمق) — بأسمائها."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k))
            keys |= _deep_keys(v, prefix + str(k) + ".")
    elif isinstance(obj, list):
        for v in obj[:200]:
            keys |= _deep_keys(v, prefix)
    return keys


def _const_key(node):
    """مفتاح ثابت في `x["اسم"]` (لو كان ثابتاً)."""
    try:
        return node.slice.value
    except AttributeError:
        try:
            return node.slice.value
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001
        return None


def _writes_of_ni_growth(path):
    """كل مواضع الكتابة على `ni_growth` (AST — مش بحث نصي)."""
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Subscript)
                        and _const_key(t) == "ni_growth"):
                    out.append((node.lineno, "تعيين بالمفتاح"))
                elif isinstance(t, ast.Name) and t.id == "ni_growth":
                    out.append((node.lineno, "تعيين متغيّر"))
        elif isinstance(node, ast.AugAssign):
            t = node.target
            if ((isinstance(t, ast.Subscript) and _const_key(t) == "ni_growth")
                    or (isinstance(t, ast.Name) and t.id == "ni_growth")):
                out.append((node.lineno, "زيادة على ni_growth"))
        elif isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", "") or getattr(fn, "id", "")
            if name in ("update", "setdefault"):
                for kw in node.args:
                    if isinstance(kw, ast.Dict):
                        for k in kw.keys:
                            if isinstance(k, ast.Constant) and k.value == "ni_growth":
                                out.append((node.lineno, "كتابة في قاموس (%s)" % name))
    return out


class GrowthSourceAudit(unittest.TestCase):
    """إثبات المصدر: مPEG مفعَّل؟ ولا «غير متاح»؟"""

    # ── ① ملفات البيانات ──────────────────────────────────────────────
    def test_no_data_file_contains_ni_growth(self):
        """⛔ مافيش ملف بيانات في المستودع فيه حقل `ni_growth`."""
        files = sorted(glob.glob(os.path.join(REPO, "data", "*.json")) +
                       glob.glob(os.path.join(REPO, "*.json")))
        self.assertTrue(files, "مافيش ملفات بيانات عشان نفحصها")
        offenders = []
        for path in files:
            try:
                data = json.loads(_read(path))
            except Exception:  # noqa: BLE001
                continue
            for key in _deep_keys(data):
                if key.lower() == "ni_growth":
                    offenders.append("%s → %s" % (os.path.relpath(path, REPO), key))
        self.assertEqual(offenders, [],
                         "حقل ni_growth موجود في ملفات البيانات: %s" % offenders)

    def test_snapshot_items_have_no_ni_growth(self):
        """⛔ ولا سطر في لقطة البيانات المنشورة فيه الحقل."""
        path = os.path.join(REPO, "data_full.json")
        if not os.path.isfile(path):
            self.skipTest("لقطة البيانات غير موجودة")
        data = json.loads(_read(path))
        stocks = data.get("stocks") or {}
        bad = [c for c, s in stocks.items()
               if isinstance(s, dict) and "ni_growth" in s]
        self.assertEqual(bad, [], "أسهم فيها ni_growth: %s" % bad[:5])

    # ── ② أعمدة الـscanner ────────────────────────────────────────────
    def test_scanner_columns_carry_no_earnings_growth(self):
        """⛔ مافيش عمود في الـscanner بيغذّي `ni_growth`."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        fields = [f for _, f in (up.TV_COLUMNS + up.TV_TECH_COLUMNS)]
        self.assertNotIn("ni_growth", fields,
                         "عمود الـscanner بيغذّي ni_growth")
        cols = [c for c, _ in (up.TV_COLUMNS + up.TV_TECH_COLUMNS)]
        growth_cols = [c for c in cols if "growth" in c.lower()]
        self.assertEqual(growth_cols, [],
                         "أعمدة الـscanner فيها نمو: %s" % growth_cols)

    # ── ③ المحركات: قراءة بس (مافيش كتابة) ────────────────────────────
    def test_no_engine_writes_ni_growth(self):
        """⛔ مافيش سطر في المحركات **يكتب** `ni_growth`."""
        offenders = []
        for name in ENGINE_FILES:
            path = os.path.join(REPO, name)
            if not os.path.isfile(path):
                continue
            for line_no, kind in _writes_of_ni_growth(path):
                offenders.append("%s:%d → %s" % (name, line_no, kind))
        self.assertEqual(offenders, [],
                         "في المحركات سطر بيكتب ni_growth: %s" % offenders)

    def test_engine_reads_of_ni_growth_are_reads_only(self):
        """📌 توثيق: كل استخدام لـ`ni_growth` في المحركات = قراءة."""
        reads = []
        for name in ENGINE_FILES:
            path = os.path.join(REPO, name)
            if not os.path.isfile(path):
                continue
            for i, line in enumerate(_read(path).splitlines(), 1):
                if "ni_growth" not in line:
                    continue
                if '.get("ni_growth")' in line or ".get('ni_growth')" in line:
                    reads.append("%s:%d" % (name, i))
        self.assertTrue(reads, "مافيش أي قراءة لـni_growth في المحركات")
        self.assertIn("update_prices.py:", " ".join(reads))

    def test_peg_call_site_reads_only_ni_growth(self):
        """⛔ مPEG بيقرأ `ni_growth` بس — مافيش proxy تاني في مساره."""
        src = _read(os.path.join(REPO, "update_prices.py"))
        self.assertIn('peg_score(P, _f(item.get("ni_growth")))', src,
                      "نقطة استدعاء PEG اتغيّرت")
        # ⛔ مافيش أي حقل تاني بيتقرا في مسار PEG
        for other in ("revenue_growth", "cagr3y", "perf_3m", "eps_growth",
                      "profit_growth"):
            self.assertNotIn('peg_score(P, _f(item.get("%s"))' % other, src,
                             "PEG بياخد proxy من %s" % other)

    # ── ④ السلوك المنشور: «غير متاح» ──────────────────────────────────
    def test_peg_is_unavailable_and_scores_zero_for_runtime_items(self):
        """⛔PEG مفعَّل بس مافيش نمو ⇒ «غير متاح» + صفر نقاط (مش «رخيص»)."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        res = up.fundamental_score(dict(RUNTIME_ITEM), {})
        self.assertIsNotNone(res)
        self.assertIsNone(res.get("peg"), "PEG لازم يكون None (غير متاح)")
        self.assertEqual(res.get("peg_points"), 0.0,
                         "PEG غير المتاح = صفر نقاط (مش أفضل شريحة)")

    def test_peg_does_not_borrow_a_proxy(self):
        """⛔ حقول تانية موجودة (نمو إيرادات · CAGR · أداء) ما بتتحوّلش لنمو."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        item = dict(RUNTIME_ITEM)
        item.update({"revenue_growth": 9.0, "cagr3y": 40.0, "perf_3m": 8.0,
                     "eps_growth": 22.0, "profit_growth": 48.0})
        res = up.fundamental_score(item, {})
        self.assertIsNone(res.get("peg"),
                          "PEG استخدم proxy — لازم يفضل غير متاح")
        self.assertEqual(res.get("peg_points"), 0.0)

    def test_published_scores_match_the_pre_peg_baseline(self):
        """⛔ الدرجات المنشورة ما اتغيّرتش بإضافة PEG ( stocks بلا نمو )."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        base_src = _extract_function(_baseline_source("update_prices.py"),
                                     "fundamental_score")
        self.assertTrue(base_src, "مش قادرين نجيب محرك الأساسيات من الـbaseline")
        ns = {"SECTOR_STATS": {}}
        try:
            exec(compile(base_src, "<baseline-fundamental>", "exec"), ns)  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            self.skipTest("محرك الـbaseline مش قابل للتنفيذ: %s" % exc)
        base_fn = ns.get("fundamental_score")
        self.assertTrue(base_fn, "محرك الـbaseline مش موجود")
        now = up.fundamental_score(dict(RUNTIME_ITEM), {})
        old = base_fn(dict(RUNTIME_ITEM), {})
        self.assertAlmostEqual(now["score"], old["score"], places=6,
                               msg="الدرجة الأساسية اتغيّرت بإضافة PEG")
        self.assertEqual(now["breakdown"]["القيمة"], old["breakdown"]["القيمة"],
                         "بند القيمة اتغيّر")

    def test_fundamental_composition_is_unchanged(self):
        """⛔ تركيبة المحور الأساسي 30+30+20+20 ما اتغيّرتش."""
        import _stub_env
        _stub_env.install()
        import update_prices as up
        res = up.fundamental_score(dict(RUNTIME_ITEM), {})
        self.assertEqual(sorted(res["breakdown"].keys()),
                         sorted(["الربحية", "القيمة", "الصحة المالية",
                                 "اكتمال البيانات"]))

    # ── ⑤ الأوزان والحدود (مطابقة الأساس) ─────────────────────────────
    def test_axis_weights_identical_to_the_baseline(self):
        """⛔ أوزان المحاور مطابقة للأساس edc49cd."""
        import octa_score
        base_src = _baseline_source("octa_score.py")
        self.assertTrue(base_src, "مش قادرين نجيب محرك الأساس")
        base_weights = None
        try:
            tree = ast.parse(base_src)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in tree.body:
                if (isinstance(node, ast.Assign)
                        and any(getattr(t, "id", "") == "AXIS_WEIGHTS"
                                for t in node.targets)):
                    try:
                        base_weights = ast.literal_eval(node.value)
                    except Exception:  # noqa: BLE001
                        base_weights = None
        self.assertIsNotNone(base_weights, "مش قادرين نقرا أوزان الأساس")
        self.assertEqual(base_weights, octa_score.AXIS_WEIGHTS,
                         "أوزان المحاور اتغيّرت")

    def test_coverage_threshold_is_still_ninety(self):
        """⛔ حد التغطية 90٪ ما اتغيّرش."""
        import opp_engine
        self.assertEqual(opp_engine.FRESH_MIN_COVERAGE, 90.0)

    def test_runtime_payload_maps_profit_growth_to_sp_g_not_ni_growth(self):
        """⛔ نمو الأرباح من مصدر الأساسيات ظاهر كـ`s_pg` — مش `ni_growth`."""
        src = _read(os.path.join(REPO, "update_prices.py"))
        self.assertIn('"s_pg": _num(s.get("profit_growth"))', src)
        # ⛔ مافيش نشر للحقل نفسه في الرد الحيّ (PEG بيقراه بس)
        self.assertNotIn('"ni_growth":', src,
                         "الرد الحيّ نشر ni_growth (مش متوقّع)")

    def test_starta_source_is_the_only_real_growth_provider(self):
        """📌 توثيق: المصدر الحقيقي لنمو الأرباح = `startamarkets`
        (حقل `profit_growth`) — وهو **مش** موصول بالحقل اللي PEG بيقراه."""
        src = _read(os.path.join(REPO, "update_prices.py"))
        self.assertIn("startamarkets.com/api/v1/egx/statistics/", src)
        self.assertIn('"s_rg": _num(s.get("revenue_growth"))', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
