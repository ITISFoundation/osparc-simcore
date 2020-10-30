""" storage subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

import trafaret as T
from aiohttp import ClientSession, web
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings, Field
from servicelib.application_keys import APP_CLIENT_SESSION_KEY, APP_CONFIG_KEY

CONFIG_SECTION_NAME = "storage"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default="storage"): T.String(),
        T.Key("port", default=11111): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # storage API version basepath
    }
)


class StorageSettings(BaseSettings):
    enabled: Optional[bool] = True
    host: str = "storage"
    port: PortInt = 11111
    vtag: VersionTag = Field(
        "v0", alias="version", description="Storage service API's version tag"
    )


def get_storage_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]


def assert_valid_config(app: web.Application) -> Dict:
    cfg = get_storage_config(app)
    _settings = StorageSettings(**cfg)
    return cfg
