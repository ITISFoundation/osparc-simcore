""" db subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

from simcore_sdk.config.db import CONFIG_SCHEMA as _PG_SCHEMA
from models_library.settings import PostgresSettings
from pydantic import BaseSettings

CONFIG_SECTION_NAME = "db"

schema = T.Dict(
    {
        T.Key("postgres"): _PG_SCHEMA,
        T.Key("enabled", default=True, optional=True): T.Bool(),
    }
)


class DBSettings(BaseSettings):
    enabled: bool = True
    postgres: PostgresSettings
