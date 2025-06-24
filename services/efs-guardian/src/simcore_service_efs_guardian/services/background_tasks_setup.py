import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_catch, log_context

from .background_tasks import removal_policy_task
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


def _on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with (
            log_context(_logger, logging.INFO, msg="Efs Guardian background task "),
            log_catch(_logger, reraise=False),
        ):
            app.state.efs_guardian_removal_policy_background_task = None

            _logger.info("starting efs guardian removal policy task")

            @exclusive_periodic(
                get_redis_lock_client(app),
                task_interval=timedelta(hours=1),
                retry_after=timedelta(minutes=5),
            )
            async def _periodic_removal_policy_task() -> None:
                await removal_policy_task(app)

            app.state.efs_guardian_removal_policy_background_task = asyncio.create_task(
                _periodic_removal_policy_task(),
                name=_periodic_removal_policy_task.__name__,
            )

    return _startup


def _on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        with (
            log_context(_logger, logging.INFO, msg="Efs Guardian shutdown.."),
            log_catch(_logger, reraise=False),
        ):
            assert _app  # nosec
            if _app.state.efs_guardian_removal_policy_background_task:
                await cancel_wait_task(
                    _app.state.efs_guardian_removal_policy_background_task
                )

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", _on_app_startup(app))
    app.add_event_handler("shutdown", _on_app_shutdown(app))
