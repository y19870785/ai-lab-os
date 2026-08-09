# INT-001 — Hermes MCP 投影

- 状态：REFERENCE PROJECTION IMPLEMENTED / VERIFIED / MERGED / ARCHIVED / REAL HERMES NOT CONNECTED
- Transport：local stdio MCP
- Contract：`trusted-interaction/v1`

## 目的（Purpose）

本投影为 Hermes 或其他可替换 Agent Shell 提供相同的七项 trusted interaction tools。名称中的
Hermes 表示首个首选集成方向，不构成 SDK、Memory、Session、协议私有字段或存储依赖。

## 启动入口（Entry Point）

安装 local extra 后运行：

```powershell
python -m applications.trusted_interaction_adapter.mcp_server
```

服务使用官方 `mcp>=2,<3` SDK 与 stdio transport。默认 resolver 不建立身份或 operation policy，
所以 tools 可以被发现，但 mutation 会返回
`interaction_adapter.identity_binding_unavailable`，不会访问数据库之外的 canonical service
boundary，也不会产生外部副作用。

## 精确工具白名单（Exact Tool Allowlist）

```text
ai_lab_interaction_preview
ai_lab_interaction_modify
ai_lab_interaction_confirm
ai_lab_interaction_cancel
ai_lab_interaction_status
ai_lab_interaction_view
ai_lab_interaction_recover
```

明确不存在 `approve`、`execute`、`verify` 或 `canonical_commit` tool。MCP tool completion、
JSON-RPC result 与 Shell Tool Response 都不等于 canonical success；Shell 必须使用 response 中的
`interaction_id`、`lifecycle_state`、`available_operations` 与 `final`。

`final` 表示 canonical Interaction 是否终止，而不是 success：`SUCCEEDED`、`FAILED`、
`CANCELLED`、`EXPIRED` 均为 true，`RECOVERY_REQUIRED` 等非终态为 false。Business success 仍需
canonical `SUCCEEDED` 与所需 Verified/Commit evidence。

## 输入边界（Input Boundary）

每个 tool 接收 `ShellAssertion`。其中 channel、shell、session、identity、workspace claim 与
conversation correlation 均为 provisional；AI-Lab resolver 必须 fail closed 地解析为
`ResolvedShellContext`。Conversation text 不是 Confirmation，Shell Memory 不是 Business Fact，
Tool Response 不是 Verified Result。

## 输出边界（Output Boundary）

所有 tools 返回相同 `AdapterResponse` envelope：contract/request/trace/interaction/revision、
canonical lifecycle/execution/verification/recovery status、available operations、Preview、
FailureInfo 与 final。`authoritative` 表示 canonical source，不表示 operation succeeded。
服务端固定注入 `adapter=trusted-interaction/v1` 与 `transport=mcp-stdio`；它们只属于 audit /
correlation provenance，不是 identity、Workspace、risk、policy 或 approval authority。MCP caller
不能通过 `ShellAssertion.correlation` 覆盖这些值。Direct Adapter 使用 `transport=direct`，因此
两条路径可区分，但共享同一 transport-neutral canonical projection。

## Hermes 配置边界

本任务不修改 Hermes 配置、不启动真实 Hermes、不进行真实 MCP wiring，也不读取或写入 Hermes
Memory。后续集成必须把 stdio server 作为独立进程启动，且不得授予 Shell 数据库访问。真实
identity binding 与 policy resolver 需要独立授权和证据。

## 冒烟证据（Smoke Evidence）

自动测试通过官方 MCP client 启动上述 module、完成 initialization、精确发现七项工具，并验证
默认 Preview 返回 transport success 但 `final=false` 的 fail-closed response。没有真实 Provider
或真实 Hermes 调用。

## 治理结果（Governance Result）

INT-001 已通过 ACC-INT-001 A～Q、最终独立审查、PR #70 Squash Merge 与 main Quality Gate
`31324821391`，并完成 post-merge reconciliation 和封存。该结果只验证 Shell-neutral Adapter
与 reference MCP projection，不构成真实 Hermes、identity binding、operation policy 或 Pilot 授权。
