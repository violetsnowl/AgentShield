# AgentShield V1.1 — Codex 开工包（B 首轮）

这是规范和任务指令，不是已经实现的项目代码。

## 怎么用
1. 创建或打开一个新的 `agentshield` 项目文件夹。
2. 将本压缩包的内容解压到该项目文件夹根目录（应有 `docs/spec/` 和 `tasks/`）。
3. 用 Codex 打开 **整个 `agentshield` 文件夹**，而不是只打开一个 .md 文件。
4. 给 Codex 发送：

```
请先读取 docs/spec/AgentShield_v1.1_Package/AgentShield_v1.1_Plan.md、
docs/spec/AgentShield_v1.1_Package/role_cards/B_Sandbox_Backend.md、
docs/spec/AgentShield_v1.1_Package/role_cards/C_Agent_Evaluation.md，
然后执行 tasks/Astra_Codex_B_First_Batch.md。先检查工作区，按文档约束
形成接口候选、可运行的 B 交易底座、C 可调用的独立 HTTP 接入测试和
交接材料。只在实际运行测试后报告通过；不要调用收费模型、
不要接真实支付、不要开发 A/C/D 的正式模块。所有接口字段待 B/C/A/D
按职责复核；完成本批后停止扩大范围。
```

## 这一批做什么
B 的最低可运行交易底座、contracts 候选、HTTP smoke test 和 B→C 交接文档。
C 此时只需要按候选契约并行写 Mock/运行器；不必等 B 完全做完。

## 重要提醒
- `AgentShield_v1.1_Plan.md` 是规范，`Astra_Codex_B_First_Batch.md` 是第一轮执行任务。
- `Plan.docx` 供人阅读，Codex 主要读 Markdown。
- 不在此包放 API Key、密码或正式留出 Gold。
- 运行后让 B 的下一位开发者在干净环境独立启动并重复 HTTP 测试，才算真实交接。
