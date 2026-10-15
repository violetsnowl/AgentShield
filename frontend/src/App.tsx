import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { api, pairFromFragment } from './api';
import { buildViewHash, parseViewState } from './routing';
import { adaptResult, evidenceStatePresentation, parseIntegrationCatalog, parseIntegrationDetail } from './integrations';
import type { IntegrationRunDetail, IntegrationRunSummary } from './integrations';
import { eventMeaning, evidenceCaveats, money, openingSplit, orderedEvents, parseEvidence, statusText } from './data';
import type { EvidenceBundle, EventPage, FixtureCatalog, Ledger, SessionPage, SessionStatus, ToolEvent } from './generated/contract';
import { CASE_GROUP_LABELS, caseDisplay } from './caseNames';
import type { CaseGroup } from './caseNames';
import { loadA4Products, A4_SOURCE_LABEL } from './data/a4Products';
import type { A4Catalog, A4Plan } from './data/a4Products';
import { computeRiskMetrics, coverageLine } from './riskMetrics';
import type { RiskRunInput } from './riskMetrics';

type Area = 'test' | 'risk' | 'insurance';
type LoadState = 'loading' | 'ready' | 'error';
const areas: { id: Area; title: string; hint: string; mark: string }[] = [
  { id: 'test', title: 'Agent 测试', hint: '选择测试方式与业务案例，创建会话并查看单次测试结果。', mark: 'Ⅰ' },
  { id: 'risk', title: '风险评估', hint: '跨运行的汇总统计与对照；每项标注数据范围与样本。', mark: 'Ⅱ' },
  { id: 'insurance', title: '保险方案', hint: 'A4 两套研究候选产品（Core / Plus）；参数待定项如实标注，非商业报价。', mark: 'Ⅲ' },
];
const errorText = (value: unknown) => value instanceof Error ? value.message : '读取失败，请重试。';
function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Id({ children }: { children: ReactNode }) { return <code className="id">{children ?? '未记录'}</code>; }
function Empty({ title, children }: { title: string; children: ReactNode }) { return <div className="empty"><strong>{title}</strong><p>{children}</p></div>; }

