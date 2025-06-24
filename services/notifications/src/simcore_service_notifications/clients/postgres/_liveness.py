import logging
from asyncio import Task
from datetime import timedelta
from typing import Final

from common_library.async_tools import cancel_and_shielded_wait
from fastapi import FastAPI
from models_library.healthchecks import IsResponsive, LivenessResult
from servicelib.background_task import create_periodic_task
from servicelib.db_asyncpg_utils import check_postgres_liveness
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.logging_utils import log_catch

_logger = logging.getLogger(__name__)

_LVENESS_CHECK_INTERVAL: Final[timedelta] = timedelta(seconds=10)


class PostgresLiveness:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

        self._liveness_result: LivenessResult = IsResponsive(elapsed=timedelta(0))
        self._task: Task | None = None

    async def _check_task(self) -> None:
        self._liveness_result = await check_postgres_liveness(get_engine(self.app))

    @property
    def is_responsive(self) -> bool:
        return isinstance(self._liveness_result, IsResponsive)

    async def setup(self) -> None:
        self._task = create_periodic_task(
            self._check_task,
            interval=_LVENESS_CHECK_INTERVAL,
            task_name="posgress_liveness_check",
        )

    async def teardown(self) -> None:
        if self._task is not None:
            with log_catch(_logger, reraise=False):
                await cancel_and_shielded_wait(self._task, max_delay=5)
