#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 الجولة ٢٤ (R24 · المرحلة ٥) — عزل سبب انحراف الذهب الحي

🎯 الغرض: تفكيك الانحراف المقاس بين **سلسلة الذهب** (محسوبة) و**السعر
   الحيّ المرصود** (السوق المحلي) إلى أجزاء قابلة للقياس:
   · رجل الذهب (`XAUUSD`) · زوج العملة (`EGP/USD`) · هامش السوق المحلي
   وتثبيت إجابة السؤال: هل السبب تاريخ/وقت؟ ولا خطأ في الوحدة؟ ولا
   زوج عملة مختلف؟ ولا مصدر مختلف؟

⛔ الأداة دي **مش بوابة CI** (اسمها مش `test_*`) ⇒ بتتشغّل وقت ما تحب.
⛔ مافيش أي كتابة جوه المشروع — كل الملفات على `/tmp` + ملف الأدلة.
⛔ مافيش أي كتابة على الإنتاج ولا أي معاملة مالية.

📌 التشغيل:
   python3 tools/r24_gold_drift_isolation.py \
       --out /workspace/output/OCTA-ROUND24-EVIDENCE/evidence/phase5_gold_measurement.json
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

T = 31.1035                       # أونصة تروي = 31.1035 جرام
TV_XAU = "FX_IDC:XAUUSD"
TV_EGP = "FX_IDC:USDEGP"


def _now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def build_series():
    """سلسلة الذهب المحسوبة (TradingView) — آخر نقطة + تاريخها."""
    import gold_history as gh
    d = gh.build(force=True)
    if not d.get("ok") or not d.get("series"):
        return None, d.get("error") or "السلسلة مبنيةش"
    return d, None


def live_price():
    """السعر المرصود من السوق المحلي + تفاصيله."""
    import gold_local as gl
    loc = gl.get(force=True) or {}
    if not loc.get("ok"):
        return None, loc.get("error") or "المصدر الحيّ مش متاح"
    return loc, None


def tv_now(symbol, count=6):
    """آخر شمعة يومية من TradingView (نفس مصدر السلسلة)."""
    import tv_ws
    bars = tv_ws.fetch(symbol, count)
    if not bars:
        return None
    b = bars[-1]
    return {"date": time.strftime("%Y-%m-%d", time.gmtime(b["t"])),
            "close": float(b["c"])}


