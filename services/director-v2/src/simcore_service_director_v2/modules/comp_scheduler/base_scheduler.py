"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next worker task(s), either one at a time or as a group of tasks.

In principle the Scheduler maintains the comp_runs table in the database.
It contains how the pipeline was run and by whom.
It also contains the final result of the pipeline run.

When a pipeline is scheduled first all the tasks contained in the DAG are set to PUBLISHED state.
Once the scheduler determines a task shall run, its state is set to PENDING, so that the sidecar can pick up the task.
The sidecar will then change the state to STARTED, then to SUCCESS or FAILED.

"""
import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, cast

import networkx as nx
from aiopg.sa.engine import Engine
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ...core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalBackendTaskNotFoundError,
    ComputationalSchedulerChangedError,
    InsuficientComputationalResourcesError,
    InvalidPipelineError,
    MissingComputationalResourcesError,
    PipelineNotFoundError,
    SchedulerError,
)
from ...models.domains.comp_pipelines import CompPipelineAtDB
from ...models.domains.comp_runs import CompRunsAtDB
from ...models.domains.comp_tasks import CompTaskAtDB, Image
from ...models.schemas.constants import ClusterID, UserID
from ...utils.computations import get_pipeline_state_from_task_states
from ...utils.scheduler import COMPLETED_STATES, Iteration, get_repository
from ..db.repositories.comp_pipelines import CompPipelinesRepository
from ..db.repositories.comp_runs import CompRunsRepository
from ..db.repositories.comp_tasks import CompTasksRepository

logger = logging.getLogger(__name__)


async def _parse_task_states(
    node_ids: List[NodeID], pipeline_tasks: Dict[str, CompTaskAtDB]
) -> Tuple[Set[NodeID], Set[NodeID]]:
    # parse task states
    tasks_in_execution: Set[NodeID] = set()
    tasks_failed: Set[NodeID] = set()
    tasks_to_start: Set[NodeID] = set()
    for node_id in node_ids:
        if pipeline_tasks[f"{node_id}"].state == RunningState.FAILED:
            tasks_failed.add(node_id)
        elif pipeline_tasks[f"{node_id}"].state == RunningState.PUBLISHED:
            # the nodes that are published shall be started
            tasks_to_start.add(node_id)
        elif pipeline_tasks[f"{node_id}"].state in (
            RunningState.STARTED,
            RunningState.PENDING,
        ):
            tasks_in_execution.add(node_id)
    return (tasks_to_start, tasks_failed)


@dataclass
class ScheduledPipelineParams:
    cluster_id: ClusterID
    mark_for_cancellation: bool = False


@dataclass
class BaseCompScheduler(ABC):
    scheduled_pipelines: Dict[
        Tuple[UserID, ProjectID, Iteration], ScheduledPipelineParams
    ]
    db_engine: Engine
    wake_up_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    default_cluster_id: ClusterID

    async def run_new_pipeline(
        self, user_id: UserID, project_id: ProjectID, cluster_id: ClusterID
    ) -> None:
        """Sets a new pipeline to be scheduled on the computational resources.
        Passing cluster_id=0 will use the default cluster. Passing an existing ID will instruct
        the scheduler to run the tasks on the defined cluster"""
        # ensure the pipeline exists and is populated with something
        dag = await self._get_pipeline_dag(project_id)
        if not dag:
            logger.warning(
                "project %s has no computational dag defined. not scheduled for a run.",
                f"{project_id=}",
            )
            return

        runs_repo: CompRunsRepository = get_repository(
            self.db_engine, CompRunsRepository
        )  # type: ignore
        new_run: CompRunsAtDB = await runs_repo.create(
            user_id=user_id,
            project_id=project_id,
            cluster_id=cluster_id,
            default_cluster_id=self.default_cluster_id,
        )
        self.scheduled_pipelines[
            (user_id, project_id, new_run.iteration)
        ] = ScheduledPipelineParams(cluster_id=cluster_id)
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
                    pipeline_params.cluster_id,
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
            raise InvalidPipelineError(
                f"{project_id}"
                f"The tasks defined for {project_id} do not contain all the tasks defined in the pipeline [{list(pipeline_dag.nodes)}]! Please check."
            )
        return pipeline_comp_tasks

    async def _update_run_result_from_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        pipeline_tasks: Dict[str, CompTaskAtDB],
    ) -> RunningState:

        pipeline_state_from_tasks: RunningState = get_pipeline_state_from_task_states(
            list(pipeline_tasks.values()),
        )
        await self._set_run_result(
            user_id, project_id, iteration, pipeline_state_from_tasks
        )
        return pipeline_state_from_tasks

    async def _set_run_result(
        self,
        user_id: UserID,
        project_id: ProjectID,
        iteration: PositiveInt,
        run_result: RunningState,
    ) -> None:
        comp_runs_repo: CompRunsRepository = get_repository(
            self.db_engine, CompRunsRepository
        )  # type: ignore
        await comp_runs_repo.set_run_result(
            user_id=user_id,
            project_id=project_id,
            iteration=iteration,
            result_state=run_result,
            final_state=(run_result in COMPLETED_STATES),
        )

    async def _update_states_from_comp_backend(
        self, cluster_id: ClusterID, project_id: ProjectID, pipeline_dag: nx.DiGraph
    ):
        pipeline_tasks: Dict[str, CompTaskAtDB] = await self._get_pipeline_tasks(
            project_id, pipeline_dag
        )
        tasks_completed: List[CompTaskAtDB] = []
        if tasks_supposedly_processing := [
            task
            for task in pipeline_tasks.values()
            if task.state in [RunningState.STARTED, RunningState.PENDING]
        ]:
            # ensure these tasks still exist in the backend, if not we abort these
            tasks_backend_status = await self._get_tasks_status(
                cluster_id, tasks_supposedly_processing
            )
            for task, backend_state in zip(
                tasks_supposedly_processing, tasks_backend_status
            ):
                if backend_state == RunningState.UNKNOWN:
                    tasks_completed.append(task)
                    # these tasks should be running but they are not available in the backend, something bad happened
                    logger.error(
                        "Project %s: %s has %s. The task disappeared from the dask-scheduler"
                        ", aborting the computational pipeline!\n"
                        "TIP: Check if the connected dask-scheduler was restarted.",
                        f"{project_id}",
                        f"{task=}",
                        f"{backend_state=}",
                    )
                elif backend_state in COMPLETED_STATES:
                    tasks_completed.append(task)
        if tasks_completed:
            await self._process_completed_tasks(cluster_id, tasks_completed)

    @abstractmethod
    async def _start_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        scheduled_tasks: Dict[NodeID, Image],
        callback: Callable[[], None],
    ) -> None:
        ...

    @abstractmethod
    async def _get_tasks_status(
        self, cluster_id: ClusterID, tasks: List[CompTaskAtDB]
    ) -> List[RunningState]:
        ...

    @abstractmethod
    async def _stop_tasks(
        self, cluster_id: ClusterID, tasks: List[CompTaskAtDB]
    ) -> None:
        ...

    @abstractmethod
    async def _process_completed_tasks(
        self, cluster_id: ClusterID, tasks: List[CompTaskAtDB]
    ) -> None:
        ...

    async def _schedule_pipeline(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        iteration: PositiveInt,
        marked_for_stopping: bool,
    ) -> None:
        logger.debug(
            "checking run of project [%s:%s] for user [%s]",
            f"{project_id=}",
            f"{iteration=}",
            f"{user_id=}",
        )

        dag = nx.DiGraph()
        comp_tasks: Dict[str, CompTaskAtDB] = {}
        pipeline_result: RunningState = RunningState.UNKNOWN
        tasks_to_start: Set[NodeID] = set()

        try:
            dag = await self._get_pipeline_dag(project_id)
            # 1. Update our list of tasks with data from backend (state, results)
            await self._update_states_from_comp_backend(cluster_id, project_id, dag)

            # 2. now find what needs to be scheduled
            comp_tasks: Dict[str, CompTaskAtDB] = await self._get_pipeline_tasks(
                project_id, dag
            )
            # filter the dag to represent the current tasks still to be scheduled
            dag.remove_nodes_from(
                {
                    node_id
                    for node_id, t in comp_tasks.items()
                    if t.state == RunningState.SUCCESS
                }
            )
            # find the tasks that need scheduling (these are the ones with no unfilled dependency, e.g. degree 0)
            tasks_to_schedule = [node_id for node_id, degree in dag.in_degree() if degree == 0]  # type: ignore
            tasks_to_start, tasks_failed = await _parse_task_states(
                tasks_to_schedule, comp_tasks
            )

            # NOTE: if we have a FAILED task, then all
            # the tasks following it are marked as ABORTED tasks
            tasks_following_failed_tasks: Set[NodeID] = set()
            for node_id in tasks_failed:
                comp_tasks[f"{node_id}"].state = RunningState.FAILED
                tasks_following_failed_tasks.update(nx.bfs_tree(dag, node_id))
                # remove the failed task from that list of nodes
                tasks_following_failed_tasks.remove(node_id)
            # mark now the aborted ones (that follow a failed one)
            for node_id in tasks_following_failed_tasks:
                comp_tasks[f"{node_id}"].state = RunningState.ABORTED

            # update the current states back in DB
            comp_tasks_repo: CompTasksRepository = cast(
                CompTasksRepository,
                get_repository(self.db_engine, CompTasksRepository),
            )
            if tasks_following_failed_tasks:
                await comp_tasks_repo.set_project_tasks_state(
                    project_id, list(tasks_following_failed_tasks), RunningState.ABORTED
                )
            if tasks_failed:
                await comp_tasks_repo.set_project_tasks_state(
                    project_id, list(tasks_failed), RunningState.FAILED
                )

            # compute and update the current status of the run
            pipeline_result = await self._update_run_result_from_tasks(
                user_id, project_id, iteration, comp_tasks
            )
        except PipelineNotFoundError:
            logger.warning(
                "pipeline %s does not exist in comp_pipeline table, it will be removed from scheduler",
                f"{project_id=}",
            )
            pipeline_result = RunningState.ABORTED
            await self._set_run_result(user_id, project_id, iteration, pipeline_result)
        except InvalidPipelineError as exc:
            logger.warning(
                "pipeline %s appears to be misconfigured, it will be removed from scheduler. Please check pipeline:\n%s",
                f"{project_id=}",
                exc,
            )
            pipeline_result = RunningState.ABORTED
            await self._set_run_result(user_id, project_id, iteration, pipeline_result)

        # 2. Are we finished??
        if not dag.nodes() or pipeline_result in COMPLETED_STATES:
            # there is nothing left, the run is completed, we're done here
            self.scheduled_pipelines.pop((user_id, project_id, iteration), None)
            logger.info(
                "pipeline %s scheduling completed with result %s",
                f"{project_id=}",
                f"{pipeline_result=}",
            )
            return

        # 3. Are we stopping??
        if marked_for_stopping:
            await self._schedule_tasks_to_stop(project_id, cluster_id, comp_tasks)
            # the scheduled pipeline will be removed in the next iteration
        else:
            # 4. Schedule the next tasks,
            await self._schedule_next_tasks(
                user_id, project_id, cluster_id, comp_tasks, list(tasks_to_start)
            )

    async def _schedule_tasks_to_stop(
        self,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks_to_stop: Dict[str, CompTaskAtDB],
    ) -> None:
        # get any running task and stop them
        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await comp_tasks_repo.mark_project_published_tasks_as_aborted(project_id)
        # stop any remaining running task, these are already submitted
        running_tasks = [
            t
            for t in tasks_to_stop.values()
            if t.state
            in [RunningState.STARTED, RunningState.RETRY, RunningState.PENDING]
        ]
        try:
            await self._stop_tasks(cluster_id, running_tasks)
        except (
            ComputationalBackendNotConnectedError,
            ComputationalSchedulerChangedError,
            ComputationalBackendTaskNotFoundError,
        ):
            logger.error("ISSUE WHILE STOPPING")
            # logger.error("%s", exc)
            # await comp_tasks_repo.set_project_tasks_state(
            #     project_id,
            #     [NodeID(k) for k in tasks_to_stop.keys()],
            #     RunningState.ABORTED,
            # )
        except asyncio.CancelledError:
            logger.warning(
                "The task stopping was cancelled, there might be still be running tasks!"
            )
            raise
        logger.debug(
            "pipeline '%s' is marked for cancellation. stopping tasks for [%s]",
            f"{project_id=}",
            f"{running_tasks=}",
        )

    async def _schedule_next_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        comp_tasks: Dict[str, CompTaskAtDB],
        tasks: List[NodeID],
    ):
        if not tasks:
            # nothing to do
            return
        # get tasks runtime requirements
        tasks_to_reqs: Dict[NodeID, Image] = {
            node_id: comp_tasks[f"{node_id}"].image for node_id in tasks
        }

        # The sidecar only pick up tasks that are in PENDING state
        comp_tasks_repo: CompTasksRepository = get_repository(
            self.db_engine, CompTasksRepository
        )  # type: ignore
        await comp_tasks_repo.set_project_tasks_state(
            project_id, tasks, RunningState.PENDING
        )

        # we pass the tasks to the dask-client
        results = await asyncio.gather(
            *[
                self._start_tasks(
                    user_id,
                    project_id,
                    cluster_id,
                    scheduled_tasks={t: r},
                    callback=self._wake_up_scheduler_now,
                )
                for t, r in tasks_to_reqs.items()
            ],
            return_exceptions=True,
        )
        for r, t in zip(results, tasks_to_reqs):
            if isinstance(
                r,
                (
                    MissingComputationalResourcesError,
                    InsuficientComputationalResourcesError,
                ),
            ):
                logger.error(
                    "Project '%s''s task '%s' could not be scheduled due to the following: %s",
                    project_id,
                    r.node_id,
                    f"{r}",
                )
                await comp_tasks_repo.set_project_tasks_state(
                    project_id, [r.node_id], RunningState.FAILED
                )
                # TODO: we should set some specific state so the user may know what to do
            elif isinstance(
                r,
                (
                    ComputationalBackendNotConnectedError,
                    ComputationalSchedulerChangedError,
                ),
            ):
                logger.error(
                    "Issue with computational backend: %s. Tasks are set back "
                    "to PUBLISHED state until scheduler comes back!",
                    r,
                )
                # we should try re-connecting.
                # in the meantime we cannot schedule tasks on the scheduler,
                # let's put these tasks back to PUBLISHED, so they might be re-submitted later
                await asyncio.gather(
                    comp_tasks_repo.set_project_tasks_state(
                        project_id, tasks, RunningState.PUBLISHED
                    ),
                )
            elif isinstance(r, Exception):
                logger.error(
                    "Unexpected error for %s with %s on %s happened when scheduling %s:\n%s\n%s",
                    f"{user_id=}",
                    f"{project_id=}",
                    f"{cluster_id=}",
                    f"{tasks=}",
                    f"{r}",
                    "".join(traceback.format_tb(r.__traceback__)),
                )
                await comp_tasks_repo.set_project_tasks_state(
                    project_id, [t], RunningState.FAILED
                )

    def _wake_up_scheduler_now(self) -> None:
        self.wake_up_event.set()
