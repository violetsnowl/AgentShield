import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';
let raw = ''; for await (const chunk of process.stdin) raw += chunk;
const config = JSON.parse(raw); raw = '';
const checks = [], observations = [], requests = [], errors = [];
let browser;
const check = (condition, label) => { assert.ok(condition, label); checks.push(label); };
const gate = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: 'zh-CN', reducedMotion: 'reduce' });
  const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => requests.push({ url: r.url(), method: r.method(), headers: r.headers(), body: r.postData() }));
  await page.goto(`${config.origin}/#pair=${config.grant}`);
  await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
  const v1 = JSON.parse(await fs.readFile(path.join(config.output, 'dev-refund-v1_evidence.json')));
  const v2 = JSON.parse(await fs.readFile(path.join(config.output, 'dev-refund-v2_evidence.json')));
  const importData = async (data, name = 'replay.json') => page.locator('input[type=file]').setInputFiles({ name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
  async function imported(data) {
    await page.getByText('离线只读回放', { exact: true }).waitFor();
    await page.getByTestId('committed-total').waitFor();
    await page.waitForFunction(sid => document.querySelector('.run-identity')?.textContent.includes(sid), data.final_snapshot.session.session_id);
  }
  async function snapshot(name) {
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(config.output, name + '.png'), fullPage: true });
    if (name === 'integration-v2-lab-1366') await page.screenshot({ path: path.join(config.output, 'integration-first-screen-1366.png') });
    const amounts = await page.locator('td.money').evaluateAll(nodes => nodes.filter(n => n.clientWidth > 0).map(n => ({ aligned: getComputedStyle(n).textAlign === 'right', fits: n.scrollWidth <= n.clientWidth + 1 })));
    check(amounts.every(n => n.aligned && n.fits), name + ': visible table money aligned and not clipped');
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), name + ': no horizontal page overflow');
  }
  // Real server creates a run; only delivery of its actual HTTP response is delayed.
  const release = gate(), responseReady = gate(); let created;
  const sessionsRoute = '**/observer/api/sessions';
  await page.route(sessionsRoute, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch(); created = await response.json(); responseReady.resolve();
    await release.promise; await route.fulfill({ response });
  });
  await page.getByRole('button', { name: '创建开发会话', exact: true }).click();
  await responseReady.promise;
  await importData(v2); await imported(v2); await snapshot('create-pending-imported-v2');
  release.resolve();
  await page.waitForResponse(r => r.url().endsWith('/observer/api/sessions') && r.request().method() === 'POST');
  await page.waitForTimeout(500);
  const stillReplay = await page.getByText('离线只读回放', { exact: true }).count() === 1;
  observations.push({ scenario: 'delayed-real-create-then-legal-v2-import', replay_preserved: stillReplay, created_session: created.session.session_id });
  check(stillReplay === !config.expectVulnerable, config.expectVulnerable ? 'F03-02 reproduced in real Edge: late create replaces replay' : 'F03-02 fixed: late create cannot replace replay');
  await snapshot('after-late-create'); await page.unroute(sessionsRoute);
  const mutations = [
    ['refund-total', e => { e.refunds[0].amount_cents = 99999; }],
    ['ledger-delta', e => { e.ledger[0].customer_delta_cents = 999; }],
    ['missing-ledger', e => { e.ledger = []; }],
    ['transaction-link', e => { e.ledger[0].transaction_id = 'transaction-unrelated'; }],
    ['snapshot-case', e => { e.final_snapshot.case.case_id = 'case-unrelated'; }],
    ['snapshot-tenant', e => { e.final_snapshot.session.tenant_id = 'tenant-unrelated'; }],
  ];
  for (const [name, mutate] of mutations) {
    await importData(v2); await imported(v2);
    const changed = structuredClone(v1); mutate(changed); await importData(changed, name + '.json');
    if (config.expectVulnerable) {
      await imported(changed); check(true, 'F03-01 reproduced: accepted ' + name);
    } else {
      await page.getByRole('alert').filter({ hasText: '不一致' }).waitFor();
      check((await page.locator('.run-identity').textContent()).includes(v2.final_snapshot.session.session_id), 'bad file cannot replace last valid replay: ' + name);
    }
    observations.push({ scenario: name, rejected: !config.expectVulnerable });
  }
  await snapshot(config.expectVulnerable ? 'contradictory-replay-accepted' : 'contradictory-replay-rejected');
  if (!config.expectVulnerable) {
    // Delay File.text for a specific file to exercise actual React handlers out of order.
    await page.evaluate(() => {
      const original = File.prototype.text;
      window.fileReleases = {};
      File.prototype.text = async function () {
        const content = await original.call(this);
        if (this.name.startsWith('slow-')) await new Promise(resolve => { window.fileReleases[this.name] = resolve; });
        return content;
      };
    });
    await importData(v1, 'slow-first.json');
    await page.waitForFunction(() => !!window.fileReleases['slow-first.json']);
    await importData(v2, 'second.json'); await imported(v2);
    await page.evaluate(() => window.fileReleases['slow-first.json']());
    await page.waitForTimeout(150);
    check((await page.locator('.run-identity').textContent()).includes(v2.final_snapshot.session.session_id), 'latest file selection wins despite reversed File.text completion');
    await importData(v1, 'slow-return.json');
    await page.waitForFunction(() => !!window.fileReleases['slow-return.json']);
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByRole('button', { name: /企业实验场/ }).click();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.evaluate(() => window.fileReleases['slow-return.json']()); await page.waitForTimeout(150);
    check(await page.getByText('离线只读回放', { exact: true }).count() === 0, 'return to service invalidates pending file reads');
    // Returning begins a catalog GET. A new import must win over that late catalog.
    await importData(v1); await imported(v1);
    const catalogGate = gate(), catalogStarted = gate();
    await page.route(sessionsRoute, async route => { const response = await route.fetch(); catalogStarted.resolve(); await catalogGate.promise; await route.fulfill({ response }); });
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click(); await catalogStarted.promise;
    await importData(v2); await imported(v2); catalogGate.resolve(); await page.waitForTimeout(200);
    check(await page.getByText('离线只读回放', { exact: true }).count() === 1, 'late directory cannot exit newer replay');
    await page.unroute(sessionsRoute);
    await snapshot('async-boundaries-fixed');
    await context.setOffline(true);
    for (const filename of ['artifacts/b_bootstrap/http_smoke/evidence_sample.json', 'artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json']) {
      const legacy = JSON.parse(await fs.readFile(path.join(config.root, filename)));
      await importData(legacy); await imported(legacy); check(true, 'valid legacy schema ' + legacy.schema_version + ' remains readable offline');
    }
    await context.setOffline(false);
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByRole('button', { name: /企业实验场/ }).click();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.locator('.filter-disclosure summary').click();
    await page.getByRole('textbox', { name: '筛选已加载运行', exact: true }).fill('dev-case-refund-v2');
    check(await page.locator('#run option').filter({ hasText: 'dev-case-refund-v1' }).count() === 0, 'case filter selects candidates without merging runs');
    await page.selectOption('#run', config.sessions[1]);
    await page.waitForResponse(r => r.url().endsWith(`/sessions/${config.sessions[1]}/evidence`));
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.locator('.filter-disclosure summary').click();
    await snapshot('integration-v2-lab-1366');
    await page.locator('.filter-disclosure summary').click();
    await page.getByRole('combobox', { name: '执行来源筛选', exact: true }).selectOption('observed_agent_execution');
    await page.getByRole('status').filter({ hasText: '没有匹配的已加载运行' }).waitFor();
    check(await page.locator('#run').inputValue() === config.sessions[1], 'source filter never silently changes selected session');
    await page.getByRole('combobox', { name: '执行来源筛选', exact: true }).selectOption('all');
    await page.getByRole('textbox', { name: '筛选已加载运行', exact: true }).fill('');
    await page.locator('.filter-disclosure summary').click();
    await page.locator('.run-identity summary').click();
    check((await page.locator('.run-identity').innerText()).includes(v2.final_snapshot.session.episode_id), 'exact episode visible in identity disclosure');
    await page.getByRole('button', { name: '复制运行身份', exact: true }).click();
    await page.getByRole('button', { name: '已复制身份', exact: true }).waitFor();
    await page.locator('.run-identity summary').click();
    await page.getByRole('button', { name: /执行证据 \/ 账本/ }).click();
    await page.getByRole('button', { name: '加载后续事件', exact: true }).click(); await page.locator('tr[data-seq="8"]').waitFor();
    await page.selectOption('#event-filter', 'replayed');
    check(await page.locator('tr[data-seq]').count() === 1 && (await page.locator('tr[data-seq]').innerText()).includes('¥0.00'), 'replay filter shows zero new funds');
    check(await page.getByTestId('committed-total').innerText() === '¥2.50', 'filter does not change transaction total');
    await page.getByRole('button', { name: '关联交易', exact: true }).click();
    await page.getByRole('button', { name: '查看关联订单', exact: true }).click();
    check((await page.locator('.order.highlighted').innerText()).includes(v2.refunds[0].order_id), 'event -> refund -> ledger -> exact runtime order');
    await snapshot('integration-order-trace-1366');
    await page.getByRole('button', { name: /执行证据 \/ 账本/ }).click();
    await page.selectOption('#event-filter', 'error');
    await page.getByText('已加载事件中没有匹配项', { exact: true }).waitFor();
    await snapshot('integration-no-matching-events-1366');
    // Use existing real historical B evidence for all four statuses (never fabricate a production score).
    const currentExample = JSON.parse(await fs.readFile(path.join(config.output, 'fault-injection-evidence.json')));
    await importData(currentExample); await imported(currentExample);
    await page.selectOption('#event-filter', 'error');
    check(currentExample.events.some(e => e.status === 'error'), 'QA-only real HTTP storage fault produced B error event');
    check((await page.locator('tr[data-seq]').innerText()).includes('未新增提交'), 'error event displayed as error without payment');
    await page.selectOption('#event-filter', 'all');
    await snapshot('integration-ledger-desktop');
    for (const area of ['风险 / 配置比较', '合同 / 情景成本']) {
      await page.getByRole('button', { name: new RegExp(area) }).click();
      const disclosure = page.locator('.integration-foot details');
      if (!(await disclosure.evaluate(node => node.open))) await disclosure.locator('summary').click();
      const panel = await page.locator('.integration-panel').innerText();
      check(['not_fitted','insufficient_evidence','partial','out_of_scope','commercial_quote=false'].every(value => panel.includes(value)), 'candidate panel contains required honest state explanations');
      check(panel.includes('counts_as_formal_run=false') || panel.includes('不计入 56 次'), 'delivered runs remain explicitly non-formal');
      if (area.startsWith('风险')) check(await page.getByRole('button', { name: '加载关联业务证据', exact: true }).isEnabled(), 'validated C result can open exact B evidence');
      else check(await page.getByRole('button', { name: '重新理算', exact: true }).isDisabled(), 'no browser-side insurance execution enabled');
      await snapshot(area.startsWith('风险') ? 'integration-risk-candidate' : 'integration-cost-candidate');
    }
    // Lost create response after a real commit: do not announce that creation failed.
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByRole('button', { name: /企业实验场/ }).click();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    let unknownCreated;
    await page.route(sessionsRoute, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      const response = await route.fetch(); unknownCreated = await response.json(); await route.abort();
    });
    await page.getByRole('button', { name: '创建开发会话', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '会话可能已经建立' }).waitFor();
    check(!!unknownCreated.session.session_id, 'create response loss occurs after real server creation');
    await snapshot('create-response-unknown-test');
    await page.unroute(sessionsRoute); await page.reload();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    check(await page.locator(`#run option[value="${unknownCreated.session.session_id}"]`).count() === 1, 'directory recovers actual session after lost create response without re-creating');
    await importData(v2); await imported(v2);
    await page.getByRole('button', { name: /企业实验场/ }).click();
    await page.setViewportSize({ width: 390, height: 844 }); await snapshot('integration-mobile');
    await page.screenshot({ path: path.join(config.output, 'integration-mobile-first-screen.png') });
  }
  check(errors.length === 0, 'no uncaught browser errors');
  for (const r of requests) {
    check(!r.headers.authorization && !r.url.includes('/tools/'), 'observer browser has no B auth or tool call');
    for (const secret of config.forbidden) assert.ok(!JSON.stringify(r).includes(secret));
  }
  const result = { mode: config.expectVulnerable ? 'baseline_reproduction_not_release_pass' : 'stage04_regression', browser: await browser.version(), observations, checks, errors };
  await fs.writeFile(path.join(config.output, 'stage04_browser_results.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ mode: result.mode, checks: checks.length, observations, errors }));
} catch (e) {
  let message = String(e.stack ?? e); for (const s of [...config.forbidden, config.grant]) message = message.replaceAll(s, '[REDACTED]');
  console.error(message); process.exitCode = 1;
} finally { if (browser) await browser.close(); }
