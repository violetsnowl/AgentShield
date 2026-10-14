import { describe, expect, it } from 'vitest';
import { buildViewHash, parseViewState } from '../src/routing';

describe('parseViewState', () => {
  it('解析合法区域与运行标识', () => {
    expect(parseViewState('#area=risk&run=session-abc123')).toEqual({ area: 'risk', run: 'session-abc123' });
  });
  it('未知区域被丢弃；非法语法的运行标识过滤', () => {
    expect(parseViewState('#area=admin&run=session-ok')).toEqual({ area: null, run: 'session-ok' });
    expect(parseViewState('#area=lab&run=has%20space')).toEqual({ area: 'lab', run: null });
    expect(parseViewState('#area=lab&run=%3Cscript%3E')).toEqual({ area: 'lab', run: null });
  });
  it('空 hash 与配对片段不产生可恢复状态', () => {
    expect(parseViewState('')).toEqual({ area: null, run: null });
    expect(parseViewState('#pair=secret-grant')).toEqual({ area: null, run: null });
  });
});

describe('buildViewHash', () => {
  it('在线模式往返一致', () => {
    const hash = buildViewHash('cost', 'session-1', false);
    expect(parseViewState(hash)).toEqual({ area: 'cost', run: 'session-1' });
  });
  it('离线回放不写入运行标识（来源文件不可恢复）', () => {
    const hash = buildViewHash('evidence', 'session-1', true);
    expect(hash).toBe('#area=evidence');
    expect(parseViewState(hash)).toEqual({ area: 'evidence', run: null });
  });
  it('未选择运行时只保留区域', () => {
    expect(buildViewHash('lab', null, false)).toBe('#area=lab');
  });
});
