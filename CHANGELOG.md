# AI-Lab OS 更新日志

## [Unreleased] 未发布

### QUALITY-004 真实 Provider 凭据隔离保护

- 在仓库根 pytest collection 边界默认排除 `tests/real`，阻止其 `conftest.py`、测试模块和
  `load_dotenv()` 在普通 pytest、IDE、Codex Validation 与本地 Full Suite 中被导入。
- 真实 Provider 测试改为双因素显式授权：必须同时提供 `--run-real-provider` 与
  `AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1`；API Key 或 `.env` 凭据存在不再等于执行授权。
- 新增 Q4-A～Q4-G 隔离回归，覆盖真实形态假凭据、空字符串、`DISABLED` sentinel、单因素拒绝与
  双因素仅 collection 验证；QUALITY-004 验证期间不调用真实 Provider。
- P0-E 的 WeCom/MCP 环境连接与工具隔离成功，但 validation suite 曾意外执行真实 Provider，故验收
  未获最终通过。该事故属于本地测试凭据隔离安全缺陷，不是 WeCom/MCP compatibility failure。

### PILOT-001 企业微信 Owner 可信任务捕获规划

- 新增中文规划基线与分层验收计划，固定 `SINGLE_OWNER / DM_ONLY / LOCAL_HOST / ALLOWLISTED /
  TEXT_ONLY`、唯一 `user_task.create`、deterministic UserTask ID、独立 read-back、restart verification
  与 uncertain outcome 禁止重执行。
- 复用 RFC-031、RFC-032、ADR-067～072、SP-021 与 INT-001，不新增 Quote/Customer domain，
  不新增 RFC/ADR，不修改 Runtime、依赖、版本、Tag 或 Release。
- 规划基线已 `PLANNING_BASELINE_APPROVED / FINAL_INDEPENDENT_PLANNING_REVIEW_PASSED`；实现与真实
  Hermes/WeCom Pilot 均未授权，任何实现需要独立授权，REL-036 仍未启动。

### INT-001 Shell-neutral Trusted Interaction Adapter 实现

- 新增 `trusted-interaction/v1` application adapter、fail-closed identity/policy authority、
  canonical Preview/Modify/Confirm/Cancel/Status/View/Recovery projection 与 ACC-INT-001 A～Q 自动证据。
- 新增官方 `mcp>=2,<3` local optional dependency 和本地 stdio MCP exact seven-tool allowlist；
  MCP/Tool success 不等于业务成功，真实 Hermes、Channel、执行与 Provider 均未接入。
- 独立审查发现并验证修复 Modify policy/risk drift、Recovery policy gate、`final` terminality、
  runtime acceptance evidence 与 adapter/transport provenance 五项 blocker。
- ACC-INT-001 A～Q 已 `PASSED / FINAL / INDEPENDENT_REVIEW_PASSED`；PR #70 Squash Merge 为
  `c3c71c7934e50725e4a82ef745245fcdb502811c`，main Quality Gate `31324821391` 为 SUCCESS。
- INT-001 对账时 PILOT-001 仍为未授权下一候选；本次仅追加 PILOT-001 规划基线，版本、Tag 与
  Release 仍未改变。

### SP-021 可信交互领域实施与合并后对账

- 新增 AI-Lab canonical Interaction aggregate、Preview、Confirmation、Approval、Execution、
  VerifiedResult、Recovery、Status/View 与审计证据。
- 新增 `interactions.db` additive schema，复用 DatabaseManager、ConnectionLease 与 transaction；
  实现 Workspace fail-closed、revision/CAS、持久化幂等和 restart recovery。
- 新增 Shell/Transport-neutral Execution 与 Verification ports；生产 Composition Root 仅注入 disabled
  ports，测试使用 deterministic Reference ports，Tool/HTTP acknowledgement 不能产生最终成功。
- 根据独立审查补强数据库原子 create idempotency claim、execution intent/outcome crash-gap
  reconciliation、Approval authority fail-closed，以及 AI-Lab-owned `CanonicalCommitEvidence`；
  VerificationPort 不再能声明 canonical commit 成功。
- 建立 ACC-021 A～R 自动化证据；最终独立审查通过后，PR #68 Squash Merge 为
  `e59091d5a54009ac87164433422c204144d21234`，main Quality Gate `31311699187` 为 SUCCESS。
- SP-021 已完成治理对账并封存；INT-001 仅为下一候选任务，INT-001、PILOT-001、REL-036 均未启动。

### ARCH-001 可信交互架构规划与合并后对账

- ARCH-001 已通过独立审查并由 PR #66 Squash Merge：审计 v0.35.0 现有业务域与通用 Runtime，定义
  Shell-neutral / Transport-neutral Trusted Interaction Boundary、identity/Workspace fail-closed、
  canonical Preview/Confirmation、Verified Result、重试、审计与恢复合同。
- RFC-032 已 Adopted，ADR-069～072 已 Accepted；main Quality Gate `31303951232` 为 SUCCESS，
  ARCH-001 已完成自闭环治理对账并封存。
- 登记 QUALITY-003 的 `2026-08-09 accidental reproduction` 与 QUALITY-004 Candidate；不实施修复。
- 不修改产品代码、Schema、Migration、Runtime、依赖、版本、Tag 或 Release，且不启动
  SP-021、INT-001、PILOT-001 或 REL-036。

### STRAT-001 产品战略校准规划

