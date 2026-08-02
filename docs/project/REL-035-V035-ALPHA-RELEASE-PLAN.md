# REL-035 — v0.35.0 Alpha 发布收口规划

> 任务类型（Task Type）：`RELEASE_GOVERNANCE`
> 历史规划 Base（Planning Base）：`5456ed2406fa54443a02b436e2684bf90698afea`
> 历史规划基线状态（Planning Baseline Original State）：`PLANNING_BASELINE_DEFINED / IMPLEMENTATION_NOT_APPROVED / NOT_STARTED`
> 规划合并提交（Planning Merge Commit）：`e596c3331ed86dbba3aeded3ccd61517d1901559`
> 实施 Base（Implementation Base）：`e596c3331ed86dbba3aeded3ccd61517d1901559`
> 当前源码版本（Current Source Version）：`0.35.0`
> 当前状态（Current State）：`FINAL_RECONCILED / ARCHIVED`
> Tag `v0.35.0`：`ANNOTATED / REMOTE_VERIFIED`
> GitHub Release `v0.35.0`：`PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED`

## 1. 版本定义

- 目标版本：`v0.35.0 Alpha`
- 发布名称：`v0.35.0 Alpha — Local Daily Operating Loop`
- 发布类型：GitHub Pre-release
- 二进制附件：None；不上传 wheel 或 sdist

本版本面向本地单用户的日常经营与工作管理。用户通过统一 Composition Root 管理
UserTask、Reminder、Waiting-For、Work Log 与 Unified Inbox，查看 Agenda 和 Daily
Review，获得确定性 Action Hints，执行明确的 Review-to-Action 操作，并完成优雅关闭、
重启恢复、静止备份与隔离恢复。

这仍是 local-first、single-user-oriented 的 Alpha，不构成 production-ready 声明。

## 2. 用户可见能力范围

| 能力 | 来源 | 发布口径 |
|---|---|---|
| Canonical Waiting-For Domain | SP-016 | 独立领域、持久化、生命周期与历史 |
| Waiting-For 确定性交互与 Inbox 确认闭环 | SP-017 | 捕获确认、转换、恢复与幂等 |
| Canonical Work Log 查询边界 | SP-018 | workspace-safe 查询、canonical/legacy ID 与显式上下文 |
| Daily Review Read Model | SP-019 | 非持久化、确定性、只读聚合 |
| Windows Local Daily Profile | SP-020 | 完整显式配置与 profile validation |
| 正式 Daily Review CLI | SP-020 | 与 API/CEO Assistant 复用同一服务 |
| Deterministic Action Hints | SP-020 | 无 LLM、无写入的 presentation |
| Review-to-Action Delegation | SP-020 | 写入委托既有 canonical services |
| Scheduler 持续运行与恢复验证 | SP-020 | 受控进程级验收范围 |
| Graceful Shutdown 与重复 Shutdown | SP-020 | 幂等关闭、连接释放与恢复 |
| Quiescent Backup 与 Isolated Restore | SP-020 | 停机后完整 data directory 复制与隔离恢复 |

上述能力只按 SP-016～SP-020 已通过的合同与验收范围发布，不扩展新的产品行为。

## 3. 明确非目标

以下能力不属于 v0.35.0，不是本次发布阻断项，也不得在 REL-035 中实现：

- External Notification Delivery（外部通知投递）；
- Recurring Reminder（周期提醒）；
- Web UI（网页界面）；
- OAuth / JWT / RBAC（身份与权限系统）；
- Strong Multi-Tenant Isolation（强多租户隔离）；
- Knowledge Main Path（Knowledge 产品主链路）；
- Automatic LLM Tool Selection（自动模型工具选择）；
- General Natural-Language Date Engine（通用自然语言日期引擎）；
- Production-Ready Claim（生产就绪声明）；
- High Availability（高可用）；
- Distributed Storage（分布式存储）；
- Online Cross-Database Consistent Snapshot（在线跨数据库一致快照）；
- Docker Production Deployment Certification（Docker 生产部署认证）。

## 4. 数据兼容边界

### 4.1 冻结结论

- 数据迁移：No destructive database migration is required.
- 既有表：No existing v0.34.0 table rewrite is required.
- 历史导入：No legacy data import is required.
- 双写：No dual-write migration is required.

这不表示 v0.35.0 没有新增数据库对象。SP-016 已引入 `followups.db`；
`waiting_for_items` 与 `waiting_for_events` 使用 `CREATE TABLE IF NOT EXISTS`
初始化，相关索引使用 `CREATE INDEX IF NOT EXISTS` 初始化。

使用现有 v0.34.0 data directory 启动 v0.35.0 Release Candidate 时，已有 UserTask、Reminder、
Inbox 和 Work Log 数据保持原样。若 `followups.db` 不存在，当前代码按需创建该文件、
表与索引；这是增量初始化，不是破坏性迁移。

