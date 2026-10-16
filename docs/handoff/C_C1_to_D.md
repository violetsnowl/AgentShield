# 给 D：C1 展示与复核

2026-10-14。C 的提交在 `feature/c-agent-evaluation` 的 `d977b4b`。完整记录见 `docs/handoff/C_C1_CHECKPOINT.md`。留出答案没有读取，56 次正式实验没有启动。

## 请 D 知道

1. **正式结果尚未产生。** 任务和 Gold 仍在复核，规则基线决策表也还没有双签。当前基线运行都是 `counts_as_formal_run=false`，不能放进正式对照。
2. **零出款要分开显示。** 开发模板 `dev-refund-v1` 上，本回合已提交 0 分，损失是 `verified` / `net_loss_cents=0`，赔款是 `needs_review` / `payout_cents=null`。界面应保持赔款为空。损失里的 0 只表示本回合没有新出款，义务定义冻结前不能显示成“应付为零”或“赔款 0 元”。`null` 与 0 继续区分。
3. **这轮不用改前端契约。** LossResult 字段集未改。期初已退放在核验内部的 `opening_refunded_cents`，不进入 `total_committed_cents`，也不是新的对外字段；期初金额大于 0 时只写在 `notes`。七个工具和 EvidenceBundle schema 3 未改。
