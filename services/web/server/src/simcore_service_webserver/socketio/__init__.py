""" socket io subsystem


"""
import logging

from aiohttp import web
from socketio import AsyncAioPikaManager, AsyncServer

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .config import (APP_CLIENT_SOCKET_REGISTRY_KEY,
                     APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME)
from .registry import InMemoryUserSocketRegistry

log = logging.getLogger(__name__)

# TODO: how this is supposed to be handled in aiohttp no singleton policy is currently unclear
sio = AsyncServer(async_mode="aiohttp", logging=log)

@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    sio.attach(app)
    from .handlers import register_handlers
    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = InMemoryUserSocketRegistry()

# alias
setup_sockets = setup
__all__ = (
    "setup_sockets"
    "sio"
)
