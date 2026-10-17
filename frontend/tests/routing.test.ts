import { describe, expect, it } from 'vitest';
import { buildViewHash, parseViewState } from '../src/routing';

describe('parseViewState', () => {
  it('解析合法区域与运行标识', () => {
    expect(parseViewState('#area=risk&run=session-abc123')).toEqual({ area: 'risk', run: 'session-abc123', evidenceFocus: false, mode: null });
    expect(parseViewState('#area=test&run=session-1')).toEqual({ area: 'test', run: 'session-1', evidenceFocus: false, mode: null });
    expect(parseViewState('#area=insurance')).toEqual({ area: 'insurance', run: null, evidenceFocus: false, mode: null });
  });
  it('IA v3 兼容旧四区深链接（evidence 聚焦证据区）', () => {
    expect(parseViewState('#area=lab&run=session-1')).toEqual({ area: 'test', run: 'session-1', evidenceFocus: false, mode: null });
    expect(parseViewState('#area=evidence&run=session-1')).toEqual({ area: 'test', run: 'session-1', evidenceFocus: true, mode: null });
    expect(parseViewState('#area=cost')).toEqual({ area: 'insurance', run: null, evidenceFocus: false, mode: null });
  });
  it('未知区域被丢弃；非法语法的运行标识过滤', () => {
    expect(parseViewState('#area=admin&run=session-ok')).toEqual({ area: null, run: 'session-ok', evidenceFocus: false, mode: null });
    expect(parseViewState('#area=lab&run=has%20space')).toEqual({ area: 'test', run: null, evidenceFocus: false, mode: null });
    expect(parseViewState('#area=lab&run=%3Cscript%3E')).toEqual({ area: 'test', run: null, evidenceFocus: false, mode: null });
  });
  it('空 hash 与配对片段不产生可恢复状态', () => {
    expect(parseViewState('')).toEqual({ area: null, run: null, evidenceFocus: false, mode: null });
    expect(parseViewState('#pair=secret-grant')).toEqual({ area: null, run: null, evidenceFocus: false, mode: null });
  });
});

describe('buildViewHash', () => {
  it('在线模式往返一致', () => {
    const hash = buildViewHash('insurance', 'session-1', false);
    expect(parseViewState(hash)).toEqual({ area: 'insurance', run: 'session-1', evidenceFocus: false, mode: null });
  });
  it('离线回放不写入运行标识（来源文件不可恢复）', () => {
    const hash = buildViewHash('test', 'session-1', true);
    expect(hash).toBe('#area=test');
    expect(parseViewState(hash)).toEqual({ area: 'test', run: null, evidenceFocus: false, mode: null });
  });
  it('未选择运行时只保留区域', () => {
    expect(buildViewHash('test', null, false)).toBe('#area=test');
  });
  it('模式标识：real 显式入 URL 且往返一致；demo 为默认不写入；未知值丢弃', () => {
    const hash = buildViewHash('risk', 'session-1', false, 'real');
    expect(hash).toContain('mode=real');
    expect(parseViewState(hash)).toEqual({ area: 'risk', run: 'session-1', evidenceFocus: false, mode: 'real' });
    expect(buildViewHash('risk', 'session-1', false, 'demo')).not.toContain('mode=');
    expect(parseViewState('#area=risk&mode=weird')).toEqual({ area: 'risk', run: null, evidenceFocus: false, mode: null });
    expect(parseViewState('#area=risk&mode=real')).toEqual({ area: 'risk', run: null, evidenceFocus: false, mode: 'real' });
  });
});
