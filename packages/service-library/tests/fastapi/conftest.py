# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import socket
from collections.abc import AsyncIterator, Callable, Iterator
from typing import cast

import arrow
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.params import Query
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic.types import PositiveFloat
from pytest_mock import MockerFixture


@pytest.fixture
def app() -> FastAPI:

    api_router = APIRouter()

    @api_router.get("/")
    def _get_root():
        return {"name": __name__, "timestamp": arrow.utcnow().datetime.isoformat()}

    @api_router.get("/data")
    def _get_data(x: PositiveFloat, y: int = Query(..., gt=3, lt=4)):
        pass

    _app = FastAPI()
    _app.include_router(api_router)

    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture(params=["", "/base-path", "/nested/path"])
def router_prefix(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def get_unused_port() -> Callable[[], int]:
    def go() -> int:
        """Return a port that is unused on the current host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return cast(int, s.getsockname()[1])

    return go


@pytest.fixture
def mock_otel_collector(mocker: MockerFixture) -> Iterator[InMemorySpanExporter]:
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    mocker.patch(
        "servicelib.fastapi.tracing._create_span_processor", return_value=span_processor
    )
    yield memory_exporter
