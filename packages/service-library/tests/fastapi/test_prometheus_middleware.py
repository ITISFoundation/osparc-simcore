# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from httpx import AsyncClient
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from servicelib.fastapi.monitoring import (
    initialize_prometheus_instrumentation,
    prometheus_instrumentation_lifespan,
)


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    """
    Fixture that sets up the Prometheus middleware in the FastAPI app.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with asynccontextmanager(prometheus_instrumentation_lifespan)(app, {}):
            yield

    app = FastAPI(lifespan=lifespan)
    initialize_prometheus_instrumentation(app)

    @app.get("/dummy-endpoint")
    async def dummy_endpoint() -> PlainTextResponse:
        return PlainTextResponse("OK", media_type="text/plain")

    async with LifespanManager(app):
        yield app


async def test_metrics_endpoint(client: AsyncClient, app: FastAPI):
    """
    Test that the /metrics endpoint is available and returns Prometheus metrics.
    """
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == CONTENT_TYPE_LATEST
    assert "# HELP" in response.text
    assert "# TYPE" in response.text


async def test_asyncio_event_loop_tasks(client: AsyncClient, app: FastAPI):
    """
    Test that the /metrics endpoint is available and returns Prometheus metrics.
    """
    response = await client.get("/dummy-endpoint")
    assert response.status_code == 200

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == CONTENT_TYPE_LATEST
    assert "asyncio_event_loop_tasks" in response.text
