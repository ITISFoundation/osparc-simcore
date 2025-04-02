import datetime

import httpx
from fastapi import FastAPI


def setup_client_session(
    app: FastAPI,
    *,
    default_timeout: datetime.timedelta = datetime.timedelta(seconds=20),
    max_keepalive_connections: int = 20
) -> None:
    async def on_startup() -> None:
        session = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(http2=True),
            limits=httpx.Limits(max_keepalive_connections=max_keepalive_connections),
            timeout=default_timeout.total_seconds(),
        )
        app.state.aiohttp_client_session = session

    async def on_shutdown() -> None:
        session = app.state.aiohttp_client_session
        assert isinstance(session, httpx.AsyncClient)  # nosec
        await session.aclose()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_client_session(app: FastAPI) -> httpx.AsyncClient:
    session = app.state.aiohttp_client_session
    assert isinstance(session, httpx.AsyncClient)  # nosec
    return session
