""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""

import logging
from typing import Any

from aiohttp import web
from servicelib.aiohttp.observer import emit
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.request_keys import RQT_USERID_KEY
from socketio.exceptions import ConnectionRefusedError as SocketIOConnectionError

from ..groups.api import list_user_groups
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import managed_resource
from ._utils import EnvironDict, SocketID, get_socket_server, register_socketio_handler
from .messages import SOCKET_IO_HEARTBEAT_EVENT, SocketMessageDict, send_messages

_logger = logging.getLogger(__name__)

ANONYMOUS_USER_ID = -1


def _get_user_id(request: web.Request) -> int:
    user_id = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    return int(user_id)


async def _set_user_in_rooms(
    sid: SocketID, app: web.Application, request: web.Request
) -> None:
    user_id = _get_user_id(request)
    primary_group, user_groups, all_group = await list_user_groups(app, user_id)
    groups = [primary_group] + user_groups + ([all_group] if bool(all_group) else [])
    sio = get_socket_server(app)
    for group in groups:
        sio.enter_room(sid, f"{group['gid']}")


@login_required
async def _authenticate_user(
    sid: SocketID, app: web.Application, request: web.Request
) -> None:
    """

    Raises:
        web.HTTPUnauthorized: when the user is not recognized. Keeps the original request
    """
    user_id = _get_user_id(request)
    _logger.debug("client %s authenticated", f"{user_id=}")
    client_session_id = request.query.get("client_session_id", None)
    if not client_session_id:
        _logger.error(
            "Tab ID is not available!", extra=get_log_record_extra(user_id=user_id)
        )
        raise web.HTTPUnauthorized(reason="missing tab id")

    sio = get_socket_server(app)
    # here we keep the original HTTP request in the socket session storage
    async with sio.session(sid) as socketio_session:
        socketio_session["user_id"] = user_id
        socketio_session["client_session_id"] = client_session_id
        socketio_session["request"] = request
    with managed_resource(user_id, client_session_id, app) as rt:
        _logger.info(
            "socketio connection from user %s",
            user_id,
            extra=get_log_record_extra(user_id=user_id),
        )
        await rt.set_socket_id(sid)


#
# socketio event handlers
#


@register_socketio_handler
async def connect(sid: SocketID, environ: EnvironDict, app: web.Application) -> bool:
    """socketio reserved handler for when the fontend connects through socket.io

    Arguments:
        sid -- the socket ID
        environ -- the WSGI environ, among other contains the original request
        app  -- the aiohttp app

    Raises:
        SocketIOConnectionError: HTTPUnauthorized
        SocketIOConnectionError: Unexpected error

    Returns:
        True if socket.io connection accepted
    """
    _logger.debug("client connecting in room %s", f"{sid=}")
    request: web.Request = environ["aiohttp.request"]
    try:
        await _authenticate_user(sid, app, request)
        await _set_user_in_rooms(sid, app, request)
    except web.HTTPUnauthorized as exc:
        raise SocketIOConnectionError("authentification failed") from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise SocketIOConnectionError(f"Unexpected error: {exc}") from exc

    # Send service_deletion_timeout to client
    # 2 seconds avoids GC from removing the services to early
    # this has been tested and is working with good results
    # the previous implementation was not working as expected
    emit_interval: int = 2
    _logger.info("Sending set_heartbeat_emit_interval with %s", emit_interval)

    user_id = _get_user_id(request)
    heart_beat_messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_HEARTBEAT_EVENT,
            "data": {"interval": emit_interval},
        }
    ]
    await send_messages(
        app,
        user_id,
        heart_beat_messages,
    )

    return True


@register_socketio_handler
async def disconnect(sid: SocketID, app: web.Application) -> None:
    """socketio reserved handler for when the socket.io connection is disconnected.

    Arguments:
        sid -- the socket ID
        app -- the aiohttp app
    """
    _logger.debug("client in room %s disconnecting", sid)
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        if "user_id" in socketio_session:

            user_id = socketio_session["user_id"]
            client_session_id = socketio_session["client_session_id"]

            with log_context(
                _logger,
                logging.INFO,
                "disconnection of %s for %s",
                f"{user_id=}",
                f"{client_session_id=}",
            ):
                with managed_resource(user_id, client_session_id, app) as rt:
                    _logger.debug("client %s disconnected from room %s", user_id, sid)
                    await rt.remove_socket_id()
                # signal same user other clients if available
                await emit(
                    app, "SIGNAL_USER_DISCONNECTED", user_id, client_session_id, app
                )

        else:
            # this should not happen!!
            _logger.error(
                "Unknown client diconnected sid: %s, session %s",
                sid,
                f"{socketio_session}",
            )


@register_socketio_handler
async def client_heartbeat(sid: SocketID, _: Any, app: web.Application) -> None:
    """JS client invokes this handler to signal its presence.

    Each time this event is received the alive key's TTL is updated in
    Redis. Once the key expires, resources will be garbage collected.

    Arguments:
        sid-- the socket ID
        _  -- the data is ignored for this handler
        app  -- the aiohttp app
    """
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        if "user_id" not in socketio_session:
            return

        user_id = socketio_session["user_id"]
        client_session_id = socketio_session["client_session_id"]
        with managed_resource(user_id, client_session_id, app) as rt:
            await rt.set_heartbeat()
