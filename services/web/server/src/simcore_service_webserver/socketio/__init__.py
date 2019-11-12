""" socket io subsystem


"""
import logging

from aiohttp import web
from socketio import AsyncAioPikaManager, AsyncServer

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .config import (APP_CLIENT_SOCKET_REGISTRY_KEY,
                     APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME)
from .handlers import register_handlers
from .registry import InMemoryUserSocketRegistry

log = logging.getLogger(__name__)

@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    mgr = None
    if CONFIG_SECTION_NAME in app[APP_CONFIG_KEY]:
        cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
        if "message_queue" in cfg and cfg["message_queue"]:
            mq_config = cfg["message_queue"]
            url = f"amqp://{mq_config['user']}:{mq_config['password']}@{mq_config['host']}:{mq_config['port']}"
            mgr = AsyncAioPikaManager(url=url, logger=log)

    sio = AsyncServer(async_mode="aiohttp", client_manager=mgr, logging=log)
    sio.attach(app)
    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = InMemoryUserSocketRegistry()
    register_handlers(app)

# alias
setup_sockets = setup
__all__ = (
    "setup_sockets"
)
