# AgentShield A0 首轮交付：PyCharm 操作指南

> 版本 2026-10-13，离线研究计算候选；**不是 B/D、A/D 双人签收或 L1 完工**。源码来自原项目中的 `sandbox/store.py` 和开发模板语义，但不修改这些文件。

## 最安全的安装方法

1. 先复制一份你现有的 `agentshield` 项目文件夹当备份，或新建接收副本。**不要覆盖旧数据库、.venv、node_modules 和历史证据。**
2. 解压本 A0 ZIP。它只有我们新增的 `actuarial/`、`configs/insurance/`、`contracts/quote_result_A_...`、`docs/business/` 和 `tests/test_actuarial_...` 等文件。不要把本压缩包的根目录嵌套到项目里；将这些目录内容合并到原项目同名目录（不覆盖 B/D 原文件）。
3. PyCharm 打开 **完整项目根目录**（可以看到 `api/`、`sandbox/`、`actuarial/` 的那一层），Terminal 切到该目录。推荐沿用原项目已经验证的 Python 3.13.1；A 模块仅使用标准库、无需另外安装库。
4. 在 PyCharm Terminal 执行：

```powershell
python -m unittest tests.test_actuarial_claims tests.test_actuarial_estimates -v
python -m actuarial.demo
```

如果已经配置 B 的 `.venv`，也可以将 `python` 替换为 `.\.venv\Scripts\python.exe`（PowerShell 中从项目根目录运行）。不要为了运行 A 模块升级 B/D 锁定依赖。

### 期望的工程演示输出

```
工程算例：应退80元、误退800元、追回200元
净损失(元): 520.0
模拟赔款(元): 420.0
商户自留(元): 100.0
B0 每任务平均赔款(分): 500.0000
B1 每任务加权赔款(分): 600.0000
证据状态: illustrative ，真实 Agent 运行次数：0；不可用于商业定价
```

`B0/B1` 数字取自**人为构造的例子**，不可用于声称风险发生频率/模型效果。

### B/D 联调注意

本轮不需要开网页、后端或连接大模型。B/D 保持现有 `frontend/src/integrations.ts` 候选边界，**不能**直接把 `quote_result_A_...json` 强行认作已签收协议。等 C 提供带事实证据引用的 LossResult、A/D 审核正式请求及义务，再开展下一轮对接。

### 发我什么

PyCharm Terminal 中两条命令的完整输出；如果红字报错，直接截图或粘贴 traceback。下一轮先解决 A/D 业务 Gold 口径，再逐步向 B/D 交付成功适配所需的版本化协议。
