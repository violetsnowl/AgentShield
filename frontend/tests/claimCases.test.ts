import { describe, it, expect } from 'vitest';
import { accidentRate, claimSummary, parseClaimCatalog, payoutLabel, rateRange } from '../src/claimCases';
import type { ClaimCase } from '../src/claimCases';

const arm = { batch_id: 'b', model: 'mimo-v2.6-flash', tasks: '加难任务', control_profile: 'P0', control_label: 'P0 裸接口',
  runs: 210, accidents: 45, rate_low: 0.164, rate_high: 0.275, net_loss_cents: 2460666, blocked_runs: 0 };
const row: ClaimCase = { case_id: '0123456789abcdef0123', batch_id: 'b', model: 'mimo-v2.6-flash', control_label: 'P0 裸接口',
  family_label: '跨单混合', net_loss_cents: 436306, payout_cents: 100000, claim_status: 'assessed', available: true };
const payload = { contract_version: 'claim-cases-0.1-candidate', commercial_quote: false, experiment_nature: '压力测试', arms: [arm], cases: [row] };

describe('权限档位对照与理赔材料', () => {
  it('reads the catalog', () => {
    const catalog = parseClaimCatalog(payload);
    expect(catalog.arms).toHaveLength(1);
    expect(catalog.cases[0].family_label).toBe('跨单混合');
  });

  it('refuses an unknown shape or a commercial quote', () => {
    expect(() => parseClaimCatalog({ ...payload, contract_version: 'other' })).toThrow();
    expect(() => parseClaimCatalog({ ...payload, commercial_quote: true })).toThrow();
    expect(() => parseClaimCatalog(null)).toThrow();
  });

  it('refuses counts that cannot be true', () => {
    expect(() => parseClaimCatalog({ ...payload, arms: [{ ...arm, accidents: 211 }] })).toThrow();
    expect(() => parseClaimCatalog({ ...payload, arms: [{ ...arm, net_loss_cents: null }] })).toThrow();
    expect(() => parseClaimCatalog({ ...payload, cases: [{ ...row, case_id: '../etc/passwd' }] })).toThrow();
  });

  it('formats rates and their range', () => {
    expect(accidentRate(arm)).toBe('21.4%');
    expect(rateRange(arm)).toBe('16.4%–27.5%');
    expect(accidentRate({ ...arm, runs: 0, accidents: 0 })).toBe('—');
    expect(rateRange({ ...arm, rate_low: null })).toBe('—');
  });

  it('never shows an undecided payout as zero', () => {
    expect(payoutLabel(row)).toBe('¥1,000.00');
    expect(payoutLabel({ ...row, payout_cents: null, claim_status: 'needs_review' })).toBe('待人工认定');
    expect(payoutLabel({ ...row, payout_cents: 0, claim_status: 'not_covered' })).toBe('不属于保险责任');
  });

  it('adds only assessed payouts and counts the rest as pending', () => {
    const catalog = parseClaimCatalog({ ...payload, cases: [row, { ...row, case_id: 'f123456789abcdef0123', net_loss_cents: 5000, payout_cents: null, claim_status: 'needs_review' }] });
    expect(claimSummary(catalog)).toEqual({ count: 2, lossCents: 441306, assessedPayoutCents: 100000, pending: 1 });
  });
});
