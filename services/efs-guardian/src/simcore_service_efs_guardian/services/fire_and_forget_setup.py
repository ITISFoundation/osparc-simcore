import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from servicelib.logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)


def _on_app_startup(_app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="Efs Guardian setup fire and forget tasks.."
        ), log_catch(_logger, reraise=False):
            _app.state.efs_guardian_fire_and_forget_tasks = set()

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with log_context(
            _logger, logging.INFO, msg="Efs Guardian fire and forget tasks shutdown.."
        ), log_catch(_logger, reraise=False):
            assert _app  # nosec
            if _app.state.efs_guardian_fire_and_forget_tasks:
                for task in _app.state.efs_guardian_fire_and_forget_tasks:
                    task.cancel()

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
