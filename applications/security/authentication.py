"""Bearer-token authentication with constant-time comparison."""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass

from applications.security.config import ApiSecurityConfig
from core.errors import ErrorCategory, FailureInfo

logger = logging.getLogger("ai-lab.security")

AUTH_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "


@dataclass(frozen=True)
class AuthResult:
    """Outcome of a Bearer-token validation; never exposes the token."""

    is_valid: bool
    failure: FailureInfo | None = None

    @classmethod
    def valid(cls) -> "AuthResult":
        return cls(is_valid=True)

    @classmethod
    def missing(cls) -> "AuthResult":
        return cls(
            is_valid=False,
            failure=FailureInfo(
                code="api.auth.missing",
                category=ErrorCategory.UNAUTHENTICATED,
                message="Authentication required",
                component="api.auth",
                operation="validate_bearer",
                retryable=False,
            ),
        )

    @classmethod
    def invalid_format(cls) -> "AuthResult":
        return cls(
            is_valid=False,
            failure=FailureInfo(
                code="api.auth.invalid_format",
                category=ErrorCategory.UNAUTHENTICATED,
                message="Invalid Authorization header format; use 'Bearer <token>'",
                component="api.auth",
                operation="validate_bearer",
                retryable=False,
            ),
        )

    @classmethod
    def invalid_token(cls) -> "AuthResult":
        return cls(
            is_valid=False,
            failure=FailureInfo(
                code="api.auth.invalid_token",
                category=ErrorCategory.UNAUTHENTICATED,
                message="Invalid authentication token",
                component="api.auth",
                operation="validate_bearer",
                retryable=False,
            ),
        )


class Authenticator:
    """Validates Bearer tokens with constant-time comparison."""

    def __init__(self, config: ApiSecurityConfig) -> None:
        self.config = config

    def validate(self, authorization_header: str | None) -> AuthResult:
        if not self.config.auth_enabled:
            return AuthResult.valid()
        if not authorization_header:
            return AuthResult.missing()
        if not authorization_header.startswith(BEARER_PREFIX):
            return AuthResult.invalid_format()
        token_bytes = authorization_header[len(BEARER_PREFIX):].encode("utf-8")
        expected_bytes = self.config.api_token.encode("utf-8")
        if not hmac.compare_digest(token_bytes, expected_bytes):
            logger.warning("api.auth.invalid_token")
            return AuthResult.invalid_token()
        return AuthResult.valid()

    def validate_from_request(self, request) -> AuthResult:
        return self.validate(request.headers.get(AUTH_HEADER))
