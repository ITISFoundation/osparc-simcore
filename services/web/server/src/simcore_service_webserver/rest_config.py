""" rest subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp import web

from ._constants import APP_CONFIG_KEY

CONFIG_SECTION_NAME = "rest"


def get_rest_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
