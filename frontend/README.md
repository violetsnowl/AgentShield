# ABCD 本地集成工作台（2026-10-13）

当前工作区已把已交付的 A0/C L0 候选结果接入原 B/D 工作台：B 仍使用 **bc-0.3-candidate**、七个公开工具和 EvidenceBundle schema 3；D 通过受控观察者读取固定目录 `artifacts/c_l0/runs`，展示 C `LossResult`、A0 `ClaimCalculationResult`、关联的 B session/episode，以及单独标明为工程示例的 A `QuoteResult`。浏览器不能提供文件路径，不能调用 Agent、核验器或保险公式，也拿不到 B 管理员令牌。（2026-10-16 演示重构版说明：界面为极简三页；规范豁免、退役项与测试映射见 `docs/decisions/UI_DEMO_REDESIGN_2026-10-16.md`，当前界面描述以 `docs/manuals/FRONTEND_USER_MANUAL.md` 为准。）

从项目根目录构建并使用独立预览库启动：

```powershell
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench `
  --db var/abcd-preview.sqlite3 `
  --port 8810 `
  --seed-development
```

启动器会自动打开带一次性本机观察授权的 `http://127.0.0.1:8810`。风险区可选择已交付的 Mock 或历史 `observed_agent_execution` 开发运行，并用“加载关联业务证据”追溯到精确的 B case/session/episode。`needs_review` 的净损失与赔付保持 `null`，不会补造结论；“重新理算”保持禁用（前端不执行保险公式），“启动 Agent”按钮已随 2026-10-16 演示重构删除（端点未接通，注记移入页脚「开发工具」）。所有当前结果均为 `counts_as_formal_run=false`，不代表 Gold、正式 L1 或商业报价。

本次集成实测：后端 115 项、前端 42 项、核心浏览器 419 条检查、异常/回放浏览器 101 条检查均通过；完整记录未随仓库分发（存档于制作方工作区）。下方阶段 03—05 内容保留为历史说明；其中“A/C 待接入”描述的是当时停止点。

---

# 阶段05接收说明

本轮只收口复验，前端仍是下述阶段04实现，未新增界面功能。最新启动/独立安装/精简包范围见 `docs/setup/RECEIVE_AND_RUN.md`；测试见 `artifacts/pro_bd_sprint/05/RESULTS.md`。新目录同机验证使用独立 npm 安装，Python全新安装因TLS失败后复用原锁定环境；不是第二机或队友签收。05 QA输出可使用全新 `artifacts/pro_bd_sprint/05/...` 目录。

下方为原阶段04使用说明，保留其版本与历史上下文。其中“没有执行05”描述当时，不代表当前停止点。A/C成功适配、真实Agent、保险计算与第二机仍待完成。

---

# AgentShield 阶段 04 工作台

React + TypeScript + Vite 单页四区工作台。B 接口仍为 **bc-0.3-candidate**，EvidenceBundle 为 schema 3，并显式读取历史 schema 1/2。观察者适配为 **observer-0.1-candidate**，不是新的公开工具协议。阶段 04 在保留 01—03 的基础上完成入口修复和集成，停止于 04；没有执行 05。

## 从项目根目录启动

本轮验证环境：Windows 11，项目 `.venv` 的 Python 3.13.1，Node 24.21.0，npm 11.19.0，Edge 155.0.4283.45。Python 依赖沿用根目录 requirements.lock；前端精确依赖及传递依赖由 package-lock.json 固定。

```powershell
npm.cmd --prefix frontend ci --ignore-scripts
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench --seed-development
```

打开 `http://127.0.0.1:8810` 的本机浏览器。启动器会自动打开一次带临时观察授权的页面，不打印授权串。手动输入裸地址的未授权浏览器只会看到授权提示。关闭终端或按 Ctrl+C 停止两项服务；仅关闭网页不会停止服务。

启动器在内存生成 B 管理凭据，启动随机 loopback 端口的 B，再启动固定 8810 端口的观察者。默认数据库为 `var/workbench.sqlite3`，固定观察租户为 `workbench-development`。不使用环境中的 AGENTSHIELD_DB，不改历史库。`--db`、`--port`、`--tenant` 由本机操作者显式指定；已有业务库应先按 B 迁移文档一致备份，不要直接用作演示库。

