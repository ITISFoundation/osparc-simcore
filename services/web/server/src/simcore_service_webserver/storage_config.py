""" storage subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional, Tuple

import trafaret as T
from aiohttp import ClientSession, web
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings, Field, AnyHttpUrl, validator
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

    url: Optional[AnyHttpUrl] = None

    @validator("url", pre=True)
    @classmethod
    def autofill_dsn(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['vtag']}",
            )
        return v


def get_storage_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]


def assert_valid_config(app: web.Application) -> Tuple[Dict, StorageSettings]:
    cfg = get_storage_config(app)
    settings = StorageSettings(**cfg)
    return cfg, settings
