# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from pathlib import Path
from typing import Any, Optional

import pytest
import simcore_service_invitations
import yaml
from cryptography.fernet import Fernet
from faker import Faker
from pytest import FixtureRequest, MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_invitations.invitations import InvitationInputs

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "invitations"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_invitations"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_invitations.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def services_docker_compose_specs(services_docker_compose_file: Path) -> dict[str, Any]:
    return yaml.safe_load(services_docker_compose_file.read_text())


@pytest.fixture
def openapi_specs(project_slug_dir: Path) -> dict[str, Any]:
    """
    Returns openapi.json
    """
    open_api_json_file = project_slug_dir / "openapi.json"
    return json.loads(open_api_json_file.read_text())


@pytest.fixture
def secret_key() -> str:
    key = Fernet.generate_key()
    return key.decode()


@pytest.fixture
def another_secret_key(secret_key: str) -> str:
    other = Fernet.generate_key()
    assert other.decode() != secret_key
    return other.decode()


@pytest.fixture(params=[True, False])
def auth_enabled(request: FixtureRequest) -> bool:
    """Enables/disables auth"""
    return request.param


@pytest.fixture
def fake_user_name(faker: Faker, auth_enabled: bool) -> Optional[str]:
    return faker.user_name() if auth_enabled else None


@pytest.fixture
def fake_password(faker: Faker, auth_enabled: bool) -> Optional[str]:
    return faker.password(length=10) if auth_enabled else None


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch,
    secret_key: str,
    fake_user_name: Optional[str],
    fake_password: Optional[str],
) -> EnvVarsDict:

    envs = setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_SECRET_KEY": secret_key,
            "INVITATIONS_OSPARC_URL": "https://myosparc.org",
            "INVITATIONS_USERNAME": fake_user_name or "null",
            "INVITATIONS_PASSWORD": fake_password or "null",
        },
    )

    return envs


@pytest.fixture(params=[True, False])
def is_trial_account(request: FixtureRequest) -> bool:
    """Enables/disables invitations with trial account"""
    return request.param


@pytest.fixture
def invitation_data(is_trial_account: bool, faker: Faker) -> InvitationInputs:
    return InvitationInputs(
        issuer="LicenseRequestID=123456789",
        guest=faker.email(),
        trial_account_days=faker.pyint(min_value=1) if is_trial_account else None,
    )
