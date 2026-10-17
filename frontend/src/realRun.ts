/** 真实运行桥接的展示适配：只解析后端状态并派生 UI 状态；不做任何模型调用。 */
export type RealRunRow = {
  label: string; run_status: string | null; task_outcome: string | null; stop_reason: string | null;
  loss_status: string | null; net_loss_cents: number | null; claim_status: string | null;
  cost_cny: number | null; payout_cents?: number | null; verify_note?: string;
};
export type RealRunAuthorization = {
  paid_enabled: boolean; paid_reason: string | null; has_key: boolean; approval_cap_cny: number | null;
  prior_paid_cny: number; prior_paid_known: boolean; source_available: boolean; per_run_cap_cny: number;
  allowed_counts: number[]; count_limit: number;
};
export type RealRunStatus = {
  status: 'idle' | 'queued' | 'running' | 'completed' | 'failed';
  batch_id: string | null; count: number | null; seed: string | null; stage: string | null;
  runs: RealRunRow[]; batch_dir: string | null; error_code: string | null; paid: boolean; cap_cny: number | null;
  authorization: RealRunAuthorization;
};

const textOr = (value: unknown, fallback: string | null): string | null => typeof value === 'string' ? value : fallback;
const numberOr = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;

export function parseRealRunStatus(value: unknown): RealRunStatus {
  const raw = (value ?? {}) as Record<string, unknown>;
  const auth = (raw.authorization ?? {}) as Record<string, unknown>;
  const runs = Array.isArray(raw.runs) ? raw.runs.map(entry => {
    const row = (entry ?? {}) as Record<string, unknown>;
    const note = textOr(row.verify_note, null);
    return {
      label: textOr(row.label, '') ?? '', run_status: textOr(row.run_status, null), task_outcome: textOr(row.task_outcome, null),
      stop_reason: textOr(row.stop_reason, null), loss_status: textOr(row.loss_status, null),
      net_loss_cents: numberOr(row.net_loss_cents), claim_status: textOr(row.claim_status, null),
      cost_cny: numberOr(row.cost_cny), payout_cents: numberOr(row.payout_cents), ...(note ? { verify_note: note } : {}),
    };
  }) : [];
  const status = ['idle', 'queued', 'running', 'completed', 'failed'].includes(String(raw.status))
    ? raw.status as RealRunStatus['status'] : 'idle';
  return {
    status, batch_id: textOr(raw.batch_id, null), count: numberOr(raw.count), seed: textOr(raw.seed, null),
    stage: textOr(raw.stage, null), runs, batch_dir: textOr(raw.batch_dir, null), error_code: textOr(raw.error_code, null),
    paid: raw.paid === true, cap_cny: numberOr(raw.cap_cny),
    authorization: {
      paid_enabled: auth.paid_enabled === true, paid_reason: textOr(auth.paid_reason, null), has_key: auth.has_key === true,
      approval_cap_cny: numberOr(auth.approval_cap_cny), prior_paid_cny: numberOr(auth.prior_paid_cny) ?? 0,
      prior_paid_known: auth.prior_paid_known === true, source_available: auth.source_available === true,
      per_run_cap_cny: numberOr(auth.per_run_cap_cny) ?? 0.5,
      allowed_counts: Array.isArray(auth.allowed_counts) ? auth.allowed_counts.filter(item => typeof item === 'number') as number[] : [1, 5],
      count_limit: numberOr(auth.count_limit) ?? 10,
    },
  };
}

export function realRunBusy(status: RealRunStatus | null): boolean {
  return status !== null && (status.status === 'queued' || status.status === 'running');
}

/** 诚实禁用原因：与后端探测一致（密钥存在性、批准记录、源数据、单飞）。 */
export function realRunDisabledReasons(status: RealRunStatus | null): string[] {
  if (status === null) return [];
  if (realRunBusy(status)) return ['单飞：同一时间只允许一个真实批次运行。'];
  const reasons: string[] = [];
  const auth = status.authorization;
  if (!auth.has_key) reasons.push('未配置：本机 .env 缺少 DEEPSEEK_API_KEY（由负责人在本机后端填写；不进入前端或仓库）。');
  if (auth.approval_cap_cny === null) reasons.push('未授权：当前阶段没有生效的付费预算批准记录；付费模型调用默认关闭、逐次批准。');
  if (!auth.source_available) reasons.push('未就绪：B-SCALE 冻结源数据路径未配置或不可读。');
  return reasons;
}

export function canStartRealRun(status: RealRunStatus | null): boolean {
  return status !== null && !realRunBusy(status) && realRunDisabledReasons(status).length === 0;
}

export function realRunStageLabel(stage: string | null): string {
  switch (stage) {
    case 'starting': return '准备中';
    case 'sampling': return '随机抽样中';
    case 'running': return '真实模型运行中';
    case 'verifying': return '自动 Gold 与复核中';
    case 'completed': return '已完成';
    case 'failed': return '失败';
    default: return '等待中';
  }
}
