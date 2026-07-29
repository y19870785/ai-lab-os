# ADR-015：Context Builder 模式

## 状态

Accepted（2026-07-12）

## 决策

所有 Prompt 构造统一经过 `ContextBuilder`。Agent 代码不得直接拼接 Prompt 字符串。
`ContextBuilder` 负责组合：

```text
system prompt + memory context + knowledge context + user input
```

## 理由

- Prompt 构造只有一个控制点；
- 自动注入 Memory 与 Knowledge；
- Prompt template 集中管理并进行版本控制。
