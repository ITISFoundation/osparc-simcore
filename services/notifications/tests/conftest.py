# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from models_library.basic_types import BootModeEnum
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.logging",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture,
    is_external_user_email: EmailStr | None,
    user_email: EmailStr,
) -> AsyncMock | None:
    """Mocks the underlying SMTP client unless tests are configured to send to an external email.

    Returns the inner ``AsyncMock`` representing the SMTP session yielded by
    ``simcore_service_notifications.clients.smtp.create_session``, so tests can
    assert calls like ``smtp_mock_or_none.send_message`` directly.
    """
    if is_external_user_email:
        print("🚨 Emails might be sent to", f"{user_email=}")
        return None

    mock_smtp = AsyncMock()
    mock_smtp_class = mocker.patch("simcore_service_notifications.clients.smtp.SMTP")
    mock_smtp_class.return_value.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_smtp_class.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_smtp


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "notifications"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_notifications"))
    return service_folder


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "LOGLEVEL": "DEBUG",
            "SC_BOOT_MODE": BootModeEnum.DEBUG,
        },
    )
