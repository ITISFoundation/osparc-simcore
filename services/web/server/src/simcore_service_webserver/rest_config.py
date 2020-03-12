""" rest subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

import trafaret as T
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = "rest"

schema = T.Dict(
    {T.Key("enabled", default=True, optional=True): T.Bool(), "version": T.Enum("v0"),}
)


def get_rest_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


__all__ = ["APP_OPENAPI_SPECS_KEY"]
