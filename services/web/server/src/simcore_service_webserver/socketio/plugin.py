"""plugin socket-io


SEE https://github.com/miguelgrinberg/python-socketio
"""

import logging
from typing import Final

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..rabbitmq import setup_rabbitmq
from ._observer import setup_socketio_observer_events
from .server import setup_socketio_server

_logger = logging.getLogger(__name__)

APP_SOCKETIO_SERVER_KEY: Final = web.AppKey("APP_SOCKETIO_SERVER_KEY", object)  # socketio.AsyncServer


@app_setup_func(
    "simcore_service_webserver.socketio",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SOCKETIO",
    logger=_logger,
)
def setup_socketio(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_SOCKETIO  # nosec
    setup_rabbitmq(app)  # for horizontal scaling
    setup_socketio_server(app)
    setup_socketio_observer_events(app)


__all__: tuple[str, ...] = ("setup_socketio",)
