import { describe, expect, it } from 'vitest';
import { caseDisplay } from '../src/caseNames';

describe('案例名称', () => {
  it('随机任务用编号显示，不暴露内部前缀', () => {
    expect(caseDisplay('BSCALE-RR-SYNTH-00069697').name).toBe('随机退款任务 00069697');
  });

  it('未收录的案例原样显示，不虚构名称', () => {
    expect(caseDisplay('unknown-case').name).toBe('unknown-case');
  });
});
