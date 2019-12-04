""" socketio subsystem based on socket-io
    and https://github.com/miguelgrinberg/python-socketio

"""
import logging

from aiohttp import web
from socketio import AsyncAioPikaManager, AsyncServer

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from . import handlers, handlers_utils
from .config import (APP_CLIENT_SOCKET_REGISTRY_KEY,
                     APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME,
                     get_redis_client)
from .redis import setup_redis_client
from .registry import InMemoryUserSocketRegistry, RedisUserSocketRegistry

log = logging.getLogger(__name__)

@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    mgr = None
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    if "message_queue" in cfg and cfg["message_queue"]:
        mq_config = cfg["message_queue"]
        url = f"amqp://{mq_config['user']}:{mq_config['password']}@{mq_config['host']}:{mq_config['port']}"
        mgr = AsyncAioPikaManager(url=url, logger=log)

    sio = AsyncServer(async_mode="aiohttp", client_manager=mgr, logging=log)
    sio.attach(app)
    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    setup_redis_client(app)
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisUserSocketRegistry(app) if cfg["redis"]["enabled"] \
                                    else InMemoryUserSocketRegistry(app)
    handlers_utils.register_handlers(app, handlers)

# alias
setup_sockets = setup
__all__ = (
    "setup_sockets"
)
