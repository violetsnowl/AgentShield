# 阶段04独立复核包

先读 REVIEW_REPORT.md；下一轮施工只读 CODEX_05_HANDOFF.md 并执行原项目05任务。

本包是审计结果与补测工具，不是用户项目替代品。原 after_04.zip 没有修改，不要把本包作为项目根代码覆盖。

## 证据层级

- checks.json 与 *.log：本轮 Python/HTTP/契约/观察者实际执行。
- submitted_command_index.json、submitted_browser_summary.json：对生产者上传记录的索引，不是本轮浏览器执行。
- source_logic_checks.*：受限替代环境的 TS 断言逻辑复核，不是原 Vitest/tsc/Vite。
- source_async_checks.*：原 App 函数配 mock hooks/HTTP 顺序复核，不是浏览器。
- generate_safe_evidence.py 与 generated_safe_evidence/：12个同模板工程运行，0—5笔退款，用于检查合法证据未被误拒，不是正式样本。
- npm_*：锁文件依赖不可用的原始记录。本轮未把另一组依赖伪装为原前端环境。
- source_async_checks.initial.*：复核工具自己的对象引用断言错误，已更正预期并保留历史，没有修改用户源码。

所有脚本都用于可信的本地审计场景；先阅读使用说明和副作用。未授予上传、付款或真实服务访问权限。
