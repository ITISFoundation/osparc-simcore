from typing import Dict

from aiohttp import web
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings, Field
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "catalog"


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
