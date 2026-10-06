#!/bin/bash
# فحص سلامة المشروع — شغّله قبل أي تعديل
cd "$(dirname "$0")"
echo "═══ فحص سلامة OCTA ═══"
echo "1. syntax:"
python3 -c "import ast; ast.parse(open('update_prices.py').read())" && echo "   ✅ OK" || echo "   ❌ FAIL"
echo "2. الدوال الـ 15:"
MISS=0
for f in tech_score fundamental_score liquidity_score news_engine sentiment_engine portfolio_fit risk_engine final_score opportunity_engine strategy_score explain_score bt_snapshot stress_test apply_calibration rank_stocks; do
  if grep -q "def $f" update_prices.py; then printf "   ✅ %s\n" "$f"; else printf "   ❌ %s مفقود!\n" "$f"; MISS=1; fi
done
echo "3. الأوزان (لازم = 1.00):"
python3 -c "
import re
s=open('update_prices.py').read()
m=re.search(r'AXIS_WEIGHTS = \{(.*?)\n\}', s, re.S)
w=[float(x) for x in re.findall(r':\s*([0-9.]+)', m.group(1))]
t=round(sum(w),4)
print(f'   {\"✅\" if abs(t-1.0)<0.01 else \"❌\"} المجموع = {t}')
"
echo "4. عدد endpoints: $(grep -c '@app.route' update_prices.py)"
echo "5. حجم: $(wc -l < update_prices.py) سطر"
[ "$MISS" == "1" ] && echo "❌ فيه دوال ناقصة — STOP!" || echo "✅ كل حاجة سليمة"
