""" socketio subsystem based on socket-io
    and https://github.com/miguelgrinberg/python-socketio

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from socketio import AsyncServer

from .._constants import APP_SETTINGS_KEY
from . import handlers, handlers_utils
from .server import APP_CLIENT_SOCKET_SERVER_KEY

log = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.socketio", ModuleCategory.ADDON, logger=log
)
def setup_socketio(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_SOCKETIO  # nosec

    # SEE https://github.com/miguelgrinberg/python-socketio/blob/v4.6.1/docs/server.rst#aiohttp
    # TODO: ujson to speed up?
    # TODO: client_manager= to socketio.AsyncRedisManager/AsyncAioPikaManager for horizontal scaling (shared sessions)
    sio = AsyncServer(async_mode="aiohttp", logger=log, engineio_logger=False)
    sio.attach(app)

    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    handlers_utils.register_handlers(app, handlers)
