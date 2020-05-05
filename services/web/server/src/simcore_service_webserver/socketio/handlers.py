""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import asyncio
import logging
from typing import Dict, List, Optional, Any

from aiohttp import web

from servicelib.observer import observe
from servicelib.utils import fire_and_forget_task, logged_gather
from socketio.exceptions import ConnectionRefusedError as SocketIOConnectionError

from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import managed_resource, get_registry
from ..resource_manager.config import get_service_deletion_timeout
from .config import get_socket_server
from .handlers_utils import register_socketio_handler
from .events import post_messages

ANONYMOUS_USER_ID = -1
_SOCKET_IO_AIOHTTP_REQUEST_KEY = "aiohttp.request"

log = logging.getLogger(__file__)


@register_socketio_handler
async def connect(sid: str, environ: Dict, app: web.Application) -> bool:
    """socketio reserved handler for when the fontend connects through socket.io

    Arguments:
        sid {str} -- the socket ID
        environ {Dict} -- the WSGI environ, among other contains the original request
        app {web.Application} -- the aiohttp app

    Returns:
        [type] -- True if socket.io connection accepted
    """
    log.debug("client connecting in room %s", sid)
    request = environ[_SOCKET_IO_AIOHTTP_REQUEST_KEY]
    try:
        await authenticate_user(sid, app, request)
    except web.HTTPUnauthorized:
        raise SocketIOConnectionError("authentification failed")
    except Exception as exc:  # pylint: disable=broad-except
        raise SocketIOConnectionError(f"Unexpected error: {exc}")

    # Send service_deletion_timeout to client
    # the interval should be < get_service_deletion_timeout(app) to avoid
    # issues, assuming half of the interval and not less the 2 seconds
    emit_interval: int = max(2, get_service_deletion_timeout(app) // 2)
    log.info("Sending set_heartbeat_emit_interval with %s", emit_interval)

    user_id = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    await post_messages(app, user_id, {'set_heartbeat_emit_interval': emit_interval})

    return True


@login_required
async def authenticate_user(
    sid: str, app: web.Application, request: web.Request
) -> None:
    """throws web.HTTPUnauthorized when the user is not recognized. Keeps the original request.
    """
    user_id = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    log.debug("client %s authenticated", user_id)
    client_session_id = request.query.get("client_session_id", None)
    if not client_session_id:
        log.error("Tab ID is not available!")
        raise web.HTTPUnauthorized(reason="missing tab id")

    with managed_resource(user_id, client_session_id, app) as rt:
        sio = get_socket_server(app)
        # here we keep the original HTTP request in the socket session storage
        async with sio.session(sid) as socketio_session:
            socketio_session["user_id"] = user_id
            socketio_session["client_session_id"] = client_session_id
            socketio_session["request"] = request
        log.info("socketio connection from user %s", user_id)
        await rt.set_socket_id(sid)


async def disconnect_other_sockets(sio, sockets: List[str]) -> None:
    log.debug("disconnecting sockets %s", sockets)
    logout_tasks = [
        sio.emit("logout", to=sid, data={"reason": "user logged out"})
        for sid in sockets
    ]
    await logged_gather(*logout_tasks, reraise=False)

    # let the client react
    await asyncio.sleep(3)
    # ensure disconnection is effective
    disconnect_tasks = [sio.disconnect(sid=sid) for sid in sockets]
    await logged_gather(*disconnect_tasks)


@observe(event="SIGNAL_USER_LOGOUT")
async def user_logged_out(
    user_id: str, client_session_id: Optional[str], app: web.Application
) -> None:
    log.debug("user %s must be disconnected", user_id)
    # find the sockets related to the user
    sio = get_socket_server(app)
    with managed_resource(user_id, client_session_id, app) as rt:
        # start by disconnecting this client if possible
        if client_session_id:
            socket_id = await rt.get_socket_id()
            if socket_id:
                await sio.disconnect(sid=socket_id)

        # now let's give a chance to all the clients to properly logout
        sockets = await rt.find_socket_ids()
        if sockets:
            # let's do it as a task so it does not block us here
            fire_and_forget_task(disconnect_other_sockets(sio, sockets))


@register_socketio_handler
async def disconnect(sid: str, app: web.Application) -> None:
    """socketio reserved handler for when the socket.io connection is disconnected.

    Arguments:
        sid {str} -- the socket ID
        app {web.Application} -- the aiohttp app
    """
    log.debug("client in room %s disconnecting", sid)
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        if "user_id" in socketio_session:
            user_id = socketio_session["user_id"]
            client_session_id = socketio_session["client_session_id"]
            with managed_resource(user_id, client_session_id, app) as rt:
                log.debug("client %s disconnected from room %s", user_id, sid)
                await rt.remove_socket_id()
        else:
            # this should not happen!!
            log.error(
                "Unknown client diconnected sid: %s, session %s",
                sid,
                str(socketio_session),
            )

@register_socketio_handler
async def client_heartbeat(sid: str, _: Any, app: web.Application) -> None:
    """JS client invokes this handler to signal its presence.

    Each time this event is received the alive key's TTL is updated in
    Redis. Once the key expires, resources will be garbage collected.

    Arguments:
        sid {str} -- the socket ID
        _ {Any} -- the data is ignored for this handler
        app {web.Application} -- the aiohttp app
    """
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        registry = get_registry(app)
        await registry.set_key_alive(
            socketio_session, False, get_service_deletion_timeout(app)
        )
