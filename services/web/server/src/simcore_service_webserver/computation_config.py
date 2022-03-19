""" computation subsystem's configuration

    - config-file schema
    - settings
"""

SERVICE_NAME = "computation"
CONFIG_SECTION_NAME = SERVICE_NAME
APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY: str = f"{__name__}.rabbit_handlers"
APP_COMP_TASKS_LISTENING_KEY: str = f"{__name__}.comp_tasks_listening_key"
