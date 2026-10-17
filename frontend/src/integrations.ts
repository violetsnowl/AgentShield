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
export type P0ResearchPlan = {
  product_id: 'AgentShield-Core' | 'AgentShield-Plus'; display_name: string; contract_version: string; currency: 'CNY'; commercial_quote: false;
  deductible_cents: number; coinsurance_bp: number; occurrence_limit_cents: number; annual_aggregate_limit_cents: number;
  annual_aggregate_limit_status: 'display_only_not_enforced'; covered_loss: string; exclusions: string[];
};
export type P0ResearchProducts = {
  schema: 'AgentShield.P0_two_research_contracts.v0.1'; version: string; currency: 'CNY'; commercial_quote: false;
  annual_aggregate_enforced_in_A0: false; premium_status: 'insufficient_evidence'; plans: P0ResearchPlan[];
};
export type P0ClaimView = {
  product_id: 'AgentShield-Core' | 'AgentShield-Plus'; contract_version: string; event_id: string; currency: 'CNY';
  deductible_cents: number; coinsurance_bp: number; occurrence_limit_cents: number; annual_aggregate_limit_cents: number;
  annual_aggregate_calculation_status: 'display_only_not_enforced'; net_loss_cents: number | null; loss_status: 'verified' | 'needs_review';
  coverage_status: 'covered' | 'excluded' | 'needs_review'; claim_status: 'assessed' | 'not_covered' | 'needs_review'; payout_cents: number | null;
  retained_loss_cents: number | null; commercial_quote: false;
};
export type P0ClaimComparison = {
  display_schema: 'AgentShield.A_P0_claim_comparison.v0.1'; label: string; source_type: 'observed_agent_execution_pending_review';
  status: 'observed_run_not_formally_admitted' | 'A_study_reviewed_zero_loss_not_formal_insurance_claim'; commercial_quote: false; real_agent_insurance_claim: false; event_id: string;
  net_loss_cents: number | null; loss_status: 'verified' | 'needs_review'; coverage_status: 'covered' | 'excluded' | 'needs_review';
  claims: P0ClaimView[]; notes: string[];
  A_study_coverage_review?: { review_version: string; coverage_scope_status: 'covered' | 'excluded'; covered_loss_triggered: boolean; formal_claim_adjudication: boolean };
  source?: { C_loss_result_sha256?: string; evidence_sha256?: string; obligation_spec_id?: string; C_original_coverage_status?: string; C_verified_net_loss_cents?: number };
};
export type IntegrationRunDetail = { summary: IntegrationRunSummary; evidence: unknown; loss_result: LossResultCandidate; claim: ClaimResultCandidate; contract: ResearchContractCandidate; quote_result: QuoteResultCandidate; p0_products: P0ResearchProducts | null; p0_claim_comparison: P0ClaimComparison | null };
export type BScaleBatchStatus = {
  status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'; batch_id: string | null; seed: string | null;
  total: number; completed: number; normal_refund: number; manual_review: number; failed: number;
  total_refund_cents: number; selected_task_ids: string[]; unique_count: number; paid_model_calls: 0; error_code: string | null;
};

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

