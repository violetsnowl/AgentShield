# B 案例生成器规范

## 固定输入与复现

权威配置为 `configs/case_generator/b-cp2-v1.json`：

- generator_version：`b-case-generator-v1`
- rules_version：`b-refund-rules-candidate-v1`
- library_id：`bcp2-public-20261014`
- seed：`agentshield-bcp2-public-seed-v1`
- business_time：固定业务时间，不取系统时钟

稳定整数由 SHA-256(generator_version | rules_version | library_id | seed | fixture_id | field) 派生。输出使用 UTF-8、键排序、两空格缩进和 LF；案例内容、登记文件、manifest 均可逐字节比较。

生成或检查：

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_case_candidates --write
.\.venv\Scripts\python.exe -m scripts.generate_case_candidates --check
```

`--write` 先在内存中生成并完成 Pydantic 与跨对象业务校验，再写临时目录；已有生成库不一致时拒绝覆盖。`--check` 不写文件，校验配置、固定 ID 集、每个 JSON 和 manifest。

## 受控注册

`contracts/fixture_ids.py` 定义固定 ID allowlist；`sandbox/fixtures/generated/registry.json` 固定每个文件路径、稳定身份和内容 SHA-256。加载器同时检查：

- ID 必须在源码 allowlist 和登记文件中。
- 路径必须位于 `sandbox/fixtures/` 下，且为登记的 JSON。
- 生成文件字节哈希必须与登记值一致。
- fixture_id/source_case_id/fixture_version 必须与登记一致。
- 结构、对象归属、确认范围、金额和余额必须通过 B 校验。

HTTP 没有注册、上传或路径接口。外部 ID、URL、相对路径和内联对象由 CreateSession 严格模型拒绝。

## fixture schema v2

schema v2 只增加商品行期初历史字段：

- `initial_refunded_quantity`
- `initial_refunded_cents`
- `initial_refund_source = pre_session_business_history`

金额采用现有累计分摊公式：`allocated_paid_cents * initial_refunded_quantity // quantity`。期初商户余额为原实付减历史退款，客户余额为历史退款，两者之和保持原实付。

历史退款是 session 前业务事实。它出现在 canonical_initial/initial_snapshot 的商品、订单及余额中，不写入本次 session 的 refunds、ledger、events。因此 C 的本 episode committed facts 只含本次 Agent 实际提交。订单初始 version 在存在历史退款时为 2，后续仍使用原 B 版本与幂等语义。

旧 schema v1 只允许零历史默认值；`dev-refund-v1/v2` 原文件不变。模板名称中的 v1/v2 与 fixture schema 版本无关。

## 输出

- 生成 fixture：`sandbox/fixtures/generated/*.json`
- 固定登记：`sandbox/fixtures/generated/registry.json`
- 审核 manifest：`artifacts/b_case_generator/CASE_MANIFEST.json`
- 导出契约：`contracts/development_fixture.schema.json`、`fixture_registry.json`、`schemas.json`、`openapi.json`
