# pylint: disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Dict

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def osparc_simcore_root_dir(request) -> Path:
    """ osparc-simcore repo root dir """
    WILDCARD = "packages/pytest-simcore/src/pytest_simcore/__init__.py"
    ROOT = Path("/")

    test_dir = Path(request.session.fspath)  # expected test dir in simcore

    for start_dir in (current_dir, test_dir):
        root_dir = start_dir
        while not any(root_dir.glob(WILDCARD)) and root_dir != ROOT:
            root_dir = root_dir.parent

        if root_dir != ROOT:
            break

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"

    assert root_dir != ROOT, msg
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir: Path) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture(scope="session")
def devel_environ(env_devel_file) -> Dict:
    env_devel = {}
    with env_devel_file.open() as f:
        env_devel = load_env(f)
    return env_devel


@pytest.fixture(scope="session")
def script_dir(osparc_simcore_root_dir: Path) -> Path:
    scripts_folder = osparc_simcore_root_dir / "scripts"
    assert scripts_folder.exists()
    return scripts_folder


@pytest.fixture(scope="session")
def services_dir(osparc_simcore_root_dir: Path) -> Path:
    services_folder = osparc_simcore_root_dir / "services"
    assert services_folder.exists()
    return services_folder


@pytest.fixture(scope="session")
def services_docker_compose_file(services_dir):
    dcpath = services_dir / "docker-compose.yml"
    assert dcpath.exists()
    return dcpath


@pytest.fixture(scope="module")
def temp_folder(request, tmpdir_factory) -> Path:
    tmp = Path(tmpdir_factory.mktemp(f"tmp_module_{request.module.__name__}"))
    return tmp


@pytest.fixture(scope="session")
def web_client_dir(services_dir: Path) -> Path:
    wbc_dir = services_dir / "web/client"
    assert wbc_dir.exists()
    return wbc_dir
