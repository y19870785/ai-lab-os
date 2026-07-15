"Immutable API security configuration parsed from SystemSettings."

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiSecurityConfig:
    "Single source of truth for API authentication and CORS policy."

    auth_enabled: bool = True
    api_token: str = ""
    allowed_origins: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        from urllib.parse import urlparse
        normalized = []
        seen = set()
        for origin in self.allowed_origins:
            o = origin.strip()
            if not o:
                continue
            if o == "*":
                if self.auth_enabled:
                    raise ValueError(
                        "Wildcard origin '*' is not allowed with authentication enabled"
                    )
                normalized.append(o)
                seen.add(o)
                continue
            # Validate origin format: must be http(s)://host[:port]
            parsed = urlparse(o)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"Origin '{o}' has invalid scheme; must be http or https"
                )
            if not parsed.hostname:
                raise ValueError(f"Origin '{o}' lacks a valid host")
            if parsed.username or parsed.password:
                raise ValueError(
                    f"Origin '{o}' contains credentials; not allowed"
                )
            if parsed.path and parsed.path != "/":
                raise ValueError(
                    f"Origin '{o}' contains a path; only scheme+host+port allowed"
                )
            if parsed.query or parsed.fragment:
                raise ValueError(
                    f"Origin '{o}' contains query/fragment; only scheme+host+port allowed"
                )
            # Reconstruct canonical form, preserving IPv6 brackets
            host = parsed.hostname
            if host is not None and ":" in host:
                host = f"[{host}]"
            # Access parsed.port safely -- it raises ValueError for >65535
            port = None
            try:
                port = parsed.port
            except ValueError:
                raise ValueError(
                    f"Origin '{o}' has invalid port"
                ) from None
            if port is not None and port not in range(1, 65536):
                raise ValueError(
                    f"Origin '{o}' has invalid port: {port}"
                )
            if port is not None:
                canonical = f"{host}:{port}"
            else:
                canonical = host
            canonical = f"{parsed.scheme}://{canonical}"
            if canonical.lower() not in seen:
                seen.add(canonical.lower())
                normalized.append(canonical)
        object.__setattr__(self, "allowed_origins", normalized)

    @classmethod
    def from_settings(
        cls,
        *,
        auth_enabled: bool,
        api_token: str,
        allowed_origins: list[str] | None = None,
        environment: str = "development",
    ) -> "ApiSecurityConfig":
        "Build and validate config; raises if auth is enabled without a token."
        if auth_enabled and not api_token:
            raise ValueError(
                "API authentication is enabled but no API token is configured. "
                "Set AI_LAB_API_TOKEN or explicitly disable auth with "
                "AI_LAB_API_AUTH_ENABLED=false."
            )
        return cls(
            auth_enabled=auth_enabled,
            api_token=api_token,
            allowed_origins=allowed_origins or [],
        )
