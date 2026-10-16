# MERGE_LOG

## 实际过程

1. 在新目录 clone GitHub 仓库并 fetch 所有远程分支。
2. 从 `origin/main@753fe69` 创建 `integration/main-a-c-20261015`。
3. 以 `--no-ff` 本地合并 A：产生 `01fb4f7`。
4. 处理 `.gitignore` 唯一冲突，取两边规则并集；没有选择任何业务语义或资金逻辑的一方覆盖另一方。
5. 以 `--no-ff` 本地合并 C：无冲突，产生 `1464a48`。
6. 验证 main、A、C 三个远程 HEAD 均为集成 HEAD 的祖先。
7. 完成首轮完整运行后才做最小联调修复，产生 `ce3ad2b` 和 `40da1d4`。

## 冲突与处理

- `.gitignore`：机械合并安全隔离规则，已解决。
- 业务规则：没有 Git 文本冲突，但存在运行期语义冲突。A v0.2 要求区分明确更正与冲突，且相似订单/不可拆分资格不明时不得猜测；C 基线首版不足，已用 fail-closed 规则和测试修复。
- 资金逻辑：没有以“测试通过”为目的放宽。相似订单和资格不足案例均转人工且零出款。
- 共享契约：四个固定案例只以源码固定 ID、固定路径、版本和 SHA-256 注册；未开放任意 JSON、路径、URL 或上传接口。

## 安全边界

- 所有运行使用独立数据库：`var/c_runs/<batch>/b.sqlite3`、HTTP 检查目录和浏览器检查目录。
- 浏览器为 observer-only，不持有 B 凭据、不调用 B 工具。
- 没有删除或覆盖旧数据库、旧证据、旧错误批次。
- 没有 Push、force、rebase 或远程分支写入。

## 环境说明

新目录创建 `.venv` 时 Windows Python 3.13 的 `ensurepip` 失败。为不中断验收，使用用户已有只读依赖环境 `..\agentshield\.venv\Scripts\python.exe`；其 FastAPI/Pydantic/Uvicorn/HTTPX/jsonschema 版本与锁文件匹配，`pip check` 通过。代码、数据库和测试产物仍全部位于独立工作树。此环境复现问题列入交接，不伪装为已修复。
