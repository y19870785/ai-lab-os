# AI-Lab OS

> SP-019 已完成 Squash Merge、ACC-019 A～M 与 post-merge Quality Gate：Daily Review 通过同一确定性只读边界聚合 Work Log、UserTask、Waiting-For、Reminder 与 Inbox。
>
> SP-020 已定义 Local Daily Operating Loop Planning Baseline；Implementation 未批准、
> 未启动，ACC-020 未执行。当前产品行为仍以 SP-019 封存基线为准。

面向个人经营者和本地工作流的 AI Operating System 基础设施：用一套 Composition Root 连接任务、提醒、日程、收件箱、记忆、Agent 与可选模型 Provider。

**当前版本：v0.34.0 Alpha / Release Authorized**
**成熟度：Alpha / local-first / single-user-oriented**

授权 Tag 为 `v0.34.0`，授权 GitHub Release 类型为 **Pre-release**，不上传 wheel 或 sdist。Tag 与 Release 的实际存在性、目标、URL 和发布时间以 GitHub 为权威来源。

AI-Lab 能帮助整理信息、记录工作、创建任务与提醒；最终业务判断和重要审批仍由用户负责。当前版本适合本地开发、验证和受控试用，不应被描述为 production ready。

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

| Profile | 用途 | 关键边界 |
|---|---|---|
| Minimal Core | Core、Memory 与基础 Runtime 开发 | 不自动安装 API、真实 Provider 或 Knowledge 大型依赖 |
| Local | API、CLI、Mock Provider、测试和构建 | 推荐的本地开发组合 |
| Real Provider | 显式外部模型验证 | 需要凭据、网络和单独授权，不属于普通 Quality Gate |
| Knowledge | 可选向量与 embedding 依赖 | 真实产品主链路仍未完成 |

运行行为由环境配置控制。默认关闭的能力不会因为代码存在而自动成为可用产品功能。

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
- Daily Review 只支持 `today` / `yesterday`，不持久化 Review snapshot，不支持任意历史日期，不调用 LLM、不主动推送，且没有 Daily Review CLI。
- Knowledge 真实主链路、Web UI、Docker 受控 build/run 与长期稳定性尚未完成正式验证。
- 普通 GitHub Quality Gate 显式排除 `tests/real`；真实 Provider 结果不能由普通门禁推导。
- CI-002 与 QUALITY-001 等已确认技术债记录在 `project_state.json`。
- SP-020 规划所针对的当前缺口仍存在：没有正式 Daily Review CLI、稳定绝对数据目录的
  Local Daily Profile、确定性 Action Hint，以及 restart/静止备份/隔离恢复正式验收。

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

- [项目机器状态](project_state.json)：版本、已验证历史基线、当前 SP、质量门禁、技术债与稳定发布授权。
- [项目大脑](docs/project/PROJECT_BRAIN.md)：长期架构事实与封存产品事实。
- [Roadmap](docs/project/ROADMAP.md)：版本范围、里程碑与候选 SP。
- [SP-020 Implementation Task](docs/project/SP-020-IMPLEMENTATION-TASK.md)：未来实现阶段、
  停止条件与授权边界；当前未获 Implementation 授权。
- [ACC-020](docs/acceptance/SP-020-local-daily-operating-loop.md)：本地日常闭环、
  restart 与 Quiescent Backup/Restore 的未来验收合同；当前 NOT_EXECUTED。
- [Changelog](CHANGELOG.md)：按产品版本记录用户可见变化。
- [v0.34.0 Alpha Release Notes](docs/releases/v0.34.0-alpha.md)：本候选版本范围、升级说明与限制。
- [Known Limitations](docs/project/KNOWN_LIMITATIONS.md)：当前限制的可读汇总。
- [RFC](docs/rfc/)：重大方案设计。
- [ADR](docs/adr/)：已作出的架构决策。
- [SP-014 Acceptance](docs/acceptance/SP-014-unified-inbox.md)：Unified Inbox 最终产品验收。

## 版本与 Release

- 当前源码版本：`0.34.0`。
- Release 阶段：v0.34.0 Alpha / Release Authorized。
- 上一个 Git Tag：`v0.33.0`。
- 授权 Tag：`v0.34.0`。
- GitHub Release 类型：Pre-release，不上传 wheel 或 sdist。
- 外部发布事实：Tag 与 Release 的实际存在性、目标、URL 和发布时间以 GitHub Tags and GitHub Releases 为权威来源。

任务编号代表开发批次，不等同于产品版本；一个产品版本可以由多个 SP 共同组成。
