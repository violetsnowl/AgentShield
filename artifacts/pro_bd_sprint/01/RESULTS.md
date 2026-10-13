# BD 冲刺阶段 01 — 本机施工与复验结果

日期：2026-10-12（Asia/Hong_Kong；JSON 时间戳为 UTC）。工作区：D:\作业合集\大三\智能+保险\agentshield。当前候选：bc-0.2-candidate。01 的增量实现和功能复验完成；没有执行 F02/阶段 02 或 D。A/C 接口审核、C 独立消费者签收仍待完成。

## 开工事实与文件位置

- 未发现适用 AGENTS.md；当前目录不是 Git 仓库，没有分支/提交号，不执行 reset/clean/checkout/push。开工没有既有阶段 RESULTS.md。
- 检查 README_B、NEXT_STEPS、B_to_C、现有模型/协议/样例及测试副作用；现有 43 个源码哈希与首批清单一致，没有发现应重复覆盖的补丁。检查结果见 inspection.json。
- 已读 docs/spec/AgentShield_v1.1_Package/AgentShield_v1.1_Plan.md、role_cards/B_Sandbox_Backend.md、role_cards/D_Frontend_Release.md，以及既有 delivery_levels_v1.1.json；不改其未验证/未签审状态。
- 工作区原缺本轮审计/冲刺资料，已从用户 Downloads 中的 AgentShield_B_Audit_Results_2026-10-12 (1).zip 和 AgentShield_Pro_BD_Sprint_2026-10-12 (1).zip 导入新增目录，没有覆盖现有代码。实际读取审计目录 docs/audit/AgentShield_B_Audit_2026-10-12 下的 AUDIT_REPORT.md、probes.json、CODEX_B_NEXT_BATCH.md，以及 tasks/AgentShield_Pro_BD_Sprint_2026-10-12/README.md、01_B_PATCH.md。关键资料没有缺失。
- 历史审计仅作首批证据；当前状态由本机复跑确认。旧 CODEX_B_NEXT_BATCH 的 F02 超出 01，按用户指定边界暂缓。
- 开工 var 下无库、AGENTSHIELD_DB 未设置。unittest 在 var 创建自己的临时库；HTTP 脚本启动 loopback 子进程且显式指向独占临时库。先修改检查脚本支持新输出目录，避免覆盖旧 HTTP 样例，然后才复跑基线。

## 实际修改

1. **F03 调用关联**：api/app.py 独立校验两个关联头；非法业务参数、非法 JSON 仍保留安全 call_id/key，非法/重复/超长/凭据头不落事件。失败无资金变化、不占成功键。sandbox/store.py 只以哈希检查已登记会话凭据；不输出凭据。非有限数字在错误审计中安全归一为占位值。
2. **F01 来源**：contracts/models.py 统一三来源枚举；旧 scripted_test/mock_agent 保留，observed_agent_execution 可沿会话/case/事件/工单/证据传播。三来源 HTTP 检查明确 model_calls=0、real_execution_proof=false；不杜撰 provider 证据。
3. **F05 工单**：新增 HumanReviewRequest/Ticket 与第七工具 submit_human_review；只保存类别、缺失事实、当前 case/customer 公开消息引用和关联字段。会话版本+1，工单/成功键/事件/版本同事务；回滚、并发、权限、幂等、结束后恢复、重启均有测试。无资金和裁决；finish(escalated) 仍只是声明，不隐式建/关工单。
4. **迁移**：001 保持不变；002 增加 human_reviews 和 schema_migrations。用隔离 v1 库逐行核对原会话、退款、账本、成功键、事件等不变，重复初始化、旧键恢复和新工单成功。没清空用户库。
5. **F04 边界**：错误处理仅观察已归属的实际 HTTP 请求；未知工具/非法 JSON 为 rejected，不增加万能执行路由。认证失败只写 security_events。C attempted、本地拒绝、超时和实际接收证据由 C 后续实现，本轮仅约定边界与测试 B 事实。
6. **协议/样例**：bc-0.2-candidate；EvidenceBundle schema=2 增加 human_reviews，ToolEvent 增加可空 ticket_id；新版仍读旧样例，旧严格消费者需升级。同步 schemas/tools/openapi/implementation_status、examples、七工具真实 response_examples，以及 evidence_example、tool_event_examples、session_source_examples。
7. **验证与交接**：新增 tests/test_b_patch.py；同步原协议测试；独立标准库 bc_smoke_test、HTTP 驱动和证据记录/交付校验脚本；更新 README_B、NEXT_STEPS、B_to_C；新增 BC_contract_v0.2 和迁移/回退说明。原金额、身份、事务断言没有放宽；原“人工工具未实现”断言改为真实未实现工具的 404，注册工具数量随本轮 6→7。

## 实际命令、退出码与日志

以下均由当前 .venv\Scripts\python.exe 执行，命令前缀为 `-m scripts.record_check --output-dir artifacts/pro_bd_sprint/01 <label> -- python`。JSON 记录精确解释器路径、起止时间、包版本、命令和原始输出；同名 .log 是该输出的 UTF-8 副本，不改历史结果。