def decompose(series_last, loc, tv_xau, tv_fx, fx_independent=None,
              gold_independent=None):
    """تفكيك الانحراف: ذهب · دولار · هامش محلي.

    ⛔⛔⛔ (الجولة ٢٥ · R24-I14) — **الدورية اتقفلت**:
       الكود القديم كان بيحسب «سعر الدولار الضمني» من **السعر المحلي
       نفسه** ⇒ (جرام محلي × 31.1035) ÷ أونصة، وبعدين بيستخدم **نفس**
       الرقم ده لإثبات إن الهامش المحلي = صفر ⇒ النتيجة كانت **بالضرورة**
       صفر مهما كان السعر المرصود (برهان: جرام ٦٠٠٠ أو ٩٠٠٠ ⇒ الهامش
       ٠٫٠٠٠٠٪ في الحالتين).
       ✅ دلوقتي: الهامش بيتحسب بس لو فيه **صرف مستقل** (مش مشتقّ من
       الذهب) — ولو مفيش ⇒ `None` + سبب (مش صفر كاذب).
    """
    gram_series = float(series_last["gram"])
    xau_series = float(series_last["xau"])
    fx_series = float(series_last["egp_per_usd"])
    gram_live = float(loc["gram_24_reference"])
    ounce_live = loc.get("ounce_usd")

    out = {
        "series": {"date": series_last.get("d"),
                   "xau_usd_per_oz": xau_series,
                   "egp_per_usd": fx_series,
                   "gram_egp": gram_series,
                   "gram_recomputed": xau_series * fx_series / T},
        "live": {"gram_24_reference_egp": gram_live,
                 "ounce_usd": ounce_live,
                 "source": loc.get("source"),
                 "source_url": loc.get("source_url"),
                 "updated_iso": loc.get("updated_iso"),
                 "fetched_at": loc.get("fetched_at")},
        "tv_snapshot": {"xau": tv_xau, "egp_per_usd": tv_fx},
    }
    # ① الاتساق الداخلي للسلسلة (وحدة الجرام)
    out["internal_consistency_pct"] = round(
        (gram_series / (xau_series * fx_series / T) - 1) * 100, 6)
    # ② الانحراف المقاس (السلسلة ⇦ الحيّ)
    out["drift_pct"] = round((gram_series / gram_live - 1) * 100, 4)
    # ③ رجل الذهب: **قراءة مستقلة** لو متاحة · وإلاSnapshot التليفزيون
    gold_used = None
    gold_src = None
    if gold_independent:
        gold_used = float(gold_independent)
        gold_src = "independent_world_gold"
    elif tv_xau and tv_xau.get("close"):
        gold_used = float(tv_xau["close"])
        gold_src = "tradingview_snapshot (نفس مزوّد السلسلة)"
    if gold_used:
        out["gold_leg_pct"] = round((gold_used / xau_series - 1) * 100, 4)
        out["gold_source"] = gold_src
    else:
        out["gold_leg_pct"] = None
        out["gold_source"] = None
    # ③ب تشخيص: نفس شمعة الـTV وقت القياس (الذهب العالمية ما اتغيّرتش؟)
    if tv_xau and tv_xau.get("close"):
        out["tv_xau_same_bar_pct"] = round(
            (float(tv_xau["close"]) / xau_series - 1) * 100, 4)
    else:
        out["tv_xau_same_bar_pct"] = None
    # ④ رجل العملة: **صرف مستقل** (مش مشتقّ من الذهب) ⇒ شرط لازم
    fx_used = None
    fx_src = None
    if fx_independent:
        fx_used = float(fx_independent)
        fx_src = "independent_fx"
    out["fx_used"] = fx_used
    out["fx_source"] = fx_src
    # ⑤ ⛔ الرقم المشتقّ من السعر المحلي — للتوثيق بس، **مش** سعر صرف
    if ounce_live:
        implied_fx = gram_live * T / float(ounce_live)
        out["implied_egp_per_usd_from_market"] = round(implied_fx, 4)
        out["implied_fx_is_derived_from_gold"] = True
        out["implied_fx_note"] = ("رقم **مشتقّ من السعر المحلي** — مش سعر "
                                  "صرف مستقل، ومينفعش يُستخدم لإثبات إن "
                                  "الهامش المحلي = صفر.")
    else:
        out["implied_egp_per_usd_from_market"] = None
        out["implied_fx_is_derived_from_gold"] = True
    # ⑥ الدورية: هل الصرف المتاح مشتقّ من الذهب؟ (لازم لأ)
    circular = None
    if fx_used and gram_live and gold_used:
        _implied = gram_live * T / float(gold_used)
        _diff = abs(fx_used / _implied - 1) * 100 if _implied else None
        circular = bool(_diff is not None and _diff <= 0.01)
        out["circular_fx_detected"] = circular
        out["circular_fx_diff_pct"] = round(_diff, 6) if _diff is not None else None
    else:
        out["circular_fx_detected"] = None
    # ⑦ الهامش المحلي: لازم صرف **مستقل** + ذهب مستقل + **مش** دائري
    if fx_used and gold_used and not circular:
        out["local_margin_pct"] = round(
            (gram_live / (gold_used * fx_used / T) - 1) * 100, 4)
        out["local_margin_note"] = (
            "الهوامش مقاس بصرف **مستقل** (مش مشتقّ من الذهب) — رقم حقيقي.")
    elif circular:
        out["local_margin_pct"] = None
        out["local_margin_note"] = (
            "⛔ الصرف المتاح **مشتقّ من سعر الذهب** ⇒ الهامش غير قابل للقياس "
            "(مش صفر) — لازم صرف مستقل.")
    else:
        out["local_margin_pct"] = None
        out["local_margin_note"] = (
            "مفيش صرف مستقل وقت القياس ⇒ **مافيش هامش محسوب** (مش صفر).")
    # ⑧ وحدة الجرام: نسب العيّارات من نفس المصدر الحيّ = النقاء ÷ 24
    ratios = {}
    karats = loc.get("karats") or {}
    for k, purity in (("14", 14), ("18", 18), ("21", 21)):
        row = karats.get(k) or {}
        sell = row.get("sell_gram") or row.get("sell")
        if not sell or not gram_live:
            continue
        ratios[k] = {"sell_egp": float(sell),
                     "ratio": round(float(sell) / gram_live, 6),
                     "purity_over_24": round(purity / 24.0, 6),
                     "abs_error": round(abs(float(sell) / gram_live
                                            - purity / 24.0), 6)}
    out["karat_ratio_check"] = ratios
    # ⑨ الهوية: (1+ذهب)(1+دولار)(1+هامش) = 1/(1+انحراف)
    g = out.get("gold_leg_pct")
    f = out.get("fx_leg_pct")
    m = out.get("local_margin_pct")
    if g is not None and f is not None and m is not None:
        ident = (1.0 / ((1 + g / 100.0) * (1 + f / 100.0)
                        * (1 + m / 100.0)) - 1) * 100
        out["identity_check_pct"] = round(ident, 6)
        out["identity_error_pp"] = round(abs(ident - out["drift_pct"]), 6)
    return out


