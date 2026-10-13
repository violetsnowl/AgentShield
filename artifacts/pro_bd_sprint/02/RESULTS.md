# BD 冲刺阶段 02 — 稳定案例与受控开发模板

日期：2026-10-12（Asia/Hong_Kong；JSON 记录为 UTC）。工作区 D:\作业合集\大三\智能+保险\agentshield。当前 bc-0.3-candidate，七工具，EvidenceBundle schema=3，迁移 001/002/003。**阶段 02 完成并停止，不进入 03 或 D。** A/C 审核及 C 独立消费者签收仍待完成。

## 开工核对与保护

实际读取当前源码/fixture/Store/模型/测试、01/RESULTS、NEXT_STEPS、B_to_C、BC_contract_v0.2、02_B_CASE_FIXTURE，并参考审计 F02 和 V1.1 第 5/8/11 节。适用 AGENTS.md 未发现；目录不是 Git 仓库，没有 commit/reset/clean/push/上传。

开工文件与阶段 01 after_01_manifest 全部一致，未发现需重复覆盖的新补丁。inspection.json 记录比对结果。先保存 checkpoints/before_02.zip / before_02_manifest.json，再用当前 .venv 复跑 42 项和阶段 01 HTTP，全部通过后实现新功能。

检查测试副作用：unittest 和 HTTP 均使用 var 内独占临时目录；HTTP 显式覆盖子进程 AGENTSHIELD_DB 为自己的库，loopback 服务与标准库客户端分进程，结束后停止服务。开工 AGENTSHIELD_DB 未配置；var 只有阶段 01 清理失败留下的两个测试库，记录原哈希且本轮不读取业务内容/不修改/不清空。旧审计、阶段 01 结果和检查点保留。

## 实际实现

- contracts/models.py：bc-0.3；fixture_id 新增 dev-refund-v2；CaseContext、ObjectMapping、CanonicalBusinessSnapshot 等权威模型；创建响应 context，EvidenceBundle schema=3/context 状态；兼容 schema=1/2；policy_version 允许受控模板中的版本 ID。七工具输入保持。
- sandbox/fixture.py 与 fixture_models.py：注册表仅允许两个仓库 JSON；验证真实加载路径、文件大小、重复键/非有限数、严格金额/数量/资格、对象唯一性、候选范围、消息/确认归属、累计确认范围、分摊逐行/尾差与余额守恒。未增加在线登记或任意路径/JSON 接入。
- 新会话稳定 case_id/source_case_id，与每次 session/episode 分离；冻结 customer/order/item/message 模板→运行映射。相同 case 不授予跨会话权限，幂等键仍按 session 隔离。
- canonical_initial 保留业务请求、公开消息和顺序/确认、所有订单/商品初态、金额、资格、余额、政策、业务时间和执行环境版本；排除运行身份/凭据/配置等。固定单租户/客户拓扑使用模板租户别名，具体边界已文档化；SHA-256 可以用纯标准库独立重算。
- dev-refund-v1 转为声明式对象/消息结构，保持原金额/数量/资格/累计确认和公开原文；dev-refund-v2 新增一订单三商品两消息，实付 1001 分、分摊 500/300/201、杯子单件 250 分、无确认消息和不合资格商品。
- migrations/003_session_cases.sql 与 Store：只增加 session_cases 和迁移登记；session/context 同事务插入。已有会话读冻结事实，不重新载入文件。原交易/工单/成功键/历史事件无重写；旧会话 context=legacy_unavailable/null。
- scripts/bc_smoke_test.py：仍仅标准库，在独立 -I 进程用 HTTP 验证七工具和两个配置/两个模板、显式映射、初态复算与隔离。run_http_checks 保留 TCP 不读响应关闭恢复、退款/工单进程重启，增加 context 重启冻结验证。
- scripts/export_contracts.py：同步模型工具/Schema/OpenAPI/status，另导出 development_fixture.schema.json、fixture_registry.json。当前响应/证据/事件样例从本次实际 HTTP 捕获；新增 case_examples 和 v2 evidence。旧样例在历史目录不动。
- tests/test_case_fixture.py 新增 13 个测试方法（含非法模板矩阵子测试），wire consistency 新增 2 项；原金额/鉴权/幂等断言保留。只将新导出版本和迁移清单的正确预期改为 schema=3、[1,2,3]，另验证旧 schema=1/2 仍可读。
- README_B、NEXT_STEPS、B_to_C 已同步；新增 BC_contract_v0.3 和 B_003_session_cases 迁移/回退说明。verify_delivery 检查本阶段材料、历史哈希与开工数据库哈希。

## 实际验证命令、退出码和证据

所有命令由当前 .venv\Scripts\python.exe 执行。统一记录前缀为：
`-m scripts.record_check --output-dir artifacts/pro_bd_sprint/02 <label> -- python`。
每个 <label>.json 含实际解释器、完整命令、时间、包版本和退出码，<label>.log 为原始输出副本。

- baseline_tests：`-m unittest discover -s tests -v`，**42 项通过，退出 0**。
- baseline_http：`-m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/02/baseline_http_evidence`，原七工具/工单/真实 TCP/重启检查通过，**退出 0**。
- fixture_backend_first：`-m unittest tests.test_backend tests.test_b_patch tests.test_case_fixture -v`，**46 项通过，退出 0**。
- fixture_http_first：`-m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/02/fixture_http_evidence`，新旧模板、两配置配对与全部 HTTP 检查通过，**退出 0**。
- fixture_full_suite：`-m unittest discover -s tests -v`，**57 项通过，退出 0**。
- fixture_contract_check：`-m scripts.export_contracts --with-openapi --check`，导出与源码一致，**退出 0**。

