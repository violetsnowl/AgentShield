import { describe, expect, it } from 'vitest';
import { categoryOf, computeRiskMetrics, coverageLine, riskVerdict } from '../src/riskMetrics';
import type { RiskRunInput } from '../src/riskMetrics';

function run(partial: Partial<RiskRunInput> & { runId: string }): RiskRunInput {
  return {
    label: 'run-label', sessionId: `session-${partial.runId}`, caseId: 'dev-case-refund-v1',
    executionSource: 'mock_agent', lossStatus: 'needs_review', netLossCents: null,
    claimStatus: 'needs_review', payoutCents: null, taskOutcome: 'completed', humanTickets: 0,
    ...partial,
  };
}

// 与交付目录现状一致的 15 条样本：3 真实模型 + 12 Mock；仅 1 条已核验（净损失 0）。
function deliveredFixture(): RiskRunInput[] {
  const rows: RiskRunInput[] = [];
  for (let index = 0; index < 3; index += 1) {
    rows.push(run({ runId: `real-${index}`, executionSource: 'observed_agent_execution', caseId: 'dev-case-refund-v1' }));
  }
  for (let index = 0; index < 12; index += 1) {
    const escalated = index % 4 === 1; // 每批一条 v2 复核运行升级
    rows.push(run({
      runId: `mock-${index}`, caseId: excluded(index) ? 'bcp2-l1-whole-low-04' : 'dev-case-refund-v2',
      taskOutcome: escalated ? 'escalated' : (index === 2 ? 'not_finished' : 'completed'),
      humanTickets: escalated ? 1 : 0,
    }));
  }
  rows[0] = run({ runId: 'verified-zero', executionSource: 'observed_agent_execution', lossStatus: 'verified', netLossCents: 0, claimStatus: 'assessed', payoutCents: 0 });
  return rows;
}
function excluded(index: number) { return index === 11; }

describe('computeRiskMetrics', () => {
  it('测试1：核验待审核（needs_review）绝不等于任务升级（escalated）', () => {
    const metrics = computeRiskMetrics(deliveredFixture());
    expect(metrics.review.length).toBe(14);
    expect(metrics.outcomeEscalated).toBe(3);
    // 两个维度互相独立：给升级的运行即使全部返回 completed，也不影响 review 计数，反之亦然。
    const shifted = computeRiskMetrics(deliveredFixture().map(row => ({ ...row, taskOutcome: 'completed' })));
    expect(shifted.outcomeEscalated).toBe(0);
    expect(shifted.review.length).toBe(14);
  });

  it('测试2：null 不等于 0——只有已核验样本进入净损失合计', () => {
    const metrics = computeRiskMetrics(deliveredFixture());
    expect(metrics.verified.length).toBe(1);
    expect(metrics.verifiedNetSumCents).toBe(0);
    expect(metrics.verifiedZero.length).toBe(1);
    expect(metrics.review.every(row => row.netLossCents === null)).toBe(true);
    expect(coverageLine(metrics)).toContain('1 / 15');
    expect(coverageLine(metrics)).toContain('暂不足以估计整体风险');
    // 即使（违反契约地）给待核验样本塞入金额，也不得被汇总。
    const dirty = computeRiskMetrics(deliveredFixture().map(row => row.lossStatus === 'needs_review' ? { ...row, netLossCents: 999 } : row));
    expect(dirty.verifiedNetSumCents).toBe(0);
  });

  it('测试4：已核验但缺金额算“核验结果缺失”，不得按 0 并入合计', () => {
    const base = deliveredFixture();
    base.push(run({ runId: 'verified-null', executionSource: 'observed_agent_execution', lossStatus: 'verified', netLossCents: null }));
    const metrics = computeRiskMetrics(base);
    expect(metrics.verified.length).toBe(2);
    expect(metrics.verifiedMissingLoss.length).toBe(1);
    expect(metrics.verifiedNetSumCents).toBe(0);
    const category = metrics.categories.find(row => row.key === '开发模板（未分类）');
    expect(category?.verifiedMissing).toBe(1);
  });

  it('测试3：运行来源分别计数，scripted_test 不得计为真实模型', () => {
    const metrics = computeRiskMetrics(deliveredFixture());
    expect(metrics.observed.length).toBe(3);
    expect(metrics.mock.length).toBe(12);
    expect(metrics.scripted.length).toBe(0);
    const withScripted = computeRiskMetrics([...deliveredFixture(), run({ runId: 'scripted-1', executionSource: 'scripted_test' }), run({ runId: 'scripted-2', executionSource: 'rule_baseline' })]);
    expect(withScripted.observed.length).toBe(3);
    expect(withScripted.scripted.length).toBe(1);
    expect(withScripted.ruleBaseline.length).toBe(1);
  });

  it('工单与升级分开统计；覆盖说明在样本不足时给出警示', () => {
    const metrics = computeRiskMetrics(deliveredFixture());
    expect(metrics.ticketRuns.length).toBe(3);
    expect(metrics.ticketTotal).toBe(3);
    expect(coverageLine(computeRiskMetrics([]))).toContain('无法估计风险');
    expect(coverageLine(computeRiskMetrics(deliveredFixture().map(row => ({ ...row, lossStatus: 'verified', netLossCents: 10 }))))).toBe('全部 15 次运行均具有已核验损失结果。');
  });

  it('业务类别按公开结构归类', () => {
    expect(categoryOf('bcp2-l1-whole-low-04')).toBe('整单 · 小额');
    expect(categoryOf('bcp2-l2-partial-high-01')).toBe('部分 · 大额');
    expect(categoryOf('dev-case-refund-v1')).toBe('开发模板（未分类）');
    expect(categoryOf('mystery-case-42')).toBe('未归类 · 待审');
  });
});

describe('coverageLine', () => {
  it('无样本与零核验时显示证据不足文案', () => {
    const none = computeRiskMetrics([run({ runId: 'a' })]);
    expect(coverageLine(none)).toContain('0 / 1');
  });
});

describe('riskVerdict', () => {
  it('样本不足时给出“证据不足”结论，且数字与覆盖说明一致', () => {
    const v = riskVerdict(computeRiskMetrics(deliveredFixture()));
    expect(v.level).toBe('整体风险：证据不足');
    expect(v.line).toContain('1 / 15');
    expect(v.line).toContain('暂不足以估计整体风险');
  });
  it('全部核验后按真实数据更新表达（不固定“证据不足”）', () => {
    const v = riskVerdict(computeRiskMetrics(deliveredFixture().map(row => ({ ...row, lossStatus: 'verified' as const, netLossCents: row.netLossCents ?? 0 }))));
    expect(v.level).toBe('核验结果已覆盖全部运行');
    expect(v.line).toContain('全部 15 次运行');
  });
  it('空目录不冒充结论', () => {
    const v = riskVerdict(computeRiskMetrics([]));
    expect(v.level).toBe('暂无可判断的记录');
  });
});
