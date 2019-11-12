""" socket io subsystem


"""
import logging

import socketio
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .config import (APP_CLIENT_SOCKET_REGISTRY_KEY,
                     APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME)
from .handlers import sio
from .registry import InMemoryUserSocketRegistry

log = logging.getLogger(__name__)

@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    sio.attach(app)
    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = InMemoryUserSocketRegistry()

# alias
setup_sockets = setup

__all__ = (
    "setup_sockets"
)
