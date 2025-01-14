# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from servicelib.fastapi import long_running_tasks


@pytest.fixture
async def bg_task_app(router_prefix: str) -> FastAPI:
    app = FastAPI()

    long_running_tasks.server.setup(app, router_prefix=router_prefix)
    return app


@pytest.fixture
async def async_client(bg_task_app: FastAPI) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=bg_task_app),
        base_url="http://backgroud.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client
