# B/D → A 接收业务审查（v0.1 候选，**未签收**）

- 证据：`sandbox/store.py`、`sandbox/fixture.py`、`sandbox/fixtures/dev-refund-v1.json` / `dev-refund-v2.json`、`docs/decisions/BC_contract_v0.3.md`、`docs/handoff/BD_to_A_CHECKLIST.md`。
- 审查方法：源码与开发模板静态核对；个别数值用单独手算/单元测试。**未声明 A/D 已双签，未实机验证 B 全功能**。
- 审核人：A 待实名确认；D 复核人：待确认；审核日期：待实际填写；签收状态：pending。

| 项目 | 已核对事实或风险 | 初步意见 | 签收 |
|---|---|---|---|
| 金额分摊 | `sandbox/store.py::_refund` 使用 `allocated_paid_cents*cumulative//quantity - refunded_cents`，v1 甲1000分/3件，累计退款333/666/1000分，增量333/333/334分；v2 杯子500分/2件=250/250分，杯垫300分/3件=100/100/100分。商品分摊由 B fixture 校验，尾差落于最后数量。 | 作为**实现事实**接受用于开发；正式业务合理性和多次历史退款归属仍需 A/D 复核。 | pending |
| 余额/权限 | B 检查当前租户、订单与确认对象、可退数量、资格及累计已退，金额由服务端计算；有原渠道、版本/事务、幂等。 | 不因需要正损失就撤掉任何既有保护；D/B 再跑必要故障手算与本地集成验证。 | pending |
| v1 文案 | `dev-policy-v1` 写“本批人工工单工具尚未接入”，但现行七个公开工具包含 `submit_human_review`。 | 不回写 v1 历史、建议用新模板及 `policy_version` 正式纠正。 | pending |
| v1 业务语义 | request 泛指“按商品与数量办理”，`message-all` 为三件甲、两件乙的累计确认，另有 `message-one` 仅确认甲一件。候选订单二 `eligible=false`。 | 现有确认**不是独立的本次申请数量 Gold**，也未说明两确认间撤销/更正优先级，唯一合法应退增量不能仅凭现有文本锁定。需补明确请求、授权时间及优先级。 | needs_review |
| v2 业务语义 | request 说“申请部分商品退款”；`message-confirm` 给杯子最多2件、杯垫最多2件；包装袋资格不满足，提问消息无确认。 | “最多2件”不等于“本次各应退2件”。具体应退商品和数量需补明确申请，包装袋应转人工核实；不能把800分上限当金钱损失基准。 | needs_review |
| 工单/完成 | `submit_human_review` 留存 `open` 工单且不出账；`finish_case` 仅公开结束状态；成功工具调用不等于业务义务全部完成。 | 把 `open` 和 `escalated` 分成流程结果；未知义务与潜在损失不填零。 | pending |
| case 和来源 | 两模板都是 `development_only`，同 `family_id=dev-refund-engineering`；stable case_id、独立 session/episode、对象映射和初态哈希均已设计。 | 不视作两道正式独立任务；正式拆分按 parent/near-variant group 保持隔离，不能把重复运行当独立 case。 | pending |
| 金额核验边界 | B 的 `refunds/ledger` 只证明实际已提交资金及状态；不能单独判定正确业务义务 `E_j`，缺追回或合法义务不能计算唯一净损失。 | C 实现独立 oracle，A 负责保险责任和理算；任意 B 退款额 ≠ 自动经济损失。 | pending |
| 保险责任 | V1.1 第10节：非故意执行错误相关、已核验额外净资金损失；事件免赔、赔付比例、单次限额；现实攻击/罚款等除外。 | A0 只实现候选研究合同，不授权商业定价、投保或支付。 | pending |
| 证据与联调 | 前端已有候选接入口，但无已审定 QuoteResult/LossResult；Agent 运行尚未完成。 | 交付候选 schema/样例后请 BD 独立验证，不改 `frontend/src/integrations.ts`。 | pending |

## A/D 需优先确认的 5 个决定

1. 客户初始申请必须新增哪些**公开字段或话术**才能独立确定 `E_j`？明确整单/部分和本次要求的数量。
2. 多次确认、后续更正和撤销的**时间优先级**：现有 v1 两条确认是否互相替代？记录可追溯的业务时点。
3. 退款义务是按订单×商品行、还是增加更细的请求维度？如何追溯同一义务的多笔退款及追回？
4. 人工工单在 `open`、已核实、已执行资金动作三种状态如何区分？在当前系统未实现人工裁决前不可替它完成赔付。
5. 研究观察终点 H 与追回确认规则是什么？不应将 H 时点未追回称为永久不可追回。

## 给 C 的输入约束

请按每个义务 j 交付合法应付增量、独立已提交增量、逐义务多退额、匹配的追回及证据引用。`LossResult` 必须区分 `verified`/`needs_review`，保留精确 `experiment/case/session/episode/config` 与业务环境版本。旧证据缺 Gold/对象映射时报告 `legacy_unavailable`，不反推。A 的纯函数不会读取 B 的 transaction 列表直接判损失。
