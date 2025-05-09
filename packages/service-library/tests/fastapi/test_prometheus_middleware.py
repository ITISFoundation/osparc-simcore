# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from collections.abc import AsyncIterable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from servicelib.fastapi.monitoring import setup_prometheus_instrumentation


@pytest.fixture
async def app(app: FastAPI) -> AsyncIterable[FastAPI]:
    """
    Fixture that sets up the Prometheus middleware in the FastAPI app.
    """
    setup_prometheus_instrumentation(app)
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
