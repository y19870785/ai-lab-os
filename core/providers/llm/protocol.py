"""LLM Provider Protocol.

Defines the unified interface for all LLM backends.
No implementation binds to any specific model provider.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from core.providers.base import BaseProvider


class Message(BaseModel):
    """A single chat message."""
    role: str = "user"          # "system" | "user" | "assistant" | "function"
    content: str = ""
    name: str | None = None     # optional function/tool name


class LLMRequest(BaseModel):
    """Request to an LLM provider."""
    messages: list[Message] = Field(default_factory=list)
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stop: list[str] = Field(default_factory=list)
    functions: list[dict[str, Any]] | None = None
    function_call: str | dict[str, str] | None = None
    json_mode: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    content: str = ""
    model: str = ""
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)
    function_call: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TokenCount(BaseModel):
    """Token count result."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMProvider(BaseProvider):
    """Abstract LLM backend.

    All LLM access goes through this interface. Agents never call
    OpenAI / Anthropic / Ollama directly.
    """

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a single completion. Blocks until done."""
        ...

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream a completion token by token."""
        ...

    @abstractmethod
    async def count_tokens(self, messages: list[Message]) -> TokenCount:
        """Count tokens for given messages."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available model names."""
        ...

    @abstractmethod
    def supports_function_call(self) -> bool:
        """Does this provider support function/tool calling?"""
        ...

    @abstractmethod
    def supports_vision(self) -> bool:
        """Does this provider support image inputs?"""
        ...

    @abstractmethod
    def supports_reasoning(self) -> bool:
        """Does this provider support chain-of-thought reasoning?"""
        ...

    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Does this provider support structured JSON output?"""
        ...
