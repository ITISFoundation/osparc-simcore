# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from aws_library.ec2 import configure_ec2_client
from aws_library.ec2._errors import EC2NotConnectedError
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.application import BaseApplicationSettings
from settings_library.ec2 import EC2Settings


@pytest.fixture
def mock_ec2_client_create(mocker: MockerFixture) -> MockType:
    mock_ec2_client = mocker.AsyncMock()
    mock_ec2_client.ping = mocker.AsyncMock(return_value=True)
    mock_ec2_client.close = mocker.AsyncMock()
    return mocker.patch("aws_library.ec2._fastapi_lifespan.SimcoreEC2API.create", return_value=mock_ec2_client)


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, EC2Settings.model_json_schema()["examples"][0])


async def test_configure_ec2_client_publishes_client_in_app_state(
    app_environment: EnvVarsDict,
    mock_ec2_client_create: MockType,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        EC2_ACCESS: EC2Settings = Field(..., json_schema_extra={"auto_default_from_env": True})

    settings = AppSettings.create_from_envs()

    app_lifespan = LifespanManager()
    configure_ec2_client(
        app_lifespan,
        settings=settings.EC2_ACCESS,
        client_name="test_ec2_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
        mock_ec2_client_create.assert_called_once_with(settings.EC2_ACCESS)
        mock_ec2_client_create.return_value.ping.assert_called_once()
        assert app.state.ec2_client == mock_ec2_client_create.return_value

    mock_ec2_client_create.return_value.close.assert_called_once()


async def test_configure_ec2_client_with_none_settings(
    mock_ec2_client_create: MockType,
):
    app_lifespan = LifespanManager()
    configure_ec2_client(
        app_lifespan,
        settings=None,
        client_name="disabled_ec2_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
        assert app.state.ec2_client is None

    mock_ec2_client_create.assert_not_called()


async def test_configure_ec2_client_closes_client_if_ping_fails(
    app_environment: EnvVarsDict,
    mock_ec2_client_create: MockType,
    mocker: MockerFixture,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        EC2_ACCESS: EC2Settings = Field(..., json_schema_extra={"auto_default_from_env": True})

    class _SingleAttempt:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _SingleAsyncRetrying:
        def __aiter__(self):
            self._yielded = False
            return self

        async def __anext__(self) -> _SingleAttempt:
            if self._yielded:
                raise StopAsyncIteration
            self._yielded = True
            return _SingleAttempt()

    mocker.patch("aws_library.ec2._fastapi_lifespan.AsyncRetrying", return_value=_SingleAsyncRetrying())

    settings = AppSettings.create_from_envs()
    mock_ec2_client_create.return_value.ping.return_value = False

    app_lifespan = LifespanManager()
    configure_ec2_client(
        app_lifespan,
        settings=settings.EC2_ACCESS,
        client_name="test_ec2_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(EC2NotConnectedError):
        async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
            pytest.fail("lifespan startup should fail before entering the context")

    mock_ec2_client_create.assert_called_once_with(settings.EC2_ACCESS)
    mock_ec2_client_create.return_value.ping.assert_called_once()
    mock_ec2_client_create.return_value.close.assert_called_once()