- 将 AI-Lab OS 定位为面向个人经营者和企业真实工作流的可信业务操作系统。
- 将 Hermes 定义为首个首选但可替换的 Agent Shell；业务事实、规则、确认、审批、审计、
  Verified Result 与 Recovery 继续由 AI-Lab 掌握。
- 建立 Agent Shell / Trusted Business Core、Memory、Knowledge、Interaction 与
  Confirmation 所有权边界，冻结通用 Agent/Tool/Workflow/Coordination 平台扩张。
- 将 v0.36 拆分为 `STRAT-001 → ARCH-001 → SP-021 → INT-001 → PILOT-001 → REL-036`，
  并重新规划 v0.37 报价需求与客户跟进、v0.38 企业知识审核与引用闭环。
- PR #63 已 Squash Merge 为 `b644c38064117a4dcb906c8607c782b67aedf1a6`，main Quality
  Gate `31038950753` 为 SUCCESS；STRAT-001 已完成 post-merge reconciliation 并封存。
- RFC-031 已 Adopted，ADR-067 与 ADR-068 已 Accepted。旧 PR #62 已关闭且未合并，由
  STRAT-001 取代；其历史设计证据继续保留，但 Implementation 从未获授权。
- 本任务未修改产品代码、Schema、Migration、运行时、版本、Tag 或 Release；ARCH-001
  尚未启动且需要独立授权。

## [0.35.0] - 2026-08-02（Alpha 预发布）

- 定义 `v0.35.0 Alpha — Local Daily Operating Loop`，汇总 SP-016～SP-020 已验收能力；不新增产品行为。
- 建立 v0.34.0 数据兼容边界：无需破坏性 Migration、旧表重写、legacy import 或 dual-write；缺失 `followups.db` 时按 `IF NOT EXISTS` 增量初始化。
- 建立 Local Daily Profile 配置升级、Release Notes、测试/smoke/build/metadata 矩阵、回滚与停止条件。
- 将 Planning Approval、Implementation Approval、Release PR Merge、Tag Authorization 与 GitHub Release Authorization 保持为独立治理事件。
- REL-035 Implementation 已获授权；源码版本提升为 `0.35.0`，并新增正式 Release Notes。
- `v0.35.0` annotated Tag 已远端验证并指向冻结 Release Head；GitHub Pre-release 已发布，
  Release ID 为 `363770731`，无二进制附件，仅使用 GitHub 自动源码归档。

### SP-020 本地日常运行与复盘行动闭环实施
- 新增严格的 Windows Local Daily Profile、稳定绝对数据目录校验、安全配置摘要、完整 WorkspaceKey 默认值与覆盖能力。
- 新增正式 `daily-review` CLI、纯确定性 Action Hint，以及带显式 `expected_revision` 的 Review-to-Action UserTask complete/cancel 薄 API。
- Phase 0 已通过自动化生命周期门禁，覆盖持续 Scheduler tick、一次性 Job、周期 health 快照、partial-start rollback、重复 shutdown、连接释放与新容器恢复。
- 将 ACC-020 driver 从准备脚手架补全为可执行 Windows harness：prepare-only 保持未测量语义，rehearsal/formal 模式真实启动 Uvicorn、执行 A～V、Provider spy、静止备份与隔离恢复。
- 正式 ACC-020 在冻结实现 Head `1c9b69ee45b4e1545b67ecd841cc217e23d4f38f` 与冻结 Driver SHA-256 `99695ac3f7544eebf5058db89b2b7d39eece6aec2e042e8f5f90273a7fcae3c5` 上执行一次且仅执行一次；A～V 报告 22/22 PASS，Provider calls 为 0，独立证据复核已批准，ACC-020 为 `PASSED / FINAL`。
- 脱敏正式证据由 Commit `7a0944f4ad1deadefe636bf5abc3d30175de0b4d` 归档；不包含原始数据库、WAL/SHM、token、Authorization header、原始日志或真实业务数据。
- SP-020 Feature PR #57 已 Squash Merge 为 `9ea4b72241bd855319231c09fa6b80c112a14305`（`2026-08-01T06:29:58Z`），main Quality Gate `30687851816` 的 Ruff 与 pytest (non-real) 均为 SUCCESS；SP-020 随后完成治理对账与封存。
- SP-020A 通过 Draft PR #58 记录上述合并后稳定治理事实；该 PR 不记录自身尚未发生的 merge commit、合并时间或 post-reconciliation Quality Gate。
- 废弃 Head `bd858807262aa1b89cdb80644895afa970edcf64` 上断言覆盖不足的 rehearsal，分类为 `INVALID_ACCEPTANCE_HARNESS / DISCARDED / INSUFFICIENT_SCENARIO_ASSERTION_COVERAGE`；该记录不是产品失败，原“22/22 PASS”无效，当时 ACC-020 仍未执行。
- 收紧 ACC-020 Driver：A～V 只能由完整结构化 checks 判定，证据分别落到真实命令/HTTP 日志、SQLite 快照、EventBus/Scheduler spy、shutdown/partial-start probe 与 source/restore 逐对象比较。
- 收紧 Local Daily Profile、完整 WorkspaceKey、Action Hint 三元决策键、terminal stale revision、公共 TaskResponse 与 Scheduler health 公共读取合同。
- 未新增 Schema、Migration、依赖或 CI；版本保持 `0.34.0`，Tag 与 GitHub Release 不变。

