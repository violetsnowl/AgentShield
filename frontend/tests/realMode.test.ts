import { describe, it, expect } from 'vitest';
import { extrapolatePremium, insuranceAdviceFrom, realBatchIdOf, summarizeRealBatch } from '../src/realMode';
import type { ExtrapolationInput, RealBatchRow } from '../src/realMode';

describe('realBatchIdOf', () => {
  const row = (batch_id: string, execution_source: string) => ({ batch_id, execution_source });
  it('优先约定前缀的真实批次，即使存在字典序更大的旧真实批次', () => {
    expect(realBatchIdOf([
      row('zz-legacy-observed-2026', 'observed_agent_execution'),
      row('bscale-web-deepseek-20261017-155329-8f3a21', 'observed_agent_execution'),
    ])).toBe('bscale-web-deepseek-20261017-155329-8f3a21');
  });
  it('多个约定真实批次取批 ID 最大者；规则基线批次永不入围', () => {
    expect(realBatchIdOf([
      row('bscale-web-deepseek-20261017-100000-aaaaaa', 'observed_agent_execution'),
      row('bscale-web-deepseek-20261017-155329-8f3a21', 'observed_agent_execution'),
      row('bscale-web-rule-baseline-20261017-130450-496b42', 'scripted_test'),
    ])).toBe('bscale-web-deepseek-20261017-155329-8f3a21');
  });
  it('无约定前缀时回退到真实运行的最大批 ID；无真实运行返回 null', () => {
    expect(realBatchIdOf([row('j2-deepseek-dev-20261013-203119', 'observed_agent_execution'), row('j1-mock-x', 'mock_agent')])).toBe('j2-deepseek-dev-20261013-203119');
    expect(realBatchIdOf([row('bscale-web-rule-baseline-20261017-130450-496b42', 'scripted_test')])).toBeNull();
    expect(realBatchIdOf([])).toBeNull();
  });
});

function row(partial: Partial<RealBatchRow> & { runId: string }): RealBatchRow {
  return {
    runStatus: 'completed', taskOutcome: 'completed', lossStatus: 'needs_review', netLossCents: null,
    claimStatus: 'needs_review', payoutCents: null, ...partial,
  };
}

function claim(partial: Partial<ExtrapolationInput>): ExtrapolationInput {
  return { lossStatus: 'needs_review', claimStatus: 'needs_review', payoutCents: null, ...partial };
}

describe('summarizeRealBatch', () => {
  it('空批次与全待核验批次都保持数据不足', () => {
    const empty = summarizeRealBatch([]);
    expect(empty.total).toBe(0);
    expect(empty.lossIncidence.status).toBe('insufficient');
    expect(empty.economicLoss.status).toBe('insufficient');
    const review = summarizeRealBatch([row({ runId: 'a' }), row({ runId: 'b' })]);
    expect(review.lossIncidence.status).toBe('insufficient');
    expect(review.economicLoss.cents).toBeNull();
    expect(review.review).toBe(2);
  });
  it('已核验但缺金额不得按 0 计', () => {
    const summary = summarizeRealBatch([
      row({ runId: 'a', lossStatus: 'verified', netLossCents: null }),
      row({ runId: 'b', lossStatus: 'verified', netLossCents: 500 }),
    ]);
    expect(summary.verifiedMissingLoss).toBe(1);
    expect(summary.economicLoss.status).toBe('insufficient');
    expect(summary.lossIncidence.status).toBe('insufficient');
  });
  it('全部核验后可给出发生率与经济损失，并注明未计条目', () => {
    const summary = summarizeRealBatch([
      row({ runId: 'a', lossStatus: 'verified', netLossCents: 0 }),
      row({ runId: 'b', lossStatus: 'verified', netLossCents: 800 }),
      row({ runId: 'c', taskOutcome: 'escalated', runStatus: 'completed' }),
    ]);
    expect(summary.lossIncidence.rate).toBe(0.5);
    expect(summary.economicLoss.cents).toBe(800);
    expect(summary.economicLoss.reason).toContain('1 条待核验');
    expect(summary.escalated).toBe(1);
  });
  it('运行状态口径回归：completed 不计入未正常完成；异常运行与 not_finished 计入', () => {
    const summary = summarizeRealBatch([
      row({ runId: 'a', runStatus: 'completed', taskOutcome: 'completed' }),
      row({ runId: 'b', runStatus: 'infra_error', taskOutcome: null }),
      row({ runId: 'c', runStatus: 'completed', taskOutcome: 'not_finished' }),
    ]);
    expect(summary.notFinished).toBe(2);
    expect(summary.escalated).toBe(0);
  });
});

