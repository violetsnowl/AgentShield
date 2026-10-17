import { describe, it, expect } from 'vitest';
import { canStartRealRun, parseRealRunStatus, realRunBusy, realRunDisabledReasons, realRunStageLabel } from '../src/realRun';

const payload = {
  status: 'idle', batch_id: null, count: null, seed: null, stage: null, runs: [], batch_dir: null,
  error_code: null, paid: true, cap_cny: null,
  authorization: { paid_enabled: false, paid_reason: 'C_ENABLE_PAID_RUNS is not true', has_key: false, approval_cap_cny: null,
    prior_paid_cny: 0.112216, prior_paid_known: true, source_available: true, per_run_cap_cny: 0.5, allowed_counts: [1, 5], count_limit: 10 },
};

describe('真实运行桥接展示适配', () => {
  it('parses the honest unauthorized state with budget facts', () => {
    const status = parseRealRunStatus(payload);
    expect(status.status).toBe('idle');
    expect(status.authorization.has_key).toBe(false);
    expect(status.authorization.approval_cap_cny).toBeNull();
    expect(status.authorization.prior_paid_cny).toBeCloseTo(0.112216);
    expect(canStartRealRun(status)).toBe(false);
    const reasons = realRunDisabledReasons(status);
    expect(reasons.some(reason => reason.includes('DEEPSEEK_API_KEY'))).toBe(true);
    expect(reasons.some(reason => reason.includes('未授权'))).toBe(true);
  });
  it('enables start only when key, approval and source are all ready', () => {
    const status = parseRealRunStatus({ ...payload, authorization: { ...payload.authorization, has_key: true, approval_cap_cny: 0.5 } });
    expect(canStartRealRun(status)).toBe(true);
    expect(realRunDisabledReasons(status)).toHaveLength(0);
    const missingSource = parseRealRunStatus({ ...payload, authorization: { ...payload.authorization, has_key: true, approval_cap_cny: 0.5, source_available: false } });
    expect(canStartRealRun(missingSource)).toBe(false);
    expect(realRunDisabledReasons(missingSource)[0]).toContain('B-SCALE');
  });
  it('keeps single-flight honesty while a batch is queued or running', () => {
    const busy = parseRealRunStatus({ ...payload, status: 'running', stage: 'running', count: 1, batch_id: 'bscale-web-deepseek-x',
      runs: [{ label: '01_x', run_status: 'completed' }], authorization: { ...payload.authorization, has_key: true, approval_cap_cny: 0.5 } });
    expect(realRunBusy(busy)).toBe(true);
    expect(canStartRealRun(busy)).toBe(false);
    expect(realRunDisabledReasons(busy)[0]).toContain('单飞');
  });
  it('labels stages in plain Chinese', () => {
    expect(realRunStageLabel('sampling')).toBe('随机抽样中');
    expect(realRunStageLabel('running')).toBe('真实模型运行中');
    expect(realRunStageLabel('verifying')).toBe('自动 Gold 与复核中');
    expect(realRunStageLabel(null)).toBe('等待中');
  });
  it('tolerates malformed payloads without granting authority', () => {
    const status = parseRealRunStatus({ status: 'weird', authorization: 'nope', runs: 'nope' });
    expect(status.status).toBe('idle');
    expect(status.runs).toEqual([]);
    expect(canStartRealRun(status)).toBe(false);
  });
});
