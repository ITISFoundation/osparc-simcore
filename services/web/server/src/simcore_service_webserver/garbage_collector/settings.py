from typing import Annotated

from aiohttp import web
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings

# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


_SEC = 1
_MINUTE = 60 * _SEC
_HOUR = 60 * _MINUTE


class GarbageCollectorSettings(BaseCustomSettings):
    GARBAGE_COLLECTOR_INTERVAL_S: Annotated[
        PositiveInt,
        Field(
            description="Waiting time between consecutive runs of the garbage-colector"
        ),
    ] = (
        30 * _SEC
    )

    GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S: Annotated[
        PositiveInt,
        Field(
            description="Time period between checks of expiration dates for trial users"
        ),
    ] = (
        1 * _HOUR
    )

    GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S: Annotated[
        PositiveInt,
        Field(description="Wait time between periodic pruning of expired API keys"),
    ] = _HOUR


def get_plugin_settings(app: web.Application) -> GarbageCollectorSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_GARBAGE_COLLECTOR
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, GarbageCollectorSettings)  # nosec
    return settings
