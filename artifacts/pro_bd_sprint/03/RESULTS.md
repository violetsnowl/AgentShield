# BD 阶段 03 — 真实数据工作台

2026-10-12，Asia/Hong_Kong；JSON 时间为 UTC。**阶段 03 完成并停止，不进入 04。** B/C 保持 bc-0.3-candidate、七工具、EvidenceBundle schema 3、迁移 001/002/003；本机观察者为 observer-0.1-candidate。A/C 审核和 C 独立消费者签收仍待本人完成。

## 核对与保护

已读当前源码、02/RESULTS、NEXT_STEPS、B_to_C、BC_contract_v0.3、V1.1 及 03_D_WORKBENCH。工作区/上级未发现适用 AGENTS.md；当前不是 Git 仓库。阶段 02 after_02_manifest 内文件与本地一致。先保存 checkpoints/before_03.zip 及 SHA-256 清单（233 文件），保留现有内容；inspection.json 记录核对。

两个阶段 01 遗留库目录仍受 Windows 权限限制，显式重查也被拒绝。**本轮未能复核现状哈希**，没有拿阶段 02 旧记录冒充当前验证；没有改 ACL、读取业务内容、迁移、清空或删除它们。所有测试使用独占临时库，旧阶段日志/审计/模板/迁移保留，新失败另存。

