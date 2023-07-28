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
    GARBAGE_COLLECTOR_INTERVAL_S: PositiveInt = Field(
        30 * _SEC,
        description="Waiting time between consecutive runs of the garbage-colector",
    )

    GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S: PositiveInt = Field(
        1 * _HOUR,
        description="Time period between checks of expiration dates for trial users",
    )

    GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S: PositiveInt = Field(
        _HOUR,
        description="Wait time between periodic pruning of expired API keys",
    )


def get_plugin_settings(app: web.Application) -> GarbageCollectorSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_GARBAGE_COLLECTOR
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, GarbageCollectorSettings)  # nosec
    return settings
