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
    await openDevTools();
    const fold = page.locator('details.evidence-fold');
    await fold.waitFor({ state: 'attached', timeout: 20000 });
    if (!(await fold.evaluate(node => node.open))) await fold.locator('summary').first().click();
  }
  async function openDevTools() {
    const fold = page.locator('details.dev-tools');
    if (await fold.count() && !(await fold.evaluate(node => node.open))) await fold.evaluate(node => { node.open = true; });
  }
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
  const navTo = async name => { await page.getByRole('link', { name, exact: true }).click(); };
  const activeNav = () => page.evaluate(() => document.querySelector('.nav-link.active')?.textContent ?? '');
  await page.goto(`${config.origin}/#pair=${config.grant}`);
  // 三个模式从空状态开始：不自动选择任何运行，第二、三页不预展示任何结果。
  await page.getByTestId('mode-sampling').waitFor({ timeout: 20000 });
  check(!page.url().includes(config.grant), 'one-use observer grant removed from URL');
  const storage = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, cookie: document.cookie }));
  check(storage.local === 0 && storage.session === 0 && storage.cookie === '', 'no JS-readable credentials or browser storage');
  const cookies = await context.cookies();
  check(cookies.length === 1 && cookies[0].httpOnly && cookies[0].sameSite === 'Strict', 'only scoped HttpOnly observer cookie');
  check(await page.getByTestId('mode-sampling').getAttribute('aria-selected') === 'true', '三个模式：默认选中抽取检验');
  check(await page.getByTestId('mode-scenario').count() === 1 && await page.getByTestId('mode-agent').count() === 1, '三个模式：选项卡齐备（抽取检验/研究情景/真实Agent）');
  const emptyText = await page.locator('main').innerText();
  check(emptyText.includes('尚未选择记录'), '未执行空状态：第一页不自动选择任何运行');
  check(!emptyText.includes('31,746') && !emptyText.includes('25,641'), '未执行空状态：第一页不出现研究情景数字');
  check(await page.locator('#run').isVisible(), '抽取检验：记录选择器可用');
  await navTo('02 风险结论');
  await page.locator('.risk-overview').waitFor();
  const samplingRiskEmpty = await page.locator('.risk-overview').innerText();
  check(samplingRiskEmpty.includes('尚未执行抽取检验') && !samplingRiskEmpty.includes('31,746'), '抽取检验未运行：第二页空状态且无研究假设数字');
  await navTo('03 保险方案');
  await page.locator('.plan-section').waitFor();
  const samplingPlanEmpty = await page.locator('.plan-section').innerText();
  check(samplingPlanEmpty.includes('尚未执行抽取检验') && !samplingPlanEmpty.includes('25,641') && !samplingPlanEmpty.includes('35,866'), '抽取检验未运行：第三页空状态且无预设保费');
  await navTo('01 测试案例');
  check(await page.locator('details.evidence-fold').count() === 0 && await page.locator('details.integration-panel').count() === 0, '未选择运行时：不展示技术折叠区');
  await layout('sampling-empty-desktop');
  // B-SCALE 一键运行：普通界面只开放免费规则基线，不暴露数据库路径或付费模型。
  check(await page.locator('[data-testid="new-test-toggle"]').count() === 1, 'P1: new-test entry is present on the case page');
  await page.locator('#agent-config').waitFor();
  const agentOptions = await page.locator('#agent-config option').evaluateAll(nodes => nodes.map(node => ({ value: node.value, label: node.textContent ?? '' })).filter(option => option.value));
  check(agentOptions.length === 1 && agentOptions[0].value === 'c-rule-baseline-v0.1', 'P1: only the free rule baseline is launchable');
  check(agentOptions[0].label.includes('规则基线'), 'P1: the launchable option is labelled as a rule baseline');
  check(!(await page.locator('#sample-run').isDisabled()), 'P1: sample-and-run is enabled after the controlled interface is connected');
  check((await page.locator('#sample-run-note').innerText()).includes('不会调用真实模型'), 'P1: the action states its no-model boundary');
  check(await page.locator('.new-test select#fixture').count() === 0, 'P1: no case picker inside the new-test flow');
  check(await page.locator('.result-list').count() === 1, 'P1: test record list is present');
  await page.waitForFunction(() => document.querySelector('.list-tab.active')?.textContent?.includes('历史测试'));
  check(true, 'P1: empty selection keeps the history view active');
  check(await page.locator('.result-list tbody tr').count() >= 5, 'P1: history view lists delivered runs');
  await page.getByRole('tab', { name: /本机测试记录/ }).click();
  await page.waitForFunction(() => document.querySelector('.list-tab.active')?.textContent?.includes('本机测试记录'));
  check(await page.locator('.result-list tbody tr').count() === config.sessions.length, 'P1: local tab lists exactly the local sessions');
  check(await page.locator(`.result-list tr[data-sid="${config.sessions[0]}"]`).count() === 1, 'P1: local records are addressable per exact session');
  await page.getByRole('tab', { name: /历史测试/ }).click();
  await page.waitForFunction(() => document.querySelector('.list-tab.active')?.textContent?.includes('历史测试'));
  await page.locator('[data-testid="new-test-toggle"]').click();
  await page.waitForFunction(() => document.querySelectorAll('#agent-config').length === 0);
  check(true, 'P1: new-test panel closes without side effects');
  async function selectRun(sid) {
    await Promise.all([page.waitForResponse(response => response.url().endsWith(`/sessions/${sid}/evidence`)), page.selectOption('#run', sid)]);
    await page.getByTestId('committed-total').waitFor();
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
  }
  // 显式选择 v1 本机会话（此后流程均以显式选择为准，不依赖自动落地）。
  await selectRun(config.sessions[0]);
  check((await page.locator('#run').inputValue()) === config.sessions[0], 'v1 exact session selected');
  check((await page.locator('main').innerText()).includes('¥3.33'), 'v1 actual 333-cent refund visible');
  check((await page.locator('.case-head h2').innerText()).includes('退款申请 · 多份确认'), 'default view shows the Chinese case name');
  check((await page.locator('main').innerText()).includes('开发运行'), 'development runs are labeled non-formal in the default view');
  check(!(await page.locator('.integration-panel').count()) && !(await page.locator('main').innerText()).includes('查看核验与理算详情'), '第一页底部技术折叠区已移除（C/A 技术面板不再展示）');
  await layout('core-lab-v1-desktop');
  await page.locator('.run-identity summary').click();
  check((await page.locator('.identity-fields').innerText()).includes(config.sessions[0]), 'v1 evidence shows the exact linked session identity');
  await page.getByRole('heading', { name: '资金账本', exact: true }).waitFor();
  check(await page.getByTestId('committed-total').innerText() === '¥3.33', 'committed total from actual refunds is 333 cents');
  await page.locator('tr[data-seq="8"]').waitFor();
  const sequences = await page.locator('tr[data-seq]').evaluateAll(nodes => nodes.map(node => Number(node.getAttribute('data-seq'))));
  check(JSON.stringify(sequences) === JSON.stringify([1,2,3,4,5,6,7,8]), 'all events render in real seq order');
  check((await page.locator('tr[data-seq="5"]').innerText()).includes('¥0.00'), 'replayed refund adds zero money');
  await page.getByRole('button', { name: '关联交易', exact: true }).first().click();
  await openEvidence();
  await page.getByRole('heading', { name: '交易追溯', exact: true }).waitFor();
  await layout('core-ledger-v1-desktop');
  if (config.phase === 'final') {
    const downloadPromise = page.waitForEvent('download');
    await openDevTools();
    await page.getByRole('button', { name: '保存证据回放', exact: true }).click();
    const download = await downloadPromise;
    const saved = path.join(config.output, 'saved-v1-replay.json');
    await download.saveAs(saved);
    const recorded = JSON.parse(await fs.readFile(saved, 'utf8'));
    check(recorded.final_snapshot.session.session_id === config.sessions[0], 'saved replay identifies exact v1 run');
    check(recorded.refunds.length === 1 && recorded.refunds[0].amount_cents === 333, 'saved replay preserves one 333-cent transaction');
    await navTo('01 测试案例');
    await selectRun(config.sessions[1]);
    check(await page.locator('.orders .order').count() === 1 && await page.locator('.message').count() === 2, 'v2 real structure: one order and two messages');
    check((await page.locator('.message').first().innerText()).includes('无结构化确认'), 'v2 unconfirmed message is explicit');
    await layout('lab-v2-desktop');
    check(await page.getByTestId('committed-total').innerText() === '¥2.50', 'v2 exact run has 250-cent refund without v1 funds');
    await layout('ledger-v2-desktop');
    const noMatchText = await page.locator('.run-result').innerText();
    check(noMatchText.includes('暂无核验结果') && noMatchText.includes('暂无理算结果'), 'seeded session without delivered counterpart shows no foreign C/A numbers');
    check(!(await page.locator('.integration-panel').count()) && !(await page.locator('main').innerText()).includes('查看核验与理算详情'), 'no technical C/A panel is shown for runs without a delivered counterpart');
    await layout('risk-candidate-desktop');
    // 研究情景模式：固定演示（不依赖运行），用于检查预设方案与合同生成。
    await navTo('01 测试案例');
    await page.getByTestId('mode-scenario').click();
    check(page.url().includes('mode=scenario'), '模式：研究情景写入 URL');
    check(await page.locator('.scenario-intro').count() === 1, '研究情景：第一页展示固定情景介绍（不依赖运行）');
    check(await page.locator('#run').count() === 0, '研究情景：右上角历史选择器隐藏');
    await navTo('03 保险方案');
    await page.locator('.plan-grid').waitFor();
    const planGrid = await page.locator('.plan-grid').innerText();
    check(planGrid.includes('¥25,641.00') && planGrid.includes('¥35,866.88'), '研究情景：Core/Plus 固定参考保费与金额不变');
    check((await page.locator('main').innerText()).includes('非经验商业报价') && (await page.locator('main').innerText()).includes('研究假设 · 非实际经验报价'), '研究情景：研究假设与非商业报价说明保留');
    await page.getByRole('button', { name: '生成Core模拟保险合同', exact: true }).click();
    check((await page.locator('.contract-document').innerText()).includes('SIM-bscale-enterprise-study-v0.1-CORE'), 'Core research contract is generated from the displayed scenario');
    check(await page.getByRole('button', { name: '打印 / 另存为PDF', exact: true }).count() === 1, 'generated contract exposes the browser print action');
    await page.getByRole('button', { name: '← 返回保险方案', exact: true }).click();
    await layout('cost-candidate-desktop');
    // 回到抽取检验继续交付运行检查。
    await navTo('01 测试案例');
    await page.getByTestId('mode-sampling').click();
    check(!page.url().includes('mode='), '模式：切回抽取检验后 URL 不带 mode');
    const deliveredCatalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const mockRuns = deliveredCatalog.runs.filter(run => run.execution_source === 'mock_agent');
    check(mockRuns.length >= 4, 'Mock delivery catalog contains complete runs');
    const selectedMock = mockRuns[0];
    const detailResponse = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${selectedMock.run_id}`));
    await page.selectOption('#run', selectedMock.session_id);
    const delivered = await (await detailResponse).json();
    await page.getByTestId('committed-total').waitFor();
    await navTo('01 测试案例');
    const resultText = await page.locator('.run-result').evaluate(node => node.textContent ?? '');
    check(resultText.includes('未知 / null') && resultText.includes('不直接等同于额外净损失'), 'C pending review shown as unknown, never filled from refund money');
    check(resultText.includes('待审核 / null'), 'A0 claim is visible without invented payout');
    check(!(await page.locator('main').innerText()).includes('illustrative'), 'engineering quote sample removed from the normal case view');
    check(await page.getByRole('button', { name: '重新理算', exact: true }).count() === 0, 'browser exposes no insurance recalculation control');
    await openEvidence();
    await page.locator('.run-identity summary').click();
    check((await page.locator('.identity-fields').innerText()).includes(delivered.summary.session_id), 'A/C result opens the exact linked B session');
    check(await page.getByTestId('committed-total').innerText() === new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(delivered.summary.total_committed_cents / 100), 'linked evidence money matches LossResult summary');
    await layout('delivered-mock-evidence-desktop');
    await page.selectOption('#run', config.sessions[0]);
    await page.getByTestId('committed-total').waitFor();
    await openDevTools();
    await page.selectOption('#fixture', 'dev-refund-v1');
    await page.getByRole('button', { name: '创建业务会话', exact: true }).click();
    await page.waitForFunction(ids => { const el = document.querySelector('#run'); return !!el && !ids.includes(el.value); }, config.sessions);
    const newSid = await page.locator('#run').inputValue();
    check(newSid !== config.sessions[0] && newSid !== config.sessions[1], 'new same-case session is a separate run');
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    check((await page.locator('.hash code').innerText()) === recorded.case_context.business_initial_hash, 'same case keeps canonical initial hash');
    check(!(await page.locator('.orders').innerText()).includes(recorded.final_snapshot.orders[0].order_id), 'same case has disjoint runtime objects');
    await page.getByText('尚无执行事件', { exact: true }).waitFor();
    check(await page.getByTestId('committed-total').innerText() === '¥0.00', 'new run has no inherited refunds');
    await layout('empty-run-desktop');
    // Controlled transport-state injection is QA only; never included in the product.
    const sessionsRoute = '**/observer/api/sessions';
    await page.route(sessionsRoute, route => route.fulfill({ status: 200, contentType: 'application/json', body: '{"sessions":[],"next_offset":null}' }));
    const runsRoute = '**/observer/api/integration-runs';
    await page.route(runsRoute, route => route.fulfill({ status: 200, contentType: 'application/json', body: '{"contract_version":"abcd-integration-0.1-candidate","runs":[]}' }));
    await page.reload();
    await page.getByText('尚未选择记录', { exact: true }).waitFor();
    await layout('empty-list-test-desktop');
    await page.unroute(sessionsRoute); await page.unroute(runsRoute); await page.reload();
    await page.getByTestId('mode-sampling').waitFor();
    await navTo('01 测试案例');
    // 从记录列表选择 v1（显式操作；不再有自动落地）。
    await page.getByRole('tab', { name: /本机测试记录/ }).click();
    await page.waitForFunction(() => document.querySelector('.list-tab.active')?.textContent?.includes('本机测试记录'));
    const listTarget = config.sessions[0];
    const rowResponse = page.waitForResponse(response => response.url().endsWith(`/sessions/${listTarget}/evidence`));
    await page.locator(`.result-list tr[data-sid="${listTarget}"] button`).click();
    await rowResponse;
    await page.getByTestId('committed-total').waitFor();
    check(await page.locator('#run').inputValue() === listTarget, 'P1: clicking a record row selects that exact run');
    check(((await page.locator(`.result-list tr[data-sid="${listTarget}"]`).getAttribute('class')) ?? '').includes('selected'), 'P1: the selected record row is highlighted');
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    check(await page.locator('#fixture').count() === 1 && await page.locator('details.dev-tools #fixture').count() === 1, 'P1: case picker exists only inside the dev-tools debug fold');
    await page.getByRole('tab', { name: /历史测试/ }).click();
    await page.waitForFunction(() => document.querySelector('.list-tab.active')?.textContent?.includes('历史测试'));
    await page.getByText('查看原始政策文案 · dev-policy-v1', { exact: true }).click();
    check((await page.locator('.policy').innerText()).includes('本批人工工单工具尚未接入'), 'v1 historical policy preserved literally');
    check((await page.locator('.policy').innerText()).includes('待 A/C/D'), 'v1 historical inconsistency flagged pending review');

    // N01/N16: 三页切换保持运行；顶部去冗余结构检查。
    for (const pageName of ['02 风险结论', '03 保险方案', '01 测试案例']) await navTo(pageName);
    check(await page.locator('#run').inputValue() === config.sessions[0], 'N01: switching all three pages keeps the selected run');
    check(await page.locator('.execution-bar').count() === 0, 'N16: former standalone execution bar removed');
    check(await page.locator('.identity-extra').count() === 1, 'N16: source labels consolidated into the run details');

    // N03: URL 状态与刷新恢复（此时为抽取检验、已选 v1 运行；第二页应保持空状态而不是展示任何预设数字）。
    await navTo('02 风险结论');
    await page.locator('.risk-overview').waitFor();
    check(page.url().includes('area=risk'), 'N03: area recorded in URL hash');
    const riskCopy = await page.locator('.risk-overview').evaluate(node => node.textContent ?? '');
    check(riskCopy.includes('尚未执行抽取检验') && !riskCopy.includes('31,746'), 'T2: 抽取检验未运行时不展示研究情景数字（已选记录不冒充批次统计）');
    await layout('risk-overview-desktop');
    await page.reload();
    await page.locator('.risk-overview').waitFor();
    check((await activeNav()).includes('02 风险结论'), 'N03: reload restores the risk area');
    await page.waitForFunction(sid => document.querySelector('#run')?.value === sid, config.sessions[0]);
    check(true, 'N03: reload restores the selected run');
    // N02: 切换运行保持当前区；无交付结果的运行不残留旧结果。
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith(`/sessions/${config.sessions[1]}/evidence`)),
      page.selectOption('#run', config.sessions[1]),
    ]);
    check((await activeNav()).includes('02 风险结论'), 'N02: switching run stays in the current area');
    check(page.url().includes('area=risk'), 'N02: run switch keeps the current area in URL');
    check(page.url().includes('run=' + config.sessions[1]), 'N03: run switch recorded in URL');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith(`/sessions/${newSid}/evidence`)),
      page.selectOption('#run', newSid),
    ]);
    check((await activeNav()).includes('02 风险结论'), 'N02: switching to another run keeps the risk area');
    check(page.url().includes('run=' + newSid), 'N03: URL tracks the second run');
    // N04: 交付运行可在测试页查看其证据（不再自动跳转、不再自动展开技术折叠区）。
    const n04Catalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const n04DeliveredOnly = n04Catalog.runs.find(run => run.execution_source === 'scripted_test' && !config.sessions.includes(run.session_id)) ?? n04Catalog.runs.find(run => run.execution_source === 'scripted_test');
    check(!!n04DeliveredOnly, 'N04: 规则基线交付运行可用');
    const n04Response = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${n04DeliveredOnly.run_id}`));
    await page.selectOption('#run', n04DeliveredOnly.session_id);
    await n04Response;
    check((await activeNav()).includes('02 风险结论'), 'N04: 选择交付运行不强制跳转（停留在当前页）');
    await navTo('01 测试案例');
    await page.getByTestId('committed-total').waitFor();
    await openEvidence();
    await page.locator('.run-identity summary').click();
    check((await page.locator('.identity-fields').innerText()).includes(n04DeliveredOnly.session_id), 'N04: 交付运行显示其准确身份与证据');
    // N03: 深链接直接恢复区+运行；前进/后退恢复区域。
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=insurance&run=${config.sessions[1]}`);
    await page.locator('.plan-section').waitFor();
    check((await activeNav()).includes('03 保险方案'), 'N03: deep link opens the requested area');
    await page.waitForFunction(sid => document.querySelector('#run')?.value === sid, config.sessions[1]);
    check(true, 'N03: deep link restores the requested run');
    await navTo('01 测试案例');
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('01 测试案例'));
    await page.goBack();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('03 保险方案'));
    check(true, 'N03: browser back returns to the previous area');
    await page.goForward();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('01 测试案例'));
    check(true, 'N03: browser forward returns to the later area');
    // N08: schema v2 期初历史退款分栏。
    const previousSid = await page.locator('#run').inputValue();
    await openDevTools();
    await page.selectOption('#fixture', 'bcp2-l1-whole-low-04');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/observer/api/sessions') && response.request().method() === 'POST'),
      page.getByRole('button', { name: '创建业务会话', exact: true }).click(),
    ]);
    await page.waitForFunction(prev => document.querySelector('#run')?.value !== prev, previousSid);
    await openEvidence();
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    const bcpSid = await page.locator('#run').inputValue();
    const bcpEvidence = await page.evaluate(async sid => (await fetch(`/observer/api/sessions/${sid}/evidence`, { headers: { 'X-Workbench-Request': '1' } })).json(), bcpSid);
    const openingCents = bcpEvidence.initial_snapshot.orders.reduce((sum, order) => sum + order.refunded_cents, 0);
    check(openingCents > 0, 'N08: fixture v2 run carries real opening history');
    const uiMoney = cents => `¥${Math.floor(Math.abs(cents) / 100).toLocaleString('zh-CN')}.${String(Math.abs(cents) % 100).padStart(2, '0')}`;
    check((await page.locator('.orders').innerText()).includes('期初历史'), 'N08: opening history labeled in the business zone');
    check((await page.locator('.orders').innerText()).includes(uiMoney(openingCents)), 'N08: opening amount shown in the business zone');
    const currentTotal = bcpEvidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0);
    check((await page.getByTestId('committed-total').innerText()) === uiMoney(currentTotal), 'N08: committed total keeps current-episode refunds only');
    check((await page.locator('.ledger-summary').innerText()).includes('另有期初历史退款'), 'N08: evidence zone annotates the opening source');
    await layout('n08-opening-history-desktop');

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
    await openDevTools();
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
    await openDevTools();
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

    // 稳定性：研究情景瞬时失败自动重试 + 显式错误态 + 手动重试恢复（不再永久“正在汇总”）。
    const scenarioRoute = '**/observer/api/research-scenario';
    let scenarioFailures = 3;
    await page.route(scenarioRoute, async route => {
      if (scenarioFailures > 0) { scenarioFailures -= 1; await route.fulfill({ status: 502, contentType: 'application/json', body: '{"code":"B_UNAVAILABLE"}' }); }
      else await route.continue();
    });
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=risk&mode=scenario`);
    await page.getByRole('button', { name: '重试读取研究情景', exact: true }).waitFor({ timeout: 20000 });
    check((await page.locator('main').innerText()).includes('研究情景未能读取'), '稳定性：研究情景连续失败后给出显式错误态而非永久转圈');
    await page.unroute(scenarioRoute);
    await page.getByRole('button', { name: '重试读取研究情景', exact: true }).click();
    await page.locator('.risk-overview').waitFor({ timeout: 20000 });
    const scenarioRiskCopy = await page.locator('.risk-overview').innerText();
    check(scenarioRiskCopy.includes('研究性风险测算') && scenarioRiskCopy.includes('¥31,746.00') && scenarioRiskCopy.includes('基于假设，非实际测得的损失'), '研究情景：第二页固定研究性风险测算（¥31,746 + 假设说明）');
    check(scenarioRiskCopy.includes('6,105') && scenarioRiskCopy.includes('33.73%'), '研究情景：任务量与四类业务权重可见');
    // 三个模式：全局同步、数据隔离、互不借用；切换不删除任何已有记录。
    await navTo('01 测试案例');
    check(await page.getByTestId('mode-scenario').getAttribute('aria-selected') === 'true', '模式：URL 恢复研究情景选中');
    check(await page.locator('.scenario-intro').count() === 1, '研究情景：第一页固定介绍（不要求选择历史记录）');
    check(await page.getByTestId('sample-run').count() === 0 && await page.getByTestId('real-run-one').count() === 0, '研究情景：不显示任何运行按钮');
    check(await page.locator('#run').count() === 0, '研究情景：右上角历史选择器隐藏');
    await page.getByTestId('mode-sampling').click();
    check(!page.url().includes('mode='), '模式：切回抽取检验后 URL 不带 mode');
    check(await page.getByTestId('sample-run').isEnabled(), '抽取检验：随机抽取按钮可用（免费规则基线）');
    await navTo('03 保险方案');
    const planIsolation = await page.locator('.plan-section').innerText();
    check(planIsolation.includes('尚未执行抽取检验') && !planIsolation.includes('25,641') && !planIsolation.includes('35,866'), '隔离：抽取检验未运行时第三页不含研究情景保费');
    await navTo('01 测试案例');
    await page.getByTestId('mode-agent').click();
    check(page.url().includes('mode=agent'), '模式：真实Agent 写入 URL');
    const realBudget = await page.getByTestId('real-run-budget').innerText();
    check(realBudget.includes('历史付费合计') && realBudget.includes('单次硬顶'), '真实Agent：预算区显示批准上限/硬顶/历史付费合计');
    check(await page.locator('#real-run-hundred').isDisabled(), '真实Agent：100 条保持扩展入口、不可直接运行');
    if (await page.getByTestId('real-run-one').isDisabled()) {
      check(await page.getByTestId('real-run-batch').isDisabled(), '真实Agent：运行按钮随授权状态一致禁用');
      const realNote = await page.getByTestId('real-run-note').innerText();
      check(realNote.includes('未授权') || realNote.includes('未配置'), '真实Agent：不可用原因逐条列明（未授权/未配置）');
    } else {
      check(await page.getByTestId('real-run-batch').isEnabled(), '真实Agent：已授权时小批量按钮可用');
      check(realBudget.includes('批准上限') && !realBudget.includes('未批准'), '真实Agent：已授权时预算区显示批准上限');
    }
    // 未选择批次：第二、三页保持空状态，无任何预设数字。
    await navTo('02 风险结论');
    await page.locator('.risk-overview').waitFor();
    const agentEmpty = await page.locator('.risk-overview').innerText();
    check(agentEmpty.includes('尚无真实Agent测试结果') && !agentEmpty.includes('31,746') && !agentEmpty.includes('数据不足'), '真实Agent：未运行/未选择时第二页为空且无预设数字');
    await navTo('03 保险方案');
    const agentPlanEmpty = await page.locator('.plan-section').innerText();
    check(agentPlanEmpty.includes('尚无真实Agent测试结果') && !agentPlanEmpty.includes('25,641'), '真实Agent：未运行/未选择时第三页为空且无预设保费');
    // 明确选择已有 5 条历史批次 → 第二页实际核验结果、第三页保险配置建议；不混入研究情景。
    await navTo('01 测试案例');
    const agentCatalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const observedRuns = agentCatalog.runs.filter(run => run.execution_source === 'observed_agent_execution');
    const byBatch = new Map();
    for (const run of observedRuns) byBatch.set(run.batch_id, (byBatch.get(run.batch_id) ?? 0) + 1);
    const fiveBatchId = [...byBatch.entries()].sort((a, b) => b[1] - a[1])[0][0];
    const fiveTarget = observedRuns.find(run => run.batch_id === fiveBatchId);
    check(byBatch.get(fiveBatchId) === 5, '真实Agent：目录中存在 5 条真实批次');
    const fiveDetail = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${fiveTarget.run_id}`));
    await page.selectOption('#run', fiveTarget.session_id);
    await fiveDetail;
    await navTo('02 风险结论');
    await page.waitForFunction(() => (document.querySelector('.risk-overview')?.innerText ?? '').includes('5 / 5'), { timeout: 30000 });
    const agentRisk = await page.locator('.risk-overview').innerText();
    const agentRiskRaw = await page.locator('.risk-overview').evaluate(node => node.textContent ?? '');
    check(agentRisk.includes('历史批次') && agentRisk.includes(fiveBatchId), '真实Agent：明确回看的历史批次被标注');
    check(agentRisk.includes('5 次') && agentRisk.includes('0.00%') && agentRisk.includes('¥0.00'), '真实Agent：第二页展示实际核验结果（5 条 / 0.00% / ¥0）');
    check(!agentRisk.includes('31,746'), '隔离：真实Agent 第二页不混入研究情景数字');
    check(agentRiskRaw.includes('任务升级与人工工单') && agentRiskRaw.includes('开发运行来源'), 'T1/T3：完整统计口径折叠内含来源与工单维度');
    await navTo('03 保险方案');
    await page.waitForFunction(() => (document.querySelector('[data-testid="insurance-advice"]')?.innerText ?? '').includes('当前测试未发现额外经济损失'), { timeout: 30000 });
    const adviceText = await page.getByTestId('insurance-advice').innerText();
    check(adviceText.includes('继续观察') && adviceText.includes('当前测试未发现额外经济损失'), '真实Agent：第三页动态保险配置建议（零损失→继续观察）');
    check(adviceText.includes('扩大测试样本') && adviceText.includes('Core 或 Plus 保障'), '真实Agent：建议卡引导扩大样本后再评估保障');
    const agentPlan = await page.locator('.plan-section').innerText();
    check(agentPlan.includes('数据不足') && !agentPlan.includes('25,641') && !agentPlan.includes('35,866'), '真实Agent：保险责任未认定时样本保费数据不足、不混入研究情景');
    await navTo('01 测试案例');
    // 切回抽取检验：记录仍在，选择器回到抽样池（切换不删除记录）。
    await page.getByTestId('mode-sampling').click();
    check(await page.locator('#run').count() === 1, '模式：切换后记录选择器仍在');
    check(await page.locator('#run optgroup').count() >= 1, '模式：切换不删除任何已有记录');

    await context.setOffline(true);
    const beforeOffline = requests.length;
    await page.locator('input[type=file]').setInputFiles(saved);
    await page.getByText('离线只读回放', { exact: true }).waitFor();
    check(await page.getByTestId('committed-total').innerText() === '¥3.33', 'saved schema3 replay works with network disabled');
    for (const pageName of ['02 风险结论', '03 保险方案', '01 测试案例']) await navTo(pageName);
    check(requests.length === beforeOffline, 'offline file import and three-page navigation make zero network requests');
    check(await page.locator('button:has-text("创建业务会话")').count() === 0, 'offline replay exposes no create or transaction action');
    await layout('offline-schema3-desktop');
    for (const [schemaVersion, filename] of [[1, 'artifacts/b_bootstrap/http_smoke/evidence_sample.json'], [2, 'artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json']]) {
      await page.locator('input[type=file]').setInputFiles(path.join(config.root, filename));
      await navTo('01 测试案例');
      await page.getByText('旧证据未记录案例上下文', { exact: true }).waitFor();
      await openEvidence();
      check((await page.locator('.content-toolbar').innerText()).includes(`schema ${schemaVersion}`), `legacy schema ${schemaVersion} shown without upgrading historical facts`);
      check(await page.locator('.hash').count() === 0, `legacy schema ${schemaVersion} has no invented hash`);
      await layout(`offline-schema${schemaVersion}-desktop`);
    }
    await page.locator('input[type=file]').setInputFiles({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{"schema_version":4}') });
    await page.getByRole('alert').filter({ hasText: '证据格式不符合' }).waitFor();
    check(true, 'invalid imported evidence produces actionable error');
    await context.setOffline(false);
    // IA3 护栏（IA v3 语义，新版界面）：默认折叠 / 分步导航 / legacy 深链接 / 交付运行全链路绑定。
    await page.getByRole('button', { name: '返回本机服务', exact: true }).click();
    await page.getByTestId('mode-sampling').waitFor();
    check((await page.locator('main').innerText()).includes('尚未选择记录'), '返回本机服务后回到空状态（不自动选择任何运行）');
    await page.reload();
    await page.getByTestId('mode-sampling').waitFor();
    check((await page.locator('main').innerText()).includes('尚未选择记录'), '刷新后仍为空状态（不自动落地历史记录）');
    const foldDev = page.locator('details.dev-tools');
    check(await foldDev.count() === 1 && !(await foldDev.evaluate(node => node.open)), 'IA3-03: 开发工具默认折叠');
    const foldSid = config.sessions[0];
    await Promise.all([page.waitForResponse(response => response.url().endsWith(`/sessions/${foldSid}/evidence`)), page.selectOption('#run', foldSid)]);
    await page.getByTestId('committed-total').waitFor();
    const foldDefault = page.locator('details.evidence-fold');
    check(await foldDefault.count() === 1 && !(await foldDefault.evaluate(node => node.open)), 'IA3-03: 详细执行证据默认折叠');
    const identityFold = page.locator('details.run-identity');
    check(await identityFold.count() === 1 && !(await identityFold.evaluate(node => node.open)), 'IA3-03: 运行详情默认折叠');
    check(!(await page.locator('main').innerText()).includes('session-'), 'IA3-03: 默认视图不含长运行 ID');
    check(await page.locator('main pre:visible').count() === 0, 'IA3-03: 默认视图不含原始 JSON');
    await page.getByRole('link', { name: /下一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('02 风险结论'));
    check(page.url().includes('area=risk'), 'IA3-01: 下一步推进到风险结论页');
    await page.getByRole('link', { name: /上一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('01 测试案例'));
    await page.getByRole('link', { name: /下一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('02 风险结论'));
    await page.getByRole('link', { name: /下一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('03 保险方案'));
    await page.getByRole('link', { name: /上一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('02 风险结论'));
    await page.getByRole('link', { name: /上一步：/ }).click();
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('01 测试案例'));
    check(true, 'IA3-01: 分步导航三步回环回到测试页');
    const liveSid = await page.locator('#run').inputValue();
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=evidence&run=${liveSid}`);
    await page.getByRole('heading', { name: '订单与商品', exact: true }).waitFor();
    check(await page.locator('details.evidence-fold').evaluate(node => node.open) === true, 'IA3-02: legacy evidence 深链接自动展开详细执行证据');
    await page.goto('about:blank');
    await page.goto(`${config.origin}/#area=cost&run=${liveSid}`);
    await page.waitForFunction(() => document.querySelector('.nav-link.active')?.textContent?.includes('03 保险方案'));
    check(true, 'IA3-02: legacy cost 深链接映射到保险方案页');
    const guardCatalog = await page.evaluate(async () => (await fetch('/observer/api/integration-runs', { headers: { 'X-Workbench-Request': '1' } })).json());
    const guardObserved = guardCatalog.runs.filter(run => run.execution_source === 'observed_agent_execution');
    const guardTarget = guardObserved.find(run => run.session_id !== liveSid) ?? guardObserved[0];
    check(!!guardTarget, 'IA3-04: 交付目录可用');
    await navTo('01 测试案例');
    await page.getByTestId('mode-agent').click();
    const guardResponse = page.waitForResponse(response => response.url().endsWith(`/observer/api/integration-runs/${guardTarget.run_id}`));
    await page.selectOption('#run', guardTarget.session_id);
    await guardResponse;
    await page.getByTestId('committed-total').waitFor();
    await openEvidence();
    await page.locator('.run-identity summary').click();
    const guardIdentity = await page.locator('.identity-fields').innerText();
    check(guardIdentity.includes(guardTarget.session_id), 'IA3-04: 运行身份与所选交付运行一致');
    check(!guardIdentity.includes(config.sessions[0]) || guardTarget.session_id === config.sessions[0], 'IA3-04: 不残留其他运行的核验/赔款');
    check((await page.getByTestId('committed-total').innerText()) === new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(guardTarget.total_committed_cents / 100), 'IA3-04: 结果卡金额指向同一运行');
    const unauthorized = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const locked = await unauthorized.newPage();
    await locked.goto(config.origin);
    await locked.getByRole('alert').filter({ hasText: '本机观察授权未建立或已过期' }).first().waitFor();
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
