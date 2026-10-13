# AgentShield 阶段 04 实际结果

2026-10-12。本轮在现有项目上先完成 04-0 审计修复、保存入口检查点，再完成原 04_D_INTEGRATION.md 的合理集成范围。已停止于 04，没有进入 05/L2，未重做 01/02/03。用户与舍友继续联合负责 BD，由用户现阶段统一推进。

## 输入、基线与保护

用户直接附加的 ZIP 为 `C:/Users/leo/Downloads/AgentShield_Stage03_Review_2026-10-12.zip`，不是已在项目中的路径。实际读出包内 REVIEW_REPORT.md、CODEX_04_ENTRY_PATCH.md、两份 frontend probe 的源码及 JSON，再安全解压至 docs/audit 同名目录，文件逐一不覆盖不同内容。ZIP SHA-256：dc01f6e110dd897dcdea50dc15bb74c52a363e22e363064efc0004525114b081。

已核对适用 AGENTS.md（未发现）和 Git（本目录无仓库），阅读当前源码、03/RESULTS、README/NEXT_STEPS/B_to_C、bc-0.3、observer-0.1、V1.1 和 04 任务。本机与 after_03 清单 429/429 文件一致。没有把审计环境中未跑的完整前端套件当成已通过，本轮用本机锁定依赖重新跑过。

施工前记录 `baseline_integrity.json`、`database_preservation_before.json`，保存 before_04。两份可读历史 SQLite 用只读连接 + backup API 一致备份在 var/stage04-private，排除出 ZIP；原库哈希收尾复核。两处历史目录 `var/migration-v1-vm5ra8a8`、`var/tmpt1rn8dz0` 仍拒绝访问，无法核查，未改 ACL、未清库。测试均为自身独占临时库，沿用项目 .venv，B/观察者仅 loopback。

## 实际修改

- `frontend/src/data.ts`：补退款行小计、唯一账本/交易关联、双边增量、逐笔与初末余额、订单商品退款增量、内部归属、事件配置/提交等事实等式核对。可核验矛盾拒绝展示；合法旧 schema 1/2 继续接受，缺失工单/成功事件留未知。哈希采用审计允许的明确声明分支：浏览器仅显示文件声明值、未复核；不把 hash 当签名。
- `frontend/src/App.tsx`：统一交互序号，迟到创建、目录、证据/分页与异步文件读取不覆盖新选择。已创建会话不撤销；响应未知先核目录。补已加载运行与来源筛选、事件状态筛选、资金不随过滤重算、事件→交易/账本→精确订单跳转、身份折叠/复制。
- `frontend/src/integrations.ts`：版本化 D 展示边界 bd-results-boundary-0.1-candidate；LossResultInput/QuoteResultInput 为 unknown，缺席 pending，未审的非空输入 unsupported_contract。没有猜测的正式 wire schema 或成功结果适配器。四种 V1.1 状态为“说明，不是当前实验结果”，commercial_quote=false。
- `frontend/src/style.css`：沿用阶段 03 的配色/中文字体和金额对齐，收纳筛选及长 ID，突出关联订单；未换技术栈或扩 L2。
- 新增原生一致性/适配边界测试与阶段 04 真实 Edge 检查；`scripts/run_workbench_checks.py` 增加允许 04 新输出目录与 suite 参数，原 03 默认套件保留。故障注入只在独占 QA 会话，真实 B HTTP 产生 error；不进入业务代码/产品按钮。
- 新增 `docs/handoff/BD_to_A_C.md`、`docs/decisions/BD_display_v0.2.md`、真实 B 引用样例 `contracts/bd_handoff_example_v0.1.json`，更新 README_B、frontend/README、NEXT_STEPS、B_to_C。新增 checkpoint/交付核对脚本。

B API/Store/模型/观察者鉴权/模板/迁移均未修改；七工具、bc-0.3-candidate、EvidenceBundle 3（兼容 1/2）、observer-0.1-candidate 和迁移 001/002/003 保持。没有新 A/C 正式模块、Gold/正式任务、付费模型、真实支付、推送、上传或公网部署。

## 分阶段实际验证

每条完整命令、开始/结束时间、退出码、输出在同名 JSON + .log；汇总 `test_command_index.json`。所有命令通过 `scripts.record_check` 保存，下面列实际子命令及标签。没有删断言或把失败日志改为成功。

1. 基线：baseline_backend 65/65、baseline_frontend_tests 15/15、独立 HTTP、B/前端契约、类型/构建，全部退出 0；baseline_browser 原 Edge 套件 341 条细粒度断言 / 16 图通过。341 不是业务实验数量。
2. 复现：reproduce_native 退出 1，新增 17 个矛盾检查全部失败（17 个控制/旧测试通过）；reproduce_browser 退出 0 表示成功复现缺陷，不能当发布通过。真实服务器创建响应被延迟，合法 v2 导入随后被抢走；六种坏文件被旧版接受。原始代码修复前证据保留。
3. 入口修复：entry_native 36/36；entry_backend 65/65；entry_http/两类契约/types/build 退出 0；entry_original_browser 341 条检查 / 16 图通过；entry_browser_r2 34 条检查 / 4 图通过。然后保存 entry_04_0 检查点，才做后续集成。
4. 最终：后端 65/65、前端 41/41、6/6 独立安全探针；独立 HTTP、契约、类型、构建全部退出 0。原浏览器回归 341 条检查 / 16 图；阶段 04 最终套件 91 条检查 / 14 图。无未捕获浏览器错误。检查含运行隔离、旧历史兼容、分页排序、0 增量重放、订单跳转、加载/空列表/无匹配/502/8秒超时、创建成功但响应丢失后从目录恢复、六类坏文件拒绝、连续导入/返回/晚到目录及只读断网回放。

