import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { api, pairFromFragment } from './api';
import { integrations, evidenceStatePresentation } from './integrations';
import { eventMeaning, evidenceCaveats, money, orderedEvents, parseEvidence, statusText } from './data';
import type { EvidenceBundle, EventPage, FixtureCatalog, Ledger, SessionPage, SessionStatus, ToolEvent } from './generated/contract';

type Area = 'lab' | 'evidence' | 'risk' | 'cost';
type LoadState = 'loading' | 'ready' | 'error';
const areas: { id: Area; title: string; subtitle: string; mark: string }[] = [
  { id: 'lab', title: '企业实验场', subtitle: '消息、订单与商品', mark: '▦' },
  { id: 'evidence', title: '执行证据 / 账本', subtitle: '事件与资金去向', mark: '≡' },
  { id: 'risk', title: '风险 / 配置比较', subtitle: '等待 C 独立核验', mark: '↔' },
  { id: 'cost', title: '合同 / 情景成本', subtitle: '等待 A 理算模块', mark: '◇' },
];
const errorText = (value: unknown) => value instanceof Error ? value.message : '读取失败，请重试。';
function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Id({ children }: { children: ReactNode }) { return <code className="id">{children ?? '未记录'}</code>; }
function Empty({ title, children }: { title: string; children: ReactNode }) { return <div className="empty"><strong>{title}</strong><p>{children}</p></div>; }

