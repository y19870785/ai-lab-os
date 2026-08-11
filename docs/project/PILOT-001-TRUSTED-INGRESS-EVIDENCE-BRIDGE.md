# PILOT-001 — 可信入站证据桥设计

- 任务：`PILOT-001-IBD`
- 性质：`ARCHITECTURE / SECURITY DESIGN ONLY`
- 状态：`DESIGN_DRAFT / PENDING_INDEPENDENT_REVIEW`
- 授权 Base：`b22f90c471520052fff04255efba37f5accd9421`
- 实现：`NOT_AUTHORIZED`
- Phase 1：`NOT_AUTHORIZED`
- 真实业务 mutation：`NOT_AUTHORIZED`

## 设计结论

```text
Recommended Architecture:
Option D — supported Hermes user-installed WeCom platform plugin
+ isolated ingress evidence issuer helper
+ AI-Lab-controlled internal evidence receiver and durable consumption store

Why:
Evidence is minted before Agent/LLM execution from the real channel event,
the private signing key stays outside prompt/MCP/conversation boundaries,
and AI-Lab verifies, persists, consumes, and audits the evidence.

Trusted Evidence Issuer:
privileged ingress issuer helper at the WeCom platform-adapter inbound boundary

Evidence Verification Authority:
AI-Lab

Replay Ownership:
AI-Lab

Hermes Source Change:
NO — supported user-installed platform plugin; generic lifecycle Hook is rejected

New AI-Lab Core Contract Required:
YES — TrustedIngressEvidence plus verification/consumption authority

MCP Contract Change Required:
YES — future confirm projection carries only evidence_id and exact confirmation_text

Phase 1:
NOT_AUTHORIZED

Implementation:
REQUIRES_SEPARATE_AUTHORIZATION
```

这里的 `NO` 只表示推荐设计不修改 Hermes core/bundled source。用户安装的 platform plugin、issuer helper、
AI-Lab receiver、持久化与 contract 仍然都是未来实现工作，必须另行授权并独立审查。

## 已确认事实与真实问题

| 已确认事实 | 当前结论 |
|---|---|
| WeCom Owner DM | `REAL / AVAILABLE` |
| Hermes → MCP | `WORKING` |
| AI-Lab canonical Preview | `WORKING` |
| Pilot Owner static binding | `WORKING` |
| `user_task.create` Policy | `WORKING` |
| UserTask business mutation | `0` |
| Fresh Owner Ingress Evidence | `UNSUPPORTED` |

现有问题不是 WeCom、Hermes、MCP 或 Preview compatibility。真正问题是：AI-Lab 只能看到模型构造的
`ShellAssertion` 与 MCP tool arguments，无法证明某次调用对应一条新的、真实的、来自配置 Owner 的
WeCom inbound event。

Bridge 只证明真实入站事件发生过。它不理解用户意图、不选择 operation/risk/approval、不决定 canonical
state、不生成 UserTask 内容，也不执行 UserTask。自然语言理解仍由 Hermes/Agent Shell 完成；业务 authority
仍由 AI-Lab 完成。

长期边界保持不变：

```text
Hermes Conversation != Approval Fact Source
Hermes Memory != Business Fact Source
Hermes Tool Response != Final Success Proof
MCP response success != business success
```

## 威胁模型与信任假设

本设计防御以下能力：

- LLM 任意构造或修改 MCP 参数；
- LLM 重填任意 Owner、channel、event ID、timestamp 或 message text；
- 同一真实事件被重放到同一或不同 Interaction；
- Hermes conversation、memory、session 或 dedupe cache 丢失/重启；
- 调用者拿到合法 `evidence_id` 后尝试跨 Owner、跨 channel、跨 conversation 或跨 Preview 使用；
- 签名、内容 digest、expiry、ordering、revision 或 consumption state 不匹配。

本设计不声称防御已取得本机管理员权限、篡改 issuer binary 或读取 issuer 私钥的 host compromise。该风险属于
部署加固与密钥轮换范围；它不能被降级为“相信模型”。即使在本地 Pilot，Agent tools 也不得获得 issuer 私钥、
私钥文件路径、secret environment、内部 receiver credential 或可调用的 mint API。

## 本机 Hermes 边界调查

