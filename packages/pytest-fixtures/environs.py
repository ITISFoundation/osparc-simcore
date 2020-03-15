# pylint: disable=redefined-outer-name

import sys
from pathlib import Path

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

## HELPERS
sys.path.append(str(current_dir / "helpers"))


@pytest.fixture(scope="session")
def osparc_simcore_root_dir() -> Path:
    """ osparc-simcore repo root dir """
    WILDCARD = "services/web/server"

    root_dir = Path(current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath
