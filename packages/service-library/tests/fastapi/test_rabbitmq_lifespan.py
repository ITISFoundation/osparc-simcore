# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator

import pytest
import servicelib.fastapi.rabbitmq_lifespan
import servicelib.rabbitmq
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.rabbitmq_lifespan import (
    RabbitMQConfigurationError,
    RabbitMQLifespanState,
    rabbitmq_connectivity_lifespan,
)
from servicelib.rabbitmq import rabbitmq_rpc_client_context
from settings_library.application import BaseApplicationSettings
from settings_library.rabbit import RabbitSettings


@pytest.fixture
def mock_rabbitmq_connection(mocker: MockerFixture) -> MockType:
    return mocker.patch.object(
        servicelib.fastapi.rabbitmq_lifespan,
        "wait_till_rabbitmq_responsive",
        return_value=mocker.AsyncMock(),
    )


@pytest.fixture
def mock_rabbitmq_rpc_client_class(mocker: MockerFixture) -> MockType:
    return mocker.patch.object(
        servicelib.rabbitmq._client_rpc,
        "RabbitMQRPCClient",
        return_value=mocker.AsyncMock(),
    )


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch, RabbitSettings.model_json_schema()["examples"][0]
    )


@pytest.fixture
def app_lifespan(
    app_environment: EnvVarsDict,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_rpc_client_class: MockType,
) -> LifespanManager:
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        RABBITMQ: RabbitSettings = Field(
            ..., json_schema_extra={"auto_default_from_env": True}
        )

    async def my_app_settings(app: FastAPI) -> AsyncIterator[State]:
        app.state.settings = AppSettings.create_from_envs()

        yield RabbitMQLifespanState(
            RABBIT_SETTINGS=app.state.settings.RABBITMQ,
        ).model_dump()

    async def my_app_rpc_server(app: FastAPI, state: State) -> AsyncIterator[State]:

        async with rabbitmq_rpc_client_context(
            "rpc_server", app.state.settings.RABBITMQ
        ) as rpc_server:
            app.state.rpc_server = rpc_server
            yield {}

    app_lifespan = LifespanManager()
    app_lifespan.add(my_app_settings)
    app_lifespan.add(rabbitmq_connectivity_lifespan)
    app_lifespan.add(my_app_rpc_server)

    assert not mock_rabbitmq_connection.called
    assert not mock_rabbitmq_rpc_client_class.called

    return app_lifespan


async def test_lifespan_rabbitmq_in_an_app(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_rpc_client_class: MockType,
    app_lifespan: LifespanManager,
):
    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ) as asgi_manager:
        # Verify that RabbitMQ responsiveness was checked
        mock_rabbitmq_connection.assert_called_once_with(
            app.state.settings.RABBITMQ.dsn
        )

        # Verify that RabbitMQ settings are in the lifespan manager state
        assert app.state.settings.RABBITMQ

    # No explicit shutdown logic for RabbitMQ in this case
    assert mock_rabbitmq_rpc_client_class.called


async def test_lifespan_rabbitmq_with_invalid_settings(
    is_pdb_enabled: bool,
):
    async def my_app_settings(app: FastAPI) -> AsyncIterator[State]:
        yield {"RABBIT_SETTINGS": None}

    app_lifespan = LifespanManager()
    app_lifespan.add(my_app_settings)
    app_lifespan.add(rabbitmq_connectivity_lifespan)

    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(RabbitMQConfigurationError, match="Invalid RabbitMQ") as excinfo:
        async with ASGILifespanManager(
            app,
            startup_timeout=None if is_pdb_enabled else 10,
            shutdown_timeout=None if is_pdb_enabled else 10,
        ):
            ...

    exception = excinfo.value
    assert isinstance(exception, RabbitMQConfigurationError)
    assert exception.validation_error
    assert exception.state["RABBIT_SETTINGS"] is None
