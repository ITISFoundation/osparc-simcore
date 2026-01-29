# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    # Override app_environment to enable notifications with rabbitmq
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
        },
    )


@pytest.fixture
def mocked_notifications_rpc_client(
    mocker: MockerFixture,
) -> MockerFixture:
    """Mock RabbitMQ RPC calls for notifications templates"""

    # Mock the RPC interface functions
    mocker.patch(
        "simcore_service_webserver.notifications._controller._rest.remote_preview_template",
        autospec=True,
    )

    mocker.patch(
        "simcore_service_webserver.notifications._controller._rest.remote_search_templates",
        autospec=True,
    )

    return mocker
