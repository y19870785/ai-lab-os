# ADR-014：Agent Runtime 模式

## 状态

Accepted（2026-07-12）

## 决策

Agent 执行采用 Runtime + Executor 模式。Runtime 管理生命周期与编排，Executor 执行
一次交互循环：

```text
context -> LLM -> tools -> memory
```

## 理由

- 将生命周期职责与执行逻辑分离；
- Executor 可以独立测试；
- Runtime 可以替换为不同的执行策略。
