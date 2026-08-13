# PILOT-001-P1A 内部可信入站确认 Pilot

## 1. 安全分类

本能力仅属于 `PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE`：

```text
INTERNAL_TEST_ONLY
LOCAL_TRUSTED_HOST
NOT_PRODUCTION_SECURITY
```

IB-IMP-A 的负面证据保持不变：已测试 WSL2 同 UID topology 可经
`pidfd_getfd` 复制 issuer capability，`SIGNING_ORACLE_ISOLATION` 仍为
`FAILED_FOR_TESTED_TOPOLOGY`，`INGRESS_PROCESS_ISOLATION` 仍为
`UNRESOLVED`。本 Pilot 仅在模型无法启动任意本地进程的前提下，把 hostile
same-UID process 排除在内部测试威胁模型之外。

## 2. 已实现的最小边界

- 默认 `.hermes/plugins/platforms/wecom/` 必须不存在。
- Pilot plugin 只投影到临时 Hermes project，停止后删除。
- WeCom event authority 只接受 `body.msgid`，缺失时不签发 Evidence。
- issuer 独立持有 Ed25519 private key、event identity key 与 content binding
  key；Hermes/LLM 只得到 opaque `evidence_id`。
- `TrustedIngressEvidenceEnvelopeV1` 使用 RFC 8785/JCS 签名，字段集合固定。
- Preview commit 后由 AI-Lab CSPRNG 生成一次性 challenge。
- Evidence consume、challenge consume、Confirmation fact 与 Interaction CAS
  在同一 SQLite transaction 中完成。
- 成功终点仅为 `AUTHORIZED`；Execution、Verification、UserTask mutation 与
  canonical business commit 均不启动。

## 3. Hermes 模型工具闸门

隔离 profile 必须关闭 Hermes progressive `tool_search`，并把 WeCom platform
toolset 限定为唯一 `ai-lab-p1a` MCP server。Hermes 会为 MCP tool 添加固定
namespace，实际 schema 枚举必须仅包含：

```text
mcp__ai_lab_p1a__ai_lab_interaction_preview
mcp__ai_lab_p1a__ai_lab_interaction_status
mcp__ai_lab_p1a__ai_lab_interaction_view
mcp__ai_lab_p1a__ai_lab_interaction_confirm
```

底层 MCP contract 名仍精确为任务书规定的四个 `ai_lab_interaction_*` 名称。
任何 `terminal`、`process`、文件写入、browser、generic code execution、
`tool_search/tool_call` 或额外 AI-Lab tool 出现时，必须停止为
`INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN`。

## 4. 自动验收映射

| 场景 | 验证目标 |
|---|---|
| P1A-A | 默认 live Pilot plugin 不存在 |
| P1A-B | Hermes/MCP 工具面恰好四个 |
| P1A-C | 模型无任意本地进程启动工具 |
| P1A-D | 只接受 `body.msgid`，相同 event identity 稳定 |
| P1A-E | challenge 由 AI-Lab 在 Preview 后生成 |
| P1A-F | Message A Evidence 不能越过 Preview/challenge 自确认 |
| P1A-G | 合法 Message B 只创建一个 Confirmation |
| P1A-H | Evidence 单次消费，replay 不增加 Confirmation |
| P1A-I | wrong Owner/conversation/challenge/text/revision 全部拒绝 |
| P1A-J | 相同 `body.msgid` 的 `evidence_id` 稳定 |
| P1A-K | consumption 持久化，不依赖进程内 cache |
| P1A-L | UserTask mutation 为 0 |
| P1A-M | real Provider call 为 0 |

## 5. 真实 WeCom 验收状态

2026-08-13 在全部自动测试与 Hermes 四工具闸门通过后，执行了真实单 Owner WeCom
内部验收。脱敏结果如下：

```text
Security profile: PILOT_GRADE_LOCAL_TRUSTED_HOST_PROFILE
Message A: PASS
Message A evidence: VERIFIED / UNUSED
Interaction: int_4ca06aa2ad8647b29cfb4d103a33d976
Preview: prv_0932c5f5ec764949bcb8b781abd7380a / revision 1
Canonical due_at: 2026-08-14T07:00:00+00:00
Owner local presentation: 2026-08-14 15:00 Asia/Shanghai

Expired challenge attempt: DENIED / evidence UNUSED
Wrong challenge text attempt: DENIED / evidence UNUSED
Fresh Message B: PASS
Consumed evidence: tie_pd2gl6aysreqgmtfb4g36f7lps27swz6onq7v7z5nokmuojaiolq
Consumed challenge: pch_d2cdd54ae46bc52714ac36602fc866db
Confirmation: cnf_a3d33c51adea49f99fa6aab401948df3
Interaction final state: AUTHORIZED / revision 3
Execution: NOT_STARTED
UserTask: 3 -> 3
AI-Lab Real Provider: 0
```

第一次预验收启动曾遗漏 nested project plugin 的显式 opt-in，canonical evidence 数为
`0`，因此该轮被判为无效并停止；未创建 Confirmation 或 UserTask。修订后临时 profile
显式启用 `platforms/wecom`，现场注册模块为
`hermes_plugins.platforms__wecom.adapter`，并新增回归测试防止 bundled adapter 静默回退。
同时发现 `hermes gateway run` 会自刷新已安装 systemd unit，并把临时 `HERMES_HOME`
写入 live service。该 unit 已恢复为 `/home/hechao/.hermes` 且验证为 `active`；launcher
现固定使用 Hermes venv Python 直接执行 `python -m gateway.run`，绕过 service-refresh
CLI 路径，临时 Pilot 不再改写默认 service。

第一次有效确认消息到达时 challenge 已过期，AI-Lab 返回
`trusted_confirmation.validation_denied`，Evidence 保持 `UNUSED`。随后 AI-Lab 轮换新
challenge；拼错文本再次被拒且 Evidence 未消费。最终精确的新 Owner 消息在 Preview
之后到达，Evidence、challenge、Confirmation 与 Interaction CAS 在同一事务中消费并
提交。该结果只升级为 `INTERNAL_PILOT_TRUSTED_CONFIRMATION_PROVEN`，等待独立审查。

## 6. 长期禁止结论

本 Pilot 不得写成 `PRODUCTION_READY`、`ENTERPRISE_READY`、
`GENERAL_TRUSTED_INGRESS_SUPPORTED` 或 `PROCESS_ISOLATION_RESOLVED`。
`PHASE_1_FULL`、Phase 2 与真实业务 mutation 均未授权。
