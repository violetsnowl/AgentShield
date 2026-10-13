/** D presentation boundary only. Neither alias defines an A/C wire contract. */
export type LossResultInput = unknown;
export type QuoteResultInput = unknown;
export type ResultKind = 'LossResult' | 'QuoteResult';
export const boundaryVersion = 'bd-results-boundary-0.1-candidate' as const;
export type ResultSlot = {
  boundary_version: typeof boundaryVersion;
  kind: ResultKind;
  owner: 'A' | 'C';
  state: 'pending' | 'unsupported_contract';
  result: null;
  commercial_quote: false;
  message: string;
};

// There are no owner-reviewed wire versions yet. Fail closed instead of guessing
// fields or treating an arbitrary JSON result as a verified LossResult/QuoteResult.
export function adaptResult(kind: ResultKind, input?: LossResultInput | QuoteResultInput): ResultSlot {
  const absent = input === undefined || input === null;
  return {
    boundary_version: boundaryVersion, kind, owner: kind === 'LossResult' ? 'C' : 'A',
    state: absent ? 'pending' : 'unsupported_contract', result: null, commercial_quote: false,
    message: absent ? '尚未收到负责人审定的协议与结果。' : '收到的内容没有已审定版本适配器，停止展示；请先完成 A/C 契约审核。',
  };
}

// Vocabulary from V1.1, not the status of any current experiment/result.
export const evidenceStatePresentation = {
  not_fitted: { title: '未标定', text: 'B2 未标定，不展示参数或情景估计。', tone: 'warning' },
  insufficient_evidence: { title: '证据不足', text: '不能给出完整估计；未知金额保留 null，不填零。', tone: 'warning' },
  partial: { title: '部分支持', text: '只展示已核验的支持范围，未知部分单列。', tone: 'warning' },
  out_of_scope: { title: '超出范围', text: '当前数据不支持此情景，不能外推报价。', tone: 'error' },
} as const;

export const integrations = [
  { ...adaptResult('LossResult'), contract: 'LossResult', reason: '等待 C 的正式运行清单与独立损失核验结果。' },
  { ...adaptResult('QuoteResult'), contract: 'QuoteResult', reason: '等待 A 的报价、合同版本、权重及证据状态接口。' },
];
