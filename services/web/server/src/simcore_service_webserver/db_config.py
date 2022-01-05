""" db subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

import trafaret as T
from aiohttp.web import Application
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

_PG_SCHEMA = T.Dict(
    {
        "database": T.String(),
        "user": T.String(),
        "password": T.String(),
        T.Key("minsize", default=1, optional=True): T.ToInt(),
        T.Key("maxsize", default=4, optional=True): T.ToInt(),
        "host": T.Or(T.String, T.Null),
        "port": T.Or(T.ToInt, T.Null),
        "endpoint": T.Or(T.String, T.Null),
    }
)

CONFIG_SECTION_NAME = "db"

schema = T.Dict(
    {
        T.Key("postgres"): _PG_SCHEMA,
        T.Key("enabled", default=True, optional=True): T.Bool(),
    }
)


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
