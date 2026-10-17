// C 运行配置注册表（只读快照 · 原样引入）。
// 来源：configs/runner/*.json（C 线已注册运行配置；2026-10-16 快照，字段由脚本逐项提取，未人工改写）。
// 用途：第一页「新建一次测试」的 Agent 选择器；仅列出真实已注册配置。
// 数据加载与展示分离：未来若 C/B 提供只读配置接口，只需替换 loadRunnerConfigs 的实现。
import raw from './runner_configs.json';

export type RunnerConfig = {
  config_id: string;
  adapter: string;
  execution_source: string;
  provider: string | null;
  model: string | null;
  frozen: boolean;
  max_run_cost_cny: number | null;
  notes: string;
  source_path: string;
};

export const RUNNER_CONFIGS_SOURCE_LABEL = 'configs/runner/*.json（C 线已注册配置 · 2026-10-16 快照）';

export async function loadRunnerConfigs(): Promise<RunnerConfig[]> {
  return raw as unknown as RunnerConfig[];
}

/** 选择器展示文案：规则基线=确定性免费；openai_compatible=真实模型（需付费授权）。 */
export function agentConfigLabel(config: RunnerConfig): string {
  if (config.adapter === 'rule_baseline') return '规则基线（确定性 · 无模型调用）';
  if (config.adapter === 'mock') return '接口模拟 Mock（记录用 · 非真实模型）';
  return `${config.provider ?? '未知提供商'} / ${config.model ?? '未知模型'}（真实模型 · 需付费授权）`;
}
