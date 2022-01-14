""" socketio subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from pydantic import BaseSettings

from .config import get_config


class SocketIOSettings(BaseSettings):
    enabled: Optional[bool] = True


def assert_valid_config(app: Application) -> Dict:
    cfg = get_config(app)
    _settings = SocketIOSettings(**cfg)
    return cfg
