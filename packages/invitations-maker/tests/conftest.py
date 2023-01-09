# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import pytest
from cryptography.fernet import Fernet
from faker import Faker
from invitations_maker.invitations import InvitationData
from pytest import FixtureRequest, MonkeyPatch
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


@pytest.fixture(params=[True, False])
def is_trial_account(request: FixtureRequest) -> bool:
    return request.param


@pytest.fixture
def invitation_data(is_trial_account: bool, faker: Faker) -> InvitationData:
    return InvitationData(
        issuer="LicenseRequestID=123456789",
        guest=faker.email(),
        trial_account_days=faker.pyint(min_value=1) if is_trial_account else None,
    )
