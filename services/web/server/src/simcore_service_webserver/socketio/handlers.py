""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import asyncio
import logging
from typing import Dict

from aiohttp import web
from socketio.exceptions import \
    ConnectionRefusedError as socket_io_connection_error

from .. import signals
from ..login.decorators import RQT_USERID_KEY, login_required
from ..resource_manager.websocket_manager import managed_resource
from .config import get_socket_server

ANONYMOUS_USER_ID = -1
_SOCKET_IO_AIOHTTP_REQUEST_KEY = "aiohttp.request"

log = logging.getLogger(__file__)

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
        raise socket_io_connection_error("authentification failed")

    return True

@login_required
async def authenticate_user(sid: str, app: web.Application, request: web.Request) -> None:
    """throws web.HTTPUnauthorized when the user is not recognized. Keeps the original request.
    """
    user_id = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    log.debug("client %s authenticated", user_id)
    tab_id = request.query.get("tabid", None)
    if not tab_id:
        log.error("Tab ID is not available!")
        raise web.HTTPUnauthorized(reason="missing tab id")

    with managed_resource(user_id, tab_id, app) as rt:
        sio = get_socket_server(app)
        # here we keep the original HTTP request in the socket session storage
        async with sio.session(sid) as socketio_session:
            socketio_session["user_id"] = user_id
            socketio_session["tab_id"] = tab_id
            socketio_session["request"] = request
        log.info("socketio connection from user %s", user_id)
        await rt.set_socket_id(sid)

@signals.observe(event=signals.SignalType.SIGNAL_USER_LOGOUT)
async def user_logged_out(user_id: str, app: web.Application):
    log.debug("user %s must be disconnected", user_id)    
    # find the sockets related to the user
    with managed_resource(user_id, None, app) as rt:
        sockets = await rt.find_socket_ids()    
    
        # give any other client a chance to logout properly
        sio = get_socket_server(app)
        logout_tasks = [sio.emit("logout", to=sid, data={"reason": "user logged out"}) for sid in sockets]
        await asyncio.gather(*logout_tasks, return_exceptions=True)
        # let the client react
        await asyncio.sleep(5)
        # ensure disconnection is effective
        sockets = await rt.find_socket_ids()
        disconnect_tasks = [sio.disconnect(sid=sid) for sid in sockets]
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)

async def disconnect(sid: str, app: web.Application):
    """socketio reserved handler for when the socket.io connection is disconnected.

    Arguments:
        sid {str} -- the socket ID
        app {web.Application} -- the aiohttp app
    """
    log.debug("client in room %s disconnecting", sid)
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        user_id = socketio_session["user_id"]
        tab_id = socketio_session["tab_id"]
        with managed_resource(user_id, tab_id, app) as rt:
            log.debug("client %s disconnected from room %s", user_id, sid)
            await rt.remove_socket_id()