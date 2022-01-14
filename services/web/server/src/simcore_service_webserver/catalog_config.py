""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "catalog"

KCATALOG_ORIGIN = f"{__name__}.catalog_origin"
KCATALOG_VERSION_PREFIX = f"{__name__}.catalog_version_prefix"


def get_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
