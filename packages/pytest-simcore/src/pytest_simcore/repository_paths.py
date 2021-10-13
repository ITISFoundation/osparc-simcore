# pylint: disable=redefined-outer-name
import sys
from pathlib import Path

import pytest

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
WILDCARD = "packages/pytest-simcore/src/pytest_simcore/__init__.py"
ROOT = Path("/")


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(request) -> Path:
    """osparc-simcore repo root dir"""
    test_dir = Path(request.session.fspath)  # expected test dir in simcore

    root_dir = CURRENT_DIR
    for start_dir in (CURRENT_DIR, test_dir):
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
def osparc_simcore_services_dir(osparc_simcore_root_dir) -> Path:
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
def osparc_simcore_api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    _folder = osparc_simcore_root_dir / "api" / "specs"
    assert _folder.exists()
    return _folder


@pytest.fixture(scope="session")
def osparc_simcore_scripts_dir(osparc_simcore_root_dir: Path) -> Path:
    scripts_folder = osparc_simcore_root_dir / "scripts"
    assert scripts_folder.exists()
    return scripts_folder


@pytest.fixture(scope="session")
def osparc_simcore_web_client_dir(services_dir: Path) -> Path:
    wbc_dir = services_dir / "web/client"
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
def services_docker_compose_file(services_dir) -> Path:
    dcpath = services_dir / "docker-compose.yml"
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
    """Current service's project slug directory"""
    raise NotImplementedError("Override fixture in project's tests/conftest.py")


@pytest.fixture(scope="session")
def project_tests_dir(project_slug_dir: Path) -> Path:
    """Current service's tests directory"""
    test_dir = project_slug_dir / "tests"
    assert test_dir.exists()
    return test_dir


@pytest.fixture(scope="session")
def openapi_specs_file_path(
    project_slug_dir: Path, osparc_simcore_api_specs_dir: Path
) -> Path:
    """Current services's OpenAPI specification file path"""
    # By convention, the OAS is stored in one of two places
    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/2584

    # fastapi based apps
    fastapi_apps_oas_path = project_slug_dir / "openapi.json"
    # aiohttp based apps
    aiohttp_apps_oas_path = (
        osparc_simcore_api_specs_dir / project_slug_dir.name / "openapi.json"
    )

    assert (
        fastapi_apps_oas_path.exists() or aiohttp_apps_oas_path.exists()
    ), f"expected {fastapi_apps_oas_path} or {aiohttp_apps_oas_path}"

    if fastapi_apps_oas_path.exists():
        return fastapi_apps_oas_path

    return aiohttp_apps_oas_path
