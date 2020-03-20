# pylint: disable=redefined-outer-name

import sys
from pathlib import Path

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(request) -> Path:
    """ osparc-simcore repo root dir """
    WILDCARD = "packages/pytest-simcore/src/pytest_simcore/environs.py"
    ROOT = Path("/")

    test_dir = Path(request.session.fspath) # expected test dir in simcore

    for start_dir in (current_dir, test_dir):
        root_dir = start_dir
        while not any(root_dir.glob(WILDCARD)) and root_dir != ROOT:
            root_dir = root_dir.parent

        if root_dir!=ROOT:
            break

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"

    assert root_dir != ROOT, msg
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture(scope="module")
def temp_folder(request, tmpdir_factory) -> Path:
    tmp = Path(tmpdir_factory.mktemp(f"tmp_module_{request.module.__name__}"))
    yield tmp
