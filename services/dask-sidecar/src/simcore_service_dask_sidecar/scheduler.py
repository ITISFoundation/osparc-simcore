import logging

import distributed
from servicelib.logging_utils import log_context

from ._meta import print_dask_scheduler_banner
from .settings import ApplicationSettings
from .utils.logs import setup_app_logging

_logger = logging.getLogger(__name__)


async def dask_setup(scheduler: distributed.Scheduler) -> None:
    """This is a special function recognized by dask when starting with flag --preload"""
    assert scheduler  # nosec

    settings = ApplicationSettings.create_from_envs()
    setup_app_logging(settings)

    with log_context(_logger, logging.INFO, "Launch dask scheduler"):
        _logger.info("app settings: %s", settings.model_dump_json(indent=1))
        print_dask_scheduler_banner()


async def dask_teardown(_worker: distributed.Worker) -> None:
    with log_context(_logger, logging.INFO, "Tear down dask scheduler"):
        ...
