# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import pytest
import simcore_service_payments
from cryptography.fernet import Fernet
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.cli_runner",
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
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    secret_key: str,
    fake_user_name: str,
    fake_password: str,
) -> EnvVarsDict:

    return setenvs_from_dict(
        monkeypatch,
        {
            "PAYMENTS_SECRET_KEY": secret_key,
            "PAYMENTS_GATEWAY_URL": "https://fake-payment-gateway.com",
            "PAYMENTS_USERNAME": fake_user_name,
            "PAYMENTS_PASSWORD": fake_password,
        },
    )
