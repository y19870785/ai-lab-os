"""Knowledge query filters.

Provides common filter builders for KnowledgeQuery.filters.
"""

from __future__ import annotations

from typing import Any

from core.knowledge.models import KnowledgeType, SourceType


def by_type(knowledge_type: KnowledgeType) -> dict[str, Any]:
    return {"knowledge_type": knowledge_type.value}


def by_source(source_type: SourceType) -> dict[str, Any]:
    return {"source_type": source_type.value}


def by_tag(tag: str) -> dict[str, Any]:
    return {"tag": tag}


def by_language(lang: str) -> dict[str, Any]:
    return {"language": lang}


def by_confidence(min_conf: float) -> dict[str, Any]:
    return {"min_confidence": min_conf}


def by_author(author: str) -> dict[str, Any]:
    return {"author": author}


def combine(*filters: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple filter dicts into one."""
    result: dict[str, Any] = {}
    for f in filters:
        result.update(f)
    return result
