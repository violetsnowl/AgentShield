# B 数据库迁移 002 与回退

本轮开工时 `var/` 没有数据库，AGENTSHIELD_DB 未配置；没有清空或迁移用户原库。旧库兼容通过在隔离临时库中加载原 001 结构和首批真实开发证据进行测试。

## 升级

1. 停止写入和本地服务。确认实际 AGENTSHIELD_DB 路径，备份对应 SQLite 数据库；推荐 SQLite backup API 制作一致备份，不能在服务运行时仅复制主文件而遗漏 WAL。备份包含私有会话信息，应留在本地，不放入仓库或交接 ZIP。
2. 确保备份及配套旧代码可读，再运行 `.\.venv\Scripts\python.exe -m scripts.init_dev --db <实际数据库路径>`。服务启动也会初始化，故必须在启动前完成备份。
3. 初始化按顺序执行 001 和 002。001 原结构不变；002 以事务创建 schema_migrations 和 human_reviews（外键关联 sessions），登记迁移 1/2。没有 UPDATE/DELETE 旧业务行。重复初始化安全。
4. 校验 `PRAGMA integrity_check` 为 ok、`PRAGMA foreign_key_check` 无结果、schema_migrations 包含 1/2。以授权凭据核对原会话、退款/账本以及原键恢复；不得用新建空库的结果替代旧库验证。

旧 schema_version 表带 CHECK(version=1)，保留其值作为 001 基线。新增 schema_migrations 是累积数据库迁移记录；EvidenceBundle.schema_version=2 表示导出格式，两者不能混用。旧 snapshot 的来源和 contract_version 原样读取；新导出会补充 human_reviews 和可空 ticket_id。

## 已运行的迁移检查

`tests.test_b_patch.MigrationTests.test_legacy_rows_and_successful_keys_survive_additive_migration`：使用原 001 SQL 和 `artifacts/b_bootstrap/http_smoke/evidence_sample.json` 构造隔离旧库；运行两次初始化；逐行比较 sessions/refunds/ledger/requests/events/security_events 未变化；检查完整性和外键；读取旧证据；按旧成功键恢复同笔退款；创建新会话并持久化工单。测试结果在 `artifacts/pro_bd_sprint/01/patch_full_suite.json`。

这是旧版本已知结构的验证，不是任意损坏/自定义数据库或生产灾备认证。

## 回退

本项目没有 Git。施工前代码和历史证据保存在 `artifacts/pro_bd_sprint/01/checkpoints/before_01.zip`，对应文件清单/哈希为 before_01_manifest.json；本轮完成检查点为 after_01.zip / after_01_manifest.json。先解压到独立目录核对，保留当前文件，不能直接强制覆盖工作区。

上线前若要回退，应停止服务，采用**相互匹配的旧代码与迁移前一致数据库备份**。旧代码的严格 ToolEvent 模型不能直接读取新增 ticket_id 字段，不能只回退代码继续指向已产生新事件的库。

如果升级后已发生退款或工单提交，不得直接恢复旧库丢弃新事实。保留当前库及 WAL 和完整证据，先完成事实对账并选择修复/兼容方案。本轮没有自动降级、数据删除、回滚已发生交易或工单关闭功能；代码检查点不是数据库备份。
