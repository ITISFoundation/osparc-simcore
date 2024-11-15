# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
import simcore_service_payments
from faker import Faker
from models_library.users import GroupID
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils_secrets import generate_token_secret_key

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_payments_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.socketio",
    "pytest_simcore.rabbit_service",
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
    return generate_token_secret_key(32)


@pytest.fixture(scope="session")
def external_envfile_dict(external_envfile_dict: EnvVarsDict) -> EnvVarsDict:
    if external_envfile_dict:
        assert "PAYMENTS_GATEWAY_API_SECRET" in external_envfile_dict
        assert "PAYMENTS_GATEWAY_URL" in external_envfile_dict
    return external_envfile_dict


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
    secret_key: str,
    faker: Faker,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "PAYMENTS_ACCESS_TOKEN_SECRET_KEY": secret_key,
            "PAYMENTS_USERNAME": faker.user_name(),
            "PAYMENTS_PASSWORD": faker.password(),
            "PAYMENTS_TRACING": "null",
        },
    )


@pytest.fixture
def user_primary_group_id(faker: Faker) -> GroupID:
    return TypeAdapter(GroupID).validate_python(faker.pyint())
