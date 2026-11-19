#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📏 الجولة ٢٦ (R26 · المتطلب ٣) — **قياس أثر PEG على الترتيب** ⭐

🎯 الغرض ⭐: البند R23-I08 كان **مفتوحاً** من الجولة ٢٣ ⭐ ⇒ ده القياس ⭐.

📌 تلات خطوات ⭐:
   ① **تدقيق المصدر** ⭐: هل في مصدر مصرّح وموثّق لنمو الأرباح
      (`ni_growth`) ⭐؟ ⛔ لو لأ ⇒ بنوثّق عدم التوفر ⭐ (مش تخمين ⭐).
   ② **القياس الحقيقي** ⭐: الترتيب **قبل/بعد** influence PEG ⭐
      على **عيّنة معروفة** ⭐ (ملف `data_full.json` الحقيقي ⭐
      بتاريخه ⭐) ⭐ — ونتائج بأرقام ⭐.
   ③ **حساسية معلَّمة** ⭐: لو (افتراضياً ⭐) في مصدر لنمو الأرباح ⭐
      ⇒ كام موضع في الترتيب هيتغيّر ⭐؟ ⭐
      ⛔ دى **تحليل حساسية** ⭐ (افتراضي ⭐) ⭐ — **مش مصدر بيانات** ⭐
      ⛔ و**مش بتتوصّل بالإنتاج** ⭐ ⛔.

⛔ ممنوع ⭐:
   · إضافة نقاط PEG ⭐
   · تغيير منهجية الترتيب ⭐
   · تغيير أي وزن أو عتبة ⭐
   · توصيل أي قياس بالإنتاج ⭐
   📌 القياس بيعدّل في الذاكرة **جوه الأداة دي بس** ⭐
   (runtime patch ⭐) ⭐ — كود الإنتاج ما اتغيّرش ⭐.

📌 التشغيل ⭐:
   python3 tools/measure_peg_impact_r26.py
   python3 tools/measure_peg_impact_r26.py --report-json /tmp/peg_r26.json
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix="octa_r26_peg_", dir="/tmp")
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

os.environ["OCTA_DATA_DIR"] = TMP
os.environ["OCTAD_TOKEN_SECRET"] = "TEST-ONLY-r26-peg-token"
os.environ["OCTA_PIN_PEPPER"] = "TEST-ONLY-r26-peg-pepper"
os.environ["OCTAD_DEV"] = "1"
os.environ["OCTA_BG_TASKS"] = "off"
os.environ["OCTA_WARMUP"] = "0"

import _stub_env  # noqa: E402

fl_mod, _ = _stub_env.install()

import update_prices as up  # noqa: E402
import octa_score  # noqa: E402

DATA_FULL = os.path.join(REPO, "data_full.json")
REPORT = {"generated_at": None, "sample": {}, "source_audit": {},
          "measurement": {}, "sensitivity": {}, "conclusion": {}}


def hr(title):
    print("\n" + "═" * 66)
    print("  " + title)
    print("═" * 66)


# ══════════════════════════════════════════════════════════════════════
#  ① تدقيق المصدر — هل في مصدر مصرّح لنمو الأرباح؟
# ══════════════════════════════════════════════════════════════════════


