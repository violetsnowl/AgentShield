import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';

let raw = ''; for await (const chunk of process.stdin) raw += chunk;
const config = JSON.parse(raw); raw = '';
const checks = [], errors = [], responses = [];
const check = (condition, label) => { assert.ok(condition, label); checks.push(label); };
let browser;
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/observer/api/')) responses.push(response);
  });
  async function openEvidence() {
    const fold = page.locator('details.evidence-fold');
    await fold.waitFor({ state: 'attached', timeout: 20000 });
    if (!(await fold.evaluate(node => node.open))) await fold.locator('summary').first().click();
  }
  await page.goto(config.origin + '/#pair=' + config.grant);
  await openEvidence();
  await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor({ timeout: 20000 });
  check((await page.locator('#run').inputValue()) === config.sessionId, 'generated session selected exactly');
  check((await page.locator('main').innerText()).includes(config.caseId), 'stable generated case identity visible');
  const labText = await page.locator('main').innerText();
  check(labText.includes('3 / 2 / 1'), 'opening history plus current refund reflected in item quantities');
  check(labText.includes('开发数据 · 待审'), 'generated candidate remains visibly development-only pending review');
  await page.screenshot({ path: path.join(config.output, 'bcp2-schema-v2-lab.png'), fullPage: true });
  await openEvidence();
  await page.getByTestId('committed-total').waitFor();
  const shown = await page.getByTestId('committed-total').innerText();
  const expected = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(config.currentRefundCents / 100);
  check(shown === expected, 'committed total contains current episode refund only');
  check((await page.locator('main').innerText()).includes('原键重放不重复计钱'), 'idempotent money semantics visible');
  await page.screenshot({ path: path.join(config.output, 'bcp2-schema-v2-evidence.png'), fullPage: true });
  await Promise.all(responses.map(async response => {
    const text = await response.text().catch(() => '');
    for (const secret of config.forbidden) check(!text.includes(secret), 'no B secret in observer response');
    check(!text.includes('"session_token"'), 'no session token in observer response');
  }));
  check(errors.length === 0, 'no page errors');
  console.log(JSON.stringify({ browser_qa: 'pass', checks: checks.length, screenshots: 2, browser: await browser.version() }));
} finally {
  if (browser) await browser.close();
}
