# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from asgi_lifespan import LifespanManager
from aws_library.kms import KMSNotConnectedError, SimcoreKMSAPI
from fastapi import FastAPI
from pytest_mock import MockerFixture
from servicelib.fastapi.lifespan_utils import configure_app_lifespan
from settings_library.kms import KMSSettings
from simcore_service_api_server.clients.kms import configure_kms


class _FakeSettings:
    """Minimal stand-in for ApplicationSettings - KMS only reads API_SERVER_KMS."""

    def __init__(self, api_server_kms: KMSSettings | None) -> None:
        self.API_SERVER_KMS = api_server_kms


def _create_app(settings: _FakeSettings) -> FastAPI:
    with configure_app_lifespan(started_banner="", starting_banner="") as app_lifespan:
        app = FastAPI(lifespan=app_lifespan)
        app.state.settings = settings
        configure_kms(app_lifespan)
    return app


async def test_configure_kms_disabled_when_not_configured():
    app = _create_app(_FakeSettings(None))

    async with LifespanManager(app):
        assert app.state.kms_client is None


async def test_configure_kms_sets_client_when_kms_reachable(
    mocked_kms_server_settings: KMSSettings,
):
    app = _create_app(_FakeSettings(mocked_kms_server_settings))

    async with LifespanManager(app):
        assert isinstance(app.state.kms_client, SimcoreKMSAPI)
        assert await app.state.kms_client.ping() is True


async def test_configure_kms_closes_client_when_ping_raises(
    mocked_kms_server_settings: KMSSettings,
    mocker: MockerFixture,
):
    kms_client = mocker.AsyncMock(spec=SimcoreKMSAPI)
    kms_client.ping.side_effect = RuntimeError("ping failed")
    mocker.patch(
        "simcore_service_api_server.clients.kms.SimcoreKMSAPI.create",
        return_value=kms_client,
    )
    app = _create_app(_FakeSettings(mocked_kms_server_settings))

    with pytest.raises(RuntimeError, match="ping failed"):
        async with LifespanManager(app):
            pytest.fail("app startup should have failed before entering the context")

    kms_client.close.assert_awaited_once_with()
    assert app.state.kms_client is None


async def test_configure_kms_raises_when_key_not_found(
    mocked_kms_server_settings: KMSSettings,
):
    """A wrongly configured (e.g. non-existent) KMS key must fail app startup, not start
    silently with encryption effectively broken."""
    unreachable_settings = mocked_kms_server_settings.model_copy(update={"KMS_KEY_ID": "does-not-exist"})

    app = _create_app(_FakeSettings(unreachable_settings))

    with pytest.raises(KMSNotConnectedError):
        async with LifespanManager(app):
            pytest.fail("app startup should have failed before entering the context")

    assert app.state.kms_client is None
