import datetime
import logging
from collections.abc import AsyncIterator
from enum import StrEnum

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from servicelib.tracing import TracingConfig

from ..tracing import setup_httpx_client_tracing
from .lifespan_utils import lifespan_context

_logger = logging.getLogger(__name__)


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


class HttpxLifespanState(StrEnum):
    HTTPX_CLIENT = "httpx_client"


def create_httpx_lifespan(
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
) -> LifespanManager[FastAPI]:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            client = None
            try:
                client = httpx.AsyncClient(
                    transport=httpx.AsyncHTTPTransport(http2=True),
                    limits=httpx.Limits(max_keepalive_connections=max_keepalive_connections),
                    timeout=default_timeout.total_seconds(),
                )
                if tracing_config:
                    setup_httpx_client_tracing(client, tracing_config=tracing_config)

                yield {
                    HttpxLifespanState.HTTPX_CLIENT: client,
                    **called_state,
                }
            finally:
                if client is not None:
                    assert isinstance(client, httpx.AsyncClient)  # nosec
                    await client.aclose()

    httpx_lifespan_manager = LifespanManager()
    httpx_lifespan_manager.add(_lifespan)
    return httpx_lifespan_manager


def get_httpx_client(app: FastAPI) -> httpx.AsyncClient:
    client = app.state.httpx_client
    assert isinstance(client, httpx.AsyncClient)  # nosec
    return client
