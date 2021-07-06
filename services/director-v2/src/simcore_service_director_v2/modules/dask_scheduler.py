import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, List, Set, Tuple, Type, cast

from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ..core.errors import ConfigurationError
from ..models.domains.comp_runs import CompRunsAtDB
from ..models.schemas.constants import UserID
from .db.repositories import BaseRepository
from .db.repositories.comp_pipelines import CompPipelinesRepository
from .db.repositories.comp_runs import CompRunsRepository
from .db.repositories.comp_tasks import CompTasksRepository

logger = logging.getLogger(__name__)


_SCHEDULED_STATES = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.STARTED,
    RunningState.RETRY,
}

_COMPLETED_STATES = {RunningState.ABORTED, RunningState.SUCCESS, RunningState.FAILED}

_DEFAULT_TIMEOUT_S: int = 5


def _get_repository(
    db_engine: Engine, repo_cls: Type[BaseRepository]
) -> BaseRepository:
    return repo_cls(db_engine=db_engine)  # type: ignore


Iteration = PositiveInt


@dataclass
class DaskScheduler:
    scheduled_pipelines: Set[Tuple[UserID, ProjectID, Iteration]]
    db_engine: Engine
    wake_up_event: asyncio.Event = asyncio.Event()

    @classmethod
    async def create_from_db(cls, app: FastAPI) -> "DaskScheduler":
        if not hasattr(app.state, "engine"):
            raise ConfigurationError(
                "Database connection is missing. Please check application configuration."
            )
        db_engine = app.state.engine
        runs_repository: CompRunsRepository = cast(
            CompRunsRepository, _get_repository(db_engine, CompRunsRepository)
        )

        # get currently scheduled runs
        runs: List[CompRunsAtDB] = await runs_repository.list(
            filter_by_state=_SCHEDULED_STATES
        )
        logger.info("DaskScheduler creation with %s runs being scheduled", len(runs))
        return cls(
            db_engine=db_engine,
            # celery_client=CeleryClient.instance(app),
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration) for r in runs
            },
        )  # type: ignore


async def scheduler_task(scheduler: DaskScheduler) -> None:
    while True:
        try:
            logger.debug("scheduler task running...")
            # await scheduler.schedule_all_pipelines()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    scheduler.wake_up_event.wait(), timeout=_DEFAULT_TIMEOUT_S
                )
        except CancelledError:
            logger.info("scheduler task cancelled")
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler now..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(_DEFAULT_TIMEOUT_S)


def on_app_startup(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def start_scheduler() -> None:
        app.state.dask_scheduler = scheduler = await DaskScheduler.create_from_db(app)
        task = asyncio.get_event_loop().create_task(scheduler_task(scheduler))
        app.state.dask_scheduler_task = task
        logger.info("DaskScheduler started")

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable[[], Coroutine[Any, Any, None]]:
    async def stop_scheduler() -> None:
        task = app.state.dask_scheduler_task
        app.state.dask_scheduler = None
        with suppress(CancelledError):
            task.cancel()
            await task
        logger.info("DaskScheduler stopped")

    return stop_scheduler


def setup(app: FastAPI):
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
