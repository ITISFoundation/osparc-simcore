""" computation subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp.web import Application

from models_library.settings.celery import CeleryConfig
from servicelib.application_keys import APP_CONFIG_KEY

SERVICE_NAME = "computation"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY = __name__ + ".rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = __name__ + ".comp_tasks_listening_key"


class ComputationSettings(CeleryConfig):
    enabled: bool = True


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = ComputationSettings(**cfg)
    return cfg