### DOCS-001 全仓 Markdown 中文规范与统一治理
- 建立简体中文主要叙述语言政策、Git 跟踪 Markdown 完整清单与统一术语表。
- 将仓库自有 Markdown 的标题、普通叙述与治理提示统一为中文，同时保留代码、命令、API、字段、状态值与历史证据。
- 新增确定性治理门禁，检查清单完整性、中文一级标题、长篇纯英文叙述、未完成翻译标记与相对链接。
- 本任务不修改产品代码、Schema、依赖、CI、版本、Tag 或 Release，也不授权或启动 SP-020 产品实施。
- DOCS-001 已通过独立审查；Approved Head `d7a6662dddaac87b41562e2348f69e04112b2be4` 由 PR #55 Squash Merge 为 `2d04f1b8574fde43b1d64a53d1ad22573073a4ef`，合并时间为 `2026-07-29T14:43:26Z`。
- 合并后的 main Quality Gate run `30462290819` 为 SUCCESS；DOCS-001 已完成治理对账并封存，版本 `0.34.0`、Tag 与 Release 保持不变。

### SP-020 本地每日运行闭环规划基线
- 定义 Windows Local Daily Profile、稳定绝对数据目录、显式 timezone/Provider/feature/auth 配置与 localhost 启动边界。
- 规划直接复用现有 `DailyReviewService` 的正式 Daily Review CLI，以及纯确定性、无 LLM、无写入的 Action Hint presentation。
- 固定 Review canonical ID 只能委托现有 UserTask、Reminder、Waiting-For、Inbox 与 Work Log 服务；不新增 Action/Review 数据库、第二 Command Bus 或 Work Log mutation。
- 采用停机后的完整 data directory Quiescent Backup 与隔离恢复，不承诺运行中跨多个 SQLite 文件的一致快照。
- 规划合并时 RFC-029、ADR-063、ADR-064 与 ACC-020 构成 Planning Baseline；当时 SP-020 Implementation 尚未批准、未启动，ACC-020 未执行。
- 产品版本保持 `0.34.0`；Tag 与 GitHub Release 均未改变。

### SP-019 每日复盘读取模型与确定性跟进视图
- 以唯一、非持久化、纯只读 `DailyReviewService` 聚合 Work Log、UserTask、Waiting-For、Reminder 与 Inbox，支持 `today` / `yesterday`、IANA timezone、DST、当前 follow-up 与 pending Inbox。
- API、CEO Assistant 与兼容 `/brief` 共享相同 query、Workspace、分类、全局排序、分页与失败语义。
- ACC-019 A～M 已在冻结实现 Head 正式执行并全部通过，Provider calls 为 0。
- Feature PR #51 已 Squash Merge 为 `a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`，main Quality Gate `30382312419` 成功；PR #52 完成治理对账。
- RFC-028 为 Adopted，ADR-061、ADR-062 为 Accepted；SP-019 已合并、验收、对账并封存。

### SP-018 工作日志查询边界与上下文闭环
- 实现唯一 `WorkLogService` 与类型化 create/get/list 边界；CEO Assistant、API、CLI、Inbox、Daily Agenda 与 Daily Brief 共享同一服务。
- `SQLiteWorkLogRepository` 复用既有 `episodic.db / episodic_memories` 与 `DatabaseManager` connection ownership；没有 `work_logs.db`、新表、索引或迁移。
- 新记录使用 `wl_<32 hex>`；旧随机 Memory ID 以稳定 `wl_legacy_<sha256>` 只读投影，历史 `inbox_wl_...` 仅作受限兼容 alias。
- 完整 Workspace identity、精确分页、确定性过滤与显式 `ut_/rem_/wf_/inbox_` context refs 已由自动化测试覆盖；查询不写回、不发事件、不调用 LLM。
- Review fixes 将 canonical/legacy/Inbox alias 的 public get 收紧为 SQL Workspace scope 先于解码与投影；Agenda 保留真实 Work Log status 并取消 ALL 的 ±365 天窗口。
- API、CLI 与 CEO Assistant 的输入验证统一进入 WorkLogService FailureInfo；未知状态与 DST 不存在/歧义 legacy wall time均 fail closed，当地日历边界正确支持 23/25 小时日期。
- PR #46 已以 Squash Merge 合入 `83ecb557fedd1d898712afc59ad13b3e0a684413`；Approved Head 为 `e941cadc783a6ac8a4bd3c75b55adf77e0a651a3`。
- ACC-018 A～O 已在 Approved Head 完整重跑并全部通过；merge commit 通过自动 main push Quality Gate `30196719409`、本地全量回归与 post-merge smoke。
- RFC-027 为 Adopted；ADR-058～ADR-060 为 Accepted；SP-018 状态为 `APPROVED / MERGED / AUTOMATED_VERIFICATION_PASSED / MANUAL_ACCEPTANCE_PASSED / POST_MERGE_VERIFIED / RECONCILED / ARCHIVED`。
- 产品版本、Tag 与 Release 不变。

### SP-017 跟进交互与捕获闭环
- 通过 PR #43 以 Squash Merge 完成确定性 Waiting-For 读取、Inbox 捕获与确认，以及显式 lifecycle interaction。
- 自然语言模糊表达只创建 pending Inbox；确认后复用持久化 Inbox-to-Waiting-For Saga，并以 Inbox ID 确定性派生唯一 `wf_...` ID。
- Lifecycle mutation 只接受 canonical `wf_...` ID；重复确认、崩溃恢复和跨进程竞争保持幂等。
- 中文确定性错误展示与 API/CLI 系统 `timezone_name` 缺省值保持一致。
- ACC-017 A～O 已通过并封存；RFC-026 为 Adopted，ADR-056 与 ADR-057 为 Accepted。
- 产品版本保持 `0.34.0`；`v0.34.0` Tag 与既有 Pre-release 均未改变。

