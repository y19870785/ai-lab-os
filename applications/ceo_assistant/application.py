"""CEO Assistant —— 超哥的个人工作总控助手。

AI-Lab 首个真实业务应用。支持：
- 工作记录 (Work Log)
- 待办任务 (Task)
- 决策记录 (Decision)
- 知识问答 (Knowledge QA)
- 每日简报 (Daily Brief)
- 多轮对话 (Multi-turn Session)
"""

from __future__ import annotations
import re
import time
import uuid
from datetime import datetime
from typing import Any

from applications.models import ApplicationInfo, ApplicationManifest, ApplicationRequest, ApplicationResponse
from applications.config import ApplicationConfig
from applications.ceo_assistant.intent import (
    IntentDecision,
    IntentEffect,
    decide_intent,
    extract_inbox_capture_content,
)
from applications.ceo_assistant.reminder_errors import ReminderUserErrorPresenter
from applications.ceo_assistant.waiting_for_errors import WaitingForUserErrorPresenter
from applications.ceo_assistant.waiting_for_intent import (
    extract_action_note,
    extract_waiting_for_capture_content,
    extract_waiting_for_id,
    parse_waiting_for_confirmation,
    parse_waiting_for_time,
)
from core.errors import (
    ErrorCategory,
    FailureException,
    FailureInfo,
    failure_from_exception,
)
from core.memory.models import MemoryQuery, MemoryType
from core.system.admission import WorkAdmission


