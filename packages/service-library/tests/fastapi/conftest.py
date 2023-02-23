# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import socket
from datetime import datetime, timezone
from typing import AsyncIterable, Callable, cast

import pytest
from fastapi import FastAPI
from fastapi.params import Query
from fastapi.routing import APIRouter
from httpx import AsyncClient
from pydantic.types import PositiveFloat
from pytest import FixtureRequest
from servicelib.fastapi import long_running_tasks


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def _get_root():
        return {
            "name": __name__,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

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

    long_running_tasks.server.setup(app, router_prefix=router_prefix)
    yield app


@pytest.fixture(scope="function")
async def async_client(bg_task_app: FastAPI) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        app=bg_task_app,
        base_url="http://backgroud.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def get_unused_port() -> Callable[[], int]:
    def go() -> int:
        """Return a port that is unused on the current host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return cast(int, s.getsockname()[1])

    return go
