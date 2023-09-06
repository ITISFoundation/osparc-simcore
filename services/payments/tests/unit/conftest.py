# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx._transports.asgi import ASGITransport
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.core.application import create_app


@pytest.fixture
def app(app_environment: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #
    async with LifespanManager(app):
        # needed for app to trigger start/stop event handlers
        async with httpx.AsyncClient(
            app=app,
            base_url="http://payments.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:
            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            client.app = client._transport.app

            yield client