本轮只读检查本机 `Hermes Agent v0.20.0`、源码 commit
`ee7c614eefcaaec1c8caeda65533eb3d9a35507f`，没有修改 Hermes source/config，也没有调用 Provider。

关键发现：

- bundled WeCom adapter 在 allowlist policy 后构造 `MessageEvent`，持有真实 `message_id`、sender、chat、
  `raw_message` 与 adapter-side UTC `timestamp`，随后才调用 `handle_message(event)`；
- `MessageEvent.metadata` 是 adapter 可写的 per-event metadata，但不能直接视为 cryptographic authority；
- Hermes 支持 `$HERMES_HOME/plugins/` 下的用户安装插件，`kind: platform` 是正式 plugin kind；
- 通用 `agent:start` Hook 在 Agent 即将运行时触发，只提供 platform/user/chat/session 与截断到 500 字符的
  message，不提供不可替换的 channel event ID、完整 content digest 或可信 receive timestamp；
- Hook handler 异常会被记录并继续主 pipeline，属于 fail-open observability extension，不能承担安全门禁；
- 普通 MCP invocation 仍是 `call_tool(tool_name, arguments=args)`，没有把 channel provenance 作为模型外
  envelope 注入 AI-Lab。

因此，通用 Hook 不能补足证据。可信 issuer 必须位于 WeCom event 已完成 channel intake/policy、但尚未进入
Agent/LLM 的 platform-adapter inbound boundary。

## 证据产生边界比较

| 候选边界 | 能看到真实事件 | 位于模型前 | 主要问题 | 结论 |
|---|---:|---:|---|---|
| WeCom adapter inbound boundary | 是 | 是 | bundled adapter 不能原地塞补丁；私钥必须隔离 | 最佳语义位置 |
| Hermes Gateway inbound boundary | 部分 | 是 | generic gateway 层可能丢失 channel-specific authenticity | 可作为 transport，不作为 issuer |
| Hermes session/runner boundary | 部分 | 否/过晚 | event 已转成 prompt/context，模型可见且字段不足 | 拒绝 |
| 独立 sidecar | 取决于上游 | 是 | 若只相信任意 socket payload，模型仍可能仿造 | 仅在它终止/验证真实 ingress 时可用 |
| AI-Lab controlled local receiver | 只能看到收到的 envelope | 是 | 无法凭空验证未签名的 Hermes assertion | 必须作为 verifier/persistence authority |

推荐边界由三部分组成：

1. 用户安装的 Hermes WeCom platform plugin 采用受支持的 extension point，负责把真实 channel event 交给
   privileged issuer helper，并在 evidence deposit 成功后才继续普通 Agent dispatch；
2. issuer helper 位于模型前，拥有独立签名私钥；它只接受 adapter 内部事件，不暴露通用 mint tool/API；
3. AI-Lab internal evidence receiver 验签并持久化，再返回 opaque `evidence_id`。该 receiver 不是 MCP tool，
   Agent/LLM 无权提交 envelope 字段或签名。

## 完整信任边界

```text
[WeCom — external trusted channel event]
        |
        | authenticated WeCom transport / allowlisted Owner DM
        v
[Hermes user-installed WeCom platform plugin — trusted adapter boundary]
        |
        | raw event fields, before Agent/LLM
        v
[Privileged Ingress Evidence Issuer Helper — trusted, private key owner]
        |                                      \
        | signed canonical envelope             \ normalized MessageEvent
        v                                        v
[AI-Lab internal evidence receiver]        [Hermes Agent / LLM — untrusted,
        |                                   model-controlled interpretation]
        | verify + persist                         |
        |                                          | evidence_id + exact text
        v                                          v
[AI-Lab Evidence Store — authoritative] <--- [MCP — model-controlled transport]
        |
        | atomic validate + consume + confirm
        v
[InteractionService / Confirmation / Audit — AI-Lab authoritative]
```

`evidence_id` 可被模型看到和选择，但它只是引用。真实性来自 AI-Lab 已验签并持久化的 envelope；能否用于某个
Preview 由 AI-Lab 的 owner/channel/content/freshness/ordering/consumption 验证决定。

## 最小可信证据信封

### 候选字段取舍

