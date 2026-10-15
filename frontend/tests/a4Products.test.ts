import { describe, expect, it } from 'vitest';
import { A4_SOURCE_LABEL, loadA4Products } from '../src/data/a4Products';

describe('A4 两套研究产品候选（只读数据层）', () => {
  it('测试4：Core 与 Plus 均能从 A4 候选 JSON 加载，且信息与源文件一致', async () => {
    const catalog = await loadA4Products();
    expect(catalog.schema).toBe('AgentShield.two_research_products.v0.1');
    expect(catalog.commercial_quote).toBe(false);
    expect(catalog.status).toBe('product_design_candidate_not_bound');
    expect(catalog.plans.map(plan => plan.product_id)).toEqual(['AgentShield-Core', 'AgentShield-Plus']);
    const [core, plus] = catalog.plans;
    expect(core.display_name).toBe('AgentShield 操作差错基础保障');
    expect(plus.display_name).toBe('AgentShield 操作差错增强保障');
    expect(core.covered_event).not.toBe(plus.covered_event);
    expect(core.exclusions.length).toBeGreaterThan(0);
    expect(plus.exclusions.length).toBeGreaterThan(0);
  });

  it('测试5：A4 中的 null 参数保持待定，不被任何默认值替换', async () => {
    const catalog = await loadA4Products();
    for (const plan of catalog.plans) {
      expect(plan.deductible_cents).toBeNull();
      expect(plan.coinsurance_bp).toBeNull();
      expect(plan.occurrence_limit_cents).toBeNull();
      expect(plan.annual_aggregate_limit_cents).toBeNull();
    }
    // Plus 的处置费用附加子限额同样为待定（可选 · 待实现）。
    expect(catalog.plans[1].optional_incident_response_sublimit_cents ?? null).toBeNull();
    expect(catalog.premium_method.commercial_rate_status).toBe('insufficient_evidence');
    expect(A4_SOURCE_LABEL).toContain('research_products_A4_candidate.json');
  });
});
