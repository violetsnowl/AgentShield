# C → A / B / D：L0 交付后的输入需求与交接件

2026-10-13。C 的 L0 结果见 `docs/handoff/C_L0_RESULTS.md`。本文件只列 C 需要别人提供什么、C 交给别人什么。所有候选都待对方审核签收。

## 给 A / D（Gold 管理方）：阻塞 R03 的输入

当前两个开发模板没有任务级合法应付义务，C 的核验器只能对真实运行输出 `needs_review`，并报告已提交金额。要让真实运行得到 `verified` 的损失，C 需要每个任务一份**义务定义文件**（obligation spec），格式见 `evaluator/obligations.py`，要点：

```json
{
  "spec_version": "obligation-spec-0.1-candidate",
  "spec_id": "唯一编号",
  "case_id": "与 B case_context 一致",
  "fixture_id": "...", "fixture_version": "...", "policy_version": "...",
  "source": "A_D_engineering | A_D_formal",
  "review_status": "A_D_reviewed | pending",
  "author": "A", "reviewer": "D",
  "closed_world": true,
  "obligations": [
    {"ref": "o1/i1", "template_order_id": "order-1", "template_item_id": "item-1", "legally_due_cents": 333}
  ],
  "recovery": {"policy": "none_in_sandbox"},
  "coverage_status_input": "covered | excluded | needs_review",
  "allowed_outcomes": ["completed"],
  "horizon": "观察终点 H 的定义"
}
```

- `legally_due_cents` 用模板对象 ID，C 通过 `case_context.object_mapping` 映射到运行 ID，不猜后缀。未知填 `null`，不能填 0。
- `closed_world=true` 表示清单外商品的应付视为 0；否则清单外退款进入 `needs_review`。
- `coverage_status_input` 是 A 的责任判定，C 只透传给 `actuarial.claims`，不自行判断。
- 文件放在 `datasets/gold/`（或 A/D 指定位置），**运行器和提示词目录不读取**；C 只在 `experiments/run_dev.py` 的核验阶段通过 plan 中的 `obligations` 字段加载。

请 A/D 优先提供：

1. 12 个 L0 工程任务的新模板（交给 B 登记）及其义务定义；`business_policy_A_candidate.md` 第 5 节的清单是起点。v1/v2 的“最多 N 件”确认不足以定唯一义务（A 自己的审查结论），需要补明确申请数量。
2. 观察终点 H 与追回规则。沙箱目前没有追回流程，C 暂按 `recovery.policy=none_in_sandbox` 处理：有出款时 R 只能在 spec 声明后才记 0。
3. 规则基线的公开决策表签收（`business_policy_A_candidate.md` 第 2 节），C1-1 将据此实现。
4. 研究预算确认：DeepSeek `deepseek-flash` 的实际 token 与按高峰价计算的费用上限逐次记录在 `artifacts/c_l0/cost_ledger.jsonl`，正式预算请按该记录估算。

## 给 A：LossResult 与理算的接口

- 候选 schema：`contracts/loss_result_C_v0.1_candidate.schema.json`（由 `evaluator/models.py` 生成，`python -m evaluator.export_schema --check` 防漂移）。
- 样例：`contracts/loss_result_C_v0.1_engineering_examples.json`（E03 已核验、E07 未知），`contracts/loss_result_C_v0.1_mock_example.json`（Mock 运行，needs_review）。
- `evaluator.verify.claim_event(loss_result)` 生成 `actuarial.claims.calculate_claim` 需要的 event；测试 `tests/test_evaluator_loss.py` 证明 9 个算例经 C 核验后再经 A 理算与手算一致（E03：净损失 520 元、赔款 420 元）。
- 每次运行目录都有 `claim_A0.json`，是把 LossResult 直接交给 A0 函数的结果；目前全部为 `needs_review`，因为没有 Gold，不是赔款结论。
- 给 A 的 B0/B1 输入（run rows）待正式任务和 split 确定后由 C 输出，字段按 `QuoteResult_A_v0.1_candidate.md` 第 3 条（case/parent/run/config/split/stratum/execution_source/manifest 引用）。

## 给 D：前端接入

- 每次运行的 `evidence.json` 是 B 管理端只读导出（schema 3），已用 D 的 `parseEvidence` 校验通过（见 C_L0_RESULTS），可直接在工作台“导入回放”。
- LossResult 适配请按候选 schema 和两份样例实现；`net_loss_cents=null` 与 0 必须区分，`loss_status=needs_review` 时不显示赔款数字。
- 运行清单：`artifacts/c_l0/runs/<batch>/batch_manifest.json` 与每个运行的 `manifest.json`，`counts_as_formal_run=false`。

## 给 B：协议意见（不阻断）

见 `docs/handoff/C_receipt_bc-0.3.md` 的“协议意见”：`$ref` 内联、`expected_version` 含义写入 description、`HistoryRequest.idempotency_key` 由运行器持有。
