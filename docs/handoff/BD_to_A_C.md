# ABCD 本地集成后的 A/C 交接（2026-10-13）

当前已完成候选链的本机接入：C 的 LossResult 和运行清单、A0 Claim 与 QuoteResult schema/工程样例均已合入；D 通过 `abcd-results-boundary-0.2-candidate` 读取固定服务端目录并追溯到精确 B case/session/episode。C 对 bc-0.3 L0 开发接口的签收见 `C_receipt_bc-0.3.md`。本轮没有修改 B 交易语义，也没有由 D 运行 Agent 或保险计算。

给 C 的下一步：交付正式 Gold 输入后的冻结运行清单，完成 C1-1、至少 10 次成本预试、56 次正式 Agent 和 28 次规则基线；三个历史真实模型开发运行需人工审核，当前继续 `needs_review/null`。给 A 的下一步：审定正式任务义务和研究合同，冻结 Claim/Quote 语义并完成正式赔付与定价。A/C/BD 还需共同决定规范 JSON 哈希与 CRLF 交付原始字节哈希的正式口径。

完整当前结论、接口矩阵和测试存档于制作方工作区（`artifacts/integration_abcd/`，未随仓库分发）。下方阶段 05 文字作为集成前历史交接保留；其中“无成功适配器”已不再是当前事实。

---

# 阶段05接收入口（原04交接正文保留）

2026-10-12：05仅做复验与收口；当前状态见 `BD_CURRENT_STATE.md`，A/C本人接收分别见 `BD_to_A_CHECKLIST.md`、`BD_to_C_CHECKLIST.md`，安装/回放见 `docs/setup/RECEIVE_AND_RUN.md`。候选接口与交易逻辑未变，无成功A/C适配器。下方“完成04后停止”是历史记录；当前完成05后停止，不自动扩功能。所有A/C/第二人签收仍pending。

---

# BD → A/C：阶段 04 交接候选

2026-10-12。用户与舍友联合负责 BD，目前由用户统一推进；本文件不重新分工，也不代表 A/C 已审核或签收。B/C 为 bc-0.3-candidate，EvidenceBundle 3（兼容 1/2），observer-0.1-candidate，迁移 001/002/003。没有新工具、B 交易改动或迁移 004。

## 实际完成与已测

工作台读取 B 的真实开发会话、事件和模拟交易；按具体 session/episode 展示，case 只作筛选关联。已加载运行可按 case/session/episode/config 和来源筛选，事件按四种真实状态筛选；分页范围明确，不把当前页当全集。筛选不会合并运行或改变退款合计。事件可跳到交易、账本及本次订单。完整身份可展开和复制，复制内容没有凭据。

F03-01/F03-02 已先复现再修复，入口检查点为 artifacts/pro_bd_sprint/04/checkpoints/entry_04_0.zip。回放核对已记录事实的内部一致性；错误文件保留前一个合法显示并给出拒绝提示。退款小计、账本对应、守恒、逐笔/初末余额、订单商品增量与归属等不一致不能正常展示。未复制退款决策、损失或赔款算法。

初态 SHA-256 在浏览器中仍为“文件声明值，未复核”；不是签名、来源认证或语义审核。旧 schema 缺失的映射、哈希、工单与成功事件资料保持未知。服务端 / 文件内容即使内部自洽也不证明真实模型执行。v1 原政策文字和历史事实保持原样。

异步创建、文件读取、目录/证据读取、返回本机与运行切换受交互序号保护；迟到完成不覆盖新选择。已创建的服务端会话不会被删除来撤销 UI；超时/响应丢失后先核对目录。详情见 04/ENTRY_RESULTS.md 与 04/RESULTS.md。

## 两个 B 实例不会自动共享结果

当前 `scripts.run_workbench` 自行启动随机 loopback 端口的 B 和 8810 观察者，默认数据库 var/workbench.sqlite3，租户 workbench-development，管理员令牌只在启动器内存。它**不会读取 C 的另一个 SQLite，也没有现成的 --base-url 附接选项**。不得让浏览器直接拿 C/B 管理令牌，不能新增无认证万能代理来联通。

本轮可用交付路径是 **C 从自己获授权的 B 只读导出 → 核对身份/脱敏 → 本机选择文件回放**。不会导入 B 数据库、不会产生新运行/退款，也不会自动变成正式 C 评测结果。

