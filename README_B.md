# AgentShield B 交易底座（阶段 02）

当前接口为 **bc-0.3-candidate，B 自测完成，A/C 审核及消费者签收待完成**。本轮只执行 BD 冲刺包 02：稳定案例/运行分离、对象映射、可比较初态和受控开发模板；阶段 01 七工具与事务保护保留；完成后停止扩展，不代表全队 L0/L1 或 J0/J1/J2 通过。

现有七工具、SQLite 退款/账本/幂等事务和管理只读导出可运行。所有 fixture 为 development_only；来源枚举兼容 scripted_test、mock_agent、observed_agent_execution。来源是创建方声明，此次仅测试标签传播，没有模型调用、真实支付或收费服务。

本轮实际记录见 [RESULTS](artifacts/pro_bd_sprint/02/RESULTS.md)，协议见 [bc-0.3](docs/decisions/BC_contract_v0.3.md)。原 bc-0.1/0.2、artifacts/b_bootstrap 和阶段 01 的结果/检查点完整保留。

## 环境与启动

已在 Windows / Python 3.13.1 / 当前 .venv 验证；依赖版本锁定于 requirements.lock。已有 .venv 可直接使用；新接收人在独立目录安装时：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip check
```

**已有库须先备份再启动。** 服务启动和 init_dev 都自动执行增量迁移 001/002/003；保留旧数据。002 增加工单；003 增加冻结案例上下文，不改写旧编号、会话来源/版本、交易、工单或事件。操作和回退限制见 [迁移说明](docs/migrations/B_003_session_cases.md)。本轮保留了阶段 01 两个遗留测试库，所有新测试均使用独占临时库。

在项目根目录的服务终端配置本地数据库和随机管理员令牌（赋值不会显示令牌）：

```powershell
$env:AGENTSHIELD_ADMIN_TOKEN = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))").Trim()
$env:AGENTSHIELD_DB = Join-Path (Get-Location) 'var\development.sqlite3'
$env:ENABLE_PAID_RUNS = 'false'
$env:MAX_COST = '0'
.\.venv\Scripts\python.exe -m scripts.init_dev --db $env:AGENTSHIELD_DB
.\.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

.env.example 仅说明变量，不自动加载。管理令牌不交给模型/浏览器/Agent。运行器 HTTP 传输层接收本会话 token，模型仅见公开 observation 和工具参数；Authorization、令牌、密钥不得写入日志/样例/仓库。会话 token 创建时返回一次，数据库只存哈希；本批没有找回或轮换端点。重启需设置同一管理员凭据才能使用相同管理客户端。

## 复跑与独立 HTTP

