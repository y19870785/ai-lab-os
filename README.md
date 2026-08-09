# AI-Lab OS 中文使用说明

> SP-019 已完成 Squash Merge、ACC-019 A～M 与 post-merge Quality Gate：Daily Review 通过同一确定性只读边界聚合 Work Log、UserTask、Waiting-For、Reminder 与 Inbox。
>
> SP-020 已通过正式 ACC-020 A～V、独立证据复核与 main Quality Gate，并完成合并、对账和封存。
> SP-021 已通过 ACC-021 A～R、最终独立审查与 main Quality Gate，并完成合并、对账和封存。INT-001 已通过 ACC-INT-001 A～Q、最终独立审查与 main Quality Gate，并完成合并、对账和封存。
> `v0.35.0` 已发布为 GitHub Pre-release，annotated Tag 指向冻结 Release Head。

AI-Lab OS 正式定位为面向个人经营者和企业真实工作流的可信业务操作系统：长期保存业务
事实、状态、规则、决策和执行证据，并通过可替换的 Agent Shell 与用户自然交互。Hermes
是首个首选但可替换的 Agent Shell，不是业务事实源或不可替换核心。

**当前版本：v0.35.0 Alpha / GitHub Pre-release Published**
**成熟度：Alpha / local-first / single-user-oriented**
**当前 Product SP：None**
**当前 Governance Task：None**
**当前工作：None**
**下一候选 Product SP：None**

`v0.35.0` 已发布为 **Pre-release**，Tag `v0.35.0` 指向冻结 Release Head
`60fc299c4f4fd1ba22fc4a00d1490f3b2b893503`。Release 不上传 wheel 或 sdist，仅有 GitHub
自动源码归档；它仍不是 production-ready。下一 Product SP 尚未批准。
上一已发布版本为 `v0.34.0`；当前已发布版本为 `v0.35.0` GitHub Pre-release。

AI-Lab 能帮助整理信息、记录工作、创建任务与提醒；最终业务判断和重要审批仍由用户负责。当前版本适合本地开发、验证和受控试用，不应被描述为 production ready。

ARCH-001 定义 Shell-neutral、Transport-neutral 的 Trusted Interaction Architecture Baseline：View、
Preview、Confirm、Cancel、Modify、Status、Verified Result、Recovery，以及 identity/Workspace、重试、
审计和恢复合同。RFC-032 已 Adopted，ADR-069～072 已 Accepted；SP-021 已实现并验证
canonical domain、持久化、Status/View 与 Fake/Reference port；INT-001 已实现 Shell-neutral
application adapter、fail-closed identity/policy authority 与本地 stdio MCP reference projection，
已通过 PR #70 合并、main Quality Gate 并完成治理对账和封存。真实 Hermes/Channel 未接入；
PILOT-001 仅为下一候选且未获授权，REL-036 未启动。详见
`docs/project/ARCH-001-TRUSTED-INTERACTION-ARCHITECTURE.md` 和
`docs/project/ARCH-001-POST-MERGE-RECONCILIATION.md`。
SP-021 实施边界、ACC-021 与合并后对账见 `docs/project/SP-021-CANONICAL-TRUSTED-INTERACTION-DOMAIN.md`、
`docs/acceptance/SP-021-canonical-trusted-interaction-domain.md` 和
`docs/project/SP-021-POST-MERGE-RECONCILIATION.md`。
INT-001 实现与 MCP 边界见 `docs/project/INT-001-SHELL-NEUTRAL-TRUSTED-INTERACTION-ADAPTER.md`、
`docs/project/INT-001-HERMES-MCP-PROJECTION.md` 和
`docs/acceptance/INT-001-shell-neutral-trusted-interaction-adapter.md`。
INT-001 合并事实与最终治理状态见
`docs/project/INT-001-POST-MERGE-RECONCILIATION.md`。

## 当前能力

### 已接入并验证