| 候选字段 | 是否进入签名信封 | 理由 |
|---|---:|---|
| `evidence_version` | 是 | 固定 canonical serialization 与验证规则 |
| `evidence_id` | 是 | 全局引用与单次消费主键 |
| `channel` | 是 | Pilot 固定为 `wecom`，拒绝跨 channel |
| `channel_account / bot binding digest` | 是 | 绑定配置 bot/account，不暴露原值 |
| `channel_user_binding digest` | 是 | 绑定唯一 Owner，不暴露 raw Owner ID |
| `channel_event_id` | 使用 digest | 唯一性需要；raw ID 不进入持久化/audit |
| `conversation_id` | 使用 digest | 限制事件所在 DM conversation，不保存 raw chat ID |
| `received_at` | 是 | issuer-side channel receive time 与 expiry 边界 |
| `event_type` | 是 | 仅允许 Owner DM text confirmation event |
| `message_content_digest` | 是 | 绑定真实文本而不保存完整聊天记录 |
| `nonce / replay key` | 否 | `evidence_id + event_id_digest + AI-Lab consumption` 已充分，额外 nonce 无新安全性 |
| `issuer` | 合并为 `issuer_key_id` | 选择受信 public key 与轮换版本 |
| `signature / MAC` | 使用 signature | Ed25519 asymmetric signature，避免 AI-Lab 持有共享 mint secret |
| `expires_at` | 是 | 明确 issuer 上限；AI-Lab 还应用更短本地 freshness window |

### 规范字段

```text
TrustedIngressEvidenceEnvelopeV1

evidence_version: trusted-ingress-evidence/v1
evidence_id: tie_<base32 sha256>
issuer_key_id: pilot001-wecom-issuer-<rotation>
channel: wecom
channel_account_digest: sha256:<hex>
owner_binding_digest: sha256:<hex>
channel_event_id_digest: sha256:<hex>
conversation_digest: sha256:<hex>
received_at: <UTC RFC3339>
event_type: owner_dm_text
message_content_digest: sha256:<hex>
expires_at: <UTC RFC3339>
signature: ed25519:<base64url>
```

签名覆盖除 `signature` 外的全部字段，采用固定字段顺序、UTF-8、无浮点数、UTC `Z`、禁止额外字段的 canonical
JSON。`evidence_id` 由 version、issuer key、account/owner/event/conversation digest 与 `received_at` 的 canonical
bytes 派生。重复 channel event 必须生成同一个 `evidence_id`，不能靠新 nonce 绕过 dedupe。

## 模型不可伪造保证

- LLM 不能 mint：私钥只在 privileged issuer helper 内存与 OS-protected credential 中；无 MCP mint tool；
- LLM 不能 alter：任何字段变化都会导致 Ed25519 验签失败；
- LLM 不能选择任意 Owner：Owner raw ID 在 adapter allowlist 后被转换为预配置 binding digest；
- LLM 不能选择任意 timestamp：`received_at` 由 issuer clock 产生并签名，ordering 还使用 AI-Lab `accepted_at`；
- LLM 不能选择任意 event ID：digest 来自真实 adapter event；
- LLM 即使猜到或读取合法 `evidence_id`，也不能改变其 owner/channel/content/ordering/consumption facts。

证据信封、私钥、credential path 与 internal receiver credential 都不得进入 prompt、MCP tool args、Hermes
conversation、Git 或 audit plaintext。MCP 未来只承载 `evidence_id` 和 exact `confirmation_text`。

## 密钥与秘密所有权

| 秘密或密钥 | 所有者 | 规则 |
|---|---|---|
| WeCom credentials | Hermes operator / privileged WeCom plugin helper | 继续属于 Hermes channel integration；不交给 AI-Lab、LLM 或 Git |
| Evidence signing private key | privileged ingress issuer helper | 独立 Ed25519 key；不得复用 `WECOM_SECRET`，不得进入 Agent process/tool env |
| AI-Lab verification key | AI-Lab trust configuration | 仅保存 public key 与 `issuer_key_id` allowlist；不能 mint evidence |
| Owner raw identity | Hermes adapter secret/config boundary | AI-Lab 只保存预配置 binding digest 与 canonical actor mapping |

密钥轮换必须允许旧 public key 在未过期 evidence 的短窗口内验证；撤销 key 后新 evidence 立即拒绝。Provider API
Key 与本设计无关，也不得被加载或调用。

