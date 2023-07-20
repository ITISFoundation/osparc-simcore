""" Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""
from typing import Final

# REQUIREMENTS:
# - guarantees all keys are unique
# - one place for all common keys
# - hierarchical classification

#
# web.Application keys, i.e. app[APP_*_KEY]
#
APP_CONFIG_KEY: Final[str] = f"{__name__ }.config"
APP_SETTINGS_KEY: Final[str] = f"{__name__ }.settings"

APP_DB_ENGINE_KEY: Final[str] = f"{__name__ }.db_engine"

APP_CLIENT_SESSION_KEY: Final[str] = f"{__name__ }.session"

APP_FIRE_AND_FORGET_TASKS_KEY: Final[str] = f"{__name__}.tasks"

APP_RABBITMQ_CLIENT_KEY: Final[str] = f"{__name__}.rabbit_client"

#
# web.Response keys, i.e. app[RSP_*_KEY]
#
