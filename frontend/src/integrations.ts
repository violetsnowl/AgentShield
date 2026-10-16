/** Strict presentation adapter for the delivered A/C candidate contracts. */
export type ResultKind = 'LossResult' | 'QuoteResult';
export const boundaryVersion = 'abcd-results-boundary-0.2-candidate' as const;

export type IntegrationRunSummary = {
  run_id: string; batch_id: string; label: string; case_id: string; session_id: string; episode_id: string; config_id: string;
  execution_source: 'scripted_test' | 'mock_agent' | 'observed_agent_execution'; provider: string | null; model: string | null; run_status: string;
  task_outcome: string | null; loss_status: 'verified' | 'needs_review'; claim_status: 'assessed' | 'not_covered' | 'needs_review';
  counts_as_formal_run: false; total_committed_cents: number;
  evidence_digest_status: 'raw_file_match' | 'canonical_json_match_raw_delivery_differs';
};
export type LossResultCandidate = {
  loss_result_version: 'loss-result-c-0.1-candidate'; oracle_version: string;
  identity: { case_id: string | null; session_id: string | null; episode_id: string | null; config_id: string | null; execution_source: string | null };
  obligation_source: 'obligation_spec' | 'engineering_case' | 'none'; obligation_spec_id: string | null; horizon: string;
  total_committed_cents: number; total_extra_cents: number | null; total_underpaid_cents: number | null;
  traceable_recovery_cents: number | null; net_loss_cents: number | null; loss_status: 'verified' | 'needs_review';
  coverage_status_input: 'covered' | 'excluded' | 'needs_review'; task_outcome: string; policy_compliance: string;
  unknown_parts: string[]; notes: string[]; obligations: unknown[];
  ledger_checks: null | { refunds_match_ledger: boolean | null; lines_sum_to_refund: boolean | null; balances_conserved: boolean | null; final_balances_reconcile: boolean | null; duplicate_transactions: number; issues: string[] };
  activity: null | { tool_events: number; write_succeeded: number; write_rejected: number; write_replayed: number; write_error: number; human_review_tickets: number };
  commercial_quote: false;
};
export type ClaimResultCandidate = {
  event_id: string; contract_version: string; currency: 'CNY'; net_loss_cents: number | null; loss_status: 'verified' | 'needs_review';
  coverage_status: 'covered' | 'excluded' | 'needs_review'; claim_status: 'assessed' | 'not_covered' | 'needs_review';
  payout_cents: number | null; retained_loss_cents: number | null; commercial_quote: false;
};
export type ResearchContractCandidate = {
  contract_version: string; currency: 'CNY'; deductible_cents: number; coinsurance_bp: number; occurrence_limit_cents: number;
  commercial_quote: false; covered_description: string; exclusions_description: string; observation_horizon: string; warning: string;
};
export type QuoteResultCandidate = {
  schema_version: 'a-quote-v0.1-candidate'; commercial_quote: false; status: 'illustrative' | 'insufficient_evidence' | 'partial' | 'out_of_scope';
  contract_version: string; data_version: string; calculation_version: string; config_id: string; execution_source: string;
  reviewed_evidence: boolean; run_count: number; methods: {
    B0: { label: string; estimated_mean_cents_decimal: string | null; scenario_cost_cents_decimal: string | null };
    B1: { label: string; estimated_mean_cents_decimal: string | null; scenario_cost_cents_decimal: string | null };
    B2: { status: string; estimated_mean_cents_decimal: string | null; scenario_cost_cents_decimal: string | null };
  }; limitations: string[];
};
export type IntegrationRunDetail = { summary: IntegrationRunSummary; evidence: unknown; loss_result: LossResultCandidate; claim: ClaimResultCandidate; contract: ResearchContractCandidate; quote_result: QuoteResultCandidate };

