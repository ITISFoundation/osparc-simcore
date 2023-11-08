from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with AsyncClient(
        app=app,
        base_url="http://payments.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as httpx_client:
        # pylint:disable=protected-access
        assert isinstance(httpx_client._transport, ASGITransport)  # noqa: SLF001
        yield httpx_client
