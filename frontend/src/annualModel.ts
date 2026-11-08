// 年度精算结果的展示适配。数字全部由后端读自已存结果，这里不重算保费。
export type StructureRow = { label: string; premium_yuan: number; premium_capital_yuan: number; mean_yuan: number; p99_yuan: number; cte99_yuan: number };

export type TierRow = {
  tier: string; label: string; monitored: boolean; accidents: number; runs: number; pricing_frequency: number; expected_events: number;
  uninsured_mean_yuan: number; uninsured_cte99_yuan: number; premium_yuan: number; premium_capital_yuan: number; insured_cte99_yuan: number; claim_year_chance: number; insurable: boolean;
  enhanced_offered: boolean; enhanced_premium_yuan: number; enhanced_premium_capital_yuan: number; enhanced_cte99_yuan: number;
};

export type AnnualContractView = { contract_version: string; product_tier: string; annual_aggregate_deductible_cents: number; coinsurance_bp: number; annual_limit_cents: number };

export type LatencyRow = { hours: number; loud_fault_loss_yuan: number };

export type AnnualSummary = {
  nature: string; contracts: AnnualContractView[]; premium_with_capital_yuan: number[];
  structures: StructureRow[]; tiers: TierRow[]; latency: LatencyRow[];
};

const isYuan = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0;

export function parseAnnualSummary(payload: unknown): AnnualSummary {
  const value = payload as { schema?: unknown; commercial_quote?: unknown; nature?: unknown; contracts?: unknown; premium_with_capital_yuan?: unknown; structures?: unknown; tiers?: unknown; latency?: unknown } | null;
  if (value === null || typeof value !== 'object' || value.schema !== 'AgentShield.annual_summary.v0.1' || value.commercial_quote !== false
    || typeof value.nature !== 'string' || !Array.isArray(value.contracts) || value.contracts.length !== 2
    || !Array.isArray(value.structures) || !Array.isArray(value.tiers) || !Array.isArray(value.latency)) {
    throw new Error('年度测算的格式不匹配，已停止展示。');
  }
  for (const row of value.structures as StructureRow[]) {
    if (![row.premium_yuan, row.premium_capital_yuan, row.mean_yuan, row.p99_yuan, row.cte99_yuan].every(isYuan)) throw new Error('年度测算的数字不完整，已停止展示。');
  }
  for (const row of value.tiers as TierRow[]) {
    if (![row.premium_yuan, row.premium_capital_yuan, row.uninsured_mean_yuan, row.uninsured_cte99_yuan, row.insured_cte99_yuan, row.enhanced_premium_yuan, row.enhanced_premium_capital_yuan, row.enhanced_cte99_yuan].every(isYuan)
      || !(row.pricing_frequency > 0) || typeof row.claim_year_chance !== 'number') throw new Error('年度测算的配置档不完整，已停止展示。');
  }
  if (!Array.isArray(value.premium_with_capital_yuan) || value.premium_with_capital_yuan.length !== 2 || !value.premium_with_capital_yuan.every(isYuan)) throw new Error('年度测算的数字不完整，已停止展示。');
  return { nature: value.nature, contracts: value.contracts as AnnualContractView[], premium_with_capital_yuan: value.premium_with_capital_yuan as number[],
    structures: value.structures as StructureRow[], tiers: value.tiers as TierRow[], latency: value.latency as LatencyRow[] };
}

export const yuan = (value: number): string => `¥${value.toLocaleString('en-US')}`;

export const percent = (value: number): string => `${(value * 100).toFixed(2)}%`;

export const contractLine = (contract: AnnualContractView): string => {
  const money = (cents: number) => yuan(Math.round(cents / 100));
  return `${contract.product_tier}：年度累计免赔 ${money(contract.annual_aggregate_deductible_cents)}，超过部分赔 ${contract.coinsurance_bp / 100}%，年度限额 ${money(contract.annual_limit_cents)}`;
};

/** 关思考且没有护栏的配置，保费没有意义，页面写明要先整改。 */
/** 保费是一个区间：下限不计资本成本，上限是计入资本成本的参考价。 */
export const premiumRange = (low: number, high: number): string => (low === high ? yuan(low) : `${yuan(low)}–${yuan(high)}`);

export const tierPremium = (row: TierRow): string => (row.insurable ? premiumRange(row.premium_yuan, row.premium_capital_yuan) : '先整改，不承保');

/** 普通损失已超过免赔额的配置不开放增强档，买了比不买更贵。 */
export const enhancedPremium = (row: TierRow): string => (row.enhanced_offered ? premiumRange(row.enhanced_premium_yuan, row.enhanced_premium_capital_yuan) : '先整改，不承保');
