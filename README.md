# AgentShield V1.1 — 企业 AI 智能体执行风险评测与情景保险定价系统

「智能＋保险 2026」参赛项目（提交截止 2026-10-18，内部以 10/17 提交为目标）。
用带明确规则的电商售后退款沙箱，让受控 AI Agent 真实执行任务；记录工具调用与账本证据，由独立核验器计算经济损失，再按研究保险合同做情景赔款成本计算与前端展示。

**主链路**：模拟企业沙箱 → 独立 Agent 执行 → 结构化证据 → 独立损失核验 → 合同理算 → 分类比较与情景成本 → 前端工作台。

---

## 现在到哪一步（2026-10-14）

- 工程链路已打通：B 沙箱（七工具，`bc-0.3-candidate`）、C 运行器与独立核验（L0 完成）、A0 精算与业务候选、D 工作台（含 A/C 候选结果的只读展示与精确 session/episode 追溯）。
- `main` 已合入 ABCD 集成版；工作分支在途：
  - `feature/bd-integration` — B 案例生成器 + 40 个公开候选案例（fixture v2）；B 侧基本完成，D 前端工作在此分支继续。
  - `feature/c-agent-evaluation` — C1-1 规则基线 + 正式实验闸门 + 预算申请。
  - `feature/a-gold-actuarial` — 已建，A 侧待开工。
- **正式 56 次实验尚未开始**：等任务/Gold 冻结、决策表双签、预算确认等（清单见 `NEXT_STEPS.md`）。
- 所有现存运行均为开发运行（`counts_as_formal_run=false`）；无商业报价（`commercial_quote=false`）。

## 快速开始

| 你要做的事 | 看这里 |
|---|---|
| 新机器安装、跑检查、启动 | `docs/setup/RECEIVE_AND_RUN.md` |
| 用前端工作台 | `docs/manuals/FRONTEND_USER_MANUAL.md`（构建/启动细节见 `frontend/README.md`） |
| 找某份文档 / 了解文档规范 | `docs/README.md`（全库文档索引） |
| Git 协作（分支、PR、提交格式） | `CONTRIBUTING.md` |
| 当前停止点与下一步 | `NEXT_STEPS.md` |
| 计划书与角色卡（全队规范） | `docs/spec/AgentShield_v1.1_Package/` |
| 历史归档（旧包说明、旧停止点、交付清单） | `docs/archive/` |

## 团队与分工（计划书第 12 节）

| 角色 | 主责 |
|---|---|
| A | 业务规则、任务与 Gold、保险研究合同与计算、论文论证 |
| B | 沙箱、交易、HTTP 与接口契约（`contracts/` 为唯一来源） |
| C | Agent 运行器、独立损失核验、执行实验与预算 |
| D | 前端工作台、联调验收、材料整合与发布 |

> B 与 D 由同组两位成员联合推进（简称 “BD”）。具体人选以计划书角色表为准。

## 硬性边界（持续有效）

- 付费模型默认关闭（`enable_paid_runs=false`、`max_cost=0`）；**未获负责人批准不启动正式实验**；不读取正式留出 Gold。
- 不接真实支付、不公网部署、不上传；浏览器不持有管理员令牌。
- 不改写历史证据；失败记录原样保留；“已测试 / 已实现 / 已审核”三态分开，签收不得代签。
- 密钥、令牌、数据库、`.env` 一律不入库（见 `.gitignore`）。

## 仓库结构（速览）

- 代码：`api/` `sandbox/` `contracts/` `migrations/`（B）・`runners/` `evaluator/` `experiments/`（C）・`actuarial/` `configs/insurance/`（A）・`frontend/` `workbench/`（D）
- 证据与结果：`artifacts/`（按批次存放；仅白名单路径入库）
- 文档：`docs/`（索引见 `docs/README.md`）
