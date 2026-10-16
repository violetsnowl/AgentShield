# AgentShield ABCD 联调实际结果

## 验收结论

`ABCD_DEVELOPMENT_INTEGRATION_PASS`

同一独立工作树已经实际启动 B 服务和 D 三页前端，并把一条既有真实 DeepSeek 开发运行完整接入为：A 公开案例 → C 已保存的真实 Agent 轨迹 → B 退款与账本 → C 独立核验 → A 研究理算 → D 只读展示。当前结论仅代表开发联调通过，不代表正式 L1/J3/J4、正式 56+28 实验或商业保险方案获批。

本轮没有新调用收费模型、没有真实支付、没有读取私有 Gold、没有 Push、没有修改远程 main，也没有改动 D 的视觉设计或页面结构。工作台验收结束后已停止，端口 8816 已关闭。

## 代码来源与本地合并关系

2026-10-16 施工前重新执行了 `git fetch --all --prune`、`git ls-remote --heads origin`、`git log`、`git merge-base` 和分支差异核查。实际远程检查点为：

- main：`753fe69db6f8c2332d669b86d48d0e3cad8bed4f`
- B/D：`feature/bd-integration`，`f47592450fa345a3e57fd79866b8ec402dca03fb`
- C：`feature/c-agent-evaluation`，`21c56a407d2715e8900a64ac520ebfe82dc3b587`
- A：`feature/a-business-insurance-v0.2`，`e56ede42b4c2bdf7a6eb002f34578bfaac45b7cb`

独立工作树：`D:\作业合集\大三\智能+保险\AgentShield_ABCD_Integration_20261016`

本地分支：`integration/abcd-development-20261016`

合并链：

1. 从既有本地集成检查点 `a724bde` 建立新 worktree；该历史已包含 main、A 公共分支、四个固定案例注册、A4 公共代码和此前 C 集成成果。
2. 合并最新 B/D，生成 `408315f`。唯一文本冲突为 `frontend/src/App.tsx`，按 UI 决策文档保留 D 最新三页版本；合并后文件 SHA 与 B/D 分支版本完全一致：`be0562f0f4abf8285fdf21c7303fd00dcadd755a`。
3. 合并 C 最新准备代码，生成 `95dfa63`，无文本冲突。
4. 针对真实 A1 证据和新增交付目录做最小回归适配，生成 `facb6db704c0089f42c115fa839610769c22152e`。

A/B/C/D 代码现已处于同一工作树。没有对任何旧工作区做覆盖式合并。

## 实际修改及原因

- `artifacts/c_l0/cost_ledger.jsonl`：登记既有真实运行的原始 token 数与费用上界 `¥0.026758`；本轮新增调用数仍为 0。
- `tests/test_workbench.py`：原测试把目录中“第一条真实运行”硬编码为 `needs_review`。加入新的已核验真实运行后该假设失效；改为接受权威详情返回的 `verified/needs_review`，同时继续强制 `needs_review => net_loss_cents=null`、`payout_cents=null`。
- `frontend/tests/browser.mjs`：新增对真实 A1 默认运行、54217 分退款、C 零净损失、A 待审/null、真实工具事件、身份一致性和三页截图的浏览器断言；风险覆盖期望从旧目录的 `1/15` 更新为实际交付目录的 `2/16`。

没有修改后端业务规则、C 核验算法、A 理算公式或 D 产品前端源码。

## 真实 A1-W_L-01 证据链

原始运行批次目录：

`artifacts/c_l0/runs/a4-a1-deepseek-once-budgeted-20261016-002056`

运行目录：

`artifacts/c_l0/runs/a4-a1-deepseek-once-budgeted-20261016-002056/01_A1-W_L-01_real_DeepSeek_development`

逐层证据：

