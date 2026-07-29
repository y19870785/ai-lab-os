from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/project/MARKDOWN_INVENTORY.md"

# 例外必须逐文件登记并说明原因。DOCS-001 当前没有 Markdown 排除项。
MARKDOWN_EXCLUSIONS: dict[str, str] = {}

H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
URL_RE = re.compile(r"https?://\S+")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
ENV_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
PATH_RE = re.compile(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")
ORDINARY_ENGLISH_HEADING_RE = re.compile(
    r"^(?:"
    r"Status|Metadata|Context|Decision|Consequences|Rationale|"
    r"Summary|Overview|Goals|Non-goals|Scope|Architecture|Components|"
    r"Motivation|Environment|Results|Known Limitations|"
    r"Alternatives Considered|Rejected Alternatives|Acceptance Record|"
    r"Validation Record|Adoption Record|Testing Strategy|Future Extensions"
    r")$",
    re.IGNORECASE,
)
PENDING_TRANSLATION_MARKERS = (
    "TODO translate",
    "translation pending",
    "TODO: translate",
)


def _git_markdown_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "*.md", "*.markdown"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _inventory_paths() -> set[str]:
    text = INVENTORY.read_text(encoding="utf-8-sig")
    return set(re.findall(r"^\| `([^`]+)` \|", text, re.MULTILINE))


def _narrative_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    for number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            continue
        if fence_char is None:
            lines.append((number, line))
    return lines


def _plain_narrative(line: str) -> str:
    line = INLINE_CODE_RE.sub("", line)
    line = MARKDOWN_LINK_RE.sub("", line)
    line = URL_RE.sub("", line)
    line = SHA_RE.sub("", line)
    line = ENV_RE.sub("", line)
    return PATH_RE.sub("", line)


def _paragraphs(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    start = 0
    parts: list[str] = []
    for number, line in _narrative_lines(text):
        if line.lstrip().startswith("|"):
            if parts:
                result.append((start, " ".join(parts)))
                parts = []
            continue
        plain = _plain_narrative(line).strip()
        if not plain:
            if parts:
                result.append((start, " ".join(parts)))
                parts = []
            continue
        if not parts:
            start = number
        parts.append(plain)
    if parts:
        result.append((start, " ".join(parts)))
    return result


def test_markdown_inventory_matches_git_scope() -> None:
    tracked = set(_git_markdown_files())
    inventory = _inventory_paths()

    assert tracked == inventory, (
        f"清单缺失：{sorted(tracked - inventory)}；"
        f"清单多余：{sorted(inventory - tracked)}"
    )
    assert set(MARKDOWN_EXCLUSIONS).issubset(tracked)
    assert all(reason.strip() for reason in MARKDOWN_EXCLUSIONS.values())

    inventory_text = INVENTORY.read_text(encoding="utf-8-sig")
    for path, reason in MARKDOWN_EXCLUSIONS.items():
        row = next(
            line
            for line in inventory_text.splitlines()
            if line.startswith(f"| `{path}` |")
        )
        assert reason in row


def test_repository_markdown_has_chinese_h1_and_headings() -> None:
    failures: list[str] = []
    for path in _git_markdown_files():
        if path in MARKDOWN_EXCLUSIONS:
            continue
        text = _read(path)
        h1 = H1_RE.findall(text)
        if not h1:
            failures.append(f"{path}: 缺少一级标题")
            continue
        if not CJK_RE.search(h1[0]):
            failures.append(f"{path}: 一级标题不含中文：{h1[0]}")

        for number, line in _narrative_lines(text):
            match = HEADING_RE.match(line)
            if not match:
                continue
            title = INLINE_CODE_RE.sub("", match.group(2)).strip()
            if match.group(1) == "#":
                continue
            if CJK_RE.search(title):
                continue
            if ORDINARY_ENGLISH_HEADING_RE.fullmatch(title):
                failures.append(f"{path}:{number}: 普通章节标题不含中文：{title}")

    assert not failures, "\n".join(failures)


def test_repository_markdown_has_no_long_english_narrative() -> None:
    failures: list[str] = []
    for path in _git_markdown_files():
        if path in MARKDOWN_EXCLUSIONS:
            continue
        text = _read(path)
        lowered = text.lower()
        for marker in PENDING_TRANSLATION_MARKERS:
            if marker.lower() in lowered:
                failures.append(f"{path}: 存在未完成翻译标记 `{marker}`")

        for line, paragraph in _paragraphs(text):
            english = len(ASCII_LETTER_RE.findall(paragraph))
            chinese = len(CJK_RE.findall(paragraph))
            if english >= 120 and chinese == 0:
                failures.append(
                    f"{path}:{line}: 长篇纯英文叙述（英文字符 {english}）"
                )

    assert not failures, "\n".join(failures)


def _relative_target(source: str, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith("#"):
        return None
    if re.match(r"^(?:https?://|mailto:|tel:|data:)", target):
        return None

    target = unquote(target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0])
    if not target:
        return None
    if "XXX" in target or target in {"ABC", "path/to/file"}:
        return None
    if "\\" in target:
        raise AssertionError(f"{source}: 相对链接混用 Windows 反斜杠：{raw_target}")

    if target.startswith("/"):
        return ROOT / target.lstrip("/")
    source_relative = (ROOT / source).parent / target
    root_relative = ROOT / target
    if source_relative.exists() or not root_relative.exists():
        return source_relative
    return root_relative


def test_repository_markdown_relative_links_exist() -> None:
    failures: list[str] = []
    for source in _git_markdown_files():
        if source in MARKDOWN_EXCLUSIONS:
            continue
        text = _read(source)
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            try:
                target = _relative_target(source, raw_target)
            except AssertionError as error:
                failures.append(str(error))
                continue
            if target is not None and not target.resolve().exists():
                failures.append(f"{source}: 相对链接不存在：{raw_target}")

    assert not failures, "\n".join(failures)
