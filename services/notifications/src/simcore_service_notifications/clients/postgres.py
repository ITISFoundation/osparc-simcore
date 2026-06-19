import logging
from asyncio import Task
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Final

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.healthchecks import IsResponsive, LivenessResult
from servicelib.background_task import create_periodic_task
from servicelib.db_asyncpg_utils import check_postgres_liveness, create_async_engine_and_database_ready
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.logging_utils import log_catch, log_context
from servicelib.retry_policies import PostgresRetryPolicyUponInitialization
from servicelib.tracing import TracingConfig
from settings_library.postgres import PostgresSettings
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity import retry

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
                await cancel_wait_task(self._task, max_delay=5)


def configure_postgres_database(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: PostgresSettings,
    tracing_config: TracingConfig | None,
) -> None:
    async def _database_lifespan(app: FastAPI) -> AsyncIterator[State]:
        # NOTE: an outer retry is used so that the service keeps retrying
        # (instead of failing on startup) while the alembic migration is not ready
        @retry(**PostgresRetryPolicyUponInitialization(_logger).kwargs)
        async def _connect() -> AsyncEngine:
            return await create_async_engine_and_database_ready(
                settings,
                app.title,
                tracing_config=tracing_config,
            )

        with log_context(_logger, logging.INFO, msg="setup postgres database"):
            app.state.engine = await _connect()

        yield {}

        with log_context(_logger, logging.INFO, msg="teardown postgres database"), log_catch(_logger, reraise=False):
            await app.state.engine.dispose()

    app_lifespan.add(_database_lifespan)


async def _postgres_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.postgres_liveness = PostgresLiveness(app)

    with log_context(_logger, logging.INFO, msg="setup postgres health"):
        await app.state.postgres_liveness.setup()

    yield {}

    with log_context(_logger, logging.INFO, msg="teardown postgres health"):
        await app.state.postgres_liveness.teardown()


def configure_postgres_liveness(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_postgres_lifespan)


def get_postgres_liveness(app: FastAPI) -> PostgresLiveness:
    assert isinstance(app.state.postgres_liveness, PostgresLiveness)  # nosec
    return app.state.postgres_liveness
