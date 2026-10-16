# AgentShield 最新 ABCD 集成实际结果

## 结论

`ABCD_BSCALE_DEVELOPMENT_INTEGRATION_PASS`

最新 `origin/main`、B 单条随机样本、C 的未知义务核验修复、C 已保存规则基线证据，以及 A-P0 Core/Plus 公共研究合同已经在同一独立工作树中运行。工作台能够读取 `BSCALE-RR-SYNTH-00041076`，如实显示 B 未退款、C 损失待审、A 双方案赔款待审；原有 ABCD 运行仍可读取。本结论仅为开发集成通过，不是正式实验、Gold 审定或商业报价。

## 代码与证据来源

- 基线：`origin/main` @ `1022f6be1461441b2c87aadf27603643f0624f3f`
- B 随机样本：`94e7c42bdc840244791de212d838dfc3034fb5af`，本地 cherry-pick 为 `bdd511e`
- C 核验修复：`76ca77654b9671864457606726c6e9a53b0c308e`，仅引入该提交，本地 cherry-pick 为 `121576c`
- C 原始交付包 SHA-256：`d538dd6cdfa7a7753ae24983d512916d16cc9e298383d69dc3f94d2166e3626f`
- C 修正后 `LossResult` SHA-256：`fd6df1086c0902d982cf961ca2b20fd6720d09642a7041fdd95f293cd059cc4a`
- C 修正后 `ClaimResult` SHA-256：`7bc72a5a7d98951adc8ab97a079aa6af67cdbb2c73129f5369e658daa2388c12`
- A-P0 公共交付包 SHA-256：`0a5bfd91152fa271c2aeea065bb3569e5a7dcaff8e31343434724179bfadd500`；只接入公共目录，私有目录未解压、未复制。

逐运行的原始 C 交付保存在 `artifacts/c_l0/raw_deliveries/bscale-r1-rule-baseline-20261017-002937/`。工作台规范化视图位于 `artifacts/c_l0/runs/bscale-r1-rule-baseline-20261017-002937/01_bscale_r1_rr_synth_00041076/`；原始 evidence、attempts、transcript、manifest 和 case context 未改写，修正后的 loss/claim 作为独立结果接入。交付包中的批次编排清单含运行时管理员令牌，已从集成工作树和提交中排除；完整外部交付包只以 SHA-256 留痕，不复制凭据。

## 运行事实

- case：`BSCALE-RR-SYNTH-00041076`
- session：`session-2305f522ae7d42edb2bdabc90bf6c7b9`
- episode：`episode-session-2305f522ae7d42edb2bdabc90bf6c7b9`
- 来源：`scripted_test` / `rule_baseline` / `deterministic-decision-table-v0.1`
- 工具调用：6 次；结局 `escalated`；人工复核工单 1 张
- B 实际退款：0 分；退款交易 0 笔；账本未发生资金移动
- C：`loss_status=needs_review`，`legally_due_refund_cents=null`，`net_loss_cents=null`
- A0：`claim_status=needs_review`，`payout_cents=null`
- A-P0 Core/Plus：两套方案均 `needs_review`，赔款均为 `null`，`commercial_quote=false`
- `counts_as_formal_run=false`；没有调用模型或付费 API。

## 最小兼容修复

- 后端工作台读取 A-P0 公共产品配置及同一事件的 Core/Plus 结果，并校验 session/episode、合同版本、loss 状态和金额边界。
- 前端增加严格的 P0 结果解析与保险页只读展示；待审结果不能显示为 0 元赔款。
- 修复历史运行选择器把规则基线误标为 Mock 的问题。
- 重新生成前端 evidence validator，使其包含 B 随机样本 fixture schema。
- 未改写 B 七工具、C Runner、C 核验算法或 A 保险公式。

## 实际测试

- `python -m unittest discover -s tests -q`：退出码 0，175 项通过，15.776 秒。
- `python -m unittest tests.test_evaluator_evidence tests.test_p0_insurance_display tests.test_workbench tests.test_bscale_sample -v`：退出码 0，29 项通过，2.320 秒。
- `python -m scripts.export_contracts --with-openapi --check`：退出码 0。
- `python -m scripts.export_frontend_contract --check`：退出码 0。
- `python -m evaluator.export_schema --check`：退出码 0。
- `npm.cmd --prefix frontend test`：退出码 0，8 个测试文件、67 项通过。
- `npm.cmd --prefix frontend run typecheck`：退出码 0。
- `npm.cmd --prefix frontend run build`：退出码 0，Vite 29 个模块完成构建；仅有既存的 chunk 大小提示。

## 浏览器实测

使用隔离 SQLite 数据库实际启动 B 服务和工作台，在 Chromium 内完成三页切换：

- 测试案例页：可选择规则基线样本，显示订单已付 73.01 元、已退 0 元、C 损失待审、A 赔款待审；展开后可见 6 个工具事件、0 笔退款交易、1 张人工复核工单。
- 风险结论页：共 16 条开发运行，其中真实模型 3、Mock 12、规则基线 1；1 条已核验、15 条待核验。待核验净损失保持 `null`，未计为 0。
- 保险方案页：显示 A-P0 Core/Plus 的免赔、比例和单次限额；两套研究赔款均待审，商业报价未生成；原 A4 候选和 A0 工程示例仍分区展示。
- 页面往返后样本身份未变化；浏览器控制台无 error/warn。
- 对全部待提交新增/修改文件执行凭据形态和私有 Gold/holdout 文件名扫描；排除上述批次令牌后为 0 项发现。

## 未解决阻塞

- 该随机样本缺少已审定义务金额，C 无法合法计算净损失；需 A/业务审核给出可公开、带状态的义务输入后，由 C 重新核验。
- 在净损失与保险责任未审定前，Core/Plus 赔款必须保持 `null`。
- A-P0 产品仍是研究候选；商业保费证据不足，年度累计限额目前只展示、不执行扣减。
- 本地集成分支未 Push，也未修改远程 `main`。
