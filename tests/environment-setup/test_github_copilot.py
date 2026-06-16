# pylint: disable=redefined-outer-name

import re
import sys
from pathlib import Path

import pytest

_REPO_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent.parent.parent
_GITHUB_DIR = _REPO_DIR / ".github"

_MD_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


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
    for lineno, line in enumerate(markdown_file.read_text(encoding="utf-8").splitlines(), start=1):
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
