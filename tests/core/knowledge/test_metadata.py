"""Tests for metadata extraction."""
import pytest
from core.knowledge.metadata import (
    build_default_registry, extract_language, extract_links, extract_tags,
)


class TestMetadataExtraction:
    def test_language_chinese(self):
        result = extract_language("这是一段中文文本用于测试语言检测功能", {})
        assert result["language"] == "zh"

    def test_language_english(self):
        result = extract_language("This is English text for language detection", {})
        assert result["language"] == "en"

    def test_extract_links(self):
        result = extract_links("Check https://example.com and visit http://test.org", {})
        assert "https://example.com" in result["references"]
        assert "http://test.org" in result["references"]

    def test_extract_tags(self):
        result = extract_tags("This is about #python and #machinelearning topics", {})
        assert "python" in result["tags"]
        assert "machinelearning" in result["tags"]

    def test_default_registry(self):
        reg = build_default_registry()
        meta = reg.extract("这是一段#Python代码\n参考https://python.org")
        assert meta["language"] == "zh"
        assert "Python" in meta["tags"]
        assert "https://python.org" in meta["references"]
