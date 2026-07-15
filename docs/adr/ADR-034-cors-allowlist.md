# ADR-034: CORS Allowlist Policy

## Status
Accepted

## Context
The API previously used \llow_origins=["*"]\, allowing any browser-based origin to access API endpoints. This is unsafe for browser-based integrations.

## Decision
Use an explicit, centrally-configured CORS allowlist.

### Policy
1. Default: no origins allowed (implicit deny-all).
2. Allowed origins are parsed from \AI_LAB_API_ALLOWED_ORIGINS\ (comma-separated).
3. Origins are normalized: deduplicated, whitespace-stripped, case-insensitive dedup.
4. Wildcard \*\ is rejected when authentication is enabled.
5. Non-browser callers (CLI, direct HTTP) are unaffected.
6. CORS configuration is stored in \ApiSecurityConfig\ alongside auth.

### Rationale
- Browser-originated requests carry user sessions and cookies; wildcard CORS defeats same-origin constraints.
- Explicit origins make the system's allowed callers observable and auditable.
- Service-to-service calls use Authorization headers and do not need CORS preflight.

## Consequences
- Browser-based consumers must be explicitly added to the allowlist.
- Preflight (OPTIONS) responses respect the configured origin list.
