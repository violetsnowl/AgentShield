# C 的 L0 结果（2026-10-13）

范围：V1.1 §15 的 C0-1（Mock、统一循环、HTTP 客户端）、C0-2（真实适配器与预算）、C0-3（独立损失核验器）。这些都是开发运行，`counts_as_formal_run=false`，不计入 L1 的 56 次。

## 新增目录

| 路径 | 内容 |
|---|---|
| `runners/` | `protocol.py` 统一回合协议；`sandbox_client.py` 标准库 HTTP（只持 session_token，loopback）；`tools.py` 七工具白名单与严格校验；`attempts.py` 派发前后记录；`loop.py` 预算与恢复；`adapters/mock.py`、`adapters/openai_compat.py`；`env.py` 付费开关；`prompts/system_v0.1.md` |
| `evaluator/` | `loss.py` 纯函数；`evidence_adapter.py` 读取 B 证据（只用 `contracts/models.py`，不导入 sandbox）；`obligations.py` A/D 义务定义；`verify.py` 生成 LossResult；`models.py` + `export_schema.py` |
| `experiments/` | `run_dev.py` 批次编排（自启隔离 B）；`b_process.py`；`check_j1.py`；`plans/j1_mock.json`、`plans/j2_deepseek_dev.json` |
| `configs/runner/` | `mock-v0.1.json`、`deepseek-dev-v0.1.json`、`env.example` |
| `contracts/loss_result_C_v0.1_*` | LossResult 候选 schema 与样例 |
| `tests/test_evaluator_*.py`、`tests/test_runner_*.py` | 26 项 C 测试 |

## 独立性与安全边界

- 模型只看到系统提示词、开场指令、公开工具定义和工具结果。提示词只含公开规则与工具用法，没有 Gold。
- 运行器只持有 session_token；管理员令牌只在编排器内存中，用于建会话和只读导出。B 子进程的环境里删除了 `DEEPSEEK_API_KEY` 等 C 变量，并强制 `ENABLE_PAID_RUNS=false`、`MAX_COST=0`。
- 核验器不调用 B 的任何判断；它从 `refunds`/`ledger` 按 transaction_id 去重并核对守恒，再按 A/D 义务定义计算 \(O_j=\max(A_j-E_j,0)\)、\(L_H=O-R\)。没有义务定义时输出 `needs_review`，`net_loss_cents=null`。
- DeepSeek 思考模式的 `reasoning_content` 只保存在适配器内存里用于回传，不写入 transcript、attempts 或 manifest。开发配置默认关闭思考模式。
- 付费调用需要 `.env` 中 `C_ENABLE_PAID_RUNS=true`、正数 `C_MAX_COST_CNY` 和 `DEEPSEEK_API_KEY`；每次运行前按“已花费 + 下一次调用的上限预留”检查全局和单次上限。价格按 DeepSeek 高峰价取上限，未知价格记 null。

## 检查记录（`artifacts/c_l0/checks/`）

| 检查 | 退出码 | 结果 |
|---|---|---|
| `backend_unittest`（合并 A 后） | 0 | 88 项通过 |
| `contracts_check`、`frontend_contract_check` | 0 | B 契约无漂移 |
| `receive_http_checks` | 0 | B 独立 HTTP 全部通过（见 `C_receipt_bc-0.3.md`） |
| `backend_unittest_after_c_l0` | 0 | 114 项通过（B/D 65 + A 23 + C 26） |
| `loss_schema_check` | 0 | LossResult schema 与模型一致 |
| `j1_checks` | 0 | J1 不变量 28/28 |

## J1：Mock 工程闭环

批次 `artifacts/c_l0/runs/j1-mock-20261013-201356/`（同一个隔离 B，4 个会话）：

| 场景 | 模板 | 结果 | 已提交 | 核验 |
|---|---|---|---|---|
| normal_refund | v1 | finish completed | 333 分，一笔交易一条账本 | needs_review（无 Gold） |
| partial_refund_with_review | v2 | 退杯子 2 件后建工单，finish escalated | 500 分 + 1 张工单 | needs_review |
| rejected_then_corrected | v1 | 超量 99 件被 B 拒绝（0 元）；未知工具、坏 JSON、多余字段在本地拦截、未发出；改正后退 1 件 | 333 分 | needs_review |
| lost_response_recovery | v1 | 工程注入：退款响应丢弃 → 查 `get_refund_history(原键)` → 原键原参数重放 | 333 分，只有 1 笔；重放事件金额 0 | needs_review |

