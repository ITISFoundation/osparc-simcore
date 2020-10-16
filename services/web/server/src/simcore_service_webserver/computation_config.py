""" computation subsystem's configuration

    - config-file schema
    - settings
"""
from simcore_sdk.config.rabbit import CONFIG_SCHEMA as _RABBIT_SCHEMA

# import trafaret as T

SERVICE_NAME = "rabbit"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY = __name__ + ".rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = __name__ + ".comp_tasks_listening_key"
schema = _RABBIT_SCHEMA
