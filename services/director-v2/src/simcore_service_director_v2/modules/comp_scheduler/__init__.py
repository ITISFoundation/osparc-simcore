import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context

from ._distributed_scheduler import (
    run_new_pipeline,
    setup_manager,
    shutdown_manager,
    stop_pipeline,
)
from ._distributed_worker import setup_worker

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="starting computational scheduler"
        ):

            await setup_worker(app)
            await setup_manager(app)

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        with log_context(
            _logger, level=logging.INFO, msg="stopping computational scheduler"
        ):
            await shutdown_manager(app)

            # TODO: we might want to stop anything running in the worker too

    return stop_scheduler


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))


__all__: tuple[str, ...] = (
    "setup",
    "run_new_pipeline",
    "stop_pipeline",
)
