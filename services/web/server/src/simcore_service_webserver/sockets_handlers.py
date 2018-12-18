""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import logging

import socketio

# TODO: this is the only config that is not part of the schema
# At first sight, adding it would require refactorin how socketio
# is setup and avoid sio as a singleton!

log = logging.getLogger(__file__)

# TODO: separate API from server application!
sio = socketio.AsyncServer(async_mode="aiohttp", logging=log)


@sio.on("connect")
def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    log.debug("client %s connects", sid)
    return True


@sio.on("disconnect")
async def disconnect(sid):
    log.debug("client %s disconnected", sid)
