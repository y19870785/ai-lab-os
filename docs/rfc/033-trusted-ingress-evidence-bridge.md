# RFC-033：可信入站证据桥合同

## 状态

- **状态**：Proposed
- **任务**：PILOT-001-IBD
- **日期**：2026-08-12
- **唯一设计 Base**：`b22f90c471520052fff04255efba37f5accd9421`
- **相关决策**：ADR-073
- **实施状态**：`NOT_AUTHORIZED`
- **Phase 1**：`NOT_AUTHORIZED`

## 摘要

本 RFC 提议在 Hermes 的 WeCom 入站适配器完成渠道校验、但消息进入 Hermes Agent / LLM 之前，由受支持的用户安装型 platform plugin 将渠道事实交给隔离的 Evidence Issuer。Issuer 生成并签署最小 `TrustedIngressEvidence` envelope，AI-Lab 负责验证、持久化、单次消费与审计。

该 Bridge 只证明一条真实、来自配置 Owner 的新 WeCom 入站事件发生过。它不理解自然语言，不决定 Operation、Risk、Approval 或 canonical state，也不执行 `UserTask`。

## 背景与问题

PILOT-001 Phase 0 已证明 WeCom Owner DM、Hermes → MCP、AI-Lab canonical Preview、静态 Owner binding 与 `user_task.create` Policy 可用，并保持 `UserTask` business mutation 为 0。仍未被证明的是：一次 MCP 调用是否对应一条新的、真实的、来自 Owner 的 WeCom inbound event。

`ShellAssertion` 与 MCP 参数都处于 model-controlled 边界；Hermes 对话、Memory、Tool Response 也都不是最终 Approval Fact Source。因此，LLM 自报的 Owner、时间、event ID 或消息内容不能解锁 Confirmation。

## 提议架构

采用以下最小组合：

1. Hermes 用户安装型 WeCom platform plugin 在模型前入站边界观察已经通过 WeCom adapter 校验的事件；
2. plugin 通过受限本地 IPC 把不可删改的渠道字段转交给独立 Evidence Issuer helper；
3. helper 持有专用 Ed25519 私钥，签署 canonical envelope；
4. AI-Lab 内部 receiver 只接受受信 issuer 的 evidence，验证签名和 binding 后持久化为 `UNUSED`；
5. 后续 Confirmation 请求只携带 opaque `evidence_id` 与 owner-facing confirmation text；
6. AI-Lab 在一个事务中验证 Preview ordering、freshness、identity、channel、content digest 和 interaction binding，并以 CAS 将 evidence 从 `UNUSED` 变为 `CONSUMED`。

推荐路径不修改 Hermes 源码，不使用通用 lifecycle Hook 充当安全 issuer。若当前 platform plugin API 无法在模型前暴露完整 event ID、时间与原始消息，则必须停止实现，并另行提出最小 upstream-compatible extension；不得静默降级，也不得直接 fork。

## 最小证据合同

建议的 canonical envelope 包含：

- `evidence_version`
- `evidence_id`
- `issuer_id`
- `channel = "wecom"`
- `channel_account_binding_digest`
- `channel_owner_binding_digest`
- `channel_event_id`
- `conversation_binding_digest`
- `event_type`
- `received_at`
- `message_content_digest`
- `replay_key`
- `expires_at`
- `signature`

不保存 raw Owner ID、WeCom credential 或完整聊天内容。`evidence_id` 是 envelope 的稳定标识；`replay_key` 从 issuer、channel account 与 channel event ID 的规范化组合派生，用于渠道级 dedupe。`received_at` 必须来自受信入站边界，不能来自模型参数。

签名覆盖除 `signature` 外的整个 canonical envelope。私钥仅由 Evidence Issuer helper 持有；AI-Lab 只持有公钥和允许的 `issuer_id`。不得复用 `WECOM_SECRET`，也不得把私钥暴露到 prompt、MCP tool args、Hermes conversation、Git 或 audit plaintext。

## Evidence 与 Confirmation Intent

`TrustedIngressEvidence` 只证明真实新消息存在，不证明它的业务含义。Confirmation 仍必须同时满足：

