# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import pytest
from cryptography.fernet import Fernet
from faker import Faker
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.cli_runner",
]


@pytest.fixture
def secret_key() -> str:
    key = Fernet.generate_key()
    return key.decode()


@pytest.fixture
def fake_user_name(faker: Faker) -> str:
    return faker.user_name()


@pytest.fixture
def fake_password(faker: Faker) -> str:
    return faker.password(length=10)


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch,
    secret_key: str,
    fake_user_name: str,
    fake_password: str,
) -> EnvVarsDict:

    envs = setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_MAKER_SECRET_KEY": secret_key,
            "INVITATIONS_MAKER_OSPARC_URL": "https://myosparc.org",
            "INVITATIONS_USERNAME": fake_user_name,
            "INVITATIONS_PASSWORD": fake_password,
        },
    )

    return envs