class CEOAssistant:
    """CEO Assistant 应用实现。

    不直接访问 Provider、数据库或 Tool，
    全部通过 ApplicationRuntime 和底层 Manager 完成。
    """

    def __init__(
        self,
        memory_manager=None,
        knowledge_manager=None,
        llm_provider=None,
        embedding_provider=None,
        user_task_service=None,
        reminder_orchestrator=None,
        reminder_inbox=None,
        reminder_management=None,
        daily_agenda=None,
        inbox_service=None,
        waiting_for_service=None,
        task_intent_parser=None,
        clock=None,
        timezone_name: str = "UTC",
        config: ApplicationConfig | None = None,
        bus=None,
        *,
        admission: WorkAdmission,
    ):
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._llm = llm_provider
        self._embedding = embedding_provider
        self._user_tasks = user_task_service
        self._reminder_orchestrator = reminder_orchestrator
        self._reminder_inbox = reminder_inbox
        self._reminder_management = reminder_management
        self._daily_agenda = daily_agenda
        self._inbox = inbox_service
        self._waiting_for = waiting_for_service
        self._task_intent_parser = task_intent_parser
        self._clock = clock
        self._timezone_name = timezone_name
        self._config = config or ApplicationConfig()
        self._bus = bus
        self._admission = admission

        # 应用信息
        self.info = ApplicationInfo(
            name="ceo-assistant",
            version="0.32.0",
            description="CEO个人工作总控助手",
            entrypoint="applications.ceo_assistant.application:CEOAssistant",
        )
        self.manifest = ApplicationManifest(
            name="ceo-assistant",
            version="0.32.0",
            description="CEO个人工作总控助手",
            entrypoint="applications.ceo_assistant.application:CEOAssistant",
            required_agents=["default-agent"],
            required_providers=["openai", "chroma"],
            required_permissions=["memory:read", "memory:write", "knowledge:read", "knowledge:write"],
        )

    @property
    def daily_agenda(self):
        """The injected DailyAgendaService instance, or None."""
        return self._daily_agenda

    # ---- 意图识别 ----

    async def _detect_intent(self, user_input: str) -> IntentDecision:
        """Return the deterministic decision used by every CEO Assistant entrypoint."""
        return decide_intent(user_input)

    @staticmethod
    def _assert_effect_contract(decision: IntentDecision) -> None:
        allowed = {
            "reminder_list": {IntentEffect.READ},
            "reminder_detail": {IntentEffect.READ},
            "daily_agenda": {IntentEffect.READ},
            "inbox_capture": {IntentEffect.WRITE},
            "inbox_list": {IntentEffect.READ},
            "waiting_for_list": {IntentEffect.READ},
            "waiting_for_detail": {IntentEffect.READ},
            "waiting_for_history": {IntentEffect.READ},
            "waiting_for_capture": {IntentEffect.WRITE},
            "waiting_for_confirm": {IntentEffect.WRITE},
            "waiting_for_follow_up": {IntentEffect.WRITE},
            "waiting_for_snooze": {IntentEffect.WRITE},
            "waiting_for_resolve": {IntentEffect.WRITE},
            "waiting_for_cancel": {IntentEffect.WRITE},
            "waiting_for_reopen": {IntentEffect.WRITE},
            "reminder_cancel": {IntentEffect.WRITE},
            "reminder_reschedule": {IntentEffect.WRITE},
            "work_log": {IntentEffect.WRITE},
            "decision": {IntentEffect.WRITE},
            "brief": {IntentEffect.READ},
            "knowledge": {IntentEffect.READ},
            "task": {IntentEffect.READ, IntentEffect.WRITE},
            "chat": {IntentEffect.CHAT},
        }
        if decision.effect not in allowed.get(decision.intent, set()):
            raise RuntimeError("Intent effect contract is invalid")

    # ---- 主执行入口 ----

    async def run(self, request: ApplicationRequest) -> ApplicationResponse:
        """Execute a new request through the shared admission boundary."""
        with self._admission.admit():
            return await self._run_accepted(request)

    async def _run_accepted(self, request: ApplicationRequest) -> ApplicationResponse:
        """执行业务请求。"""
        t0 = time.time()

        try:
            decision = await self._detect_intent(request.user_input)
            self._assert_effect_contract(decision)
            mode = request.metadata.get("provider_mode", self._detect_mode())

            result = None
            if decision.intent == "inbox_capture":
                result = await self._handle_inbox_capture(request)
            elif decision.intent == "inbox_list":
                result = await self._handle_inbox_list(request)
            elif decision.intent == "waiting_for_capture":
                result = await self._handle_waiting_for_capture(request)
            elif decision.intent == "waiting_for_confirm":
                result = await self._handle_waiting_for_confirm(request)
            elif decision.intent == "waiting_for_list":
                result = await self._handle_waiting_for_list(request)
            elif decision.intent == "waiting_for_detail":
                result = await self._handle_waiting_for_detail(request)
            elif decision.intent == "waiting_for_history":
                result = await self._handle_waiting_for_history(request)
            elif decision.intent.startswith("waiting_for_"):
                result = await self._handle_waiting_for_lifecycle(
                    request, decision.intent
                )
            elif decision.intent == "work_log":
                result = await self._handle_work_log(request)
            elif decision.intent == "reminder_list":
                result = await self._handle_reminder_list(request)
            elif decision.intent == "reminder_detail":
                result = await self._handle_reminder_detail(request)
            elif decision.intent == "reminder_cancel":
                result = await self._handle_reminder_cancel(request)
            elif decision.intent == "reminder_reschedule":
                result = await self._handle_reminder_reschedule(request)
            elif decision.intent == "daily_agenda":
                result = await self._handle_daily_agenda(request)
            elif decision.intent == "task":
                result = await self._handle_task(request)
            elif decision.intent == "decision":
                result = await self._handle_decision(request)
            elif decision.intent == "knowledge":
                result = await self._handle_knowledge_qa(request)
            elif decision.intent == "brief":
                result = await self._handle_brief(request)
            else:
                result = await self._handle_chat(request)

            answer = result.get("answer", "")
            if mode == "mock" and not result.get("_deterministic", False):
                answer = f"[MOCK MODE] {answer}\n\n(Set OPENAI_API_KEY to use real LLM)"
            metadata = dict(result.get("metadata", {}))
            metadata.setdefault("intent", decision.intent)
            metadata.setdefault("effect", decision.effect.value)

            return ApplicationResponse(
                application_id=self.info.application_id,
                answer=answer,
                status=result.get("status", "ok"),
                citations=result.get("citations", []),
                usage=result.get("usage", {}),
                latency_ms=(time.time() - t0) * 1000,
                trace_id=request.workspace_key.trace_id,
                mode=mode,
                metadata=metadata,
            )
        except FailureException as exc:
            presented = WaitingForUserErrorPresenter.present(exc.failure)
            presented = ReminderUserErrorPresenter.present(presented)
            raise FailureException(presented) from exc
        except Exception as exc:
            failure = failure_from_exception(
                exc,
                component="application.ceo_assistant",
                operation="execute",
                trace_id=request.workspace_key.trace_id,
                code="application.ceo_assistant.execute_failed",
            )
            message = (
                "CEO Assistant dependency is not configured"
                if failure.category == ErrorCategory.NOT_CONFIGURED
                else "CEO Assistant request failed"
            )
            raise FailureException(failure.model_copy(update={"message": message})) from exc

    # ---- 1. 工作记录 ----

    async def _handle_inbox_capture(self, request: ApplicationRequest) -> dict[str, Any]:
        """Capture explicit input without creating a downstream business object."""

        if self._inbox is None:
            raise RuntimeError("Inbox service is not configured")
        content = extract_inbox_capture_content(request.user_input)
        if content is None:
            raise ValueError("Inbox capture content is empty")
        item = await self._inbox.capture(
            workspace_key=request.workspace_key,
            content=content,
            source="ceo_assistant",
            metadata={"intent": "inbox_capture"},
        )
        return {
            "answer": f"已放入收件箱：{item.content}",
            "status": "ok",
            "metadata": {"inbox_item": item.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_inbox_list(self, request: ApplicationRequest) -> dict[str, Any]:
        """List pending Inbox items without side effects."""

        if self._inbox is None:
            raise RuntimeError("Inbox service is not configured")
        page = await self._inbox.list(workspace_key=request.workspace_key, status="pending")
        if page.items:
            lines = ["待整理的收件箱记录："]
            lines.extend(f"- {item.id}: {item.content}" for item in page.items)
            answer = "\n".join(lines)
        else:
            answer = "收件箱中没有待整理记录。"
        return {
            "answer": answer,
            "status": "ok",
            "metadata": {"inbox": page.model_dump(mode="json")},
            "_deterministic": True,
        }

    def _require_waiting_for(self, request: ApplicationRequest):
        if self._waiting_for is None:
            raise FailureException(FailureInfo(
                code="inbox.waiting_for.unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Waiting-For service is unavailable",
                component="waiting_for",
                operation="ceo_assistant",
                retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        return self._waiting_for

    @staticmethod
    def _waiting_for_line(item) -> str:
        time_value = item.next_review_at or item.expected_by
        return (
            f"{item.id} | {item.subject} | 等待：{item.waiting_on} | "
            f"状态：{item.status.value} | 时间："
            f"{time_value.isoformat() if time_value else '未设置'}"
        )

    async def _waiting_for_candidates(self, request: ApplicationRequest) -> dict[str, Any]:
        page = await self._require_waiting_for(request).list(
            workspace_key=request.workspace_key, view="open", limit=50
        )
        if page.items:
            lines = ["请使用明确的 wf_ ID；候选等待事项："]
            lines.extend(f"- {self._waiting_for_line(item)}" for item in page.items)
        else:
            lines = ["请使用明确的 wf_ ID；当前没有可选的等待事项。"]
        return {
            "answer": "\n".join(lines),
            "status": "ok",
            "metadata": {"waiting_for_candidates": page.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_waiting_for_capture(
        self, request: ApplicationRequest
    ) -> dict[str, Any]:
        if self._inbox is None:
            raise RuntimeError("Inbox service is not configured")
        content = extract_waiting_for_capture_content(request.user_input)
        if content is None:
            raise ValueError("Waiting-For capture content is empty")
        from core.inbox import InboxSuggestedType

        item = await self._inbox.capture(
            workspace_key=request.workspace_key,
            content=content,
            source="ceo_assistant",
            suggested_type=InboxSuggestedType.WAITING_FOR,
            metadata={"intent": "waiting_for_capture"},
        )
        return {
            "answer": (
                f"已捕获为待确认收件箱记录：{item.id}\n"
                "下一步请使用该 Inbox ID 明确整理成等待事项。"
            ),
            "status": "ok",
            "metadata": {"inbox_item": item.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_waiting_for_confirm(
        self, request: ApplicationRequest
    ) -> dict[str, Any]:
        if self._inbox is None or self._clock is None:
            raise RuntimeError("Waiting-For confirmation dependencies are not configured")
        parsed = parse_waiting_for_confirmation(
            request.user_input, self._timezone_name, self._clock
        )
        inbox_item = await self._inbox.resolve_to_waiting_for(
            workspace_key=request.workspace_key,
            inbox_item_id=parsed.inbox_item_id,
            subject=parsed.subject,
            waiting_on=parsed.waiting_on,
            next_review_at=parsed.next_review_at,
            timezone=parsed.timezone,
        )
        service = self._require_waiting_for(request)
        item = await service.get(
            workspace_key=request.workspace_key,
            waiting_for_id=inbox_item.resolved_target_id,
        )
        events = await service.list_events(
            workspace_key=request.workspace_key,
            waiting_for_id=item.id,
            limit=1,
        )
        event = events.items[0]
        return {
            "answer": (
                f"等待事项已确认。\nInbox ID：{inbox_item.id}\n"
                f"Waiting-For ID：{item.id}\n事项：{item.subject}\n"
                f"等待对象：{item.waiting_on}\nrevision：{item.revision}\n"
                f"event：{event.event_type.value}\n"
                f"next_review_at：{item.next_review_at.isoformat()}"
            ),
            "status": "ok",
            "metadata": {
                "inbox_item": inbox_item.model_dump(mode="json"),
                "waiting_for": item.model_dump(mode="json"),
                "event": event.model_dump(mode="json"),
            },
            "_deterministic": True,
        }

    async def _handle_waiting_for_list(
        self, request: ApplicationRequest
    ) -> dict[str, Any]:
        page = await self._require_waiting_for(request).list(
            workspace_key=request.workspace_key, view="open", limit=50
        )
        lines = ["当前没有等待事项。"] if not page.items else ["等待事项："]
        lines.extend(f"- {self._waiting_for_line(item)}" for item in page.items)
        return {
            "answer": "\n".join(lines),
            "status": "ok",
            "metadata": {"waiting_for": page.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_waiting_for_detail(
        self, request: ApplicationRequest
    ) -> dict[str, Any]:
        waiting_for_id = extract_waiting_for_id(request.user_input)
        if waiting_for_id is None:
            return await self._waiting_for_candidates(request)
        item = await self._require_waiting_for(request).get(
            workspace_key=request.workspace_key, waiting_for_id=waiting_for_id
        )
        return {
            "answer": self._waiting_for_line(item),
            "status": "ok",
            "metadata": {"waiting_for": item.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_waiting_for_history(
        self, request: ApplicationRequest
    ) -> dict[str, Any]:
        waiting_for_id = extract_waiting_for_id(request.user_input)
        if waiting_for_id is None:
            return await self._waiting_for_candidates(request)
        page = await self._require_waiting_for(request).list_events(
            workspace_key=request.workspace_key, waiting_for_id=waiting_for_id
        )
        lines = [f"{waiting_for_id} 的催办历史："]
        lines.extend(
            f"- {event.sequence} | {event.event_type.value} | {event.note}"
            for event in page.items
        )
        return {
            "answer": "\n".join(lines),
            "status": "ok",
            "metadata": {"waiting_for_events": page.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_waiting_for_lifecycle(
        self, request: ApplicationRequest, intent: str
    ) -> dict[str, Any]:
        waiting_for_id = extract_waiting_for_id(request.user_input)
        if waiting_for_id is None:
            return await self._waiting_for_candidates(request)
        service = self._require_waiting_for(request)
        current = await service.get(
            workspace_key=request.workspace_key, waiting_for_id=waiting_for_id
        )
        note = extract_action_note(request.user_input)
        common = {
            "workspace_key": request.workspace_key,
            "waiting_for_id": waiting_for_id,
            "expected_revision": current.revision,
            "source": "ceo_assistant",
            "trace_id": request.workspace_key.trace_id,
        }
        if intent == "waiting_for_follow_up":
            result = await service.record_follow_up(note=note, **common)
        elif intent == "waiting_for_snooze":
            if self._clock is None:
                raise RuntimeError("Waiting-For clock is not configured")
            next_review_at = parse_waiting_for_time(
                request.user_input, self._timezone_name, self._clock
            )
            result = await service.snooze(
                next_review_at=next_review_at, note=note, **common
            )
        elif intent == "waiting_for_resolve":
            result = await service.resolve(resolution_note=note, **common)
        elif intent == "waiting_for_cancel":
            result = await service.cancel(note=note, **common)
        elif intent == "waiting_for_reopen":
            result = await service.reopen(note=note, **common)
        else:
            raise RuntimeError(f"Unsupported Waiting-For lifecycle intent: {intent}")
        item = result.item
        time_value = item.next_review_at or item.expected_by
        return {
            "answer": (
                f"Waiting-For ID：{item.id}\nrevision：{item.revision}\n"
                f"event：{result.event.event_type.value}\n状态：{item.status.value}\n"
                f"时间：{time_value.isoformat() if time_value else '终态'}"
            ),
            "status": "ok",
            "metadata": result.model_dump(mode="json"),
            "_deterministic": True,
        }

    async def _handle_work_log(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理工作记录输入。"""
        if self._memory is None:
            raise RuntimeError("Memory service is not configured")
        user_input = request.user_input
        # Strip common prefixes
        for prefix in ["记录:", "记录：", "记录 ", "log:", "log "]:
            if user_input.startswith(prefix):
                user_input = user_input[len(prefix):].strip()

        # 实体提取
        extracted = await self._extract_work_entities(user_input)

        # 写入 Episodic Memory
        episode_content = {
            "type": "work_log",
            "raw_text": user_input,
            "date": extracted.get("date", datetime.now().strftime("%Y-%m-%d")),
            "target": extracted.get("target", ""),
            "subject": extracted.get("subject", user_input[:100]),
            "status": extracted.get("status", ""),
            "tags": extracted.get("tags", []),
        }

        from core.memory.models import MemoryItem, MemoryType
        item = MemoryItem(
            memory_type=MemoryType.EPISODIC,
            content=episode_content,
            importance=extracted.get("importance", 0.6),
            metadata={
                "session_id": request.workspace_key.session_id,
                "agent_id": "ceo-assistant",
                "source": "user_input",
            },
        )
        await self._memory.save_memory(
            memory_type=item.memory_type,
            content=item.content,
            importance=item.importance,
            metadata=item.metadata,
        )

        # 构建回复
        tags_str = ", ".join(extracted.get("tags", [])) if extracted.get("tags") else "无"
        answer_parts = ["[OK] 已记录工作内容：", ""]
        if extracted.get("subject"):
            answer_parts.append(f"事项: {extracted['subject']}")
        if extracted.get("target"):
            answer_parts.append(f"对象: {extracted['target']}")
        if extracted.get("status"):
            answer_parts.append(f"状态: {extracted['status']}")
        answer_parts.append(f"标签: [{tags_str}]")

        return {"answer": "\n".join(answer_parts), "status": "ok", "metadata": extracted}

    async def _extract_work_entities(self, text: str) -> dict[str, Any]:
        """从自然语言中提取实体。

        优先使用 LLM，fallback 到规则提取。
        """
        # 规则提取 (fallback)
        result = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "target": "",
            "subject": "",
            "status": "",
            "tags": [],
            "importance": 0.5,
        }

        # 尝试提取对象
        person_patterns = [r"和(.{1,8})确认", r"与(.{1,8})沟通", r"跟(.{1,8})说", r"见了(.{1,8})", r"和张(.{1,8})", r"和李(.{1,8})", r"和王(.{1,8})"]
        for pat in person_patterns:
            m = re.search(pat, text)
            if m:
                result["target"] = m.group(1).strip()
                break

        # 尝试提取状态
        status_patterns = [r'等待([^，,。.、]{1,8})', r'待([^，,。.、]{1,6})', r'完成了', r'已完成', r'进行中', r'确认了']
        for pat in status_patterns:
            m = re.search(pat, text)
            if m:
                result["status"] = m.group(0).strip()
                break

        # 标签提取
        tag_keywords = {
            "蜂蜡": ["蜂蜡"], "检测": ["检测", "FDA", "CFR"], "客户": ["客户", "报价"],
            "会议": ["会议", "开会"], "文档": ["文档", "报告", "文件"],
            "方案": ["方案", "计划"], "进展": ["进展", "推进"],
        }
        for tag, kws in tag_keywords.items():
            if any(kw in text for kw in kws):
                result["tags"].append(tag)

        # 主体事项
        if "和" in text or "与" in text:
            parts = re.split(r"[，。,\.\n]", text)
            for p in parts:
                if len(p) > 10:
                    result["subject"] = p.strip()[:100]
                    break
        if not result["subject"]:
            result["subject"] = text[:100]

        return result

    # ---- 2. 待办任务 ----

    async def _handle_reminder_list(self, request: ApplicationRequest) -> dict[str, Any]:
        """Return a deterministic persisted Reminder inbox view."""
        if self._reminder_inbox is None:
            raise FailureException(FailureInfo(
                code="reminder.inbox_unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder inbox is unavailable",
                component="reminder.inbox",
                operation="list_natural_language",
                retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        from core.reminders import (
            ReminderInboxStatus,
            ReminderInboxTimeScope,
            ReminderInboxView,
        )

        text = request.user_input.strip()
        statuses = None
        time_scope = None
        view = None
        if any(marker in text for marker in (
            "待触发", "待处理", "接下来有什么", "还有什么", "有什么要做", "我的提醒",
        )):
            view = ReminderInboxView.PENDING
        elif "已触发" in text:
            statuses = {ReminderInboxStatus.TRIGGERED}
        elif "失败" in text:
            statuses = {ReminderInboxStatus.FAILED}
        if "今天" in text:
            time_scope = ReminderInboxTimeScope.TODAY

        page = await self._reminder_inbox.list(
            workspace_key=request.workspace_key,
            statuses=statuses,
            time_scope=time_scope,
            view=view,
            limit=20,
            offset=0,
            trace_id=request.workspace_key.trace_id,
        )
        if not page.items:
            answer = "当前没有符合条件的提醒。"
        else:
            lines = ["提醒列表："]
            for item in page.items:
                lines.append(
                    f"[{item.status.value}] {item.task_title} | "
                    f"{item.scheduled_for.isoformat()} | ID: {item.reminder_id}"
                )
            answer = "\n".join(lines)
        if "我的提醒" in text:
            all_items = await self._reminder_inbox.list(
                workspace_key=request.workspace_key,
                limit=100,
                offset=0,
                trace_id=request.workspace_key.trace_id,
            )
            triggered = sum(item.status == ReminderInboxStatus.TRIGGERED for item in all_items.items)
            cancelled = sum(item.status == ReminderInboxStatus.CANCELLED for item in all_items.items)
            if triggered or cancelled:
                answer += f"\n另有 {triggered} 条已触发、{cancelled} 条已取消提醒。"
        return {
            "answer": answer,
            "status": "ok",
            "metadata": {"intent": "reminder_list", **page.model_dump(mode="json")},
            "_deterministic": True,
        }

    def _require_reminder_management(self, request: ApplicationRequest):
        if self._reminder_management is None:
            raise FailureException(FailureInfo(
                code="reminder.management_unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder management is unavailable",
                component="reminder.management",
                operation="resolve",
                retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        return self._reminder_management

    @staticmethod
    def _reminder_target(text: str) -> tuple[str | None, str | None]:
        reminder_id = re.search(r"\brem_[A-Za-z0-9]+\b", text)
        if reminder_id:
            return reminder_id.group(0), None
        title = text
        for marker in (
            "查看这条提醒", "查看提醒", "取消这条提醒", "取消提醒",
            "把提醒", "将提醒", "取消", "的提醒",
        ):
            title = title.replace(marker, " ")
        title = re.split(r"改到|延后到", title, maxsplit=1)[0].strip(" ，。:：")
        title = re.sub(r"^(?:把|将)\s*", "", title)
        return None, title or None

    async def _handle_reminder_detail(self, request: ApplicationRequest) -> dict[str, Any]:
        reminder_id, title_query = self._reminder_target(request.user_input)
        if reminder_id is None and title_query is None:
            raise FailureException(ReminderUserErrorPresenter.target_required(
                action="查看", trace_id=request.workspace_key.trace_id,
            ))
        view = await self._require_reminder_management(request).status(
            workspace_key=request.workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            trace_id=request.workspace_key.trace_id,
        )
        return {
            "answer": (
                f"提醒详情：\n{view.task_title}\n状态：{view.status}\n"
                f"时间：{view.scheduled_for.isoformat()}\nReminder ID：{view.reminder_id}"
            ),
            "status": "ok",
            "metadata": {"intent": "reminder_detail", **view.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_reminder_cancel(self, request: ApplicationRequest) -> dict[str, Any]:
        reminder_id, title_query = self._reminder_target(request.user_input)
        if reminder_id is None and title_query is None:
            raise FailureException(ReminderUserErrorPresenter.target_required(
                action="取消", trace_id=request.workspace_key.trace_id,
            ))
        result = await self._require_reminder_management(request).cancel(
            workspace_key=request.workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            trace_id=request.workspace_key.trace_id,
        )
        current = result.current
        return {
            "answer": (
                f"提醒已取消：\n{current.task_title}\n"
                f"原定时间：{result.previous_scheduled_for.isoformat()}\n"
                f"Reminder ID：{current.reminder_id}"
            ),
            "status": "ok",
            "metadata": {"intent": "reminder_cancel", **result.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_reminder_reschedule(self, request: ApplicationRequest) -> dict[str, Any]:
        marker = next(
            (candidate for candidate in ("延后到", "改到", "改期") if candidate in request.user_input),
            None,
        )
        target_text, time_text = (
            request.user_input.split(marker, 1) if marker else (request.user_input, "")
        )
        reminder_id, title_query = self._reminder_target(target_text)
        if reminder_id is None and title_query is None:
            raise FailureException(ReminderUserErrorPresenter.target_required(
                action="改期", trace_id=request.workspace_key.trace_id,
            ))
        if not time_text.strip():
            raise FailureException(ReminderUserErrorPresenter.time_required(
                trace_id=request.workspace_key.trace_id,
            ))
        if self._task_intent_parser is None:
            raise FailureException(FailureInfo(
                code="reminder.intent.not_configured",
                category=ErrorCategory.NOT_CONFIGURED,
                message="Reminder time parser is not configured",
                component="reminder.intent",
                operation="parse_time",
                retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        parsed = self._task_intent_parser.parse(f"{time_text.strip()} 提醒我 临时事项")
        idempotency_key = str(request.metadata.get("idempotency_key") or "").strip()
        result = await self._require_reminder_management(request).reschedule(
            workspace_key=request.workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            remind_at=parsed.due_at,
            timezone_name=parsed.timezone,
            idempotency_key=idempotency_key,
            trace_id=request.workspace_key.trace_id,
        )
        current = result.current
        return {
            "answer": (
                f"提醒已改期：\n{current.task_title}\n"
                f"原时间：{result.previous_scheduled_for.isoformat()}\n"
                f"新时间：{current.scheduled_for.isoformat()}\n"
                f"Reminder ID：{current.reminder_id}"
            ),
            "status": "ok",
            "metadata": {"intent": "reminder_reschedule", **result.model_dump(mode="json")},
            "_deterministic": True,
        }

    async def _handle_task(self, request: ApplicationRequest) -> dict[str, Any]:
        """Create or query canonical UserTasks."""
        if self._user_tasks is None:
            raise FailureException(FailureInfo(
                code="user_tasks.not_configured",
                category=ErrorCategory.NOT_CONFIGURED,
                message="UserTask service is not configured",
                component="user_tasks",
                operation="ceo_assistant",
                trace_id=request.workspace_key.trace_id,
            ))
        user_input = request.user_input

        if any(kw in user_input for kw in ["查看", "有什么", "列表", "查询", "当前任务", "待办列表"]):
            from core.user_tasks import UserTaskQuery, UserTaskStatus
            tasks = await self._user_tasks.list(
                UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=100),
                trace_id=request.workspace_key.trace_id,
            )
            if not tasks:
                return {"answer": "[Tasks] 当前没有待办任务。", "status": "ok"}
            lines = ["[Tasks] 当前待办任务：", ""]
            for task in tasks:
                due = task.due_at.isoformat() if task.due_at else ""
                lines.append(f"[{task.priority.value}] {task.title} — {task.status.value}"
                             + (f" | 截止: {due}" if due else "") + f" | ID: {task.id}")
            return {"answer": "\n".join(lines), "status": "ok"}

        task_id_match = re.search(r"\but_[a-zA-Z0-9_]+\b", user_input)
        if any(kw in user_input for kw in ["完成任务", "标记完成", "已完成"]):
            if task_id_match is None:
                raise ValueError("完成任务需要明确的 task ID")
            task = await self._user_tasks.complete(
                task_id_match.group(0), request.workspace_key.trace_id
            )
            return {"answer": f"[OK] 已完成任务：{task.title}", "status": "ok",
                    "metadata": {"task_id": task.id}}
        if "取消任务" in user_input:
            if task_id_match is None:
                raise ValueError("取消任务需要明确的 task ID")
            task = await self._user_tasks.cancel(
                task_id_match.group(0), request.workspace_key.trace_id
            )
            return {"answer": f"[OK] 已取消任务：{task.title}", "status": "ok",
                    "metadata": {"task_id": task.id}}

        from core.user_tasks import UserTaskPriority
        priority = UserTaskPriority.MEDIUM
        if any(kw in user_input for kw in ["紧急", "马上", "立刻", "尽快"]):
            priority = UserTaskPriority.HIGH
        elif any(kw in user_input for kw in ["有空", "空闲", "不急"]):
            priority = UserTaskPriority.LOW

        if self._task_intent_parser is None:
            raise FailureException(FailureInfo(
                code="reminder.intent.not_configured",
                category=ErrorCategory.NOT_CONFIGURED,
                message="Task intent parser is not configured",
                component="reminder.intent",
                operation="parse_time",
                retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        parsed = self._task_intent_parser.parse(user_input)
        if parsed.kind == "reminder":
            if self._reminder_orchestrator is None:
                raise FailureException(FailureInfo(
                    code="reminder.unavailable",
                    category=ErrorCategory.UNAVAILABLE,
                    message="Reminder scheduling is unavailable",
                    component="reminder.orchestration",
                    operation="create_natural_language_reminder",
                    retryable=False,
                    trace_id=request.workspace_key.trace_id,
                ))
            idempotency_key = (
                str(request.metadata.get("idempotency_key") or "").strip()
                or request.workspace_key.trace_id.strip()
                or uuid.uuid4().hex
            )
            result = await self._reminder_orchestrator.create_for_task(
                title=parsed.title,
                due_at=parsed.due_at,
                timezone_name=parsed.timezone,
                priority=priority,
                description=user_input,
                session_id=request.workspace_key.session_id,
                trace_id=request.workspace_key.trace_id,
                workspace_scope="|".join((
                    request.workspace_key.tenant_id,
                    request.workspace_key.workspace_id,
                    request.workspace_key.namespace,
                )),
                workspace={
                    "tenant_id": request.workspace_key.tenant_id or "default",
                    "workspace_id": request.workspace_key.workspace_id or "default",
                    "namespace": request.workspace_key.namespace or "default",
                },
                idempotency_key=idempotency_key,
            )
            metadata = result.model_dump(mode="json")
            metadata["intent"] = "reminder"
            return {
                "answer": (
                    f"提醒已安排：{parsed.title}\n时间: {metadata['scheduled_for']}\n"
                    f"Task ID: {result.task_id}\nReminder ID: {result.reminder_id}"
                ),
                "status": "ok",
                "metadata": metadata,
                "_deterministic": True,
            }

        task = await self._user_tasks.create(
            title=parsed.title, description=user_input, priority=priority, due_at=parsed.due_at,
            timezone=parsed.timezone, source="ceo_assistant",
            session_id=request.workspace_key.session_id, agent_id="ceo-assistant",
            trace_id=request.workspace_key.trace_id,
            metadata={
                "intent": "task",
                "time_unparsed": parsed.time_unparsed,
                "workspace": {
                    "tenant_id": request.workspace_key.tenant_id or "default",
                    "workspace_id": request.workspace_key.workspace_id or "default",
                    "namespace": request.workspace_key.namespace or "default",
                },
            },
        )
        due_line = f"\n截止: {task.due_at.isoformat()}" if task.due_at else ""
        if parsed.time_unparsed:
            due_line = "\n截止: 时间未识别，任务已保存为无截止日期"
        answer = (
            f"[OK] 已创建任务：\n\n任务: {task.title}\n优先级: {task.priority.value}"
            f"\n状态: {task.status.value}{due_line}\nID: {task.id}"
        )
        return {"answer": answer, "status": "ok", "metadata": task.model_dump(mode="json")}

    # ---- 3. 决策记录 ----

    async def _handle_decision(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理决策记录。"""
        if self._memory is None:
            raise RuntimeError("Memory service is not configured")
        user_input = request.user_input

        decision_info = {
            "trigger": "",
            "alternatives": [],
            "chosen": "",
            "reason": "",
            "expected_result": "",
            "outcome_status": "pending",
            "raw_text": user_input,
        }

        # 提取决策内容
        chosen_match = re.search(r"(先|决定|采用|选择|确认使用|用)(.+?)(?:[，。,\.]|$)", user_input)
        if chosen_match:
            decision_info["chosen"] = chosen_match.group(2).strip()[:200]

        reason_match = re.search(r"(因为|由于|原因是)(.+?)(?:[，。,\.]|$)", user_input)
        if reason_match:
            decision_info["reason"] = reason_match.group(2).strip()[:200]

        alt_match = re.search(r"(不先做|不采用|不选|放弃)(.+?)(?:[，。,\.]|$)", user_input)
        if alt_match:
            decision_info["alternatives"].append(alt_match.group(2).strip()[:100])

        if not decision_info["chosen"]:
            decision_info["chosen"] = user_input[:200]

        # 写入 Decision Memory
        if self._memory:
            from core.memory.models import MemoryItem, MemoryType
            item = MemoryItem(
                memory_type=MemoryType.DECISION,
                content={
                    "type": "decision",
                    **decision_info,
                },
                importance=0.8,
                metadata={
                    "session_id": request.workspace_key.session_id,
                    "agent_id": "ceo-assistant",
                },
            )
            await self._memory.save_memory(
                memory_type=item.memory_type,
                content=item.content,
                importance=item.importance,
                metadata=item.metadata,
            )

        answer_parts = ["[OK] 已记录决策：", ""]
        if decision_info["chosen"]:
            answer_parts.append(f"决策: {decision_info['chosen']}")
        if decision_info["reason"]:
            answer_parts.append(f"理由: {decision_info['reason']}")
        if decision_info["alternatives"]:
            answer_parts.append(f"备选方案: {', '.join(decision_info['alternatives'])}")
        answer_parts.append("状态: 待追踪结果")

        return {"answer": "\n".join(answer_parts), "status": "ok", "metadata": decision_info}

    # ---- 4. 知识问答 ----

    async def _handle_knowledge_qa(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理知识问答。"""
        user_input = request.user_input
        citations = []

        if self._knowledge:
            try:
                results = await self._knowledge.search(user_input, top_k=5)
                if results:
                    answer_parts = ["[KB] 基于知识库检索：", ""]
                    for i, r in enumerate(results[:3]):
                        score = getattr(r, "score", 0)
                        content = getattr(r, "content", str(r))[:200]
                        source = ""
                        if hasattr(r, "metadata") and r.metadata:
                            source = r.metadata.get("source", "")
                        elif hasattr(r, "item") and r.item:
                            source = getattr(r.item, "source", "")

                        answer_parts.append(f"{i+1}. {content}")
                        src_info = f"来源: {source}" if source else "来源: 知识库"
                        answer_parts.append(f"   {src_info} (置信度: {score:.2f})")
                        if source:
                            citations.append(source)

                    return {"answer": "\n".join(answer_parts), "status": "ok", "citations": citations}
                return {"answer": "[KB] 未找到相关知识。请先导入文档。", "status": "ok"}
            except Exception as exc:
                failure = failure_from_exception(
                    exc,
                    component="application.ceo_assistant.knowledge",
                    operation="retrieve",
                    trace_id=request.workspace_key.trace_id,
                    code="application.ceo_assistant.knowledge_failed",
                )
                raise FailureException(failure.model_copy(update={
                    "message": "Knowledge retrieval failed",
                })) from exc

        raise FailureException(FailureInfo(
            code="application.ceo_assistant.knowledge_disabled",
            category=ErrorCategory.DISABLED,
            message="Knowledge service is disabled",
            component="application.ceo_assistant.knowledge",
            operation="retrieve",
            trace_id=request.workspace_key.trace_id,
        ))

    # ---- 5. 每日简报 ----

    async def _handle_brief(self, request: ApplicationRequest) -> dict[str, Any]:
        """生成每日简报。所有数据必须来自真实 Store。"""
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"[Brief] 每日简报 — {today}", "=" * 40, ""]

        # 1. 待办任务
        tasks = []
        if self._user_tasks is not None:
            from core.user_tasks import UserTaskQuery, UserTaskStatus
            tasks = await self._user_tasks.list(
                UserTaskQuery(status=UserTaskStatus.ACTIVE, limit=50),
                trace_id=request.workspace_key.trace_id,
            )

        if tasks:
            lines.append(f"待办任务 ({len(tasks)}):")
            for task in tasks:
                lines.append(f"  [{task.priority.value}] {task.title}"
                             + (f" — 截止: {task.due_at.isoformat()}" if task.due_at else ""))
            lines.append("")

        # 2. 最近工作记录
        episodes = []
        if self._memory:
            q = MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10)
            results = await self._memory.retrieve_memory(q)
            episodes = [r for r in results if r.content.get("type") == "work_log"]

        if episodes:
            lines.append(f"最近工作记录 ({len(episodes)}):")
            for e in episodes[:5]:
                c = e.content
                lines.append(f"  - {c.get('subject', '')[:60]} ({c.get('status', '')})")
            lines.append("")

        # 3. 最近决策
        decisions = []
        if self._memory:
            decisions = [r for r in (await self._memory.retrieve_memory(MemoryQuery(memory_type=MemoryType.DECISION, top_k=20))) 
                        if r.content.get("type") == "decision"]
        if decisions:
            lines.append(f"最近决策 ({len(decisions)}):")
            for d in decisions[:3]:
                c = d.content
                lines.append(f"  - {c.get('chosen', '')[:80]} (结果: {c.get('outcome_status', 'pending')})")
            lines.append("")

        # 4. 建议优先处理
        if tasks:
            lines.append("建议优先处理:")
            priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
            sorted_tasks = sorted(tasks, key=lambda task: priority_order[task.priority.value])[:3]
            for i, task in enumerate(sorted_tasks):
                lines.append(f"  {i+1}. {task.title[:60]} ({task.priority.value}优先级)")

        if not tasks and not episodes and not decisions:
            lines.append("今日暂无工作记录和任务。")

        return {"answer": "\n".join(lines), "status": "ok"}

    # ---- 6. 多轮对话 ----

    async def _handle_chat(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理多轮对话。"""
        user_input = request.user_input

        # 尝试从 Memory 加载上下文
        context_parts = []
        if self._memory:
            from core.memory.models import MemoryQuery, MemoryType
            q = MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=5)
            recent = await self._memory.retrieve_memory(q)
            if recent:
                context_parts.append("最近工作记录:")
                for r in recent[:3]:
                    c = r.content
                    if c.get("subject"):
                        context_parts.append(f"- {c.get('date', '')}: {c.get('subject', '')[:80]}")

        context = "\n".join(context_parts) if context_parts else ""

        # 使用 LLM 生成回复
        if self._llm:
            try:
                from core.providers.llm.protocol import LLMRequest, Message
                messages = [
                    Message(role="system", content=f"""你是超哥的 CEO Assistant。用中文回复，简洁直接。

当前上下文：
{context if context else '暂无最近工作记录。'}

你可以帮助：
- 记录工作内容
- 管理待办任务
- 记录决策
- 检索知识库
- 生成每日简报"""),
                    Message(role="user", content=user_input),
                ]
                resp = await self._llm.generate(LLMRequest(
                    messages=messages,
                    model=self._config.default_model,
                    max_tokens=512,
                    temperature=0.7,
                ))
                answer = resp.content or "抱歉，我暂时无法回答。"
                return {"answer": answer, "status": "ok", "usage": resp.usage or {}}
            except Exception as exc:
                failure = failure_from_exception(
                    exc,
                    component="application.ceo_assistant.provider",
                    operation="generate",
                    trace_id=request.workspace_key.trace_id,
                    code="application.ceo_assistant.provider_failed",
                )
                raise FailureException(failure.model_copy(update={
                    "message": "LLM provider request failed",
                })) from exc

        raise FailureException(FailureInfo(
            code="application.ceo_assistant.provider_not_configured",
            category=ErrorCategory.NOT_CONFIGURED,
            message="LLM provider is not configured",
            component="application.ceo_assistant.provider",
            operation="generate",
            trace_id=request.workspace_key.trace_id,
        ))

    # ---- 辅助方法 ----

    def _detect_mode(self) -> str:
        return self._config.provider_mode
    async def _handle_daily_agenda(self, request):
        if self._daily_agenda is None:
            raise FailureException(FailureInfo(
                code="agenda.unavailable", category=ErrorCategory.UNAVAILABLE,
                message="Daily agenda is unavailable", component="agenda",
                operation="list_natural_language", retryable=False,
                trace_id=request.workspace_key.trace_id,
            ))
        text = request.user_input.strip()
        view = "today"
        if any(m in text for m in ("接下来三个小时", "未来三小时", "接下来有什么事")):
            view = "next"
        elif any(m in text for m in ("需要注意", "失败的提醒", "逾期任务")):
            view = "attention"
        elif any(m in text for m in ("已经完成", "做了哪些事", "完成记录")):
            view = "completed"
        page = await self._daily_agenda.list(
            workspace_key=request.workspace_key, view=view, limit=50,
            trace_id=request.workspace_key.trace_id,
        )
        if not page.items:
            return {"answer": "\u5f53\u524d\u6ca1\u6709\u7b26\u5408\u6761\u4ef6\u7684\u65e5\u7a0b\u5b89\u6392\u3002", "status": "ok", "metadata": {"intent": "daily_agenda", "view": view}, "_deterministic": True}
        lines = ["\u65e5\u7a0b\u6982\u89c8\uff1a", ""]
        for item in page.items:
            time_str = ""
            if item.scheduled_for:
                t = item.scheduled_for.isoformat()
                time_str = f"{t} \u2014 "
            elif item.due_at:
                t = item.due_at.isoformat()
                time_str = f"\u622a\u6b62 {t} \u2014 "
            source_label = {"reminder": "\u63d0\u9192", "user_task": "\u4efb\u52a1", "work_log": "\u5de5\u4f5c\u8bb0\u5f55", "waiting_for": "\u7b49\u5f85\u4e8b\u9879"}.get(item.source.value, item.source.value)
            if item.source.value == "waiting_for":
                waiting_on = item.metadata.get("waiting_on", "")
                lines.append(
                    f"{time_str}{item.title} | ID: {item.waiting_for_id} | "
                    f"\u7b49\u5f85: {waiting_on}  [{source_label} / {item.status}]"
                )
            else:
                lines.append(f"{time_str}{item.title}  [{source_label} / {item.status}]")
        summary = f"\u5171 {page.count} \u9879" + ("\uff0c\u663e\u793a\u90e8\u5206" if page.has_more else "")
        return {"answer": "\n".join(lines) + f"\n\n({summary})", "status": "ok", "metadata": {"intent": "daily_agenda", **page.model_dump(mode="json")}, "_deterministic": True}
