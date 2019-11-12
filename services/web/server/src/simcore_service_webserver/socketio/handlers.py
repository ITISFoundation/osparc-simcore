""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import inspect
import logging
import sys
from functools import wraps
from typing import Dict

from aiohttp import web
from socketio import AsyncServer

from .. import signals
from ..login.decorators import RQT_USERID_KEY, login_required
from .config import get_socket_registry, get_socket_server, APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY

ANONYMOUS_USER_ID = -1
_SOCKET_IO_AIOHTTP_REQUEST_KEY = "aiohttp.request"

log = logging.getLogger(__file__)

def socket_io_handler(app: web.Application):
    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            return await func(*args, **kwargs, app=app)
        return wrapped
    return decorator

def has_socket_io_handler_signature(fun) -> bool:
    # last parameter is web.Application
    return any(param.annotation == web.Application
        for name, param in inspect.signature(fun).parameters.items())

def register_handlers(app: web.Application):
    sio = get_socket_server(app)
    this_module = sys.modules[__name__]
    predicate = lambda obj: inspect.isfunction(obj) and has_socket_io_handler_signature(obj) and inspect.iscoroutinefunction(obj) and inspect.getmodule(obj) == this_module
    member_fcts = inspect.getmembers(this_module, predicate)
    # convert handler
    partial_fcts = [socket_io_handler(app)(func_handler) for _, func_handler in member_fcts]
    app[APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY] = partial_fcts
    # register the fcts
    for func in partial_fcts:
        sio.on(func.__name__, handler=func)
    # partial_connect = socket_io_handler(app)(connect)
    # partial_disconnect = socket_io_handler(app)(disconnect)
    # sio.on("connect", handler=partial_connect)
    # sio.on("disconnect", handler=partial_disconnect)


async def connect(sid: str, environ: Dict, app: web.Application):
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
    sio = get_socket_server(app)
    async with sio.session(sid) as socketio_session:
        socketio_session["user_id"] = userid
        socketio_session["request"] = request
    log.info("websocket connection from user %s", userid)


async def disconnect(sid: str, app: web.Application):
    # async with sio.session(sid) as session:
    #     request = session["request"]
    #     app = request.app
    #     registry = get_socket_registry(app)
    #     #TODO: how to handle different sessions from the same user? (i.e. multiple tabs)
    #     if not registry.remove_socket(sid):
    #         # mark user for disconnection
    #         # signal if no socket ids are left
    #         await signals.user_disconnected_event(request)
    log.debug("client %s disconnected", sid)
