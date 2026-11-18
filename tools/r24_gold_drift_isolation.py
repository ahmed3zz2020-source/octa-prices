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


def decompose(series_last, loc, tv_xau, tv_fx):
    """تفكيك الانحراف: ذهب · دولار · هامش محلي."""
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
    # ③ رجل الذهب: سعر الأونصة من **السوق المحلي نفسه** مقابل إغلاق
    #    السلسلة ⇒ ده الفرق في الذهب بين نقطة السلسلة ووقت القياس.
    if ounce_live:
        out["gold_leg_pct"] = round((float(ounce_live) / xau_series - 1) * 100, 4)
    elif tv_xau and tv_xau.get("close"):
        out["gold_leg_pct"] = round((tv_xau["close"] / xau_series - 1) * 100, 4)
    else:
        out["gold_leg_pct"] = None
    # ③ب تشخيص: نفس شمعة الـTV وقت القياس (الذهب العالمية ما اتغيّرتش؟)
    if tv_xau and tv_xau.get("close"):
        out["tv_xau_same_bar_pct"] = round(
            (tv_xau["close"] / xau_series - 1) * 100, 4)
    else:
        out["tv_xau_same_bar_pct"] = None
    # ④ رجل العملة: الفرق بين سعر الصرف الرسمي في السلسلة والضمني من السوق
    if ounce_live:
        implied_fx = gram_live * T / float(ounce_live)
        out["implied_egp_per_usd_from_market"] = round(implied_fx, 4)
        out["fx_leg_pct"] = round((implied_fx / fx_series - 1) * 100, 4)
        # ⑤ الهامش المحلي بعد ضبط الدولار الضمني
        out["local_margin_pct"] = round(
            (gram_live / (float(ounce_live) * implied_fx / T) - 1) * 100, 4)
    else:
        out["implied_egp_per_usd_from_market"] = None
        out["fx_leg_pct"] = None
        out["local_margin_pct"] = None
    # ⑥ وحدة الجرام: نسب العيّارات من نفس المصدر الحيّ = النقاء ÷ 24
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
    # ⑦ الهوية: (1+ذهب)(1+دولار)(1+هامش) = 1/(1+انحراف)
    g = out.get("gold_leg_pct")
    f = out.get("fx_leg_pct")
    m = out.get("local_margin_pct")
    if g is not None and f is not None and m is not None:
        ident = (1.0 / ((1 + g / 100.0) * (1 + f / 100.0)
                        * (1 + m / 100.0)) - 1) * 100
        out["identity_check_pct"] = round(ident, 6)
        out["identity_error_pp"] = round(abs(ident - out["drift_pct"]), 6)
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
    res = decompose(last, loc, tv_xau, tv_fx)
    res["measured_at_utc"] = _now_iso()
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
    print("   الانحراف: %+.4f%% · ذهب %s · دولار %s · هامش %s"
          % (res["drift_pct"], res.get("gold_leg_pct"), res.get("fx_leg_pct"),
             res.get("local_margin_pct")))
    print("   الاتساق الداخلي للسلسلة: %+.6f%%" % res["internal_consistency_pct"])

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
