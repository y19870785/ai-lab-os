# ADR-046：Deterministic Intent Effect Classification

状态：Accepted

**Accepted by:** SP-012 · PR [#25](https://github.com/y19870785/ai-lab-os/pull/25) · Merge Commit `d550ab8757b50e4d12587d5e71a0058089bd3821`

## Decision

CEO Assistant 使用不可变 `IntentDecision`，同时声明 intent、confidence 与 `read/write/chat` effect。应用边界校验 intent/effect 组合，并将两者写入响应 metadata。

## Consequences

测试可以直接证明查询意图不会落入写 handler。该机制不是通用授权系统，也不替代服务层 workspace、admission 或持久化约束。
