import { describe, expect, it } from 'vitest';
import { openingSplit } from '../src/data';
import type { EvidenceBundle } from '../src/generated/contract';

/** 最小合成证据（字段与 factory 一致；openingSplit 不重复做校验）。 */
const bundle = (initialCents: number, currentCents: number) => ({
  initial_snapshot: { orders: [{ order_id: 'o1', refunded_cents: initialCents, items: [{ item_id: 'i1', refunded_cents: initialCents, refunded_quantity: initialCents ? 1 : 0 }] }] },
  final_snapshot: { orders: [{ order_id: 'o1', refunded_cents: initialCents + currentCents, items: [{ item_id: 'i1', refunded_cents: initialCents + currentCents, refunded_quantity: (initialCents ? 1 : 0) + (currentCents ? 1 : 0) }] }] },
  refunds: [], events: [], ledger: [],
}) as unknown as EvidenceBundle;

describe('openingSplit', () => {
  it('把期初历史与本轮增量分开（金额与数量）', () => {
    const split = openingSplit(bundle(1500, 500));
    expect(split.total_opening_cents).toBe(1500);
    expect(split.byOrder.get('o1')).toEqual({ opening_cents: 1500, current_cents: 500, opening_quantity: 1, current_quantity: 1 });
    expect(split.byItem.get('i1')?.current_quantity).toBe(1);
  });
  it('无期初历史时全为零增量', () => {
    const split = openingSplit(bundle(0, 250));
    expect(split.total_opening_cents).toBe(0);
    expect(split.byOrder.get('o1')?.opening_cents).toBe(0);
    expect(split.byOrder.get('o1')?.current_cents).toBe(250);
  });
});