function Business({ evidence, focusedOrder }: { evidence: EvidenceBundle; focusedOrder: string | null }) {
  const state = evidence.final_snapshot;
  const context = evidence.case_context;
  return <>
    <section className="case-brief"><div><span className="section-kicker">当前业务请求</span><h2>{state.case.request}</h2><p>只呈现开发模板的公开事实。业务语义与模板仍待 A/C/D 审核。</p></div><Badge tone="warning">开发数据 · 待审</Badge></section>
    <div className="business-columns">
      <section className="panel messages"><div className="section-head"><h2>售后消息</h2><span>{state.case.messages.length} 条公开记录</span></div>
        {state.case.messages.map((message, index) => <article className="message" key={message.message_id}>
          <div className="message-head"><span className="message-number">{index + 1}</span><strong>客户消息</strong><Badge>{message.confirmation ? '附结构化确认' : '无结构化确认'}</Badge></div>
          <p>{message.text}</p><Id>{message.message_id}</Id>
          {message.confirmation && <details><summary>查看确认范围</summary><Id>{message.confirmation.order_id}</Id><ul>{message.confirmation.items.map(line => <li key={line.item_id}><Id>{line.item_id}</Id><span>确认数量 {line.quantity}</span></li>)}</ul></details>}
        </article>)}
      </section>
      <section className="panel orders"><div className="section-head"><h2>订单与商品</h2><span>{state.orders.length} 个会话内订单</span></div>
        {state.orders.map((order, index) => <article className={focusedOrder === order.order_id ? "order highlighted" : "order"} id={`order-${order.order_id}`} key={order.order_id}>
          <div className="order-head"><div><h3>订单 {index + 1}</h3><Id>{order.order_id}</Id></div><Badge tone={order.refunded_cents ? 'good' : ''}>{({ paid: '已支付', partially_refunded: '部分退款', refunded: '已退款' })[order.status]}</Badge></div>
          <div className="order-amounts"><span>实付 <b>{money(order.paid_cents)}</b></span><span>已退 <b>{money(order.refunded_cents)}</b></span><span>剩余 <b>{money(order.remaining_cents)}</b></span></div>
          <div className="table-scroll"><table><thead><tr><th>商品 / 资格</th><th className="number">购买 / 已退 / 可退</th><th className="number">分摊实付</th><th className="number">已退金额</th></tr></thead><tbody>{order.items.map(item => <tr key={item.item_id}><td><strong>{item.name}</strong><span className="cell-note">{item.eligible ? '符合模板资格' : '不符合模板资格'}</span><details><summary>商品 ID</summary><Id>{item.item_id}</Id></details></td><td className="number">{item.quantity} / {item.refunded_quantity} / {item.refundable_quantity}</td><td className="money">{money(item.allocated_paid_cents)}</td><td className="money">{money(item.refunded_cents)}</td></tr>)}</tbody></table></div>
          <p className="fine-print">订单版本 {order.version} · CNY · 模拟原渠道 {order.original_channel}</p>
        </article>)}
      </section>
    </div>
    <section className="panel context"><div className="section-head"><h2>业务初态与版本</h2><Badge>{evidence.case_context_status ?? 'legacy_unavailable'}</Badge></div>
      {context ? <><div className="metadata"><div><span>模板</span><Id>{context.fixture_version}</Id></div><div><span>业务政策</span><Id>{context.policy_version}</Id></div><div><span>执行环境</span><Id>{context.environment_version}</Id></div><div><span>稳定案例</span><Id>{context.case_id}</Id></div></div><div className="hash"><span>规范初态 SHA-256</span><Id>{context.business_initial_hash}</Id><small>文件声明值 · 未复核。不是签名、来源认证或风险成绩。</small></div>
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
  function trace(id: string) { setTransactionId(id); window.setTimeout(() => document.getElementById('trace')?.scrollIntoView({ block: 'nearest' }), 0); }
  return <>
    <section className="ledger-summary"><div><span>已提交退款 · 模拟资金</span><strong className="money" data-testid="committed-total">{money(committed)}</strong><p>{evidence.refunds.length} 笔交易；原键重放不重复计钱</p></div><div><span>商户余额</span><strong className="money">{money(evidence.final_snapshot.merchant_balance_cents)}</strong><p>来自本次运行的最终快照</p></div><div><span>客户余额</span><strong className="money">{money(evidence.final_snapshot.customer_balance_cents)}</strong><p>不是保险赔款或商业报价</p></div></section>
    <section className="panel"><div className="section-head"><h2>执行事件</h2><span>按本次 session 内的 seq 排序</span></div><p className="section-note">B 记录实际到达服务端的事件。C 的本地尝试、超时与响应接收另待接入；服务端提交不证明客户端收到。</p>
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
      {evidence.human_reviews === undefined ? <Empty title="旧 schema 未记录工单集合">未记录不等于确认没有工单。</Empty> : evidence.human_reviews.length === 0 ? <Empty title="暂无人工工单">本次运行没有持久化的人工审核请求。</Empty> : evidence.human_reviews.map(ticket => <article key={ticket.ticket_id} className="ticket"><strong>{ticket.category}</strong><Badge tone="warning">{ticket.status}</Badge><Id>{ticket.ticket_id}</Id><ul>{ticket.missing_facts.map((fact, i) => <li key={i}>{fact}</li>)}</ul><details><summary>查看工单关联记录</summary><pre>{JSON.stringify(ticket, null, 2)}</pre></details></article>)}
    </section>
  </>;
}

export default function App() {
  const [area, setArea] = useState<Area>('lab');
  const [fixtures, setFixtures] = useState<FixtureCatalog['fixtures']>([]);
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [sid, setSid] = useState('');
  const [runFilter, setRunFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [focusedOrder, setFocusedOrder] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [fixtureId, setFixtureId] = useState<'dev-refund-v1' | 'dev-refund-v2'>('dev-refund-v1');
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
  const input = useRef<HTMLInputElement>(null);
  const selection = useRef('');
  const replayMode = useRef(false);
  const interaction = useRef(0);
  const currentIntent = (epoch: number) => interaction.current === epoch;
  selection.current = sid;

  useEffect(() => { setCopied(false); }, [sid]);

  async function catalog(epoch: number) {
    const [f, list] = await Promise.all([api<FixtureCatalog>('api/fixtures'), api<SessionPage>('api/sessions')]);
    if (currentIntent(epoch) && !replayMode.current) {
      setFixtures(f.fixtures); setSessions(list.sessions); setNextOffset(list.next_offset); setCatalogReady(true);
    }
    return list.sessions;
  }
  useEffect(() => {
    let active = true; const epoch = interaction.current;
    (async () => { try { await pairFromFragment(); const list = await catalog(epoch); if (!active || !currentIntent(epoch) || replayMode.current) return;
      if (list.length) setSid(list.find(row => row.case_id === 'dev-case-refund-v1')?.session_id ?? list[0].session_id);
      else setState('ready');
    } catch (e) { if (active && currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } } })();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!sid || offline) return;
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

  async function loadService(epoch: number) {
    setState('loading'); setError('');
    try {
      const list = await catalog(epoch);
      if (!currentIntent(epoch) || replayMode.current) return;
      if (list.length) setSid(list[0].session_id); else setState('ready');
    } catch (e) { if (currentIntent(epoch) && !replayMode.current) { setError(errorText(e)); setState('error'); } }
  }
  function retry() {
    const epoch = ++interaction.current;
    if (sid && catalogReady && !replayMode.current) { setRefresh(v => v + 1); return; }
    void loadService(epoch);
  }
  function returnToService() {
    const epoch = ++interaction.current; replayMode.current = false;
    setOffline(false); setBundle(null); setEvents([]); setSid(''); setCatalogReady(false); setActionError('');
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
      setBundle(null); setSid(result.session.session_id); setArea('lab');
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
      replayMode.current = true; setOffline(true); setSid(evidence.final_snapshot.session.session_id); setBundle(evidence); setEvents(orderedEvents(evidence.events)); setState('ready'); setError(''); setPageError(''); setActionError(''); setArea('evidence');
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
  const visibleRuns = sessions.filter(row => (!runFilter || [row.case_id, row.session_id, row.episode_id, row.config_id].some(value => value.toLowerCase().includes(runFilter.toLowerCase()))) && (sourceFilter === 'all' || row.sources.execution_source === sourceFilter));
  const selectedOutsideFilter = sessions.find(row => row.session_id === sid && !visibleRuns.some(item => item.session_id === sid));
  function showOrder(id: string) {
    setFocusedOrder(id); setArea('lab');
    window.setTimeout(() => document.getElementById(`order-${id}`)?.scrollIntoView({ block: 'center', behavior: 'auto' }), 0);
  }
  async function copyIdentity() {
    if (!session) return;
    try { await navigator.clipboard.writeText(JSON.stringify({ case_id: session.case_id, session_id: session.session_id, episode_id: session.episode_id })); setCopied(true); }
    catch { setActionError('复制不可用，请展开运行身份并手动复制。'); }
  }
  const current = bundle?.final_snapshot.session.session_id === sid ? bundle : null;
  const session = current?.final_snapshot.session ?? sessions.find(row => row.session_id === sid);
  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={e => e.preventDefault()}><span className="brand-mark" aria-hidden="true">◈</span><span>AgentShield<small>保险风险评测工作台</small></span></a>
      <nav aria-label="工作区域">{areas.map(item => <button key={item.id} className={area === item.id ? 'nav-item active' : 'nav-item'} aria-current={area === item.id ? 'page' : undefined} onClick={() => setArea(item.id)}><span className="nav-mark" aria-hidden="true">{item.mark}</span><span>{item.title}<small>{item.subtitle}</small></span></button>)}</nav>
      <div className="sidebar-note"><Badge>本机开发环境</Badge><p>工程事实可追溯<br/>业务语义仍待审核</p><small>bc-0.3-candidate<br/>七工具 · 模拟资金</small></div>
    </aside>
    <main><header className="page-header"><div><span className="breadcrumb">BD 联合开发 / 阶段 04</span><h1>{areas.find(item => item.id === area)?.title}</h1><p>先选择一次运行，再阅读事实与证据。</p></div><div className="header-actions"><Badge tone={offline ? 'warning' : state === 'error' ? 'error' : state === 'loading' ? '' : 'good'}>{offline ? '本地文件 · 只读回放' : state === 'error' ? '读取失败' : state === 'loading' ? '正在读取' : 'B 本机服务'}</Badge><button onClick={() => input.current?.click()}>导入回放</button><input ref={input} className="file-input" type="file" accept="application/json,.json" aria-label="导入证据文件" onChange={importFile}/></div></header>
      {offline ? <div className="notice warning" role="status"><strong>离线只读回放</strong>　内容来自所选文件，未经签名认证；不代表本机最新状态。切换功能区不会调用 B，也不会重新执行退款。<button onClick={returnToService}>返回本机服务</button></div>
        : <section className="run-controls" aria-label="运行选择"><details className="filter-disclosure"><summary>筛选运行 · 已加载 {sessions.length} 条</summary><div className="run-filters"><label>筛选已加载运行<input aria-label="筛选已加载运行" value={runFilter} onChange={e => setRunFilter(e.target.value)} placeholder="case / session / episode / 配置"/></label><label>执行来源<select aria-label="执行来源筛选" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}><option value="all">全部来源</option>{['scripted_test','mock_agent','observed_agent_execution'].map(value => <option key={value} value={value}>{value}</option>)}</select></label><span>已加载 {sessions.length}，匹配 {visibleRuns.length}。{nextOffset !== null ? '还有后续页，可继续加载。' : '目录已完整加载。'}</span>{visibleRuns.length === 0 && catalogReady && <span role="status">没有匹配的已加载运行；当前选择保持不变。</span>}</div></details><div className="run-picker"><label htmlFor="run">当前运行（session / episode 独立）</label><select id="run" value={sid} onChange={e => { ++interaction.current; replayMode.current = false; setFocusedOrder(null); setCopied(false); setSid(e.target.value); setArea('lab'); }} disabled={!catalogReady || creating}><option value="" disabled>选择具体运行</option>{selectedOutsideFilter && <option value={selectedOutsideFilter.session_id}>当前选择（筛选外）｜{selectedOutsideFilter.session_id}</option>}{visibleRuns.map(row => <option key={row.session_id} value={row.session_id}>{row.case_id} ｜ {row.session_id}</option>)}</select>{nextOffset !== null && <button className="text-button" onClick={moreRuns}>加载更多运行</button>}</div><div className="new-run"><label htmlFor="fixture">创建会话所用模板</label><div><select id="fixture" value={fixtureId} disabled={!catalogReady || creating} onChange={e => setFixtureId(e.target.value as typeof fixtureId)}>{fixtures.length ? fixtures.map(fixture => <option key={fixture.fixture_id} value={fixture.fixture_id}>{fixture.fixture_id}</option>) : <option value="dev-refund-v1">正在读取模板</option>}</select><button className="primary" onClick={create} disabled={!catalogReady || creating}>{creating ? '正在创建…' : '创建开发会话'}</button></div></div></section>}
      {actionError && <div role="alert" className="notice error">{actionError}</div>}
      {session && <div className="identity-compact"><details className="run-identity"><summary><strong>{session.case_id}</strong><span>本次运行 …{session.session_id.slice(-8)}</span><Badge tone="good">{session.status === 'finished' ? '已结束' : '进行中'}</Badge><span className="fine-print">展开 session / episode / 版本</span></summary><div className="identity-fields"><div><span>{current?.case_context ? '稳定 case' : 'case（按原记录）'}</span><Id>{session.case_id}</Id></div><div><span>本次 session</span><Id>{session.session_id}</Id></div><div><span>本次 episode</span><Id>{session.episode_id}</Id></div><div>版本 {session.version} · <Id>{session.config_id}</Id></div></div></details><button onClick={copyIdentity}>{copied ? '已复制身份' : '复制运行身份'}</button></div>}

      <div className="execution-bar"><div><Badge tone="warning">{current ? current.sources.execution_source ?? '执行来源未记录' : '开发环境'}</Badge><span>{current ? current.sources.fixture_source ?? '模板来源未记录' : 'development_only'} · 来源标签不证明真实模型运行</span></div><div><button disabled aria-describedby="runner-note">启动 Agent</button><span id="runner-note">C 正式运行器尚未接入</span></div></div>
      {state === 'loading' && <div className="loading" role="status" aria-live="polite"><span className="spinner"/>正在读取本次运行的真实数据…</div>}
      {state === 'error' && <div role="alert" className="empty error"><strong>当前数据未能加载</strong><p>{error}</p><button onClick={retry}>重试读取</button><p className="fine-print">也可以导入已保存的证据，进行离线只读回放。</p></div>}
      {state === 'ready' && !current && <Empty title="还没有开发会话">选择一个受控模板并创建会话，即可查看业务初态。创建会话不会调用模型或提交退款。</Empty>}
      {state === 'ready' && current && <>
        <div className="content-toolbar"><span>证据 schema {current.schema_version} · {current.contract_version ?? '历史未记录版本'} · {offline ? '文件导出时间' : '快照导出时间'} {current.exported_at.replace('T', ' ').slice(0, 19)} UTC</span><div>{!offline && <button onClick={() => { ++interaction.current; setRefresh(v => v + 1); }}>刷新本次运行</button>}<button onClick={saveReplay}>保存证据回放</button></div></div>
        <details className="notice warning"><summary>证据核对范围 · 来源未认证 / 初态哈希未复核</summary><ul>{evidenceCaveats(current).map(note => <li key={note}>{note}</li>)}</ul></details>
        {area === 'lab' && <Business evidence={current} focusedOrder={focusedOrder}/>}
        {area === 'evidence' && <Evidence key={sid} evidence={current} events={events} more={!offline && events.length < current.events.length} onMore={moreEvents} paging={paging} pageError={pageError} onOrder={showOrder}/>}
      </>}
      {(area === 'risk' || area === 'cost') && <PendingModule area={area} evidence={state === 'ready' ? current : null}/>}
      <footer>开发模板不属于正式任务或 Gold。A/C 审核与 C 独立消费者签收仍待完成。</footer>
    </main>
  </div>;
}

function PendingModule({ area, evidence }: { area: 'risk' | 'cost'; evidence: EvidenceBundle | null }) {
  const risk = area === 'risk';
  const slot = integrations.find(item => item.owner === (risk ? 'C' : 'A'))!;
  return <section className="integration-panel" aria-label={risk ? '风险比较待接入' : '合同理算待接入'}>
    <div className="integration-lead"><span className="integration-mark" aria-hidden="true">{risk ? '↔' : '◇'}</span><div><Badge tone="warning">待接入 · {slot.owner} 模块</Badge><h2>{risk ? '尚未评测，保留判断' : '尚无报价，等待合同依据'}</h2><p>{slot.reason}</p></div></div>
    <div className="integration-body"><div><h3>{risk ? '已有的工程证据' : '可供接入的运行证据'}</h3><p>{evidence ? '已选择一次独立运行，可以查看它的事件与模拟资金账本。' : '选择本机运行或导入证据后，可查看 B 的公开工程事实。'}</p>
      <dl><div><dt>证据格式</dt><dd>{evidence ? `schema ${evidence.schema_version}` : '尚未选择'}</dd></div><div><dt>运行配置</dt><dd><Id>{evidence?.final_snapshot.session.config_id ?? '尚未选择'}</Id></dd></div><div><dt>规范业务初态</dt><dd>{evidence?.case_context ? '已记录，仅用于初态核对' : '不可用 / 未选择'}</dd></div></dl>
      <p className="fine-print">业务退款金额不是独立损失、风险等级或保险赔款。开发执行不计为正式模型结果。</p></div>
      <div><h3>{risk ? '待 C 提供' : '待 A 提供'}</h3><ul>{(risk ? ['正式运行清单与配置、预算及失败记录', 'LossResult 与独立核验的损失依据', '配对条件、证据不足与未知状态'] : ['QuoteResult 与合同版本', '权重、证据状态与理算依据', '情景成本与 B0 / B1 展示契约']).map(text => <li key={text}>{text}<Badge tone="warning">待接入</Badge></li>)}</ul>
      <button disabled aria-describedby={`pending-${area}`}>{risk ? '查看损失依据' : '重新理算'}</button><p className="fine-print" id={`pending-${area}`}>{risk ? 'C 尚未交付正式结果，不生成比较成绩。' : 'A 尚未交付模块，前端不实现第二套保险公式。'}</p></div></div>
    <div className="integration-foot"><strong>仅研究情景 · commercial_quote=false · 非商业报价</strong><p>{slot.contract} 适配状态：{slot.state}。{slot.message}</p><details><summary>证据状态说明（不是当前实验结果）</summary><div className="state-guide">{Object.entries(evidenceStatePresentation).map(([key, value]) => <div key={key}><Badge tone={value.tone}>{value.title} / {key}</Badge><p>{value.text}</p></div>)}</div></details></div>
    <div className="integration-foot">{slot.contract} 展示位置已预留；字段与语义须由模块负责人审核后接入，本轮未冻结其契约。</div>
  </section>;
}
