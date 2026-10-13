# B/C 契约 0.1 候选

状态：候选、待 A/C/D 按职责复核；未冻结，未通过 J0。依据 V1.1 主规范与 B 首批任务。

## 开发约定

- 权威字段来源 `contracts/models.py`：注册表生成 JSON Schema、当前工具定义及真实 HTTP 路由，OpenAPI 由实际路由导出。六工具 implemented，`submit_human_review` planned，无路由、无伪成功。
- 管理端 `POST /api/v1/sessions` 创建独立快照，返回随机会话令牌一次。管理员 Bearer 令牌来自环境，不设默认密码。数据库只保存会话令牌 SHA-256。运行器传输层持有令牌，不传给模型。
- 工具路径 `POST /api/v1/sessions/{session_id}/tools/{tool_name}`；同前缀 GET `/status`、`/observation`。管理 GET `/api/v1/admin/sessions/{session_id}/{events|ledger|evidence}`。没有 evaluate/quotes/experiments 接口。
- 运行器提供 `X-Call-ID`（省略时记录 request_id），写操作必须有 `Idempotency-Key`。键作用域为 session 内所有写工具，保留至数据库归档。同工具同规范化 JSON 参数返回原结果；不同工具或参数 409 IDEMPOTENCY_CONFLICT。call_id 不参与指纹，失败不占用键。
- 身份/对象归属检查先于成功键恢复；成功键恢复先于可变版本/结束状态检查。新键旧版本 409 STALE_STATE。订单版本每次退款加一，会话版本每次退款/finish 加一，查询与重试不变。refund 使用订单版本，finish 使用会话版本。
- finish 后禁止新退款及新 finish；同键原结果恢复和查询仍可用。outcome 是调用者声明，不是核验结论；escalated 不代表已建人工工单。
- ID 为字符串，金额 CNY 整数分，数量严格正整数（拒 bool/string/float），拒绝重复商品行/额外字段。支付渠道只取订单原渠道，不接受模型指定。
- 开发分摊：按行 gross_cents 比例分摊订单实付，向下取整，再按余数降序、item_id 升序补分。行内累计退 q 件金额为 floor(line_paid*q/original_qty)，本次取前后累计差，最后一件收尾差。算法版本 `largest-remainder-prefix-v1-development`，待 A 审定。
- 结构化确认是同一订单商品的累计授权上限；核对已退+本次不超过引用消息上限，历史确认不相加。本批无撤销消息；更正/撤销规则待 A/D 提供，不宣称支持。
- ToolEvent seq 会话内递增，提交、恢复和失败都有记录。`client_receipt=unknown`：提交/响应发送不证明客户收到。replayed 的 committed_amount_cents=0，不重复计资金增量。来源字段独立记录。
- EvidenceBundle 由一致读事务导出初始/终态、订单分摊、退款、双向等价账本、事件、规则和来源。不含 Gold/损失/赔款/正确答案。JSONL 是可恢复导出，SQLite 是事实源。
- 错误统一 code/message/retryable/request_id：422 字段/协议校验；401 未认证；403 身份或对象越权；404 无路由/不存在的管理对象；409 幂等/版本/数量/资格/结束冲突；500 内部失败；503 数据库忙。错误不包含 SQL、堆栈、凭据或原非法输入。

## 待审人与边界

1. A：分摊算法、确认累计范围、资格快照、原路退款、开发 fixture 公开事实。当前无 A/D 签字；不算正式 12 个 L0 或 24+4 任务。
2. C：call_id/幂等作用域、响应丢失恢复、ToolEvent 时序、EvidenceBundle 初始/增量及独立义务映射；消费者独立 HTTP 接入待验收。
3. D：版本与 after_seq 轮询、结束声明、拒绝/未知显示、干净环境复跑。
4. B 下一位：收齐反馈后修改并冻结 contracts，接入已审 fixture 时新增版本，不改旧会话。

LossResult 属于 C，沿用主规范 §5.2/§9 的 oracle_version、义务、实际/合法增量、额外支出、追回、净损失、业务与核验状态、证据和未知部分；未知为 null。B 不生成 LossResult 或复制其算法。

QuoteResult 属于 A，沿用 §5.2/§10 的合同/数据/配置、样本/权重、适用范围、证据状态、B0/B1/B2、commercial_quote=false，B2 未启用为 not_fitted。B 不提供假报价；待 C/A 提供权威模型再接管理包装层。
