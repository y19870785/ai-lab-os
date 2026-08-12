# ADR-073：由 AI-Lab 持有可信入站证据消费事实

## 状态

- **状态**：Proposed
- **日期**：2026-08-12
- **任务**：PILOT-001-IBD
- **相关 RFC**：RFC-033
- **实施状态**：`NOT_AUTHORIZED`

## 背景

PILOT-001 已证明 WeCom Owner DM、Hermes → MCP 与 AI-Lab canonical Preview 可工作，但现有链路无法证明某次 MCP Confirmation 对应 Preview 之后新发生的一条真实 Owner inbound event。

Hermes 能观察 channel fact，但 Hermes Agent、LLM、conversation、memory 和 tool response 都不应成为最终 Approval Fact Source。现有 `ShellAssertion` 可由模型影响，现有 `AuditEvidence` 则面向 Interaction lifecycle transition；两者都不能表达一个在模型前产生、可验签、可去重并被原子消费的 channel fact。

## 决策

采用 RFC-033 的可信入站证据桥：

1. 由 Hermes 用户安装型 WeCom platform plugin 在模型前的 adapter inbound boundary 观察真实事件；
2. privileged supervisor 通过单一、预连接、不可继承的 anonymous IPC capability 把可信 plugin callback 连接到
   Evidence Issuer；issuer 不监听具名 socket/port，不接受 bearer token，也不提供通用 mint/sign API；
3. helper 使用专用 Ed25519 私钥签署最小 canonical envelope；
4. AI-Lab 使用配置的 issuer 公钥验证 evidence，并持久化 `UNUSED / CONSUMED` 状态；
5. AI-Lab 在 Confirmation 事务中完成 freshness、Preview ordering、binding、content digest 与 CAS consume；
6. Hermes 只能签发或转交 channel-originated evidence，不能接受 Confirmation、授权 Interaction 或推进 business state。

推荐路径分类为：

```text
Hermes Source Change:
NO

Hermes Extension:
SUPPORTED USER-INSTALLED PLATFORM PLUGIN
```

只有可信 adapter callback 持有 capability handle；handle 不进入 env/file/prompt/tool registry，也不由 Agent tool/shell
子进程继承。issuer 只接受该既有连接上的严格 V1 frame。若 compatibility/security spike 不能证明这些属性，必须
`STOP_IMPLEMENTATION / SIGNING_ORACLE_ISOLATION_UNPROVEN`，并另行设计最小 upstream-compatible extension。
不得把通用 lifecycle Hook、具名 local socket 或“本地 caller”当作安全 issuer，也不得建立 Hermes fork。

## 权威与密钥归属

- WeCom credentials：仍由 Hermes 部署边界持有；
- Evidence signing private key：仅由隔离的 Evidence Issuer helper 持有；
- Event identity key：仅由 issuer 持有，独立于 signing key 并跨 signing-key rotation 稳定；
- Content binding key：仅由 issuer 与 AI-Lab verifier secret config 持有；
- AI-Lab verification key：由 AI-Lab 配置与部署边界持有，仅包含公钥；
- replay、consumption 与 audit fact：由 AI-Lab 持久化并最终裁决。

Bridge 密钥不得复用 `WECOM_SECRET`，不得进入 LLM prompt、MCP args、Hermes conversation、Git 或 audit plaintext。
raw Owner/account/chat identity 不写入仓库或 evidence store；使用 operator-provisioned random opaque binding ID，
不把普通 SHA-256 描述为匿名化。

唯一 event identity 为 `evidence_id`：

```text
evidence_id = "tie_" + base32_lower_no_pad(HMAC-SHA256(
  event_identity_key,
  UTF8("ai-lab/trusted-ingress-event/v1")
    || LP_UTF8(channel)
    || LP_UTF8(channel_account_binding_id)
    || LP_UTF8(owner_binding_id)
    || LP_UTF8(conversation_binding_id)
    || LP_UTF8(raw_wecom_msgid)
))
```

