# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from asgi_lifespan import LifespanManager
from aws_library.kms import KMSNotConnectedError, SimcoreKMSAPI
from fastapi import FastAPI
from settings_library.kms import KMSSettings
from simcore_service_api_server.clients.kms import setup_kms


class _FakeSettings:
    """Minimal stand-in for ApplicationSettings - setup_kms() only reads API_SERVER_KMS."""

    def __init__(self, api_server_kms: KMSSettings | None) -> None:
        self.API_SERVER_KMS = api_server_kms


async def test_setup_kms_disabled_when_not_configured():
    app = FastAPI()
    app.state.settings = _FakeSettings(None)
    setup_kms(app)

    async with LifespanManager(app):
        assert app.state.kms_client is None


async def test_setup_kms_sets_client_when_kms_reachable(
    mocked_kms_server_settings: KMSSettings,
):
    app = FastAPI()
    app.state.settings = _FakeSettings(mocked_kms_server_settings)
    setup_kms(app)

    async with LifespanManager(app):
        assert isinstance(app.state.kms_client, SimcoreKMSAPI)
        assert await app.state.kms_client.ping() is True


async def test_setup_kms_raises_when_key_not_found(
    mocked_kms_server_settings: KMSSettings,
):
    """A wrongly configured (e.g. non-existent) KMS key must fail app startup, not start
    silently with encryption effectively broken."""
    unreachable_settings = mocked_kms_server_settings.model_copy(update={"KMS_KEY_ID": "does-not-exist"})

    app = FastAPI()
    app.state.settings = _FakeSettings(unreachable_settings)
    setup_kms(app)

    with pytest.raises(KMSNotConnectedError):
        async with LifespanManager(app):
            pytest.fail("app startup should have failed before entering the context")

    assert app.state.kms_client is None