function RequestSummary({ evidence }: { evidence: EvidenceBundle }) {
  const state = evidence.final_snapshot;
  return <section className="facts">
    <div className="cell"><h3>当前业务请求</h3><p className="req">{state.case.request}</p><p className="fine-print">只呈现开发模板的公开事实。</p></div>
    {state.orders.slice(0, 2).map((order, index) => <div className="cell" key={order.order_id}>
      <h3>订单 {index + 1} · {({ paid: '已支付', partially_refunded: '部分退款', refunded: '已退款' })[order.status]}</h3>
      <p className="kv">实付 {money(order.paid_cents)} ｜ 已退 {money(order.refunded_cents)}</p>
      <p className="big">{money(order.remaining_cents)}<small>{order.remaining_cents > 0 && !order.items.some(item => item.eligible) ? '资格未满足' : '原路退回'}</small></p>
    </div>)}
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
          <div className="order-head"><div><h3>订单 {index + 1}</h3><Id>{order.order_id}</Id></div><Badge tone={order.refunded_cents ? 'good' : ''}>{({ paid: '已支付', partially_refunded: '部分退款', refunded: '已退款' })[order.status]}</Badge></div>
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

function Evidence({ evidence, events, more, onMore, paging, pageError, onOrder }: { onOrder: (id: string) => void; evidence: EvidenceBundle; events: ToolEvent[]; more: boolean; onMore: () => void; paging: boolean; pageError: string }) {
  const [eventFilter, setEventFilter] = useState('all');
  const [eventId, setEventId] = useState<string | null>(null);
  const [transactionId, setTransactionId] = useState<string | null>(null);
  const event = evidence.events.find(row => row.event_id === eventId);
  const refund = evidence.refunds.find(row => row.transaction_id === transactionId);
  const entry = evidence.ledger.find(row => row.transaction_id === transactionId);
  const visibleEvents = orderedEvents(events).filter(row => eventFilter === 'all' || row.status === eventFilter);
  const committed = evidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0);
  const split = openingSplit(evidence);
  function trace(id: string) { setTransactionId(id); window.setTimeout(() => document.getElementById('trace')?.scrollIntoView({ block: 'nearest' }), 0); }
  return <>
    <section className="ledger-summary"><div><span>已提交退款 · 模拟资金</span><strong className="money">{money(committed)}</strong><p>{evidence.refunds.length} 笔交易；原键重放不重复计钱</p>{split.total_opening_cents > 0 && <p className="cell-note">另有期初历史退款 {money(split.total_opening_cents)}（session 开始前，不计入本轮）</p>}</div><div><span>商户余额</span><strong className="money">{money(evidence.final_snapshot.merchant_balance_cents)}</strong><p>来自本次运行的最终快照</p></div><div><span>客户余额</span><strong className="money">{money(evidence.final_snapshot.customer_balance_cents)}</strong><p>不是保险赔款或商业报价</p></div></section>
    <section className="panel"><div className="section-head"><h2>执行事件</h2></div><p className="section-note">B 记录实际到达服务端的事件。C 的本地尝试、超时与响应接收另待接入；服务端提交不证明客户端收到。</p>
      <div className="event-filter"><label htmlFor="event-filter">事件状态</label><select id="event-filter" value={eventFilter} onChange={e => setEventFilter(e.target.value)}><option value="all">全部状态</option>{Object.entries(statusText).map(([key, value]) => <option key={key} value={key}>{value} / {key}</option>)}</select><small>已加载 {events.length} / {evidence.events.length} 条，匹配 {visibleEvents.length} 条；筛选不改变资金总额。</small></div>
      {events.length > 0 && visibleEvents.length === 0 && <Empty title="已加载事件中没有匹配项">可切换筛选或加载后续事件；没有匹配不等于运行中从未出现。</Empty>}
      {events.length === 0 ? <Empty title="尚无执行事件">此会话只建立了初态，尚未调用工具。当前没有真实 Agent 运行器。</Empty> : <div className="table-scroll"><table className="events-table"><thead><tr><th>序号 / 事件时间</th><th>工具 / call_id</th><th>真实状态 / 事实</th><th className="number">本次提交</th><th>追溯</th></tr></thead><tbody>{visibleEvents.map(row => <tr key={row.event_id} data-seq={row.seq}><td><strong className="seq">{row.seq}</strong><time className="cell-note">{row.recorded_at.replace('T', ' ').slice(0, 19)} UTC</time></td><td><strong>{row.tool_name}</strong><Id>{row.call_id}</Id></td><td><Badge tone={row.status}>{statusText[row.status]} / {row.status}</Badge><span className="cell-note">{eventMeaning(row)}</span></td><td className="money">{money(row.committed_amount_cents)}</td><td><button className="text-button" onClick={() => setEventId(row.event_id)}>事件详情 {row.seq}</button>{row.transaction_id && <button className="text-button" onClick={() => trace(row.transaction_id!)}>关联交易</button>}</td></tr>)}</tbody></table></div>}
      {more && <div className="table-footer"><button onClick={onMore} disabled={paging}>{paging ? '正在读取…' : '加载后续事件'}</button></div>}{pageError && <p role="alert" className="notice error">{pageError}</p>}
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

export default function App() {
  const [area, setArea] = useState<Area>(() => parseViewState(window.location.hash).area ?? 'test');
  const [fixtures, setFixtures] = useState<FixtureCatalog['fixtures']>([]);
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [sid, setSid] = useState('');
  const [runFilter, setRunFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [focusedOrder, setFocusedOrder] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [fixtureId, setFixtureId] = useState<FixtureCatalog['fixtures'][number]['fixture_id']>('dev-refund-v1');
  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [creating, setCreating] = useState(false);
  const [catalogReady, setCatalogReady] = useState(false);
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [offline, setOffline] = useState(false);
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [paging, setPaging] = useState(false);
  const [pageError, setPageError] = useState('');
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
  const [agentConfig, setAgentConfig] = useState('observed_agent_execution');
  const [evidenceOpen, setEvidenceOpen] = useState(() => parseViewState(window.location.hash).evidenceFocus);
  const input = useRef<HTMLInputElement>(null);
  const selection = useRef('');
  const replayMode = useRef(false);
  const interaction = useRef(0);
  const moreMenu = useRef<HTMLDetailsElement>(null);
  const filterRef = useRef<HTMLDetailsElement>(null);
  const pendingRun = useRef<string | null>(parseViewState(window.location.hash).run);
  const currentIntent = (epoch: number) => interaction.current === epoch;
  selection.current = sid;

  useEffect(() => { setCopied(false); }, [sid]);

  async function catalog(epoch: number) {
    const [f, list, delivered] = await Promise.all([api<FixtureCatalog>('api/fixtures'), api<SessionPage>('api/sessions'), api<unknown>('api/integration-runs')]);
    const integrated = parseIntegrationCatalog(delivered);
    if (currentIntent(epoch) && !replayMode.current) {
      setFixtures(f.fixtures); setSessions(list.sessions); setNextOffset(list.next_offset); setIntegrationRuns(integrated);
      setIntegrationId(current => integrated.some(row => row.run_id === current) ? current : integrated[0]?.run_id ?? ''); setCatalogReady(true);
    }
    return { sessions: list.sessions, integrated };
  }
  useEffect(() => {
    let active = true; const epoch = interaction.current;
    (async () => { try { await pairFromFragment(); const { sessions: list, integrated } = await catalog(epoch); if (!active || !currentIntent(epoch) || replayMode.current) return;
      if (list.length || integrated.length) {
        const wanted = pendingRun.current;
        pendingRun.current = null;
        const restored = wanted ? list.find(row => row.session_id === wanted) : undefined;
        const deliveredWanted = wanted && !restored && integrated.some(row => row.session_id === wanted);
        if (wanted && !restored && !deliveredWanted) setRouteNotice(`URL 中的运行（…${wanted.slice(-8)}）不在当前目录或已不可用；已回退到默认选择。`);
        const nextSid = restored?.session_id ?? (deliveredWanted ? wanted as string : undefined) ?? list.find(row => row.case_id === 'dev-case-refund-v1')?.session_id ?? list[0]?.session_id ?? '';
        setSid(nextSid);
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
    setState('loading'); setError(''); setBundle(null); setEvents([]); setPageError('');
    (async () => { try {
      const raw = await api<unknown>(`api/integration-runs/${delivered.run_id}`);
      const result = parseIntegrationDetail(raw);
      if (!currentIntent(epoch) || replayMode.current) return;
      const evidence = parseEvidence(result.evidence, result.summary.session_id);
      if (evidence.final_snapshot.session.episode_id !== result.summary.episode_id) throw new Error('A/C 结果与 B 证据的 episode 不一致。');
      replayMode.current = true; setOffline(true); setReplaySource('delivery');
      setNavBack(area !== 'test' ? area : null); setArea('test');
      setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setPageError(''); setActionError('');
      setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
    } catch (e) { if (currentIntent(epoch)) setActionError(errorText(e)); } })();
  }, [sid, sessions, integrationRuns, catalogReady, offline, area]);

  useEffect(() => {
    if (!sid || offline) return;
    if (catalogReady && !sessions.some(row => row.session_id === sid) && integrationRuns.some(row => row.session_id === sid)) return;
    const controller = new AbortController(); const epoch = interaction.current;
    setState('loading'); setError(''); setBundle(null); setEvents([]); setPageError('');
    (async () => { try {
      const [raw, page, ledger] = await Promise.all([
        api<unknown>(`api/sessions/${sid}/evidence`, { signal: controller.signal }),
        api<EventPage>(`api/sessions/${sid}/events?limit=4`, { signal: controller.signal }),
        api<Ledger>(`api/sessions/${sid}/ledger`, { signal: controller.signal }),
      ]);
      const evidence = parseEvidence(raw, sid);
      if (JSON.stringify(evidence.ledger) !== JSON.stringify(ledger.entries)
          || page.events.some(row => !evidence.events.some(item => JSON.stringify(item) === JSON.stringify(row))))
        throw new Error('运行在读取期间发生变化或接口事实不一致，请刷新获取一致快照。');
      if (controller.signal.aborted || !currentIntent(epoch) || replayMode.current) return;
      setBundle(evidence); setEvents(page.events); setState('ready');
    } catch (e) { if (!controller.signal.aborted && currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } } })();
    return () => controller.abort();
  }, [sid, offline, refresh]);

  useEffect(() => {
    document.querySelector('main')?.scrollTo(0, 0);
  }, [area]);

  useEffect(() => {
    const next = buildViewHash(area, sid || null, offline);
    if (window.location.hash !== next) history.replaceState(null, '', window.location.pathname + window.location.search + next);
  }, [area, sid, offline]);

  useEffect(() => {
    const onPop = () => {
      const view = parseViewState(window.location.hash);
      if (view.area) setArea(view.area);
      if (replayMode.current) return;
      if (view.run && view.run !== selection.current) {
        if (sessions.some(row => row.session_id === view.run) || integrationRuns.some(row => row.session_id === view.run)) { ++interaction.current; setFocusedOrder(null); setSid(view.run); setRouteNotice(''); }
        else setRouteNotice('URL 中的运行不在当前目录或已不可用；当前选择保持不变。');
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [sessions, integrationRuns]);
  async function loadService(epoch: number) {
    setState('loading'); setError('');
    try {
      const { sessions: list, integrated } = await catalog(epoch);
      if (!currentIntent(epoch) || replayMode.current) return;
      const wanted = pendingRun.current; pendingRun.current = null;
      const restored = wanted ? list.find(row => row.session_id === wanted) : undefined;
      const deliveredWanted = wanted && !restored && integrated.some(row => row.session_id === wanted);
      if (wanted && !restored && !deliveredWanted) setRouteNotice('URL 中的运行不在当前目录或已不可用。');
      if (list.length || deliveredWanted) setSid(restored?.session_id ?? (deliveredWanted ? wanted as string : list[0].session_id)); else setState('ready');
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
    void loadService(epoch);
  }
  async function create() {
    const epoch = ++interaction.current;
    setCreating(true); setActionError('');
    try {
      const result = await api<{ session: SessionStatus }>('api/sessions', { method: 'POST', body: { fixture_id: fixtureId } });
      if (!currentIntent(epoch) || replayMode.current) return;
      await catalog(epoch);
      if (!currentIntent(epoch) || replayMode.current) return;
      setBundle(null); setSid(result.session.session_id); setNavBack(null);
    } catch (e) {
      if (currentIntent(epoch) && !replayMode.current) setActionError(errorText(e) + ' 若创建响应丢失，会话可能已经建立；请刷新页面核对运行清单后再创建。');
    } finally { setCreating(false); }
  }
  async function moreRuns() {
    if (nextOffset === null) return;
    const epoch = interaction.current;
    try {
      const list = await api<SessionPage>(`api/sessions?offset=${nextOffset}`);
      if (!currentIntent(epoch) || replayMode.current) return;
      setSessions(old => [...old, ...list.sessions.filter(row => !old.some(item => item.session_id === row.session_id))]); setNextOffset(list.next_offset);
    } catch (e) { if (currentIntent(epoch) && !replayMode.current) setActionError(errorText(e)); }
  }
  async function moreEvents() {
    if (!bundle) return;
    setPaging(true); setPageError(''); const requestedSid = sid; const epoch = interaction.current;
    try { const page = await api<EventPage>(`api/sessions/${sid}/events?after_seq=${events.at(-1)?.seq ?? 0}&limit=4`);
      if (!currentIntent(epoch) || selection.current !== requestedSid || replayMode.current) return;
      if (page.events.some(row => !bundle.events.some(item => JSON.stringify(item) === JSON.stringify(row)))) throw new Error('检测到更新，请刷新本次运行后继续。');
      setEvents(old => orderedEvents([...old, ...page.events.filter(row => !old.some(item => item.seq === row.seq))]));
    } catch (e) { if (currentIntent(epoch) && selection.current === requestedSid && !replayMode.current) setPageError(errorText(e)); } finally { setPaging(false); }
  }
  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const element = event.target; const file = element.files?.[0]; if (!file) return;
    const epoch = ++interaction.current; element.value = ''; setActionError('');
    try {
      if (file.size > 5 * 1024 * 1024) throw new Error('回放文件超过 5 MiB，未读取。');
      const content = await file.text();
      if (!currentIntent(epoch)) return;
      const evidence = parseEvidence(JSON.parse(content));
      replayMode.current = true; setOffline(true); setReplaySource('file'); setSid(evidence.final_snapshot.session.session_id); setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setPageError(''); setActionError(''); setArea('test'); setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
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
    setNavBack(area !== 'test' ? area : null); ++interaction.current; replayMode.current = true; setOffline(true); setReplaySource('delivery'); setSid(integration.summary.session_id);
    setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setPageError(''); setActionError(''); setArea('test'); setEvidenceOpen(true); window.setTimeout(() => document.getElementById('evidence-fold')?.scrollIntoView({ block: 'start' }), 0);
  }
  const visibleRuns = sessions.filter(row => (!runFilter || [row.case_id, row.session_id, row.episode_id, row.config_id].some(value => value.toLowerCase().includes(runFilter.toLowerCase()))) && (sourceFilter === 'all' || row.sources.execution_source === sourceFilter));
  const selectedOutsideFilter = sessions.find(row => row.session_id === sid && !visibleRuns.some(item => item.session_id === sid));
  const deliveredOptions = integrationRuns.filter(row => !sessions.some(item => item.session_id === row.session_id));
  function revealRuns() { filterRef.current?.setAttribute('open', ''); document.getElementById('run')?.focus(); }
  function showOrder(id: string) {
    if (area !== 'test') setNavBack(area);
    setFocusedOrder(id); setArea('test'); setEvidenceOpen(true);
    window.setTimeout(() => document.getElementById(`order-${id}`)?.scrollIntoView({ block: 'center', behavior: 'auto' }), 0);
  }
  async function copyIdentity() {
    if (!session) return;
    try { await navigator.clipboard.writeText(JSON.stringify({ case_id: session.case_id, session_id: session.session_id, episode_id: session.episode_id })); setCopied(true); }
    catch { setActionError('复制不可用，请展开运行身份并手动复制。'); }
  }
  const current = bundle?.final_snapshot.session.session_id === sid ? bundle : null;
  const session = current?.final_snapshot.session ?? sessions.find(row => row.session_id === sid);
  const matchedIntegration = integration && integration.summary.session_id === sid ? integration : null;
  const integrationPending = !offline && !matchedIntegration && integrationRuns.some(row => row.session_id === sid) && integrationState !== 'error';
  const resultCommitted = current ? current.refunds.reduce((sum, row) => sum + row.amount_cents, 0) : 0;
  const resultOpeningCents = current ? openingSplit(current).total_opening_cents : 0;
  const areaIndex = areas.findIndex(item => item.id === area);
  const prevArea = areaIndex > 0 ? areas[areaIndex - 1] : null;
  const nextArea = areaIndex < areas.length - 1 ? areas[areaIndex + 1] : null;
  const jump = (target: Area) => { setNavBack(null); setArea(target); history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(target, sid || null, offline)); };
  return <div className="app-shell">
    <header className="topbar">
      <div className="tb-left"><a className="brand" href="#" onClick={e => e.preventDefault()}><span className="brand-mark" aria-hidden="true">◈</span><span>AgentShield<small>保险风险评测工作台</small></span></a></div>
      <div className="tb-center"><nav className="navgroup" aria-label="工作区域">{areas.map(item => <button key={item.id} className={area === item.id ? 'nav-item active' : 'nav-item'} aria-current={area === item.id ? 'page' : undefined} onClick={() => { setNavBack(null); setArea(item.id); history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(item.id, sid || null, offline)); }}><span className="nav-mark" aria-hidden="true">{item.mark}</span><span>{item.title}</span></button>)}</nav></div>
      <div className="tb-right">
        {navBack && navBack !== area && <button className="nav-back-button" title={`回到${areas.find(item => item.id === navBack)?.title ?? '上一位置'}`} onClick={() => { const target = navBack; setNavBack(null); setArea(target); }}>← 返回上一位置</button>}
        
      </div>
    </header>
    <div className="subbar">
      <div className="sub-row">
      {(!offline || replaySource === 'delivery') && <><div className="run-picker"><label htmlFor="run">运行</label><select id="run" value={sid} onChange={e => { ++interaction.current; replayMode.current = false; setFocusedOrder(null); setCopied(false); setNavBack(null); setRouteNotice(''); setSid(e.target.value); history.pushState(null, '', window.location.pathname + window.location.search + buildViewHash(area, e.target.value, false)); }} disabled={!catalogReady || creating}><option value="" disabled>选择具体运行</option>{selectedOutsideFilter && <option value={selectedOutsideFilter.session_id}>当前选择（筛选外）｜{selectedOutsideFilter.session_id}</option>}{visibleRuns.length > 0 && <optgroup label="本机会话">{visibleRuns.map(row => <option key={row.session_id} value={row.session_id}>{row.case_id} ｜ {row.session_id}</option>)}</optgroup>}{deliveredOptions.length > 0 && <optgroup label="已交付历史运行">{deliveredOptions.map(row => <option key={row.session_id} value={row.session_id}>{(row.execution_source === 'observed_agent_execution' ? '真实模型' : 'Mock')} · {row.label} ｜ …{row.session_id.slice(-8)}</option>)}</optgroup>}</select>{nextOffset !== null && <button className="text-button" onClick={moreRuns}>加载更多运行</button>}<button className="text-button" onClick={revealRuns}>查看已有运行</button></div></>}
      <Badge tone={offline ? 'warning' : state === 'error' ? 'error' : state === 'loading' ? '' : 'good'}>{offline ? (replaySource === 'delivery' ? 'A/C 交付证据 · 只读' : '本地文件 · 只读回放') : state === 'error' ? '读取失败' : state === 'loading' ? '正在读取' : 'B 本机服务'}</Badge>
      </div>
      <div className="sub-row">
      {session && <div className="identity-compact"><span className="run-summary"><strong>{session.case_id}</strong><span>本次运行 …{session.session_id.slice(-8)}</span><Badge tone="good">{session.status === 'finished' ? '已结束' : '进行中'}</Badge></span><details className="run-identity"><summary>运行详情（session / episode / 版本 / 来源）</summary><div className="identity-fields"><div><span>{current?.case_context ? '稳定 case' : 'case（按原记录）'}</span><Id>{session.case_id}</Id></div><div><span>本次 session</span><Id>{session.session_id}</Id></div><div><span>本次 episode</span><Id>{session.episode_id}</Id></div><div>版本 {session.version} · <Id>{session.config_id}</Id></div></div><div className="identity-extra"><span className="identity-extra-line"><Badge tone="warning">{current ? current.sources.execution_source ?? '执行来源未记录' : '开发环境'}</Badge><span className="fine-print">{current ? `${current.sources.fixture_source ?? '模板来源未记录'} · 来源标签须结合 C 运行清单核对` : 'development_only · 来源标签须结合 C 运行清单核对'}</span></span><span className="identity-extra-line"><button onClick={copyIdentity}>{copied ? '已复制身份' : '复制运行身份'}</button></span></div></details></div>}
      <details ref={moreMenu} className="more-menu"><summary>⋯ 更多</summary><div className="more-menu-body"><button onClick={() => { moreMenu.current?.removeAttribute('open'); input.current?.click(); }}>导入回放</button><button onClick={() => { moreMenu.current?.removeAttribute('open'); saveReplay(); }}>保存证据回放</button></div></details><input ref={input} className="file-input" type="file" accept="application/json,.json" aria-label="导入证据文件" onChange={importFile}/>
      {(!offline || replaySource === 'delivery') && <details ref={filterRef} className="filter-disclosure"><summary>筛选运行 · 已加载 {sessions.length} 条</summary><div className="run-filters"><label>筛选已加载运行<input aria-label="筛选已加载运行" value={runFilter} onChange={e => setRunFilter(e.target.value)} placeholder="case / session / episode / 配置"/></label><label>执行来源<select aria-label="执行来源筛选" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}><option value="all">全部来源</option>{['scripted_test','mock_agent','observed_agent_execution'].map(value => <option key={value} value={value}>{value}</option>)}</select></label><span>已加载 {sessions.length}，匹配 {visibleRuns.length}。{nextOffset !== null ? '还有后续页，可继续加载。' : '目录已完整加载。'}</span>{visibleRuns.length === 0 && catalogReady && <span role="status">没有匹配的已加载运行；当前选择保持不变。</span>}</div></details>}
      </div>
    </div>
    <main><header className="page-header"><div><h1>{areas.find(item => item.id === area)?.title}</h1><p>{areas.find(item => item.id === area)?.hint}</p></div><span className="zone-chips">{area === 'test' && <Badge tone="warning">开发数据 · 待审</Badge>}</span></header>
      {offline && <div className="notice warning" role="status"><strong>{replaySource === 'delivery' ? 'A/C 交付证据只读视图' : '离线只读回放'}</strong>　{replaySource === 'delivery' ? '内容来自已校验的本地交付目录，属于开发运行；不会连接原 C 实例。' : '内容来自所选文件，未经签名认证；不代表本机最新状态。'} 切换功能区不会调用 B，也不会重新执行退款。<button onClick={returnToService}>返回本机服务</button></div>}
      {actionError && <div role="alert" className="notice error">{actionError}</div>}
      {routeNotice && <div role="status" className="notice warning">{routeNotice}<button onClick={() => setRouteNotice('')}>知道了</button></div>}
      

      {state === 'loading' && <div className="loading" role="status" aria-live="polite"><span className="spinner"/>正在读取本次运行的真实数据…</div>}
      {state === 'error' && <div role="alert" className="empty error"><strong>当前数据未能加载</strong><p>{error}</p><button onClick={retry}>重试读取</button><p className="fine-print">也可以导入已保存的证据，进行离线只读回放。</p></div>}
      {state === 'ready' && area === 'test' && <StartCard agentConfig={agentConfig} onAgentConfig={setAgentConfig} offline={offline} catalogReady={catalogReady} creating={creating} fixtures={fixtures} fixtureId={fixtureId} onFixture={value => setFixtureId(value as FixtureCatalog['fixtures'][number]['fixture_id'])} onCreate={create} onReveal={revealRuns}/>}
      {state === 'ready' && !current && area === 'test' && <Empty title="还没有开发会话">选择测试方式与业务案例并创建会话，即可查看业务初态。创建会话不会调用模型或提交退款。</Empty>}
      {state === 'ready' && current && <>
        <div className="content-toolbar"><span>证据 schema {current.schema_version} · {current.contract_version ?? '历史未记录版本'} · {offline ? '文件导出时间' : '快照导出时间'} {current.exported_at.replace('T', ' ').slice(0, 19)} UTC</span><div>{!offline && <button onClick={() => { ++interaction.current; setRefresh(v => v + 1); }}>刷新本次运行</button>}</div></div>
        <details className="notice warning"><summary>证据核对范围 · 来源未认证 / 初态哈希未复核</summary><ul>{evidenceCaveats(current).map(note => <li key={note}>{note}</li>)}</ul></details>
        {area === 'test' && <>
          <RequestSummary evidence={current}/>
          <section className="result-cards" aria-label="单次运行结果">
            <div className="result-card"><span>已提交退款 · 模拟资金</span><strong className="money" data-testid="committed-total">{money(resultCommitted)}</strong><p>{current.refunds.length} 笔交易 · 原键重放不重复计钱</p>{resultOpeningCents > 0 && <p className="cell-note">另有期初历史退款 {money(resultOpeningCents)}（session 开始前，不计入本轮）</p>}</div>
            <div className="result-card"><span>核验净损失（C）</span>{matchedIntegration ? (matchedIntegration.loss_result.net_loss_cents === null ? <Badge tone="warning">未知 / null</Badge> : <strong className="money">{money(matchedIntegration.loss_result.net_loss_cents)}</strong>) : <Badge tone="warning">暂无核验结果</Badge>}<p>{matchedIntegration ? '仅限已核验范围；不推断全部应付款额已完成确认。' : '该会话尚无 C/A 交付目录条目；不展示其他运行的数字。'}</p></div>
            <div className="result-card"><span>研究赔款（A）</span>{matchedIntegration ? (matchedIntegration.claim.payout_cents === null ? <Badge tone="warning">待审核 / null</Badge> : <strong className="money">{money(matchedIntegration.claim.payout_cents)}</strong>) : <Badge tone="warning">暂无理算结果</Badge>}<p>研究用途 · commercial_quote=false。</p></div>
            <div className="result-card"><span>运行状态</span><Badge tone="good">{current.final_snapshot.session.status === 'finished' ? '已结束' : '进行中'}</Badge><p>{current.sources.execution_source ?? '来源未记录'} · 开发运行，不计入 56 次。</p></div>
          </section>
          {integrationPending && <div className="loading" role="status"><span className="spinner"/>正在校验 A/C 交付结果…</div>}
          {matchedIntegration && <ResultPanel detail={matchedIntegration} onLoadEvidence={loadDeliveredEvidence}/>}
          {!matchedIntegration && !integrationPending && integrationState === 'error' && integrationRuns.some(row => row.session_id === sid) && <div className="empty error" role="alert"><strong>A/C 结果已停止展示</strong><p>{integrationError}</p><button onClick={() => setIntegrationRefresh(value => value + 1)}>重试读取</button></div>}
          <details id="evidence-fold" className="evidence-fold" open={evidenceOpen} onToggle={event => setEvidenceOpen(event.currentTarget.open)}><summary>详细执行证据 · 事件与资金去向（按需打开）</summary>
            <div className="fold-actions"><a href="#" onClick={event => { event.preventDefault(); document.querySelector('.result-cards')?.scrollIntoView({ block: 'start' }); }}>↑ 回到结果</a></div>
            <Business evidence={current} focusedOrder={focusedOrder}/>
            <Evidence key={sid} evidence={current} events={events} more={!offline && events.length < current.events.length} onMore={moreEvents} paging={paging} pageError={pageError} onOrder={showOrder}/>
          </details>
        </>}
      </>}
      {state === 'ready' && area === 'risk' && <RiskOverview runs={integrationRuns} offline={offline}/>}
      {state === 'ready' && area === 'insurance' && <InsurancePlans runs={integrationRuns} offline={offline}/>}
      <footer><p>开发模板和 C L0 运行不属于正式任务或 Gold；A/C 契约仍是 candidate，正式实验与全队签收尚未完成。ABCD 本机集成 · 工程事实可追溯 · 业务 Gold 仍待审核 · bc-0.3 · C L0 · A0 · 七工具 · 模拟资金。</p></footer>
    </main>
    <div className="exitrow">
      <span className="exit-cap">读完这一段，出口就在手边</span>
      <div className="exit-plate">
        {prevArea ? <a className="back" href={buildViewHash(prevArea.id, sid || null, offline)} onClick={e => { e.preventDefault(); jump(prevArea.id); }}>‹ 回看：<b>{prevArea.mark}</b> {prevArea.title}</a> : <span className="back">‹ 回看：无（第 1 站）</span>}
        {nextArea ? <a className="go" href={buildViewHash(nextArea.id, sid || null, offline)} onClick={e => { e.preventDefault(); jump(nextArea.id); }}>前往下一站 <b>{nextArea.mark}</b> {nextArea.title}<small>约 1 分钟</small></a> : <a className="go" href={buildViewHash('test', sid || null, offline)} onClick={e => { e.preventDefault(); jump('test'); }}>走完了 · 回到 <b>Ⅰ</b> Agent 测试<small>从头再看 · 约 3–5 分钟</small></a>}
        <span className="arrow" aria-hidden="true">{nextArea ? '→' : '↺'}</span>
      </div>
    </div>
  </div>;
}

function decimalCents(value: string | null) {
  if (value === null || !Number.isFinite(Number(value))) return '不可用';
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(Number(value) / 100);
}

function StartCard({ agentConfig, onAgentConfig, offline, catalogReady, creating, fixtures, fixtureId, onFixture, onCreate, onReveal }: {
  agentConfig: string; onAgentConfig: (value: string) => void; offline: boolean; catalogReady: boolean; creating: boolean;
  fixtures: FixtureCatalog['fixtures']; fixtureId: string; onFixture: (value: string) => void; onCreate: () => void; onReveal: () => void;
}) {
  const groups: CaseGroup[] = ['dev', 'public', 'stress', 'engineering', 'other'];
  const grouped = groups.map(group => ({ group, items: fixtures.filter(fixture => caseDisplay(fixture.fixture_id).group === group) })).filter(entry => entry.items.length > 0);
  return <section className="start-card" aria-label="开始测试">
    <div className="step">
      <label htmlFor="agent-config">① 测试方式 / Agent 配置</label>
      <select id="agent-config" value={agentConfig} onChange={event => onAgentConfig(event.target.value)} disabled={offline}>
        <option value="observed_agent_execution">真实模型配置 · deepseek-flash-dev（历史配置，运行接口未接通）</option>
        <option value="mock_agent">Mock（接口模拟，非真实模型）</option>
        <option value="scripted_test">规则基线（对照 · 非 LLM）</option>
      </select>
      <p className="fine-print">仅作“拟用配置”标注；选择不会触发任何运行。</p>
    </div>
    <div className="step">
      <label htmlFor="fixture">② 业务案例</label>
      <select id="fixture" value={fixtureId} disabled={!catalogReady || creating || offline} onChange={event => onFixture(event.target.value)}>
        {fixtures.length ? grouped.map(entry => <optgroup key={entry.group} label={CASE_GROUP_LABELS[entry.group]}>{entry.items.map(fixture => <option key={fixture.fixture_id} value={fixture.fixture_id}>{caseDisplay(fixture.fixture_id).name} ｜ {fixture.fixture_id}</option>)}</optgroup>) : <option value="dev-refund-v1">正在读取案例…</option>}
      </select>
    </div>
    <div className="step">
      <span className="step-label">③ 连接状态</span>
      <div className="conn-row"><Badge tone={offline ? 'warning' : 'good'}>{offline ? '离线只读' : '本机服务 ✓'}</Badge><Badge tone="warning">模型运行接口 ✖ 未接通</Badge><Badge tone="good">离线回放 ✓</Badge></div>
      <p className="fine-print">真实模型 / Mock / 规则基线按来源分别标注，不混称。</p>
    </div>
    <div className="step">
      <span className="step-label">④ 运行测试</span>
      <div className="conn-row">
        {!offline && <button className="primary" onClick={onCreate} disabled={!catalogReady || creating}>{creating ? '正在创建…' : '创建业务会话'}</button>}
        <button disabled aria-describedby="runner-note">启动 Agent</button>
        <button className="text-button" onClick={onReveal}>查看已有运行 ↓</button>
      </div>
      <p className="fine-print" id="runner-note">创建业务会话只建立业务初态，不等于执行 Agent；浏览器运行接口接通前「启动 Agent」保持禁用。</p>
    </div>
  </section>;
}

function ResultPanel({ detail, onLoadEvidence }: { detail: IntegrationRunDetail; onLoadEvidence: () => void }) {
  const lossSlot = adaptResult('LossResult', detail.loss_result);
  const quoteSlot = adaptResult('QuoteResult', detail.quote_result);
  return <section className="integration-panel" aria-label="单次核验与理算结果">
    <div className="integration-lead"><span className="integration-mark" aria-hidden="true">↔</span><div><Badge tone="warning">C L0 候选</Badge> <Badge tone="warning">A0 研究候选</Badge><h2>{detail.loss_result.loss_status === 'needs_review' ? '独立核验已执行，损失仍待业务审核' : '独立核验已有可确认结果'}</h2><p>{lossSlot.message}</p></div></div>
    <p className="fine-print panel-identity-note">运行身份已按 session / episode 校验并与所选运行一致；完整 ID 与版本见顶部「运行详情」。执行来源：<Badge tone="warning">{detail.summary.execution_source}</Badge> {detail.summary.provider} / {detail.summary.model} · 开发运行，不计入 56 次。</p>
    <div className="integration-body">
      <div><h3>业务事实与独立核验</h3><dl><div><dt>已提交退款</dt><dd className="money">{money(detail.loss_result.total_committed_cents)}</dd></div><div><dt>净损失</dt><dd>{detail.loss_result.net_loss_cents === null ? <Badge tone="warning">未知 / null</Badge> : <><strong className="money">{money(detail.loss_result.net_loss_cents)}</strong>{detail.loss_result.net_loss_cents === 0 && <small className="cell-note">0 仅限已核验范围；不推断全部应付款额已完成确认。</small>}</>}</dd></div><div><dt>核验状态</dt><dd><Badge tone={detail.loss_result.loss_status === 'verified' ? 'good' : 'warning'}>{detail.loss_result.loss_status}</Badge></dd></div><div><dt>责任输入</dt><dd>{detail.loss_result.coverage_status_input}</dd></div><div><dt>义务来源</dt><dd>{detail.loss_result.obligation_source}</dd></div></dl><p className="fine-print">退款总额只表示 B 已提交资金事实，绝不直接等同于额外净损失。</p><details className="fold-body"><summary>核验依据与缺口明细</summary><dl><div><dt>oracle</dt><dd><Id>{detail.loss_result.oracle_version}</Id></dd></div><div><dt>账本一致</dt><dd>{detail.loss_result.ledger_checks?.issues.length ? <Badge tone="error">存在问题</Badge> : <Badge tone="good">无已记录问题</Badge>}</dd></div><div><dt>工具事件</dt><dd>{detail.loss_result.activity?.tool_events ?? '未记录'}</dd></div><div><dt>人工工单</dt><dd>{detail.loss_result.activity?.human_review_tickets ?? '未记录'}</dd></div></dl><ul>{detail.loss_result.unknown_parts.length ? detail.loss_result.unknown_parts.map(item => <li key={item}>{item}<Badge tone="warning">未知</Badge></li>) : <li>没有未解析字段</li>}</ul></details><button onClick={onLoadEvidence}>加载关联业务证据</button></div>
      <div><h3>本研究合同与 A0 理算</h3><Badge tone="warning">A0 研究候选</Badge><dl><div><dt>合同版本</dt><dd><Id>{detail.contract.contract_version}</Id></dd></div><div><dt>免赔额</dt><dd className="money">{money(detail.contract.deductible_cents)}</dd></div><div><dt>赔付比例</dt><dd>{(detail.contract.coinsurance_bp / 100).toFixed(2)}%</dd></div><div><dt>每次限额</dt><dd className="money">{money(detail.contract.occurrence_limit_cents)}</dd></div><div><dt>损失</dt><dd>{detail.claim.net_loss_cents === null ? '待审核 / null' : money(detail.claim.net_loss_cents)}</dd></div><div><dt>研究赔款</dt><dd>{detail.claim.payout_cents === null ? <Badge tone="warning">待审核 / null</Badge> : <strong className="money">{money(detail.claim.payout_cents)}</strong>}</dd></div></dl><p className="fine-print">claim_status={detail.claim.claim_status}；commercial_quote=false。前端不复制理算公式。</p><button disabled aria-describedby="pending-cost">重新理算</button><p className="fine-print" id="pending-cost">工作台只展示 A 已交付的结果；交互式重算与正式数据尚未接入。</p>
        <div className="quote-sample"><h3>工程情景成本样例</h3><Badge tone="warning">illustrative · 非本次运行</Badge><dl><div><dt>B0 均值</dt><dd>{decimalCents(detail.quote_result.methods.B0.estimated_mean_cents_decimal)}</dd></div><div><dt>B0 情景成本</dt><dd>{decimalCents(detail.quote_result.methods.B0.scenario_cost_cents_decimal)}</dd></div><div><dt>B1 均值</dt><dd>{decimalCents(detail.quote_result.methods.B1.estimated_mean_cents_decimal)}</dd></div><div><dt>B1 情景成本</dt><dd>{decimalCents(detail.quote_result.methods.B1.scenario_cost_cents_decimal)}</dd></div><div><dt>B2</dt><dd>{detail.quote_result.methods.B2.status}</dd></div></dl></div></div>
    </div>
    <div className="integration-foot"><strong>仅研究用途 · commercial_quote=false · 非商业报价</strong><p>LossResult 适配状态：{lossSlot.state}；QuoteResult 工程样例适配状态：{quoteSlot.state}。结果已按 session / episode 与所选运行校验一致。</p></div>
    {detail.summary.evidence_digest_status !== 'raw_file_match' && <div className="integration-foot warning-text">证据声明哈希匹配规范 JSON（排序键、LF）；交付文件实际为 CRLF，原始字节哈希由 C_DELIVERY_MANIFEST 另行保护。历史文件未被改写。</div>}
    <div className="integration-foot"><details><summary>证据状态说明</summary><div className="state-guide">{Object.entries(evidenceStatePresentation).map(([key, value]) => <div key={key}><Badge tone={value.tone}>{value.title} / {key}</Badge><p>{value.text}</p></div>)}</div></details></div>
  </section>;
}

function SourceFold({ label, rows }: { label: string; rows: RiskRunInput[] }) {
  if (rows.length === 0) return null;
  return <details className="fold-body"><summary>{label}（{rows.length}）</summary><ul>{rows.map(row => <li key={row.runId}><Id>{row.runId}</Id><span className="cell-note">{row.label} · …{row.sessionId.slice(-8)}</span></li>)}</ul></details>;
}

function RiskOverview({ runs, offline }: { runs: IntegrationRunSummary[]; offline: boolean }) {
  const [details, setDetails] = useState<IntegrationRunDetail[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (offline) { setDetails(null); setError(''); return; }
    let active = true;
    (async () => { try {
      const all = await Promise.all(runs.map(async run => parseIntegrationDetail(await api<unknown>(`api/integration-runs/${run.run_id}`))));
      if (active) setDetails(all);
    } catch (e) { if (active) setError(errorText(e)); } })();
    return () => { active = false; };
  }, [runs, offline]);
  if (offline) return <Empty title="离线只读模式">跨运行汇总需要本机服务；离线时不会发起任何请求。</Empty>;
  if (error) return <div className="empty error" role="alert"><strong>汇总数据未能读取</strong><p>{error}</p></div>;
  if (details === null) return <div className="loading" role="status"><span className="spinner"/>正在汇总已交付开发运行…</div>;
  if (details.length === 0) return <Empty title="暂无可汇总的已交付运行">目录里没有完整的 A/C 交付条目；不会用开发会话冒充统计样本。</Empty>;
  const inputs: RiskRunInput[] = details.map(detail => ({
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
  const sourceRows = [
    { label: '真实模型开发运行', count: metrics.observed.length },
    { label: 'Mock 开发运行', count: metrics.mock.length },
    { label: '规则基线开发运行（scripted_test）', count: metrics.scripted.length },
    { label: '规则基线开发运行（rule_baseline）', count: metrics.ruleBaseline.length },
    { label: '其他来源开发运行', count: metrics.otherSources.length },
  ].filter(row => row.count > 0);
  return <section className="risk-overview" aria-label="跨运行风险评估">
    <div className="scope-banner" role="status"><strong>汇总视图 · 基于 {metrics.total} 次已交付开发运行</strong><span>全部为开发运行（counts_as_formal_run=false）；正式 56 次实验未执行，本页不作正式结论。</span></div>
    <div className="risk-grid">
      <article className="risk-card"><h3>测试覆盖</h3><p className="big-number">{metrics.total}</p><p>已交付开发运行总数</p><p className="range-tag">[范围：本机交付目录｜开发｜样本 {metrics.total}]</p><SourceFold label="来源运行" rows={inputs}/></article>
      <article className="risk-card"><h3>开发运行来源</h3><ul className="source-list">{sourceRows.map(row => <li key={row.label}><span>{row.label}</span><strong>{row.count}</strong></li>)}</ul><p className="fine-print">仅表示运行来源构成，不等于任务正确率或风险高低对照；真实模型、Mock 与规则基线分开标注，不混称；同任务可比的核验对照待正式数据。</p><p className="range-tag">[范围：按 execution_source 分类｜开发｜样本 {metrics.total}]</p></article>
      <article className="risk-card"><h3>核验覆盖</h3><p className="big-number">{metrics.verified.length} / {metrics.total}</p><p>已核验 / 全部运行（loss_status）</p><p>待核验（needs_review）{metrics.review.length} 条，净损失保持 null，未记零；待核验 ≠ 任务升级。</p><p className="range-tag">[范围：loss_status｜开发｜样本 {metrics.total}]</p><SourceFold label="待核验运行" rows={metrics.review}/></article>
      <article className="risk-card"><h3>核验损失（仅已核验样本）</h3><p className="coverage-line">{coverageLine(metrics)}</p><p className="big-number">{metrics.verified.length ? money(metrics.verifiedNetSumCents) : '证据不足'}</p><p>已核验样本净损失（{metrics.verified.length} 条已核验{metrics.verifiedZero.length ? `，其中 ${metrics.verifiedZero.length} 条为已核验零损失` : ''}）</p><p className="fine-print">零金额仅指已核验样本；待核验为未知（null），不解释为 0，也不并入合计。</p><p className="range-tag">[范围：loss_status=verified｜开发｜样本 {metrics.verified.length}]</p><SourceFold label="来源运行" rows={metrics.verified}/></article>
      <article className="risk-card"><h3>研究赔款</h3><p className="big-number">{metrics.assessed.length ? money(metrics.payoutSumCents) : '待审核 / 证据不足'}</p><p>已理算 {metrics.assessed.length} / {metrics.total}；其余维持待审（payout 未记零）</p><p className="range-tag">[范围：claim_status=assessed｜开发｜样本 {metrics.assessed.length}]</p><SourceFold label="来源运行" rows={metrics.assessed}/></article>
      <article className="risk-card"><h3>按业务类别</h3><div className="table-scroll"><table><thead><tr><th>类别</th><th className="number">运行</th><th className="number">已核验</th><th className="number">净损失合计</th></tr></thead><tbody>{metrics.categories.map(category => <tr key={category.key}><td>{category.key}</td><td className="number">{category.runs}</td><td className="number">{category.verified}</td><td className="money">{category.verified ? money(category.lossCents) : '—'}</td></tr>)}</tbody></table></div><p className="range-tag">[范围：按案例 ID 公开结构归类｜开发｜样本 {metrics.total}]</p></article>
      <article className="risk-card"><h3>任务升级（task_outcome）</h3><p className="big-number">{metrics.outcomeEscalated}</p><p>task_outcome=escalated 的运行数（交付 manifest）</p><p className="fine-print">任务结果拆解：completed {metrics.outcomeCompleted} · escalated {metrics.outcomeEscalated} · not_finished {metrics.outcomeNotFinished}{metrics.outcomeOther ? ` · 其他 ${metrics.outcomeOther}` : ''}</p><p className="fine-print">人工工单（独立维度 · B 证据 human_reviews）：{metrics.ticketRuns.length} 个运行，共 {metrics.ticketTotal} 张工单；工单与核验状态不能互相代替。</p><p className="range-tag">[范围：manifest.task_outcome｜开发｜样本 {metrics.total}]</p><SourceFold label="升级运行" rows={metrics.escalated}/></article>
      <article className="risk-card"><h3>企业业务汇总（B-SCALE）</h3><p>未接入。</p><p className="fine-print">B 的企业业务汇总尚未交付；模拟订单数不会计作 Agent 测试次数。</p></article>
    </div>
  </section>;
}

function A4PlanCard({ plan, catalog }: { plan: A4Plan; catalog: A4Catalog }) {
  const pending = <Badge tone="warning">待定</Badge>;
  return <article className="plan-card">
    <h2>{plan.display_name}</h2>
    <p className="fine-print"><Id>{plan.product_id}</Id> <Badge tone="warning">{catalog.status}</Badge> <Badge tone="warning">commercial_quote=false</Badge></p>
    <dl>
      <div><dt>产品定位与被保险人</dt><dd>{plan.insured}</dd></div>
      <div><dt>保障责任</dt><dd>{plan.covered_event}</dd></div>
      <div><dt>主要责任免除</dt><dd><ul className="plan-exclusions">{plan.exclusions.map(item => <li key={item}>{item}</li>)}</ul></dd></div>
      <div><dt>免赔额</dt><dd>{plan.deductible_cents === null ? pending : money(plan.deductible_cents)}</dd></div>
      <div><dt>赔付比例</dt><dd>{plan.coinsurance_bp === null ? pending : `${(plan.coinsurance_bp / 100).toFixed(2)}%`}</dd></div>
      <div><dt>单次赔付限额</dt><dd>{plan.occurrence_limit_cents === null ? pending : money(plan.occurrence_limit_cents)}</dd></div>
      <div><dt>年度累计赔付限额</dt><dd>{plan.annual_aggregate_limit_cents === null ? <><Badge tone="warning">待定</Badge><small className="cell-note">年度累计限额理算尚未实现，不能假装已接通。</small></> : money(plan.annual_aggregate_limit_cents)}</dd></div>
      {plan.optional_incident_response_sublimit_cents !== undefined && <div><dt>处置费用附加子限额</dt><dd><Badge tone="warning">可选 · 待实现</Badge><small className="cell-note">处置费用附加责任当前无 A0 计算实现，仅登记为研究候选，不并入理算。</small></dd></div>}
      <div><dt>赔付结构</dt><dd>{plan.claims_basis}</dd></div>
      <div><dt>保额与限额设计口径</dt><dd>{plan.limit_design}</dd></div>
    </dl>
    <p className="fine-print">预计赔款成本与商业保费：<Badge tone="warning">{catalog.premium_method.commercial_rate_status ?? 'insufficient_evidence'}</Badge> 证据不足，不出具数字；保费口径见下方「测算依据」。</p>
  </article>;
}

function InsurancePlans({ runs, offline }: { runs: IntegrationRunSummary[]; offline: boolean }) {
  const [details, setDetails] = useState<IntegrationRunDetail[] | null>(null);
  const [error, setError] = useState('');
  const [catalog, setCatalog] = useState<A4Catalog | null>(null);
  const [catalogError, setCatalogError] = useState('');
  useEffect(() => {
    let active = true;
    loadA4Products().then(value => { if (active) setCatalog(value); }).catch(e => { if (active) setCatalogError(errorText(e)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (offline) { setDetails(null); setError(''); return; }
    let active = true;
    (async () => { try {
      const all = await Promise.all(runs.map(async run => parseIntegrationDetail(await api<unknown>(`api/integration-runs/${run.run_id}`))));
      if (active) setDetails(all);
    } catch (e) { if (active) setError(errorText(e)); } })();
    return () => { active = false; };
  }, [runs, offline]);
  if (catalogError) return <div className="empty error" role="alert"><strong>A4 产品候选未能读取</strong><p>{catalogError}</p></div>;
  if (catalog === null) return <div className="loading" role="status"><span className="spinner"/>正在读取 A4 研究产品候选…</div>;
  const sample = details?.find(item => item.summary.execution_source === 'observed_agent_execution') ?? details?.[0] ?? null;
  const contract = sample?.contract ?? null;
  const quote = sample?.quote_result ?? null;
  return <section className="plan-section" aria-label="保险方案">
    <div className="plan-grid">{catalog.plans.map(plan => <A4PlanCard key={plan.product_id} plan={plan} catalog={catalog}/>)}</div>
    <p className="fine-print">以上为 A 交付的两套研究候选产品（参数未绑定，null 一律显示为待定）；前端只接收并展示权威字段，不计算赔款或商业保费。{error && <span role="alert">（交付目录读取失败：{error}，下方工程示例暂不可读）</span>}</p>
    <details className="fold-body engineering-sample"><summary>测算依据与数据要求（A4 候选）</summary>
      <dl>{Object.entries(catalog.premium_method).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
      <h3>必要数据（data_requirements）</h3>
      <ul>{catalog.data_requirements.map(item => <li key={item}>{item}</li>)}</ul>
      <p className="fine-print">来源：{A4_SOURCE_LABEL}；schema：{catalog.schema}；currency：{catalog.currency}；状态：{catalog.status}；commercial_quote=false。</p>
    </details>
    <details className="fold-body engineering-sample"><summary>单事件理算工程示例（不代表 Core / Plus 保险报价）</summary>
      <Badge tone="warning">A0 研究合同 · 分离标注</Badge>
      <p>旧 A0 默认研究合同的单事件工程理算与工程情景样例，仅用于验证展示链路与计算口径；其参数未被 Core / Plus 采用，也不构成商业报价。年度累计限额理算尚未实现。</p>
      <dl>
        <div><dt>合同版本</dt><dd>{contract ? <Id>{contract.contract_version}</Id> : '样例未读取'}</dd></div>
        <div><dt>单事件免赔额（A0 示例）</dt><dd>{contract ? money(contract.deductible_cents) : '—'}</dd></div>
        <div><dt>赔付比例（A0 示例）</dt><dd>{contract ? `${(contract.coinsurance_bp / 100).toFixed(2)}%` : '—'}</dd></div>
        <div><dt>单次赔付限额（A0 示例）</dt><dd>{contract ? money(contract.occurrence_limit_cents) : '—'}</dd></div>
        <div><dt>B0 均值</dt><dd>{quote ? decimalCents(quote.methods.B0.estimated_mean_cents_decimal) : '样例未读取'}</dd></div>
        <div><dt>B0 情景成本</dt><dd>{quote ? decimalCents(quote.methods.B0.scenario_cost_cents_decimal) : '样例未读取'}</dd></div>
        <div><dt>B1 均值</dt><dd>{quote ? decimalCents(quote.methods.B1.estimated_mean_cents_decimal) : '样例未读取'}</dd></div>
        <div><dt>B1 情景成本</dt><dd>{quote ? decimalCents(quote.methods.B1.scenario_cost_cents_decimal) : '样例未读取'}</dd></div>
        <div><dt>B2</dt><dd>{quote ? quote.methods.B2.status : '样例未读取'}</dd></div>
      </dl>
      <p className="fine-print">illustrative · 非本次运行 · commercial_quote=false；示例参数（免赔/比例/限额）与 Core / Plus 的「待定」无关。</p>
    </details>
  </section>;
}
