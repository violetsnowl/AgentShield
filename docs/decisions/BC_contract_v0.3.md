# B/C 接口候选 bc-0.3-candidate

2026-10-12，阶段 02（F02），待 A/C/D 审核。bc-0.2 的七工具、鉴权、幂等、人工工单和留痕边界继续适用。本文件仅补充案例/模板/运行分离，不代表全队关口通过，没有开始 D。

## 身份与运行

新会话的 session.case_id、公开 Case.case_id、ToolEvent.case_id、人工工单.case_id 使用注册表稳定编号：dev-refund-v1 对应 dev-case-refund-v1；dev-refund-v2 对应 dev-case-refund-v2。同一模板跨配置/重复运行仍是同一个 case；session_id/episode_id、令牌及运行对象每次独立。case_id 不再是会话主键，事件按 session_id+seq 定位。

管理创建响应新增 case_context；管理 EvidenceBundle 在 schema_version=3 中返回同一冻结内容及 case_context_status。CaseContext 含 case_id/source_case_id/parent_case_id/family_id、fixture_id/version/content_sha256、policy_version、environment_version、review_status、object_mapping、canonical_initial、business_initial_hash/hash_algorithm。

当前 case_id=source_case_id，后者表示仓库开发模板的来源编号，不是外部正式任务授权编号。两个模板 parent_case_id=null、family_id=dev-refund-engineering，是待审开发分组，不证明统计独立，不增加正式任务/Gold 数量。fixture_version 为模板修订号；policy_version 为公开规则版本；environment_version=sandbox-rules-v1-development 表示当前资格、累计确认、退款分摊、版本及工单执行规则。规则改变时须审查这些版本；contract_version 只描述传输协议。

## 显式对象映射

object_mapping 的 customers/orders/items/messages 都是 **稳定模板 ID → 当前会话运行 ID**。模板内对象 ID 全局唯一；运行 ID 每次新建。禁止解析随机字符串猜模板身份、禁止跨会话复用对象 ID。

C 从管理创建响应保存 context，或从管理 evidence 获取；七工具本身不增加权限。核验时按 case_id、模板/策略版本选择自己的候选业务标准，再把标准中的 order/item/message 模板 ID 经映射关联退款、账本、确认消息和工单。本轮只验证公开工程事实的关联，不读取/生成 Gold。

case_context 无 token；原有创建响应的 session_token 仍是凭据，不能保存到样例或日志。同 case、同租户也不互相授权；会话认证和对象归属逐项检查，幂等键依旧按 session_id 隔离。

## 规范业务初态与哈希

canonical_initial 的 business-initial-v1 格式保留：

- 原请求、候选订单顺序、公开消息顺序/原文/结构化确认及证据状态；所有引用用模板 ID。
- 订单/商品数量、gross 权重、资格、分摊金额、可退/已退数量与金额、实付/余额、状态、初始版本、币种、模拟渠道及分摊版本。
- policy 全文和版本、商户/客户初始余额、business_time、environment_version。

排除 session/episode/token、experiment/config/execution_source、创建/导出时间、case/parent/family/fixture 修订等身份元数据。客户使用模板 ID；当前模板只有一个授权租户/客户，运行 tenant_id 规范为 template-tenant，保留所有订单属于同一租户/客户的授权关系。此规范不能直接套用未经设计的多客户/多租户业务。

业务哈希采用 sha256-canonical-json-v1：将 canonical_initial 的对象键排序、ensure_ascii=false、separators=(",", ":")、allow_nan=false，以 UTF-8 编码后计算 SHA-256。金额/数量只有整数；数组保留顺序；文本不做 Unicode NFC 或空白归一。这不是 RFC 8785 实现。fixture_content_sha256 计算原文件字节，空白变化也影响它，不等于业务哈希。

固定开发哈希见 contracts/fixture_registry.json；它们不是业务正确性标签。业务初态只在创建时冻结，不随退款/工单改变。不同配置可比较初态；哈希相同不证明预算/扰动相同、真实模型运行或统计独立。对象 ID 和文本不做语义归一，换名/改写导致哈希变化也不能据此宣称独立样本。

