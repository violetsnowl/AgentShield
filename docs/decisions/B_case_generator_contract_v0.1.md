# B 案例生成器契约 v0.1（候选）

状态：B-CP1/CP2 工程实现通过，A/C/D 业务审核待完成。上位 B/C wire 仍为 bc-0.3-candidate，EvidenceBundle 仍为 schema 3。

本候选只引入两项加法式兼容：

1. fixture_id 的源码固定 allowlist 增加 B-CP2 公开开发候选。
2. development fixture 文件 schema 增加 v2 期初历史退款字段。

schema v2 的 `initial_refunded_quantity`、`initial_refunded_cents` 和 `initial_refund_source=pre_session_business_history` 只定义 session 创建前的业务初态。期初历史退款减少商户余额和订单剩余额、增加客户期初余额，并占用累计可退数量。它不创建本 episode 的 Refund、LedgerEntry 或 ToolEvent，不进入 C 对本次 Agent committed facts 的归因。

受控登记由 `contracts/fixture_ids.py` 与 `sandbox/fixtures/generated/registry.json` 双重固定，加载时校验路径、身份、字节哈希和业务不变量。HTTP 不提供注册、上传、URL、路径或内联 fixture 输入。

原 `dev-refund-v1/v2` 文件保持 schema v1 和原业务哈希；名称中的 v1/v2 不表示 fixture schema 版本。数据库无新增迁移，旧会话、旧证据和历史退款事实不改写。

A1 公共候选补丁当前不可见。本契约只提供对接字段和补充候选，不冻结 A1 Gold、正式任务或留出。
