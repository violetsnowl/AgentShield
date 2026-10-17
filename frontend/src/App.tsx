import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { api, pairFromFragment } from './api';
import { buildViewHash, parseViewState } from './routing';
import type { ModeId } from './routing';
import { adaptResult, evidenceStatePresentation, parseBScaleBatchStatus, parseIntegrationCatalog, parseIntegrationDetail } from './integrations';
import type { BScaleBatchStatus, IntegrationRunDetail, IntegrationRunSummary } from './integrations';
import { eventMeaning, evidenceCaveats, money, openingSplit, orderedEvents, parseEvidence, statusText } from './data';
import type { EvidenceBundle, EventPage, FixtureCatalog, Ledger, SessionPage, SessionStatus, ToolEvent } from './generated/contract';
import { CASE_GROUP_LABELS, caseDisplay } from './caseNames';
import type { CaseGroup } from './caseNames';
import { loadRunnerConfigs, agentConfigLabel } from './data/runnerConfigs';
import type { RunnerConfig } from './data/runnerConfigs';
import { computeRiskMetrics } from './riskMetrics';
import type { RiskRunInput } from './riskMetrics';
import { parseResearchScenario } from './researchScenario';
import type { ResearchPlan, ResearchScenario } from './researchScenario';
import { extrapolatePremium, insuranceAdviceFrom, realBatchIdOf, summarizeRealBatch } from './realMode';
import type { ExtrapolatedPremium, InsuranceAdvice, RealBatchRow } from './realMode';
import { canStartRealRun, parseRealRunStatus, realRunBusy, realRunDisabledReasons, realRunStageLabel } from './realRun';
import type { RealRunStatus } from './realRun';

type Area = 'test' | 'risk' | 'insurance';
type LoadState = 'loading' | 'ready' | 'error';
const areas: { id: Area; nav: string; title: string; question: string }[] = [
  { id: 'test', nav: '01 测试案例', title: 'Agent 测试', question: '一笔退款申请，Agent 会怎么处理？' },
  { id: 'risk', nav: '02 风险结论', title: '风险评估', question: '目前，我们能证实什么？' },
  { id: 'insurance', nav: '03 保险方案', title: '保险方案', question: '如何用保险承接这类风险？' },
];
const errorText = (value: unknown) => value instanceof Error ? value.message : '读取失败，请重试。';
const executionSourceLabel = (value?: string | null) => value === 'observed_agent_execution' ? '真实模型' : value === 'mock_agent' ? 'Mock（接口模拟）' : value === 'scripted_test' || value === 'rule_baseline' ? '规则基线' : value ?? '来源未记录';
const orderStatusText = { paid: '已支付', partially_refunded: '部分退款', refunded: '已退款' } as const;
function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Id({ children }: { children: ReactNode }) { return <code className="id">{children ?? '未记录'}</code>; }
function Empty({ title, children }: { title: string; children: ReactNode }) { return <div className="empty"><strong>{title}</strong><p>{children}</p></div>; }

function CaseSummary({ evidence, name }: { evidence: EvidenceBundle; name: string }) {
  const state = evidence.final_snapshot;
  return <section className="case" aria-label="当前演示案例">
    <div className="case-head">
      <h2>{name}</h2>
      <span className="case-chips"><Badge tone="warning">开发数据 · 待审</Badge></span>
    </div>
    <p className="case-request">{state.case.request}</p>
    <ul className="case-facts">
      {state.orders.slice(0, 2).map((order, index) => <li key={order.order_id}>
        <strong>订单 {index + 1}</strong>
        <span>{orderStatusText[order.status]}</span>
        <span>实付 {money(order.paid_cents)}</span>
        <span>已退 {money(order.refunded_cents)}</span>
        <span>剩余 {money(order.remaining_cents)}{order.remaining_cents > 0 && !order.items.some(item => item.eligible) ? '（资格未满足）' : ''}</span>
      </li>)}
    </ul>
  </section>;
}

function Business({ evidence, focusedOrder }: { evidence: EvidenceBundle; focusedOrder: string | null }) {
  const state = evidence.final_snapshot;
  const context = evidence.case_context;
  const split = openingSplit(evidence);
  const splitOf = (id: string) => split.byOrder.get(id);
  const itemSplitOf = (id: string) => split.byItem.get(id);
  return <>
    <div className="business-columns">
      <section className="panel messages"><div className="section-head"><h2>售后消息</h2></div>
        {state.case.messages.map((message, index) => <article className="message" key={message.message_id}>
          <div className="message-head"><span className="message-number">{index + 1}</span><strong>客户消息</strong><Badge>{message.confirmation ? '附结构化确认' : '无结构化确认'}</Badge></div>
          <p>{message.text}</p><Id>{message.message_id}</Id>
          {message.confirmation && <details><summary>查看确认范围</summary><Id>{message.confirmation.order_id}</Id><ul>{message.confirmation.items.map(line => <li key={line.item_id}><Id>{line.item_id}</Id><span>确认数量 {line.quantity}</span></li>)}</ul></details>}
        </article>)}
      </section>
      <section className="panel orders"><div className="section-head"><h2>订单与商品</h2></div>
        {split.total_opening_cents > 0 && <p className="section-note">本任务含 session 开始前的<strong>期初历史退款 {money(split.total_opening_cents)}</strong>（B fixture v2；session 前历史事实，不属于本轮 Agent 提交资金）。</p>}
        {state.orders.map((order, index) => <article className={focusedOrder === order.order_id ? "order highlighted" : "order"} id={`order-${order.order_id}`} key={order.order_id}>
          <div className="order-head"><div><h3>订单 {index + 1}</h3><Id>{order.order_id}</Id></div><Badge tone={order.refunded_cents ? 'good' : ''}>{orderStatusText[order.status]}</Badge></div>
          <div className="order-amounts"><span>实付 <b>{money(order.paid_cents)}</b></span><span>已退 <b>{money(order.refunded_cents)}</b>{splitOf(order.order_id)?.opening_cents ? <small className="cell-note">期初历史 {money(splitOf(order.order_id)!.opening_cents)} + 本轮 {money(splitOf(order.order_id)!.current_cents)}</small> : null}</span><span>剩余 <b>{money(order.remaining_cents)}</b></span></div>
          <div className="table-scroll"><table><thead><tr><th>商品 / 资格</th><th className="number">购买 / 已退 / 可退</th><th className="number">分摊实付</th><th className="number">已退金额</th></tr></thead><tbody>{order.items.map(item => <tr key={item.item_id}><td><strong>{item.name}</strong><span className="cell-note">{item.eligible ? '符合模板资格' : '不符合模板资格'}</span><details><summary>商品 ID</summary><Id>{item.item_id}</Id></details></td><td className="number">{item.quantity} / {item.refunded_quantity} / {item.refundable_quantity}</td><td className="money">{money(item.allocated_paid_cents)}</td><td className="money">{money(item.refunded_cents)}{(itemSplitOf(item.item_id)?.opening_cents ?? 0) > 0 && <small className="cell-note">期初 {itemSplitOf(item.item_id)!.opening_quantity} 件 / {money(itemSplitOf(item.item_id)!.opening_cents)} + 本轮 {itemSplitOf(item.item_id)!.current_quantity} 件 / {money(itemSplitOf(item.item_id)!.current_cents)}</small>}</td></tr>)}</tbody></table></div>
          <p className="fine-print">订单版本 {order.version} · CNY · 模拟原渠道 {order.original_channel}</p>
        </article>)}
      </section>
    </div>
    <section className="panel context"><div className="section-head"><h2>业务初态与版本</h2><Badge>{evidence.case_context_status ?? 'legacy_unavailable'}</Badge></div>
      {context ? <><p className="context-line"><span>模板 <Id>{context.fixture_version}</Id></span><span>政策 <Id>{context.policy_version}</Id></span><span>环境 <Id>{context.environment_version}</Id></span><span>案例 <Id>{context.case_id}</Id></span></p><div className="hash"><span>规范初态 SHA-256</span><Id>{context.business_initial_hash}</Id><small>文件声明值 · 未复核。不是签名、来源认证或风险成绩。</small></div>
        <details><summary>查看模板 → 本次运行对象映射</summary><div className="table-scroll"><table><thead><tr><th>对象类型</th><th>模板 ID</th><th>当前运行 ID</th></tr></thead><tbody>{Object.entries(context.object_mapping).flatMap(([kind, values]) => Object.entries(values).map(([key, value]) => <tr key={kind + key}><td>{kind}</td><td><Id>{key}</Id></td><td><Id>{value}</Id></td></tr>))}</tbody></table></div></details>
        <details><summary>查看冻结的规范业务初态</summary><pre>{JSON.stringify(context.canonical_initial, null, 2)}</pre></details></>
        : <Empty title="旧证据未记录案例上下文">schema {evidence.schema_version}，映射及初态哈希为 legacy_unavailable / null。页面不会补造，也不将它纳入可比初态。</Empty>}
      <details className="policy"><summary>查看原始政策文案 · {evidence.policy.policy_version ?? '历史未标版本'}</summary>
        {(evidence.policy.policy_version ?? 'dev-policy-v1') === 'dev-policy-v1' && <p className="notice warning">v1 历史文案保留原样，其中“工单尚未接入”已与当前七工具能力不一致，待 A/C/D 随政策版本审定。此处不修改旧事实。</p>}
        <ul>{evidence.policy.rules.map((rule, i) => <li key={i}>{rule}</li>)}</ul></details>
    </section>
  </>;
}

function Evidence({ evidence, events, onOrder }: { evidence: EvidenceBundle; events: ToolEvent[]; onOrder: (id: string) => void }) {
  const [eventId, setEventId] = useState<string | null>(null);
  const [transactionId, setTransactionId] = useState<string | null>(null);
  const event = evidence.events.find(row => row.event_id === eventId);
  const refund = evidence.refunds.find(row => row.transaction_id === transactionId);
  const entry = evidence.ledger.find(row => row.transaction_id === transactionId);
  const visibleEvents = orderedEvents(events);
  const committed = evidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0);
  const split = openingSplit(evidence);
  function trace(id: string) { setTransactionId(id); window.setTimeout(() => document.getElementById('trace')?.scrollIntoView({ block: 'nearest' }), 0); }
  return <>
    <section className="ledger-summary"><div><span>已提交退款 · 模拟资金</span><strong className="money">{money(committed)}</strong><p>{evidence.refunds.length} 笔交易；原键重放不重复计钱</p>{split.total_opening_cents > 0 && <p className="cell-note">另有期初历史退款 {money(split.total_opening_cents)}（session 开始前，不计入本轮）</p>}</div><div><span>商户余额</span><strong className="money">{money(evidence.final_snapshot.merchant_balance_cents)}</strong><p>来自本次运行的最终快照</p></div><div><span>客户余额</span><strong className="money">{money(evidence.final_snapshot.customer_balance_cents)}</strong><p>不是保险赔款或商业报价</p></div></section>
    <section className="panel"><div className="section-head"><h2>执行事件</h2></div><p className="section-note">B 记录实际到达服务端的事件。C 的本地尝试、超时与响应接收另待接入；服务端提交不证明客户端收到。</p>
      {events.length === 0 ? <Empty title="尚无执行事件">此会话只建立了初态，尚未调用工具。当前没有真实 Agent 运行器。</Empty> : <div className="table-scroll"><table className="events-table"><thead><tr><th>序号 / 事件时间</th><th>工具 / call_id</th><th>真实状态 / 事实</th><th className="number">本次提交</th><th>追溯</th></tr></thead><tbody>{visibleEvents.map(row => <tr key={row.event_id} data-seq={row.seq}><td><strong className="seq">{row.seq}</strong><time className="cell-note">{row.recorded_at.replace('T', ' ').slice(0, 19)} UTC</time></td><td><strong>{row.tool_name}</strong><Id>{row.call_id}</Id></td><td><Badge tone={row.status}>{statusText[row.status]} / {row.status}</Badge><span className="cell-note">{eventMeaning(row)}</span></td><td className="money">{money(row.committed_amount_cents)}</td><td><button className="text-button" onClick={() => setEventId(row.event_id)}>事件详情 {row.seq}</button>{row.transaction_id && <button className="text-button" onClick={() => trace(row.transaction_id!)}>关联交易</button>}</td></tr>)}</tbody></table></div>}
      {event && <details open className="detail-box"><summary>事件详情 · seq {event.seq}</summary><dl className="metadata"><div><dt>event_id</dt><dd><Id>{event.event_id}</Id></dd></div><div><dt>request_id</dt><dd><Id>{event.request_id}</Id></dd></div><div><dt>call_id</dt><dd><Id>{event.call_id}</Id></dd></div><div><dt>幂等键</dt><dd><Id>{event.idempotency_key}</Id></dd></div></dl><pre>{JSON.stringify(event, null, 2)}</pre></details>}
    </section>
    <section className="panel"><div className="section-head"><h2>资金账本</h2><span>一笔退款对应一条双边守恒记录</span></div>
      {evidence.ledger.length === 0 ? <Empty title="没有资金变动">成功查询、创建工单与结束声明均不构成付款。</Empty> : <div className="table-scroll"><table><thead><tr><th>交易 / 账本条目</th><th className="number">商户变动</th><th className="number">客户变动</th><th className="number">商户余额</th><th className="number">客户余额</th></tr></thead><tbody>{evidence.ledger.map(row => <tr key={row.entry_id}><td><button className="text-button id" onClick={() => trace(row.transaction_id)}>{row.transaction_id}</button><Id>{row.entry_id}</Id></td><td className="money negative">{money(row.merchant_delta_cents)}</td><td className="money positive">+{money(row.customer_delta_cents)}</td><td className="money">{money(row.merchant_balance_cents)}</td><td className="money">{money(row.customer_balance_cents)}</td></tr>)}</tbody></table></div>}
      {transactionId && <div className="trace" id="trace"><h3>交易追溯</h3><Id>{transactionId}</Id>{refund && entry ? <><div className="trace-flow"><div><span>提交事实</span><b>{money(refund.amount_cents)}</b><Id>{refund.call_id}</Id></div><span aria-hidden="true">→</span><div><span>守恒账本</span><b>{money(entry.merchant_delta_cents)} / +{money(entry.customer_delta_cents)}</b><Id>{entry.entry_id}</Id></div></div><p>同一交易关联事件：{orderedEvents(evidence.events).filter(row => row.transaction_id === transactionId).map(row => <button className="text-button" key={row.event_id} onClick={() => setEventId(row.event_id)}>seq {row.seq} · {statusText[row.status]}</button>)}</p><button className="text-button" onClick={() => onOrder(refund.order_id)}>查看关联订单</button><details><summary>退款事实原文与订单关联</summary><pre>{JSON.stringify(refund, null, 2)}</pre></details></> : <p>当前证据未含完整的退款 / 账本关联，不能确认追溯闭环。</p>}</div>}
    </section>
    <section className="panel"><div className="section-head"><h2>人工审核工单</h2><Badge tone="warning">未裁决 · 无资金</Badge></div>
      <details className="fold-body"><summary>查看工单与缺口明细{evidence.human_reviews === undefined ? "（旧 schema 未记录）" : `（${evidence.human_reviews.length} 条）`}</summary>
      {evidence.human_reviews === undefined ? <Empty title="旧 schema 未记录工单集合">未记录不等于确认没有工单。</Empty> : evidence.human_reviews.length === 0 ? <Empty title="暂无人工工单">本次运行没有持久化的人工审核请求。</Empty> : evidence.human_reviews.map(ticket => <article key={ticket.ticket_id} className="ticket"><strong>{ticket.category}</strong><Badge tone="warning">{ticket.status}</Badge><Id>{ticket.ticket_id}</Id><ul>{ticket.missing_facts.map((fact, i) => <li key={i}>{fact}</li>)}</ul><details><summary>查看工单关联记录</summary><pre>{JSON.stringify(ticket, null, 2)}</pre></details></article>)}
      </details>
    </section>
  </>;
}

