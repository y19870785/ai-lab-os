# ADR-048：User-Facing Failure Presentation Boundary

状态：Accepted

**Accepted by:** SP-012 · PR [#25](https://github.com/y19870785/ai-lab-os/pull/25) · Merge Commit `d550ab8757b50e4d12587d5e71a0058089bd3821`

## Decision

Reminder 服务继续拥有稳定 FailureInfo 机器码；CEO Assistant 的集中 `ReminderUserErrorPresenter` 负责中文、可执行的用户文案。API 保持统一非 2xx 错误结构，聊天和 CLI 不直接展示底层英文异常。

## Consequences

机器合同和用户表达可以独立演进。Presenter 只能承诺确定性 Parser 真实支持的今天/明天明确时间格式，不得暗示支持相对分钟或复杂日期。
