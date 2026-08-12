# PILOT-001 — 可信入站证据桥验收计划

- 任务：`PILOT-001-IBD`
- 状态：`PLANNING_BASELINE_APPROVED / FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED / NOT_EXECUTED`
- 授权 Base：`b22f90c471520052fff04255efba37f5accd9421`
- 关联设计：`docs/project/PILOT-001-TRUSTED-INGRESS-EVIDENCE-BRIDGE.md`
- 关联决策：`RFC-033 / ADOPTED / ADR-073 / ACCEPTED`
- Bridge implementation：`NOT_AUTHORIZED`
- Phase 1 / Phase 2：`NOT_AUTHORIZED / NOT_AUTHORIZED`
- AI-Lab Real Provider：`0 planned / 0 executed`

## 验收目的与边界

本计划验证未来实现是否能把一条真实、新鲜、唯一、来自配置 Owner 的 WeCom inbound event 转换为模型不可
伪造的 `TrustedIngressEvidence`，并由 AI-Lab 验证、持久化、单次消费与审计。

本计划不验证通用 Channel Platform、Agent Runtime、Workflow Engine、完整 IAM、企业级 PKI、Phase 2、
Execution、Verification、Canonical Commit 或真实 UserTask creation。没有合法 Message B evidence 时，任何
Confirmation 与业务 mutation 必须 fail closed。

