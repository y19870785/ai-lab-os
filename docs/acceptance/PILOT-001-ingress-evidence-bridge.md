# PILOT-001 — 可信入站证据桥验收计划

- 任务：`PILOT-001-IBD`
- 状态：`PLANNING_BASELINE / NOT_EXECUTED / PENDING_INDEPENDENT_REVIEW`
- 授权 Base：`b22f90c471520052fff04255efba37f5accd9421`
- 关联设计：`docs/project/PILOT-001-TRUSTED-INGRESS-EVIDENCE-BRIDGE.md`
- 关联决策：`RFC-033 / ADR-073 / PROPOSED`
- Bridge implementation：`NOT_AUTHORIZED`
- Phase 1 / Phase 2：`NOT_AUTHORIZED / NOT_AUTHORIZED`
- AI-Lab Real Provider：`0 planned / 0 executed`

## 验收目的与边界

本计划验证未来实现是否能把一条真实、新鲜、唯一、来自配置 Owner 的 WeCom inbound event 转换为模型不可
伪造的 `TrustedIngressEvidence`，并由 AI-Lab 验证、持久化、单次消费与审计。

本计划不验证通用 Channel Platform、Agent Runtime、Workflow Engine、完整 IAM、企业级 PKI、Phase 2、
Execution、Verification、Canonical Commit 或真实 UserTask creation。没有合法 Message B evidence 时，任何
Confirmation 与业务 mutation 必须 fail closed。

## 统一测试夹具

未来实施验收必须使用隔离的 Pilot workspace、固定 Clock、唯一配置 Owner、测试 issuer key pair 与本地
AI-Lab receiver。除 IB-A 的受控真实 Owner event 外，负向场景优先使用签名 fixture/Fake issuer，不加载 Provider
credential，也不调用真实 LLM。

每个场景至少记录：

```text
test_case
interaction_id
preview_id / preview_revision
evidence_id
issuer_key_id
channel/account/owner/conversation digest match result
received_at / accepted_at / preview.created_at
signature/content/intent result
consumption state before/after
confirmation count before/after
UserTask count before/after
FailureInfo code
raw secret / raw Owner ID leakage scan
AI-Lab Real Provider Called
```

证据输出只使用 canonical ID、digest、时间与脱敏状态；不得记录 raw Owner ID、WECOM_SECRET、issuer private key、
full raw event、完整聊天记录或 Provider credential。

## IB-A 真实 Owner 证据接受

前置：Preview 已存在；issuer/receiver/key allowlist 正常；配置 Owner 在同一 DM conversation 发送包含正确 Preview
confirmation code 的 Message B。

验证：

- evidence 在 Agent/LLM 前产生并由 AI-Lab receiver 验签持久化；
- `channel=wecom`、account/owner/conversation digest 与 Pilot binding 匹配；
- `accepted_at > preview.created_at`；
- exact Message B content digest 与 deterministic confirmation intent 匹配；
- AI-Lab 在同一 transaction/CAS 中形成 Confirmation 并把 evidence 标为 `CONSUMED`；
- valid Confirmation 前 UserTask count 不变；本场景不执行 UserTask。

预期：`ACCEPTED / CONFIRMATION_FACT_CREATED / BUSINESS_MUTATION_0`。

## IB-B 模型伪造证据拒绝

模型构造不存在的 `evidence_id`、自填 envelope/signature 或修改合法 envelope 任一字段。

预期：`trusted_ingress.evidence_missing` 或 `trusted_ingress.signature_invalid`；Confirmation 0；UserTask mutation 0。

## IB-C 错误 Owner 拒绝

使用另一 WeCom user 或 owner digest 不匹配的有效签名 evidence。

预期：`trusted_ingress.binding_mismatch`；不消费到目标 Preview；Confirmation 0；UserTask mutation 0。

## IB-D 错误 Channel 拒绝

使用非 `wecom` channel 或错误 bot/account digest 的有效签名 evidence。

预期：`trusted_ingress.binding_mismatch`；Confirmation 0；UserTask mutation 0。

## IB-E 过期证据拒绝

固定 Clock 超过 issuer `expires_at` 或 AI-Lab freshness window；同时覆盖 future timestamp/skew 超限。

预期：`trusted_ingress.evidence_expired`；不得因 message ID 不同而放行。

## IB-F 同一证据重放拒绝

第一次合法 confirm 已把 evidence 标为 `CONSUMED`；随后用相同 `evidence_id` 对同一或另一 Preview 重放。

预期：同一 idempotency key/同一 payload 只返回既有结果；任何不同 payload/Preview/Interaction 返回
`trusted_ingress.evidence_replayed` 或 conflict；Confirmation 不增加；重启后结果相同。

## IB-G Preview 前事件拒绝

