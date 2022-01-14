""" storage subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional, Tuple

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from pydantic import AnyHttpUrl, BaseSettings, Field, validator

from .storage_config import get_storage_config


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


def assert_valid_config(app: web.Application) -> Tuple[Dict, StorageSettings]:
    cfg = get_storage_config(app)
    settings = StorageSettings(**cfg)
    return cfg, settings
