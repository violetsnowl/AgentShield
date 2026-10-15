# FRONTEND_RISK_INSURANCE_FIXES.md — 风险评估与保险方案定向修复

日期：2026-10-15/16 · 范围：**仅 D 线前端与前端测试**；未改 B/C/A 权威后端、业务规则与计算逻辑；本地完成，**未提交 / 未 Push / 未合并主分支**。

本轮只做内容准确性与数据映射修复，不涉及新设计讨论。

## 一、修复内容（P0-1 ~ P0-6）

### P0-1 核验待审核 ≠ 人工升级（已修复）
- 删除旧的「人工升级 = needs_review 数量」错误口径。
- 新增「**任务升级（task_outcome）**」卡：按交付 manifest 的 `task_outcome=escalated` 实时统计（当前 3），并附任务结果拆解行（completed 11 · escalated 3 · not_finished 1）。
- 「人工工单」列为独立维度（B 证据 `human_reviews`，当前 3 个运行、共 3 张），卡内注明与核验状态不能互相代替。
- 14 条 `needs_review` 移入「核验覆盖」卡（1 / 15，待核验 14，净损失保持 null、未记零；标注「待核验 ≠ 任务升级」）。

### P0-2 风险损失表达层次（已修复）
- 「核验损失（仅已核验样本）」卡**最上方先显示覆盖警示**（由纯函数实时生成，样本不足时自动出现）：
  “当前只有 1 / 15 次运行具有已核验损失结果，暂不足以估计整体风险。”
- 其下才是「已核验样本净损失 ¥0.00（1 条已核验，其中 1 条为已核验零损失）」。
- 零金额 / 未知 / 待审核分别显示：待核验为未知（null），不解释为 0、不并入合计；无已核验样本时显示「证据不足」。核验失败状态在当前交付数据中不存在；出现时将单列（不会并入任何合计）。

### P0-3 运行数量 ≠ 模型表现比较（已修复）
- 原「真实模型 vs Mock」改为「**开发运行来源**」：真实模型开发运行 / Mock 开发运行 / 规则基线（scripted_test、rule_baseline）/ 其他来源分别实时计数。
- 卡内注明：仅表示运行来源构成，**不等于任务正确率或风险高低对照**；`scripted_test` 不视为真实 LLM；同任务可比的核验对照待正式数据；开发运行不计入 56 次正式实验。

### P0-4 保险页改为 A4 真实 Core / Plus（已修复）
- 第三页主体改为 A4 两套研究候选产品卡（数据为 A4 公共包原样 JSON）：
  - **AgentShield 操作差错基础保障**（`AgentShield-Core`）
  - **AgentShield 操作差错增强保障**（`AgentShield-Plus`）
- 每卡展示：产品名称、产品定位与被保险人、保障责任、主要责任免除、免赔额、赔付比例、单次赔付限额、年度累计赔付限额、赔付结构、限额设计口径。
- Plus 独有：**处置费用附加子限额 = 「可选 · 待实现」**（当前无 A0 计算实现，仅登记为研究候选，不并入理算）。
- 预计赔款成本 / 商业保费：显示 `insufficient_evidence`（证据不足，不出具数字）；年度累计限额理算明确标注未实现。

### P0-5 不把 A0 研究合同冒充 Core / Plus（已修复）
- A4 中 `deductible_cents / coinsurance_bp / occurrence_limit_cents / annual_aggregate_limit_cents`（及 Plus 附加子限额）均为 `null` → UI 一律显示「**待定**」；核心浏览器断言确保方案卡区域内**不出现任何金额数字（无 ¥）**、且「待定」存在。
- 旧 A0 单事件工程理算能力保留，但移动到页面**下方折叠区**：「单事件理算工程示例（不代表 Core / Plus 保险报价）」（含 A0 合同参数与 QuoteResult 工程样例，`illustrative`、分离标注）。

