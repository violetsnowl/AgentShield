# AgentShield ABCD 本地集成接收入口（2026-10-13）

当前工作区已在原 BD 阶段 05 基线上合入经清单校验的 A/C L0 交付，并完成 B→C→A 候选链与 D 展示联调。先读 `artifacts/integration_abcd/INTEGRATION_REPORT.md`、`INTERFACE_MATRIX.md` 和 `INTEGRATION_CHANGELOG.md`。本轮没有 Git 提交或远程操作；工作区也不是 Git 仓库，因此接收方应按检查点清单审核本地文件。

启动方式见 `frontend/README.md`。当前实测后端 115 项、前端 42 项、核心浏览器 419 条、异常/回放浏览器 101 条均通过。A/C 交付仍为候选接口与非正式开发证据；正式 Gold、56 次 Agent 实验、28 次规则基线、正式保险定价和第二台机器接收均未完成。

下方阶段 05 精简包说明保留为历史接收记录，不代表本次 ABCD 集成包已经重新制作。

---

# AgentShield BD 阶段 05 接收入口

2026-10-12。这是同学接收用的精简源码包，不是正式实验数据或全量历史审计副本。先读 `docs/handoff/BD_CURRENT_STATE.md`；A、C 分别按 `BD_to_A_CHECKLIST.md`、`BD_to_C_CHECKLIST.md` 接收。所有签收仍 pending，BD 的自测不能代签。

## 解压与完整性

将 ZIP 解压到一个**全新目录**，不要覆盖已有项目或数据库。ZIP 根目录直接包含本文件、api、frontend、contracts 等。旁边的 `*_manifest.json` 给出 ZIP SHA-256；内置 `PACKAGE_MANIFEST.json` 列出载荷逐文件哈希。可用 `Get-FileHash <ZIP路径> -Algorithm SHA256` 比较外置清单，并在解压后的根目录执行：

```powershell
python -c "import hashlib,json,pathlib; r=pathlib.Path('.'); m=json.loads((r/'PACKAGE_MANIFEST.json').read_text('utf-8')); assert all(hashlib.sha256((r/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in m['files']); print('payload hashes match')"
```

包不含 `.venv`、node_modules、dist、数据库、管理员令牌、会话凭据、模型/API 密钥、正式留出答案或任何嵌套 ZIP。只含公开工程模板及最小历史回归样例；正式 Gold 未读取或打包。完整历史和全部截图留在原项目。各历史 RESULTS 中的旧 ZIP/完整截图/完整清单路径可能不在精简包中；它们是历史记录，不是本包缺少运行依赖。`verify_delivery`、`verify_workbench_delivery`、`verify_stage04_delivery` 等旧全量历史核对脚本需原项目，不作为精简包接收命令。

## 安装与启动（Windows / 本机 loopback）

本轮锁定环境：Python 3.13.1、Node 24.21.0、npm 11.19.0，Edge 155.0.4283.45；依赖见 requirements.lock / frontend/package-lock.json。不要用自动升级或放宽版本解决安装失败。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --timeout 15 --retries 1 -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Python 安装失败，保留日志；不要忽略错误继续' }
npm.cmd --prefix frontend ci --ignore-scripts --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'npm 安装失败，保留日志' }
.\.venv\Scripts\python.exe artifacts/pro_bd_sprint/05/support/check_environment.py
npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw '构建失败' }
.\.venv\Scripts\python.exe -m scripts.run_workbench --seed-development
```

启动器自动打开一次临时观察授权页面；B 管理凭据仅保存在服务端内存，不需粘贴到浏览器。默认 `http://127.0.0.1:8810`、新库 `var/workbench.sqlite3`；Ctrl+C 关闭两服务。首次在空观察租户播种两份明确标记的 scripted_test 开发运行（333 / 250 分模拟退款、工单、拒绝、原键重放），重启不追加样例。裸地址不授予读取权限；`--no-open` 不给浏览器配对。不要将旧库当演示库，不改成公网地址。

本轮新目录的 npm 缓存安装、构建已通过；**全新 Python 安装遇到 PyPI TLS EOF 失败**，后端/启动验证明确复用了原项目已核对锁版本的 Python 虚拟环境。没有关闭 TLS 校验、换未核对版本或打包原环境。这不是完整独立依赖安装通过；接收人仍需执行上面的安装并保留结果。

## 接收检查（都在包根目录执行）

```powershell
$bdReceiveStamp = Get-Date -Format yyyyMMdd-HHmmss
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.run_http_checks --output-dir "artifacts/pro_bd_sprint/05/receive-http-$bdReceiveStamp"
.\.venv\Scripts\python.exe -m scripts.export_contracts --with-openapi --check
.\.venv\Scripts\python.exe -m scripts.export_frontend_contract --check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --output-dir "artifacts/pro_bd_sprint/05/receive-browser-$bdReceiveStamp"
.\.venv\Scripts\python.exe -m scripts.run_workbench_checks --suite stage04 --output-dir "artifacts/pro_bd_sprint/05/receive-integration-$bdReceiveStamp"
```

每条命令分别检查 `$LASTEXITCODE`；不能以最后一条的退出码代替全套。后端当前 65 项、前端 41 项，浏览器 341 / 91 条细粒度检查，计数不是正式样本数。测试用独占临时库；无需模型或支付。浏览器检查使用已安装 Edge，不会自动下载浏览器。需要允许本机 loopback/子进程的终端；本轮沙箱 EPERM/启动超时记录仍保留。

页面加载后可“导入回放”选择 `contracts/fixture_v2_evidence_example.json`（schema 3）、`artifacts/b_bootstrap/http_smoke/evidence_sample.json`（schema 1）、`artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json`（schema 2）。这些均为开发证据，不是正式任务。断网后导入不上传、不调用工具；旧映射/哈希缺失继续未知。浏览器 hash 未复核、文件未签名，内部一致不等于业务合法或真实模型来源。冷启动/刷新离线尚不支持，A 离线理算尚未接入。

## 接收回执（本人填写）

接收人：待填；日期：待填；机器/操作系统：待填；Python/Node/Edge/依赖：待填；ZIP SHA-256：待填；命令/退出码/日志：待填；模板/回放核对：待填；问题：待填；接受范围与保留意见：待填。

本次执行者是当前用户会话中的 Codex；没有换机器，也没有 A/C/舍友实际操作。成功适配 A/C、真实 Agent、保险计算、第二机复现与全队 J2/L1 均未验收。阶段 05 到此收口，不自动扩功能。
