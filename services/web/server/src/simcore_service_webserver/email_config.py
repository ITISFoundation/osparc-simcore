""" email's subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from models_library.basic_types import PortInt
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "smtp"


class EmailSettings(BaseSettings):
    sender: str = "OSPARC support <support@osparc.io>"
    host: str
    port: PortInt
    tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = EmailSettings(**cfg)
    return cfg