### P0-6 A4 数据接入方式（按约束实现）
- B 观察者当前没有 A4 保险产品只读接口 → **未新增后端端点**，采用前端静态只读数据层：
  - 数据：`frontend/src/data/research_products_A4_candidate.json` —— A4 公共包（`智能2.zip → git_ready/configs/insurance/research_products_A4_candidate.json`）**原样拷贝、未改动**。
  - **加载与展示分离**：`frontend/src/data/a4Products.ts` 暴露 `loadA4Products()`；未来 B/A 提供正式只读接口时，**只需替换该函数实现，页面无需重新设计**。
- 页面保留准确的 `schema`（`AgentShield.two_research_products.v0.1`）、`status`（`product_design_candidate_not_bound`）、`commercial_quote=false` 与来源说明；未打包任何私有 Gold、API Key 或运行凭据。

## 二、测试（复用既有套件；未删除任何断言）

新增前端单测（vitest）：
- `frontend/tests/riskMetrics.test.ts`：测试1（needs_review ≠ escalated，含维度互换反例）、测试2（null ≠ 0，含“违规塞入金额也不被汇总”反例）、测试3（来源分桶：scripted_test 不计为真实模型）、覆盖文案边界、类别归类。
- `frontend/tests/a4Products.test.ts`：测试4（Core/Plus 与源文件一致）、测试5（null 参数保持待定、不被替换）。

核心浏览器新增断言（沿用既有套件）：
- `T1: needs_review is not tallied as task escalation` / `T1: pending verification keeps its own coverage dimension` / `T1: human review tickets reported as a separate dimension`
- `T2: verified sample loss carries the coverage caveat`（覆盖警示 + ¥0.00 + 样本口径）
- `T3: run sources labeled without performance comparison`（来源卡文案与反例词排除）
- `plans show pending values instead of invented premiums`（加严：两产品齐全 + 含「待定」+ 方案卡区域内无金额）
- `plans remain explicitly non-commercial`（加严：同时含 commercial_quote=false）

历史功能回归（测试6）：运行选择、证据追溯、离线回放、鉴权与只读边界等既有断言全部保留并全绿（全量电池）。

## 三、测试结果（本机实测）

- 前端单测：**7 文件 / 59 项全过**；`tsc --noEmit` 通过；生产构建通过。
- 全量电池 11 项全过：后端 unittest 125、契约检查 3、http checks、前端单测、typecheck、build、核心浏览器 1766 项、stage04 142 项、bcp2 21 项。
- 产物：`artifacts/pro_bd_sprint/05/receive-*-20261016-003500`（浏览器结果 JSON 与截图）。
- 验收截图：`artifacts/pro_bd_sprint/05/ia3-shots-20261015/ia3-2-risk-page.png`（风险评估）、`ia3-3-insurance-page.png`（Core/Plus 保险方案）。

## 四、仍需 A / B / C 的接口与数据（前端已如实占位）

| 缺口 | 归属 | 前端现状 |
|---|---|---|
| Core / Plus 参数审定（免赔 / 比例 / 单次与年度限额）、聚合保额定义 | A | 全部显示「待定」，无替代值 |
| 商业保费与预计赔款成本的权威测算 | A | `insufficient_evidence`，不出数字 |
| 处置费用附加责任的独立口径与子限额 | A | 「可选 · 待实现」 |
| 年度累计限额逐事件理算 | A/C | 明确标注未实现 |
| 正式 Gold 与正式 LossResult（正式样本） | A/C | 不生成、不伪造 |
| 企业业务汇总（B-SCALE）只读接口 | B | 「未接入」卡 |
| `rule_baseline` execution_source 枚举（含正式产品只读接口） | B | 来源分桶已兼容，无数据显示 0 |
| 同任务可比的核验对照（正式） | A/C/B | 文案注明「待正式数据」 |

## 五、按指令明确不做

不替 C 生成 LossResult；不替 A 审定保费；不接 B-SCALE；不运行真实 Agent；不生成正式统计样本；不实现年度累计理算。缺数据处一律显示 **待定 / 证据不足 / 尚未接入**。
