# VERSION_AND_DIFF

## 验收结论

代码统一状态：**PASS（开发集成范围）**。整体项目状态见 `FINAL_STATUS.md`，因正式业务冻结、双保险方案和 A 发布审计仍未完成，最终总状态为 **PARTIAL**。

## 远程版本确认

2026-10-15 施工前通过 `git ls-remote` / `git fetch --prune origin` 重新确认：

- `origin/main`: `753fe69db6f8c2332d669b86d48d0e3cad8bed4f`
- `origin/feature/bd-integration`: `1c8573dca3169c75bef08a5a85464f3903af0cc5`
- `origin/feature/a-business-insurance-v0.2`: `e56ede42b4c2bdf7a6eb002f34578bfaac45b7cb`
- `origin/feature/c-agent-evaluation`: `931df2a6ab98780344cc5d5b53a74da2e91202c2`

与任务给出的旧快照一致，但本轮以重新获取的远程引用为准。

## 独立工作树

- 目录：`D:\作业合集\大三\智能+保险\AgentShield_Integration_20261015`
- 本地分支：`integration/main-a-c-20261015`
- 基底：最新 `origin/main`
- A 合并提交：`01fb4f7`
- C 合并提交：`1464a48`
- 联调修复提交：`ce3ad2b`
- A v0.2 决策表来源修复：`40da1d4`
- 未 Push；远程引用未改写；用户原有 `agentshield` 目录未覆盖。

## main 已含 B/D 的证据

- `origin/feature/bd-integration` 是 `origin/main` 的祖先；main 已包含该分支，并在其后还有 D 的全站前端定稿提交。
- 因此没有重复导入旧 BD 分支。
- main 中的 B 受控 fixture、真实 HTTP 服务、观察者工作台、D 最新前端均作为整合基底保留。

## A 尚未合入 main 的内容

A 分支相对 main 为 1 个提交、35 个文件：

- `business_policy_A_v0.2.md`。
- 24 个公开 development 候选案例及公共索引、哈希和发布矩阵。
- A2/A3 发布安全测试与交接文档。
- 私有 Gold 不在仓库中，本轮没有读取。

## C 尚未合入 main 的内容

C 分支相对 main 为 2 个提交、26 个文件：

- 免费确定性规则基线和 runner adapter。
- schema v2 期初历史退款适配、独立核验入口。
- 开发/正式运行门禁、预算预试和角色交接文档。
- 正式计划保持 blocked；没有启动付费模型。

## 文件关系与接口差异

- A/C 两分支共同相对 main 的净新增为 61 个文件、4077 行新增、2 行删除。
- A、C 都没有修改 main 的 `frontend/`，因此不存在 C 旧前端覆盖 D 最新前端的问题。
- 唯一文本合并冲突为 `.gitignore`：保留 main 的 B 公共产物规则，同时保留 A 的 `_private/`、`A_D_custody_PRIVATE_DO_NOT_COMMIT/`、`*_private_gold*/` 隔离规则。
- 首轮运行后发现并修复的接口差异：A 固定案例未进入 B 严格 allowlist；C 无 obligation spec 时把零出款误判为已核验零损失；前端不识别规则基线的 `scripted_test`；C 运行清单仍指向旧 A 决策表。

## 未纳入范围

- 未合并旧 `feature/a-gold-actuarial`。
- 未假设 B-SCALE 本地十万订单分支已经进入 main。
- 未抽样、未注册新增正式任务、未修改私有 Gold、未运行 56+28 正式批次。