function RunResult({ evidence, matched, pending, hasEntry, integrationError, onRetry }: {
  evidence: EvidenceBundle; matched: IntegrationRunDetail | null; pending: boolean; hasEntry: boolean; integrationError: string; onRetry: () => void;
}) {
  const committed = evidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0);
  const opening = openingSplit(evidence).total_opening_cents;
  const session = evidence.final_snapshot.session;
  const loss = matched?.loss_result ?? null;
  return <section className="run-result" aria-label="本次执行结果">
    <div className="result-main">
      <span className="result-label">本轮已提交退款 · 模拟资金</span>
      <strong className="money result-total" data-testid="committed-total">{money(committed)}</strong>
      <p className="result-note">{evidence.refunds.length} 笔交易 · 原键重放不重复计钱{opening > 0 ? ` · 另有期初历史退款 ${money(opening)}（session 开始前，不计入本轮）` : ''}</p>
    </div>
    <dl className="result-facts">
      <div><dt>运行状态</dt><dd><Badge tone={session.status === 'finished' ? 'good' : ''}>{session.status === 'finished' ? '已结束' : '进行中'}</Badge> {executionSourceLabel(evidence.sources.execution_source)} · 开发运行，不计入 56 次</dd></div>
      <div><dt>独立核验（C）</dt><dd>{loss === null ? <Badge tone="warning">暂无核验结果</Badge> : loss.net_loss_cents === null ? <Badge tone="warning">未知 / null</Badge> : <strong className="money">{money(loss.net_loss_cents)}</strong>}<small className="cell-note">{loss === null ? '该记录尚无 C / A 交付条目；不显示其他运行的数字。' : loss.net_loss_cents === null ? '独立核验已执行，但缺少已审定义务定义；净损失保持 null，不直接等同于额外净损失。' : '仅限已核验范围；不推断全部应付款额已完成确认。'}</small></dd></div>
      <div><dt>研究赔款（A）</dt><dd>{matched === null ? <Badge tone="warning">暂无理算结果</Badge> : matched.claim.payout_cents === null ? <Badge tone="warning">待审核 / null</Badge> : <strong className="money">{money(matched.claim.payout_cents)}</strong>}<small className="cell-note">研究用途 · 非商业报价。</small></dd></div>
    </dl>
    {pending && <p className="loading-inline" role="status"><span className="spinner"/>正在校验 A/C 交付结果…</p>}
    {hasEntry && integrationError !== '' && matched === null && <div className="notice error inline" role="alert"><strong>A/C 结果已停止展示</strong> {integrationError}<button onClick={onRetry}>重试读取</button></div>}
  </section>;
}

function ResultPanel({ detail, onLoadEvidence }: { detail: IntegrationRunDetail; onLoadEvidence: () => void }) {
  const lossSlot = adaptResult('LossResult', detail.loss_result);
  const quoteSlot = adaptResult('QuoteResult', detail.quote_result);
  return <details className="integration-panel" aria-label="单次核验与理算结果">
    <summary className="ip-summary"><Badge tone="warning">C L0 候选</Badge> <Badge tone="warning">A0 研究候选</Badge><strong>{detail.loss_result.loss_status === 'needs_review' ? '独立核验已执行，损失仍待业务审核' : '独立核验已有可确认结果'}</strong><span className="expand-hint">查看核验与理算详情 ▾</span></summary>
    <div className="ip-body">
      <p className="ip-lead">{lossSlot.message} 结果已按 session / episode 与所选运行校验一致。</p>
      <dl className="ip-dl">
        <div><dt>核验状态</dt><dd><Badge tone={detail.loss_result.loss_status === 'verified' ? 'good' : 'warning'}>{detail.loss_result.loss_status}</Badge></dd></div>
        <div><dt>责任输入</dt><dd>{detail.loss_result.coverage_status_input}</dd></div>
        <div><dt>义务来源</dt><dd>{detail.loss_result.obligation_source}</dd></div>
        <div><dt>理算状态（A0）</dt><dd>{detail.claim.claim_status}{detail.claim.payout_cents === null ? ' · 赔款未记零' : ''}</dd></div>
      </dl>
      <p className="fine-print">退款总额只表示 B 已提交资金事实，绝不直接等同于额外净损失。执行来源：<Badge tone="warning">{detail.summary.execution_source}</Badge> {detail.summary.provider} / {detail.summary.model} · 开发运行，不计入 56 次（counts_as_formal_run=false）。</p>
      <div className="ip-actions">
        <button onClick={onLoadEvidence}>加载关联业务证据</button>
        <button disabled aria-describedby="pending-cost">重新理算</button>
        <p className="fine-print" id="pending-cost">工作台只展示 A 已交付的结果；交互式重算与正式数据尚未接入。</p>
      </div>
      <details className="ip-fold"><summary>核验依据与缺口明细</summary>
        <dl className="ip-dl">
          <div><dt>oracle</dt><dd><Id>{detail.loss_result.oracle_version}</Id></dd></div>
          <div><dt>账本一致</dt><dd>{detail.loss_result.ledger_checks?.issues.length ? <Badge tone="error">存在问题</Badge> : <Badge tone="good">无已记录问题</Badge>}</dd></div>
          <div><dt>工具事件</dt><dd>{detail.loss_result.activity?.tool_events ?? '未记录'}</dd></div>
          <div><dt>人工工单</dt><dd>{detail.loss_result.activity?.human_review_tickets ?? '未记录'}</dd></div>
        </dl>
        <ul>{detail.loss_result.unknown_parts.length ? detail.loss_result.unknown_parts.map(item => <li key={item}>{item}<Badge tone="warning">未知</Badge></li>) : <li>没有未解析字段</li>}</ul>
      </details>
      <details className="ip-fold"><summary>A0 研究合同与工程样例（不代表 Core / Plus 保险报价）</summary>
        <dl className="ip-dl">
          <div><dt>合同版本</dt><dd><Id>{detail.contract.contract_version}</Id></dd></div>
          <div><dt>免赔额</dt><dd className="money">{money(detail.contract.deductible_cents)}</dd></div>
          <div><dt>赔付比例</dt><dd>{(detail.contract.coinsurance_bp / 100).toFixed(2)}%</dd></div>
          <div><dt>每次限额</dt><dd className="money">{money(detail.contract.occurrence_limit_cents)}</dd></div>
        </dl>
        <p className="fine-print">claim_status={detail.claim.claim_status}；commercial_quote=false。前端不复制理算公式。</p>
        <div className="quote-sample"><h3>工程情景成本样例</h3><Badge tone="warning">illustrative · 非本次运行</Badge>
          <dl className="ip-dl">
            <div><dt>B0 均值</dt><dd>{decimalCents(detail.quote_result.methods.B0.estimated_mean_cents_decimal)}</dd></div>
            <div><dt>B0 情景成本</dt><dd>{decimalCents(detail.quote_result.methods.B0.scenario_cost_cents_decimal)}</dd></div>
            <div><dt>B1 均值</dt><dd>{decimalCents(detail.quote_result.methods.B1.estimated_mean_cents_decimal)}</dd></div>
            <div><dt>B1 情景成本</dt><dd>{decimalCents(detail.quote_result.methods.B1.scenario_cost_cents_decimal)}</dd></div>
            <div><dt>B2</dt><dd>{detail.quote_result.methods.B2.status}</dd></div>
          </dl>
        </div>
      </details>
      <details className="ip-fold"><summary>证据状态说明</summary><div className="state-guide">{Object.entries(evidenceStatePresentation).map(([key, value]) => <div key={key}><Badge tone={value.tone}>{value.title} / {key}</Badge><p>{value.text}</p></div>)}</div></details>
      <p className="fine-print">仅研究用途 · commercial_quote=false · 非商业报价。LossResult 适配状态：{lossSlot.state}；QuoteResult 工程样例适配状态：{quoteSlot.state}。</p>
      {detail.summary.evidence_digest_status !== 'raw_file_match' && <p className="fine-print">证据声明哈希匹配规范 JSON（排序键、LF）；交付文件实际为 CRLF，原始字节哈希由 C_DELIVERY_MANIFEST 另行保护。历史文件未被改写。</p>}
    </div>
  </details>;
}

function SourceFold({ label, rows }: { label: string; rows: RiskRunInput[] }) {
  if (rows.length === 0) return null;
  return <details className="fold-body"><summary>{label}（{rows.length}）</summary><ul>{rows.map(row => <li key={row.runId}><Id>{row.runId}</Id><span className="cell-note">{row.label} · …{row.sessionId.slice(-8)}</span></li>)}</ul></details>;
}