AI-Lab receiver 先接受 evidence，随后才创建 Preview；即使 issuer `received_at` 被模型声称为更晚也不得放行。

预期：基于 AI-Lab `accepted_at <= preview.created_at` 返回 `trusted_ingress.ordering_invalid`。

## IB-H 证据跨重启保持

分别覆盖 AI-Lab、Hermes、MCP 与 issuer restart：

- `UNUSED` evidence 重启后仍可在窗口内验证一次；
- `CONSUMED` evidence 重启后仍拒绝重放；
- key rotation/reload 不改变 evidence ID；
- Hermes/MCP restart 不重置 AI-Lab consumption fact。

预期：`RESTART_SAFE / SINGLE_USE_PRESERVED`。

## IB-I Raw Owner ID 不泄漏

扫描 Git diff、日志、FailureInfo、AuditEvidence、MCP response、test report 与持久化 payload。

预期：只出现 `owner_binding_digest`/canonical actor；raw Owner ID、WeCom Secret、private key 与完整 raw event 为 0。

## IB-J 消息摘要不匹配拒绝

使用合法 evidence，但 future confirm request 的 `confirmation_text` 发生空格、标点、Unicode、大小写、删减或同义改写。

预期：按 UTF-8/NFC/CRLF→LF 的 exact canonicalization 计算后返回 `trusted_ingress.content_mismatch`；模型摘要
不能替代真实 Message B。

## IB-K 无效签名或 MAC 拒绝

覆盖 bit flip、未知 `issuer_key_id`、撤销 key、错误 public key、canonical JSON 额外字段与非 canonical 时间格式。

预期：`trusted_ingress.signature_invalid`；不得回退到 HMAC/明文 assertion 或普通模型确认。

## IB-L 无证据确认拒绝

调用 future confirm projection，但不提供 `evidence_id`，或只提供 `ShellAssertion.message_id`、conversation text、
Hermes memory/session、MCP transport provenance。

预期：`trusted_ingress.evidence_missing`；现有 `ShellAssertion` 不能被升级为可信 evidence。

## IB-M 同 Agent turn 自动确认拒绝

Message A 创建 Preview 后，Agent 在同一 turn 使用 Message A event、模型生成 event ID 或模型自报时间尝试 confirm。

预期：没有独立 post-Preview Message B；event digest/order/confirmation code 任一门禁失败；Confirmation 0；
UserTask mutation 0。

## IB-N Preview 保持零业务 mutation

在 Bridge 正常、异常、timeout、issuer unavailable、storage unavailable 与 replay 场景中执行 Message A Preview。

预期：可以产生 Interaction/Preview/Audit，但 UserTask 与其他 canonical business object count 始终不变；MCP
Preview response 不得标记 business success。

## IB-O 不依赖真实 Provider

在 Provider credentials absent、present-but-unauthorized 与 mock/disabled 三种环境运行全部自动验收。

预期：结果完全一致；`--run-real-provider` 不提供；`AI_LAB_ALLOW_REAL_PROVIDER_TESTS` 未设置；AI-Lab Real
Provider executed 为 0。

## 失败矩阵

| 失败条件 | 预期 FailureInfo | Confirmation 数量 | 业务 mutation 数量 |
|---|---|---:|---:|
| missing/invalid evidence | `trusted_ingress.evidence_missing/invalid` | 0 | 0 |
| invalid signature/key | `trusted_ingress.signature_invalid` | 0 | 0 |
| expired/too old | `trusted_ingress.evidence_expired` | 0 | 0 |
| already consumed | `trusted_ingress.evidence_replayed` | 不增加 | 0 |
| wrong Owner/channel/account | `trusted_ingress.binding_mismatch` | 0 | 0 |
| wrong conversation/Preview/code | `trusted_ingress.conversation_mismatch/preview_mismatch` | 0 | 0 |
| event before Preview | `trusted_ingress.ordering_invalid` | 0 | 0 |
| content digest mismatch | `trusted_ingress.content_mismatch` | 0 | 0 |
| storage/issuer unavailable | `trusted_ingress.storage_unavailable/issuer_unavailable` | 0 | 0 |
| revision/CAS conflict | `interaction.confirmation_conflict` | 0 | 0 |

全部失败必须 fail closed，不得降级成普通模型确认。

## Phase 1 验收门禁

IB-A～IB-O 全部获得自动证据、必要真实边界证据与独立安全/架构复核前：

```text
FRESH_OWNER_INGRESS_EVIDENCE:
UNSUPPORTED

PHASE_1:
NOT_AUTHORIZED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

REAL_BUSINESS_MUTATION:
NOT_AUTHORIZED
```

本文件只定义未来 acceptance contract，不构成任何 `PASSED`、`SUPPORTED`、`IMPLEMENTED`、`MERGED` 或
`MAIN_QUALITY_GATE_PASSED` 事实。
