"""Knowledge metadata extraction.

Extracts structured metadata from content: author, date, language, tags, references.
Plug-in architecture — add new extractors by registering them.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from core.knowledge.models import KnowledgeItem

# Type alias for a metadata extractor function
MetadataExtractor = Callable[[str, dict[str, Any]], dict[str, Any]]
"""Takes (content, current_metadata) and returns updates to merge."""


class MetadataExtractorRegistry:
    """Registry of metadata extraction functions."""

    def __init__(self) -> None:
        self._extractors: list[tuple[str, MetadataExtractor]] = []

    def register(self, name: str, fn: MetadataExtractor) -> None:
        """Register an extractor. Execution order = registration order."""
        self._extractors.append((name, fn))

    def extract(self, content: str, base_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run all extractors and merge results."""
        metadata = dict(base_metadata or {})
        for name, fn in self._extractors:
            try:
                updates = fn(content, metadata)
                metadata.update(updates)
            except Exception:
                pass  # Best-effort: one extractor failing shouldn't break the chain
        return metadata


# ── Built-in extractors ──

def extract_language(content: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Detect language (simple heuristic: CJK character ratio)."""
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', content))
    total = max(len(content), 1)
    return {"language": "zh" if cjk / total > 0.1 else "en"}


def extract_links(content: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Extract URLs and markdown links as references."""
    urls = re.findall(r'https?://[^\s)]+', content)
    md_links = re.findall(r'\]\((https?://[^)]+)\)', content)
    all_urls = urls + md_links
    return {"references": list(set(all_urls))} if all_urls else {}


def extract_tags(content: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Extract hashtags (#tag)."""
    tags_en = re.findall(r'#([a-zA-Z][a-zA-Z0-9_]*)', content)
    tags_cn = re.findall(r'#([\u4e00-\u9fff][\u4e00-\u9fff]*)', content)
    tags = tags_en + tags_cn
    return {"tags": list(set(tags))} if tags else {}
def build_default_registry() -> MetadataExtractorRegistry:
    """Return a registry with built-in extractors."""
    reg = MetadataExtractorRegistry()
    reg.register("language", extract_language)
    reg.register("links", extract_links)
    reg.register("tags", extract_tags)
    return reg