### v0.34.0 Alpha / 已授权发布
- 源产品版本从 `0.33.0` 升级为 `0.34.0`，未改变业务行为或数据库 Schema。
- 根目录 `project_state.json` 成为唯一机器可读仓库治理状态源；`pyproject.toml` 继续作为唯一运行时版本源。
- 完成 SP-014、SP-014B 与 ACC-014 最终状态对账；SP-015 已合并、通过合并后验证并封存，当时 SP-016 仍仅为候选。
- 重新划分 README、Project Brain 与 Roadmap 的职责，移除过时阶段、不可靠文档数量和重复 SP 历史。
- 新增 v0.34.0 Alpha 发布说明与自动化项目治理一致性测试。
- SP-015、SP-015A 与 SP-015R 已封存；Owner 与 ChatGPT 已授权 `v0.34.0` GitHub Pre-release。实际发布状态、Tag 目标、Release URL 与时间以 GitHub Tags 和 GitHub Releases 为权威来源。
- 以独立验证的发布基线 `22f88d1da962fb436c48c19e5343fad8bf62f5f6` 和 Quality Gate run `29855987444` 替代自指的 tracked `main_commit` 模型；Tag 与 Release 事实以 GitHub 为权威来源。

### SP-014 统一 Inbox 与治理对账
- Unified Inbox 与 Capture-to-Action 通过 PR #32 合并为 `5bad5d412f9f2dabb158527a96c20c6e95e86d6e`。
- API、CLI 与 CEO Assistant 通过规范组合根支持显式转换为 UserTask、Reminder、Work Log、Note 和 Dismiss。
- 已验证工作空间隔离、持久化跨进程解析 claim、幂等性、竞争解析、重启持久性与崩溃恢复。
- ACC-014 A～L 通过；SP-014 状态为 `APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED / RECONCILED / ARCHIVED`。
- 产品版本保持 `0.33.0`；未创建 Tag 或 Release，SP-015 未启动。

### SP-014B 中文数字提醒时间兼容
- 确定性 Reminder 解析器在显式包含 `上午/下午/晚上` 时接受中文小时 `一` 至 `十二`。
- 复用既有时段转换、分钟解析、UTC 转换、过去时间校验、标题提取与 FailureInfo 路径。
- 为 ACC-014 场景 K 增加解析器、意图路由和真实 `/chat` 集成覆盖，包括幂等性与 Inbox 隔离。
- 不支持的日期、相对时间、模糊后缀、中文分钟、Recurring Reminder 与 LLM 解析仍不在范围内。
- 通过 PR #33 合并为 `22f85db16a43e7d09a903859a26ac6a310370d81`；ACC-014 场景 K 与完整 API 安全场景 L 在合并后 main 基线上通过。
- 状态：`APPROVED / MERGED / VERIFIED / RECONCILED / ARCHIVED`。产品版本保持 `0.33.0`。

### SP-012 意图安全与 Reminder 查询体验
- 新增确定性 `read/write/chat` 意图效果合同与读优先 Reminder 查询别名。
- Work Log 仅允许由显式命令或明确的已完成行动语句创建。
- 对目标缺失和不受支持的 Reminder 时间表达提供中文可操作提示。
- 新增真实 FastAPI、组合根、SQLite、Reminder Inbox 与 Memory 无副作用测试。
- 2026-07-17 通过 PR #25 合并为 `d550ab8757b50e4d12587d5e71a0058089bd3821`。
- 状态：`APPROVED / MERGED / RECONCILED / ARCHIVED`。
- RFC-022 为 Adopted；ADR-046/047/048 为 Accepted。

### SP-011 Reminder 管理闭环
- 新增共享 Reminder 管理边界，统一状态、取消、重新安排、工作空间检查与标题 fail-closed 解析。
- 新增可操作的 `view=pending`、CLI 管理命令、确定性响应分离与 UTF-8 CLI 输出处理。
- 复用既有 Reminder/Scheduler Saga，包括可查询的部分失败与哈希化重新安排幂等 metadata。
- 新增真实组合根、FastAPI lifespan、SQLite 重启、有效单次执行与子进程 UTF-8 测试。
- Windows 本地 Python 3.12 合并前验证：`1026 passed, 27 warnings in 58.15s`；这不是 GitHub Actions 或跨平台 CI 结果。
- RFC-021 为 Adopted；ADR-043/044/045 为 Accepted。
- 2026-07-17 通过 PR #23 合并为 `5c4b442b2b5c7f934ac381020ba8b310976d5d3a`。
- 状态：`APPROVED / MERGED / RECONCILED / ARCHIVED`。
- 产品版本保持 `0.33.0`；未创建 Tag 或 GitHub Release。

