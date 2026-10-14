import validate from './generated/evidence.validator.cjs';
import type { EvidenceBundle, ToolEvent } from './generated/contract';

const secretKey = /^(session_token|admin_token|authorization|api_key|access_token|password|secret)$/i;

export function hasSecretKeys(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, child]) => secretKey.test(key) || hasSecretKeys(child));
}

export function parseEvidence(value: unknown, expectedSession?: string): EvidenceBundle {
  if (hasSecretKeys(value) || !validate(value)) throw new Error('证据格式不符合 schema 1/2/3，或包含凭据字段。');
  const evidence = value as EvidenceBundle;
  if (![1, 2, 3].includes(evidence.schema_version ?? 0)) throw new Error('证据必须明确声明 schema 1/2/3。');
  function checkNumbers(node: unknown) {
    if (!node || typeof node !== 'object') return;
    for (const [key, child] of Object.entries(node)) {
      if (['raw_arguments', 'validated_arguments', 'result', 'error'].includes(key)) continue;
      if ((key.endsWith('_cents') || key === 'seq') && typeof child === 'number' && !Number.isSafeInteger(child))
        throw new Error('证据金额或序号超出浏览器可精确表示的整数范围。');
      checkNumbers(child);
    }
  }
  checkNumbers(evidence);
  if (!Number.isSafeInteger(evidence.refunds.reduce((sum, row) => sum + row.amount_cents, 0)))
    throw new Error('退款合计超出浏览器可精确表示的整数范围。');
  const first = evidence.initial_snapshot.session;
  const last = evidence.final_snapshot.session;
  if ((expectedSession && last.session_id !== expectedSession) || first.session_id !== last.session_id
      || first.episode_id !== last.episode_id || first.case_id !== last.case_id)
    throw new Error('证据包含不一致的运行身份，已停止展示。');
  for (const row of [...evidence.events, ...evidence.refunds, ...evidence.ledger, ...(evidence.human_reviews ?? [])]) {
    if (row.session_id !== last.session_id) throw new Error('证据混入其他 session，已停止展示。');
  }
  const seq = new Set<number>();
  for (const event of evidence.events) {
    if (event.episode_id !== last.episode_id || event.case_id !== last.case_id || seq.has(event.seq))
      throw new Error('事件身份或顺序编号不一致。');
    seq.add(event.seq);
  }
  if ((evidence.case_context_status === 'recorded') !== (evidence.case_context != null))
    throw new Error('案例上下文状态与内容不一致。');
  if (evidence.case_context && evidence.case_context.case_id !== last.case_id)
    throw new Error('案例上下文不属于本次运行。');
  if (new Set(evidence.refunds.map(row => row.transaction_id)).size !== evidence.refunds.length
      || new Set(evidence.ledger.map(row => row.transaction_id)).size !== evidence.ledger.length)
    throw new Error('证据含重复交易，无法展示可靠的资金合计。');
  checkFactConsistency(evidence);
  // Legacy absence is retained; never derive a mapping/hash from runtime IDs.
  return evidence;
}

