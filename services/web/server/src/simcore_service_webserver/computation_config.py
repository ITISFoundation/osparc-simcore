""" computation subsystem's configuration

    - config-file schema
    - settings
"""
from simcore_sdk.config.rabbit import RabbitConfig


SERVICE_NAME = "computation"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY = __name__ + ".rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = __name__ + ".comp_tasks_listening_key"


class ComputationSettings(RabbitConfig):
    enabled: bool = True
