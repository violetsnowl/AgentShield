/** N03 URL 导航状态：只承载非敏感标识（区域 + session_id），令牌、授权与 Gold 一律不入 URL。 */

export type AreaId = 'lab' | 'evidence' | 'risk' | 'cost';
const AREA_IDS: readonly AreaId[] = ['lab', 'evidence', 'risk', 'cost'];

export type ViewState = { area: AreaId | null; run: string | null };

/** 解析 `#area=<区>&run=<session_id>`；未知/非法值一律丢弃（不猜、不补、不硬编码 schema）。 */
export function parseViewState(hash: string): ViewState {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const area = params.get('area');
  const run = params.get('run');
  return {
    area: area && (AREA_IDS as readonly string[]).includes(area) ? (area as AreaId) : null,
    run: run && /^[a-z0-9._-]{1,128}$/i.test(run) ? run : null,
  };
}

/** 构造 hash：回放（离线）模式只保留区域，避免刷新后把文件内容误当可恢复的本机运行。 */
export function buildViewHash(area: AreaId, run: string | null, offline: boolean): string {
  const params = new URLSearchParams();
  params.set('area', area);
  if (!offline && run) params.set('run', run);
  return '#' + params.toString();
}