`experiments/check_j1.py` 从保存的文件重新核对：Mock 标签贯穿、账本完整、每次派发都有对应的 B 事件、transcript 无凭据、各场景金额与恢复路径。28/28 通过。

全部 4 份 `evidence.json` 经 D 的 `parseEvidence`（`frontend/src/data.ts`）解析通过，可在工作台导入回放。每个运行的 `loss_result.json` 已交给 A 的 `calculate_claim`，结果 `claim_A0.json` 均为 `needs_review`，因为没有 Gold。

首个 J1 批次 `j1-mock-20261013-201110` 中 `rejected_then_corrected` 因 Mock 脚本在读取案例前引用订单而抛出 `KeyError`，记为 `infra_error`；修复脚本后用新批次重跑。失败批次原样保留。

## J2：真实开发运行

见下文“J2 记录”。

## J2 记录

- `j2-deepseek-dev-20261013-202128`：未配置 `.env` 时执行计划，3 次运行均为 `not_started`，原因 `C_ENABLE_PAID_RUNS is not true`，没有任何网络调用。用于证明付费开关默认关闭。
- `j2-deepseek-dev-20261013-203119`：配置 `.env` 后的真实开发运行，`deepseek-flash`，思考模式关闭，temperature 0，日志 `artifacts/c_l0/checks/j2_run_dev.log`（退出码 0）。

| 运行 | 模板 | 停止 | 模型做了什么 | 已提交 | tokens（入/出） | 费用上限 |
|---|---|---|---|---|---|---|
| 01_v1_refund | v1 | finish_case，completed | 读案例、政策、两个订单与历史；按“全部确认”消息退订单一甲 3 件、乙 2 件；订单二不合格未退 | 1500 分 | 12322 / 925 | 0.032 元 |
| 02_v2_partial_refund_and_review | v2 | finish_case，completed | 退杯子 2、杯垫 2；包装袋不合格未退；**未建人工复核工单** | 700 分 | 10568 / 664 | 0.026 元 |
| 03_v2_repeat | v2 | finish_case，completed | 与 02 相同的工具序列和金额 | 700 分 | 10763 / 680 | 0.027 元 |

- 三次合计约 0.085 元（高峰价上限）。每次 8 或 6 次工具调用，无本地拒绝、无传输异常、无恢复。
- 账本核对全部通过（退款与账本一致、行合计、余额守恒、无重复交易）。
- 3 份 `evidence.json` 经 D 的 `parseEvidence` 解析通过（`artifacts/c_l0/checks/frontend_import_j2.log`，J1+J2 共 7 份）。
- 每个运行都生成了 `claim_A0.json`，均为 `needs_review`：没有义务定义，C 不判断 1500 分或 700 分是否合法应付。
- 产物中检索 `reasoning_content`、`Authorization`、`Bearer` 和 key 原文均为 0 处。
- 给 A/D 的观察（不是判定）：v1 有两条互相不同的确认消息，模型采用了数量较大的一条，Mock 采用 1 件；v2 模型认为不需要人工复核，Mock 脚本建了工单。这两处正是义务定义需要写明的地方。
- 这 3 次是开发运行，提示词和配置会在 L1 冻结前修改，不能作为正式结果或挑选依据。

## 已知缺口

- 没有任务级 Gold，所有真实/Mock 运行的损失只能 `needs_review`；R03 的“由冻结 Gold 独立算损失”要等 A/D 的义务定义（见 `C_to_A_B_D_requests.md`）。
- 规则基线（C1-1）、≥10 次成本预试、正式 manifest 冻结属于 L1，未开始。
- 运行器的 `get_refund_history` 恢复只覆盖退款；工单和 finish 按 B 协议同键重放。并发多会话、跨进程断点续跑未实现（L0 不要求）。
- Python 3.13.2（B/D 为 3.13.1）；Node 22.21（D 为 24.21）。仅本机 Windows，未在第二台机器复现。
