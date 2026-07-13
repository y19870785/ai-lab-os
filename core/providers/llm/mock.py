"""Mock LLM Provider for testing and development."""

from __future__ import annotations

from typing import Any, AsyncIterator

from core.providers.llm.protocol import (
    LLMProvider, LLMRequest, LLMResponse, Message, TokenCount,
)
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class MockLLMProvider(LLMProvider):
    """Mock LLM that echoes the last user message as response.

    Used for:
    - Unit testing (no network, deterministic)
    - CI pipelines
    - Interface verification
    """

    def __init__(self) -> None:
        info = ProviderInfo(
            provider_id="mock-llm-001",
            provider_type=ProviderType.LLM,
            name="mock",
            version="1.0.0",
            description="Mock LLM for testing",
            capabilities=[
                ProviderCapability(name="generate", version="1.0"),
                ProviderCapability(name="stream", version="1.0"),
                ProviderCapability(name="function_call", version="1.0"),
            ],
        )
        super().__init__(info)

    async def _do_initialize(self) -> None:
        pass

    async def _do_shutdown(self) -> None:
        pass

    async def _do_health_check(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self._require_ready()
        last_msg = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        return LLMResponse(
            content=f"[mock] {last_msg}",
            model="mock-v1",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self._require_ready()
        response = await self.generate(request)
        for chunk in response.content.split():
            yield chunk + " "

    async def count_tokens(self, messages: list[Message]) -> TokenCount:
        total = sum(len(m.content.split()) for m in messages)
        return TokenCount(input_tokens=total, output_tokens=0, total_tokens=total)

    async def list_models(self) -> list[str]:
        return ["mock-v1", "mock-v2", "mock-large"]

    def supports_function_call(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False

    def supports_reasoning(self) -> bool:
        return False

    def supports_json_mode(self) -> bool:
        return True
