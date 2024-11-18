import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from . import _scheduler_factory
from ._base_scheduler import BaseCompScheduler

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="starting computational scheduler"
        ):
            app.state.scheduler = await _scheduler_factory.create_from_db(app)

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        await get_scheduler(app).shutdown()

    return stop_scheduler


def get_scheduler(app: FastAPI) -> BaseCompScheduler:
    return cast(BaseCompScheduler, app.state.scheduler)


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))


__all__: tuple[str, ...] = (
    "setup",
    "BaseCompScheduler",
    "get_scheduler",
)
