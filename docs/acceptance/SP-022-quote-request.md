# ACC-022 — Quote Request 规划级验收矩阵

> 状态：PLANNING_BASELINE / 0_EXECUTED / NOT_PASSED
> 日期：2026-08-15
> 适用任务：SP-022
> 实现：NOT_AUTHORIZED

## 使用规则

本文件只定义未来验收场景，不记录执行证据。所有场景当前均为 `PLANNED / NOT_EXECUTED`；只有相应 Slice 获得独立实现和验收授权后才能执行。real Provider、LLM 文本、HTTP 2xx 或 CLI exit 0 均不能单独证明业务成功。

## 场景矩阵

| ID | 切片 | 场景与预期 | 状态 |
|---|---|---|---|
| ACC-022-A | A | create 生成稳定不可复用 Quote ID、revision=1，canonical read-back 匹配 | PLANNED / NOT_EXECUTED |
| ACC-022-B | A | get 仅返回同 WorkspaceKey 对象；not found 使用稳定错误 | PLANNED / NOT_EXECUTED |
| ACC-022-C | A | list 以 WorkspaceKey 隔离并稳定分页，不泄露其他 workspace | PLANNED / NOT_EXECUTED |
| ACC-022-D | A | 跨 workspace get/link/mutation 全部 fail closed 为 `quote.workspace_mismatch` | PLANNED / NOT_EXECUTED |
| ACC-022-E | A | expected revision 正确时 CAS 成功并仅递增一次 | PLANNED / NOT_EXECUTED |
| ACC-022-F | A | stale revision 返回 `quote.revision_conflict`，不覆盖 canonical fact | PLANNED / NOT_EXECUTED |
| ACC-022-G | A | 同 idempotency key、同 payload 重试返回相同 Quote/Verified Result且无重复 Audit | PLANNED / NOT_EXECUTED |
| ACC-022-H | A | 同 key、不同 payload/operation 返回 `quote.idempotency_conflict`且零额外写入 | PLANNED / NOT_EXECUTED |
| ACC-022-I | A | create -> DRAFT，满足前置条件后 DRAFT -> QUALIFIED | PLANNED / NOT_EXECUTED |
| ACC-022-J | A | QUALIFIED -> READY_FOR_QUOTE，要求 owner、范围和 Next Action | PLANNED / NOT_EXECUTED |
| ACC-022-K | A | READY_FOR_QUOTE -> CLOSED_WON，成交证据缺失时拒绝 | PLANNED / NOT_EXECUTED |
| ACC-022-L | A | READY_FOR_QUOTE -> CLOSED_LOST，未成交原因缺失时拒绝 | PLANNED / NOT_EXECUTED |
| ACC-022-M | A | 非终态 -> CANCELLED 需要原因和人工确认 | PLANNED / NOT_EXECUTED |
| ACC-022-N | A | CANCELLED -> DRAFT 需要 reopen reason、引用复核和人工确认 | PLANNED / NOT_EXECUTED |
| ACC-022-O | A | CLOSED_WON/CLOSED_LOST 及所有未列出跃迁返回 `quote.invalid_transition` | PLANNED / NOT_EXECUTED |
| ACC-022-P | A | persistence failure/unknown 不宣称成功，保留可恢复 FailureInfo | PLANNED / NOT_EXECUTED |
| ACC-022-Q | A | CLI/API 将稳定 FailureInfo 映射为非零退出码/非 2xx，并保留 machine code | PLANNED / NOT_EXECUTED |
| ACC-022-R | A | command accepted 后必须 canonical read-back、Audit 与 Verified Result 才声明成功 | PLANNED / NOT_EXECUTED |
| ACC-022-S | B | Inbox 在 claim 后崩溃，原 key 重试只创建一个 Quote | PLANNED / NOT_EXECUTED |
| ACC-022-T | B | Quote 已创建但 Inbox 未完成，reconciliation 补 linkage/completion且不重复 Audit | PLANNED / NOT_EXECUTED |
| ACC-022-U | B | 重复 Inbox 事件返回原 claim/Quote；payload conflict fail closed | PLANNED / NOT_EXECUTED |
| ACC-022-V | B | reconciliation scan/repair 可重复、稳定分页并保留最终失败证据 | PLANNED / NOT_EXECUTED |
| ACC-022-W | A/B | Follow-up 只引用 Waiting-For；owner/status/due/history 不在 Quote 中复制 | PLANNED / NOT_EXECUTED |
| ACC-022-X | A/C | Next Action 由 Quote 拥有；Daily Review 与 Action Hint 只读投影且不能反向修改 | PLANNED / NOT_EXECUTED |
| ACC-022-Y | C | projection failure 记录 `quote.projection_failed` 与 repair cursor，不回滚 Quote | PLANNED / NOT_EXECUTED |
| ACC-022-Z | D | CEO Assistant 未获独立授权时 intent mapping fail closed、业务写入为 0 | PLANNED / NOT_EXECUTED |
| ACC-022-AA | A-D | Audit/FailureInfo 的 workspace、ID、revision、operation、trace/correlation 与结果一致 | PLANNED / NOT_EXECUTED |
| ACC-022-AB | A-D | LLM/tool 文本与 transport success 不能替代 canonical read-back 或 Verified Result | PLANNED / NOT_EXECUTED |

## 通过门槛

- 当前执行数必须保持 `0`，通过数必须保持 `0`。
- 每个场景需要可复现输入、canonical before/after、Audit/FailureInfo、unexpected writes 与 Provider call 计数。
- A、B、C、D 分别按独立授权执行；某一 Slice 通过不得自动授权另一 Slice。
- ACC-022 只有在所有获准场景完成独立证据复核后才可能标记 Passed；本规划不作该声明。
