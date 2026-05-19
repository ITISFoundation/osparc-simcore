import datetime

import httpx
from fastapi import FastAPI

from servicelib.tracing import TracingConfig

from ..tracing import setup_httpx_client_tracing


def setup_httpx_client(
    app: FastAPI,
    *,
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None,
) -> None:
    async def on_startup() -> None:
        client = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(http2=True),
            limits=httpx.Limits(max_keepalive_connections=max_keepalive_connections),
            timeout=default_timeout.total_seconds(),
        )
        if tracing_config:
            setup_httpx_client_tracing(client, tracing_config=tracing_config)
        app.state.httpx_client = client

    async def on_shutdown() -> None:
        client = app.state.httpx_client
        assert isinstance(client, httpx.AsyncClient)  # nosec
        await client.aclose()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_httpx_client(app: FastAPI) -> httpx.AsyncClient:
    client = app.state.httpx_client
    assert isinstance(client, httpx.AsyncClient)  # nosec
    return client
