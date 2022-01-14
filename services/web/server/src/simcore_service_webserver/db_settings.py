""" db subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from .db_config import CONFIG_SECTION_NAME


class PgSettings(PostgresSettings):
    endpoint: Optional[str] = None  # TODO: PC remove or deprecate that one

    class Config:
        fields = {"db": "database"}


class DatabaseSettings(BaseSettings):
    enabled: bool = True
    postgres: PgSettings


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = DatabaseSettings(**cfg)
    return cfg
