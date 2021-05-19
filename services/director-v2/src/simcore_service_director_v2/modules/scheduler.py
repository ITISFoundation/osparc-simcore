"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next celery task(s), either one at a time or as a group of tasks.
"""
import asyncio
import logging
from asyncio import CancelledError
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple, Type

import networkx as nx
from aiopg.sa.engine import Engine
from celery import Task
from celery.exceptions import TimeoutError as CeleryTimeoutError
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
class Scheduler:
    scheduled_pipelines: Set[Tuple[UserID, ProjectID, Iteration]]
    db_engine: Engine
    celery_client: CeleryClient
    wake_up_event: asyncio.Event = asyncio.Event()

    @classmethod
    async def create_from_db(cls, app: FastAPI) -> "Scheduler":
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
        logger.info("Scheduler creation with %s runs being scheduled", len(runs))
        return cls(
            db_engine=db_engine,
            celery_client=CeleryClient.instance(app),
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration) for r in runs
            },
        )

    async def run(self) -> None:
        while True:
            logger.info("Scheduler checking pipelines and tasks")
            self.wake_up_event.clear()
            await asyncio.gather(
                *[
                    self._check_pipeline_status(user_id, project_id, iteration)
                    for user_id, project_id, iteration in self.scheduled_pipelines
                ]
            )
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self.wake_up_event.wait(), timeout=_DEFAULT_TIMEOUT_S
                )

    async def schedule_pipeline_run(
        self, user_id: UserID, project_id: ProjectID
    ) -> None:
        runs_repo = _get_repository(self.db_engine, CompRunsRepository)
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
        pipeline_dag: nx.DiGraph = nx.from_dict_of_lists(
            pipeline_at_db.dag_adjacency_list, create_using=nx.DiGraph
        )
        if not pipeline_dag.nodes:
            logger.warning("pipeline %s has no node to be run", project_id)
            await comp_runs_repo.set_run_result(
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
                result_state=RunningState.NOT_STARTED,
            )
            return

        # get the tasks that were scheduled
        comp_tasks: Dict[str, CompTaskAtDB] = {
            str(t.node_id): t
            for t in await comp_tasks_repo.get_comp_tasks(project_id)
            if (str(t.node_id) in list(pipeline_dag.nodes()))
        }
        if not comp_tasks:
            logger.warning("pipeline %s has no computational node", project_id)
            await comp_runs_repo.set_run_result(
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
                result_state=RunningState.UNKNOWN,
            )
            return
        # filter the tasks with what were already completed
        pipeline_dag.remove_nodes_from(
            {
                node_id
                for node_id, t in comp_tasks.items()
                if t.state
                in [RunningState.SUCCESS, RunningState.FAILED, RunningState.ABORTED]
            }
        )
        if not pipeline_dag.nodes:
            # was already completed
            pipeline_state_from_tasks = get_pipeline_state_from_task_states(
                comp_tasks.values(), self.celery_client.settings.publication_timeout
            )
            logger.info(
                "pipeline %s completed with result %s",
                project_id,
                pipeline_state_from_tasks,
            )
            await comp_runs_repo.set_run_result(
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
                result_state=pipeline_state_from_tasks,
            )

            # remove the pipeline
            self.scheduled_pipelines.remove((user_id, project_id, iteration))
            return

        # get the tasks that should be run now
        tasks_to_run: Dict[str, Dict[str, Any]] = {
            node_id: {
                "runtime_requirements": _runtime_requirement(comp_tasks[node_id].image)
            }
            for node_id, degree in pipeline_dag.in_degree()
            if degree == 0 and comp_tasks[node_id].state == RunningState.PUBLISHED
        }
        if not tasks_to_run:
            # we are currently running or there is nothing left to be done
            pipeline_state_from_tasks = get_pipeline_state_from_task_states(
                comp_tasks.values(), self.celery_client.settings.publication_timeout
            )
            await comp_runs_repo.set_run_result(
                user_id=user_id,
                project_id=project_id,
                iteration=iteration,
                result_state=pipeline_state_from_tasks,
            )
            return

        # let's schedule the tasks, mark them as PENDING so the sidecar will take it
        await comp_tasks_repo.mark_project_tasks_as_pending(
            project_id, tasks_to_run.keys()
        )

        scheduled_tasks: Dict[str, Task] = self.celery_client.send_single_tasks(
            user_id=user_id, project_id=project_id, single_tasks=tasks_to_run
        )
        for t in scheduled_tasks.values():
            asyncio.get_event_loop().create_task(_check_task_status(t))


def celery_on_message(body: Any) -> None:
    # FIXME: this might become handy when we stop starting tasks recursively
    logger.warning(body)


async def _check_task_status(task: Task):
    try:
        # wait for the result here
        result = task.get(on_message=celery_on_message, propagate=False)
        logger.warning("RESULT OBTAINED: %s for task %s", result, task)
    except CeleryTimeoutError:
        logger.error("timeout on waiting for task %s", task)
    except Exception:  # pylint: disable=broad-except
        logger.error("An unexpected error happend while running Celery task %s", task)


def get_scheduler(app: FastAPI) -> Scheduler:
    return app.state.scheduler


async def scheduler_task(app: FastAPI) -> None:
    while True:
        try:
            app.state.scheduler = scheduler = await Scheduler.create_from_db(app)
            await scheduler.run()

        except CancelledError:
            logger.info("Scheduler background task cancelled")
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(_DEFAULT_TIMEOUT_S)
        finally:
            app.state.scheduler = None
            logger.debug("Scheduler task completed")
