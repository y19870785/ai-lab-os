# Markdown 文档治理清单

> DOCS-001 使用 `git ls-files "*.md" "*.markdown"` 生成并核对本清单。初始语言统计保留任务开始时的 173 个文件基线；DOCS-001 新增 3 份治理文档，REL-035 新增 4 份发布治理文档，STRAT-001 新增 5 份战略治理文档，STRAT-001A 新增 1 份对账文档，ARCH-001 新增 6 份架构规划文档，ARCH-001A、SP-021A 与 INT-001A 各新增 1 份自闭环对账文档，INT-001 新增 3 份实现与验收文档，PILOT-001 新增 3 份中文规划、验收与发现证据文档，PILOT-001-IBD 新增 4 份中文设计、验收与决策文档，PILOT-001-IB-IMP-A 新增 1 份中文安全 Spike 证据文档，PILOT-001-P1A 新增 1 份中文内部可信确认验收文档，PILOT-001-P1B 新增 1 份中文进程隔离缓解与受支持 Pilot 部署 Profile 验收文档，SP-022 新增 5 份中文规划合同与验收矩阵文档。标题、表格、乱码、长篇叙述和链接由治理测试动态扫描，当前没有排除项或未解决问题。

## 汇总

- Git 跟踪 Markdown：215
- 仓库自有且纳入范围：215
- 排除：0
- 初始中文：93
- 初始中英混合：41
- 初始英文为主：39
- 已审计并标准化的既有文档：173
- 新增中文治理文档：39
- 有效标题：每份文档恰好一个中文一级标题，其他普通标题均含中文
- Markdown 表格：解释性表头与长篇单元格均由治理测试检查
- 已修复乱码：1 个文件（`CHANGELOG.md` 历史段落）
- 自动化语言治理回归：7 项通过
- 保留的技术英文：API、CLI、HTTP、ID、RFC、ADR、SP、ACC、UTC、JSON，以及代码符号、路径和机器状态值
- 未解决文档发现：0
- 剩余例外：0

## 清单

