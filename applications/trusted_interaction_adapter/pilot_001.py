"""PILOT-001 Phase-0 static binding and preview-only policy authorities."""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NoReturn
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from applications.trusted_interaction_adapter.models import (
    ResolvedOperationPlan,
    ResolvedShellContext,
    ShellAssertion,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.user_tasks.models import UserTask, UserTaskPriority
from core.workspace.models import WorkspaceKey

PILOT_MODE = "phase0_preview_only"
P1A_PILOT_MODE = "internal_trusted_ingress_confirmation"
EXPECTED_CHANNEL = "wecom"
BINDING_TYPE = "PILOT_GRADE_LOCAL_SINGLE_OWNER_BINDING"
ALLOWED_OPERATION = "user_task.create"
POLICY_REFERENCE = "pilot-001/user-task-create/v1"
FIXED_SOURCE = "wecom_owner_pilot"
RISK_LEVEL = "medium"
PREVIEW_TTL_SECONDS = 900

_CONFIG_KEYS = {
    "mode": "AI_LAB_PILOT_001_MODE",
    "expected_shell": "AI_LAB_PILOT_001_EXPECTED_SHELL",
    "expected_channel": "AI_LAB_PILOT_001_EXPECTED_CHANNEL",
    "owner_channel_identity": "AI_LAB_PILOT_001_OWNER_CHANNEL_IDENTITY",
    "actor_id": "AI_LAB_PILOT_001_ACTOR_ID",
    "tenant_id": "AI_LAB_PILOT_001_TENANT_ID",
    "workspace_id": "AI_LAB_PILOT_001_WORKSPACE_ID",
    "namespace": "AI_LAB_PILOT_001_NAMESPACE",
}
_PARAMETER_FIELDS = frozenset(
    {"title", "description", "priority", "due_at", "timezone"}
)


def _fail(
    *,
    code: str,
    operation: str,
    message: str,
    trace_id: str = "",
    category: ErrorCategory = ErrorCategory.PERMISSION_DENIED,
) -> NoReturn:
    raise FailureException(
        FailureInfo(
            code=code,
            category=category,
            message=message,
            component="pilot_001_authority",
            operation=operation,
            retryable=False,
            trace_id=trace_id,
        )
    )


@dataclass(frozen=True, repr=False)
class Pilot001AuthorityConfig:
    """Local-only single-Owner binding facts; raw identity is never projected."""

    mode: str
    expected_shell: str
    expected_channel: str
    owner_channel_identity: str = field(repr=False)
    actor_id: str
    tenant_id: str
    workspace_id: str
    namespace: str

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> Pilot001AuthorityConfig:
        source = os.environ if environ is None else environ
        values = {
            field_name: str(source.get(variable_name, "")).strip()
            for field_name, variable_name in _CONFIG_KEYS.items()
        }
        missing = [
            variable_name
            for field_name, variable_name in _CONFIG_KEYS.items()
            if not values[field_name]
        ]
        if missing:
            _fail(
                code="pilot_001.binding_config_missing",
                operation="load_binding_config",
                message="Pilot binding configuration is incomplete: "
                + ", ".join(missing),
            )
        if values["mode"] not in {PILOT_MODE, P1A_PILOT_MODE}:
            _fail(
                code="pilot_001.mode_denied",
                operation="load_binding_config",
                message="Pilot mode is not authorized for a bounded PILOT-001 composition",
            )
        if values["expected_channel"].casefold() != EXPECTED_CHANNEL:
            _fail(
                code="pilot_001.channel_config_denied",
                operation="load_binding_config",
                message="Pilot channel must be the configured WeCom channel",
            )
        if hmac.compare_digest(
            values["owner_channel_identity"], values["actor_id"]
        ):
            _fail(
                code="pilot_001.raw_owner_actor_denied",
                operation="load_binding_config",
                message="Canonical actor must not persist the raw channel identity",
            )
        return cls(**values)

    @property
    def binding_evidence_id(self) -> str:
        material = (
            f"PILOT-001\x1f{self.expected_shell}\x1f{self.expected_channel}\x1f"
            f"{self.owner_channel_identity}\x1f{self.actor_id}\x1f{self.tenant_id}\x1f"
            f"{self.workspace_id}\x1f{self.namespace}"
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        return f"pilot001_binding_{digest}"

    def workspace(self, *, trace_id: str = "") -> WorkspaceKey:
        return WorkspaceKey(
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            namespace=self.namespace,
            user_id=self.actor_id,
            trace_id=trace_id,
        )


class Pilot001OwnerBindingResolver:
    """Match untrusted assertions against one explicit local Pilot binding."""

    def __init__(self, config: Pilot001AuthorityConfig) -> None:
        self._config = config

    async def resolve(self, assertion: ShellAssertion) -> ResolvedShellContext:
        trace_id = assertion.correlation.get("trace_id", "")
        matches = (
            assertion.shell.strip().casefold()
            == self._config.expected_shell.casefold()
            and assertion.channel.strip().casefold()
            == self._config.expected_channel.casefold()
            and hmac.compare_digest(
                assertion.channel_identity.strip(),
                self._config.owner_channel_identity,
            )
        )
        if not matches:
            _fail(
                code="pilot_001.binding_denied",
                operation="identity_binding",
                message="Shell assertion does not match the local single-Owner Pilot binding",
                trace_id=trace_id,
            )
        return ResolvedShellContext(
            workspace=self._config.workspace(trace_id=trace_id),
            actor_id=self._config.actor_id,
            binding_type=BINDING_TYPE,
            binding_evidence_id=self._config.binding_evidence_id,
        )


class Pilot001OperationPolicyResolver:
    """Authorize one strict UserTask Preview policy without business execution."""

    async def resolve(
        self,
        *,
        context: ResolvedShellContext,
        requested_operation: str,
        parameters: dict[str, Any],
        trace_id: str,
    ) -> ResolvedOperationPlan:
        if requested_operation.strip() != ALLOWED_OPERATION:
            _fail(
                code="pilot_001.operation_denied",
                operation="operation_policy",
                message="Requested operation is outside the PILOT-001 allowlist",
                trace_id=trace_id,
            )
        supplied = frozenset(parameters)
        if supplied - _PARAMETER_FIELDS:
            _fail(
                code="pilot_001.authority_field_denied",
                operation="operation_policy",
                message="Pilot parameters contain an unauthorized field",
                trace_id=trace_id,
            )
        if _PARAMETER_FIELDS - supplied:
            _fail(
                code="pilot_001.parameters_incomplete",
                operation="operation_policy",
                message="Pilot preview requires all strict UserTask fields",
                trace_id=trace_id,
                category=ErrorCategory.VALIDATION,
            )

        title = parameters["title"]
        description = parameters["description"]
        priority = parameters["priority"]
        due_at = parameters["due_at"]
        timezone_name = parameters["timezone"]
        if not all(
            isinstance(value, str)
            for value in (title, description, priority, due_at, timezone_name)
        ):
            _fail(
                code="pilot_001.parameters_invalid",
                operation="operation_policy",
                message="Pilot preview fields must use their canonical string forms",
                trace_id=trace_id,
                category=ErrorCategory.VALIDATION,
            )

        try:
            ZoneInfo(timezone_name.strip())
            parsed_due_at = datetime.fromisoformat(due_at.strip())
            if parsed_due_at.tzinfo is None or parsed_due_at.utcoffset() is None:
                raise ValueError("due_at must include timezone information")
            task = UserTask(
                title=title,
                description=description,
                priority=UserTaskPriority(priority.strip().lower()),
                due_at=parsed_due_at,
                timezone=timezone_name,
                source=FIXED_SOURCE,
            )
        except (ValidationError, ValueError, ZoneInfoNotFoundError):
            _fail(
                code="pilot_001.parameters_invalid",
                operation="operation_policy",
                message="Pilot preview parameters violate canonical UserTask validation",
                trace_id=trace_id,
                category=ErrorCategory.VALIDATION,
            )

        normalized = {
            "title": task.title,
            "description": task.description,
            "priority": task.priority.value,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "timezone": task.timezone,
            "source": FIXED_SOURCE,
        }
        return ResolvedOperationPlan(
            canonical_operation=ALLOWED_OPERATION,
            policy_reference=POLICY_REFERENCE,
            risk_level=RISK_LEVEL,
            normalized_parameters=normalized,
            mutation_summary=f"创建 UserTask：{task.title}",
            safe_summary=f"PILOT-001 任务预览：{task.title}",
            expected_external_effects=(),
            requires_confirmation=True,
            requires_approval=False,
            canonical_commit_required=True,
            preview_ttl_seconds=PREVIEW_TTL_SECONDS,
        )