def circular_repro():
    """
    ⛔ **إعادة إنتاج العيب القديم** (R24-I14) — برهان سلبي:
       الصيغة القديمة (سعر الصرف الضمني مشتقّ من السعر المحلي ⇒ الهامش
       = ٠) بتطلع **صفر** مهما كان السعر المرصود.
       ⛔ ومع صيغة مستقلة (صرف مستقل) ⇒ الهامش بيبقى رقم حقيقي.
    """
    row = {"d": "2026-01-01", "xau": 3000.0, "egp_per_usd": 50.0,
           "gram": round(3000.0 * 50.0 / T, 4)}
    out = []
    for local_gram in (5000.0, 6000.0, 9000.0):
        loc = {"gram_24_reference": local_gram, "ounce_usd": 3000.0,
               "karats": {}}
        old_implied = local_gram * T / 3000.0
        old_margin = (local_gram / (3000.0 * old_implied / T) - 1) * 100
        new = decompose(row, loc, None, None, fx_independent=50.0,
                        gold_independent=3000.0)
        out.append({"local_gram": local_gram,
                    "old_circular_margin_pct": round(old_margin, 10),
                    "old_circular_margin_is_zero": abs(old_margin) < 1e-9,
                    "new_independent_margin_pct": new.get("local_margin_pct")})
    return out



def negative_proof(series_doc, drift_pct=5.0):
    """⛔ برهان سالب: لو السلسلة نفسها فيها انحراف ⇒ الاختبار الحتمي **يفشل**.

    ⛔ بن.Inject انحراف في آخر نقطة من نسخة السلسلة (في الذاكرة بس) ونشغّل
    الاختبار الحتمي في عملية منفصلة ⇒ لازم يطلع كود خروج ≠ ٠.
    """
    import gold_history as gh
    bad = copy.deepcopy(series_doc)
    last = bad["series"][-1]
    last["gram"] = round(float(last["gram"]) * (1 + drift_pct / 100.0), 4)
    runner = os.path.join(tempfile.gettempdir(), "_r24_gold_bad_runner.py")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(
            "import json, os, runpy, sys\n"
            "REPO = %r\n"
            "sys.path.insert(0, REPO)\n"
            "os.environ['GOLD_HISTORY_PATH'] = '/tmp/_r24_gold_bad_cache.json'\n"
            "import gold_history as gh\n"
            "with open('/tmp/_r24_gold_bad_series.json', encoding='utf-8') as fh:\n"
            "    doc = json.load(fh)\n"
            "gh.build = lambda force=False: doc\n"
            "try:\n"
            "    runpy.run_path(os.path.join(REPO, 'test_gold_integrity.py'),\n"
            "                  run_name='__main__')\n"
            "except SystemExit as exc:\n"
            "    code = exc.code if isinstance(exc.code, int) else 1\n"
            "    sys.stdout.flush()\n"
            "    os._exit(code)\n" % REPO)
    with open("/tmp/_r24_gold_bad_series.json", "w", encoding="utf-8") as fh:
        json.dump(bad, fh, ensure_ascii=False)
    proc = subprocess.run([sys.executable, runner], capture_output=True,
                          text=True, timeout=600, cwd=REPO)
    out = proc.stdout or ""
    drift_line = [l for l in out.splitlines() if "الفرق عن المعاداة" in l]
    return {
        "injected_drift_pct": drift_pct,
        "exit_code": proc.returncode,
        "failed_as_expected": proc.returncode != 0,
        "drift_check_line": (drift_line[0].strip() if drift_line else None),
        "tail": out.strip().splitlines()[-6:],
    }


