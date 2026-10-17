# 文档系统：索引与规范

本文件是 AgentShield 全项目文档的**唯一索引**。找信息先看这里；新增、移动、改名文档前，先读本文件的「维护规则」。

## 一、目录规范（每类内容住哪）

| 位置 | 放什么 |
|---|---|
| `README.md`（根） | 项目门面：是什么、现在到哪、快速开始 |
| `NEXT_STEPS.md`（根） | **当前停止点与下一步**（全项目唯一“状态真源”，不堆历史） |
| `CONTRIBUTING.md`（根） | Git 协作规范：分支、提交格式、PR 规则、禁区 |
| `AgentShield_v1.2_Plan.md`（根） | **当前生效的计划书**（V1.2 工作基线；历史 V1.1 包在 `docs/spec/`） |
| `docs/setup/` | 接收、环境安装、检查命令、启动 |
| `docs/manuals/` | 使用手册（操作说明） |
| `docs/modules/` | 各模块的当前说明（如 B 交易底座） |
| `docs/handoff/` | 角色间交接、签收清单、回执、请求 |
| `docs/decisions/` | 接口/边界决策记录（按版本留存） |
| `docs/business/` | 业务规则、精算候选、业务审查记录 |
| `docs/validation/` | 验收记录（N/Q/R 项实测矩阵与复现说明） |
| `docs/migrations/` | 数据库迁移说明 |
| `docs/spec/` | 计划书历史版本与角色卡（V1.1 包；当前版计划书在根目录） |
| `docs/audit/` | 历史独立复核包（按日期目录） |
| `docs/archive/` | 已归档文档（不再维护；**保留原样**，见该目录 README） |
| `artifacts/` | 实验证据与结果（按批次；仅白名单路径入库） |
| `.impeccable/` | D 线设计流程档案（方向契约、决策草图、完工审查截图/报告；随 D 线维护） |
| `frontend/README.md` | 工作台构建/启动说明（跟着代码走） |

## 二、命名规范

1. **角色与缩写保持大写**：`A` `B` `C` `D` `BD` `BC` `L0/L1` `C1` `J1` `v0.1`。
2. **普通词小写**，词间用 `_`；不做纯大小写改名（Windows 与 Linux 对大小写不友好）。
3. 交接类：`<from>_to_<to>[_<类型>].md`，类型词表：`handoff / checklist / receipt / requests / results / state`。
   例：`BD_to_A_checklist.md`、`C_receipt_bc-0.3.md`、`C_to_A_B_D_requests.md`。
4. 决策类：`<主题>_v<版本>.md`。例：`BC_contract_v0.3.md`。
5. 日期只用于归档与批次：ISO 格式（`2026-10-14`）。
6. 新增文档一律用 ASCII 文件名；历史中文名文件已归档、不再新增。
7. 验收类：`<范围>_acceptance.md`。例：`N01-N16_acceptance.md`。

## 三、维护规则

- 被取代的文档**不删除**：移入 `docs/archive/`，并在本文件「归档登记」表登记（旧位置 → 现位置 → 替代文档）。
- 移动/改名任何文档，必须同步更新：① 本索引；② 所有引用它的文档（用搜索确认）。
- 归档文档内容保持原样（含当时的旧路径引用）；对应关系以「归档登记」表为准。
- 实验证据（`artifacts/`）与审计记录（`docs/audit/`）不得改写。

## 四、归档登记（2026-10-14 整理）

| 旧位置（原引用名） | 现位置 | 替代文档 |
|---|---|---|
| `AgentShield_v1.1_Plan(1).md`（根） | 已删除（与 spec 版完全同哈希的重复副本） | `docs/spec/AgentShield_v1.1_Package/AgentShield_v1.1_Plan.md` |
| `00_先读我_C交付说明.md`（根） | `docs/archive/00_先读我_C交付说明.md` | `docs/handoff/C_L0_RESULTS.md`、`docs/setup/RECEIVE_AND_RUN.md` |
| `README_START_HERE.md`（根） | `docs/archive/README_START_HERE.md` | 根 `README.md`、`docs/spec/` |
| `README_RECEIVE.md`（根） | `docs/archive/README_RECEIVE.md` | `docs/setup/RECEIVE_AND_RUN.md` |
| `GIT_HANDOFF_README.md`（根） | `docs/archive/GIT_HANDOFF_README.md` | `docs/setup/RECEIVE_AND_RUN.md`（环境/检查/启动内容已并入） |
| `README_B.md`（根） | `docs/modules/B_sandbox_backend.md` | 自身续用（文件继续维护） |
| `GIT_COLLABORATION.md`（根） | `CONTRIBUTING.md` | 自身续用（已扩写） |
| `docs/FRONTEND_USER_MANUAL.md` | `docs/manuals/FRONTEND_USER_MANUAL.md` | 自身续用 |
| `tasks/`（根整目录） | `docs/archive/tasks/` | 现行指令见 `NEXT_STEPS.md` |
| `PACKAGE_MANIFEST.json`、`C_DELIVERY_MANIFEST.json`（根） | `docs/archive/delivery_manifests/` | —（历史交付的逐文件 SHA-256 记录，仅存档） |
| `NEXT_STEPS.md` 内 2026-10-12/13 历史停止点 | `docs/archive/stop_points_2026-10-12_13.md` | `NEXT_STEPS.md`（现行停止点） |
| `NEXT_STEPS.md` 内 2026-10-14 版 | `docs/archive/stop_points_2026-10-14.md` | `NEXT_STEPS.md`（现行停止点） |

