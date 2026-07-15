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
            if o.lower() in seen:
                continue
            seen.add(o.lower())
            normalized.append(o)
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
