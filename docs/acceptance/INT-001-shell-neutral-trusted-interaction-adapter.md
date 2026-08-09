# ACC-INT-001 — Shell-Neutral Trusted Interaction Adapter 验收

- 状态：AUTOMATED_EVIDENCE_PASSED / PENDING_INDEPENDENT_REVIEW
- Base：`49d77b6bd6bde3fe39eaecd5a7f8aa5b66249356`
- Real Provider calls：0
- Real Hermes calls：0

## 验收矩阵（Acceptance Matrix）

| 场景 | 验收目标 | 自动证据状态 |
|---|---|---|
| A | Shell-neutral ownership；无 repository / DB / raw SQL / Hermes 私有依赖 | PASSED |
| B | identity / Workspace binding 缺失时 fail closed | PASSED |
| C | operation policy 缺失时 fail closed | PASSED |
| D | Preview 零外部副作用 | PASSED |
| E | create + preview 组合 idempotency；payload conflict 可见 | PASSED |
| F | Confirmation 精确绑定 canonical Preview/actor/Workspace/revision | PASSED |
| G | Modify supersede 旧 Preview，旧 consent 失效 | PASSED |
| H | Cancel 委托 canonical safety rules | PASSED |
| I | Status 直接投影 canonical state | PASSED |
| J | View 使用 canonical available operations | PASSED |
| K | MCP exact allowlist；无 approve/execute/verify/commit tools | PASSED |
| L | MCP/transport success 不等于 business success | PASSED |
| M | FailureInfo 复用且 secrets 脱敏 | PASSED |
| N | Interaction ID/status 在 restart 后可恢复 | PASSED |
| O | Recovery 只调用 canonical recover，不 re-execute | PASSED |
| P | 两种 Shell assertion 可观察同一 canonical Interaction | PASSED |
| Q | 全产品 non-real regression 与 credentials isolation | PASSED |

## 证据位置（Evidence Locations）

- `tests/applications/trusted_interaction_adapter/test_adapter_service.py`
- `tests/integration/test_trusted_interaction_mcp_projection.py`
- `tests/acceptance/test_acc_int_001_shell_adapter.py`
- `tests/governance/test_project_state_consistency.py`

## 结果解释（Interpretation）

自动测试通过不构成最终独立审查、Ready 或 Merge 授权。A～Q 自动证据已通过，并将在 Draft PR
当前 Head 上提交独立审查；文档保持 `PENDING_INDEPENDENT_REVIEW`。

## 排除范围（Exclusions）

未执行真实 Hermes、真实 Provider、真实外部动作、企业微信、ApprovalAuthority、
Execution/Verification/CanonicalCommit adapter 或 Pilot 验收。QUALITY-003 与 QUALITY-004 状态未
改变。
