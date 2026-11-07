# 技术债清单

> 当前源码版本：v0.35.0 Alpha | 更新日期：2026-11-08

## 开放

| ID | 描述 | 状态 |
|---|---|---|
| QUALITY-001 | 建立并逐步清理全仓 Ruff 基线。 | OPEN |
| SCHEDULER-001 | 稳定 Scheduler 时序测试并建立持续运行基线。 | OPEN |
| DEPLOY-001 | Docker build/run、持久化卷、关闭和恢复缺正式验收。 | OPEN |
| SECURITY-001 | 静态 Bearer Token 无身份、RBAC 和热轮换。 | OPEN |
| KNOWLEDGE-001 | Knowledge reindex、chunk persistence、citation 及真实产品主链路未完成。 | OPEN |

### SCHEDULER-001 部分进展（仍 OPEN）

SCHEDULER-001 部分进展：已补充注入时钟一致性、UTC Cron 子集合同及 60 秒真实后台循环回归基线。后者仅覆盖同一进程内两个实例/独立 SQLite 连接、阶段间优雅关闭与实例重建；跨进程、异常退出恢复、长时负载与生产验收仍未完成，因此该项继续列为 OPEN，而非已解决。

60 秒持续性候选仍未验收通过：独立复跑在第二阶段观察到同 Job 重叠，持久化 attempt 16 为 claim_expired，attempt 17 随后执行；未记录完整续租/单调时钟时间线，失租根因 UNKNOWN。旧检查可被“每阶段第 7 秒后停转”变异绕过，已增加窗口化 tick/执行进展检查。短 TTL、重叠和 CAS 断言保留，不能把另一次绿测当作失败已解决。

## 已解决

| ID | 描述 | 状态 |
|---|---|---|
| CI-002 | Real-provider collection skip 已限定于 `tests/real/**`；混合收集时普通测试正常执行。 | RESOLVED |
| AGENDA-001 | Daily Agenda 已成为可选来源聚合器；禁用 Reminder/Scheduler 不再使整个 Agenda 不可用。 | RESOLVED |

## 设计取舍

- Scheduler 当前为单进程实现；这不等同于具备分布式调度能力。
- Real Provider 测试依赖明确授权的凭据和网络，普通 Quality Gate 不运行真实外部 Provider。
