from fastapi import FastAPI, APIRouter
from ._routes import router
from ._task import TaskManager
from ._errors import BaseLongRunningError
from ._error_handlers import base_long_running_error_handler


def setup(app: FastAPI, *, router_prefix: str = "") -> None:
    async def on_startup() -> None:
        # add routing paths
        main_router = APIRouter()
        main_router.include_router(router, prefix=router_prefix)
        app.include_router(main_router)

        # add components to state
        app.state.long_running_task_manager = TaskManager()

        # add error handlers
        app.add_exception_handler(BaseLongRunningError, base_long_running_error_handler)

    async def on_shutdown() -> None:
        if app.state.long_running_task_manager:
            task_manager: TaskManager = app.state.long_running_task_manager
            await task_manager.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
