from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/project/MARKDOWN_INVENTORY.md"

# 文件级排除必须逐项登记并说明原因。DOCS-001 当前没有排除项。
MARKDOWN_EXCLUSIONS: dict[str, str] = {}

# 纯英文普通标题默认禁止。这里只允许不可合理中文化的正式技术标题，且逐项说明。
TECHNICAL_HEADING_EXCEPTIONS: dict[str, str] = {}

# 表头中的纯技术标识可以保留；解释性 Field/Value/Status 等不属于此表。
TECHNICAL_TABLE_HEADER_EXCEPTIONS: dict[str, str] = {
    "API": "正式技术缩写",
    "CLI": "正式技术缩写",
    "HTTP": "正式协议名称",
    "ID": "正式技术缩写",
    "RFC": "治理标识符",
    "ADR": "治理标识符",
    "SP": "治理标识符",
    "ACC": "治理标识符",
    "UTC": "正式时间标准",
    "JSON": "正式数据格式",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
URL_RE = re.compile(r"https?://\S+")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
ENV_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
PATH_RE = re.compile(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")
MACHINE_VALUE_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\s*/\s*[A-Z][A-Z0-9_]*)*$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/{}<>=*+\-]*$")
PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]")
QUESTION_MARK_CORRUPTION_RE = re.compile(r"\?{4,}")
PENDING_TRANSLATION_MARKERS = (
    "TODO translate",
    "translation pending",
    "TODO: translate",
)
MOJIBAKE_FRAGMENTS = (
    "\ufffd",
    "涓€",
    "鏇存柊",
    "鍏ㄥ眬",
    "娴嬭瘯",
    "閿惎",
    "棣栨",
    "鏋舵瀯",
    "鍘嗗彶",
    "鈥?",
    "Ã©",
    "Ã¤",
    "Ã¥",
    "Â ",
    "â€",
    "ä¸",
    "å…",
    "æ–",
    "çš",
    "è¯",
    "é€",
    "æœ",
    "ç»",
)


@dataclass(frozen=True)
class Heading:
    line: int
    level: int
    title: str


@dataclass(frozen=True)
class MarkdownTable:
    line: int
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


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
    """返回代码围栏和 HTML 注释之外的 Markdown 叙述行。"""
    lines: list[tuple[int, str]] = []
    fence_char: str | None = None
    fence_length = 0
    in_comment = False

    for number, original in enumerate(text.splitlines(), start=1):
        line = original
        match = FENCE_RE.match(line)
        if match and not in_comment:
            marker = match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            continue
        if fence_char is not None:
            continue

        visible: list[str] = []
        cursor = 0
        while cursor < len(line):
            if in_comment:
                end = line.find("-->", cursor)
                if end < 0:
                    cursor = len(line)
                    continue
                in_comment = False
                cursor = end + 3
                continue
            start = line.find("<!--", cursor)
            if start < 0:
                visible.append(line[cursor:])
                break
            visible.append(line[cursor:start])
            in_comment = True
            cursor = start + 4

        if not in_comment or visible:
            lines.append((number, "".join(visible)))
    return lines


def _headings(text: str) -> list[Heading]:
    headings: list[Heading] = []
    for number, line in _narrative_lines(text):
        match = HEADING_RE.match(line)
        if match:
            headings.append(
                Heading(
                    line=number,
                    level=len(match.group(1)),
                    title=INLINE_CODE_RE.sub("", match.group(2)).strip(),
                )
            )
    return headings


def _heading_failures(path: str, text: str) -> list[str]:
    headings = _headings(text)
    failures: list[str] = []
    h1 = [heading for heading in headings if heading.level == 1]

    if len(h1) != 1:
        failures.append(f"{path}: 有效一级标题数量应为 1，实际为 {len(h1)}")
    if headings and headings[0].level != 1:
        failures.append(f"{path}:{headings[0].line}: 第一个有效标题必须是一级标题")
    if h1 and not CJK_RE.search(h1[0].title):
        failures.append(f"{path}:{h1[0].line}: 一级标题不含中文：{h1[0].title}")

    for heading in headings:
        if heading.level == 1 or CJK_RE.search(heading.title):
            continue
        if heading.title in TECHNICAL_HEADING_EXCEPTIONS:
            continue
        failures.append(
            f"{path}:{heading.line}: 普通章节标题不含中文：{heading.title}"
        )
    return failures


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


def _table_cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    stripped = stripped.removeprefix("|")
    stripped = stripped.removesuffix("|")
    return tuple(cell.strip() for cell in stripped.split("|"))


