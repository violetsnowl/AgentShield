---
name: "AgentShield 保险风险评测工作台"
description: "机场导视世界 (The Terminal Wayfinding)：黄只做导视，黑白灰承载内容；读到哪里，出口就在哪里。"
colors:
  signal-yellow: "#ffcc00"
  signal-yellow-deep: "#f2c200"
  signage-ink: "#0b0b0b"
  paper-white: "#ffffff"
  concrete: "#e6e6e6"
  plaster: "#f7f7f7"
  hairline: "#d8d8d8"
  muted-graphite: "#6b6b6b"
  soft-graphite: "#4a4a4a"
  status-pass: "#0a7d32"
  status-caution: "#8a6116"
  status-error: "#a4343a"
typography:
  display:
    fontFamily: "Noto Sans SC, Microsoft YaHei UI, PingFang SC, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 900
    lineHeight: 1.4
    fontFeature: "tnum"
  headline:
    fontFamily: "Noto Sans SC, Microsoft YaHei UI, PingFang SC, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 900
    lineHeight: 1.35
    letterSpacing: "0.01em"
  title:
    fontFamily: "Noto Sans SC, Microsoft YaHei UI, PingFang SC, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "Noto Sans SC, Microsoft YaHei UI, PingFang SC, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Noto Sans SC, Microsoft YaHei UI, PingFang SC, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 500
    lineHeight: 1.6
    letterSpacing: "0.1em"
  mono:
    fontFamily: "Consolas, Cascadia Mono, monospace"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.6
    fontFeature: "tnum"
rounded:
  near-square: "2px"
spacing:
  tight: "6px"
  snug: "8px"
  control: "12px"
  rhythm: "14px"
  panel: "16px"
  gutter: "22px"
  gutter-wide: "32px"
components:
  button:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    height: "34px"
    padding: "5px 12px"
  button-primary:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    height: "34px"
    padding: "5px 12px"
  button-primary-hover:
    backgroundColor: "{colors.signal-yellow-deep}"
    textColor: "{colors.signage-ink}"
  nav-item:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    height: "34px"
    padding: "6px 13px"
  nav-item-active:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    height: "34px"
    padding: "6px 13px"
  badge:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    padding: "1px 9px"
  badge-good:
    textColor: "{colors.status-pass}"
  badge-warning:
    textColor: "{colors.status-caution}"
  badge-error:
    textColor: "{colors.status-error}"
  input:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.signage-ink}"
    rounded: "{rounded.near-square}"
    padding: "4px 8px"
  section-head:
    backgroundColor: "{colors.signage-ink}"
    textColor: "{colors.paper-white}"
    padding: "10px 16px"
  subbar:
    backgroundColor: "{colors.concrete}"
    textColor: "{colors.signage-ink}"
    padding: "8px 22px"
  exit-plate:
    backgroundColor: "{colors.signage-ink}"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.near-square}"
    padding: "12px 18px"
  exit-plate-arrow:
    backgroundColor: "{colors.signal-yellow}"
    textColor: "{colors.signage-ink}"
    width: "52px"
---

# Design System: AgentShield 保险风险评测工作台

## Overview

**Creative North Star: "航站楼导视 The Terminal Wayfinding"**

AgentShield 工作台是一座让第三人读懂 AI 理赔执行事实的「航站楼」。整套视觉语法来自机场导视：黄色只干导视一件事——当前站、去向箭头、出发动作；黑、白、灰承载全部内容；2px 墨框把每一块信息钉成一块标牌；黑底栏目头像登机口上方的横带。工作台不讲述情绪，它指路：「读到哪里，出口就在哪里」——每一区内容读到头，视口底缘的出口牌就指向下一站。

密度与诚实是同一件事。界面按机场信息墙的密度组织：事实贴着事实，数字贴着数字，没有装饰性图表，也没有为好看而存在的一像素（第一用户要在 3–5 分钟内沿 Ⅰ→Ⅳ 走完一遍完整故事）。不可信的地方必须写在牌面上：未复核、待审、禁用都占一行自己的位置，用虚线、状态色与文字解释呈现，而不是藏起来。

运动在此系统中几乎不存在——没有入场编排、没有 hover 位移，状态切换像标牌翻面一样瞬时完成；唯一的动效是读取中的 spinner，且已被 prefers-reduced-motion 护栏接管。已确认的反向参照是旧版「通用深色评测控制台」（多色描边、装饰图表、深色格子的「AI 默认味」）——它被明确否决。