## 五、现行文档清单（每份一句话）

**根目录**
- `README.md` — 项目门面与导航。
- `NEXT_STEPS.md` — 当前停止点、在途分支、P0/P1 清单、禁止事项。
- `CONTRIBUTING.md` — 分支表、提交格式、PR 规则、合并顺序。
- `AgentShield_v1.2_Plan.md` — V1.2 计划书（工作基线，2026-10-14 确认入库）。
- `PRODUCT.md` — 产品档案（impeccable：用户、使命、定位、约束、品牌承诺）。
- `DESIGN.md` — 视觉设计系统定稿（导视系统：令牌 frontmatter＋八节规范；侧车 `.impeccable/design.json`）。

**docs/setup/**
- `RECEIVE_AND_RUN.md` — 克隆、环境安装、完整检查命令、启动工作台、接收回执要素。

**docs/manuals/**
- `FRONTEND_USER_MANUAL.md` — 工作台操作手册（启动、演示三页结构、演示记录选择器、回放与开发工具）。

**docs/modules/**
- `B_sandbox_backend.md` — B 交易底座：七工具、账本/幂等、迁移、证据契约（原 README_B）。

**docs/handoff/**
- `BD_CURRENT_STATE.md` — BD 侧交接状态（阶段05 收口 + 10-13 集成增补）。
- `BD_to_A_C.md` — BD→A/C 联合交接（跨实例导出/回放路径、最小语义需求）。
- `BD_to_A_CHECKLIST.md` — 给 A 的业务与研究合同接收清单（待 A 签收）。
- `BD_to_C_CHECKLIST.md` — 给 C 的沙箱与证据接收清单（C 已出接收记录）。
- `B_to_C.md` — B→C 接入交接（工具、幂等、证据细节）。
- `C_L0_RESULTS.md` — C 的 L0 结果（J1/J2、核验器、运行清单）。
- `C_receipt_bc-0.3.md` — C 对 bc-0.3 的接收记录。
- `C_to_A_B_D_requests.md` — C 对 A/B/D 的输入请求（义务定义、预算等）。
- `A_BSCALE_AUTOGOLD_TO_C_D.md` — A→C/D：B-SCALE 动态模拟授权自动 Gold（开发候选）交接（生成器用法、C 接入流程、首案公开身份、边界与测试）。
- `REAL_MODE_INTERFACE_DRAFT_2026-10-17.md` — 「真实 Agent 实测」模式接口结构草案（待与 C/A 对齐；含待确认问题清单，未接通前保持禁用）。

**docs/decisions/**
- `BC_contract_v0.1/0.2/0.3.md` — B/C 接口契约演进（当前 bc-0.3-candidate）。
- `BD_display_v0.2.md` — 展示边界候选（bd-display-0.2）。
- `BD_observer_v0.1.md` — 观察者适配（observer-0.1-candidate）。
- `IA_V3_case_display_names.md` — IA v3 案例中文显示名映射（公开业务事实，无答案暗示）。
- `IA_V3_navigation.md` — IA v3 三页导航 / 单一运行选择器 / 深链接 / 护栏决策（批C）。
- `UI_DEMO_REDESIGN_2026-10-16.md` — 演示 UI 重构与规范豁免（面向评委的极简三页；含 A/B/C 测试映射与退役清单；已随主仓集成提交 `825378e` 进入 main）。
- `PAGE1_RANDOM_SAMPLING_2026-10-16.md` — 第一页「随机抽样式 Agent 测试」交互重构（UI 结构、安全接口设计草案、B-SCALE→可执行案例缺口清单、拆分交付状态；已随本批合并至 main）。
- `STABILITY_MODES_2026-10-17.md` — 稳定批次与双模式（轮询回填自我取消等三根因取证与修复、批次持久化恢复、真实/演示双模式与样本外推三态、验证数字）。

**docs/business/**
- `business_policy_A_candidate.md` — A0 业务规则候选与决策表（待双签）。
- `BD_A_review_v0.1.md` — B/D→A 的业务审查（未签收）。
- `QuoteResult_A_v0.1_candidate.md` — A 的 QuoteResult 候选接口说明。
- `engineering_*.json` — 工程算例/输入（合成，非真实数据）。
- `A0_RECEIPT.md`、`A0_patch/` — A0 首轮交付回执与补丁说明（历史）。

**docs/migrations/** — `B_002_human_reviews.md`、`B_003_session_cases.md`。

**docs/validation/**
- `N01-N16_acceptance.md` — 前端 N 项验收矩阵（D 线，批B：批A 改动 `bd5546f`/`6e83d01` 的自动化证据；批C（IA v3）行已同步新检查名）。
- `IA_V3_test_migration_map.md` — IA v3 测试迁移映射（旧检查 → 新检查名/进入路径；行为断言零删除）。
- `UI_ROUND_2026-10-16.md` — UI-first 收口轮交付记录（紧凑运行条、三页体验收口、Core vs Plus 对比区；含修改清单、验证数字与遗留项）。
- `REAL_RUN_IMPORT_00069697_20261017.md` — 首条真实 DeepSeek 运行导入与验收（导入位置、读取器复验、真实批次选择与演示分离、遮蔽测试、第三页待 A 数据清单）。

**docs/spec/AgentShield_v1.1_Package/**（历史） — 计划书 V1.1（`.md`/`.docx`）、`delivery_levels_v1.1.json`、`role_cards/`（A/B/C/D 四份任务卡）。

**docs/audit/** — 三次独立复核包（B_Audit、Stage03、Stage04，均为历史记录）。

**docs/archive/** — 见该目录 `README.md` 索引。

## 六、在途（在分支上、尚未合入 main 的文档）

- `feature/bd-integration`：**历史批次已全部并入 main**（旧批次随主仓集成提交 `825378e`；「第一页随机抽样重构」feat `e6275dc` 与文档提交已推送并合并，实时值以 `git ls-remote` 为准）。D 线设计档案（`PRODUCT.md`、`DESIGN.md`、`frontend/design/`、`.impeccable/`）已随 2026-10-15 合并进入 main。
- `feature/c-agent-evaluation`：`docs/handoff/C_C1_CHECKPOINT.md`、`C_C1_to_A/B/D.md`。
- `feature/a-gold-actuarial`：待 A 开工，暂无文档。
- （bd · 已推送）2026-10-16 演示 UI 重构批：`docs/decisions/UI_DEMO_REDESIGN_2026-10-16.md`、`docs/manuals/FRONTEND_USER_MANUAL.md` 与 `frontend/README.md` 同步修订、`frontend/src/{App.tsx,style.css,riskMetrics.ts}` 重排、四份前端/回归测试改写；**main 未合并，等待用户验收**。
- （bd · 已推送并合入 main）2026-10-16 深夜「第一页随机抽样重构」：`docs/decisions/PAGE1_RANDOM_SAMPLING_2026-10-16.md`、`frontend/src/{App.tsx,style.css,caseNames.ts}`、`frontend/src/data/{runnerConfigs.ts,runner_configs.json}`、`frontend/tests/{browser.mjs,runnerConfigs.test.ts}`；feat `e6275dc`（文档提交紧随其后），基线=主仓集成提交 `825378e`（merge `746f214`）。
- （research-risk-contracts · 本轮）2026-10-17「稳定批次与双模式」：`docs/decisions/STABILITY_MODES_2026-10-17.md`、`docs/handoff/REAL_MODE_INTERFACE_DRAFT_2026-10-17.md`、`frontend/src/{App.tsx,routing.ts,riskMetrics.ts,style.css,realMode.ts}`、`frontend/tests/{browser.mjs,realMode.test.ts,routing.test.ts,riskMetrics.test.ts}`、`workbench/bscale_batches.py`、`tests/test_bscale_batches.py`、`docs/manuals/FRONTEND_USER_MANUAL.md` 同步修订。

> 合并后请把新增文档登入本索引（维护规则第 2 条）。
