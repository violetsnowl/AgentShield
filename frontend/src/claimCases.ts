// 权限档位对照与理赔材料的展示适配（纯函数，便于单测）。
// 数字全部来自本机实验结果，这里不计算保险责任，也不把未知金额写成 0。
import { money } from './data';

export type ControlArm = {
  batch_id: string; model: string; tasks: string; control_profile: string; control_label: string;
  runs: number; accidents: number; rate_low: number | null; rate_high: number | null;
  net_loss_cents: number; blocked_runs: number;
};

export type ClaimCase = {
  case_id: string; batch_id: string; model: string; control_label: string; family_label: string;
  net_loss_cents: number; payout_cents: number | null; claim_status: string | null; available: boolean;
};

export type ClaimCatalog = { experiment_nature: string; arms: ControlArm[]; cases: ClaimCase[] };

export type ClaimExport = { filename: string; html: string };

const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0;

export function parseClaimCatalog(payload: unknown): ClaimCatalog {
  const value = payload as { contract_version?: unknown; commercial_quote?: unknown; experiment_nature?: unknown; arms?: unknown; cases?: unknown } | null;
  if (value === null || typeof value !== 'object' || value.contract_version !== 'claim-cases-0.1-candidate' || value.commercial_quote !== false
    || typeof value.experiment_nature !== 'string' || !Array.isArray(value.arms) || !Array.isArray(value.cases)) {
    throw new Error('实验结果的格式不匹配，已停止展示。');
  }
  for (const arm of value.arms as ControlArm[]) {
    if (!isCount(arm.runs) || !isCount(arm.accidents) || !isCount(arm.net_loss_cents) || arm.accidents > arm.runs) throw new Error('实验结果的数字不完整，已停止展示。');
  }
  for (const row of value.cases as ClaimCase[]) {
    if (!/^[0-9a-f]{20}$/.test(row.case_id) || !isCount(row.net_loss_cents)) throw new Error('事故记录不完整，已停止展示。');
  }
  return { experiment_nature: value.experiment_nature, arms: value.arms as ControlArm[], cases: value.cases as ClaimCase[] };
}

export const accidentRate = (arm: ControlArm): string => (arm.runs === 0 ? '—' : `${(arm.accidents / arm.runs * 100).toFixed(1)}%`);

export const rateRange = (arm: ControlArm): string => (arm.rate_low === null || arm.rate_high === null
  ? '—' : `${(arm.rate_low * 100).toFixed(1)}%–${(arm.rate_high * 100).toFixed(1)}%`);

/** 未核定时显示原因，不写成 ¥0。 */
export const payoutLabel = (row: ClaimCase): string => {
  if (row.claim_status === 'needs_review' || row.payout_cents === null) return '待人工认定';
  if (row.claim_status === 'not_covered') return '不属于保险责任';
  return money(row.payout_cents);
};

export function claimSummary(catalog: ClaimCatalog): { count: number; lossCents: number; assessedPayoutCents: number; pending: number } {
  const assessed = catalog.cases.filter(row => row.claim_status === 'assessed' && row.payout_cents !== null);
  return {
    count: catalog.cases.length,
    lossCents: catalog.cases.reduce((sum, row) => sum + row.net_loss_cents, 0),
    assessedPayoutCents: assessed.reduce((sum, row) => sum + (row.payout_cents as number), 0),
    pending: catalog.cases.length - assessed.length,
  };
}

/** 工作台的安全策略不允许直接打开带内联样式的页面，所以交给浏览器保存为本地文件。 */
export function saveClaimExport(file: ClaimExport): void {
  const url = URL.createObjectURL(new Blob([file.html], { type: 'text/html;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = file.filename;
  link.click();
  URL.revokeObjectURL(url);
}
