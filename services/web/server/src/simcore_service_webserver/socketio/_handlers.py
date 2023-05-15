""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""

import logging
from typing import Any

from aiohttp import web
from models_library.users import UserID
from servicelib.aiohttp.observer import emit
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.request_keys import RQT_USERID_KEY
from socketio.exceptions import ConnectionRefusedError as SocketIOConnectionError

from ..groups.api import list_user_groups
from ..login.decorators import login_required
from ..resource_manager.websocket_manager import managed_resource
from ._utils import EnvironDict, SocketID, get_socket_server, register_socketio_handler
from .messages import SOCKET_IO_HEARTBEAT_EVENT, SocketMessageDict, send_messages

_logger = logging.getLogger(__name__)

_ANONYMOUS_USER_ID = -1

# Messages reaching users
_MSG_UNAUTHORIZED_MISSING_SESSION_INFO = (
    "Sorry, we cannot identify you. Please reaload the page and login again."
)


# Send service_deletion_timeout to client
# 2 seconds avoids GC from removing the services to early
# this has been tested and is working with good results
# the previous implementation was not working as expected
_EMIT_INTERVAL_S: int = 2


@login_required
async def _authenticate_user(
    socket_id: SocketID, app: web.Application, request: web.Request
) -> UserID:
    """

    Raises:
        web.HTTPUnauthorized: when the user is not recognized. Keeps the original request
    """
    user_id = UserID(request.get(RQT_USERID_KEY, _ANONYMOUS_USER_ID))
    client_session_id = request.query.get("client_session_id", None)

    _logger.debug("client %s,%s authenticated", f"{user_id=}", f"{client_session_id=}")

    if not client_session_id:
        _logger.error("Tab ID is missing", extra=get_log_record_extra(user_id=user_id))
        raise web.HTTPUnauthorized(reason=_MSG_UNAUTHORIZED_MISSING_SESSION_INFO)

    # here we keep the original HTTP request in the socket session storage
    sio = get_socket_server(app)
    async with sio.session(socket_id) as socketio_session:
        socketio_session["user_id"] = user_id
        socketio_session["client_session_id"] = client_session_id
        socketio_session["request"] = request

    with managed_resource(user_id, client_session_id, app) as resource_registry:
        _logger.info(
            "socketio connection from user %s",
            user_id,
            extra=get_log_record_extra(user_id=user_id),
        )
        await resource_registry.set_socket_id(socket_id)

    return user_id


async def _set_user_in_group_rooms(
    app: web.Application, user_id: UserID, socket_id: SocketID
) -> None:
    """Adds user in rooms associated to its groups"""
    primary_group, user_groups, all_group = await list_user_groups(app, user_id)
    groups = [primary_group] + user_groups + ([all_group] if bool(all_group) else [])

    sio = get_socket_server(app)
    for group in groups:
        sio.enter_room(socket_id, f"{group['gid']}")


#
# socketio event handlers
#


@register_socketio_handler
async def connect(
    socket_id: SocketID, environ: EnvironDict, app: web.Application
) -> bool:
    """socketio reserved handler for when the fontend connects through socket.io

    Arguments:
        environ -- the WSGI environ, among other contains the original request

    Raises:
        SocketIOConnectionError: HTTPUnauthorized
        SocketIOConnectionError: Unexpected error

    Returns:
        True if socket.io connection accepted
    """
    _logger.debug("client connecting in room %s", f"{socket_id=}")

    try:
        user_id = await _authenticate_user(
            socket_id, app, request=environ["aiohttp.request"]
        )

        await _set_user_in_group_rooms(app, user_id, socket_id)

        _logger.info("Sending set_heartbeat_emit_interval with %s", _EMIT_INTERVAL_S)

        heart_beat_messages: list[SocketMessageDict] = [
            {
                "event_type": SOCKET_IO_HEARTBEAT_EVENT,
                "data": {"interval": _EMIT_INTERVAL_S},
            }
        ]
        await send_messages(
            app,
            user_id,
            heart_beat_messages,
        )

    except web.HTTPUnauthorized as exc:
        raise SocketIOConnectionError("authentification failed") from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise SocketIOConnectionError(f"Unexpected error: {exc}") from exc

    return True


@register_socketio_handler
async def disconnect(socket_id: SocketID, app: web.Application) -> None:
    """socketio reserved handler for when the socket.io connection is disconnected."""
    sio = get_socket_server(app)
    async with sio.session(socket_id) as socketio_session:
        if user_id := socketio_session.get("user_id"):
            client_session_id = socketio_session["client_session_id"]

            with log_context(
                _logger,
                logging.INFO,
                "disconnection of %s for %s",
                f"{user_id=}",
                f"{client_session_id=}",
            ):
                with managed_resource(
                    user_id, client_session_id, app
                ) as resource_registry:
                    await resource_registry.remove_socket_id()
                # signal same user other clients if available
                await emit(
                    app, "SIGNAL_USER_DISCONNECTED", user_id, client_session_id, app
                )

        else:
            # this should not happen!!
            _logger.error(
                "Unknown client diconnected sid: %s, session %s",
                socket_id,
                f"{socketio_session}",
            )


@register_socketio_handler
async def client_heartbeat(socket_id: SocketID, _: Any, app: web.Application) -> None:
    """JS client invokes this handler to signal its presence.

    Each time this event is received the alive key's TTL is updated in
    Redis. Once the key expires, resources will be garbage collected.

    Arguments:
        sid-- the socket ID
        _  -- the data is ignored for this handler
        app  -- the aiohttp app
    """
    sio = get_socket_server(app)
    async with sio.session(socket_id) as socketio_session:
        if user_id := socketio_session.get("user_id"):
            client_session_id = socketio_session["client_session_id"]

            with managed_resource(user_id, client_session_id, app) as rt:
                await rt.set_heartbeat()