独立标准库 HTTP 脚本从 initial_snapshot 和显式映射还原完整初态，并自行 SHA-256 复核；不导入 B 数据库代码。配对至少核对稳定 case、模板/环境版本及初态，再由 C 核查运行配置和扰动条件。

## 受控开发模板

只允许 sandbox/fixture.py 源代码注册表登记的仓库 JSON。CreateSession.fixture_id 枚举同步，不接受文件路径、URL、内联模板、任意 case_id 或在线登记。路径 resolve 后必须仍在 fixtures 目录，单文件最大 512 KB；拒绝重复 JSON 属性、NaN/Infinity、未知字段。文件内 fixture/source case/version 必须匹配登记。

创建前检查严格整数分/正数量、布尔资格、对象唯一性、候选集合、客户和确认对象归属、确认数量上限、初始余额守恒。声明的商品分摊必须逐行符合最大余数法；并列按稳定模板 item_id 排序，不能只检查总和。验证后 session/context 同事务落盘；非法模板或 context 插入错误不留部分会话/成功键/交易/工单/事件。INVALID_FIXTURE 返回安全 422，不含文件路径或内容。

v1 保留原两订单（两商品/一商品）、三消息、1500+200 分及甲商品 333/333/334 分退款、累计确认和资格行为。原政策文本也保留，其中有首批“工单尚未接入”的历史文案；当前能力以七工具注册表为准。该文案/政策版本及初态变更仍待 A/C 审核，不能悄悄修改历史初态。

v2 为一订单三商品、两消息（一条无确认）：实付 1001 分，gross 权重 501/300/201，分摊 500/300/201；杯子两件，每件 250 分；杯垫三件但确认累计最多两件；包装袋资格未满足且未获退款确认。这只是结构不同的工程模板，不是正式独立样本。

修订/新增时更新受控登记、fixture_version 和必要的来源/分组语义，同步 CreateSession 枚举、fixture_registry.json、development_fixture.schema.json，复跑校验和金额/权限/HTTP 测试。已有会话只用数据库内冻结事实，不重读模板。确认更正、撤销、授权合并等仍待 A/D 审定，没有实现绕过普通控制的通道。

## 兼容与待审

迁移 003 仅新增 session_cases；001/002、原交易/工单/事件/成功请求结果不重写。无 context 的旧会话保留原 case-session-* 编号，schema=3 导出为 case_context_status=legacy_unavailable、case_context=null。不按字符串猜旧来源，不伪造旧哈希；旧会话追加的恢复事件也保留旧 case_id。

新解析器读 schema=1/2/3；新导出外层 bc-0.3/schema=3，内部旧 snapshot/事件/工单来源保持原值。旧严格消费者要升级。policy_version 从单一 Literal 扩为版本 ID，但外部仍不能注入任意规则。操作和回退见 docs/migrations/B_003_session_cases.md。

待 A/D：case/parent/family 分组，v2 事实与政策版本，确认更正/撤销/授权范围，旧政策文案修订。待 C：context 取得、模板义务映射、canonical 完整性与租户归一/字符串规范、schema=3/legacy_unavailable、配对条件和事件定位。无人代签或冻结。


## 阶段 03 补充（2026-10-12）

上文“没有开始 D”描述阶段 02 当时的停止点。现已按用户授权完成 D 工作台的阶段 03；B/C 版本与既有事实语义不变。新增管理目录 GET /api/v1/admin/fixtures、GET /api/v1/admin/sessions（强制 tenant_id，offset/limit），原事件 GET 增加可选 limit，默认保持旧行为。对应 FixtureCatalog/FixtureMetadata/SessionPage 已导出到 schemas/OpenAPI；七工具与 EvidenceBundle 的既有字段不变，没有迁移 004。

这些读取适配与 observer-0.1-candidate 鉴权边界见 BD_observer_v0.1.md；真实 HTTP 样例见 contracts/workbench_examples.json。仍为候选，A/C 语义审核和 C 独立消费者签收待完成。