### SP-010 提醒收件箱
- 新增由 API、CLI 与确定性 CEO Assistant 查询共享的持久化 Reminder Inbox。
- 新增 `GET /reminders`，支持 status、today、upcoming、分页与稳定排序。
- 新增 `python -m cli reminders`，提供人类可读与 JSON 输出。
- 新增稳定数据库分页、当前页 `count`、`has_more`、状态/时间过滤与工作空间隔离。
- 明确本地 API 的 `application/json; charset=utf-8` 合同。
- 详情与列表视图复用 ADR-040 状态聚合。
- RFC-020 为 Adopted；ADR-041 与 ADR-042 为 Accepted。
- Windows 本地 Python 3.12 合并前验证：`1013 passed, 27 warnings in 57.76s`；这不是 GitHub Actions 或跨平台 CI 结果。
- 2026-07-16 通过 PR #21 合并为 `af437afc32dcb17da68d600d6840ec94c8cbe681`。
- 状态：`APPROVED / MERGED / RECONCILED / ARCHIVED`。
- 产品版本保持 `0.33.0`；未创建 Tag 或 GitHub Release。

### SP-009 自然语言 Reminder 闭环
- 新增带注入时钟与 IANA 时区的确定性今天/明天 Reminder 解析器。
- 通过窄编排器把 CEO Assistant 接入既有 UserTask/Reminder/Scheduler Saga。
- 新增请求哈希幂等、聚合持久化状态 API 与组合根 CLI 状态查询。
- 新增真实 lifespan SQLite 重启、到期触发、有效单次执行与失败可见性测试。
- Windows 本地 Python 3.12 候选验证：`1006 passed, 27 warnings in 50.02s`；这不是 GitHub Actions 或跨平台 CI 结果。
- 2026-07-16 通过 PR #19 合并为 `b1274d066cbc01053144cba8d5654a5f8c8a21da`。
- 状态：`APPROVED / MERGED / RECONCILED / ARCHIVED`。
- 产品版本保持 `0.33.0`；未创建 Tag 或 GitHub Release。

### SP-008 内部工作准入边界
- 新增由生命周期支撑的单一内部应用工作准入边界。
- 新增受保护的 CEO Assistant 直接入口与 Scheduler producer 入口。
- 新增由 Task 所有的已准入工作能力约束，防止 detached child Task 携带准入绕过。
- 通过 `spawn_accepted_task()` 保留显式接受的 Scheduler Job 延续。
- 保持 SP-007 FastAPI 生命周期与 `FailureInfo` 行为。
- 2026-07-16 通过 PR #16 合并为 `1858d4991379058948559cc96e2672df44e42b67`。
- Windows 本地 Python 3.12 合并验证：`977 passed, 27 warnings in 49.17s`；这不是 GitHub Actions 或跨平台 CI 结果。
- 产品版本保持 `0.33.0`；未创建 Tag 或 GitHub Release。

### SP-007 系统生命周期准入门禁
- 新增系统生命周期状态机与 FastAPI 受保护路由准入门禁。
- 新增 single-flight 优雅关闭协调。
- 新增结构化生命周期失败码与 draining `Retry-After` 行为。
- 新增生命周期感知的健康报告。
- 2026-07-16 通过 PR #14 合并为 `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`；未创建新的产品 Tag 或 Release。
- 内部直接调用准入由 SP-008 完成。

### SP-006 API 安全边界
- 新增集中式 Bearer-token 认证。
- 新增显式 CORS allowlist。
- 新增 `UNAUTHENTICATED` ErrorCategory（HTTP 401）。
- 新增 51 个安全专项测试。
- 2026-07-15 通过 PR #12 合并；未创建新的产品 Tag 或 Release。


### SP-005 Reminder & Scheduler Bridge（已合并，尚未发布）

- PR #10 已通过审查并以 Squash Merge 合并到 `main`；审查结论为 `APPROVED`，SP-005 merge baseline 为 `167b0d78f7713b1d5bfc85198c1461c7a35f63d3`，合并时间为 `2026-07-15T14:03:32Z`。

- Scheduler One-shot 成功后进入 completed 并清空 next_run；跨 Runtime 使用 SQLite CAS claim 和 token 校验。
- 持久化 JobRun、claim expiry 与脱敏 FailureInfo；旧 Workflow Job 通过幂等 migration 保持兼容。
- 新增 Action Handler Registry、持久化 Reminder/ReminderOccurrence 与数据库唯一幂等键。
- 新增创建、查询、重新安排、取消和 Occurrence 查询 API，继续复用统一 FailureInfo 错误契约。
- UserTask complete/cancel 同步协调未触发 Reminder；部分失败保留 pending_cancel，并允许同一终态请求再次补偿。
- reminders.db 与 scheduler.db 使用显式 Saga 和 reconciliation，不宣称跨数据库事务或 exactly-once execution。
- 产品版本保持 `0.33.0`；未创建 v0.34.0 Tag 或 GitHub Release。
- Windows 隔离 Python 3.12 本地最终验证：`888 passed, 27 warnings in 45.19s`；不是 GitHub Actions 或跨平台 CI 结果。
- 审查修复：Scheduler 管理操作改为数据库状态、revision 与 claim 条件写；EventBus post-commit 失败只降低 observability；过期 claim 遵守 retry delay；RUNNING Reminder Job 的 reschedule 返回 409 且不修改 Reminder。

### SP-004 UserTask 用户任务

- **状态**：Completed
- **Merge PR**：#8
- **审查结论**：APPROVED
- **合并方式**：Squash Merge
- **Merge Commit / SP-004 merge baseline**：`10d1534049be2d526c930c513912dc661ac41728`
- **合并时间**：`2026-07-15T11:39:33Z`

