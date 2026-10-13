# BD → A 业务与研究合同接收清单（待 A 本人审核）

本轮没有替 A 实现公式或签署规则。bc-0.3-candidate、两个公开开发模板和历史政策仍是候选；D 中金额是 B 已提交的模拟资金事实，不是损失、保费或赔款。commercial_quote=false。

## 接收材料

`README_RECEIVE.md`、`BD_CURRENT_STATE.md`、`BD_to_A_C.md`；`docs/spec/AgentShield_v1.1_Package/AgentShield_v1.1_Plan.md`、A任务卡与 delivery_levels_v1.1.json；`BC_contract_v0.3.md`；`sandbox/fixtures/dev-refund-v1.json`、`dev-refund-v2.json`；`contracts/evidence_example.json`、`fixture_v2_evidence_example.json`、`case_examples.json`、`bd_handoff_example_v0.1.json`。最后一个是实际 B 证据引用与 A/C 缺席示例，不是已审 QuoteResult/LossResult wire 格式。

## A 需逐项审定

- [ ] 整数分分摊、平分余数顺序、逐次退款尾差、数量及余额边界是否符合业务；v1 示例333/333/334分，v2结构不同及250分首退只是实现事实，不自动构成规则正确性结论。
- [ ] 合法确认的消息/对象/数量/时点和更正优先级；未确认、冲突、更正、部分退款、资格变化如何处理；不能只从客服自然语言或工具 succeeded 判断合法。
- [ ] 稳定 case 与运行对象映射、规范初态/可比条件，以及两开发模板的业务语义。正式任务/Gold 由对应负责人后续提供，本轮未读取正式留出答案。
- [ ] 持久化人工工单的类别/缺失事实/证据范围、何时升级及如何计入业务义务。open 工单与 finish 声明不表示已裁决、已付款或损失为0；后续人工裁决流程尚未开发。
- [ ] v1 历史政策中的“工单尚未接入”与当前七工具差异。保留旧事实，若更新须新政策/模板版本并记录适用范围，不能静默改写历史证据。
- [ ] 与 C 对齐合法应付/额外支出/追回/观察时点净损失、义务引用、缺失与未知；B退款总额不能直接当损失。case重复与独立样本、缺配对/失败运行、类别权重和支持范围需明确。

## A 需交付的研究计算接口

- 版本化 QuoteResult schema、语义文档、合法/非法/缺失/边界样例、错误模型，以及实际结果（未实现部分明确留空）。不以展示候选替代正式 wire 审定。
- 合同版本、数据/计算版本、C结果与运行清单引用、配置/类别样本量/业务量或权重；合同/公式依据由 A 服务端或离线模块实现，前端不复制。
- B0/B1/B2、not_fitted/insufficient_evidence/partial/out_of_scope 的准确字段及组合，null与0区别、超范围/部分结果如何显示；零观测不能声称零风险。样本描述与情景估计需区分；始终为研究用途，commercial_quote=false。
- 合同修改与重算入口、输入输出版本/错误和可重复样例；重算生成新结果版本，不改变 B 历史轨迹或模型运行数。A离线理算、赔付计算尚未完成。

## 本人执行与回执

按 README_RECEIVE 安装、构建、启动；检查企业实验场的原政策/公开消息/订单/商品，以及账本到交易/事件的追溯。导入上述开发证据及schema1/2历史样例，确认缺失不补造。必要时执行 `python -m unittest discover -s tests -v` 和 `python -m scripts.run_http_checks --output-dir <全新目录>` 理解实现事实；这些通过不能代替业务审定。

记录：审核人、日期、规则/合同/模板版本、逐项接受/保留意见、修改依据、样例/命令/结果、与C的分歧、下一输入与接受范围。全部**待 A 本人填写**。D 当前空值 pending、非空未审协议 unsupported_contract，尚无成功适配器；收到 schema/语义/样例后由 BD 在另行授权范围逐版本接入并测试。

没有 A/C 审定、真实运行与独立核验前，不开始正式56次实验、不宣布全队J2/L1或R09。第二机/第二人复现也仍待实际执行。