**Key Characteristics:**
- 机场导视世界：黄只做导视，黑/白/灰承载内容
- 2px 墨框构件、黑底栏目头、方角（圆角 2px）
- 固定画框：100vh 控制台，只有内容区滚动，出口牌停靠在视口底缘
- 平面标牌：零投影，唯一例外是出口牌的一层轻浮影
- 无编排动效：状态瞬时切换；仅加载 spinner，reduced-motion 已护栏
- 字体自托管离线：Noto Sans SC 400/500/700/900（简中整文件＋拉丁子集）；等宽仅用于标识符与金额

## Colors

调色板里只有一支「会走路的颜色」——导视黄；其余是让标牌成立的墨、纸、灰，和三个克制的状态词。总原则：色在字不在底——颜色永远染文字与描边，不铺底。

### Primary
- **导视黄 Signal Yellow**: 只出现在三种导视语境——顶栏当前站（黄底导航项）、去向箭头（出口牌箭头格、追溯流的 →）、出发动作（primary 按钮「创建开发会话」、品牌印）。它负责「指」不负责「说」：任何内容面、容器底、装饰都不得铺黄。
- **导视黄·深 Signal Yellow Deep**: 黄底按钮的 hover 档，同色略深，只服务导视黄的悬停。

### Tertiary
三个状态色只作语义词汇使用，不构成第三个强调色：
- **通过绿 Pass Green**: 核验通过、正向金额（+退款）的文字色。
- **警示琥珀 Caution Amber**: 待审、未复核、未知、回放来源的警示文字色。
- **错误砖 Error Brick**: 读取失败、拒绝、证据不一致的文字色与错误构件描边。

### Neutral
- **墨黑 Signage Ink**: 全部构件边框（2px）、黑底栏目头、出口牌底、正文主文字、滚动条、光标。
- **纸白 Paper White**: 页面与面板底，以及按钮、输入、badge 的默认白底。
- **干灰 Concrete**: 运行条底色、按钮 hover 底。
- **灰泥 Plaster**: 表头、代码块、section-note、内嵌信息块的底。
- **发丝线 Hairline**: 行列分隔、消息边界、加载框边——只做分隔，不做构件轮廓。
- **次级墨 Muted Graphite**: 次要说明、字段标签、fine-print。
- **柔墨 Soft Graphite**: 可交互的次级文字（折叠摘要、表头文字、控件标签）。

### Named Rules
**The Wayfinding-Only Yellow Rule.** 黄只做导视：当前站、去向箭头、出发动作。任何内容面、容器、装饰都不得铺黄；黄的面积越小，指向越准。

**The Color-In-Type Rule.** 状态色活在字与描边里，不活在底色里：badge 白底墨框，good/warning/error 只染文字；仅在黑底栏目头内允许按深底换档（描边＋亮色文字）。

## Typography

**Display Font:** Noto Sans SC（自托管 woff2，简中整文件＋拉丁子集，离线可用；回退 Microsoft YaHei UI / PingFang SC / system-ui）
**Body Font:** Noto Sans SC（同上；拉丁子集特意覆盖 → ‹ › ↺ ◈ 等导视字形）
**Label/Mono Font:** Consolas（回退 Cascadia Mono / monospace）——只给金额与机器标识符

**Character:** 单一无衬线家族内部的四级字重叙事：900 是站名与余额，700 是栏目标题与强调，500 是控件与标签，400 是阅读正文——没有更轻的字重。等宽只在「这是机器标识」或「这是钱」时出现。

### Hierarchy
- **Display** (900, 28px/26px, tabular-nums): 台账汇总大字（28px）与核心事实带余额（26px）；数字是页面里最大的东西之一。
- **Headline** (900, 22px, letter-spacing 0.01em): 区头 H1 区名；900 让中文站名有标牌感。
- **Title** (700, 17px；黑底栏目头内 13.5px；H3 14.5px): 栏目与卡片标题。
- **Body** (400, 14px/1.6；消息段 13px/1.85): 正文与客户消息，阅读段落限宽 65ch。
- **Label** (500, 11.5px；facts 格标题 letter-spacing 0.1em；badge 11px): 标签、说明、fine-print、徽标文字。
- **Mono** (700, 13px, tabular-nums): 金额（Consolas）；标识符沿用浏览器默认等宽 code。

### Named Rules
**The Weight-Is-Station Rule.** 字重即站级：900 = 站名/余额，700 = 标题/强调，500 = 控件/标签，400 = 正文。系统里不存在 light 字重。

