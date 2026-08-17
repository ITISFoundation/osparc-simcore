from datetime import timedelta
from typing import Annotated

from aiohttp import web
from pydantic import Field, PositiveFloat, PositiveInt
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY

# Guest-user GC lock key pattern.
#
# This format is intentionally used with two identities during the guest lifecycle:
# - guest *name* while the account is under construction
# - guest user *id* while the account is initialized and waiting for first resource use
#
# The garbage collector checks BOTH keys before pruning guest users (see _core_guests.py).
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


_SEC = 1
_MINUTE = 60 * _SEC
_HOUR = 60 * _MINUTE


class GarbageCollectorSettings(BaseCustomSettings):
    GARBAGE_COLLECTOR_INTERVAL_S: Annotated[
        PositiveInt,
        Field(description="Waiting time between consecutive runs of the garbage-collector"),
    ] = 30 * _SEC

    GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S: Annotated[
        PositiveInt,
        Field(description="Time period between checks of expiration dates for trial users"),
    ] = 1 * _HOUR

    GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S: Annotated[
        PositiveInt,
        Field(description="Wait time between periodic pruning of expired API keys"),
    ] = _HOUR

    GARBAGE_COLLECTOR_PRUNE_DOCUMENTS_INTERVAL_S: Annotated[
        PositiveInt,
        Field(description="Wait time between periodic pruning of documents"),
    ] = 30 * _MINUTE

    GARBAGE_COLLECTOR_TASK_STALE_FACTOR: Annotated[
        PositiveFloat,
        Field(
            description="Multiplier applied to each periodic task's own interval to determine "
            "how long it can go without reporting progress before the webserver healthcheck "
            "considers it stuck/hanging and reports the service as unhealthy"
        ),
    ] = 5.0

    GARBAGE_COLLECTOR_TASK_MIN_STALENESS: Annotated[
        timedelta,
        Field(
            description="Minimum amount of time a periodic task is allowed to go without reporting "
            "progress before the webserver healthcheck considers it stuck/hanging, regardless of "
            "the task's own interval and GARBAGE_COLLECTOR_TASK_STALE_FACTOR"
        ),
    ] = timedelta(hours=1)


def get_plugin_settings(app: web.Application) -> GarbageCollectorSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_GARBAGE_COLLECTOR
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, GarbageCollectorSettings)  # nosec
    return settings
