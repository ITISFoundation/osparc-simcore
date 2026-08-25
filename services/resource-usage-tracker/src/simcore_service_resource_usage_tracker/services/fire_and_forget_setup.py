import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)


def _on_app_startup(_app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with (
            log_context(
                _logger,
                logging.INFO,
                msg="Resource Usage Tracker setup fire and forget tasks..",
            ),
            log_catch(_logger, reraise=False),
        ):
            _app.state.rut_fire_and_forget_tasks = set()

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with (
            log_context(
                _logger,
                logging.INFO,
                msg="Resource Usage Tracker fire and forget tasks shutdown..",
            ),
            log_catch(_logger, reraise=False),
        ):
            assert _app  # nosec
            if _app.state.rut_fire_and_forget_tasks:
                for task in _app.state.rut_fire_and_forget_tasks:
                    await cancel_wait_task(task)

    return _stop


def configure_fire_and_forget(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _fire_and_forget_lifespan(app: FastAPI) -> AsyncIterator[State]:
        try:
            await _on_app_startup(app)()
            yield {}
        finally:
            await _on_app_shutdown(app)()

    app_lifespan.add(_fire_and_forget_lifespan)
