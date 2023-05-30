""" plugin socket-io


    SEE https://github.com/miguelgrinberg/python-socketio
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import _handlers
from ._observer import setup_socketio_observer_events
from ._utils import register_socketio_handlers
from .server import setup_socketio_server

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.socketio",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SOCKETIO",
    logger=_logger,
    depends=["simcore_service_webserver.rabbitmq"],
)
def setup_socketio(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_SOCKETIO  # nosec

    setup_socketio_server(app)
    register_socketio_handlers(app, _handlers)
    setup_socketio_observer_events(app)


__all__: tuple[str, ...] = (
    "setup_socketio",
    "setup_socketio_server",
)
