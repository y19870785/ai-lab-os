# REL-035 — v0.35.0 Alpha 发布收口实施任务书

> 本文件是未来 REL-035 正式实施的唯一授权边界；当前不构成实施、合并、Tag 或
> GitHub Release 授权。

## 1. 任务身份

```text
Task ID:
REL-035

Task Type:
RELEASE_GOVERNANCE

Target Version:
0.35.0

Target Release Name:
v0.35.0 Alpha — Local Daily Operating Loop

Future Implementation Base:
Planning PR merge 后最新 main，由 Owner 重新冻结

Future Branch:
chore/rel-035-v035-alpha-release-consolidation

Future PR Title:
chore(release): consolidate v0.35.0 alpha release

Implementation Status:
NOT APPROVED / NOT STARTED

Tag Authorization:
NOT GRANTED

GitHub Release Authorization:
NOT GRANTED
```

## 2. 启动授权与基线

只有 Planning PR 已合并、Owner 明确给出最新 main 的完整 40 位 SHA，并单独声明
`REL-035 IMPLEMENTATION APPROVED` 后，才能启动本任务。规划批准或合并本身不授权实施。

启动前必须记录：

```powershell
git fetch --prune origin
git switch main
git pull --ff-only origin main
git status --short
git rev-parse HEAD
git log -1 --oneline
git tag --list "v0.34.0" "v0.35.0"
```

并实时核验：

- HEAD 精确等于 Owner 新冻结的 Future Implementation Base；
- 工作区干净；
- 没有未审查 Product/Governance PR；
- `v0.34.0` Tag 与 GitHub Pre-release 存在且事实一致；
- `v0.35.0` Tag 与 GitHub Release 不存在。

任一不符立即停止，禁止自行改用新 SHA。

## 3. 冻结产品事实

- SP-016～SP-020 已完成、验收、对账并封存；ACC-016～ACC-020 均为 PASSED / FINAL；
- Current Product SP 与 Next Candidate Product SP 均为 None；
- 本任务不实现功能、不修产品缺陷、不修改 Schema/Migration；
- 发布范围与非目标只来自 `REL-035-V035-ALPHA-RELEASE-PLAN.md`；
- 若发现真实产品缺陷，停止并建议独立 Product Fix SP，不在 release consolidation 中夹带修复。

## 4. 允许修改范围

正式实施原则上只允许修改：

- `pyproject.toml`；
- `project_state.json`；
- `README.md`、`CHANGELOG.md`、`ARCHITECTURE.md`；
- `docs/project/REL-035-V035-ALPHA-RELEASE-PLAN.md`；
- `docs/project/REL-035-IMPLEMENTATION-TASK.md`；
- `docs/project/PROJECT_BRAIN.md`、`PROJECT_STATUS.md`、`PROJECT_HEALTH.md`；
- `docs/project/ROADMAP.md`、`RELEASE_CHECKLIST.md`、`VERSION_MATRIX.md`、
  `KNOWN_LIMITATIONS.md`；
- 正式 v0.35.0 Release Notes；
- `tests/governance/test_project_state_consistency.py` 与必要的纯治理/版本断言。

额外文件必须在最终报告中逐项解释必要性。禁止修改产品模块、依赖、build backend、
package discovery、CI、数据库代码或运行时配置逻辑。

## 5. 版本号修改范围

实施阶段只能在通过授权后，将当前发布事实从 `0.34.0` 对账为 `0.35.0`：

1. `pyproject.toml:[project].version`；
2. `project_state.json` 的 `version`、`current_version` 与当前 `release_status`；
3. 当前用户文档、版本矩阵、发布清单和 Release Notes 中的发布版本口径；
4. 治理与版本测试中的精确期望值。

不得改写 v0.34.0 历史 Release Notes、历史 Tag、历史验收证据或历史 commit 事实。
不得在 Release Candidate 验证通过前把 v0.35.0 标为 published/authorized。

## 6. Release Notes 正式生成

按规划文档定义的十段结构生成版本化 Release Notes，并明确：

- GitHub Pre-release、Alpha、无二进制附件；
- SP-016～SP-020 的已验收用户能力；
- v0.34.0 → v0.35.0 停机升级与配置调整步骤；
- 既有数据库保持、缺失 `followups.db` 的增量初始化；
- Local Daily Profile 必填配置；
- non-goals、known limitations、安全与单用户边界；
- frozen Release Head、验证结果、Tag target 与发布事实（仅在相应状态达成后填写）。

文档不得把规划、候选或未授权事件写成已发生。

## 7. README / CHANGELOG / 项目状态对账

- README：将当前版本入口和用户可见能力更新为 v0.35.0 Alpha，但保留限制；
- CHANGELOG：增加 v0.35.0 条目，区分用户变化、升级、验证与未包含范围；
- Project Brain / Status / Health：记录 REL-035 状态机的真实当前节点；
- Roadmap：把 v0.35.0 从候选开发线转为已收口版本，不提前批准后续 SP；
- Version Matrix：列入 SP-016～SP-020 能力和 v0.34.0 数据兼容边界；
- Known Limitations：删除已被 SP-020 验收推翻的当前限制，保留真实边界；
- Release Checklist：逐项记录真实执行结果，不预勾选未完成 Gate。

## 8. 升级说明

正式说明必须要求：停止 v0.34.0、确认连接释放、完整备份 data directory、使用源码
checkout 外绝对路径、安装/切换 v0.35.0、复制调整 local-daily 配置、执行 profile
validation、启动并 smoke。

