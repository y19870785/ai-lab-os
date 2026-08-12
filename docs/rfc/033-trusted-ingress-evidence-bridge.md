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
2. privileged supervisor 建立 plugin → issuer 的单一、预连接、不可继承 anonymous IPC capability；issuer 不监听
   具名 socket/port，不接受 bearer token，不提供 mint/sign API；
3. helper 持有专用 Ed25519 私钥，签署 canonical envelope；
4. AI-Lab 内部 receiver 只接受受信 issuer 的 evidence，验证签名和 binding 后持久化为 `UNUSED`；
5. 后续 Confirmation 请求只携带 opaque `evidence_id` 与 owner-facing confirmation text；
6. AI-Lab 在一个事务中验证 Preview ordering、freshness、identity、channel、content digest 和 interaction binding，并以 CAS 将 evidence 从 `UNUSED` 变为 `CONSUMED`。

推荐路径不修改 Hermes 源码，不使用通用 lifecycle Hook 充当安全 issuer。只有可信 adapter callback 持有 capability
handle，handle 不进入 env/file/prompt/tool registry 且不被 Agent tool/shell 子进程继承。issuer 只接受该既有连接上的
严格 V1 frame，并拒绝新连接、未知字段与任意字段签名请求。若 compatibility/security spike 不能证明这些属性，
必须 `STOP_IMPLEMENTATION / SIGNING_ORACLE_ISOLATION_UNPROVEN`；不得静默降级，也不得直接 fork。

## 最小证据合同

唯一 `TrustedIngressEvidenceEnvelopeV1` 顶层必须且只能包含：

- `evidence_version`
- `evidence_id`
- `issuer_key_id`
- `channel = "wecom"`
- `channel_account_binding_id`
- `owner_binding_id`
- `conversation_binding_id`
- `event_type`
- `received_at`
- `message_content_digest`
- `expires_at`
- `signature`

`channel_account_binding_id`、`owner_binding_id` 与 `conversation_binding_id` 是 operator-provisioned random opaque
IDs，不是 raw identifier 的普通 SHA-256。raw Owner/account/chat ID 不进入 Git、MCP authority fields、普通 audit、
evidence store 或公开报告。

唯一 event identity 是 `evidence_id`，不存在 `replay_key`。issuer 使用独立且跨 signing-key rotation 稳定的
`event_identity_key`：

```text
identity_input = UTF8("ai-lab/trusted-ingress-event/v1")
  || LP_UTF8(channel)
  || LP_UTF8(channel_account_binding_id)
  || LP_UTF8(owner_binding_id)
  || LP_UTF8(conversation_binding_id)
  || LP_UTF8(raw_wecom_msgid)
evidence_id = "tie_" + base32_lower_no_pad(
  HMAC-SHA256(event_identity_key, identity_input)
)
```

`LP_UTF8` 为 4-byte unsigned big-endian length + UTF-8 bytes。PILOT-001 V1 的 `raw_wecom_msgid` 只能直接来自
authenticated WeCom inbound callback `body.msgid`。plugin 可复制/规范化但不得合成；Hermes
`MessageEvent.message_id`、`headers.req_id`、Hermes UUID、session/correlation ID、MCP `message_id` 和 LLM ID
全部禁止作为 evidence identity fallback。`body.msgid` 缺失/blank 时不签发 evidence，返回
`trusted_ingress.channel_event_id_unavailable`，Confirmation denied，business mutation 0。

raw `body.msgid` 只在 authenticated callback frame 与 adapter/issuer TCB 内使用，不进入 envelope、MCP、prompt
authority fields、Git、普通 audit 或公开报告；只持久化 derived `evidence_id`。
`received_at`、`expires_at`、`issuer_key_id`、Owner、conversation 与 content 均不参与 identity；同一 event 跨
Hermes/issuer/MCP restart、redelivery 和 signing-key rotation 必须得到相同 `evidence_id`。

issuer 必须以 `evidence_id` 为 key 原子持久化 OS-protected issuance journal，保存首次时间和完整 signed envelope。
redelivery（含 key rotation 后）只返回原 envelope，不用新 key 重签、不刷新 expiry；journal 不可用或同 ID payload
不一致时 fail closed。旧 verification public key 至少保留到 envelope 过期。

