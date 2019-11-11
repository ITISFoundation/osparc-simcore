""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import logging

import socketio
from aiohttp import web

from ..login.decorators import RQT_USERID_KEY, login_required

ANONYMOUS_USER_ID = -1

# TODO: this is the only config that is not part of the schema
# At first sight, adding it would require refactorin how socketio
# is setup and avoid sio as a singleton!

log = logging.getLogger(__file__)

# TODO: separate API from server application!
sio = socketio.AsyncServer(async_mode="aiohttp",
    logger=log,
    cors_allowed_origins='*', # FIXME: deactivate when reverse proxy issue with traefik resolved
    engineio_logger=log)


@sio.on("connect")
async def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    request = environ["aiohttp.Request"]
    response = await socket_connect(request)
    log.debug("client %s connects", sid)
    return True

@login_required
async def socket_connect(request: web.Request) -> web.Response:
    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    log.info(8*"*")
    log.info("websocket connection from user %s", userid)

@sio.on("disconnect")
async def disconnect(sid):
    log.debug("client %s disconnected", sid)
