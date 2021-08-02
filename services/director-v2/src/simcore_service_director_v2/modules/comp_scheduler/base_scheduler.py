"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next celery task(s), either one at a time or as a group of tasks.

In principle the Scheduler maintains the comp_runs table in the database.
It contains how the pipeline was run and by whom.
It also contains the final result of the pipeline run.

When a pipeline is scheduled first all the tasks contained in the DAG are set to PUBLISHED state.
Once the scheduler determines a task shall run, its state is set to PENDING, so that the sidecar can pick up the task.
The sidecar will then change the state to STARTED, then to SUCCESS or FAILED.

"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
from aiopg.sa.engine import Engine
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ...core.errors import SchedulerError
from ...models.domains.comp_pipelines import CompPipelineAtDB
from ...models.domains.comp_runs import CompRunsAtDB
from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.constants import UserID
from ...utils.computations import get_pipeline_state_from_task_states
from ...utils.exceptions import PipelineNotFoundError
from ...utils.scheduler import COMPLETED_STATES, Iteration, get_repository
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..db.repositories.comp_tasks import CompTasksRepository

logger = logging.getLogger(__name__)


@dataclass
class ScheduledPipelineParams:
    mark_for_cancellation: bool = False


@dataclass
class BaseCompScheduler(ABC):
    scheduled_pipelines: Dict[
        Tuple[UserID, ProjectID, Iteration], ScheduledPipelineParams
    ]
    db_engine: Engine
    wake_up_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    async def run_new_pipeline(self, user_id: UserID, project_id: ProjectID) -> None:
        runs_repo: CompRunsRepository = get_repository(
            self.db_engine, CompRunsRepository
        )  # type: ignore
        new_run: CompRunsAtDB = await runs_repo.create(
            user_id=user_id, project_id=project_id
        )
        self.scheduled_pipelines[
            (user_id, project_id, new_run.iteration)
        ] = ScheduledPipelineParams()
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def stop_pipeline(
        self, user_id: UserID, project_id: ProjectID, iteration: Optional[int] = None
    ) -> None:
        if not iteration:
            # if no iteration given find the latest one in the list
            possible_iterations = {
                it
                for u_id, p_id, it in self.scheduled_pipelines
                if u_id == user_id and p_id == project_id
            }
            if not possible_iterations:
                raise SchedulerError(
                    f"There are no pipeline scheduled for {user_id}:{project_id}"
                )
            iteration = max(possible_iterations)

        # mark the scheduled pipeline for stopping
        self.scheduled_pipelines[
            (user_id, project_id, iteration)
        ].mark_for_cancellation = True
        # ensure the scheduler starts right away
        self._wake_up_scheduler_now()

    async def schedule_all_pipelines(self) -> None:
        self.wake_up_event.clear()
        # if one of the task throws, the other are NOT cancelled which is what we want
        await asyncio.gather(
            *[
                self._schedule_pipeline(
                    user_id,
                    project_id,
                    iteration,
                    pipeline_params.mark_for_cancellation,
                )
                for (
                    user_id,
                    project_id,
                    iteration,
                ), pipeline_params in self.scheduled_pipelines.items()
            ]
        )

    async def _get_pipeline_dag(self, project_id: ProjectID) -> nx.DiGraph:
        comp_pipeline_repo: CompPipelinesRepository = get_repository(
            self.db_engine, CompPipelinesRepository
        )  # type: ignore
        pipeline_at_db: CompPipelineAtDB = await comp_pipeline_repo.get_pipeline(
            project_id
        )
        pipeline_dag = pipeline_at_db.get_graph()
        return pipeline_dag

    async def _get_pipeline_tasks(
        self, project_id: ProjectID, pipeline_dag: nx.DiGraph
    ) -> Dict[str, CompTaskAtDB]:
        comp_tasks_repo: CompTasksRepository = get_repository(
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

    async def _update_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        pipeline_tasks: Dict[str, CompTaskAtDB],
    ) -> RunningState:

        pipeline_state_from_tasks = get_pipeline_state_from_task_states(
            list(pipeline_tasks.values()),
        )

        comp_runs_repo: CompRunsRepository = get_repository(
            self.db_engine, CompRunsRepository
        )  # type: ignore
        await comp_runs_repo.set_run_result(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
            result_state=pipeline_state_from_tasks,
            final_state=(pipeline_state_from_tasks in COMPLETED_STATES),
        )
        return pipeline_state_from_tasks

    @abstractmethod
    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        comp_tasks: Dict[str, CompTaskAtDB],
        tasks: List[NodeID],
    ) -> None:
        pass

    @abstractmethod
    async def _stop_tasks(self, tasks: List[CompTaskAtDB]) -> None:
        pass

    async def _schedule_pipeline(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        marked_for_stopping: bool,
    ) -> None:
        logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            project_id,
            iteration,
            user_id,
        )

        pipeline_dag = nx.DiGraph()
        pipeline_tasks: Dict[str, CompTaskAtDB] = {}
        pipeline_result: RunningState = RunningState.UNKNOWN
        try:
            pipeline_dag = await self._get_pipeline_dag(project_id)
            pipeline_tasks: Dict[str, CompTaskAtDB] = await self._get_pipeline_tasks(
                project_id, pipeline_dag
            )

            # filter out the tasks with what were already completed
            pipeline_dag.remove_nodes_from(
                {
                    node_id
                    for node_id, t in pipeline_tasks.items()
                    if t.state in COMPLETED_STATES
                }
            )

            # update the current status of the run
            pipeline_result = await self._update_run_result(
                user_id, project_id, iteration, pipeline_tasks
            )
        except PipelineNotFoundError:
            logger.warning(
                "pipeline %s does not exist in comp_pipeline table, it will be removed from scheduler",
                project_id,
            )

        if not pipeline_dag.nodes():
            # there is nothing left, the run is completed, we're done here
            self.scheduled_pipelines.pop((user_id, project_id, iteration))
            logger.info(
                "pipeline %s scheduling completed with result %s",
                project_id,
                pipeline_result,
            )
            return

        if marked_for_stopping:
            # get any running task and stop them
            comp_tasks_repo: CompTasksRepository = get_repository(
                self.db_engine, CompTasksRepository
            )  # type: ignore
            await comp_tasks_repo.mark_project_tasks_as_aborted(project_id)
            # stop any remaining running task
            running_tasks = [
                t
                for t in pipeline_tasks.values()
                if t.state in [RunningState.STARTED, RunningState.RETRY]
            ]
            await self._stop_tasks(running_tasks)
            # the scheduled pipeline will be removed in the next iteration
            return

        # find the next tasks that should be run now,
        # this tasks are in PUBLISHED state and all their dependents are completed
        next_tasks: List[NodeID] = [
            node_id
            for node_id, degree in pipeline_dag.in_degree()  # type: ignore
            if degree == 0 and pipeline_tasks[node_id].state == RunningState.PUBLISHED
        ]
        if not next_tasks:
            # nothing to run at the moment
            return

        # let's schedule the tasks, mark them as PENDING so the sidecar will take them
        await self._start_tasks(user_id, project_id, pipeline_tasks, next_tasks)

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()
