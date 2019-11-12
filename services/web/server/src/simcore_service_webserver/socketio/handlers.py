""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import logging

from aiohttp import web
from . import sio
from .. import signals
from ..login.decorators import RQT_USERID_KEY, login_required
from .config import get_socket_registry

ANONYMOUS_USER_ID = -1
_SOCKET_IO_AIOHTTP_REQUEST_KEY = "aiohttp.request"

log = logging.getLogger(__file__)

def register_handlers():
    # fake function to force registration of socket.io handlers
    pass

@sio.on('connect')
async def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    request = environ[_SOCKET_IO_AIOHTTP_REQUEST_KEY]
    try:
        await authenticate_user(sid, request)
    except web.HTTPUnauthorized:
        log.exception("Websocket connection unauthorized")
        return False

    log.debug("client %s connects", sid)
    return True

@login_required
async def authenticate_user(sid, request: web.Request) -> web.Response:
    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    app = request.app
    registry = get_socket_registry(app)
    registry.add_socket(userid, sid)

    async with sio.session(sid) as socketio_session:
        socketio_session["user_id"] = userid
        socketio_session["request"] = request
    log.info("websocket connection from user %s", userid)


@sio.on('disconnect')
async def disconnect(sid):
    async with sio.session(sid) as session:
        request = session["request"]
        app = request.app
        registry = get_socket_registry(app)
        #TODO: how to handle different sessions from the same user? (i.e. multiple tabs)
        if not registry.remove_socket(sid):
            # signal if no socket ids are left
            await signals.user_disconnected_event(request)
    log.debug("client %s disconnected", sid)