本轮上述测试没有失败运行；Starlette/httpx 弃用警告按原样保留。施工期间一次补丁工具拒绝同文件 delete/add、另一次文档补丁返回匹配错误，均检查落盘后改用精确文件写入，不是将失败测试改写为成功。

独立 HTTP 的实际证据在 fixture_http_evidence/：evidence_sample、http_responses、events_sample、case_pair_a_evidence、case_pair_b_evidence、fixture_v2_evidence、case_examples、case_checks、tcp_disconnect_evidence 和 server.log。

## 重点验收观察

- 两个不同 config 的同 case：case/source_case 和 canonical/hash 相等，session/episode、customer/order/item/message ID 不同。A 运行退款不改变 B 初态；同 case 的跨会话令牌/对象访问和写入拒绝。
- 从 HTTP initial_snapshot 和 object_mapping 重建 canonical，标准库 SHA-256 与返回 hash 一致；无需猜 ID 或访问 B 数据库。新退款可以映射回 order-1/item-1/message-all，供 C 后续接业务义务。
- v1 主链路：一笔 333 分退款、一条账本、一个 open 工单、结束会话版本 4。v2：一笔 250 分退款、一条账本、一个无资金工单，最终商户 751/客户 250 分。不是把结果求和当多笔退款。
- 不合法数量/金额/资格类型、对象重复、缺失/跨订单引用、确认超量、错误分摊、余额、注册身份/版本、未知字段、重复 JSON 键、NaN、过大/缺失/越界文件：请求拒绝且所有业务表与请求前一致。context 插入故障回滚整个会话创建。
- 更新请求文案、公开消息、确认数量、资格、政策/业务时间/候选顺序会改变业务 hash；仅变运行配置/身份标签不影响；字典键顺序不影响。
- 新会话退款/工单/context 跨真实进程重启不变。模板不可用时已有会话仍能查询及原键恢复。
- 旧 001 数据迁移和旧 001/002 工单数据迁移均测试两次初始化，原行逐项不变；旧退款、工单、finish 原键返回旧结果，原 case_id/事件保留。没有通过清库适配新编号。
- TCP 实测发送完整请求后关闭连接、读取响应字节数 0；查询 committed 后原键恢复，仍仅一笔 333 分退款/账本。
- model_calls=0；三来源仅标签传播，不把 observed_agent_execution 当真实模型证明。

## 兼容性变化与待审

新稳定 case_id 的含义与旧 case-session-* 不同；旧编号保留，新会话不能据 case_id 合并运行状态。context 在创建响应/证据外层，旧会话明确 legacy_unavailable/null，不重构未经审核的来源。新外层 schema=3/contract=bc-0.3，内部旧 snapshot、事件、工单来源/版本不变。新模型解析旧 schema=1/2，旧严格客户端需升级。

公开工具仍为七个，未增加万能路由/文件注入/权限绕过。数据库 001/002 不变，003 为附加表。旧代码不应直接配新 v2 政策/上下文数据库回退；须保留当前事实并使用匹配备份，详见迁移说明。

待 A/D 审案例/parent/family 分组、v2 事实及政策、确认更正/撤销/授权范围；待 C 审 canonical 完整性、租户归一、序列化/映射、配对条件、旧证据与 schema=3。v1 原规则中的“工单未接入”旧文案本轮随历史事实保留，当前实际七工具可用；其文案/政策版本/初态调整待审。不得把两个工程模板计为正式独立样本或 Gold。

C 独立签收、B 下一位开发者干净环境复跑待本人填写。没有正式留出 Gold、模型调用、真实支付、A/C 正式模块、D 前端、公网部署、远端推送或上传；没有代签或声称全队门槛通过。仅 Windows/Python 3.13.1 验证，其他平台、多机、断电和负载未测。

## 检查点

施工前检查点 checkpoints/before_02.zip / before_02_manifest.json 保留；完成检查点 checkpoints/after_02.zip / after_02_manifest.json 保存代码、文档和证据，不含 .venv、var、实际令牌或运行缓存。解压到独立目录审核，不直接强制覆盖。前后归档/哈希验证另存 checkpoints/checkpoint_verification.json。

## 最终交付校验

实际执行：`-m scripts.record_check --output-dir artifacts/pro_bd_sprint/02 delivery_check -- python -m scripts.verify_delivery --output-dir artifacts/pro_bd_sprint/02/delivery_manifest`，**退出 0**。delivery_check.json / delivery_check.log 记录：依赖版本与锁文件匹配、pip check 无冲突、导出契约一致、隔离库初始化两次成功；83 个历史证据/检查点/规范/迁移文件保持开工哈希，2 个既有测试数据库原字节不变；80 个源码/文档哈希保存到 delivery_manifest/source_manifest.json。

前后 ZIP 的 CRC 与逐文件 SHA-256 检查结果保存在 checkpoints/checkpoint_verification.json。after_02 包含本阶段最终代码、契约、文档和复验证据；不含数据库/令牌/.venv，也没有上传。当前没有 Git，故不虚构提交号。

**阶段 02 已完成并停止，不自动执行 03。**
