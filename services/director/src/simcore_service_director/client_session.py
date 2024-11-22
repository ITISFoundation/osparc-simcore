import httpx
from fastapi import FastAPI


def setup_client_session(app: FastAPI) -> None:
    async def on_startup() -> None:
        session = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(http2=True))
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
