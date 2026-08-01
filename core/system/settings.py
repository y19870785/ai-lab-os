"""集中、不可变的系统设置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.provider_mode import detect_provider_mode

_DOTENV_LOADED = False


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SystemSettings:
    """Single source of configuration for one AI-Lab process."""

    environment: str
    provider_mode: str
    data_dir: Path
    sqlite_dir: Path
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    embedding_model: str = ""
    vector_provider: str = ""
    chroma_dir: Path | None = None
    timeout: float = 60.0
    max_retries: int = 3
    enable_knowledge: bool = False
    enable_scheduler: bool = False
    enable_coordination: bool = False
    enable_user_tasks: bool = True
    enable_daily_review: bool = True
    enable_reminders: bool = False
    enable_api: bool = False
    timezone_name: str = "Asia/Shanghai"
    scheduler_tick_interval: float = 1.0
    profile_name: str = ""
    api_bind: str = "127.0.0.1"
    workspace_tenant_id: str = "default"
    workspace_id: str = "default"
    workspace_namespace: str = "default"
    workspace_session_id: str = ""
    workspace_agent_id: str = ""

    enable_api_auth: bool = True

    api_token: str = ""

    api_allowed_origins: list[str] = ()

    def __post_init__(self) -> None:
        raw_data_dir = Path(self.data_dir)
        raw_sqlite_dir = Path(self.sqlite_dir)
        mode = self.provider_mode.lower().strip()
        if mode not in {"real", "mock", "test", "invalid"}:
            raise ValueError(f"Unsupported provider mode: {self.provider_mode}")
        object.__setattr__(self, "provider_mode", mode)
        object.__setattr__(self, "data_dir", Path(self.data_dir).resolve())
        object.__setattr__(self, "sqlite_dir", Path(self.sqlite_dir).resolve())
        if self.chroma_dir is not None:
            object.__setattr__(self, "chroma_dir", Path(self.chroma_dir).resolve())
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone_name must be a valid IANA timezone") from exc
        if self.scheduler_tick_interval <= 0:
            raise ValueError("scheduler_tick_interval must be positive")
        if self.profile_name not in {"", "local-daily"}:
            raise ValueError(f"Unsupported AI_LAB_PROFILE: {self.profile_name}")
        if self.profile_name == "local-daily":
            if not raw_data_dir.is_absolute():
                raise ValueError("AI_LAB_DATA_DIR must be an absolute path")
            if not raw_sqlite_dir.is_absolute():
                raise ValueError("AI_LAB_SQLITE_DIR must be an absolute path")
            try:
                self.sqlite_dir.relative_to(self.data_dir)
            except ValueError as exc:
                raise ValueError(
                    "AI_LAB_SQLITE_DIR must be under AI_LAB_DATA_DIR"
                ) from exc
            if mode not in {"mock", "test", "real"}:
                raise ValueError(
                    "AI_LAB_PROVIDER_MODE must be mock, test, or real"
                )
            required_flags = {
                "AI_LAB_ENABLE_USER_TASKS": self.enable_user_tasks,
                "AI_LAB_ENABLE_DAILY_REVIEW": self.enable_daily_review,
                "AI_LAB_ENABLE_REMINDERS": self.enable_reminders,
                "AI_LAB_ENABLE_SCHEDULER": self.enable_scheduler,
                "AI_LAB_ENABLE_API": self.enable_api,
            }
            disabled_flags = {
                "AI_LAB_ENABLE_KNOWLEDGE": self.enable_knowledge,
                "AI_LAB_ENABLE_COORDINATION": self.enable_coordination,
            }
            missing = [name for name, enabled in required_flags.items() if not enabled]
            unexpected = [name for name, enabled in disabled_flags.items() if enabled]
            if missing or unexpected:
                raise ValueError(
                    "Local Daily Profile feature flags are invalid: "
                    + ", ".join(missing + unexpected)
                )
            if not self.enable_api_auth or not self.api_token:
                raise ValueError(
                    "Local Daily Profile requires API auth and a non-empty token"
                )
            if self.api_bind != "127.0.0.1":
                raise ValueError("Local Daily Profile API bind must be 127.0.0.1")
            workspace_values = (
                self.workspace_tenant_id,
                self.workspace_id,
                self.workspace_namespace,
                self.workspace_session_id,
                self.workspace_agent_id,
            )
            if any(not value.strip() for value in workspace_values):
                raise ValueError(
                    "Local Daily Profile requires a complete WorkspaceKey"
                )

    def safe_summary(self, *, project_root: Path | None = None) -> dict[str, object]:
        """Return effective configuration without exposing credentials."""

        root = (project_root or Path.cwd()).resolve()
        legacy = (root / "data").resolve()
        return {
            "profile": self.profile_name or "default",
            "data_root": str(self.data_dir),
            "sqlite_root": str(self.sqlite_dir),
            "timezone": self.timezone_name,
            "provider_mode": self.provider_mode,
            "features": {
                "user_tasks": self.enable_user_tasks,
                "daily_review": self.enable_daily_review,
                "reminders": self.enable_reminders,
                "scheduler": self.enable_scheduler,
                "knowledge": self.enable_knowledge,
                "coordination": self.enable_coordination,
                "api": self.enable_api,
            },
            "auth_enabled": self.enable_api_auth,
            "api_bind": self.api_bind,
            "api_token": "configured" if self.api_token else "not configured",
            "provider_secret": (
                "configured" if self.api_key else "not configured"
            ),
            "workspace": {
                "tenant_id": self.workspace_tenant_id,
                "workspace_id": self.workspace_id,
                "namespace": self.workspace_namespace,
                "session_id": self.workspace_session_id,
                "agent_id": self.workspace_agent_id,
            },
            "legacy_data_dir_detected": (
                legacy != self.data_dir and legacy.exists()
            ),
            "legacy_data_dir": (
                str(legacy)
                if legacy != self.data_dir and legacy.exists()
                else None
            ),
        }


def _load_dotenv_once(project_root: Path) -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(project_root / ".env", override=False)
    finally:
        _DOTENV_LOADED = True


def load_system_settings(
    *,
    project_root: Path | None = None,
    load_dotenv: bool = True,
) -> SystemSettings:
    """Load environment variables once at a process entry point."""

    root = (project_root or Path.cwd()).resolve()
    if load_dotenv:
        _load_dotenv_once(root)

    explicit_mode = os.getenv("AI_LAB_PROVIDER_MODE", "").strip().lower()
    detected = detect_provider_mode()
    mode = explicit_mode or detected
    if mode == "mock" and explicit_mode != "mock":
        # No implicit mock in a real process. Tests inject test/mock explicitly.
        mode = "invalid"

    data_dir = Path(os.getenv("AI_LAB_DATA_DIR", str(root / "data")))
    sqlite_dir = Path(os.getenv("AI_LAB_SQLITE_DIR", str(data_dir / "sqlite")))
    profile_name = os.getenv("AI_LAB_PROFILE", "").strip().lower()
    if profile_name not in {"", "local-daily"}:
        raise ValueError(f"Unsupported AI_LAB_PROFILE: {profile_name}")
    local_daily = profile_name == "local-daily"
    if local_daily:
        required = (
            "AI_LAB_DATA_DIR",
            "AI_LAB_SQLITE_DIR",
            "AI_LAB_TIMEZONE",
            "AI_LAB_PROVIDER_MODE",
            "AI_LAB_ENABLE_USER_TASKS",
            "AI_LAB_ENABLE_DAILY_REVIEW",
            "AI_LAB_ENABLE_REMINDERS",
            "AI_LAB_ENABLE_SCHEDULER",
            "AI_LAB_ENABLE_KNOWLEDGE",
            "AI_LAB_ENABLE_COORDINATION",
            "AI_LAB_ENABLE_API",
            "AI_LAB_API_AUTH_ENABLED",
            "AI_LAB_API_TOKEN",
            "AI_LAB_API_BIND",
            "AI_LAB_TENANT_ID",
            "AI_LAB_WORKSPACE_ID",
            "AI_LAB_NAMESPACE",
            "AI_LAB_SESSION_ID",
            "AI_LAB_AGENT_ID",
        )
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError(
                "Local Daily Profile missing explicit settings: "
                + ", ".join(missing)
            )

    return SystemSettings(
        environment=os.getenv("AI_LAB_ENV", "development"),
        provider_mode=mode,
        data_dir=data_dir,
        sqlite_dir=sqlite_dir,
        api_key=os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("AI_LAB_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", ""),
        model=os.getenv("AI_LAB_LLM_MODEL") or os.getenv("OPENAI_MODEL", ""),
        embedding_model=os.getenv("AI_LAB_EMBEDDING_MODEL") or os.getenv("OPENAI_EMBEDDING_MODEL", ""),
        vector_provider=os.getenv("AI_LAB_VECTOR_PROVIDER", ""),
        chroma_dir=Path(os.getenv("AI_LAB_CHROMA_DIR", str(data_dir / "chroma"))),
        timeout=float(os.getenv("AI_LAB_LLM_TIMEOUT", "60")),
        max_retries=int(os.getenv("AI_LAB_LLM_RETRY", "3")),
        enable_knowledge=_as_bool(os.getenv("AI_LAB_ENABLE_KNOWLEDGE"), False),
        enable_scheduler=_as_bool(os.getenv("AI_LAB_ENABLE_SCHEDULER"), False),
        enable_coordination=_as_bool(os.getenv("AI_LAB_ENABLE_COORDINATION"), False),
        enable_user_tasks=_as_bool(os.getenv("AI_LAB_ENABLE_USER_TASKS"), True),
        enable_daily_review=_as_bool(os.getenv("AI_LAB_ENABLE_DAILY_REVIEW"), True),
        enable_reminders=_as_bool(os.getenv("AI_LAB_ENABLE_REMINDERS"), False),
        enable_api=_as_bool(os.getenv("AI_LAB_ENABLE_API"), False),
        timezone_name=os.getenv("AI_LAB_TIMEZONE", "Asia/Shanghai"),
        scheduler_tick_interval=float(os.getenv("AI_LAB_SCHEDULER_TICK_INTERVAL", "1")),
        profile_name=profile_name,
        api_bind=os.getenv("AI_LAB_API_BIND", "127.0.0.1"),
        workspace_tenant_id=os.getenv(
            "AI_LAB_TENANT_ID", "local" if local_daily else "default"
        ),
        workspace_id=os.getenv(
            "AI_LAB_WORKSPACE_ID", "daily" if local_daily else "default"
        ),
        workspace_namespace=os.getenv("AI_LAB_NAMESPACE", "default"),
        workspace_session_id=os.getenv(
            "AI_LAB_SESSION_ID", "local-daily" if local_daily else ""
        ),
        workspace_agent_id=os.getenv(
            "AI_LAB_AGENT_ID", "local-user" if local_daily else ""
        ),

        enable_api_auth=_as_bool(os.getenv("AI_LAB_API_AUTH_ENABLED"), True),

        api_token=os.getenv("AI_LAB_API_TOKEN", ""),

        api_allowed_origins=[

            o.strip() for o in

            os.getenv("AI_LAB_API_ALLOWED_ORIGINS", "").split(",")

            if o.strip()

        ],
    )


def make_test_settings(
    data_dir: Path,
    *,
    enable_knowledge: bool = False,
    enable_scheduler: bool = False,
    enable_coordination: bool = False,
    enable_reminders: bool = False,
    enable_daily_review: bool = True,
    timezone_name: str = "Asia/Shanghai",
    scheduler_tick_interval: float = 1.0,
) -> SystemSettings:
    """Build isolated settings that never touch the user's runtime data.

    API auth is disabled by default so existing tests can call the API directly.
    Auth-specific tests should enable it explicitly.
    """

    return SystemSettings(
        environment="test",
        provider_mode="test",
        data_dir=data_dir,
        sqlite_dir=data_dir / "sqlite",
        enable_knowledge=enable_knowledge,
        enable_scheduler=enable_scheduler,
        enable_coordination=enable_coordination,
        enable_reminders=enable_reminders,
        enable_daily_review=enable_daily_review,
        timezone_name=timezone_name,
        scheduler_tick_interval=scheduler_tick_interval,
        enable_api_auth=False,
        workspace_tenant_id="default",
        workspace_id="default",
        workspace_namespace="default",
        workspace_session_id="test",
        workspace_agent_id="test",
    )
