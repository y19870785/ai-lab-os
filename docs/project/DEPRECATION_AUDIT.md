# AI-Lab 重复实现弃用审计

> 日期：2026-08-15
> 重建来源：`6d2b40d` 弃用审计与 `8967e20` 重复实现收口
> 性质：GOV-RECOVERY-001-R2 授权的独立技术债重建；不构成 Ready 或 Merge 授权。

## 审计范围

清点 [能力所有权](CAPABILITY_OWNERSHIP.md) 标记为 DEPRECATION_CANDIDATE 的重复实现：顶层 `agents/`、`knowledge/`、`core/agent/` 的引用关系、打包范围与工作区草稿文件。

## 引用关系审计

| 模块 | 文件数 | 外部引用 | 判定 |
| --- | --- | --- | --- |
| `agents/`（顶层） | 13 | 无（仅自身内部 import） | 非 canonical / DEPRECATED_COMPATIBILITY |
| `core/agent/` | 3 | 无（仅自身内部 import） | 非 canonical / DEPRECATED_COMPATIBILITY |
| `core/agents/` | 12 | 有（core/system、core/workflow、examples、tests） | 在用实现 |
| `knowledge/`（顶层） | 20 | 无（仅自身内部 import） | 非 canonical / DEPRECATED_COMPATIBILITY |
| `core/knowledge/` | 14 | 有（core/system、core/agents/executor、examples、tests） | 在用实现 |
| `workflows/`（顶层） | 1 | 无（空 `__init__.py` 桩） | DEPRECATED_COMPATIBILITY 空桩 |
| `prompts/`（顶层） | 1 | 无（空 `__init__.py` 桩） | DEPRECATED_SOURCE_ONLY 空桩 |
| `database/`（顶层） | 1 | 无（空 `__init__.py` 桩） | 空桩 |

说明：`agents.identity`、`agents.tools`、`knowledge.models` 等引用全部发生在各自包内部；`core.agents` 与 `core.knowledge` 是正式入口（如 `core/system/factory.py`、`core/agents/executor.py`）实际使用的实现。

## 打包范围审计

`pyproject.toml` 的 `[tool.setuptools.packages.find]` 当前把 canonical implementation packages 与 `agents*`、`knowledge*`、`workflows*` deprecated compatibility packages 一并列入发布产物；`core.agent` 随 `core*` 保留。`prompts*` 与 `database*` 未在 include 中，不打包。

## 工作区草稿文件

仓库根目录存在未跟踪草稿文件（`_fix_test.py`、`_phase23_writer.py`、`_p27_0.b64` 至 `_p27_6.b64`、`_p27_all.b64`），已确认均不在 `git ls-files` 中；本轮已清理，不进入版本库。

## 原收口建议（已由 R6B 兼容性证据修正）

R4/R5 曾建议把 `agents*`、`knowledge*`、`workflows*` 移出 package discovery 并删除旧目录。R6B 对固定 Base `f01a8c74...` 实际构建 wheel/sdist 后确认：这些 namespace 与 `core.agent` 都进入受支持安装产物并可导入。根据 [版本政策](../governance/VERSIONING_POLICY.md)“同一 Major 的 Minor 升级向后兼容、弃用至少保留一个 Minor”规则，立即删除不成立；本节原建议由下述兼容矩阵取代。

## R6B 基线可导入性矩阵

| 命名空间 | Base 源码 import | Base 构建制品 wheel/sdist | 公开源码示例/正式文档 | 仓库外部消费者 | Canonical 替代路径 | Forwarding 判定 |
|---|---|---|---|---|---|---|
| `agents` / `agents.*` | 13 个模块中 11 个成功；`agents.memory`、`agents.permission` 因 base 的旧 `MemoryType` import 失败 | 包含；clean install 保持相同 11 成功 / 2 个既有失败 | `agents/__init__.py` 有 `from agents...` 示例；RFC-003 为历史设计 | 无，仅包内自引用 | `core/agents` | 类型与 lifecycle 无完整一一映射；保留原模块，不把既有失败误报为兼容成功 |
| `knowledge` / `knowledge.*` | 20/20 成功 | 包含；clean install 20/20 成功 | `knowledge/__init__.py` 有 `from knowledge...` 示例；ADR-006/RFC-004 为历史设计 | 无，仅包内自引用 | `core/knowledge` | 模型、storage protocol 无完整一一映射；保留原模块 |
| `core.agent` | 3/3 成功 | 随 `core*` 包含；clean install 3/3 成功 | ADR-005、RFC-003 与 package docstring | 无，仅包内自引用 | `core.agents` | ADR-005 已证明无一对一映射；保留原模块 |
| `workflows` | 1/1 成功 | 包含；clean install 1/1 成功 | REPOSITORY_MAP 曾列为 Workflow 定义 | 无；空桩 | `core.workflow` | 薄 namespace 可提示 replacement，但继续保留空桩 |
| `prompts` | 1/1 成功 | base wheel/sdist 不包含，clean install import 失败 | VERSIONING_POLICY 仅含未来提案 | 无；空桩 | 无 canonical registry | 保持 base artifact 行为；源码空桩暂留且不打包 |

