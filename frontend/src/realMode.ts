// 真实 Agent 批次汇总与样本外推参考保费（纯函数，便于单测）。
// 原则：核验不完整或保险责任未确定 → 数据不足；null 不按 0 处理；
// 样本外推只是小样本研究参考，绝非商业报价，也绝不用 1% 情景假设冒充实测。
import { money } from './data';

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
  confirmedPositiveCents: number;
  confirmedPositiveCount: number;
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
  // 真实运行字段口径（回归修复）：manifest run_status 'completed' 即正常完成；
  // 异常运行（infra_error/started/not_started…）与 task_outcome 'not_finished' 才计入「未正常完成」。
  // 旧实现误用 B 会话的 'finished' 口径，把完成的真实运行错数成未完成（首条网页真实运行目检发现）。
  const notFinished = rows.filter(row => (row.runStatus !== null && row.runStatus !== 'completed') || row.taskOutcome === 'not_finished').length;
  const escalated = rows.filter(row => row.taskOutcome === 'escalated').length;
  // 「已确认的可保损失」只统计已核验且金额已知的正损失；null 一律跳过（绝不当作 0）。
  const confirmedPositiveCents = verified.reduce((sum, row) => sum + ((row.netLossCents ?? 0) > 0 ? (row.netLossCents as number) : 0), 0);
  const confirmedPositiveCount = verified.filter(row => (row.netLossCents ?? 0) > 0).length;
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
  return { total, verified: verified.length, review: review.length, verifiedMissingLoss, confirmedPositiveCents, confirmedPositiveCount, notFinished, escalated, lossIncidence, economicLoss };
}

/**
 * 「AgentShield 保险配置建议」：先用真实批次核验数据评估风险，再决定是否需要保险——
 * 不是一律推荐购买。三态（纯展示规则，无新算法、不碰合同与定价公式）：
 * - evaluate（已观察到已核验经济损失）：建议评估保险保障；C 核验损失不等于已认定保险责任；
 * - no_need（全部已核验且净损失均为 0）：结论=当前测试未发现额外经济损失（继续观察，扩大样本后再评估）；
 * - insufficient（核验不完整/缺金额/无数据）：暂无法形成保险配置建议，绝不把未核验金额当作 0。
 */
export type InsuranceAdvice = { kind: 'no_need' | 'evaluate' | 'insufficient'; title: string; detail: string; caveat: string };

export function insuranceAdviceFrom(summary: RealBatchSummary): InsuranceAdvice {
  const scope = `基于当前批次 ${summary.total} 条真实运行`;
  if (summary.total === 0) {
    return { kind: 'insufficient', title: '暂无法形成保险配置建议',
      detail: '当前批次尚无已交付的真实运行。',
      caveat: '先运行并完成独立核验后，再评估是否需要投保。' };
  }
  if (summary.confirmedPositiveCents > 0) {
    const pending = summary.review > 0 ? `；另有 ${summary.review} 条尚未核验，结论可能随核验推进变化` : '';
    return { kind: 'evaluate', title: '建议评估保险保障',
      detail: `${scope}中已观察到已核验经济损失 ${money(summary.confirmedPositiveCents)}（${summary.confirmedPositiveCount} 条运行）${pending}。`,
      caveat: '建议进一步评估 Core / Plus 保障的适用性；C 核验出的经济损失并不等于已认定保险责任——保险责任认定由 A 另行审查。' };
  }
  if (summary.review === 0 && summary.verifiedMissingLoss === 0) {
    return { kind: 'no_need', title: '当前测试未发现额外经济损失',
      detail: `本批 ${summary.total} 条真实 Agent 任务全部完成独立核验，净经济损失为 0 元。`,
      caveat: '当前尚无充分依据配置具体保险方案，建议扩大测试样本，再根据实际风险水平评估是否需要 Core 或 Plus 保障。' };
  }
  const reason = summary.verifiedMissingLoss > 0
    ? `存在 ${summary.verifiedMissingLoss} 条已核验但缺金额的运行（未按 0 计入）`
    : `${summary.review} 条运行尚未完成核验`;
  return { kind: 'insufficient', title: '暂无法形成保险配置建议',
    detail: `${scope}中${reason}。`,
    caveat: '核验完整后再评估是否投保；不将未核验金额当作 0。' };
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
