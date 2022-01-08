from typing import Dict, Optional

from aiohttp.web import Application
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from socketio import AsyncServer

from ._contants import APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME


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