- baseline_tests：`-m unittest discover -s tests -v`，26 项通过，退出 **0**；baseline_tests.json / baseline_tests.log。
- baseline_http：`-m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/01/baseline_http_evidence`，原六工具 HTTP/进程重启通过，退出 **0**；baseline_http.json / baseline_http.log，原始响应在 baseline_http_evidence/。
- patch_backend_first：`-m unittest tests.test_backend tests.test_b_patch -v`，33 项中 2 个 Windows 清理错误，退出 **1**；patch_backend_first.json / .log 保留。sqlite3 的连接上下文不自动关闭句柄，临时目录清理触发 WinError 32；修复为 contextlib.closing。没有把业务失败改为宽松断言，也没有删除库掩盖迁移。
- patch_backend_second：同上，33 项通过，退出 **0**；patch_backend_second.json / .log。
- patch_http_first：`-m scripts.run_http_checks --output-dir artifacts/pro_bd_sprint/01/patch_http_evidence`，七工具独立 HTTP、新工单、权限/结束恢复、退款与工单跨真实进程重启通过，退出 **0**；patch_http_first.json / .log，HTTP 响应/服务日志/TCP 证据在 patch_http_evidence/。
- patch_full_suite：`-m unittest discover -s tests -v`，**42 项通过，退出 0**；patch_full_suite.json / .log。覆盖原交易、并发、后续行失败回滚、协议/schema、14 个新增补丁/迁移测试及新样例一致性。
- patch_contract_check：`-m scripts.export_contracts --with-openapi --check`，模型与导出一致，退出 **0**；patch_contract_check.json / .log。

HTTP 核心链路只有 1 笔 333 分退款、1 条账本、1 个 open 工单；订单版本 2，会话经退款/工单/finish 到版本 4。工单事件金额 0。TCP 子测试使用另一个隔离会话，通过 socket.sendall 发完请求后 shutdown/close，完全不读取响应，查到 committed，再原键恢复同 transaction_id；该会话同样只有 1 笔 333 分退款/1 条账本。不是把收到的响应对象丢弃来冒充断连测试。

第一次清理失败遗留的两个测试库保留在 var/migration-v1-vm5ra8a8/legacy.sqlite3 和 var/tmpt1rn8dz0/test.sqlite3，均为本轮测试新建，不是用户原库，不打包进代码检查点。后续成功运行的临时库按脚本正常清理。历史 Starlette/httpx 弃用警告保留，历史 Header alias 警告亦未改写；不宣称无警告。

## 对照旧审计的本次预期

旧 docs/audit/.../probes.json 只读保留，不重写成新成功结果。新行为由 tests/test_b_patch.py 和本次日志验证：

- P01：observed_agent_execution 从 422 改为 201，验证完整标签传播；不是实际模型证明。
- P04：非法数量仍 422，但有效两头正确入事件，随后修正参数原键可成功。
- P05 NaN/溢出：仍拒绝且证据可读，后续正常退款成功；保留此正确行为。
- P06/P08：已认证未知工具/非法 JSON 分别 404/422 且有 rejected 事件；未认证或跨会话不写目标事件。
- P07：人工工具从未实现改为真实持久化工单，使用已定义合法请求成功，额外裁决/金额字段仍拒绝。
- P09：不同键同版本并发只有一笔成功、另一笔 STALE_STATE；后续商品行失败全部回滚。
- P02/P03：第二 fixture 与稳定案例/多订单语义属于 F02；本轮未实现也不宣称通过。

## 待审事项、限制与停止点

A：公开消息引用/缺失事实语义，原金额分摊、资格与确认范围。C：来源声明与真实模型证据分离、attempt/HTTP/提交关联、schema=2 严格消费、工单与 finish 版本/恢复语义、缺证据空列表。接收人必须本人填写 NEXT_STEPS；不代签。BD 后续分工仍由用户与舍友按实际进展决定。

本轮无 A 保险算法、C 正式 Agent/核验器、D 前端、正式留出 Gold、付费模型、真实支付、公网部署、远端推送或项目上传。最小工单没有人工处理/裁决/关闭/分派功能；没有声称全队关口或正式人工审核能力通过。其他平台、断电、多机和规模压测未验证。

前检查点 checkpoints/before_01.zip 与 before_01_manifest.json 保留施工前源码/旧证据；后检查点记录最终代码/文档/本次证据，均不含 .venv、数据库或实际凭据。无 Git 时以 ZIP 和 SHA-256 核验。回退需在独立目录检查代码，并按 docs/migrations/B_002_human_reviews.md 使用匹配的一致数据库备份，不能强覆盖或丢弃已提交事实。

## 最终交付校验

`-m scripts.record_check --output-dir artifacts/pro_bd_sprint/01 delivery_check -- python -m scripts.verify_delivery --output-dir artifacts/pro_bd_sprint/01/delivery_manifest` 实际退出 **0**；日志 delivery_check.json / delivery_check.log。pip check 无依赖冲突，锁定版本匹配；契约导出一致；隔离库初始化两次成功；17 个历史 b_bootstrap 文件与开工 SHA-256 一致；70 个源码/文档哈希保存到 delivery_manifest/source_manifest.json。

另以用户原 ZIP 逐文件比对导入资料：14 个审计文件、6 个冲刺文件全部字节一致，见 input_preservation.json；审计结论/日志及阶段任务卡没有改写。

最终代码、文档和证据归档为 checkpoints/after_01.zip，清单为 checkpoints/after_01_manifest.json；归档完整性与逐项 SHA-256 核对记录在 checkpoints/checkpoint_verification.json（不向归档内自引用写入自身哈希）。归档不含 .venv、var 数据库、实际凭据或运行缓存；前检查点仍独立保留。消费者可先核对清单再在独立目录解压检查。

**阶段 01 已完成并停止；不自动跳入 02，不开发 D。**
