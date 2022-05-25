# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pprint import pprint
from typing import AsyncIterator, Iterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx._transports.asgi import ASGITransport
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture(scope="session")
def default_test_env_vars() -> dict[str, str]:
    #
    pprint(list(ApplicationSettings.schema()["properties"].keys()))
    # [
    # 'SC_BOOT_MODE',
    # 'LOG_LEVEL',
    # 'API_SERVER_POSTGRES',
    # 'API_SERVER_WEBSERVER',
    # 'API_SERVER_CATALOG',
    # 'API_SERVER_STORAGE',
    # 'API_SERVER_DIRECTOR_V2',
    # 'API_SERVER_TRACING',
    # 'API_SERVER_DEV_FEATURES_ENABLED',
    # 'API_SERVER_REMOTE_DEBUG_PORT'
    # ]
    #
    return {
        "WEBSERVER_HOST": "webserver",
        "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
        "API_SERVER_POSTGRES": "null",
        "API_SERVER_TRACING": "null",
        "LOG_LEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }


## APP & TEST CLIENT ------


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch, default_test_env_vars: dict[str, str]
) -> FastAPI:
    from simcore_service_api_server.core.application import init_app

    # environ
    for key, value in default_test_env_vars.items():
        monkeypatch.setenv(key, value)

    app = init_app()
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            app=app,
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:

            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            setattr(client, "app", client._transport.app)

            yield client


@pytest.fixture
def sync_client(app: FastAPI) -> Iterator[TestClient]:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(
        app, base_url="http://api.testserver.io", raise_server_exceptions=True
    ) as cli:
        yield cli
