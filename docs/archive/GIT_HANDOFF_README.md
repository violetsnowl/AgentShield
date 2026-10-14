# AgentShield V1.1 ABCD Git 交接说明

本交接包来自 2026-10-14 的最新统一工作区，用于由接收组员建立一个新的 Git 仓库并完成初始提交。包内没有 `.git`，制作方没有执行 `git init`、提交、分支或远程操作。

## 当前工程状态

- **A（精算/保险）**：`actuarial/` 提供 A0 损失到赔付的工程计算与 QuoteResult 候选契约。
- **B（企业沙箱）**：`api/`、`sandbox/`、`migrations/` 提供 bc-0.3-candidate 七工具、SQLite 事务、幂等、证据与人工工单。
- **C（Agent/评测）**：`runners/`、`evaluator/`、`experiments/` 提供 Mock/兼容适配器、统一循环、独立 LossResult 核验和开发批次工具。
- **D（工作台）**：`frontend/`、`workbench/` 提供 React + TypeScript + Vite 四区工作台和受控本机观察者。

B→C→A0→D 的开发工程链已经接通。包内保留两组明确标识的非模型 Mock 演示数据（`j1-mock-20261013-201356` 与 `j1-mock-20261013-234140`）、后端/前端回归直接引用的 schema 1/2 公开证据 fixture，以及一条用于验证 `observed_agent_execution` 来源标签的最小历史开发证据子集。该子集只含经扫描的 manifest/evidence/loss/claim；manifest 已在打包副本中移除 provider request IDs、逐调用明细和非必要运行元数据，未纳入 attempts、transcript、提示词、私有推理或原始模型响应。所有这些材料均为非正式开发证据，不是 Gold、正式损失或商业报价。

## 推荐环境

- Windows 11 或等价的受支持开发环境
- Python 3.13.1
- Node.js 24.21.0
- npm 11.19.0
- 浏览器自动化验证使用已安装的 Microsoft Edge

Python 精确依赖见 `requirements.lock`，前端精确依赖见 `frontend/package-lock.json`。不要在首次接收时自动升级依赖。

## 在新机器恢复环境

在解压后的项目根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

`.env.example` 与 `configs/runner/env.example` 只有空值或关闭付费开关的模板。不要把真实 API Key、管理员令牌、session token 或 Cookie 提交到 Git。

## 完整检查

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.export_contracts --with-openapi --check
.\.venv\Scripts\python.exe -m scripts.export_frontend_contract --check
.\.venv\Scripts\python.exe -m evaluator.export_schema --check
.\.venv\Scripts\python.exe -m scripts.run_http_checks --output-dir artifacts/local-http-check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

运行 Mock 工程闭环：

```powershell
.\.venv\Scripts\python.exe -m experiments.run_dev --plan experiments/plans/j1_mock.json
```

命令会在本地 `artifacts/c_l0/runs/` 下产生一个新的非正式 Mock 批次，不调用收费模型或真实支付。用输出中的批次路径执行 `python -m experiments.check_j1 --batch <批次路径>`。

如需浏览器回归：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks `
  --output-dir artifacts/integration_abcd/git-handoff-browser `
  --phase final --suite stage03
```

## 启动本地工作台

```powershell
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench `
  --db var/local-workbench.sqlite3 `
  --port 8810 `
  --seed-development
```

启动器会在 loopback 启动 B 与观察者，并打开一次带临时配对授权的页面。浏览器只持有受限的 HttpOnly 观察者 Cookie；B 管理凭据不会进入前端。按 `Ctrl+C` 停止服务。

## 单位核对

所有资金 Schema 使用整数分字段，例如 `net_loss_cents`。E03 的源码和测试是：

- `net_loss_cents = 52000`，即 **520 元**；
- `payout_cents = 42000`，即 **420 元**。

因此“520 分/420 分”是错误表述。测试与 Schema 的实际单位是分，数值 52000/42000 换算后是 520 元/420 元。

## 尚未完成

- 正式业务 Gold 审定和私有留出管理；
- B 受控随机案例生成器的最终交付；
- C 的正式 56 次 Agent 批次、28 次规则基线和正式成本预试；
- A 的正式损失分析、保险研究与商业报价；
- 最终 L1 联合验收和第二台机器/第二位操作者签收。

## 交付包没有包含

`.venv`、`node_modules`、`frontend/dist`、数据库及 WAL/SHM、`.env`、密钥/令牌/Cookie、历史 ZIP、内部回退检查点、旧审计包、正式 Gold/留出答案、真实模型 attempts/transcript/提示词/原始响应和机器日志。主工程中的历史材料没有被删除，只是没有进入这个 Git 源码包。

## 验证 ZIP

交付目录中的 `AgentShield_V1.1_ABCD_Git_Source_manifest.json` 记录 ZIP SHA-256、文件数、总大小和逐文件 SHA-256。先验证 ZIP 总哈希，再解压到空目录，逐项比较清单。制作方的独立解压结果见同目录 `REPRODUCTION_REPORT.md`。