`--seed-development` 仅在观察租户没有任何会话时，经真实 B HTTP 写入两个开发脚本样例：v1 一笔 333 分退款、v2 一笔 250 分退款，各一条双边账本、一张待审工单，以及读取、拒绝与原键重放事件。它不会调用模型或真实支付。已有会话时不再次播种，避免重启生成重复示例。页面上的“创建开发会话”只建立新初态，事件/交易/账本为空；不会执行这些样例脚本。

浏览器的临时观察授权在 120 秒内仅可交换一次，随后使用最长一小时的独立 HttpOnly/SameSite=Strict 观察者 cookie。**它不是 B 管理员令牌或 B session_token**，也没有工具执行权限。B 凭据不返回浏览器。授权过期需停止并重新运行启动器；`--no-open` 不打开授权页面，因此不给普通浏览器数据访问权。

## 四个区域

- 企业实验场：实际注册模板、具体 session/episode、公开消息、结构化确认、订单和商品余额；冻结初态、版本、哈希、显式对象映射及原始政策。
- 执行证据/账本：实际事件分页、快照和账本。按 session 内 seq 阅读；事件详情含 request/call/幂等键及原始事实。退款可关联交易、账本、订单与事件。查询、工单、结束声明不是付款；原键重放新增资金为零。
- 风险/配置比较：C 正式运行器、运行清单与 LossResult 待接入；启动 Agent 与损失依据按钮禁用。
- 合同/情景成本：A QuoteResult、合同版本、权重和证据状态待接入；重新理算禁用，无前端保险公式和虚构报价。

同 case 的不同 session/episode 从不合并金额或状态。模板选择框只用于创建新会话，不改变当前会话的模板。来源标签照证据展示，scripted_test/observed_agent_execution 等标签本身不证明真实模型执行。

v1 政策历史原文保留；其中“本批人工工单工具尚未接入”与当前七工具实现的差异在展开政策时标明待 A/C/D 审核。旧 case 编号只按原记录展示，不冒充稳定案例标识；legacy_unavailable/null 不生成映射或哈希。

## 回放与断网边界

“保存证据回放”下载当前快照的无凭据 JSON；“导入回放”仅在浏览器内读取文件，最大 5 MiB，不上传。按从 B 模型生成的 JSON Schema 校验，再检查 schema 版本、运行身份、事件序号、重复交易、凭据字段、金额精度，以及退款行小计/账本/余额/订单商品增量的内部一致性。发现矛盾则拒绝新文件并保留先前合法视图。内部一致不等于来源真实或业务合法。schema 1/2 缺失的上下文、工单集合保持未知，不补默认事实。

导入后醒目标为本地只读文件，不能创建会话或调用工具；文件未签名，不代表本机最新状态。金额只做整数分展示、事实恒等式校对及已提交退款求和，不计算风险或保险理算。canonical/hash 在浏览器中仅显示“文件声明值，未复核”，不作来源签名。缺失成功提交事件时明示追溯未验证，不补造历史记录。

**已实测：**页面已经加载时，将浏览器网络设为 offline，导入保存的 schema 3 和历史 schema 1/2 文件，四区导航和证据阅读无网络请求。

**未满足：**断网冷启动/离线刷新整个网页（没有 Service Worker 或独立离线安装包）、A 离线理算、第二台机器独立复现。因此不宣布 L1 R09 或团队关口通过。

## 开发与检查

