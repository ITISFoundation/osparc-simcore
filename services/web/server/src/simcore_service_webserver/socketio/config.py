""" websocket subsystem's configuration

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
APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = __name__ + ".websocket_handlers"

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.Int()),
    T.Key("message_queue", default=True, optional=True): T.Dict({
        T.Key("host", default='rabbit', optional=True): T.String(),
        T.Key("port", default=5672, optional=True): T.Int(),
        "user": T.String(),
        "password": T.String(),
        T.Key("channel", default="socketio"): T.String()
    }),
})

def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]

def get_socket_registry(app: web.Application):
    return app[APP_CLIENT_SOCKET_REGISTRY_KEY]
