# INSURANCE_INTERFACE

## 当前真实可用能力

当前只有一个研究候选合同 `research-refund-ai-v0.1-candidate`：

- 保障对象：经 C 独立核验、在声明配置和范围内的非故意 AI 执行错误造成的可追溯额外净资金损失。
- 当前参数：事件免赔 10000 分；赔付比例 10000 bp（100%）；每次限额 100000 分；无已实现总累计限额。
- 研究赔款：仅在 `loss_status=verified` 且 `coverage_status=covered` 时计算；公式为事件级 `min(每次限额, 比例 × max(净损失-免赔, 0), 净损失)`，整数分、ROUND_HALF_UP。
- 除外：`coverage_status=excluded` 时赔款 0；证据或责任不明时必须 `needs_review/null`。
- 保险输入不是 B gross refund，而是 C 已独立核验的 event net loss。

A0 QuoteResult 还可计算：

- B0：已评估案例赔款的非分层 case mean × 目标业务量。
- B1：四个事前 strata 的目标权重 × 分层 case mean × 目标业务量。
- 同 case 重复运行先平均；estimation/holdout 和 parent group 防泄漏；不同 execution source 不混用。
- B2：`not_fitted`。
- 输出始终 `commercial_quote=false`；B0/B1 是纯风险成本情景，不是商业保费。

## 本轮四个案例的实际输出

四案都没有 A/D obligation spec，故 C LossResult 为 `needs_review/null`，A0 赔款也为 `needs_review/null`。这证明接口可消费合法输入并 fail closed，不证明商业价格。

仓库内工程合同算例覆盖已核验损失、免赔、赔付比例、限额、除外和追偿等算法，单测通过；它们明确是 engineering injection，不冒充真实 Agent 损失。

## 与“两套保险方案”要求的差距

当前尚未具备两套不同规格的产品。需要 A 提案、用户确认后才可实现：

- 两套方案各自的保障对象、责任、除外、免赔、赔付条件和限额含义。
- 保额选择方法与业务量/暴露量的联系。
- 可核验损失频率、严重度、追偿时点、置信/可信度方法。
- 商业保费加载：费用、资本、利润、税费、风险边际等；当前代码刻意不生成。
- 两套方案的保障与价格差异、版本和审批状态。

在这些输入冻结前，前端必须继续显示“待确认/非商业报价”，不得写死保费或把工程 B0/B1 当产品价。
