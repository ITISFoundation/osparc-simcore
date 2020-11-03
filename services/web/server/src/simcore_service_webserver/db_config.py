""" db subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

import trafaret as T
from aiohttp.web import Application
from pydantic import BaseSettings, constr
from typing import Optional

from models_library.settings.postgres import PostgresSettings
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_sdk.config.db import CONFIG_SCHEMA as _PG_SCHEMA

CONFIG_SECTION_NAME = "db"

schema = T.Dict(
    {
        T.Key("postgres"): _PG_SCHEMA,
        T.Key("enabled", default=True, optional=True): T.Bool(),
    }
)


class PgSettings(PostgresSettings):
    endpoint: Optional[constr(strip_whitespace=True, regex=r"\w+:\d+")] = None

    class Config:
        fields = {"db": "database"}


class DatabaseSettings(BaseSettings):
    enabled: bool = True
    postgres: PgSettings


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = DatabaseSettings(**cfg)
    return cfg
