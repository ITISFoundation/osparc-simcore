# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path

import pytest
import simcore_service_efs_guardian
from faker import Faker
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "payments"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_payments"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_efs_guardian.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def env_devel_dict(
    env_devel_dict: EnvVarsDict, external_envfile_dict: EnvVarsDict
) -> EnvVarsDict:
    if external_envfile_dict:
        return external_envfile_dict
    return env_devel_dict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
    faker: Faker,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "EFS_DNS_NAME": "fs-xxx.efs.us-east-1.amazonaws.com",
            "EFS_MOUNTED_PATH": "/tmp/efs",
            "EFS_PROJECT_SPECIFIC_DATA_DIRECTORY": "project-specific-data",
            "EFS_ONLY_ENABLED_FOR_USERIDS": "[]",
            "EFS_GUARDIAN_TRACING": "null",
            "SC_USER_ID": "8004",
            "SC_USER_NAME": "scu",
            "EFS_USER_ID": "8006",
            "EFS_USER_NAME": "efs",
            "EFS_GROUP_ID": "8106",
            "EFS_GROUP_NAME": "efs-group",
        },
    )
