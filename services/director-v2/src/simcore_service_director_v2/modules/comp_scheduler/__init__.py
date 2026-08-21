import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.logging_utils import log_context

from ._constants import MODULE_NAME_SCHEDULER
from ._manager import run_new_pipeline, setup_manager, shutdown_manager, stop_pipeline
from ._releaser import setup_releaser, shutdown_releaser
from ._worker import setup_worker, shutdown_worker

_logger = logging.getLogger(__name__)


async def _comp_scheduler_lifespan(app: FastAPI) -> AsyncIterator[None]:
    with log_context(_logger, level=logging.INFO, msg=f"starting {MODULE_NAME_SCHEDULER}"):
        await setup_releaser(app)
        await setup_worker(app)
        await setup_manager(app)
    try:
        yield
    finally:
        with log_context(_logger, level=logging.INFO, msg=f"stopping {MODULE_NAME_SCHEDULER}"):
            await shutdown_manager(app)
            await shutdown_worker(app)
            await shutdown_releaser(app)


def configure_comp_scheduler(app_lifespan: LifespanManager) -> None:
    app_lifespan.add(_comp_scheduler_lifespan)


__all__: tuple[str, ...] = (
    "configure_comp_scheduler",
    "run_new_pipeline",
    "stop_pipeline",
)
