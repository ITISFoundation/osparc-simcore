# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from aws_library.kms import configure_kms_client
from aws_library.kms._errors import KMSNotConnectedError
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.application import BaseApplicationSettings
from settings_library.kms import KMSSettings
from tenacity import AsyncRetrying, stop_after_attempt, wait_none


@pytest.fixture
def mock_kms_client_create(mocker: MockerFixture) -> MockType:
    mock_kms_client = mocker.AsyncMock()
    mock_kms_client.ping = mocker.AsyncMock(return_value=True)
    mock_kms_client.close = mocker.AsyncMock()
    return mocker.patch("aws_library.kms._fastapi_lifespan.SimcoreKMSAPI.create", return_value=mock_kms_client)


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, KMSSettings.model_json_schema()["examples"][0])


async def test_configure_kms_client_publishes_client_in_app_state(
    app_environment: EnvVarsDict,
    mock_kms_client_create: MockType,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        KMS_ACCESS: KMSSettings = Field(..., json_schema_extra={"auto_default_from_env": True})

    settings = AppSettings.create_from_envs()

    app_lifespan = LifespanManager()
    configure_kms_client(
        app_lifespan,
        settings=settings.KMS_ACCESS,
        client_name="test_kms_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
        mock_kms_client_create.assert_called_once_with(settings.KMS_ACCESS)
        mock_kms_client_create.return_value.ping.assert_called_once()
        assert app.state.kms_client == mock_kms_client_create.return_value

    mock_kms_client_create.return_value.close.assert_called_once()


async def test_configure_kms_client_with_none_settings(
    mock_kms_client_create: MockType,
):
    app_lifespan = LifespanManager()
    configure_kms_client(
        app_lifespan,
        settings=None,
        client_name="disabled_kms_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
        assert app.state.kms_client is None

    mock_kms_client_create.assert_not_called()


async def test_configure_kms_client_closes_client_if_ping_fails(
    app_environment: EnvVarsDict,
    mock_kms_client_create: MockType,
    mocker: MockerFixture,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        KMS_ACCESS: KMSSettings = Field(..., json_schema_extra={"auto_default_from_env": True})

    mocker.patch(
        "aws_library.kms._fastapi_lifespan.AsyncRetrying",
        return_value=AsyncRetrying(reraise=True, stop=stop_after_attempt(1), wait=wait_none()),
    )

    settings = AppSettings.create_from_envs()
    mock_kms_client_create.return_value.ping.return_value = False

    app_lifespan = LifespanManager()
    configure_kms_client(
        app_lifespan,
        settings=settings.KMS_ACCESS,
        client_name="test_kms_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(KMSNotConnectedError):
        async with ASGILifespanManager(app, startup_timeout=10, shutdown_timeout=10):
            pytest.fail("lifespan startup should fail before entering the context")

    mock_kms_client_create.assert_called_once_with(settings.KMS_ACCESS)
    mock_kms_client_create.return_value.ping.assert_called_once()
    mock_kms_client_create.return_value.close.assert_called_once()