## AI-Lab 新合同判断

现有 `ShellAssertion` 明确是 untrusted assertion，模型可以构造 `channel_identity`、`message_id` 与 correlation，
不能升级为证据。现有 `Confirmation` 只记录 Preview/actor/policy/time，不记录独立 ingress evidence 与消费状态。
现有 `AuditEvidence` 是 Interaction transition audit，不是可验签、可单次消费的 channel fact。因此现有合同不足。

未来最小新类型：

```text
TrustedIngressEvidence
- signed envelope fields
- accepted_at                # AI-Lab clock
- verification_key_id
- verification_status
- consumption_status        # UNUSED | CONSUMED
- consumed_at
- consumed_interaction_id
- consumed_preview_id
- consumed_preview_revision
- consumption_idempotency_key_digest
```

还需要最小 authority/repository 边界：

```text
TrustedIngressEvidenceVerifier.verify(envelope)
TrustedIngressEvidenceRepository.accept_verified(...)
TrustedIngressEvidenceRepository.consume_with_confirmation(...)
```

AI-Lab receiver 验签后立即持久化 `accepted_at` 与 `UNUSED`。`InteractionService.confirm` 的未来受控入口必须在
同一数据库 transaction/CAS 中验证 evidence 并写入 Confirmation、Audit 与 `CONSUMED`。若现有 generic
`interaction_facts` 无法在 association 前保存 evidence 或无法保证原子单次消费，则允许未来实施提出最小新表；
本任务不创建 Schema/Migration。

## MCP 最小变更判断

现有 confirm projection 没有 evidence reference，因此未来需要最小 request addition：

```text
evidence_id: str
confirmation_text: str
```

禁止把 envelope、signature、owner、timestamp、event ID 或 digest 作为模型可填写 authority fields。AI-Lab 根据
`evidence_id` 读取已验签记录，再对 `confirmation_text` 进行同一 canonicalization 与 digest compare。MCP tool
仍只投影请求/结果；`MCP success != business success`，Verified Result、Canonical Commit 与 Interaction lifecycle
语义完全不变。

## 内容绑定与确认意图

Bridge 原则上不持久化完整聊天记录。issuer 对规范化后的 Message B 文本计算 `message_content_digest`；AI-Lab
持久化 digest，不持久化 raw message。未来 confirm request 提交模型看到的 exact `confirmation_text`，AI-Lab
按同一规则规范化并比较 digest，不一致即拒绝。

规范化规则必须窄且可复现：UTF-8、Unicode NFC、CRLF→LF；不 trim、不改标点、不改大小写、不做自然语言改写。
任何模型摘要、同义改写或省略都不能通过 digest。

Fresh Ingress Evidence 与 Confirmation Intent 是两个事实：

- Evidence 证明“这是一条新的真实 Owner 消息”；
- Confirmation Intent 证明“该真实消息明确确认指定 Preview”。

为避免把任意“确认”映射到多个 Preview，Preview UI/response 未来必须生成非秘密、human-visible 的
`preview_confirmation_code`，例如从 `preview_id + preview_revision` 派生的短码。合法 Message B 必须包含明确形式：

```text
确认 <preview_confirmation_code>
```

AI-Lab 使用 deterministic parser 验证 exact content 与 Preview code；LLM 只转发文本，不能替 AI-Lab决定 intent。
短码不是 authority，真正 authority 仍是签名 evidence、AI-Lab ordering 与单次消费。

## Message A、Message B 与顺序证明

```text
Message A (real Owner event A)
  -> Preview created (zero business mutation)
  -> AI-Lab persists preview.created_at / preview_revision / confirmation code

Message B (different real Owner event B)
  -> issuer signs event B before Agent
  -> AI-Lab receiver persists evidence.accepted_at
  -> Agent interprets and submits evidence_id + exact text
  -> AI-Lab proves accepted_at > preview.created_at
  -> AI-Lab verifies intent/code and atomically consumes evidence with Confirmation
```

AI-Lab 不相信 LLM 自报时间。ordering 以 AI-Lab 自己的 `preview.created_at` 与 receiver `accepted_at` 为主；签名
`received_at` 只用于 channel-side age/skew 检查。Message A 与 Message B 必须具有不同 event digest，且 Message B
必须在 Preview 已存在后才被 AI-Lab receiver 接受。same-turn auto-confirm 必然缺少合法的 post-Preview event B。

