"""SQLite adapter for Work Logs stored in the existing episodic table."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from core.database.connection import transaction
from core.database.manager import DatabaseManager
from core.work_log.errors import (
    WorkLogConflictError,
    WorkLogLegacyProjectionError,
    WorkLogNotFoundError,
    WorkLogRepositoryError,
    WorkLogWorkspaceMismatchError,
)
from core.work_log.models import (
    CANONICAL_ID_PATTERN,
    INBOX_ALIAS_PATTERN,
    LEGACY_ID_PATTERN,
    WorkLogContextRef,
    WorkLogPage,
    WorkLogQuery,
    WorkLogRecord,
    WorkLogSource,
    WorkLogStatus,
    canonical_workspace,
)
from core.workspace.models import WorkspaceKey


class SQLiteWorkLogRepository:
    """Borrow the DatabaseManager-owned episodic connection for every operation."""

    LOGICAL_NAME = "episodic"
    TABLE = "episodic_memories"
    IMPORTANCE = 0.6

    def __init__(
        self,
        database_manager: DatabaseManager | None = None,
        db_path: str | Path = "episodic.db",
        *,
        timezone_name: str,
    ) -> None:
        self._owns_manager = database_manager is None
        self._manager = database_manager or DatabaseManager(Path(db_path).parent)
        self._path = self._manager.bind_path(self.LOGICAL_NAME, db_path)
        self._timezone_name = self._valid_zone(timezone_name).key
        self._initialized = False

    async def initialize(self) -> None:
        """Verify the existing Episodic Store schema without mutating it."""

        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                row = conn.execute(
                    "SELECT type FROM sqlite_master WHERE name=?",
                    (self.TABLE,),
                ).fetchone()
                if row is None or row["type"] != "table":
                    raise RuntimeError("episodic_memories table is not initialized")
            self._initialized = True
        except Exception as exc:
            raise WorkLogRepositoryError(
                "Work Log repository initialization failed"
            ) from exc

    async def close(self) -> None:
        """Close only a standalone manager; borrowed managers keep ownership."""

        if self._owns_manager:
            self._manager.close_all()
        self._initialized = False

    async def health_check(self) -> dict[str, object]:
        if not self._initialized:
            return {"status": "not_initialized"}
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                conn.execute(f"SELECT 1 FROM {self.TABLE} LIMIT 1")
            return {"status": "healthy"}
        except sqlite3.Error:
            return {"status": "failed"}

    async def create(self, record: WorkLogRecord) -> WorkLogRecord:
        if record.schema_version != 1 or not CANONICAL_ID_PATTERN.fullmatch(record.id):
            raise WorkLogConflictError("only canonical Work Logs can be created")
        await self._insert(record, record.id)
        row = self._row_by_storage_id(record.id)
        if row is None:
            raise WorkLogRepositoryError("canonical Work Log was not persisted")
        return self._project_row(row)

    async def create_from_inbox(
        self, record: WorkLogRecord, reserved_id: str
    ) -> WorkLogRecord:
        if record.source != WorkLogSource.INBOX or not record.inbox_item_id:
            raise WorkLogConflictError("Inbox source evidence is required")
        if not (
            CANONICAL_ID_PATTERN.fullmatch(reserved_id)
            or INBOX_ALIAS_PATTERN.fullmatch(reserved_id)
        ):
            raise WorkLogConflictError("reserved Inbox Work Log id is invalid")
        await self._insert(record, reserved_id)
        if INBOX_ALIAS_PATTERN.fullmatch(reserved_id):
            projected = self._project_inbox_alias(
                self._row_by_storage_id(reserved_id), reserved_id
            )
            if projected is None:
                raise WorkLogRepositoryError("reserved Inbox row was not persisted")
            return projected
        row = self._row_by_storage_id(reserved_id)
        if row is None:
            raise WorkLogRepositoryError("Inbox Work Log was not persisted")
        return self._project_row(row)

    async def _insert(self, record: WorkLogRecord, storage_id: str) -> None:
        content = self._canonical_content(record)
        outer_metadata = {
            "source": record.source.value,
            "workspace_id": record.workspace_key.workspace_id,
        }
        if record.inbox_item_id:
            outer_metadata["inbox_item_id"] = record.inbox_item_id
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                with transaction(conn):
                    conn.execute(
                        f"""
                        INSERT INTO {self.TABLE}
                        (id, memory_type, content, importance, embedding,
                         timestamp, ttl, metadata)
                        VALUES (?, 'episodic', ?, ?, NULL, ?, NULL, ?)
                        """,
                        (
                            storage_id,
                            json.dumps(
                                content,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            self.IMPORTANCE,
                            record.created_at.isoformat(),
                            json.dumps(
                                outer_metadata,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            raise WorkLogConflictError("Work Log id already exists") from exc
        except sqlite3.Error as exc:
            raise WorkLogRepositoryError("Work Log insert failed") from exc

    async def get(
        self, workspace_key: WorkspaceKey, work_log_id: str
    ) -> WorkLogRecord:
        workspace = canonical_workspace(workspace_key)
        try:
            if CANONICAL_ID_PATTERN.fullmatch(work_log_id):
                row = self._row_by_storage_id(work_log_id)
                record = self._project_row(row) if row is not None else None
            elif INBOX_ALIAS_PATTERN.fullmatch(work_log_id):
                row = self._row_by_storage_id(work_log_id)
                record = self._project_inbox_alias(row, work_log_id)
            elif LEGACY_ID_PATTERN.fullmatch(work_log_id):
                record = self._find_legacy_projection(work_log_id)
            else:
                record = None
        except (WorkLogNotFoundError, WorkLogLegacyProjectionError):
            raise
        except sqlite3.Error as exc:
            raise WorkLogRepositoryError("Work Log lookup failed") from exc
        if record is None:
            raise WorkLogNotFoundError("Work Log was not found")
        if self._workspace_identity(record.workspace_key) != self._workspace_identity(
            workspace
        ):
            raise WorkLogWorkspaceMismatchError(
                "Work Log belongs to another workspace"
            )
        return record

    async def list(
        self, workspace_key: WorkspaceKey, query: WorkLogQuery
    ) -> WorkLogPage:
        workspace = canonical_workspace(workspace_key)
        try:
            with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
                sql, params = self._visible_rows_sql(workspace)
                rows = conn.execute(sql, params).fetchall()
            records = [self._project_row(row) for row in rows]
            visible = [record for record in records if self._matches(record, query)]
            visible.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
            total_count = len(visible)
            items = tuple(visible[query.offset : query.offset + query.limit])
            return WorkLogPage(
                items=items,
                count=len(items),
                limit=query.limit,
                offset=query.offset,
                has_more=query.offset + len(items) < total_count,
                total_count=total_count,
            )
        except WorkLogLegacyProjectionError:
            raise
        except sqlite3.Error as exc:
            raise WorkLogRepositoryError("Work Log query failed") from exc

    def _row_by_storage_id(self, storage_id: str) -> sqlite3.Row | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            return conn.execute(
                f"SELECT * FROM {self.TABLE} WHERE id=? AND memory_type='episodic'",
                (storage_id,),
            ).fetchone()

    def _find_legacy_projection(self, canonical_id: str) -> WorkLogRecord | None:
        with self._manager.lease(self.LOGICAL_NAME, self._path) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM {self.TABLE}
                WHERE memory_type='episodic'
                  AND json_valid(content)
                  AND json_type(content)='object'
                  AND json_extract(content, '$.type')='work_log'
                """
            ).fetchall()
        for row in rows:
            if self._legacy_id(row["id"]) == canonical_id:
                return self._project_row(row)
        return None

    def _project_inbox_alias(
        self, row: sqlite3.Row | None, alias: str
    ) -> WorkLogRecord | None:
        if row is None:
            return None
        content = self._content_or_none(row)
        if not isinstance(content, dict) or content.get("type") != "work_log":
            raise WorkLogNotFoundError("Inbox alias is not a Work Log")
        outer = self._metadata(row)
        source = self._string(content.get("source")) or self._string(
            outer.get("source")
        )
        inbox_item_id = self._string(content.get("inbox_item_id")) or self._string(
            outer.get("inbox_item_id")
        )
        if source != WorkLogSource.INBOX.value or not inbox_item_id:
            raise WorkLogNotFoundError("Inbox alias has no consistent Inbox source")
        expected = (
            "inbox_wl_"
            + hashlib.sha256(
                f"inbox_wl|{inbox_item_id}".encode("utf-8")
            ).hexdigest()[:24]
        )
        if expected != alias:
            raise WorkLogNotFoundError("Inbox alias source evidence does not match")
        return self._project_legacy(row, content, outer)

    def _project_row(self, row: sqlite3.Row) -> WorkLogRecord:
        content = self._content_or_none(row)
        if not isinstance(content, dict) or content.get("type") != "work_log":
            raise WorkLogNotFoundError("row is not a Work Log")
        if CANONICAL_ID_PATTERN.fullmatch(row["id"]):
            return self._decode_canonical(row, content)
        return self._project_legacy(row, content, self._metadata(row))

    def _decode_canonical(
        self, row: sqlite3.Row, content: dict[str, Any]
    ) -> WorkLogRecord:
        digest = self._row_digest(row["id"])
        try:
            workspace = content["metadata"]
            if not isinstance(workspace, dict):
                raise ValueError("canonical workspace is invalid")
            return WorkLogRecord(
                id=row["id"],
                workspace_key=WorkspaceKey(
                    tenant_id=workspace["tenant_id"],
                    workspace_id=workspace["workspace_id"],
                    namespace=workspace["namespace"],
                    user_id="",
                    session_id="",
                    trace_id="",
                ),
                occurred_at=content["occurred_at"],
                timezone=content["timezone"],
                subject=content["subject"],
                raw_text=content["raw_text"],
                target=content.get("target"),
                status=content["status"],
                tags=content.get("tags", []),
                source=content["source"],
                context_refs=content.get("context_refs", []),
                created_at=row["timestamp"],
                schema_version=content["schema_version"],
                inbox_item_id=content.get("inbox_item_id"),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise WorkLogLegacyProjectionError(
                "Canonical Work Log row is malformed",
                row_digest=digest,
                field="canonical_row",
            ) from exc

    def _project_legacy(
        self,
        row: sqlite3.Row,
        content: dict[str, Any],
        outer: dict[str, Any],
    ) -> WorkLogRecord:
        row_id = row["id"]
        digest = self._row_digest(row_id)
        if not isinstance(row_id, str) or not row_id:
            self._projection_failure(digest, "id")

        notes: list[str] = []
        workspace = self._legacy_workspace(content)
        zone = self._legacy_zone(content, notes)
        occurred_at = self._legacy_occurred_at(content, row, zone, digest, notes)
        created_at = self._legacy_created_at(row, zone, digest)
        subject = self._legacy_subject(content, digest)
        raw_text = self._legacy_raw_text(content, subject)
        status, legacy_raw_status = self._legacy_status(content.get("status"))
        tags = self._legacy_tags(content.get("tags"), notes)
        target = self._legacy_target(content.get("target"))
        source, legacy_raw_source = self._legacy_source(
            content, outer, row_id, notes
        )
        refs = self._legacy_refs(content.get("context_refs"), notes)
        inbox_item_id = self._string(content.get("inbox_item_id")) or self._string(
            outer.get("inbox_item_id")
        )
        try:
            return WorkLogRecord(
                id=self._legacy_id(row_id),
                workspace_key=workspace,
                occurred_at=occurred_at,
                timezone=zone.key,
                subject=subject,
                raw_text=raw_text,
                target=target,
                status=status,
                tags=tags,
                source=source,
                context_refs=refs,
                created_at=created_at,
                legacy_memory_id=row_id,
                legacy_raw_status=legacy_raw_status,
                legacy_raw_source=legacy_raw_source,
                legacy_projection_notes=tuple(notes),
                schema_version=0,
                inbox_item_id=inbox_item_id,
            )
        except (ValueError, ValidationError) as exc:
            raise WorkLogLegacyProjectionError(
                "Legacy Work Log projection failed",
                row_digest=digest,
                field="record",
            ) from exc

    @staticmethod
    def _canonical_content(record: WorkLogRecord) -> dict[str, Any]:
        content: dict[str, Any] = {
            "type": "work_log",
            "schema_version": 1,
            "metadata": {
                "tenant_id": record.workspace_key.tenant_id,
                "workspace_id": record.workspace_key.workspace_id,
                "namespace": record.workspace_key.namespace,
            },
            "occurred_at": record.occurred_at.isoformat(),
            "timezone": record.timezone,
            "subject": record.subject,
            "raw_text": record.raw_text,
            "target": record.target,
            "status": record.status.value,
            "tags": list(record.tags),
            "source": record.source.value,
            "context_refs": [
                item.model_dump(mode="json") for item in record.context_refs
            ],
        }
        if record.inbox_item_id:
            content["inbox_item_id"] = record.inbox_item_id
        return content

    def _visible_rows_sql(
        self, workspace: WorkspaceKey
    ) -> tuple[str, tuple[object, ...]]:
        complete = """
            json_type(content, '$.metadata.tenant_id')='text'
            AND trim(json_extract(content, '$.metadata.tenant_id'))<>''
            AND json_type(content, '$.metadata.workspace_id')='text'
            AND trim(json_extract(content, '$.metadata.workspace_id'))<>''
            AND json_type(content, '$.metadata.namespace')='text'
            AND trim(json_extract(content, '$.metadata.namespace'))<>''
        """
        identity = """
            json_extract(content, '$.metadata.tenant_id')=?
            AND json_extract(content, '$.metadata.workspace_id')=?
            AND json_extract(content, '$.metadata.namespace')=?
        """
        if self._workspace_identity(workspace) == ("default", "default", "default"):
            scope = (
                f"((({complete}) AND ({identity})) "
                f"OR (({complete}) IS NOT TRUE))"
            )
        else:
            scope = f"(({complete}) AND ({identity}))"
        sql = f"""
            SELECT * FROM {self.TABLE}
            WHERE memory_type='episodic'
              AND json_valid(content)
              AND json_type(content)='object'
              AND json_extract(content, '$.type')='work_log'
              AND {scope}
        """
        return sql, self._workspace_identity(workspace)

    @staticmethod
    def _matches(record: WorkLogRecord, query: WorkLogQuery) -> bool:
        if query.date_from is not None and record.occurred_at < query.date_from:
            return False
        if query.date_to is not None and record.occurred_at >= query.date_to:
            return False
        if query.target is not None and (record.target or "").casefold() != (
            query.target.casefold()
        ):
            return False
        if query.tags:
            available = {value.casefold() for value in record.tags}
            if not all(value.casefold() in available for value in query.tags):
                return False
        if query.status is not None and record.status != query.status:
            return False
        if query.text is not None:
            needle = query.text.casefold()
            haystack = "\n".join(
                (record.subject, record.raw_text, record.target or "")
            ).casefold()
            if needle not in haystack:
                return False
        if query.context_ref is not None and not any(
            ref.target_id == query.context_ref for ref in record.context_refs
        ):
            return False
        return True

    def _legacy_workspace(self, content: dict[str, Any]) -> WorkspaceKey:
        metadata = content.get("metadata")
        if isinstance(metadata, dict):
            values = tuple(
                self._string(metadata.get(key))
                for key in ("tenant_id", "workspace_id", "namespace")
            )
            if all(values):
                return WorkspaceKey(
                    tenant_id=values[0],
                    workspace_id=values[1],
                    namespace=values[2],
                    user_id="",
                    session_id="",
                    trace_id="",
                )
        return WorkspaceKey(
            tenant_id="default",
            workspace_id="default",
            namespace="default",
            user_id="",
            session_id="",
            trace_id="",
        )

    def _legacy_zone(
        self, content: dict[str, Any], notes: list[str]
    ) -> ZoneInfo:
        raw = self._string(content.get("timezone"))
        if raw:
            try:
                return self._valid_zone(raw)
            except ValueError:
                notes.append("invalid_timezone_fallback")
        return self._valid_zone(self._timezone_name)

    def _legacy_occurred_at(
        self,
        content: dict[str, Any],
        row: sqlite3.Row,
        zone: ZoneInfo,
        digest: str,
        notes: list[str],
    ) -> datetime:
        candidates = (
            ("content.occurred_at", content.get("occurred_at")),
            ("content.date", content.get("date")),
            ("timestamp", row["timestamp"]),
        )
        for field, value in candidates:
            parsed = self._parse_legacy_datetime(value, zone)
            if parsed is not None:
                if field != "content.occurred_at":
                    notes.append(f"occurred_at_from_{field.replace('.', '_')}")
                return parsed
        self._projection_failure(digest, "occurred_at")

    def _legacy_created_at(
        self, row: sqlite3.Row, zone: ZoneInfo, digest: str
    ) -> datetime:
        parsed = self._parse_legacy_datetime(row["timestamp"], zone)
        if parsed is None:
            self._projection_failure(digest, "created_at")
        return parsed

    @staticmethod
    def _legacy_subject(content: dict[str, Any], digest: str) -> str:
        for key, limit in (
            ("subject", 500),
            ("raw_text", 500),
            ("description", 500),
            ("title", 500),
        ):
            value = SQLiteWorkLogRepository._string(content.get(key))
            if value:
                return value[:limit]
        raise WorkLogLegacyProjectionError(
            "Legacy Work Log has no safe subject",
            row_digest=digest,
            field="subject",
        )

    @staticmethod
    def _legacy_raw_text(content: dict[str, Any], subject: str) -> str:
        for key in ("raw_text", "subject", "description"):
            value = SQLiteWorkLogRepository._string(content.get(key))
            if value:
                return value[:4_000]
        return subject

    @staticmethod
    def _legacy_status(value: Any) -> tuple[WorkLogStatus, str | None]:
        raw = SQLiteWorkLogRepository._string(value)
        if not raw:
            return WorkLogStatus.INFORMATIONAL, None
        normalized = raw.casefold()
        mapping = {
            "completed": WorkLogStatus.COMPLETED,
            "已完成": WorkLogStatus.COMPLETED,
            "完成": WorkLogStatus.COMPLETED,
            "done": WorkLogStatus.COMPLETED,
            "in_progress": WorkLogStatus.IN_PROGRESS,
            "进行中": WorkLogStatus.IN_PROGRESS,
            "正在进行": WorkLogStatus.IN_PROGRESS,
            "blocked": WorkLogStatus.BLOCKED,
            "阻塞": WorkLogStatus.BLOCKED,
            "卡住": WorkLogStatus.BLOCKED,
            "等待": WorkLogStatus.BLOCKED,
        }
        mapped = mapping.get(normalized)
        return (
            (mapped, None)
            if mapped is not None
            else (WorkLogStatus.INFORMATIONAL, raw)
        )

    @staticmethod
    def _legacy_tags(value: Any, notes: list[str]) -> tuple[str, ...]:
        if isinstance(value, str):
            values: list[Any] = [value]
        elif isinstance(value, list):
            values = value
        elif value is None:
            return ()
        else:
            notes.append("invalid_tags_ignored")
            return ()
        result: list[str] = []
        seen: set[str] = set()
        for candidate in values:
            item = str(candidate).strip()[:64]
            if not item or item.casefold() in seen:
                continue
            seen.add(item.casefold())
            result.append(item)
            if len(result) == 20:
                break
        return tuple(result)

    @staticmethod
    def _legacy_target(value: Any) -> str | None:
        return value.strip()[:200] or None if isinstance(value, str) else None

    def _legacy_source(
        self,
        content: dict[str, Any],
        outer: dict[str, Any],
        row_id: str,
        notes: list[str],
    ) -> tuple[WorkLogSource, str | None]:
        raw = self._string(content.get("source")) or self._string(outer.get("source"))
        if raw:
            try:
                return WorkLogSource(raw.casefold()), None
            except ValueError:
                notes.append("unknown_source_mapped_to_legacy")
                return WorkLogSource.LEGACY, raw
        inbox_item_id = self._string(content.get("inbox_item_id")) or self._string(
            outer.get("inbox_item_id")
        )
        if INBOX_ALIAS_PATTERN.fullmatch(row_id) and inbox_item_id:
            return WorkLogSource.INBOX, None
        return WorkLogSource.LEGACY, None

    @staticmethod
    def _legacy_refs(
        value: Any, notes: list[str]
    ) -> tuple[WorkLogContextRef, ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            notes.append("invalid_context_refs_ignored")
            return ()
        result: list[WorkLogContextRef] = []
        seen: set[tuple[str, str]] = set()
        for candidate in value:
            try:
                ref = WorkLogContextRef.model_validate(candidate)
            except (ValidationError, TypeError, ValueError):
                notes.append("invalid_context_ref_ignored")
                continue
            identity = (ref.kind.value, ref.target_id)
            if identity in seen:
                notes.append("duplicate_context_ref_ignored")
                continue
            seen.add(identity)
            result.append(ref)
            if len(result) == 20:
                break
        return tuple(result)

    @staticmethod
    def _parse_legacy_datetime(value: Any, zone: ZoneInfo) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, time.min)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                if len(raw) == 10:
                    parsed = datetime.combine(date.fromisoformat(raw), time.min)
                else:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _content_or_none(row: sqlite3.Row) -> Any:
        try:
            return json.loads(row["content"])
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _metadata(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["metadata"] or "{}")
            return value if isinstance(value, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def _workspace_identity(workspace_key: WorkspaceKey) -> tuple[str, str, str]:
        workspace = canonical_workspace(workspace_key)
        return workspace.tenant_id, workspace.workspace_id, workspace.namespace

    @staticmethod
    def _legacy_id(row_id: str) -> str:
        return f"wl_legacy_{hashlib.sha256(row_id.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _row_digest(row_id: Any) -> str:
        return hashlib.sha256(str(row_id).encode("utf-8")).hexdigest()

    @staticmethod
    def _string(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _valid_zone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("invalid IANA timezone") from exc

    @staticmethod
    def _projection_failure(digest: str, field: str):
        raise WorkLogLegacyProjectionError(
            "Legacy Work Log projection failed",
            row_digest=digest,
            field=field,
        )