**The Tabular-Money Rule.** 所有金额、计数与 seq 使用 tabular-nums；金额（.money）用 Consolas 等宽。钱不对齐，就不像账本。

## Layout

固定画框的 100vh 控制台：顶栏（品牌｜居中四站导航｜操作）与运行条（干灰细条）不滚动；内容区在 main 内滚动（max-width 1720px 居中，页边距 22px，≥1500px 放宽至 32px）；视口底缘停靠出口牌条。顶栏与页脚以 4px 墨线封边，运行条以 2px 墨线封边。

- 内容栅格：业务区双栏 minmax(240px,.85fr) / minmax(0,1.65fr)（≥1500px 推至 280px/1.8fr）；账本汇总 1.3fr/1fr/1fr 三格带；面板纵向单列，14px 是面板间距的节奏单位。
- 密度取向：信息墙密度——面板 padding 16px，格与格之间以 2px 墨线而非空白分隔。
- 断点四档：1500px（留白放宽、双栏加宽）、1180px（导航副标题隐藏、业务双栏塌为单列）、900px（结果身份四格转两格）、760px（顶栏转纵排、导航单行横滚、facts 三格转列、出口牌纵排）。

### Named Rules
**The Fixed-Frame Rule.** 画框不动，只有内容滚动：顶栏、运行条、出口牌是航站楼的固定设施，滚动永远不把出口带走。

**The Station-Order Rule.** 四站顺序（Ⅰ 企业实验场 → Ⅱ 执行证据 / 账本 → Ⅲ 风险 / 配置比较 → Ⅳ 合同 / 情景成本）是唯一主叙事；任意时刻，区头都显示章号、区名与诚实标签。

## Elevation & Depth

平面标牌，零投影。深度由三件东西表达：2px 墨框（把每块内容钉成牌子）、黑底栏目头（让面板压下去一层）、灰泥与干灰的底差（信息条与页面底分层）。hover 从不改变高度或添加阴影，只改填充色。唯一例外是出口牌——`box-shadow: 0 10px 30px -18px rgba(0, 0, 0, .5)` 让这块「从平面伸出来、指向你」的牌子轻微浮起。

### Shadow Vocabulary
- **出口牌浮影 Exit-plate float** (`box-shadow: 0 10px 30px -18px rgba(0, 0, 0, .5)`): 全站唯一投影，只属于停靠的出口牌。

### Named Rules
**The Flat-Sign Rule.** 表面即标牌，标牌没有影子：全站零投影、零渐变、零玻璃拟态。唯一的浮起属于出口牌——因为它是唯一从平面伸出来的东西。

**The Depth-By-Frame Rule.** 深浅靠框与底，不靠影：2px 墨框、黑底栏目头、灰泥/干灰底差已经足够分层。

## Shapes

方角为骨：一切构件圆角 2px（近乎直角），没有大圆角、胶囊或圆按钮。轮廓一律 2px 实线墨框；1px 发丝线只做行列分隔与消息边界，绝不做构件轮廓。虚线是「缺位语」——禁用、空态、加载中、不可回退一律虚线灰框；实线永远表示「这块东西是存在的」。

### Named Rules
**The 2px Ink Frame Rule.** 构件轮廓一律 2px 实线墨框；1px 只允许以发丝线形态做内部分隔。

**The Near-Square Rule.** 圆角一律 2px：方角是标牌的本体形状；全站唯一的圆是加载 spinner。

**The Dashed-Absence Rule.** 虚线 = 缺位：禁用、空、加载中、不可回退；实线 = 存在。两者语义不得互换。

## Components

控件全部保持标准 web 件（button/select/input 墨框方角），标牌构件负责指路：黑底栏目头、2px 墨框面板、竖墨线三格事实带、停靠出口牌。

### Buttons
- **Shape:** 近乎直角（2px 圆角）、2px 墨框；标准 web button，最小高度 34px。
- **Primary:** 黄底墨字 700——「出发动作」（创建开发会话）；一张屏上至多一个。
- **Hover / Focus:** hover 换底不换高（白→干灰、黄→导视黄·深）；focus-visible 统一 3px 墨色外描边、offset 2px；无过渡动画，状态瞬时切换。
- **Disabled:** 白底、虚线灰框、灰字——未接通功能禁用并附解释，不放假按钮。

### Chips（badge）
- **Style:** 白底、2px 墨框、11px/500 文字、line-height 1.7；色在字不在底。
- **State:** good/warning/error 只染文字；黑底栏目头内按深底换档（描边＋亮色文字）。

