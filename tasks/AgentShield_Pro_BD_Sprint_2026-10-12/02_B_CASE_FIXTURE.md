# Astra Codex 本轮任务 02：B 稳定案例与多 fixture

继续在原 `agentshield` 仓库工作。先检查上一阶段报告和测试；如果 01 的金额、权限、幂等或迁移测试失败，先停止新功能并修复。不要推倒重写。参考审计报告 F02、V1.1 第 5、8、11 节、现有 fixture/Store/会话/EvidenceBundle 实现。

需要让 C 的真实评测能区分：**一个稳定的业务案例 case**、这个案例的**独立 session/episode**、会话中**映射后的订单/商品/消息 ID**，以及用来判断业务初态可比性的**业务哈希**。

必须实现：
1. 受控 fixture 注册/加载，首批仅允许仓库内已登记的开发样例；不能接受 Agent 任意文件路径或不受控外部 JSON。保留 `dev-refund-v1` 的既有行为。补至少一个真实结构不同的 `dev-refund-v2` 工程模板；只标 development fixture，不冒充正式独立样本或 Gold。
2. 稳定 `case_id`/`source_case_id`，与每次新建的 `session_id`/`episode_id` 分离；`parent_case_id`/`family_id`/policy/fixture/environment 版本字段如含义待 A 审定，明确候选语义，不能随意宣称独立任务。为 C 提供从稳定模板对象 ID 到 session 内对象 ID 的显式映射。
3. 业务初态的 canonical snapshot/hash：排除 session、token、模型运行等非业务标识，但必须保留所有影响行为结果的业务事实。两次相同案例重建得相同业务哈希，不同会话状态互相隔离；不同案例应有不同身份。
4. 将当前写死的订单布局、公开消息结构解耦。固定开发模板的金额/数量、对象唯一性、资格、分摊与尾差一致性在创建前检查；无效 fixture 不形成部分会话，旧库和既有账本可继续读取。
5. 预留 A/D 对确认更正、撤销和授权范围的业务审核点。不要在没有业务标准时自己创造正式 Gold 或替换普通控制。

验收至少包含：同 case 建两次独立 session；跨两个候选配置可比较初态；旧模板正常退款与幂等回归；不同模板装载；非法 fixture 无副作用；跨会话无法读取/修改；EvidenceBundle 的映射足以让 C 在**不导入 B 内部数据库代码**的情况下关联 Gold 义务。运行实际 HTTP 与全部回归；检查导出契约一致性。

**停止点**：在 `artifacts/pro_bd_sprint/02/RESULTS.md` 留测试/迁移/契约版本与审计证据，并更新 B_to_C 与 NEXT_STEPS。B 提供候选，不代替 A/C/D 真正审核或声称全队 J2 完成。不要自动扩正式 24+4 任务，不开始 D，等待下一条。
