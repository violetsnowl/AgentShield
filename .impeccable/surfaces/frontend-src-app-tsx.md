---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: ["frontend/src/style.css"]
---

# Surface brief — AgentShield 工作台（前端 · 四区）

- **Scope & visitor mode**: Operate（一个用来"读证据、走流程、做演示"的工作台；四区＝企业实验场 / 执行证据·账本 / 风险·配置比较 / 合同·情景成本）
- **Audience & job**: 第一用户＝评委与材料读者（3–5 分钟沿 Ⅰ→Ⅳ 走完一次完整故事）；日常用户＝团队与复核者（查证据、回放、导出）
- **Proof / content**: 真实运行证据链（消息 → 工具事件 → 交易 → 账本 → 独立核验 → 研究赔款）；诚实标签（开发数据·待审 / 未复核 / 禁用即解释）；数字 0≠null
- **Constraints**: 四区保留 + 统一运行选择（V1.2 §16/§26）；N01–N16 验收；603+ 项自动检查保持全绿；前端只读权威结果

## Direction contract

THESIS: 一个"航站楼式"的保险理赔评测工作台——读到哪里，出口就在哪里：每一段内容读到头，面前就有一块指向下一站的出口牌。它拒绝"评测控制台"的通用深色格子与装饰性图表。

OWN-WORLD: 黄 #ffcc00 只干导视一件事（当前站、去向箭头、出发动作）；黑 #0b0b0b / 白 #ffffff / 灰 #e6e6e6 承载全部内容；人文无衬线（Noto Sans SC 900/700/500/400）＋等宽数字；边缘规则箭头；所有控件保持标准 web 件；特征动作＝每区末尾的出口牌（‹ 回看 ｜ 前往下一站 → Ⅱ · 约 N 分钟）。

STORY: 第一次来的人在 3–5 分钟内沿 Ⅰ→Ⅳ 走完一遍：业务 → 执行证据 → 核验 → 保险；每段结尾的出口牌把他自然推向下一段；老手随时跳区（不换运行），跨区跳转照常精确命中。

FIRST VIEWPORT: 顶栏＝品牌＋居中四导航（当前站高亮，无导视带）；其下＝运行身份细条（当前运行 · 来源标签）；再下＝区头（章节号＋区名＋诚实标签）；核心事实行（请求＋两笔订单余额）；双栏（售后消息 ｜ 订单与商品）；视口底缘＝出口牌。

FORM: 结构「出口牌」——自推清单第 6 位（deal 4/6/7 中的第 6 位）；seed key c4df0576。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