### 4.2 数据兼容验证

正式实施必须在隔离副本上验证：

1. 以包含既有 UserTask、Reminder、Inbox、Work Log 数据且不含 `followups.db` 的
   v0.34.0 数据目录启动 release candidate；
2. 确认既有数据可读且未发生表重写或导入；
3. 触发 Waiting-For 初始化，确认只新增 `followups.db`、两张表和既定索引；
4. 重启后复查既有数据与新 Waiting-For 数据；
5. 对测试前后备份做文件清单与关键记录对账。

若现有 v0.34.0 数据无法安全读取，立即停止发布并评估 Product Fix SP。

## 5. 配置升级边界

旧 `.env` 不保证满足 Local Daily Profile。升级时必须显式配置并通过 profile
validation：

- `AI_LAB_DATA_DIR` 为源码 checkout 外的稳定绝对路径；
- `AI_LAB_SQLITE_DIR` 为绝对路径且位于 `AI_LAB_DATA_DIR` 内；
- `AI_LAB_TIMEZONE` 为有效 IANA timezone；
- `AI_LAB_PROVIDER_MODE` 显式设置；
- 所有 Local Daily feature flags 显式设置；
- `AI_LAB_API_TOKEN` 显式设置且不得提交；
- `AI_LAB_TENANT_ID`、`AI_LAB_WORKSPACE_ID`、`AI_LAB_NAMESPACE`、
  `AI_LAB_SESSION_ID` 与 `AI_LAB_AGENT_ID` 组成完整 WorkspaceKey 上下文。

推荐升级路径：

1. 停止 v0.34.0 进程；
2. 确认数据库连接已释放；
3. 完整备份现有 data directory；
4. 将数据目录放在源码 checkout 外的稳定绝对路径；
5. 切换或安装 v0.35.0 release candidate；
6. 复制并调整 `config/local-daily.env.example` 所列配置；
7. 执行 profile validation；
8. 启动服务并完成 smoke。

配置校验失败必须保持 fail closed；不得自动猜测路径、timezone、Provider、feature
flags、token 或 WorkspaceKey。

## 6. Release Notes 结构

正式 Release Notes 必须至少包含：

1. Release identity：版本、名称、Alpha/Pre-release 与无二进制附件；
2. Highlights：Local Daily Operating Loop 的用户价值；
3. Included capabilities：按 SP-016～SP-020 列出；
4. Entry points：Local Daily Profile、CLI、API 与 CEO Assistant 的支持边界；
5. Upgrade from v0.34.0：停机、备份、配置调整、validation 与 smoke；
6. Data compatibility：既有数据保持、`followups.db` 增量初始化；
7. Security and operating boundaries：本地单用户、静态 token、无强多租户；
8. Known limitations / non-goals；
9. Verification：release candidate、build、metadata、安装与 post-merge 证据；
10. Source and provenance：frozen release head、Tag target、Release URL 与发布时间。

Release Notes 不得宣称未验收能力、production-ready、在线跨库一致快照或二进制发布。

## 7. 正式实施范围

Planning PR 已合并且 Owner 已独立授权 Implementation；唯一实施边界为
`REL-035-IMPLEMENTATION-TASK.md`。实施只允许：

- 将 `pyproject.toml` 与机器可读当前版本从 `0.34.0` 提升到 `0.35.0`；
- 生成正式 v0.35.0 Release Notes；
- 对账 README、CHANGELOG、项目状态、版本矩阵、限制和发布清单；
- 执行数据兼容、配置升级、测试、smoke、build、metadata 与全新安装验证；
- 合并后对账，冻结 Release Head；
- 在独立授权后依次创建 Tag 与 GitHub Pre-release；
- 输出最终发布报告。

实施不得加入产品功能、Schema/Migration、依赖、CI、运行时配置逻辑或新的 Product SP。

## 8. 验证矩阵

| 门禁（Gate） | 最低验证 | 通过标准 |
|---|---|---|
| Governance | `python -m pytest tests/governance -q` | REL-035 类型、状态、版本与文档一致 |
| Version | `python -m pytest tests/core/test_version.py -q` | runtime 与 distribution 版本一致 |
| Ordinary regression | non-real 全量 pytest | 0 新增失败，不调用真实 Provider |
| Full regression | `python -m pytest tests -q --tb=no` | 如实分类 real-provider 环境错误 |
| Lint | Ruff 检查本轮 Python 变更 | SUCCESS |
| Upgrade compatibility | v0.34.0 数据隔离副本 | 既有数据可读；只允许缺失对象增量初始化 |
| Profile | Local Daily profile validation | 必填配置完整且 fail closed |
| Smoke | profile、service、Daily Review、shutdown/restart | 入口可执行、关键读写闭环通过 |
| Build | `python -m build` | wheel 与 sdist 构建成功但不提交/上传 |
| Metadata | 解包与全新安装检查 | version 均为 `0.35.0`，包发现完整 |
| Diff hygiene | `git diff --check` 与变更清单 | 只含授权实施文件，无运行数据/秘密 |
| Post-merge | main Quality Gate + reconciliation | 成功后才能冻结 Release Head |

