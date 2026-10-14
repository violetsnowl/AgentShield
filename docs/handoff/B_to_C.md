# B → C 接入交接（bc-0.3 候选，待接收）

> 状态提示（2026-10-14）：本文写于阶段 02–04；当前状态以 `NEXT_STEPS.md` 为准。

当前已完成 BD 阶段 04 集成（下文阶段 02/03 记录保留其历史语境）。B/C 仍为 bc-0.3-candidate，七工具、EvidenceBundle schema 3 与迁移 001/002/003 不变；新增 observer-0.1-candidate 本机观察者，不能替代 C 运行器。阶段 02 的案例与模板说明保留如下。最新验证见 artifacts/pro_bd_sprint/04/RESULTS.md，阶段 02 历史证据见 artifacts/pro_bd_sprint/02/RESULTS.md。C 独立消费者和 A 业务签收仍待本人完成，没有代签全队关口或真实模型运行。

## 接入和版本

按 `docs/modules/B_sandbox_backend.md` 在 loopback 启动；旧数据库先备份再运行迁移 003。管理侧创建会话并保管管理员令牌，运行器传输层只接对应 session_token，模型只看公开 observation 和工具参数。令牌不进模型消息、浏览器、日志或仓库。

七个 POST 工具共用 /api/v1/sessions/{session_id}/tools/{name}：

- get_case / get_business_policy：参数 {}。
- get_order：order_id；get_refund_history：order_id，可带 idempotency_key。
- submit_refund：order_id、items、confirmation_message_id、expected_version（订单版本）、reason。
- submit_human_review：category、missing_facts、evidence_message_ids、expected_version（会话版本）。
- finish_case：outcome、explanation、expected_version（会话版本）。

权威模型 contracts/models.py，导出 tools/schemas/openapi/implementation_status；额外参数拒绝。新会话初始版本 1，退款推进订单和会话，工单与 finish 仅推进会话。公开示例展示退款 1→2、工单 2→3、finish 3→4。

EvidenceBundle schema_version=3 保留 human_reviews/ticket_id，增加 case_context_status/case_context。新版兼容旧 schema=1/2，原 snapshot 的 contract/source 不改写；旧严格解析器需要同步更新。不要将新导出外层版本当成旧会话已重新执行。

## 阶段 02 的案例、映射与可比初态

管理建会话可选 dev-refund-v1 或 dev-refund-v2；新 case_id/source_case_id 稳定，session_id/episode_id 及所有运行对象各自独立。创建响应的 case_context 与 evidence.case_context 相同并持久化。模型无需管理凭据；C 管理/核验部分保存此公开工程上下文时必须剔除 session_token。

context.object_mapping 的 customers/orders/items/messages 是“模板 ID → 运行 ID”。按稳定 case_id 和 fixture/policy/environment 版本选择候选义务，再映射订单/商品/证据引用；不能猜随机 ID 后缀，也不能跨会话复用。case_id 不再唯一代表运行，事件和尝试仍需 session_id/episode_id/call_id 定位。

canonical_initial 以模板对象 ID 记录请求/消息/确认、所有订单商品事实、规则、余额、业务时间和环境版本；运行 tenant_id 规范为 template-tenant（当前仅单租户/客户拓扑），排除 session/token/experiment/config/source 等运行标签。business_initial_hash 按排序键、无多余空白、Unicode UTF-8、禁止非有限数的 JSON 做 SHA-256，数组/原文顺序不归一。详细排除项见 bc-0.3。

两个配置同 case 的 canonical/hash 应一致，但还需 C 核对预算与扰动。哈希不证明业务语义正确、样本独立或模型真实执行。parent_case_id=null、family_id=dev-refund-engineering 只是待审分组，两个模板不增加正式独立样本数。

旧会话没有可靠稳定映射：schema=3 导出为 legacy_unavailable/null，原 case-session ID、退款/工单和事件保留，不伪造来源或哈希。原退款、工单、finish 键继续返回原结果。C 必须显式处理旧证据，不能默默把它们与新稳定 case 合并。

v1 保留原业务事实（含旧政策文案，工单实际可用）；v2 是一订单三商品、两消息，其中一条无确认，1001 分分摊 500/300/201，杯子每件 250 分、包装袋不符合资格。模板没有 Gold。确认更正/撤销和授权范围、v1 旧文案修订由 A/D 审核，不在 B 中自行设定正式答案。

