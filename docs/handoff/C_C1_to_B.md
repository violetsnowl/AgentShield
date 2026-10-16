# 给 B：C1 接口核对

2026-10-14。C 的提交在 `feature/c-agent-evaluation` 的 `d977b4b`。完整记录见 `docs/handoff/C_C1_CHECKPOINT.md`。bc-0.3、七个工具、EvidenceBundle schema 3 和数据库迁移这轮都没有改。

## 期初历史退款

在 `origin/feature/bd-integration`（`b0fe90b`）上核对了公开案例 `bcp2-l1-whole-low-04`：

- 期初客户余额和订单已退都是 10673 分。当时 `refunds` 为空，本回合已提交记为 0。
- 已退 1 件、确认上限 3 件的商品行，规则基线再提交 2 件；另外两行按确认提交 2 件和 1 件。
- B 入账 53365 分。归因结果里期初仍是 10673，本回合已提交是 53365，账本问题列表为空。

## 请 B 配合的两处

1. C 当前模型的 `case_context.fixture_id` 只接受 `dev-refund-v1` 和 `dev-refund-v2`。解析上述证据时校验失败，`experiments.check_opening_refunds` 退出码 3。schema v2 和 42 个 fixture id 进入 C 所在代码之后，才能用提交里的模型直接核验生成案例。
2. 规则基线创建会话时暂时发送 `execution_source=scripted_test`，配置号是 `c-rule-baseline-v0.1`。正式清单前请在枚举中增加 `rule_baseline`，以便和 B 的脚本测试、Mock 场景分开。