`received_at` 是可信 adapter 首次接受事件的时间，格式固定为 UTC RFC3339、毫秒精度、`Z`；redelivery 复用首次值。
`expires_at = received_at + issuer_ttl`，TTL 是受控静态配置，caller 不可指定，redelivery 不可刷新。
`message_content_digest` 为
`HMAC-SHA256(content_binding_key, UTF8("ai-lab/message-content/v1") || LP_UTF8(NFC(CRLF_TO_LF(text))))`，
以 `hmac-sha256:<lowercase hex>` 表示；该 key 只属于 issuer 与 AI-Lab verifier secret config。

验证器先按 exact V1 schema 拒绝 missing/unknown/duplicate fields、错误类型、非 NFC string、非法 enum 与非规范
时间；移除 `signature` 后，使用 RFC 8785/JCS 生成其余 11 字段的 exact UTF-8 payload bytes。Ed25519 签名覆盖且
只覆盖这些 bytes。私钥仅由 issuer 持有；AI-Lab 只持有公钥和 `issuer_key_id` allowlist。不得复用
`WECOM_SECRET`，也不得把任何 secret 暴露到 prompt、MCP args、conversation、Git 或 audit plaintext。

## Evidence 与 Confirmation Intent

`TrustedIngressEvidence` 只证明真实新消息存在，不证明它的业务含义。Confirmation 仍必须同时满足：

- 指定 Interaction 已存在有效 Preview；
- 新 evidence 的 AI-Lab `accepted_at` 晚于该 Preview 的 `created_at`；
- evidence 属于预期 WeCom account、唯一 Owner、conversation 与 Interaction；
- owner-facing Message B 是单一 raw WeCom event，精确内容为
  `确认 <preview_confirmation_challenge>`；
- 受控 confirmation parser 判定 Message B 是对该 Preview 的显式确认；
- content digest 与本次提交给受控 parser 的规范化文本一致；
- challenge 由 AI-Lab 在 Preview 创建后用 CSPRNG 生成，绑定 preview ID/revision、one-time、未过期；
- evidence 尚未消费且未过期。

`preview_confirmation_challenge` 是 AI-Lab canonical Preview fact，不可在 Preview 前预测，不由 Hermes/LLM 选择，
也不从 predictable preview ID/revision 派生；它本身不是 authority。不得拼接多条消息，不接受 paraphrase、semantic
equivalent 或“yes/好的/确认了”fallback。Message A 只产生 Preview；同一 turn 不得自动确认。

## Freshness、Replay 与恢复

Freshness 至少要求：

- `received_at <= now + allowed_clock_skew`；
- `now - received_at <= freshness_window`；
- AI-Lab `accepted_at > preview.created_at`；
- exact Message B 包含该 Preview 创建后生成的 one-time challenge；
- binding 与 expected channel、Owner、conversation、Interaction 一致；
- evidence 状态为 `UNUSED`；
- `expires_at > now`。

`accepted_at > preview.created_at` 只是必要的 deposit ordering，不单独证明 event 在 Preview 后发生；Preview 前 event
可能延迟 deposit。不可预测 causal challenge 才是主要 ordering proof。

AI-Lab 必须持久化 `evidence_id`、envelope payload digest、状态、revision、accepted/consumed 时间与消费目标。
durable uniqueness 为 `PRIMARY KEY (evidence_id)`；相同 ID/相同 payload 返回既有记录，相同 ID/不同 payload
collision/conflict 并告警。消费以 `UNIQUE (evidence_id)` 和
`state = UNUSED AND revision = expected_revision` CAS 保证最多一次。Hermes dedupe cache 只能作为优化。

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

只有 IB-A 至 IB-S 的独立验收全部通过，且证明 body.msgid-only provenance、causal challenge、signing-oracle denied、stable event identity、model-non-forgeable、
single-use/replay-safe、restart-safe、Preview-before-confirm ordering、wrong owner/event denial 以及有效确认前零
business mutation，才可另行申请 Phase 1 授权。

当前结论：

```text
RFC-033:
PROPOSED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

PHASE_1:
NOT_AUTHORIZED

PHASE_2:
NOT_AUTHORIZED

QUALITY-003:
NOT_AUTHORIZED

REL-036:
NOT_AUTHORIZED

VERSION:
0.35.0
```
