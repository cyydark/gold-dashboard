const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  console.log('=== Task 2: 验证价格卡片池随机化 ===\n');

  // ── 加载页面 ────────────────────────────────────────────────────────────────
  console.log('Step 1: 加载页面，等待卡片显示...');
  await page.goto('http://localhost:18000/', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForSelector('#card-XAUUSD:not([style*="display: none"])', { timeout: 10000 });
  await page.waitForTimeout(500);

  function getCardState(sym) {
    return page.evaluate((s) => {
      const el = document.getElementById('card-' + s);
      return {
        color: getComputedStyle(el).getPropertyValue('--card-accent').trim(),
        font:  getComputedStyle(el).getPropertyValue('--card-font').trim(),
      };
    }, sym);
  }

  // ── Step 2: 记录初始颜色/字体 ──────────────────────────────────────────────
  console.log('\nStep 2: 记录初始颜色/字体...');
  const initial = {};
  for (const sym of ['XAUUSD', 'AU9999', 'USDCNY']) {
    initial[sym] = await getCardState(sym);
    console.log(`  ${sym}: ${initial[sym].color} | ${initial[sym].font.substring(0, 25)}...`);
  }
  const uniqueColors = new Set(Object.values(initial).map((s) => s.color)).size;
  const uniqueFonts  = new Set(Object.values(initial).map((s) => s.font)).size;
  console.log(`  唯一颜色: ${uniqueColors}/3 — ${uniqueColors === 3 ? '✓' : '✗'}`);
  console.log(`  唯一字体: ${uniqueFonts}/3  — ${uniqueFonts === 3 ? '✓' : '✗'}`);

  // ── Step 3: 等待价格更新（~15s）───────────────────────────────────────────
  console.log('\nStep 3: 等待价格轮询更新（最多 20s）...');
  const ts1 = await page.$eval('#last-update', (el) => el.textContent);
  await page.waitForTimeout(20000);
  const ts2 = await page.$eval('#last-update', (el) => el.textContent);
  const gotUpdate = ts1 !== ts2;
  console.log(`  时间戳: ${ts1} → ${ts2}`);
  console.log(`  更新触发: ${gotUpdate ? '✓' : '✗ (测试继续)'}`);

  // ── Step 4: 价格更新后状态 ─────────────────────────────────────────────────
  console.log('\nStep 4: 价格更新后颜色/字体...');
  const afterUpdate = {};
  for (const sym of ['XAUUSD', 'AU9999', 'USDCNY']) {
    afterUpdate[sym] = await getCardState(sym);
    console.log(`  ${sym}: ${afterUpdate[sym].color} | ${afterUpdate[sym].font.substring(0, 25)}...`);
  }
  const uniqueAfter = new Set(Object.values(afterUpdate).map((s) => s.color)).size;
  console.log(`  更新后唯一颜色: ${uniqueAfter}/3 — ${uniqueAfter === 3 ? '✓' : '✗'}`);

  let anyChanged = false;
  for (const sym of ['XAUUSD', 'AU9999', 'USDCNY']) {
    const changed = initial[sym].color !== afterUpdate[sym].color ||
                    initial[sym].font  !== afterUpdate[sym].font;
    if (changed) { anyChanged = true; }
  }
  console.log(`  至少一卡变化: ${anyChanged ? '✓（随机性正常）' : '⚠ 需多次验证'}`);

  // ── Step 5: 切换 XAUUSD 数据源 ────────────────────────────────────────────
  console.log('\nStep 5: 切换 XAUUSD 数据源...');
  const beforeSwitch = await getCardState('XAUUSD');
  await page.selectOption('#src-xau', 'binance');
  await page.waitForTimeout(1500);
  const afterSwitch = await getCardState('XAUUSD');
  const xauChanged = beforeSwitch.color !== afterSwitch.color ||
                     beforeSwitch.font  !== afterSwitch.font;
  console.log(`  切换前: ${beforeSwitch.color}`);
  console.log(`  切换后: ${afterSwitch.color}`);
  console.log(`  XAUUSD 变化: ${xauChanged ? '✓' : '⚠（可能随机同色）'}`);

  // 检查 AU9999/USDCNY 未被误改
  const othersStable = (await Promise.all(['AU9999', 'USDCNY'].map(async (sym) => {
    const curr = await getCardState(sym);
    return curr.color === afterUpdate[sym].color && curr.font === afterUpdate[sym].font;
  }))).every(Boolean);
  console.log(`  AU9999/USDCNY 未被影响: ${othersStable ? '✓' : '⚠'}`);

  // ── Step 6: 最终唯一性 ─────────────────────────────────────────────────────
  console.log('\nStep 6: 最终颜色唯一性...');
  const finalState = {};
  for (const sym of ['XAUUSD', 'AU9999', 'USDCNY']) {
    finalState[sym] = await getCardState(sym);
  }
  const finalUnique = new Set(Object.values(finalState).map((s) => s.color)).size;
  console.log(`  最终唯一颜色: ${finalUnique}/3 — ${finalUnique === 3 ? '✓' : '✗'}`);
  for (const sym of ['XAUUSD', 'AU9999', 'USDCNY']) {
    console.log(`    ${sym}: ${finalState[sym].color}`);
  }

  // ── Step 7: 控制台错误 ─────────────────────────────────────────────────────
  console.log('\nStep 7: 控制台错误检查...');
  if (errors.length === 0) {
    console.log('  ✓ 无错误\n');
  } else {
    console.log(`  ✗ ${errors.length} 个错误:`);
    errors.forEach((e) => console.log(`    - ${e}`));
  }

  // ── 总结 ──────────────────────────────────────────────────────────────────
  console.log('=== 验证结果 ===');
  const allPass =
    uniqueColors === 3 &&
    uniqueFonts  === 3 &&
    finalUnique  === 3 &&
    errors.length === 0;
  console.log(allPass ? '✅ 全部通过 — 共享池随机化功能正常' : '⚠ 部分问题，见上文');

  await browser.close();
  process.exit(allPass ? 0 : 1);
})();
