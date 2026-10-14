# 接收与运行指南（新成员 / 新机器入口）

本文件合并了原 `README_RECEIVE.md` 与 `GIT_HANDOFF_README.md`（两份原件已归档，见 `docs/README.md`「归档登记」），是当前**唯一**的安装、检查与启动说明。

## 0. 克隆仓库与选分支

```bash
git clone https://github.com/violetsnowl/AgentShield.git
cd AgentShield
git switch <你的分支>        # 分支表见 CONTRIBUTING.md（例如 feature/c-agent-evaluation）
```

> 历史说明：2026-10-13 之前项目以 ZIP 交付、用逐文件 SHA-256 清单核验；旧的交付清单存档在 `docs/archive/delivery_manifests/`。现在以 Git 仓库为准。

## 1. 环境要求（2026-10 实测）

- Windows 11（或等价受支持环境）；浏览器检查使用已安装的 **Microsoft Edge**（不会自动下载）。
- Python 3.13；Node.js 24.21.0；npm 11.19.0（B/D 环境为 3.13.1；C 的机器为 3.13.2，属正常差异）。
- 精确依赖已锁定：`requirements.lock`、`frontend/package-lock.json`。**不要**在首次接收时自动升级依赖。

## 2. 安装

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock
.\\.venv\\Scripts\\python.exe -m pip check
npm.cmd --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

- 若 pip 下载失败（曾出现 PyPI TLS EOF），**保留日志、不要关闭 TLS 校验或换未锁定版本**，换网络后重试。
- `.venv/`、`node_modules/`、`var/`（运行数据库）都不会入库；按上面命令在本机生成。

## 3. 完整检查（逐条看退出码，不要只看最后一条）

```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmmss
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
.\\.venv\\Scripts\\python.exe -m scripts.export_contracts --with-openapi --check
.\\.venv\\Scripts\\python.exe -m scripts.export_frontend_contract --check
.\\.venv\\Scripts\\python.exe -m evaluator.export_schema --check
.\\.venv\\Scripts\\python.exe -m scripts.run_http_checks --output-dir "artifacts/local-http-$stamp"
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\\.venv\\Scripts\\python.exe -m scripts.run_workbench_checks --output-dir "artifacts/local-browser-$stamp"
.\\.venv\\Scripts\\python.exe -m scripts.run_workbench_checks --suite stage04 --output-dir "artifacts/local-replay-$stamp"
```

- 各命令使用自己的隔离临时库；**无需**模型或真实支付。
- 计数随分支变化（2026-10-13 集成版参考：后端 115 项、前端 42 项、核心浏览器 419 条、异常/回放 101 条；2026-10-14 的 B 分支为 125/42/419+21/101）。**计数是 QA 断言条数，不是正式样本数。**
- 输出目录必须全新（脚本会拒绝覆盖历史证据）。
- 部分 Windows 沙箱会阻断 Python 的 loopback/子进程；请在允许本机 loopback 的终端运行，不要通过删断言或放宽安全设置绕过。
- 想跑一次 Mock 工程闭环（自动启动隔离 B，不调收费模型）：

```powershell
.\\.venv\\Scripts\\python.exe -m experiments.run_dev --plan experiments/plans/j1_mock.json
# 结果写入新的 artifacts/c_l0/runs/<批次>；核对：python -m experiments.check_j1 --batch <批次路径>
```

## 4. 启动前端工作台

```powershell
npm.cmd --prefix frontend run build
.\\.venv\\Scripts\\python.exe -m scripts.run_workbench --db var/local-workbench.sqlite3 --port 8810 --seed-development
```

- 启动器会自动打开一次带临时观察授权的页面；浏览器只持有受限的 HttpOnly 观察者 cookie，**B 管理凭据不会进入前端**。
- 不要手输裸地址 `http://127.0.0.1:8810`（无授权会显示未授权）；`--no-open` 不给普通浏览器数据访问权。
- `--seed-development` 仅在该库为空时写入两个开发脚本样例（333 分 / 250 分模拟退款），重启不追加。
- Ctrl+C 停止 B 与观察者两个服务；只关网页不会停服务。
- 界面操作、四区说明、导入回放细节见 `docs/manuals/FRONTEND_USER_MANUAL.md`。

## 5. 导入回放样例（schema 1/2/3）

工作台“导入回放”可选用仓库内开发证据（不上传、不执行工具）：

- `contracts/fixture_v2_evidence_example.json`（schema 3）
- `artifacts/b_bootstrap/http_smoke/evidence_sample.json`（schema 1）
- `artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json`（schema 2）

## 6. 接收回执（新成员在 PR 或消息里记录）

接收人 / 日期 / 机器与操作系统 / Python・Node・依赖版本 / 所选分支与提交号 / 各命令与退出码 / 遇到的问题 / 接受范围与保留意见。

**注意**：成功的自测不能替代 A/C 的业务与消费者签收；签收单在 `docs/handoff/` 对应清单中填写。

## 7. 附录说明

- 2026-10-13 集成工作区的完整记录（INTEGRATION_REPORT / 接口矩阵 / 变更清单）**未随仓库分发**，存档于制作方本地工作区；工作台“集成结果”视图读取的是仓库内的 `artifacts/c_l0/runs` 批次。
- `scripts/verify_delivery.py` 等旧交付核对脚本针对历史 ZIP 包，不作为当前接收命令。
- 安全边界：所有服务仅 loopback；密钥、令牌、数据库不入库；成效以各阶段 `artifacts/` 实测记录为准。
