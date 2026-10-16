# FIXED_CASE_E2E

## 最终批次

- 批次：`integration-fixed-a-cases-20261015-202215`
- Git HEAD：`40da1d4957bbd3c4832b2bf0b7dad159f343bed3`
- 执行源：`scripted_test`，provider=`rule_baseline`，确定性、非模型、非付费。
- 决策表：`docs/business/business_policy_A_v0.2.md#2`，A-approved / D-pending，未双签。
- 每个运行 `counts_as_formal_run=false`、`cost_cny=0.0`。
- 链路：A public fixture → B 真实 loopback HTTP 创建 session → C 规则基线调用七工具 → B 交易/账本/工单 → C 独立 EvidenceBundle/LossResult → A0 `calculate_claim` → 前端只读 catalog/detail。

## A1-W_L-01：清晰整单退款

- session：`session-1f6fc9cfcc3f45bd9ba2d91198cd6436`
- runner/task：completed / completed。
- B 实际提交：54217 分，0 人工工单；交易与账本守恒。
- C：无 A/D obligation spec，因此 `needs_review/null`，没有把退款总额冒充损失。
- A0：`claim_status=needs_review`，`payout_cents=null`。
- 前端：可从风险结果加载精确 session 的交易和账本。

## A1-P_H-03：部分退款与相似订单

- session：`session-432e8ed00a2d41148ae68fad89d0442e`
- runner/task：completed / escalated。
- B 实际提交：0 分，1 人工工单。
- 原因：多笔候选订单都有历史确认，但当前申请没有结构化订单范围；没有从相似订单确认猜测当前请求。
- C/A0：均 `needs_review/null`。

## A1-P_L-05：重复确认

- session：`session-524907e4240e4f8d85750817c6726345`
- runner/task：completed / completed。
- B 实际提交：15630 分，0 人工工单。
- 相同确认去重后只处理一次；没有重复出款。
- C/A0：因缺 obligation spec，均 `needs_review/null`。

## ENG-A0-06：资格不足与人工升级

- session：`session-48280ee95e05414ab74c91a38280b40e`
- runner/task：completed / escalated。
- B 实际提交：0 分，1 人工工单。
- 资格不足且公开事实不能证明允许拆分，未放宽资金约束。
- C/A0：均 `needs_review/null`，没有把零出款写成已核验零损失。

## 兼容性结论

- B HTTP ↔ A fixture：PASS，四个案例可由严格 allowlist 创建 session，版本和 hash 固定，仍为 development_only。
- B ↔ C runner：PASS，七工具、session 身份、EvidenceBundle、账本、幂等和 schema v2 期初退款回归通过。
- C independent verifier ↔ A0：PASS（接口层）；LossResult 可直接进入理算函数。
- 业务/保险结论：PARTIAL；没有 Gold/obligation spec 时正确保持待审，不能得出正式损失或赔款。

## 历史批次说明

- `...-201056` 保留首轮零出款误判证据，不作为验收结果。
- `...-201156` 验证了 `needs_review/null` 修复，但 manifest 仍指旧决策表。
- `...-202215` 同时包含正确业务结果和 A v0.2 来源，作为本轮最终证据。