- 新增正式 UserTask 领域、UTC 时间模型、生命周期、revision 并发控制和 `tasks.db` 持久化。
- `/tasks` 从固定 Mock 改为真实 CRUD、列表、更新、完成和取消 API，并复用统一错误契约。
- CEO Assistant 新任务不再写入 Decision Memory；brief 和任务查询改用 UserTaskService。
- 提供显式、幂等、非破坏的历史 Decision Memory 任务导入入口。
- 审查修复为 Legacy importer 增加完整分页，并迁移 deadline、priority、status、session、agent 与 source。
- `timezone` 改为 IANA 校验，`due_at` 保持 UTC；CEO Assistant 不再把无法识别的具体时间静默改为当日结束。
- Legacy 终态时间不再由创建时间编造；半点、一刻和分钟表达采用完整匹配；列表时间筛选统一进入 FailureInfo 校验边界。
- revision 强制大于等于 1；损坏持久化行统一归类为 Persistence Failure；metadata 递归拒绝敏感键。
- Reminder Trigger 与 UserTask-Scheduler Bridge 留给 SP-005。
- SP-004 Windows 本地完整验证：`847 passed, 27 warnings in 38.81s`；不是 GitHub Actions 结果。首次全量测试的 5 个错误来自 pytest 子进程继承的 SOCKS 代理；仅清理测试子进程代理变量后全量通过，未修改系统代理或 `.env`。
- 产品版本保持 `0.33.0`；本次合并未创建 v0.34.0 Tag 或 GitHub Release，SP-005 Reminder & Scheduler Bridge 为下一项开发。

## [0.33.0] - 2026-07-15 版本

### 版本治理

- 将 `pyproject.toml` 的 `[project].version` 确立为唯一运行时产品版本来源。
- `core.__version__` 优先读取 `ai-lab` distribution metadata；源码模式从同一 `pyproject.toml` 派生，不再维护硬编码副本。
- CLI、API、Health、基础配置与 Windows 启动入口统一显示派生版本。
- v0.33.0 基线在全新隔离 Python 3.12 环境中的最终 Windows 本地验证为 `820 passed, 27 warnings in 37.64s`；真实 DeepSeek 测试为 `5 passed in 8.37s`。这些结果不是跨平台 CI 或 GitHub Actions 记录。
- 审查修复将 Core、API、Real Provider、Knowledge、Test、Build、Dev 依赖按 PEP 621 extras 分层，`requirements.txt` 不再维护第二套依赖真源。
- setuptools 包发现补齐 `api` 与 `cli`，并显式排除 tests、data、logs、runtime 与 Chroma 运行数据。
- `setup.bat` 不再吞掉 pip/pytest 失败；CLI/API 启动脚本会传播版本解析、CLI 与 Uvicorn 的真实退出码。
- 项目状态文档改用 Implemented / Integrated / Verified / Disabled，删除与未完成主链路冲突的“100% Stable”表述。

### 稳定化基线

- SP-001：Single Composition Root 与 CLI/API 真实主链路。
- SP-002：统一 `FailureInfo`、失败语义与 System Health 聚合。
- SP-003：DatabaseManager 连接所有权、operation-scoped lease、原子写入和生命周期清理。
- SP-003 阶段最终本地验证记录为 `800 passed, 26 warnings`，不是 GitHub Actions 结果。
- `v0.32.4-review-baseline` 历史冻结标签保持不变；v0.33.0 Tag 与 GitHub Release 只允许在 Release PR 审查并合并后创建。

### 已知限制

- Reminder 外部通知投递、Recurring Reminder、Inbox、Knowledge Reindex/Chunk Persistence/Citation、自动 Tool Calling、Coordination 主链路、Database backup/restore、in-flight counting 与 drain timeout 仍未完成。

---

## SP-003 已完成（2026-07-15）

