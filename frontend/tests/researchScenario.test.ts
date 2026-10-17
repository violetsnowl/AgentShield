import { describe, expect, it } from 'vitest';
import { parseResearchScenario } from '../src/researchScenario';

const payload = () => ({
  schema: 'AgentShield.research_risk_pricing_result.v0.1', scenario_version: 'study-v1', currency: 'CNY',
  annual_agent_task_volume: 6105,
  categories: [
    ['whole_low', 2059], ['whole_high', 938], ['partial_low', 2145], ['partial_high', 963],
  ].map(([key, count]) => ({ key, label: key, task_count: count, weight: '0.25', accident_probability: '0.01', average_accident_loss_cents: 52000, expected_annual_loss_cents: 1 })),
  premium_loading_ratio: '0.25', expected_annual_economic_loss_cents: 3174600,
  risk_formula: 'R', premium_formula: 'P', claim_formula: 'I',
  plans: ['AgentShield-Core', 'AgentShield-Plus'].map((product_id, index) => ({ product_id, display_name: product_id, contract_version: `v${index}`, deductible_cents: 10000,
    coinsurance_bp: 8000, occurrence_limit_cents: 100000, annual_aggregate_limit_cents: 10000000,
    annual_aggregate_limit_status: 'display_only_not_enforced', covered_loss: 'covered', exclusions: ['excluded'],
    claims_basis: 'claim basis', limit_design: 'limit basis',
    scenario_event_payout_cents: { whole_low: 33600, whole_high: 33600, partial_low: 33600, partial_high: 33600 },
    annual_pure_risk_cost_cents: 2051280, annual_reference_premium_cents: index ? 3586688 : 2564100, commercial_quote: false })),
  contract_context: { policyholder: '模拟投保人', insured: '模拟被保险人', designated_agent: '指定Agent', business_scope: '退款业务', insurance_period: '一年' },
  assumption_notice: '基于假设，非实际测得的损失', experience_pricing_status: 'not_available_research_assumptions_only',
  annual_aggregate_calculation_status: 'display_only_not_enforced', commercial_quote: false,
});

describe('research scenario adapter', () => {
  it('accepts the shared risk and pricing result', () => {
    const result = parseResearchScenario(payload());
    expect(result.expected_annual_economic_loss_cents).toBe(3174600);
    expect(result.plans.map(plan => plan.annual_reference_premium_cents)).toEqual([2564100, 3586688]);
  });

  it('rejects a commercial quote or mismatched population', () => {
    expect(() => parseResearchScenario({ ...payload(), commercial_quote: true })).toThrow(/边界/);
    const broken = payload(); broken.categories[0].task_count = 1;
    expect(() => parseResearchScenario(broken)).toThrow(/不一致/);
  });
});
