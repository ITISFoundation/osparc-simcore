""" plugin socket-io


    SEE https://github.com/miguelgrinberg/python-socketio
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..rabbitmq import setup_rabbitmq
from ._observer import setup_socketio_observer_events
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
    setup_rabbitmq(app)  # for horizontal scaling
    setup_socketio_server(app)
    setup_socketio_observer_events(app)


__all__: tuple[str, ...] = ("setup_socketio",)
