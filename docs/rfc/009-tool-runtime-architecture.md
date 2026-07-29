# RFC-009：Tool Runtime 架构

**状态：** Accepted
**版本：** v0.18.0
**日期：** 2026-07-12
**作者：** AI-Lab Core Team

## 摘要

本文定义 Tool Runtime Layer，即 AI-Lab 全部 Tool 的统一执行、发现、Sandbox、权限、
Audit 与 Metrics 系统。Agent Runtime 必须把每个外部 Capability 交给该 Layer，不得
直接调用 Tool。

## 动机

AI-Lab 未来可能支持 100 个以上的 Python、Shell、Browser、File、SQL、Git、Docker、
MCP、ERP、WeChat、Email、Calendar 与 OCR Tool。缺少统一 Runtime 时，每个 Agent
都必须了解 Tool 专用调用方式、权限模型和错误处理，会导致强耦合与安全风险。

## 架构

```text
Agent Runtime
      │
      ▼
Tool Executor (single entry point)
      │
  ┌───┼───────────┐
  ▼   ▼           ▼
Validator  Permission  Sandbox
  └───────┼───────────┘
          ▼
      Tool Registry
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  Echo  Calc  DateTime  UUID
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  Metrics  Audit  Events
```

## 关键设计决策

1. **单一入口：** `ToolExecutor` 是唯一执行路径，Agent Runtime 不直接调用 Tool；
2. **Protocol-first：** 全部 Tool 实现
   `ToolProtocol.initialize/execute/validate/health_check/shutdown`；
3. **Registry + Factory：** `ToolRegistry` 保存 `ToolInfo` 与延迟 Factory；
4. **通过 `asyncio.wait_for` 实现 Sandbox：** 在 Sandbox Layer 强制超时；未来 Python/
   Shell Tool 使用 Docker Sandbox；
5. **单 Tool 权限：** `ToolInfo` 声明所需权限，`PermissionManager` 检查 Agent capability；
6. **Metrics 与 Audit 不可分离：** 每次执行都被记录，不存在无 Trace 的 Tool 执行。

## Tool 生命周期

```text
REGISTERED → READY → RUNNING → (IDLE) → STOPPED
                  ↘
                  FAILED → DISABLED
```

## Event 类型

| 事件 | 触发条件 |
| --- | --- |
| `tool.registered` | Tool 加入 Registry |
| `tool.executed` | Tool 执行成功 |
| `tool.failed` | Tool 执行失败 |
| `tool.timeout` | Tool 超过 Sandbox timeout |
| `tool.disabled` | Tool 状态设为 `DISABLED` |

## 未来扩展

- **MCP Adapter：** 为 MCP-compatible Tool 提供统一 Adapter（Phase 3.4）；
- **自动发现：** 扫描 `core/tools/builtin/` 并注册 `ToolProtocol` 实现；
- **Docker Sandbox：** 隔离 Python/Shell Tool；
- **Tool Marketplace：** 带版本的远程 Tool Registry；
- **Tool Composition：** 通过 Workflow Engine 串联多个 Tool。
