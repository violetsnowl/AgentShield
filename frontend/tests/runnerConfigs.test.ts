import { describe, it, expect } from 'vitest';
import { loadRunnerConfigs, agentConfigLabel } from '../src/data/runnerConfigs';
import { caseDisplay } from '../src/caseNames';

describe('已注册 Agent 配置注册表（只读快照）', () => {
  it('列出 configs/runner 的真实注册配置且字段完整', async () => {
    const list = await loadRunnerConfigs();
    expect(list.length).toBe(5);
    const ids = list.map(config => config.config_id);
    expect(ids).toContain('c-deepseek-flash-fixed-dev-v0.1');
    expect(ids).toContain('c-rule-baseline-v0.1');
    for (const config of list) {
      expect(config.config_id.startsWith('c-')).toBe(true);
      expect(config.source_path.startsWith('configs/runner/')).toBe(true);
      expect(['openai_compatible', 'rule_baseline', 'mock']).toContain(config.adapter);
    }
  });
  it('付费与免付费配置被如实标注，不伪造可用性', async () => {
    const list = await loadRunnerConfigs();
    const model = list.find(config => config.config_id === 'c-deepseek-flash-fixed-dev-v0.1');
    expect(model).toBeDefined();
    expect(agentConfigLabel(model!)).toContain('真实模型');
    expect(agentConfigLabel(model!)).toContain('需付费授权');
    const baseline = list.find(config => config.config_id === 'c-rule-baseline-v0.1');
    expect(baseline).toBeDefined();
    expect(agentConfigLabel(baseline!)).toContain('规则基线');
    expect(agentConfigLabel(baseline!)).not.toContain('需付费授权');
  });
  it('来源案例 ID（B 侧 source_case_id）映射到与 fixture 一致的中文显示名', () => {
    expect(caseDisplay('dev-case-refund-v1').name).toBe('退款申请 · 多份确认');
    expect(caseDisplay('case-bcp2-l1-whole-low-04').name).toBe('整单退款 · 小额 · L1-04');
    expect(caseDisplay('unknown-case-xyz').name).toBe('unknown-case-xyz');
  });
});