- Canonical UserTask：真实持久化、查询和生命周期管理。
- Reminder Core：持久化 Reminder、Scheduler Job 与站内状态；支持今天/明天的确定性时间子集。
- Reminder Management：列表、详情、取消、改期、workspace 校验和幂等语义。
- Intent Safety：读、写、聊天显式分离；模糊查询优先只读。
- Work Log（SP-018）：统一 create/get/list、完整 Workspace identity、canonical/legacy ID、API/CLI/CEO/Inbox 入口与只读查询；ACC-018 A～O 已通过并封存。
- Daily Review（SP-019）：支持 `today` / `yesterday`、本地 IANA timezone、DST 23/25 小时日、当前 follow-up、pending Inbox、全局稳定排序与分页；API、CEO Assistant 和兼容 `/brief` 共用同一 `DailyReviewService`，ACC-019 A～M 已通过并封存。
- Daily Agenda：统一读取 UserTask、Reminder、Waiting-For 与 canonical Work Log。
- Unified Inbox / Capture-to-Action：捕获待整理事项，并显式转化为 UserTask、Reminder、Work Log、Note 或 Dismiss。
- Waiting-For Follow-up Interaction：自然语言先捕获 Inbox，再以 Inbox ID 确认创建；显式 `wf_...` ID 支持确定性生命周期操作，已通过 ACC-017 A～O 并封存。
- API、CLI 与 CEO Assistant：共享 canonical Composition Root 和领域服务。
- Bearer Token 与 CORS allowlist：提供本地 API 安全边界。
- Local Daily Operating Loop（SP-020）：正式 Daily Review CLI、确定性 Action Hints、
  Review-to-Action、持续 Scheduler、优雅关闭、重启恢复、静止备份与隔离恢复已通过
  ACC-020；这仍是本地 Alpha 边界。

### 已实现但默认关闭或需显式配置

- Reminder / Scheduler：已集成和验证，是否启动由运行配置决定。
- Knowledge：基础实现存在，但真实主链路、reindex、chunk persistence 和 citation 尚未完成。
- Coordination：基础实现存在，默认关闭，未接入 CEO Assistant 主链路。
- Real LLM Provider：需要显式安装对应 extra、配置凭据并获得单独验证授权；普通测试门禁不调用真实 Provider。

### 原型或未完成

- 通用 Task / Workflow API 中不属于正式 UserTask 领域的路径仍是原型边界。
- 自动 Tool Calling、完整 MCP 产品闭环和完整 Agent Runtime 产品闭环尚未完成。
- 外部通知、Recurring Reminder、Web UI、用户身份、OAuth/JWT/RBAC、强多租户和企业级部署尚未实现。

## 快速开始

要求 Python 3.11 或更高版本。

```powershell
git clone https://github.com/y19870785/ai-lab-os.git
cd ai-lab-os
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[local]"
```

查看 CLI：

```powershell
python -m cli --help
```

启动本地 API：

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

最小 Core 安装可以使用：

```powershell
python -m pip install -e .
```

`pyproject.toml` 是版本、依赖和 package discovery 的唯一运行时来源；`requirements.txt` 仅兼容代理 `.[local]`。

## 运行 Profile

| 配置（Profile） | 用途 | 关键边界 |
|---|---|---|
| Minimal Core | Core、Memory 与基础 Runtime 开发 | 不自动安装 API、真实 Provider 或 Knowledge 大型依赖 |
| Local | API、CLI、Mock Provider、测试和构建 | 推荐的本地开发组合 |
| Local Daily | Windows 本地日常闭环 | 显式绝对数据目录、完整 WorkspaceKey、Bearer Token 与 localhost bind |
| Real Provider | 显式外部模型验证 | 需要凭据、网络和单独授权，不属于普通 Quality Gate |
| Knowledge | 可选向量与 embedding 依赖 | 真实产品主链路仍未完成 |

运行行为由环境配置控制。默认关闭的能力不会因为代码存在而自动成为可用产品功能。

### Windows Local Daily 首次启动

使用项目支持的 Python 3.12，从仓库根目录完成一次可复现配置：

```powershell
py -3.12 -m venv .venv_312
$Python = ".\.venv_312\Scripts\python.exe"
& $Python -m pip install -e ".[local]"

Copy-Item .\config\local-daily.env.example .\.env
notepad .\.env
```

在根目录 `.env` 中至少把 `AI_LAB_DATA_DIR`、`AI_LAB_SQLITE_DIR` 改成真实、稳定的
绝对本机路径，把 `AI_LAB_API_TOKEN` 改成仅自己持有的随机 secret，并核对
`AI_LAB_TIMEZONE`、`AI_LAB_TENANT_ID`、`AI_LAB_WORKSPACE_ID`、
`AI_LAB_NAMESPACE`、`AI_LAB_SESSION_ID` 与 `AI_LAB_AGENT_ID`。不得把示例 token
或业务数据目录提交到 Git。

启动前先验证最终 Profile；只有精确的 `local-daily` 才会成功：

