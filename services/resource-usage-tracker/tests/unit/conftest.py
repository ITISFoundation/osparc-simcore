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
    service_folder = osparc_simcore_root_dir / "services" / "resource-usage"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_resource_usage"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_invitations.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def jsondata(faker: Faker) -> dict:
    return {
        "name": faker.name(),
        "email": faker.email(),
        "phone": faker.phone_number(),
        "address": {
            "street": faker.street_address(),
            "city": faker.city(),
            "state": faker.state(),
            "zipcode": faker.zipcode(),
        },
    }


@pytest.fixture
def fake_user_name(faker: Faker) -> str:
    return faker.user_name()


@pytest.fixture
def fake_password(faker: Faker) -> str:
    return faker.password(length=10)


@pytest.fixture
def fake_port(faker: Faker) -> int:
    return faker.pyint(min_value=1024, max_value=65535)


@pytest.fixture
def fake_url(faker: Faker) -> str:
    return faker.url()


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch,
    fake_user_name: str,
    fake_port: int,
    fake_url: str,
    fake_password: str,
) -> EnvVarsDict:

    envs = setenvs_from_dict(
        monkeypatch,
        {
            "RESOURCE_USAGE_PROMETHEUS_PASSWORD": fake_password,
            "RESOURCE_USAGE_PROMETHEUS_PORT": str(fake_port),
            "RESOURCE_USAGE_PROMETHEUS_USERNAME": fake_user_name,
            "RESOURCE_USAGE_PROMETHEUS_URL": "https://example.org",
        },
    )

    return envs
