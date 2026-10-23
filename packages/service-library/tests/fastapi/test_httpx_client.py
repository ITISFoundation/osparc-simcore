# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from fastapi_lifespan_manager import LifespanManager as AppLifespanManager
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from servicelib.fastapi.httpx_client import configure_httpx_client, get_httpx_client
from servicelib.tracing import TracingConfig

_URL_PATH = "/foo"


@pytest.fixture
def get_app_with_httpx_client() -> Callable[..., FastAPI]:
    """Builds an app whose lifespan serves the shared client to `app.state`."""

    def _factory(*, tracing_config: TracingConfig | None) -> FastAPI:
        app_lifespan = AppLifespanManager[FastAPI]()
        configure_httpx_client(app_lifespan, tracing_config=tracing_config)
        return FastAPI(lifespan=app_lifespan)

    return _factory


async def test_lifespan_serves_mockable_client(
    get_app_with_httpx_client: Callable[..., FastAPI],
    mocked_server_api: respx.MockRouter,
    base_url: str,
):
    # NOTE: the client is built with an explicit `AsyncHTTPTransport`, so this also checks that
    # `respx` still intercepts it instead of the request reaching the network.
    app = get_app_with_httpx_client(tracing_config=None)

    async with LifespanManager(app, startup_timeout=None, shutdown_timeout=10):
        client = get_httpx_client(app)
        assert isinstance(client, httpx.AsyncClient)  # nosec

        # NOTE: the client has no `base_url`, hence callers pass absolute URLs
        response = await client.get(f"{base_url}{_URL_PATH}")

    assert response.status_code == status.HTTP_200_OK
    assert len(mocked_server_api.calls) == 1
    assert client.is_closed


async def test_lifespan_client_requests_emit_spans(
    get_app_with_httpx_client: Callable[..., FastAPI],
    mocked_server_api: respx.MockRouter,
    base_url: str,
    tracing_config_enabled: tuple[TracingConfig, InMemorySpanExporter],
):
    # NOTE: instrumenting the client is the only way outbound calls of every service using this
    # seam show up in traces, and it goes unnoticed if the instrumentor stops matching the client.
    tracing_config, span_exporter = tracing_config_enabled
    app = get_app_with_httpx_client(tracing_config=tracing_config)

    async with LifespanManager(app, startup_timeout=None, shutdown_timeout=10):
        await get_httpx_client(app).get(f"{base_url}{_URL_PATH}")

    client_spans = [span for span in span_exporter.get_finished_spans() if span.kind == SpanKind.CLIENT]
    assert [span.name for span in client_spans] == ["GET"]

    attributes = dict(client_spans[0].attributes or {})
    assert attributes.get("url.full", attributes.get("http.url")) == f"{base_url}{_URL_PATH}"
