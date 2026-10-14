import { describe, it, expect } from 'vitest';
import { adaptResult, boundaryVersion, evidenceStatePresentation, parseIntegrationCatalog, parseIntegrationDetail } from '../src/integrations';

const summary = {
  run_id: '0123456789abcdef0123', batch_id: 'j2-development', label: '01_v1', case_id: 'case-1', session_id: 'session-1', episode_id: 'episode-1',
  config_id: 'config-1', execution_source: 'observed_agent_execution', provider: 'provider', model: 'model', run_status: 'completed', task_outcome: 'completed',
  loss_status: 'needs_review', claim_status: 'needs_review', counts_as_formal_run: false, total_committed_cents: 1500,
  evidence_digest_status: 'canonical_json_match_raw_delivery_differs',
};
const loss = {
  loss_result_version: 'loss-result-c-0.1-candidate', oracle_version: 'c-oracle-0.1-candidate', computed_at: '2026-10-13T00:00:00Z',
  identity: { case_id: 'case-1', session_id: 'session-1', episode_id: 'episode-1', config_id: 'config-1', execution_source: 'observed_agent_execution' },
  obligation_source: 'none', obligation_spec_id: null, horizon: 'pending-review', obligations: [], total_committed_cents: 1500,
  total_extra_cents: null, total_underpaid_cents: null, traceable_recovery_cents: null, net_loss_cents: null, task_outcome: 'completed',
  policy_compliance: 'not_evaluated', loss_status: 'needs_review', coverage_status_input: 'needs_review', ledger_checks: null, activity: null,
  unknown_parts: ['obligation_spec_missing'], notes: [], commercial_quote: false,
};
const claim = { event_id: 'episode-1', contract_version: 'research-v0.1', currency: 'CNY', net_loss_cents: null, loss_status: 'needs_review', coverage_status: 'needs_review', claim_status: 'needs_review', payout_cents: null, retained_loss_cents: null, commercial_quote: false };
const contract = { contract_version: 'research-v0.1', currency: 'CNY', deductible_cents: 10000, coinsurance_bp: 10000, occurrence_limit_cents: 100000, commercial_quote: false, covered_description: 'research', exclusions_description: 'research exclusions', observation_horizon: 'pending', warning: 'engineering only' };
const quote = { schema_version: 'a-quote-v0.1-candidate', commercial_quote: false, status: 'illustrative', contract_version: 'research-v0.1', data_version: 'engineering', calculation_version: 'a0', config_id: 'scripted', execution_source: 'scripted_test', reviewed_evidence: false, run_count: 9, methods: { B0: { label: 'mean', estimated_mean_cents_decimal: '500.0000', scenario_cost_cents_decimal: '500000.0000' }, B1: { label: 'weighted', estimated_mean_cents_decimal: '600.0000', scenario_cost_cents_decimal: '600000.0000' }, B2: { status: 'not_fitted', estimated_mean_cents_decimal: null, scenario_cost_cents_decimal: null } }, limitations: ['engineering only'] };

describe('versioned A/C presentation boundary', () => {
  it.each(['LossResult', 'QuoteResult'] as const)('%s remains pending without selected data', kind => {
    for (const input of [null, undefined]) expect(adaptResult(kind, input)).toMatchObject({ state: 'pending', result: null, commercial_quote: false, boundary_version: boundaryVersion });
  });
  it('accepts the C candidate while keeping needs_review money null', () => {
    expect(adaptResult('LossResult', loss)).toMatchObject({ state: 'needs_review', commercial_quote: false });
    expect(adaptResult('LossResult', { ...loss, net_loss_cents: 0 })).toMatchObject({ state: 'unsupported_contract', result: null });
  });
  it('accepts only the non-commercial illustrative A quote candidate', () => {
    expect(adaptResult('QuoteResult', quote)).toMatchObject({ state: 'ready', commercial_quote: false });
    expect(adaptResult('QuoteResult', { ...quote, commercial_quote: true })).toMatchObject({ state: 'unsupported_contract', result: null });
  });
  it('links summary, LossResult and A0 claim by exact run identity', () => {
    const catalog = parseIntegrationCatalog({ contract_version: 'abcd-integration-0.1-candidate', runs: [summary] });
    expect(catalog[0].counts_as_formal_run).toBe(false);
    const detail = parseIntegrationDetail({ summary, evidence: {}, loss_result: loss, claim, contract, quote_result: quote });
    expect(detail.loss_result.net_loss_cents).toBeNull();
    expect(detail.claim.payout_cents).toBeNull();
    expect(() => parseIntegrationDetail({ summary, evidence: {}, loss_result: { ...loss, identity: { ...loss.identity, session_id: 'other' } }, claim, contract, quote_result: quote })).toThrow(/身份不一致/);
  });
  it('keeps all required V1.1 unavailable states readable without numeric results', () => {
    expect(Object.keys(evidenceStatePresentation)).toEqual(['not_fitted', 'insufficient_evidence', 'partial', 'out_of_scope']);
    expect(evidenceStatePresentation.insufficient_evidence.text).toContain('null');
  });
});
