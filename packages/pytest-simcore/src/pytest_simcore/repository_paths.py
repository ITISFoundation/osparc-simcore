# pylint: disable=redefined-outer-name
import sys
from pathlib import Path

import pytest

_CURRENT_DIR = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)
_WILDCARD = "packages/pytest-simcore/src/pytest_simcore/__init__.py"
_ROOT = Path("/")


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(request: pytest.FixtureRequest) -> Path:
    """osparc-simcore repo root dir"""
    test_dir = Path(request.session.fspath)  # expected test dir in simcore

    root_dir = _CURRENT_DIR
    for start_dir in (_CURRENT_DIR, test_dir):
        root_dir = start_dir
        while not any(root_dir.glob(_WILDCARD)) and root_dir != _ROOT:
            root_dir = root_dir.parent

        if root_dir != _ROOT:
            break

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"

    assert root_dir != _ROOT, msg
    assert root_dir.exists(), msg
    assert any(root_dir.glob(_WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope="session")
def osparc_simcore_services_dir(osparc_simcore_root_dir: Path) -> Path:
    """Path to osparc-simcore/services folder"""
    services_dir = osparc_simcore_root_dir / "services"
    assert services_dir.exists()
    return services_dir


@pytest.fixture(scope="session")
def osparc_simcore_packages_dir(osparc_simcore_root_dir: Path) -> Path:
    _folder = osparc_simcore_root_dir / "packages"
    assert _folder.exists()
    return _folder


@pytest.fixture(scope="session")
def osparc_simcore_scripts_dir(osparc_simcore_root_dir: Path) -> Path:
    scripts_folder = osparc_simcore_root_dir / "scripts"
    assert scripts_folder.exists()
    return scripts_folder


@pytest.fixture(scope="session")
def osparc_simcore_web_client_dir(services_dir: Path) -> Path:
    wbc_dir = services_dir / "static-webserver/client"
    assert wbc_dir.exists()
    return wbc_dir


# alias for backwards compatibility (new are longer to avoid name collisions)
packages_directory = osparc_simcore_packages_dir
services_dir = osparc_simcore_services_dir
web_client_dir = osparc_simcore_web_client_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir: Path) -> Path:
    """Path to osparc-simcore/.env-devel file"""
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture(scope="session")
def services_docker_compose_file(services_dir: Path) -> Path:
    dcpath = services_dir / "docker-compose.yml"
    assert dcpath.exists()
    return dcpath


@pytest.fixture(scope="session")
def services_docker_compose_dev_vendors_file(osparc_simcore_services_dir: Path) -> Path:
    """Path to osparc-simcore/services/docker-compose-dev-vendors.yml file"""
    dcpath = osparc_simcore_services_dir / "docker-compose-dev-vendors.yml"
    assert dcpath.exists()
    return dcpath


@pytest.fixture(scope="session")
def pylintrc(osparc_simcore_root_dir: Path) -> Path:
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


## LOCAL PACKAGE and SERVICE DIRECTORY STRUCTURE -------


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    raise NotImplementedError("Override fixture in project's tests/conftest.py")
    #
    # Implementation example
    #   folder = CURRENT_DIR.parent
    #   assert folder.exists()
    #   assert any(folder.glob("src/simcore_service_dynamic_sidecar"))
    #   return folder
    #


@pytest.fixture(scope="session")
def project_tests_dir(project_slug_dir: Path) -> Path:
    test_dir = project_slug_dir / "tests"
    assert test_dir.exists()
    return test_dir
