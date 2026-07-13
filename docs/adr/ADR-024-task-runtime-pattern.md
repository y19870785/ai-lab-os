# ADR-024: Task Runtime Pattern

**状态：** Accepted
**版本：** v0.22.0
**日期：** 2026-07-13

## 上下文

Workflow 负责 How（如何执行步骤），Scheduler 负责 When（何时触发），但缺少一个层来回答 Why（为什么执行）和 Who（谁负责整体生命周期）。还需要管理多个 Workflow 的组合和共享上下文。

## 决策

**Task Runtime 独立为一层**，位于 Scheduler 之上：

- Scheduler：触发执行（Cron / Interval）
- Task Runtime：编排执行（多 Workflow 组合、依赖解析、上下文共享）
- Workflow：执行步骤（Agent / Tool 调用）

三者之间的关系：
```
Scheduler 触发 → Task Runtime 编排 → Workflow Runtime 执行
```

## 后果

- **正面**：清晰的职责分离、为 Multi-Agent 预留接口、跨 Workflow 共享上下文
- **负面**：增加一层间接调用，但这是架构演进必需的代价