type RecordValue = Record<string, unknown>;
const object = (value: unknown, label: string): RecordValue => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} 格式无效。`);
  return value as RecordValue;
};
const text = (value: unknown, label: string) => { if (typeof value !== 'string' || !value) throw new Error(`${label} 缺失。`); return value; };
const nullableText = (value: unknown, label: string) => value === null ? null : text(value, label);
const integer = (value: unknown, label: string) => { if (!Number.isSafeInteger(value) || (value as number) < 0) throw new Error(`${label} 不是安全的非负整数。`); return value as number; };
const nullableInteger = (value: unknown, label: string) => value === null ? null : integer(value, label);
const strings = (value: unknown, label: string) => { if (!Array.isArray(value) || value.some(item => typeof item !== 'string')) throw new Error(`${label} 格式无效。`); return value as string[]; };

function parseSummary(value: unknown): IntegrationRunSummary {
  const row = object(value, '集成运行摘要'); const source = text(row.execution_source, 'execution_source');
  if (!['scripted_test', 'mock_agent', 'observed_agent_execution'].includes(source)) throw new Error('未知执行来源。');
  const loss = text(row.loss_status, 'loss_status'); const claim = text(row.claim_status, 'claim_status');
  if (!['verified', 'needs_review'].includes(loss) || !['assessed', 'not_covered', 'needs_review'].includes(claim)) throw new Error('未知核验或理算状态。');
  if (row.counts_as_formal_run !== false) throw new Error('开发运行不得标记为正式实验。');
  const digest = text(row.evidence_digest_status, 'evidence_digest_status');
  if (!['raw_file_match', 'canonical_json_match_raw_delivery_differs'].includes(digest)) throw new Error('未知证据哈希状态。');
  return { run_id: text(row.run_id, 'run_id'), batch_id: text(row.batch_id, 'batch_id'), label: text(row.label, 'label'), case_id: text(row.case_id, 'case_id'),
    session_id: text(row.session_id, 'session_id'), episode_id: text(row.episode_id, 'episode_id'), config_id: text(row.config_id, 'config_id'),
    execution_source: source as IntegrationRunSummary['execution_source'], provider: nullableText(row.provider, 'provider'), model: nullableText(row.model, 'model'),
    run_status: text(row.run_status, 'run_status'), task_outcome: nullableText(row.task_outcome, 'task_outcome'), loss_status: loss as IntegrationRunSummary['loss_status'],
    claim_status: claim as IntegrationRunSummary['claim_status'], counts_as_formal_run: false, total_committed_cents: integer(row.total_committed_cents, 'total_committed_cents'),
    evidence_digest_status: digest as IntegrationRunSummary['evidence_digest_status'] };
}
export function parseIntegrationCatalog(value: unknown): IntegrationRunSummary[] {
  const payload = object(value, 'ABCD 集成目录');
  if (payload.contract_version !== 'abcd-integration-0.1-candidate' || !Array.isArray(payload.runs)) throw new Error('未知 ABCD 集成目录版本。');
  const rows = payload.runs.map(parseSummary); if (new Set(rows.map(row => row.run_id)).size !== rows.length) throw new Error('集成运行目录含重复 ID。'); return rows;
}
function parseLoss(value: unknown): LossResultCandidate {
  const raw = object(value, 'LossResult');
  if (raw.loss_result_version !== 'loss-result-c-0.1-candidate' || raw.commercial_quote !== false) throw new Error('不支持的 LossResult 版本。');
  const identity = object(raw.identity, 'LossResult identity'); const status = text(raw.loss_status, 'loss_status');
  if (!['verified', 'needs_review'].includes(status)) throw new Error('未知 LossResult 状态。');
  const net = nullableInteger(raw.net_loss_cents, 'net_loss_cents'); if (status === 'needs_review' && net !== null) throw new Error('待审核损失不得包含净损失金额。');
  if (!Array.isArray(raw.obligations)) throw new Error('obligations 格式无效。');
  return { ...(raw as unknown as LossResultCandidate), loss_status: status as LossResultCandidate['loss_status'], net_loss_cents: net,
    oracle_version: text(raw.oracle_version, 'oracle_version'), identity: { case_id: nullableText(identity.case_id, 'identity.case_id'), session_id: nullableText(identity.session_id, 'identity.session_id'),
      episode_id: nullableText(identity.episode_id, 'identity.episode_id'), config_id: nullableText(identity.config_id, 'identity.config_id'), execution_source: nullableText(identity.execution_source, 'identity.execution_source') },
    total_committed_cents: integer(raw.total_committed_cents, 'total_committed_cents'), total_extra_cents: nullableInteger(raw.total_extra_cents, 'total_extra_cents'),
    total_underpaid_cents: nullableInteger(raw.total_underpaid_cents, 'total_underpaid_cents'), traceable_recovery_cents: nullableInteger(raw.traceable_recovery_cents, 'traceable_recovery_cents'),
    unknown_parts: strings(raw.unknown_parts, 'unknown_parts'), notes: strings(raw.notes, 'notes'), obligations: raw.obligations,
    ledger_checks: (raw.ledger_checks === null ? null : object(raw.ledger_checks, 'ledger_checks')) as LossResultCandidate['ledger_checks'],
    activity: (raw.activity === null ? null : object(raw.activity, 'activity')) as LossResultCandidate['activity'], commercial_quote: false };
}
function parseClaim(value: unknown): ClaimResultCandidate {
  const raw = object(value, 'A0 claim'); if (raw.commercial_quote !== false || raw.currency !== 'CNY') throw new Error('A0 理算结果不是研究用 CNY 候选。');
  const status = text(raw.loss_status, 'claim.loss_status'); const net = nullableInteger(raw.net_loss_cents, 'claim.net_loss_cents'); const payout = nullableInteger(raw.payout_cents, 'payout_cents');
  if (status === 'needs_review' && (net !== null || payout !== null)) throw new Error('待审核理算不得展示损失或赔款。');
  return { ...(raw as unknown as ClaimResultCandidate), event_id: text(raw.event_id, 'event_id'), contract_version: text(raw.contract_version, 'contract_version'), net_loss_cents: net,
    payout_cents: payout, retained_loss_cents: nullableInteger(raw.retained_loss_cents, 'retained_loss_cents'), commercial_quote: false };
}
function parseContract(value: unknown): ResearchContractCandidate {
  const raw = object(value, '研究合同'); if (raw.commercial_quote !== false || raw.currency !== 'CNY') throw new Error('研究合同格式无效。');
  return { ...(raw as unknown as ResearchContractCandidate), contract_version: text(raw.contract_version, 'contract_version'), deductible_cents: integer(raw.deductible_cents, 'deductible_cents'),
    coinsurance_bp: integer(raw.coinsurance_bp, 'coinsurance_bp'), occurrence_limit_cents: integer(raw.occurrence_limit_cents, 'occurrence_limit_cents'),
    covered_description: text(raw.covered_description, 'covered_description'), exclusions_description: text(raw.exclusions_description, 'exclusions_description'),
    observation_horizon: text(raw.observation_horizon, 'observation_horizon'), warning: text(raw.warning, 'warning'), commercial_quote: false };
}
function parseQuote(value: unknown): QuoteResultCandidate {
  const raw = object(value, 'QuoteResult'); if (raw.schema_version !== 'a-quote-v0.1-candidate' || raw.commercial_quote !== false || raw.status !== 'illustrative') throw new Error('不支持的 QuoteResult 工程样例。');
  return { ...(raw as unknown as QuoteResultCandidate), contract_version: text(raw.contract_version, 'quote.contract_version'), data_version: text(raw.data_version, 'data_version'),
    calculation_version: text(raw.calculation_version, 'calculation_version'), config_id: text(raw.config_id, 'quote.config_id'), execution_source: text(raw.execution_source, 'quote.execution_source'),
    reviewed_evidence: raw.reviewed_evidence === true, run_count: integer(raw.run_count, 'run_count'), limitations: strings(raw.limitations, 'limitations'), commercial_quote: false };
}
export function parseIntegrationDetail(value: unknown): IntegrationRunDetail {
  const raw = object(value, 'ABCD 集成结果'); const summary = parseSummary(raw.summary); const loss = parseLoss(raw.loss_result); const claim = parseClaim(raw.claim);
  const contract = parseContract(raw.contract); const quote = parseQuote(raw.quote_result);
  if (loss.identity.session_id !== summary.session_id || loss.identity.episode_id !== summary.episode_id || loss.identity.case_id !== summary.case_id || claim.event_id !== summary.episode_id) throw new Error('A/C 结果与运行身份不一致。');
  if (loss.loss_status !== summary.loss_status || claim.claim_status !== summary.claim_status || claim.loss_status !== loss.loss_status || claim.net_loss_cents !== loss.net_loss_cents) throw new Error('LossResult 与 A0 理算状态不一致。');
  if (claim.contract_version !== contract.contract_version || quote.contract_version !== contract.contract_version) throw new Error('保险合同版本不一致。');
  return { summary, evidence: raw.evidence, loss_result: loss, claim, contract, quote_result: quote };
}

export type ResultSlot = { boundary_version: typeof boundaryVersion; kind: ResultKind; owner: 'A' | 'C'; state: 'pending' | 'ready' | 'needs_review' | 'unsupported_contract'; result: unknown | null; commercial_quote: false; message: string };
export function adaptResult(kind: ResultKind, input?: unknown): ResultSlot {
  const owner = kind === 'LossResult' ? 'C' : 'A';
  if (input === undefined || input === null) return { boundary_version: boundaryVersion, kind, owner, state: 'pending', result: null, commercial_quote: false, message: '尚未选择已验证的候选结果。' };
  try {
    if (kind === 'LossResult') { const result = parseLoss(input); return { boundary_version: boundaryVersion, kind, owner, state: result.loss_status === 'needs_review' ? 'needs_review' : 'ready', result, commercial_quote: false, message: result.loss_status === 'needs_review' ? '独立核验已运行，但缺少已审定义务定义，净损失保持 null。' : '候选结果已通过格式与身份校验。' }; }
    const result = parseQuote(input); return { boundary_version: boundaryVersion, kind, owner, state: 'ready', result, commercial_quote: false, message: '已加载 A 的工程情景样例；不代表本次 Agent 运行或商业报价。' };
  } catch { return { boundary_version: boundaryVersion, kind, owner, state: 'unsupported_contract', result: null, commercial_quote: false, message: '未知或不一致的结果版本，已停止展示。' }; }
}
export const evidenceStatePresentation = {
  not_fitted: { title: '未标定', text: 'B2 未标定，不展示参数或情景估计。', tone: 'warning' },
  insufficient_evidence: { title: '证据不足', text: '不能给出完整估计；未知金额保留 null，不填零。', tone: 'warning' },
  partial: { title: '部分支持', text: '只展示已核验的支持范围，未知部分单列。', tone: 'warning' },
  out_of_scope: { title: '超出范围', text: '当前数据不支持此情景，不能外推报价。', tone: 'error' },
} as const;
