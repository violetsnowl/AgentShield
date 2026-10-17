# 真实 Agent 实测模式 · 接口结构草案（待与 C / A 对齐）

- 状态：**草案（未接通）**。本文不是已实现的接口，而是第一页「真实 Agent 实测」模式在接通前需要与 C（Runner）、A（理算/赔款）逐项对齐的结构清单。**在 C/A 回执前，前端不假设任何新字段、不发起任何真实模型调用。**
- 现行边界（已实现并可见）：模式选择器「研究情景演示 / 真实 Agent 实测」；真实模式下「运行 1 条」「运行小批量（≤10 条）」按钮**保持禁用**，并列明三条原因（未接通 / 未授权付费 / 未配置 B-SCALE 源）。前端绝不直连 DeepSeek、不持有 API Key（前端请求只发往本机观察者 `/observer/*`）。
- 相关既定纪律：付费模型默认关（`ENABLE_PAID_RUNS=false`、`MAX_COST=0`，运行器侧还会清扫 `DEEPSEEK_API_KEY/C_ENABLE_PAID_RUNS/C_MAX_COST_CNY` 等环境变量）；正式 56+28 实验未获批准不跑；不读正式留出 Gold；不接真实支付。

## 1. 需要的后端入口（建议形状 · 待 C 确认）

| 端点（本机观察者层） | 方法 | 作用 | 授权 |
| --- | --- | --- | --- |
| `/observer/api/real-batches` | POST | 启动一次真实 Agent 批次；body 仅 `{count: 1..10}`（先 1 条、再小批量；批次大小由操作者参数控制，浏览器不得选择更大范围） | 观察者 cookie + 服务端付费授权开关；未授权 → 明确错误码 |
| `/observer/api/real-batches/current` | GET | 批次状态（同现有批次状态字段形状） | 观察者 cookie |

结果消费沿用**现有已联调契约**：`/observer/api/integration-runs`（目录 + `batch_id` 过滤）与 `/observer/api/integration-runs/{run_id}`（逐条明细）。批次完成后由服务端刷新目录。

错误码建议（沿用现有文案通道）：`REAL_RUNNER_UNAVAILABLE`（C 运行器未接通）、`PAID_NOT_AUTHORIZED`（未授予付费授权/预算）、`BSCALE_SOURCE_UNAVAILABLE`（源数据未配置）、`BATCH_ALREADY_RUNNING`。

## 2. 前端消费的逐条字段（全部为已存在并经浏览器测试的契约字段）

- 运行身份：`summary.run_id / session_id / episode_id / case_id / batch_id / label / execution_source / provider / model / run_status / task_outcome / total_committed_cents`
- C 核验：`loss_result.loss_status`（`verified` / `needs_review`）、`loss_result.net_loss_cents`（null 不记 0）、`loss_result.obligations[].legally_due_cents`
- A 理算：`claim.claim_status`、`claim.payout_cents`；P0 双方案：`p0_claim_comparison.claims[].{product_id, contract_version, claim_status, payout_cents, loss_status, coverage_status, retained_loss_cents}`

**待与 C/A 对齐的问题（不作假设，逐条等回执）：**

1. （C）真实批次的执行入口：调用哪个模块/函数？单条与小批量的并发/超时/预算上限？批次 ID 与抽样种子由谁生成、落在哪个文件？
2. （C）任务选择：真实模式是否也从 B-SCALE 6105 任务池抽样（复用 `select_task_ids`）？是否沿用 evidence_status 构成？每个任务仍生成独立隔离会话与 episode？
3. （C）每条的核验路径：批次内是否逐条产出 `loss_result.json`（含 needs_review 语义）？运行中断/超时的逐条状态如何表达（`run_status` 取值表）？
4. （A）单事件赔款：真实模式的 Core/Plus 单事件赔款是否按 P0 口径逐条产出 `claim_core_plus.json`（与演示批次同构）？「保险责任未确定」与「触碰除外责任」分别落在哪些字段值上？
5. （A）核定边界：什么条件下允许某条从 `needs_review` 变为核定（`assessed`）？谁执行、记录在哪里？
6. （C/A）「全部有效核验」的判定标准：是否等价于批次内每条 `loss_status == verified` 且 `payout_cents != null`？是否允许混合批次（部分核定）出具部分外推？

## 3. 样本外推参考保费（前端展示逻辑 · 待 A 确认口径）

当前已实现并在浏览器测试中固化的三态展示规则（数据自身只有 needs_review 时永远停在「数据不足」，不会用 1% 假设冒充）：

```
P =（1 + 附加比例）× 年度任务量 V ×（已核定正赔款事件数 ÷ 样本量 n）× 平均单次赔款
```

- 全部有效核验且赔款均为 0 → **样本参考保费为 0**（不引入任何假设概率）；
- 任一条核验未完成（needs_review）或保险责任未确定（payout=null）→ **数据不足**，不出数字、不生成合同；
- 附加比例与年度任务量 V 复用研究情景配置（0.25 / 6,105），仅为研究口径；小样本外推**不是商业报价**，合同文本已与演示情景合同分开（「样本外推参考合同」，编号前缀 `SIM-sample-extrapolation-`）。

待 A 确认：公式与「已核定」定义；是否需要分层（按四个业务类别）外推；样本下限（n 低于多少直接判数据不足）；年度累计限额是否需要参与。

## 4. 前端已就绪、接通后无需改动的部分

- 模式标识贯穿三页（URL `mode=real`；第二、三页显示模式与当前批次 ID）；
- 第二页真实区块：运行数 / 已核验数 / 操作错误（未正常完成、转人工）/ 损失发生率 / 经济损失（后两者在核验不完整时显示「数据不足」）；
- 第三页样本外推区块：Core / Plus 两卡 + 不可生成时的禁用与原因逐条列出；
- 批次状态跨服务重启恢复（`var/bscale_authorization/current_batch.json`），「当前批次」与「历史」不混算。
