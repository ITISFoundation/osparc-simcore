# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
"""The `connect` handler must declare the signature python-socketio calls it with.

Since python-socketio 5.17 the server invokes `connect` as `(sid, environ, auth)`, where `auth` is
the payload of the client's CONNECT packet (Socket.IO v4), and retries with the legacy
`(sid, environ)` only when the first call raises TypeError (SEE
socketio/async_server.py `_handle_connect` in v5.18.1). A handler written for the legacy signature
keeps working, but it runs on the retry and never sees what the client sent. `_socket_io_handler`
passes `app` as a keyword to every registered handler, so a handler without `auth` collides on the
first call and the payload is lost.
"""

from unittest.mock import MagicMock

import pytest
import socketio.exceptions  # type: ignore[import-untyped]
from simcore_service_webserver.socketio import _handlers
from simcore_service_webserver.socketio._utils import _socket_io_handler


@pytest.mark.parametrize(
    "auth",
    [None, {"token": "the-handler-does-not-read-it-yet"}],
    ids=["client_sends_no_payload", "client_sends_payload"],
)
async def test_connect_handler_accepts_the_auth_argument(auth: object | None):
    # the app is never used: authentication happens on the request before the app is touched
    connect_handler = _socket_io_handler(MagicMock())(_handlers.connect)

    # an empty environ makes the handler refuse, which is how this test tells "ran the body"
    # apart from "failed to bind the arguments", the latter raising a plain TypeError
    with pytest.raises(socketio.exceptions.ConnectionRefusedError, match=r"aiohttp\.request"):
        await connect_handler("socket-id", {}, auth)