## Freshness 与单次消费

Fresh 的必要条件全部成立才为 true：

```text
signature valid
issuer_key_id trusted
channel == wecom
account/owner/conversation digest matches expected Pilot binding
event_type == owner_dm_text
received_at <= accepted_at + allowed_clock_skew
now - accepted_at <= configured_freshness_window
now < expires_at
accepted_at > preview.created_at
channel_event_id_digest != Message A event digest
content digest matches exact confirmation_text
confirmation code binds the expected preview_id/revision
consumption_status == UNUSED
expected Interaction revision/CAS matches
```

`message_id changed` 单独不构成 freshness。建议 Pilot freshness window 默认为 5 分钟，但它是未来受控配置，不在
本设计写死 Runtime 值；issuer `expires_at` 不能延长 AI-Lab 本地窗口。

AI-Lab 以 `evidence_id` 与 `channel_event_id_digest` 双唯一约束 dedupe，并在 Confirmation transaction 中以 CAS 将
`UNUSED -> CONSUMED`。相同 idempotency key、相同 Interaction/Preview/payload 的响应丢失可返回既有结果；不同
payload、Preview、Interaction 或 key 必须 conflict。Hermes dedupe cache 只优化 channel delivery，绝不是消费事实源。

## 重启与恢复

- AI-Lab restart：verified evidence 与 consumption state 持久化，重启后 `CONSUMED` 仍拒绝；
- Hermes restart：不影响 AI-Lab accepted/consumed facts；Agent 可用同一 idempotency key 查询/重试结果；
- MCP restart：只影响 transport；不能重置 evidence、Preview 或 Confirmation；
- issuer restart：私钥由 OS-protected store 重新加载；同一 event 的 deterministic ID 仍触发 AI-Lab dedupe；
- storage unavailable：receiver 不返回 accepted evidence reference，plugin 不把该事件宣传成可确认，整体 fail closed；
- issuer unavailable：普通对话可按独立 policy 决定是否继续，但 Confirmation path 必须不可用，绝不降级为模型确认。

## 传输方案比较

| 方案 | Hermes source 修改 | 安全边界 | 密钥所有权 | 失败语义 | 部署/耦合 | Replay 与测试 | 结论 |
|---|---|---|---|---|---|---|---|
| A：bundled adapter → sidecar/local socket | 通常需要 adapter patch | 若 sidecar 只信 socket payload 则不足；需 adapter authenticity | sidecar private key | 必须 deposit-before-dispatch | 中等；耦合 bundled method | AI-Lab consumption；可测 | 语义好，但 patch 不优先 |
| B：Gateway Hook/Plugin → AI-Lab endpoint | Hook 无 source change | 当前 `agent:start` 字段不足且过晚 | Hook secret 易与 Agent 共域 | Hook error 当前 fail-open | 低，但安全不足 | 无 event uniqueness | 拒绝 generic Hook |
| C：AI-Lab wrapper/bridge 终止 WeCom ingress | 无 Hermes core change | 最强；AI-Lab-side process 看真实 event | wrapper private key | 可严格 fail closed | 高；重复 channel transport | 强 replay/testability | 安全强但不是最小 |
| D：user-installed WeCom platform plugin + privileged issuer helper | 无 Hermes core change | 模型前、supported plugin、helper 私钥隔离 | issuer helper private key | deposit-before-Agent；失败关闭 Confirmation | 中等；WeCom-specific | AI-Lab durable consumption；高可测 | **推荐** |

Option D 不 fork Hermes，不修改 bundled source；它使用现有 user-installed platform plugin extension。实现审查必须证明
plugin 能完整替代/委托当前 WeCom adapter contract 而不双连同一 bot。若 Hermes 当前 plugin API 无法做到稳定的
pre-Agent interception，唯一允许的 fallback 是单独提案的 minimal upstream-compatible extension point；不得在本
任务中偷塞 patch，更不得创建 fork。

## Hermes 与 AI-Lab 所有权

Hermes/plugin 可以 observe、issue、forward channel-originated evidence，但不能决定：

- Confirmation 是否接受；
- Interaction 是否进入 `AUTHORIZED`；
- Approval 是否满足；
- UserTask 是否创建；
- Execution/Verification/Canonical Commit 是否成功。

