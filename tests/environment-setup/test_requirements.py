import re
import sys
from pathlib import Path

import pytest

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
REPO_DIR = CURRENT_DIR.parent.parent
assert any(REPO_DIR.glob(".git"))

SERVICES_DIR = REPO_DIR / "services"
assert SERVICES_DIR.exists()


@pytest.mark.parametrize(
    "exclude",
    [
        "aioresponses",
        "coverage",
        "flaky",
        "hypothesis",
        "pytest",
        "moto",
        "respx",
    ],
)
@pytest.mark.parametrize(
    "base_path",
    SERVICES_DIR.rglob("_base.txt"),
    ids=lambda p: f"{p.relative_to(SERVICES_DIR)}",
)
def test_libraries_are_not_allowed_in_base_requirements(base_path: Path, exclude: str):
    requirements_text = re.sub(
        r"(^|\s)(#.*|\n)", "", base_path.read_text().lower(), flags=re.MULTILINE
    )
    assert exclude not in requirements_text
