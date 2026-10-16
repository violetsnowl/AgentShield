# C 检查点：C1-1 规则基线、正式计划与成本预试

2026-10-14。分支 `feature/c-agent-evaluation`，起点 `8c4b477`（与当时的 `origin/main`、`origin/feature/c-agent-evaluation` 相同，已包含 C L0）。本轮没有改运行循环、Mock、真实适配器或损失公式，也没有启动 56 次正式实验，没有调用付费接口，没有读取 A/D 留出答案。

## 本轮交付

- 确定性规则基线 `c-rule-baseline-0.1-candidate`：只读公开工具结果，经现有白名单和 HTTP 循环执行。决策表来源是尚未双签的 `docs/business/business_policy_A_candidate.md` 第 2 节。
- 正式规模占位 `experiments/plans/l1_formal_blocked.json`：24 常规 + 4 压力，真实配置重复 2 次共 56 槽，规则基线 28 槽，独立业务样本 28。`runs` 为空。
- 成本预试占位 `experiments/plans/c1_cost_pretrial_blocked.json`：用已有 3 次开发运行凑满 10 次所需的另外 7 次，只指向 `dev-refund-v1/v2`。
- 预算估算 `experiments/fixtures/cost_pretrial_estimate.json`。
- 期初历史退款与本回合提交分开记账。LossResult 字段集未改。

规则：同一订单上多份不同的累计确认不相加、不任选，转人工。订单字段 `refunded_quantity` 已经包含期初已退，确认上限先扣掉它，再决定本回合数量。`get_refund_history` 只代表本回合。

## 测试

环境：新建本地 `.venv`，按 `requirements.lock` 安装。Python 3.13。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

结果：131 项通过，退出码 0。其中新增 `tests/test_rule_baseline.py`、`tests/test_c1_preparation.py`。原有核验、运行器和全仓测试仍通过。

开发模板上的真实 HTTP（隔离 B，费用 0，`counts_as_formal_run=false`）：

```powershell
.\.venv\Scripts\python.exe -m experiments.run_dev --plan experiments/plans/c1_rule_baseline_dev.json
```

批次 `artifacts/c_l0/runs/c1-rule-baseline-dev-20261014-203301`（按仓库忽略规则留在本机，不进入提交）：

| 运行 | 结果 | 已提交 | 损失 | 赔款 |
|---|---|---|---|---|
| dev-refund-v1 | escalated，已建人工审核 | 0 分 | `verified` / `net_loss_cents=0` | `needs_review` / `payout_cents=null` |
| dev-refund-v2 | completed | 700 分（杯子 2、杯垫 2；包装袋未退） | `needs_review` / `null` | `needs_review` / `null` |

v1 的 `verified/0` 是现有核验器在“没有义务定义且本回合提交为 0”时的原行为。赔款函数仍给出 `needs_review`。这个 0 只表示本回合没有新出款，不能在 Gold 冻结前当成合法应付为零。

正式脚本：

```powershell
.\.venv\Scripts\python.exe -m experiments.run_formal --plan experiments/plans/l1_formal_blocked.json
```

退出码 2，`launch=false`，`paid_api_called=false`。把同一计划交给 `experiments.run_dev` 也会在启动 B 之前退出。

## 期初历史退款

B 的 `origin/feature/bd-integration`（`b0fe90b`）已能创建 `bcp2-l1-whole-low-04`。在该工作区调用公开工具后，用本轮归因代码读取证据：

- 期初客户余额和订单已退均为 10673 分；当时 `refunds` 为空，本回合已提交为 0。
- 规则基线对已退过 1 件、确认上限 3 件的商品行提交 2 件，另外两行按确认提交 2 件和 1 件。
- B 实际入账 53365 分。归因结果：期初仍为 10673，本回合已提交为 53365，账本问题列表为空。

本分支自己的 `EvidenceBundle` 还不能解析这份证据：`case_context.fixture_id` 只接受 `dev-refund-v1` 和 `dev-refund-v2`，检查脚本退出码 3。原始拆分仍能看到期初 10673 与本回合 53365 是两个字段。

## 接口变更

- 运行配置新增 `adapter=rule_baseline`。实现在 `runners/baseline.py`、`runners/adapters/rule_baseline.py`。
- 创建会话时的 `execution_source` 仍是现有枚举值 `scripted_test`。配置号 `c-rule-baseline-v0.1` 用来区分 B 的脚本测试和 Mock 场景。正式清单前需要 B 增加 `rule_baseline` 标签。
- bc-0.3、七个工具、EvidenceBundle schema 3、LossResult 字段和数据库迁移都没有改。
- 核验增加内部计数 `opening_refunded_cents`。它不进入 `total_committed_cents`。期初金额大于 0 时，`notes` 写明该金额留在初态。订单已退差额对不上本回合退款时，记入 `ledger_checks.issues`，损失改为 `needs_review`。
- 正式计划和预试计划带 `status=blocked`。开发运行器拒绝这种计划，也拒绝 `counts_as_formal_run=true` 或 `launch_paid_api=true`。

## 成本

已记录的 3 次 `deepseek-flash` 开发运行合计上限 0.085458 元，单次最高 0.032044 元。这 3 次计入 10 次预试，不计入 56 次正式运行。

按同一单次上限，并乘以 3 作为更长正式任务的预算申请（不是报价）：

- 剩下 7 次预试：0.672924 元
- 56 次正式：5.383392 元
- 申请授权合计：6.056316 元

不乘安全系数时，7 次预试 0.224308 元，56 次正式 1.794464 元。本轮没有新的付费调用。

## 下一阶段阻塞

1. A/D 冻结正式任务、Gold 和留出隔离。当前 40 份候选仍在复核，计划里没有案例编号。
2. A/D 双签第 2 节决策表。当前基线是候选程序。
3. 确认付费预算后再跑剩下 7 次预试；预算未确认前不调用真实接口。
4. 集成 B 的 fixture schema v2 和 42 个 fixture id 之后，C 的模型才能直接核验生成案例证据。
5. B 为规则基线增加独立的 `execution_source` 之后，正式 manifest 才能在线上和脚本测试分开。
6. 有义务定义之后，才能把 v1 这种零提交运行从“本回合未出款”推进到可比较的损失。
