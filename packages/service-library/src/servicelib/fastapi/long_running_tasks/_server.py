import datetime
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi_lifespan_manager import LifespanManager, State
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


def _include_router(app: FastAPI, router_prefix: str) -> None:
    main_router = APIRouter()
    main_router.include_router(router, prefix=router_prefix)
    app.include_router(main_router)


def configure_server(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    *,
    router_prefix: str = "",
    redis_settings: RedisSettings,
    rabbit_settings: RabbitSettings,
    lrt_namespace: LRTNamespace,
    stale_task_check_interval: datetime.timedelta = DEFAULT_STALE_TASK_CHECK_INTERVAL,
    stale_task_detect_timeout: datetime.timedelta = DEFAULT_STALE_TASK_DETECT_TIMEOUT,
) -> None:
    _include_router(app, router_prefix)
    app.add_exception_handler(BaseLongRunningError, base_long_running_error_handler)  # type: ignore[arg-type]

    async def _lifespan(_: FastAPI) -> AsyncIterator[State]:
        long_running_manager: FastAPILongRunningManager | None = None
        try:
            app.state.long_running_manager = long_running_manager = FastAPILongRunningManager(
                stale_task_check_interval=stale_task_check_interval,
                stale_task_detect_timeout=stale_task_detect_timeout,
                redis_settings=redis_settings,
                rabbit_settings=rabbit_settings,
                lrt_namespace=lrt_namespace,
            )
            await long_running_manager.setup()
            yield {}
        finally:
            if long_running_manager is not None:
                await long_running_manager.teardown()

    app_lifespan.add(_lifespan)
