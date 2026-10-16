# FIXES_AND_REGRESSIONS

## 最小修复

1. B/A 受控注册
   - `contracts/fixture_ids.py`：只追加四个指定固定 ID。
   - `sandbox/fixture.py`：固定映射到 A 公共 development 目录，逐项校验 source case、fixture version 和 SHA-256。
   - 重新导出 OpenAPI、schemas、fixture registry 和前端生成类型。
   - 未开放任意 JSON、路径、URL 或上传。

2. C/A 规则基线
   - `runners/baseline.py`：A v0.2 下，多候选订单均有历史确认而当前请求无结构化范围时转人工。
   - 资格未满足且拆分范围不明确时转人工。
   - 对不同确认明确记录“缺少结构化替代关系，无法判定有效更正或冲突”；已有明确文本更正测试保持通过。
   - 来源元数据改指向 `docs/business/business_policy_A_v0.2.md#2`。

3. C/A LossResult
   - `evaluator/verify.py`：只要缺少 obligation spec，零出款也保持 `needs_review/null`，但仍如实报告 committed money 和完整账本检查。

4. 前端兼容
   - `frontend/src/integrations.ts`：接受合法 `scripted_test`。
   - `frontend/src/App.tsx`：将其标为“规则基线”，不再误标 Mock。
   - 未改布局、导航和 CSS。

## 新增/修改回归

- 固定 allowlist 精确性和注入路径拒绝。
- A 重复确认只执行一次。
- 相似订单不从历史确认猜测当前请求。
- 资格不足且拆分不明时零出款转人工。
- 文本明确更正不被机械当作冲突。
- 无 spec 的正出款和零出款都保持待审。
- 前端 catalog 接受 rule baseline 的 `scripted_test`。
- manifest 决策表来源与 A v0.2 一致。

## 最终回归记录

- 后端全量：152/152 PASS，26.392 秒。
- 前端 Vitest：51/51 PASS，5/5 suites。
- TypeScript：PASS。
- 生产构建：PASS，23 modules。
- OpenAPI/B 共享契约：PASS。
- 前端 wire/evidence schema：PASS。
- C LossResult schema：PASS。
- B 真实 HTTP：PASS；模型调用 0；重启、断连、幂等、账本、人审全部通过。
- 核心浏览器：737 checks PASS，18 screenshots，真实 B HTTP，模型调用 0，支付调用 0。
- Stage04：117 checks PASS，`errors=[]`，所有篡改样例被拒绝。
- 最终固定案例：4/4 runner 完成，成本均 0，模型调用 0，正式计数均 false。

## 证据目录

- HTTP：`artifacts/integration_20261015/regression-http/`
- 最终核心浏览器：`artifacts/pro_bd_sprint/05/integration-final-browser-core-20261015/`
- 最终 Stage04：`artifacts/pro_bd_sprint/05/integration-final-stage04-20261015/`
- 最终固定案例：`artifacts/c_l0/runs/integration-fixed-a-cases-20261015-202215/`

## 未修改

- 未重构前端。
- 未改保险产品参数或商业保费公式。
- 未改私有 Gold、留出答案、旧数据库或历史证据。
- 未启动付费/真实模型，未运行正式实验，未进入十万订单抽样。
