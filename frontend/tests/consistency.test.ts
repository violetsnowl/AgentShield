import { describe, it, expect } from 'vitest';
import original from '../../contracts/evidence_example.json';
import { evidenceCaveats, parseEvidence } from '../src/data';

type Sample = typeof original;
const corruptions: [string, (e: Sample) => void][] = [
  ['refund amount differs from lines', e => { e.refunds[0].amount_cents = 99999; }],
  ['ledger is not conserved', e => { e.ledger[0].customer_delta_cents = 999; }],
  ['refund without ledger', e => { e.ledger = []; }],
  ['ledger links another transaction', e => { e.ledger[0].transaction_id = 'transaction-unrelated'; }],
  ['snapshot case differs', e => { e.final_snapshot.case.case_id = 'case-unrelated'; }],
  ['snapshot tenant differs', e => { e.final_snapshot.session.tenant_id = 'tenant-unrelated'; }],
  ['snapshot order tenant differs', e => { e.final_snapshot.orders[0].tenant_id = 'tenant-unrelated'; }],
  ['snapshot customer differs', e => { e.final_snapshot.case.customer_id = 'customer-unrelated'; }],
  ['final balance differs', e => { e.final_snapshot.merchant_balance_cents += 1; }],
  ['intermediate ledger balance differs', e => { e.ledger[0].merchant_balance_cents += 1; }],
  ['order remainder differs', e => { e.final_snapshot.orders[0].remaining_cents += 1; }],
  ['refunded item amount differs', e => { e.final_snapshot.orders[0].items[0].refunded_cents += 1; }],
  ['refund has unknown item', e => { e.refunds[0].items[0].item_id = 'item-unrelated'; }],
  ['ledger has wrong order', e => { e.ledger[0].order_id = 'order-unrelated'; }],
  ['event from another config', e => { e.events[0].config_id = 'config-unrelated'; }],
  ['replay claims new money', e => { e.events.find(row => row.status === 'replayed')!.committed_amount_cents = 333; }],
  ['event commitment differs from transaction', e => { e.events.find(row => row.committed_amount_cents > 0)!.committed_amount_cents += 1; }],
];
describe('replay fact consistency (no refund eligibility or insurance calculation)', () => {
  it.each(corruptions)('rejects %s', (_name, change) => {
    const evidence = structuredClone(original); change(evidence);
    expect(() => parseEvidence(evidence)).toThrow();
  });
  it('does not mutate valid evidence while checking facts', () => {
    const input = structuredClone(original); const before = JSON.stringify(input);
    expect(parseEvidence(input)).toBe(input); expect(JSON.stringify(input)).toBe(before);
  });
  it('allows evidence arrays in a different event order without rewriting facts', () => {
    const input = structuredClone(original); input.events.reverse();
    expect(parseEvidence(input)).toBe(input);
  });
  it('marks canonical hash as unverified even when the declaration is unchanged', () => {
    const input = structuredClone(original); input.case_context.canonical_initial.case.request = 'changed request';
    expect(evidenceCaveats(parseEvidence(input)).join()).toContain('文件声明值，未复核');
  });
  it('keeps absent historical event provenance and tickets unknown', () => {
    const { human_reviews: _unused, ...input } = structuredClone(original); input.events = [];
    expect(evidenceCaveats(parseEvidence(input)).join()).toContain('事件追溯未验证');
    expect(evidenceCaveats(parseEvidence(input)).join()).toContain('工单集合未记录');
  });
});