实际最终命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/04/final_http_evidence
.\.venv\Scripts\python.exe -m scripts.export_contracts --with-openapi --check
.\.venv\Scripts\python.exe -m scripts.export_frontend_contract --check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --output-dir artifacts/pro_bd_sprint/04/final_original_browser_evidence
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --suite stage04 --output-dir artifacts/pro_bd_sprint/04/final_integration_browser_evidence
.\.venv\Scripts\python.exe docs/audit/AgentShield_Stage03_Review_2026-10-12/observer_extra_probes.py --project . --output artifacts/pro_bd_sprint/04/observer_security_checks.json
```

对应日志：final_backend、final_http、final_contracts、final_frontend_contracts、final_native、final_types、integration_build_r2（即最终前端源码构建，之后只改测试/文档）、final_original_browser、final_integration_browser、observer_security，退出码全 0。输出目录不得重复使用，复跑请给新目录/标签。

完整 HTTP 还实际验证同 case 不同配置业务初态 hash、独立对象/状态；v1 333 分和 v2 250 分；迁移旧库、原退款与工单键、进程重启、TCP 发完不读的提交恢复。没有在真实旧库上运行写入测试。

中间两次测试脚本失败另存：entry_browser 在返回服务仍处账本区却等待订单标题，显式切到企业区后通过；integration_browser 在风险区展开状态说明、切合同区后重复点击将同一 details 收起，改为检查 open 后再展开，保留全部内容断言。没有因此改业务逻辑或删测试。既有 httpx/TestClient 弃用警告仍记录，不自行降级依赖。

## 启动与页面截图

实际检查环境：Windows、本项目 Python 3.13.1、Node 24.21.0 / npm 11.19.0、锁定 React/TypeScript/Vite 和 Edge 155.0.4283.45。检查实际启动了隔离 B + 观察者服务和 Edge，结束后停止；没有留下演示端口常驻。

```powershell
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench --seed-development
```

默认浏览器自动在 127.0.0.1:8810 换取一次性本机观察授权，B 管理凭据只留服务端，日志不打印授权串。默认 var/workbench.sqlite3 空观察租户才播种两份明确开发脚本样例。新建按钮仅建初态，不执行 Agent。详细安装和选库说明见 frontend/README.md。

最终新套件截图在 `final_integration_browser_evidence/`（14 张）；旧套件在 `final_original_browser_evidence/`（16 张），全是本机本次真实浏览器输出。重点：

- integration-first-screen-1366.png：1366×768 企业实验场首屏。
- integration-order-trace-1366.png：具体订单高亮，实际 v2 250 分退款。
- contradictory-replay-rejected.png、after-late-create.png：坏文件拒绝与晚到创建保护。
- integration-ledger-desktop.png：QA 存储故障产生的真实 error 事件，0 已提交；不是自然模型事故。
- integration-risk-pending.png、integration-cost-pending.png：A/C 缺席状态和 commercial_quote=false。
- integration-mobile-first-screen.png、integration-mobile.png：390×844 首屏及长页。
- create-response-unknown-test.png：真实创建后受控丢弃响应的未知状态提示。

人工实际查看范围和局限见 visual_review.json。已查看关键桌面/移动图；自动检查整页横向溢出和表格金额对齐。没有宣称逐像素看过全部截图。桌面首屏看见请求及消息/订单标题，商品行仍需向下读；移动首屏仍较多来源/导航说明，未做 L2 深度收纳。安全审查范围/凭据扫描证据见 security_review.json。

## 兼容、待接入与停止点

A/C 未交付正式 schema/结果，所以成功 wire 适配仍待负责人审核，本轮完成的是版本化拒绝/缺席边界和需求清单。没有假 LossResult/QuoteResult、假理赔、假风险图表或“运行成功”按钮。C 独立消费者签收、A 业务/政策/合同审定仍待本人。

当前启动器启动自己的 B/SQLite；不会自动看到 C 另一实例。现有可用交付路径为授权管理端只读导出精确 session → 脱敏文件及清单 → 本地只读回放。BD_to_A_C 给出步骤、最小字段语义、样例/版本与待审问题。没有新增万能代理或向浏览器发管理令牌。

schema 1/2/3、legacy_unavailable/null、原键恢复、历史政策保留；缺失不填零。浏览器 canonical hash 尚未复算，未签名文件不证明真实来源。页面已加载后的断网文件回放通过；断网冷启动/刷新、A 离线理算、第二台机器独立复现仍未完成。两个不可读旧库目录仍未核查。不宣称 R09/J2/L1 或全队验收通过。

## 检查点与交付核对

- before_04.zip：464 文件，SHA-256 0420087cd604dbd00148afee06bbb3be45ea386fed908629bf139861df1367ff。
- entry_04_0.zip：628 文件，SHA-256 5f3c59b498b8c723dcd70b97537ec5b9a43616bcca841ae40335c91d07917461。
- after_04.zip：最终可回退源码/证据检查点，SHA-256/文件数及逐文件验证在 checkpoints/after_04_manifest.json。排除所有环境、dist、数据库和凭据；不会嵌套本阶段自身检查点。复现仍需 README 的锁定依赖安装与构建。
- `delivery_verification/verification.json` 核对历史/审计/spec/task/B 事实文件原样、契约导出、真实交接样例和两份可读原库哈希；`final_checkpoint_verification.json` 核对 ZIP 和工作区。原审计报告、03 及本轮中间失败证据保留。

回退时先保留当前文件，在新目录展开所需 ZIP；不是自动覆盖操作。数据库一致备份仅在 var/stage04-private，不含于共享检查点；两个拒绝访问目录不能称已备份。本轮没有 Git commit，检查点不是远端提交。

完成阶段 04 后停止。模型调用 = 0，真实支付调用 = 0。