1. 运行身份与来源：`manifest.json`、`batch_manifest.json`。来源为 `observed_agent_execution`，provider/model 为 `deepseek/deepseek-flash`，`counts_as_formal_run=false`。
2. 真实模型与工具轨迹：`transcript.json`、`attempts.jsonl`。共有 4 次真实 provider response；工具顺序为 `get_case`、`get_business_policy`、`get_order`、`get_refund_history`、`submit_refund`、`finish_case`。
3. B 权威资金事实：`evidence.json`。session 为 `session-9a0236ff919449019325868386f2916c`，episode 为 `episode-session-9a0236ff919449019325868386f2916c`；退款提交 54217 分，客户 `+54217`、商户 `-54217`，交易和账本守恒。
4. C 核验：`loss_result.json`。使用 A4 公开候选义务输入，合法应退 54217 分，实际退款 54217 分，`loss_status=verified`，`net_loss_cents=0`。该义务仍标记为候选、待 A/D 真人签审，不冒充正式 Gold。
5. A 研究理算：`claim_A0.json`。`claim_status=needs_review`、`payout_cents=null`；没有把零净损失机械显示成零赔款。
6. D 适配结果：observer run id 为 `e06fec8c62df3cb74675`；同一 session/episode/config 可从详情接口和页面证据折叠区追溯。

原始批次从旧集成工作树按字节复制，9 个文件逐一核对 SHA-256 相同；未改写原始 manifest、退款、损失、赔款或来源标签。manifest 中记录的 canonical evidence SHA-256 为 `3205116657154dc238e7545dbe769012ab37ddd6cfa30991967df2856d5b5390`。核对日志：`artifacts/abcd_integration_20261016_round1/logs/01_real_run_integrity.log`。

## 第一页逐项核对

- 业务案例：A1-W_L-01，公开请求可见；默认选择的是已保存真实运行，不是本轮临时 session。
- 运行来源：真实模型开发运行，`observed_agent_execution`，DeepSeek / deepseek-flash；不计入正式 56 次。
- B 实际退款：54217 分，即 `¥542.17`。
- C 候选范围核验：合法应退 54217 分、净损失 0 分，状态 `verified`。
- A 研究赔款：状态 `needs_review`，赔款为 `null`，页面显示“待审核 / null”，未伪造为 0。
- 展开证据：可见 6 个真实工具事件、退款交易、账本、session/episode/config；只读回放没有再次提交退款。

## 实际测试记录

所有最终测试使用独立数据库和新输出目录，退出码均为 0：

- `py -m unittest discover -s tests -v`：163/163 通过，12.478 秒。日志：`artifacts/abcd_integration_20261016_round1/logs/05_python_unittest_final.log`。
- `py -m scripts.export_contracts --with-openapi --check`：B/OpenAPI 契约一致。日志：`06_openapi_contract.log`。
- `py -m scripts.export_frontend_contract --check`：前端 wire types 与 B/Evidence schema 一致。日志：`07_frontend_contract.log`。
- `py -m evaluator.export_schema --check`：LossResult schema 一致。日志：`08_loss_schema.log`。
- `py -m scripts.run_http_checks --output-dir artifacts/abcd_integration_20261016_round1/http`：B 独立 HTTP 通过；退款、账本、重启恢复、真实 TCP 断连恢复、跨 session 隔离和管理接口拒绝均通过，模型调用 0。日志：`09_http_checks.log`。
- 隔离 DB 固定案例创建检查：A1-W_L-01、A1-P_H-03、A1-P_L-05、ENG-A0-06 均返回 HTTP 201，四个 session/episode 独立，模型调用 0。日志：`10_fixed_case_sessions.log`。
- `npm test`：7 个文件、63/63 通过。日志：`12_frontend_tests_unsandboxed.log`。
- `npm run typecheck`：通过。日志：`13_frontend_typecheck.log`。
- `npm run build`：正式 Vite build 通过，27 个模块完成转换。日志：`14_frontend_build.log`。
- `py -m unittest tests.test_evaluator_evidence tests.test_evaluator_loss tests.test_actuarial_claims tests.test_a4_audit_and_boundaries -v`：C/A 聚焦回归 33/33 通过。日志：`24_c_a_focused.log`。
- `py -m scripts.run_workbench_checks --suite stage04 --output-dir artifacts/integration_abcd/round1-stage04-20261016`：121 项通过；延迟创建/合法导入保留，6 类篡改证据全部拒绝。日志：`18_workbench_stage04.log`。
- `py -m scripts.run_workbench_checks --output-dir artifacts/integration_abcd/round1-core-screenshots-final-20261016`：Edge/Chromium 155 实测 2046 项通过，20 张截图；未捕获异常 0、外网请求 0、模型调用 0、真实支付 0、浏览器写业务工具 0、原交易未变化。日志：`22_workbench_core_screenshots_final.log`，结构化结果：`artifacts/integration_abcd/round1-core-screenshots-final-20261016/browser_results.json`。

