# ADR-033: API Authentication Mechanism

## Status
Accepted

## Context
The AI-Lab API previously allowed unauthenticated access to all endpoints. As the system transitions from prototype to alpha, API access must be controlled.

## Decision
Use a single, centrally-configured static Bearer token for API authentication.

### Authentication flow
1. \ApiSecurityConfig\ is built from \SystemSettings\ at app creation time.
2. \Authenticator\ validates \Authorization: Bearer <token>\ using \hmac.compare_digest\.
3. Protected routers include \Depends(require_auth)\ as a router-level dependency.
4. Failed auth returns HTTP 401 with \ErrorCategory.UNAUTHENTICATED\ and standard \WWW-Authenticate: Bearer\ semantics.
5. Tokens are never logged or included in error responses.

### Configuration
- \AI_LAB_API_AUTH_ENABLED\: boolean, defaults to \True\.
- \AI_LAB_API_TOKEN\: bearer token value, empty by default.
- Auth enabled without token causes application build failure.

## Alternatives Considered
- **JWT/OAuth**: proportionally complex for a single-tenant alpha; deferred.
- **IP-based allowlist**: fragile in dynamic environments; complements but does not replace.
- **Zero auth / trust-by-network**: unacceptable for any remote exposure.

## Consequences
- Initial consumer integration requires explicit token configuration.
- Token rotation requires configuration change and restart.
- No user-level or role-based access differentiation in this phase.
