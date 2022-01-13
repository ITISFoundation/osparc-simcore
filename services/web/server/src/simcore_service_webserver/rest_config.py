""" rest subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

import trafaret as T
from aiohttp import web
from models_library.basic_types import VersionTag
from pydantic import BaseSettings, Field

from ._constants import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from ._meta import API_VTAG

CONFIG_SECTION_NAME = "rest"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        "version": T.Enum("v0"),
    }
)


class RestApiSettings(BaseSettings):
    enabled: Optional[bool] = True
    vtag: VersionTag = Field(
        API_VTAG, alias="version", description="web-server API's version tag"
    )


def get_rest_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def assert_valid_config(app: web.Application) -> Dict:
    cfg = get_rest_config(app)
    _settings = RestApiSettings(**cfg)
    return cfg


__all__ = ["APP_OPENAPI_SPECS_KEY"]