矩阵直接来自 clean detached `origin/main` build 与 clean target install，对 37 个 packaged compatibility 模块逐个 import，不以 `__all__` 推断。35 个成功与 2 个既有失败在修订制品中保持一致；source-only `prompts` 另行验证。它能证明 base artifact 的 import surface，却不能证明所有未知外部消费者不存在。

## 兼容安全收口结果（2026-08-15，R6B）

- cleanup phase completed：duplicate implementation ownership removed where safe；compatibility shims retained；final namespace removal deferred for at least one Minor。
- duplicate implementation 的 canonical ownership 已收口到 `core/agents` 与 `core/knowledge`；旧 namespace 不再拥有 canonical 身份，但未立即物理删除。
- `agents/`（13 文件）、`knowledge/`（20 文件）与 `core/agent/`（3 文件）因无法建立语义可靠的一一 forwarding，保留 base 原模块并在 package import 时发出 `DeprecationWarning`。
- `workflows/` 保留空 compatibility namespace 并指向 `core.workflow`；`prompts/` 保持 base 的 source-only/not-packaged 行为。所有兼容 namespace 至少保留整个 v0.36 Minor，最早删除版本为 v0.37.0，且删除仍需独立授权。
- `database/` 不在打包范围且无运行时引用，但既有 PILOT 隔离守卫要求该目录存在；clean checkout 不保留空目录，因此保留最小 `database/__init__.py` 兼容标记，不恢复任何数据库实现。
- `pyproject.toml` 明确区分 canonical implementation packages（`api*`、`applications*`、`cli*`、`core*`）与 deprecated compatibility packages（`agents*`、`knowledge*`、`workflows*`）。本阶段没有能够安全剥离的 `excluded obsolete implementation packages`；`prompts*`、`database*` 是 source-only/guard marker 而非实现包，仍不打包。
- 证据分类为：`no supported in-repository consumer`；`documented and packaged base import surface exists`；`cannot prove absence of every unknown external consumer`；换言之，`unknown external consumers cannot be disproven`。因此不再记录 `NO_SUPPORTED_PUBLIC_IMPORT_CONTRACT_FOR_REMOVED_PACKAGES`，也不使用“Alpha 所以兼容政策不适用”的例外。
- wheel/sdist 与 clean target install 测试锁定兼容包存在、真实 import 成功、`DeprecationWarning` 和 source-only `prompts` 边界。
- 相关文档已同步：ARCHITECTURE.md 模块树、PROJECT_CONTEXT.md、ADR-005 链接、CAPABILITY_OWNERSHIP.md 状态行。
- 原提交记录全量回归 1868 通过、零失败；本重建分支的结果以本轮独立验证为准。

## 正式文档一致性扫描（2026-08-15）

对当前非归档 Markdown 中的 `agents/`、`knowledge/`、`core/agent/`、`workflows/`、`prompts/` 与 `knowledge/storage/protocol.py` 声明逐项分类：

| 命中 | 分类 | 处理 |
|---|---|---|
| ADR-006 的 `knowledge/storage/protocol.py` Accepted 路径 | CURRENT_CONFLICT | 已在原 ADR 顶部追加可审计 amendment；当前路径固定为 `core/knowledge/protocol.py`、`sqlite_store.py`、`manager.py`，原正文保留为历史 |
| VERSIONING_POLICY 的顶层 `prompts/` 目录树与 v0.33 当前基线 | CURRENT_CONFLICT | 已标记 `DEPRECATED_SOURCE_ONLY / NOT_CANONICAL / NOT_PACKAGED`，目录树仍是 FUTURE_PROPOSAL，当前版本对账为 v0.35.0 Alpha |
| RFC-003 顶层 `agents/`、RFC-004 顶层 `knowledge/` | HISTORICAL_CONTEXT / FUTURE_PROPOSAL | RFC 历史正文不批量改写；不作为当前结构或实现证明 |
| ADR-005 的 `core/agent/` 与顶层 `agents` | HISTORICAL_CONTEXT / COMPATIBILITY_RECORD | 已有显著说明：旧类型与当前 `core/agents` 无一对一映射，因此保留原语义 deprecated package |
| TECHNICAL_DEBT、CAPABILITY_OWNERSHIP、PROJECT_CONTEXT、REPOSITORY_MAP 中的删除说明 | CURRENT_CONFLICT / REMOVAL_RECORD | 当前结构声明已改为 compatibility retained；明确历史删除尝试的记录可保留 |
| ARCHITECTURE、PROJECT_STRUCTURE、PUBLIC_API_INVENTORY、TEST_MATRIX 的 `core/agents`/`core/knowledge` | 当前 canonical 路径 | 无冲突，不修改 |

本扫描关闭的是仓库当前正式文档冲突，不声称所有未知外部文档、历史分支或外部消费者不存在；外部兼容性证据边界继续遵循前述三层结论。

## 相关文档

- [能力所有权](CAPABILITY_OWNERSHIP.md)
- [技术债清单](TECHNICAL_DEBT.md)
- [Git 工作流](../governance/GIT_WORKFLOW.md)
