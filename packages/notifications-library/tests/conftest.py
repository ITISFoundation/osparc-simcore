# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path

import notifications_library
import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.faker_products",
    "pytest_simcore.faker_user_extension",
    # "pytest_simcore.pydantic_models",
    # "pytest_simcore.pytest_global_environs",
]


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


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(notifications_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir
