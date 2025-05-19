# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST,
)
from servicelib.aiohttp.monitoring import setup_monitoring


@pytest.fixture
def aiohttp_app_with_monitoring():
    app = web.Application()
    setup_monitoring(app, app_name="test_app")
    return app


@pytest.fixture
async def client(aiohttp_app_with_monitoring):
    async with TestServer(aiohttp_app_with_monitoring) as server:
        async with TestClient(server) as client:
            yield client


async def test_metrics_endpoint(client):
    response = await client.get("/metrics")
    assert response.status == 200
    assert response.headers["Content-Type"] == CONTENT_TYPE_LATEST
    body = await response.text()
    assert "# HELP" in body  # Check for Prometheus metrics format
