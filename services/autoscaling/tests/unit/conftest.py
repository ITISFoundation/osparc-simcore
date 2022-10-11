# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import pytest
import simcore_service_autoscaling
from faker import Faker
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "autoscaling"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_autoscaling"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_autoscaling.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "AWS_KEY_NAME": "TODO",
            "AWS_DNS": faker.domain_name(),
            "AWS_ACCESS_KEY_ID": "str",
            "AWS_SECRET_ACCESS_KEY": "str",
            "AWS_SECURITY_GROUP_IDS": '["a", "b"]',
            "AWS_SUBNET_ID": "str",
        },
    )
    return mock_env_devel_environment | envs