AI-Lab 必须 verify、persist、consume、audit evidence，并拥有 Preview/Confirmation/Interaction/CAS 事实。Hermes
Conversation、Memory、Tool Response 继续不具备 Approval/Business/Success authority。

## 失败语义

| 失败条件 | AI-Lab 结果 | 可否降级为模型确认 |
|---|---|---:|
| evidence missing | `trusted_ingress.evidence_missing` | 否 |
| envelope/schema invalid | `trusted_ingress.evidence_invalid` | 否 |
| signature invalid / unknown key | `trusted_ingress.signature_invalid` | 否 |
| expired / too old / future timestamp | `trusted_ingress.evidence_expired` | 否 |
| already consumed / duplicate event | `trusted_ingress.evidence_replayed` | 否 |
| wrong Owner / account / channel | `trusted_ingress.binding_mismatch` | 否 |
| wrong conversation | `trusted_ingress.conversation_mismatch` | 否 |
| wrong Interaction/Preview/code | `trusted_ingress.preview_mismatch` | 否 |
| received/accepted before Preview | `trusted_ingress.ordering_invalid` | 否 |
| message digest mismatch | `trusted_ingress.content_mismatch` | 否 |
| storage unavailable | `trusted_ingress.storage_unavailable` | 否 |
| issuer unavailable | `trusted_ingress.issuer_unavailable` | 否 |
| revision/CAS conflict | `interaction.confirmation_conflict` | 否 |

所有失败都返回脱敏 `FailureInfo`，不记录 raw Owner ID、raw event ID、raw content、signature private material 或
internal credential。失败不能修改 UserTask，也不能把 Preview 升级为 Confirmation。

## Phase 1 唯一解锁门禁

以下全部经实施证据与独立审查通过前，`PHASE_1_NOT_AUTHORIZED`：

- Fresh Owner Evidence 为 supported，且证据在模型前产生；
- LLM 不能 mint/alter/选择 Owner、event ID 或 timestamp；
- 同一 evidence/event single-use、dedupe、CAS 与 restart-safe；
- AI-Lab 可证明 Message B evidence `accepted_at > preview.created_at`；
- wrong owner/channel/conversation/interaction/preview/content 全部 deny；
- same-event replay 与 Message A same-turn auto-confirm deny；
- evidence/issuer/storage 不可用时 fail closed；
- Confirmation intent 与指定 Preview code 确定性绑定；
- valid Confirmation 前 UserTask business mutation 保持 0；
- 不依赖真实 Provider；MCP success 不升级为 business success；
- secret、raw Owner ID 与 raw chat content 不进入 Git/audit plaintext。

该门禁只允许未来单独讨论 Phase 1，不自动授权 Phase 1、Phase 2、真实 UserTask mutation、QUALITY-003、
REL-036 或 v0.36.0。

## 实施切片建议

本节不是实施授权，只用于降低后续评审耦合：

1. `IB-IMP-A`：Hermes user-installed platform plugin/issuer helper spike，只证明 pre-Agent envelope 与 key isolation；
2. `IB-IMP-B`：AI-Lab verifier/receiver/persistence 与 restart/replay contract；
3. `IB-IMP-C`：future confirm evidence reference、deterministic intent、atomic consumption；
4. `IB-ACC`：执行 IB-A～IB-O acceptance，独立安全/架构审查；
5. 只有全部通过后，才可单独申请 Phase 1 authorization。

任何切片都必须从新的精确 Base、独立任务与独立授权开始。本 Draft 不创建代码、Schema、endpoint、plugin、Hook、
socket、key、UserTask 或真实 Message B。

## 治理停止点

```text
INGRESS_EVIDENCE_BRIDGE_DESIGN:
DRAFT / PENDING_INDEPENDENT_REVIEW

FRESH_OWNER_INGRESS_EVIDENCE:
UNSUPPORTED

PHASE_1:
NOT_AUTHORIZED

PHASE_2:
NOT_AUTHORIZED

BRIDGE_IMPLEMENTATION:
NOT_AUTHORIZED

REAL_BUSINESS_MUTATION:
NOT_AUTHORIZED
```

完成本规划后停止，等待独立规划审查。
