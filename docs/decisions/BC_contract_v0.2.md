# B/C 接口候选 bc-0.2-candidate

2026-10-12，阶段 01。B 自测完成；A/C 尚未签收或冻结。只处理 F03、F01、F05、F04；F02、多 fixture、阶段 02 和 D 不在本轮。`BC_contract_v0.1.md` 与 `artifacts/b_bootstrap/` 保留为历史记录。

## 来源与版本

`CreateSession.execution_source`、会话快照、公开 case、ToolEvent、工单和 EvidenceBundle 的来源统一支持 `scripted_test`、`mock_agent`、`observed_agent_execution`，默认仍为 `scripted_test`。来源由管理创建方声明，不能验证确实发生过模型调用。此次测试模型调用数为 0；C 后续提供实际 provider/model/request_id/usage 证据，不得从标签反推真实执行。

新会话使用 `bc-0.2-candidate`。不改写旧会话冻结的 contract/source 信息。新导出 EvidenceBundle 使用 schema_version=2，增加 `human_reviews`；ToolEvent 增加可空 `ticket_id`。新版解析器仍接受 schema_version=1、缺少上述新增字段的旧证据（默认空列表/null）；旧版严格解析器需升级，不能声称向旧消费者无条件兼容。新导出外层契约版本描述导出格式，内部旧快照仍保留当时版本。

## 调用关联和失败

X-Call-ID 与 Idempotency-Key 各自独立验证：仅允许单个头、1–128 个 ASCII 字母/数字/下划线/点/冒号/连字符。拒绝重复头、超长或非法字符、包含当前管理员/会话凭据、数据库中已登记的会话凭据，以及 bearer/sk/api-key/token 等可疑前缀。此规则不是任意外部密钥识别器；运行器必须生成专用关联 ID，禁止放入凭据。

已认证请求即使业务参数不合法（例如 quantity=0），有效的关联字段仍保存在 rejected ToolEvent；每个无效字段置 null，不能连带丢弃另一个有效字段。非法请求维持 422、无交易/资金变化，不占用成功幂等键。修正参数后可用该键执行。失败时没有合法 X-Call-ID 则为 null；成功请求未提供 X-Call-ID 则用服务端 request_id 补齐。幂等指纹基于脱敏前的已校验参数，不允许不同文本因脱敏而错误匹配。审计参数会脱敏；非法 NaN/Infinity 转为占位字符串，避免错误处理再次崩溃。

## 最小人工审核工单

已实现 `POST /api/v1/sessions/{session_id}/tools/submit_human_review`，必须使用本会话令牌和 Idempotency-Key。参数：

- `category`：1–2000 字符的问题类别说明。
- `missing_facts`：1–30 个非空待核实字段/问题，每项最长 2000 字符。
- `evidence_message_ids`：0–30 个当前 case/customer 的公开消息 ID，必须存在且不重复；无公开证据可传空列表。
- `expected_version`：当前 **会话版本**，不是订单版本。额外字段被拒绝。

返回持久化工单：ticket_id、session_id、case_id、上述问题/证据、status=open、created_at、idempotency_key、call_id、session_version_before/after 和 sources。工单不含裁决、正确答案、Gold、损失或赔款；不改变订单、退款或账本，只把会话版本加 1。工单、会话版本、成功键与成功事件在同一 SQLite 事务提交；事件失败则全部回滚。成功/重放事件以 ticket_id 关联，transaction_id=null、committed_amount_cents=0。

退款、工单、finish 共享每会话幂等键空间。同键同参数返回原工单（原 ID/时间/call_id）；同键不同参数/工具为 IDEMPOTENCY_CONFLICT。认证和对象归属始终先检查，成功键恢复先于过期版本/会话结束检查。新键旧会话版本为 STALE_STATE；不同新键允许表达不同工单，本轮不做语义去重。

`finish_case(outcome=escalated)` 仍只是调用者声明：不会自动创建或关闭工单，也不强制已有工单。需要工单时先提交工单、取得新会话版本，再 finish。finish 后拒绝新写，仍允许读取和原键恢复。没有分派、处理结论、关闭工单或队列端点；管理员通过 evidence.human_reviews 只读查看。工单响应不确定时用原键原参数重试；get_refund_history 仅查询退款。

## B/C 留痕边界

C 在派发前记录模型工具尝试（attempted），包括模型给出的未知工具、不合法参数、本地拒绝、未发出的请求、传输超时以及实际收到的响应。C 自己保留本地 attempt ID、工具名称和安全参数，并关联派发的 X-Call-ID / Idempotency-Key；超时是接收状态不确定，不能记成退款未发生。此客户端记录器由 C 后续实现，本轮未代写或代签。

B 只记录实际抵达 B 且可安全归属的 HTTP 请求和数据库提交事实。认证成功后，已知工具参数错误、非法 JSON、未知工具/不支持的方法可写 rejected 事件；未知工具不会执行，raw_arguments=null。错误观察处理不增加万能执行路由，注册表只含七个已实现工具。认证失败只写独立 security_events，不污染目标会话，也不记录明文令牌。

`status=succeeded` 表示该工具成功执行（读取工具成功也属于此状态），`replayed` 表示返回已有结果，`rejected` 表示未成功执行，`error` 表示执行错误；绝不可把 attempted 或 execution_source 当成功标志。存储本身故障时不能保证持久化失败事件，C 应保留自己的尝试记录。所有服务端事件的 client_receipt=unknown，B 不能证明客户端/模型收到响应。

资金事实以 refunds/ledger 中的 transaction_id 去重计算；只有新退款成功事件有 committed_amount_cents 增量，工单、失败和重放均为 0。超时先查历史、再沿用原键原参数恢复。not_found 仅代表该次读取尚未发现提交，不能证明请求永远不会提交。工单或 finish 超时直接沿用原键原参数恢复。

## 持久化迁移与待审项

001 原样保留；002 新增 human_reviews、schema_migrations 并登记 1/2，重复初始化不重写业务记录。旧 schema_version 表因旧 CHECK 约束继续记录基线 1，完整迁移版本看 schema_migrations；它与 EvidenceBundle 的导出 schema_version 各有含义。迁移/备份/回退操作见 `docs/migrations/B_002_human_reviews.md`。

待 C 审：来源声明与真实调用证据的分离、尝试与提交的关联、严格 schema=2 消费、工单/finish 的恢复语义和缺证据空列表。待 A 审：问题/证据语义以及旧退款分摊和确认范围。BD 后续按实际完成情况分工；展示和队列本轮未开发。未经本人反馈不签收、不冻结接口，不改变规范中的 not_verified/not_checked 关口。
