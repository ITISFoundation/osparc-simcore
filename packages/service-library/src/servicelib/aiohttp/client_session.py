from collections.abc import AsyncGenerator
from typing import cast

from aiohttp import ClientSession, ClientTimeout, web
from common_library.json_serialization import json_dumps

from ..utils import (
    get_http_client_request_aiohttp_connect_timeout,
    get_http_client_request_aiohttp_sock_connect_timeout,
    get_http_client_request_total_timeout,
)
from .application_keys import APP_CLIENT_SESSION_KEY


async def persistent_client_session(app: web.Application) -> AsyncGenerator[None, None]:
    """Ensures a single client session per application

    IMPORTANT: Use this function ONLY in cleanup context , i.e.
        app.cleanup_ctx.append(persistent_client_session)

    """
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/4628

    # ANE: it is important to have fast connection handshakes
    # also requests should be as fast as possible
    # some services are not that fast to  reply
    timeout_settings = ClientTimeout(
        total=get_http_client_request_total_timeout(),
        connect=get_http_client_request_aiohttp_connect_timeout(),
        sock_connect=get_http_client_request_aiohttp_sock_connect_timeout(),
    )

    async with ClientSession(
        timeout=timeout_settings,
        json_serialize=json_dumps,
    ) as session:
        app[APP_CLIENT_SESSION_KEY] = session
        yield


def get_client_session(app: web.Application) -> ClientSession:
    """Refers to the one-and-only client in the app"""
    assert APP_CLIENT_SESSION_KEY in app  # nosec
    return cast(ClientSession, app[APP_CLIENT_SESSION_KEY])


__all__: tuple[str, ...] = (
    "get_client_session",
    "persistent_client_session",
)
