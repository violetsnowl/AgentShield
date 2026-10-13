import { describe, it, expect } from 'vitest';
import v1 from '../../artifacts/b_bootstrap/http_smoke/evidence_sample.json';
import v2 from '../../artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json';
import v3 from '../../contracts/evidence_example.json';
import fixture2 from '../../contracts/fixture_v2_evidence_example.json';
import { eventMeaning, money, orderedEvents, parseEvidence, statusText } from '../src/data';

describe('真实历史及当前 B 证据', () => {
  it.each([v1, v2, v3, fixture2])('accepts saved schema $schema_version without fabricating context', (value) => {
    const data = parseEvidence(value);
    expect(data.schema_version).toBe(value.schema_version);
    expect(data.case_context).toEqual('case_context' in value ? value.case_context : undefined);
  });
  it('keeps legacy_unavailable/null explicit', () => {
    const data = parseEvidence({ ...v3, case_context: null, case_context_status: 'legacy_unavailable' });
    expect(data.case_context).toBeNull();
  });
  it('rejects mixed sessions even with the same stable case', () => {
    const data = structuredClone(v3);
    data.events[0].session_id = 'another-session';
    expect(() => parseEvidence(data)).toThrow(/session/);
    expect(() => parseEvidence(v3, 'another-session')).toThrow(/运行身份/);
  });
  it('rejects mixed episode and duplicate event sequence', () => {
    const data = structuredClone(v3);
    data.events[0].episode_id = 'other-episode';
    expect(() => parseEvidence(data)).toThrow();
    data.events[0] = data.events[1];
    expect(() => parseEvidence(data)).toThrow();
  });
  it('rejects unknown schema/status and inconsistent recorded/null', () => {
    expect(() => parseEvidence({ ...v3, schema_version: 4 })).toThrow();
    expect(() => parseEvidence({ ...v3, case_context: null })).toThrow();
    expect(() => parseEvidence({ ...v3, events: [{ ...v3.events[0], status: 'committed' }] })).toThrow();
  });
  it('rejects credential-bearing imported files', () => {
    expect(() => parseEvidence({ ...v3, session_token: 'not-a-real-credential' })).toThrow();
    const data = structuredClone(v3);
    data.events[0].raw_arguments = { api_key: 'not-a-real-credential' } as typeof data.events[0]['raw_arguments'];
    expect(() => parseEvidence(data)).toThrow();
  });
  it('rejects duplicate transactions instead of counting them twice', () => {
    expect(() => parseEvidence({ ...v3, refunds: [...v3.refunds, v3.refunds[0]] })).toThrow(/重复交易/);
    expect(() => parseEvidence({ ...v3, ledger: [...v3.ledger, v3.ledger[0]] })).toThrow(/重复交易/);
  });
  it('requires an explicit schema version and exact integer money', () => {
    const { schema_version: _version, ...missingVersion } = v3;
    expect(() => parseEvidence(missingVersion)).toThrow(/schema/);
    const data = structuredClone(v3);
    data.refunds[0].amount_cents = Number.MAX_SAFE_INTEGER + 1;
    expect(() => parseEvidence(data)).toThrow(/整数范围/);
  });
  it('renders the real error status as an error, never a payment', () => {
    const data = parseEvidence(v3);
    expect(statusText.error).toBe('错误');
    expect(eventMeaning({ ...data.events[0], status: 'error', committed_amount_cents: 0 })).toBe('未新增提交');
  });
  it('sorts seq without altering original facts', () => {
    const data = parseEvidence(v3);
    const reversed = [...data.events].reverse();
    expect(orderedEvents(reversed).map(row => row.seq)).toEqual(data.events.map(row => row.seq));
    expect(reversed[0]).toBe(data.events.at(-1));
  });
  it('distinguishes reads, real commits, replay and no-money tickets', () => {
    const data = parseEvidence(v3);
    expect(eventMeaning(data.events.find(row => row.tool_name === 'get_case' && row.status === 'succeeded')!)).toContain('非付款');
    expect(eventMeaning(data.events.find(row => row.tool_name === 'submit_refund' && row.status === 'succeeded')!)).toContain('已提交');
    expect(eventMeaning(data.events.find(row => row.status === 'replayed')!)).toContain('无新增资金');
    expect(eventMeaning(data.events.find(row => row.tool_name === 'submit_human_review' && row.status === 'succeeded')!)).toContain('无资金');
  });
  it('formats integer cents and rejects unsafe money', () => {
    expect([0, 1, 333, -333, 100123].map(money)).toEqual(['¥0.00', '¥0.01', '¥3.33', '−¥3.33', '¥1,001.23']);
    expect(() => money(0.1)).toThrow();
    expect(() => money(Number.MAX_SAFE_INTEGER + 1)).toThrow();
  });
});