1. C 在本人受控终端配置获授权的 B 地址与环境中的 AGENTSHIELD_ADMIN_TOKEN（不用命令行参数、浏览器、日志或仓库承载令牌）。选择管理目录中的精确 session，并核对 tenant/episode/config；不要仅按 case 找“唯一运行”。
2. 使用已有 `python -m scripts.export_evidence --base-url <已授权的本机 B 地址> --session-id <实际 session_id> --output-dir <全新目录>`。调用前确认输出目录不存在；该旧脚本会写 evidence.json/events.jsonl，不要指向历史输出。导出是管理 HTTP 只读，不执行工具。
3. 交付 evidence.json 及其 SHA-256、来源实例的非敏感说明、session/episode/config 清单、执行来源的证明和接口版本。禁止提供创建响应中的 session_token、管理员令牌、模型 API 密钥、Gold 或私有模型推理。
4. BD 在已加载工作台“导入回放”选择 evidence.json。页面内离线回放支持 schema 1/2/3；不上传。读取成功不等于 A/C 语义签收。冷启动离线/刷新离线、A 离线理算、第二台电脑复现均未满足，不能据此宣布 R09/J2。

将来如采用同一 B 实例实时集成，必须先共同确认受控服务端身份、固定观察租户、实例地址、授权会话清单与生命周期，再单独实现/验证受限适配。当前不共享内存管理员令牌、不改绑定为 0.0.0.0、不通过不同库的偶然同名 case 合并数据。

## 待 C 审核的最小语义需求（不是冻结字段定义）

- 版本化 LossResult schema 和真实样例；明确 oracle_version、业务/核验状态、未知/待审部分，整数分与 null 的含义。
- 精确 case/session/episode/config/experiment 及环境/模板/政策版本；运行清单需含来源证明、预算、失败与缺配对；case 重复不得当独立样本。
- 每项义务的对象引用、实际增量、合法应付、额外支出、对应追回、观察时点净损失及证据引用。未知不填 0，不能从 B 的退款额推断损失。
- 可追到 B 的 event_id/seq/call_id/transaction_id/order_id 与证据文件版本；attempted、本地拒绝/超时和客户端收到与 B 的提交事实分开。
- 没有 context 的历史运行如何引用义务；不允许猜映射/伪造 hash。哪些状态允许呈现部分值，哪些必须停止显示，由 C/A 审定。

## 待 A 审核的最小语义需求（不是冻结字段定义）

- 版本化 QuoteResult schema 和真实/明确标识的工程样例，合同/数据/计算版本、来源与适用范围。
- 对应 C 结果与运行清单、合同/公式依据、配置、类别样本数、业务量/权重、支持范围、样本描述值与情景估计值及未知部分。
- B0/B1/B2、not_fitted/insufficient_evidence/partial/out_of_scope 的准确状态字段位置与状态组合；commercial_quote 必须 false。零观测不能声称零风险。
- 修改合同的服务端/离线入口与错误模型；重算只生成新结果版本，不改变历史轨迹、退款或模型运行计数。前端不实现理算公式。

## 已实现的 D 适配边界

`frontend/src/integrations.ts` 为 bd-results-boundary-0.1-candidate：LossResultInput/QuoteResultInput 保持 unknown；没有 A/C 已审定版本时 null/缺席返回 pending，任意非空内容返回 unsupported_contract，result=null、commercial_quote=false。不接受猜测字段或“看起来像结果”的 JSON。没有假接口、假成绩、权威计算或运行成功按钮。

界面可展开 V1.1 四类状态的文字/色彩说明，明确不是当前实验结果。后续应在负责人交付 schema、语义和样例后逐版本加入适配器及成功/失败回归，未知版本必须拒绝；不能将 unknown 直接断言为已接入类型。

`contracts/bd_handoff_example_v0.1.json` 是本轮真实开发 HTTP 证据的身份/文件引用及缺席状态，**不是 LossResult/QuoteResult wire 样例**。现成 B HTTP 样例仍见 contracts/workbench_examples.json，stage 03 原样保留。

## 待签收

A：业务/政策/v1 旧文案、保险语义及 QuoteResult。C：bc-0.3 独立消费者、真实运行器/尝试记录/独立核验、LossResult。BD 下一位：按 frontend/README 启动、复验、安全边界和截图核对；再与本人分别记录接收人/环境/日期/命令/结果/问题。当前都 pending，不代签全队 J0/J1/J2/L1。

本轮完成 04 后停止，不自动执行 05、L2 美化、正式实验或发布。
