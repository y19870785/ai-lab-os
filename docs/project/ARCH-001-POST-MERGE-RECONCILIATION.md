# ARCH-001 合并后治理对账

- 对账任务：ARCH-001A
- 状态：OPEN / DRAFT / PENDING_INDEPENDENT_REVIEW / NOT_READY / NOT_MERGE_AUTHORIZED / SELF_CLOSING
- 生效规则：本记录在 ARCH-001A Draft PR 经独立审查、Owner 授权并合并进入 main 时自动成为最终权威对账记录。
- 递归规则：ARCH-001A / SELF-CLOSING / NO_RECURSIVE_RECONCILIATION；不创建 ARCH-001B。

## 合并事实

| 事实 | 记录 |
|---|---|
| ARCH-001 Planning PR | #66 / MERGED / CLOSED |
| Approved Head | `5edbb37da6bf9d4b7dd98f5d0e860c695a08ce90` |
| Merge Base | `7bf12b1f4206608f0c67223546e8400eb9066c8e` |
| Squash Merge Commit | `4f9eab191fc0d99898ee69a2b42912017e4740e3` |
| Merged At | `2026-08-09T08:37:05Z` |
| main Quality Gate | `31303951232 / SUCCESS` |
| GitHub Ruff | SUCCESS |
| GitHub pytest non-real | SUCCESS |
| Changed-file scope | 22 files；均为规划文档、治理状态或治理一致性测试 |

Squash Merge Commit 的唯一父提交是批准的 Merge Base。`origin/main` 在对账任务开始时精确为
`4f9eab191fc0d99898ee69a2b42912017e4740e3`，没有夹带未知提交。

## 验证证据

ARCH-001 合并后的有效本地验证记录如下：

| 检查 | 结果 |
|---|---|
| governance tests | 29 passed |
| version metadata tests | 10 passed |
| pytest non-real | 1712 passed / 27 warnings |
| credentials-isolated full suite | 1712 passed / 5 skipped / 27 warnings |
| real-test collection isolation | 使用非空 sentinel `DISABLED` 后，5 项 real tests 均 skip |
| Ruff changed-Python-files | SUCCESS |
| `git diff --check` | PASS |

GitHub Quality Gate 的 real-test collection isolation 与 non-real suite 均成功；普通 Quality Gate
没有配置真实 Provider 凭据，也不把 real-provider tests 作为常规门禁。

## 决策状态

- ARCH-001：`APPROVED / MERGED / MAIN_QUALITY_GATE_PASSED / POST_MERGE_RECONCILED / ARCHIVED`。
- RFC-032：Adopted by ARCH-001 / PR #66 / Merge Commit
  `4f9eab191fc0d99898ee69a2b42912017e4740e3`。
- ADR-069、ADR-070、ADR-071、ADR-072：Accepted by ARCH-001 / PR #66 / Merge Commit
  `4f9eab191fc0d99898ee69a2b42912017e4740e3`。
- 上述状态采纳架构合同，不批准任何产品实现。

## Real Provider 误调用与质量候选项

ARCH-001 合并后的本地验证期间发生过一次 accidental / unauthorized real-provider invocation。
Windows 环境中把 Provider credential environment variable 设置为 `''` 没有形成可靠隔离，
`python-dotenv` 随后从本地 `.env` 重新载入真实凭据。该次调用再次观察到既有现象：

```text
QUALITY-003
test_deepseek_brief
→ daily_review.date_invalid
```

该事件未输出或提交 secret，未提交 Provider response body，未修改产品代码，也未启动
QUALITY-003。后续改用非空 sentinel `DISABLED`，real tests 正确 skip，最终有效的
credentials-isolated full suite 为绿色。

QUALITY-003 保持：

```text
CANDIDATE / NON_BLOCKING / REAL_PROVIDER_ONLY / NOT_STARTED / NOT_AUTHORIZED
Observation: 2026-08-09 accidental reproduction
```

同时登记 `QUALITY-004 Candidate — Real-Provider Credential Isolation Guard`：

```text
Observed: Empty-string environment overrides can allow local .env credentials
to be reloaded by python-dotenv and unintentionally enable real tests.
Status: CANDIDATE / SAFETY_RELEVANT / NON_BLOCKING_FOR_ARCH_001 /
NOT_STARTED / NOT_AUTHORIZED
```

ARCH-001A 只登记 Candidate，不实施修复。在 QUALITY-004 获得单独授权前，所有
credentials-isolated 验证必须使用非空无效 sentinel，先确认 real-test collection 全部 skip；
如果任何 real test 开始调用 Provider，必须立即停止并报告。

## 范围与不可变事实

- Product code changed：No。
- Schema / Migration changed：No。
- Runtime changed：No。
- Dependencies / lock files changed：No。
- Version：`0.35.0`，未改变。
- `v0.35.0` annotated tag object：`99de47895b967bc41c3b1dcb3d2caaa630fcd4de`，未改变。
- `v0.35.0` peeled commit：`60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`，未改变。
- GitHub Release：Existing published Pre-release / unchanged。
- PR #62：CLOSED / DRAFT / NOT_MERGED / SUPERSEDED_BY_STRAT_001 /
  IMPLEMENTATION_NEVER_AUTHORIZED；Head `31cf7125b2543fb2d29ed38f373ddcebe4170b70`，未修改或重新打开。

## 后续治理边界

对账生效后的 canonical 状态：

```text
Current Product SP: None
Current Governance Task: None
SP-021: Canonical Trusted Interaction Domain /
NEXT_CANDIDATE / NOT_STARTED / REQUIRES_SEPARATE_AUTHORIZATION /
IMPLEMENTATION_NOT_APPROVED
INT-001: NOT_STARTED / NOT_APPROVED
PILOT-001: NOT_STARTED / NOT_APPROVED
REL-036: NOT_STARTED / NOT_APPROVED
```

ARCH-001A 不启动上述任何任务，不恢复旧 PR #62 的名称或方案，不创建 ARCH-001B。
