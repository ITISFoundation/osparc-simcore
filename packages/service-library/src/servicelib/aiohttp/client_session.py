""" async client session


    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#persistent-session
"""
import logging
from typing import Any, MutableMapping

from aiohttp import ClientSession, ClientTimeout, web

from ..json_serialization import json_dumps
from ..utils import (
    get_http_client_request_aiohttp_connect_timeout,
    get_http_client_request_aiohttp_sock_connect_timeout,
    get_http_client_request_total_timeout,
)
from .application_keys import APP_CLIENT_SESSION_KEY

log = logging.getLogger(__name__)


def get_client_session(app: MutableMapping[str, Any]) -> ClientSession:
    """Lazy initialization of ClientSession

    Ensures unique session
    """
    session = app.get(APP_CLIENT_SESSION_KEY)
    if session is None or session.closed:
        # it is important to have fast connection handshakes
        # also requests should be as fast as possible
        # some services are not that fast to  reply
        # Setting the time of a request using this client session to 5 seconds totals
        timeout_settings = ClientTimeout(
            total=get_http_client_request_total_timeout(),
            connect=get_http_client_request_aiohttp_connect_timeout(),
            sock_connect=get_http_client_request_aiohttp_sock_connect_timeout(),
        )  # type: ignore

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
    log.info("Starting session %s", session)

    yield

    # closes held session
    if session is not app.get(APP_CLIENT_SESSION_KEY):
        log.error(
            "Unexpected client session upon cleanup! expected %s, got %s",
            session,
            app.get(APP_CLIENT_SESSION_KEY),
        )

    await session.close()
    assert session.closed  # nosec


# FIXME: if get_client_session upon startup fails and session is NOT closed. Implement some kind of gracefull shutdonw https://docs.aiohttp.org/en/latest/client_advanced.html#graceful-shutdown
# TODO: add some tests


__all__ = ["APP_CLIENT_SESSION_KEY", "get_client_session", "persistent_client_session"]
