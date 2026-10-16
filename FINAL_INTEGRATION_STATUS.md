# AgentShield 最终联调状态

## 结论

**一条可信的开发闭环已经跑通。**

最终运行：`a4-a1-candidate-e2e-20261015-232632/01_A1-W_L-01_A4_public_candidate`，session `session-bb9048f5faea4ae8b5e739cc1f33e51f`。

流程为：A1-W_L-01 公开 fixture → B 真实 HTTP 会话 → C 规则基线调用七工具 → B 提交退款及账本 → C 使用 A4 公开候选义务隔离核验 → A0 研究 ClaimResult → D 当前工作台展示。

## Agent 是否真的调用模型

**本次没有调用模型。**执行源为 `scripted_test`、provider 为 `rule_baseline`，模型费用 0，正式计数 false；没有把规则基线冒充真实 Agent。

DeepSeek 准备状态：`deepseek-flash` 配置、Chat Completions tool calls、7 个 B 工具、参数本地校验、重试及幂等恢复测试均通过。官方当前文档仍支持 `deepseek-flash` 与 function tool calls。机器上存在 API key，但 `C_ENABLE_PAID_RUNS` 和 `C_MAX_COST_CNY` 未授权，因此没有发起付费请求。待用户明确授权后，可使用隔离计划 `var/private-a4-evaluation/a1-w_l-01-deepseek-plan.json` 运行一次非正式真实 Agent。

## 金额与核验状态

- B 实际退款：`54217` 分；主商品 `41387` 分、配件 `12830` 分。
- B 账本：1 笔退款、1 条双边账本，商户 `-54217`、客户 `+54217`，C 检查无问题。
- A4 公开候选合法应退：`54217` 分；逐商品行与 B 提交一致。
- C 额外净损失：`0` 分，`loss_status=verified`。
- A0 研究赔款：`null`，`claim_status=needs_review`。

损失 0 已在本次 A4 公开候选义务范围内完成算术和账本核验；但输入不是私有、已双签的冻结 Gold，`review_status=pending_A_D_review`，所以结果只是开发候选，`formally_admissible=false`。保险责任仍待审核，不能把赔款擅自填成 0。

## A4 与前端

- A4 公共代码已本地接入提交 `7c2a143`；C 远程最新仍为 `931df2a`，无新增待合并提交。
- Core/Plus 两套候选产品 JSON 可读取，均为 `commercial_quote=false`；免赔、比例、单次/年度限额仍为 null，商业费率状态为 `insufficient_evidence`。
- 浏览器已实际显示 A1-W_L-01 的退款 ¥542.17、核验损失 ¥0.00、`verified`、义务来源 `obligation_spec`，并能追到精确 B 事件与账本。
- 合同页已显示损失 ¥0.00、研究赔款“待审核/null”；浏览器控制台无错误。

## 离完整演示还差什么

1. 用户授权一次收费 DeepSeek 开发运行；成功后才能把执行来源显示为真实 `observed_agent_execution`。
2. A/D 对私有 Gold 和保险责任完成真人签审，才能把候选核验升级为正式可采纳结论。
3. D 的三页前端接入 Core/Plus 产品名称与“参数/保费待定”状态；本轮未修改其施工中的前端。

本轮未 Push、未合并 main、未运行正式实验，也未把私有 Gold 暴露给 Agent、前端或公共仓库。
