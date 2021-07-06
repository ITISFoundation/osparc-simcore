import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Set, Tuple, Type, cast

import networkx as nx
from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ..core.errors import ConfigurationError, SchedulerError
from ..models.domains.comp_pipelines import CompPipelineAtDB
from ..models.domains.comp_runs import CompRunsAtDB
from ..models.domains.comp_tasks import CompTaskAtDB
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

    async def run_new_pipeline(self, user_id: UserID, project_id: ProjectID) -> None:
        runs_repo: CompRunsRepository = _get_repository(
            self.db_engine, CompRunsRepository
        )  # type: ignore
        new_run: CompRunsAtDB = await runs_repo.create(
            user_id=user_id, project_id=project_id
        )
        self.scheduled_pipelines.add((user_id, project_id, new_run.iteration))
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def schedule_all_pipelines(self) -> None:
        self.wake_up_event.clear()
        # if one of the task throws, the other are NOT cancelled which is what we want
        await asyncio.gather(
            *[
                self._schedule_pipeline(user_id, project_id, iteration)
                for user_id, project_id, iteration in self.scheduled_pipelines
            ]
        )

    async def _get_pipeline_dag(self, project_id: ProjectID) -> nx.DiGraph:
        comp_pipeline_repo: CompPipelinesRepository = _get_repository(
            self.db_engine, CompPipelinesRepository
        )  # type: ignore
        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(
            project_id
        )
        pipeline_dag = pipeline_at_db.get_graph()
        if not pipeline_dag.nodes():
            # this should not happen
            raise SchedulerError(
                f"The pipeline of project {project_id} does not contain an adjacency list! Please check."
            )
        return pipeline_dag

    async def _get_pipeline_tasks(
        self, project_id: ProjectID, pipeline_dag: nx.DiGraph
    ) -> Dict[str, CompTaskAtDB]:
        comp_tasks_repo: CompTasksRepository = _get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        pipeline_comp_tasks: Dict[str, CompTaskAtDB] = {
            str(t.node_id): t
            for t in await comp_tasks_repo.get_comp_tasks(project_id)
            if (str(t.node_id) in list(pipeline_dag.nodes()))
        }
        if len(pipeline_comp_tasks) != len(pipeline_dag.nodes()):
            raise SchedulerError(
                f"The tasks defined for {project_id} do not contain all the tasks defined in the pipeline [{list(pipeline_dag.nodes)}]! Please check."
            )
        return pipeline_comp_tasks

    async def _schedule_pipeline(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt
    ) -> None:
        logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            project_id,
            iteration,
            user_id,
        )

        pipeline_dag: nx.DiGraph = await self._get_pipeline_dag(project_id)
        pipeline_tasks: Dict[str, CompTaskAtDB] = await self._get_pipeline_tasks(
            project_id, pipeline_dag
        )

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()


async def scheduler_task(scheduler: DaskScheduler) -> None:
    while True:
        try:
            logger.debug("scheduler task running...")
            await scheduler.schedule_all_pipelines()
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
