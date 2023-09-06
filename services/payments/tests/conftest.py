# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import re
from pathlib import Path

import pytest
import simcore_service_payments
import yaml
from cryptography.fernet import Fernet
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
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
    dirpath = Path(simcore_service_payments.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def secret_key() -> str:
    key = Fernet.generate_key()
    return key.decode()


@pytest.fixture
def another_secret_key(secret_key: str) -> str:
    other = Fernet.generate_key()
    assert other.decode() != secret_key
    return other.decode()


@pytest.fixture
def fake_user_name(faker: Faker) -> str:
    return faker.user_name()


@pytest.fixture
def fake_password(faker: Faker) -> str:
    return faker.password(length=10)


@pytest.fixture
def docker_compose_service_payments_envs(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    payments = yaml.safe_load(services_docker_compose_file.read_text())["services"][
        "payments"
    ]

    def _substitute(item):
        key, value = item.split("=")
        if m := re.match(r"\${([^{}:-]\w+)", value):
            if value := env_devel_dict.get(m.group(1)):
                return key, value
        return None

    envs: EnvVarsDict = {}
    for item in payments.get("environment", []):
        if found := _substitute(item):
            key, value = found
            envs[key] = value

    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_payments_envs: EnvVarsDict,
    secret_key: str,
    fake_user_name: str,
    fake_password: str,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_payments_envs,
            "PAYMENTS_SECRET_KEY": secret_key,
            "PAYMENTS_USERNAME": fake_user_name,
            "PAYMENTS_PASSWORD": fake_password,
        },
    )