- 指定 Interaction 已存在有效 Preview；
- 新 evidence 的 AI-Lab `accepted_at` 晚于该 Preview 的 `created_at`；
- evidence 属于预期 WeCom account、唯一 Owner、conversation 与 Interaction；
- owner-facing Message B 明确包含该 Preview 的短期 `preview_confirmation_code`；
- 受控 confirmation parser 判定 Message B 是对该 Preview 的显式确认；
- content digest 与本次提交给受控 parser 的规范化文本一致；
- evidence 尚未消费且未过期。

`preview_confirmation_code` 负责把意图绑定到指定 Preview，但它本身不是 authority。Message A 只产生 Preview；同一 Agent turn 不得用 Message A 自动确认。Message B 必须是 Preview 之后发生的新 Owner inbound event。

## Freshness、Replay 与恢复

Freshness 至少要求：

- `received_at <= now + allowed_clock_skew`；
- `now - received_at <= freshness_window`；
- AI-Lab `accepted_at > preview.created_at`；
- binding 与 expected channel、Owner、conversation、Interaction 一致；
- evidence 状态为 `UNUSED`；
- `expires_at > now`。

AI-Lab 必须持久化 `evidence_id`、`replay_key`、envelope digest、状态、revision、accepted/consumed 时间与消费目标。在数据库事务中以 `state = UNUSED AND revision = expected_revision` 执行 CAS；唯一约束阻止同一 `replay_key` 重入。Hermes dedupe cache 只能作为优化，不能作为消费事实来源。

AI-Lab、Hermes 或 MCP 重启后，已持久化的 `CONSUMED` 状态仍然生效。存储不可用、issuer 不可用或事务不确定时全部 fail closed，不得退回普通模型确认。

## AI-Lab 合同影响

现有 `ShellAssertion` 不足，因为它明确是 model-controlled assertion；现有 `AuditEvidence` 记录 lifecycle transition，也不是模型前产生、可验签且可单次消费的渠道事实。

后续实现需要最小新合同：

- `TrustedIngressEvidence`：不可由 MCP/LLM 构造的已签名 envelope；
- `TrustedIngressEvidenceVerifier`：验证 issuer、签名、canonicalization 与 binding；
- `TrustedIngressEvidenceRepository`：持久化、dedupe、CAS consume 与恢复；
- Confirmation 输入新增 opaque `evidence_id` 与待校验的 confirmation text。

这是 MCP contract change，但不是 MCP success 语义变化。MCP response success 仍不等于 business success；Verified Result、Canonical Commit 与 Interaction lifecycle 的既有权威边界保持不变。

## 失败语义

以下情况统一拒绝 Confirmation：evidence 缺失、格式无效、签名无效、过期、已消费、错误 Owner、错误 channel、错误 interaction、过旧、发生在 Preview 之前、content digest 不匹配、存储不可用、issuer 不可用或 CAS 冲突。拒绝不得产生业务 mutation。

## 被拒绝的替代方案

- **Hermes adapter 直接向 sidecar 发证**：可行但需要修改内置 adapter，升级耦合更高。
- **通用 Gateway lifecycle Hook**：当前 Hook 缺少完整 event ID/可信时间/完整内容，并且异常不会阻断消息管线，不能作为安全 issuer。
- **AI-Lab wrapper 接管整个 Hermes ingress**：边界最清晰，但部署复杂且重复 channel platform 职责。
- **Hermes fork**：维护与供应链成本过高，只能作为最后选择，本 RFC 不接受。
- **LLM/MCP 传完整 evidence envelope**：模型可替换字段或重放，不构成可信边界。

## Phase 1 解锁条件

只有 IB-A 至 IB-O 的独立验收全部通过，且证明 model-non-forgeable、single-use/replay-safe、restart-safe、Preview-before-confirm ordering、wrong owner/event denial 以及有效确认前零 business mutation，才可另行申请 Phase 1 授权。

当前结论：

```text
RFC-033:
PROPOSED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

PHASE_1:
NOT_AUTHORIZED
```
