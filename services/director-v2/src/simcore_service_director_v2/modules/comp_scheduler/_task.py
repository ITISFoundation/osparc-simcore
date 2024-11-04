import datetime
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Final

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientsManager
from servicelib.redis_utils import exclusive
from settings_library.redis import RedisDatabase

from . import _scheduler_factory

_logger = logging.getLogger(__name__)

_COMPUTATIONAL_SCHEDULER_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(
    seconds=5
)
_TASK_NAME: Final[str] = "computational services scheduler"


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="starting computational scheduler"
        ):
            redis_clients_manager: RedisClientsManager = app.state.redis_clients_manager
            lock_key = f"{app.title}:computational_scheduler"
            app.state.scheduler = scheduler = await _scheduler_factory.create_from_db(
                app
            )
            app.state.computational_scheduler_task = start_periodic_task(
                exclusive(
                    redis_clients_manager.client(RedisDatabase.LOCKS),
                    lock_key=lock_key,
                )(scheduler.schedule_all_pipelines),
                interval=_COMPUTATIONAL_SCHEDULER_INTERVAL,
                task_name=_TASK_NAME,
                early_wake_up_event=scheduler.wake_up_event,
            )

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        await stop_periodic_task(app.state.computational_scheduler_task)

    return stop_scheduler
