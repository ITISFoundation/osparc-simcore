# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_webserver.notifications._controller import _rest


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # Override app_environment to enable notifications with rabbitmq
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
        },
    )


@pytest.fixture
def mocked_notifications_rpc_client(
    mocker: MockerFixture,
) -> MockerFixture:
    """Mock RabbitMQ RPC calls for notifications templates"""

    # Mock the RPC interface functions
    mocker.patch(
        f"{_rest.__name__}.remote_preview_template",
        autospec=True,
    )

    mocker.patch(
        f"{_rest.__name__}.remote_search_templates",
        autospec=True,
    )

    return mocker