## 工单与结束会话

工单 category 为非空文本，missing_facts 为 1–30 个待核实问题，evidence_message_ids 为当前 case/customer 的 0–30 个不重复公开消息 ID；缺证据可为空。身份、归属、版本和幂等均检查。返回唯一 ticket_id、status=open、时间、会话/案例、原键/call_id、会话版本前后和来源。

事务原子保存工单、会话版本、成功键和事件；失败全部回滚。没有自动退款、Gold、正确答案、损失或赔款判断。工单事件 transaction_id=null、committed_amount_cents=0；管理 evidence.human_reviews 可读全部工单。没有领取/裁决/关闭端点。

需要转人工时先建工单，再使用新会话版本 finish(escalated)。finish 自身仍是调用者声明，允许无工单 escalated，不自动创建/关闭工单，不是最终任务核验结论。finish 后不能新写，但可读取和恢复原键。

## 幂等与不确定响应

三个写工具共享会话内 Idempotency-Key 空间。运行器生成专用安全键及 X-Call-ID，按会话串行执行多工具调用。同键同规范化参数返回原结果和原 transaction_id/ticket_id/call_id/时间；同键改参或换工具为 IDEMPOTENCY_CONFLICT。JSON 对象键顺序不影响指纹，数组顺序影响。认证和对象归属先检查，成功键恢复先于过期版本和会话结束检查。

退款超时先查 get_refund_history(order_id, idempotency_key)，已 committed 则使用事实或原键原参数恢复。not_found 只说明该次查询没有看到提交，不能换键盲退。工单/finish 超时用原键原参数恢复；退款历史不查工单。新键旧版本为 STALE_STATE，结束后新键为 SESSION_FINISHED。500/503 不意味着客户端能断言是否提交，仍按同键协议查证。

两个关联头分别只接受单个 1–128 字符 [A-Za-z0-9_.:-] 值；拒绝凭据/可疑前缀/重复/非法头。即使业务参数 422，有效关联字段保留，无效字段独立置 null，失败不占成功键。客户端应记录错误 request_id，不把异常输出拼成下一次业务参数。

## C attempted 与 B 事实

C 负责在 HTTP 派发前留下模型尝试、原始工具名及安全参数、本地未知工具/拒绝、是否发出、超时和实际响应。未发送的工具不应期待 B 有事件。实际派发时用 X-Call-ID 和键关联本地 attempt；运输重试保留业务键，单次 HTTP request_id 可变化。不得把未执行的尝试记成执行成功。

B 负责实际抵达且认证归属正确的请求、错误和原子提交事实。未知工具/非法 JSON 是 rejected，不执行；错误处理不是万能执行路由。认证失败只进 security_events，不污染受害会话。存储故障时 B 也可能无法持久化失败事件，C 本地记录不能依赖 B 补齐。

ToolEvent.status 区分 succeeded/rejected/replayed/error；来源标签不是执行结果。读取成功也为 succeeded，不能因此算退款。client_receipt 始终 unknown，B 无法证明模型收到响应。新增退款成功事件才有 committed_amount_cents 增量，重放为 0；按 refunds/ledger 的 transaction_id 去重，禁止累加所有响应金额。

三种 execution_source 由管理方声明：scripted_test、mock_agent、observed_agent_execution。此次三者均只做受控传播测试（model_calls=0）。C 后续负责真实 provider/model/request_id/usage 证据，不能从 observed 标签杜撰真实运行。C attempted 记录器/核验器不在此次 B 实现中。

## 核验事实与接收

管理 evidence 是一致读快照，提供初始/最终 snapshot、退款、账本、事件、工单、冻结开发规则和来源。它不是 Gold，不含正确性结论。开发订单实付 1500 分：甲三件共 1000 分、乙两件 500 分；甲依次 333/333/334 分。首笔退款后商户 1367、客户 333，一笔交易对应一条包含双方增量的账本。工单金额为 0。

