"""Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

import asyncio
from typing import Final

from aiohttp import ClientSession, web

# APPLICATION's CONTEXT KEYS

# NOTE: use these keys to store/retrieve data from aiohttp.web.Application
# SEE https://docs.aiohttp.org/en/stable/web_quickstart.html#aiohttp-web-app-key

#
# web.Application keys, i.e. app[APP_*_KEY]
#
APP_CONFIG_KEY: Final = web.AppKey("APP_CONFIG_KEY", dict[str, object])

APP_AIOPG_ENGINE_KEY: Final[str] = f"{__name__}.aiopg_engine"

APP_CLIENT_SESSION_KEY: Final = web.AppKey("APP_CLIENT_SESSION_KEY", ClientSession)


APP_FIRE_AND_FORGET_TASKS_KEY: Final = web.AppKey(
    "APP_FIRE_AND_FORGET_TASKS_KEY", set[asyncio.Task]
)


#
# web.Response keys, i.e. app[RSP_*_KEY]
#
