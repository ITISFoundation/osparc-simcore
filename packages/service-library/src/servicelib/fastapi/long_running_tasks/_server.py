from typing import Final

from fastapi import APIRouter, FastAPI
from pydantic import PositiveFloat

from ...long_running_tasks._errors import BaseLongRunningError
from ...long_running_tasks._task import TasksManager
from ._error_handlers import base_long_running_error_handler
from ._routes import router

_MINUTE: Final[PositiveFloat] = 60


def setup(
    app: FastAPI,
    *,
    router_prefix: str = "",
    stale_task_check_interval_s: PositiveFloat = 1 * _MINUTE,
    stale_task_detect_timeout_s: PositiveFloat = 5 * _MINUTE,
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
        app.state.long_running_task_manager = TasksManager(
            stale_task_check_interval_s=stale_task_check_interval_s,
            stale_task_detect_timeout_s=stale_task_detect_timeout_s,
        )

    async def on_shutdown() -> None:
        if app.state.long_running_task_manager:
            task_manager: TasksManager = app.state.long_running_task_manager
            await task_manager.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)

    # add error handlers
    # NOTE: Exception handler can not be added during the on_startup script, otherwise not working correctly
    app.add_exception_handler(BaseLongRunningError, base_long_running_error_handler)    # type: ignore[arg-type]
