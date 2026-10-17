# 网页 → DeepSeek Runner 桥接交付（C→D 轻量交接的落地，2026-10-17）

C 的交接包（`docs/handoff/C_to_D_deepseek_00069697.md`）说明 Runner 及全链代码已在工程内，缺口只有
「网页按钮 → run_dev」的桥与「运行后核验链自动化」。本文件记录 D 侧落地方案与验证结果。

## 架构（全部复用现有组件，无新算法）

```
第一页「＋新建一次测试 · 真实 Agent 模式」
  └─ 运行 1 条 / 5 条（100 条保持扩展入口，禁用）
       └─ POST /observer/api/real-runs          （workbench/app.py，观察者鉴权）
            └─ RealRunManager                    （workbench/real_runs.py：单飞/持久化/恢复/授权探测）
                 └─ scripts/run_real_batch.py     （编排器，子进程）
                      ├─ sandbox.bscale_authorization.select_task_ids   随机抽样（固定种子可复现）
                      ├─ experiments.run_dev --plan <生成的计划>         复用 C Runner + B 沙箱
                      │    （付费开关仅在子进程注入：C_ENABLE_PAID_RUNS / C_MAX_COST_CNY）
                      ├─ scripts/a_bscale_auto_gold_batch.py             A5 自动 Gold（仅写仓库外私有目录）
                      └─ experiments.reverify_evidence                   C 核验 → 最终 loss_result/claim_A0
                           （原文件保留为 *_before_gold.json，另写 post_obligation/）
                 └─ 完成后 results.refresh_batch → 第二、三页自动联动（realBatchIdOf 前缀优选）
```

## 授权与预算（逐次、可审计）

- **密钥**：只从本机 `AgentShield/.env`（Git 忽略、原生支持）读取 `DEEPSEEK_API_KEY`；不入库、不入前端、不写日志。
  付费开关**不写入** `.env`，由编排器按批准范围在子进程环境逐次注入。
- **批准记录**：`var/real_run/approval.json`（Git 忽略）——`active_cap_cny` 为当前阶段生效上限；
  1 条 = ¥0.50、5 条 = ¥1.50（分阶段批准）。超额、缺批准或缺密钥都会在启动前被拒绝并给出原因。
- **全局上限口径**：`C_MAX_COST_CNY` 对应台账累计（含历史付费 ¥0.112216）；参数与配置的单次硬顶 ¥0.50 同时生效。
- **Gold 隔离**：自动 Gold 只写仓库外 `AgentShield_RealGold/<批次>/`；会话结束前不读取、不进入计划/提示词/B 环境。
- **launch_paid_api 永为 false**：计划保持 `status=development`、`counts_as_formal_run=false`，过 `formal_gates.dev_launch_block`。

## 免费 dry-run（不花钱走通同一条链路）

- 编排器支持 `--config configs/runner/rule-baseline-v0.1.json`（确定性基线，无模型调用）；
  QA 专用管理器（子类）可把任何启动强制为 dry-run——观察者端点从不传入，产品路径不受影响。
- 本地 QA：`artifacts/pro_bd_sprint/05/bridge-qa-20261017-181203/`（12/12，含进度渲染、完成横幅、
  权威目录回读、第二页仍指向正式真实批次不被 dry-run 劫持）。

## 验证（2026-10-17）

| 项 | 结果 |
|---|---|
| python 全量 | **225/225**（新增 `tests/test_real_run_bridge.py` 10 例：过门、批准边界、Gold 目录隔离、状态机、锁死回归、免费全链路） |
| vitest | **91/91**（新增 `realRun.test.ts` 5 例） |
| typecheck / build | 通过 |
| 核心浏览器 stage03 | core 260 / final 2076 全通过（0 模型调用、0 支付调用） |
| stage04 回归 | 174 通过 |
| 免费 dry-run 全链路 | 抽样→计划→run_dev（rule baseline）→自动 Gold→reverify→最终文件→读取器→目录，全部通过 |

## 运维说明

- 启动（本机）：观察者正常启动即可（真实面板状态自动探测：密钥/批准/源库/单飞）。
- 放行密钥：在 `E:\CUFE\竞赛\智能＋保险 2026\AgentShield\.env` 写入一行 `DEEPSEEK_API_KEY=...`（只此一行；不要写付费开关）。
- 运行：第一页 → 真实 Agent 模式 → 运行 1 条；完成后 批次 ID/种子/每案核验状态在面板与「历史测试」可见。
- 100 条：A5 自动 Gold 单次 ≤10 条（编排器已按 10 条分批循环），属扩展目标，需单独批准预算。

## 已知边界（诚实态）

- 新案例的**保险责任审查仍由 A 线下完成**（A7 同流程）；第三页在 `claim_core_plus` 缺失时显示「数据不足」，不冒充 0。
- 前端不直连模型、不持有密钥；B 子进程自动剥离付费环境变量（`experiments/b_process.py` 既有行为）。
- `counts_as_formal_run=false`：网络启动的批次均为开发运行，不计入正式 56 次。

## 首条网页端真实运行（2026-10-17 18:26，负责人批准 ¥0.50 内）

- 操作：第一页 → 真实 Agent 模式 → 「运行 1 条（单条贯通）」真实点击；随机任务 `rr-synth-00077620`。
- 结果：`bscale-web-deepseek-20261017-182612/01_bscale_sim_rr_synth_00077620`——completed；
  实际退款 22,067 分；**C 核验 verified、净损失 0 分**；A 赔款认定保持 `needs_review/null`（线下待审，不冒充 0）。
- 费用：**¥0.024428**（10,098 输入 / 529 输出 token，上限内）；台账合计更新为 ¥0.136644。
- 网页验收 15/15（0 控制台错误）：完成横幅（批次/核验）、第二页真实模式指向新批次（1 次 / 1 条已核验 ·
  操作错误 0/0 · 损失发生率 0.00% · 经济损失 ¥0.00）、第三页诚实「数据不足」（等 A 审查）；截图见
  `artifacts/pro_bd_sprint/05/paid-run-20261017-182607/`。
- 随附修复：真实运行「未正常完成」口径回归（manifest `run_status='completed'` 即正常完成；旧实现误按
  B 会话 `'finished'` 口径把干净运行数成未完成——目检发现并修复，实时页面复核 0/0）。
