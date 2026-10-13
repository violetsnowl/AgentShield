# B 迁移 003：冻结案例上下文

新增 session_cases(session_id 主键/外键, payload)，payload 是 CaseContext：业务身份、模板版本、对象映射、规范初态和哈希。与 sessions 同事务插入。没有修改旧 sessions/refunds/ledger/requests/events/human_reviews 的 SQL，没有反向生成旧映射。

## 升级

1. 停止服务/写入，确认 AGENTSHIELD_DB，使用 SQLite backup API 制作一致备份；不要在服务运行时只复制主文件而忽略 WAL。备份含私有会话信息，不放入仓库/代码 ZIP。
2. 保存配套旧代码，执行 `.\.venv\Scripts\python.exe -m scripts.init_dev --db <数据库路径>`。服务启动也自动执行 001→002→003，因此先备份后启动。
3. schema_migrations 应含 1/2/3；旧 schema_version 基线表仍为 1。检查 PRAGMA integrity_check、foreign_key_check 和原会话/退款/工单/成功键。重复初始化不改旧业务行。
4. 只有新会话获得稳定 case/context。旧会话仍可读取、继续允许的业务动作和原键恢复；schema=3 导出用 legacy_unavailable/null 标记缺少稳定关系。不能自动把旧运行并入 stable case 配对样本。

新版解析器兼容旧 schema=1/2；旧 snapshot 不增加字段，不改 contract/source。新字段只在 EvidenceBundle 外层和管理创建响应。退款/工单/finish 的旧键返回原结果，恢复事件正常追加，旧事件原文不变。

## 已验证

- 原 001 结构和首批实际证据：重复迁移、逐行保持原事实、旧退款原键恢复（test_b_patch）。
- 原 001/002 结构和阶段 01 实际证据：迁移两次，逐行核对原退款/账本/工单/请求/事件；退款、工单、finish 三个原键全部返回旧结果；旧 case_id 不重写（test_case_fixture）。
- context 写入故障时 session 回滚；非法/缺失/越界模板无部分业务数据。
- 新会话退款/工单/context 跨真实进程重启恢复；模板不可用时已有会话仍读冻结数据。

本轮没有迁移用户原库。var 内两个阶段 01 遗留测试库按开工哈希保留，所有本轮测试用独占临时库。不把这些隔离测试冒充实际用户旧库升级证明。

## 回退

施工前检查点在 artifacts/pro_bd_sprint/02/checkpoints/before_02.zip 和 before_02_manifest.json；完成检查点为 after_02.zip / after_02_manifest.json。先解压到独立目录核验，不直接覆盖当前文件。代码 ZIP 不含数据库或实际令牌。

若已创建阶段 02 运行，不能仅回退代码继续指向当前库：旧程序不认识完整 context/schema=3，且旧单一 policy Literal 不能读取 v2 策略。无新增事实时使用匹配的旧代码和一致迁移前备份；若已有退款/工单提交，保留当前库/WAL/证据，先对账再选兼容修复方案，不能恢复旧库丢弃提交。没有自动降级/删除事实功能。
