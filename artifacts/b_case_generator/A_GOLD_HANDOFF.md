# 给 A 的 Gold 审核交接

B 只交付业务事实和待审任务。A 负责审定合法处理、正确金额、拒绝/升级条件、损失义务与保险语义；另一位成员仍需独立核对。

## A 接收内容

- `CASE_MANIFEST.json`：case/family/parent、生成器版本、seed、fixture/hash、类别和候选划分。
- `sandbox/fixtures/generated/*.json`：客户请求、订单、商品、购买数量、分摊实付、资格、消息、结构化确认、期初历史退款和公开规则。
- `contracts/development_fixture.schema.json`：fixture schema v1/v2。
- `GENERATOR_SPEC.md`：可复现算法、历史退款边界和注册规则。

A 应逐案例确认：

1. whole/partial 与 low/high 分类是否符合冻结规格。
2. 资格、结构化确认、更正和人工审核条件。
3. schema v2 历史退款的累计数量、金额、期初余额及剩余可退范围。
4. 相似订单和冲突消息是否有唯一合法处理；无唯一答案时保留 pending_business_review。
5. family/parent 与 estimate/holdout 候选隔离。
6. 正式正确退款金额、允许操作集合、必须拒绝/升级条件。
7. Gold、义务 spec、观察时点、追回和保险覆盖语义不得回写 Agent 可读 fixture。

## A1 对接状态

用户说明 A 已交付 28 个正式候选和 12 个工程候选，但当前 BD 分支没有 A1 公共补丁、公开 manifest 或可见数据结构。B-CP2 的数量、四类分类、case/family/parent、初态哈希和待审状态与 V1.1 公开要求对齐，但这是独立补充候选。

需要 A/D 提供可公开的 A1 manifest/schema 映射，至少包含公开 case identity、category、family、split、fixture/rules version 和审核状态；不要提供私有 Gold 答案或正式留出内容。完成映射前不得宣称 B-CP2 替代或冻结 A1。
