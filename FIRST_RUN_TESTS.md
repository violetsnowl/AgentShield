# FIRST_RUN_TESTS

## 合并后、修复前的真实首轮

首轮是在 `1464a48` 上运行，结果如下：

- 后端：`python -m unittest discover -s tests -v`，146/146 PASS，24 个 A 公开 JSON 均通过 B fixture schema 校验。
- B HTTP：PASS；333 分退款、1 transaction、1 ledger、17 events、人工工单、重启恢复、真实断连后同键恢复、跨 session 拒绝全部成立；模型调用 0。
- OpenAPI/B 契约：`scripts.export_contracts --with-openapi --check` PASS。
- 前端共享契约：`scripts.export_frontend_contract --check` PASS。
- C LossResult schema：`evaluator.export_schema --check` PASS。
- 前端单测：50/50 PASS。
- TypeScript：PASS。
- 生产构建：PASS，23 个模块构建完成。
- 核心浏览器：PASS，747 项、18 张截图、真实 B HTTP、观察者只读、支付调用 0。
- Stage04 浏览器：PASS，117 项，7 类篡改/竞态检查均按预期拒绝，`errors=[]`。

## 首轮环境假失败

- 沙箱内 Starlette TestClient 卡在本机 socket pair；同一命令在允许回环 socket 的独立环境通过。
- 沙箱内 Vitest 因 Vite 临时文件重命名 `EPERM` 失败；同一代码在允许文件操作的环境 50/50 通过。
- 两者均记录为执行环境限制，不计为产品失败。

## 首轮暴露的真实问题

- 四个指定 A 案例虽通过 schema，但不在 B REGISTRY，无法通过真实 HTTP 创建 session。
- 规则基线对 A v0.2 的相似订单、不可拆分资格和更正/冲突边界处理不足。
- 无 A/D obligation spec 且零出款时，C 错误地产出 `verified/0`。
- 前端 catalog 拒绝规则基线合法的 `scripted_test`，页面显示“未知执行来源”。
- C 基线 manifest 的决策表来源仍指向旧 `business_policy_A_candidate.md`。
- A 的 `scripts.a2_release_audit` 无法启动：缺少其 import 的 `scripts.a1_preflight`。

## 原始证据

- B HTTP：`artifacts/integration_20261015/first-run-http/`
- 核心浏览器：`artifacts/pro_bd_sprint/05/integration-first-run-browser-core-20261015/`
- Stage04：`artifacts/pro_bd_sprint/05/integration-first-run-stage04-20261015/`
- 首个固定案例批次：`artifacts/c_l0/runs/integration-fixed-a-cases-20261015-201056/`（保留了零出款误判的历史证据）
