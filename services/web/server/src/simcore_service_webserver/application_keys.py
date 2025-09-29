"""web.AppKey definitions for simcore_service_webserver"""

from typing import TYPE_CHECKING, Final

from aiohttp import web
from servicelib.aiohttp.application_keys import (
    APP_AIOPG_ENGINE_KEY,
    APP_CLIENT_SESSION_KEY,
    APP_CONFIG_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
)

if TYPE_CHECKING:
    # Application settings key - defined here **to avoid circular imports**
    from .application_settings import ApplicationSettings

    APP_SETTINGS_APPKEY: Final = web.AppKey("APP_SETTINGS", ApplicationSettings)
else:
    APP_SETTINGS_APPKEY: Final = web.AppKey("APP_SETTINGS", None)


__all__: tuple[str, ...] = (
    "APP_AIOPG_ENGINE_KEY",
    "APP_CLIENT_SESSION_KEY",
    "APP_CONFIG_KEY",
    "APP_FIRE_AND_FORGET_TASKS_KEY",
    "APP_SETTINGS_APPKEY",
)

# nopycln: file
