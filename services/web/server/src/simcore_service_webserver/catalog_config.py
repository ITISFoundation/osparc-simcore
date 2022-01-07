""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
import os
from typing import Dict

import trafaret as T
from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings, Field
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "catalog"


_default_values = {
    "host": os.environ.get("CATALOG_HOST", "catalog"),
    "port": int(os.environ.get("CATALOG_PORT", 8000)),
}

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default=_default_values["host"]): T.String(),
        T.Key("port", default=_default_values["port"]): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # catalog API version basepath
    }
)


class CatalogSettings(BaseSettings):
    enabled: bool = True
    host: str = "catalog"
    port: PortInt = 8000
    vtag: VersionTag = Field(
        "v0", alias="version", description="Catalog service API's version tag"
    )

    class Config:
        prefix = "CATALOG_"


def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def assert_valid_config(app: web.Application) -> Dict:
    cfg = get_config(app)
    _settings = CatalogSettings(**cfg)
    return cfg
