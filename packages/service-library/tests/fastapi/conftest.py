# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.params import Query
from fastapi.routing import APIRouter
from pydantic.types import PositiveFloat
from _pytest.fixtures import FixtureRequest
from httpx import AsyncClient
from servicelib.fastapi import long_running
from typing import AsyncIterable


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def _get_root():
        return {"name": __name__, "timestamp": datetime.utcnow().isoformat()}

    @api_router.get("/data")
    def _get_data(x: PositiveFloat, y: int = Query(..., gt=3, lt=4)):
        pass

    _app = FastAPI()
    _app.include_router(api_router)

    return _app


@pytest.fixture(params=["", "/base-path", "/nested/path"])
def router_prefix(request: FixtureRequest) -> str:
    return request.param


@pytest.fixture
async def bg_task_app(router_prefix: str) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    long_running.setup_server(app, router_prefix=router_prefix)
    yield app


@pytest.fixture(scope="function")
async def async_client(bg_task_app: FastAPI) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        app=bg_task_app,
        base_url="http://backgroud.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client
