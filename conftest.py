"""Pytest 真实 Provider 测试的全仓 fail-closed 边界。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REAL_PROVIDER_FLAG = "--run-real-provider"
REAL_PROVIDER_ENV = "AI_LAB_ALLOW_REAL_PROVIDER_TESTS"
_DISABLED_MESSAGE = (
    "Real-provider tests disabled. Explicit --run-real-provider and "
    "AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1 are required."
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册独立于凭据存在性的真实 Provider 执行授权。"""
    parser.addoption(
        REAL_PROVIDER_FLAG,
        action="store_true",
        default=False,
        help=(
            "Allow real-provider test collection only when "
            "AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1 is also set."
        ),
    )


def _real_provider_tests_authorized(config: pytest.Config) -> bool:
    """仅在 CLI 与环境双因素同时满足时授权真实 Provider 测试。"""
    return bool(config.getoption(REAL_PROVIDER_FLAG)) and (
        os.getenv(REAL_PROVIDER_ENV) == "1"
    )


def _is_real_provider_path(path: Path) -> bool:
    """识别 tests/real 目录自身及其全部后代。"""
    normalized = Path(path)
    parts = tuple(part.casefold() for part in normalized.parts)
    return any(
        parts[index : index + 2] == ("tests", "real")
        for index in range(len(parts) - 1)
    )


def pytest_ignore_collect(
    collection_path: Path,
    config: pytest.Config,
) -> bool | None:
    """在危险 conftest/test module 导入前排除未授权 tests/real。"""
    if _is_real_provider_path(collection_path) and not _real_provider_tests_authorized(
        config
    ):
        return True
    return None


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """对目录外误放的 real marker 提供第二层 fail-closed 保护。"""
    if _real_provider_tests_authorized(config):
        return
    denied = pytest.mark.skip(reason=_DISABLED_MESSAGE)
    for item in items:
        if item.get_closest_marker("real") is not None:
            item.add_marker(denied)


def pytest_report_header(config: pytest.Config) -> str | None:
    """向普通 pytest/IDE 调用说明真实 Provider 测试为何未启用。"""
    if not _real_provider_tests_authorized(config):
        return _DISABLED_MESSAGE
    return None
