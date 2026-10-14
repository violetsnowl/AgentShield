# ABCD 本地集成后的当前状态（2026-10-13）

> 状态提示（2026-10-14）：本文为 BD 侧交接状态记录；全项目当前状态以 `NEXT_STEPS.md` 为准。其中“当前目录仍不是 Git 仓库”等表述为当时语境。

已在阶段 05 BD 基线上合入经交付清单 404/404 校验（清单存档于 `docs/archive/delivery_manifests/`）的 A0/C L0 交付，并新增受控 A/C→D 只读适配。B 交易逻辑、bc-0.3-candidate、七工具、EvidenceBundle schema 3 和迁移 001/002/003 保持不变。完整后端 115 项、前端 42 项、核心浏览器 419 条、异常/回放 101 条均通过；详见制作方工作区存档（`artifacts/integration_abcd/`，未随仓库分发）。

C 已签收 B 的 L0 开发接口；D 现在能显示交付的 C LossResult、A0 Claim 和独立 Quote 工程示例，并追溯到精确 B session/episode。所有运行仍为 `counts_as_formal_run=false`，真实模型历史开发结果保持 `needs_review/null`。正式 Gold、C1-1、56+28 正式运行、A 正式定价/理赔、第二机接收及 A/C 联合签收未完成，不能宣布 L1。

本轮没有 Git 远程操作或提交；当前目录仍不是 Git 仓库。下方阶段 05 内容作为合并前历史状态保留。

---

# BD 当前状态：阶段 05 收口候选

2026-10-12。用户与舍友联合负责 BD，目前仍由用户统一使用 Codex 推进。阶段 01—04 的交易/界面能力保持原状，05 只复验、整理交接、修正打包遗漏及增加 QA 工具。无 Git 仓库，无虚构 commit；检查点和清单在 `artifacts/pro_bd_sprint/05/checkpoints/`。

## 当前版本与实际能力

- B/C：`bc-0.3-candidate`，七工具，EvidenceBundle 3，兼容 schema 1/2；迁移 001/002/003。权威模型 `contracts/models.py`，候选 `docs/decisions/BC_contract_v0.3.md`，导出 `contracts/openapi.json` / schemas/tools/examples。
- 已实现原子退款/双边账本、权限/版本检查、幂等、原键恢复、持久化人工工单及增量迁移。`api/app.py`、`sandbox/store.py`、`migrations/` 在05未改。退款/工单/结束三工具共享会话内幂等空间；查询成功不是付款、重放资金增量为零。
- 稳定 case 与独立 session/episode、模板对象映射、canonical_initial/business_initial_hash 持久化；两个受控开发模板在 `sandbox/fixtures/`，初态与样例在 contracts。模板不是正式业务题或 Gold。旧证据 context 缺失仍是 legacy_unavailable/null，不倒填编号/哈希。
- D：React + TypeScript + Vite，`observer-0.1-candidate`、`bd-display-0.2`（候选文件 `BD_display_v0.2.md`）、`bd-results-boundary-0.1-candidate`。四区工作台按精确运行读取真实 B 开发事实；事件按 succeeded/rejected/replayed/error；能追踪交易、账本、订单。04 的一致性与异步竞争修复本轮重新通过。
- A/C **尚无成功结果适配器**：`frontend/src/integrations.ts` 以 unknown 为输入，空值 pending，非空未审输入 unsupported_contract，result=null、commercial_quote=false。缺版本化 schema、语义、样例、正式结果及后续成功适配实现，不是“只等填数据”。Agent 按钮禁用；没有模型执行器、独立损失核验或保险公式。

## 本次真实验证与可复现入口

完整命令、版本、退出码与输出见 `artifacts/pro_bd_sprint/05/checks/*.json/.log` 和 `test_command_index.json`。直接命令与接收步骤见 `docs/setup/RECEIVE_AND_RUN.md`。本轮使用 Python 3.13.1 / Node 24.21.0 / npm 11.19.0 / Edge 155.0.4283.45，requirements.lock 和 package-lock 未改。

