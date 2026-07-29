# ADR-017：Tool Sandbox 隔离

**状态：** Accepted
**版本：** v0.18.0
**日期：** 2026-07-12

## 背景

Tool 可能执行任意 Python、Shell 命令或外部 API 调用。缺少隔离时，异常或恶意 Tool
可能阻塞事件循环、消耗过多资源或使 Runtime 崩溃。

## 决策

采用分层 Sandbox：

- **Phase 1（当前）：** `ToolSandbox` 使用 `asyncio.wait_for` 包装执行并强制超时。
  异常被捕获并返回 `ToolResult(success=False, error=...)`，避免崩溃传播；
- **Phase 2（未来）：** 为 Python/Shell Tool 提供 Docker Sandbox，实现进程、内存和
  文件系统隔离；
- **Phase 3（未来）：** 为 browser-use Tool 提供带网络策略的独立 Browser Context。

## 当前不采用完整 Sandbox 的原因

- 当前内置 Echo、Calculator、DateTime 与 UUID Tool 是无 I/O 的纯 Python，不需要
  Docker 隔离；
- 过早引入 Docker 会增加复杂度并降低开发速度；
- `ToolSandbox` 抽象允许未来用 Docker Executor 替换 `asyncio.wait_for`，无需修改
  `ToolExecutor` 或 Tool 实现。

## 后果

- **正面：** 抽象清晰，当前即可强制异步超时，并为 Docker 隔离保留扩展点；
- **负面：** 当前 Sandbox 无法防护 CPU 密集型无限循环，只能处理异步超时。
