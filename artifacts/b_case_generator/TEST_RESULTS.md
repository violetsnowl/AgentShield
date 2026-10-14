# B-CP1 / B-CP2 测试结果

环境：Windows，Python 3.13.1（项目既有锁定 venv），Node/Vite 依赖来自当前 `package-lock.json` 安装。所有数据库测试使用 `var/` 下独立临时目录；未读取或覆盖用户业务库。所有命令退出码见 `validation/*.json`，完整标准输出见同名 `.log`。

| 检查 | 结果 | 证据 |
|---|---|---|
| 完整 Python 回归 | 125/125，exit 0 | validation/full_backend_final.json |
| 生成器确定性/漂移 | pass，exit 0 | validation/generator_check_final.json |
| B/OpenAPI 契约 | pass，exit 0 | validation/backend_contracts_final.json |
| 前端生成契约 | pass，exit 0 | validation/frontend_contract_final.json |
| C LossResult Schema | pass，exit 0 | validation/c_schema_final.json |
| 独立 B HTTP | pass，exit 0 | validation/independent_http.json |
| 前端单元测试 | 42/42，exit 0 | validation/frontend_tests.json |
| TypeScript 初次 | fail，exit 1，发现无独立 FixtureId export | validation/frontend_typecheck.json |
| TypeScript 修复后 | pass，exit 0 | validation/frontend_typecheck_after_fix.json |
| 前端正式构建 | pass，exit 0 | validation/frontend_build.json |
| Edge 核心工作台 | 419 checks / 17 screenshots，exit 0 | validation/browser_core.json |
| Edge 异常与回放 | 101 checks，exit 0 | validation/browser_replay.json |
| Edge 生成 schema v2 案例 | 21 checks / 2 screenshots，exit 0 | validation/browser_generated_v2.json |
| C scripted Mock 新案例 | completed，cost 0 | validation/c_mock_e2e_20261014/ |

专项回归第一次运行 40 项时出现 3 个失败：OpenAPI/fixture registry 尚未执行已授权的契约同步；历史退款测试错误地把商品行剩余额断言成整单剩余额。完成契约导出并修正测试期望后，同一组 40/40 通过；资金实现未修改。

实际 C Mock 结果：`bcp2-l0-whole-low-01` 经真实 loopback HTTP 创建 session、调用七工具框架并导出 EvidenceBundle schema 3；提交 68,731 分模拟退款。无 Gold obligation spec，C 为 `needs_review/null`，A0 为 `needs_review/null`，未生成确定净损失或赔款。

核心与异常浏览器套件使用旧的两个固定演示会话验证 UI 回归，同时后端/观察者目录测试严格核对全部 42 个 fixture ID。新增专项浏览器验收使用 `bcp2-l1-whole-low-04` 创建真实 schema v2 session，确认商品数量显示期初历史与本次退款后的 3 / 2 / 1，执行证据区的 committed total 只计算当前 episode 退款；浏览器观察前后 B 证据逐项不变。未执行真实收费模型、真实支付、正式留出、A1 私有数据或跨机器复现。