首轮还真实暴露并保留了三类非产品失败：Windows 沙箱 SQLite 锁、沙箱临时目录 `EPERM rename`、新增真实运行导致旧测试硬编码状态/数量漂移。前两项在非沙箱隔离进程重跑后通过；第三项通过上述最小测试适配修复。失败日志仍保存在 `02_python_unittest.log`、`03_python_unittest_unsandboxed.log`、`11_frontend_tests.log` 和早期浏览器日志中，没有删改。

## 浏览器实测

启动命令使用独立 DB 和输出目录；启动日志为 `artifacts/abcd_integration_20261016_round1/logs/19_live_workbench.log`。实际操作包括选择真实 A1 运行、展开证据、切换三页、切换到 Mock 后核对旧金额不残留、刷新/回退、证据回放、未授权访问、读取失败与六种篡改证据拒绝。

关键截图：

- 第一页真实运行：`artifacts/integration_abcd/round1-core-screenshots-final-20261016/real-a1-first-page-desktop.png`
- 第一页证据与身份：`artifacts/integration_abcd/round1-core-screenshots-final-20261016/real-a1-evidence-desktop.png`
- 第二页风险结论：`artifacts/integration_abcd/round1-core-screenshots-final-20261016/risk-overview-desktop.png`
- 第三页保险方案：`artifacts/integration_abcd/round1-core-screenshots-final-20261016/cost-candidate-desktop.png`

第二页当前展示 16 条开发记录、2 条已核验、14 条待核验、已核验样本净损失 `¥0.00`；页面明确分列真实模型与 Mock 来源并提示样本不足，不生成正式风险结论。第三页可读取 A4 Core/Plus 候选产品；保费、免赔、共保和限额仍为待定，A0 工程理算与 Core/Plus 候选方案分开显示。

安全检查确认：observer cookie 为 HttpOnly/Strict；前端响应、本地存储和构建产物不含 B 凭据或 API Key；未授权浏览器不能读取运行目录；所有浏览器请求均为本机 origin；读取和回放不会调用 B 写工具。

## 阻塞、暂缓项与责任人

本轮开发联调没有 P0 阻塞。

不影响本轮 PASS、但阻止正式结论或商业展示的事项：

- A/D：对 A4 候选义务和产品参数做真人签审；签审前不得升级为正式 Gold。
- A：确认 Core/Plus 的保额、免赔、限额、共保、保费公式及可调用测算接口；当前全部按待定展示。
- C：待正式授权后再执行 56+28；继续保持真实模型、规则基线和 Mock 的来源隔离。
- D：后续可补四个 A 固定案例的友好显示名；当前第一页显示 fixture id，但公开请求、身份与金额完整可追溯。这是文案/数据层改进，不是本轮运行阻断。
- 团队：若把该本地检查点交给另一台机器，必须连同被 `.gitignore` 保护的真实运行目录和浏览器证据目录一起安全传递；不得放入公共仓库。

## 接收与回退

当前源码、测试和本地证据足以供其他队员独立接收并重复无付费联调。推荐以本分支当前 HEAD 作为本地检查点；关键源码节点为 `95dfa63`，最小兼容/验收节点为 `facb6db704c0089f42c115fa839610769c22152e`。可通过 `git diff 95dfa63..facb6db` 独立审查本轮三处兼容改动；无需重写历史或影响远程分支。

工作台已停止。停止证明：`artifacts/abcd_integration_20261016_round1/logs/23_workbench_shutdown.log`。