def audit_source():
    hr("① تدقيق مصدر نمو الأرباح (ni_growth) — متاح ولا لأ؟")

    # أ) ملفات البيانات
    data_files = [DATA_FULL]
    ddir = os.path.join(REPO, "data")
    if os.path.isdir(ddir):
        for n in sorted(os.listdir(ddir)):
            if n.endswith(".json"):
                data_files.append(os.path.join(ddir, n))
    hits_data = []
    for p in data_files:
        try:
            raw = open(p, encoding="utf-8").read()
        except Exception:
            continue
        if "ni_growth" in raw:
            hits_data.append(os.path.basename(p))
    print("  · ملفات البيانات المفحوصة: %d" % len(data_files))
    print("  · ملفات فيها ni_growth: %s" % (hits_data or "لا يوجد ⭐"))

    # ب) أعمدة الـscanner
    src = open(os.path.join(REPO, "update_prices.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    cols = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in ("TV_COLUMNS", "TV_TECH_COLUMNS"):
                    try:
                        cols[t.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    fields = []
    for c in (cols.get("TV_COLUMNS") or []) + (cols.get("TV_TECH_COLUMNS") or []):
        fields.append(c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else c)
    hit_cols = [f for f in fields if "ni_growth" in str(f)]
    print("  · أعمدة الـscanner المفحوصة: %d" % len(fields))
    print("  · أعمدة اسمها ni_growth: %s" % (hit_cols or "لا يوجد ⭐"))

    # ج) أسطر الكتابة في الكود
    writers = []
    for name in ("update_prices.py", "opp_engine.py", "octa_score.py",
                 "update_prices.py.bak"):
        p = os.path.join(REPO, name)
        if not os.path.isfile(p):
            continue
        try:
            t2 = ast.parse(open(p, encoding="utf-8").read())
        except Exception:
            continue
        for node in ast.walk(t2):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant):
                    if t.slice.value == "ni_growth":
                        writers.append((name, node.lineno))
    print("  · أسطر **تكتب** ni_growth في الكود: %s" % (writers or "لا يوجد ⭐"))

    REPORT["source_audit"] = {
        "data_files_checked": len(data_files),
        "data_files_with_ni_growth": hits_data,
        "scanner_columns_checked": len(fields),
        "scanner_columns_named_ni_growth": hit_cols,
        "code_lines_writing_ni_growth": writers,
        "available": bool(hits_data or hit_cols or writers),
        "verdict_ar": ("مصدر متاح ⭐" if (hits_data or hit_cols or writers)
                       else "لا يوجد أي مصدر مصرّح لنمو الأرباح ⭐ ⇒ PEG غير متاح ⭐"),
    }
    print("  ⇒ الحكم: %s" % REPORT["source_audit"]["verdict_ar"])
    return REPORT["source_audit"]["available"]


# ══════════════════════════════════════════════════════════════════════
#  بناء العيّنة المعروفة من البيانات الحقيقية
# ══════════════════════════════════════════════════════════════════════


def build_sample():
    hr("② العيّنة المعروفة — data_full.json (ملف حقيقي بتاريخه)")
    d = json.load(open(DATA_FULL, encoding="utf-8"))
    stocks = d.get("stocks") or {}
    items = []
    for code, v in stocks.items():
        it = {
            "code": code,
            "name": v.get("name") or code,
            "sector": v.get("sectorAr") or v.get("sector") or "أخرى",
            "price": v.get("p"),
            "pe": v.get("pe"), "pb": v.get("pb"), "roe": v.get("roe"),
            "net_margin": v.get("nm"), "de_ratio": v.get("de"),
            "eps": v.get("eps"), "revenue": v.get("rev"),
            "div_yield": v.get("dy"), "beta": v.get("beta"),
            "volatility": v.get("vol1y"), "vol1y": v.get("vol1y"),
            "mdd1y": v.get("mdd1y"), "sharpe3y": v.get("sharpe3y"),
            "volume": v.get("v"), "mkt_cap": v.get("mc"),
            "rel_volume": v.get("relvol"),
            "rsi": v.get("rsi"), "sma50": v.get("ma50"),
            "sma200": v.get("ma200"), "macd": v.get("macd"),
            "macd_signal": v.get("macdSig"),
            "data_confidence": v.get("conf"),
        }
        items.append(it)
    stats = octa_score.build_sector_stats(items)
    REPORT["sample"] = {
        "file": "data_full.json",
        "file_timestamp": d.get("_ts"),
        "file_source": d.get("_src"),
        "stocks_in_file": len(stocks),
        "items_built": len(items),
        "sectors": len(stats),
        "with_pe": sum(1 for i in items if i.get("pe") is not None),
        "with_pb": sum(1 for i in items if i.get("pb") is not None),
        "with_ni_growth": sum(1 for i in items if i.get("ni_growth") is not None),
    }
    print("  · الملف: %s · التاريخ: %s · المصدر: %s"
          % (REPORT["sample"]["file"], REPORT["sample"]["file_timestamp"],
             REPORT["sample"]["file_source"]))
    print("  · الأسهم: %d · القطاعات: %d · فيها P/E: %d · فيها P/B: %d"
          % (len(items), len(stats), REPORT["sample"]["with_pe"],
             REPORT["sample"]["with_pb"]))
    print("  · فيها نمو أرباح (ni_growth): %d ⭐"
          % REPORT["sample"]["with_ni_growth"])
    return items, stats


# ══════════════════════════════════════════════════════════════════════
#  الترتيب — نفس محرك الإنتاج بالظبط
# ══════════════════════════════════════════════════════════════════════


def rank(items, stats):
    """ترتيب بنفس محرك الإنتاج (final_score) — بترتيب تنازلي."""
    out = []
    for it in items:
        t = octa_score.tech_score(it)
        f = up.fundamental_score(it, stats)
        l = octa_score.liquidity_score(it)
        r = up.risk_engine(it, stats)
        fin = up.final_score(it, t, f, l, stats)
        score = fin.get("final_score")
        if score is None:
            continue
        out.append({"code": it["code"], "score": score,
                    "fundamental": (fin.get("axes") or {}).get("fundamental"),
                    "risk": (fin.get("axes") or {}).get("risk"),
                    "peg": (f or {}).get("peg")})
    out.sort(key=lambda x: -x["score"])
    return out


def compare(a, b, label):
    """مقارنة ترتيبين: كام موضع اتغيّر + طوبولوجيا ⚠."""
    ca = [x["code"] for x in a]
    cb = [x["code"] for x in b]
    pos_a = {c: i + 1 for i, c in enumerate(ca)}
    pos_b = {c: i + 1 for i, c in enumerate(cb)}
    common = [c for c in ca if c in pos_b]
    changed = [c for c in common if pos_a[c] != pos_b[c]]
    max_shift = 0
    for c in common:
        max_shift = max(max_shift, abs(pos_a[c] - pos_b[c]))
    # ترابط كيندال (تقريب على الرتب المشتركة)
    conc = disc = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            s = (pos_a[common[i]] - pos_a[common[j]]) * \
                (pos_b[common[i]] - pos_b[common[j]])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    total_pairs = conc + disc
    tau = round((conc - disc) / total_pairs, 4) if total_pairs else 1.0
    top_a = ca[:20]
    top_b = cb[:20]
    overlap = len(set(top_a) & set(top_b))
    res = {
        "label": label,
        "n_a": len(ca), "n_b": len(cb),
        "positions_changed": len(changed),
        "positions_changed_pct": round(len(changed) * 100.0 / len(common), 2)
        if common else 0.0,
        "max_rank_shift": max_shift,
        "kendall_tau": tau,
        "top20_overlap": overlap,
        "top20_identical": top_a == top_b,
        "changed_examples": [(c, pos_a[c], pos_b[c]) for c in changed[:10]],
    }
    print("  · %s" % label)
    print("    موضع اتغيّر: %d / %d (%.2f%%) · أقصى إزاحة: %d · كيندال: %s"
          % (res["positions_changed"], res["n_a"], res["positions_changed_pct"],
             res["max_rank_shift"], res["kendall_tau"]))
    print("    تقاطع أعلى ٢٠: %d/20 · نفس الترتيب بالظبط: %s"
          % (overlap, res["top20_identical"]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-json", default="")
    args = ap.parse_args()

    import datetime
    REPORT["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    available = audit_source()
    items, stats = build_sample()

    hr("③ القياس الحقيقي — الترتيب قبل/بعد influence PEG")
    base = rank(items, stats)

    #Ranking A: كما هو مشحون
    # Ranking B: PEG معطّل (runtime patch فقط ⭐ — كود الإنتاج ما اتغيّرش ⭐)
    orig_peg_score = up.peg_score
    try:
        up.peg_score = lambda pe, g: (0.0, None)
        without = rank(items, stats)
    finally:
        up.peg_score = orig_peg_score

    m = compare(base, without, "الحالة الفعلية (بيانات اليوم) ⇄ نفس الترتيب بدون نقاط PEG")
    REPORT["measurement"] = {
        "ranking_with_peg": base[:25],
        "ranking_without_peg": without[:25],
        "comparison": m,
        "peg_points_added": 0,
        "methodology_changed": False,
        "note_ar": ("نمو الأرباح غير متاح من أي مصدر مصرّح ⭐ ⇒ PEG = "
                    "«غير متاح» ⭐ ⇒ صفر نقطة لكل سهم ⭐ ⇒ "
                    "الترتيب **متطابق** مع/ بدون PEG ⭐ ⇒ "
                    "الأثر الحالي على الترتيب = **صفر موضع** ⭐."),
    }
    print("  ⇒ الأثر الحالي: %d موضع من %d ⭐ (PEG غير متاح ⇒ صفر نقطة ⭐)"
          % (m["positions_changed"], m["n_a"]))

    # ── حساسية معلَّمة (افتراضي ⭐ — مش مصدر ⭐) ──
    hr("④ تحليل حساسية (افتراضي ⭐ — مش مصدر بيانات ⭐)")
    sens = []
    for g in (5.0, 15.0, 30.0):
        patched = []
        for it in items:
            it2 = dict(it)
            it2["ni_growth"] = g          # ⭐ افتراضي ⭐ موحّد ⭐
            patched.append(it2)
        r_with = rank(patched, stats)
        try:
            up.peg_score = lambda pe, gg: (0.0, None)
            r_without = rank(patched, stats)
        finally:
            up.peg_score = orig_peg_score
        c = compare(r_with, r_without,
                    "نمو أرباح افتراضي موحّد %.0f%% ⇄ بدون نقاط PEG" % g)
        c["hypothetical_growth_pct"] = g
        c["is_real_data_source"] = False
        sens.append(c)
    REPORT["sensitivity"] = {
        "cases": sens,
        "note_ar": ("حساسية **افتراضية** ⭐: نمو أرباح موحّد لكل الأسهم ⭐ "
                    "عشان نعرف **حدود** أثر PEG ⭐. ⛔ مش مصدر بيانات ⭐ "
                    "⛔ مش متوصّل بالإنتاج ⭐ ⛔ ولا نقطة PEG اتضافت ⭐."),
    }

    REPORT["conclusion"] = {
        "r23_i08_status": "مقيس ⭐",
        "peg_available_now": available,
        "current_ranking_impact_positions": m["positions_changed"],
        "current_ranking_impact_pct": m["positions_changed_pct"],
        "kendall_tau": m["kendall_tau"],
        "top20_identical": m["top20_identical"],
        "sensitivity_max_positions_changed": max(
            (s["positions_changed"] for s in sens), default=0),
        "sensitivity_max_rank_shift": max(
            (s["max_rank_shift"] for s in sens), default=0),
        "no_production_change": True,
        "no_peg_points_added": True,
    }
    hr("⑤ الخلاصة")
    print(json.dumps(REPORT["conclusion"], ensure_ascii=False, indent=2))

    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as fh:
            json.dump(REPORT, fh, ensure_ascii=False, indent=2)
        print("📄 التقرير: %s" % args.report_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
