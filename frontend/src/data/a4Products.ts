// A4 两套研究保险产品候选（公开包原样引入 · 只读展示）。
// 文件：research_products_A4_candidate.json（schema AgentShield.two_research_products.v0.1）。
// 来源：A4 公共包 智能2.zip → git_ready/configs/insurance/research_products_A4_candidate.json（2026-10-15 原样拷贝，未改动）。
// 状态：product_design_candidate_not_bound；commercial_quote=false；参数 null = 待团队审定，前端不得替换或计算。
// 数据加载与展示分离：未来若 B/A 提供只读产品接口，只需替换 loadA4Products 的实现，页面组件无需改动。
import raw from './research_products_A4_candidate.json';

export type A4Plan = {
  product_id: string;
  display_name: string;
  insured: string;
  covered_event: string;
  exclusions: string[];
  claims_basis: string;
  deductible_cents: number | null;
  coinsurance_bp: number | null;
  occurrence_limit_cents: number | null;
  annual_aggregate_limit_cents: number | null;
  optional_incident_response_sublimit_cents?: number | null;
  limit_design: string;
};

export type A4Catalog = {
  schema: string;
  currency: string;
  commercial_quote: boolean;
  status: string;
  plans: A4Plan[];
  premium_method: Record<string, string>;
  data_requirements: string[];
};

export const A4_SOURCE_LABEL = 'A4 公共包 git_ready/configs/insurance/research_products_A4_candidate.json（原样引入 · 2026-10-15 · 候选未绑定）';

export async function loadA4Products(): Promise<A4Catalog> {
  return raw as unknown as A4Catalog;
}