def _tables(text: str) -> list[MarkdownTable]:
    narrative = _narrative_lines(text)
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(narrative):
        number, line = narrative[index]
        _, separator = narrative[index + 1]
        if "|" not in line or not TABLE_SEPARATOR_RE.match(separator):
            index += 1
            continue

        rows: list[tuple[str, ...]] = []
        cursor = index + 2
        while cursor < len(narrative):
            _, row = narrative[cursor]
            if "|" not in row or not row.strip():
                break
            rows.append(_table_cells(row))
            cursor += 1
        tables.append(
            MarkdownTable(
                line=number,
                header=_table_cells(line),
                rows=tuple(rows),
            )
        )
        index = cursor
    return tables


def _is_technical_cell(cell: str) -> bool:
    visible = cell.strip().strip("*")
    if not visible:
        return True
    if visible in TECHNICAL_TABLE_HEADER_EXCEPTIONS:
        return True
    if INLINE_CODE_RE.fullmatch(visible):
        return True
    if MACHINE_VALUE_RE.fullmatch(visible):
        return True
    return bool(IDENTIFIER_RE.fullmatch(visible) and "_" in visible)


def _table_failures(path: str, text: str) -> list[str]:
    failures: list[str] = []
    for table in _tables(text):
        for cell in table.header:
            if CJK_RE.search(cell) or _is_technical_cell(cell):
                continue
            failures.append(f"{path}:{table.line}: 英文解释性表头：{cell}")
        for row_offset, row in enumerate(table.rows, start=2):
            for cell in row:
                plain = _plain_narrative(cell)
                english = len(ASCII_LETTER_RE.findall(plain))
                chinese = len(CJK_RE.findall(plain))
                if english >= 80 and chinese == 0 and not _is_technical_cell(cell):
                    failures.append(
                        f"{path}:{table.line + row_offset}: "
                        f"长篇纯英文解释单元格（英文字符 {english}）"
                    )
    return failures


def _mojibake_failures(path: str, text: str) -> list[str]:
    failures: list[str] = []
    if PRIVATE_USE_RE.search(text):
        failures.append(f"{path}: 包含 Unicode 私用区乱码字符")
    if QUESTION_MARK_CORRUPTION_RE.search(text):
        failures.append(f"{path}: 包含连续大量问号")
    for fragment in MOJIBAKE_FRAGMENTS:
        if fragment in text:
            failures.append(f"{path}: 包含已确认 mojibake 特征 `{fragment}`")
    return failures


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


def test_repository_markdown_has_one_chinese_h1_and_chinese_headings() -> None:
    failures: list[str] = []
    for path in _git_markdown_files():
        if path not in MARKDOWN_EXCLUSIONS:
            failures.extend(_heading_failures(path, _read(path)))
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


def test_repository_markdown_tables_use_chinese_explanatory_text() -> None:
    failures: list[str] = []
    for path in _git_markdown_files():
        if path not in MARKDOWN_EXCLUSIONS:
            failures.extend(_table_failures(path, _read(path)))
    assert not failures, "\n".join(failures)


def test_repository_markdown_has_no_encoding_corruption() -> None:
    failures: list[str] = []
    for path in _git_markdown_files():
        if path not in MARKDOWN_EXCLUSIONS:
            failures.extend(_mojibake_failures(path, _read(path)))
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


def test_language_gate_regression_examples() -> None:
    assert _heading_failures(
        "sample.md",
        "```python\n# comment\n```\n## 中文章节\n",
    )[0].endswith("有效一级标题数量应为 1，实际为 0")
    assert _heading_failures(
        "sample.md",
        "<!--\n# 注释中的伪标题\n-->\n## 中文章节\n",
    )[0].endswith("有效一级标题数量应为 1，实际为 0")
    assert any(
        "实际为 2" in failure
        for failure in _heading_failures(
            "sample.md",
            "# 中文标题\n# 第二个中文标题\n",
        )
    )
    assert any(
        "Implementation phases" in failure
        for failure in _heading_failures(
            "sample.md",
            "# 中文标题\n## Implementation phases\n",
        )
    )
    assert any(
        "英文解释性表头" in failure
        for failure in _table_failures(
            "sample.md",
            "# 中文标题\n\n| Field | Value |\n| --- | --- |\n| `id` | `x` |\n",
        )
    )
    assert not _mojibake_failures("sample.md", "# 中文标题\n操作娴熟")
    assert not _mojibake_failures("sample.md", "# 中文标题\n林棣安完成了检查")
    assert _mojibake_failures("sample.md", "# 中文标题\n鏇存柊鏃ュ織") != []
    assert _mojibake_failures("sample.md", "# 中文标题\n\ufffd") != []
    assert _mojibake_failures("sample.md", "# 中文标题\n????") != []
    assert not _table_failures(
        "sample.md",
        "# 中文标题\n\n| ID | `status_code` |\n| --- | --- |\n| `x` | `READY` |\n",
    )
    assert not _heading_failures(
        "sample.md",
        "# 中文标题\n\n```python\n## Implementation phases\n```\n",
    )
