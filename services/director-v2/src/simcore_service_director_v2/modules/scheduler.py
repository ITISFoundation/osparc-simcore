"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next celery task(s), either one at a time or as a group of tasks.
"""
import asyncio
import logging
from asyncio import CancelledError
from dataclasses import dataclass
from typing import Any, Dict, Set, Tuple

import networkx as nx
from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.utils.db import RUNNING_STATE_TO_DB

from ..models.domains.comp_pipelines import CompPipelineAtDB
from ..models.domains.comp_tasks import CompTaskAtDB, Image
from ..modules.celery import CeleryClient
from ..modules.director_v0 import DirectorV0Client
from ..utils.computations import get_pipeline_state_from_task_states
from .db.repositories.comp_pipelines import CompPipelinesRepository
from .db.repositories.comp_tasks import CompTasksRepository

logger = logging.getLogger(__name__)


@dataclass
class Scheduler:
    scheduled_pipelines: Set[Tuple[UserID, ProjectID]]
    db_engine: Engine
    celery_client: CeleryClient
    director_client: DirectorV0Client

    @classmethod
    async def create_from_db(cls, app: FastAPI) -> "Scheduler":
        db_engine = app.state.engine
        pipeline_repository = CompPipelinesRepository(db_engine)
        published_pipelines = await pipeline_repository.list_pipelines_with_state(
            state={RunningState.PUBLISHED, RunningState.STARTED}
        )
        logger.info(
            "Scheduler created with %s published pipelines", len(published_pipelines)
        )
        return cls(
            db_engine=db_engine,
            celery_client=CeleryClient.instance(app),
            director_client=DirectorV0Client.instance(app),
            scheduled_pipelines={
                (p.user_id, p.project_id) for p in published_pipelines
            },
        )

    def schedule_pipeline(self, user_id: UserID, project_id: ProjectID) -> None:
        self.scheduled_pipelines.add((user_id, project_id))

    async def schedule_all_pipelines(self) -> None:
        for user_id, project_id in self.scheduled_pipelines:
            await self.check_pipeline_status(user_id, project_id)

    async def check_pipeline_status(
        self, user_id: UserID, project_id: ProjectID
    ) -> None:
        comp_pipeline_repo = CompPipelinesRepository(self.db_engine)
        comp_tasks_repo = CompTasksRepository(self.db_engine)

        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(
            project_id
        )
        pipeline_dag: nx.DiGraph = nx.from_dict_of_lists(
            pipeline_at_db.dag_adjacency_list, create_using=nx.DiGraph
        )
        if not pipeline_dag.nodes:
            await comp_pipeline_repo.mark_pipeline_state(
                project_id, state=RunningState.NOT_STARTED
            )
            return

        # get the tasks that were scheduled
        comp_tasks: Dict[str, CompTaskAtDB] = {
            str(t.node_id): t
            for t in await comp_tasks_repo.get_comp_tasks(project_id)
            if (str(t.node_id) in list(pipeline_dag.nodes()))
        }
        if not comp_tasks:
            await comp_pipeline_repo.mark_pipeline_state(
                project_id, state=RunningState.UNKNOWN
            )
            return
        pipeline_dag.remove_nodes_from(
            {
                node_id
                for node_id, t in comp_tasks.items()
                if t.state == RunningState.SUCCESS
            }
        )
        if not pipeline_dag.nodes:
            # was already successfully completed
            await comp_pipeline_repo.mark_pipeline_state(
                project_id, state=RunningState.SUCCESS
            )
            return

        def _runtime_requirement(node_image: Image) -> str:
            if node_image.requires_gpu:
                return "gpu"
            if node_image.requires_mpi:
                return "mpi"
            return "cpu"

        # get the tasks that should be run
        tasks_to_run: Dict[str, Dict[str, Any]] = {
            node_id: {
                "runtime_requirements": _runtime_requirement(comp_tasks[node_id].image)
            }
            for node_id, degree in pipeline_dag.in_degree()
            if degree == 0 and comp_tasks[node_id].state == RunningState.PUBLISHED
        }
        if not tasks_to_run:
            pipeline_state_from_tasks = get_pipeline_state_from_task_states(
                comp_tasks.values(), self.celery_client.settings.publication_timeout
            )
            await comp_pipeline_repo.mark_pipeline_state(
                project_id, state=RUNNING_STATE_TO_DB[pipeline_state_from_tasks]
            )
            return
        comp_tasks_repo.mark_project_tasks_as_pending(project_id, tasks_to_run.keys())
        self.celery_client.send_single_tasks(
            user_id=user_id, project_id=project_id, single_tasks=tasks_to_run
        )


async def scheduler_task(app: FastAPI) -> None:
    while True:
        try:
            app.state.scheduler = scheduler = await Scheduler.create_from_db(app)
            while True:
                logger.info("Scheduler checking pipelines and tasks")
                await scheduler.schedule_all_pipelines()
                await asyncio.sleep(5)

        except CancelledError:
            logger.info("Scheduler background task cancelled")
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(5)
        finally:
            app.state.scheduler = None