下面测试使用自己的隔离库，不访问 AGENTSHIELD_DB 指向的业务库。HTTP 脚本自行启动 loopback Uvicorn 和独立标准库客户端，并在结束时停止服务。无需另启服务：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.run_http_checks
.\.venv\Scripts\python.exe -m scripts.export_contracts --with-openapi --check
```

本轮完整测试 57 项通过（42 项开工基线，新增 15 项）；独立 HTTP 覆盖七工具、非法参数关联、333 分退款唯一入账、工单无资金变化、原键恢复、权限隔离、finish 后恢复、退款/工单/冻结案例上下文服务重启恢复；两个配置同案例哈希相同且状态隔离，标准库客户端仅凭 HTTP 映射重建初态。另以原始 TCP 发送完整请求，关闭连接而不读取响应，再查历史/沿用原键恢复，确认仅一笔退款/账本。这是本地故障注入，不是断电或生产网络可靠性证明。

每次 HTTP 默认输出到新建 artifacts/http_checks/run-随机值。可指定新的 --output-dir；目录已存在则拒绝，避免改写历史。用记录器保存命令、实际退出码和输出，标签也必须新建：

```powershell
.\.venv\Scripts\python.exe -m scripts.record_check --output-dir artifacts/pro_bd_sprint/02 verify_again -- python -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.record_check --output-dir artifacts/pro_bd_sprint/02 http_again -- python -m scripts.run_http_checks
```

对一个已运行且已获本地授权的服务，C 可复制 scripts/bc_smoke_test.py 到独立目录，设置与服务匹配的管理凭据后执行：

```powershell
python bc_smoke_test.py --base-url http://127.0.0.1:8000 --output-dir c_acceptance_new
```

脚本仅用 Python 标准库，不导入 sandbox、不读取数据库；创建开发会话并执行模拟业务，不能对非测试服务随意运行。它的成功不替代 C 自己的消费者签收。

## 案例与开发模板

同 fixture 重建时 case_id/source_case_id 稳定，session_id/episode_id、凭据和对象 ID 每次独立。case_context 的 object_mapping 明确列出模板 customer/order/item/message ID 到运行 ID，C 无需解析随机字符串。相同案例、模板/环境版本的不同配置先比较 business_initial_hash，再核查运行条件；这不证明独立样本或真实模型调用。

canonical_initial 保存所有公开业务初态和执行规则版本，排除 session/token/config 等运行信息；只读冻结，不随退款更新。哈希协议见 bc-0.3 文档，独立 HTTP 脚本会重建并复算。旧会话不补造映射或哈希；其原 case-session 编号和恢复结果保留。

模板仅允许仓库内源码登记的 dev-refund-v1 与 dev-refund-v2，不接受 Agent 文件路径、URL 或内联 JSON。v1 保留原金额/数量/确认/资格，v2 为一订单三商品、两消息，实付 1001 分、首商品退款 250 分。两者都为 development_only、待 A/C/D 审核，不是正式任务/Gold。v1 原政策中“工单尚未接入”的历史文案尚待修订，当前可用能力以七工具注册表为准。

## HTTP 和契约

- 管理 POST /api/v1/sessions：至少 tenant_id，可选择 fixture_id（dev-refund-v1/v2）、config_id 和 execution_source；创建响应附 case_context；仅创建响应返回 session_token。
- 会话 POST /api/v1/sessions/{session_id}/tools/{name}：get_case、get_order、get_business_policy、get_refund_history、submit_refund、submit_human_review、finish_case。
- 三个写工具必须使用 Idempotency-Key，可带 X-Call-ID。两头独立校验，合法关联信息在 422 时仍保留；无效/凭据值不进入事件。
- submit_refund 的 expected_version 是订单版本；submit_human_review 和 finish_case 的是会话版本。工单仅持久化待核实问题/公开证据，status=open，无裁决、无资金变化。
- finish_case(escalated) 不自动创建或关闭工单。需要工单时先创建再以新会话版本 finish；会话结束后仍可原键恢复，不能新写。
- 会话 GET /status、/observation；管理 GET /api/v1/admin/sessions/{session_id}/events?after_seq=0、/ledger、/evidence。
- EvidenceBundle schema=3，保留 human_reviews/ticket_id，新增 case_context_status/context；新版解析旧 schema=1/2，旧会话 context=null、legacy_unavailable，旧严格消费者需升级。
- /openapi.json 和 /docs 可供本地查看定义；不要在浏览器输入管理员令牌。鉴权失败只记独立 security_events，不污染目标会话。

权威定义为 contracts/models.py 和注册表；tools.json、schemas.json、openapi.json、implementation_status.json 由 scripts.export_contracts 生成。修改模型后先导出，再 --check；不要分别手改三套协议。请求样例在 examples.json，七工具实际响应在 response_examples.json，实际证据/事件在 evidence_example.json / tool_event_examples.json，三来源标签示例在 session_source_examples.json；案例/配对样例在 case_examples.json，第二模板证据在 fixture_v2_evidence_example.json，受控模板登记/结构在 fixture_registry.json 与 development_fixture.schema.json。原六工具样例仍在 artifacts/b_bootstrap，不能删除来“重建”。

管理导出命令（只读，不重放）：

```powershell
.\.venv\Scripts\python.exe -m scripts.export_evidence --base-url http://127.0.0.1:8000 --session-id SESSION_ID --output-dir artifacts/local_export_new
```

将 SESSION_ID 替换为实际会话 ID；凭据只取环境。导出的 JSON/JSONL 是派生证据，SQLite 是事实源。

## 边界和接续

只面向本地可信团队开发；未完成多机、吞吐、断电、密钥轮换、正式任务/Gold、真实 Agent/核验器、保险算法、前端、工单分派处理、真实支付和公网部署。锁定依赖的 Starlette/httpx 弃用警告保留；历史还有 Pydantic Header alias 警告，依赖升级时复核，不能据此声称无警告。

测试只清理自己创建的临时目录；不得删除旧库来规避迁移。需要新开发数据时停止服务后指定 var 下的新数据库，保留旧库。无 Git 仓库，本轮用文件归档和 SHA-256 保存前后检查点。BD 目前共同负责、由用户操作，分工待实际进展确定。

C 按 [交接](docs/handoff/B_to_C.md) 接续；下一位 B 开发者先读 [NEXT_STEPS](NEXT_STEPS.md)。A/C 审核保持待填；阶段 02 完成后停止，不自动进入 03 或 D。


## 阶段 03：本机观察者工作台

React/TypeScript/Vite 四区页面已接入真实 B 开发数据。启动与安全说明见 frontend/README.md；新增只读管理目录与分页适配见 docs/decisions/BD_observer_v0.1.md。不要把 AGENTSHIELD_ADMIN_TOKEN 或 session_token 填入浏览器或 VITE_* 配置。

B/C 仍为 bc-0.3-candidate，七工具、EvidenceBundle schema 3、迁移 001/002/003 不变。当前完整回归 65 项；阶段 03 结果、失败过程日志及浏览器截图在 artifacts/pro_bd_sprint/03/RESULTS.md。没有实现 A/C 正式结果，没有进入阶段 04。


## 阶段 04 接续记录（2026-10-12）

已在现有阶段 03 上先复现并修复回放一致性和异步创建/导入竞争，保存入口检查点，再完成 D 的筛选、追溯、待接入状态与交接。B/C bc-0.3、七工具、EvidenceBundle 3、observer-0.1、迁移 001/002/003 不变，本轮没有 B 交易逻辑改动。

启动仍为 `npm.cmd --prefix frontend run build` 后 `.\.venv\Scripts\python.exe -m scripts.run_workbench --seed-development`（默认 127.0.0.1:8810，服务端内存鉴权，首次空库写入明确的开发脚本模拟交易）。使用独立开发库，不将已有业务库当演示数据。详情见 frontend/README.md。

本轮实测与限制：artifacts/pro_bd_sprint/04/RESULTS.md；给 A/C 的接口需求、真实 B 身份样例、跨实例只读导出/导入流程：docs/handoff/BD_to_A_C.md。A/C 协议/业务与 C 独立消费者仍待本人审核；不自动进入 05 或正式实验。