describe('extrapolatePremium', () => {
  const options = { annualTaskVolume: 6105, loadingRatio: 0.25 };
  it('核验未完成 → 数据不足，不给数字', () => {
    const result = extrapolatePremium([claim({}), claim({ lossStatus: 'verified', claimStatus: 'assessed', payoutCents: 100 })], options);
    expect(result.status).toBe('insufficient');
    expect(result.premiumCents).toBeNull();
    expect(result.reasons.join('')).toContain('核验未完成');
  });
  it('保险责任未确定（已核验但 payout=null）→ 数据不足', () => {
    const result = extrapolatePremium([claim({ lossStatus: 'verified', claimStatus: 'assessed', payoutCents: null })], options);
    expect(result.status).toBe('insufficient');
    expect(result.reasons.join('')).toContain('保险责任未确定');
  });
  it('全部有效核验且赔款均为 0 → 参考保费为 0', () => {
    const result = extrapolatePremium([
      claim({ lossStatus: 'verified', claimStatus: 'assessed', payoutCents: 0 }),
      claim({ lossStatus: 'verified', claimStatus: 'not_covered', payoutCents: 0 }),
    ], options);
    expect(result.status).toBe('ok');
    expect(result.premiumCents).toBe(0);
    expect(result.eventCount).toBe(0);
  });
  it('有正赔款事件 → 按频率×均值×年度量×加载系数外推', () => {
    const result = extrapolatePremium([
      claim({ lossStatus: 'verified', claimStatus: 'assessed', payoutCents: 0 }),
      claim({ lossStatus: 'verified', claimStatus: 'assessed', payoutCents: 900 }),
    ], options);
    expect(result.frequency).toBe(0.5);
    expect(result.meanSeverityCents).toBe(900);
    // 6105 × 0.5 × 900 × 1.25 = 3434062.5 → 3434063（分）
    expect(result.premiumCents).toBe(Math.round(6105 * 0.5 * 900 * 1.25));
  });
  it('空样本 → 数据不足', () => {
    const result = extrapolatePremium([], options);
    expect(result.status).toBe('insufficient');
    expect(result.reasons.join('')).toContain('样本为空');
  });
});

describe('insuranceAdviceFrom（保险配置建议：先评估风险，再决定是否投保）', () => {
  const summaryOf = (rows: RealBatchRow[]) => summarizeRealBatch(rows);
  it('全部核验且净损失均为 0 → 当前测试未发现额外经济损失（继续观察；N 动态；零风险不当长期结论）', () => {
    const advice = insuranceAdviceFrom(summaryOf([
      row({ runId: 'a', runStatus: 'completed', lossStatus: 'verified', netLossCents: 0 }),
      row({ runId: 'b', runStatus: 'completed', lossStatus: 'verified', netLossCents: 0 }),
    ]));
    expect(advice.kind).toBe('no_need');
    expect(advice.title).toBe('当前测试未发现额外经济损失');
    expect(advice.detail).toContain('本批 2 条真实 Agent 任务');  // N 按批次动态生成，不写死
    expect(advice.detail).toContain('净经济损失为 0 元');
    expect(advice.caveat).toContain('扩大测试样本');
    expect(advice.caveat).toContain('Core 或 Plus 保障');
    expect(advice.title + advice.caveat).not.toContain('无需购买');
  });
  it('出现已核验经济损失 → 建议评估保险保障；不把 C 核验损失当作已认定保险责任', () => {
    const advice = insuranceAdviceFrom(summaryOf([
      row({ runId: 'a', runStatus: 'completed', lossStatus: 'verified', netLossCents: 0 }),
      row({ runId: 'b', runStatus: 'completed', lossStatus: 'verified', netLossCents: 800 }),
    ]));
    expect(advice.kind).toBe('evaluate');
    expect(advice.title).toBe('建议评估保险保障');
    expect(advice.detail).toContain('已核验经济损失');
    expect(advice.detail).toContain('¥8.00');
    expect(advice.detail).toContain('1 条运行');
    expect(advice.detail).not.toContain('可保损失');
    expect(advice.caveat).toContain('不等于已认定保险责任');
  });
  it('存在待核验或缺金额 → 暂无法形成建议（绝不把未核验金额当作 0）', () => {
    expect(insuranceAdviceFrom(summaryOf([row({ runId: 'a', runStatus: 'completed' })])).kind).toBe('insufficient');
    const missing = insuranceAdviceFrom(summaryOf([row({ runId: 'a', lossStatus: 'verified', netLossCents: null })]));
    expect(missing.kind).toBe('insufficient');
    expect(missing.detail).toContain('缺金额');
    expect(insuranceAdviceFrom(summaryOf([])).kind).toBe('insufficient');
  });
  it('已确认正损失优先：即使仍有待核验也建议评估，并注明结论可能变化', () => {
    const advice = insuranceAdviceFrom(summaryOf([
      row({ runId: 'a', runStatus: 'completed', lossStatus: 'verified', netLossCents: 500 }),
      row({ runId: 'b', runStatus: 'completed' }),
    ]));
    expect(advice.kind).toBe('evaluate');
    expect(advice.detail).toContain('尚未核验');
  });
});
