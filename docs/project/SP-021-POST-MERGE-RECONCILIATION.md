# SP-021 合并后治理对账（Post-Merge Reconciliation）

- 任务：SP-021A — SP-021 Post-Merge Reconciliation
- 状态：OPEN / DRAFT / PENDING_INDEPENDENT_REVIEW / NOT_READY / NOT_MERGE_AUTHORIZED / SELF_CLOSING
- 生效规则：本记录在 SP-021A Draft PR 经独立审查、另行授权并合并进入 `main` 时自动成为最终权威对账记录；不得创建 SP-021B 或递归 post-merge reconciliation。

## 合并事实（Merge facts）

| 事实 | 权威值 |
|---|---|
| Feature PR | #68 — `SP-021: implement canonical trusted interaction domain` |
| Approved Head | `3c899d6a0d83d3d546ce0eb38ec921181dbe2d81` |
| Authorized Base | `072276207ec0cc0d69372ef38e833c3e1b72ae90` |
| Squash Merge Commit | `e59091d5a54009ac87164433422c204144d21234` |
| Merge Time UTC | `2026-08-09T11:48:19Z` |
| Parent Count / Unique Parent | `1` / `072276207ec0cc0d69372ef38e833c3e1b72ae90` |
| Base → Merge | ahead `1` / behind `0` |
| Merge Commit Title | `feat(interaction): add canonical trusted interaction domain` |
| Implementation Scope | 28 files |

PR #68 已 `MERGED / CLOSED`。上述值是已经独立确认的历史事实，不由本对账任务重算或重解释。

## 独立审查（Independent review）

首轮独立审查发现并阻止了四项 blocker：

1. canonical commit authority；
2. execution intent crash gap；
3. create idempotency atomicity；
4. approval authority fail-closed。

这些问题均在 Approved Head `3c899d6a0d83d3d546ce0eb38ec921181dbe2d81` 完成修正，并经最终独立复核通过。保留此段作为实现者不能自证、审查必须先于 Ready 与 Merge 的工程治理证据。

## 主分支质量门禁（Main Quality Gate）

| 检查 | 结果 |
|---|---|
| Run / Head | `31311699187` / `e59091d5a54009ac87164433422c204144d21234` |
| Ruff | SUCCESS |
| real-test collection isolation | 10 passed / 5 skipped |
| pytest non-real | 1731 passed / 6 skipped / 27 warnings |

GitHub hosted runner 在该 Gate 中使用 `OPENAI_API_KEY=""` 与 `AI_LAB_LLM_API_KEY=""`，没有调用真实 Provider；这不是 `DISABLED` sentinel 验证，也不解决 QUALITY-004。SP-021A 本地验证必须使用非空无效 sentinel，并先确认 real tests 全部 skip。

## 最终范围（Final scope）

SP-021 实际建立了以下 AI-Lab-owned canonical 能力：

- canonical Interaction aggregate；
- Preview、Confirmation 与独立 Approval 事实；
- Execution、Verified Result 与 Canonical Commit Evidence；
- Recovery、Status/View 与 Audit Evidence；
- Workspace fail-closed、revision/CAS 与持久化 idempotency；
- restart recovery；
- additive `interactions.db` schema initialization（没有 standalone migration file）；
- 默认禁用的 production ports；
- deterministic Reference/Fake test authorities。

上述是 SP-021 已合并实现的历史范围。SP-021A 本身只修改治理文档、机器状态与治理测试，不修改产品代码、Schema、Migration 或 Runtime。

## 最终治理状态（Final governance state）

```text
SP-021:
APPROVED /
MERGED /
MAIN_QUALITY_GATE_PASSED /
POST_MERGE_RECONCILED /
ARCHIVED

ACC-021 A-R:
PASSED /
FINAL /
INDEPENDENT_REVIEW_PASSED

SP-021A:
SELF_CLOSING /
NO_RECURSIVE_RECONCILIATION
```

Current Product SP 与 Current Governance Task 均为 None。INT-001 是 `NEXT_CANDIDATE / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION / IMPLEMENTATION_NOT_APPROVED`；PILOT-001 与 REL-036 均保持 `NOT_STARTED / NOT_APPROVED`。

## 保持不变的边界（Preserved boundaries）

- No Hermes integration；
- No MCP product integration；
- No Enterprise WeChat integration；
- No real external executor 或 real Provider；
- No generic Agent、Tool、Workflow 或 Coordination expansion；
- No version bump、Tag 或 Release；
- QUALITY-003 保持 `CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED`，历史 observation `test_deepseek_brief → daily_review.date_invalid` 不变；
- QUALITY-004 保持 `CANDIDATE / SAFETY_RELEVANT / NOT_STARTED / NOT_AUTHORIZED`；
- PR #62 保持 `CLOSED / DRAFT / NOT_MERGED / SUPERSEDED_BY_STRAT_001 / IMPLEMENTATION_NEVER_AUTHORIZED`，Head 为 `31cf7125b2543fb2d29ed38f373ddcebe4170b70`。

版本继续为 `0.35.0`。`v0.35.0` annotated tag object 为 `99de47895b967bc41c3b1dcb3d2caaa630fcd4de`，peeled commit 为 `60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`；现有 Published Pre-release 不变。

## 授权边界（Authorization boundary）

本记录不授权 SP-021A Ready 或 Merge，也不授权 INT-001、PILOT-001、REL-036、QUALITY-003、QUALITY-004 或 `v0.36.0`。后续只能通过新的明确 Owner 授权继续。