**Merge PR**：[#5](https://github.com/y19870785/ai-lab-os/pull/5)

**合并方式**：Squash Merge

**审查结论**：APPROVED

**SP-003 Merge Commit**：`ce3655ff5f7a625da6b168058873dadfc2289b5f`

**合并时间**：`2026-07-14T19:59:33Z`

### DatabaseManager 连接所有权

- Composition Root 将同一个 `DatabaseManager` 注入 Episodic、Semantic、Decision 三个 SQLite Memory Store。
- 新增显式 `ConnectionLease`：Managed Mode 在完整借用周期持有 per-database lock，退出时不关闭共享连接；Standalone Mode 关闭自身创建的 operation-scoped connection。
- `DatabaseManager` 支持显式路径绑定、路径冲突拒绝、失效缓存识别、单连接关闭与关闭后显式重开。
- 保持 `settings.sqlite_dir/episodic.db`、`semantic.db`、`decision.db` 原路径，不创建 `data/database/` 下的第二套数据库，不修改 Schema。
- 三类 Store 的写操作统一显式 commit/rollback，`batch_save` 保持单事务原子性。
- Database Health 接入 `RuntimeStatus` 与 `FailureInfo`，探针只检查已打开连接，不自动创建数据库。
- 新增真实连接、事务回滚、并发、路径兼容、Composition Root 与 shutdown 验证。
- 修复审查发现的租约竞态：`close()`/`close_all()` 等待活跃 managed lease；关闭失败的连接保留在 Manager 中并可重试，`close_all()` 尝试全部连接后统一报告失败。
- Knowledge SQLite Store 与 SchedulerPersistence 所有权迁移不在本轮范围内。
- SP-003 审查修复专项测试：`32 passed in 1.75s`；受影响模块：`141 passed in 7.97s`。
- 全量本地测试：`800 passed, 26 warnings in 41.93s`。首次运行记录为 `795 passed, 26 warnings, 5 errors in 33.58s`，错误均来自继承 SOCKS 代理的既有 DeepSeek real 测试；仅在测试子进程清空代理变量后重跑通过，未修改用户全局环境。

---

## SP-002 已完成（2026-07-14）

**Merge PR**：[#3](https://github.com/y19870785/ai-lab-os/pull/3)
**合并方式**：Squash Merge
**Merge Commit / main 基线**：`a39dc6a2434b409d311709b08b2c0df9a555a610`
**合并时间**：`2026-07-14T18:22:14Z`
**审查结论**：APPROVED

### 失败语义与可观测性收敛

- 新增唯一错误契约 `core/errors/`：`ErrorCategory`、`ErrorSeverity`、`RuntimeStatus`、不可变 `FailureInfo`、异常与 HTTP 映射。
- Agent 失败不再把错误文本写入 `answer`；Provider、Memory、Knowledge、Tool 使用可机器读取的独立错误码。
- LLM 回答成功但 Memory 保存失败时返回 `degraded`，保留回答并明确记录持久化失败。
- Task 修复 `i -= 1` 无效重试，改为每个 Workflow 独立 attempt 循环；空计划和重试耗尽不再标记完成。
- Scheduler 不再静默吞掉 tick 异常，新增连续失败、最近错误、后台 task 跟踪及完整 shutdown 收集。
- API 使用统一错误响应和 HTTP 状态映射；未知异常不再向客户端暴露内部路径或堆栈。
- `SystemContainer.health()` 改为真实组件聚合，区分 `healthy`、`degraded`、`failed`、`disabled` 与 `not_initialized`。
- Agent、Task、Scheduler 的失败事件采用统一扁平 envelope，并携带 trace id。
- 首轮审查修复：Agent 开启 Memory、Knowledge 或 Tool 但缺少依赖时返回 `failed + FailureInfo`，不再静默跳过。
- CEO Assistant 与 ApplicationRuntime 不再把失败包装成 HTTP 200；API 统一返回非 2xx 错误契约，且不在 `answer` 中携带异常文本。
- MemoryManager 记录 Store 操作故障，并在后续成功操作或健康探针通过后恢复为 `healthy`。
- System Health 将关键组件的 `stopped`、`not_initialized`、`not_configured`、`disabled`、`degraded`、`failed` 纳入顶层聚合。

### 验证状态

- SP-002 审查修复专项故障注入测试：`28 passed in 1.56s`。
- 受影响模块测试：`423 passed, 2 warnings in 11.62s`。
- DeepSeek 真实测试已随全量测试通过（测试子进程清空继承的 SOCKS 代理变量后直连）。
- 全量测试：`768 passed, 26 warnings in 34.43s`。
- 上述结果为合并前的本地 pytest 验证记录；当时 GitHub 没有远端 CI checks，不得视为 GitHub Actions 结果。
- PR #3 已通过审查并以 Squash Merge 合并到 `main`。

---

## SP-001 已完成（2026-07-14）

### 架构稳定化

- 新增 `core/system/`，提供不可变 `SystemSettings`、唯一 `create_system()` 和显式 `SystemContainer`。
- CLI、CLI 单次命令、FastAPI lifespan、兼容 Bootstrap 与集成测试统一使用同一套系统 Factory。
- FastAPI dependency 改为读取 `app.state.system`，不再创建空 `ApplicationRuntime`。
- ApplicationRegistry 保存真实应用实例；ApplicationRuntime 只派发已注册实例。
- CEO Assistant 通过统一 MemoryManager 写入 Episodic Memory，API 工作记录与跨重启持久化已验收。
- Workflow、Scheduler、Task、Agent、Tool 与 Provider 由 Composition Root 注入并统一管理生命周期。

### 行为修正

- 删除 ApplicationRuntime 自动创建应用、直接创建 OpenAI Provider 和异常后 Mock Echo。
- Agent 缺少 LLM、Memory 或 ToolExecutor 时显式失败，不再返回成功 Echo。
- Scheduler Job 和 Task 缺少 WorkflowRuntime 时不再标记成功。
- Mock Provider 仅允许在显式 `mock/test` 模式启用；配置不完整时系统状态为 `invalid` 并拒绝启动。
- 修复 OpenAI Compatible LLM/Embedding 的模型配置优先级：显式参数 > `AI_LAB_*` > `OPENAI_*` > 默认值。

### 验证

- Composition Root、真实实例注册、API Memory 写入、跨重启持久化、Scheduler 生命周期和 No Fake Success 测试已新增。
- DeepSeek 真实测试：`5 passed in 9.20s`。
- 全量测试：`735 passed, 26 warnings in 34.06s`。
- PR #1 已合并：https://github.com/y19870785/ai-lab-os/pull/1
- Merge commit：`0a36e250ab8382af6cf3ab3068e432aa69ba3399`
- 架构审查：Approved
- 合并后复核：Passed

---

## [0.32.4] - 2026-07-13 版本

### Interactive First Experience Fix —— 交互式首次体验修复

**问题根因**：`start.bat` 执行 `python -m cli`（无参数），无参数时只打印命令帮助就 `sys.exit(0)`。用户双击后永远看不到交互界面。

**统一 Provider 模式检测**：
- 所有入口统一调用 `core/provider_mode.py` 的 `detect_provider_mode()`
- 返回 `real` / `mock` / `invalid` 三种状态
- 禁止已配 Key 时误报 REAL，禁止未配 Key 时显示 REAL
- start.bat 不再自己实现模式检测

**交互式 CLI**：
- 新增 `cli/ceo.py`：持续交互循环 + Intent Router + 快捷键支持
- 自然语言输入自动路由到工作记录/任务/决策/知识问答
- 支持 `/help` `/brief` `/tasks` `/records` `/decisions` `/knowledge` `/new-session` `/status` `/clear` `/exit`
- `python -m cli ceo` 进入交互模式
- `scripts/start.bat` 双击即进入交互

**API 独立启动入口**：
- 新增 `scripts/start_api.bat`：启动 `uvicorn api.app:app --host 127.0.0.1 --port 8000`
- CLI 和 API 入口完全分离

**修复与回归**：
- pyproject.toml 去除 UTF-8 BOM 头，修复 pytest 无法解析
- 修复 CLI ceo 命令的 MemoryManager 初始化链路
- 全量 712 passed（新增 18 个交互测试），零回归

**DeepSeek 真实交互验证**：通过 ✓
**First Experience Gate**：PASS ✓

---
## [0.32.3] - 2026-07-13 版本

### CEO Assistant 发布清理

- 修复 `tests/real/` 加载 API Key 后污染普通测试的全局测试隔离问题。
- 新增全局 `isolate_api_keys` fixture，并由 `tests/real/conftest.py` 覆盖真实 Provider 场景。
- 全局测试从 692 passed、2 failed 修复为 699 passed、0 failed；其中 non-real 测试 694 passed、0 failed，real Provider 测试 5 passed、0 failed。
- `scripts/start.bat`、`scripts/setup.bat`、`scripts/diagnose.bat` 与 `scripts/stop.bat` 提供一键操作入口。
- Stability Gate 与 First Experience Gate 均通过。

---

## [0.32.2] - 2026-07-13 版本

### CEO Assistant 首次运行稳定化

- 修复任务优先级断言、conversation memory 的 task 路由、测试 collection 导入顺序冲突和 real async fixture 配置。
- non-real 测试：694 passed、0 failed、26 warnings。
- 单独 real Provider 测试：5 passed、0 failed。
- 已知限制：当时全局 real 模式仍有 4 个 async fixture collection error；这是 v0.32.2 的历史状态，不代表当前测试结果。
- 统一 `AI_LAB_LLM_PROVIDER` 等环境变量，同时兼容已弃用的 `OPENAI_API_KEY` 等旧变量。
- `python -m cli chat` 可直接启动 CEO Assistant。
- Stability Gate：PASS（普通测试 0 failed，DeepSeek 真实验证通过）。

---

## [0.32.0] - 2026-07-13 版本

### CEO Assistant MVP：AI-Lab 首个真实业务应用

- 产品定位从 Framework First 转向 Application First，提供工作记录、待办任务、决策记录、知识问答、每日简报和多轮对话。
- 新增 `brief`、`log`、`task`、`decide` 与 `chat` CLI 命令。
- 新增 `POST /work-logs`、`POST /decisions`、`GET /brief` 与 `POST /knowledge/ask` API 路由。
- 新增 `applications/ceo_assistant/`、`product/`、对应 CLI 命令与 API 路由，以及本地 SentenceTransformer Embedding Provider。
- 修复 DatabaseManager、KnowledgeManager、Chroma metadata、CLI UTF-8、意图优先级与 MemoryManager 调用接口。
- 完成 DeepSeek LLM、本地 Embedding、Chroma Vector Store、Document QA Pipeline 与 Personal Assistant Demo 的真实 Provider 验证。
- 全量 647 项测试通过，零回归。

---

## [0.31.0] - 2026-07-13 版本

### Alpha 现场验证

- 完成统一启动入口、环境配置、持久化、故障注入、可观测性与 Field Demo 验证。
- 全量 647 项测试通过。

---

<details>
<summary>历史版本（v0.1.0 - v0.30.0）</summary>

## [0.30.0] - Application Foundation 与 Alpha 部署
## [0.23.0] - 多智能体协作
## [0.22.0] - Task 运行时
## [0.21.0] - Scheduler 运行时
## [0.20.0] - 工作流引擎
## [0.19.0] - MCP Adapter 与端到端集成
## [0.18.0] - 工具系统
## [0.17.0] - Agent 运行时
## [0.16.0] - 知识层
## [0.15.0] - Provider 层
## [0.14.0] - 架构稳定化
## [0.13.0] - Core 与 Memory 稳定化
## [0.12.0] - Memory 层集成
## [0.11.0] - Semantic 与 Decision Memory
## [0.10.0] - 情景记忆（Episodic Memory）
## [0.9.0] - Memory 整合引擎
## [0.8.0] - Session Memory 实现
## [0.7.0] - Core 运行时实现
## [0.6.1] - Decision Memory 架构设计
## [0.5.0] - 治理层
## [0.4.0] - 知识层架构设计
## [0.3.0] - Agent 架构
## [0.2.0] - Memory 层架构设计
## [0.1.0] - Core 层架构设计

</details>

> SP-007 System Lifecycle Admission Gate: APPROVED / MERGED / RECONCILED / ARCHIVED. SP-008 Internal Work Admission Boundary: APPROVED / MERGED / RECONCILED / ARCHIVED，通过 PR #16 以 Squash Commit `1858d4991379058948559cc96e2672df44e42b67` 合并。版本仍为 `0.33.0`，下一项稳定化任务尚未选择。