IB-A～IB-S 均为 `DEFINED / NOT_EXECUTED`，不得将设计批准表述为场景通过。

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
channel/account/owner/conversation opaque binding match result
received_at / accepted_at / preview.created_at
signature/content/intent result
consumption state before/after
confirmation count before/after
UserTask count before/after
FailureInfo code
raw secret / raw Owner ID leakage scan
AI-Lab Real Provider Called
```

证据输出只使用 canonical ID、opaque binding ID、keyed digest、时间与脱敏状态；不得记录 raw Owner/account/chat ID、WECOM_SECRET、issuer private key、
full raw event、完整聊天记录或 Provider credential。

四份规划文档共同采用唯一 V1 envelope：

```text
evidence_version
evidence_id
issuer_key_id
channel
channel_account_binding_id
owner_binding_id
conversation_binding_id
received_at
event_type
message_content_digest
expires_at
signature
```

不得出现 `issuer_id`、`channel_event_id`、`channel_event_id_digest` 或 `replay_key`。`evidence_id` 是唯一稳定 event
identity，由 issuer 的独立 `event_identity_key` 对 domain + channel + opaque account binding + raw channel event ID
以及 Owner/conversation binding 执行 length-prefixed HMAC-SHA256 派生；`received_at`、content 与
`issuer_key_id` 不参与 identity。签名 payload 必须使用
RFC 8785/JCS exact UTF-8 bytes；unknown/extra/duplicate fields fail closed。

PILOT-001 V1 的 authoritative raw channel event ID 只能是 authenticated WeCom callback `body.msgid`。不得使用
Hermes `MessageEvent.message_id`、`headers.req_id`、Hermes UUID、session/correlation ID、MCP/LLM ID fallback。

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

## IB-A 真实 Owner 证据接受

前置：Preview 已存在且 AI-Lab 在创建后生成、持久化了 CSPRNG one-time
`preview_confirmation_challenge`；配置 Owner 在同一 DM conversation 的一个独立 raw event 中发送精确 Message B：
`确认 <preview_confirmation_challenge>`。

验证：

- evidence 在 Agent/LLM 前产生并由 AI-Lab receiver 验签持久化；
- `channel=wecom`、account/owner/conversation opaque binding IDs 与 Pilot binding 匹配；
- `accepted_at > preview.created_at`；
- exact Message B content digest 与单一 event command/challenge 匹配；
- AI-Lab 在同一 transaction/CAS 中形成 Confirmation 并把 evidence 标为 `CONSUMED`；
- valid Confirmation 前 UserTask count 不变；本场景不执行 UserTask。

预期：`ACCEPTED / CONFIRMATION_FACT_CREATED / BUSINESS_MUTATION_0`。

## IB-B 模型伪造证据拒绝

模型构造不存在的 `evidence_id`、自填 envelope/signature 或修改合法 envelope 任一字段。

预期：`trusted_ingress.evidence_missing` 或 `trusted_ingress.signature_invalid`；Confirmation 0；UserTask mutation 0。

## IB-C 错误 Owner 拒绝

使用另一 WeCom user 或 owner opaque binding ID 不匹配的有效签名 evidence。

预期：`trusted_ingress.binding_mismatch`；不消费到目标 Preview；Confirmation 0；UserTask mutation 0。

## IB-D 错误 Channel 拒绝

使用非 `wecom` channel 或错误 bot/account opaque binding ID 的有效签名 evidence。

预期：`trusted_ingress.binding_mismatch`；Confirmation 0；UserTask mutation 0。

## IB-E 过期证据拒绝

固定 Clock 超过 issuer `expires_at` 或 AI-Lab freshness window；同时覆盖 future timestamp/skew 超限。

预期：`trusted_ingress.evidence_expired`；不得因 message ID 不同而放行。

## IB-F 同一证据重放拒绝

第一次合法 confirm 已把 evidence 标为 `CONSUMED`；随后用相同 `evidence_id` 对同一或另一 Preview 重放。

预期：同一 idempotency key/同一 payload 只返回既有结果；任何不同 payload/Preview/Interaction 返回
`trusted_ingress.evidence_replayed` 或 conflict；Confirmation 不增加；重启后结果相同。

## IB-G Preview 前事件拒绝

AI-Lab receiver 先接受 evidence，随后才创建 Preview；该 event 不含 post-Preview challenge。

预期：ordering/challenge gate 返回 `trusted_ingress.ordering_invalid`；accepted_at 与 challenge 都必须满足。

## IB-H 证据跨重启保持

分别覆盖 AI-Lab、Hermes、MCP 与 issuer restart：

- `UNUSED` evidence 重启后仍可在窗口内验证一次；
- `CONSUMED` evidence 重启后仍拒绝重放；
- key rotation/reload 不改变 evidence ID；`received_at`/expiry 不因 redelivery 刷新；
- Hermes/MCP restart 不重置 AI-Lab consumption fact。

预期：`RESTART_SAFE / SINGLE_USE_PRESERVED`。

## IB-I Raw Owner ID 不泄漏

扫描 Git diff、日志、FailureInfo、AuditEvidence、MCP response、test report 与持久化 payload。

预期：只出现 operator-provisioned random opaque binding IDs/canonical actor；raw Owner/account/chat ID、普通
SHA-256 identifier pseudonym、WeCom Secret、private key 与完整 raw event 为 0。

## IB-J 消息摘要不匹配拒绝

使用合法 evidence，但 future confirm request 的 `confirmation_text` 发生空格、标点、Unicode、大小写、删减或同义改写。

预期：按 UTF-8/NFC/CRLF→LF 的 exact canonicalization 计算后返回 `trusted_ingress.content_mismatch`；模型摘要
不能替代真实 Message B。

## IB-K 无效签名或 MAC 拒绝

覆盖 bit flip、未知 `issuer_key_id`、撤销 key、错误 public key、RFC 8785/JCS 非规范 bytes、额外/未知/重复字段与
非规范时间格式。

预期：`trusted_ingress.signature_invalid`；不得回退到 HMAC/明文 assertion 或普通模型确认。

## IB-L 无证据确认拒绝

调用 future confirm projection，但不提供 `evidence_id`，或只提供 `ShellAssertion.message_id`、conversation text、
Hermes memory/session、MCP transport provenance。

预期：`trusted_ingress.evidence_missing`；现有 `ShellAssertion` 不能被升级为可信 evidence。

## IB-M 同 Agent turn 自动确认拒绝

Message A 创建 Preview 后，Agent 在同一 turn 使用 Message A event、模型生成 event ID 或模型自报时间尝试 confirm。

预期：没有独立 post-Preview Message B；event identity/order/one-time challenge 任一门禁失败；Confirmation 0；
UserTask mutation 0。

## IB-N Preview 保持零业务 mutation

在 Bridge 正常、异常、timeout、issuer unavailable、storage unavailable 与 replay 场景中执行 Message A Preview。

预期：可以产生 Interaction/Preview/Audit，但 UserTask 与其他 canonical business object count 始终不变；MCP
Preview response 不得标记 business success。

## IB-O 不依赖真实 Provider

在 Provider credentials absent、present-but-unauthorized 与 mock/disabled 三种环境运行全部自动验收。

预期：结果完全一致；`--run-real-provider` 不提供；`AI_LAB_ALLOW_REAL_PROVIDER_TESTS` 未设置；AI-Lab Real
Provider executed 为 0。

## IB-P Signing Oracle 拒绝

分别从 Agent/LLM、MCP tool、Hermes tool、local shell 与同一 OS user 的非可信进程尝试：连接 issuer、传入任意
Owner/event/time/content fields、调用 mint/sign method、读取或继承 IPC handle。

验证：issuer 没有具名 listener 或通用 API；只有 supervisor 预连接且 non-inheritable 的 capability handle 可用；
handle 不在 env/file/prompt/tool registry；非可信子进程没有 inherited handle；错误 frame/新连接全部拒绝且不签名。

预期：`SIGNING_ORACLE_DENIED / trusted_ingress.issuer_input_unauthenticated`；valid envelope 0；Confirmation mutation 0；
UserTask mutation 0。若任一 caller 能取得有效签名，implementation spike 必须停止，不能进入 Phase 1。

## IB-Q 重复事件稳定身份

将同一 raw WeCom channel event 在 Hermes restart、issuer restart、MCP restart、redelivery 与 signing-key rotation
之后再次送达；同时改变 delivery time，但保持 channel、opaque account binding 与 raw event ID 不变。

验证：每次均按
`HMAC-SHA256(event_identity_key, domain || LP(channel) || LP(account_binding) || LP(owner_binding) ||
LP(conversation_binding) || LP(raw_wecom_msgid))`
得到相同 `evidence_id`；`received_at` 与 `issuer_key_id` 不进入 identity；不存在 `replay_key`；AI-Lab
`PRIMARY KEY (evidence_id)` 返回既有记录或拒绝 payload conflict。issuer durable issuance journal 必须返回首次
signed envelope，不得因 restart/key rotation 重签或刷新时间；绝不创建第二个 `UNUSED` fact。

预期：`DUPLICATE_EVENT_STABLE_IDENTITY / SINGLE_CONSUMABLE_FACT`；重复 Confirmation mutation 0；UserTask mutation 0。

## IB-R Preview-before-event 因果性

真实 Owner event 在 Preview 创建前已被接收并签名，但人为延迟 evidence deposit，直到 Preview 创建后才送达
AI-Lab，因此表面上满足 `accepted_at > preview.created_at`。该旧 event 不可能包含 Preview 创建后才由 AI-Lab
CSPRNG 生成的 `preview_confirmation_challenge`。

`accepted_at` 不单独证明 channel event ordering。

预期：证明 accepted_at alone insufficient；exact challenge/content gate 返回
`PREVIEW_BEFORE_EVENT_CAUSALITY / CONFIRMATION_DENIED`；Confirmation mutation 0；UserTask/business mutation 0。

## IB-S Channel event ID fallback 拒绝

覆盖两个独立场景：

1. authenticated callback `body.msgid` missing/blank，但 `headers.req_id` 存在；
2. `body.msgid` 与 `headers.req_id` 均缺失，Hermes 原本会生成 UUID/`MessageEvent.message_id`。

预期：bridge 不消费任何 Hermes fallback ID，返回 `trusted_ingress.channel_event_id_unavailable`；
`CHANNEL_EVENT_ID_FALLBACK_DENIED / NO_TRUSTED_EVIDENCE_ISSUED / NO_CONFIRMATION / BUSINESS_MUTATION_0`。

## 单一事件与 Hermes batching

PILOT-001 Confirmation 要求一个独立 raw WeCom event 包含完整精确 command：
`确认 <preview_confirmation_challenge>`。例如先发“确认”、再发“<challenge>”的两条消息不得由 Hermes batching、
session context、LLM 或 MCP 拼成一个 authoritative Confirmation；安全拒绝是预期行为。

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
| untrusted issuer caller/signing oracle | `trusted_ingress.issuer_input_unauthenticated` | 0 | 0 |
| duplicate event after restart/key rotation | `trusted_ingress.evidence_replayed/conflict` | 不增加 | 0 |
| delayed pre-Preview event deposited after Preview | `trusted_ingress.ordering_invalid` | 0 | 0 |
| body.msgid missing with req_id/UUID fallback | `trusted_ingress.channel_event_id_unavailable` | 0 | 0 |

全部失败必须 fail closed，不得降级成普通模型确认。

## Phase 1 验收门禁

IB-A～IB-S 全部获得自动证据、必要真实边界证据与独立安全/架构复核前：

```text
FRESH_OWNER_INGRESS_EVIDENCE:
UNSUPPORTED

PHASE_1:
NOT_AUTHORIZED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

REAL_BUSINESS_MUTATION:
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

本文件只定义未来 acceptance contract，不构成任何 `PASSED`、`SUPPORTED`、`IMPLEMENTED`、`MERGED` 或
`MAIN_QUALITY_GATE_PASSED` 事实。
