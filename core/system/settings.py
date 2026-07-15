"""集中、不可变的系统设置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
    enable_reminders: bool = False
    enable_api: bool = False

    enable_api_auth: bool = True

    api_token: str = ""

    api_allowed_origins: list[str] = ()

    def __post_init__(self) -> None:
        mode = self.provider_mode.lower().strip()
        if mode not in {"real", "mock", "test", "invalid"}:
            raise ValueError(f"Unsupported provider mode: {self.provider_mode}")
        object.__setattr__(self, "provider_mode", mode)
        object.__setattr__(self, "data_dir", Path(self.data_dir).resolve())
        object.__setattr__(self, "sqlite_dir", Path(self.sqlite_dir).resolve())
        if self.chroma_dir is not None:
            object.__setattr__(self, "chroma_dir", Path(self.chroma_dir).resolve())


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
        enable_reminders=_as_bool(os.getenv("AI_LAB_ENABLE_REMINDERS"), False),
        enable_api=_as_bool(os.getenv("AI_LAB_ENABLE_API"), False),

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
        enable_api_auth=False,
    )