PILOT-001 V1 的 `raw_wecom_msgid` 只允许来自 authenticated WeCom callback `body.msgid`。plugin 不得合成；
Hermes `MessageEvent.message_id`、`headers.req_id`、Hermes UUID、session/correlation ID、MCP/LLM ID 均不得 fallback。
`body.msgid` 缺失/blank 时返回 `trusted_ingress.channel_event_id_unavailable`，不签发 evidence，不产生 Confirmation
或 business mutation。raw msgid 只留在 callback/issuer TCB，只持久化 derived `evidence_id`。

`received_at` 与 `issuer_key_id` 不参与 identity；不存在 `replay_key`。AI-Lab durable uniqueness 是
`PRIMARY KEY (evidence_id)`，并通过 `UNIQUE (evidence_id)` consumption fact 与 revision CAS 保证最多一次。
issuer 另以 `evidence_id` 为 key 维护 OS-protected durable issuance journal；redelivery 与 signing-key rotation 后
只能返回首次 signed envelope，不得刷新时间或重签。journal 不可用/不一致时 fail closed，旧 public key 保留到过期。

唯一 V1 envelope 字段为：`evidence_version`、`evidence_id`、`issuer_key_id`、`channel`、
`channel_account_binding_id`、`owner_binding_id`、`conversation_binding_id`、`received_at`、`event_type`、
`message_content_digest`、`expires_at`、`signature`。`received_at` 是 adapter 首次接受时间；
`expires_at = received_at + issuer_ttl`，redelivery 不刷新。验证器拒绝 unknown/extra fields，移除 signature 后按
RFC 8785/JCS 生成 exact UTF-8 payload bytes并执行 Ed25519 verification。

Preview 创建后，AI-Lab 使用 CSPRNG 生成不可预测的 `preview_confirmation_challenge`，作为绑定
preview ID/revision、one-time、随 Preview 过期的 canonical Preview fact。合法 Message B 必须在单一 raw WeCom
event 中精确为 `确认 <preview_confirmation_challenge>`；禁止多消息拼接、LLM paraphrase、semantic equivalent
与普通“yes/好的/确认了”。`accepted_at > preview.created_at` 仅是必要 deposit ordering，不单独证明 event ordering；post-Preview challenge
才是 event 不可能早于 Preview 的主要因果证明。

## 理由

该选择把可信事实的产生点放在模型之前，同时把最终验证和单次消费留在 AI-Lab。用户安装型 plugin 避免修改 Hermes 核心源码；隔离 helper 避免将签名私钥放入 Agent/LLM 进程；非对称签名避免 AI-Lab verification 端具备伪造新 evidence 的共享密钥能力。

AI-Lab 的持久化 CAS 是 replay safety 的必要条件。只依赖 Hermes session、memory 或 dedupe cache，会在 restart、并发或跨 session 情况下丢失 consumption fact。

## 后果

正面影响：

- LLM 无法选择 Owner、event ID 或受信时间，也无法签发或修改 evidence；
- 同一 event 跨 restart、redelivery 与 signing-key rotation 保持同一 `evidence_id`，且只能消费一次；
- Preview-before-confirm ordering 可由 AI-Lab 的持久化时间事实证明；
- Preview-before-event causality 由 post-Preview unpredictable challenge 证明，不能只依赖 accepted_at；
- Bridge 不保存完整聊天记录，只保存 content digest 与必要审计元数据；
- MCP success 与 business success 的既有区分不变。

代价与约束：

- 后续实现需要新的 `TrustedIngressEvidence` 合同、持久化记录与 Confirmation contract change；
- 需要独立 issuer helper、非继承 IPC capability、独立 event identity/content binding keys 与签名密钥轮换；
- plugin/API 能力必须在实现授权后单独做兼容性 spike；
- issuer、storage 或验证链路故障时 Confirmation 必须 fail closed。

## 未选择方案

- Hermes adapter 源码直连 sidecar：升级耦合更高；
- Gateway 通用 Hook：字段不足且当前失败语义不是 fail closed；
- AI-Lab 全面接管 Hermes channel ingress：部署复杂度超过最小目标；
- Hermes fork：维护成本与供应链风险不可接受；
- 把模型提供的 `ShellAssertion` 当 evidence：不能建立模型不可伪造性。

## 授权状态

本 ADR 仅记录 Proposed 设计，不代表实现或支持状态：

```text
ADR-073:
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
