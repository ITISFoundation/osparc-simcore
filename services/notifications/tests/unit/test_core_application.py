# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_notifications.core.application import create_app

_POSTGRES_DEPENDENT_PLUGINS: tuple[str, ...] = (
    "configure_postgres_database",
    "configure_postgres_liveness",
    "configure_rabbitmq_client",
    "configure_rpc_api",
)

_ALWAYS_CONFIGURED_PLUGINS: tuple[str, ...] = (
    "configure_smtp_config_check",
    "configure_redis_client",
    "configure_task_manager",
)


@pytest.fixture
def mocked_plugins(mocker: MockerFixture) -> dict[str, MagicMock]:
    return {
        name: mocker.patch(f"simcore_service_notifications.core.application.{name}")
        for name in (*_POSTGRES_DEPENDENT_PLUGINS, *_ALWAYS_CONFIGURED_PLUGINS)
    }


def test_worker_mode_skips_postgres_setup(
    mock_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    mocked_plugins: dict[str, MagicMock],
):
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "true")

    create_app()

    for name in _POSTGRES_DEPENDENT_PLUGINS:
        mocked_plugins[name].assert_not_called()
    for name in _ALWAYS_CONFIGURED_PLUGINS:
        mocked_plugins[name].assert_called_once()


def test_server_mode_initializes_postgres_setup(
    mock_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    mocked_plugins: dict[str, MagicMock],
):
    monkeypatch.setenv("NOTIFICATIONS_WORKER_MODE", "false")

    create_app()

    for name in (*_POSTGRES_DEPENDENT_PLUGINS, *_ALWAYS_CONFIGURED_PLUGINS):
        mocked_plugins[name].assert_called_once()