不得声称“完全无新增数据库对象”。应明确 `followups.db`、`waiting_for_items`、
`waiting_for_events` 与索引在缺失时增量初始化，且无需破坏性迁移、旧表重写、legacy
import 或 dual-write。

## 9. 测试与 Smoke 矩阵

至少执行并记录：

```powershell
python -m pytest tests/governance -q
python -m pytest tests/core/test_version.py -q
python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no
python -m pytest tests -q --tb=no
python -m ruff check <本轮变更的 Python 文件>
git diff --check
```

Smoke 必须使用隔离数据与 sentinel credentials，且不调用真实 Provider：

1. profile validation 成功与关键缺失/非法配置 fail closed；
2. 服务启动与 `/health`；
3. Daily Review CLI 与 API 可执行并复用同一 WorkspaceKey；
4. 一个真实本地 work loop：写入 → Waiting-For/Inbox → Daily Review → Action Hint →
   Review-to-Action；
5. graceful shutdown、重复 shutdown、restart recovery；
6. quiescent backup 与 isolated restore；
7. 现有 v0.34.0 数据隔离副本兼容验证。

本任务不得重新执行正式 ACC-020 A～V，也不得生成或修改 ACC-020 Evidence。

## 10. 构建与安装包元数据验证

执行 `python -m build`，产物只用于本地验证且不得提交或上传。必须检查：

- wheel 与 sdist 文件名版本为 `0.35.0`；
- wheel `METADATA` 与 sdist `PKG-INFO` 的 Version 为 `0.35.0`；
- wheel/sdist 均包含预期 package 与文档，不改变 package discovery/build backend；
- 在全新隔离环境安装 wheel 后，distribution metadata 与运行时版本均为 `0.35.0`；
- 安装后的受支持 CLI/入口可执行。

若构建依赖或镜像导致失败，必须区分 harness/environment failure 与产品缺陷；不得修改
依赖或 build backend 规避。

## 11. Release PR 与 Post-Merge Reconciliation

Release PR 必须保持 Draft，直到 Owner/独立审查者明确批准 Ready。允许的状态推进：

```text
IMPLEMENTATION_APPROVED / IMPLEMENTATION_IN_PROGRESS
→ SOURCE_VERSION_UPDATED / RELEASE_DOCUMENTATION_UPDATED
→ RELEASE_CANDIDATE_VALIDATED
→ RELEASE_PR_APPROVED / RELEASE_PR_MERGED
→ MAIN_QUALITY_GATE_PASSED
```

合并后从最新 main 建立独立 reconciliation 载体，至少记录 merge commit、main Quality
Gate、版本/metadata 复验、无 Tag/Release 的当时事实，以及所有开放风险。未完成对账前
不得冻结 Release Head。

## 12. 发布 Head 冻结

只有 Release PR 已合并、main Quality Gate 成功且 Post-Merge Reconciliation 完成后，
Owner 才能冻结一个完整 SHA 为 `Release Head`。冻结记录必须包含：

- commit SHA 与 `git log -1 --oneline`；
- main Quality Gate run ID 与结论；
- 源版本、构建与安装元数据结论；
- `v0.35.0` Tag/Release 当时仍不存在；
- 变更文件与 open risks。

后续 main 移动不自动改变 frozen head；需要改动时撤销冻结并重新走 Gate。

## 13. Tag 授权

Tag Authorization 必须在 Release Head Freeze 之后单独由 Owner 明确授予。执行前再次
确认 `v0.35.0` 不存在；创建 annotated Tag 后验证其 peeled commit 精确等于 frozen
Release Head，再推送并远端复核。

禁止移动、复用或静默重建 Tag。Tag 创建不授权 GitHub Release。

## 14. GitHub Pre-release 授权

只有 Tag 远端验证完成后，Owner 才能单独授权 GitHub Pre-release。发布要求：

- Tag：`v0.35.0`；
- Name：`v0.35.0 Alpha — Local Daily Operating Loop`；
- 类型：Pre-release；
- binary assets：None；
- Body：使用已审查的正式 Release Notes；
- 发布后验证 Tag、name、prerelease flag、target、URL、时间与 assets。

禁止修改 v0.34.0 Release，禁止由 Tag Authorization 推导 Release Authorization。

## 15. 最终发布报告

报告必须包含 Base、Release PR/head/merge、main Quality Gate、Release Head、完整变更文件、
版本/数据/Schema/Migration/产品代码结论、测试与 smoke、build/metadata/install、升级兼容、
Tag 与 GitHub Release 事实、开放风险、stop conditions 和每个独立授权证据。

最终状态只能在全部事实成立后写为：

```text
REL-035:
RECONCILED / ARCHIVED

v0.35.0:
PRE_RELEASE_PUBLISHED
```

## 16. 停止条件

以下任一情况立即停止：Base/工作区/开放 PR/Tag/Release 事实不符；需要产品代码、Schema、
Migration、依赖、CI 或配置逻辑改动；v0.34.0 数据不可安全读取；治理断言只能通过删除、
skip、xfail 或放宽；普通测试在 frozen Base 已失败；需要重跑 ACC-020；需要拆分 Product
Fix SP；或任何独立授权缺失。

## 17. 当前授权边界

```text
Implementation:
NOT APPROVED / NOT STARTED

Source Version:
0.34.0 / UNCHANGED

Tag v0.35.0:
NOT AUTHORIZED / NOT CREATED

GitHub Release v0.35.0:
NOT AUTHORIZED / NOT CREATED
```
