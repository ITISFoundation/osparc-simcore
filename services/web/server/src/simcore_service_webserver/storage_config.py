""" storage subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp import ClientSession, web
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY, APP_CONFIG_KEY

CONFIG_SECTION_NAME = "storage"


def get_storage_config(app: web.Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def get_client_session(app: web.Application) -> ClientSession:
    return app[APP_CLIENT_SESSION_KEY]
