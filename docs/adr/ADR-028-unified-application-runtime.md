# ADR-028: Unified Application Runtime

**Date:** 2026-07-13
**Status:** Accepted

## Decision

CLI 和 REST API 共享同一个 `ApplicationRuntime` 实例，不各自创建。

理由：统一生命周期管理、统一应用注册、避免代码重复。
