# ADR-027：工作空间隔离

**Date:** 2026-07-13
**Status:** Accepted

## 决策

采用 Tenant → Workspace → Namespace 三级逻辑隔离。当前只实现逻辑隔离（通过 WorkspaceKey 校验），不实现物理数据库隔离。

跨 Workspace 数据访问必须显式检查 `CrossWorkspaceError`。
