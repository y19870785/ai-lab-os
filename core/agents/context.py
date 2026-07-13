"""ContextBuilder — single entry point for building Agent prompts."""
from __future__ import annotations
from typing import Any
from core.agents.models import AgentRequest, AgentContext, AgentInfo
from core.agents.config import AgentConfig

class ContextBuilder:
    def __init__(self, info: AgentInfo, config: AgentConfig | None = None):
        self._info = info
        self._config = config or AgentConfig()
    async def build(self, request: AgentRequest, memory_items: list[dict[str, Any]] | None = None, knowledge_results: list[dict[str, Any]] | None = None) -> AgentContext:
        ctx = AgentContext(session_id=request.session_id, agent_id=request.agent_id or self._info.id)
        if memory_items:
            ctx.memory_items = memory_items
        if knowledge_results:
            ctx.knowledge_results = knowledge_results
        ctx.system_prompt = self._build_system_prompt()
        ctx.messages = self._build_messages(request, memory_items, knowledge_results)
        return ctx
    def _build_system_prompt(self) -> str:
        parts = [self._config.system_prompt or "You are " + self._info.name + ". " + self._info.description]
        if self._info.capabilities:
            parts.append("Capabilities: " + ", ".join(self._info.capabilities))
        return " ".join(parts)
    def _build_messages(self, request, memory, knowledge) -> list[dict[str, str]]:
        msgs = []
        if knowledge:
            k_text = " ".join(str(k.get("content", ""))[:500] for k in knowledge[:3])
            if k_text:
                msgs.append({"role": "system", "content": "Relevant knowledge: " + k_text})
        if memory:
            m_text = " ".join(str(m.get("content", ""))[:300] for m in memory[:5])
            if m_text:
                msgs.append({"role": "system", "content": "Recent context: " + m_text})
        msgs.append({"role": "user", "content": request.user_input})
        return msgs