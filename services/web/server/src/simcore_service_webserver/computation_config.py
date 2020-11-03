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
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY: str = f"{__name__}.rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = f"{__name__}.comp_tasks_listening_key"


class ComputationSettings(CeleryConfig):
    enabled: bool = True


def get_config(app: Application) -> Dict:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]


def create_settings(app: Application) -> ComputationSettings:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    settings = ComputationSettings.create_from_env(**cfg)
    # NOTE: we are saving it in a separate item to config
    app[f"{__name__}.ComputationSettings"] = settings
    return settings


def get_settings(app: Application) -> ComputationSettings:
    return app[f"{__name__}.ComputationSettings"]