| 路径（Path） | 类别（Category） | 仓库自有（Repository Owned） | 初始语言（Current Language） | 事实风险（Current Fact Risk） | 要求动作（Required Action） | 排除原因（Exclusion Reason） | 最终状态（Final Status） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AGENTS.md` | Root | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `ARCHITECTURE.md` | Root | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `CHANGELOG.md` | Root | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `README.md` | Root | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `applications/alpha_assistant/README.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `applications/ceo_assistant/README.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `deploy/README.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/acceptance/SP-009-reminder-closure.md` | Acceptance | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/acceptance/SP-010-reminder-inbox.md` | Acceptance | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/acceptance/SP-011-reminder-management.md` | Acceptance | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/acceptance/SP-012-intent-safety-reminder-query.md` | Acceptance | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/acceptance/SP-013-daily-agenda.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/SP-014-unified-inbox.md` | Acceptance | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/acceptance/SP-016-waiting-for-domain.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/SP-017-follow-up-interaction-closure.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/SP-018-work-log-query-boundary-context-closure.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/SP-019-daily-review-read-model.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/SP-020-local-daily-operating-loop.md` | Acceptance | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/acceptance/INT-001-shell-neutral-trusted-interaction-adapter.md` | Acceptance | 是 | 中英混合 | 是 | INT-001 新增 | — | 完成 |
| `docs/acceptance/SP-021-canonical-trusted-interaction-domain.md` | Acceptance | 是 | 中英混合 | 是 | SP-021 新增 | — | 完成 |
| `docs/acceptance/SP-022-quote-request.md` | Acceptance | 是 | 中文 | 是 | SP-022 新增 | — | 待独立规划审查 |
| `docs/acceptance/PILOT-001-wecom-owner-pilot.md` | Acceptance | 是 | 中文 | 是 | PILOT-001 新增 | — | 规划中 |
| `docs/acceptance/PILOT-001-phase0-hermes-wecom-discovery.md` | Acceptance | 是 | 中文 | 是 | PILOT-001-P0R 新增 | — | 完成 |
| `docs/acceptance/PILOT-001-ingress-evidence-bridge.md` | Acceptance | 是 | 中文 | 是 | PILOT-001-IBD 新增 | — | 完成 |
| `docs/acceptance/PILOT-001-IB-IMP-A-hermes-capability-spike.md` | Acceptance | 是 | 中文 | 是 | PILOT-001-IB-IMP-A 新增 | — | 完成 |
| `docs/acceptance/PILOT-001-P1A-internal-trusted-ingress-confirmation.md` | Acceptance | 是 | 中文 | 是 | PILOT-001-P1A 新增 | — | 完成 |
| `docs/acceptance/PILOT-001-P1B-process-isolation-mitigation.md` | Acceptance | 是 | 中文 | 是 | PILOT-001-P1B 新增 | — | 完成 |
| `docs/adr/000-template.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-001-core-layer-package-structure.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-002-message-bus-interface.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-003-memory-layer-tech-stack.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-004-memory-data-model.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-005-agent-identity-model.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-006-knowledge-storage-strategy.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-007-decision-memory-model.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-008-unified-memory-api.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-009-database-manager-lifecycle.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-010-provider-registry-pattern.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-011-model-agnostic-principle.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-012-pipeline-architecture.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-013-hybrid-retrieval.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-014-agent-runtime-pattern.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-015-context-builder-pattern.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-016-tool-registry-pattern.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-017-tool-sandbox-isolation.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-018-adapter-pattern.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-019-tool-invocation-pipeline.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-020-workflow-runtime-pattern.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-021-workflow-state-machine.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-022-scheduler-pattern.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-023-trigger-design.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-024-agent-coordination-pattern.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-024-task-runtime-pattern.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-025-agent-message-bus.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-025-task-dependency-design.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-026-application-context.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-027-workspace-isolation.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-028-unified-application-runtime.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-029-memory-sqlite-connection-ownership.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-030-canonical-user-task-domain.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-031-scheduler-action-handler.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-032-reminder-effectively-once.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-033-api-authentication.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-034-cors-allowlist.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-035-system-lifecycle-state-machine.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-036-shutdown-admission-policy.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-037-canonical-internal-work-entrypoint.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-038-admission-gate-dependency-injection.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-039-natural-language-reminder-orchestration-boundary.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-040-reminder-status-aggregation-contract.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-041-reminder-inbox-query-boundary.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-042-reminder-list-status-consistency.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-043-reminder-management-coordination-boundary.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-044-deterministic-response-provider-separation.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-045-actionable-reminder-inbox-semantics.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-046-deterministic-intent-effect-classification.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-047-read-on-ambiguity-explicit-write.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-048-user-facing-failure-presentation.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-049-daily-agenda-read-model-boundary.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-050-cross-source-agenda-ordering-pagination.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-051-agenda-query-failure-semantics.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-052-inbox-resolution-idempotency.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-053-inbox-source-workspace-boundary.md` | ADR | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/adr/ADR-054-canonical-waiting-for-domain.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-055-daily-agenda-optional-source-composition.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-056-deterministic-follow-up-interaction-boundary.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-057-inbox-to-waiting-for-resolution-saga.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-058-work-log-service-over-episodic-storage.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-059-canonical-work-log-id-and-legacy-projection.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-060-explicit-work-log-context-references.md` | ADR | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/adr/ADR-061-daily-review-non-persistent-read-model.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-062-daily-review-source-failure-and-availability-semantics.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-063-daily-review-action-hints-pure-deterministic-presentation.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-064-local-daily-profile-quiescent-backup-restore.md` | ADR | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/adr/ADR-067-hermes-first-replaceable-agent-shell.md` | ADR | 是 | 中文 | 是 | STRAT-001 新增 | — | 完成 |
| `docs/adr/ADR-068-ai-lab-business-fact-action-authority.md` | ADR | 是 | 中文 | 是 | STRAT-001 新增 | — | 完成 |
| `docs/adr/ADR-069-shell-neutral-versioned-interaction-contract.md` | ADR | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/adr/ADR-070-preview-confirmation-ai-lab-canonical-facts.md` | ADR | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/adr/ADR-071-verified-result-required-before-final-success.md` | ADR | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/adr/ADR-072-identity-workspace-mapping-fail-closed.md` | ADR | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/adr/ADR-073-ai-lab-owned-ingress-evidence-consumption.md` | ADR | 是 | 中文 | 是 | PILOT-001-IBD 新增 | — | 完成 |
| `docs/adr/ADR-074-quote-follow-up-next-action-ownership.md` | ADR | 是 | 中文 | 是 | SP-022 新增 | — | 待独立规划审查 |
| `docs/adr/ADR-075-inbox-to-quote-request-reconciliation.md` | ADR | 是 | 中文 | 是 | SP-022 新增 | — | 待独立规划审查 |
| `docs/architecture/ARCHITECTURE.md` | Architecture | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/architecture/DATABASE_CONNECTION_OWNERSHIP.md` | Architecture | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/architecture/FAILURE_SEMANTICS.md` | Architecture | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/architecture/REMINDER_SCHEDULER_BRIDGE.md` | Architecture | 是 | 中英混合 | 否 | 术语统一 | — | 完成 |
| `docs/architecture/SYSTEM_COMPOSITION.md` | Architecture | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/architecture/USER_TASK_ARCHITECTURE.md` | Architecture | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/architecture/WAITING_FOR_DOMAIN.md` | Architecture | 是 | 中英混合 | 否 | 术语统一 | — | 完成 |
| `docs/governance/AGENT_POLICY.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/DEVELOPMENT_POLICY.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/GIT_WORKFLOW.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/KNOWLEDGE_POLICY.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/MODEL_POLICY.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/PROJECT_CONTEXT.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/governance/VERSIONING_POLICY.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/guides/DEVELOPMENT_GUIDE.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/project/ALPHA_CHECKLIST.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/ALPHA_DEPLOYMENT_REPORT.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/ALPHA_REPORT.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/ALPHA_STATUS.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/ARCHITECTURE_STATUS.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/BENCHMARK.md` | Project | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/project/DATA_PERSISTENCE_MAP.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/DECISION_INDEX.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/DEPLOYMENT_GUIDE.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/DOCUMENTATION_POLICY.md` | Project | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/project/INCIDENT_PLAYBOOK.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/INT-001-HERMES-MCP-PROJECTION.md` | Project | 是 | 中英混合 | 是 | INT-001 新增 | — | 完成 |
| `docs/project/INT-001-POST-MERGE-RECONCILIATION.md` | Project | 是 | 中英混合 | 是 | INT-001A 新增 | — | 完成 |
| `docs/project/INT-001-SHELL-NEUTRAL-TRUSTED-INTERACTION-ADAPTER.md` | Project | 是 | 中英混合 | 是 | INT-001 新增 | — | 完成 |
| `docs/project/KNOWN_LIMITATIONS.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/MARKDOWN_INVENTORY.md` | Project | 是 | 中文 | 是 | 保持原样 | — | 完成 |
| `docs/project/METRICS.md` | Project | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/project/MILESTONES.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/OPERATIONS_GUIDE.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/PERFORMANCE.md` | Project | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/project/PROJECT_BRAIN.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/PROJECT_HEALTH.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/PRODUCT_STRATEGY.md` | Project | 是 | 中文 | 是 | STRAT-001 新增 | — | 完成 |
| `docs/project/CAPABILITY_OWNERSHIP.md` | Project | 是 | 中文 | 是 | STRAT-001 新增 | — | 完成 |
| `docs/project/STRAT-001-POST-MERGE-RECONCILIATION.md` | Project | 是 | 中文 | 是 | STRAT-001A 新增 | — | 完成 |
| `docs/project/ARCH-001-TRUSTED-INTERACTION-ARCHITECTURE.md` | Project | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/project/ARCH-001-POST-MERGE-RECONCILIATION.md` | Project | 是 | 中文 | 是 | ARCH-001A 新增 | — | 完成 |
| `docs/project/PROJECT_STATUS.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/PROJECT_STRUCTURE.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/PUBLIC_API_INVENTORY.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/REL-035-FINAL-RECONCILIATION.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/REL-035-IMPLEMENTATION-TASK.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/REL-035-V035-ALPHA-RELEASE-PLAN.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/RELEASE_CHECKLIST.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/RELEASE_NOTES.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/REPOSITORY_MAP.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/ROADMAP.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/SECURITY_CHECKLIST.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/SP-020-IMPLEMENTATION-TASK.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/SP-021-CANONICAL-TRUSTED-INTERACTION-DOMAIN.md` | Project | 是 | 中英混合 | 是 | SP-021 新增 | — | 完成 |
| `docs/project/SP-021-POST-MERGE-RECONCILIATION.md` | Project | 是 | 中英混合 | 是 | SP-021A 新增 | — | 完成 |
| `docs/project/SP-022-V037-QUOTE-REQUEST-PLANNING.md` | Project | 是 | 中文 | 是 | SP-022 新增 | — | 待独立规划审查 |
| `docs/project/PILOT-001-WECOM-OWNER-TRUSTED-TASK-CAPTURE.md` | Project | 是 | 中文 | 是 | PILOT-001 新增 | — | 规划中 |
| `docs/project/PILOT-001-TRUSTED-INGRESS-EVIDENCE-BRIDGE.md` | Project | 是 | 中文 | 是 | PILOT-001-IBD 新增 | — | 完成 |
| `docs/project/TECHNICAL_DEBT.md` | Project | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/project/TERMINOLOGY_GLOSSARY.md` | Project | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `docs/project/TEST_MATRIX.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/project/VERSION_MATRIX.md` | Project | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/release/v0.30.0.md` | Release | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/releases/v0.34.0-alpha.md` | Release | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/releases/v0.35.0-alpha.md` | Release | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/review/CURRENT_RISKS.md` | Other | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/review/GPT56_REVIEW_HANDOFF.md` | Other | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/review/READING_ORDER.md` | Other | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/reviews/SR-001-first-testable-product-slice-assessment.md` | Other | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/rfc/000-template.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/001-core-layer-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/002-memory-layer-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/003-agent-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/004-knowledge-layer-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/005-core-runtime-architecture.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/006-provider-layer-architecture.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/007-knowledge-layer-architecture.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/008-agent-runtime-architecture.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/009-tool-runtime-architecture.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/010-mcp-adapter-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/011-workflow-engine-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/012-scheduler-runtime-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/013-task-runtime-architecture.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/015-reminder-scheduler-bridge.md` | RFC | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/rfc/016-api-security-boundary.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/017-system-lifecycle-admission-gate.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/018-internal-work-admission-boundary.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/019-natural-language-reminder-closure.md` | RFC | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/rfc/020-reminder-inbox.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/021-reminder-management-closure.md` | RFC | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/rfc/022-natural-language-intent-safety.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/023-daily-agenda-read-model.md` | RFC | 是 | 英文为主 | 是 | 中文化 | — | 完成 |
| `docs/rfc/024-unified-inbox-capture-to-action.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/025-canonical-waiting-for-domain.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/026-follow-up-interaction-capture-closure.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/027-work-log-query-boundary-context-closure.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/028-daily-review-read-model-deterministic-follow-up.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/029-local-daily-operating-loop-review-to-action.md` | RFC | 是 | 中文 | 是 | 事实对账 | — | 完成 |
| `docs/rfc/031-agent-shell-trusted-business-core-separation.md` | RFC | 是 | 中文 | 是 | STRAT-001 新增 | — | 完成 |
| `docs/rfc/032-trusted-interaction-boundary-adapter-contract.md` | RFC | 是 | 中文 | 是 | ARCH-001 新增 | — | 完成 |
| `docs/rfc/033-trusted-ingress-evidence-bridge.md` | RFC | 是 | 中文 | 是 | PILOT-001-IBD 新增 | — | 完成 |
| `docs/rfc/034-quote-request-trusted-write-contract.md` | RFC | 是 | 中文 | 是 | SP-022 新增 | — | 待独立规划审查 |
| `docs/rfc/RFC-013-multi-agent-architecture.md` | RFC | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/rfc/RFC-014-application-foundation.md` | RFC | 是 | 中英混合 | 是 | 术语统一 | — | 完成 |
| `docs/todo/TECHNICAL_DEBT.md` | Other | 是 | 英文为主 | 否 | 中文化 | — | 完成 |
| `examples/field_validation/sample_documents/ai_lab_overview.md` | Other | 是 | 中英混合 | 否 | 术语统一 | — | 完成 |
| `product/BUSINESS_WORKFLOWS.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `product/PRODUCT_ROADMAP.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `product/REQUIREMENTS.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `product/USE_CASES.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
| `product/VISION.md` | Other | 是 | 中文 | 否 | 保持原样 | — | 完成 |
