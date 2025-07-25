import datetime

from fastapi import APIRouter, FastAPI
from settings_library.redis import RedisSettings

from ...long_running_tasks.constants import (
    DEFAULT_STALE_TASK_CHECK_INTERVAL,
    DEFAULT_STALE_TASK_DETECT_TIMEOUT,
)
from ...long_running_tasks.errors import BaseLongRunningError
from ...long_running_tasks.task import Namespace
from ._error_handlers import base_long_running_error_handler
from ._manager import FastAPILongRunningManager
from ._routes import router


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    redis_settings: RedisSettings,
    namespace: Namespace,
    stale_task_check_interval: datetime.timedelta = DEFAULT_STALE_TASK_CHECK_INTERVAL,
    stale_task_detect_timeout: datetime.timedelta = DEFAULT_STALE_TASK_DETECT_TIMEOUT,
) -> None:
    """
    - `router_prefix` APIs are mounted on `/task/...`, this
        will change them to be mounted as `{router_prefix}/task/...`
    - `stale_task_check_interval_s` interval at which the
        TaskManager checks for tasks which are no longer being
        actively monitored by a client
    - `stale_task_detect_timeout_s` interval after which a
        task is considered stale
    """

    async def on_startup() -> None:
        # add routing paths
        main_router = APIRouter()
        main_router.include_router(router, prefix=router_prefix)
        app.include_router(main_router)

        # add components to state
        app.state.long_running_manager = long_running_manager = (
            FastAPILongRunningManager(
                app=app,
                stale_task_check_interval=stale_task_check_interval,
                stale_task_detect_timeout=stale_task_detect_timeout,
                redis_settings=redis_settings,
                namespace=namespace,
            )
        )
        await long_running_manager.setup()

    async def on_shutdown() -> None:
        if app.state.long_running_manager:
            task_manager: FastAPILongRunningManager = app.state.long_running_manager
            await task_manager.teardown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

    # add error handlers
    # NOTE: Exception handler can not be added during the on_startup script, otherwise not working correctly
    app.add_exception_handler(BaseLongRunningError, base_long_running_error_handler)  # type: ignore[arg-type]
