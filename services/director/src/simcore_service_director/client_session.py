from aiohttp import ClientSession, ClientTimeout
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.utils import (
    get_http_client_request_aiohttp_connect_timeout,
    get_http_client_request_aiohttp_sock_connect_timeout,
    get_http_client_request_total_timeout,
)


def setup_client_session(app: FastAPI) -> None:
    async def on_startup() -> None:
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/4628

        # ANE: it is important to have fast connection handshakes
        # also requests should be as fast as possible
        # some services are not that fast to  reply
        timeout_settings = ClientTimeout(
            total=get_http_client_request_total_timeout(),
            connect=get_http_client_request_aiohttp_connect_timeout(),
            sock_connect=get_http_client_request_aiohttp_sock_connect_timeout(),
        )
        session = ClientSession(
            timeout=timeout_settings,
            json_serialize=json_dumps,
        )
        app.state.aiohttp_client_session = session

    async def on_shutdown() -> None:
        session = app.state.aiohttp_client_session
        assert isinstance(session, ClientSession)  # nosec
        await session.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_client_session(app: FastAPI) -> ClientSession:
    session = app.state.aiohttp_client_session
    assert isinstance(session, ClientSession)  # nosec
    return session
