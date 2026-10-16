# 协作规范（Contributing）

本文件是全队 Git 协作规范（由 2026-10-14 交接包的 Git 建议升级而来）。**只讲怎么做**：项目状态见 `NEXT_STEPS.md`，文档规范见 `docs/README.md`。

## 一个主仓库

四个模块在同一个主仓库、同一条稳定 `main` 上协作。不要另建互不关联、无法原子更新接口的分仓库。

## 分支（2026-10-14 整理后）

| 分支 | 归属与用途 | 状态 |
|---|---|---|
| `main` | 唯一基准；只放“已认可”的版本 | 已含 ABCD 集成 + 文档系统整理 |
| `feature/a-gold-actuarial` | A：正式任务、Gold、精算与合同 | 已建，待开工 |
| `feature/bd-integration` | BD：B 案例库（已完成部分）+ D 前端工作 | 领先 main（B 案例生成器 / fixture v2） |
| `feature/c-agent-evaluation` | C：规则基线、正式计划、执行实验 | 领先 main（C1-1 完成，等待准入） |

- 开新工作：`git switch main && git pull && git switch -c feature/<角色>-<主题>`；一个分支只做一件事。
- 正式 Gold 与私有留出**不要**直接提交到分支，使用团队批准的受控存储与访问流程。
- 已推送的分支不要强推重写历史；用追加提交或合并。

## 提交信息格式

`<类型>(<角色>): <一句话>`；类型：`feat` / `fix` / `docs` / `test` / `chore`；角色：`a` / `b` / `c` / `d` / `bd` / `all`。

例：`feat(c): 加入确定性规则基线`、`docs(bd): 更新 NEXT_STEPS 停止点`。

- 一个提交只做一件事；测试证据（命令 + 退出码）写进提交正文或 PR 描述。
- 禁止把失败改成通过、把 unknown/null 填成结果、改写历史证据。

## Pull Request 规则

- 每个 PR 只解决一个明确范围，说明：触发条件、最终行为、接口变更、验证命令与结果。
- 修改 `contracts/`、OpenAPI、JSON Schema、`configs/insurance/` 或证据模型时，先提交**契约 PR**，并同时提供版本、迁移/兼容策略、样例和消费者测试。
- A/C 接口变更至少由生产方和消费方各一人审核；B/D 鉴权或资金路径变更需要安全复核。
- 合并前运行：后端完整测试、三项契约检查、前端 test/typecheck/build；涉及 UI 或运行链时再运行 HTTP、Mock 和浏览器检查（命令清单见 `docs/setup/RECEIVE_AND_RUN.md` 第 3 节）。
- 不将 Mock、开发运行或来源标签写成正式 Agent/Gold 成果。
- 合并方式建议 **Squash and merge**；合并后删除该功能分支（除非它还要继续用）。

## 推荐合并顺序

1. 契约、Schema、迁移和兼容测试；
2. B 的业务/证据实现；
3. C 的运行器和独立核验；
4. A 的 Gold/理赔/研究逻辑；
5. D 的展示与发布适配；
6. 全链回归和版本标记。

跨模块 PR：先固定接口，再以可独立评审的小提交实现生产方、消费方和 UI，最后合并全链测试。不要在不同分支同时静默改同一 schema 版本。

## 文档

- 新增、移动、改名文档前先读 `docs/README.md` 的规范；改动必须同步更新索引与全部引用（用搜索确认）。
- 历史文档不删除：移入 `docs/archive/` 并在索引登记。

## 仓库工程约定（易踩坑，2026-10-16 增补）

- **行尾风格是混合的**：`frontend/src/App.tsx`、`style.css`、`frontend/tests/browser.mjs`、`stage04-browser.mjs` 为 CRLF；`frontend/src/riskMetrics.ts`、`frontend/tests/riskMetrics.test.ts`、`artifacts/pro_bd_sprint/05/support/check_startup.mjs` 等为 LF。批量重写文件前先比对原文件 EOL 并保持一致；提交前用 `git diff --cached --ignore-cr-at-eol --stat` 自查——某文件行数骤降 = EOL 被整文件翻转，须转回原风格再提交。
- **gitignore 目录内的 tracked 文件**（如 `artifacts/pro_bd_sprint/05/support/check_startup.mjs`）：`git add <path>` 会被整体拒绝（提示 "paths are ignored"，同批其它文件也不入暂存）——须 `git add -f` 且单独一条命令。
- **折叠（`<details>`）改造后的浏览器检查迁移**：关闭的 details 内元素对 Playwright 不可见（click/selectOption/innerText 失效；textContent/count 不受影响）。做法：幂等 helper 先 `evaluate(node => { node.open = true; })` 展开再交互；helper 插入点须落在语句行之前，避开多行 `Promise.all([...])` 内部。
- **新增 UI 文案与既有文案重名会触发 Playwright strict-mode 冲突**（如对比表单元格 vs 卡片标题）：等待/定位改用 `getByRole('heading'|'cell'|'button', { name })` 等角色化选择器。

## 硬性禁区（与计划书一致）

- 付费模型默认关闭（`enable_paid_runs=false`、`max_cost=0`）；正式实验需负责人批准。
- 不读取正式留出 Gold；不接真实支付；不公网部署；浏览器不持有管理员令牌。
- 密钥、令牌、数据库、`.env` 不入库；提交前检查 `git status`。
- 不代签：签收单只能由本人填写。