历史 Planning PR 只验证规划状态并保持 `0.34.0`。当前实施已将源码版本提升至
`0.35.0`，完成 Release Candidate 验证；没有重跑 ACC-020 A～V。

## 9. 发布状态机

```text
PLANNING_BASELINE_DEFINED
IMPLEMENTATION_NOT_APPROVED
NOT_STARTED

→ IMPLEMENTATION_APPROVED
  IMPLEMENTATION_IN_PROGRESS

→ SOURCE_VERSION_UPDATED
  RELEASE_DOCUMENTATION_UPDATED
  RELEASE_CANDIDATE_VALIDATED

→ RELEASE_PR_APPROVED
  RELEASE_PR_MERGED
  MAIN_QUALITY_GATE_PASSED

→ POST_MERGE_RECONCILED
  RELEASE_HEAD_FROZEN

→ TAG_AUTHORIZED
  TAG_CREATED

→ GITHUB_RELEASE_AUTHORIZED
  PRE_RELEASE_PUBLISHED

→ RECONCILED
  ARCHIVED
```

Planning PR Approval、Implementation Approval、Release PR Merge、Tag Authorization 与
GitHub Release Authorization 是五个独立治理事件，不得合并或相互推导。

## 10. 授权顺序

1. Planning PR 独立审查与合并；
2. Owner 冻结最新 main 为 Implementation Base，并明确授权实施；
3. Release PR 独立审查与合并，main Quality Gate 通过；
4. Post-Merge Reconciliation 完成并冻结 Release Head；
5. Owner 单独授权创建 `v0.35.0` Tag，校验 Tag 精确指向 frozen head；
6. Owner 单独授权发布 GitHub Pre-release，再校验发布事实。

第 1～6 步均已按独立授权事件完成。Release PR #60 已合并，main Quality Gate 成功，
Release Head 已冻结，annotated Tag 与 GitHub Pre-release 均已远端验证。本规划的历史授权
顺序不因发布完成而改变。

## 11. 停止条件

任一条件命中必须停止，不得扩大 REL-035：

- 授权 Base SHA、工作区、开放 PR、v0.34.0 Tag 或 GitHub Release 外部事实不符；
- `v0.35.0` Tag 或 GitHub Release 已存在；
- 发现 SP-016～SP-020 的真实未完成产品缺陷或 v0.34.0 数据不可安全读取；
- 需要修改产品 Python、Schema/Migration、依赖、CI 或 Local Daily Profile 行为；
- 需要重跑/改写 ACC-020 或修改历史 Acceptance Evidence；
- 需要删除、skip、xfail 或放宽既有断言；
- 原始 Base 普通测试失败，或规划必须拆成 Product Fix SP。

停止报告必须列明触发条件、仓库事实、证据、发布影响、建议下一步以及是否需要
Product Fix SP。

## 12. 回滚原则

- Planning PR：在合并前通过普通 Git revert/关闭 PR 回滚，不影响产品版本、Tag 或 Release；
- Release PR：在 Tag 创建前优先 revert 合并提交，并重新通过 main Quality Gate；
- Tag：只在明确授权且确认没有已发布 Release/外部消费者后处理，禁止静默移动 Tag；
- GitHub Release：已发布后不通过改写历史伪装回滚；撤回、标记或补发必须单独授权并保留审计记录；
- 数据：始终保留升级前完整 data directory 备份；恢复必须写入隔离目录并验证，禁止覆盖唯一副本；
- 任何回滚都不得自动恢复到“不受支持但看似能跑”的旧配置。

## 13. 历史规划基线与当前结论

Planning Baseline Original State：

```text
REL-035:
PLANNING_BASELINE_DEFINED /
IMPLEMENTATION_NOT_APPROVED /
NOT_STARTED
```

Current Implementation State：

```text
Planning Merge Commit:
e596c3331ed86dbba3aeded3ccd61517d1901559

Implementation Base:
e596c3331ed86dbba3aeded3ccd61517d1901559

Current Source Version:
0.35.0

REL-035:
FINAL_RECONCILED /
ARCHIVED

v0.35.0:
PRE_RELEASE_PUBLISHED

Tag v0.35.0:
ANNOTATED / REMOTE_VERIFIED

GitHub Release v0.35.0:
PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED
```