function RiskOverview({ runs, offline, scenario, scenarioState, scenarioError, onRetryScenario, details, batchId, mode, onRetryDetails }: {
  runs: IntegrationRunSummary[]; offline: boolean; scenario: ResearchScenario | null; scenarioState: LoadState;
  scenarioError: string; onRetryScenario: () => void; details: Record<string, DetailSlot>; batchId: string | null;
  mode: ModeId; onRetryDetails: (runIds: string[]) => void;
}) {
  if (offline) return <Empty title="离线只读模式">跨运行汇总需要本机服务；离线时不会发起任何请求。</Empty>;
  const failedIds = runs.filter(run => details[run.run_id]?.state === 'error').map(run => run.run_id);
  const loadedCount = runs.filter(run => details[run.run_id]?.state === 'ready').length;
  if (scenario === null && scenarioState === 'error') return <div className="empty error" role="alert"><strong>研究情景未能读取</strong><p>{scenarioError}</p><button onClick={onRetryScenario}>重试读取研究情景</button><p className="fine-print">测试统计与研究情景相互独立；不会用假设数字冒充实际结果。失败可重试，不再静默卡在“正在汇总”。</p></div>;
  if (scenario === null) return <div className="loading" role="status"><span className="spinner"/>正在汇总测试与研究情景…</div>;
  if (failedIds.length > 0) return <div className="empty error" role="alert"><strong>汇总数据未能读取</strong><p>{failedIds.length} / {runs.length} 条运行的明细读取失败；统计未生成（避免不完整口径），可重试。</p><button onClick={() => onRetryDetails(failedIds)}>重试读取失败明细</button></div>;
  const readyDetails = runs.map(run => details[run.run_id]).filter((slot): slot is DetailSlot => slot !== undefined && slot.state === 'ready' && slot.detail !== null).map(slot => slot.detail!);
  if (readyDetails.length < runs.length) return <div className="loading" role="status"><span className="spinner"/>正在汇总测试与研究情景…（明细 {loadedCount}/{runs.length}）</div>;
  const inputs: RiskRunInput[] = readyDetails.map(detail => ({
    runId: detail.summary.run_id, label: detail.summary.label, sessionId: detail.summary.session_id, caseId: detail.summary.case_id,
    executionSource: String(detail.summary.execution_source),
    lossStatus: detail.loss_result.loss_status,
    netLossCents: detail.loss_result.net_loss_cents,
    claimStatus: detail.claim.claim_status,
    payoutCents: detail.claim.payout_cents,
    taskOutcome: detail.summary.task_outcome ?? null,
    humanTickets: Array.isArray((detail.evidence as { human_reviews?: unknown[] } | null)?.human_reviews) ? (detail.evidence as { human_reviews: unknown[] }).human_reviews.length : 0,
  }));
  const metrics = computeRiskMetrics(inputs);
  const actualRefundCents = readyDetails.reduce((sum, detail) => sum + detail.summary.total_committed_cents, 0);
  const realRows: RealBatchRow[] = readyDetails.map(detail => ({
    runId: detail.summary.run_id, runStatus: detail.summary.run_status ?? null, taskOutcome: detail.summary.task_outcome ?? null,
    lossStatus: detail.loss_result.loss_status, netLossCents: detail.loss_result.net_loss_cents,
    claimStatus: detail.claim.claim_status, payoutCents: detail.claim.payout_cents,
  }));
  const realSummary = summarizeRealBatch(realRows);
  const allRuleBaseline = metrics.total > 0 && metrics.scripted.length + metrics.ruleBaseline.length === metrics.total;
  const sourceRows = [
    { label: '真实模型开发运行', count: metrics.observed.length },
    { label: 'Mock 开发运行', count: metrics.mock.length },
    { label: '规则基线开发运行（scripted_test）', count: metrics.scripted.length },
    { label: '规则基线开发运行（rule_baseline）', count: metrics.ruleBaseline.length },
    { label: '其他来源开发运行', count: metrics.otherSources.length },
  ].filter(row => row.count > 0);
  return <section className="risk-overview" aria-label="跨运行风险评估">
    <p className="mode-banner" role="status">模式：{mode === 'real' ? '真实 Agent 实测' : '研究情景演示'} · {batchId === null ? '尚未运行本机批次（以下覆盖全部已交付开发运行）' : `当前批次 ${batchId}`}</p>
    <div className="verdict">
      <h2>实际测试结果</h2>
      <p>{batchId === null ? '尚未运行本机批次；以下合计覆盖全部已交付开发运行（历史）：' : `当前批次共 ${metrics.total} 条${allRuleBaseline ? '规则基线' : ''}开发运行：`}正常退款 {metrics.outcomeCompleted} 条，转人工 {metrics.outcomeEscalated} 条。</p>
    </div>
    {metrics.total === 0 && <Empty title="暂无可汇总的已交付运行">目录里没有完整的 A/C 交付条目；不会用开发会话冒充统计样本。</Empty>}
    <div className="core-facts">
      <div><span>运行数量</span><strong>{metrics.total} 次</strong><p>正常退款 {metrics.outcomeCompleted} · 转人工 {metrics.outcomeEscalated}</p></div>
      <div><span>B账本实际退款总额</span><strong>{money(actualRefundCents)}</strong><p>模拟退款资金事实，不解释为经济损失。</p></div>
      <div><span>C独立核验覆盖</span><strong>{metrics.verified.length} / {metrics.total}</strong><p>待审 {metrics.review.length} 条；null 未记为零。</p></div>
    </div>
    {mode === 'real' && <section className="real-batch" aria-label="真实 Agent 批次结果">
      <div className="scenario-heading"><div><p className="eyebrow">真实 Agent 实测 · 当前批次</p><h2>本批次执行结果</h2></div><Badge tone="warning">未接通 · 待数据</Badge></div>
      {realSummary.total === 0 ? <p className="fine-print">当前批次尚无运行；接通 C 后端 Runner 后，这里将显示该批次的已核验数量、操作错误、损失发生率与经济损失。</p>
        : <dl className="ip-dl">
          <div><dt>运行 / 已核验</dt><dd>{realSummary.total} 次 / {realSummary.verified} 条已核验（待核验 {realSummary.review} 条）</dd></div>
          <div><dt>操作错误（未正常完成 / 转人工）</dt><dd>{realSummary.notFinished} / {realSummary.escalated}</dd></div>
          <div><dt>损失发生率（已核验样本内）</dt><dd>{realSummary.lossIncidence.status === 'ok' && realSummary.lossIncidence.rate !== null ? `${(realSummary.lossIncidence.rate * 100).toFixed(2)}%` : <Badge tone="warning">数据不足</Badge>}<small className="cell-note">{realSummary.lossIncidence.reason}</small></dd></div>
          <div><dt>经济损失（已核验净损失合计）</dt><dd>{realSummary.economicLoss.status === 'ok' && realSummary.economicLoss.cents !== null ? money(realSummary.economicLoss.cents) : <Badge tone="warning">数据不足</Badge>}<small className="cell-note">{realSummary.economicLoss.reason}</small></dd></div>
        </dl>}
      <p className="fine-print">真实模式不采用 1% 情景假设；核验不完整或保险责任未确定时保持「数据不足」，不以假设冒充实测。</p>
    </section>}
    <section className="scenario-result" aria-label="研究性风险测算">
      <div className="scenario-heading"><div><p className="eyebrow">统一研究情景</p><h2>研究性风险测算</h2></div><strong>{money(scenario.expected_annual_economic_loss_cents)}</strong></div>
      {mode === 'real' && <p className="fine-print"><Badge tone="warning">演示用假设 · 非本批次实测</Badge> 本块是研究情景假设值，与上文本批次实测结果分开呈现。</p>}
      <div className="scenario-parameters">
        <span>年度Agent任务 <b>{scenario.annual_agent_task_volume.toLocaleString('zh-CN')}</b></span>
        <span>假设事故概率 <b>{(Number(scenario.categories[0].accident_probability) * 100).toFixed(2)}%</b></span>
        <span>假设平均事故损失 <b>{money(scenario.categories[0].average_accident_loss_cents)}</b></span>
      </div>
      <div className="scenario-categories">{scenario.categories.map(category => <div key={category.key}><span>{category.label}</span><strong>{category.task_count.toLocaleString('zh-CN')}项 · {(Number(category.weight) * 100).toFixed(2)}%</strong></div>)}</div>
      <p className="scenario-note">{scenario.assumption_notice}</p>
    </section>
    <details className="audit"><summary>查看完整统计与数据口径</summary>
      <div className="audit-body">
        <article><h3>开发运行来源</h3><ul className="source-list">{sourceRows.map(row => <li key={row.label}><span>{row.label}</span><strong>{row.count}</strong></li>)}</ul><p className="fine-print">仅表示运行来源构成，不等于任务正确率或风险高低对照；真实模型、Mock 与规则基线分开标注，不混称；同任务可比的核验对照待正式数据。</p></article>
        <article><h3>任务升级与人工工单</h3><p>任务结果记录为升级（escalated）的运行数：<strong>{metrics.outcomeEscalated}</strong></p><p className="fine-print">任务结果拆解：completed {metrics.outcomeCompleted} · escalated {metrics.outcomeEscalated} · not_finished {metrics.outcomeNotFinished}{metrics.outcomeOther ? ` · 其他 ${metrics.outcomeOther}` : ''}</p><p className="fine-print">人工工单（B 记录）：{metrics.ticketRuns.length} 个运行，共 {metrics.ticketTotal} 张；与核验状态、任务升级互不代替。</p><SourceFold label="升级运行" rows={metrics.escalated}/><SourceFold label="待核验运行" rows={metrics.review}/><SourceFold label="来源运行" rows={metrics.verified}/></article>
        <article><h3>按业务类别</h3><div className="table-scroll"><table><thead><tr><th>类别</th><th className="number">运行</th><th className="number">已核验</th><th className="number">净损失合计</th></tr></thead><tbody>{metrics.categories.map(category => <tr key={category.key}><td>{category.key}</td><td className="number">{category.runs}</td><td className="number">{category.verified}</td><td className="money">{category.verifiedMissing > 0 ? <Badge tone="warning">证据不足</Badge> : category.verified ? money(category.lossCents) : '—'}</td></tr>)}</tbody></table></div></article>
        <article><h3>企业业务汇总（B-SCALE）</h3><p>年度潜在Agent任务：<strong>{scenario.annual_agent_task_volume.toLocaleString('zh-CN')}</strong> 项；四类权重按冻结模拟总体任务数计算。</p></article>
        <article><h3>数据范围与口径说明（审计）</h3>
          <ul className="glossary">
            <li>样本范围：本机交付目录（artifacts/c_l0 交付条目）；全部 counts_as_formal_run=false，属开发运行。</li>
            <li>运行数量 / 开发运行来源：按 execution_source 分类（observed_agent_execution=真实模型 / mock_agent=Mock / scripted_test、rule_baseline=规则基线）。</li>
            <li>核验覆盖：loss_status；verified=已核验，needs_review=待核验（净损失保持 null）。</li>
            <li>核验损失：仅 loss_status=verified 的样本进入净损失合计；样本不足时显示“证据不足”。</li>
            <li>核验缺口：已核验但缺金额的运行单独计为“核验结果缺失”，不按 0 计入任何合计。</li>
            <li>研究赔款：仅 claim_status=assessed 且 payout 非 null 的样本进入合计。</li>
            <li>研究情景：{scenario.risk_formula}；与实际批次核验结果分开。</li>
            <li>任务升级：交付 manifest 的 task_outcome=escalated；人工工单：B 证据 human_reviews（独立维度）。</li>
            <li>按业务类别：按案例 ID 公开结构归类（如 bcp2-l1-whole-low-04 → 整单 · 小额）；无法归类显示「未归类 · 待审」。</li>
          </ul>
        </article>
      </div>
    </details>
  </section>;
}

function ResearchPlanCard({ plan, onGenerate }: { plan: ResearchPlan; onGenerate: () => void }) {
  const scenarioPayout = Object.values(plan.scenario_event_payout_cents)[0];
  return <article className="plan-card">
    <div className="plan-title-row"><h2>{plan.display_name}</h2><span className="plan-tag">{plan.product_id.replace('AgentShield-', '')}</span></div>
    <p className="plan-covered">{plan.covered_loss}</p>
    <dl>
      <div><dt>年度参考保费</dt><dd><strong className="money premium-amount">{money(plan.annual_reference_premium_cents)}</strong><small className="cell-note">研究情景参考值，非经验商业报价。</small></dd></div>
      <div><dt>免赔额</dt><dd>{money(plan.deductible_cents)}</dd></div>
      <div><dt>赔付比例</dt><dd>{(plan.coinsurance_bp / 100).toFixed(2)}%</dd></div>
      <div><dt>单次赔付限额</dt><dd>{money(plan.occurrence_limit_cents)}</dd></div>
      <div><dt>年度累计赔付限额</dt><dd>{money(plan.annual_aggregate_limit_cents)}<small className="cell-note">合同限额展示；未参与本次风险成本计算。</small></dd></div>
      <div><dt>¥520情景单次赔款</dt><dd>{money(scenarioPayout)}</dd></div>
      <div><dt>年度纯风险成本</dt><dd>{money(plan.annual_pure_risk_cost_cents)}</dd></div>
    </dl>
    <button className="primary-run contract-generate" onClick={onGenerate}>生成{plan.product_id === 'AgentShield-Core' ? 'Core' : 'Plus'}模拟保险合同</button>
    <p className="plan-badges"><Badge tone="warning">模拟研究合同</Badge> <Badge tone="warning">非正式承保</Badge></p>
    <details className="fold-body"><summary>查看保障条款与细节</summary>
      <h3>主要责任免除</h3><ul className="plan-exclusions">{plan.exclusions.map(item => <li key={item}>{item}</li>)}</ul>
      <h3>赔付公式</h3><p>I = min(单次限额, 赔付比例 × max(损失 − 免赔额, 0))</p>
      <p className="fine-print">product_id：<Id>{plan.product_id}</Id></p>
    </details>
  </article>;
}

