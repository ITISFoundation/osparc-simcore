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
from models_library.users import GroupID
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
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
    faker: Faker,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_payments_env_vars,
            "PAYMENTS_ACCESS_TOKEN_SECRET_KEY": secret_key,
            "PAYMENTS_USERNAME": faker.user_name(),
            "PAYMENTS_PASSWORD": faker.password(),
        },
    )


@pytest.fixture
def user_primary_group_id(faker: Faker) -> GroupID:
    return parse_obj_as(GroupID, faker.pyint())
