# ADR-007: Decision Memory 模型

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 007                                  |
| **标题**     | Decision Memory 模型                  |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-002 (更新版)                      |
| **取代**     | —                                    |

## 1. 背景

在 AI-Lab 的原始 Memory Layer 设计中（RFC-002），记忆分为三层：Session、Episodic、Semantic。但缺少一个关键的记忆维度——**决策记忆**。

Agent 在日常运行中会做出大量决策：
- 用户问"我应该投资这个行业吗？" → Agent 给出分析并建议
- Agent 在任务中选择了方案 A 而不是方案 B
- Agent 在多个工具之间选择了调用方式

这些决策过程的信息非常有价值：
- **对 Agent 自身**：下次类似场景可以参考之前的推理链
- **对用户**：可以理解 Agent 为什么这么建议，而不是只看结论
- **对系统**：可以分析决策模式，优化 Agent 行为

### 现有设计的不足

原设计中，决策数据面临两个去处，但都不合适：

| 候选位置 | 问题 |
| --- | --- |
| Episodic Memory | 粒度太粗——Episodic 记录整次交互，决策只是其中的一部分，难以独立检索 |
| Knowledge Layer DecisionKnowledge | 生命周期和所有权不匹配——DecisionKnowledge 是用户管理的正式知识，Agent 每次自动写入会污染知识空间 |

需要一个独立的记忆类型来承载"决策过程"。

## 2. 决策

### 2.1 在 Memory Layer 中新增 Decision Memory

将 Decision Memory 作为 Memory Layer 的第四种记忆类型，与 Session、Episodic、Semantic 平级。

Memory Layer 变为四层架构：

```
Session Memory  (短期，会话上下文)
Episodic Memory (长期，历史交互)
Semantic Memory (长期，概念关系)
Decision Memory (长期，决策推理)     ← 新增
```

### 2.2 为什么不归入 Knowledge Layer

| 反对理由 | 说明 |
| --- | --- |
| 生命周期不同 | Decision Memory 受遗忘策略管理（重要性衰减、自动淘汰），DecisionKnowledge 由用户决定保留 |
| 创建方式不同 | Decision Memory 由 Agent 运行时自动写入，DecisionKnowledge 由用户手动管理 |
| 置信度不同 | Decision Memory 是运行时中等置信度（~0.7），DecisionKnowledge 是用户验证后的高置信度（1.0） |
| 可变性不同 | Decision Memory 是只追加的（记录发生了什么），DecisionKnowledge 可编辑可版本管理 |

**结论**：Decision Memory 和 DecisionKnowledge 不是"二选一"的关系，而是"流水线"的关系——Agent 自动记录 → 用户筛选升级。

```
Decision Memory (系统自动) ──→ 用户推送 ──→ DecisionKnowledge (用户管理)
```

### 2.3 数据结构原则

| 原则 | 说明 |
| --- | --- |
| 只追加（Append-only） | 决策记录一旦写入不可修改——只可标记 outcome 更新 |
| 结构化推理链 | 推理过程不能是一段文本，必须是结构化的步骤列表 |
| 可溯源 | 每条决策记录必须关联到触发它的 Episodic Memory / Session |
| 重要性驱动 | 不是每个决策都值得记录。通过 importance 阈值控制写入 |

### 2.4 写入触发策略

什么情况下写入 Decision Memory？

```
Agent 做出一个"重要决定"
    │
    ▼
是否满足以下任一条件？
    │
    ├── 决策涉及多个备选方案（alternatives ≥ 2）
    ├── 决策的影响范围较大（由 Agent 重要性评估）
    ├── 用户明确要求 "解释你的推理"
    ├── 决策涉及高风险操作（需要用户审批的工具调用）
    │
    任一满足 → 写入 Decision Memory
    都不满足 → 不写入（信息在 Episodic Memory 中已足够）
```

### 2.5 决策结果追踪

决策记录在写入时 `outcome` 为 `PENDING`。后续通过两种方式更新：

1. **自动追踪**：Agent 在执行决策后的后续交互中发现结果明确（如"方案 A 成功达到预期"），自动更新 outcome
2. **定期回顾**：Consolidation Engine 定期扫描 PENDING 状态的决策，尝试从后续 Episodic Memory 中推断结果

### 2.6 与 Episodic Memory 的关联方式

```
Episodic Memory (一次交互)
    │
    ├──→ references → [Decision-001, Decision-002]
    │                  (在这次交互中做出的决策)
    │
Decision Memory (一个决策)
    │
    ├──→ belongs_to → Episodic-001
    │                  (这个决策是在哪次交互中做出的)
```

双向关联，但各自独立存储。

## 3. 后果

### 正面

- 决策过程可独立检索和回顾，不必从整段对话文本中提取
- Agent 可以"回忆"之前的推理链，提升决策一致性
- 为后续的"决策模式分析"和"Agent 行为优化"提供数据基础
- 通过 `outcome` 追踪，可以建立"决策→结果"的反馈闭环

### 负面

- Memory Layer 多了一种记忆类型，增加了存储和管理的复杂度
- 决策推理链的结构化存储占用的存储空间比纯文本大
- 重要性阈值需要调优——太低则噪声多，太高则漏记重要决策

### 风险

- 推理链的结构化程度不够时，可能退化为"一段决策文本"
  - **缓解**：提供灵活的回退模式——当结构提取失败时，至少保存一段文本描述
- 自动结果追踪可能误判（如因果混淆）
  - **缓解**：结果追踪只做"建议"，不做自动修改；outcome 的自动更新需要足够置信度

## 4. 理由

选择在 Memory Layer 中新增 Decision Memory，而不是扩展现有 Episodic Memory 或 Knowledge Layer，原因：

1. **关注点分离**：Episodic 负责"发生了什么"，Decision 负责"为什么这么选"。分开后各自可以优化存储和检索策略
2. **生命周期一致**：与现有 Memory 类型一样受遗忘策略管理，保持 Memory Layer 的统一性
3. **升级路径清晰**：Agent 自动记录在 Memory，用户手动管理在 Knowledge——边界清晰，不相互污染

## 5. 相关链接

- [RFC-002: Memory Layer Architecture](docs/rfc/002-memory-layer-architecture.md)（更新版，含 Decision Memory）
- [RFC-004: Knowledge Layer Architecture](docs/rfc/004-knowledge-layer-architecture.md)（含 DecisionKnowledge 定义）
- [KNOWLEDGE_POLICY.md](../governance/KNOWLEDGE_POLICY.md)（知识管理策略）