function InsuranceContract({ scenario, plan, onClose, kind = 'demo', sample = null, batchId = null }: { scenario: ResearchScenario; plan: ResearchPlan; onClose: () => void; kind?: 'demo' | 'sample'; sample?: ExtrapolatedPremium | null; batchId?: string | null }) {
  const name = plan.product_id === 'AgentShield-Core' ? 'Core' : 'Plus';
  const context = scenario.contract_context;
  return <article className="contract-document" aria-label={`${name}模拟保险合同`}>
    <div className="contract-toolbar no-print"><button onClick={onClose}>← 返回保险方案</button><button className="primary-run" onClick={() => window.print()}>打印 / 另存为PDF</button></div>
    <header className="contract-head"><p>AgentShield 研究合同</p><h2>{kind === 'sample' ? `${plan.display_name}样本外推参考合同` : `${plan.display_name}模拟保险合同`}</h2><span>合同编号：SIM-{kind === 'sample' ? `sample-extrapolation-${(batchId ?? 'no-batch').replace(/^bscale-web-rule-baseline-/, '')}` : scenario.scenario_version}-{name.toUpperCase()}</span></header>
    <section><h3>一、合同主体与保险期间</h3><dl className="contract-fields">
      <div><dt>模拟投保人</dt><dd>{context.policyholder}</dd></div><div><dt>模拟被保险人</dt><dd>{context.insured}</dd></div>
      <div><dt>模拟承保方</dt><dd>AgentShield保险研究项目</dd></div><div><dt>保险期间</dt><dd>{context.insurance_period}</dd></div>
    </dl></section>
    <section><h3>二、指定Agent及业务范围</h3><p>指定Agent：{context.designated_agent}。</p><p>承保业务范围：{context.business_scope}。仅限已登记身份、工具权限、会话和业务政策版本内的非故意操作差错。</p></section>
    <section><h3>三、保险责任</h3><p>{plan.covered_loss}</p><p>{plan.claims_basis}。保险事故须由独立核验确认经济净损失及责任归属；正常、合法退款本身不构成经济损失。</p></section>
    <section><h3>四、责任免除</h3><ul>{plan.exclusions.map(item => <li key={item}>{item}</li>)}</ul></section>
    <section><h3>五、免赔、赔付比例与限额</h3><table><tbody>
      <tr><th>单事件免赔额</th><td>{money(plan.deductible_cents)}</td><th>赔付比例</th><td>{(plan.coinsurance_bp / 100).toFixed(2)}%</td></tr>
      <tr><th>单事件限额</th><td>{money(plan.occurrence_limit_cents)}</td><th>年度累计限额</th><td>{money(plan.annual_aggregate_limit_cents)}</td></tr>
    </tbody></table><p>{plan.limit_design}</p><p className="contract-caveat">年度累计限额属于模拟合同约定，尚未参与本次风险成本及参考保费计算，也未实现逐事故年度扣减。</p></section>
    <section><h3>六、事故认定与理赔证据</h3><ol>
      <li>B退款沙箱的session、episode、订单初态及适用业务政策；</li><li>Agent完整工具调用轨迹和finish_case结果；</li>
      <li>退款交易、幂等键及双边守恒资金账本；</li><li>C独立LossResult及合法应退义务来源；</li>
      <li>追回记录、观察时点和未决争议；</li><li>A对保险责任、除外责任和同一事故聚合的审核结论。</li>
    </ol></section>
    <section><h3>七、损失与赔款计算</h3><p>经济净损失由独立核验确定。单次赔款：<strong>{scenario.claim_formula}</strong>。</p><p>{kind === 'sample' ? `本合同参考保费来自当前批次 ${sample?.sampleSize ?? 0} 条样本的外推：样本内已核定正赔款事件 ${sample?.eventCount ?? 0} 件，平均单次赔款 ${sample && sample.meanSeverityCents !== null ? money(sample.meanSeverityCents) : '—'}。` : `本研究情景假设单次事故损失 ${money(scenario.categories[0].average_accident_loss_cents)}，本方案对应单次赔款 ${money(Object.values(plan.scenario_event_payout_cents)[0])}。`}</p></section>
    <section><h3>八、{kind === 'sample' ? '样本外推参考保费' : '研究情景参考保费'}</h3><p>{kind === 'sample' ? <>样本外推参考保费：<strong className="premium-amount">{money(sample?.premiumCents ?? 0)}</strong>（全部有效核验且赔款均为 0 时为 0；核验不完整不出具本合同）。</> : <>年度参考保费：<strong className="premium-amount">{money(plan.annual_reference_premium_cents)}</strong>；年度纯风险成本：{money(plan.annual_pure_risk_cost_cents)}。</>}</p>
      {kind === 'sample' ? <p>样本：{sample?.sampleSize ?? 0} 条运行、已核定正赔款事件 {sample?.eventCount ?? 0} 件、样本频率 {sample && sample.frequency !== null ? `${(sample.frequency * 100).toFixed(2)}%` : '—'}、平均单次赔款 {sample && sample.meanSeverityCents !== null ? money(sample.meanSeverityCents) : '—'}、附加比例 {(Number(scenario.premium_loading_ratio) * 100).toFixed(2)}%。</p>
        : <p>假设：年度任务 {scenario.annual_agent_task_volume.toLocaleString('zh-CN')} 项、各类事故概率 {(Number(scenario.categories[0].accident_probability) * 100).toFixed(2)}%、平均事故损失 {money(scenario.categories[0].average_accident_loss_cents)}、附加比例 {(Number(scenario.premium_loading_ratio) * 100).toFixed(2)}%。</p>}
      <p>保费公式：{kind === 'sample' ? 'P =（1 + 附加比例）× 年度任务量 ×（已核定正赔款事件数 ÷ 样本量）× 平均单次赔款' : scenario.premium_formula}。</p></section>
    <section className="contract-declaration"><h3>九、模拟研究声明</h3><p>本合同仅用于AgentShield研究演示，不构成正式保险要约、承保承诺、商业报价、电子保单或赔付决定；不接入保险公司、支付或电子签章。真正经验定价状态：尚不可用。{kind === 'sample' ? `样本外推参考保费基于小样本均值与频率，样本量有限（当前 ${sample?.sampleSize ?? 0} 条），不代表长期经验赔付水平。${sample && sample.sampleSize <= 1 ? '样本量仅 1 条：该数字为研究性单样本估算，不代表年度零风险，也不构成经验费率或商业报价。' : ''}` : ''}</p></section>
    <footer><span>模拟投保人：________________</span><span>研究项目：________________</span><span>日期：________________</span></footer>
  </article>;
}

function AdviceCard({ advice }: { advice: InsuranceAdvice }) {
  const badge = advice.kind === 'no_need' ? '无需投保' : advice.kind === 'evaluate' ? '建议评估' : '数据不足';
  return <article className={`advice-card advice-${advice.kind}`} data-testid="insurance-advice" role="status">
    <div className="advice-head"><h3>AgentShield 保险配置建议</h3><Badge tone={advice.kind === 'evaluate' ? 'warning' : ''}>{badge}</Badge></div>
    <p className="advice-title">{advice.title}</p>
    <p className="fine-print">{advice.detail}</p>
    <p className="fine-print">{advice.caveat}</p>
  </article>;
}

