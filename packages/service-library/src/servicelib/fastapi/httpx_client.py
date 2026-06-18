import datetime
import logging
from collections.abc import AsyncIterator
from enum import StrEnum

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from servicelib.tracing import TracingConfig

from ..tracing import setup_httpx_client_tracing
from .lifespan_utils import PublisherLifespan, create_publisher_lifespan, lifespan_context

_logger = logging.getLogger(__name__)


class HttpxLifespanState(StrEnum):
    HTTPX_CLIENT = "httpx_client"


def _create_httpx_client_lifespan(
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
) -> PublisherLifespan:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            client: httpx.AsyncClient | None = None
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
                    await client.aclose()

    return _lifespan


def _create_httpx_lifespan_manager(
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
) -> LifespanManager[FastAPI]:
    httpx_lifespan_manager = LifespanManager()
    httpx_lifespan_manager.add(
        _create_httpx_client_lifespan(
            default_timeout=default_timeout,
            max_keepalive_connections=max_keepalive_connections,
            tracing_config=tracing_config,
        )
    )
    httpx_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=HttpxLifespanState.HTTPX_CLIENT,
            app_state_attr="httpx_client",
        )
    )
    return httpx_lifespan_manager


def configure_httpx_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
) -> None:
    app_lifespan.include(
        _create_httpx_lifespan_manager(
            default_timeout=default_timeout,
            max_keepalive_connections=max_keepalive_connections,
            tracing_config=tracing_config,
        )
    )


def get_httpx_client(app: FastAPI) -> httpx.AsyncClient:
    client = app.state.httpx_client
    assert isinstance(client, httpx.AsyncClient)  # nosec
    return client
