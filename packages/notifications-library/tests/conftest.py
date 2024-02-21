# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path

import notifications_library
import pytest
from pydantic import EmailStr, parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.faker_payments_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.docker_compose",
    "pytest_simcore.postgres_service",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.tmp_path_extra",
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
        "--external-user-email",
        action="store",
        type=str,
        default=None,
        help="Overrides `user_email` fixture",
    )
    group.addoption(
        "--external-support-email",
        action="store",
        type=str,
        default=None,
        help="Overrides `support_email` fixture",
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
        print("🚨 EXTERNAL `envfile` option detected. Loading", envfile, "...")
        envs = load_dotenv(envfile)
        assert "PAYMENTS_GATEWAY_API_SECRET" in envs
        assert "PAYMENTS_GATEWAY_URL" in envs

    return envs


@pytest.fixture(scope="session")
def external_user_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-user-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def user_email(user_email: EmailStr, external_user_email: EmailStr | None) -> EmailStr:
    """Overrides pytest_simcore.faker_users_data.user_email"""
    if external_user_email:
        print(
            f"📧 EXTERNAL `user_email` detected. Setting user_email={external_user_email}"
        )
        return external_user_email
    return user_email


@pytest.fixture(scope="session")
def external_support_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-support-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def support_email(
    support_email: EmailStr, external_support_email: EmailStr | None
) -> EmailStr:
    """Overrides pytest_simcore.faker_users_data.support_email"""
    if external_support_email:
        print(
            f"📧 EXTERNAL `support_email` detected. Setting support_email={external_support_email}"
        )
        return external_support_email
    return support_email


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(notifications_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir
