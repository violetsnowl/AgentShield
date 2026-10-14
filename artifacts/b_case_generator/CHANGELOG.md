# B 案例生成器变更清单

## 生成器与候选

- `sandbox/case_generator.py`：确定性生成、业务校验、manifest、原子首次写入和漂移检查。
- `scripts/generate_case_candidates.py`：`--write/--check` CLI。
- `configs/case_generator/b-cp2-v1.json`：固定版本、seed、业务时间和数量。
- `sandbox/fixtures/generated/`：40 个公开候选和内容哈希登记。
- `artifacts/b_case_generator/CASE_MANIFEST.json`：分类、家族、候选划分、初态哈希和待审状态。

## 兼容与契约

- `sandbox/fixture_models.py`：DevelopmentFixture 支持 schema 1/2；TemplateItem 增加期初历史字段。
- `sandbox/fixture.py`：固定生成登记、内容哈希校验、历史退款不变量和 canonical 初态。
- `contracts/fixture_ids.py`：42 个源码固定 ID（2 个旧模板 + 40 个候选）。
- `contracts/models.py`：仅扩展 FixtureId 枚举；bc-0.3、七工具和 EvidenceBundle 3 不变。
- 重新生成 `development_fixture.schema.json`、`fixture_registry.json`、`schemas.json`、`openapi.json`。
- 同步前端生成契约和验证器；`frontend/src/App.tsx` 从 FixtureCatalog 推导 fixture_id 类型。

## 测试与联调

- `tests/test_case_generator.py`：确定性、计数/划分、schema v1/v2、守恒、不可重复退款、episode 归因、session 隔离、HTTP、C/A 未知语义和注入拒绝。
- 原测试的两模板固定断言更新为严格匹配当前源码 REGISTRY。
- `experiments/plans/bcp2_mock.json`：一个公开新候选的 C scripted Mock HTTP 计划。
- `scripts/run_bcp2_browser_check.py` 与 `frontend/tests/bcp2-browser.mjs`：生成 schema v2 案例的真实 B/观察者/Edge 只读展示验收。
- `artifacts/b_case_generator/validation/`：脱敏命令、退出码和联调证据。

## 公共接口影响

加法式变化：

1. CreateSession/FixtureMetadata 的 fixture_id enum 从 2 个扩展到 42 个源码登记 ID。
2. development fixture 文件 schema 支持 v2 期初历史字段。

保持不变：HTTP 路由、七工具请求/响应、退款金额算法、事务/账本/幂等、session/episode 隔离、EvidenceBundle schema 3、C 损失核验、A0 保险公式和数据库迁移版本。