本机未找到 frontend-design/SKILL.md。收到用户指定仓库后，实际读取远程 [SKILL.md](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) 和同目录 [LICENSE.txt](https://github.com/anthropics/skills/blob/main/skills/frontend-design/LICENSE.txt)，确认该技能为 Apache-2.0。本轮依据其设计指南实现，未全局安装，也未把整个仓库认定为同一许可证。

## 实际修改

- frontend：React 19.3.0、TypeScript 7.0.2、Vite 8.3.4 与精确锁文件；四区单页、中文样式、键盘焦点、reduced-motion 和窄屏布局。
- 企业实验场：真实模板/会话目录、独立 session/episode、公开消息与确认、订单/商品余额、冻结初态/映射/hash/政策。创建会话只建立初态；真实 Agent 控件禁用并解释。
- 执行证据/账本：实际请求 B 事件分页、证据与账本，校验同一运行的一致性；seq 排序、call_id/事件/订单/交易/工单追溯。查询不是付款、重放不重复计钱；333/250 分为真实 HTTP 写入的模拟资金。
- 风险比较/合同成本：C 正式运行清单及 LossResult、A QuoteResult/合同/权重/证据状态均显示待接入，无虚构成绩或前端保险公式。
- workbench/app.py：受限本机观察者，一次性本机授权、短时独立 HttpOnly cookie、固定租户、Host/Origin/请求头校验。无任意代理或工具执行路由。B 凭据留在服务端，创建响应剔除并丢弃 session_token。
- B 最小适配：管理模板目录、按租户分页的会话目录、事件可选 limit；省略 limit 保持原行为。既有交易/幂等/权限/工单方法、Wire 类、模板与迁移未改写。
- B 模型生成 TS 类型与 JSON Schema；浏览器校验器预编译，不开放 unsafe-eval。schema 1/2/3、legacy_unavailable/null、历史工单未知与空数组明确区分；拒绝混合运行、重复序号/交易、凭据字段和不安全整数金额。
- 无凭据证据文件保存/导入（≤5 MiB）仅在浏览器内处理，无上传、不再执行退款。旧编号和政策保持原样。
- README_B、BC_contract_v0.3、B_to_C、NEXT_STEPS 同步；新增 frontend/README.md、BD_observer_v0.1.md 及真实 HTTP 捕获的 contracts/workbench_examples.json。

## 视觉方案与截图检查

先确定单次运行的证据阅读结构：深蓝 #18344B、纸白 #F5F7F9、正文 #243746、青绿 #087F75、待审琥珀 #966515、错误红 #B53E46；微软雅黑/苹方/思源黑体本机字体链，正文 14px、标题 18/26px、8px 间距基准。金额等宽、表格右对齐，无外部字体或图片请求。

先实现企业实验场与账本，在 core_browser_csp_fixed_evidence 生成并实际查看两张截图后，才完善其余两个待接入区。实际核对身份层级、长 ID 换行、金额对齐、333 分事件→交易→单条双边账本及重放零金额。之后查看 A/C、窄屏、错误/超时及旧证据回放截图。没有把全部生成截图一概声称为人工逐张检查；自动检查另覆盖页面溢出、ID 边界、金额对齐。

最终截图位于 **final_browser_evidence/**，共 16 张：

- core-lab-v1-desktop.png、core-ledger-v1-desktop.png：v1 事实与账本追溯。
- lab-v2-desktop.png、ledger-v2-desktop.png、lab-v2-mobile.png：真实 v2 和 390×844 窄屏。
- risk-pending-desktop.png、cost-pending-desktop.png：A/C 待接入。
- empty-run-desktop.png：实际新会话，无事件/交易。
- empty-list-test-desktop.png、loading-test-desktop.png、error-test-desktop.png、timeout-test-desktop.png：测试脚本受控网络注入，仅证明 UI 状态处理，不当作真实业务结果。
- offline-schema1/2/3-desktop.png：历史/网页实际保存证据的断网回放。
- unauthorized-desktop.png：未授权浏览器不能读取运行。

## 实际测试

下面所有结果均有同名 `.json`（完整命令、环境、时间、退出码）和 `.log`，位于本目录；Python 均用当前项目 .venv。

- 原阶段 02 基线：从 before_03.zip 解到独占临时目录，执行 `python -m unittest discover -s tests -v`，**57/57，退出 0**。记录 pristine_57_tests。
- 当前后端：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`，**65/65，退出 0**。记录 regression_65；原 57 + 新观察者 8，含七工具、幂等/权限、旧退款/工单/finish 原键迁移恢复、双模板和非法模板回滚。
- 独立 HTTP：`python -m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/03/final_http_evidence`，**退出 0**。记录 final_http；独立标准库客户端、333/250 分、同 case 配置隔离、初态复算、进程重启原键恢复、实际 TCP 不读响应关闭恢复、来源标签传播通过，模型调用 0。
- B 契约：`python -m scripts.export_contracts --with-openapi --check`，**退出 0**。记录 final_contracts。
- 前端类型/Schema 对照：`python -m scripts.export_frontend_contract --check`，**退出 0**。记录 final_frontend_contracts。
- 前端测试：`npm.cmd --prefix frontend test`，**15/15，退出 0**。记录 final_frontend_tests；覆盖真实旧/新证据、null/legacy、运行隔离、重复记录、凭据拒绝、金额精度与状态语义。
- 独立类型检查：`npm.cmd --prefix frontend run typecheck`，**退出 0**。记录 frontend_types；最终构建又执行了一次类型检查。
- 构建：`npm.cmd --prefix frontend run build`，**退出 0**。记录 final_frontend_build；含校验器生成一致性、tsc 和 Vite build。
- 完整浏览器联调：`python -m scripts.run_workbench_checks --output-dir artifacts/pro_bd_sprint/03/final_browser_evidence`，**退出 0**。记录 final_browser。真实 B/观察者/临时库 + Edge 155.0.4283.45，1440×1000 与 390×844，16 截图、零未捕获 JS 异常、零外部请求。341 条细粒度断言含逐请求重复凭据检查，不等于 341 个独立业务用例。
- 交付/保护：`python -m scripts.verify_workbench_delivery --output-dir artifacts/pro_bd_sprint/03/delivery_verification`，**退出 0**；记录 final_delivery 与 delivery_verification 下的文件。186 个历史/规范文件哈希通过，24 个原有 Store 方法及全部既有 Wire 类 AST 未变，108 个源码文件留存哈希；旧库哈希未验证，不计作通过。

浏览器实测涵盖：双模板、新建同 case 运行独立、旧账本不变、事件排序/分页、重放零金额、A/C 禁用、无确认消息、加载清除旧事实、502、实际 8 秒超时、迟到响应不覆盖新选择、未授权访问、下载后断网回放、schema 1/2 无哈希、无 JS 存储/可读 cookie、无浏览器 B Authorization 或 session_token、临时管理秘密不进入请求/响应/构建产物。

## 失败过程保留

- baseline_tests：sandbox 的 asyncio socketpair 卡住，停止本轮挂起子进程，退出 4294967295；baseline_http 启动超时，退出 1。允许 loopback 后复验，没有删断言或清旧库。
- baseline_tests_local：在只读模型已加入、导出尚未同步的开发中间态运行，55 通过、2 个正确的契约漂移失败，退出 1；不视为原始基线。另从 before_03 快照复跑 57 项通过，最终 65 项通过。
- frontend_core_build：类型生成的 patternProperties 与 CSS 声明问题，退出 1，已修正。
- frontend_core_build_retry：构建本身退出 0，但记录器控制台 GBK 打印 Unicode 失败；文件已保存。record_check 改为 UTF-8 控制台输出，后续正常。
- core_browser/core_browser_retry：运行时 Ajv 编译被 CSP 阻止，退出 1；改为预编译，不放宽 CSP。frontend_csp_build 首次调用参数错误也保留，修正后 frontend_csp_build_fixed/core_browser_csp_fixed 通过。

Starlette/httpx 弃用警告原样保留。旧审计/阶段结果及上述失败均未被成功记录覆盖。

## 启动与检查点

从根目录运行 `npm.cmd --prefix frontend ci --ignore-scripts`、`npm.cmd --prefix frontend run build`，再 `.\.venv\Scripts\python.exe -m scripts.run_workbench --seed-development`。启动器自动打开受限授权页面，默认 127.0.0.1:8810；详细说明见 frontend/README.md。本轮联调进程已停止，没有公网部署或常驻自动任务。

checkpoints/before_03.zip 与 after_03.zip 均配归档 SHA-256 和逐文件清单，checkpoint_verification.json 记录校验。回退先另存当前代码，将 before_03 解压到**新目录**核对，不强制覆盖当前目录。检查点不含 .venv、node_modules、dist、var 数据库或凭据；依赖按锁文件重建。没有新增迁移，回退也不能删除新产生的运行事实，实际用户数据库须另行一致备份。

## 限制与待审

- 没有正式 Agent、C 核验、A 报价/理算、正式任务或 Gold；没有付费模型或真实支付，不代 A/C 审定。
- **已加载网页**的 schema 1/2/3 断网只读回放通过；断网冷启动/刷新、A 离线理算、第二台机器独立复现未完成，不能声明 L1 R09 或团队 J0/J1/J2 通过。
- Windows/Edge 验证不代表其他平台、浏览器、移动真机或 Vite 热更新路径通过；规模、多机与断电恢复未验收。
- 旧遗留库现状哈希受权限限制未复核；真实旧用户库升级需独立备份和验证。
- A/C/D 审案例分组、模板/确认/原政策语义；C 独立签收并提供运行清单/LossResult；A 提供 QuoteResult/合同/权重/证据状态；BD 接续者按 frontend/README.md 独立复现。两个结果协议只预留显示位置，未擅自冻结字段。

**到此停止，不自动执行阶段 04。**
