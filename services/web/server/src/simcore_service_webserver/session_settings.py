""" session subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp.web import Application
from pydantic import BaseSettings, constr
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from .session_config import CONFIG_SECTION_NAME


class SessionSettings(BaseSettings):
    secret_key: constr(strip_whitespace=True, min_length=32)


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = SessionSettings(**cfg)
    return cfg
