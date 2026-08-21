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


async def _releaser_lifespan(app: FastAPI) -> AsyncIterator[None]:
    with log_context(_logger, level=logging.INFO, msg=f"starting {MODULE_NAME_SCHEDULER} releaser"):
        await setup_releaser(app)
    try:
        yield
    finally:
        with log_context(_logger, level=logging.INFO, msg=f"stopping {MODULE_NAME_SCHEDULER} releaser"):
            await shutdown_releaser(app)


async def _worker_lifespan(app: FastAPI) -> AsyncIterator[None]:
    with log_context(_logger, level=logging.INFO, msg=f"starting {MODULE_NAME_SCHEDULER} worker"):
        await setup_worker(app)
    try:
        yield
    finally:
        with log_context(_logger, level=logging.INFO, msg=f"stopping {MODULE_NAME_SCHEDULER} worker"):
            await shutdown_worker(app)


async def _manager_lifespan(app: FastAPI) -> AsyncIterator[None]:
    with log_context(_logger, level=logging.INFO, msg=f"starting {MODULE_NAME_SCHEDULER} manager"):
        await setup_manager(app)
    try:
        yield
    finally:
        with log_context(_logger, level=logging.INFO, msg=f"stopping {MODULE_NAME_SCHEDULER} manager"):
            await shutdown_manager(app)


def configure_comp_scheduler(app_lifespan: LifespanManager) -> None:
    # NOTE: each resource is registered as its own lifespan so that, if a later one fails to
    # start, the LifespanManager only tears down the resources that were actually started (in
    # reverse order), instead of leaving them dangling.
    app_lifespan.add(_releaser_lifespan)
    app_lifespan.add(_worker_lifespan)
    app_lifespan.add(_manager_lifespan)


__all__: tuple[str, ...] = (
    "configure_comp_scheduler",
    "run_new_pipeline",
    "stop_pipeline",
)
