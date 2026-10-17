# AgentShield 最终代码交接

## 版本

- 远程目标分支：`feature/research-risk-contracts`（不修改 `main`）。
- 本地验收时的 B-SCALE 网页一键 100 条检查点为 `fcb2cd0`，第二页风险测算、第三页 Core/Plus 参考保费与模拟合同检查点为 `a968cd0`，加载时序修复尝试为 `4a98607`。
- GitHub 拒绝公开原提交者邮箱，因此推送前只改写了上述未发布提交的作者/提交者邮箱元数据；文件树没有变化。远程对应检查点依次为 `c836922`、`32d8e93`、`9b0992e`。
- 交接文档提交后的最终分支 SHA 以 `git rev-parse HEAD` 为准。

## Windows 安装与启动

实测环境为 Windows 11、Python 3.13、Node.js 24.21.0、npm 11.19.0。Python 和前端依赖分别锁定在 `requirements.lock` 与 `frontend/package-lock.json`。

```powershell
git switch feature/research-risk-contracts
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend ci --ignore-scripts --no-audit --no-fund

$env:AGENTSHIELD_BSCALE_DB = 'D:\path\to\synthetic_merchant_v1.sqlite3'
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m scripts.run_workbench --db var/local-workbench.sqlite3 --port 8810 --seed-development
```

启动器会打开带临时观察授权的浏览器页面；不要手工打开无授权的裸地址。管理令牌由启动器在内存中随机生成，不应写入文件或交给前端。

## 已通过检查

- Python 后端完整单元测试：184/184 通过。
- B/OpenAPI、前端共享契约与 C Schema 检查通过；B 独立 HTTP 检查通过。
- 前端单元测试：70/70 通过；TypeScript typecheck 与正式 build 通过。
- Stage04 Edge 集成检查：1176 项断言通过；付费模型调用 0，支付调用 0。
- 网页真实 100 条批次完成；最新保存批次 `bscale-web-rule-baseline-20261017-130450-496b42` 为 93 条退款、7 条转人工、0 失败，账本全部守恒，C LossResult 与 A ClaimResult 均保持 `needs_review/null`。
- 第二页动态计算年度情景预期损失 31,746.00 元；第三页动态计算 Core 25,641.00 元、Plus 35,866.88 元，并可生成两份不同的可打印模拟合同。

## 已知问题

- 一键批次完成后，第二、三页有时仍停留在“正在汇总测试与研究情景”；刷新页面后恢复。`4a98607` 的加载时序修复尝试未彻底解决该问题。本轮按要求不再修改业务或前端逻辑。
- 历史运行目录累计较多时，旧 Stage03 全量浏览器脚本可能在 180 秒超时；当前批次页面与 Stage04 已通过。
- `frontend/dist`、运行数据库和新批次证据均被忽略；新机器必须先 build，并按下节线下接收数据。

## 必须线下传递的忽略文件

不要上传包含本地运行环境或凭据的原始批次压缩包。以下文件用受控的线下渠道按原相对目录传递：

1. B-SCALE 源数据库（启动一键随机批次所必需）：
   `D:\作业合集\大三\智能+保险\AgentShield_BSCALE_Sample_20261017\var\bscale-source-audit-20261017\var\exposure_population\synthetic_merchant_v1.sqlite3`
   大小 52,097,024 字节，SHA-256 `0DD86B3D988FBE5A878BA24F08253AEC2E2772BAED7DE3360771E11A1B79E544`。
2. 最新演示批次摘要：
   `var\bscale_authorization\bscale-web-rule-baseline-20261017-130450-496b42.json`
3. 最新演示批次 B 会话、退款与账本库：
   `var\c_runs\bscale-web-rule-baseline-20261017-130450-496b42\b.sqlite3`
4. 最新演示批次 C 核验、A 理算与逐条证据：
   `artifacts\c_l0\runs\bscale-web-rule-baseline-20261017-130450-496b42\`

`var\local-workbench.sqlite3` 或 `var\workbench.sqlite3` 仅在需要保留原机器上的临时开发会话时才线下传递；正常接收可用 `--seed-development` 新建。`.env`、API Key、管理员令牌、私有 Gold、私有留出答案不得传递或提交。
