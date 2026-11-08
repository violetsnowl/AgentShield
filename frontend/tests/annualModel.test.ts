import { describe, expect, it } from 'vitest';
import { contractLine, enhancedPremium, parseAnnualSummary, percent, tierPremium, yuan } from '../src/annualModel';
import type { TierRow } from '../src/annualModel';

const tier: TierRow = { tier: 'B', label: '低思考 + P0 或 P1', monitored: false, accidents: 1, runs: 210, pricing_frequency: 0.026476, expected_events: 132,
  uninsured_mean_yuan: 82668, uninsured_cte99_yuan: 356209, premium_yuan: 6599, insured_cte99_yuan: 197841, premium_capital_yuan: 13000, claim_year_chance: 0.0209, insurable: true, enhanced_offered: true, enhanced_premium_yuan: 17950, enhanced_premium_capital_yuan: 21000, enhanced_cte99_yuan: 125584 };
const payload = () => ({ schema: 'AgentShield.annual_summary.v0.1', commercial_quote: false, nature: '研究测算', premium_with_capital_yuan: [22013, 39375],
  contracts: [{ contract_version: 'v', product_tier: '基础档', annual_aggregate_deductible_cents: 15000000, coinsurance_bp: 8000, annual_limit_cents: 30000000 },
    { contract_version: 'e', product_tier: '增强档', annual_aggregate_deductible_cents: 8000000, coinsurance_bp: 9000, annual_limit_cents: 30000000 }],
  structures: [{ label: '不投保', premium_yuan: 0, premium_capital_yuan: 0, mean_yuan: 82668, p99_yuan: 339500, cte99_yuan: 356209 }], tiers: [tier], latency: [{ hours: 24, loud_fault_loss_yuan: 265899 }] });

describe('annual model view', () => {
  it('keeps the stored numbers', () => {
    const summary = parseAnnualSummary(payload());
    expect(summary.tiers[0].premium_yuan).toBe(6599);
    expect(summary.latency[0].loud_fault_loss_yuan).toBe(265899);
  });

  it('refuses a commercial quote or another schema', () => {
    expect(() => parseAnnualSummary({ ...payload(), commercial_quote: true })).toThrow('格式不匹配');
    expect(() => parseAnnualSummary({ ...payload(), schema: 'other' })).toThrow('格式不匹配');
  });

  it('refuses a missing amount instead of showing zero', () => {
    const broken = payload();
    broken.structures[0] = { ...broken.structures[0], cte99_yuan: null as unknown as number };
    expect(() => parseAnnualSummary(broken)).toThrow('不完整');
  });

  it('refuses a zero pricing frequency', () => {
    const broken = payload();
    broken.tiers = [{ ...tier, pricing_frequency: 0 }];
    expect(() => parseAnnualSummary(broken)).toThrow('不完整');
  });

  it('writes the contract in plain words', () => {
    expect(contractLine(payload().contracts[0])).toBe('基础档：年度累计免赔 ¥150,000，超过部分赔 80%，年度限额 ¥300,000');
    expect(contractLine(payload().contracts[1])).toBe('增强档：年度累计免赔 ¥80,000，超过部分赔 90%，年度限额 ¥300,000');
  });

  it('does not quote a premium for a configuration that must be fixed first', () => {
    expect(tierPremium(tier)).toBe('¥6,599–¥13,000');
    expect(enhancedPremium(tier)).toBe('¥17,950–¥21,000');
    expect(enhancedPremium({ ...tier, enhanced_offered: false })).toBe('先整改，不承保');
    expect(tierPremium({ ...tier, insurable: false })).toBe('先整改，不承保');
  });

  it('refuses a summary without both tiers', () => {
    expect(() => parseAnnualSummary({ ...payload(), contracts: [payload().contracts[0]] })).toThrow('格式不匹配');
    expect(() => parseAnnualSummary({ ...payload(), premium_with_capital_yuan: [22013] })).toThrow('不完整');
  });

  it('formats money and rates', () => {
    expect(yuan(1234567)).toBe('¥1,234,567');
    expect(percent(0.026476)).toBe('2.65%');
  });
});
