""" async client session


    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#persistent-session
"""
import logging
from collections.abc import MutableMapping
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

from ..json_serialization import json_dumps
from ..utils import (
    get_http_client_request_aiohttp_connect_timeout,
    get_http_client_request_aiohttp_sock_connect_timeout,
    get_http_client_request_total_timeout,
)
from .application_keys import APP_CLIENT_SESSION_KEY

_logger = logging.getLogger(__name__)

_PERSISTENT_CLIENT_SESSION_STATE = "{__name__}.persistent_client_session"


def get_client_session(app: MutableMapping[str, Any]) -> ClientSession:
    """Lazy initialization of ClientSession

    Ensures unique session
    """
    session = app.get(APP_CLIENT_SESSION_KEY)
    if session is None or session.closed:

        # Can be restarted if closed or not initialized,
        # but not if the session is done!
        if app.get(_PERSISTENT_CLIENT_SESSION_STATE, {}).get("done", False):
            msg = "Cannot create a new session after the application cleanup context is completed"
            raise RuntimeError(msg)

        # it is important to have fast connection handshakes
        # also requests should be as fast as possible
        # some services are not that fast to  reply
        # Setting the time of a request using this client session to 5 seconds totals
        timeout_settings = ClientTimeout(
            total=get_http_client_request_total_timeout(),
            connect=get_http_client_request_aiohttp_connect_timeout(),
            sock_connect=get_http_client_request_aiohttp_sock_connect_timeout(),
        )

        app[APP_CLIENT_SESSION_KEY] = session = ClientSession(
            timeout=timeout_settings,
            json_serialize=json_dumps,
        )
    return session


async def persistent_client_session(app: web.Application):
    """Ensures a single client session per application

    IMPORTANT: Use this function ONLY in cleanup context , i.e.
        app.cleanup_ctx.append(persistent_client_session)

    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#aiohttp-persistent-session
    """
    # lazy creation and holds reference to session at this point
    session = get_client_session(app)
    app[_PERSISTENT_CLIENT_SESSION_STATE] = {"done": False}

    yield

    # closes held session
    if session is not app.get(APP_CLIENT_SESSION_KEY):
        _logger.error(
            "Unexpected client session upon cleanup! expected %s, got %s",
            session,
            app.get(APP_CLIENT_SESSION_KEY),
        )

    await session.close()
    assert session.closed  # nosec
    app[_PERSISTENT_CLIENT_SESSION_STATE]["done"] = True


__all__: tuple[str, ...] = (
    "APP_CLIENT_SESSION_KEY",
    "get_client_session",
    "persistent_client_session",
)
