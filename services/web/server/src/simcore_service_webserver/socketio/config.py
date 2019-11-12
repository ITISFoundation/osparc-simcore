""" director subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

import trafaret as T
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from socketio import AsyncServer

CONFIG_SECTION_NAME = 'websocket'
APP_CLIENT_SOCKET_SERVER_KEY = __name__ + ".websocket_socketio"
APP_CLIENT_SOCKET_REGISTRY_KEY = __name__ + ".websocket_registry"

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Bool(),
})

def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]

def get_socket_registry(app: web.Application):
    return app[APP_CLIENT_SOCKET_REGISTRY_KEY]
