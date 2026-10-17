export type ResearchCategory = {
  key: 'whole_low' | 'whole_high' | 'partial_low' | 'partial_high';
  label: string;
  task_count: number;
  weight: string;
  accident_probability: string;
  average_accident_loss_cents: number;
  expected_annual_loss_cents: number;
};

export type ResearchPlan = {
  product_id: 'AgentShield-Core' | 'AgentShield-Plus';
  display_name: string;
  contract_version: string;
  deductible_cents: number;
  coinsurance_bp: number;
  occurrence_limit_cents: number;
  annual_aggregate_limit_cents: number;
  annual_aggregate_limit_status: 'display_only_not_enforced';
  covered_loss: string;
  exclusions: string[];
  claims_basis: string;
  limit_design: string;
  scenario_event_payout_cents: Record<ResearchCategory['key'], number>;
  annual_pure_risk_cost_cents: number;
  annual_reference_premium_cents: number;
  commercial_quote: false;
};

export type ResearchScenario = {
  schema: 'AgentShield.research_risk_pricing_result.v0.1';
  scenario_version: string;
  currency: 'CNY';
  annual_agent_task_volume: number;
  categories: ResearchCategory[];
  premium_loading_ratio: string;
  expected_annual_economic_loss_cents: number;
  risk_formula: string;
  premium_formula: string;
  claim_formula: string;
  plans: ResearchPlan[];
  contract_context: { policyholder: string; insured: string; designated_agent: string; business_scope: string; insurance_period: string };
  assumption_notice: string;
  experience_pricing_status: 'not_available_research_assumptions_only';
  annual_aggregate_calculation_status: 'display_only_not_enforced';
  commercial_quote: false;
};

const object = (value: unknown, name: string): Record<string, unknown> => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(`${name}格式无效。`);
  return value as Record<string, unknown>;
};
const text = (value: unknown, name: string) => {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`${name}格式无效。`);
  return value;
};
const integer = (value: unknown, name: string) => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error(`${name}格式无效。`);
  return value;
};
const texts = (value: unknown, name: string) => {
  if (!Array.isArray(value)) throw new Error(`${name}格式无效。`);
  return value.map((item, index) => text(item, `${name}[${index}]`));
};

export function parseResearchScenario(value: unknown): ResearchScenario {
  const raw = object(value, '研究情景');
  if (raw.schema !== 'AgentShield.research_risk_pricing_result.v0.1' || raw.currency !== 'CNY'
      || raw.commercial_quote !== false || raw.experience_pricing_status !== 'not_available_research_assumptions_only'
      || raw.annual_aggregate_calculation_status !== 'display_only_not_enforced') throw new Error('研究情景边界无效。');
  const volume = integer(raw.annual_agent_task_volume, '年度任务量');
  if (!Array.isArray(raw.categories) || raw.categories.length !== 4) throw new Error('研究情景必须包含四类业务。');
  const categoryKeys = ['whole_low', 'whole_high', 'partial_low', 'partial_high'] as const;
  const categories = raw.categories.map((value, index) => {
    const row = object(value, `类别${index}`); const key = text(row.key, '类别键');
    if (!categoryKeys.includes(key as ResearchCategory['key'])) throw new Error('研究情景类别无效。');
    return { key: key as ResearchCategory['key'], label: text(row.label, '类别名称'), task_count: integer(row.task_count, '类别任务量'),
      weight: text(row.weight, '类别权重'), accident_probability: text(row.accident_probability, '事故概率'),
      average_accident_loss_cents: integer(row.average_accident_loss_cents, '平均损失'),
      expected_annual_loss_cents: integer(row.expected_annual_loss_cents, '预期损失') };
  });
  if (new Set(categories.map(row => row.key)).size !== 4 || categories.reduce((sum, row) => sum + row.task_count, 0) !== volume) throw new Error('研究情景类别任务量不一致。');
  if (!Array.isArray(raw.plans) || raw.plans.length !== 2) throw new Error('研究情景必须包含Core和Plus。');
  const plans = raw.plans.map((value, index) => {
    const row = object(value, `方案${index}`); const productId = text(row.product_id, '产品ID');
    if (!['AgentShield-Core', 'AgentShield-Plus'].includes(productId) || row.commercial_quote !== false || row.annual_aggregate_limit_status !== 'display_only_not_enforced') throw new Error('研究保险方案边界无效。');
    const payouts = object(row.scenario_event_payout_cents, '分类赔款');
    return { product_id: productId as ResearchPlan['product_id'], display_name: text(row.display_name, '方案名称'),
      contract_version: text(row.contract_version, '合同版本'), deductible_cents: integer(row.deductible_cents, '免赔额'),
      coinsurance_bp: integer(row.coinsurance_bp, '赔付比例'), occurrence_limit_cents: integer(row.occurrence_limit_cents, '单次限额'),
      annual_aggregate_limit_cents: integer(row.annual_aggregate_limit_cents, '年度限额'), annual_aggregate_limit_status: 'display_only_not_enforced' as const,
      covered_loss: text(row.covered_loss, '保险责任'), exclusions: texts(row.exclusions, '责任免除'),
      claims_basis: text(row.claims_basis, '理赔基础'), limit_design: text(row.limit_design, '限额口径'),
      scenario_event_payout_cents: Object.fromEntries(categoryKeys.map(key => [key, integer(payouts[key], `${key}赔款`)])) as Record<ResearchCategory['key'], number>,
      annual_pure_risk_cost_cents: integer(row.annual_pure_risk_cost_cents, '纯风险成本'),
      annual_reference_premium_cents: integer(row.annual_reference_premium_cents, '参考保费'), commercial_quote: false as const };
  });
  if (new Set(plans.map(row => row.product_id)).size !== 2) throw new Error('研究保险方案重复。');
  const context = object(raw.contract_context, '合同上下文');
  return { schema: 'AgentShield.research_risk_pricing_result.v0.1', scenario_version: text(raw.scenario_version, '情景版本'), currency: 'CNY',
    annual_agent_task_volume: volume, categories, premium_loading_ratio: text(raw.premium_loading_ratio, '附加比例'),
    expected_annual_economic_loss_cents: integer(raw.expected_annual_economic_loss_cents, '年度预期损失'),
    risk_formula: text(raw.risk_formula, '风险公式'), premium_formula: text(raw.premium_formula, '保费公式'), claim_formula: text(raw.claim_formula, '赔款公式'), plans,
    contract_context: { policyholder: text(context.policyholder, '投保人'), insured: text(context.insured, '被保险人'), designated_agent: text(context.designated_agent, '指定Agent'), business_scope: text(context.business_scope, '业务范围'), insurance_period: text(context.insurance_period, '保险期间') },
    assumption_notice: text(raw.assumption_notice, '情景说明'), experience_pricing_status: 'not_available_research_assumptions_only',
    annual_aggregate_calculation_status: 'display_only_not_enforced', commercial_quote: false };
}
