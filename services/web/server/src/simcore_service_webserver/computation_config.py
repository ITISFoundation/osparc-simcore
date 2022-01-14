""" computation subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

SERVICE_NAME = "computation"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY: str = f"{__name__}.rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = f"{__name__}.comp_tasks_listening_key"


def get_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
