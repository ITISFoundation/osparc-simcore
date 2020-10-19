""" computation subsystem's configuration

    - config-file schema
    - settings
"""
from models_library.celery import CeleryConfig

SERVICE_NAME = "computation"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY = __name__ + ".rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = __name__ + ".comp_tasks_listening_key"


class ComputationSettings(CeleryConfig):
    enabled: bool = True
