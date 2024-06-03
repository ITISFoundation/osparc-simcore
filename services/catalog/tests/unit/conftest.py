# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import pytest
import simcore_service_catalog
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.postgres_service",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "catalog"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_catalog"))
    return service_folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_catalog.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def env_devel_dict(
    env_devel_dict: EnvVarsDict, external_envfile_dict: EnvVarsDict
) -> EnvVarsDict:
    if external_envfile_dict:
        assert "CATALOG_DEV_FEATURES_ENABLED" in external_envfile_dict
        assert "CATALOG_SERVICES_DEFAULT_RESOURCES" in external_envfile_dict
        return external_envfile_dict
    return env_devel_dict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    """Produces testing environment for the app
    by replicating the environment defined in the docker-compose
    when initialized with .env-devel
    """
    return setenvs_from_dict(
        monkeypatch,
        {**docker_compose_service_environment_dict},
    )
