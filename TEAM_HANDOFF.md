# TEAM_HANDOFF

## A 需要完成

- 修复 `scripts.a2_release_audit` 的缺失依赖 `scripts.a1_preflight`，提供可在公共仓库独立运行的审计入口。
- 对固定/正式案例提供版本化 obligation spec；不能只给 allowed outcome 或确认上限。
- 与用户提出两套保险方案，明确保障、免赔、比例、限额/保额、业务量和商业保费方法；确认前不写死参数。
- 保持私有 Gold 在 A/D custody，不放入公共 runner 或前端。

## C 需要完成

- 在 A/D 双签后，把 v0.2 规则表和 obligation spec 版本冻结到 runner manifest；当前 `decision_table_signed=false` 必须保留。
- 为“本次请求”和确认的撤销/替代关系设计版本化结构字段；否则有效更正与冲突只能保守人审。
- 若要将 `rule_baseline` 作为独立 execution_source，先与 B/前端共同升级 schema；当前继续用 `scripted_test + config/provider` 是兼容方案。
- 下一轮真实 Agent 开发测试只能在明确预算/模型授权后运行；正式 56+28 仍由门禁阻断。

## D / 前端需要完成

- 对 A 的 40 个正式候选逐案真人独立签收义务、边界、split/family 和 Gold hash。
- 在不改动历史证据的前提下，为 catalog 增加 `superseded`/批次状态、筛选和折叠，减少错误批次与修复批次并列造成的混乱。
- 收敛页头与卡片的重复身份信息，并将“当前运行结果”和“工程情景样例”做更清楚的视觉分组。
- 两套产品只有在 A/用户批准接口后再做展示；不得在前端复制理算公式或写死保费。

## B / 共享契约需要完成

- 保持四案严格固定 allowlist；正式候选发布时必须另起版本和审核流程，不能把 development_only 改名冒充正式。
- 评估是否增加结构化 current request / confirmation supersession 字段，以及版本迁移、旧证据兼容和 OpenAPI 影响。
- 修复/记录 Windows Python 3.13 `ensurepip` 的可复现安装问题。

## 下一轮建议顺序

1. A 修审计入口并提交 obligation spec 草案。
2. D 真人双签一个普通退款和一个人工升级案例。
3. B/C 冻结对应开发版本；先用免费规则基线复验。
4. 若用户明确授权模型和预算，再跑固定案例真实 Agent 开发测试；仍标非正式。
5. A 提交两套保险方案参数供用户确认；确认后才实现接口和前端。
6. 十万订单抽样另开一轮，不与上述固定案例证据混用。
