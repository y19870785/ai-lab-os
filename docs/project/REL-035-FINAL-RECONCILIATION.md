# REL-035 — v0.35.0 最终发布对账与治理封存记录

> Task ID：`REL-035-FINAL`
> Task Type：`RELEASE_GOVERNANCE_RECONCILIATION`
> 对账 Base：`60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`
> 生效边界：本记录及同步治理状态随最终对账 PR 合并后生效；Draft PR 本身不授权 Ready 或 Merge。

## 1. 对账结论

`v0.35.0 Alpha — Local Daily Operating Loop` 已按独立治理事件完成 Release PR 合并、
main Quality Gate、Post-Merge Reconciliation、Release Head 冻结、annotated Tag 创建与远端
验证，以及 GitHub Pre-release 发布与远端验证。REL-035 在本最终对账 PR 合并后形成：

```text
REL-035:
FINAL_RECONCILED / ARCHIVED

v0.35.0:
PRE_RELEASE_PUBLISHED

Current Governance Task:
NONE
```

下一 Product SP 尚未批准；本对账不启动新 Product SP，也不改变产品能力边界。

## 2. Planning 与 Implementation 证据链

| 事实 | 值 |
|---|---|
| Planning Base | `5456ed2406fa54443a02b436e2684bf90698afea` |
| Planning Merge Commit | `e596c3331ed86dbba3aeded3ccd61517d1901559` |
| Implementation Base | `e596c3331ed86dbba3aeded3ccd61517d1901559` |
| Release PR | `#60` |
| Approved PR Head | `f39045410b7aacfa2c14356e5e519f8fc3b440b9` |
| Squash Merge Commit | `60fc299c4f4fd1ba22fc4a00d1490f3b2b893503` |
| Merged At | `2026-08-02T11:00:45Z` |
| main Quality Gate | `30744879482 / SUCCESS` |
| Release Head | `60fc299c4f4fd1ba22fc4a00d1490f3b2b893503` |

PR #60 使用 squash merge，合并提交的唯一父提交是 Implementation Base，Base 比较为
`ahead 1 / behind 0`。Release Head 与合并后的 `origin/main` 精确一致。

## 3. Tag 远端事实

| 事实 | 值 |
|---|---|
| Tag | `v0.35.0` |
| Tag Type | `ANNOTATED` |
| Tag Object SHA | `99de47895b967bc41c3b1dcb3d2caaa630fcd4de` |
| Tag Peeled Commit | `60fc299c4f4fd1ba22fc4a00d1490f3b2b893503` |
| Tag Message | `v0.35.0 Alpha — Local Daily Operating Loop` |

Tag object 与 peeled commit 已通过本地和 `git ls-remote --tags origin` 双重验证。Tag 未被
移动、覆盖、删除或重建。

## 4. GitHub Pre-release 远端事实

| 事实 | 值 |
|---|---|
| GitHub Release ID | `363770731` |
| Name | `v0.35.0 Alpha — Local Daily Operating Loop` |
| Type | `PRE-RELEASE` |
| Draft | `NO` |
| Published At | `2026-08-02T11:32:43Z` |
| URL | `https://github.com/y19870785/ai-lab-os/releases/tag/v0.35.0` |
| Binary Assets | `0` |
| Source Archives | GitHub automatic source archives only |

Release Body 已与经过授权的确定性状态规范化临时正文逐字核对，允许的差异仅为
CRLF/LF 与末尾换行。正文不含候选期的 `DRAFT_PR_OPEN`、
`PENDING_INDEPENDENT_REVIEW`、`NOT_PUBLISHED`、未合并 PR 或未冻结 Release Head 状态；
正文包含已远端验证的 `v0.35.0` annotated Tag、Provider calls `0` 与
`No destructive database migration is required.`。

## 5. Release Notes 来源与快照边界

Tag 中的 `docs/releases/v0.35.0-alpha.md` 是发布前 Release Candidate 审计快照，因此保留
当时的候选期状态。公开 GitHub Release Body 以该文件为唯一来源，只执行获得授权的五项
确定性发布状态规范化；没有使用 `--generate-notes`，没有添加额外发布内容。

main 中的 `docs/releases/v0.35.0-alpha.md` 由本最终对账 PR 更新为正式发布事实，同时保留
全部能力、升级、数据兼容、安全边界、已知限制和验证结果。Tag 指向的历史快照不修改。

## 6. 已完成的候选版本验证

| 验证项 | 结果 |
|---|---|
| Governance + Version | `37 passed` |
| pytest non-real | `1708 passed / 27 warnings` |
| Full pytest | `1708 passed / 5 skipped / 27 warnings` |
| Ruff | `PASS` |
| Runtime Version | `0.35.0` |
| Distribution Metadata | `0.35.0` |
| Build | `ai_lab-0.35.0-py3-none-any.whl` / `ai_lab-0.35.0.tar.gz` |
| Twine | `PASS` |
| Fresh Installation | `PASS` |
| Provider Calls | `0` |

Post-Merge Reconciliation 在独立 detached worktree 对 `60fc299c...` 重新执行 Version、build、
Twine 和 wheel METADATA 检查；merge tree 与 Approved PR Head tree 相同。纯治理最终对账不
重跑 ACC-020 A～V、真实 Provider、产品 smoke、数据兼容升级、build、Twine 或 fresh-install。

## 7. 两次发布前安全停止

```text
Attempt 1:
RELEASE_BODY_GENERATION_CONTRACT_MISMATCH
原因：授权脚本预期下划线形式，Tag 原文使用空格形式。
远端影响：NONE

Attempt 2:
POWERSHELL_EMPTY_ARRAY_INLINE_COUNT_MISJUDGMENT
发生位置：Release 创建之前。
远端影响：NONE
```

两次停止都发生在 `gh release create` 之前，没有创建额外 Release、Draft Release、Tag、
附件或其他远端对象。它们是授权脚本/命令 harness 问题，不是产品缺陷、测试失败或发布回滚。

## 8. 变更与非变更声明

本最终对账只修改发布治理文档、`project_state.json` 与治理测试：

```text
Product Code Changed: false
Schema Changed: false
Migration Changed: false
Dependencies Changed: false
CI Changed: false
Provider Calls: 0
Tag Mutated: false
GitHub Release Mutated After Publication: false
```

已知产品限制保持不变：系统仍是 Alpha、local-first、single-user-oriented；不是
production-ready、enterprise-ready、stable release 或 general availability。

## 9. 封存条件

以下条件全部成立后，本记录随最终对账 PR 合并，REL-035 才正式封存：

1. 本 PR 只包含授权治理文件；
2. Governance、Version、non-real、full pytest 与 Ruff 通过；
3. Markdown 动态计数为 `180`，仓库自有 Markdown 为 `180`，新增治理 Markdown 为 `7`；
4. 独立审查确认外部 Tag/Release 事实未漂移；
5. Owner 单独授权 Ready 与 Merge；
6. 合并后的 main Quality Gate 成功并完成最终 post-merge 事实核验。

Draft PR 创建不满足第 5、6 项，也不构成 Ready 或 Merge 授权。
