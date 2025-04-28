import logging
from collections.abc import Callable

from fastapi import FastAPI

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG

_logger = logging.getLogger(__name__)


def create_start_app_handler(app: FastAPI) -> Callable:
    async def _on_startup() -> None:
        _logger.info("Application starting ...")
        print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201

    return _on_startup


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def _on_shutdown() -> None:
        _logger.info("Application stopping, ...")
        print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201

    return _on_shutdown