def independent_readings():
    """
    📌 القراءات **المستقلة** (الجولة ٢٥): ذهب عالمي من مزوّد مستقل ·
       صرف من مصادر عملة مستقلة · سعر محلي من مرجع السوق.
    ⛔ مافيش قراءة ⇒ `None` + سبب (مافيش رقم مخترع).
    """
    try:
        import gold_parity as gpar
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    gold = gpar.world_gold(force=True)
    fx = gpar.fx_official(force=True)
    loc = gpar.local_gold(force=True)
    out = {"gold": gold, "fx": fx, "local": loc, "ok": False}
    out["ok"] = bool(gold.get("ok") and fx.get("ok") and loc.get("ok"))
    if not out["ok"]:
        out["error"] = "قراءة مستقلة ناقصة"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    doc, err = build_series()
    if not doc:
        print("⛔ السلسلة مبنيةش: %s" % err)
        return 2
    last = doc["series"][-1]
    loc, err = live_price()
    if not loc:
        print("⛔ السعر الحيّ مش متاح: %s" % err)
        return 2
    tv_xau = tv_now(TV_XAU)
    tv_fx = tv_now(TV_EGP)
    # 📌 القراءات المستقلة (دولار صرف مش مشتقّ من الذهب)
    ind = independent_readings()
    res = decompose(last, loc, tv_xau, tv_fx,
                    fx_independent=(ind.get("fx") or {}).get("value"),
                    gold_independent=(ind.get("gold") or {}).get("value"))
    res["measured_at_utc"] = _now_iso()
    res["independent_sources"] = {
        "gold": {"id": (ind.get("gold") or {}).get("id"),
                 "url": (ind.get("gold") or {}).get("url"),
                 "field": (ind.get("gold") or {}).get("field"),
                 "value": (ind.get("gold") or {}).get("value"),
                 "source_timestamp": (ind.get("gold") or {}).get("source_timestamp"),
                 "unit": (ind.get("gold") or {}).get("unit")},
        "fx": {"id": (ind.get("fx") or {}).get("id"),
               "url": (ind.get("fx") or {}).get("url"),
               "field": (ind.get("fx") or {}).get("field"),
               "value": (ind.get("fx") or {}).get("value"),
               "source_timestamp": (ind.get("fx") or {}).get("source_timestamp"),
               "unit": (ind.get("fx") or {}).get("unit"),
               "cross_checks": (ind.get("fx") or {}).get("cross_checks"),
               "dispersion_pct": (ind.get("fx") or {}).get("dispersion_pct")},
    }
    res["series_meta"] = {
        "points": len(doc.get("series") or []),
        "sources": doc.get("sources"),
        "from": (doc.get("series") or [{}])[0].get("d"),
        "to": last.get("d"),
    }
    print("── القياس ──")
    print("   السلسلة (%s): %.4f ج.م/جرام · ذهب %.4f · دولار %.4f"
          % (last.get("d"), last["gram"], last["xau"], last["egp_per_usd"]))
    print("   الحيّ (%s): %.2f ج.م/جرام · أونصة %.2f دولار"
          % (res["live"].get("updated_iso"), res["live"]["gram_24_reference_egp"],
             res["live"].get("ounce_usd") or float("nan")))
    print("   مستقل — ذهب: %s (وقت %s) · صرف: %s (وقت %s)"
          % ((ind.get("gold") or {}).get("value"),
             (ind.get("gold") or {}).get("source_timestamp"),
             (ind.get("fx") or {}).get("value"),
             (ind.get("fx") or {}).get("source_timestamp")))
    print("   الانحراف: %+.4f%% · ذهب %s · هامش محلي %s"
          % (res["drift_pct"], res.get("gold_leg_pct"),
             res.get("local_margin_pct")))
    print("   الاتساق الداخلي للسلسلة: %+.6f%%" % res["internal_consistency_pct"])
    print("   الهامش المحلي: %s" % res.get("local_margin_note"))

    print("── إعادة إنتاج العيب القديم (دورية) ──")
    repro = circular_repro()
    res["circular_repro"] = repro
    for row in repro:
        print("   جرام محلي %.0f ⇒ الهامش القديم %.6f%% · الهامش المستقل %s%%"
              % (row["local_gram"], row["old_circular_margin_pct"],
                 row["new_independent_margin_pct"]))

    print("── البرهان السالب (انحراف في السلسلة ⇒ الاختبار الحتمي يفشل) ──")
    neg = negative_proof(doc)
    res["negative_proof"] = neg
    print("   كود الخروج: %s (المتوقع ≠ ٠) ⇒ %s"
          % (neg["exit_code"], "✅ فشل زي المفروض" if neg["failed_as_expected"]
             else "❌ مانشلش"))

    out_path = args.out
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
        print("   الأدلة اتكتبت: %s" % out_path)
    return 0 if neg["failed_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
