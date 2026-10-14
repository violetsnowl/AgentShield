# N01–N16 前端验收矩阵（D 线 · 批B 落档）

> 依据：`AgentShield_v1.2_Plan.md` §26.7（N01—N16 正式功能验收矩阵）、§16（D 任务卡 D1-1—D1-3）。
> 被测版本：`feature/bd-integration`（批A `bd5546f` + 批B 小补 `6e83d01`）。
> 实测环境：Windows 11 · Python 3.13.5（uv）· Node 24.19.0 · Microsoft Edge 155.0.4283.45。
> 本轮产物：`artifacts/pro_bd_sprint/05/b-core-20261015-003915/`（核心浏览器 603 项）、`…/b-stage04-20261015-003915/`（101 项）、`…/b-bcp2-20261015-003915/`（B 案例库 21 项）；前端单测 50 项（批A 新增 8 项）。
> 复现命令见 `docs/setup/RECEIVE_AND_RUN.md` §3（输出目录必须全新且在白名单内）。
> 判定说明：本表由自动化证据（真实 Edge 浏览器回归 + 单元测试）支撑；"部分通过/未实现"如实登记，不以截图替代行为断言。团队联合验收（J3）时按 §17.2 复核；本记录不替代 A/C 的业务/契约签收。

| ID | 场景（§26.7） | 结果 | 证据（自动化检查名，可 grep 于产物 JSON） | 说明与限制 |
|---|---|---|---|---|
| N01 | 四区任意相互切换：导航与内容一致；当前 run 不变 | ✅ PASS | `N01: switching all four areas keeps the selected run` | 切换功能区只换区域，不创建/重选运行 |
| N02 | 风险区切换 run：保持风险区，加载新 run，不串旧数据 | ✅ PASS | `N02: switching run stays in the current area`；`N02: switching to another run keeps the risk area` | "已交付结果浏览面板"对无关会话保持独立选择并带"不同运行"提示（既定语义）；会话确有对应交付结果时进入受控过渡态，杜绝旧数字残留 |
| N03 | 后退/前进/刷新/深链接恢复；失权给解释 | ✅ PASS | `N03: area recorded in URL hash`、`N03: reload restores the risk area`、`N03: reload restores the selected run`、`N03: deep link opens the requested area`、`N03: deep link restores the requested run`、`N03: browser back returns to the previous area`、`N03: browser forward returns to the later area`、`N03: run switch recorded in URL`、`one-use observer grant removed from URL` | URL 只含区域与 session_id 非敏感标识；配对授权一次性消费且不入 URL；离线回放 URL 只保留区域；无效/不可用身份提示并回退，不渲染旧金额 |
| N04 | 风险→证据、事件→交易→账本→订单：精确命中并可返回 | ✅ PASS | `N04: risk result restored after returning`、`A/C result opens the exact linked B session`、`linked evidence money matches LossResult summary`、`event -> refund -> ledger -> exact runtime order`（stage04） | 页头"← 返回上一位置"返回原阅读上下文 |
| N05 | 快速切换不同 session：迟到响应不覆盖 | ✅ PASS | `late previous-session response cannot replace current run`、`latest file selection wins despite reversed File.text completion`（stage04）、`late directory cannot exit newer replay`（stage04）、`F03-02 fixed: late create cannot replace replay`（stage04） | 交互序号 + AbortController 双保险 |
| N06 | 分页/筛选/切区：可见范围明确，入账汇总不变 | ✅ PASS | `real event pagination preserves seq order`、`filter does not change transaction total`、`replayed refund adds zero money`、`case filter selects candidates without merging runs`（stage04）、`source filter never silently changes selected session`（stage04） | 汇总始终来自 bundle 退款；不用可见行求和 |
| N07 | 新建未执行 session：显示业务初态/空证据 | ✅ PASS | `new run has no inherited refunds`、`same case keeps canonical initial hash`、`same case has disjoint runtime objects`、`v2 unconfirmed message is explicit` | 空证据与"尚无执行事件"状态完整，不冒充已执行 |
| N08 | v2 期初历史退款：期初/本轮分开，金额数量守恒 | ✅ PASS | `N08: fixture v2 run carries real opening history`、`N08: opening history labeled in the business zone`、`N08: opening amount shown in the business zone`、`N08: committed total keeps current-episode refunds only`、`N08: evidence zone annotates the opening source`；B 案例库：`opening history plus current refund reflected in item quantities`、`committed total contains current episode refund only` | 实测样本 bcp2-l1-whole-low-04：期初 ¥106.73 不进本轮合计；企业区订单/商品行与证据区分别标注 |
| N09 | C `verified/0` 与 A `needs_review/null` 的区分 | ✅ PASS（防御性完成） | `C candidate result is visible and remains needs_review`、`unknown loss is not filled from refund money`、`A0 claim is visible without invented payout`；单测 `accepts the C candidate while keeping needs_review money null` | 净损失=0 时新增"0 仅限已核验范围"限定文案（批B 新增）；暂无真实 verified/0 样本，正式运行后复查 |
| N10 | mock/规则基线/真实开发/正式 来源一致 | 部分通过 | `generated candidate remains visibly development-only pending review`（B 案例库）、`delivered runs remain explicitly non-formal`（stage04）、`candidate panel contains required honest state explanations`（stage04）、`source filter never silently changes selected session`（stage04） | "仅合法正式样本入统计"需 56+28 正式数据产生后验收；当前无混入路径 |
| N11 | A0/A1 Quote 版本不同或字段缺失：显式适配，不虚构 | ✅ PASS | `A0 claim is visible without invented payout`、`engineering quote is separated from selected Agent run`、`validated C result can open exact B evidence`（stage04）、`no browser-side insurance execution enabled`（stage04）；单测 `accepts only the non-commercial illustrative A quote candidate`、`links summary, LossResult and A0 claim by exact run identity` | fail-closed 适配：未知版本拒载、不复制理算公式 |
| N12 | schema 1/2/3 回放及非法 JSON | ✅ PASS | `saved schema3 replay works with network disabled`、`offline file import and four-area navigation make zero network requests`、`legacy schema 1/2 shown without upgrading historical facts`、`invalid imported evidence produces actionable error`、`valid legacy schema 1/2 remains readable offline`（stage04）、`bad file cannot replace last valid replay: refund-total`（stage04） | 非法文件拒绝且保留前一个合法状态；不触发资金写入 |
| N13 | 无权/断网/接口错误/空数据 | 部分通过（断网冷启动未实现） | `error state does not show stale orders`、`actual eight-second browser timeout handled`、`unapproved browser cannot read runs`、`only scoped HttpOnly observer cookie`、`no uncaught browser errors`、`no external browser requests` | 已加载页面断网 + 文件回放零请求（N12）通过；**整页断网冷启动/离线刷新未实现——如实标注，不宣称**（批D 视时间） |
| N14 | 同 case 不同 session：拒绝跨 run 误关联 | ✅ PASS | `same case has disjoint runtime objects`、`v2 exact run has 250-cent refund without v1 funds`、`late previous-session response cannot replace current run`；单测 `rejects mixed sessions even with the same stable case`、`rejects mixed episode and duplicate event sequence` | 解析层身份/序号一致性拒绝混入 |
| N15 | 大目录/长文本/窄屏 | 部分通过 | `lab-v2-mobile: no page horizontal overflow`、`lab-v2-mobile: table money right aligned without clipping`、`integration-mobile: no horizontal page overflow`（stage04） | 窄屏（390px）通过；**大目录/长文本无样本、未专门覆盖** |
| N16 | 四区内容去重：身份唯一主入口，详情默认折叠 | ✅ PASS（v1 范围） | `N16: former standalone execution bar removed`、`N16: source labels and actions consolidated into the identity strip`；截图 `b-core-20261015-003915/core-lab-v1-desktop.png` | 批A 完成"身份/来源/操作"单一条；更深层信息架构与视觉打磨列入批C（视觉方向稿待确认） |

## 未覆盖 / 未实现（如实登记）

1. **N13 断网冷启动**：未实现（现状＝已加载页面断网可用 + 文件回放零请求）。计划允许缓做，保留诚实未实现状态。
2. **N15 大目录/长文本**：无相应数据样本，未覆盖；登记待补。
3. **N10 正式统计**：需 56+28 正式数据；待 C 的正式批次与 A 的统计结果。
4. **N09 verified/0 真实样本**：暂无；防御性文案已实现。

## 核对说明

- 本表引用的检查名均为真实运行产物原文；写作前已逐条与 `browser_results.json` / `stage04_browser_results.json` / `bcp2-browser.mjs` 源文件核对。
- 复现产出目录必须全新（脚本拒绝覆盖）；核心与 stage04 输出须在 `artifacts/pro_bd_sprint/03-05` 白名单内。
- 记录：BD/D · 2026-10-15 · 自动化证据（未人工签收）。
