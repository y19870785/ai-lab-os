# ADR-026: Application Context Design

**Date:** 2026-07-13
**Status:** Accepted

## Decision

所有 Application 请求通过 `ApplicationContext` 统一携带隔离信息（WorkspaceKey），不通过全局变量或线程局部存储。

理由：显式传递避免隐式依赖，便于测试和调试。
