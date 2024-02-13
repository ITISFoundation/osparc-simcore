# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import simcore_service_payments
import yaml
from faker import Faker
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, parse_obj_as
from pytest_simcore.helpers.rawdata_fakers import (
    random_payment_transaction,
    random_product,
    random_user,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
from servicelib.utils_secrets import generate_token_secret_key
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pytest_socketio",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
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
    return generate_token_secret_key(32)


@pytest.fixture
def fake_user_name(faker: Faker) -> str:
    return faker.user_name()


@pytest.fixture
def fake_password(faker: Faker) -> str:
    return faker.password(length=10)


def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup(
        "external_environment",
        description="Replaces mocked services with real ones by passing actual environs and connecting directly to external services",
    )
    group.addoption(
        "--external-envfile",
        action="store",
        type=Path,
        default=None,
        help="Path to an env file. Consider passing a link to repo configs, i.e. `ln -s /path/to/osparc-ops-config/repo.config`",
    )
    group.addoption(
        "--external-email",
        action="store",
        type=str,
        default=None,
        help="An email for test_services_notifier_email",
    )


@pytest.fixture(scope="session")
def external_environment(request: pytest.FixtureRequest) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    if envfile := request.config.getoption("--external-envfile"):
        assert isinstance(envfile, Path)
        print("🚨 EXTERNAL: external envs detected. Loading", envfile, "...")
        envs = load_dotenv(envfile)
        assert "PAYMENTS_GATEWAY_API_SECRET" in envs
        assert "PAYMENTS_GATEWAY_URL" in envs

    return envs


@pytest.fixture
def env_devel_dict(
    env_devel_dict: EnvVarsDict, external_environment: EnvVarsDict
) -> EnvVarsDict:
    if external_environment:
        return external_environment
    return env_devel_dict


@pytest.fixture
def docker_compose_service_payments_env_vars(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    """env vars injected at the docker-compose"""

    payments = yaml.safe_load(services_docker_compose_file.read_text())["services"][
        "payments"
    ]

    def _substitute(key, value):
        if m := re.match(r"\${([^{}:-]\w+)", value):
            expected_env_var = m.group(1)
            try:
                # NOTE: if this raises, then the RHS env-vars in the docker-compose are
                # not defined in the env-devel
                if value := env_devel_dict[expected_env_var]:
                    return key, value
            except KeyError:
                pytest.fail(
                    f"{expected_env_var} is not defined in .env-devel but used in docker-compose services[{payments}].environment[{key}]"
                )
        return None

    envs: EnvVarsDict = {}
    for key, value in payments.get("environment", {}).items():
        if found := _substitute(key, value):
            _, new_value = found
            envs[key] = new_value

    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_payments_env_vars: EnvVarsDict,
    secret_key: str,
    fake_user_name: str,
    fake_password: str,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_payments_env_vars,
            "PAYMENTS_ACCESS_TOKEN_SECRET_KEY": secret_key,
            "PAYMENTS_USERNAME": fake_user_name,
            "PAYMENTS_PASSWORD": fake_password,
        },
    )


@pytest.fixture
def product(faker: Faker) -> dict[str, Any]:
    return random_product(support_email="support@osparc.io", fake=faker)


@pytest.fixture
def product_name(faker: Faker, product: dict[str, Any]) -> ProductName:
    return parse_obj_as(IDStr, product["name"])


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return parse_obj_as(UserID, faker.pyint())


@pytest.fixture
def user_email(faker: Faker) -> EmailStr:
    return parse_obj_as(EmailStr, faker.email())


@pytest.fixture
def user_first_name(faker: Faker) -> str:
    return faker.first_name()


@pytest.fixture
def user_last_name(faker: Faker) -> str:
    return faker.last_name()


@pytest.fixture
def user_name(user_email: str) -> IDStr:
    return parse_obj_as(IDStr, user_email.split("@")[0])


@pytest.fixture
def user(
    faker: Faker,
    user_id: UserID,
    user_email: EmailStr,
    user_first_name: str,
    user_last_name: str,
    user_name: IDStr,
) -> dict[str, Any]:
    return random_user(
        id=user_id,
        email=user_email,
        name=user_name,
        first_name=user_first_name,
        last_name=user_last_name,
        fake=faker,
    )


@pytest.fixture
def user_primary_group_id(faker: Faker) -> GroupID:
    return parse_obj_as(GroupID, faker.pyint())


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return parse_obj_as(WalletID, faker.pyint())


@pytest.fixture
def wallet_name(faker: Faker) -> IDStr:
    return parse_obj_as(IDStr, f"wallet-{faker.word()}")


@pytest.fixture
def successful_transaction(
    faker: Faker,
    wallet_id: WalletID,
    user_email: EmailStr,
    user_id: UserID,
    product_name: ProductName,
) -> dict[str, Any]:
    initiated_at = datetime.now(tz=timezone.utc)
    return random_payment_transaction(
        payment_id=f"pt_{faker.pyint()}",
        price_dollars=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        state=PaymentTransactionState.SUCCESS,
        initiated_at=initiated_at,
        completed_at=initiated_at + timedelta(seconds=10),
        osparc_credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        product_name=product_name,
        user_id=user_id,
        user_email=user_email,
        wallet_id=wallet_id,
        comment=f"fake fixture in {__name__}.successful_transaction",
        invoice_url=faker.image_url(),
    )
