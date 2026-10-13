# AgentShield A0 第一轮交付回执（开发者自测，A/D 签收仍 pending）

**日期**：2026-10-13（按当前会话）；**来源基线**：BD Stage05 ZIP；**范围**：仅 A 新增模块和候选文档。**本次操作者**：ChatGPT 在隔离的 Linux Python 3.13.5 工作容器中编写并测试；不是用户 Windows/PyCharm 复现，也不是 B/D 签收。

## A0-1 业务审查

- `docs/business/BD_A_review_v0.1.md`：v1/v2 分摊、权限、确认、工单、历史政策及未决争议。
- `docs/business/business_policy_A_candidate.md`：公开证据驱动的决策表、事前分类，以及 L0 8常规+4压力的**待审设计清单**。
- 重要缺口：两个开发模板不足以独立界定唯一本次合法应退义务；`review_status` 仍 pending；正式 Gold 未创建。

## A0-2 金额核对

- `docs/business/engineering_claim_cases_v0.1.json`：9个有手算期望的工程算例，涵盖正常、拦截、多退追回、跨义务不可抵消、同事件免赔一次、全部追回、未知、除外、免赔边界。
- 全部金额使用整数分。**工程注入不是实际 B 网关已允许的错误支付，不能汇入真实 Agent 事故率。**

## A0-3 保险函数与情景统计

- `actuarial/contracts.py`：研究合同/整数和非法值校验。
- `actuarial/claims.py`：已验证损失和责任条件下，事件赔款和商户自留；半入舍进至整数分。
- `actuarial/estimate.py`：单 case 重复先聚合；B0/B1；目标权重校验；开发/留出隔离；部分/零损失处理，B2 `not_fitted`。
- `actuarial/demo.py`：无网络、无外部 API、无支付的工程演示。
- `configs/insurance/research_contract_v0.1.json`：研究责任候选及默认免赔/比例/限额。
- `contracts/quote_result_A_v0.1_candidate.schema.json` 和 `contracts/quote_result_A_v0.1_{engineering,insufficient}_example.json`：给 BD 的候选 wire 与示例；**不修改 B/D 的权威 `contracts/models.py` 或前端适配器**。
- `docs/business/QuoteResult_A_v0.1_candidate.md`：统计语义、输入来源、状态及接入限制。

## 这次实际测试

在原 BD 解压源码的独立工作副本中仅加入上述 A 文件后，执行以下命令：

```
python -m unittest tests.test_actuarial_claims tests.test_actuarial_estimates tests.test_actuarial_cases -v
# 退出码 0；23 tests；OK。详情见 TEST_LOG_A_ONLY.txt。

python -m unittest discover -s tests -q
# 退出码 0；88 tests；OK（包括原有 65 项）；见 TEST_LOG_ALL.txt。

python -m actuarial.demo
# 退出码 0；应退80误退800追回200 -> 净损失520元、模拟赔款420元；B0=500.0000分；B1=600.0000分。
```

`jsonschema` Draft202012Validator 校验了工程示例及证据不足示例，两者通过。**这里未运行用户 Windows 的 Python 3.13.1 锁版本环境，也未完整执行 Node/Edge UI 套件、真实 Agent 或真实保险数据审验。**

## 下一轮待办及责任边界

1. **A 与 D**：逐条审核公开申请事实、确认覆盖与更正时点、Gold 允许动作集合、义务定义与 H 观察终点。正式留出 Gold 对 C 运行器及调提示词目录保密。以上文件内容仅候选，签收 pending。
2. **C**：独立 LossResult oracle、逐义务已提交/应付金额与追回关系、`loss_status`、`coverage_status` 的输入分界、run manifest/父 case/证据引用；**不能用直接读取 B 的“正确结果”实现核验器**。
3. **B/D**：待收到最终审定 schema、样例和真实 C LossResult 后再实现 `frontend/src/integrations.ts` 适配；当前 `unsupported_contract` 行为正确，不能因文件名称像 QuoteResult 就跳过审核。
4. **本机负责人**：在 PyCharm 独立运行以上命令并保留退出码/日志；相同项目根目录合并，不覆盖任何已有 B/D 代码、数据库或历史证据。
5. **A1（尚未授权/完成）**：28个正式任务及双人 Gold 复核、真实 Agent 结果分析、正式定价研究与报告章节。本次全部未完成。

**状态：A0 工程候选可进入独立复核；A/D/C/BD 全队验收、L1/J2/R09 均未完成。**
