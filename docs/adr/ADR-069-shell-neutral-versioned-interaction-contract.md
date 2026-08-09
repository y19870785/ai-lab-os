# ADR-069：采用 Shell-neutral 版本化 Interaction Contract

- Status: Accepted
- Date: 2026-08-06
- Governance Task: ARCH-001
- Related RFC: RFC-032
- Accepted by: ARCH-001 / PR #66 / Merge Commit `4f9eab191fc0d99898ee69a2b42912017e4740e3`
- Implementation: NOT_APPROVED / NOT_STARTED

## 背景（Context）

Hermes 是首个首选 Agent Shell，但 AI-Lab 的业务能力不能依赖 Hermes 私有模块、协议、memory 或数据库
布局。当前 `/chat`、ApplicationRequest、ToolResult 与 MCP mock foundations 都不是可信交互领域合同。

## 决策（Decision）

定义版本标识为 `trusted-interaction/v1` 的 Shell-neutral、Transport-neutral application contract，覆盖 View、
Preview、Confirm、Cancel、Modify、Status、Verified Result 与 Recovery。HTTP、Python API、MCP 或其他
transport 只能做 projection；serialization 不是 domain contract。

每次请求必须保留 canonical/correlation IDs、resolved Workspace/actor、revision、idempotency、FailureInfo、
authoritative marker 与 audit reference。Shell 和 Adapter 不访问 AI-Lab 数据库，不绕过 Policy、Preview、
Confirmation、Approval、Audit、Status、Verified Result 或 Recovery。

后续必须用非 Hermes Fake/Reference Adapter 与 Hermes Adapter 运行相同 contract vectors，证明 Shell 可替换。

## 后果（Consequences）

正面结果：业务所有权不随 Shell/transport 更换；集成故障可以用统一 Status/FailureInfo 恢复；MCP 保持候选。

代价与风险：需要版本协商、compatibility policy 和双层测试；现有入口需要渐进适配。ARCH-001 只规划，
不创建 model、endpoint、adapter 或 test implementation。

## 被拒绝的方案（Rejected Alternatives）

- 直接以 Hermes API 或内部对象作为合同：造成不可替换绑定。
- 以 HTTP JSON 或 MCP schema 作为 domain contract：把 serialization 与业务语义混为一谈。
- 允许 Shell 直连数据库：绕过 service、audit、Workspace 与 migration ownership。

## 状态与授权（Status and Authorization）

本 ADR 已由 ARCH-001 / PR #66 合并接受。Accepted 不批准实现、INT-001 或 Hermes 接入；
这些工作仍需后续单独授权。
