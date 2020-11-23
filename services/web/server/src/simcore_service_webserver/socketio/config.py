""" socketio subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

import trafaret as T
from aiohttp.web import Application
from pydantic import BaseSettings
from servicelib.application_keys import APP_CONFIG_KEY
from socketio import AsyncServer

CONFIG_SECTION_NAME = "socketio"
APP_CLIENT_SOCKET_SERVER_KEY = __name__ + ".socketio_socketio"
APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = __name__ + ".socketio_handlers"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.ToInt()),
    }
)


class SocketIOSettings(BaseSettings):
    enabled: Optional[bool] = True


def get_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_socket_server(app: Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]


def assert_valid_config(app: Application) -> Dict:
    cfg = get_config(app)
    _settings = SocketIOSettings(**cfg)
    return cfg
