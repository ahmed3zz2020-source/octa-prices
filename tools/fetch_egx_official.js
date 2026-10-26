/**
 * 📸 جلب لقطة رسمية من البورصة المصرية (EGX) — ٢٦ أكتوبر ٢٠٢٦
 * ⚠️ لازم يتشغّل بمتصفح حقيقي (Playwright) لأن الموقع محمي بـF5/TSPD.
 * 📌 الناتج: data/index_official.json
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('/usr/local/lib/node_modules/playwright');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'index_official.json');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const INDEXES = [
  { code: 'CASE30', id: 'EGX30' },
  { code: 'EGX70_EWI', id: 'EGX70' },
  { code: 'EGX100_EWI', id: 'EGX100' },
  { code: 'EGX_SHARIAH', id: 'EGX33' },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: '/root/.cache/ms-playwright/chromium-1243/chrome-linux/chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, userAgent: UA });
  const page = await ctx.newPage();

  const out = {
    version: new Date().toISOString().slice(0, 10),
    source: 'البورصة المصرية (EGX) — beta.egx.com.eg/api/bff/egx',
    source_note: 'لقطة رسمية: قيمة المؤشر، الأوزان، ومكونات كل مؤشر + حالة السوق.',
    market_status: null,
    indices: {},
  };

  // نجمع الردود من الشبكة
  const bag = {};
  page.on('response', async (r) => {
    const u = r.url();
    const m = u.match(/\/api\/bff\/egx\/([a-z0-9-]+)(?:\?([^#]*))?/i);
    if (!m) return;
    const key = m[1] + (m[2] ? '?' + m[2] : '');
    try {
      const j = await r.json();
      if (j && j.success && j.data) bag[key] = j.data;
    } catch (e) { }
  });

  // 1) صفحة المؤشرات — بتدّي market-status + index-data لكل المؤشر
  // (من مرتين: عشان نضمن إن أول طلب ما يضيعش)
  for (let pass = 0; pass < 2; pass++) {
    for (const ix of INDEXES) {
      await page.goto('https://beta.egx.com.eg/en/market/indices?index=' + ix.code,
        { waitUntil: 'networkidle', timeout: 60000 }).catch(() => { });
      await page.waitForTimeout(3500);
    }
  }

  // 2) الأوزان + المكونات
  for (let pass = 0; pass < 2; pass++) {
    for (const ix of INDEXES) {
      await page.goto('https://beta.egx.com.eg/en/market/indices/constituents?index=' + ix.code,
        { waitUntil: 'networkidle', timeout: 60000 }).catch(() => { });
      await page.waitForTimeout(3000);
    }
  }
  // 3) أوزان EGX30 (اللي ليها endpoint خاص) — نعيد زيارة الصفحة
  for (let a = 0; a < 2; a++) {
    await page.goto('https://beta.egx.com.eg/en/market/indices/constituents?index=CASE30',
      { waitUntil: 'networkidle', timeout: 60000 }).catch(() => { });
    await page.waitForTimeout(4000);
  }
  const w30 = bag['egx30-weights'] || null;

  out.market_status = bag['market-status'] || null;
  for (const ix of INDEXES) {
    const live = bag['index-data?interval=1&indexName=' + ix.code] || null;
    const cons = bag['index-constituents?indexName=' + ix.code] || null;
    const weights = (ix.code === 'CASE30' && w30 && w30.items) ? w30.items : null;
    out.indices[ix.id] = {
      egx_code: ix.code,
      live: live && live.liveIndex ? live.liveIndex : (live || null),
      constituents: (cons && cons.items) ? cons.items : (Array.isArray(cons) ? cons : []),
      weights: weights || [],
    };
    console.log('✅', ix.id, 'live=', !!(out.indices[ix.id].live),
      'cons=', (out.indices[ix.id].constituents || []).length,
      'weights=', (out.indices[ix.id].weights || []).length);
  }

  if (!out.market_status || !Object.keys(out.indices).length) {
    console.error('❌ البيانات الراجعة ناقصة — مش هنكتب ملف');
    await browser.close();
    process.exit(1);
  }
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('💾', OUT, (fs.statSync(OUT).size / 1024).toFixed(1) + ' KB');
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
