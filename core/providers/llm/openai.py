"""OpenAI LLM Provider —— 真实 OpenAI API 接入。

遵循 LLMProvider Protocol，支持：
- Chat completion (generate)
- Streaming
- Token counting
- Model listing
- Retry + timeout
- Metrics
"""

from __future__ import annotations

import os
import time
import asyncio
from typing import Any, AsyncIterator

from core.providers.llm.protocol import (
    LLMProvider, LLMRequest, LLMResponse, Message, TokenCount,
)
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class OpenAILLMProvider(LLMProvider):
    """OpenAI LLM backend via openai Python SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key or os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self._base_url = (
            base_url or os.getenv("AI_LAB_LLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        self._model = (
            model or os.getenv("AI_LAB_LLM_MODEL")
            or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = None
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

        info = ProviderInfo(
            provider_id=f"openai-{self._model}",
            provider_type=ProviderType.LLM,
            name="openai",
            version="2.14.0",
            description=f"OpenAI LLM Provider ({self._model})",
            capabilities=[
                ProviderCapability(name="generate", version="1.0"),
                ProviderCapability(name="stream", version="1.0"),
                ProviderCapability(name="function_call", version="1.0"),
                ProviderCapability(name="vision", version="1.0"),
                ProviderCapability(name="json_mode", version="1.0"),
                ProviderCapability(name="reasoning", version="1.0"),
            ],
        )
        super().__init__(info)
        self._info = info

    async def _do_initialize(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )

    async def _do_shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None

    async def _do_health_check(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    # ---- LLMProvider interface ----

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self._require_ready()
        t0 = time.time()

        messages = self._to_openai_messages(request.messages)
        kwargs: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }
        if request.stop:
            kwargs["stop"] = request.stop
        if request.functions:
            kwargs["functions"] = request.functions
        if request.function_call:
            kwargs["function_call"] = request.function_call
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(self._max_retries + 1):
            try:
                completion = await asyncio.wait_for(
                    self._client.chat.completions.create(**kwargs),
                    timeout=self._timeout,
                )
                break
            except asyncio.TimeoutError:
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                self._error_count += 1
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(2 ** attempt)

        self._request_count += 1
        self._total_latency_ms += (time.time() - t0) * 1000

        choice = completion.choices[0]
        usage_dict = {}
        if completion.usage:
            usage_dict = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }

        fc = None
        if choice.message.function_call:
            fc = {
                "name": choice.message.function_call.name,
                "arguments": choice.message.function_call.arguments,
            }

        return LLMResponse(
            content=choice.message.content or "",
            model=completion.model,
            finish_reason=choice.finish_reason or "stop",
            usage=usage_dict,
            function_call=fc,
            raw=completion.model_dump(),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self._require_ready()
        messages = self._to_openai_messages(request.messages)
        kwargs: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stream": True,
        }

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def count_tokens(self, messages: list[Message]) -> TokenCount:
        # Simple approximation: ~4 chars per token for English
        total_chars = sum(len(m.content) for m in messages)
        approx_tokens = max(1, total_chars // 4)
        return TokenCount(input_tokens=approx_tokens, output_tokens=0, total_tokens=approx_tokens)

    async def list_models(self) -> list[str]:
        if not self._client:
            return [self._model]
        try:
            models = await self._client.models.list()
            return [m.id for m in models.data]
        except Exception:
            return [self._model]

    def supports_function_call(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def supports_reasoning(self) -> bool:
        return "o1" in self._model or "o3" in self._model

    def supports_json_mode(self) -> bool:
        return True

    # ---- Helpers ----

    def _to_openai_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        result = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.name:
                msg["name"] = m.name
            result.append(msg)
        return result

    @property
    def metrics(self) -> dict[str, Any]:
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": self._total_latency_ms / max(1, self._request_count),
            "model": self._model,
        }
