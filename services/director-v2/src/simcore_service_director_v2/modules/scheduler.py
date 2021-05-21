"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next celery task(s), either one at a time or as a group of tasks.
"""
import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Set, Tuple, Type

import networkx as nx
from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt

from ..core.errors import ConfigurationError
from ..models.domains.comp_pipelines import CompPipelineAtDB
from ..models.domains.comp_runs import CompRunsAtDB
from ..models.domains.comp_tasks import CompTaskAtDB, Image
from ..models.schemas.constants import UserID
from ..modules.celery import CeleryClient
from ..utils.computations import get_pipeline_state_from_task_states
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
    db_engine: Engine, repo_type: Type[BaseRepository]
) -> BaseRepository:
    return repo_type(db_engine=db_engine)


def _runtime_requirement(node_image: Image) -> str:
    if node_image.requires_gpu:
        return "gpu"
    if node_image.requires_mpi:
        return "mpi"
    return "cpu"


Iteration = PositiveInt


@dataclass
class CeleryScheduler:
    scheduled_pipelines: Set[Tuple[UserID, ProjectID, Iteration]]
    db_engine: Engine
    celery_client: CeleryClient
    wake_up_event: asyncio.Event = asyncio.Event()

    @classmethod
    async def create_from_db(cls, app: FastAPI) -> "CeleryScheduler":
        if not hasattr(app.state, "engine"):
            raise ConfigurationError(
                "Database connection is missing. Please check application configuration."
            )
        db_engine = app.state.engine
        runs_repository = _get_repository(db_engine, CompRunsRepository)

        # get currently scheduled runs
        runs: List[CompRunsAtDB] = await runs_repository.list(
            filter_by_state=_SCHEDULED_STATES
        )
        logger.info("CeleryScheduler creation with %s runs being scheduled", len(runs))
        return cls(
            db_engine=db_engine,
            celery_client=CeleryClient.instance(app),
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration) for r in runs
            },
        )

    async def run(self) -> None:
        logger.info("CeleryScheduler checking pipelines and tasks")
        self.wake_up_event.clear()
        await asyncio.gather(
            *[
                self._check_pipeline_status(user_id, project_id, iteration)
                for user_id, project_id, iteration in self.scheduled_pipelines
            ]
        )

    async def schedule_pipeline_run(
        self, user_id: UserID, project_id: ProjectID
    ) -> None:
        runs_repo: CompRunsRepository = _get_repository(
            self.db_engine, CompRunsRepository
        )
        new_run: CompRunsAtDB = await runs_repo.create(
            user_id=user_id, project_id=project_id
        )
        self.scheduled_pipelines.add((user_id, project_id, new_run.iteration))
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()

    async def _check_pipeline_status(
        self, user_id: UserID, project_id: ProjectID, iteration: PositiveInt
    ) -> None:
        logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            project_id,
            iteration,
            user_id,
        )
        comp_runs_repo: CompRunsRepository = _get_repository(
            self.db_engine, CompRunsRepository
        )
        comp_pipeline_repo: CompPipelinesRepository = _get_repository(
            self.db_engine, CompPipelinesRepository
        )
        comp_tasks_repo: CompTasksRepository = _get_repository(
            self.db_engine, CompTasksRepository
        )

        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(
            project_id
        )
        pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()
        if not pipeline_dag.nodes:
            # this should not happen
            logger.error("pipeline %s has no node to be run", project_id)
            return

        # get the tasks that were scheduled
        comp_tasks: Dict[str, CompTaskAtDB] = {
            str(t.node_id): t
            for t in await comp_tasks_repo.get_comp_tasks(project_id)
            if (str(t.node_id) in list(pipeline_dag.nodes()))
        }
        if not comp_tasks:
            # this should not happen
            logger.error("pipeline %s has computational node", project_id)
            return

        # filter out the tasks with what were already completed
        pipeline_dag.remove_nodes_from(
            {
                node_id
                for node_id, t in comp_tasks.items()
                if t.state in _COMPLETED_STATES
            }
        )

        # update the current status of the run
        pipeline_state_from_tasks = get_pipeline_state_from_task_states(
            comp_tasks.values(), self.celery_client.settings.publication_timeout
        )
        await comp_runs_repo.set_run_result(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
            result_state=pipeline_state_from_tasks,
            final_state=(pipeline_state_from_tasks in _COMPLETED_STATES),
        )

        if not pipeline_dag.nodes:
            # there is nothing left, the run is completed
            self.scheduled_pipelines.remove((user_id, project_id, iteration))
            logger.info(
                "pipeline %s completed with result %s",
                project_id,
                pipeline_state_from_tasks,
            )
            return

        # find the next tasks that should be run now
        next_tasks_to_run: Dict[str, Dict[str, Any]] = {
            node_id: {
                "runtime_requirements": _runtime_requirement(comp_tasks[node_id].image)
            }
            for node_id, degree in pipeline_dag.in_degree()
            if degree == 0 and comp_tasks[node_id].state == RunningState.PUBLISHED
        }
        if not next_tasks_to_run:
            # nothing to run at the moment
            return

        # let's schedule the tasks, mark them as PENDING so the sidecar will take it
        await comp_tasks_repo.mark_project_tasks_as_pending(
            project_id, next_tasks_to_run.keys()
        )

        self.celery_client.send_single_tasks(
            user_id=user_id,
            project_id=project_id,
            single_tasks=next_tasks_to_run,
            callback=self._wake_up_scheduler_now,
        )


async def scheduler_task(scheduler: CeleryScheduler) -> None:
    while True:
        try:
            await scheduler.run()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    scheduler.wake_up_event.wait(), timeout=_DEFAULT_TIMEOUT_S
                )
        except CancelledError:
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler now..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(_DEFAULT_TIMEOUT_S)


def on_app_startup(app: FastAPI) -> Callable:
    async def start_scheduler() -> None:
        app.state.scheduler = scheduler = await CeleryScheduler.create_from_db(app)
        task = asyncio.get_event_loop().create_task(scheduler_task(scheduler))
        app.state.scheduler_task = task
        logger.info("CeleryScheduler started")

    return start_scheduler


def on_app_shutdown(app: FastAPI) -> Callable:
    async def stop_scheduler() -> None:
        task = app.state.scheduler_task
        app.state.scheduler = None
        with suppress(CancelledError):
            task.cancel()
            await task
        logger.info("CeleryScheduler stopped")

    return stop_scheduler


def setup(app: FastAPI):

    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
