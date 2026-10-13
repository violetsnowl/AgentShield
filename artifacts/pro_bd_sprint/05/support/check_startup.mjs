import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
let raw = ''; for await (const chunk of process.stdin) raw += chunk;
const config = JSON.parse(raw); raw = '';
const require = createRequire(path.join(config.root, 'frontend/package.json'));
const { chromium } = require('playwright-core');
let browser, step = 'launch';
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, locale: 'zh-CN' });
  const page = await context.newPage();
  await page.goto(config.url);
  step = 'initial UI';
  await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor({ timeout: 20000 });
  assert.equal(new URL(page.url()).hash, '');
  assert.equal(await page.getByRole('button', { name: '启动 Agent', exact: true }).isDisabled(), true);
  step = 'catalog';
  while (await page.getByRole('button', { name: '加载更多运行', exact: true }).count()) {
    await page.getByRole('button', { name: '加载更多运行', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('#run option[value]:not([value=""])').length >= 2);
  }
  const options = await page.locator('#run option').evaluateAll(nodes => nodes.filter(n => n.value).map(n => ({ id: n.value, label: n.textContent })));
  const ids = options.map(n => n.id);
  assert.equal(ids.length, 2);
  if (config.previous) assert.deepEqual(ids, config.previous.sessions);
  for (const [caseId, amount] of [['dev-case-refund-v1', '¥3.33'], ['dev-case-refund-v2', '¥2.50']]) {
    step = `live template ${caseId}`;
    const selected = options.find(option => option.label.startsWith(caseId + ' '));
    assert(selected, `missing exact case ${caseId}`);
    await page.locator('#run').selectOption(selected.id);
    await page.waitForFunction(value => document.querySelector('main')?.textContent?.includes(value), amount);
    assert((await page.locator('main').innerText()).includes('scripted_test'));
  }
  await page.screenshot({ path: path.join(config.output, `fresh-live-${config.index}.png`), fullPage: true });
  await context.setOffline(true);
  const cases = [
    [3, 'contracts/fixture_v2_evidence_example.json'],
    [1, 'artifacts/b_bootstrap/http_smoke/evidence_sample.json'],
    [2, 'artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json'],
  ];
  for (const [schema, filename] of cases) {
    step = `offline schema ${schema}`;
    const buffer = await fs.readFile(path.join(config.root, filename));
    assert.equal(JSON.parse(buffer).schema_version, schema);
    await page.locator('input[type=file]').setInputFiles({ name: `schema-${schema}.json`, mimeType: 'application/json', buffer });
    await page.getByText('离线只读回放', { exact: true }).waitFor();
    await page.waitForFunction(s => document.querySelector('main')?.textContent?.includes(s), JSON.parse(buffer).final_snapshot.session.session_id);
    assert.equal(await page.getByRole('button', { name: '创建开发会话', exact: true }).count(), 0);
  }
  await page.screenshot({ path: path.join(config.output, `fresh-replay-${config.index}.png`), fullPage: true });
  assert.deepEqual(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie]), [0, 0, '']);
  process.stdout.write(JSON.stringify({ sessions: ids, two_templates: true, offline_loaded_page_schemas: [1, 2, 3], browser: browser.version(), index: config.index }));
} catch (error) {
  const grant = new URL(config.url).hash.slice('#pair='.length);
  const message = String(error.message).replaceAll(config.url, '[observer URL removed]').replaceAll(grant, '[observer grant removed]');
  process.stderr.write(JSON.stringify({ step, name: error.name, message })); process.exitCode = 1;
} finally { await browser?.close(); }