### Cards / Containers
- **Corner Style:** 2px（近乎直角）。
- **Background:** 纸白面板底；黑底栏目头；灰泥 section-note。
- **Shadow Strategy:** 无（见 Elevation & Depth）。
- **Border:** 2px 墨框；内部以发丝线分隔。
- **Internal Padding:** 16px（面板），13px 16px（facts 格）。
- 跨区跳转定位时，订单卡获得 6px 内嵌黄左标（inset 6px 0 导视黄）——是「你在这里」的指针，不是阴影。

### Inputs / Fields
- **Style:** 白底、2px 墨框、2px 圆角、padding 4px 8px；标准 select 同款；placeholder 用中性灰。
- **Focus:** 3px 墨色描边、offset 2px（全站统一焦点语言）。
- **Error / Disabled:** 禁用走虚线灰框；错误以 .notice.error（错误砖描边）呈现，不染输入框底。

### Navigation
- **Style:** 顶栏居中四站：站号（900，Ⅰ/Ⅱ/Ⅲ/Ⅳ）＋区名＋小字副标题；当前站黄底 700，副标题转深黄。
- **States:** 非当前站白底；hover 干灰；1180px 以下隐藏副标题，760px 以下单行横滚。
- **Return:** 跨区跳转（如从追溯「查看关联订单」回到 Ⅰ 区）后，顶栏右侧出现虚线「← 返回上一位置」。

### 出口牌 Exit Plate（特征构件）
每区读到头即出口：停靠条里的黑底双仓牌——「‹ 回看：上一站」｜「前往下一站 → 站号 区名 约 1 分钟」，尾部 52px 黄底箭头格；Ⅳ 区收尾时去向改为「走完了 · 回到 Ⅰ」，箭头变 ↺。全站唯一阴影构件，也是「读到哪里，出口就在哪里」的实体。

### 核心事实行 Core Facts Band（特征构件）
三格带：2px 墨框、竖墨线分格、第一格 1.6 倍宽（当前业务请求），其余两格为订单余额大字（900/tabular）。每个案子开头的「事实墙」。

### 运行条 Run Strip（特征构件）
干灰细条承载全局运行上下文：当前运行选择、来源徽标（B 本机服务 / 只读回放）、运行身份折叠、筛选。切区不换运行——这条是全站唯一的「当前所在」。

### Loading
- 读取中：虚线灰框＋spinner（20px、3px 墨环）；全站唯一动效，reduced-motion 下停用。

### Named Rules
**The Standard-Control Rule.** 控件一律标准 web 件：button/select/input 墨框方角、系统行为（Tab、Enter、原生下拉），不做自定义绘制的控件隐喻。

**The Exit-Plate Rule.** 每区读完即出口牌（‹ 回看 ｜ 前往下一站 →），Ⅳ 区收尾回 Ⅰ；出口牌是全站唯一的跨区固定出口，也是唯一浮起构件。

**The Honest-Disabled Rule.** 未接通 = 禁用＋解释（虚线灰框＋一行原因），放进牌面的诚实语境，绝不放假按钮。

## Do's and Don'ts

### Do:
- **Do** 让黄只出现在导视语境：当前站、去向箭头、出发动作；其余全部黑白灰。
- **Do** 用 2px 墨框＋2px 圆角＋黑底栏目头构成一切标牌构件。
- **Do** 保持控件为标准 web 件（≥34px 高、墨框）；未接通功能做成「虚线禁用＋一行解释」。
- **Do** 用 tabular-nums 排版所有金额与计数；金额用 Consolas 等宽。
- **Do** 把 null / 未知写成自己的徽标（「未知 / null」），与 0 严格区分。
- **Do** 每区末尾给出口牌；Ⅳ 区收尾回「到 Ⅰ」。
- **Do** 让状态色只染文字与描边。

### Don't:
- **Don't** 给任何构件加投影、渐变或玻璃拟态——出口牌浮影是全站唯一例外。
- **Don't** 用黄铺内容面、容器底或装饰；黄是手指，不是背景。
- **Don't** 用大圆角、胶囊或圆按钮；圆角只有 2px（唯一全圆是 spinner）。
- **Don't** 引入编排动效或 hover 位移。
- **Don't** 回到旧版「通用深色评测控制台」的视觉（多色描边、装饰图表、深色格子）——已确认的反向参照。
- **Don't** 把「未复核 / 未验证」的诚实标签换成确定语气或省略。