// Fact equalities only: never infer eligibility, legal obligation, loss or insurance payout.
function checkFactConsistency(e: EvidenceBundle) {
  const requireFact = (ok: boolean, detail: string) => { if (!ok) throw new Error(`证据事实不一致：${detail}，已停止导入 / 展示。`); };
  const sum = (values: number[]) => values.reduce((a, b) => a + BigInt(b), 0n);
  const unique = (values: string[]) => new Set(values).size === values.length;
  const first = e.initial_snapshot, last = e.final_snapshot, identity = last.session;
  for (const key of ['tenant_id', 'experiment_id', 'config_id'] as const)
    requireFact(first.session[key] === identity[key], `运行 ${key}`);
  requireFact(first.case.customer_id === last.case.customer_id, '运行客户');
  for (const snapshot of [first, last]) {
    requireFact(snapshot.case.case_id === identity.case_id, '快照 case');
    requireFact(unique(snapshot.orders.map(o => o.order_id)), '重复订单');
    requireFact(unique(snapshot.case.messages.map(m => m.message_id)), '重复消息');
    requireFact(snapshot.case.messages.every(m => m.customer_id === snapshot.case.customer_id), '消息客户');
    requireFact(snapshot.case.candidate_order_ids.every(id => snapshot.orders.some(o => o.order_id === id)), '候选订单关联');
    for (const order of snapshot.orders) {
      requireFact(order.tenant_id === identity.tenant_id && order.customer_id === snapshot.case.customer_id, '订单归属');
      requireFact(BigInt(order.paid_cents) === BigInt(order.refunded_cents) + BigInt(order.remaining_cents), '订单实付 / 已退 / 剩余');
      requireFact(unique(order.items.map(i => i.item_id)), '重复商品');
      requireFact(sum(order.items.map(i => i.allocated_paid_cents)) === BigInt(order.paid_cents)
        && sum(order.items.map(i => i.refunded_cents)) === BigInt(order.refunded_cents), '商品行与订单金额');
    }
  }
  requireFact(first.orders.length === last.orders.length && first.orders.every(o => last.orders.some(x => x.order_id === o.order_id)), '初末订单集合');
  requireFact(unique(e.events.map(row => row.event_id)) && unique(e.ledger.map(row => row.entry_id)), '重复事件 / 账本编号');
  requireFact(e.refunds.length === e.ledger.length, '退款与账本缺失关联');
  let merchant = BigInt(first.merchant_balance_cents), customer = BigInt(first.customer_balance_cents);
  for (const refund of [...e.refunds].sort((a, b) => a.session_version_after - b.session_version_after)) {
    const order = last.orders.find(o => o.order_id === refund.order_id);
    const entry = e.ledger.find(row => row.transaction_id === refund.transaction_id);
    requireFact(!!order && !!entry && entry.order_id === refund.order_id, '交易 / 订单 / 账本关联');
    requireFact(unique(refund.items.map(i => i.item_id)) && refund.items.every(i => order!.items.some(x => x.item_id === i.item_id)), '退款商品关联');
    requireFact(sum(refund.items.map(i => i.amount_cents)) === BigInt(refund.amount_cents), '退款总额与商品行小计');
    requireFact(BigInt(entry!.merchant_delta_cents) === -BigInt(refund.amount_cents)
      && BigInt(entry!.customer_delta_cents) === BigInt(refund.amount_cents), '账本双边增量与退款');
    merchant += BigInt(entry!.merchant_delta_cents); customer += BigInt(entry!.customer_delta_cents);
    requireFact(merchant === BigInt(entry!.merchant_balance_cents) && customer === BigInt(entry!.customer_balance_cents), '账本逐笔余额');
  }
  requireFact(merchant === BigInt(last.merchant_balance_cents) && customer === BigInt(last.customer_balance_cents), '期初 + 已提交变化 ≠ 期末');
  for (const order of last.orders) {
    const initial = first.orders.find(o => o.order_id === order.order_id)!;
    const refunds = e.refunds.filter(r => r.order_id === order.order_id);
    requireFact(order.paid_cents === initial.paid_cents && BigInt(order.refunded_cents) === BigInt(initial.refunded_cents) + sum(refunds.map(r => r.amount_cents)), '订单退款增量');
    requireFact(order.items.length === initial.items.length && order.items.every(i => initial.items.some(x => x.item_id === i.item_id)), '初末商品集合');
    for (const item of order.items) {
      const before = initial.items.find(i => i.item_id === item.item_id)!;
      const lines = refunds.flatMap(r => r.items).filter(i => i.item_id === item.item_id);
      requireFact(item.allocated_paid_cents === before.allocated_paid_cents && item.quantity === before.quantity, '商品初始实付 / 数量');
      requireFact(BigInt(item.refunded_cents) === BigInt(before.refunded_cents) + sum(lines.map(i => i.amount_cents))
        && BigInt(item.refunded_quantity) === BigInt(before.refunded_quantity) + sum(lines.map(i => i.quantity)), '商品已退增量');
    }
  }
  const commits = new Set<string>();
  for (const event of e.events) {
    requireFact(event.experiment_id === identity.experiment_id && event.config_id === identity.config_id, '事件运行配置');
    const refund = e.refunds.find(r => r.transaction_id === event.transaction_id);
    if (event.transaction_id) requireFact(!!refund, '事件交易关联');
    if (event.status === 'succeeded' && event.tool_name === 'submit_refund') {
      requireFact(!!refund && !commits.has(refund.transaction_id) && event.committed_amount_cents === refund.amount_cents, '事件提交金额 / 唯一提交');
      commits.add(refund!.transaction_id);
    } else requireFact(event.committed_amount_cents === 0, '读取 / 拒绝 / 错误 / 重放不能新增资金');
  }
  requireFact((e.human_reviews ?? []).every(t => t.case_id === identity.case_id), '工单 case');
}

