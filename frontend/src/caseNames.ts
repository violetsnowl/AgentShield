/** IA v3 案例显示名映射（D 侧视图层）。
 * 只描述公开业务事实，不暗示 Agent 应如何处理；fixture id 保留在「运行详情」。
 * 生成来源：sandbox/fixtures/generated/registry.json；规则记录：docs/decisions/IA_V3_case_display_names.md */

export type CaseGroup = 'dev' | 'public' | 'stress' | 'engineering' | 'other';
export type CaseDisplay = { name: string; group: CaseGroup };

export const CASE_GROUP_LABELS: Record<CaseGroup, string> = {
  dev: '标准开发案例',
  public: '生成器公开案例',
  stress: '压力案例',
  engineering: '工程案例',
  other: '其它案例',
};

export const caseNames: Record<string, CaseDisplay> = {
  'dev-refund-v1': { name: '退款申请 · 多份确认', group: 'dev' },
  'dev-refund-v2': { name: '部分退款 · 含未确认消息', group: 'dev' },
  'bcp2-l0-whole-low-01': { name: '整单退款 · 小额 · L0-01', group: 'public' },
  'bcp2-l0-whole-low-02': { name: '整单退款 · 小额 · L0-02', group: 'public' },
  'bcp2-l0-whole-high-01': { name: '整单退款 · 大额 · L0-01', group: 'public' },
  'bcp2-l0-whole-high-02': { name: '整单退款 · 大额 · L0-02', group: 'public' },
  'bcp2-l0-partial-low-01': { name: '部分退款 · 小额 · L0-01', group: 'public' },
  'bcp2-l0-partial-low-02': { name: '部分退款 · 小额 · L0-02', group: 'public' },
  'bcp2-l0-partial-high-01': { name: '部分退款 · 大额 · L0-01', group: 'public' },
  'bcp2-l0-partial-high-02': { name: '部分退款 · 大额 · L0-02', group: 'public' },
  'bcp2-l1-whole-low-01': { name: '整单退款 · 小额 · L1-01', group: 'public' },
  'bcp2-l1-whole-low-02': { name: '整单退款 · 小额 · L1-02', group: 'public' },
  'bcp2-l1-whole-low-03': { name: '整单退款 · 小额 · L1-03', group: 'public' },
  'bcp2-l1-whole-low-04': { name: '整单退款 · 小额 · L1-04', group: 'public' },
  'bcp2-l1-whole-low-05': { name: '整单退款 · 小额 · L1-05', group: 'public' },
  'bcp2-l1-whole-low-06': { name: '整单退款 · 小额 · L1-06', group: 'public' },
  'bcp2-l1-whole-high-01': { name: '整单退款 · 大额 · L1-01', group: 'public' },
  'bcp2-l1-whole-high-02': { name: '整单退款 · 大额 · L1-02', group: 'public' },
  'bcp2-l1-whole-high-03': { name: '整单退款 · 大额 · L1-03', group: 'public' },
  'bcp2-l1-whole-high-04': { name: '整单退款 · 大额 · L1-04', group: 'public' },
  'bcp2-l1-whole-high-05': { name: '整单退款 · 大额 · L1-05', group: 'public' },
  'bcp2-l1-whole-high-06': { name: '整单退款 · 大额 · L1-06', group: 'public' },
  'bcp2-l1-partial-low-01': { name: '部分退款 · 小额 · L1-01', group: 'public' },
  'bcp2-l1-partial-low-02': { name: '部分退款 · 小额 · L1-02', group: 'public' },
  'bcp2-l1-partial-low-03': { name: '部分退款 · 小额 · L1-03', group: 'public' },
  'bcp2-l1-partial-low-04': { name: '部分退款 · 小额 · L1-04', group: 'public' },
  'bcp2-l1-partial-low-05': { name: '部分退款 · 小额 · L1-05', group: 'public' },
  'bcp2-l1-partial-low-06': { name: '部分退款 · 小额 · L1-06', group: 'public' },
  'bcp2-l1-partial-high-01': { name: '部分退款 · 大额 · L1-01', group: 'public' },
  'bcp2-l1-partial-high-02': { name: '部分退款 · 大额 · L1-02', group: 'public' },
  'bcp2-l1-partial-high-03': { name: '部分退款 · 大额 · L1-03', group: 'public' },
  'bcp2-l1-partial-high-04': { name: '部分退款 · 大额 · L1-04', group: 'public' },
  'bcp2-l1-partial-high-05': { name: '部分退款 · 大额 · L1-05', group: 'public' },
  'bcp2-l1-partial-high-06': { name: '部分退款 · 大额 · L1-06', group: 'public' },
  'bcp2-l0-stress-conflict': { name: '压力案例 · 双确认冲突 · L0', group: 'stress' },
  'bcp2-l0-stress-ineligible': { name: '压力案例 · 资格不符 · L0', group: 'stress' },
  'bcp2-l0-stress-injection': { name: '压力案例 · 越权指令文本 · L0', group: 'stress' },
  'bcp2-l0-stress-maximum': { name: '压力案例 · 订单上限 · L0', group: 'stress' },
  'bcp2-l1-stress-conflict': { name: '压力案例 · 双确认冲突 · L1', group: 'stress' },
  'bcp2-l1-stress-ineligible': { name: '压力案例 · 资格不符 · L1', group: 'stress' },
  'bcp2-l1-stress-injection': { name: '压力案例 · 越权指令文本 · L1', group: 'stress' },
  'bcp2-l1-stress-maximum': { name: '压力案例 · 订单上限 · L1', group: 'stress' },
};

/** 未收录的案例原样显示 fixture id，归入「其它案例」，不虚构名称。
 * 另支持 B 侧 source_case_id 的确定性别名：`case-<fixture id>` 与 `dev-case-refund-v1/v2`。 */
export function caseDisplay(id: string): CaseDisplay {
  return caseNames[id]
    ?? (id.startsWith('case-') ? caseNames[id.slice('case-'.length)] : undefined)
    ?? (id.startsWith('dev-case-') ? caseNames[`dev-${id.slice('dev-case-'.length)}`] : undefined)
    ?? { name: id, group: 'other' };
}
