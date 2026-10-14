# C 对 bc-0.3-candidate 的接收记录

对应 `docs/handoff/BD_to_C_CHECKLIST.md`。本记录只覆盖 C 在本机实际执行的检查；A/D 的业务语义审定不在此列。

## 环境

- 接收人：C（本人机器，Cursor 编码助手执行命令）；日期：2026-10-13。
- 机器：Windows 10.0.26200；Python 3.13.2（`C:\path\to\python.exe` 新建 `.venv`）。B/D 的验证环境是 3.13.1，补丁版本不同。
- 依赖：`pip install -r requirements.lock` 成功（官方源，无 TLS 错误），`pip check` 无冲突。fastapi 0.136.0 / pydantic 2.13.3 / starlette 1.7.0 / uvicorn 0.45.0 / httpx 0.28.1。
- 代码基线：BD 阶段 05 精简包 + A0 patch 0.1（按 `docs/business/A0_patch/A0_PATCH_MANIFEST.json` 逐文件 SHA-256 核对后合并）。A 副本中其余 225 个文件与主目录逐字节一致，备份于 `<external-local-backup.zip>`（SHA-256 `03E7149C976B028CF3E43BACDFECB7F233A8481F647A407F40A5A61D13643FCC`）后删除。

## 已执行命令与结果

| 命令 | 退出码 | 结果 | 记录 |
|---|---|---|---|
| `python -m unittest discover -s tests -q` | 0 | 88 项通过（B/D 65 + A 23） | `artifacts/c_l0/checks/backend_unittest.json` |
| `python -m scripts.export_contracts --with-openapi --check` | 0 | Contract artifacts match source models | `artifacts/c_l0/checks/contracts_check.json` |
| `python -m scripts.export_frontend_contract --check` | 0 | Frontend wire types match B models | `artifacts/c_l0/checks/frontend_contract_check.json` |
| `python -m scripts.run_http_checks --output-dir artifacts/c_l0/receive-http` | 0 | 见下 | `artifacts/c_l0/checks/receive_http_checks.json` |

A 在 Python 3.11 / 非锁定依赖下报告的 `Contract drift: openapi.json`，在锁定依赖下不复现，判断为依赖版本差异，不是接口改动。

`run_http_checks` 自启隔离 B，并在 `-I` 隔离 Python 子进程中运行标准库 `bc_smoke_test.py`（cwd 为临时目录，不导入 sandbox）。实际观察：

- 七工具可用；单笔 333 分退款，一笔交易对应一条账本；工单 1 张、金额 0；会话版本 4。
- 非法参数仍保留关联头；跨会话访问、Agent 凭据调用管理导出均被拒绝。
- 丢弃响应后查历史并同键恢复；进程重启后原键返回原交易与原工单；TCP 发完即断开、不读响应后，历史可见 committed 且同键恢复不重复扣款。
- 两模板 v1/v2：同 case 两配置初态哈希一致、状态隔离，标准库按映射重建初态并复算哈希；v2 首退 250 分。
- 三种 execution_source 标签传播；model_calls=0，不证明真实执行。

## C 自有消费者（runners/sandbox_client.py）

C 的运行器 HTTP 客户端独立实现（标准库，不导入 sandbox/api）。J1 批次 `artifacts/c_l0/runs/j1-mock-20261013-201356/` 实测：

- [x] 同 case 两次创建身份可关联、对象/余额独立（4 个会话各自 session/episode，账本互不混合）。
- [x] 写工具使用运行器生成的 `Idempotency-Key` 与 `X-Call-ID`；超量退款被 B 拒绝且金额 0；失败不占成功键（改正后用新键成功）。
- [x] 响应丢失（工程注入）后先 `get_refund_history(order_id, 原键)`，再以相同键与原参数恢复；B 事件为 succeeded → replayed，只有 1 笔退款和 1 条账本，重放金额 0。
- [x] attempted 记录：派发前写 `dispatch`，本地拒绝（未知工具/坏 JSON/多余字段）写 `local_rejection` 且未发出，B 侧无对应事件；每个已派发调用都能用 X-Call-ID 对上 B 事件。
- [x] 按 refunds/ledger 的 transaction_id 计提交金额，不累加响应金额；工单与 finish 不计钱。

详情见 `docs/handoff/C_L0_RESULTS.md`。

## 协议意见（不阻断，供 B 登记）

1. `contracts/tools.json` 的 `submit_refund` 参数使用 `$defs/$ref`。C 适配器在发送给模型前内联展开，不修改 B 契约。
2. 工具定义中 `expected_version` 的含义（退款=订单版本；工单/结束=会话版本）只在文档里，描述字段未写明。C 在系统提示词中说明；建议 B 后续在 description 中补充。
3. `HistoryRequest.idempotency_key` 是传输层键，模型不应自行构造。C 的白名单校验会剥离模型提供的该字段，由运行器在恢复流程中自行使用。

## 接受范围

接受 bc-0.3-candidate 作为 C 的 L0 开发接口：七工具、幂等/恢复语义、EvidenceBundle schema 3 和 case_context 映射。保留意见如上。不代表 A/D 业务签收或全队 J0/J1/J2。
