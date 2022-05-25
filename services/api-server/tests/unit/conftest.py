# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterator, Iterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx._transports.asgi import ASGITransport

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
