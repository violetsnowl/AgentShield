/** N03 URL 导航状态：只承载非敏感标识（区域 + session_id），令牌、授权与 Gold 一律不入 URL。 */
export type AreaId = 'test' | 'risk' | 'insurance';
const AREA_IDS: readonly AreaId[] = ['test', 'risk', 'insurance'];
/** IA v3 兼容：旧四区深链接映射（lab/evidence → 测试页；evidence 额外聚焦详细执行证据；cost → 保险方案）。 */
const LEGACY_AREAS: Record<string, { area: AreaId; evidenceFocus: boolean }> = {
  lab: { area: 'test', evidenceFocus: false },
  evidence: { area: 'test', evidenceFocus: true },
  risk: { area: 'risk', evidenceFocus: false },
  cost: { area: 'insurance', evidenceFocus: false },
};
/**
 * 三个互不借用数据的全局模式：
 * - sampling 抽取检验：免费规则基线随机抽取与批量执行（执行驱动）；
 * - scenario 研究情景：预先固定的研究演示（无需运行，自成一体）；
 * - agent 真实Agent：真实调用 DeepSeek 的实测（执行驱动，只统计明确选择的批次）。
 * 默认模式为 sampling（不入 URL）。
 */
export type ModeId = 'sampling' | 'scenario' | 'agent';
const MODE_IDS: readonly ModeId[] = ['sampling', 'scenario', 'agent'];
export type ViewState = { area: AreaId | null; run: string | null; evidenceFocus: boolean; mode: ModeId | null };
/** 解析 `#area=<区>&run=<session_id>&mode=<模式>`；未知/非法值一律丢弃（不猜、不补、不硬编码 schema）。 */
export function parseViewState(hash: string): ViewState {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const area = params.get('area');
  const run = params.get('run');
  const mode = params.get('mode');
  const known = area
    ? (AREA_IDS as readonly string[]).includes(area)
      ? { area: area as AreaId, evidenceFocus: false }
      : LEGACY_AREAS[area] ?? null
    : null;
  return {
    area: known ? known.area : null,
    evidenceFocus: known ? known.evidenceFocus : false,
    mode: mode && (MODE_IDS as readonly string[]).includes(mode) ? mode as ModeId : null,
    run: run && /^[a-z0-9._-]{1,128}$/i.test(run) ? run : null,
  };
}
/** 构造 hash：回放（离线）模式只保留区域，避免刷新后把文件内容误当可恢复的本机运行。sampling 为默认模式不入 URL。 */
export function buildViewHash(area: AreaId, run: string | null, offline: boolean, mode: ModeId | null = null): string {
  const params = new URLSearchParams();
  params.set('area', area);
  if (!offline && run) params.set('run', run);
  if (mode !== null && mode !== 'sampling') params.set('mode', mode);
  return '#' + params.toString();
}
