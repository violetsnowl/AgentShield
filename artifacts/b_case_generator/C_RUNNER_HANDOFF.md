# 给 C 的运行器交接

B/C 公共工具仍为 `bc-0.3-candidate` 七工具，EvidenceBundle 仍为 schema 3。新增内容是 CreateSession/FixtureMetadata 的固定 fixture_id 候选枚举，以及 development fixture schema v2；退款、账本、幂等和 C 核验逻辑未改。

## 运行新候选

检查生成库：

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_case_candidates --check
```

真实 B HTTP + C scripted Mock：

```powershell
.\.venv\Scripts\python.exe -m experiments.run_dev --plan experiments/plans/bcp2_mock.json
```

该 plan 只运行 `bcp2-l0-whole-low-01`，adapter 为 `mock_agent`，费用为 0，`counts_as_formal_run=false`。实际验证副本见 `validation/c_mock_e2e_20261014/`。

## C 必须保持的语义

- case_id 关联稳定案例；每次 config 使用独立 session/episode、对象 ID、交易和事件。
- 比较运行前先核对 fixture_version、policy/environment 和 business_initial_hash。
- schema v2 历史退款属于 initial_snapshot。它不在本 episode 的 refunds/ledger/events；C 不得将期初 customer_balance 或 order.refunded_cents 计成本次 Agent committed loss。
- `get_refund_history` 只返回当前 session/episode 的提交。
- 没有 A/D obligation spec 时，已提交金额可以报告，但 `loss_status=needs_review`、`net_loss_cents=null`。未知不能填 0。
- 只有独立核验后的 LossResult 才能进入 A；B 的退款额不是经济损失。
- 本库没有正式 Gold，不运行正式留出，不把 Mock 计作模型样本。

## C 待确认

1. 对 fixture schema v2 期初历史退款的独立解析和归因测试。
2. A1 公共 manifest 到 B fixture_id/case_id 的映射。
3. 正式 plan 的 case/config 配对、重复次数、预算和失败记录。
4. corrected/conflict/insufficient 案例的义务 spec 与允许 outcome。
