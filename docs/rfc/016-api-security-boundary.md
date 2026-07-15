# RFC-016: Application API Security Boundary

## Status
Adopted

## Context
AI-Lab Application / CEO Assistant API has entered the real execution chain. However:
- The API lacks unified access authentication.
- CORS is configured to allow any origin (\llow_origins=["*"]\).
- Without authentication, any caller with network access can invoke business APIs.
- There is no explicit contract between caller identity and API trust boundary.

SP-006 establishes the minimum, verifiable API security boundary for the alpha development phase.

## Decision
1. All business API endpoints (tasks, work-logs, reminders, chat, applications, decisions, brief, knowledge, workflows) require a bearer token when authentication is enabled.
2. Health and metrics endpoints (/health, /health/*, /metrics) remain public.
3. Authentication uses static bearer tokens configured via \AI_LAB_API_TOKEN\. Token validation uses \hmac.compare_digest\ for constant-time comparison.
4. CORS uses an explicit allowlist via \AI_LAB_API_ALLOWED_ORIGINS\; the default forbids any origin. Wildcard \*\ with authentication enabled is rejected at configuration time.
5. Authentication enforcement is centralized in \pplications/security/\ and applied at router level via \include_router(dependencies=[Depends(require_auth)])\.
6. Token configuration is validated at application build time: if auth is enabled and no token is configured, the app fails to start.
7. When auth is disabled (explicit \AI_LAB_API_AUTH_ENABLED=false\), it must be explicit and is intended only for trusted local development.

## Consequences
- All API consumers must include an \Authorization: Bearer <token>\ header for protected endpoints.
- CLI and non-browser callers are unaffected by CORS restrictions.
- Missing or invalid tokens return HTTP 401.
- Token never appears in logs, responses, or exception details.
- Auth-disabled mode is test-only; production-or-remote must use auth enabled.
- Prompt injection, multi-user RBAC, JWT/OAuth, and complete identity systems remain out of scope.
