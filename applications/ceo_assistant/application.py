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
import os
import json
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any
import uuid

from applications.models import ApplicationInfo, ApplicationManifest, ApplicationContext, ApplicationRequest, ApplicationResponse
from applications.config import ApplicationConfig


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
        config: ApplicationConfig | None = None,
        bus=None,
    ):
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._llm = llm_provider
        self._embedding = embedding_provider
        self._config = config or ApplicationConfig()
        self._bus = bus

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

    # ---- 意图识别 ----

    async def _detect_intent(self, user_input: str) -> dict[str, Any]:
        """识别用户意图，决定走哪个处理器。

        使用规则 + LLM 混合策略：
        1. 先做关键词规则匹配（快速路径）
        2. 无法确定时使用 LLM 意图分类
        3. 决策 > 任务 > 工作记录 优先级递减
        """
        text = user_input.lower().strip()

        # 规则匹配
        intent = "chat"  # 默认聊天
        confidence = 0.5

        # 简报
        brief_keywords = ["简报", "今日总结", "今天做了什么", "今天的工作", "今日概览", "daily brief", "工作概览"]
        if any(kw in text for kw in brief_keywords):
            intent = "brief"
            confidence = 0.9

        # 决策（必须在任务之前，因为两者关键词有重叠）
        decision_keywords = ["决定", "决策", "选择", "采用", "确认使用", "不先做", "放弃"]
        if any(kw in text for kw in decision_keywords):
            intent = "decision"
            confidence = 0.7

        # 任务
        task_keywords = ["任务", "待办", "提醒我", "todo", "task", "截止", "完成", "取消任务", "暂停"]
        if any(kw in text for kw in task_keywords) and intent == "chat":
            intent = "task"
            confidence = 0.8

        # 知识问答
        knowledge_keywords = ["什么是", "解释", "法规", "标准", "规定", "文档", "查询", "查找", "怎么"]
        if any(kw in text for kw in knowledge_keywords):
            intent = "knowledge"
            confidence = 0.7

        # 工作记录
        log_keywords = ["记录", "今天", "刚才", "完成了", "确认了", "收到了", "会议", "见了"]
        if any(kw in text for kw in log_keywords):
            intent = "work_log"
            confidence = 0.7

        return {"intent": intent, "confidence": confidence}

    # ---- 主执行入口 ----

    async def run(self, request: ApplicationRequest) -> ApplicationResponse:
        """执行业务请求。"""
        t0 = time.time()

        try:
            intent = await self._detect_intent(request.user_input)
            mode = request.metadata.get("provider_mode", self._detect_mode())

            result = None
            if intent["intent"] == "work_log":
                result = await self._handle_work_log(request)
            elif intent["intent"] == "task":
                result = await self._handle_task(request)
            elif intent["intent"] == "decision":
                result = await self._handle_decision(request)
            elif intent["intent"] == "knowledge":
                result = await self._handle_knowledge_qa(request)
            elif intent["intent"] == "brief":
                result = await self._handle_brief(request)
            else:
                result = await self._handle_chat(request)

            answer = result.get("answer", "")
            if mode == "mock":
                answer = f"[MOCK MODE] {answer}\n\n(Set OPENAI_API_KEY to use real LLM)"

            return ApplicationResponse(
                application_id=self.info.application_id,
                answer=answer,
                status=result.get("status", "ok"),
                citations=result.get("citations", []),
                usage=result.get("usage", {}),
                latency_ms=(time.time() - t0) * 1000,
                trace_id=request.workspace_key.trace_id,
                mode=mode,
                metadata=result.get("metadata", {}),
            )
        except Exception as e:
            return ApplicationResponse(
                application_id=self.info.application_id,
                answer="",
                status="error",
                error=str(e),
                latency_ms=(time.time() - t0) * 1000,
                trace_id=request.workspace_key.trace_id,
                mode=self._detect_mode(),
            )

    # ---- 1. 工作记录 ----

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

    async def _handle_task(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理任务创建/查询。"""
        if self._memory is None:
            raise RuntimeError("Memory service is not configured")
        user_input = request.user_input

        # 查询已有任务
        if any(kw in user_input for kw in ["查看", "有什么", "列表", "查询", "当前任务", "待办列表"]):
            if self._memory:
                from core.memory.models import MemoryQuery, MemoryType
                q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=20)
                tasks = await self._memory.retrieve_memory(q)
                # Filter task entries
                task_items = [t for t in tasks if t.content.get("type") == "task"]
                if task_items:
                    lines = ["[Tasks] 当前待办任务：", ""]
                    for t in task_items:
                        c = t.content
                        priority = c.get("priority", "中")
                        status = c.get("status", "待办")
                        title = c.get("title", c.get("subject", ""))
                        deadline = c.get("deadline", "")
                        lines.append(f"[{priority}] {title} — {status}" + (f" | 截止: {deadline}" if deadline else ""))
                    return {"answer": "\n".join(lines), "status": "ok"}
                return {"answer": "[Tasks] 当前没有待办任务。", "status": "ok"}
            return {"answer": "[Tasks] 当前没有待办任务。(Mock)", "status": "ok"}

        # 创建任务
        task_info = {
            "title": "",
            "deadline": "",
            "priority": "中",
            "status": "待办",
            "raw_text": user_input,
        }

        # 提取截止时间
        deadline_patterns = [
            (r"明[天日](\w{1,3})午", "+1d"),
            (r"今天(\w{1,3})午", "+0d"),
            (r"(\d+)月(\d+)[日号]", ""),
        ]
        if "明天" in user_input:
            tomorrow = datetime.now() + timedelta(days=1)
            task_info["deadline"] = tomorrow.strftime("%Y-%m-%d")
        elif "今天" in user_input:
            task_info["deadline"] = datetime.now().strftime("%Y-%m-%d")

        # 提取优先级
        if any(kw in user_input for kw in ["紧急", "马上", "立刻", "尽快"]):
            task_info["priority"] = "高"
        elif any(kw in user_input for kw in ["有空", "空闲", "不急"]):
            task_info["priority"] = "低"

        # 提取标题
        title_match = re.search(r"(提醒我|记得|别忘了)(.+?)(?:[。，\.]|$)", user_input)
        if title_match:
            task_info["title"] = title_match.group(2).strip()
        else:
            clean = re.sub(r"(提醒我|创建任务|帮忙|帮|请)", "", user_input).strip()
            task_info["title"] = clean[:80]

        # 写入 Decision Memory (任务存储)
        if self._memory:
            from core.memory.models import MemoryItem, MemoryType
            item = MemoryItem(
                memory_type=MemoryType.DECISION,
                content={
                    "type": "task",
                    **task_info,
                },
                importance=0.7 if task_info["priority"] == "高" else 0.5,
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

        answer = f"[OK] 已创建任务：\n\n任务: {task_info['title']}\n优先级: {task_info['priority']}\n状态: {task_info['status']}"
        if task_info["deadline"]:
            answer += f"\n截止: {task_info['deadline']}"

        return {"answer": answer, "status": "ok", "metadata": task_info}

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
        answer_parts.append(f"状态: 待追踪结果")

        return {"answer": "\n".join(answer_parts), "status": "ok", "metadata": decision_info}

    # ---- 4. 知识问答 ----

    async def _handle_knowledge_qa(self, request: ApplicationRequest) -> dict[str, Any]:
        """处理知识问答。"""
        user_input = request.user_input
        citations = []

        if self._knowledge:
            try:
                from core.knowledge.models import KnowledgeQuery
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
            except Exception as e:
                return {"answer": f"[KB] 知识检索异常: {e}", "status": "error"}

        return {"answer": "[KB] 知识服务已禁用。", "status": "disabled"}

    # ---- 5. 每日简报 ----

    async def _handle_brief(self, request: ApplicationRequest) -> dict[str, Any]:
        """生成每日简报。所有数据必须来自真实 Store。"""
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"[Brief] 每日简报 — {today}", "=" * 40, ""]

        # 1. 待办任务
        tasks = []
        if self._memory:
            from core.memory.models import MemoryQuery, MemoryType
            q = MemoryQuery(memory_type=MemoryType.DECISION, top_k=50)
            results = await self._memory.retrieve_memory(q)
            tasks = [r for r in results if r.content.get("type") == "task" and r.content.get("status") in ("待办", "进行中", "pending")]

        if tasks:
            lines.append(f"待办任务 ({len(tasks)}):")
            for t in tasks:
                c = t.content
                lines.append(f"  [{c.get('priority', '中')}] {c.get('title', '无标题')}" 
                           + (f" — 截止: {c.get('deadline', '未设置')}" if c.get('deadline') else ""))
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
            priority_order = {"高": 1, "中": 2, "低": 3}
            sorted_tasks = sorted(tasks, key=lambda t: priority_order.get(t.content.get("priority", "中"), 2))[:3]
            for i, t in enumerate(sorted_tasks):
                lines.append(f"  {i+1}. {t.content.get('title', '')[:60]} ({t.content.get('priority', '中')}优先级)")

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
                return {"answer": "", "status": "error", "metadata": {"error": str(exc)}}

        return {"answer": "", "status": "not_configured", "metadata": {"error": "LLM provider is not configured"}}

    # ---- 辅助方法 ----

    def _detect_mode(self) -> str:
        return self._config.provider_mode