function InsurancePlans({ runs, scenario, scenarioState, scenarioError, onRetryScenario, details, batchId, mode, onRetryDetails }: {
  runs: IntegrationRunSummary[]; scenario: ResearchScenario | null; scenarioState: LoadState; scenarioError: string;
  onRetryScenario: () => void; details: Record<string, DetailSlot>; batchId: string | null; mode: ModeId;
  onRetryDetails: (runIds: string[]) => void;
}) {
  const [contractProduct, setContractProduct] = useState<ResearchPlan['product_id'] | null>(null);
  const [sampleContractProduct, setSampleContractProduct] = useState<ResearchPlan['product_id'] | null>(null);
  if (scenario === null && scenarioState === 'error') return <div className="empty error" role="alert"><strong>研究情景未能读取</strong><p>{scenarioError}</p><button onClick={onRetryScenario}>重试读取研究情景</button></div>;
  if (scenario === null) return <div className="loading" role="status"><span className="spinner"/>正在计算研究保险方案…</div>;
  const readyDetails = runs.map(run => details[run.run_id]).filter((slot): slot is DetailSlot => slot !== undefined && slot.state === 'ready' && slot.detail !== null).map(slot => slot.detail!);
  const failedIds = runs.filter(run => details[run.run_id]?.state === 'error').map(run => run.run_id);
  // 「保险配置建议」= 复用第二页同源核验统计（同一 summarizeRealBatch 映射）；真实模式专用，明细未载全时保持「无法建议」。
  const adviceRows: RealBatchRow[] = readyDetails.map(detail => ({
    runId: detail.summary.run_id, runStatus: detail.summary.run_status ?? null, taskOutcome: detail.summary.task_outcome ?? null,
    lossStatus: detail.loss_result.loss_status, netLossCents: detail.loss_result.net_loss_cents,
    claimStatus: detail.claim.claim_status, payoutCents: detail.claim.payout_cents,
  }));
  const advice: InsuranceAdvice | null = mode !== 'real' ? null
    : readyDetails.length === runs.length
      ? insuranceAdviceFrom(summarizeRealBatch(adviceRows))
      : { kind: 'insufficient', title: '暂无法形成保险配置建议',
          detail: `核验明细尚未全部载入（${readyDetails.length}/${runs.length} 条），载入完成后再评估。`,
          caveat: '不将未核验金额当作 0。' };
  const sampleRows = (productId: ResearchPlan['product_id']) => readyDetails.map(detail => {
    const row = detail.p0_claim_comparison?.claims.find(item => item.product_id === productId);
    if (!row) return { lossStatus: detail.loss_result.loss_status, claimStatus: detail.claim.claim_status, payoutCents: null as number | null };
    return { lossStatus: row.loss_status, claimStatus: row.claim_status, payoutCents: row.payout_cents };
  });
  if (mode === 'real' && sampleContractProduct !== null) {
    const chosen = scenario.plans.find(item => item.product_id === sampleContractProduct) ?? null;
    const result = chosen ? extrapolatePremium(sampleRows(chosen.product_id), { annualTaskVolume: scenario.annual_agent_task_volume, loadingRatio: Number(scenario.premium_loading_ratio) }) : null;
    if (chosen && result && result.status === 'ok' && result.premiumCents !== null) return <InsuranceContract scenario={scenario} plan={chosen} onClose={() => setSampleContractProduct(null)} kind="sample" sample={result} batchId={batchId}/>;
  }
  const generated = scenario.plans.find(plan => plan.product_id === contractProduct) ?? null;
  if (generated) return <InsuranceContract scenario={scenario} plan={generated} onClose={() => setContractProduct(null)}/>;
  const p0Sample = readyDetails.find(detail => detail.p0_claim_comparison !== null) ?? null;
  return <section className="plan-section" aria-label="保险方案">
    <div className="verdict"><h2>{mode === 'real' ? '样本外推参考保费（研究）' : '年度研究保险方案'}</h2><p>{mode === 'real' ? '按当前批次 A 已核定的 Core / Plus 单事件赔款做小样本外推；核验不完整或保险责任未确定时保持数据不足。' : '两档参考保费均由同一研究情景和A-P0单次理赔公式计算；真正经验定价尚不可用。'}</p></div>
    <p className="mode-banner" role="status">模式：{mode === 'real' ? '真实 Agent 实测' : '研究情景演示'} · {batchId === null ? '尚未运行本机批次' : `当前批次 ${batchId}`}</p>
    {mode === 'real' && advice && <AdviceCard advice={advice}/>}
    {mode === 'real' && <>
      <div className="plan-grid">{scenario.plans.map(plan => {
        const result = extrapolatePremium(sampleRows(plan.product_id), { annualTaskVolume: scenario.annual_agent_task_volume, loadingRatio: Number(scenario.premium_loading_ratio) });
        return <article className="plan-card" key={plan.product_id}>
          <div className="plan-title-row"><h2>{plan.display_name}</h2><span className="plan-tag">{plan.product_id.replace('AgentShield-', '')} · 样本外推</span></div>
          <dl>
            <div><dt>样本外推参考保费</dt><dd>{result.status === 'ok' && result.premiumCents !== null ? <strong className="money premium-amount">{money(result.premiumCents)}</strong> : <Badge tone="warning">数据不足</Badge>}<small className="cell-note">小样本外推 · 非商业报价。</small></dd></div>
            <div><dt>样本量 / 已核定事件</dt><dd>{result.sampleSize} 条 / {result.eventCount} 件</dd></div>
            <div><dt>样本事故频率</dt><dd>{result.frequency === null ? '—' : `${(result.frequency * 100).toFixed(2)}%`}</dd></div>
            <div><dt>平均单次赔款</dt><dd>{result.meanSeverityCents === null ? '—' : money(result.meanSeverityCents)}</dd></div>
          </dl>
          {result.sampleSize <= 1 && <p className="fine-print">样本量仅 {result.sampleSize} 条 · 研究性估算：{result.eventCount === 0 ? '本样本无已核定正赔款事件，¥0.00 不代表年度零风险；' : ''}不构成经验费率或商业报价。</p>}
          {result.status !== 'ok' && <ul className="fine-print real-reasons">{result.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
          <button className="primary-run contract-generate" disabled={result.status !== 'ok'} onClick={() => setSampleContractProduct(plan.product_id)}>{result.status === 'ok' ? `生成${plan.product_id === 'AgentShield-Core' ? 'Core' : 'Plus'}样本外推参考合同` : '数据不足 · 不能生成合同'}</button>
          <p className="plan-badges"><Badge tone="warning">样本外推 · 研究用途</Badge> <Badge tone="warning">非商业报价</Badge></p>
        </article>;
      })}</div>
      <p className="fine-print">外推公式：P =（1 + 附加比例）× 年度任务量 ×（已核定正赔款事件数 ÷ 样本量）× 平均单次赔款；全部有效核验且赔款均为 0 时，样本参考保费为 0；核验不完整时不给出数字。</p>
    </>}
    {mode !== 'real' && <div className="plan-grid">{scenario.plans.map(plan => <ResearchPlanCard key={plan.product_id} plan={plan} onGenerate={() => setContractProduct(plan.product_id)}/>)}</div>}
    {p0Sample?.p0_claim_comparison && p0Sample.p0_products && <details className="fold-body engineering-sample">
      <summary>当前批次单条理赔状态（与研究情景定价分开）</summary>
      <p><strong>{p0Sample.summary.case_id}</strong> · <Badge tone="warning">{p0Sample.p0_claim_comparison.status === 'A_study_reviewed_zero_loss_not_formal_insurance_claim' ? '开发运行 · A 已研究审核' : '开发运行·待审'}</Badge></p>
      <dl>
        <div><dt>执行来源</dt><dd>{executionSourceLabel(p0Sample.summary.execution_source)} / {p0Sample.summary.provider}</dd></div>
        <div><dt>C 净损失</dt><dd>{p0Sample.p0_claim_comparison.net_loss_cents === null ? '待业务审核' : money(p0Sample.p0_claim_comparison.net_loss_cents)}</dd></div>
        <div><dt>保险责任</dt><dd>{p0Sample.p0_claim_comparison.coverage_status}</dd></div>
        <div><dt>A 审核记录</dt><dd>{p0Sample.p0_claim_comparison.A_study_coverage_review ? `${p0Sample.p0_claim_comparison.A_study_coverage_review.review_version} · 研究性（非正式理赔）` : '未记录（待审）'}</dd></div>
        <div><dt>商业报价</dt><dd>未生成（commercial_quote=false）</dd></div>
      </dl>
      <div className="engineering-grid">{p0Sample.p0_claim_comparison.claims.map(result => {
        const plan = p0Sample.p0_products?.plans.find(item => item.product_id === result.product_id);
        return <article className="plan-card" key={result.product_id}>
          <h3>{plan?.display_name ?? result.product_id}</h3>
          <p><Badge tone="warning">{result.claim_status}</Badge></p>
          <dl>
            <div><dt>单事件免赔</dt><dd>{money(result.deductible_cents)}</dd></div>
            <div><dt>赔付比例</dt><dd>{(result.coinsurance_bp / 100).toFixed(2)}%</dd></div>
            <div><dt>单事件限额</dt><dd>{money(result.occurrence_limit_cents)}</dd></div>
            <div><dt>研究赔款</dt><dd>{result.payout_cents === null ? '待审核' : money(result.payout_cents)}</dd></div>
          </dl>
          <p className="fine-print">年累计限额仅展示，未执行扣减；不是商业报价或已赔付结论。</p>
        </article>;
      })}</div>
    </details>}
    {failedIds.length > 0 && <p className="fine-print" role="alert">当前批次理赔记录读取失败：{failedIds.length} 条；研究情景方案仍可独立查看。<button className="text-button" onClick={() => onRetryDetails(failedIds)}>重试读取失败明细</button></p>}
  </section>;
}

function decimalCents(value: string | null) {
  if (value === null || !Number.isFinite(Number(value))) return '不可用';
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(Number(value) / 100);
}

type LedgerSlot = { state: 'loading' | 'ready' | 'error'; committedCents: number | null; tradeCount: number | null };
type LossSlot = { state: 'loading' | 'ready' | 'error'; netLossCents: number | null; legalDue: number | null; payoutCents: number | null };
type DetailSlot = { state: 'loading' | 'ready' | 'error'; detail: IntegrationRunDetail | null };
const idleBatch = (): BScaleBatchStatus => ({ status: 'idle', batch_id: null, seed: null, total: 100, completed: 0,
  normal_refund: 0, manual_review: 0, failed: 0, total_refund_cents: 0, selected_task_ids: [], unique_count: 0,
  paid_model_calls: 0, error_code: null });

/** C 义务口径候选应退：仅当每条义务都带合法应退金额时求和；否则 null（待核验），不补零。 */
function legalDueSum(obligations: unknown[]): number | null {
  if (obligations.length === 0) return null;
  let sum = 0;
  for (const item of obligations) {
    const value = (item as { legally_due_cents?: unknown } | null)?.legally_due_cents;
    if (typeof value !== 'number' || !Number.isSafeInteger(value)) return null;
    sum += value;
  }
  return sum;
}

function NewTestPanel({ open, onToggle, configs, selected, onSelect, batch, onStart, mode, onMode, realRun, onStartRealRun }: {
  open: boolean; onToggle: () => void; configs: RunnerConfig[] | null; selected: string; onSelect: (value: string) => void;
  batch: BScaleBatchStatus; onStart: () => void; mode: ModeId; onMode: (value: ModeId) => void;
  realRun: RealRunStatus | null; onStartRealRun: (count: number) => void;
}) {
  const freeConfigs = configs?.filter(config => config.adapter === 'rule_baseline') ?? null;
  const current = freeConfigs?.find(config => config.config_id === selected) ?? null;
  const running = batch.status === 'queued' || batch.status === 'running';
  return <section className="new-test" aria-label="新建一次测试">
    <button className="new-test-toggle" data-testid="new-test-toggle" aria-expanded={open} onClick={onToggle}>＋新建一次测试</button>
    {open && <div className="new-test-panel">
      <div className="mode-switch" role="radiogroup" aria-label="执行模式">
        <button type="button" role="radio" aria-checked={mode === 'demo'} data-testid="mode-demo" className={mode === 'demo' ? 'mode-option active' : 'mode-option'} onClick={() => onMode('demo')}>研究情景演示</button>
        <button type="button" role="radio" aria-checked={mode === 'real'} data-testid="mode-real" className={mode === 'real' ? 'mode-option active' : 'mode-option'} onClick={() => onMode('real')}>真实 Agent 实测</button>
      </div>
      {mode === 'demo' && <>
      <label className="agent-pick"><span>执行器（仅免费规则基线）</span>
        <select id="agent-config" aria-label="选择 Agent 配置" value={selected} disabled={configs === null} onChange={event => onSelect(event.target.value)}>
          {freeConfigs === null ? <option value="">正在读取已注册配置…</option> : freeConfigs.map(config => <option key={config.config_id} value={config.config_id}>{agentConfigLabel(config)}</option>)}
        </select></label>
      {current && <p className="fine-print">来源 {current.source_path} · {current.frozen ? '已冻结' : '未冻结'} · 单次成本上限（配置）{current.max_run_cost_cny === null ? '—' : `¥${current.max_run_cost_cny.toFixed(2)}`}</p>}
      <button className="primary-run" id="sample-run" data-testid="sample-run" disabled={running || current === null} onClick={onStart} aria-describedby="sample-run-note">随机抽取100项并运行</button>
      <p className="fine-print" id="sample-run-note">仅运行免费确定性规则基线；不会调用真实模型或产生 API 费用。同一时间只允许一个批次。</p>
      {running && <div className="batch-progress" role="status" aria-live="polite"><progress value={batch.completed} max={batch.total}/><strong>已完成 {batch.completed}/{batch.total}</strong><span>正常退款 {batch.normal_refund} · 转人工 {batch.manual_review} · 失败 {batch.failed}</span></div>}
      {batch.status === 'completed' && <div className="batch-progress batch-complete" role="status"><strong>本批次已完成 {batch.completed}/{batch.total}</strong><span>正常退款 {batch.normal_refund} · 转人工 {batch.manual_review} · 失败 {batch.failed} · 退款总额 {money(batch.total_refund_cents)}</span></div>}
      {batch.status === 'failed' && <p className="notice error" role="alert">批次执行失败；已完成记录仍保留，请检查本机服务日志。</p>}
      <p className="fine-print">抽样与执行由后端负责（总体版本、随机种子、任务 ID、批次与类别随记录落盘）；普通界面不提供事项类别或具体案例的手动选择。</p>
      </>}
      {mode === 'real' && <div className="real-panel" data-testid="real-panel">
        <p className="fine-print">执行器：deepseek / deepseek-flash（配置 c-deepseek-flash-fixed-dev-v0.1 · 未冻结）。真实调用由本机后端 Runner 子进程在预算批准范围内发起；前端绝不直连模型、不持有 API Key。</p>
        {realRun === null ? <p className="fine-print">正在读取真实运行状态…</p> : <>
          <p className="fine-print" data-testid="real-run-budget">预算：本阶段批准上限 {realRun.authorization.approval_cap_cny === null ? '未批准' : `¥${realRun.authorization.approval_cap_cny.toFixed(2)}`} · 单次硬顶 {`¥${realRun.authorization.per_run_cap_cny.toFixed(2)}`} · 本机历史付费合计 {realRun.authorization.prior_paid_known ? `¥${realRun.authorization.prior_paid_cny.toFixed(6)}` : '未知'}</p>
          <div className="real-actions">
            <button className="primary-run" id="real-run-one" data-testid="real-run-one" disabled={!canStartRealRun(realRun)} aria-describedby="real-run-note" onClick={() => onStartRealRun(1)}>运行 1 条（单条贯通）</button>
            <button className="primary-run" id="real-run-batch" data-testid="real-run-batch" disabled={!canStartRealRun(realRun)} aria-describedby="real-run-note" onClick={() => onStartRealRun(5)}>运行小批量（5 条）</button>
            <button className="primary-run" id="real-run-hundred" disabled title="扩展目标：需单独批准预算并按每批 10 条生成 Gold；本轮不执行。">运行 100 条（扩展目标）</button>
          </div>
          {realRunDisabledReasons(realRun).length > 0 && <ul className="fine-print" id="real-run-note" data-testid="real-run-note">
            {realRunDisabledReasons(realRun).map(reason => <li key={reason}>{reason}</li>)}
          </ul>}
          {realRunBusy(realRun) && <div className="batch-progress" role="status" aria-live="polite"><progress value={realRun.runs.length} max={realRun.count ?? 1}/><strong>{realRunStageLabel(realRun.stage)} · 已完成 {realRun.runs.length}/{realRun.count ?? '—'}</strong><span>批次 {realRun.batch_id ?? '分配中'} · 随机种子与任务 ID 由后端记录</span></div>}
          {realRun.status === 'completed' && <div className="batch-progress batch-complete" role="status"><strong>真实批次已完成 {realRun.runs.length}/{realRun.count}</strong><span>批次 {realRun.batch_id} · 已自动接入 A 自动 Gold 核验；结果贯穿第二、三页</span>{realRun.runs.map(row => <span key={row.label}>{row.label}：{row.run_status ?? '—'} · 核验 {row.loss_status ?? '—'} · 赔款认定由 A 线下审查</span>)}</div>}
          {realRun.status === 'failed' && <p className="notice error" role="alert">真实批次失败（{realRun.error_code ?? '未知原因'}）；已完成记录保留，请查看本机日志。</p>}
        </>}
        <p className="fine-print">执行顺序：先运行 1 条贯穿三页，再扩到小批量；批次 ID 与随机种子由后端记录并贯穿第一、二、三页。新案例保险责任由 A 线下审查；未确定前第三页显示「数据不足」，不冒充 0。</p>
      </div>}
    </div>}
  </section>;
}

function TestRecordList({ sessions, runs, batchId, selected, onSelect, tab, onTab, ledgerBySession, lossByRun, onRetryDetails }: {
  sessions: SessionStatus[]; runs: IntegrationRunSummary[]; selected: string; onSelect: (sid: string) => void;
  batchId: string | null; tab: 'batch' | 'local' | 'history'; onTab: (tab: 'batch' | 'local' | 'history') => void;
  ledgerBySession: Record<string, LedgerSlot>; lossByRun: Record<string, LossSlot>; onRetryDetails: (runIds: string[]) => void;
}) {
  const ledgerCell = (slot: LedgerSlot | undefined) => slot === undefined || slot.state === 'loading'
    ? <span className="cell-note">读取中…</span>
    : slot.state === 'error' ? <span className="cell-note">读取失败</span>
    : <><strong className="money">{money(slot.committedCents ?? 0)}</strong><span className="cell-note">{slot.tradeCount} 笔交易</span></>;
  const localRows = sessions.map(session => {
    const display = caseDisplay(session.case_id);
    return <tr key={session.session_id} data-sid={session.session_id} className={selected === session.session_id ? 'selected' : ''}>
      <td><strong>{display.name}</strong><span className="cell-note">{session.case_id}</span></td>
      <td><Badge>{session.status === 'finished' ? '已结束' : '未运行'}</Badge><span className="cell-note">{session.config_id ?? '未指定配置'} · 本机开发会话</span></td>
      <td className="number">{ledgerCell(ledgerBySession[session.session_id])}</td>
      <td className="number"><span className="cell-note">未接入</span></td>
      <td className="number"><span className="cell-note">未接入</span></td>
      <td className="number"><span className="cell-note">未接入</span></td>
      <td><button className="text-button" onClick={() => onSelect(session.session_id)}>详情</button></td>
    </tr>;
  });
  const batchRuns = batchId === null ? [] : runs.filter(run => run.batch_id === batchId);
  const previousRuns = batchId === null ? runs : runs.filter(run => run.batch_id !== batchId);
  const integrationRows = (items: IntegrationRunSummary[]) => items.map(run => {
    const display = caseDisplay(run.case_id);
    const slot = lossByRun[run.run_id];
    let dueCell: ReactNode; let lossCell: ReactNode; let claimCell: ReactNode;
    if (slot === undefined || slot.state === 'loading') {
      const loading = <span className="cell-note">读取中…</span>;
      dueCell = loading; lossCell = loading; claimCell = loading;
    } else if (slot.state === 'error') {
      const failed = <span className="cell-note">读取失败</span>;
      dueCell = failed; lossCell = failed; claimCell = failed;
    } else {
      dueCell = slot.legalDue === null ? <Badge tone="warning">待核验</Badge> : <><strong className="money">{money(slot.legalDue)}</strong><span className="cell-note">C 义务口径 · 待审</span></>;
      lossCell = slot.netLossCents === null ? <Badge tone="warning">待核验 / null</Badge> : <strong className="money">{money(slot.netLossCents)}</strong>;
      claimCell = slot.payoutCents === null ? <Badge tone="warning">待审核 / null</Badge> : <strong className="money">{money(slot.payoutCents)}</strong>;
    }
    return <tr key={run.run_id} data-sid={run.session_id} className={selected === run.session_id ? 'selected' : ''}>
      <td><strong>{display.name}</strong><span className="cell-note">{run.case_id} · {run.label}</span></td>
      <td><Badge tone={run.execution_source === 'observed_agent_execution' ? 'good' : ''}>{executionSourceLabel(run.execution_source)}</Badge><span className="cell-note">{run.provider ? `${run.provider} / ${run.model ?? '—'}` : '无模型调用'} · {run.run_status === 'finished' ? '已结束' : run.run_status}{run.task_outcome ? ` · ${run.task_outcome}` : ''}</span></td>
      <td className="number"><strong className="money">{money(run.total_committed_cents)}</strong><span className="cell-note">B 账本事实</span></td>
      <td className="number">{dueCell}</td>
      <td className="number">{lossCell}</td>
      <td className="number">{claimCell}</td>
      <td><button className="text-button" onClick={() => onSelect(run.session_id)}>详情</button></td>
    </tr>;
  });
  const table = (rows: ReactNode[]) => <div className="table-scroll"><table className="rec-table"><thead><tr>
    <th>业务事项</th><th>Agent / 运行状态</th><th className="number">已提交退款（B）</th><th className="number">候选应退（C）</th><th className="number">核验净损失（C）</th><th className="number">研究赔款（A）</th><th>操作</th>
  </tr></thead><tbody>{rows}</tbody></table></div>;
  return <section className="result-list" aria-label="测试记录">
    <div className="list-tabs" role="tablist" aria-label="测试记录分组">
      {batchId !== null && <button role="tab" aria-selected={tab === 'batch'} className={tab === 'batch' ? 'list-tab active' : 'list-tab'} onClick={() => onTab('batch')}>当前批次（{batchRuns.length}）</button>}
      <button role="tab" aria-selected={tab === 'local'} className={tab === 'local' ? 'list-tab active' : 'list-tab'} onClick={() => onTab('local')}>本机测试记录（{sessions.length}）</button>
      <button role="tab" aria-selected={tab === 'history'} className={tab === 'history' ? 'list-tab active' : 'list-tab'} onClick={() => onTab('history')}>历史测试（{previousRuns.length}）</button>
    </div>
    {tab === 'batch'
      ? (batchRuns.length === 0
        ? <p className="list-empty">当前批次正在运行；完成后将在这里显示本批次的实际运行记录。</p>
        : table(integrationRows(batchRuns)))
      : tab === 'local'
      ? (sessions.length === 0
        ? <p className="list-empty">本机还没有单独创建的开发会话。</p>
        : table(localRows))
      : (previousRuns.length === 0
        ? <p className="list-empty">交付目录中还没有已交付运行。</p>
        : table(integrationRows(previousRuns)))}
    {Object.entries(lossByRun).some(([, slot]) => slot.state === 'error') && <p className="fine-print" role="alert">部分明细读取失败。<button className="text-button" onClick={() => onRetryDetails(Object.keys(lossByRun).filter(id => lossByRun[id].state === 'error'))}>重试读取失败明细</button></p>}
    <p className="fine-print">「当前批次」只包含本次随机抽取结果；「历史测试」保留其他已交付开发运行。保险赔款与商户退款是两个概念，金额均按各自口径标注。</p>
  </section>;
}

export default function App() {
  const [area, setArea] = useState<Area>(() => parseViewState(window.location.hash).area ?? 'test');
  const [fixtures, setFixtures] = useState<FixtureCatalog['fixtures']>([]);
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [sid, setSid] = useState('');
  const [focusedOrder, setFocusedOrder] = useState<string | null>(null);
  const [fixtureId, setFixtureId] = useState<FixtureCatalog['fixtures'][number]['fixture_id']>('dev-refund-v1');
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [creating, setCreating] = useState(false);
  const [catalogReady, setCatalogReady] = useState(false);
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [offline, setOffline] = useState(false);
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [routeNotice, setRouteNotice] = useState('');
  const [navBack, setNavBack] = useState<Area | null>(null);
  const [integrationRuns, setIntegrationRuns] = useState<IntegrationRunSummary[]>([]);
  const [integrationId, setIntegrationId] = useState('');
  const [integration, setIntegration] = useState<IntegrationRunDetail | null>(null);
  const [integrationState, setIntegrationState] = useState<LoadState>('loading');
  const [integrationError, setIntegrationError] = useState('');
  const [integrationRefresh, setIntegrationRefresh] = useState(0);
  const [replaySource, setReplaySource] = useState<'file' | 'delivery'>('file');
  const [newTestOpen, setNewTestOpen] = useState(true);
  const [runnerConfigs, setRunnerConfigs] = useState<RunnerConfig[] | null>(null);
  const [agentConfigId, setAgentConfigId] = useState('');
  const [researchScenario, setResearchScenario] = useState<ResearchScenario | null>(null);
  const [scenarioState, setScenarioState] = useState<LoadState>('loading');
  const [scenarioError, setScenarioError] = useState('');
  const [listTab, setListTab] = useState<'batch' | 'local' | 'history'>('history');
  const [batchStatus, setBatchStatus] = useState<BScaleBatchStatus>(idleBatch);
  const [realRun, setRealRun] = useState<RealRunStatus | null>(null);
  const [mode, setMode] = useState<ModeId>(() => parseViewState(window.location.hash).mode ?? 'demo');
  const [ledgerBySession, setLedgerBySession] = useState<Record<string, LedgerSlot>>({});
  const [runDetails, setRunDetails] = useState<Record<string, DetailSlot>>({});
  const fileReplay = offline && replaySource === 'file';
  const [evidenceOpen, setEvidenceOpen] = useState(() => parseViewState(window.location.hash).evidenceFocus);
  const input = useRef<HTMLInputElement>(null);
  const selection = useRef('');
  const replayMode = useRef(false);
  const interaction = useRef(0);
  const pendingRun = useRef<string | null>(parseViewState(window.location.hash).run);
  /** 页面自动选定的“入口默认运行”sid：只有这一次自动落地不展开证据；其余选择（用户切换/深链接/新建）按主动操作处理。 */
  const defaultLanding = useRef<string | null>(null);
  const currentIntent = (epoch: number) => interaction.current === epoch;
  selection.current = sid;

  async function catalog(epoch: number) {
    const [f, list, delivered] = await Promise.all([api<FixtureCatalog>('api/fixtures'), api<SessionPage>('api/sessions'), api<unknown>('api/integration-runs')]);
    const integrated = parseIntegrationCatalog(delivered);
    if (currentIntent(epoch) && !replayMode.current) {
      setFixtures(f.fixtures); setSessions(list.sessions); setIntegrationRuns(integrated);
      setIntegrationId(current => integrated.some(row => row.run_id === current) ? current : integrated[0]?.run_id ?? ''); setCatalogReady(true);
    }
    return { sessions: list.sessions, integrated };
  }
  useEffect(() => {
    let active = true; const epoch = interaction.current;
    (async () => { try { await pairFromFragment(); const { sessions: list, integrated } = await catalog(epoch);
      const batch = parseBScaleBatchStatus(await api<unknown>('api/bscale-batches/current'));
      const realStatus = parseRealRunStatus(await api<unknown>('api/real-runs/current'));
      if (!active || !currentIntent(epoch) || replayMode.current) return;
      setBatchStatus(batch); setRealRun(realStatus); if (batch.batch_id !== null) setListTab('batch');
      if (list.length || integrated.length) {
        const wanted = pendingRun.current;
        pendingRun.current = null;
        const restored = wanted ? list.find(row => row.session_id === wanted) : undefined;
        const deliveredWanted = wanted && !restored && integrated.some(row => row.session_id === wanted);
        if (wanted && !restored && !deliveredWanted) setRouteNotice(`URL 中的运行（…${wanted.slice(-8)}）不在当前目录或已不可用；已回退到默认选择。`);
        const nextSid = restored?.session_id
          ?? (deliveredWanted ? wanted as string : undefined)
          ?? integrated.find(row => row.execution_source === 'observed_agent_execution')?.session_id
          ?? list.find(row => row.case_id === 'dev-case-refund-v1')?.session_id
          ?? list[0]?.session_id
          ?? integrated[0]?.session_id
          ?? '';
        setSid(nextSid);
        defaultLanding.current = wanted ? null : nextSid;
        if (!nextSid) setState('ready');
      }
      else {
        if (pendingRun.current) { setRouteNotice('URL 中的运行不在当前目录或已不可用。'); pendingRun.current = null; }
        setState('ready');
      }
    } catch (e) { if (active && currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } } })();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!integrationId) { setIntegration(null); setIntegrationState('ready'); return; }
    const controller = new AbortController(); setIntegrationState('loading'); setIntegrationError('');
    (async () => { try {
      const raw = await api<unknown>(`api/integration-runs/${integrationId}`, { signal: controller.signal });
      const result = parseIntegrationDetail(raw);
      const evidence = parseEvidence(result.evidence, result.summary.session_id);
      if (evidence.final_snapshot.session.episode_id !== result.summary.episode_id) throw new Error('A/C 结果与 B 证据的 episode 不一致。');
      if (!controller.signal.aborted) { setIntegration({ ...result, evidence }); setIntegrationState('ready'); }
    } catch (e) { if (!controller.signal.aborted) { setIntegration(null); setIntegrationError(errorText(e)); setIntegrationState('error'); } } })();
    return () => controller.abort();
  }, [integrationId, integrationRefresh]);

  useEffect(() => {
    const match = integrationRuns.find(row => row.session_id === sid);
    if (match) setIntegrationId(match.run_id);
  }, [sid, integrationRuns]);

  useEffect(() => {
    if (!sid || offline || !catalogReady || replayMode.current) return;
    if (sessions.some(row => row.session_id === sid)) return;
    const delivered = integrationRuns.find(row => row.session_id === sid);
    if (!delivered) return;
    const epoch = ++interaction.current;
    const initialLanding = defaultLanding.current === sid;
    if (initialLanding) defaultLanding.current = null;
    setState('loading'); setError(''); setBundle(null); setEvents([]);
    (async () => { try {
      const raw = await api<unknown>(`api/integration-runs/${delivered.run_id}`);
      const result = parseIntegrationDetail(raw);
      if (!currentIntent(epoch) || replayMode.current) return;
      const evidence = parseEvidence(result.evidence, result.summary.session_id);
      if (evidence.final_snapshot.session.episode_id !== result.summary.episode_id) throw new Error('A/C 结果与 B 证据的 episode 不一致。');
      replayMode.current = true; setOffline(true); setReplaySource('delivery');
      setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setActionError('');
      if (!initialLanding) {
        setNavBack(area !== 'test' ? area : null); setArea('test');
        setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
      }
    } catch (e) { if (currentIntent(epoch)) { setActionError(errorText(e)); setState('ready'); } } })();
  }, [sid, sessions, integrationRuns, catalogReady, offline, area]);

  useEffect(() => {
    if (!sid || offline) return;
    if (catalogReady && !sessions.some(row => row.session_id === sid) && integrationRuns.some(row => row.session_id === sid)) return;
    const controller = new AbortController(); const epoch = interaction.current;
    setState('loading'); setError(''); setBundle(null); setEvents([]);
    (async () => { try {
      const [raw, page, ledger] = await Promise.all([
        api<unknown>(`api/sessions/${sid}/evidence`, { signal: controller.signal }),
        api<EventPage>(`api/sessions/${sid}/events?limit=100`, { signal: controller.signal }),
        api<Ledger>(`api/sessions/${sid}/ledger`, { signal: controller.signal }),
      ]);
      const evidence = parseEvidence(raw, sid);
      if (JSON.stringify(evidence.ledger) !== JSON.stringify(ledger.entries)
          || page.events.some(row => !evidence.events.some(item => JSON.stringify(item) === JSON.stringify(row))))
        throw new Error('运行在读取期间发生变化或接口事实不一致，请刷新获取一致快照。');
      if (controller.signal.aborted || !currentIntent(epoch) || replayMode.current) return;
      setBundle(evidence); setEvents(orderedEvents(page.events)); setState('ready');
    } catch (e) { if (!controller.signal.aborted && currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } } })();
    return () => controller.abort();
  }, [sid, offline, refresh]);

  useEffect(() => {
    document.querySelector('main')?.scrollTo(0, 0);
  }, [area]);

  useEffect(() => {
    const next = buildViewHash(area, sid || null, offline, mode);
    if (window.location.hash !== next) history.replaceState(null, '', window.location.pathname + window.location.search + next);
  }, [area, sid, offline, mode]);

  useEffect(() => {
    const onPop = () => {
      const view = parseViewState(window.location.hash);
      if (view.area) setArea(view.area);
      if (!replayMode.current) setMode(view.mode ?? 'demo');
      if (replayMode.current) return;
      if (view.run && view.run !== selection.current) {
        if (sessions.some(row => row.session_id === view.run) || integrationRuns.some(row => row.session_id === view.run)) { ++interaction.current; setFocusedOrder(null); setSid(view.run); defaultLanding.current = null; setRouteNotice(''); }
        else setRouteNotice('URL 中的运行不在当前目录或已不可用；当前选择保持不变。');
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [sessions, integrationRuns]);
  useEffect(() => {
    if (fileReplay) return;
    let active = true;
    loadRunnerConfigs()
      .then(list => { if (active) { setRunnerConfigs(list); setAgentConfigId((list.find(config => config.adapter === 'rule_baseline')?.config_id ?? '')); } })
      .catch(() => { if (active) setRunnerConfigs([]); });
    return () => { active = false; };
  }, [fileReplay]);
  const scenarioLoadEpoch = useRef(0);
  async function loadScenario() {
    // 观察授权由首次目录加载兑换完成；失败自动重试（0.6s/1.2s 退避），仍失败则进入显式错误态（可手动重试），不再静默转圈。
    const epoch = ++scenarioLoadEpoch.current;
    setScenarioState('loading'); setScenarioError('');
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const raw = await api<unknown>('api/research-scenario');
        if (scenarioLoadEpoch.current !== epoch) return;
        setResearchScenario(parseResearchScenario(raw)); setScenarioState('ready'); return;
      } catch (e) {
        if (scenarioLoadEpoch.current !== epoch) return;
        if (attempt < 2) await new Promise(resolve => { window.setTimeout(resolve, 600 * (attempt + 1)); });
        else { setScenarioError(errorText(e)); setScenarioState('error'); }
      }
    }
  }
  useEffect(() => {
    // 不在 pairing 兑换完成前发起（快速 401 曾让风险/保险页一直转圈）；失败可重试。
    if (fileReplay || !catalogReady) return;
    void loadScenario();
    return () => { scenarioLoadEpoch.current += 1; };
  }, [fileReplay, catalogReady]);
  useEffect(() => {
    if (!['queued', 'running'].includes(batchStatus.status)) return;
    let active = true;
    let timer = 0;
    const poll = async () => {
      try {
        const next = parseBScaleBatchStatus(await api<unknown>('api/bscale-batches/current'));
        if (!active) return;
        if (next.status === 'completed' && next.batch_id !== null) {
          // 先取权威目录、再更新批次状态：setBatchStatus 会改变本 effect 依赖并清理旧的 active，
          // 若在两次 await 之间触发，回填会在 `if (!active)` 处自我取消——这是“批次完成后页面不刷新、看似卡住”的真实根因。
          const catalog = parseIntegrationCatalog(await api<unknown>('api/integration-runs'));
          if (!active) return;
          setBatchStatus(next);
          setIntegrationRuns(catalog);
          setListTab('batch');
          const first = catalog.find(row => row.batch_id === next.batch_id);
          if (first) {
            ++interaction.current; replayMode.current = false; setOffline(false); setReplaySource('file');
            setBundle(null); setEvents([]); setSid(first.session_id); setArea('test'); setEvidenceOpen(false);
          }
        } else {
          setBatchStatus(next);
          if (next.status === 'queued' || next.status === 'running') {
            timer = window.setTimeout(() => { void poll(); }, 500);
          }
        }
      } catch (e) { if (active) setActionError(errorText(e)); }
    };
    timer = window.setTimeout(() => { void poll(); }, 500);
    return () => { active = false; window.clearTimeout(timer); };
  }, [batchStatus.status, batchStatus.batch_id]);
  useEffect(() => {
    if (!realRunBusy(realRun)) return;
    let active = true;
    let timer = 0;
    const poll = async () => {
      try {
        const next = parseRealRunStatus(await api<unknown>('api/real-runs/current'));
        if (!active) return;
        if (next.status === 'completed' && next.batch_id !== null) {
          // 与免费批次同理：先取权威目录、再更新状态，避免回填被 effect 清理自我取消。
          const catalog = parseIntegrationCatalog(await api<unknown>('api/integration-runs'));
          if (!active) return;
          setRealRun(next);
          setIntegrationRuns(catalog);
          setListTab('history');
        } else if (next.status === 'failed') {
          setRealRun(next);
        } else {
          setRealRun(next);
          timer = window.setTimeout(() => { void poll(); }, 1500);
        }
      } catch (error) {
        if (active) {
          setActionError(errorText(error));
          timer = window.setTimeout(() => { void poll(); }, 3000);
        }
      }
    };
    timer = window.setTimeout(() => { void poll(); }, 1200);
    return () => { active = false; window.clearTimeout(timer); };
  }, [realRun?.status, realRun?.batch_id]);
  useEffect(() => {
    if (fileReplay || !catalogReady) return;
    const pending = sessions.filter(row => !(row.session_id in ledgerBySession));
    if (pending.length === 0) return;
    pending.forEach(row => setLedgerBySession(map => row.session_id in map ? map : { ...map, [row.session_id]: { state: 'loading', committedCents: null, tradeCount: null } }));
    void (async () => {
      for (const row of pending) {
        try {
          const ledger = await api<Ledger>(`api/sessions/${row.session_id}/ledger`);
          const committed = ledger.entries.reduce((sum, entry) => sum + (-entry.merchant_delta_cents), 0);
          setLedgerBySession(map => ({ ...map, [row.session_id]: { state: 'ready', committedCents: committed, tradeCount: ledger.entries.length } }));
        } catch {
          setLedgerBySession(map => ({ ...map, [row.session_id]: { state: 'error', committedCents: null, tradeCount: null } }));
        }
      }
    })();
  }, [sessions, catalogReady, fileReplay, ledgerBySession]);
  const detailsEpoch = useRef(0);
  const detailsInFlight = useRef<Set<string>>(new Set());
  const runDetailsRef = useRef<Record<string, DetailSlot>>({});
  useEffect(() => { runDetailsRef.current = runDetails; }, [runDetails]);
  async function ensureRunDetails(runIds: string[]) {
    // 有界并发（6 路）+ 每条重试一次：避免上百条明细同时压垮本机服务引发 8 秒超时风暴；错误槽位保留可重试。
    const epoch = detailsEpoch.current;
    const queue = [...new Set(runIds)].filter(id => {
      const slot = runDetailsRef.current[id];
      return (slot === undefined || slot.state === 'error') && !detailsInFlight.current.has(id);
    });
    if (queue.length === 0) return;
    queue.forEach(id => detailsInFlight.current.add(id));
    setRunDetails(current => { const next = { ...current }; for (const id of queue) if (!next[id] || next[id].state === 'error') next[id] = { state: 'loading', detail: null }; return next; });
    const worker = async () => {
      for (;;) {
        const id = queue.shift();
        if (id === undefined) return;
        let slot: DetailSlot = { state: 'error', detail: null };
        for (let attempt = 0; attempt < 2; attempt += 1) {
          try { slot = { state: 'ready', detail: parseIntegrationDetail(await api<unknown>(`api/integration-runs/${id}`)) }; break; }
          catch { if (attempt === 0) await new Promise(resolve => { window.setTimeout(resolve, 500); }); }
        }
        detailsInFlight.current.delete(id);
        if (detailsEpoch.current !== epoch) return;
        runDetailsRef.current = { ...runDetailsRef.current, [id]: slot };
        setRunDetails(current => ({ ...current, [id]: slot }));
      }
    };
    await Promise.all(Array.from({ length: 6 }, () => worker()));
  }
  function retryRunDetails(runIds: string[]) { void ensureRunDetails(runIds); }
  useEffect(() => {
    if (fileReplay || !catalogReady || integrationRuns.length === 0) return;
    const missing = integrationRuns.map(row => row.run_id).filter(id => !(id in runDetailsRef.current));
    if (missing.length === 0) return;
    void ensureRunDetails(missing);
  }, [integrationRuns, catalogReady, fileReplay]);
  useEffect(() => () => { detailsEpoch.current += 1; }, []);
  useEffect(() => {
    if (sid === '') return;
    if (sessions.some(row => row.session_id === sid)) setListTab('local');
    else {
      const run = integrationRuns.find(row => row.session_id === sid);
      if (run) setListTab(batchStatus.batch_id !== null && run.batch_id === batchStatus.batch_id ? 'batch' : 'history');
    }
  }, [sid, sessions, integrationRuns, batchStatus.batch_id]);
  async function loadService(epoch: number, preferDelivered = true) {
    setState('loading'); setError('');
    try {
      const { sessions: list, integrated } = await catalog(epoch);
      if (!currentIntent(epoch) || replayMode.current) return;
      const wanted = pendingRun.current; pendingRun.current = null;
      const restored = wanted ? list.find(row => row.session_id === wanted) : undefined;
      const deliveredWanted = wanted && !restored && integrated.some(row => row.session_id === wanted);
      if (wanted && !restored && !deliveredWanted) setRouteNotice('URL 中的运行不在当前目录或已不可用。');
      const nextLocal = list.find(row => row.case_id === 'dev-case-refund-v1')?.session_id ?? list[0]?.session_id;
      const nextDelivered = integrated.find(row => row.execution_source === 'observed_agent_execution')?.session_id ?? integrated[0]?.session_id;
      const nextSid = restored?.session_id ?? (deliveredWanted ? wanted as string : undefined)
        ?? (preferDelivered ? (nextDelivered ?? nextLocal) : (nextLocal ?? nextDelivered)) ?? '';
      if (nextSid) { setSid(nextSid); defaultLanding.current = wanted ? null : nextSid; } else setState('ready');
    } catch (e) { if (currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } }
  }
  function retry() {
    const epoch = ++interaction.current;
    if (sid && catalogReady && !replayMode.current) { setRefresh(v => v + 1); return; }
    void loadService(epoch);
  }
  function returnToService() {
    const epoch = ++interaction.current; replayMode.current = false;
    setOffline(false); setReplaySource('file'); setBundle(null); setEvents([]); setSid(''); setCatalogReady(false); setActionError(''); setNavBack(null); setRouteNotice('');
    void loadService(epoch, false);
  }
  async function startBScaleBatch() {
    setActionError('');
    try {
      const started = parseBScaleBatchStatus(await api<unknown>('api/bscale-batches', { method: 'POST' }));
      setBatchStatus(started); setListTab('batch'); setNewTestOpen(true);
    } catch (e) { setActionError(errorText(e)); }
  }
  async function startRealRun(count: number) {
    setActionError('');
    try {
      setRealRun(parseRealRunStatus(await api<unknown>('api/real-runs', { method: 'POST', body: { count } })));
      setNewTestOpen(true);
    } catch (e) {
      const reasons = (e as { reasons?: string[] }).reasons;
      setActionError(errorText(e) + (Array.isArray(reasons) && reasons.length ? ' ' + reasons.join(' ') : ''));
      try { setRealRun(parseRealRunStatus(await api<unknown>('api/real-runs/current'))); } catch { /* 保留上次已知状态 */ }
    }
  }
  async function create() {
    const epoch = ++interaction.current;
    setCreating(true); setActionError('');
    try {
      const result = await api<{ session: SessionStatus }>('api/sessions', { method: 'POST', body: { fixture_id: fixtureId } });
      if (!currentIntent(epoch) || replayMode.current) return;
      await catalog(epoch);
      if (!currentIntent(epoch) || replayMode.current) return;
      setBundle(null); setSid(result.session.session_id); defaultLanding.current = null; setNavBack(null);
    } catch (e) {
      if (currentIntent(epoch) && !replayMode.current) setActionError(errorText(e) + ' 若创建响应丢失，会话可能已经建立；请刷新页面核对运行清单后再创建。');
    } finally { setCreating(false); }
  }
  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const element = event.target; const file = element.files?.[0]; if (!file) return;
    const epoch = ++interaction.current; element.value = ''; setActionError('');
    try {
      if (file.size > 5 * 1024 * 1024) throw new Error('回放文件超过 5 MiB，未读取。');
      const content = await file.text();
      if (!currentIntent(epoch)) return;
      const evidence = parseEvidence(JSON.parse(content));
      replayMode.current = true; setOffline(true); setReplaySource('file'); defaultLanding.current = null; setSid(evidence.final_snapshot.session.session_id); setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setActionError(''); setArea('test'); setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
    } catch (e) {
      if (currentIntent(epoch)) {
        setActionError(errorText(e));
        if (bundle) setState('ready'); else { setError('证据未能载入，请重新选择或重试本机读取。'); setState('error'); }
      }
    }
  }
  function saveReplay() {
    if (!bundle) return;
    const data = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(data); const anchor = document.createElement('a'); anchor.href = url;
    anchor.download = `evidence-${bundle.final_snapshot.session.session_id}.json`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function loadDeliveredEvidence() {
    if (!integration) return;
    const evidence = parseEvidence(integration.evidence, integration.summary.session_id);
    setNavBack(area !== 'test' ? area : null); ++interaction.current; replayMode.current = true; setOffline(true); setReplaySource('delivery'); defaultLanding.current = null; setSid(integration.summary.session_id);
    setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setActionError(''); setArea('test'); setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
  }
  const deliveredOptions = integrationRuns.filter(row => !sessions.some(item => item.session_id === row.session_id));
  function chooseRun(next: string) {
    if (!next || next === sid) return;
    ++interaction.current; replayMode.current = false; setFocusedOrder(null); setNavBack(null); setRouteNotice('');
    if (offline) { setOffline(false); setReplaySource('file'); }
    defaultLanding.current = null;
    setSid(next);
    history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(area, next, false, mode));
  }
  function showOrder(id: string) {
    if (area !== 'test') setNavBack(area);
    setFocusedOrder(id); setArea('test'); setEvidenceOpen(true);
    window.setTimeout(() => document.getElementById(`order-${id}`)?.scrollIntoView({ block: 'center', behavior: 'auto' }), 0);
  }
  const current = bundle?.final_snapshot.session.session_id === sid ? bundle : null;
  const session = current?.final_snapshot.session ?? sessions.find(row => row.session_id === sid);
  const matchedIntegration = integration && integration.summary.session_id === sid ? integration : null;
  const lossByRun = useMemo(() => {
    const derived: Record<string, LossSlot> = {};
    for (const [id, slot] of Object.entries(runDetails)) {
      derived[id] = slot.state === 'ready' && slot.detail
        ? { state: 'ready', netLossCents: slot.detail.loss_result.net_loss_cents, legalDue: legalDueSum(slot.detail.loss_result.obligations), payoutCents: slot.detail.claim.payout_cents }
        : { state: slot.state === 'error' ? 'error' : 'loading', netLossCents: null, legalDue: null, payoutCents: null };
    }
    return derived;
  }, [runDetails]);
  const currentBatchRuns = useMemo(
    () => batchStatus.batch_id === null ? integrationRuns : integrationRuns.filter(row => row.batch_id === batchStatus.batch_id),
    [batchStatus.batch_id, integrationRuns],
  );
  // 真实模式的批次来源与演示批次分开：优先约定前缀的真实批次，绝不被规则基线批次遮蔽、也不与历史混算。
  const realBatchId = useMemo(() => realBatchIdOf(integrationRuns), [integrationRuns]);
  const pageRuns = mode === 'real' ? integrationRuns.filter(row => row.batch_id === realBatchId) : currentBatchRuns;
  const pageBatchId = mode === 'real' ? realBatchId : batchStatus.batch_id;
  const integrationPending = !offline && !matchedIntegration && integrationRuns.some(row => row.session_id === sid) && integrationState !== 'error';
  const runName = session ? caseDisplay((current?.case_context as { fixture_id?: string } | null)?.fixture_id ?? session.case_id).name : '';
  const areaIndex = areas.findIndex(item => item.id === area);
  const currentArea = areas[areaIndex] ?? areas[0];
  const prevArea = areaIndex > 0 ? areas[areaIndex - 1] : null;
  const nextArea = areaIndex < areas.length - 1 ? areas[areaIndex + 1] : null;
  const jump = (target: Area) => { setNavBack(null); setArea(target); history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(target, sid || null, offline, mode)); };
  const fixtureGroups: CaseGroup[] = ['dev', 'public', 'stress', 'engineering', 'other'];
  const groupedFixtures = fixtureGroups.map(group => ({ group, items: fixtures.filter(fixture => caseDisplay(fixture.fixture_id).group === group) })).filter(entry => entry.items.length > 0);
  return <div className="app-shell">
    <header className="site-head">
      <a className="brand" href="#" onClick={event => event.preventDefault()}><span className="brand-mark" aria-hidden="true">◈</span><span className="brand-name">AgentShield</span></a>
      <nav className="site-nav" aria-label="页面导航">{areas.map(item => <a key={item.id} className={area === item.id ? 'nav-link active' : 'nav-link'} aria-current={area === item.id ? 'page' : undefined} href={buildViewHash(item.id, sid || null, offline, mode)} onClick={event => { event.preventDefault(); setNavBack(null); setArea(item.id); history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(item.id, sid || null, offline, mode)); }}>{item.nav}</a>)}</nav>
      <div className="head-side">
        {(!offline || replaySource === 'delivery') && <label className="run-pick"><span className="run-pick-label">演示记录</span>
          <select id="run" aria-label="选择演示记录" value={sid} disabled={!catalogReady || creating} onChange={event => chooseRun(event.target.value)}>
            <option value="" disabled>选择具体运行</option>
            {sessions.length > 0 && <optgroup label="本机会话">{sessions.map(row => <option key={row.session_id} value={row.session_id}>{row.case_id} ｜ {row.session_id}</option>)}</optgroup>}
            {deliveredOptions.length > 0 && <optgroup label="已交付历史运行">{deliveredOptions.map(row => <option key={row.session_id} value={row.session_id}>{executionSourceLabel(row.execution_source)} · {row.label} ｜ …{row.session_id.slice(-8)}</option>)}</optgroup>}
          </select></label>}
        {navBack && navBack !== area && <button className="nav-back-button" title={`回到${areas.find(item => item.id === navBack)?.title ?? '上一位置'}`} onClick={() => { const target = navBack; setNavBack(null); setArea(target); }}>← 返回上一位置</button>}
      </div>
    </header>
    <main>
      <div className="page-head">
        <p className="eyebrow">{currentArea.title}</p>
        <h1>{currentArea.question}</h1>
      </div>
      {offline && <div className="notice warning" role="status"><strong>{replaySource === 'delivery' ? 'A/C 交付证据只读视图' : '离线只读回放'}</strong>　{replaySource === 'delivery' ? '来自已校验的本地交付目录；属于开发运行，不会连接外部服务。' : '内容来自所选文件，未经签名认证；不代表本机最新状态。'}<button onClick={returnToService}>返回本机服务</button></div>}
      {actionError && <div role="alert" className="notice error">{actionError}</div>}
      {routeNotice && <div role="status" className="notice warning">{routeNotice}<button onClick={() => setRouteNotice('')}>知道了</button></div>}

      {state === 'loading' && <div className="loading" role="status" aria-live="polite"><span className="spinner"/>正在读取本次运行的真实数据…</div>}
      {state === 'error' && <div role="alert" className="empty error"><strong>当前数据未能加载</strong><p>{error}</p><button onClick={retry}>重试读取</button><p className="fine-print">也可以导入已保存的证据，进行离线只读回放。</p></div>}
      {state === 'ready' && area === 'test' && <>
        {!fileReplay && <NewTestPanel open={newTestOpen} onToggle={() => setNewTestOpen(value => !value)} configs={runnerConfigs} selected={agentConfigId} onSelect={setAgentConfigId} batch={batchStatus} onStart={startBScaleBatch} mode={mode} onMode={setMode} realRun={realRun} onStartRealRun={startRealRun}/>}
        {!fileReplay && (sessions.length > 0 || integrationRuns.length > 0 || batchStatus.batch_id !== null) && <TestRecordList sessions={sessions} runs={integrationRuns} batchId={batchStatus.batch_id} selected={sid} onSelect={chooseRun} tab={listTab} onTab={setListTab} ledgerBySession={ledgerBySession} lossByRun={lossByRun} onRetryDetails={retryRunDetails}/>}
        {!current && <Empty title="还没有开发会话">可在下方「开发工具」中创建业务初态，或在上方「演示记录」选择一个已有运行。创建会话不会调用模型或提交退款。</Empty>}
        {current && <>
        <CaseSummary evidence={current} name={runName}/>
        <RunResult evidence={current} matched={matchedIntegration} pending={integrationPending} hasEntry={integrationRuns.some(row => row.session_id === sid)} integrationError={integrationError} onRetry={() => setIntegrationRefresh(value => value + 1)}/>
        {matchedIntegration && <ResultPanel detail={matchedIntegration} onLoadEvidence={loadDeliveredEvidence}/>}
        <details id="evidence-fold" className="evidence-fold" open={evidenceOpen} onToggle={event => setEvidenceOpen(event.currentTarget.open)}>
          <summary>查看完整执行记录与核验依据</summary>
          <div className="evidence-body">
            <details className="run-identity"><summary>运行详情（session / episode / 版本 / 来源）</summary>
              <div className="identity-fields">
                <div><span>{current.case_context ? '稳定 case' : 'case（按原记录）'}</span><Id>{session?.case_id ?? ''}</Id></div>
                <div><span>本次 session</span><Id>{session?.session_id ?? ''}</Id></div>
                <div><span>本次 episode</span><Id>{session?.episode_id ?? ''}</Id></div>
                <div>版本 {session?.version} · <Id>{session?.config_id ?? ''}</Id></div>
              </div>
              <div className="identity-extra"><span className="identity-extra-line"><Badge tone="warning">{current.sources.execution_source ?? '执行来源未记录'}</Badge><span className="fine-print">{current.sources.fixture_source ?? '模板来源未记录'} · 来源标签须结合 C 运行清单核对</span></span></div>
            </details>
            <p className="content-toolbar">证据 schema {current.schema_version} · {current.contract_version ?? '历史未记录版本'} · {offline ? '文件导出时间' : '快照导出时间'} {current.exported_at.replace('T', ' ').slice(0, 19)} UTC</p>
            <details className="notice warning caveats"><summary>证据核对范围 · 来源未认证 / 初态哈希未复核</summary><ul>{evidenceCaveats(current).map(note => <li key={note}>{note}</li>)}</ul></details>
            <Business evidence={current} focusedOrder={focusedOrder}/>
            <Evidence key={sid} evidence={current} events={events} onOrder={showOrder}/>
          </div>
        </details>
        </>}
      </>}
      {state === 'ready' && area === 'risk' && <RiskOverview runs={pageRuns} offline={offline && replaySource !== 'delivery'} scenario={researchScenario} scenarioState={scenarioState} scenarioError={scenarioError} onRetryScenario={loadScenario} details={runDetails} batchId={pageBatchId} mode={mode} onRetryDetails={retryRunDetails}/>}
      {state === 'ready' && area === 'insurance' && <InsurancePlans runs={pageRuns} scenario={researchScenario} scenarioState={scenarioState} scenarioError={scenarioError} onRetryScenario={loadScenario} details={runDetails} batchId={pageBatchId} mode={mode} onRetryDetails={retryRunDetails}/>}
      <nav className="stepper" aria-label="分步导航">
        {prevArea ? <a className="step-link prev" href={buildViewHash(prevArea.id, sid || null, offline, mode)} onClick={event => { event.preventDefault(); jump(prevArea.id); }}>← 上一步：{prevArea.nav}</a> : <span className="step-link disabled">已经是第一步</span>}
        {nextArea ? <a className="step-link next" href={buildViewHash(nextArea.id, sid || null, offline, mode)} onClick={event => { event.preventDefault(); jump(nextArea.id); }}>下一步：{nextArea.nav} →</a> : <a className="step-link next" href={buildViewHash('test', sid || null, offline, mode)} onClick={event => { event.preventDefault(); jump('test'); }}>回到第一步：01 测试案例 ↺</a>}
      </nav>
      <footer className="site-foot">
        <p>开发运行不属于正式任务或 Gold；正式实验与全队签收尚未完成。模拟资金 · 非商业报价。</p>
        <details className="dev-tools"><summary>开发工具 · 调试入口（演示默认不展开；用于固定案例回归）</summary>
          <div className="dev-grid">
            <div className="dev-item"><span className="dev-label">当前运行</span><div className="dev-row"><button onClick={() => { ++interaction.current; setRefresh(value => value + 1); }} disabled={offline || !current}>刷新本次运行</button></div><p className="fine-print">重新读取所选运行的证据；不改变任何业务事实。</p></div>
            {!offline && <div className="dev-item"><span className="dev-label">新建业务初态</span><div className="dev-row">
              <select id="fixture" aria-label="选择业务案例" value={fixtureId} disabled={!catalogReady || creating} onChange={event => setFixtureId(event.target.value as FixtureCatalog['fixtures'][number]['fixture_id'])}>
                {fixtures.length ? groupedFixtures.map(entry => <optgroup key={entry.group} label={CASE_GROUP_LABELS[entry.group]}>{entry.items.map(fixture => <option key={fixture.fixture_id} value={fixture.fixture_id}>{caseDisplay(fixture.fixture_id).name} ｜ {fixture.fixture_id}</option>)}</optgroup>) : <option value="dev-refund-v1">正在读取案例…</option>}
              </select>
              <button onClick={create} disabled={!catalogReady || creating}>{creating ? '正在创建…' : '创建业务会话'}</button>
            </div><p className="fine-print">仅建立业务初态（不会调用模型、不会提交退款）；「启动 Agent」在运行接口接通前不存在。</p></div>}
            <div className="dev-item"><span className="dev-label">回放</span><div className="dev-row">
              <button onClick={() => input.current?.click()}>导入回放</button>
              <button onClick={saveReplay} disabled={!bundle}>保存证据回放</button>
            </div><p className="fine-print">导入按离线只读处理；保存导出当前证据 JSON。</p></div>
          </div>
          <details className="version-fold"><summary>版本与技术信息</summary><p className="fine-print">开发模板与 C L0 运行不构成正式任务或 Gold；A/C 契约仍为 candidate（bc-0.3-candidate · abcd-integration-0.1-candidate · observer-0.1-candidate）；ABCD 本机集成 · 七工具 · 模拟资金。</p></details>
        </details>
      </footer>
    </main>
    <input ref={input} className="file-input" type="file" accept="application/json,.json" aria-label="导入证据文件" onChange={importFile}/>
  </div>;
}
