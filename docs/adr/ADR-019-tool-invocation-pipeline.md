# ADR-019: Tool Invocation Pipeline

**状态：** Accepted
**版本：** v0.19.0
**日期：** 2026-07-12

## 上下文

从 Agent 发起到工具返回结果，需要经过多层处理：校验、权限、沙箱、执行、审计。每层独立且可替换。

## 决策

采用 **Pipeline 模式**，固定链路顺序：

```
ToolExecutor.execute()
    ├── 1. ToolRegistry.get_info()     ← 查找工具元数据
    ├── 2. ToolValidator.validate()    ← JSON Schema 参数校验
    ├── 3. PermissionManager.check()   ← Agent 权限检查
    ├── 4. ToolRegistry.get()          ← 懒加载工具实例
    ├── 5. ToolSandbox.execute()       ← 超时 + 异常隔离
    │       └── ToolProtocol.execute() ← 实际执行（内置 / MCP / ...）
    ├── 6. ToolMetrics.record()        ← 指标统计
    ├── 7. ToolAudit.record()          ← 审计记录
    └── 8. EventBus.publish()          ← 事件发布
```

各层之间通过 `ToolRequest → ToolResult` 传递数据，互不共享可变状态。

## 为什么不用责任链模式

责任链允许动态调整顺序，但工具执行的顺序是固定的（安全校验必须在前），动态调整反而引入风险。Pipeline 模式更清晰地表达了「这是不可变的安全链路」。

## 后果

- **正面**：链路清晰，每层可独立测试。
- **负面**：增加新层需要修改 ToolExecutor，但这种情况极少（架构稳定后不应频繁增删层）。
