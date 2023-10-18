# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from pathlib import Path

import pytest
import simcore_service_payments
import yaml
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.utils_secrets import generate_token_secret_key

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.postgres_service",
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


@pytest.fixture
def docker_compose_service_payments_env_vars(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    """env vars injected at the docker-compose"""

    payments = yaml.safe_load(services_docker_compose_file.read_text())["services"][
        "payments"
    ]

    def _substitute(item):
        key, value = item.split("=")
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
    for item in payments.get("environment", []):
        if found := _substitute(item):
            key, value = found
            envs[key] = value

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