```powershell
& $Python -m cli profile --require-local-daily
.\scripts\start-local-daily.ps1 -Port 8000
```

启动脚本从 `$PSScriptRoot` 固定仓库根目录、根目录 `.env` 和项目 Python；调用脚本时
所在的 working directory 不会改变配置或 data root。脚本只绑定 `127.0.0.1`。

在第二个 PowerShell 窗口验证真实进程：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready

# 无 token 的业务请求必须失败（HTTP 401）。
try {
    Invoke-RestMethod http://127.0.0.1:8000/agenda -ErrorAction Stop
    throw "未授权请求意外成功"
} catch {
    $_.Exception.Response.StatusCode.value__  # 401
}

$Token = (Get-Content .\.env |
    Where-Object { $_ -like "AI_LAB_API_TOKEN=*" } |
    Select-Object -First 1).Split("=", 2)[1]
$Headers = @{ Authorization = "Bearer $Token" }
Invoke-RestMethod http://127.0.0.1:8000/agenda -Headers $Headers
Invoke-RestMethod "http://127.0.0.1:8000/daily-review?date=today" -Headers $Headers
```

回到服务窗口按 `Ctrl+C`。进程必须完成优雅关闭并释放
`DatabaseManager.connection_count` 到 0；Phase 0 自动化测试和 ACC-020 driver 会记录
shutdown、background task 与连接数证据。若进程不能退出、仍占用 SQLite 或端口，不得
直接复制运行中的数据目录并声称备份成功。

服务停止后仍可运行独立 CLI（每次请求使用同一 Profile WorkspaceKey 和新的
trace ID）：

CLI 的 Workspace 覆盖参数会先去除首尾空白；未提供参数时使用 Profile 默认值，但显式
传入全空白值会失败关闭，不会回退 Profile 或 `default` workspace。

```powershell
& $Python -m cli daily-review --date today
& $Python -m cli daily-review --date yesterday --json
```
## 典型使用入口

```powershell
# 查看提醒
python -m cli reminders --json

# 查看今日日程
python -m cli agenda --view today --json

# 查看 Unified Inbox
python -m cli inbox list --json
```

Daily Review 的真实公共入口为：

```text
GET /daily-review?date=today
GET /daily-review?date=yesterday
GET /daily-review/action-hints?date=today
GET /brief
CEO Assistant：今日简报 / 昨日简报
```

API、CLI 和 CEO Assistant 最终都进入 `core.system.create_system()` 创建的 `SystemContainer`，不会各自组装第二套 Repository 或领域服务。

## 架构概览

```text
Governance
  └─ Application / CEO Assistant / API / CLI
       └─ Canonical Composition Root
            ├─ UserTask / Reminder / Daily Agenda / Daily Review / Unified Inbox
            ├─ Scheduler / Workflow / Agent / Tool / Coordination
            ├─ Knowledge / Provider
            └─ Memory / Database / EventBus / Core
