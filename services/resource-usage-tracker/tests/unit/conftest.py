# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import pytest
from faker import Faker
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "resource-usage-tracker"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_resource_usage_tracker"))
    return service_folder


@pytest.fixture
def fake_port(faker: Faker) -> int:
    return faker.pyint(min_value=1024, max_value=65535)


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch, fake_port: int, faker: Faker
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "RESOURCE_USAGE_PROMETHEUS_PASSWORD": faker.password(),
            "RESOURCE_USAGE_PROMETHEUS_PORT": str(fake_port),
            "RESOURCE_USAGE_PROMETHEUS_USERNAME": faker.user_name(),
            "RESOURCE_USAGE_PROMETHEUS_URL": faker.url(),
        },
    )

    return envs
