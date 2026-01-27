import datetime

from fastapi import APIRouter, FastAPI
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from ...long_running_tasks.constants import (
    DEFAULT_STALE_TASK_CHECK_INTERVAL,
    DEFAULT_STALE_TASK_DETECT_TIMEOUT,
)
from ...long_running_tasks.errors import BaseLongRunningError
from ...long_running_tasks.models import LRTNamespace
from ._error_handlers import base_long_running_error_handler
from ._manager import FastAPILongRunningManager
from ._routes import router


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    redis_settings: RedisSettings,
    rabbit_settings: RabbitSettings,
    lrt_namespace: LRTNamespace,
    stale_task_check_interval: datetime.timedelta = DEFAULT_STALE_TASK_CHECK_INTERVAL,
    stale_task_detect_timeout: datetime.timedelta = DEFAULT_STALE_TASK_DETECT_TIMEOUT,
) -> None:
    """
    - `router_prefix` APIs are mounted on `/...`, this
        will change them to be mounted as `{router_prefix}/...`
    - `redis_settings` settings for Redis connection
    - `rabbit_settings` settings for RabbitMQ connection
    - `lrt_namespace` namespace for the long-running tasks
    - `stale_task_check_interval` interval at which the
        TaskManager checks for tasks which are no longer being
        actively monitored by a client
    - `stale_task_detect_timeout` interval after which atask is considered stale
    """

    async def on_startup() -> None:
        # add routing paths
        main_router = APIRouter()
        main_router.include_router(router, prefix=router_prefix)
        app.include_router(main_router)

        # add components to state
        app.state.long_running_manager = long_running_manager = FastAPILongRunningManager(
            stale_task_check_interval=stale_task_check_interval,
            stale_task_detect_timeout=stale_task_detect_timeout,
            redis_settings=redis_settings,
            rabbit_settings=rabbit_settings,
            lrt_namespace=lrt_namespace,
        )
        await long_running_manager.setup()

    async def on_shutdown() -> None:
        if app.state.long_running_manager:
            long_running_manager: FastAPILongRunningManager = app.state.long_running_manager
            await long_running_manager.teardown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

    # add error handlers
    # NOTE: Exception handler can not be added during the on_startup script, otherwise not working correctly
    app.add_exception_handler(BaseLongRunningError, base_long_running_error_handler)  # type: ignore[arg-type]
