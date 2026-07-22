# 技术债清单

> 当前源码版本：v0.34.0 Alpha | 更新日期：2026-07-22

## 开放

| ID | 描述 | 状态 |
|---|---|---|
| QUALITY-001 | 建立并逐步清理全仓 Ruff 基线。 | OPEN |
| SCHEDULER-001 | 稳定 Scheduler 时序测试并建立持续运行基线。 | OPEN |
| DEPLOY-001 | Docker build/run、持久化卷、关闭和恢复缺正式验收。 | OPEN |
| SECURITY-001 | 静态 Bearer Token 无身份、RBAC 和热轮换。 | OPEN |
| KNOWLEDGE-001 | Knowledge reindex、chunk persistence、citation 及真实产品主链路未完成。 | OPEN |

## 已解决

| ID | 描述 | 状态 |
|---|---|---|
| CI-002 | Real-provider collection skip 已限定于 `tests/real/**`；混合收集时普通测试正常执行。 | RESOLVED |
| AGENDA-001 | Daily Agenda 已成为可选来源聚合器；禁用 Reminder/Scheduler 不再使整个 Agenda 不可用。 | RESOLVED |

## 设计取舍

- Scheduler 当前为单进程实现；这不等同于具备分布式调度能力。
- Real Provider 测试依赖明确授权的凭据和网络，普通 Quality Gate 不运行真实外部 Provider。
