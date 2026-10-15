import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

let raw = ''; for await (const chunk of process.stdin) raw += chunk;
const config = JSON.parse(raw); raw = '';
const require = createRequire(import.meta.url);
const { chromium } = config.playwrightModule ? require(config.playwrightModule) : require('playwright-core');
const checks = [], consoleErrors = [], requests = [], responseChecks = [];
let browser;
function check(condition, label) { assert.ok(condition, label); checks.push(label); }
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.on('pageerror', error => consoleErrors.push(error.message));
  page.on('request', request => requests.push({ url: request.url(), method: request.method(), headers: request.headers(), body: request.postData() }));
  page.on('response', response => {
    if (response.url().includes('/observer/api/')) {
      responseChecks.push((async () => {
        let content;
        try { content = await response.text(); } catch { return; } // Aborted reads are checked by the UI-state tests.
        for (const secret of config.forbidden) check(!content.includes(secret), 'no B secret in browser API response');
        check(!content.includes('"session_token"'), 'no run credential in browser API response');
        if (response.status() === 201 && response.url().endsWith('/observer/api/sessions')
            && (response.request().postData() ?? '').includes('dev-refund-v1'))
          await fs.writeFile(path.join(config.output, 'created-session-observer.json'), content);
      })());
    }
  });
  async function openEvidence() {
    const fold = page.locator('details.evidence-fold');
    await fold.waitFor({ state: 'attached', timeout: 20000 });
    if (!(await fold.evaluate(node => node.open))) await fold.locator('summary').first().click();
  }
  await page.goto(`${config.origin}/#pair=${config.grant}`);
  await openEvidence();
  await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor({ timeout: 20000 });
  check(!page.url().includes(config.grant), 'one-use observer grant removed from URL');
  const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, cookie: document.cookie }));
  check(storage.local === 0 && storage.session === 0 && storage.cookie === '', 'no JS-readable credentials or browser storage');
  const cookies = await context.cookies();
  check(cookies.length === 1 && cookies[0].httpOnly && cookies[0].sameSite === 'Strict', 'only scoped HttpOnly observer cookie');
  check(await page.getByRole('button', { name: '启动 Agent', exact: true }).isDisabled(), 'real Agent control disabled');
  check((await page.locator('#run').inputValue()) === config.sessions[0], 'v1 exact session selected');
  check((await page.locator('main').innerText()).includes('¥3.33'), 'v1 actual 333-cent refund visible');
  async function layout(name) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}: no page horizontal overflow`);
    const money = await page.locator('td.money').evaluateAll(nodes => nodes.map(node => ({ align: getComputedStyle(node).textAlign, overflow: node.scrollWidth > node.clientWidth + 1 })));
    check(money.every(row => row.align === 'right' && !row.overflow), `${name}: table money right aligned without clipping`);
    const ids = await page.locator('code.id').evaluateAll(nodes => nodes.filter(node => node.clientWidth > 0).map(node => node.scrollWidth <= node.clientWidth + 1));
    check(ids.every(Boolean), `${name}: visible IDs wrap within bounds`);
    await page.screenshot({ path: path.join(config.output, `${name}.png`), fullPage: true });
  }
  await layout('core-lab-v1-desktop');
  await openEvidence();
  await openEvidence();
  await page.getByRole('heading', { name: '资金账本', exact: true }).waitFor();
  check((await page.getByTestId('committed-total').innerText()) === '¥3.33', 'committed total from actual refunds is 333 cents');
  await page.getByRole('button', { name: '加载后续事件', exact: true }).click();
  await page.locator('tr[data-seq="8"]').waitFor();
  const sequences = await page.locator('tr[data-seq]').evaluateAll(nodes => nodes.map(node => Number(node.getAttribute('data-seq'))));
  check(JSON.stringify(sequences) === JSON.stringify([1,2,3,4,5,6,7,8]), 'real event pagination preserves seq order');
  check((await page.locator('tr[data-seq="5"]').innerText()).includes('¥0.00'), 'replayed refund adds zero money');
  await page.getByRole('button', { name: '关联交易', exact: true }).first().click();
  await openEvidence();
  await page.getByRole('heading', { name: '交易追溯', exact: true }).waitFor();
  await layout('core-ledger-v1-desktop');
  if (config.phase === 'final') {
    const downloadPromise = page.waitForEvent('download');
    await page.locator('details.more-menu > summary').click();
    await page.getByRole('button', { name: '保存证据回放', exact: true }).click();
    const download = await downloadPromise;
    const saved = path.join(config.output, 'saved-v1-replay.json');
    await download.saveAs(saved);
    const recorded = JSON.parse(await fs.readFile(saved, 'utf8'));
    check(recorded.final_snapshot.session.session_id === config.sessions[0], 'saved replay identifies exact v1 run');
    check(recorded.refunds.length === 1 && recorded.refunds[0].amount_cents === 333, 'saved replay preserves one 333-cent transaction');
    async function selectRun(sid) {
      await Promise.all([page.waitForResponse(response => response.url().endsWith(`/sessions/${sid}/evidence`)), page.selectOption('#run', sid)]);
      await openEvidence();
      await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
      await page.getByRole('button', { name: '刷新本次运行', exact: true }).waitFor();
    }
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await selectRun(config.sessions[1]);
    check(await page.locator('.orders .order').count() === 1 && await page.locator('.message').count() === 2, 'v2 real structure: one order and two messages');
    check((await page.locator('.message').first().innerText()).includes('无结构化确认'), 'v2 unconfirmed message is explicit');
    await layout('lab-v2-desktop');
    await openEvidence();
    check(await page.getByTestId('committed-total').innerText() === '¥2.50', 'v2 exact run has 250-cent refund without v1 funds');
    await layout('ledger-v2-desktop');
    const noMatchText = await page.locator('.result-cards').innerText();
    check(noMatchText.includes('暂无核验结果') && noMatchText.includes('暂无理算结果'), 'seeded session without delivered counterpart shows no foreign C/A numbers');
    check(!(await page.locator('.integration-panel').count()), 'no candidate panel is shown for runs without a delivered counterpart');
    await layout('risk-candidate-desktop');
    await page.getByRole('button', { name: /保险方案/ }).click();
    await page.getByText('AgentShield 操作差错基础保障').waitFor();
    const planGrid = await page.locator('.plan-grid').innerText();
    check(planGrid.includes('待定') && planGrid.includes('操作差错增强保障') && !planGrid.includes('¥'), 'plans show pending values instead of invented premiums');
    check((await page.locator('main').innerText()).includes('非商业报价') && (await page.locator('main').innerText()).includes('commercial_quote=false'), 'plans remain explicitly non-commercial');
    await layout('cost-candidate-desktop');
    const deliveredCatalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const mockRuns = deliveredCatalog.runs.filter(run => run.execution_source === 'mock_agent');
    check(mockRuns.length >= 4, 'Mock delivery catalog contains complete runs');
    const selectedMock = mockRuns[0];
    const detailResponse = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${selectedMock.run_id}`));
    await page.selectOption('#run', selectedMock.session_id);
    const delivered = await (await detailResponse).json();
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await page.locator('.integration-panel').waitFor();
    const panelText = await page.locator('.integration-panel').innerText();
    check(panelText.includes('C L0 候选') && panelText.includes('needs_review'), 'C candidate result is visible and remains needs_review');
    check(panelText.includes('未知 / null') && panelText.includes('不直接等同于额外净损失'), 'unknown loss is not filled from refund money');
    check(panelText.includes('A0 研究候选') && panelText.includes('待审核 / null'), 'A0 claim is visible without invented payout');
    check(panelText.includes('illustrative') && panelText.includes('非本次运行'), 'engineering quote is separated from selected Agent run');
    check(await page.getByRole('button', { name: '加载关联业务证据', exact: true }).isEnabled(), 'C result can trace to its exact B evidence');
    check(await page.getByRole('button', { name: '重新理算', exact: true }).isDisabled(), 'browser does not recalculate insurance');
    await page.getByRole('button', { name: '加载关联业务证据', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'A/C 交付证据只读视图' }).waitFor();
    await page.locator('.run-identity summary').click();
    check((await page.locator('.identity-fields').innerText()).includes(delivered.summary.session_id), 'A/C result opens the exact linked B session');
    check(await page.getByTestId('committed-total').innerText() === new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(delivered.summary.total_committed_cents / 100), 'linked evidence money matches LossResult summary');
    await layout('delivered-mock-evidence-desktop');
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await layout('lab-v2-mobile');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.selectOption('#fixture', 'dev-refund-v1');
    await page.getByRole('button', { name: '创建业务会话', exact: true }).click();
    await page.getByRole('button', { name: '创建业务会话', exact: true }).waitFor();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.waitForFunction(ids => !ids.includes(document.querySelector('#run').value), config.sessions);
    const newSid = await page.locator('#run').inputValue();
    check(newSid !== config.sessions[0] && newSid !== config.sessions[1], 'new same-case session is a separate run');
    check((await page.locator('.hash code').innerText()) === recorded.case_context.business_initial_hash, 'same case keeps canonical initial hash');
    check(!(await page.locator('.orders').innerText()).includes(recorded.final_snapshot.orders[0].order_id), 'same case has disjoint runtime objects');
    await openEvidence();
    await page.getByText('尚无执行事件', { exact: true }).waitFor();
    check(await page.getByTestId('committed-total').innerText() === '¥0.00', 'new run has no inherited refunds');
    await layout('empty-run-desktop');
    // Controlled transport-state injection is QA only; never included in the product.
    const sessionsRoute = '**/observer/api/sessions';
    await page.route(sessionsRoute, route => route.fulfill({ status: 200, contentType: 'application/json', body: '{"sessions":[],"next_offset":null}' }));
    await page.reload();
    await page.getByText('还没有开发会话', { exact: true }).waitFor();
    await layout('empty-list-test-desktop');
    await page.unroute(sessionsRoute); await page.reload();
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    if ((await page.locator('#run').inputValue()) !== config.sessions[0]) await selectRun(config.sessions[0]);
    await page.getByText('查看原始政策文案 · dev-policy-v1', { exact: true }).click();
    check((await page.locator('.policy').innerText()).includes('本批人工工单工具尚未接入'), 'v1 historical policy preserved literally');
    check((await page.locator('.policy').innerText()).includes('待 A/C/D'), 'v1 historical inconsistency flagged pending review');

    // N01/N16: 三页切换保持运行；顶部去冗余结构检查。
    for (const areaName of [/风险评估/, /保险方案/, /Agent 测试/]) await page.getByRole('button', { name: areaName }).click();
    check(await page.locator('#run').inputValue() === config.sessions[0], 'N01: switching all three pages keeps the selected run');
    check(await page.locator('.execution-bar').count() === 0, 'N16: former standalone execution bar removed');
    check(await page.locator('.identity-extra').count() === 1, 'N16: source labels and actions consolidated into the identity strip');

    // N03: URL 状态与刷新恢复。
    await page.getByRole('button', { name: /风险评估/ }).click();
    await page.locator('.risk-overview').waitFor();
    check(page.url().includes('area=risk'), 'N03: area recorded in URL hash');
    const riskCopy = await page.locator('.risk-overview').innerText();
    check(riskCopy.includes('任务升级') && riskCopy.includes('task_outcome=escalated') && !riskCopy.includes('人工升级'), 'T1: needs_review is not tallied as task escalation');
    check(riskCopy.includes('核验覆盖') && riskCopy.includes('待核验（needs_review）') && riskCopy.includes('待核验 ≠ 任务升级'), 'T1: pending verification keeps its own coverage dimension');
    check(riskCopy.includes('1 / 15') && riskCopy.includes('暂不足以估计整体风险') && riskCopy.includes('已核验样本净损失') && riskCopy.includes('¥0.00'), 'T2: verified sample loss carries the coverage caveat');
    check(riskCopy.includes('开发运行来源') && riskCopy.includes('真实模型开发运行') && riskCopy.includes('Mock 开发运行') && !riskCopy.includes('vs Mock'), 'T3: run sources labeled without performance comparison');
    check(riskCopy.includes('人工工单') && riskCopy.includes('human_reviews'), 'T1: human review tickets reported as a separate dimension');
    await page.reload();
    await page.locator('.risk-overview').waitFor();
    check((await page.locator('h1').innerText()).includes('风险'), 'N03: reload restores the risk area');
    await page.waitForFunction(sid => document.querySelector('#run').value === sid, config.sessions[0]);
    check(true, 'N03: reload restores the selected run');
    // N02: 切换运行保持当前区；无交付结果的运行不残留旧结果。
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith(`/sessions/${config.sessions[1]}/evidence`)),
      page.selectOption('#run', config.sessions[1]),
    ]);
    check((await page.locator('h1').innerText()).includes('风险'), 'N02: switching run stays in the current area');
    check(page.url().includes('run=' + config.sessions[1]), 'N03: run switch recorded in URL');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith(`/sessions/${newSid}/evidence`)),
      page.selectOption('#run', newSid),
    ]);
    check((await page.locator('h1').innerText()).includes('风险'), 'N02: switching to another run keeps the risk area');
    check(page.url().includes('run=' + newSid), 'N03: URL tracks the second run');
    // N04: 从交付运行跳到证据后，可用“返回上一位置”回到原区域。
    const n04Catalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const n04DeliveredOnly = n04Catalog.runs.find(run => !config.sessions.includes(run.session_id)) ?? n04Catalog.runs[0];
    const n04Response = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${n04DeliveredOnly.run_id}`));
    await page.selectOption('#run', n04DeliveredOnly.session_id);
    await n04Response;
    await page.locator('h1', { hasText: 'Agent 测试' }).waitFor();
    check(await page.locator('details.evidence-fold').evaluate(node => node.open) === true, 'N04: 交付运行选中后自动展开详细执行证据');
    await page.getByRole('button', { name: /返回上一位置/ }).click();
    await page.locator('h1', { hasText: '风险' }).waitFor();
    check(true, 'N04: 返回上一位置回到原先的风险页');
    // N03: 深链接直接恢复区+运行；前进/后退恢复区域。
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=insurance&run=${config.sessions[1]}`);
    await page.getByText('AgentShield 操作差错基础保障').waitFor();
    check((await page.locator('h1').innerText()).includes('保险'), 'N03: deep link opens the requested area');
    await page.waitForFunction(sid => document.querySelector('#run').value === sid, config.sessions[1]);
    check(true, 'N03: deep link restores the requested run');
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await page.locator('h1', { hasText: 'Agent 测试' }).waitFor();
    await page.goBack();
    await page.locator('h1', { hasText: '保险' }).waitFor();
    check(true, 'N03: browser back returns to the previous area');
    await page.goForward();
    await page.locator('h1', { hasText: 'Agent 测试' }).waitFor();
    check(true, 'N03: browser forward returns to the later area');
    // N08: schema v2 期初历史退款分栏。
    const previousSid = await page.locator('#run').inputValue();
    await page.selectOption('#fixture', 'bcp2-l1-whole-low-04');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/observer/api/sessions') && response.request().method() === 'POST'),
      page.getByRole('button', { name: '创建业务会话', exact: true }).click(),
    ]);
    await page.waitForFunction(prev => document.querySelector('#run').value !== prev, previousSid);
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    const bcpSid = await page.locator('#run').inputValue();
    const bcpEvidence = await page.evaluate(async sid => (await fetch(`/observer/api/sessions/${sid}/evidence`, { headers: { 'X-Workbench-Request': '1' } })).json(), bcpSid);
    const openingCents = bcpEvidence.initial_snapshot.orders.reduce((sum, order) => sum + order.refunded_cents, 0);
    check(openingCents > 0, 'N08: fixture v2 run carries real opening history');
    const uiMoney = cents => `¥${Math.floor(Math.abs(cents) / 100).toLocaleString('zh-CN')}.${String(Math.abs(cents) % 100).padStart(2, '0')}`;
    check((await page.locator('.orders').innerText()).includes('期初历史'), 'N08: opening history labeled in the business zone');
    check((await page.locator('.orders').innerText()).includes(uiMoney(openingCents)), 'N08: opening amount shown in the business zone');
    await openEvidence();
    const currentTotal = bcpEvidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0);
    check((await page.getByTestId('committed-total').innerText()) === uiMoney(currentTotal), 'N08: committed total keeps current-episode refunds only');
    check((await page.locator('.ledger-summary').innerText()).includes('另有期初历史退款'), 'N08: evidence zone annotates the opening source');
    await layout('n08-opening-history-desktop');
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();

    const evidenceRoute = `**/observer/api/sessions/${config.sessions[1]}/evidence`;
    let release;
    let gate = new Promise(resolve => { release = resolve; });
    await page.route(evidenceRoute, async route => { await gate; await route.continue().catch(() => {}); });
    await page.selectOption('#run', config.sessions[1]);
    await page.getByRole('status').filter({ hasText: '正在读取本次运行' }).waitFor();
    check(await page.locator('.orders').count() === 0, 'loading hides previous run facts');
    await layout('loading-test-desktop');
    release(); await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    await page.unroute(evidenceRoute);

    await page.route(evidenceRoute, route => route.fulfill({ status: 502, contentType: 'application/json', body: '{"code":"B_UNAVAILABLE"}' }));
    await page.getByRole('button', { name: '刷新本次运行', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '暂时无法读取 B 服务' }).waitFor();
    check(await page.locator('.orders').count() === 0, 'error state does not show stale orders');
    await layout('error-test-desktop');
    await page.unroute(evidenceRoute);
    await page.getByRole('button', { name: '重试读取', exact: true }).click();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();

    gate = new Promise(resolve => { release = resolve; });
    await page.route(evidenceRoute, async route => { await gate; await route.abort().catch(() => {}); });
    await page.getByRole('button', { name: '刷新本次运行', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '请求超过 8 秒' }).waitFor({ timeout: 12000 });
    await layout('timeout-test-desktop');
    check(true, 'actual eight-second browser timeout handled');
    release(); await page.unroute(evidenceRoute);
    await page.getByRole('button', { name: '重试读取', exact: true }).click();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();

    // A delayed response for v1 must not overwrite a newer v2 selection.
    const delayed = `**/observer/api/sessions/${config.sessions[0]}/evidence`;
    gate = new Promise(resolve => { release = resolve; });
    await page.route(delayed, async route => { await gate; await route.continue().catch(() => {}); });
    await page.selectOption('#run', config.sessions[0]);
    await page.getByRole('status').filter({ hasText: '正在读取本次运行' }).waitFor();
    await selectRun(config.sessions[1]);
    release(); await page.unroute(delayed);
    check((await page.locator('#run').inputValue()) === config.sessions[1] && await page.locator('.orders .order').count() === 1, 'late previous-session response cannot replace current run');

    await context.setOffline(true);
    const beforeOffline = requests.length;
    await page.locator('input[type=file]').setInputFiles(saved);
    await page.getByText('离线只读回放', { exact: true }).waitFor();
    check(await page.getByTestId('committed-total').innerText() === '¥3.33', 'saved schema3 replay works with network disabled');
    for (const area of [/风险评估/, /保险方案/, /Agent 测试/]) await page.getByRole('button', { name: area }).click();
    check(requests.length === beforeOffline, 'offline file import and three-page navigation make zero network requests');
    check(await page.getByRole('button', { name: '创建业务会话', exact: true }).count() === 0, 'offline replay exposes no create or transaction action');
    await layout('offline-schema3-desktop');
    for (const [schemaVersion, filename] of [[1, 'artifacts/b_bootstrap/http_smoke/evidence_sample.json'], [2, 'artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json']]) {
      await page.locator('input[type=file]').setInputFiles(path.join(config.root, filename));
      await page.getByRole('button', { name: /Agent 测试/ }).click();
      await page.getByText('旧证据未记录案例上下文', { exact: true }).waitFor();
      check((await page.locator('.content-toolbar').innerText()).includes(`schema ${schemaVersion}`), `legacy schema ${schemaVersion} shown without upgrading historical facts`);
      check(await page.locator('.hash').count() === 0, `legacy schema ${schemaVersion} has no invented hash`);
      await layout(`offline-schema${schemaVersion}-desktop`);
    }
    await page.locator('input[type=file]').setInputFiles({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{"schema_version":4}') });
    await page.getByRole('alert').filter({ hasText: '证据格式不符合' }).waitFor();
    check(true, 'invalid imported evidence produces actionable error');
    await context.setOffline(false);
    // IA3 护栏（IA v3）：默认折叠 / 出口牌三站 / legacy 深链接 / 交付运行全链路绑定。
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByTestId('committed-total').waitFor();
    await page.reload();
    await page.getByTestId('committed-total').waitFor();
    const foldDefault = page.locator('details.evidence-fold');
    check(await foldDefault.count() === 1 && !(await foldDefault.evaluate(node => node.open)), 'IA3-03: 详细执行证据默认折叠');
    const identityFold = page.locator('details.run-identity');
    check(await identityFold.count() === 1 && !(await identityFold.evaluate(node => node.open)), 'IA3-03: 运行详情默认折叠');
    check(!(await page.locator('main').innerText()).includes('session-'), 'IA3-03: 默认视图不含长运行 ID');
    check(await page.locator('main pre:visible').count() === 0, 'IA3-03: 默认视图不含原始 JSON');
    await page.getByRole('link', { name: /前往下一站/ }).click();
    await page.locator('h1', { hasText: '风险评估' }).waitFor();
    check(page.url().includes('area=risk'), 'IA3-01: 出口牌推进到风险评估页');
    await page.getByRole('link', { name: /回看/ }).click();
    await page.locator('h1', { hasText: 'Agent 测试' }).waitFor();
    await page.getByRole('link', { name: /前往下一站/ }).click();
    await page.locator('h1', { hasText: '风险评估' }).waitFor();
    await page.getByRole('link', { name: /前往下一站/ }).click();
    await page.locator('h1', { hasText: '保险方案' }).waitFor();
    await page.getByRole('link', { name: /走完了/ }).click();
    await page.locator('h1', { hasText: 'Agent 测试' }).waitFor();
    check(true, 'IA3-01: 出口牌完成三站循环回到测试页');
    const liveSid = await page.locator('#run').inputValue();
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=evidence&run=${liveSid}`);
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    check(await page.locator('details.evidence-fold').evaluate(node => node.open) === true, 'IA3-02: legacy evidence 深链接自动展开详细执行证据');
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=cost&run=${liveSid}`);
    await page.locator('h1', { hasText: '保险方案' }).waitFor();
    check(true, 'IA3-02: legacy cost 深链接映射到保险方案页');
    const guardCatalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const guardTarget = guardCatalog.runs.find(run => run.session_id !== liveSid) ?? guardCatalog.runs[0];
    check(!!guardTarget, 'IA3-04: 交付目录可用');
    const guardResponse = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${guardTarget.run_id}`));
    await page.selectOption('#run', guardTarget.session_id);
    await guardResponse;
    await page.getByRole('button', { name: /Agent 测试/ }).click();
    await page.locator('.integration-panel').waitFor();
    await page.locator('.run-identity summary').click();
    const guardIdentity = await page.locator('.identity-fields').innerText();
    check(guardIdentity.includes(guardTarget.session_id), 'IA3-04: 运行身份与所选交付运行一致');
    check(!guardIdentity.includes(config.sessions[0]) || guardTarget.session_id === config.sessions[0], 'IA3-04: 不残留其他运行的核验/赔款');
    await page.locator('.run-identity summary').click();
    check((await page.getByTestId('committed-total').innerText()) === new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(guardTarget.total_committed_cents / 100), 'IA3-04: 结果卡金额指向同一运行');
    const unauthorized = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const locked = await unauthorized.newPage();
    await locked.goto(config.origin);
    await locked.getByRole('alert').filter({ hasText: '本机观察授权未建立或已过期' }).waitFor();
    check(!config.sessions.some(id => (requests.find(request => request.body?.includes(id))?.body ?? '').includes('session_token')), 'no B session secret in browser bodies');
    check(!(await locked.locator('body').innerText()).includes(config.sessions[0]), 'unapproved browser cannot read runs');
    await locked.screenshot({ path: path.join(config.output, 'unauthorized-desktop.png'), fullPage: true });
    await unauthorized.close();
  }
  for (const request of requests) {
    check(!request.headers.authorization, 'browser sends no B Authorization header');
    for (const secret of config.forbidden) check(!JSON.stringify(request).includes(secret), 'B credential absent from browser requests');
    check(!request.url.includes('/tools/'), 'browser never invokes a B tool');
  }
  check(consoleErrors.length === 0, 'no uncaught browser errors');
  check(requests.every(request => request.url.startsWith(config.origin)), 'no external browser requests');
  await Promise.all(responseChecks);
  for (const filename of await fs.readdir(path.join(config.root, 'frontend/dist/assets'))) {
    const built = await fs.readFile(path.join(config.root, 'frontend/dist/assets', filename), 'utf8');
    for (const secret of [...config.forbidden, config.grant]) check(!built.includes(secret), 'credential absent from built assets');
  }
  await fs.writeFile(path.join(config.output, 'browser_results.json'), JSON.stringify({ phase: config.phase, browser: await browser.version(), viewport: [1440,1000], checks, uncaught_errors: consoleErrors, external_requests: requests.filter(request => !request.url.startsWith(config.origin)).length }, null, 2));
  console.log(JSON.stringify({ browser_qa: 'pass', phase: config.phase, checks: checks.length, screenshots: (await fs.readdir(config.output)).filter(name => name.endsWith('.png')).length, browser: await browser.version() }));
} catch (error) {
  let message = String(error.stack ?? error) + '\nBrowser errors: ' + JSON.stringify(consoleErrors); for (const secret of [...config.forbidden, config.grant]) message = message.replaceAll(secret, '[REDACTED]');
  console.error(message); process.exitCode = 1;
} finally { if (browser) await browser.close(); }
