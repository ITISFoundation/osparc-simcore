""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
import os
from typing import Dict

import trafaret as T
from aiohttp import ClientSession, web
from models_library.settings import PortInt, VersionTag
from pydantic import BaseSettings, conint, constr
from servicelib.application_keys import APP_CLIENT_SESSION_KEY, APP_CONFIG_KEY

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
    vtag: VersionTag = "v0"

    class Config:
        prefix = "CATALOG_"


def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]