export function evidenceCaveats(e: EvidenceBundle): string[] {
  const notes = ['已核对已记录字段的身份、金额及账本恒等关系；不证明来源真实、业务合法或损失核验通过。'];
  notes.push(e.case_context ? '规范初态哈希为文件声明值，未复核；不是签名或来源认证。' : '历史案例映射 / 初态哈希不可用，未补造。');
  if (e.human_reviews === undefined) notes.push('工单集合未记录，不等于没有工单。');
  if (e.refunds.some(r => !e.events.some(event => event.transaction_id === r.transaction_id && event.status === 'succeeded' && event.tool_name === 'submit_refund')))
    notes.push('部分退款未附成功提交事件，事件追溯未验证；不补造事件。');
  return notes;
}

export function money(cents: number): string {
  if (!Number.isSafeInteger(cents)) throw new Error('金额不是安全整数分。');
  const abs = Math.abs(cents);
  return `${cents < 0 ? '−' : ''}¥${Math.floor(abs / 100).toLocaleString('zh-CN')}.${String(abs % 100).padStart(2, '0')}`;
}

export const statusText = { succeeded: '成功', rejected: '拒绝', replayed: '原键重放', error: '错误' } as const;
export function eventMeaning(event: ToolEvent): string {
  if (event.status === 'replayed') return '返回原结果 · 无新增资金';
  if (event.status === 'rejected' || event.status === 'error') return '未新增提交';
  if (event.transaction_id && event.committed_amount_cents > 0) return '退款已提交';
  if (event.ticket_id) return '工单已持久化 · 无资金';
  if (event.tool_name === 'finish_case') return '结果声明 · 非核验';
  return '读取成功 · 非付款';
}
export function orderedEvents(events: ToolEvent[]) { return [...events].sort((a, b) => a.seq - b.seq); }


export type OpeningSplit = {
  byOrder: Map<string, { opening_cents: number; current_cents: number; opening_quantity: number; current_quantity: number }>;
  byItem: Map<string, { opening_cents: number; current_cents: number; opening_quantity: number; current_quantity: number }>;
  total_opening_cents: number;
};

/**
 * 期初历史退款拆分（V1.2 §26.4-1 / N08）：session 开始前的已退事实与本轮增量分开呈现。
 * 事实恒等关系已由 parseEvidence 校验；本函数只做读数与拆分，不推断责任、损失或赔款。
 */
export function openingSplit(e: EvidenceBundle): OpeningSplit {
  const byOrder: OpeningSplit['byOrder'] = new Map();
  const byItem: OpeningSplit['byItem'] = new Map();
  let total = 0;
  for (const order of e.final_snapshot.orders) {
    const before = e.initial_snapshot.orders.find(row => row.order_id === order.order_id);
    if (!before) continue;
    const openingQty = before.items.reduce((sum, item) => sum + item.refunded_quantity, 0);
    const currentQty = order.items.reduce((sum, item) => sum + item.refunded_quantity, 0) - openingQty;
    byOrder.set(order.order_id, { opening_cents: before.refunded_cents, current_cents: order.refunded_cents - before.refunded_cents, opening_quantity: openingQty, current_quantity: currentQty });
    total += before.refunded_cents;
    for (const item of order.items) {
      const prior = before.items.find(row => row.item_id === item.item_id);
      if (!prior) continue;
      byItem.set(item.item_id, { opening_cents: prior.refunded_cents, current_cents: item.refunded_cents - prior.refunded_cents, opening_quantity: prior.refunded_quantity, current_quantity: item.refunded_quantity - prior.refunded_quantity });
    }
  }
  return { byOrder, byItem, total_opening_cents: total };
}
