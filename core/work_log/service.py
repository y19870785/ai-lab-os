"""Single application boundary for Work Log writes and queries."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.work_log.errors import (
    WorkLogConflictError,
    WorkLogIdInvalidError,
    WorkLogLegacyProjectionError,
    WorkLogNotFoundError,
    WorkLogRepositoryError,
    WorkLogWorkspaceMismatchError,
)
from core.work_log.models import (
    CANONICAL_ID_PATTERN,
    INBOX_ALIAS_PATTERN,
    LEGACY_ID_PATTERN,
    WorkLogCreateCommand,
    WorkLogPage,
    WorkLogQuery,
    WorkLogRecord,
    WorkLogSource,
    canonical_workspace,
)
from core.work_log.repository import WorkLogRepository
from core.workspace.models import WorkspaceKey


class WorkLogService:
    """Validate Work Log contracts and translate adapter failures once."""

    COMPONENT = "work_log"
    _MAX_ID_ATTEMPTS = 5

    def __init__(
        self,
        repository: WorkLogRepository,
        *,
        clock: Clock,
        timezone_name: str = "UTC",
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._timezone_name = self._validate_timezone(timezone_name)

    async def initialize(self) -> None:
        try:
            await self._repository.initialize()
        except WorkLogRepositoryError as exc:
            self._raise_repository("initialize", exc, trace_id="")

    async def close(self) -> None:
        await self._repository.close()

    async def health_check(self) -> dict[str, object]:
        check = getattr(self._repository, "health_check", None)
        return await check() if check is not None else {"status": "healthy"}

    async def create(
        self,
        *,
        workspace_key: WorkspaceKey,
        command: WorkLogCreateCommand,
    ) -> WorkLogRecord:
        workspace = canonical_workspace(workspace_key)
        now = self._clock.now().astimezone(timezone.utc)
        zone = command.timezone or self._timezone_name
        record_args = {
            "workspace_key": workspace,
            "occurred_at": command.occurred_at or now,
            "timezone": zone,
            "subject": command.subject,
            "raw_text": command.raw_text,
            "target": command.target,
            "status": command.status,
            "tags": command.tags,
            "source": command.source,
            "context_refs": command.context_refs,
            "created_at": now,
            "schema_version": 1,
        }
        for _ in range(self._MAX_ID_ATTEMPTS):
            record = WorkLogRecord(id=f"wl_{uuid.uuid4().hex}", **record_args)
            try:
                return await self._repository.create(record)
            except WorkLogConflictError:
                continue
            except WorkLogRepositoryError as exc:
                self._raise_repository(
                    "create", exc, trace_id=workspace.trace_id
                )
        self._raise(
            "work_log.repository_failed",
            ErrorCategory.PERSISTENCE_FAILURE,
            "create",
            trace_id=workspace.trace_id,
            retryable=True,
            cause_type=WorkLogConflictError.__name__,
        )

    async def create_from_inbox(
        self,
        *,
        workspace_key: WorkspaceKey,
        inbox_item_id: str,
        subject: str,
        raw_text: str,
        reserved_id: str | None = None,
    ) -> WorkLogRecord:
        workspace = canonical_workspace(workspace_key)
        inbox_item_id = inbox_item_id.strip()
        if not inbox_item_id.startswith("inbox_"):
            self._raise(
                "work_log.context_ref_invalid",
                ErrorCategory.VALIDATION,
                "create_from_inbox",
                trace_id=workspace.trace_id,
            )
        generated_id = (
            "wl_"
            + hashlib.sha256(
                f"work_log|{inbox_item_id}".encode("utf-8")
            ).hexdigest()[:32]
        )
        target_id = reserved_id or generated_id
        if not (
            CANONICAL_ID_PATTERN.fullmatch(target_id)
            or INBOX_ALIAS_PATTERN.fullmatch(target_id)
        ):
            self._raise(
                "work_log.id_invalid",
                ErrorCategory.VALIDATION,
                "create_from_inbox",
                trace_id=workspace.trace_id,
            )
        now = self._clock.now().astimezone(timezone.utc)
        try:
            record = WorkLogRecord(
                id=generated_id,
                workspace_key=workspace,
                occurred_at=now,
                timezone=self._timezone_name,
                subject=subject,
                raw_text=raw_text,
                status="completed",
                tags=("inbox",),
                source=WorkLogSource.INBOX,
                created_at=now,
                schema_version=1,
                inbox_item_id=inbox_item_id,
            )
            return await self._repository.create_from_inbox(record, target_id)
        except WorkLogConflictError:
            return await self._recover_inbox_target(
                workspace, target_id, inbox_item_id
            )
        except (ValueError, ValidationError) as exc:
            self._raise_validation(
                exc, "create_from_inbox", trace_id=workspace.trace_id
            )
        except WorkLogRepositoryError as exc:
            self._raise_repository(
                "create_from_inbox", exc, trace_id=workspace.trace_id
            )

    async def get(
        self, *, workspace_key: WorkspaceKey, work_log_id: str
    ) -> WorkLogRecord:
        workspace = canonical_workspace(workspace_key)
        work_log_id = work_log_id.strip()
        if not (
            CANONICAL_ID_PATTERN.fullmatch(work_log_id)
            or LEGACY_ID_PATTERN.fullmatch(work_log_id)
            or INBOX_ALIAS_PATTERN.fullmatch(work_log_id)
        ):
            raise FailureException(
                self._failure(
                    "work_log.id_invalid",
                    ErrorCategory.VALIDATION,
                    "get",
                    trace_id=workspace.trace_id,
                    cause_type=WorkLogIdInvalidError.__name__,
                )
            )
        try:
            return await self._repository.get(workspace, work_log_id)
        except WorkLogNotFoundError as exc:
            self._raise_mapped(
                "work_log.not_found",
                ErrorCategory.NOT_FOUND,
                "get",
                exc,
                workspace.trace_id,
            )
        except WorkLogWorkspaceMismatchError as exc:
            self._raise_mapped(
                "work_log.workspace_mismatch",
                ErrorCategory.PERMISSION_DENIED,
                "get",
                exc,
                workspace.trace_id,
            )
        except WorkLogRepositoryError as exc:
            self._raise_repository("get", exc, trace_id=workspace.trace_id)

    async def list(
        self, *, workspace_key: WorkspaceKey, query: WorkLogQuery
    ) -> WorkLogPage:
        workspace = canonical_workspace(workspace_key)
        try:
            return await self._repository.list(workspace, query)
        except WorkLogLegacyProjectionError as exc:
            self._raise_repository("list", exc, trace_id=workspace.trace_id)
        except WorkLogRepositoryError as exc:
            self._raise_repository("list", exc, trace_id=workspace.trace_id)

    async def _recover_inbox_target(
        self,
        workspace: WorkspaceKey,
        target_id: str,
        inbox_item_id: str,
    ) -> WorkLogRecord:
        try:
            record = await self._repository.get(workspace, target_id)
        except (
            WorkLogNotFoundError,
            WorkLogWorkspaceMismatchError,
        ) as exc:
            self._raise_mapped(
                "work_log.repository_failed",
                ErrorCategory.CONFLICT,
                "create_from_inbox",
                exc,
                workspace.trace_id,
            )
        except WorkLogRepositoryError as exc:
            self._raise_repository(
                "create_from_inbox", exc, trace_id=workspace.trace_id
            )
        if (
            record.source != WorkLogSource.INBOX
            or record.inbox_item_id != inbox_item_id
        ):
            self._raise(
                "work_log.repository_failed",
                ErrorCategory.CONFLICT,
                "create_from_inbox",
                trace_id=workspace.trace_id,
                cause_type=WorkLogConflictError.__name__,
            )
        return record

    def _raise_validation(
        self, exc: Exception, operation: str, *, trace_id: str
    ) -> None:
        text = str(exc).casefold()
        if "subject" in text or "raw_text" in text:
            code = "work_log.subject_required"
        elif "timezone" in text:
            code = "work_log.timezone_invalid"
        elif "occurred_at" in text or "datetime" in text:
            code = "work_log.occurred_at_invalid"
        elif "context" in text:
            code = "work_log.context_ref_invalid"
        else:
            code = "work_log.query_invalid"
        self._raise_mapped(
            code, ErrorCategory.VALIDATION, operation, exc, trace_id
        )

    def _raise_repository(
        self, operation: str, exc: WorkLogRepositoryError, *, trace_id: str
    ) -> None:
        if isinstance(exc, WorkLogLegacyProjectionError):
            self._raise(
                "work_log.legacy_projection_failed",
                ErrorCategory.PERSISTENCE_FAILURE,
                operation,
                trace_id=trace_id,
                cause_type=exc.__class__.__name__,
                details={"row_digest": exc.row_digest, "field": exc.field},
            )
        self._raise_mapped(
            "work_log.repository_failed",
            ErrorCategory.PERSISTENCE_FAILURE,
            operation,
            exc,
            trace_id,
            retryable=True,
        )

    @staticmethod
    def _validate_timezone(value: str) -> str:
        try:
            return ZoneInfo(value).key
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("invalid Work Log timezone") from exc

    @classmethod
    def _failure(
        cls,
        code: str,
        category: ErrorCategory,
        operation: str,
        *,
        trace_id: str,
        cause_type: str = "",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> FailureInfo:
        messages = {
            "work_log.not_configured": "Work Log service is not configured",
            "work_log.not_found": "Work Log was not found",
            "work_log.workspace_mismatch": "Work Log belongs to another workspace",
            "work_log.id_invalid": "Work Log id is invalid",
            "work_log.subject_required": "Work Log subject is required",
            "work_log.occurred_at_invalid": "Work Log occurred_at is invalid",
            "work_log.timezone_invalid": "Work Log timezone is invalid",
            "work_log.query_invalid": "Work Log query is invalid",
            "work_log.limit_invalid": "Work Log query limit is invalid",
            "work_log.context_ref_invalid": "Work Log context reference is invalid",
            "work_log.repository_failed": "Work Log repository operation failed",
            "work_log.legacy_projection_failed": "Legacy Work Log projection failed",
        }
        return FailureInfo(
            code=code,
            category=category,
            message=messages[code],
            component=cls.COMPONENT,
            operation=operation,
            retryable=retryable,
            trace_id=trace_id,
            cause_type=cause_type,
            details=details or {},
        )

    @classmethod
    def _raise(
        cls,
        code: str,
        category: ErrorCategory,
        operation: str,
        *,
        trace_id: str,
        cause_type: str = "",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        raise FailureException(
            cls._failure(
                code,
                category,
                operation,
                trace_id=trace_id,
                cause_type=cause_type,
                details=details,
                retryable=retryable,
            )
        )

    @classmethod
    def _raise_mapped(
        cls,
        code: str,
        category: ErrorCategory,
        operation: str,
        exc: Exception,
        trace_id: str,
        *,
        retryable: bool = False,
    ) -> None:
        try:
            cls._raise(
                code,
                category,
                operation,
                trace_id=trace_id,
                cause_type=exc.__class__.__name__,
                retryable=retryable,
            )
        except FailureException as failure:
            raise failure from exc


class WorkLogUserErrorPresenter:
    """Localize only the human message while preserving failure semantics."""

    _MESSAGES = {
        "work_log.not_configured": "工作记录服务尚未配置。",
        "work_log.not_found": "未找到这条工作记录。",
        "work_log.workspace_mismatch": "这条工作记录不属于当前工作区。",
        "work_log.id_invalid": "工作记录 ID 格式无效。",
        "work_log.subject_required": "工作记录主题不能为空。",
        "work_log.occurred_at_invalid": "工作记录时间无效。",
        "work_log.timezone_invalid": "工作记录时区无效。",
        "work_log.query_invalid": "工作记录查询条件无效。",
        "work_log.limit_invalid": "工作记录查询数量无效。",
        "work_log.context_ref_invalid": "工作记录上下文引用无效。",
        "work_log.repository_failed": "工作记录暂时无法访问。",
        "work_log.legacy_projection_failed": "历史工作记录无法安全读取。",
    }

    @classmethod
    def present(cls, failure: FailureInfo) -> FailureInfo:
        message = cls._MESSAGES.get(failure.code)
        return (
            failure.model_copy(update={"message": message})
            if message is not None
            else failure
        )
