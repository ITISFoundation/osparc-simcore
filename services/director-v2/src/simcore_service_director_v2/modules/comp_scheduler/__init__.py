import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ._constants import MODULE_NAME_SCHEDULER
from ._manager import run_new_pipeline, setup_manager, shutdown_manager, stop_pipeline
from ._worker import setup_worker, shutdown_worker

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg=f"starting {MODULE_NAME_SCHEDULER}"
        ):
            await setup_worker(app)
            await setup_manager(app)

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg=f"stopping {MODULE_NAME_SCHEDULER}"
        ):
            await shutdown_manager(app)
            await shutdown_worker(app)

    return stop_scheduler


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))


__all__: tuple[str, ...] = (
    "setup",
    "run_new_pipeline",
    "stop_pipeline",
)
