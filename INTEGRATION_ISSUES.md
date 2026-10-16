# INTEGRATION_ISSUES

## 已关闭

- I-01，P1，B/A：四个固定 A 案例不在 B allowlist。已用固定 ID、固定源码路径、版本和 SHA-256 注册；仍为 `development_only`，任意路径/JSON/上传继续拒绝。
- I-02，P1，B/C：无 obligation spec 且零出款被判 `verified/0`。已改为 `needs_review/null`；零出款只是账本事实，不能证明合法义务为零。
- I-03，P1，C/A：相似订单的历史确认可能被误当本次请求。已 fail closed，转人工且零出款。
- I-04，P1，C/A：存在资格不足行和未结构化事实时可能擅自拆分。已 fail closed，转人工。
- I-05，P1，C/A：不同确认的原因说明未区分“有效更正”与“无替代关系的冲突”。已明确只有结构化替代关系可判更正；当前 wire 无法证明时转人工；文本更正回归仍通过。
- I-06，P1，前端：不接受 `scripted_test`。已修复并显示“规则基线”。
- I-07，P2，证据来源：manifest 指向旧 A 决策表。已改为 `business_policy_A_v0.2.md#2`，最终批次复验。

## 未关闭 / 负责人

- I-08，P0（正式运行 blocker），A：`scripts.a2_release_audit` import 不存在的 `scripts.a1_preflight`，当前命令直接 `ModuleNotFoundError`。需要 A 补齐公共 preflight 或修正审计入口；本轮没有接触其私有输入。
- I-09，P0（正式运行 blocker），A/D：40 案例义务、Gold 和决策表尚未 D 真人双签。当前 LossResult/赔款必须保持待审。
- I-10，P0（产品 blocker），A/用户：两套保险产品的保障范围、免赔/比例/限额、业务量口径和商业保费方法尚未批准；本轮不能虚构。
- I-11，P1，C/A：公开 wire 没有结构化“本次请求”和确认替代链。规则基线只能保守转人工，不能自动区分所有有效更正场景。
- I-12，P2，D/前端：运行和模板选择器冗长，历史失败/修复批次缺少 superseded 展示。
- I-13，P2，工程环境：新 Python 3.13 venv 的 `ensurepip` 失败；本轮借用已有匹配依赖环境完成真实验收。需修复可复现安装路径。
- I-14，P2，C/B 契约：规则基线在 wire 上仍使用 `execution_source=scripted_test`，靠 config/provider 区分；未来可考虑正式增加 `rule_baseline` 枚举，但需版本化迁移，不能本轮单边修改。

## 判定原则

以上 P0 只阻断正式冻结、商业报价和付费真实 Agent，不阻断本轮免费的开发固定案例联调。因此总状态为 PARTIAL，而不是 BLOCKED。
