# RFC-014: Application Foundation Architecture

**Version:** 1.0
**Date:** 2026-07-13
**Status:** Implemented (v0.30.0)

## Summary

建立 AI-Lab Application Foundation，实现 Application Runtime + Workspace/Tenant 隔离 + REST API + CLI，使 AI-Lab 具备可部署、可调用的 Alpha 产品入口。

## Architecture

```
CLI / REST API
      ↓
ApplicationRuntime (唯一入口)
      ↓
ApplicationContext (携带 WorkspaceKey)
      ↓
Orchestrator / Agent Runtime
      ↓
Knowledge / Memory / Tool / Provider
```

## Key Decisions

1. ApplicationRuntime 是唯一业务入口，不直接访问 Provider/DB/Tool
2. WorkspaceKey 作为统一隔离键，所有底层调用携带
3. ApplicationManifest 声明所有依赖，禁止散落注册
4. CLI 和 API 共享同一个 ApplicationRuntime

## Files

- `applications/` — ApplicationRuntime + Registry + Manifest
- `core/workspace/` — Tenant + Workspace + WorkspaceKey
- `api/` — FastAPI REST API
- `cli/` — CLI 命令行
- `deploy/` — Docker 部署配置
- `core/security.py` — 安全边界