1. 在 C 自己的目录/环境复制 scripts/bc_smoke_test.py，对已授权的本地开发服务运行标准库脚本并保留命令/退出码/证据。B 本次独立 -I 子进程测试不是 C 签收。
2. 检查七工具、新 schema、严格参数/权限/版本、单笔 333 分退款、一个工单、原键恢复和 finish 关系。反馈协议分歧，不私改服务掩盖不兼容。
3. C 后续实现并验证 attempted/本地拒绝/超时与 B 事实的关联；A 审证据、确认范围及金额规则。真实模型或正式任务需另行安排，本轮无此授权。
4. 接收人、环境、日期、命令、结果、问题分别写入 NEXT_STEPS 的待填记录；未经本人确认不冻结候选。

本次 57 项完整回归通过；独立标准库 HTTP 在两个配置下比较同 case、根据返回映射重建初态并复算哈希，验证 v2 的 250 分退款/工单。本次实际验证还包括关闭 TCP 连接且不读取响应后的查询/原键恢复，以及退款和工单跨服务进程重启恢复。Windows 本机通过，不代表断电、多机或公网可靠性。迁移和回退见 docs/migrations/B_003_session_cases.md；新事件库不应直接交给旧版严格模型读取。

本轮结束于 02；阶段 01 的七工具/幂等/权限/工单继续有效。03/D 前端、正式 Agent/损失核验器、保险计算、工单分派裁决、真实支付与部署均未开展。


## 阶段 03 的最小读取适配与交接

- B 管理侧新增 fixtures 与按 tenant_id 分页的 sessions 目录；events 增加可选 limit，省略仍保持原契约。七个工具、既有模型字段、交易方法和历史迁移没有改写。详见 docs/decisions/BD_observer_v0.1.md 与 contracts/workbench_examples.json。
- D 经受限本机观察者读取具体 session 的证据/事件/账本；管理员和 B session_token 均留在服务端。独立观察授权 cookie 只有固定开发租户的读取和创建初态权限，不能操作工具。C 仍使用原独立 HTTP 接入方式，不使用这个观察者执行正式 Agent。
- UI 保留 succeeded/rejected/replayed/error；查询成功、工单与结束声明不计付款；重放金额为零。观察者访问不创建工具事件。C 的 attempted、本地拒绝/异常/超时及响应接收仍由 C 记录。
- case 不是运行缓存键；会话/episode 的账本分开。同 case 新运行初态 hash 一致但交易为空。旧 schema 1/2/3 的 legacy_unavailable/null 明示，历史编号和政策不变。
- 当前后端完整回归 65 项、前端数据测试 15 项；独立 HTTP、契约、构建/类型检查、真实浏览器联调通过。已保存 schema 1/2/3 的断网只读回放实测通过，但冷启动离线页面和 A 离线理算没有实现，不代表 R09 通过。
- 风险比较及合同/情景成本只留待接入界面；LossResult/QuoteResult 的具体字段仍需 C/A 提供并审核。没有创建正式任务、Gold、模型成绩、商业报价或赔款。

给 C：先在本人环境签收 bc-0.3 的工具与证据，再提供正式运行清单和 LossResult；保持 session/episode 身份和来源证明，不用开发脚本替代真实执行。给 A：审 v1 历史政策和模板语义，再交付合同/权重/证据状态与 QuoteResult。给 BD 接续者：按 frontend/README.md 启动，核对本机授权、租户范围、兼容分支和 stage 03 检查点，先完成独立复现与待审事项。阶段 03 完成即停止，不自动进入 04。


## 阶段 04 接续

B 七工具/契约/鉴权/交易/迁移没有变更。D 修复事实一致性与异步竞争，新增精确运行筛选、事件到交易/账本/订单跳转及只接受已审协议的 A/C 适配边界。未审协议尚无成功适配器，不承认任意 JSON 为 LossResult/QuoteResult；页面明确 pending 和 commercial_quote=false。

重要：run_workbench 自启动独立 B，不会自动看到 C 另一实例的运行。本轮可用的交付方式是 C 管理侧只读导出特定 session 的 EvidenceBundle，脱敏后由 BD 本地回放；不把不同库/运行合并，不分享管理员凭据到浏览器。具体命令、最小语义清单、未知分支与独立签收记录见 docs/handoff/BD_to_A_C.md。前端初态哈希只显示文件声明未复核；来源真实性与业务语义仍由各负责人审核。

最新实际结果见 04/RESULTS.md；阶段 04 完成后停止，A/C 与 C 独立消费者签收待本人完成。
