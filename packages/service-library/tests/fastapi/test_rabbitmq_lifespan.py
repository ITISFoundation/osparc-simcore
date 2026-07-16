# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import servicelib.fastapi.rabbitmq_lifespan
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client,
    configure_rabbitmq_rpc_client,
)
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
def mock_rabbitmq_client_class(mocker: MockerFixture) -> MockType:
    mock_client_instance = mocker.AsyncMock()
    mock_client_instance.close = mocker.AsyncMock()
    return mocker.patch.object(
        servicelib.fastapi.rabbitmq_lifespan,
        "RabbitMQClient",
        return_value=mock_client_instance,
    )


@pytest.fixture
def mock_rabbitmq_rpc_client_create(mocker: MockerFixture) -> MockType:
    mock_rpc_client_instance = mocker.AsyncMock()
    mock_rpc_client_instance.close = mocker.AsyncMock()
    return mocker.patch.object(
        servicelib.fastapi.rabbitmq_lifespan.RabbitMQRPCClient,
        "create",
        return_value=mock_rpc_client_instance,
    )


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, RabbitSettings.model_json_schema()["examples"][0])


async def test_configure_rabbitmq_client_publishes_client_in_app_state(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_client_class: MockType,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        RABBITMQ: RabbitSettings = Field(..., json_schema_extra={"auto_default_from_env": True})

    settings = AppSettings.create_from_envs()

    app_lifespan = LifespanManager()
    configure_rabbitmq_client(
        app_lifespan,
        settings=settings.RABBITMQ,
        client_name="test_rabbit_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        mock_rabbitmq_connection.assert_called_once_with(
            settings.RABBITMQ.dsn  # pylint: disable=no-member
        )
        mock_rabbitmq_client_class.assert_called_once_with(
            client_name="test_rabbit_client",
            settings=settings.RABBITMQ,
        )
        assert app.state.rabbitmq_client == mock_rabbitmq_client_class.return_value

    mock_rabbitmq_client_class.return_value.close.assert_called_once()


async def test_configure_rabbitmq_rpc_client_publishes_rpc_client_in_app_state(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_rpc_client_create: MockType,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        RABBITMQ: RabbitSettings = Field(..., json_schema_extra={"auto_default_from_env": True})

    settings = AppSettings.create_from_envs()

    app_lifespan = LifespanManager()
    configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings.RABBITMQ,
        client_name="test_rabbit_rpc_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        mock_rabbitmq_connection.assert_called_once_with(
            settings.RABBITMQ.dsn  # pylint: disable=no-member
        )
        mock_rabbitmq_rpc_client_create.assert_called_once_with(
            client_name="test_rabbit_rpc_client",
            settings=settings.RABBITMQ,
        )
        assert app.state.rabbitmq_rpc_client == mock_rabbitmq_rpc_client_create.return_value

    mock_rabbitmq_rpc_client_create.return_value.close.assert_called_once()


async def test_configure_rabbitmq_client_with_none_settings(
    is_pdb_enabled: bool,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_client_class: MockType,
):
    app_lifespan = LifespanManager()
    configure_rabbitmq_client(
        app_lifespan,
        settings=None,
        client_name="disabled_rabbit_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        assert app.state.rabbitmq_client is None

    mock_rabbitmq_connection.assert_not_called()
    mock_rabbitmq_client_class.assert_not_called()


async def test_configure_rabbitmq_rpc_client_with_none_settings(
    is_pdb_enabled: bool,
    mock_rabbitmq_connection: MockType,
    mock_rabbitmq_rpc_client_create: MockType,
):
    app_lifespan = LifespanManager()
    configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=None,
        client_name="disabled_rabbit_rpc_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        assert app.state.rabbitmq_rpc_client is None

    mock_rabbitmq_connection.assert_not_called()
    mock_rabbitmq_rpc_client_create.assert_not_called()
