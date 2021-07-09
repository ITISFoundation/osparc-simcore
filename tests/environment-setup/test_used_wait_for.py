# pylint: disable=redefined-outer-name

import hashlib
import sys
from pathlib import Path

import pytest

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.resolve()

ASSERT_ERROR_MESSAGE = (
    "Looks like thewait-for script changed. Ensure the code is taken from"
    "https://github.com/eficode/wait-for/releases"
)


@pytest.fixture
def wait_for_path() -> Path:
    return CURRENT_DIR / ".." / ".." / "scripts" / "common-docker-boot" / "wait-for"


@pytest.fixture
def sha256sum() -> str:
    # NOTICE: only change this value if you have updated the script
    # compute this on a linux box with (macos will produce a different value)
    # from this directory run:
    # sha256sum ../../scripts/common-docker-boot/wait-for
    # current version v2.1.2
    return "a444f069a25a333b375cc835895e39f44606040701a622f3c0abb2fc62d39ebf"


def test_wait_for_did_not_change(sha256sum: str, wait_for_path: Path) -> None:
    with open(wait_for_path, "rb") as f:
        file_content = f.read()
        readable_hash = hashlib.sha256(file_content).hexdigest()
        assert readable_hash == sha256sum, ASSERT_ERROR_MESSAGE