```

关键边界：

- `pyproject.toml`：唯一运行时产品版本源。
- `project_state.json`：唯一机器可读仓库治理状态与稳定发布授权源；当前 Git/GitHub 对象按需查询。
- `core/system/factory.py:create_system()`：唯一 Composition Root。
- SQLite 持久化 claim：Unified Inbox 跨进程唯一解析权和崩溃恢复边界。
- `FailureInfo`：跨领域统一失败语义。

更完整的实现关系见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 当前限制

- Alpha、local-first、single-user-oriented；没有生产可用性承诺。
- Workspace 是逻辑隔离边界，不等于完整用户身份或强多租户授权。
- Reminder 当前提供站内持久化状态，不代表邮件、短信或推送已经送达。
- 不支持 Recurring Reminder、复杂自然语言日期或 LLM 时间裁决。
- Daily Review 只支持 `today` / `yesterday`，不持久化 Review snapshot，不支持任意历史日期，不调用 LLM、不主动推送；CLI 与 API 复用同一个服务。
- Knowledge 真实主链路、Web UI、Docker 受控 build/run 与长期稳定性尚未完成正式验证。
- 普通 GitHub Quality Gate 显式排除 `tests/real`；真实 Provider 结果不能由普通门禁推导。
- CI-002 与 QUALITY-001 等已确认技术债记录在 `project_state.json`。
- SP-020 已补齐正式 Daily Review CLI、Local Daily Profile、确定性 Action Hint
  与 Review-to-Action UserTask revision 边界；restart、静止备份与隔离恢复已由正式
  ACC-020 验证，验收与独立证据复核均为 `PASSED / FINAL`。

## 开发与测试

普通治理和回归门禁：

```powershell
python -m pytest tests/governance -q
python -m pytest tests --ignore=tests/real -m "not real" -q --tb=no
python -m build
```

Ruff 只检查本次修改或新增的 Python 文件：

```powershell
python -m ruff check <changed-python-files>
```

不得通过删除测试、扩大 skip 或放宽旧断言获得绿色结果。

## 文档导航

- [文档政策](docs/project/DOCUMENTATION_POLICY.md)：简体中文主要叙述语言、技术标识、原始证据、链接与例外管理规则。
- [Markdown 文档清单](docs/project/MARKDOWN_INVENTORY.md)：全部 Git 跟踪 Markdown 的范围、初始语言和最终治理状态。
- [统一术语表](docs/project/TERMINOLOGY_GLOSSARY.md)：中英文术语、技术标识与适用语境。
- [项目机器状态](project_state.json)：版本、已验证历史基线、当前 SP、质量门禁、技术债与稳定发布授权。
- [产品战略](docs/project/PRODUCT_STRATEGY.md)：可信业务操作系统定位、产品边界与 v0.36+ 路线。
- [能力所有权](docs/project/CAPABILITY_OWNERSHIP.md)：Agent Shell、业务核心、Memory、Knowledge 与 Interaction 所有权。
- [STRAT-001 合并后对账](docs/project/STRAT-001-POST-MERGE-RECONCILIATION.md)：Merge、main Quality Gate、RFC/ADR 与旧 PR #62 的最终治理事实。
- [项目大脑](docs/project/PROJECT_BRAIN.md)：长期架构事实与封存产品事实。
- [Roadmap](docs/project/ROADMAP.md)：版本范围、里程碑与候选 SP。
- [REL-035 v0.35.0 Alpha 发布规划](docs/project/REL-035-V035-ALPHA-RELEASE-PLAN.md)：
  发布范围、兼容升级、验证矩阵与授权状态机。
- [REL-035 实施任务书](docs/project/REL-035-IMPLEMENTATION-TASK.md)：版本提升、验证与发布
  收口的历史授权边界。
- [REL-035 最终发布对账](docs/project/REL-035-FINAL-RECONCILIATION.md)：Tag、GitHub
  Pre-release、发布证据和最终封存记录。
- [SP-020 Implementation Task](docs/project/SP-020-IMPLEMENTATION-TASK.md)：已封存的历史
  实施合同。
- [ACC-020](docs/acceptance/SP-020-local-daily-operating-loop.md)：本地日常闭环、
  restart 与 Quiescent Backup/Restore 的正式验收记录；PASSED / FINAL。
- [Changelog](CHANGELOG.md)：按产品版本记录用户可见变化。
- [v0.35.0 Alpha Release Notes](docs/releases/v0.35.0-alpha.md)：已发布 Pre-release 的范围、升级说明与限制。
- [v0.34.0 Alpha Release Notes](docs/releases/v0.34.0-alpha.md)：上一已发布版本的历史说明。
- [Known Limitations](docs/project/KNOWN_LIMITATIONS.md)：当前限制的可读汇总。
- [RFC](docs/rfc/)：重大方案设计。
- [ADR](docs/adr/)：已作出的架构决策。
- [SP-014 Acceptance](docs/acceptance/SP-014-unified-inbox.md)：Unified Inbox 最终产品验收。

## 版本与 Release

- 当前源码版本：`0.35.0`。
- Release 阶段：v0.35.0 Alpha / GitHub Pre-release Published。
- 当前已发布 Git Tag：`v0.35.0`；上一已发布 Tag：`v0.34.0`。
- v0.35.0 Tag：ANNOTATED / REMOTE_VERIFIED。
- v0.35.0 GitHub Release：PUBLISHED / PRE-RELEASE / REMOTE_VERIFIED；不上传 wheel 或 sdist。
- 外部发布事实：Tag 与 Release 的实际存在性、目标、URL 和发布时间以 GitHub Tags and GitHub Releases 为权威来源。
- v0.35.0：Local Daily Operating Loop 已发布为 Pre-release；REL-035 已最终对账并封存。
- 最近完成的 Product SP：SP-021 / ACC-021 PASSED / FINAL / reconciled / archived；当前 Product SP 与 Governance Task 均为 None。

任务编号代表开发批次，不等同于产品版本；一个产品版本可以由多个 SP 共同组成。
