# pylint: disable=redefined-outer-name
import sys
from pathlib import Path

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(request) -> Path:
    """ osparc-simcore repo root dir """
    WILDCARD = "packages/pytest-simcore/src/pytest_simcore/__init__.py"
    ROOT = Path("/")

    test_dir = Path(request.session.fspath)  # expected test dir in simcore

    root_dir = current_dir
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
def osparc_simcore_api_specs_dir(osparc_simcore_root_dir) -> Path:
    dirpath = osparc_simcore_root_dir / "api" / "specs"
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_services_dir(osparc_simcore_root_dir) -> Path:
    """ Path to osparc-simcore/services folder """
    services_dir = osparc_simcore_root_dir / "services"
    assert services_dir.exists()
    return services_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir: Path) -> Path:
    """ Path to osparc-simcore/.env-devel file """
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture(scope="session")
def packages_directory(osparc_simcore_root_dir: Path) -> Path:
    _folder = osparc_simcore_root_dir / "packages"
    assert _folder.exists()
    return _folder


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


@pytest.fixture(scope="session")
def web_client_dir(services_dir: Path) -> Path:
    wbc_dir = services_dir / "web/client"
    assert wbc_dir.exists()
    return wbc_dir


@pytest.fixture(scope="session")
def pylintrc(osparc_simcore_root_dir: Path) -> Path:
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    tdir = (current_dir / "..").resolve()
    assert tdir.exists()
    assert tdir.name == "tests"
    return tdir


## PACKAGE and SERVICE DIRECTORY STRUCTURE


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    raise NotImplementedError("Override fixture in project's tests/conftest.py")


@pytest.fixture(scope="session")
def project_tests_dir(project_slug_dir: Path) -> Path:
    test_dir = project_slug_dir / "tests"
    assert test_dir.exists()
    return test_dir


# TODO: test that all these path compositions exist
