# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from fixtures.fake_services import PushServicesCallable, ServiceInRegistryInfoDict
from httpx._transports.asgi import ASGITransport


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with httpx.AsyncClient(
        app=app,
        base_url="http://director.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        assert isinstance(client._transport, ASGITransport)
        yield client


@pytest.fixture
async def created_services(
    push_services: PushServicesCallable,
) -> list[ServiceInRegistryInfoDict]:
    return await push_services(
        number_of_computational_services=3, number_of_interactive_services=2
    )
