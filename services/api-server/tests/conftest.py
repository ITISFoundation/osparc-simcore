# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from pathlib import Path

from pydantic import TypeAdapter
import pytest
import simcore_service_api_server
from dotenv import dotenv_values
from models_library.projects import ProjectID
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_api_server.models.schemas.jobs import JobID

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.httpx_calls_capture",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
]


@pytest.fixture(scope="session")
def project_env_devel_vars(project_slug_dir: Path) -> EnvVarsDict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environs = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    assert not any(value is None for key, value in environs.items())
    return environs


@pytest.fixture(scope="session")
def dockerfile_env_vars(project_slug_dir: Path) -> EnvVarsDict:
    dockerfile = project_slug_dir / "Dockerfile"
    assert dockerfile.exists()
    # manual selection of ENV defined in Dockerfile
    return {
        "SC_USER_ID": "8004",
        "SC_USER_NAME": "scu",
        "SC_BUILD_TARGET": "production",
        "SC_BOOT_MODE": "production",
    }


@pytest.fixture(scope="session")
def default_app_env_vars(
    dockerfile_env_vars: EnvVarsDict,
    project_env_devel_vars: EnvVarsDict,
) -> EnvVarsDict:
    """env-vars composed from the project's .env-devel and Dockerfile to set the app environment"""

    env_vars = {}
    # warning update order matters
    env_vars.update(project_env_devel_vars)
    env_vars.update(dockerfile_env_vars)
    env_vars["API_SERVER_DEV_FEATURES_ENABLED"] = "1"
    env_vars["API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED"] = "1"
    env_vars["API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED"] = "0"

    return env_vars


## FOLDER LAYOUT ----


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def tests_utils_dir(project_tests_dir: Path) -> Path:
    utils_dir = (project_tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir


## BASIC IDENTIFIERS ---


@pytest.fixture
def job_id(project_id: ProjectID) -> JobID:
    return TypeAdapter(JobID).validate_python(project_id)
