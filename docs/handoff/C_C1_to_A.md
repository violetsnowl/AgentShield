# 给 A：C1 待确认事项

2026-10-14。C 的提交在 `feature/c-agent-evaluation` 的 `d977b4b`。完整记录见 `docs/handoff/C_C1_CHECKPOINT.md`。留出答案没有读取，56 次正式实验没有启动，也没有新的付费调用。

## 请 A 确认

1. **决策表。** 规则基线 `c-rule-baseline-0.1-candidate` 依据 `docs/business/business_policy_A_candidate.md` 第 2 节。同一订单上多份不同的累计确认不相加、不任选，转人工。订单上的 `refunded_quantity` 先占用确认上限。该表尚未双签，基线仍是候选程序。
2. **正式任务和 Gold。** 占位计划 `experiments/plans/l1_formal_blocked.json` 写明 56 次真实运行和 28 次规则基线，`runs` 为空。任务与 Gold 冻结后，C 才填入案例编号并开跑。
3. **零出款的读法。** 开发模板 `dev-refund-v1` 上，基线因确认冲突转人工，本回合已提交 0 分，损失为 `verified` / `net_loss_cents=0`，赔款为 `needs_review` / `payout_cents=null`。这个 0 表示本回合没有新出款。义务定义冻结前，它不能当作合法应付为零。
4. **预算。** 已有 3 次 `deepseek-flash` 开发运行合计上限 0.085458 元，单次最高 0.032044 元。这 3 次计入 10 次成本预试，不计入 56 次正式运行。按单次上限的 3 倍申请剩余预算：7 次预试 0.672924 元，56 次正式 5.383392 元，合计 **6.056316 元**。这是预算申请，不是报价。明细在 `experiments/fixtures/cost_pretrial_estimate.json`。确认之后 C 才补跑剩余 7 次预试。
