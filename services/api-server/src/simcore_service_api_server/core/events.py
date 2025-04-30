import logging

from .._meta import APP_FINISHED_BANNER_MSG, APP_STARTED_BANNER_MSG

_logger = logging.getLogger(__name__)


async def on_startup() -> None:
    _logger.info("Application starting ...")
    print(APP_STARTED_BANNER_MSG, flush=True)  # noqa: T201


async def on_shutdown() -> None:
    _logger.info("Application stopping, ...")
    print(APP_FINISHED_BANNER_MSG, flush=True)  # noqa: T201
