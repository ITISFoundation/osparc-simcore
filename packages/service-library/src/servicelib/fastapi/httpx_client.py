import datetime
import logging
from collections.abc import AsyncIterator
from enum import StrEnum

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from servicelib.tracing import TracingConfig

from ..tracing import setup_httpx_client_tracing
from .lifespan_utils import StatefulLifespan, lifespan_context

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


def _create_httpx_client_lifespan(
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
) -> StatefulLifespan:
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


def _create_httpx_default_publisher_lifespan(
    state_key: HttpxLifespanState = HttpxLifespanState.HTTPX_CLIENT,
    app_state_attr: str = "httpx_client",
) -> StatefulLifespan:
    async def _publisher_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}.{_publisher_lifespan.__name__}"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            client = state.get(state_key)
            if not isinstance(client, httpx.AsyncClient):
                msg = f"HTTPX client not found in lifespan state under key '{state_key}'"
                raise TypeError(msg)

            setattr(app.state, app_state_attr, client)
            yield called_state

    return _publisher_lifespan


def create_httpx_lifespan_manager(
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20,
    tracing_config: TracingConfig | None = None,
    publisher_lifespan: StatefulLifespan | None = None,
) -> LifespanManager[FastAPI]:
    httpx_lifespan_manager = LifespanManager()
    httpx_lifespan_manager.add(
        _create_httpx_client_lifespan(
            default_timeout=default_timeout,
            max_keepalive_connections=max_keepalive_connections,
            tracing_config=tracing_config,
        )
    )
    httpx_lifespan_manager.add(publisher_lifespan or _create_httpx_default_publisher_lifespan())
    return httpx_lifespan_manager


def get_httpx_client(app: FastAPI) -> httpx.AsyncClient:
    client = app.state.httpx_client
    assert isinstance(client, httpx.AsyncClient)  # nosec
    return client
