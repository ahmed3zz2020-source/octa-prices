#!/usr/bin/env python3
"""
🧪 اختبار فلتر إخفاء الوصفة — بعد إصلاح نظام الاستراتيجيات
───────────────────────────────────────────────────────────────
الهدف: نتأكد من حاجتين مع بعض، وهما متناقضين:

  ١) الوصفة ما تطلعش أبدًا (أوزان · عتبات · معادلات)
  ٢) قوائم الاستراتيجيات ونتيجة التقييم بتوصل للواجهة

✅ بيشتغل على الكود الحقيقي: بيقرا update_prices.py، بيستخرج
   التعريفات بالـAST، وبينفّذها — من غير استيراد السيرفر كله.
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).with_name("update_prices.py")
FAILED = []


def load_filter():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & {"_HIDDEN_KEYS", "_TOP_ALLOWED_KEYS"}:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "_hide_recipe":
            nodes.append(node)
    if len(nodes) != 3:
        raise SystemExit(f"❌ متوقع ٣ تعريفات في الملف، لقينا {len(nodes)}")
    ns = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SRC), "exec"), ns)
    return ns["_hide_recipe"]


def check(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} {detail}")
        FAILED.append(name)


def walk_keys(obj, acc=None):
    """كل المفاتيح في أي عمق."""
    acc = acc if acc is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            walk_keys(v, acc)
    elif isinstance(obj, list):
        for i in obj:
            walk_keys(i, acc)
    return acc


def main():
    hide = load_filter()

    # ── ١) /api/stocks: نتيجة كل سهم ما فيهاش الوصفة ولا الاستراتيجيات ──
    print("\n① /api/stocks")
    out = hide({
        "egx30": [{
            "code": "COMI", "name": " commercials", "price": 33.2,
            "final_score": 72.1, "safety_score": 65.0,
            "strategies": {"balanced": {"name": "متوازن", "score": 70.5,
                                        "decision": "إشارة محايدة",
                                        "filters_passed": True}},
        }],
        "snapshot_id": "20261020-1035-abcd",
    })
    item = out["egx30"][0]
    check("النتيجة والأسعار بتفضل", item.get("final_score") == 72.1 and item.get("price") == 33.2)
    check("'strategies' جوه السهم اتشال", "strategies" not in item)
    check("مفيش مفاتيح وصفة في الرد كله",
          not (walk_keys(out) & {"weights", "axis_weights", "risk_penalty_mult",
                                 "min_liquidity", "formula", "scoring", "calibration",
                                 "raw_scores", "part_scores", "sub_scores"}),
          f"← {sorted(walk_keys(out) & {'weights', 'axis_weights', 'risk_penalty_mult'})}")

    # ── ٢) /api/strategies: القائمة توصل، والأوزان جواها مخفية ──
    print("\n② /api/strategies")
    out = hide({
        "strategies": [
            {"key": "swing", "name": "مضاربة (سوينج)", "desc": "صفقات قصيرة",
             "timeframe": "أيام إلى أسابيع", "focus": "الحركة والزخم فقط",
             "weights": {"technical": 40, "fundamental": 12}},
            {"key": "balanced", "name": "متوازن", "desc": "توازن",
             "timeframe": "3-12 شهر", "focus": "كل المحاور",
             "weights": {"technical": 18, "fundamental": 25}},
        ],
    })
    check("'strategies' وصل في مستوى الرد الأعلى", "strategies" in out)
    check("القائمة فيها استراتيجيتين", len(out.get("strategies", [])) == 2)
    check("الاسم والإطار الزمني موجودين",
          out["strategies"][0].get("name") == "مضاربة (سوينج)"
          and out["strategies"][0].get("timeframe") == "أيام إلى أسابيع")
    check("الأوزان جوه القائمة مخفية", "weights" not in out["strategies"][0])

    # ── ٣) /api/strategy/<code>/<strategy>: النتيجة توصل والأوزان مخفية ──
    print("\n③ /api/strategy/COMI/balanced")
    out = hide({
        "code": "COMI", "name": "تجاري", "price": 33.2,
        "strategy": {
            "strategy": "balanced", "strategy_name": "متوازن",
            "timeframe": "3-12 شهر", "focus": "كل المحاور",
            "score": 70.5,
            "axes": {"technical": 72.0, "fundamental": 61.0, "liquidity": 55.0,
                     "news": 45.0, "sentiment": 50.0, "risk": 66.0, "portfolio": 70.0},
            "weights": {"technical": 0.18, "fundamental": 0.25, "liquidity": 0.12,
                        "news": 0.08, "sentiment": 0.05, "risk": 0.20, "portfolio": 0.12},
            "base": 72.0, "risk_penalty": -3.2, "liquidity_penalty": 0.0,
            "filters_passed": True, "filter_notes": [],
            "decision": "إشارة محايدة", "confidence": 80.0,
        },
        "all_strategies": {"balanced": {"name": "متوازن", "score": 70.5,
                                        "decision": "إشارة محايدة", "filters_passed": True}},
    })
    st = out.get("strategy")
    check("'strategy' وصل في مستوى الرد الأعلى", isinstance(st, dict))
    check("النتيجة والقرار موجودين",
          st and st.get("score") == 70.5 and st.get("decision") == "إشارة محايدة")
    check("'axes' وصل (نتيجة كل محور)", st and "axes" in st and len(st["axes"]) == 7)
    check("'confidence' و'base' و'risk_penalty' وصلوا",
          st and all(k in st for k in ("confidence", "base", "risk_penalty")))
    check("الأوزان مخفية جوه النتيجة", st and "weights" not in st)
    check("'all_strategies' وصل", "all_strategies" in out)
    check("مفيش وصفة في الرد كله",
          not (walk_keys(out) & {"weights", "axis_weights", "risk_penalty_mult",
                                 "min_liquidity", "formula", "scoring", "calibration",
                                 "raw_scores", "part_scores", "sub_scores"}),
          f"← {sorted(walk_keys(out) & {'weights', 'axis_weights'})}")

    # ── ٤) /api/portfolio و /api/stats: قائمة الأسماء توصل ──
    print("\n④ /api/portfolio + /api/stats")
    out = hide({
        "portfolio": {"holdings": 3, "total_value": 100.0},
        "sectors": [{"name": "بنوك", "count": 5}],
        "strategies": [{"key": "swing", "name": "مضاربة (سوينج)", "timeframe": "أيام"}],
    })
    check("'strategies' وصل", "strategies" in out and len(out["strategies"]) == 1)
    check("'portfolio' و'sectors' وصلوا", "portfolio" in out and "sectors" in out)

    # ── ٥) عمق القائمة: عناصر القائمة في عمق ١ ──
    print("\n⑤ عمق القوائم")
    out = hide({"egx30": [{"code": "COMI", "strategies": {"balanced": {"score": 70}}}]})
    check("'strategies' جوه عنصر في قائمة اتشال", "strategies" not in out["egx30"][0])
    out = hide([{"code": "COMI", "strategies": {"balanced": {"score": 70}}}])
    check("رد نص root: 'strategies' جوه اتشال", "strategies" not in out[0])

    # ── ٦) الوصفة في أي عمق تتفسخ ──
    print("\n⑥ الوصفة في أي عمق")
    out = hide({"a": {"b": {"c": {"weights": {"x": 1}, "formula": "y",
                                      "risk_penalty_mult": 2.0, "min_liquidity": 45}}}})
    check("كل مفاتيح الوصفة اتشالت", "weights" not in walk_keys(out)
          and "formula" not in walk_keys(out)
          and "risk_penalty_mult" not in walk_keys(out)
          and "min_liquidity" not in walk_keys(out))

    # ── ٧) وصفة المعايرة: current_weights مخفي + تعديل الأوزان محمي ──
    print("\n⑦ وصفة المعايرة")
    out = hide({"calibration": {"version": "v1.1"}, "current_weights": {"technical": 0.18},
                "note": "لتعديل الأوزان"})
    check("'current_weights' مخفي", "current_weights" not in out)
    check("'calibration' لسه مخفي (فيه سجل الأوزان)", "calibration" not in out)
    check("الملاحظة العامة بتفضل", out.get("note", "").startswith("لتعديل"))

    # ── ٨) وزن المحور في مساهمات /api/explain ──
    print("\n⑧ وزن المحور في المساهمات")
    out = hide({"explanation": {"contributions": [
        {"axis": "fundamental", "name": "التحليل الأساسي", "score": 62.0,
         "axis_weight": 22.0, "contribution": 13.6}]}})
    c = out["explanation"]["contributions"][0]
    check("'axis_weight' اتشال", "axis_weight" not in c)
    check("'contribution' فاضل (نتيجة مش وصفة)", c.get("contribution") == 13.6)
    check("'score' فاضل", c.get("score") == 62.0)
    check("مفيش أي مفتاح وزن في الرد", "weight" not in walk_keys(out))

    src = SRC.read_text(encoding="utf-8")
    check("'weight' لسه موجود للأخبار (وزن الأهمية مش وصفة)",
          '"weight": weight' in src)
    i = src.find('@app.route("/api/calibration")')
    block = src[i:i + 1200] if i >= 0 else ""
    check("POST /api/calibration محمي بتوكن الأدمن",
          'X-OCTA-Admin' in block and 'compare_digest' in block and '503' in block)
    check("GET /api/calibration لسه مفتوح للواجهة",
          'if request.method == "POST"' in block and "current_weights" in block)

    print("\n" + "═" * 46)
    if FAILED:
        print(f"❌ فشل {len(FAILED)} اختبار: {', '.join(FAILED)}")
        return 1
    print("✅ كل الاختبارات عدّت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
