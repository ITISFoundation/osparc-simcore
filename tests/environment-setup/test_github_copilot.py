# pylint: disable=redefined-outer-name

import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent.parent.parent
_GITHUB_DIR = _REPO_DIR / ".github"

_MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_CODE_FENCE_RE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)$")


def _iter_prose_lines(markdown: str) -> Iterator[tuple[int, str]]:
    opening_marker = ""
    for lineno, line in enumerate(markdown.splitlines(), start=1):
        match = _CODE_FENCE_RE.fullmatch(line)
        if opening_marker:
            if (
                match
                and match[1][0] == opening_marker[0]
                and len(match[1]) >= len(opening_marker)
                and not match[2].strip(" \t")
            ):
                opening_marker = ""
            continue
        if match and (match[1][0] == "~" or "`" not in match[2]):
            opening_marker = match[1]
            continue
        yield lineno, line


@pytest.mark.parametrize(
    "markdown, expected",
    [
        pytest.param("[link](missing.md)", [(1, "[link](missing.md)")], id="prose"),
        pytest.param("```python\n[link](missing.md)\n```\nafter", [(4, "after")], id="backticks"),
        pytest.param("~~~python\n[link](missing.md)\n~~~\nafter", [(4, "after")], id="tildes"),
        pytest.param("````\n```\n[link](missing.md)\n````\nafter", [(5, "after")], id="shorter-marker"),
        pytest.param("```\n[link](missing.md)\n````\nafter", [(4, "after")], id="longer-closing-marker"),
        pytest.param("~~~\n```\n[link](missing.md)\n~~~\nafter", [(5, "after")], id="different-marker"),
        pytest.param("   ```\n[link](missing.md)\n   ```\nafter", [(4, "after")], id="indented-fence"),
        pytest.param("```\n    ```\n[link](missing.md)\n```\nafter", [(5, "after")], id="overindented-closer"),
        pytest.param("```\n```not-a-closer\n[link](missing.md)\n```\nafter", [(5, "after")], id="closer-with-text"),
        pytest.param("```\n[link](missing.md)\n``` \t\nafter", [(4, "after")], id="closer-with-whitespace"),
        pytest.param("```\n[link](missing.md)", [], id="unclosed-fence"),
        pytest.param("```invalid`info\nafter", [(1, "```invalid`info"), (2, "after")], id="backtick-in-info"),
    ],
)
def test_prose_lines_exclude_fenced_code(markdown: str, expected: list[tuple[int, str]]):
    assert list(_iter_prose_lines(markdown)) == expected


@pytest.fixture(params=["instructions", "prompts", "skills"])
def github_copilot_category_dir(request: pytest.FixtureRequest) -> Path:
    directory = _GITHUB_DIR / request.param
    assert directory.exists()
    return directory


@pytest.fixture
def markdown_file(request: pytest.FixtureRequest) -> Path:
    path: Path = request.param
    assert path.exists()
    return path


@pytest.mark.parametrize(
    "markdown_file",
    sorted(_GITHUB_DIR.rglob("*.md")),
    indirect=True,
    ids=lambda p: str(p.relative_to(_GITHUB_DIR)),
)
def test_reference_links_exist(markdown_file: Path):
    broken: list[str] = []
    for lineno, line in _iter_prose_lines(markdown_file.read_text(encoding="utf-8")):
        # strip inline code spans to avoid false positives (e.g. `[T](Class):`)
        scanned = _INLINE_CODE_RE.sub("", line)
        for href in _MD_LINK_RE.findall(scanned):
            if href.startswith(("#", "http://", "https://")):
                continue
            target = (markdown_file.parent / href.partition("#")[0].strip()).resolve()
            if not target.exists():
                rel = markdown_file.relative_to(_REPO_DIR)
                broken.append(f"Broken link in {rel}:{lineno} : {href!r}")

    assert not broken, "\n".join(broken)
