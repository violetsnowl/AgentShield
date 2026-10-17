// 真实 Agent 批次汇总与样本外推参考保费（纯函数，便于单测）。
// 原则：核验不完整或保险责任未确定 → 数据不足；null 不按 0 处理；
// 样本外推只是小样本研究参考，绝非商业报价，也绝不用 1% 情景假设冒充实测。

export type RealBatchRow = {
  runId: string;
  runStatus: string | null;
  taskOutcome: string | null;
  lossStatus: 'verified' | 'needs_review';
  netLossCents: number | null;
  claimStatus: string;
  payoutCents: number | null;
};

export type RealBatchSummary = {
  total: number;
  verified: number;
  review: number;
  verifiedMissingLoss: number;
  notFinished: number;
  escalated: number;
  lossIncidence: { status: 'ok' | 'insufficient'; rate: number | null; reason: string };
  economicLoss: { status: 'ok' | 'insufficient'; cents: number | null; reason: string };
};

export function summarizeRealBatch(rows: RealBatchRow[]): RealBatchSummary {
  const total = rows.length;
  const verified = rows.filter(row => row.lossStatus === 'verified');
  const review = rows.filter(row => row.lossStatus === 'needs_review');
  const verifiedMissingLoss = verified.filter(row => row.netLossCents === null).length;
  const notFinished = rows.filter(row => row.runStatus !== null && row.runStatus !== 'finished').length;
  const escalated = rows.filter(row => row.taskOutcome === 'escalated').length;
  let lossIncidence: RealBatchSummary['lossIncidence'];
  if (total === 0) lossIncidence = { status: 'insufficient', rate: null, reason: '当前批次尚无运行。' };
  else if (verified.length === 0) lossIncidence = { status: 'insufficient', rate: null, reason: `已核验 0 / ${total}，损失发生率暂不可得。` };
  else if (verifiedMissingLoss > 0) lossIncidence = { status: 'insufficient', rate: null, reason: '存在已核验但缺金额的运行，损失发生率暂不可得。' };
  else lossIncidence = { status: 'ok', rate: verified.filter(row => (row.netLossCents ?? 0) > 0).length / verified.length, reason: review.length > 0 ? `另有 ${review.length} 条待核验未计入。` : '' };
  let economicLoss: RealBatchSummary['economicLoss'];
  if (total === 0) economicLoss = { status: 'insufficient', cents: null, reason: '当前批次尚无运行。' };
  else if (verified.length === 0) economicLoss = { status: 'insufficient', cents: null, reason: `已核验 0 / ${total}，经济损失暂不可得。` };
  else if (verifiedMissingLoss > 0) economicLoss = { status: 'insufficient', cents: null, reason: '存在已核验但缺金额的运行，不得按 0 计入合计。' };
  else economicLoss = { status: 'ok', cents: verified.reduce((sum, row) => sum + (row.netLossCents ?? 0), 0), reason: review.length > 0 ? `另有 ${review.length} 条待核验未计入。` : '' };
  return { total, verified: verified.length, review: review.length, verifiedMissingLoss, notFinished, escalated, lossIncidence, economicLoss };
}

export type ExtrapolationInput = { lossStatus: 'verified' | 'needs_review'; claimStatus: string; payoutCents: number | null };

/**
 * 真实模式的「当前批次」选择：优先约定前缀（bscale-web-deepseek-）的真实批次（取批 ID 最大者）；
 * 无约定前缀时回退到全部真实模型运行中批 ID 最大者；没有任何真实模型运行时返回 null。
 * 目的：真实批次绝不被演示/规则基线批次遮蔽，也绝不把历史运行混入真实批次统计。
 */
export function realBatchIdOf(runs: { batch_id: string; execution_source: string }[]): string | null {
  const batches = runs.filter(row => row.execution_source === 'observed_agent_execution').map(row => row.batch_id);
  if (batches.length === 0) return null;
  const designated = batches.filter(id => id.startsWith('bscale-web-deepseek-'));
  const pool = designated.length > 0 ? designated : batches;
  return pool.reduce((max, id) => (id > max ? id : max));
}

export type ExtrapolatedPremium = {
  status: 'ok' | 'insufficient';
  premiumCents: number | null;
  eventCount: number;
  sampleSize: number;
  frequency: number | null;
  meanSeverityCents: number | null;
  reasons: string[];
};

/**
 * 样本外推参考保费：P =（1 + 附加比例）× 年度任务量 ×（已核定正赔款事件数 ÷ 样本量）× 平均单次赔款。
 * 全部有效核验且赔款均为 0 → P = 0；核验不完整或保险责任未确定 → 数据不足（不给数字）。
 */
export function extrapolatePremium(rows: ExtrapolationInput[], options: { annualTaskVolume: number; loadingRatio: number }): ExtrapolatedPremium {
  const sampleSize = rows.length;
  const reasons: string[] = [];
  if (sampleSize === 0) reasons.push('当前批次尚无运行（样本为空）。');
  const review = rows.filter(row => row.lossStatus === 'needs_review');
  if (review.length > 0) reasons.push(`核验未完成：${review.length} / ${sampleSize} 条仍待核验（needs_review），不得用假设概率代替。`);
  const missing = rows.filter(row => row.lossStatus === 'verified' && (row.claimStatus === 'needs_review' || row.payoutCents === null));
  if (missing.length > 0) reasons.push(`保险责任未确定：${missing.length} 条已核验运行没有已核定赔款（payout = null）。`);
  if (reasons.length > 0) return { status: 'insufficient', premiumCents: null, eventCount: 0, sampleSize, frequency: null, meanSeverityCents: null, reasons };
  const payouts = rows.map(row => row.payoutCents as number);
  const eventPayouts = payouts.filter(value => value > 0);
  const eventCount = eventPayouts.length;
  if (eventCount === 0) return { status: 'ok', premiumCents: 0, eventCount: 0, sampleSize, frequency: 0, meanSeverityCents: 0, reasons: [] };
  const meanSeverityCents = Math.round(eventPayouts.reduce((sum, value) => sum + value, 0) / eventCount);
  const frequency = eventCount / sampleSize;
  const premium = Math.round(options.annualTaskVolume * frequency * meanSeverityCents * (1 + options.loadingRatio));
  return { status: 'ok', premiumCents: premium, eventCount, sampleSize, frequency, meanSeverityCents, reasons: [] };
}
