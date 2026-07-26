# ADR-062 — Daily Review Source Failure and Availability Semantics

Status: Proposed / Planning Baseline
Date: 2026-07-26
Target: SP-019

## Context

Daily Review 聚合五个 canonical services，其中 UserTask 和 ReminderInbox 可因配置关闭或 composition 缺失而不可用。空结果、主动禁用、未配置和运行失败具有不同产品含义。如果静默忽略来源，Review 会看似完整却遗漏事实；如果所有缺失都失败，又无法在合法关闭 optional source 时使用其余来源。

## Decision

每个 source 必须记录唯一状态：

```text
available
disabled
not_configured
failed
```

- `available`：已启用且查询成功，合法空集合也属于 available。
- `disabled`：配置明确关闭。
- `not_configured`：运行时没有所需 service 或 dependency。
- `failed`：已启用来源出现 runtime、数据完整性或 legacy projection failure。

`disabled` 与 `not_configured` 是显式、可见的降级：不阻止其他来源生成 Review，但必须出现在 `source_status`，不得呈现为该来源“没有事项”。

`failed` 必须使整份 Review fail closed。不得返回部分成功 payload，也不得把失败 source 标成空集合。

对外统一返回 `daily_review.source_failed`；安全 details 仅允许：

```text
source
upstream_code
upstream_category
```

不得暴露数据库路径、原始异常、内部 SQL、正文或 traceback。

## Consequences

- 调用者可以区分“零事项”和“没有读取该来源”。
- optional source 的合法关闭不会阻断其余 canonical facts。
- 已启用来源损坏时不会输出虚假的完整报告。
- API 与 CEO Assistant 必须共享同一 FailureInfo/presenter 合同。
- Source adapter 必须知道配置状态与 composition 状态，但不能探测数据库作为替代。

## Rejected Alternatives

- 所有不可用都失败：使合法 disabled source 无法降级。
- 所有失败都部分成功：会把数据完整性问题伪装成完整 Review。
- 只记录布尔 `available`：无法区分配置、组合与运行错误。
- 记录原始异常：泄露内部实现与敏感信息。

## Governance

本 ADR 仅建立 Planning Baseline。状态为 Proposed，不批准或启动 SP-019 实施。
