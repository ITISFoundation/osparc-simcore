""" socketio subsystem based on socket-io
    and https://github.com/miguelgrinberg/python-socketio

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from socketio import AsyncServer

from . import handlers, handlers_utils
from .config import APP_CLIENT_SOCKET_SERVER_KEY, assert_valid_config

log = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.socketio", ModuleCategory.SYSTEM, logger=log
)
def setup_socketio(app: web.Application):
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
    sio = AsyncServer(async_mode="aiohttp", client_manager=None, logging=log)
    sio.attach(app)

    # FIXME: cleanup sio??

    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    handlers_utils.register_handlers(app, handlers)
