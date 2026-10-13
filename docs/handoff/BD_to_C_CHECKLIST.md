# BD → C 接收清单（待 C 本人签收）

版本 bc-0.3-candidate / EvidenceBundle 3（兼容1/2）/ 迁移001/002/003。这是工程候选，不能把 B 自测或来源标签当 C 消费者验收、真实 Agent 或独立损失核验。

## 接收文件

- `README_RECEIVE.md`、`docs/handoff/BD_CURRENT_STATE.md`、`B_to_C.md`、`BD_to_A_C.md`；实际边界以当前文档及源码为准，旧阶段结果保留历史语境。
- `docs/decisions/BC_contract_v0.3.md`、`BD_observer_v0.1.md`、`contracts/models.py`、`openapi.json`、`schemas.json`、`tools.json`、`examples.json`、`response_examples.json`、`session_source_examples.json`。
- `contracts/case_examples.json`、`fixture_registry.json`、`development_fixture.schema.json`、`evidence_example.json`、`fixture_v2_evidence_example.json`；两份 `sandbox/fixtures/` 开发模板；schema1/2最小旧样例随包保留。
- `scripts/bc_smoke_test.py`（纯标准库独立客户端）、`run_http_checks.py`、`export_evidence.py`；`docs/migrations/` 及迁移 SQL。先在隔离库验收，旧库需一致备份，不清库掩盖迁移。

## 路由、身份和公开信息

- 管理凭据：POST `/api/v1/sessions` 建会话；GET `/api/v1/admin/fixtures`；GET `/api/v1/admin/sessions?tenant_id=<固定租户>&limit=…&offset=…`；GET `/api/v1/admin/sessions/{sid}/evidence|events|ledger`。events 用 after_seq/limit 分页；具体字段和边界以 OpenAPI 为准。
- 会话凭据：GET `/api/v1/sessions/{sid}/status|observation`；七个 POST `/api/v1/sessions/{sid}/tools/{name}`：get_case、get_order、get_business_policy、get_refund_history、submit_refund、submit_human_review、finish_case。额外参数/非法整数/跨会话访问应拒绝。
- 管理员与 session_token 只用于受控终端/运行器传输层，不给模型、浏览器、日志或交接包。模型只看公开 observation/messages、结构化确认和工具输入/输出；公开消息不是 Gold。
- case_id 是稳定业务案例。每次运行按 session_id/episode_id 连同 tenant/config/experiment 精确识别；金额/状态/账本不跨运行合并。template→runtime 映射在 case_context.object_mapping，不猜 ID 后缀；canonical_initial 与业务初态 hash 用于比较，不代表业务审核/来源认证。
- schema1/2 的 legacy_unavailable/null 保持未知，不补新映射或哈希。新导出外层 schema 3 不代表旧轨迹重新执行。v1 旧政策文案保留并待审。

## 必须验证的恢复与记录边界

- [ ] 同 case 两次创建身份可关联但对象/状态/余额独立；两模板、整数分、非法模板无部分数据。
- [ ] 三写工具的成功幂等键共享会话空间；同键同参数返回原结果，即使旧 expected_version/会话已结束；同键换参数或工具冲突。退款用订单版本，工单/finish 用会话版本。
- [ ] 422 非法业务参数保留有效 X-Call-ID/Idempotency-Key，无效头独立置 null；失败不占成功键。401/跨会话错误不能污染别人的 ToolEvent。
- [ ] 超时、500/503、TCP断开不证明未提交。记录本地 unknown；退款先 get_refund_history（带原键），再用**相同业务键与原参数**恢复；工单/finish 同键重放恢复。不得盲换新键重扣或把未知当失败。跨进程重启和旧退款/工单原键迁移均要验。
- [ ] C 在派发前记录 attempt、原工具名、安全参数、是否发出、本地拒绝/未知工具/超时及实际接收。X-Call-ID 关联 B；单次 request_id 与业务幂等键含义不同。未发出的尝试可能没有 B 事件；存储失败也可能无失败事件，C 自己留记录。
- [ ] B 的 succeeded/rejected/replayed/error 是抵达服务后的事实；查询成功不是付款，client_receipt=unknown。按 refunds/ledger.transaction_id 识别提交；新退款成功才增加 committed_amount_cents，重放为0，不能累加响应金额。工单/finish不是退款。

## C 本人执行与交付

先按 README_RECEIVE 安装和执行独立 HTTP 检查。该命令自动创建隔离 B，当前预期为333/250分开发退款、各一次提交/账本、持久工单、同键/重启/TCP恢复；并非真实 Agent。

```powershell
$cStamp = Get-Date -Format yyyyMMdd-HHmmss
.\.venv\Scripts\python.exe -m scripts.run_http_checks --output-dir "artifacts/pro_bd_sprint/05/c-receive-$cStamp"
```

进一步在 C 自己目录用纯标准库消费者对**已授权的隔离开发 B**运行（此 smoke 会创建开发会话和模拟交易，不要指向历史生产库）：

```powershell
# AGENTSHIELD_ADMIN_TOKEN 由本机获授权的安全机制提供；不在命令参数中粘贴。
# $cBaseUrl 为已核对的本机 B 地址；输出目录必须全新。
.\.venv\Scripts\python.exe -I scripts/bc_smoke_test.py --base-url $cBaseUrl --output-dir "artifacts/pro_bd_sprint/05/c-client-$cStamp"
```

当前 run_workbench 创建自己的 B，不会自动读 C 的另一库。跨实例采用以下**只读导出**，不要扩通用代理：

```powershell
$cExport = "artifacts/pro_bd_sprint/05/c-export-$cStamp"
if (Test-Path -LiteralPath $cExport) { throw '请使用全新输出目录，避免覆盖历史证据' }
.\.venv\Scripts\python.exe -m scripts.export_evidence --base-url $cBaseUrl --session-id $cSessionId --output-dir $cExport
if ($LASTEXITCODE -ne 0) { throw '导出失败' }
Get-FileHash -LiteralPath "$cExport/evidence.json" -Algorithm SHA256
```

$cSessionId 必须先从授权目录精确选择并核对 tenant/episode/config，不能只凭 case。提交 evidence.json/events.jsonl、文件 SHA-256、来源实例的非敏感说明、契约/schema/政策/模板版本、完整运行身份与来源证明；剔除凭据、私有推理和 Gold。BD 本地导入不改 B，不等于 A/C 语义审定。不同实例同名 case 不合并。

C 后续提供版本化 LossResult schema、合法/非法/缺失样例、运行/义务/证据引用、oracle_version、损失及追回时点、未知/null和状态组合；真实 provider/model/request_id/usage 与尝试记录需独立证据。不能用 B 退款总额替代损失，observed_agent_execution 标签本身不是证明。D 目前没有成功适配器，需负责人交付后另行实现/测试；未知版本继续拒绝。

回执：接收人/日期/机器/依赖/ZIP hash/命令/退出码/日志/协议分歧/接受范围均**待本人填写**。本轮未代 C 跑正式模型，也未替 C 签收。
