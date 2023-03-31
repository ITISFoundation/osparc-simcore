""" socketio subsystem based on socket-io
    and https://github.com/miguelgrinberg/python-socketio

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import handlers, handlers_utils
from .server import setup_socketio_server

log = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.socketio",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SOCKETIO",
    logger=log,
)
def setup_socketio(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_SOCKETIO  # nosec

    setup_socketio_server(app)
    handlers_utils.register_handlers(app, handlers)


__all__: tuple[str, ...] = (
    "setup_socketio",
    "setup_socketio_server",
)
