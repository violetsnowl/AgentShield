# C 对组员三条确认的回执

2026-10-15。C 已按下面三条继续自己职责内的准备，没有改 B 的共享协议，没有把四个固定案例写进当前分支的 fixture 枚举，也没有发起付费调用。

## 1. 四个案例的注册

确认：`A1-W_L-01`、`A1-P_H-03`、`A1-P_L-05`、`ENG-A0-06` 只在未推送的集成树上完成受控注册，状态仍是 `development_only`。当前 C 分支 `931df2a` 的 `FixtureId` 仍只有 `dev-refund-v1` 和 `dev-refund-v2`。真实 Agent 开发计划因此保持阻断，不能在这棵树上启动。

## 2. A1-P_H-03

已标记为「规则基线保守转人工，可能存在不必要升级」，业务判断留给 A。记录在 `experiments/fixtures/fixed_case_baseline_notes.json`。规则基线没有为 `order-main` 增加硬编码退款，也没有新增结构化“本次请求”字段。

若以后要做通用方案，C 会单独写一份字段说明，列出 B、C、A 和前端各自要改什么，并保证 Agent 与规则基线看到同一份公开信息。实施前再请负责人确认。

## 3. execution_source

本次联调继续使用 `scripted_test`，配置号 `c-rule-baseline-v0.1`，provider 为 `rule_baseline`。真实模型配置使用现有的 `observed_agent_execution`。C 不会单独把 `rule_baseline` 加进自己的枚举。下一版由 B 升级共享契约，C 适配运行器，A 核对精算来源枚举，前端做展示兼容，测试通过后再切换。

## 第一次真实运行怎么接

拿到已注册四案的集成树，并把本分支的 C 文件放上去之后，第一案用：

```powershell
python -m experiments.run_dev --plan experiments/plans/a1_w_l_01_agent_dev.json
```

这次只跑 `A1-W_L-01`。付费开关默认关闭；`C_ENABLE_PAID_RUNS`、正数 `C_MAX_COST_CNY` 和 `DEEPSEEK_API_KEY` 都到齐，并且负责人明确授权之后，这条命令才会调用 DeepSeek。当前这棵 C 分支没有四案注册，在这里执行不会打到模型。

跑完后的证据目录里会有轨迹、EvidenceBundle、账本和模型调用记录。A4 的已审核义务文件到位后：

```powershell
python -m experiments.reverify_evidence --evidence <run>/evidence.json --obligations <A4-spec.json> --out <run>
```

没有义务文件时，损失和赔款保持 `needs_review` / `null`。

四案计划仍是 `experiments/plans/fixed_cases_agent_dev_blocked.json`，第一案成功后再打开另外三案。模型配置是 `configs/runner/deepseek-fixed-dev-v0.1.json`。四次合计申请额 0.384528 元，这一次单独封顶 0.15 元。都还不是已批准预算。

正式 56 次加 28 次规则基线仍不启动。
