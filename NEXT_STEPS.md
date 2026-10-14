# 当前停止点与下一步（2026-10-14）

> 本文件是全项目唯一的“状态真源”，只保留当前状态与下一步。被替换的旧停止点原文已迁入 `docs/archive/stop_points_2026-10-12_13.md`（保留原样）。**不要再把历史说明堆回本文件**；每次更新：改写“当前状态”，把上一版降级进归档。

## 当前状态

- `main`：已合入 ABCD 集成版（A/C L0 候选链 + D 只读展示 + 工作台集成视图），并完成 2026-10-14 文档系统整理。
- 计划书 V1.2（工作基线，2026-10-14 确认）已入库：`AgentShield_v1.2_Plan.md`（根目录）。
- 工作分支（都在 main 之上追加，未合回）：
  - `feature/bd-integration`（+1 提交）：B 案例生成器与 fixture v2、40 个公开候选案例、浏览器专项；**B 侧基本完成**，该分支接下来作为 **D 前端**的工作线。
  - `feature/c-agent-evaluation`（+2 提交）：C1-1 规则基线、正式计划占位、成本预审申请；等准入条件解除后执行。
  - `feature/a-gold-actuarial`：已建，待 A 开工。
- 所有现存运行均为开发运行（`counts_as_formal_run=false`）；无正式 Gold；无商业报价。

## P0：正式实验（56 次真实 + 28 次基线）的准入条件 —— 缺一不可

- [ ] 正式任务与 Gold 冻结、留出隔离（负责人 A/D；当前 40 个公开候选待审，见 `feature/bd-integration` 的 `artifacts/b_case_generator/A_GOLD_HANDOFF.md`）
- [ ] 规则基线决策表 A/D 双签（依赖 `docs/business/business_policy_A_candidate.md` 第 2 节）
- [ ] 研究预算确认（C 的申请上限 ¥6.056316 = 7 次预试 + 56 次正式；未确认前不调用付费接口，明细见 `feature/c-agent-evaluation` 的 `experiments/fixtures/cost_pretrial_estimate.json`）
- [ ] B 增加 `rule_baseline` 的 `execution_source` 枚举（C1 请求，属契约变更走契约 PR）
- [ ] 义务定义（obligation spec）就绪 —— 否则核验只能输出 `needs_review`、无法出损失数字
- [ ] A/C/BD 共同确认：正式清单、配置配对、样本计数、观测终点 H 与追回规则
- [ ] 历史证据的规范 JSON 哈希与 CRLF 交付字节差异口径（A/C/BD 共同定案）

## P1：团队验收与可移植性

- 第二台机器 / 第二操作者独立安装与复跑（记录环境、命令、退出码）。
- 网页冷启动 / 刷新离线方案；A 离线理算验收。
- 三个历史真实模型开发运行的 `needs_review` 补人工审核（净损失与赔付保持 `null`，不得由 D 猜测）。
- （旧）两处 ACL 受限旧库的核查（见归档停止点原文）。

## 禁止自行扩展（持续有效）

不自动进入正式实验；不调用收费模型或真实支付；不在浏览器重算保险；不放宽观察者鉴权；不改写历史证据；不代签。

## 版本锚点

- 基线标签：`baseline-20261013`（初始导入提交）。
- 分支与提交的实时状态：`git ls-remote origin` / `git log --oneline --all --decorate`。