推荐用上述构建后同源服务进行验收。Vite 热更新入口保留，可先运行 `npm.cmd --prefix frontend run dev`，再运行启动器并加 `--dev-origin http://127.0.0.1:5173`。Vite 仅监听 127.0.0.1，固定代理到 8810；不要配置 VITE_* 管理令牌。热更新路径本轮未单独做浏览器验收，正式记录对应构建后的同源页面。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.run_http_checks
.\.venv\Scripts\python.exe -m scripts.export_contracts --with-openapi --check
.\.venv\Scripts\python.exe -m scripts.export_frontend_contract --check
npm.cmd --prefix frontend run check-contract
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
$bdCheckStamp = Get-Date -Format yyyyMMdd-HHmmss
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --output-dir "artifacts/pro_bd_sprint/04/browser-$bdCheckStamp"
```

浏览器检查使用锁定的 playwright-core 和本机 Edge（不自动下载浏览器）。检查启动真实 B 与观察者，使用独占临时库和干净浏览器上下文，结束后关闭服务。未安装 Edge 的环境需自行提供受支持的浏览器适配，本轮不声称跨平台通过。部分 Windows 沙箱会阻断 Python asyncio 的 socketpair，需在允许本机 loopback 的终端运行；不能通过删断言、清旧库或放宽安全设置解决。

B 模型变更后的生成顺序：`python -m scripts.export_contracts --with-openapi`，`python -m scripts.export_frontend_contract`，`npm.cmd --prefix frontend run generate-validator`，再运行上述检查。校验器在构建前预编译，浏览器 CSP 不允许 unsafe-eval。

## 安全与交接

观察者只有本机启动器授权、固定租户的读取，以及两种受控开发模板的新建入口。无任意路径转发、工具代理、上传、登录服务、云服务或收费组件。Host/Origin/自定义请求头/Sec-Fetch-Site 检查、无 CORS 放行、短时授权、HttpOnly cookie、无缓存/无 referrer/禁止嵌框/CSP 同时启用。cookie 的 Secure=false 仅因这是严格 127.0.0.1 HTTP 开发服务；不得据此部署到局域网或公网。

接口变更、HTTP 对照与限制见 `docs/decisions/BD_observer_v0.1.md`；本轮命令、退出码、日志及截图见 `artifacts/pro_bd_sprint/04/RESULTS.md`；阶段 03 原证据保留。A/C 与 C 独立消费者仍需本人签收。视觉指导来自已实际读取的 Anthropic frontend-design；本机未安装该技能，来源与许可证核对记录在阶段结果中。

## 阶段 04 增量与接续

筛选只针对已加载运行/事件，明确显示分页范围。case 不合并 session/episode；筛选不改变资金合计。长身份可展开/复制；交易追溯可跳到本次会话的精确订单。来源标签照事实显示，真实 Agent 按钮仍禁用。

创建与导入可以交错操作，统一交互序号保证较新的选择获胜。已创建的服务端会话仍保留；返回本机后读取目录可找到它。连续文件读取逆序、晚到目录与旧会话读取也不能抢走新选择。创建超时不证明服务端未执行，先核对运行清单，不盲目重复创建。

A/C 的 LossResult/QuoteResult 尚未交付正式 schema。本轮只实现 `bd-results-boundary-0.1-candidate`：unknown 输入，空值 pending；非空但未审版本 unsupported_contract，result=null。界面的 not_fitted/insufficient_evidence/partial/out_of_scope 是明确标注的状态说明，不是实验结果。保留 commercial_quote=false，无前端权威公式。

`run_workbench` 自行启动独立 B，不会自动读取 C 另一个数据库。当前交付路径是 C 从自己获授权的 B 用已有只读 HTTP 导出精确 session，再在本页本地导入回放。完整最小字段需求、授权边界与步骤见 `docs/handoff/BD_to_A_C.md`；不要将管理员令牌放到浏览器或增加通用代理。

新增阶段 04 检查（输出目录必须全新）：

```powershell
$bdCheckStamp = Get-Date -Format yyyyMMdd-HHmmss
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --suite stage04 --output-dir "artifacts/pro_bd_sprint/04/integration-$bdCheckStamp"
```

默认无 `--suite` 时仍跑原阶段 03 浏览器回归（同样可输出到 04 新目录）。stage04 套件延迟真实创建响应、导入合法回放、检验畸形文件、逆序 File.text、目录竞争、筛选/跳转/待接入状态。`fault-injection-evidence.json` 来自单独测试会话中受控存储故障下的真实 B HTTP error 事件，仅 QA；它不是自然模型事故。测试恢复故障钩子、关闭服务并删除自身独占临时库，不碰既有库。

当前本机检查点不含 `.venv`、node_modules、dist、凭据和数据库。可读旧库的一致备份仅留在 var/stage04-private，未进入交付压缩包；两个权限受限历史目录仍未核查。第二台环境复现、断网冷启动/刷新和 A 离线理算仍待接入，不能宣称整个团队 L1 或 R09 已通过。