- `python -m unittest discover -s tests -v`：原目录及新目录均 65/65，含旧退款/工单原键迁移恢复、非法模板原子性、隔离和权限。新目录复用原 Python 环境。
- `python -m scripts.run_http_checks --output-dir <全新目录>`：两目录均通过。独立标准库客户端、真实 loopback HTTP、333/250 分开发退款、同 case 独立状态及初态复算、三来源标签、进程重启、TCP 发完不读响应后同键恢复；真实模型调用 0。
- `export_contracts --with-openapi --check`、`export_frontend_contract --check`：通过；前端 test 41/41、typecheck、构建/预编译校验器一致性通过。
- `run_workbench_checks` 默认原浏览器套件：341 条/16图；`--suite stage04`：91 条/14图；六项观察者安全探针通过。包括旧 schema、两模板、坏回放拒绝、创建/导入竞争、事件顺序、金额追溯、网络错误/未知创建和浏览器凭据检查；不是正式业务实验。
- 新目录 `var/stage05-reception` 从候选精简包解压，npm ci --offline --ignore-scripts 成功；首次构建发现打包漏 `.d.cts`，补回原文件并修正打包规则后成功。业务源码未改。实际 CLI/Edge 启动、重启及 schema 1/2/3 已加载页面断网回放另存新证据。
- 新 Python 虚拟环境创建成功，但 pip 下载因 TLS EOF 失败；后续使用原锁定 .venv。**同一台 Windows、同一 Codex 操作者、部分复用环境；不是第二机/第二人或完整干净安装验收。**

首次沙箱测试挂起/HTTP超时/前端临时文件 EPERM、首次精简包构建失败均留档，不删除或将失败改成通过。后端原生复跑完成后，仅终止本轮已核实的挂起测试子进程；没有清理历史库。

## 安全、保护和交付路径

与 after_04 清单 779/779 相同后才开始05。审计 ZIP 只新增到 `docs/audit/AgentShield_Stage04_Review_2026-10-12/`；附件 hash 与目录在05/audit_import.json。来源包中的说明按本轮用户边界读取，没有据此开展其他阶段。

B 和观察者仅 loopback；B 管理/会话凭据保留服务端，浏览器仅短时独立 HttpOnly 观察授权；无通用管理/工具代理。运行测试使用独占临时库。两份可读旧库哈希收尾复核；`var/migration-v1-vm5ra8a8`、`var/tmpt1rn8dz0` 权限受限仍未知，未改 ACL。没有模型/支付/公网/上传/推送/正式 Gold 操作。

启动器自建 B/SQLite，不读取 C 另一个实例。当前跨实例路径：C 获授权管理端只读导出精确 session → 提交文件哈希、身份/版本/来源证明 → BD 本地只读导入。不能叫实时 Agent 联调。将来同实例实时适配需单独设计固定服务端身份、租户/会话授权与生命周期，不能给浏览器管理员令牌。

## 待各负责人接收

- C：按 `BD_to_C_CHECKLIST.md` 独立跑消费者 smoke，确认候选协议；实现/验证 attempted 记录、真实运行清单与独立核验，交付 LossResult schema/样例/真实结果。签收 pending。
- A：按 `BD_to_A_CHECKLIST.md` 审分摊、资格、确认/更正、工单、v1 历史政策与保险研究接口，交付 QuoteResult schema/样例/语义。签收 pending。
- BD/舍友：按 `docs/setup/RECEIVE_AND_RUN.md` 独立安装/启动/回放，记录实际机器、操作者和失败。后续成功适配、第二机、离线冷启动/A理算另行授权；不自动继续。

浏览器初态 hash 未复核，文件未签名；冷启动/刷新离线、A 离线理算、真实 Agent、保险计算、第二机及两处旧库核查仍未完成。不宣布正式56次实验可开始，不签 J0/J1/J2/L1/R09。优先级与输入依赖见 NEXT_STEPS。
