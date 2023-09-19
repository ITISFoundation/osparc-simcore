import logging

import distributed

from ._meta import print_dask_scheduler_banner

_logger = logging.getLogger(__name__)


async def dask_setup(scheduler: distributed.Scheduler) -> None:
    """This is a special function recognized by the dask worker when starting with flag --preload"""
    _logger.info("Setting up scheduler...")
    assert scheduler  # nosec
    print_dask_scheduler_banner()


async def dask_teardown(_worker: distributed.Worker) -> None:
    _logger.info("Shutting down scheduler")
