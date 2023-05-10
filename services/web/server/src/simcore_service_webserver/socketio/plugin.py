""" plugin socket-io


    SEE https://github.com/miguelgrinberg/python-socketio
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import _handlers, _utils
from .server import setup_socketio_server

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.socketio",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SOCKETIO",
    logger=_logger,
)
def setup_socketio(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_SOCKETIO  # nosec

    setup_socketio_server(app)
    _utils.register_handlers(app, _handlers)


__all__: tuple[str, ...] = (
    "setup_socketio",
    "setup_socketio_server",
)