export function parseBScaleBatchStatus(value: unknown): BScaleBatchStatus {
  const raw = object(value, 'B-SCALE 批次状态');
  const status = text(raw.status, 'batch.status');
  if (!['idle', 'queued', 'running', 'completed', 'failed'].includes(status)) throw new Error('未知批次状态。');
  const total = integer(raw.total, 'batch.total'); const completed = integer(raw.completed, 'batch.completed');
  const paid = integer(raw.paid_model_calls, 'batch.paid_model_calls');
  if (total > 100 || completed > total || paid !== 0) throw new Error('B-SCALE 批次边界无效。');
  return {
    status: status as BScaleBatchStatus['status'], batch_id: nullableText(raw.batch_id, 'batch.batch_id'), seed: nullableText(raw.seed, 'batch.seed'),
    total, completed, normal_refund: integer(raw.normal_refund, 'batch.normal_refund'), manual_review: integer(raw.manual_review, 'batch.manual_review'),
    failed: integer(raw.failed, 'batch.failed'), total_refund_cents: integer(raw.total_refund_cents, 'batch.total_refund_cents'),
    selected_task_ids: strings(raw.selected_task_ids, 'batch.selected_task_ids'), unique_count: integer(raw.unique_count, 'batch.unique_count'),
    paid_model_calls: 0, error_code: nullableText(raw.error_code, 'batch.error_code'),
  };
}

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
function parseP0Products(value: unknown): P0ResearchProducts | null {
  if (value === undefined || value === null) return null;
  const raw = object(value, 'A-P0 products');
  if (raw.schema !== 'AgentShield.P0_two_research_contracts.v0.1' || raw.currency !== 'CNY' || raw.commercial_quote !== false || raw.annual_aggregate_enforced_in_A0 !== false || raw.premium_status !== 'insufficient_evidence' || !Array.isArray(raw.plans)) throw new Error('A-P0 研究合同格式无效。');
  const plans = raw.plans.map((value, index) => {
    const plan = object(value, `A-P0 plan ${index}`); const id = text(plan.product_id, 'product_id');
    if (!['AgentShield-Core', 'AgentShield-Plus'].includes(id) || plan.currency !== 'CNY' || plan.commercial_quote !== false || plan.annual_aggregate_limit_status !== 'display_only_not_enforced') throw new Error('A-P0 研究合同边界无效。');
    return { ...(plan as unknown as P0ResearchPlan), product_id: id as P0ResearchPlan['product_id'], display_name: text(plan.display_name, 'display_name'), contract_version: text(plan.contract_version, 'contract_version'),
      deductible_cents: integer(plan.deductible_cents, 'deductible_cents'), coinsurance_bp: integer(plan.coinsurance_bp, 'coinsurance_bp'), occurrence_limit_cents: integer(plan.occurrence_limit_cents, 'occurrence_limit_cents'), annual_aggregate_limit_cents: integer(plan.annual_aggregate_limit_cents, 'annual_aggregate_limit_cents'), exclusions: strings(plan.exclusions, 'exclusions') };
  });
  if (new Set(plans.map(plan => plan.product_id)).size !== 2) throw new Error('A-P0 研究合同集合不完整。');
  return { ...(raw as unknown as P0ResearchProducts), version: text(raw.version, 'P0 version'), plans };
}
export function parseP0Comparison(value: unknown, summary: IntegrationRunSummary, loss: LossResultCandidate, products: P0ResearchProducts | null): P0ClaimComparison | null {
  if (value === undefined || value === null) return null;
  const raw = object(value, 'A-P0 claim comparison');
  const reviewStatus = text(raw.status, 'P0 status');
  if (raw.display_schema !== 'AgentShield.A_P0_claim_comparison.v0.1' || raw.source_type !== 'observed_agent_execution_pending_review'
    || !['observed_run_not_formally_admitted', 'A_study_reviewed_zero_loss_not_formal_insurance_claim'].includes(reviewStatus)
    || raw.commercial_quote !== false || raw.real_agent_insurance_claim !== false || !Array.isArray(raw.claims)) throw new Error('A-P0 双方案结果格式无效。');
  const net = nullableInteger(raw.net_loss_cents, 'P0 net_loss_cents'); const status = text(raw.loss_status, 'P0 loss_status');
  if (raw.event_id !== summary.episode_id || status !== loss.loss_status || net !== loss.net_loss_cents) throw new Error('A-P0 双方案结果与 C 核验身份不一致。');
  const reviewed = reviewStatus === 'A_study_reviewed_zero_loss_not_formal_insurance_claim';
  if (reviewed) {
    const review = object(raw.A_study_coverage_review, 'A-P0 A_study_coverage_review');
    if (loss.loss_status !== 'verified' || review.review_version !== 'A7-insurance-coverage-review-v0.1' || review.coverage_scope_status !== raw.coverage_status
      || !['covered', 'excluded'].includes(String(raw.coverage_status)) || review.covered_loss_triggered !== false || review.formal_claim_adjudication !== false) throw new Error('A-P0 已审核结果缺少研究责任审查记录（或与 C 原始输入矛盾）。');
    const source = object(raw.source, 'A-P0 source');
    if (typeof source.C_loss_result_sha256 !== 'string' || typeof source.evidence_sha256 !== 'string' || typeof source.obligation_spec_id !== 'string'
      || source.C_original_coverage_status !== loss.coverage_status_input || source.C_verified_net_loss_cents !== net) throw new Error('A-P0 已审核结果与 C 原始损失/证据绑定不一致。');
  } else if (raw.coverage_status !== loss.coverage_status_input) throw new Error('A-P0 双方案结果与 C 核验身份不一致。');
  const versions = new Map(products?.plans.map(plan => [plan.product_id, plan.contract_version]));
  const claims = raw.claims.map((value, index) => {
    const row = object(value, `A-P0 claim ${index}`); const id = text(row.product_id, 'P0 product_id'); const payout = nullableInteger(row.payout_cents, 'P0 payout_cents'); const retained = nullableInteger(row.retained_loss_cents, 'P0 retained_loss_cents');
    if (!['AgentShield-Core', 'AgentShield-Plus'].includes(id) || row.event_id !== summary.episode_id || row.commercial_quote !== false || row.net_loss_cents !== net || row.loss_status !== status || row.coverage_status !== raw.coverage_status || (versions && row.contract_version !== versions.get(id as P0ResearchPlan['product_id']))) throw new Error('A-P0 双方案单项结果不一致。');
    if (reviewed && (row.claim_status !== 'assessed' || payout === null || retained === null || payout > Math.max(net ?? 0, 0))) throw new Error('A-P0 已审核单项结果必须为有界 assessed 金额。');
    if (status === 'needs_review' && (row.claim_status !== 'needs_review' || payout !== null || retained !== null)) throw new Error('A-P0 待审结果不得包含赔款金额。');
    return { ...(row as unknown as P0ClaimView), product_id: id as P0ClaimView['product_id'], contract_version: text(row.contract_version, 'P0 contract_version'), deductible_cents: integer(row.deductible_cents, 'P0 deductible_cents'), coinsurance_bp: integer(row.coinsurance_bp, 'P0 coinsurance_bp'), occurrence_limit_cents: integer(row.occurrence_limit_cents, 'P0 occurrence_limit_cents'), annual_aggregate_limit_cents: integer(row.annual_aggregate_limit_cents, 'P0 annual_aggregate_limit_cents'), net_loss_cents: net, payout_cents: payout, retained_loss_cents: retained };
  });
  if (new Set(claims.map(row => row.product_id)).size !== 2) throw new Error('A-P0 双方案结果不完整。');
  return { ...(raw as unknown as P0ClaimComparison), status: reviewStatus as P0ClaimComparison['status'], event_id: text(raw.event_id, 'P0 event_id'), net_loss_cents: net, loss_status: status as P0ClaimComparison['loss_status'], claims, notes: strings(raw.notes, 'P0 notes') };
}
export function parseIntegrationDetail(value: unknown): IntegrationRunDetail {
  const raw = object(value, 'ABCD 集成结果'); const summary = parseSummary(raw.summary); const loss = parseLoss(raw.loss_result); const claim = parseClaim(raw.claim);
  const contract = parseContract(raw.contract); const quote = parseQuote(raw.quote_result);
  if (loss.identity.session_id !== summary.session_id || loss.identity.episode_id !== summary.episode_id || loss.identity.case_id !== summary.case_id || claim.event_id !== summary.episode_id) throw new Error('A/C 结果与运行身份不一致。');
  if (loss.loss_status !== summary.loss_status || claim.claim_status !== summary.claim_status || claim.loss_status !== loss.loss_status || claim.net_loss_cents !== loss.net_loss_cents) throw new Error('LossResult 与 A0 理算状态不一致。');
  if (claim.contract_version !== contract.contract_version || quote.contract_version !== contract.contract_version) throw new Error('保险合同版本不一致。');
  const p0Products = parseP0Products(raw.p0_products); const p0Claims = parseP0Comparison(raw.p0_claim_comparison, summary, loss, p0Products);
  return { summary, evidence: raw.evidence, loss_result: loss, claim, contract, quote_result: quote, p0_products: p0Products, p0_claim_comparison: p0Claims };
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
