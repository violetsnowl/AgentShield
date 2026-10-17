// 风险评估页聚合（纯函数，便于单测）。
// 原则：全部由输入实测数据实时计算，不硬编码；核验状态与任务结果、工单是相互独立的维度，不互相代替。

export type RiskRunInput = {
  runId: string;
  label: string;
  sessionId: string;
  caseId: string;
  executionSource: string;
  lossStatus: 'verified' | 'needs_review';
  netLossCents: number | null;
  claimStatus: 'assessed' | 'not_covered' | 'needs_review';
  payoutCents: number | null;
  taskOutcome: string | null;
  humanTickets: number;
};

export type RiskCategory = { key: string; runs: number; verified: number; verifiedMissing: number; lossCents: number };

export type RiskMetrics = {
  total: number;
  observed: RiskRunInput[];
  mock: RiskRunInput[];
  scripted: RiskRunInput[];
  ruleBaseline: RiskRunInput[];
  otherSources: RiskRunInput[];
  verified: RiskRunInput[];
  review: RiskRunInput[];
  verifiedNetSumCents: number;
  verifiedZero: RiskRunInput[];
  verifiedMissingLoss: RiskRunInput[];
  assessed: RiskRunInput[];
  payoutSumCents: number;
  escalated: RiskRunInput[];
  outcomeCompleted: number;
  outcomeEscalated: number;
  outcomeNotFinished: number;
  outcomeOther: number;
  ticketRuns: RiskRunInput[];
  ticketTotal: number;
  categories: RiskCategory[];
};

export function categoryOf(caseId: string): string {
  const match = /bcp2-(l\d)-(whole|partial)-(low|high)-/.exec(caseId);
  if (match) return `${match[2] === 'whole' ? '整单' : '部分'} · ${match[3] === 'low' ? '小额' : '大额'}`;
  if (/^dev-/.test(caseId)) return '开发模板（未分类）';
  return '未归类 · 待审';
}

export function computeRiskMetrics(inputs: RiskRunInput[]): RiskMetrics {
  const sources = ['observed_agent_execution', 'mock_agent', 'scripted_test', 'rule_baseline'];
  const observed = inputs.filter(row => row.executionSource === 'observed_agent_execution');
  const mock = inputs.filter(row => row.executionSource === 'mock_agent');
  const scripted = inputs.filter(row => row.executionSource === 'scripted_test');
  const ruleBaseline = inputs.filter(row => row.executionSource === 'rule_baseline');
  const otherSources = inputs.filter(row => !sources.includes(row.executionSource));
  // 核验损失只汇总 verified 样本；needs_review 的 null 不视为 0，也不并入合计。
  const verified = inputs.filter(row => row.lossStatus === 'verified');
  const review = inputs.filter(row => row.lossStatus === 'needs_review');
  // 已核验但缺金额 = 核验结果缺失：不并入 0，单独计数、单独展示。
  const verifiedMissingLoss = verified.filter(row => row.netLossCents === null);
  const verifiedNetSumCents = verified.reduce((sum, row) => sum + (row.netLossCents ?? 0), 0);
  const verifiedZero = verified.filter(row => row.netLossCents === 0);
  const assessed = inputs.filter(row => row.claimStatus === 'assessed' && row.payoutCents !== null);
  const payoutSumCents = assessed.reduce((sum, row) => sum + (row.payoutCents ?? 0), 0);
  // 任务升级按交付 manifest 的 task_outcome；与 loss_status / 工单互不代替。
  const escalated = inputs.filter(row => row.taskOutcome === 'escalated');
  const ticketRuns = inputs.filter(row => row.humanTickets > 0);
  const ticketTotal = inputs.reduce((sum, row) => sum + row.humanTickets, 0);
  const outcome = (value: string) => inputs.filter(row => row.taskOutcome === value).length;
  const buckets = new Map<string, RiskCategory>();
  for (const row of inputs) {
    const key = categoryOf(row.caseId);
    const bucket = buckets.get(key) ?? { key, runs: 0, verified: 0, verifiedMissing: 0, lossCents: 0 };
    bucket.runs += 1;
    if (row.lossStatus === 'verified') {
      bucket.verified += 1;
      if (row.netLossCents === null) bucket.verifiedMissing += 1;
      else bucket.lossCents += row.netLossCents;
    }
    buckets.set(key, bucket);
  }
  return {
    total: inputs.length,
    observed, mock, scripted, ruleBaseline, otherSources,
    verified, review, verifiedNetSumCents, verifiedZero, verifiedMissingLoss,
    assessed, payoutSumCents,
    escalated,
    outcomeCompleted: outcome('completed'),
    outcomeEscalated: outcome('escalated'),
    outcomeNotFinished: outcome('not_finished'),
    outcomeOther: inputs.filter(row => row.taskOutcome !== null && !['completed', 'escalated', 'not_finished'].includes(row.taskOutcome)).length,
    ticketRuns, ticketTotal,
    categories: [...buckets.values()],
  };
}

// 核验覆盖说明：先于金额展示，明确“样本不足”而不是让读者把全体损失读成 0。
export function coverageLine(metrics: RiskMetrics): string {
  const { total, verified } = metrics;
  if (total === 0) return '目录里没有可汇总的运行，无法估计风险。';
  if (verified.length === 0) return `当前 0 / ${total} 次运行具有已核验损失结果，暂不足以估计整体风险。`;
  if (verified.length < total) return `当前只有 ${verified.length} / ${total} 次运行具有已核验损失结果，暂不足以估计整体风险。`;
  return `全部 ${total} 次运行均具有已核验损失结果。`;
}

/** 页首结论（动态）：证据不足时说清楚不足，数据充分时按真实结果更新表达，不固定文案。 */
export function riskVerdict(metrics: RiskMetrics): { level: string; line: string } {
  if (metrics.total === 0) return { level: '暂无可判断的记录', line: coverageLine(metrics) };
  if (metrics.verified.length < metrics.total) return { level: '整体风险：证据不足', line: coverageLine(metrics) };
  return { level: '核验结果已覆盖全部运行', line: coverageLine(metrics) };
}
